"""Level 2: answer a customer question about a bill in plain English, grounded in
the extracted data and pre-computed (code-calculated) stats."""
import json

from llm import ask

from .schema import BillExtraction
from .stats import compute_stats

SYSTEM = (
    "You are a helpful customer service assistant explaining a Pakistani electricity bill. "
    "Answer the customer's question in clear, plain English, using ONLY the DATA and COMPUTED FACTS "
    "given below - never outside tariff or rate knowledge. "
    "The COMPUTED FACTS were calculated in code from the bill, so quote them exactly rather than "
    "recalculating. If a value needed to answer is not present in the data, say so plainly instead of "
    "guessing. If you must estimate, label it clearly as an estimate and explain how you got it. "
    "If the question could reasonably mean more than one thing, state which meaning you used. "
    "Do not mention names, addresses, CNIC, or account/meter numbers. Keep the answer concise (2-4 "
    "sentences) and specific, citing exact PKR amounts and percentages where relevant. "
    "When referring to a month from usage_history or dates, write it naturally (e.g. 'July 2025'), "
    "not in YYYY-MM form. Always answer in English, even though parts of the bill may be in Urdu."
)


def answer_question(bill: BillExtraction, question: str) -> str:
    stats = compute_stats(bill)
    data = bill.official_json()
    data["usage_history"] = bill.usage_history
    if bill.notes:
        data["notes"] = bill.notes
    context = (
        f"BILL DATA (extracted from the image):\n{json.dumps(data, indent=2, default=str)}\n\n"
        f"COMPUTED FACTS (exact, calculated in code from the bill data above):\n"
        f"{json.dumps(stats, indent=2, default=str)}\n\n"
        f"CUSTOMER QUESTION: {question}"
    )
    return ask(context, system=SYSTEM, max_tokens=500).strip()
