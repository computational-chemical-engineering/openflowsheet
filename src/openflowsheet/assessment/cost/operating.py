"""Operating-cost arithmetic (E01 design §4.5.6, §4.6, §4.7.2–§4.7.4).

The pieces the cost contributor composes into `opex.*`, `revenue.*` and `product.annual`:

- `PER_SI` — the exact SI factor of each price `per` (§4.5.6); a price becomes currency per SI unit
  by division by its factor.
- `price_on_basis` — a utility or material price on the assessment basis (§4.6): stated on it (or
  silent about currency and year), escalated by its own `escalation_series`, else
  `PRICE_BASIS_MISMATCH(<id>)`.
- `annual` — `rate · 3600 · h_op`, the yearly amount of a per-second rate (§4.7.2, §4.7.4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from openflowsheet.assessment.cost.index import (
    ExchangeRates,
    IndexSeries,
    SourceBasis,
    TargetBasis,
    escalate,
)
from openflowsheet.assessment.program import Limitation, Refusal
from openflowsheet.compile.spec import Expr

__all__ = ["ENERGY_PER", "PER_SI", "SECONDS_PER_HOUR", "PriceOnBasis", "annual", "price_on_basis"]

#: §4.5.6: exact SI factors (J, kg, mol, m³, s); `year` prices a fixed line and has no SI factor.
PER_SI: Final[Mapping[str, float]] = {
    "J": 1.0,
    "kJ": 1e3,
    "MJ": 1e6,
    "GJ": 1e9,
    "kWh": 3.6e6,
    "MWh": 3.6e9,
    "kg": 1.0,
    "t": 1e3,
    "mol": 1.0,
    "kmol": 1e3,
    "m3": 1.0,
    "s": 1.0,
}
ENERGY_PER: Final = frozenset({"J", "kJ", "MJ", "GJ", "kWh", "MWh"})
SECONDS_PER_HOUR: Final = 3600.0


@dataclass(frozen=True)
class PriceOnBasis:
    """A price in assessment currency per SI unit of its `per`, with its escalation factor (1.0
    when stated on the basis) and any limitation the escalation carries."""

    value: float
    per: str
    escalation: float = 1.0
    limitations: tuple[Limitation, ...] = ()


def price_on_basis(
    price_id: str,
    price: Mapping[str, Any],
    target: TargetBasis,
    series: Mapping[str, IndexSeries],
    rates: ExchangeRates,
) -> PriceOnBasis | Refusal:
    """`price.value / PER_SI[per]`, times `E` (§4.6) when the price states another basis and names
    its `escalation_series`. A price silent about currency or year is read on the basis's."""
    per = str(price["per"])
    if per not in PER_SI:
        return Refusal("PRICE_BASIS_MISMATCH", price_id, f"`per: {per}` is not a rate unit")
    currency = str(price.get("currency", target.currency))
    year = int(price.get("year", target.year))
    si = float(price["value"]) / PER_SI[per]
    if currency == target.currency and year == target.year:
        return PriceOnBasis(si, per)
    series_id = price.get("escalation_series")
    if series_id is None:
        return Refusal(
            "PRICE_BASIS_MISMATCH",
            price_id,
            f"stated in {currency} {year}, the basis is {target.currency} {target.year}",
        )
    own = TargetBasis(
        target.currency, target.year, {currency: str(series_id)}, target.location_factor
    )
    found = escalate(SourceBasis(currency, year), own, series, rates)
    if isinstance(found, Refusal):
        return found
    return PriceOnBasis(si * found.factor, per, found.factor, found.limitations)


def annual(rate: Expr, hours_per_year: Expr) -> Expr:
    """`rate · 3600 · h_op` (per year from per second), left to right."""
    return rate * SECONDS_PER_HOUR * hours_per_year
