"""The capital chain and annualisation (E01 design §4.7.1, §4.7.3).

A chain is an ordered list of steps `{name, terms: [{of, factor | factor_product}]}`:
`capex.<name> = Σ_terms (Π factor_product, left to right) · capex.<of>`, a left fold in term order,
with `of` ∈ {`sum_purchased`, `sum_bare_module`, an earlier step}. A term with neither `factor` nor
`factor_product` is `capex.<of>` itself. `capital_total` names the step `capex.total` aliases (the
annualised capital), `fci` the step `capex.fci` aliases (the base of fixed-OPEX fractions).

Presets live in `openflowsheet/_data/assessment/cost/chains.json` (`bare-module-total`,
`ebtf-prisma-v1`). A document gives `capital.chain` (a preset id) or its own `steps`,
`capital_total` and `fci`.

`CRF(i, n) = i(1+i)^n / ((1+i)^n − 1)`, on the domain `i ≥ 0.001`, `n ≥ 1` (§4.7.3).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Final

from openflowsheet.compile.spec import Expr

__all__ = [
    "BASES",
    "DISCOUNT_RATE_MIN",
    "Chain",
    "ChainError",
    "ChainStep",
    "ChainTerm",
    "chain_from",
    "crf",
    "discount_rate_domain",
    "load_chain",
]

#: The two sums a chain may start from (§4.7.1), as `capex.<base>` output ids.
BASES: Final = ("sum_purchased", "sum_bare_module")
#: §4.7.3: the smallest discount rate the CRF is evaluated at.
DISCOUNT_RATE_MIN: Final = 0.001
#: Names a step may not take: the per-item and alias output ids of §4.1.
_RESERVED: Final = frozenset({*BASES, "total", "fci", "purchased", "bare_module"})


class ChainError(ValueError):
    """A chain names an `of` that is not a base or an earlier step, or is otherwise malformed."""


@dataclass(frozen=True)
class ChainTerm:
    of: str
    #: The factors, multiplied left to right; empty for the bare `capex.<of>`.
    factors: tuple[float, ...]

    def factor(self) -> float | None:
        """`Π factors` left to right on floats, `None` for no factor (§4.7.1)."""
        if not self.factors:
            return None
        product = self.factors[0]
        for value in self.factors[1:]:
            product = product * value
        return product


@dataclass(frozen=True)
class ChainStep:
    name: str
    terms: tuple[ChainTerm, ...]

    def value(self, of: Mapping[str, Expr]) -> Expr:
        """`Σ_terms factor·of[term.of]`, a left fold in term order."""
        total: Expr | None = None
        for term in self.terms:
            factor = term.factor()
            value = of[term.of] if factor is None else factor * of[term.of]
            total = value if total is None else total + value
        return total


@dataclass(frozen=True)
class Chain:
    chain_id: str | None
    steps: tuple[ChainStep, ...]
    capital_total: str
    fci: str
    source: str = ""

    @property
    def bases(self) -> frozenset[str]:
        """The sums the chain reads (`sum_bare_module` makes a missing F_BM a refusal)."""
        return frozenset(t.of for s in self.steps for t in s.terms if t.of in BASES)


def _term(term: Mapping[str, Any], where: str) -> ChainTerm:
    if "factor" in term and "factor_product" in term:
        raise ChainError(f"{where}: give `factor` or `factor_product`, not both")
    if "factor" in term:
        return ChainTerm(str(term["of"]), (float(term["factor"]),))
    return ChainTerm(str(term["of"]), tuple(float(v) for v in term.get("factor_product", ())))


def chain_from(
    steps: Sequence[Mapping[str, Any]],
    capital_total: str,
    fci: str,
    *,
    chain_id: str | None = None,
    source: str = "",
) -> Chain:
    """A chain from its document form, checked: every `of` is a base or an earlier step, step
    names are unique and not reserved, `capital_total` and `fci` name steps."""
    known: list[str] = []
    parsed: list[ChainStep] = []
    for index, step in enumerate(steps):
        name = str(step["name"])
        where = f"capital step {index} ({name!r})"
        if name in _RESERVED or name in known:
            raise ChainError(f"{where}: the name is reserved or repeated")
        terms = tuple(_term(term, where) for term in step["terms"])
        if not terms:
            raise ChainError(f"{where}: no terms")
        for term in terms:
            if term.of not in BASES and term.of not in known:
                raise ChainError(f"{where}: `of` {term.of!r} is neither a base nor an earlier step")
        known.append(name)
        parsed.append(ChainStep(name, terms))
    for label, name in (("capital_total", capital_total), ("fci", fci)):
        if name not in known:
            raise ChainError(f"`{label}` {name!r} names no step")
    return Chain(chain_id, tuple(parsed), capital_total, fci, source)


_CHAINS: dict[str, Chain] = {}


def load_chain(chain_id: str) -> Chain:
    """The preset `chain_id` from `chains.json`, read once."""
    if not _CHAINS:
        path = files("openflowsheet").joinpath("_data", "assessment", "cost", "chains.json")
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document["chains"]:
            _CHAINS[entry["chain_id"]] = chain_from(
                entry["steps"],
                entry["capital_total"],
                entry["fci"],
                chain_id=entry["chain_id"],
                source=entry["source"],
            )
    if chain_id not in _CHAINS:
        raise ChainError(f"no capital-chain preset {chain_id!r}; presets: {sorted(_CHAINS)}")
    return _CHAINS[chain_id]


def crf(rate: Expr, years: Expr) -> Expr:
    """`CRF(i, n) = i(1+i)^n / ((1+i)^n − 1)` (§4.7.3), with `(1+i)^n` built once."""
    growth = (1.0 + rate) ** years
    return rate * growth / (growth - 1.0)


def discount_rate_domain(rate: float, years: float) -> str | None:
    """`None` inside §4.7.3's domain (`i ≥ 0.001`, `n ≥ 1`), else why not."""
    if not rate >= DISCOUNT_RATE_MIN:
        return f"discount_rate {rate!r} < {DISCOUNT_RATE_MIN}"
    if not years >= 1:
        return f"lifetime_years {years!r} < 1"
    return None
