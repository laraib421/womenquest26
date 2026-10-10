# WTQ Build Track — Utility Bill Decoder

An AI assistant that reads K-Electric (KE), LESCO and IESCO electricity bills (as images)
and (1) extracts structured billing details into JSON, and (2) answers plain-English
customer questions about a bill, grounded in the extracted data and code-computed facts.

## Requirements

- Python 3.12 (3.11+ required)
- A Gemini API key (free tier works — see `.env.example`)

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your real API key:

```
GEMINI_API_KEY=your-real-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

## Run

Both commands take a folder of bill images and the competition's CSV templates, and
write the completed CSVs. Results are cached per bill ID in `data/.cache/` so reruns
don't repeat API calls.

**Level 1 — extract bill details:**
```bash
python run.py level1 --bills <bills_folder> --template <level1_template.csv> --out output/level1.csv
```

**Level 2 — answer customer questions:**
```bash
python run.py level2 --bills <bills_folder> --template <level2_template.csv> --out output/level2.csv
```

**Both in one command:**
```bash
python run.py all --bills <bills_folder> \
  --level1-template <level1_template.csv> --level1-out output/level1.csv \
  --level2-template <level2_template.csv> --level2-out output/level2.csv
```

Example, using the competition's test folder layout:
```bash
python run.py all --bills test/bills \
  --level1-template test/csv/level1.csv --level1-out output/level1.csv \
  --level2-template test/csv/level2.csv --level2-out output/level2.csv
```

## How it works

- **`llm.py`** — thin wrapper around the Gemini API (OpenAI-compatible endpoint), with
  text and vision calls, JSON parsing/validation, and a built-in rate limiter + retry
  (free tier is 15 requests/min).
- **`bill_decoder/schema.py`** — Pydantic model for the required Level 1 JSON shape.
- **`bill_decoder/extract.py`** — Level 1: one vision call per bill reads the image and
  returns the structured JSON directly (provider, charges, taxes, readings, etc.), plus
  the monthly usage-history chart when present, used only internally for Level 2.
- **`bill_decoder/stats.py`** — deterministic, code-computed facts from the extracted
  data (tax %, cost per unit, late-payment surcharge, months above a usage threshold,
  month-over-month change, etc.) — calculations are done in Python, not guessed by the
  model, per the competition's recommendation.
- **`bill_decoder/qa.py`** — Level 2: answers each question using only the extracted
  bill data and the pre-computed facts above, so the model explains and phrases rather
  than calculates from scratch.
- **`bill_decoder/pipeline.py`** / **`run.py`** — reads the CSV templates, runs
  extraction/Q&A per row, writes the completed CSVs with correct quoting/escaping.

Every number reported in a Level 2 answer that requires arithmetic (percentages, sums,
counts, month-over-month changes) is computed in `stats.py`, not by the LLM, to avoid
AI arithmetic errors. The model is only asked to read the image (Level 1) and to
explain/phrase already-computed numbers in plain English (Level 2).

## AI usage

- **Model used in the solution:** Google Gemini, `gemini-3.5-flash-lite`, via the
  OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`).
  Used for both Level 1 (vision — reading the bill image) and Level 2 (text — phrasing
  answers from pre-computed facts).
- **Other AI services:** none. No OCR library, no invoice-extraction API — the model
  reads the bill image directly.
- **AI coding assistant used to help write this code:** Claude (Anthropic), via Claude
  Code, used throughout development to design and write the extraction prompt, the
  Pydantic schema, the stats calculations, the CSV pipeline, and this README.
