"""The foreground inventory: boundary exchanges `a_k(x)`, `b_e(x)` (E01 design §4.8.1).

- **Technosphere** (`utilities[].lca`, `materials[].lca`): `a_k = α_k · φ_k(x)` in the activity's
  unit per second, with `α_k = amount / SI(per)` (θ `asm:lca.alpha.<k>`; the document states
  `amount` activity units per `per` unit of the boundary quantity) and `φ_k` the boundary quantity
  in SI:
  - a heating or cooling utility's energy rate `Σ |Q|` over the items that use it (W);
  - electricity taken **net**: `Σ` consumption `−` `Σ` generation (W), so a net generator gives a
    negative `a_k` (§4.8.1 "generation carries a negative sign"); a motor-driven machine's
    consumption is the cost contributor's `size.<U>.drive.power` output (W/η_m, §9.2.7) and a
    turbine's generation `−W·η_gen`, the same expressions the operating cost nets;
  - a material's stream: mass `ṁ` (kg/s) for `per` in kg/t, amount `ṅ` (mol/s) for mol/kmol, on
    the material's `basis` (`mass_total`, `component`, `molar_total`).
  This is track A's convention for the LCA hand expectations (`benchmarks/e01/lca_hand/`,
  `docs/E01A_DECISIONS.md` WO-A5); the activity's `si_per_unit` is not on this path.
- **Biosphere** (a material with role `emission`): each mapped component `c` gives
  `b_e = M_c · n_c` (kg/s) to the direct-factor table's flow.

Exchange ids `<k>`: `utility.<u>.<activity>`, `material.<s>.<activity>`, `emission.<s>.<c>` (a
repeated id gets `.<j>`); each is the output `inventory.<k>.rate`. Construction order is document
order: utilities, then materials (§4.2.4 step 6). A utility exchange needs the cost contributor's
plan (its sizing defines the utility's users); without it the exchange is withheld.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from openflowsheet.assessment.cost.operating import ENERGY_PER, PER_SI
from openflowsheet.assessment.lca.tables import (
    DirectFactorTable,
    LcaTable,
    UnitScoreTable,
)
from openflowsheet.assessment.linearization import Refusal
from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    FunctionalBuilder,
    Limitation,
    Symbols,
    Theta,
)
from openflowsheet.assessment.sizing import SizedItem, SizingContext, plan_sizing
from openflowsheet.compile.spec import Algebra, Expr
from openflowsheet.models import flow_id
from openflowsheet.models.thermal.state import vapor_id

__all__ = ["Exchange", "InventoryPlan", "plan_inventory", "stream_flow"]

MASS_PER: Final = frozenset({"kg", "t"})
MOLAR_PER: Final = frozenset({"mol", "kmol"})
SI_UNIT: Final[Mapping[str, str]] = {
    **{p: "J" for p in ENERGY_PER},
    **{p: "kg" for p in MASS_PER},
    **{p: "mol" for p in MOLAR_PER},
}


@dataclass(frozen=True)
class Exchange:
    """One foreground exchange: `a_k = α_k·φ_k` (technosphere) or `b_e = φ_e` (biosphere)."""

    exchange_id: str
    kind: Literal["technosphere", "biosphere"]
    table_id: str
    column: str
    unit: str
    phi: FunctionalBuilder
    alpha: Theta | None = None

    @property
    def output_id(self) -> str:
        return f"inventory.{self.exchange_id}.rate"

    def build(self, s: Symbols, a: Algebra) -> Expr:
        if self.alpha is None:
            return self.phi(s, a)
        return s.theta(self.alpha.theta_id) * self.phi(s, a)


@dataclass
class InventoryPlan:
    exchanges: list[Exchange] = field(default_factory=list)
    theta: list[Theta] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    #: Exchanges that could not be built, `(exchange id, reason)`: every impact depends on them.
    withheld: list[tuple[str, str]] = field(default_factory=list)


def _fold(builders: Sequence[FunctionalBuilder]) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        total: Expr = builders[0](s, a)
        for b in builders[1:]:
            total = total + b(s, a)
        return total

    return build


def _output(output_id: str) -> FunctionalBuilder:
    def build(s: Symbols, a: Algebra) -> Expr:
        return s.out(output_id)

    return build


def stream_flow(
    sctx: SizingContext, stream: str, basis: str, component: str | None, molar: bool
) -> FunctionalBuilder:
    """A stream's boundary quantity on `basis`: mass (kg/s) or, when `molar`, amount (mol/s)."""
    masses = sctx.ctx.view.molar_masses()
    if basis == "mass_total" and not molar:
        return sctx.mass_builder(stream)
    if basis == "molar_total" or (basis == "component" and vapor_id(stream) in sctx.variables):
        moles = sctx.moles_builder(stream)
        if molar:
            return moles
        if basis == "component":
            m = masses[str(component)]
            return lambda s, a: moles(s, a) * m
        return sctx.mass_builder(stream)
    if basis == "mass_total":  # molar amount of a mass-basis material
        return sctx.moles_builder(stream)
    name = flow_id(stream, str(component))
    if molar:
        return lambda s, a: s.x(name)
    m = masses[str(component)]
    return lambda s, a: s.x(name) * m


class _Electricity:
    """`φ = Σ consumption − Σ generation` (W) over the cost plan's electric items."""

    def __init__(self, items: Sequence[SizedItem], cost_outputs: frozenset[str]) -> None:
        self.consume: list[FunctionalBuilder] = []
        self.generate: list[FunctionalBuilder] = []
        for item in items:
            if item.electricity is None or item.power is None:
                continue
            if item.electricity == "generation":
                self.generate.append(item.power)
            elif item.size.get("power") in cost_outputs:
                output = str(item.size["power"])
                self.consume.append(_output(output))
            else:
                self.consume.append(item.power)

    def __bool__(self) -> bool:
        return bool(self.consume or self.generate)

    def build(self, s: Symbols, a: Algebra) -> Expr:
        total: Expr = 0.0
        for k, b in enumerate(self.consume):
            total = b(s, a) if k == 0 else total + b(s, a)
        for b in self.generate:
            total = total - b(s, a)
        return total


def _alpha(
    doc: Mapping[str, Any], exchange_id: str, amount: float, per: str, unit: str, path: str
) -> Theta:
    theta_id = f"asm:lca.alpha.{exchange_id}"
    declared = dict(doc.get("uncertainty", {})).get(theta_id)
    span = None if declared is None else tuple(map(float, declared["relative_range"]))
    return Theta(
        theta_id,
        amount / PER_SI[per],
        f"{unit}/{SI_UNIT[per]}",
        f"{path} ({amount!r} {unit} per {per})",
        span,  # type: ignore[arg-type]
    )


def plan_inventory(
    ctx: BuildContext,
    state: Mapping[str, float],
    tables: Mapping[str, LcaTable],
    refused_tables: Mapping[str, Refusal],
) -> InventoryPlan:
    """The exchanges the document declares, in construction order (§4.2.4 step 6)."""
    doc = ctx.spec.document
    run = _Inventory(doc, tables, refused_tables)
    sctx = SizingContext(ctx, state)
    cost: ContributionPlan | None = ctx.earlier.get("cost")

    utilities = [u for u in doc.get("utilities", ()) if u.get("lca")]
    items: tuple[SizedItem, ...] = ()
    cost_outputs: frozenset[str] = frozenset()
    if utilities and cost is not None:
        items = plan_sizing(ctx, state)[0].items
        cost_outputs = frozenset(o.output_id for o in cost.outputs)
    for utility in utilities:
        run.add_utility(utility, cost, items, cost_outputs)
    for material in doc.get("materials", ()):
        s_id, basis = str(material["connection"]), str(material["basis"])
        component = material.get("component")
        for j, body in enumerate(material.get("lca", ())):
            per = str(body["per"])
            molar = per in MOLAR_PER
            phi = (
                stream_flow(sctx, s_id, basis, component, molar)
                if per in MASS_PER | MOLAR_PER
                else None
            )
            run.technosphere(
                f"materials.{s_id}.lca[{j}]",
                f"material.{s_id}",
                body,
                phi,
                MASS_PER | MOLAR_PER,
                "a stream's mass or amount",
            )
        if material["role"] != "emission" or "emission" not in material:
            continue
        emission = material["emission"]
        table_id = str(emission["table"])
        for c, flow in emission["flows"].items():
            k = run.exchange_id(f"emission.{s_id}.{c}")
            target = f"{table_id}.{flow}"
            table = run.table_of(table_id, DirectFactorTable, target, "LCA_FLOW_UNKNOWN")
            if table is None:
                run.plan.withheld.append((k, f"table {table_id} unusable"))
                continue
            if flow not in table.columns or c not in ctx.view.components:
                detail = "not in the table" if flow not in table.columns else f"no component {c}"
                run.plan.refusals.append(Refusal("LCA_FLOW_UNKNOWN", target, detail))
                run.plan.withheld.append((k, f"{target}: {detail}"))
                continue
            run.plan.exchanges.append(
                Exchange(
                    k,
                    "biosphere",
                    table_id,
                    str(flow),
                    "kg/s",
                    stream_flow(sctx, s_id, "component", str(c), False),
                )
            )
    return run.plan


@dataclass
class _Inventory:
    """`plan_inventory`'s run: the plan being built and the exchange ids taken so far."""

    doc: Mapping[str, Any]
    tables: Mapping[str, LcaTable]
    refused_tables: Mapping[str, Refusal]
    plan: InventoryPlan = field(default_factory=InventoryPlan)
    used: dict[str, int] = field(default_factory=dict)

    def add_utility(
        self,
        utility: Mapping[str, Any],
        cost: ContributionPlan | None,
        items: tuple[SizedItem, ...],
        cost_outputs: frozenset[str],
    ) -> None:
        """A utility's exchanges, one per `lca` entry, on its energy rate (electricity: net, with
        an `ELECTRICITY_NETTED` limitation when an item generates). With a cost plan and no item
        using the utility, none; without a cost plan, each entry is withheld."""
        u = str(utility["utility_id"])
        phi: FunctionalBuilder | None = None
        why = "no cost plan defines the utility's users"
        if cost is not None:
            phi = self.utility_phi(u, utility["kind"], items, cost_outputs)
            why = "the utility has no users"
        for j, body in enumerate(utility["lca"]):
            if phi is None and cost is not None:
                continue  # no item uses the utility: no exchange (as the operating cost)
            self.technosphere(f"utilities.{u}.lca[{j}]", f"utility.{u}", body, phi, ENERGY_PER, why)

    def utility_phi(
        self, u: str, kind: Any, items: tuple[SizedItem, ...], cost_outputs: frozenset[str]
    ) -> FunctionalBuilder | None:
        """Utility `u`'s energy rate over the cost plan's items that use it: electricity net
        (appending `ELECTRICITY_NETTED` to the plan when an item generates), else the sum of the
        users' duties; `None` when no item uses it."""
        phi: FunctionalBuilder | None
        if kind == "electricity":
            net = _Electricity(items, cost_outputs)
            phi = net.build if net else None
            if net.generate:
                self.plan.limitations.append(Limitation("ELECTRICITY_NETTED", f"lca.{u}"))
        else:
            users = [i.duty for i in items if i.utility == u and i.duty is not None]
            phi = _fold(users) if users else None
        return phi

    def technosphere(
        self,
        path: str,
        base: str,
        body: Mapping[str, Any],
        phi: FunctionalBuilder | None,
        kinds: frozenset[str],
        why: str,
    ) -> None:
        k = self.exchange_id(f"{base}.{body['activity']}")
        target = f"{body['table']}.{body['activity']}"
        table = self.table_of(str(body["table"]), UnitScoreTable, target, "LCA_ACTIVITY_UNKNOWN")
        if table is None:
            self.plan.withheld.append((k, f"table {body['table']} unusable"))
            return
        activity = table.activity(str(body["activity"]))
        if activity is None:
            self.plan.refusals.append(Refusal("LCA_ACTIVITY_UNKNOWN", target, "not in the table"))
            self.plan.withheld.append((k, f"{target} unknown"))
            return
        per = str(body["per"])
        if per not in kinds:
            self.plan.refusals.append(
                Refusal("LCA_ACTIVITY_UNKNOWN", f"{path}.per", f"`per: {per}` does not fit {why}")
            )
            self.plan.withheld.append((k, f"`per: {per}` does not fit"))
            return
        if phi is None:
            self.plan.withheld.append((k, why))
            return
        alpha = _alpha(self.doc, k, float(body["amount"]), per, activity.unit, path)
        self.plan.theta.append(alpha)
        self.plan.exchanges.append(
            Exchange(
                k,
                "technosphere",
                table.table_id,
                activity.activity_id,
                f"{activity.unit}/s",
                phi,
                alpha,
            )
        )

    def exchange_id(self, base: str) -> str:
        self.used[base] = self.used.get(base, 0) + 1
        return base if self.used[base] == 1 else f"{base}.{self.used[base]}"

    def table_of(self, table_id: str, wanted: type, target: str, code: str) -> Any:
        if table_id in self.refused_tables:
            r = self.refused_tables[table_id]
            self.plan.refusals.append(Refusal(r.code, target, r.detail))
            return None
        table = self.tables.get(table_id)
        if not isinstance(table, wanted):
            listing = "lca.tables" if wanted is UnitScoreTable else "lca.direct_factors"
            self.plan.refusals.append(
                Refusal(code, target, f"table {table_id!r} is not in {listing}")
            )
            return None
        return table
