"""The output catalogue: every id an assessment may publish, with its unit (E01 design §4.1).

Inside a report an id is unprefixed; a study names it `assessment:<id>` (ADR 0052 D9). Item ids
contain dots (`<U>.drum`), so each pattern anchors on its fixed prefix and suffix. `classify` is the
single test of whether an id is publishable; the program refuses to compile an output it does not
recognise, because an id outside the catalogue is one no study or report can interpret.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "ASSESSMENT_PREFIX",
    "CATALOGUE",
    "SIZE_QUANTITIES",
    "CatalogueEntry",
    "classify",
    "study_name",
]

#: The prefix a study names an assessment output by (§4.1, ADR 0052 D9).
ASSESSMENT_PREFIX: Final = "assessment:"

#: `size.<item>.<q>`'s quantities and their SI units (§4.1).
SIZE_QUANTITIES: Final = {
    "area": "m2",
    "volume": "m3",
    "diameter": "m",
    "height": "m",
    "power": "W",
    "vol_flow": "m3/s",
    "head": "m",
    "n_parallel": "1",
}


@dataclass(frozen=True)
class CatalogueEntry:
    name: str
    pattern: re.Pattern[str]
    unit: str
    meaning: str


def _entry(name: str, pattern: str, unit: str, meaning: str) -> CatalogueEntry:
    return CatalogueEntry(name, re.compile(pattern), unit, meaning)


_SIZE = "|".join(SIZE_QUANTITIES)

#: §4.1's table, in its order. The first matching entry classifies an id, so the fixed names
#: (`capex.sum_purchased`, `opex.total`, …) precede the open patterns that would also match them.
CATALOGUE: Final[tuple[CatalogueEntry, ...]] = (
    _entry("size", rf"^size\.(?P<item>.+)\.(?P<q>{_SIZE})$", "SI of q", "sizing quantity"),
    _entry("capex.purchased", r"^capex\.purchased\.(?P<item>.+)$", "currency", "purchased cost"),
    _entry("capex.bare_module", r"^capex\.bare_module\.(?P<item>.+)$", "currency", "bare module"),
    _entry("capex.sum", r"^capex\.(sum_purchased|sum_bare_module)$", "currency", "sum over items"),
    _entry("capex.step", r"^capex\.(?P<step>[^.]+)$", "currency", "capital-chain step"),
    _entry("opex.total", r"^opex\.total$", "currency/yr", "utilities + materials + waste + fixed"),
    _entry("opex.utility", r"^opex\.utility\.(?P<u>.+)$", "currency/yr", "utility cost"),
    _entry("opex.material", r"^opex\.material\.(?P<s>.+)$", "currency/yr", "raw-material cost"),
    _entry("opex.waste", r"^opex\.waste\.(?P<s>.+)$", "currency/yr", "waste cost"),
    _entry("opex.fixed", r"^opex\.fixed\.(?P<line>.+)$", "currency/yr", "fixed operating line"),
    _entry("revenue.total", r"^revenue\.total$", "currency/yr", "sum of revenues"),
    _entry("revenue", r"^revenue\.(?P<s>.+)$", "currency/yr", "product or co-product revenue"),
    _entry(
        "annual.capital_charge", r"^annual\.capital_charge$", "currency/yr", "CRF · capex.total"
    ),
    _entry("tac", r"^tac$", "currency/yr", "annual.capital_charge + opex.total"),
    _entry("profit", r"^profit$", "currency/yr", "revenue.total − tac"),
    _entry("product.annual", r"^product\.annual$", "kg/yr or mol/yr", "functional unit per year"),
    _entry("lcox", r"^lcox$", "currency/kg", "tac / product.annual"),
    _entry("inventory", r"^inventory\.(?P<k>.+)\.rate$", "unit/s", "foreground exchange"),
    _entry(
        "impact",
        r"^impact\.(?P<m>.+)\.(?P<per>rate|annual|per_fu)$",
        "category unit per s, yr or FU",
        "characterised impact",
    ),
    _entry("derived", r"^derived\.(?P<id>.+)$", "declared", "ratio of affine combinations"),
    _entry("adm", r"^adm\.(?P<entry>.+)\.(?P<k>[^.]+)$", "1", "admissibility row, ≥ 0 required"),
)


def classify(output_id: str) -> CatalogueEntry | None:
    """The catalogue entry of `output_id` (unprefixed), or `None` when it is not publishable."""
    if output_id.startswith(ASSESSMENT_PREFIX):
        return None
    for entry in CATALOGUE:
        if entry.pattern.match(output_id):
            return entry
    return None


def study_name(output_id: str) -> str:
    """`assessment:<output_id>`, the name a study uses."""
    return ASSESSMENT_PREFIX + output_id
