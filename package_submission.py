"""Assemble the competition ZIP in the exact required shape:
  output/level1.csv, output/level2.csv
  source/README.md, source/.env.example, source/<project code>
  demo/demo.mp4 (if present)

Run this LAST, after output/level1.csv and output/level2.csv are the real,
final test-data results.

Usage:  python package_submission.py
"""
import argparse
import csv
import json
import math
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path

from bill_decoder.schema import BillExtraction, CHARGE_TYPES, TAX_TYPES, PROVIDERS

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "_submission_stage"
ZIP_PATH = ROOT / "submission.zip"

SOURCE_FILES = [
    "README.md", ".env.example", "requirements.txt", "llm.py", "run.py", "package_submission.py",
]
SOURCE_DIRS = ["bill_decoder"]
EXCLUDE_DIR_NAMES = {"__pycache__"}
REQUIRED_OUTPUTS = ["output/level1.csv", "output/level2.csv"]


def _read_csv(path, columns):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != columns:
                raise ValueError(f"expected columns {columns}, got {reader.fieldnames}")
            rows = list(reader)
            if any(set(row) != set(columns) or any(v is None for v in row.values()) for row in rows):
                raise ValueError("row has missing or extra cells")
            return rows
    except (OSError, UnicodeError, csv.Error, ValueError) as e:
        raise SystemExit(f"Invalid CSV {path}: {e}") from e


def _default_template(name):
    for folder in (ROOT / "data" / "test" / "csv", ROOT / "test" / "csv"):
        if (folder / name).is_file():
            return folder / name
    raise SystemExit(
        "Test templates not found. Pass --level1-template and --level2-template "
        "with the supplied test CSV paths."
    )


def _validate_bill(text, bill_id):
    try:
        if "\n" in text or "\r" in text:
            raise ValueError("JSON must be on one line")
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result
        data = json.loads(text, object_pairs_hook=unique_object)
        if not isinstance(data, dict) or set(data) != set(BillExtraction.OFFICIAL_FIELDS):
            raise ValueError("JSON must contain exactly the official fields")
        if data["provider"] is not None and data["provider"] not in PROVIDERS:
            raise ValueError("invalid provider")
        if data["tariff"] is not None and not isinstance(data["tariff"], str):
            raise ValueError("tariff must be text or null")
        for key in ("bill_month", "reading_date", "issue_date", "due_date"):
            value = data[key]
            if value is None:
                continue
            pattern = r"\d{4}-\d{2}" if key == "bill_month" else r"\d{4}-\d{2}-\d{2}"
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError(f"invalid date format: {key}")
            date.fromisoformat(value + "-01" if key == "bill_month" else value)
        text_fields = {"provider", "tariff", "bill_month", "reading_date", "issue_date", "due_date"}
        for key in set(BillExtraction.OFFICIAL_FIELDS) - text_fields - {"charges", "taxes"}:
            value = data[key]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError(f"{key} must be a finite number or null")
        for key, allowed in (("charges", CHARGE_TYPES), ("taxes", TAX_TYPES)):
            if not isinstance(data[key], list):
                raise ValueError(f"{key} must be a list")
            for line in data[key]:
                if not isinstance(line, dict) or set(line) != {"type", "amount"}:
                    raise ValueError(f"invalid {key} entry")
                if line["type"] not in allowed:
                    raise ValueError(f"invalid {key} type")
                amt = line["amount"]
                if amt is not None and (type(amt) not in (int, float) or not math.isfinite(amt)):
                    raise ValueError(f"invalid {key} amount")
        if data == BillExtraction().official_json():
            raise ValueError("null-filled extraction failure; retry this bill")
    except (ValueError, TypeError, OverflowError) as e:
        raise SystemExit(f"Invalid Level 1 JSON for {bill_id}: {e}") from e


def check_outputs(level1_template=None, level2_template=None):
    missing = [p for p in REQUIRED_OUTPUTS if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            f"Missing required output file(s): {missing}\n"
            "Run the pipeline against the REAL test data first (python run.py all ...)."
        )
    for p in REQUIRED_OUTPUTS:
        full = ROOT / p
        if full.stat().st_size == 0:
            raise SystemExit(f"{p} is empty - did the run actually finish?")
    columns1 = ["bill_id", "json"]
    columns2 = ["bill_id", "question_id", "question", "answer"]
    template1 = _read_csv(level1_template or _default_template("level1.csv"), columns1)
    template2 = _read_csv(level2_template or _default_template("level2.csv"), columns2)
    rows1 = _read_csv(ROOT / REQUIRED_OUTPUTS[0], columns1)
    rows2 = _read_csv(ROOT / REQUIRED_OUTPUTS[1], columns2)
    if len(template1) != 10 or len(template2) != 120:
        raise SystemExit("Use the real test templates: expected 10 bills and 120 questions.")
    ids = [r["bill_id"] for r in template1]
    if len(set(ids)) != 10 or any(not bill_id.strip() for bill_id in ids):
        raise SystemExit("Test Level 1 template has blank or duplicate bill IDs.")
    expected_pairs = {(bill_id, f"Q{i}") for bill_id in ids for i in range(1, 13)}
    if {(r["bill_id"], r["question_id"]) for r in template2} != expected_pairs:
        raise SystemExit("Test Level 2 template must contain Q1-Q12 for every test bill.")
    if [r["bill_id"] for r in rows1] != ids:
        raise SystemExit("Level 1 output bill IDs/count/order do not match the test template.")
    identity = lambda rows: [(r["bill_id"], r["question_id"], r["question"]) for r in rows]
    if identity(rows2) != identity(template2):
        raise SystemExit("Level 2 output IDs/questions/count/order do not match the test template.")
    for row in rows1:
        _validate_bill(row["json"], row["bill_id"])
    failure_prefixes = (
        "could not generate an answer", "sorry, this bill could not be processed",
    )
    for row in rows2:
        answer = row["answer"].strip()
        if not answer or answer.lower().startswith(failure_prefixes):
            raise SystemExit(f"Missing/failed answer for {row['bill_id']} {row['question_id']}; retry it.")
    print("Validated 10 test bills and 120 answers against the supplied templates.")


def copy_tree_filtered(src: Path, dst: Path):
    def ignore(dirpath, names):
        return [n for n in names if n in EXCLUDE_DIR_NAMES or n.endswith(".pyc")]
    shutil.copytree(src, dst, ignore=ignore)


def main():
    parser = argparse.ArgumentParser(description="Validate and package WTQ test results")
    parser.add_argument("--level1-template", help="Original test Level 1 CSV")
    parser.add_argument("--level2-template", help="Original test Level 2 CSV")
    args = parser.parse_args()
    check_outputs(args.level1_template, args.level2_template)

    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "output").mkdir(parents=True)
    (STAGE / "source").mkdir(parents=True)

    for p in REQUIRED_OUTPUTS:
        shutil.copy2(ROOT / p, STAGE / p)

    for f in SOURCE_FILES:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, STAGE / "source" / f)
        else:
            print(f"WARNING: {f} not found, skipping")

    for d in SOURCE_DIRS:
        copy_tree_filtered(ROOT / d, STAGE / "source" / d)

    demo = ROOT / "demo" / "demo.mp4"
    for ext in (".mp4", ".mov", ".webm"):
        candidate = ROOT / "demo" / f"demo{ext}"
        if candidate.exists():
            (STAGE / "demo").mkdir(exist_ok=True)
            shutil.copy2(candidate, STAGE / "demo" / candidate.name)
            print(f"Included demo: {candidate.name}")
            break
    else:
        print("No demo video found in demo/ - submitting without one (optional, -5 bonus pts).")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in STAGE.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(STAGE))

    try:
        shutil.rmtree(STAGE)
    except OSError:
        print(f"(Could not remove staging folder {STAGE} - likely OneDrive syncing it. "
              "Safe to delete manually; the ZIP itself is already written.)")

    size_mb = ZIP_PATH.stat().st_size / 1024 / 1024
    print(f"\nWrote {ZIP_PATH} ({size_mb:.2f} MB)")
    if size_mb > 15:
        print("WARNING: ZIP exceeds the 15 MB limit! Remove the demo video or large files.")
    else:
        print("Size OK (under 15 MB).")

    print("\nContents:")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for n in sorted(zf.namelist()):
            print(" ", n)


if __name__ == "__main__":
    main()
