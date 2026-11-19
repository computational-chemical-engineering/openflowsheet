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

Every ratio carries the single-choice `domain` regime entry `derived.<id>.denominator` with the
row `den/|den(x₀)| ≥ 0` (§4.7.5 erratum 2026-10-29, R-868): it enters a study's closure like any
other admissibility row, so the optimizer is told about the pole, and on the float path a row ≤ 0
is the evaluation error `METRIC_UNDEFINED(derived.<id>)` at every state
(`AssessmentProgram.evaluate`), so a study candidate where it occurs is not verified.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from openflowsheet.assessment.linearization import Refusal
from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    FunctionalBuilder,
    OutputDef,
    Symbols,
    Theta,
    register_contributor,
)
from openflowsheet.assessment.regimes import AdmissibilityRow, RegimeEntry
from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.compile.spec import Algebra, Expr, PropertyBlock

__all__ = ["Affine", "DerivedContributor"]

PREFIX = "derived."
#: The `domain` entry of ratio `derived.<id>` is `derived.<id>.denominator`, its one row `den`.
DENOMINATOR = "denominator"


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
        """The declared ratios in declaration order, each planned by `_Derivation.add` against
        the earlier contributors' outputs (§4.7.5), and the report section of the ratios kept
        (`_undefined`). No `derived` block: an empty plan."""
        declared = list(ctx.spec.document.get("derived", ()))
        if not declared:
            return ContributionPlan()
        earlier = [o for plan in ctx.earlier.values() for o in plan.outputs]
        known = {o.output_id for o in earlier}
        unavailable = {n: why for plan in ctx.earlier.values() for n, why in plan.unavailable}
        theta = tuple(t for plan in ctx.earlier.values() for t in plan.theta)
        blocks = tuple(b for plan in ctx.earlier.values() for b in plan.blocks)
        run = _Derivation(ctx, state, earlier, known, unavailable, theta, blocks)
        for doc in declared:
            run.add(doc)

        def section(values: Mapping[str, float]) -> dict[str, Any]:
            undefined, withheld_at = _undefined(run.ratios, values)
            return {"undefined": undefined, "withheld": withheld_at}

        return ContributionPlan(
            outputs=tuple(run.outputs),
            regime_entries=tuple(run.entries),
            refusals=tuple(run.refusals),
            section=section,
            unavailable=tuple(run.withheld.items()),
        )


@dataclass
class _Derivation:
    """`DerivedContributor.plan`'s run. Frame: the build context, the planning state, the
    earlier outputs (`derived` outputs appended as they are kept), their ids (`known`), the
    outputs unavailable so far with why, and the earlier plans' theta and blocks. State: the
    outputs, regime entries and refusals of this plan, the outputs it withholds with why, the
    ratios kept, `y` the outputs' values at the planning state once evaluated (lazily, by the
    first ratio with a denominator) and `failed` why they could not be."""

    ctx: BuildContext
    state: Mapping[str, float]
    earlier: list[OutputDef]
    known: set[str]
    unavailable: dict[str, str]
    theta: tuple[Theta, ...]
    blocks: tuple[tuple[PropertyBlock, tuple[str, ...]], ...]
    outputs: list[OutputDef] = field(default_factory=list)
    entries: list[RegimeEntry] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    withheld: dict[str, str] = field(default_factory=dict)
    ratios: dict[str, tuple[Affine, Affine | None]] = field(default_factory=dict)
    y: dict[str, float] | None = None
    failed: str | None = None

    def add(self, doc: Mapping[str, Any]) -> None:
        """Plan one declared ratio `doc`: refused `ASSESSMENT_OUTPUT_UNKNOWN` when declared
        twice; refused per term and withheld when a term names no earlier output; withheld when
        a term is unavailable; with a denominator, refused `ASSESSMENT_EVALUATION_FAILED` and
        withheld when the earlier outputs do not evaluate at the planning state, refused
        `METRIC_UNDEFINED` and withheld when the denominator there is ≤ 0, else its `domain`
        entry appended. A kept ratio's value joins `y` (once evaluated), and its output joins
        the outputs, the earlier outputs, `known` and the ratios."""
        output_id = PREFIX + str(doc["id"])
        if output_id in self.ratios or output_id in self.withheld:
            self.refusals.append(Refusal("ASSESSMENT_OUTPUT_UNKNOWN", output_id, "declared twice"))
            return
        numerator = Affine.of(doc["numerator"])
        given = Affine.of(doc.get("denominator"))
        denominator = None if given.zero else given
        refs = [n for n, _ in numerator.terms]
        refs += [n for n, _ in denominator.terms] if denominator is not None else []
        bad = sorted({r for r in refs if r not in self.known and r not in self.unavailable})
        if bad:
            self.refusals.extend(
                Refusal(
                    "ASSESSMENT_OUTPUT_UNKNOWN",
                    r,
                    f"{output_id} may reference only earlier outputs (§4.7.5)",
                )
                for r in bad
            )
            self.withheld[output_id] = f"references unknown outputs {bad}"
            self.unavailable[output_id] = self.withheld[output_id]
            return
        missing = sorted({r for r in refs if r in self.unavailable})
        if missing:
            self.withheld[output_id] = f"depends on {missing}"
            self.unavailable[output_id] = self.withheld[output_id]
            return
        if denominator is not None and not self.denominator_admitted(output_id, denominator):
            return
        if self.y is not None:
            n = numerator.value(self.y)
            self.y[output_id] = n if denominator is None else n / denominator.value(self.y)
        self.outputs.append(OutputDef(output_id, str(doc["unit"]), _ratio(numerator, denominator)))
        self.earlier.append(self.outputs[-1])
        self.known.add(output_id)
        self.ratios[output_id] = (numerator, denominator)

    def denominator_admitted(self, output_id: str, denominator: Affine) -> bool:
        """True once ratio `output_id`'s `domain` entry is appended (`_domain_entry`): the
        earlier outputs evaluated at the planning state (`y`, evaluated by the first call, or
        `failed` with why not) and `denominator` > 0 there. False, with the output withheld,
        when they do not evaluate (refusal `ASSESSMENT_EVALUATION_FAILED`, each call after a
        failure too) or the denominator is ≤ 0 (refusal `METRIC_UNDEFINED`)."""
        if self.y is None and self.failed is None:
            try:
                self.y = self.ctx.evaluate(self.state, self.earlier, self.theta, self.blocks)
            except TwinEvaluationError as error:
                self.failed = str(error)
        if self.y is None:
            self.refusals.append(
                Refusal("ASSESSMENT_EVALUATION_FAILED", output_id, str(self.failed))
            )
            self.withheld[output_id] = "earlier outputs not evaluable at the planning state"
            self.unavailable[output_id] = self.withheld[output_id]
            return False
        d = denominator.value(self.y)
        if not d > 0.0:
            self.refusals.append(Refusal("METRIC_UNDEFINED", output_id, f"denominator {d!r} ≤ 0"))
            self.withheld[output_id] = "non-positive denominator"
            self.unavailable[output_id] = self.withheld[output_id]
            return False
        self.entries.append(_domain_entry(output_id, denominator, d))
        return True


def _domain_entry(output_id: str, denominator: Affine, d: float) -> RegimeEntry:
    """The single-choice `domain` entry of a ratio: row `den/|den(x₀)| ≥ 0`, `d = den(x₀) > 0`."""
    return RegimeEntry(
        f"{output_id}.{DENOMINATOR}",
        "domain",
        "positive",
        "a ratio's denominator is > 0 (§4.7.5)",
        (AdmissibilityRow("den", denominator.build, abs(d)),),
    )


def _undefined(
    ratios: Mapping[str, tuple[Affine, Affine | None]], values: Mapping[str, float]
) -> tuple[list[str], list[str]]:
    """At `values`: the derived outputs whose denominator is ≤ 0 (§4.7.5), and those that
    reference one of them (directly or through another), in declaration order."""
    undefined: list[str] = []
    withheld: list[str] = []
    bad: set[str] = set()
    for output_id, (numerator, denominator) in ratios.items():
        refs = [n for n, _ in numerator.terms]
        refs += [n for n, _ in denominator.terms] if denominator is not None else []
        if any(r in bad for r in refs):
            withheld.append(output_id)
            bad.add(output_id)
        elif denominator is not None and not denominator.value(values) > 0.0:
            undefined.append(output_id)
            bad.add(output_id)
    return undefined, withheld


register_contributor("derived", DerivedContributor)
