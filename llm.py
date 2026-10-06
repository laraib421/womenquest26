import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# name -> (base_url, key env var, model env var, default model)
OPENAI_COMPATIBLE = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL", "llama-3.1-8b-instant"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-1.5-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "openai/gpt-oss-120b"),
}

LAST_PROVIDER = None  # shows which provider answered last (handy in the UI)


def _order():
    raw = os.getenv("PROVIDER_ORDER", "groq,gemini,openrouter,anthropic")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _call_openai_compatible(name, system, prompt, max_tokens):
    base_url, key_var, model_var, default_model = OPENAI_COMPATIBLE[name]
    key = os.getenv(key_var)
    if not key:
        raise RuntimeError(f"{key_var} not set")
    client = OpenAI(api_key=key, base_url=base_url, timeout=30, max_retries=0)
    resp = client.chat.completions.create(
        model=os.getenv(model_var, default_model),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content


def _call_anthropic(system, prompt, max_tokens):
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key, timeout=30, max_retries=0)
    msg = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def ask(prompt, system="You are a helpful assistant.", max_tokens=1000):
    """Try each provider in order. Move to the next on ANY failure
    (quota, rate limit, bad key, network, timeout)."""
    global LAST_PROVIDER
    errors = []
    for name in _order():
        try:
            if name == "anthropic":
                text = _call_anthropic(system, prompt, max_tokens)
            elif name in OPENAI_COMPATIBLE:
                text = _call_openai_compatible(name, system, prompt, max_tokens)
            else:
                continue
            if text and text.strip():
                LAST_PROVIDER = name
                return text
            errors.append(f"{name}: empty response")
        except Exception as e:
            errors.append(f"{name}: {str(e)[:120]}")
            print(f"[llm] {name} failed, trying next -> {str(e)[:120]}")
    raise RuntimeError("All providers failed:\n" + "\n".join(errors))


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
    print("Answered by:", LAST_PROVIDER)