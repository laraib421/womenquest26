"""Level 2: answer customer questions about a bill in plain English, grounded in
the extracted data and pre-computed (code-calculated) stats.

All questions for one bill are answered in a SINGLE call (batched) instead of one
call per question - same grounding, ~12x fewer API calls, much faster on the free
tier's 15 requests/min limit. Falls back to one-by-one calls for any question the
batch call fails to answer."""
import json

from llm import ask, ask_json

from .schema import BillExtraction
from .stats import compute_stats

RULES = (
    "Answer each question in clear, plain English, using ONLY the DATA and COMPUTED FACTS given below - "
    "never outside tariff or rate knowledge. The COMPUTED FACTS were calculated in code from the bill, so "
    "quote them exactly rather than recalculating. If a value needed to answer is not present in the data, "
    "say so plainly instead of guessing. If you must estimate, label it clearly as an estimate and explain "
    "how you got it. If a question could reasonably mean more than one thing, state which meaning you used. "
    "Do not mention names, addresses, CNIC, or account/meter numbers. Keep each answer concise (2-4 "
    "sentences) and specific, citing exact PKR amounts and percentages where relevant. When referring to a "
    "month from usage_history, write it naturally (e.g. 'July 2025'), not YYYY-MM. Always answer in "
    "English, even though parts of the bill may be in Urdu."
)

SYSTEM_BATCH = (
    "You are a helpful customer service assistant explaining a Pakistani electricity bill, answering "
    "several customer questions about the SAME bill at once. " + RULES +
    " Answer every question independently and completely - do not skip any, and do not let one answer "
    "reference 'see above'."
)

SYSTEM_SINGLE = "You are a helpful customer service assistant explaining a Pakistani electricity bill. " + RULES


def _context(bill: BillExtraction) -> str:
    data = bill.official_json()
    data["usage_history"] = bill.usage_history
    if bill.notes:
        data["notes"] = bill.notes
    stats = compute_stats(bill)
    return (
        f"BILL DATA (extracted from the image):\n{json.dumps(data, indent=2, default=str)}\n\n"
        f"COMPUTED FACTS (exact, calculated in code from the bill data above):\n"
        f"{json.dumps(stats, indent=2, default=str)}"
    )


def answer_question(bill: BillExtraction, question: str) -> str:
    """Single-question call (used by the web UI's free-form 'ask' box)."""
    prompt = f"{_context(bill)}\n\nCUSTOMER QUESTION: {question}"
    return ask(prompt, system=SYSTEM_SINGLE, max_tokens=500).strip()


def answer_questions_batch(bill: BillExtraction, questions: list[dict]) -> dict:
    """questions: [{"question_id": "Q1", "question": "..."}, ...]
    Returns {question_id: answer_text}. Falls back to per-question calls for any
    id missing or empty in the batch response, so a partial/malformed batch never
    silently loses an answer."""
    numbered = "\n".join(f'{q["question_id"]}: {q["question"]}' for q in questions)
    prompt = (
        f"{_context(bill)}\n\nCUSTOMER QUESTIONS:\n{numbered}\n\n"
        'Respond with JSON: {"answers": {"Q1": "...", "Q2": "...", ...}} - one key per question id above, '
        "every key present."
    )
    results: dict[str, str] = {}
    try:
        data = ask_json(prompt, system=SYSTEM_BATCH, max_tokens=4000)
        raw = data.get("answers", {}) if isinstance(data, dict) else {}
        # Only nonempty text is an answer. Retry malformed values rather than
        # submitting a number or a Python representation of a nested object.
        if isinstance(raw, dict):
            results = {k: v.strip() for k, v in raw.items()
                       if isinstance(v, str) and v.strip()}
    except Exception:
        pass  # fall through to per-question retry below for everything

    missing = [q for q in questions if not results.get(q["question_id"], "").strip()]
    for q in missing:
        try:
            answer = answer_question(bill, q["question"])
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Single-question retry returned no text answer")
            results[q["question_id"]] = answer.strip()
        except Exception as e:
            results[q["question_id"]] = f"Could not generate an answer ({str(e)[:100]})."
    return results
