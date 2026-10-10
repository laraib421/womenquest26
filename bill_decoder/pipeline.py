"""CSV orchestration: read the competition's templates, fill them in, write results.
Extraction results are cached to disk per bill_id so a crash or rerun doesn't
repeat work (and doesn't burn extra API calls)."""
import csv
import json
import sys
import traceback
from pathlib import Path

from .extract import extract_bill
from .qa import answer_question
from .schema import BillExtraction

IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def _find_image(bills_dir: Path, bill_id: str) -> Path:
    for ext in IMAGE_EXTS:
        p = bills_dir / f"{bill_id}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"No image found for bill_id '{bill_id}' in {bills_dir}")


def _cache_path(cache_dir: Path, bill_id: str) -> Path:
    return cache_dir / f"{bill_id}.json"


def get_or_extract(bills_dir: Path, cache_dir: Path, bill_id: str) -> BillExtraction:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(cache_dir, bill_id)
    if cp.exists():
        return BillExtraction(**json.loads(cp.read_text(encoding="utf-8")))
    image = _find_image(bills_dir, bill_id)
    bill = extract_bill(str(image))
    cp.write_text(json.dumps(bill.model_dump(), indent=2, default=str), encoding="utf-8")
    return bill


def run_level1(bills_dir: str, template_csv: str, out_csv: str, cache_dir: str):
    bills_dir, cache_dir = Path(bills_dir), Path(cache_dir)
    with open(template_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for i, row in enumerate(rows, 1):
        bill_id = row["bill_id"].strip()
        print(f"[level1] {i}/{len(rows)} {bill_id} ...", end=" ", flush=True)
        try:
            bill = get_or_extract(bills_dir, cache_dir, bill_id)
            out_rows.append({"bill_id": bill_id, "json": json.dumps(bill.official_json(), default=str)})
            print("ok")
        except Exception as e:
            traceback.print_exc()
            print(f"FAILED ({e}) - writing null-filled JSON")
            blank = BillExtraction().official_json()
            out_rows.append({"bill_id": bill_id, "json": json.dumps(blank, default=str)})

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bill_id", "json"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"[level1] wrote {len(out_rows)} rows -> {out_csv}")


def run_level2(bills_dir: str, template_csv: str, out_csv: str, cache_dir: str):
    bills_dir, cache_dir = Path(bills_dir), Path(cache_dir)
    with open(template_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    bill_cache: dict[str, BillExtraction] = {}
    out_rows = []
    for i, row in enumerate(rows, 1):
        bill_id = row["bill_id"].strip()
        question = row["question"]
        print(f"[level2] {i}/{len(rows)} {bill_id} {row.get('question_id', '')} ...", end=" ", flush=True)
        try:
            if bill_id not in bill_cache:
                bill_cache[bill_id] = get_or_extract(bills_dir, cache_dir, bill_id)
            answer = answer_question(bill_cache[bill_id], question)
            print("ok")
        except Exception as e:
            traceback.print_exc()
            answer = "Sorry, this bill could not be processed, so this question cannot be answered."
            print(f"FAILED ({e})")
        out_rows.append({
            "bill_id": bill_id,
            "question_id": row.get("question_id", ""),
            "question": question,
            "answer": answer,
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bill_id", "question_id", "question", "answer"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"[level2] wrote {len(out_rows)} rows -> {out_csv}")
