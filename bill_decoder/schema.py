"""Pydantic models for the Level 1 JSON output (WTQ Build Track - Utility Bill Decoder)."""
from typing import ClassVar, List, Optional, Tuple

from pydantic import BaseModel, Field

CHARGE_TYPES = {"energy", "fixed", "fpa", "quarterly_adjustment", "surcharge", "meter_rent", "subsidy", "other"}
TAX_TYPES = {"gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"}


class ChargeLine(BaseModel):
    type: str
    amount: float


class TaxLine(BaseModel):
    type: str
    amount: float


class BillExtraction(BaseModel):
    provider: Optional[str] = None
    tariff: Optional[str] = None
    sanctioned_load_kw: Optional[float] = None

    bill_month: Optional[str] = None
    reading_date: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None

    previous_reading: Optional[float] = None
    current_reading: Optional[float] = None
    units_consumed: Optional[float] = None

    charges: List[ChargeLine] = Field(default_factory=list)
    total_charges: Optional[float] = None

    taxes: List[TaxLine] = Field(default_factory=list)
    total_taxes: Optional[float] = None

    current_bill: Optional[float] = None
    arrears: Optional[float] = None
    payable_within_due_date: Optional[float] = None
    payable_after_due_date: Optional[float] = None

    # Extra fields we extract for Level 2 Q&A grounding. NOT part of the official
    # Level 1 schema — stripped before writing level1.csv.
    usage_history: List[dict] = Field(default_factory=list)  # [{"month": "Jul-25", "units": 239}, ...]
    notes: Optional[str] = None  # anything unusual noticed (e.g. multiple meters)

    OFFICIAL_FIELDS: ClassVar[Tuple[str, ...]] = (
        "provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date",
        "issue_date", "due_date", "previous_reading", "current_reading", "units_consumed",
        "charges", "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
        "payable_within_due_date", "payable_after_due_date",
    )

    def official_json(self) -> dict:
        """The exact dict the competition schema wants - no extra fields."""
        d = self.model_dump()
        return {k: d[k] for k in self.OFFICIAL_FIELDS}
