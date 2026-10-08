import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# WTQ 2026 allowed Gemini models: gemini-3.5-flash-lite, gemini-3.1-flash-lite
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def ask(prompt, system="You are a helpful assistant.", max_tokens=1000):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = OpenAI(api_key=key, base_url=BASE_URL, timeout=30, max_retries=2)
    resp = client.chat.completions.create(
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    text = resp.choices[0].message.content
    if not text or not text.strip():
        raise RuntimeError("Gemini returned an empty response")
    return text


def ask_json(prompt, system="", schema=None, max_tokens=1500):
    """Ask for JSON only. Optionally validate with a pydantic model."""
    system += "\nRespond with valid JSON only. No explanation, no markdown fences."
    text = ask(prompt, system=system, max_tokens=max_tokens)
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"Model did not return valid JSON:\n{text[:300]}")
    return schema(**data) if schema else data


if __name__ == "__main__":
    print(ask("Say hello in one sentence."))
