"""Cost basis: escalate, then convert, then locate (E01 design §4.6, ADR 0052 D6).

An item or price stated on a basis `(cur_b, Y_b)` is brought to the assessment's
`(cur_t, Y_t, location)` by

    E = [I_s(Y_t) / I_s(Y_b)] · X(cur_b → cur_t, Y_t) · LF

evaluated left to right in that order, with `s = basis.escalation_series[cur_b]`, `X` the
annual-average rate for `Y_t` crossed through USD (1 when the currencies agree) and `LF` the
location factor (default 1.0). For a set whose basis is an index value (SSLW: CEPCI 500), a
selected series whose `code` is that index (a user's CEPCI) takes `I_s(Y_b)` as the basis value
itself; otherwise the set's `year_equivalent` is used with the currency's public series, with
limitation `INDEX_BASIS_MAPPED(<set>, CEPCI 500 → 2006)`. Refusals: `ESCALATION_SERIES_MISSING`,
`INDEX_YEAR_UNAVAILABLE`, `EXCHANGE_RATE_UNAVAILABLE` (never raised; returned as `Refusal`).

Shipped series (`openflowsheet/_data/assessment/index/`): BLS PPI WPU11, Eurostat PPI C28 (euro
area) and Federal Reserve G.5A exchange rates. CEPCI values are never shipped (D6); a user may
supply them as a series file of the same layout.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, Literal

from openflowsheet.assessment.program import Limitation, Refusal

__all__ = [
    "SHIPPED_RATES",
    "SHIPPED_SERIES",
    "Escalation",
    "ExchangeRates",
    "IndexSeries",
    "SourceBasis",
    "TargetBasis",
    "escalate",
    "load_rates",
    "load_series",
    "rates_from",
    "series_from",
]

SHIPPED_SERIES: Final = ("bls-ppi-wpu11-annual-v1", "eurostat-ppi-c28-ea-annual-v1")
SHIPPED_RATES: Final = ("frb-g5a-annual-v1",)


@dataclass(frozen=True)
class IndexSeries:
    """An annual-average price index (§4.6 series file)."""

    series_id: str
    code: str
    values: Mapping[int, float]
    document: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def value(self, year: int) -> float | None:
        return self.values.get(year)


@dataclass(frozen=True)
class ExchangeRates:
    """Annual-average exchange rates, each currency as its source publishes it: `USD_per_unit`
    or `units_per_USD`."""

    series_id: str
    rates: Mapping[str, tuple[Literal["USD_per_unit", "units_per_USD"], Mapping[int, float]]]
    document: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def usd_per_unit(self, currency: str, year: int) -> float | None:
        """USD per one unit of `currency` in `year` (1.0 for USD), or `None` if not published."""
        if currency == "USD":
            return 1.0
        entry = self.rates.get(currency)
        if entry is None:
            return None
        convention, values = entry
        rate = values.get(year)
        if rate is None:
            return None
        return rate if convention == "USD_per_unit" else 1.0 / rate


def series_from(document: Mapping[str, Any]) -> IndexSeries:
    values = {int(year): float(value) for year, value in dict(document["values"]).items()}
    return IndexSeries(
        str(document["series_id"]),
        str(document["code"]),
        MappingProxyType(values),
        MappingProxyType(dict(document)),
    )


def rates_from(document: Mapping[str, Any]) -> ExchangeRates:
    rates = {}
    for currency, entry in dict(document["rates"]).items():
        convention = entry["convention"]
        if convention not in ("USD_per_unit", "units_per_USD"):
            raise ValueError(f"{document['series_id']}: {currency} convention {convention!r}")
        values = {int(year): float(value) for year, value in dict(entry["values"]).items()}
        rates[currency] = (convention, MappingProxyType(values))
    return ExchangeRates(
        str(document["series_id"]), MappingProxyType(rates), MappingProxyType(dict(document))
    )


def _shipped(series_id: str) -> Mapping[str, Any]:
    path = files("openflowsheet").joinpath("_data", "assessment", "index", f"{series_id}.json")
    if not path.is_file():
        raise KeyError(f"no shipped index or exchange-rate series {series_id!r}")
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if document.get("series_id") != series_id:
        raise ValueError(f"{path}: declares series_id {document.get('series_id')!r}")
    return document


def load_series(series_id: str) -> IndexSeries:
    """A shipped index series."""
    return series_from(_shipped(series_id))


def load_rates(series_id: str = "frb-g5a-annual-v1") -> ExchangeRates:
    """A shipped exchange-rate series."""
    return rates_from(_shipped(series_id))


@dataclass(frozen=True)
class SourceBasis:
    """The basis an item's cost or a price is stated on: a currency and a year, or (a set) an
    index value with its series code and the year it maps to without that series."""

    currency: str
    year: int | None = None
    index: tuple[str, float] | None = None
    year_equivalent: int | None = None
    set_id: str | None = None


@dataclass(frozen=True)
class TargetBasis:
    """The assessment's basis (`basis` of the document, defaults applied)."""

    currency: str
    year: int
    escalation_series: Mapping[str, str]
    location_factor: float = 1.0


@dataclass(frozen=True)
class Escalation:
    """`E` and its parts, for the item's provenance (§4.5.5)."""

    factor: float
    index_ratio: float
    exchange: float
    location: float
    series_id: str
    base: tuple[str, float]
    target: tuple[int, float]
    limitations: tuple[Limitation, ...] = ()


def escalate(
    source: SourceBasis,
    target: TargetBasis,
    series: Mapping[str, IndexSeries],
    rates: ExchangeRates,
) -> Escalation | Refusal:
    """`E` for `source` on `target` (§4.6); `series` holds every series a document can name,
    shipped and user-supplied, by id."""
    series_id = target.escalation_series.get(source.currency)
    if series_id is None or series_id not in series:
        return Refusal(
            "ESCALATION_SERIES_MISSING",
            source.currency,
            f"no escalation series for {source.currency}"
            + ("" if series_id is None else f" ({series_id!r} is not available)"),
        )
    s = series[series_id]
    limitations: list[Limitation] = []
    if source.index is not None:
        code, value = source.index
        if s.code == code:
            base_value, base_label = value, f"{code} {value!r}"
        else:
            if source.year_equivalent is None:
                return Refusal(
                    "INDEX_YEAR_UNAVAILABLE",
                    series_id,
                    f"basis {code} {value!r} has no year_equivalent and {series_id!r} is not "
                    f"{code}",
                )
            mapped = s.value(source.year_equivalent)
            if mapped is None:
                return Refusal("INDEX_YEAR_UNAVAILABLE", f"{series_id}, {source.year_equivalent}")
            base_value, base_label = mapped, str(source.year_equivalent)
            limitations.append(
                Limitation(
                    "INDEX_BASIS_MAPPED",
                    str(source.set_id),
                    {"mapping": f"{code} {value:g} → {source.year_equivalent}"},
                )
            )
    else:
        if source.year is None:
            raise ValueError("a source basis needs a year or an index value")
        found = s.value(source.year)
        if found is None:
            return Refusal("INDEX_YEAR_UNAVAILABLE", f"{series_id}, {source.year}")
        base_value, base_label = found, str(source.year)
    target_value = s.value(target.year)
    if target_value is None:
        return Refusal("INDEX_YEAR_UNAVAILABLE", f"{series_id}, {target.year}")
    if source.currency == target.currency:
        exchange = 1.0
    else:
        usd_b = rates.usd_per_unit(source.currency, target.year)
        if usd_b is None:
            return Refusal("EXCHANGE_RATE_UNAVAILABLE", f"{source.currency}, {target.year}")
        usd_t = rates.usd_per_unit(target.currency, target.year)
        if usd_t is None:
            return Refusal("EXCHANGE_RATE_UNAVAILABLE", f"{target.currency}, {target.year}")
        exchange = usd_b / usd_t
    ratio = target_value / base_value
    factor = ratio * exchange * target.location_factor
    return Escalation(
        factor=factor,
        index_ratio=ratio,
        exchange=exchange,
        location=target.location_factor,
        series_id=series_id,
        base=(base_label, base_value),
        target=(target.year, target_value),
        limitations=tuple(limitations),
    )
