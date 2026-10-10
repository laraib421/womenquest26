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
        s["month_with_highest_units"] = max(hist, key=lambda h: h["units"])["month"]
        s["month_with_lowest_units"] = min(hist, key=lambda h: h["units"])["month"]
        for threshold in (100, 150, 200, 250, 300):
            above = [h["month"] for h, u in zip(hist, units) if u > threshold]
            s[f"months_above_{threshold}_units"] = {"count": len(above), "months": above}

        # Seasonal split - month label is "YYYY-MM", so [5:7] is the month number as text.
        def _season_avg(hist_list, months_set):
            vals = [h["units"] for h in hist_list if h.get("month", "")[5:7] in months_set]
            return round(sum(vals) / len(vals), 1) if vals else None

        summer = _season_avg(hist, {"06", "07", "08"})
        winter = _season_avg(hist, {"12", "01", "02"})
        if summer is not None:
            s["summer_avg_units_jun_aug"] = summer
        if winter is not None:
            s["winter_avg_units_dec_feb"] = winter
        if summer is not None and winter is not None:
            s["summer_minus_winter_units"] = round(summer - winter, 1)

        if len(hist) >= 3:
            last3 = hist[-3:]
            s["last_3_months"] = [{"month": h["month"], "units": h["units"]} for h in last3]
            s["last_3_months_trend"] = (
                "increasing" if last3[-1]["units"] > last3[0]["units"]
                else "decreasing" if last3[-1]["units"] < last3[0]["units"] else "flat"
            )
            # Simple moving-average projection for "next month", explicitly labelled an estimate.
            s["projected_next_month_units_estimate"] = round(sum(h["units"] for h in last3) / 3, 1)

        if bill.units_consumed is not None:
            s["current_month_units"] = bill.units_consumed
            s["current_vs_history_avg_diff"] = round(bill.units_consumed - s["usage_history_avg"], 1)

            # Year-over-year: same calendar month, one year earlier (matched by label, e.g.
            # bill_month "2026-04" -> look for "2025-04" in the history).
            if bill.bill_month and len(bill.bill_month) == 7:
                try:
                    yr, mo = bill.bill_month.split("-")
                    last_year_label = f"{int(yr) - 1}-{mo}"
                    match = next((h["units"] for h in hist if h.get("month") == last_year_label), None)
                    if match is not None:
                        s["same_month_last_year_units"] = match
                        s["change_vs_same_month_last_year"] = round(bill.units_consumed - match, 1)
                except ValueError:
                    pass

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
                # Hypothetical "if I use the same units as last month" bill estimate.
                if "avg_cost_per_unit_pkr" in s:
                    s["estimated_bill_if_same_as_previous_month_pkr"] = round(prev * s["avg_cost_per_unit_pkr"], 2)

        # "Spread cost evenly across the year" - average monthly cost estimate from average
        # monthly units at the current average per-unit cost. A real tariff is tiered/non-linear,
        # so this is explicitly an estimate, not an exact figure.
        if "avg_cost_per_unit_pkr" in s:
            s["estimated_avg_monthly_cost_pkr"] = round(s["usage_history_avg"] * s["avg_cost_per_unit_pkr"], 2)

    if bill.arrears is not None:
        s["has_outstanding_arrears"] = bill.arrears > 0
        s["arrears_pkr"] = bill.arrears

    return s
