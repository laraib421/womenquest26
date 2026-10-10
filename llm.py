import base64
import json
import mimetypes
import os
import threading
import time

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()

# WTQ 2026 allowed Gemini models: gemini-3.5-flash-lite, gemini-3.1-flash-lite
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Free tier is 15 requests/min. Stay a little under that across all callers/threads.
_RATE_LIMIT_PER_MIN = 14
_call_times = []
_rate_lock = threading.Lock()


def _throttle():
    with _rate_lock:
        now = time.time()
        _call_times[:] = [t for t in _call_times if now - t < 60]
        if len(_call_times) >= _RATE_LIMIT_PER_MIN:
            sleep_for = 60 - (now - _call_times[0]) + 0.5
        else:
            sleep_for = 0
        _call_times.append(now + sleep_for)
    if sleep_for > 0:
        time.sleep(sleep_for)


def _client(timeout=30):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=timeout, max_retries=2)


def _with_retry(fn, retries=4):
    for attempt in range(retries):
        _throttle()
        try:
            return fn()
        except RateLimitError:
            if attempt == retries - 1:
                raise
            time.sleep(8 * (attempt + 1))


def _model():
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def _extract_text(resp):
    text = resp.choices[0].message.content
    if not text or not text.strip():
        raise RuntimeError("Gemini returned an empty response")
    return text


def ask(prompt, system="You are a helpful assistant.", max_tokens=1000):
    resp = _with_retry(lambda: _client().chat.completions.create(
        model=_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    ))
    return _extract_text(resp)


def _image_data_url(image_path):
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def ask_vision(image_path, prompt, system="You are a helpful assistant.", max_tokens=2000, timeout=60):
    """Ask a question about an image (vision call)."""
    resp = _with_retry(lambda: _client(timeout=timeout).chat.completions.create(
        model=_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            },
        ],
    ))
    return _extract_text(resp)


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"Model did not return valid JSON:\n{text[:400]}")


def ask_json(prompt, system="", schema=None, max_tokens=1500):
    """Ask for JSON only. Optionally validate with a pydantic model."""
    system = system + "\nRespond with valid JSON only. No explanation, no markdown fences."
    data = _parse_json(ask(prompt, system=system, max_tokens=max_tokens))
    return schema(**data) if schema else data


def ask_json_vision(image_path, prompt, system="", schema=None, max_tokens=2500, timeout=60):
    """Ask a question about an image and get JSON back. Optionally validate with a pydantic model."""
    system = system + "\nRespond with valid JSON only. No explanation, no markdown fences."
    data = _parse_json(ask_vision(image_path, prompt, system=system, max_tokens=max_tokens, timeout=timeout))
    return schema(**data) if schema else data


if __name__ == "__main__":
    print(ask("Say hello in one sentence."))
