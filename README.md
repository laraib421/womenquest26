# AI Challenge Starter (WTQ 2026)

A small Python wrapper around **Gemini** for the Women Tech Quest 2026 "Build with AI" challenge.

Model: `gemini-3.5-flash-lite` (allowed model; `gemini-3.1-flash-lite` is also allowed).

## Project Structure

```
.
├── llm.py            # ask() and ask_json() helpers (Gemini only)
├── check_setup.py    # pre-event readiness check
├── requirements.txt  # Python packages
├── .env              # your API key (git-ignored, never submit)
├── .env.example      # template for .env
└── README.md
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your key from https://aistudio.google.com:

```
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Check everything is ready:

```bash
python check_setup.py
```

## Usage

```python
from llm import ask, ask_json

print(ask("Explain quantum computing in one sentence."))

data = ask_json("List 3 primary colors under key 'colors'")
print(data)
```

`ask_json` accepts an optional pydantic model: `ask_json(prompt, schema=MyModel)`.

## Notes

- Free tier limits: 15 requests/min, 500 requests/day.
- Never commit `.env` or paste the key in code.

## License

MIT License
