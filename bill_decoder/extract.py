"""Level 1: extract structured billing details from a bill image."""
from llm import ask_json_vision

from .schema import BillExtraction

SYSTEM = (
    "You are an expert at reading Pakistani electricity bills (K-Electric/KE, LESCO, IESCO). "
    "You read the bill image carefully and extract exact printed values. "
    "You NEVER invent or guess a value. You NEVER recalculate or correct amounts - use what is printed."
)

PROMPT = """Read this electricity bill image and extract its details as JSON.

Return EXACTLY this JSON shape (every key present, even if its value is null):
{
  "provider": "KE | LESCO | IESCO",
  "tariff": "string, exact printed tariff code (e.g. A1-R, A-1a(01))",
  "sanctioned_load_kw": number,

  "bill_month": "YYYY-MM",
  "reading_date": "YYYY-MM-DD",
  "issue_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",

  "previous_reading": number,
  "current_reading": number,
  "units_consumed": number,

  "charges": [ {"type": "energy|fixed|fpa|quarterly_adjustment|surcharge|meter_rent|subsidy|other", "amount": number} ],
  "total_charges": number,

  "taxes": [ {"type": "gst|electricity_duty|income_tax|municipal_tax|other_tax", "amount": number} ],
  "total_taxes": number,

  "current_bill": number,
  "arrears": number,
  "payable_within_due_date": number,
  "payable_after_due_date": number,

  "usage_history": [ {"month": "YYYY-MM, inferred from the chart's year labels/groupings and bill_month", "units": number} ],
  "notes": "string or null - note anything unusual, e.g. multiple meters/net metering, torn/unclear sections"
}

RULES (follow exactly):
- Extract values AS PRINTED. Do not recalculate, round, or correct any amount.
- Amounts are numbers in PKR. Strip currency labels and commas (e.g. "Rs. 19,964" -> 19964).
- A credit/subsidy/"CR" suffix means NEGATIVE. "38209CR" -> -38209. A subsidy charge line is negative.
- Dates: "22nd Sep 2026" -> "2026-09-22". "MAR 2026" -> "2026-03". bill_month is YYYY-MM only.
- due_date is the last date to pay WITHOUT a late payment surcharge.
- Use null for any value that is not printed, blank, covered by a grey box, or unreadable. Do not guess. Use [] for an empty list.
- charges: one entry per line in the charges/bill-calculation section. Skip blank lines and lines printed as 0.
  Keep separate entries when the same type appears more than once (e.g. two energy slabs).
  - energy: cost of units used (Variable Upto ... Units, Cost of Electricity, Energy Charges)
  - fixed: fixed charges
  - fpa: fuel price adjustment (covers both FPA and FCA)
  - quarterly_adjustment: QTA / Uniform Quarterly Adjustment
  - surcharge: Additional Surcharge (PHL), F.C Surcharge, etc.
  - meter_rent: meter rent / service rent
  - subsidy: government subsidy/relief lines (record as negative)
  - other: anything else
  If the bill shows ONLY a combined total with no itemized lines, put ONE entry with the most fitting type
  (usually "energy") for that total, or if truly unclassifiable, use "other".
- total_charges: the printed charges subtotal, or null if none is printed.
- taxes: one entry per line in the tax/government section specifically (classify by SECTION, not name).
  - gst: sales tax / GST, including GST on FPA
  - electricity_duty: electricity duty (often "ED")
  - income_tax: income tax
  - municipal_tax: municipal/local charges under taxes (e.g. KE MUCT/KMC)
  - other_tax: anything else (extra tax, further tax, TV fee)
  IMPORTANT: If the bill shows only ONE combined tax figure (e.g. a single "Taxes" line with no
  itemized GST/electricity-duty/municipal-tax/income-tax lines beneath it), you MUST return
  taxes: [] (empty list) and put that single amount in total_taxes. Do NOT invent a single tax
  entry to hold it - only use entries in taxes[] when the bill itself prints separate itemized
  tax lines.
- total_taxes: the printed tax subtotal, or null if none is printed.
- current_bill: this month's bill amount as printed.
- arrears: previous dues carried forward. Keep the printed sign. null if blank.
- payable_within_due_date: amount payable by the due date.
- payable_after_due_date: amount payable after the due date. If several late-payment amounts are shown
  (e.g. 5% and 10% surcharge tiers), use the HIGHEST one. If this field prints TEXT instead of a number
  (e.g. "NOT TO BE PAID", blank, or a dash), return null - do NOT substitute any other amount from
  elsewhere on the bill.
- usage_history: the monthly usage history table/chart if present (e.g. "13 Month Usage History"), as
  [{"month": "...", "units": ...}, ...] in the order printed, oldest first. [] if not present.
  Give month as "YYYY-MM". The chart often groups bars under two year labels (e.g. "2025" then "2026")
  with the split between December and January - use that grouping, plus bill_month, to infer each year.
  The last entry is usually the current bill's own month - include it too if shown in the chart.
- Do NOT include any personal identifiers: no names, addresses, CNIC, account numbers, reference numbers,
  consumer numbers, or meter numbers anywhere in the output (most are already covered by grey boxes).
- If there are multiple meters / net-metering readings that make previous_reading/current_reading ambiguous,
  set those two fields to null, still give your best units_consumed if determinable, and explain in "notes".
"""


def extract_bill(image_path: str) -> BillExtraction:
    return ask_json_vision(image_path, PROMPT, system=SYSTEM, schema=BillExtraction, max_tokens=2500, timeout=60)
