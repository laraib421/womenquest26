"""Optional web UI for the Bill Decoder: upload a bill image, see the Level 1
extraction, and ask Level 2 questions about it. Not required by the competition
(a CLI run.py satisfies the submission), but useful for the demo video."""
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import batch
from .extract import extract_bill
from .pipeline import get_or_extract
from .qa import answer_question
from .schema import BillExtraction
from .stats import compute_stats

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "web_static"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "wtq_bill_decoder_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
SAMPLES_DIR = ROOT / "data" / "train" / "bills"
SAMPLES_CACHE = ROOT / "data" / ".cache"

app = FastAPI(title="Utility Bill Decoder")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_SESSION: dict[str, BillExtraction] = {}


def _payload(bill_id: str, bill: BillExtraction) -> dict:
    return {
        "bill_id": bill_id,
        "json": bill.official_json(),
        "stats": compute_stats(bill),
        "usage_history": bill.usage_history,
        "notes": bill.notes,
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/samples")
def list_samples():
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.name for p in SAMPLES_DIR.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))


@app.get("/api/samples/{name}")
def sample_image(name: str):
    p = SAMPLES_DIR / name
    if not p.exists():
        raise HTTPException(404, "Sample not found")
    return FileResponse(p)


@app.post("/api/samples/{name}/load")
def load_sample(name: str):
    p = SAMPLES_DIR / name
    if not p.exists():
        raise HTTPException(404, "Sample not found")
    bill = get_or_extract(SAMPLES_DIR, SAMPLES_CACHE, p.stem)
    _SESSION[name] = bill
    return _payload(name, bill)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    dest = UPLOAD_DIR / file.filename
    dest.write_bytes(await file.read())
    try:
        bill = extract_bill(str(dest))
    except Exception as e:
        raise HTTPException(502, f"Could not read this bill: {str(e)[:200]}")
    _SESSION[file.filename] = bill
    return _payload(file.filename, bill)


class AskBody(BaseModel):
    bill_id: str
    question: str


@app.post("/api/ask")
def ask(body: AskBody):
    bill = _SESSION.get(body.bill_id)
    if not bill:
        raise HTTPException(400, "Upload a bill first.")
    try:
        return {"answer": answer_question(bill, body.question)}
    except Exception as e:
        raise HTTPException(502, f"Could not answer: {str(e)[:200]}")


class BatchBody(BaseModel):
    bills_dir: str
    level1_template: str
    level2_template: str
    level1_out: str = "output/level1.csv"
    level2_out: str = "output/level2.csv"


def _resolve(p: str) -> str:
    path = Path(p)
    return str(path if path.is_absolute() else ROOT / path)


@app.post("/api/batch/run")
def batch_run(body: BatchBody):
    for label, p in [("bills_dir", body.bills_dir), ("level1_template", body.level1_template),
                      ("level2_template", body.level2_template)]:
        if not Path(_resolve(p)).exists():
            raise HTTPException(400, f"{label} not found: {p}")
    job_id = batch.start_job(
        _resolve(body.bills_dir), _resolve(body.level1_template), _resolve(body.level1_out),
        _resolve(body.level2_template), _resolve(body.level2_out), str(ROOT / "data" / ".cache"),
    )
    return {"job_id": job_id}


@app.get("/api/batch/status/{job_id}")
def batch_status(job_id: str):
    status = batch.get_status(job_id)
    if not status:
        raise HTTPException(404, "Unknown job")
    return status
