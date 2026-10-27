"""The `derived` contributor: ratios of affine combinations of earlier outputs (E01 design §4.7.5).

```
derived.<id> = (Σ α_i y_i + α_0) / (Σ β_j y_j + β_0)
```

`y` are earlier output ids (the `cost` and `lca` contributors', and derived outputs declared before
this one). A `denominator` that is absent or all zero means no ratio. Each affine combination is a
left fold over its `terms` in sorted id order (the canonical document's order, so two documents
with one `assessment_sha256` build one expression), then `+ α_0`.

Planning, on floats at the planning state (§4.2.2):
- a term naming no earlier output, or a later or the same derived output, is refused
  `ASSESSMENT_OUTPUT_UNKNOWN(<term>)` (references go backwards only, so the outputs are acyclic);
- a term naming an unavailable output makes this output unavailable (§4.9);
- a denominator ≤ 0 is refused `METRIC_UNDEFINED(derived.<id>)` and the output is unavailable: a
  non-positive denominator is never a negative "cost" (§4.7.5). The report repeats the check at
  the state it reports (`undefined` in the section).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    FunctionalBuilder,
    OutputDef,
    Refusal,
    Symbols,
    register_contributor,
)
from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.compile.spec import Algebra, Expr

__all__ = ["Affine", "DerivedContributor"]

PREFIX = "derived."


@dataclass(frozen=True)
class Affine:
    """`Σ coefficient·y + constant`, the terms in sorted id order."""

    terms: tuple[tuple[str, float], ...]
    constant: float

    @classmethod
    def of(cls, doc: Mapping[str, Any] | None) -> Affine:
        doc = doc or {}
        terms = dict(doc.get("terms", {}))
        return cls(
            tuple((k, float(terms[k])) for k in sorted(terms)), float(doc.get("constant", 0.0))
        )

    @property
    def zero(self) -> bool:
        return self.constant == 0.0 and all(c == 0.0 for _, c in self.terms)

    def value(self, y: Mapping[str, float]) -> float:
        total: float | None = None
        for name, c in self.terms:
            t = c * y[name]
            total = t if total is None else total + t
        return self.constant if total is None else total + self.constant

    def build(self, s: Symbols, a: Algebra) -> Expr:
        total: Expr | None = None
        for name, c in self.terms:
            t = c * s.out(name)
            total = t if total is None else total + t
        return self.constant if total is None else total + self.constant


def _ratio(numerator: Affine, denominator: Affine | None) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        n = numerator.build(s, a)
        return n if denominator is None else n / denominator.build(s, a)

    return build


class DerivedContributor:
    """The `derived` contributor (§4.2.2, §4.7.5)."""

    name = "derived"

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        declared = list(ctx.spec.document.get("derived", ()))
        if not declared:
            return ContributionPlan()
        earlier = [o for plan in ctx.earlier.values() for o in plan.outputs]
        known = {o.output_id for o in earlier}
        unavailable = {n: why for plan in ctx.earlier.values() for n, why in plan.unavailable}
        theta = tuple(t for plan in ctx.earlier.values() for t in plan.theta)
        blocks = tuple(b for plan in ctx.earlier.values() for b in plan.blocks)
        outputs: list[OutputDef] = []
        refusals: list[Refusal] = []
        withheld: dict[str, str] = {}
        ratios: dict[str, tuple[Affine, Affine | None]] = {}
        y: dict[str, float] | None = None
        failed: str | None = None
        for doc in declared:
            output_id = PREFIX + str(doc["id"])
            if output_id in ratios or output_id in withheld:
                refusals.append(Refusal("ASSESSMENT_OUTPUT_UNKNOWN", output_id, "declared twice"))
                continue
            numerator = Affine.of(doc["numerator"])
            given = Affine.of(doc.get("denominator"))
            denominator = None if given.zero else given
            refs = [n for n, _ in numerator.terms]
            refs += [n for n, _ in denominator.terms] if denominator is not None else []
            bad = sorted({r for r in refs if r not in known and r not in unavailable})
            if bad:
                refusals.extend(
                    Refusal(
                        "ASSESSMENT_OUTPUT_UNKNOWN",
                        r,
                        f"{output_id} may reference only earlier outputs (§4.7.5)",
                    )
                    for r in bad
                )
                withheld[output_id] = f"references unknown outputs {bad}"
                unavailable[output_id] = withheld[output_id]
                continue
            missing = sorted({r for r in refs if r in unavailable})
            if missing:
                withheld[output_id] = f"depends on {missing}"
                unavailable[output_id] = withheld[output_id]
                continue
            if denominator is not None:
                if y is None and failed is None:
                    try:
                        y = ctx.evaluate(state, earlier, theta, blocks)
                    except TwinEvaluationError as error:
                        failed = str(error)
                if y is None:
                    refusals.append(Refusal("ASSESSMENT_EVALUATION_FAILED", output_id, str(failed)))
                    withheld[output_id] = "earlier outputs not evaluable at the planning state"
                    unavailable[output_id] = withheld[output_id]
                    continue
                d = denominator.value(y)
                if not d > 0.0:
                    refusals.append(
                        Refusal("METRIC_UNDEFINED", output_id, f"denominator {d!r} ≤ 0")
                    )
                    withheld[output_id] = "non-positive denominator"
                    unavailable[output_id] = withheld[output_id]
                    continue
            if y is not None:
                n = numerator.value(y)
                y[output_id] = n if denominator is None else n / denominator.value(y)
            outputs.append(OutputDef(output_id, str(doc["unit"]), _ratio(numerator, denominator)))
            earlier.append(outputs[-1])
            known.add(output_id)
            ratios[output_id] = (numerator, denominator)

        def section(values: Mapping[str, float]) -> dict[str, Any]:
            return {"undefined": _undefined(ratios, values)}

        return ContributionPlan(
            outputs=tuple(outputs),
            refusals=tuple(refusals),
            section=section,
            unavailable=tuple(withheld.items()),
        )


def _undefined(
    ratios: Mapping[str, tuple[Affine, Affine | None]], values: Mapping[str, float]
) -> list[str]:
    """The derived outputs whose denominator is ≤ 0 at `values` (§4.7.5)."""
    return [
        output_id
        for output_id, (_, denominator) in ratios.items()
        if denominator is not None and not denominator.value(values) > 0.0
    ]


register_contributor("derived", DerivedContributor)
