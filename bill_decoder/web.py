"""Optional web UI for the Bill Decoder: upload a bill image, see the Level 1
extraction, and ask Level 2 questions about it. Not required by the competition
(a CLI run.py satisfies the submission), but useful for the demo video."""
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .extract import extract_bill
from .qa import answer_question
from .schema import BillExtraction
from .stats import compute_stats

STATIC = Path(__file__).resolve().parent / "web_static"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "wtq_bill_decoder_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Utility Bill Decoder")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_SESSION: dict[str, BillExtraction] = {}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    dest = UPLOAD_DIR / file.filename
    dest.write_bytes(await file.read())
    bill = extract_bill(str(dest))
    _SESSION[file.filename] = bill
    return {
        "bill_id": file.filename,
        "json": bill.official_json(),
        "stats": compute_stats(bill),
        "notes": bill.notes,
    }


class AskBody(BaseModel):
    bill_id: str
    question: str


@app.post("/api/ask")
def ask(body: AskBody):
    bill = _SESSION.get(body.bill_id)
    if not bill:
        return {"error": "Upload a bill first."}
    return {"answer": answer_question(bill, body.question)}
