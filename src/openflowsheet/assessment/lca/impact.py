"""Characterised impacts and allocation (E01 design §4.8.1 "Allocation", §4.8.3).

`impact.<m>.rate = A_fac · (Σ_k q_{m,k} a_k + Σ_e c_{m,e} b_e)` — one left fold over the exchanges
in construction order, each term `θ · inventory.<k>.rate` — then `.annual = rate·3600·h_op` and
`.per_fu = rate / f(x)`. `q` and `c` are θ (`asm:lca.q.<table>.<m>.<activity>`,
`asm:lca.c.<table>.<m>.<flow>`), so `∂h/∂q = A_fac·a(x)`: contribution analysis for free.

Allocation (applied to every `h_m`): `none` and `substitution` multiply by nothing (substitution's
avoided activities are the exchanges the document declares with a negative `amount`); `factor` by
the constant θ `asm:lca.allocation.factor`; `mass` by `ṁ_FU / Σ ṁ_products`; `economic` by
`p_FU ṁ_FU / Σ p_i ṁ_i`, with the cost contributor's price θ. The two ratios are smooth; a
non-positive denominator at the planning state refuses every impact
(`ASSESSMENT_EVALUATION_FAILED(lca.allocation)`), and a zero one at a later state is an evaluation
error. `products` defaults to the materials whose role is `product` or `co_product`.

A category an exchange's table does not carry withholds that category (`LCA_ACTIVITY_UNKNOWN` or
`LCA_FLOW_UNKNOWN(<table>.<m>)`); an exchange that could not be built withholds every category.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from openflowsheet.assessment.cost.operating import annual
from openflowsheet.assessment.defaults import default
from openflowsheet.assessment.lca.inventory import Exchange, InventoryPlan, stream_flow
from openflowsheet.assessment.lca.tables import LcaTable, UnitScoreTable
from openflowsheet.assessment.program import (
    BuildContext,
    FunctionalBuilder,
    Limitation,
    OutputDef,
    Refusal,
    Symbols,
    Theta,
)
from openflowsheet.assessment.sizing import SizingContext
from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.compile.spec import Algebra, Expr

__all__ = ["ImpactPlan", "categories_of", "plan_impacts"]

HOURS = "asm:operation.hours_per_year"


@dataclass
class ImpactPlan:
    outputs: list[OutputDef] = field(default_factory=list)
    theta: list[Theta] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    unavailable: list[tuple[str, str]] = field(default_factory=list)
    defaulted: list[dict[str, Any]] = field(default_factory=list)


def categories_of(document: Mapping[str, Any], tables: Mapping[str, LcaTable]) -> list[str]:
    """`lca.categories`, else every category of the listed tables, unit-score tables first, in
    listing and file order."""
    lca = dict(document.get("lca", {}))
    if "categories" in lca:
        return [str(m) for m in lca["categories"]]
    found: list[str] = []
    for table_id in [*lca.get("tables", ()), *lca.get("direct_factors", ())]:
        table = tables.get(str(table_id))
        for c in () if table is None else table.categories:
            if c.category_id not in found:
                found.append(c.category_id)
    return found


def _ranged(document: Mapping[str, Any], theta_id: str) -> tuple[float, float] | None:
    declared = dict(document.get("uncertainty", {})).get(theta_id)
    if declared is None:
        return None
    lo, hi = declared["relative_range"]
    return (float(lo), float(hi))


def _ratio(numerator: FunctionalBuilder, terms: Sequence[FunctionalBuilder]) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        total: Expr = terms[0](s, a)
        for term in terms[1:]:
            total = total + term(s, a)
        return numerator(s, a) / total

    return build


class _Planner:
    def __init__(
        self,
        ctx: BuildContext,
        state: Mapping[str, float],
        inventory: InventoryPlan,
        tables: Mapping[str, LcaTable],
    ) -> None:
        self.ctx = ctx
        self.state = state
        self.doc = ctx.spec.document
        self.lca: Mapping[str, Any] = dict(self.doc.get("lca", {}))
        self.inventory = inventory
        self.tables = tables
        self.sctx = SizingContext(ctx, state)
        self.out = ImpactPlan()
        cost = ctx.earlier.get("cost")
        self.cost_theta: dict[str, Theta] = (
            {} if cost is None else {t.theta_id: t for t in cost.theta}
        )

    def _theta(self, theta_id: str, value: float, unit: str, provenance: str) -> None:
        if theta_id in self.cost_theta or any(t.theta_id == theta_id for t in self.out.theta):
            return
        self.out.theta.append(Theta(theta_id, value, unit, provenance, _ranged(self.doc, theta_id)))

    def hours(self) -> str:
        if HOURS not in self.cost_theta:
            operation = dict(self.doc.get("operation", {}))
            if "hours_per_year" in operation:
                value, why = float(operation["hours_per_year"]), "operation.hours_per_year"
            else:
                entry = default("operation.hours_per_year")
                value, why = float(entry.value), f"default {entry.key}: {entry.text}"
                self.out.defaulted.append(
                    {"key": "operation.hours_per_year", "value": value, "target": "lca"}
                )
            self._theta(HOURS, value, "h/yr", why)
        return HOURS

    def functional_unit(self) -> tuple[FunctionalBuilder, str] | None:
        fu = self.lca.get("functional_unit")
        if fu is None:
            return None
        basis = str(fu["basis"])
        molar = basis == "molar_total"
        flow = stream_flow(self.sctx, str(fu["connection"]), basis, fu.get("component"), molar)
        return flow, "mol" if molar else "kg"

    def allocation(self) -> FunctionalBuilder | None | Refusal:
        """The factor's builder; `None` for no factor; a refusal when it cannot be formed."""
        spec = dict(self.lca.get("allocation", {"method": "none"}))
        method = str(spec["method"])
        if method in ("none", "substitution"):
            return None
        if method == "factor":
            if "factor" not in spec:
                return Refusal("METRIC_UNDEFINED", "lca.allocation", "method factor needs `factor`")
            theta_id = "asm:lca.allocation.factor"
            self._theta(theta_id, float(spec["factor"]), "1", "lca.allocation.factor")
            return lambda s, a: s.theta(theta_id)
        fu = self.lca.get("functional_unit")
        if fu is None:
            return Refusal(
                "METRIC_UNDEFINED", "lca.allocation", f"{method} needs a functional unit"
            )
        materials = {str(m["connection"]): m for m in self.doc.get("materials", ())}
        products = [str(p) for p in spec.get("products", ())] or [
            s for s, m in materials.items() if m["role"] in ("product", "co_product")
        ]
        if not products:
            return Refusal("METRIC_UNDEFINED", "lca.allocation", "no products to allocate over")
        fu_stream = str(fu["connection"])
        if method == "mass":
            numerator = self.sctx.mass_builder(fu_stream)
            terms = [self.sctx.mass_builder(p) for p in products]
        else:
            priced: list[FunctionalBuilder] = []
            for stream in [fu_stream, *products]:
                price = self.cost_theta.get(f"asm:material.{stream}.price")
                material = materials.get(stream)
                if price is None or material is None:
                    return Refusal(
                        "METRIC_UNDEFINED", "lca.allocation", f"economic: {stream} has no price"
                    )
                molar = "/kg" not in price.unit
                flow = stream_flow(
                    self.sctx, stream, str(material["basis"]), material.get("component"), molar
                )
                priced.append(_priced(price.theta_id, flow))
            numerator, terms = priced[0], priced[1:]
        denominator = _ratio(_one, terms)  # 1/Σ, evaluated only to test the sign
        check = OutputDef("derived.lca_allocation_check", "1", denominator)
        theta = [*self.cost_theta.values(), *self.out.theta]
        cost = self.ctx.earlier.get("cost")
        blocks = () if cost is None else cost.blocks
        try:
            value = self.ctx.evaluate(self.state, [check], theta, blocks)[check.output_id]
        except TwinEvaluationError as error:
            return Refusal("ASSESSMENT_EVALUATION_FAILED", "lca.allocation", str(error))
        if not value > 0.0:
            return Refusal(
                "ASSESSMENT_EVALUATION_FAILED", "lca.allocation", "non-positive denominator"
            )
        return _ratio(numerator, terms)

    def plan(self, categories: Sequence[str]) -> ImpactPlan:
        out = self.out
        exchanges = self.inventory.exchanges
        withheld = self.inventory.withheld
        allocation = self.allocation() if categories else None
        if isinstance(allocation, Refusal):
            out.refusals.append(allocation)
        hours = self.hours() if categories else HOURS
        fu = self.functional_unit()
        for m in categories:
            ids = [f"impact.{m}.rate", f"impact.{m}.annual", f"impact.{m}.per_fu"]
            # A withheld exchange is reported where it was refused; nothing more is looked up.
            unit = None if withheld else self._unit(m)
            reason = self._blocked(m, exchanges, withheld, allocation, unit)
            if reason is not None:
                out.unavailable.extend((i, reason) for i in ids)
                continue
            assert unit is not None
            terms: list[tuple[str, str]] = []
            for e in exchanges:
                table = self.tables[e.table_id]
                letter = "q" if isinstance(table, UnitScoreTable) else "c"
                theta_id = f"asm:lca.{letter}.{e.table_id}.{m}.{e.column}"
                value = table.value(m, e.column)
                assert value is not None
                self._theta(
                    theta_id, value, f"{unit}/{e.unit[:-2]}", f"{e.table_id} {m} {e.column}"
                )
                terms.append((theta_id, e.output_id))
            factor = allocation if not isinstance(allocation, Refusal) else None
            out.outputs.append(OutputDef(ids[0], f"{unit}/s", _rate(terms, factor)))
            out.outputs.append(OutputDef(ids[1], f"{unit}/yr", _annual(ids[0], hours)))
            if fu is None:
                out.unavailable.append((ids[2], "no functional unit declared"))
            else:
                flow, per = fu
                out.outputs.append(OutputDef(ids[2], f"{unit}/{per}", _per_fu(ids[0], flow)))
        if any(o.output_id.startswith("impact.") for o in out.outputs):
            out.limitations.append(Limitation("LCA_BACKGROUND_UNCERTAINTY_NOT_PROPAGATED", "lca"))
            out.limitations.append(Limitation("LCA_CAPITAL_GOODS_EXCLUDED", "lca"))
        return out

    def _unit(self, m: str) -> str | None:
        units = {
            c.unit
            for t_id in [*self.lca.get("tables", ()), *self.lca.get("direct_factors", ())]
            if (t := self.tables.get(str(t_id))) is not None
            for c in t.categories
            if c.category_id == m
        }
        if len(units) == 1:
            return units.pop()
        self.out.refusals.append(
            Refusal(
                "LCA_ACTIVITY_UNKNOWN",
                f"lca.categories.{m}",
                "no listed table carries it" if not units else f"units disagree: {sorted(units)}",
            )
        )
        return None

    def _blocked(
        self,
        m: str,
        exchanges: Sequence[Exchange],
        withheld: Sequence[tuple[str, str]],
        allocation: FunctionalBuilder | None | Refusal,
        unit: str | None,
    ) -> str | None:
        if withheld:
            return f"exchanges withheld: {[k for k, _ in withheld]}"
        if unit is None:
            return f"category {m}: no unique unit in the listed tables"
        if isinstance(allocation, Refusal):
            return f"allocation: {allocation.detail}"
        missing = [e for e in exchanges if self.tables[e.table_id].value(m, e.column) is None]
        for e in missing:
            code = "LCA_ACTIVITY_UNKNOWN" if e.kind == "technosphere" else "LCA_FLOW_UNKNOWN"
            self.out.refusals.append(Refusal(code, f"{e.table_id}.{m}", f"no score for {e.column}"))
        if missing:
            return f"tables without category {m}: {sorted({e.table_id for e in missing})}"
        return None


def _one(s: Symbols, a: Algebra) -> Expr:
    return 1.0


def _priced(theta_id: str, flow: FunctionalBuilder) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        return s.theta(theta_id) * flow(s, a)

    return build


def _annual(rate: str, hours: str) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        return annual(s.out(rate), s.theta(hours))

    return build


def _per_fu(rate: str, flow: FunctionalBuilder) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        return s.out(rate) / flow(s, a)

    return build


def _rate(terms: Sequence[tuple[str, str]], factor: FunctionalBuilder | None) -> FunctionalBuilder:
    """`A_fac · Σ θ·out(inventory)`, a left fold in construction order; `0.0` for no exchange."""

    def build(s: Symbols, a: Algebra) -> Expr:
        total: Expr = 0.0
        for k, (theta_id, output_id) in enumerate(terms):
            term = s.theta(theta_id) * s.out(output_id)
            total = term if k == 0 else total + term
        if factor is None:
            return total
        return factor(s, a) * total

    return build


def plan_impacts(
    ctx: BuildContext,
    state: Mapping[str, float],
    inventory: InventoryPlan,
    tables: Mapping[str, LcaTable],
    categories: Sequence[str],
) -> ImpactPlan:
    """The impact outputs of `categories` over the planned inventory (§4.8.3)."""
    return _Planner(ctx, state, inventory, tables).plan(categories)
