# Utility Bill Decoder

**WTQ 2026 Build Track submission.** An AI assistant that reads K-Electric (KE), LESCO
and IESCO electricity bill images and:

1. **Level 1 — Extraction:** pulls out billing details, readings, charges, taxes, and
   payable amounts into a strict JSON schema.
2. **Level 2 — Explanation:** answers plain-English customer questions about a bill,
   with calculations grounded in the actual bill data — not guessed.

Built with Python and Google's Gemini (`gemini-3.5-flash-lite`), a competition-allowed
model, used for both image understanding (Level 1) and natural-language answering
(Level 2).

---

## Contents

- [Quick start](#quick-start)
- [Running the pipeline](#running-the-pipeline)
- [Optional web UI](#optional-web-ui)
- [Design](#design)
- [Project layout](#project-layout)
- [Packaging the submission](#packaging-the-submission)
- [AI usage](#ai-usage)

---

## Quick start

**Requirements:** Python 3.12 (3.11+ works), a free Gemini API key.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add a real key (get one free, no card required, at
[aistudio.google.com](https://aistudio.google.com)):

```env
GEMINI_API_KEY=your-real-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Verify the setup with one test call:

```bash
python llm.py
```

---

## Running the pipeline

`run.py` takes a folder of bill images and the competition's CSV templates, and writes
the completed CSVs. Per-bill extraction results are cached in `data/.cache/`, so a
rerun after an interruption never repeats a finished bill or burns an extra API call.

```bash
# Level 1 only - extract bill details
python run.py level1 --bills <bills_folder> --template <level1_template.csv> --out output/level1.csv

# Level 2 only - answer customer questions
python run.py level2 --bills <bills_folder> --template <level2_template.csv> --out output/level2.csv

# Both, one command
python run.py all --bills <bills_folder> \
  --level1-template <level1_template.csv> --level1-out output/level1.csv \
  --level2-template <level2_template.csv> --level2-out output/level2.csv
```

**Example**, using the competition's test folder layout:

```bash
python run.py all --bills test/bills \
  --level1-template test/csv/level1.csv --level1-out output/level1.csv \
  --level2-template test/csv/level2.csv --level2-out output/level2.csv
```

A failed bill never aborts the run — it's logged and written as a null-filled row so
the output CSVs always have the full, required row count.

---

## Optional web UI

A browser UI for exploring a bill interactively and for running the exact same
pipeline with a live progress view — useful for demoing the solution.

```bash
python -m uvicorn bill_decoder.web:app --port 8001
```

Open **http://127.0.0.1:8001**:

- **Single bill** — drop in a bill image (or load one of the bundled samples), see the
  extracted fields, charges, taxes and a 12-month usage chart, then ask it questions.
- **Run full batch** — point at a bills folder and the two CSV templates, click Start,
  and watch Level 1 and Level 2 run with live progress bars and a streaming log. This
  calls the same `run_level1()` / `run_level2()` functions as the CLI, so results are
  identical either way.

This UI is entirely optional — it's not required to produce the submission CSVs — but
it's the easiest way to record the demo video, since one screen can show the bill
image, the extracted fields, a few Level 2 answers, and the CSVs being generated.

---

## Design

**Two-pass extraction, not one.** Level 1 is a single vision call per bill: the model
reads the image directly and returns the required JSON. No OCR library, no
invoice-extraction API — just the model reading pixels.

**Code computes, the model explains.** Every number a Level 2 answer needs — tax
percentage, cost per unit, late-payment surcharge, months above a usage threshold,
month-over-month change — is calculated deterministically in
[`bill_decoder/stats.py`](bill_decoder/stats.py), in plain Python. The model is only
ever asked to phrase an already-correct number in plain English, never to do the
arithmetic itself. This is the single biggest lever against AI hallucination in the
answers, and it's why the output includes exact figures like "a 31.3% increase" rather
than a vague approximation.

**Batched Level 2 answering.** All of a bill's questions are answered in one API call
(a JSON map of `question_id → answer`), not one call per question. For a 10-bill,
12-question test set that's 20 total calls instead of ~130 — well inside the free
tier's 15 requests/minute limit, and roughly 6x faster. If the batched response is
missing or malformed for any individual question, that question is automatically
retried on its own, so no CSV cell is ever left blank.

**Strict extraction rules, not best-effort guessing.** The Level 1 prompt encodes the
competition's exact rules: numbers not strings, credits/subsidies as negative, `null`
for anything not printed or unreadable (never a guess), `[]` for taxes only when the
bill prints a single combined figure (with that figure going to `total_taxes`
instead), the highest of several late-payment tiers, and no personal identifiers in
the output. These were checked field-by-field against the guide's worked example
(`KESC_0008`) and matched exactly.

**Resilience.** A built-in rate limiter and retry in [`llm.py`](llm.py) keep every call
under the free tier's limit automatically. Any single bill that fails to extract or
answer doesn't stop the run — it's logged and the row is written with sensible
fallback content, so a submission is never missing a required row.

---

## Project layout

```
llm.py                       Gemini wrapper: text + vision calls, JSON parsing,
                              rate limiting and retry
run.py                       CLI entry point
package_submission.py        Builds the final submission.zip

bill_decoder/
  schema.py                  Pydantic model for the Level 1 JSON shape
  extract.py                 Level 1: vision call -> structured JSON
  stats.py                   Code-computed facts used to ground Level 2 answers
  qa.py                      Level 2: batched question answering
  pipeline.py                CSV read/write orchestration, per-bill caching
  batch.py                   Background job runner for the web UI's progress view
  web.py                     Optional FastAPI web UI
  web_static/                UI frontend (HTML/CSS/JS)
```

---

## Packaging the submission

Once `output/level1.csv` and `output/level2.csv` hold the real test-data results
(and an optional `demo/demo.mp4` has been recorded), build the submission ZIP:

```bash
python package_submission.py
```

This assembles `output/`, `source/` (all project code, README, `.env.example`) and an
optional `demo/` into `submission.zip` in the exact structure the competition expects,
and checks the 15 MB size limit before you upload.

---

## AI usage

- **Model used in the solution:** Google Gemini, `gemini-3.5-flash-lite`, via the
  OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`).
  Used for both Level 1 (vision — reading the bill image) and Level 2 (text — phrasing
  pre-computed facts into an answer).
- **Other AI services:** none. No OCR library, no third-party invoice-extraction API —
  the model reads the bill image directly.
- **AI coding assistant used to write this code:** Claude (Anthropic), via Claude Code,
  used throughout development to design and write the extraction prompt, the Pydantic
  schema, the stats calculations, the CSV pipeline, the web UI, and this README.
