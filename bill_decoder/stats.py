"""Deterministic calculations over an extracted bill, computed in code (not by the
LLM) so Level 2 answers are grounded in exact numbers rather than guessed."""
from .schema import BillExtraction


def compute_stats(bill: BillExtraction) -> dict:
    s = {}

    charges_sum = sum(c.amount for c in bill.charges)
    taxes_sum = sum(t.amount for t in bill.taxes)
    if bill.charges:
        s["charges_sum_from_lines"] = round(charges_sum, 2)
        by_type = {}
        for c in bill.charges:
            by_type[c.type] = round(by_type.get(c.type, 0) + c.amount, 2)
        s["charges_by_type"] = by_type
    if bill.taxes:
        s["taxes_sum_from_lines"] = round(taxes_sum, 2)
        by_type = {}
        for t in bill.taxes:
            by_type[t.type] = round(by_type.get(t.type, 0) + t.amount, 2)
        s["taxes_by_type"] = by_type

    bill_amt = bill.current_bill
    if bill_amt and bill.total_taxes is not None:
        s["taxes_pct_of_current_bill"] = round(bill.total_taxes / bill_amt * 100, 2)
    if bill_amt and bill.total_charges is not None:
        s["charges_pct_of_current_bill"] = round(bill.total_charges / bill_amt * 100, 2)

    if bill.units_consumed and bill.total_charges is not None:
        s["avg_cost_per_unit_pkr"] = round(bill.total_charges / bill.units_consumed, 4)

    if bill.payable_after_due_date is not None and bill.payable_within_due_date is not None:
        s["late_payment_surcharge_pkr"] = round(bill.payable_after_due_date - bill.payable_within_due_date, 2)
        if bill.payable_within_due_date:
            s["late_payment_surcharge_pct"] = round(
                s["late_payment_surcharge_pkr"] / bill.payable_within_due_date * 100, 2
            )

    hist = [h for h in bill.usage_history if isinstance(h.get("units"), (int, float))]
    if hist:
        units = [h["units"] for h in hist]
        s["usage_history_count"] = len(units)
        s["usage_history_min"] = min(units)
        s["usage_history_max"] = max(units)
        s["usage_history_avg"] = round(sum(units) / len(units), 1)
        for threshold in (100, 150, 200, 250, 300):
            above = [h["month"] for h, u in zip(hist, units) if u > threshold]
            s[f"months_above_{threshold}_units"] = {"count": len(above), "months": above}
        if bill.units_consumed is not None:
            s["current_month_units"] = bill.units_consumed
            s["current_vs_history_avg_diff"] = round(bill.units_consumed - s["usage_history_avg"], 1)
            if len(units) >= 2:
                # Decide whether the history's last entry duplicates the current bill month by
                # comparing MONTH LABELS, not consumption values - matching on units is wrong
                # whenever two different months happen to use the same number of units.
                last_is_current = bool(bill.bill_month) and hist[-1].get("month") == bill.bill_month
                prev = units[-2] if last_is_current else units[-1]
                s["previous_month_units"] = prev
                s["change_vs_previous_month"] = round(bill.units_consumed - prev, 1)
                if prev:
                    s["change_vs_previous_month_pct"] = round((bill.units_consumed - prev) / prev * 100, 1)

    if bill.arrears is not None:
        s["has_outstanding_arrears"] = bill.arrears > 0
        s["arrears_pkr"] = bill.arrears

    return s
