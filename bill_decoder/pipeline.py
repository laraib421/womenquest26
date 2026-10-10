"""CSV orchestration: read the competition's templates, fill them in, write results.
Extraction results are cached to disk per bill_id so a crash or rerun doesn't
repeat work (and doesn't burn extra API calls)."""
import csv
import json
import traceback
from pathlib import Path

from .extract import extract_bill
from .qa import answer_questions_batch
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


def run_level1(bills_dir: str, template_csv: str, out_csv: str, cache_dir: str, on_progress=None):
    """on_progress(done, total, bill_id, status) is called after each bill, if given."""
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
            if on_progress:
                on_progress(i, len(rows), bill_id, "ok")
        except Exception as e:
            traceback.print_exc()
            print(f"FAILED ({e}) - writing null-filled JSON")
            blank = BillExtraction().official_json()
            out_rows.append({"bill_id": bill_id, "json": json.dumps(blank, default=str)})
            if on_progress:
                on_progress(i, len(rows), bill_id, f"failed: {e}")

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bill_id", "json"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"[level1] wrote {len(out_rows)} rows -> {out_csv}")


def run_level2(bills_dir: str, template_csv: str, out_csv: str, cache_dir: str, on_progress=None):
    """Batches all questions for a bill into one API call. on_progress(done_bills,
    total_bills, bill_id, status) is called after each bill's questions are answered."""
    bills_dir, cache_dir = Path(bills_dir), Path(cache_dir)
    with open(template_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    by_bill: dict[str, list[dict]] = {}
    for row in rows:
        by_bill.setdefault(row["bill_id"].strip(), []).append(row)

    out_rows = []
    bill_ids = list(by_bill.keys())
    for bi, bill_id in enumerate(bill_ids, 1):
        bill_rows = by_bill[bill_id]
        print(f"[level2] {bi}/{len(bill_ids)} {bill_id} ({len(bill_rows)} questions) ...", end=" ", flush=True)
        try:
            bill = get_or_extract(bills_dir, cache_dir, bill_id)
            questions = [{"question_id": r.get("question_id", ""), "question": r["question"]} for r in bill_rows]
            answers = answer_questions_batch(bill, questions)
            for r in bill_rows:
                out_rows.append({
                    "bill_id": bill_id,
                    "question_id": r.get("question_id", ""),
                    "question": r["question"],
                    "answer": answers.get(r.get("question_id", ""), "Could not generate an answer."),
                })
            print("ok")
            if on_progress:
                on_progress(bi, len(bill_ids), bill_id, "ok")
        except Exception as e:
            traceback.print_exc()
            print(f"FAILED ({e})")
            for r in bill_rows:
                out_rows.append({
                    "bill_id": bill_id,
                    "question_id": r.get("question_id", ""),
                    "question": r["question"],
                    "answer": "Sorry, this bill could not be processed, so this question cannot be answered.",
                })
            if on_progress:
                on_progress(bi, len(bill_ids), bill_id, f"failed: {e}")

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bill_id", "question_id", "question", "answer"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"[level2] wrote {len(out_rows)} rows -> {out_csv}")
