"""Quotes: a stated cost that replaces an item's correlation (E01 design §4.5.4).

With `exponent`, the quote is `power-law-v1` (`C_ref = cost`, `S_ref = size.value`); without it,
`constant-v1`. Either is escalated by §4.6: `C = C_base·E`. A quote has no `size` regime. A
constant quote that states a size is checked at the evaluation state: `|S/S_q − 1| > 0.1` is
limitation `QUOTE_SIZE_MISMATCH(<item>)`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.assessment.cost.forms import constant, power_law
from openflowsheet.assessment.program import Limitation
from openflowsheet.compile.spec import Algebra, Expr

__all__ = ["MISMATCH_TOLERANCE", "Quote", "quote_from", "size_mismatch"]

#: §4.5.4: a constant quote's stated size within 10 % of the item's.
MISMATCH_TOLERANCE: Final = 0.1


@dataclass(frozen=True)
class Quote:
    cost: float
    currency: str
    year: int
    kind: Literal["purchased", "bare_module"]
    source: str
    size_quantity: str | None = None
    size_value: float | None = None
    exponent: float | None = None
    location: str | None = None
    accuracy_class: int | None = None
    relative_range: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.exponent is not None and self.size_value is None:
            raise ValueError("a quote with an exponent needs its size (§4.5.4)")

    @property
    def form(self) -> str:
        return "constant-v1" if self.exponent is None else "power-law-v1"

    def cost_expr(self, escalation: float, size: Expr | None, alg: Algebra) -> Expr:
        """`C = C_base·E`: `cost·E` for a constant quote, `cost·(S/S_q)^n·E` with an exponent."""
        if self.exponent is None:
            return constant(self.cost) * escalation
        if size is None or self.size_value is None:
            raise ValueError("a scaled quote is evaluated at the item's size")
        return power_law(size, self.cost, self.size_value, self.exponent, alg) * escalation


def quote_from(document: Mapping[str, Any]) -> Quote:
    """A `quote` object of the assessment document (`assessment.schema.json#/$defs/quote`)."""
    size = document.get("size")
    rr = document.get("relative_range")
    return Quote(
        cost=float(document["cost"]),
        currency=str(document["currency"]),
        year=int(document["year"]),
        kind=document["kind"],
        source=str(document["source"]),
        size_quantity=None if size is None else str(size["quantity"]),
        size_value=None if size is None else float(size["value"]),
        exponent=None if document.get("exponent") is None else float(document["exponent"]),
        location=document.get("location"),
        accuracy_class=document.get("accuracy_class"),
        relative_range=None if rr is None else (float(rr[0]), float(rr[1])),
    )


def size_mismatch(quote: Quote, item_id: str, size: float) -> Limitation | None:
    """`QUOTE_SIZE_MISMATCH(<item>)` for a constant quote whose stated size is more than 10 % from
    the item's size at the evaluation state; `None` otherwise (or without a stated size)."""
    if quote.exponent is not None or quote.size_value is None:
        return None
    if abs(size / quote.size_value - 1.0) > MISMATCH_TOLERANCE:
        return Limitation(
            "QUOTE_SIZE_MISMATCH",
            item_id,
            {"size": size, "quoted_size": quote.size_value, "quantity": quote.size_quantity},
        )
    return None
