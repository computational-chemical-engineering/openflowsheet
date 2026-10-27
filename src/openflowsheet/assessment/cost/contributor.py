"""The `cost` contributor: sizing → cost forms → escalation → bare module → capital chain →
operating cost → annualisation (E01 design §4.5–§4.7, §9.2.6, §9.2.7; ADR 0052).

Every choice (correlation, options, size and piece regimes, drive inclusion, domain checks) is made
here on floats at the planning state, or taken from the held regime, and handed to the builders
as data (§4.2.2). Sums are left folds in construction order (§4.2.4): items in the host's unit
order, utilities and materials in document order, then chain steps and fixed lines.

An output that would depend on a refused, not excluded item, or on an input the document lacks,
is not built: it is listed in `ContributionPlan.unavailable` with its reason (§4.9, A40).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.assessment.cost import capital, forms, operating, quotes, sets
from openflowsheet.assessment.cost.index import (
    SHIPPED_SERIES,
    IndexSeries,
    SourceBasis,
    TargetBasis,
    escalate,
    load_rates,
    load_series,
    series_from,
)
from openflowsheet.assessment.defaults import default
from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    FunctionalBuilder,
    Limitation,
    OutputDef,
    Refusal,
    Symbols,
    Theta,
    register_contributor,
)
from openflowsheet.assessment.regimes import AdmissibilityRow, RegimeEntry, size_units
from openflowsheet.assessment.sizing import SizedItem, SizingPlan, plan_sizing
from openflowsheet.canonical import document_sha256
from openflowsheet.compile.spec import Algebra, Expr
from openflowsheet.models import flow_id
from openflowsheet.models.thermal.state import vapor_id

__all__ = ["CostContributor", "ItemCost"]

#: The SSLW option an item's top-level `material`/`tray_type`/`subtype` keys stand for, per entry.
_MATERIAL_OPTIONS: Final = ("material", "tray_material")
_SUBTYPE_OPTIONS: Final = ("hx_type", "pump_type", "compressor_type", "motor_type")
#: Form input → the item's `size` quantity it reads (§9.2.4).
_SIZE_INPUT: Final = {
    "area": "area",
    "diameter": "diameter",
    "length": "height",
    "vol_flow": "vol_flow",
    "head": "head",
    "power": "power",
}
#: Refusal codes that concern an item's capital only (the operating cost still stands).
_CAPITAL_CODES: Final = frozenset(
    {
        "NO_CORRELATION",
        "CORRELATION_OUT_OF_RANGE",
        "BARE_MODULE_FACTOR_MISSING",
        "ESCALATION_SERIES_MISSING",
        "INDEX_YEAR_UNAVAILABLE",
        "EXCHANGE_RATE_UNAVAILABLE",
    }
)


@dataclass
class ItemCost:
    """One item's provenance for the report (§4.5.5), filled while planning."""

    item_id: str
    family: str
    source: dict[str, Any] = field(default_factory=dict)
    regime: dict[str, str] = field(default_factory=dict)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    escalation: dict[str, Any] | None = None
    accuracy_class: int | None = None
    relative_range: tuple[float, float] | None = None
    extrapolated: bool = False
    purchased: str | None = None
    bare_module: str | None = None
    included_in: str | None = None


def _out(output_id: str) -> FunctionalBuilder:
    return lambda s, a: s.out(output_id)


def _fold(ids: Sequence[str]) -> FunctionalBuilder:
    """`Σ out(id)` as a left fold in `ids` order; `0.0` for none."""

    def build(s: Symbols, a: Algebra) -> Expr:
        if not ids:
            return 0.0
        total: Expr = s.out(ids[0])
        for name in ids[1:]:
            total = total + s.out(name)
        return total

    return build


def _theta_value(theta_id: str) -> FunctionalBuilder:
    return lambda s, a: s.theta(theta_id)


def _scaled(theta_id: str, output_id: str) -> FunctionalBuilder:
    return lambda s, a: s.theta(theta_id) * s.out(output_id)


def _flow_cost(flow: FunctionalBuilder, price: str, hours: str) -> FunctionalBuilder:
    """`annual(p·ṅ, h)` (§4.7.2)."""
    return lambda s, a: operating.annual(s.theta(price) * flow(s, a), s.theta(hours))


def _energy_cost(
    consume: tuple[SizedItem, ...],
    generate: tuple[SizedItem, ...],
    price: str,
    export: str,
    hours: str,
) -> FunctionalBuilder:
    """`annual(p·Σ consumed, h) − Σ annual(q·generated, h)` (§4.7.2; netting when q = p)."""

    def build(s: Symbols, a: Algebra) -> Expr:
        total: Expr = 0.0
        for k, i in enumerate(consume):
            rate_of = i.power or i.duty
            assert rate_of is not None
            rate = rate_of(s, a)
            total = rate if k == 0 else total + rate
        cost: Expr = operating.annual(s.theta(price) * total, s.theta(hours))
        for i in generate:
            assert i.power is not None
            cost = cost - operating.annual(s.theta(export) * i.power(s, a), s.theta(hours))
        return cost

    return build


def _covered(target: str, excluded: Mapping[str, str]) -> bool:
    return any(target == x or target.startswith(x + ".") for x in excluded)


class _Planner:
    """One planning pass of the `cost` contributor."""

    def __init__(self, ctx: BuildContext, state: Mapping[str, float]) -> None:
        self.ctx = ctx
        self.doc: Mapping[str, Any] = ctx.spec.document
        self.sizing, self.sctx = plan_sizing(ctx, state)
        self.sizing_plan: SizingPlan = self.sizing
        self.outputs: list[OutputDef] = []
        self.theta: list[Theta] = []
        self.entries: list[RegimeEntry] = []
        self.refusals: list[Refusal] = []
        self.limitations: list[Limitation] = []
        self.unavailable: dict[str, str] = {}
        self.defaulted: list[dict[str, Any]] = []
        self.records: list[ItemCost] = []
        self.excluded: dict[str, str] = {
            item_id: str(body["exclude"]["reason"])
            for item_id, body in dict(self.doc.get("items", {})).items()
            if "exclude" in body
        }
        self.selections: dict[str, forms.Selection] = {}
        self.item_values: dict[str, float] = {}

    # -- basis (§4.6) ----------------------------------------------------------------------------

    def basis(self) -> None:
        basis = dict(self.doc["basis"])
        escalation = dict(basis.get("escalation_series", {}))
        for currency in ("USD", "EUR"):
            if currency not in escalation:
                escalation[currency] = str(default(f"escalation_series.{currency}").value)
                self._defaulted(f"escalation_series.{currency}", escalation[currency])
        lf_doc = basis.get("location_factor")
        if lf_doc is None:
            lf = float(default("basis.location_factor").value)
            self._defaulted("basis.location_factor", lf)
        else:
            lf = float(lf_doc["value"])
        self.target = TargetBasis(str(basis["currency"]), int(basis["year"]), escalation, lf)
        rates_id = basis.get("exchange_rates")
        if rates_id is None:
            rates_id = str(default("exchange_rates").value)
            self._defaulted("exchange_rates", rates_id)
        self.rates = load_rates(str(rates_id))
        self.series: dict[str, IndexSeries] = {sid: load_series(sid) for sid in SHIPPED_SERIES}
        for ref in dict(self.doc.get("data", {})).get("series", ()):
            if ref["id"] in self.series or "path" not in ref:
                continue
            document = json.loads(Path(ref["path"]).read_text(encoding="utf-8"))
            if document_sha256(document) == ref["sha256"]:
                self.series[str(ref["id"])] = series_from(document)
        operation = dict(self.doc.get("operation", {}))
        self.op: dict[str, Theta] = {}
        for key, unit, structural in (
            ("hours_per_year", "h/yr", False),
            ("lifetime_years", "yr", True),
            ("discount_rate", "1/yr", True),
        ):
            if key in operation:
                value, provenance = float(operation[key]), f"operation.{key}"
            else:
                entry = default(f"operation.{key}")
                value, provenance = float(entry.value), f"default {entry.key}: {entry.text}"
                self._defaulted(f"operation.{key}", value)
            self.op[key] = self._theta(f"asm:operation.{key}", value, unit, provenance, structural)

    def _defaulted(self, key: str, value: Any, target: str = "") -> None:
        self.defaulted.append({"key": key, "value": value, "target": target})

    def _theta(
        self,
        theta_id: str,
        value: float,
        unit: str,
        provenance: str,
        structural: bool = False,
        relative_range: tuple[float, float] | None = None,
    ) -> Theta:
        declared = dict(self.doc.get("uncertainty", {})).get(theta_id)
        if declared is not None:
            lo, hi = declared["relative_range"]
            relative_range = (float(lo), float(hi))
        theta = Theta(theta_id, value, unit, provenance, relative_range, structural)
        self.theta.append(theta)
        return theta

    def _escalation(self, source: SourceBasis, record: ItemCost) -> float | Refusal:
        found = escalate(source, self.target, self.series, self.rates)
        if isinstance(found, Refusal):
            return Refusal(found.code, found.target or record.item_id, found.detail)
        self.limitations.extend(lim for lim in found.limitations if lim not in self.limitations)
        record.escalation = {
            "factor": found.factor,
            "index_ratio": found.index_ratio,
            "exchange": found.exchange,
            "location_factor": found.location,
            "series": found.series_id,
            "base": list(found.base),
            "target": list(found.target),
        }
        return found.factor

    # -- items (§4.5) ----------------------------------------------------------------------------

    def items(self) -> None:
        values = self.sctx.values(self.sizing.outputs, self.sizing.theta)
        self.item_values = values
        sizing_refused = [r.target for r in self.sizing.refusals]
        self.capital_refused: list[str] = []
        self.opex_refused: list[str] = []
        for target in sizing_refused:
            if not _covered(target, self.excluded):
                self.capital_refused.append(target)
                self.opex_refused.append(target)
        machines: dict[str, SizedItem] = {}
        for item in self.sizing.items:
            if item.family in ("machine.pump", "machine.compressor"):
                machines[item.unit_id] = item
            record = ItemCost(item.item_id, item.family)
            if item.item_id in self.excluded:
                continue
            already = any(
                t == item.item_id or t.startswith(item.item_id + ".") for t in sizing_refused
            )
            refusal = self._cost_item(item, record, values, machines, already)
            if refusal is not None:
                self.refusals.append(refusal)
                self.capital_refused.append(refusal.target)
            elif record.purchased is not None or record.bare_module is not None:
                self.records.append(record)

    def _item_doc(self, item: SizedItem) -> Mapping[str, Any]:
        return self.sctx.item(item.item_id)

    def _cost_item(
        self,
        item: SizedItem,
        record: ItemCost,
        values: Mapping[str, float],
        machines: Mapping[str, SizedItem],
        already: bool,
    ) -> Refusal | None:
        doc = self._item_doc(item)
        if "quote" in doc:
            return self._quote(item, record, values, quotes.quote_from(doc["quote"]))
        if item.family == "machine.drive":
            machine = machines.get(item.unit_id)
            if machine is not None and machine.item_id in self.included_drive:
                record.included_in = machine.item_id
                record.source = {"included_in": machine.item_id}
                purchased = f"capex.purchased.{item.item_id}"
                self.outputs.append(OutputDef(purchased, self.target.currency, lambda s, a: 0.0))
                record.purchased = purchased
                record.bare_module = f"capex.bare_module.{item.item_id}"
                self.outputs.append(
                    OutputDef(record.bare_module, self.target.currency, lambda s, a: 0.0)
                )
                return None
        found = self._entry(item, doc)
        if isinstance(found, Refusal):
            return found
        cost_set, e = found
        form = forms.FORMS[e.form]
        x_float: dict[str, Any] = {}
        x_build: dict[str, FunctionalBuilder] = {}
        for name in form.inputs:
            got = self._input(item, record, e, name, values)
            if got is None:
                if already:
                    return None
                return Refusal("SIZING_INPUT_UNAVAILABLE", f"{item.item_id}.{name}")
            x_float[name], x_build[name] = got
        units = 1
        if form.inherits_units:
            machine = machines.get(item.unit_id)
            if machine is not None and machine.item_id in self.selections:
                units = self.selections[machine.item_id].n
        allow = bool(doc.get("allow_extrapolation", False))
        sel = forms.select(form, e, x_float, allow_extrapolation=allow, units=units)
        if isinstance(sel, forms.OutOfRange):
            return Refusal(
                "CORRELATION_OUT_OF_RANGE",
                f"{item.item_id}.{sel.target}",
                f"{sel.range_name} = {sel.value!r} not in [{sel.low!r}, {sel.high!r}] {sel.detail}",
            )
        sel = self._held(item.item_id, form, e, sel)
        self.selections[item.item_id] = sel
        if e.includes_drive:
            self.included_drive.add(item.item_id)
        for name, (value, low, high) in sel.extrapolated.items():
            record.extrapolated = True
            self.limitations.append(
                Limitation(
                    "CORRELATION_EXTRAPOLATED",
                    f"{item.item_id}.{form.target(name)}",
                    {"value": value, "range": [low, high]},
                )
            )
        self._regime(item.item_id, form, e, sel, x_build, record)
        source = SourceBasis(
            str(cost_set.document["basis"]["currency"]),
            index=(str(cost_set.document["basis"]["index"]["series"]), cost_set.index_value),
            year_equivalent=int(cost_set.document["basis"]["year_equivalent"]["year"]),
            set_id=cost_set.set_id,
        )
        factor = self._escalation(source, record)
        if isinstance(factor, Refusal):
            return factor
        entry_doc = cost_set.entry(e.entry_id).document
        record.accuracy_class = int(
            entry_doc.get("accuracy_class", cost_set.document["accuracy_class"])
        )
        rr = entry_doc.get("uncertainty", {}).get("relative_range")
        record.relative_range = None if rr is None else (float(rr[0]), float(rr[1]))
        record.source = {
            "set": e.set_id,
            "entry": e.entry_id,
            "form": e.form,
            "citation": cost_set.document["source"].get("citation"),
            "source_lines": dict(e.sources),
            "options": dict(e.options),
            "options_defaulted": list(e.defaulted),
        }
        if e.ratio != 1.0:
            index = entry_doc["index_basis"]
            record.source["index_basis"] = (
                f"{index['series']} {sets._number(index['value']):g} → "
                f"{cost_set.index_value:g} by the source's ratio"
            )
        for name in e.defaulted:
            self._defaulted(f"option.{name}", e.options[name], item.item_id)

        def base(s: Symbols, a: Algebra) -> Expr:
            x = {name: build(s, a) for name, build in x_build.items()}
            return form.cost(e, x, sel, a)

        return self._capital(item, record, base, factor, doc, entry_doc)

    def _quote(
        self, item: SizedItem, record: ItemCost, values: Mapping[str, float], q: quotes.Quote
    ) -> Refusal | None:
        size_id: str | None = None
        if q.size_quantity is not None:
            size_id = item.size.get(q.size_quantity)
            if size_id is None and q.exponent is not None:
                return Refusal("SIZING_INPUT_UNAVAILABLE", f"{item.item_id}.{q.size_quantity}")
            if size_id is not None:
                mismatch = quotes.size_mismatch(q, item.item_id, values[size_id])
                if mismatch is not None:
                    self.limitations.append(mismatch)
        factor = self._escalation(SourceBasis(q.currency, q.year), record)
        if isinstance(factor, Refusal):
            return factor
        record.source = {
            "quote": {
                "source": q.source,
                "kind": q.kind,
                "form": q.form,
                "currency": q.currency,
                "year": q.year,
            }
        }
        record.accuracy_class = q.accuracy_class
        record.relative_range = q.relative_range

        def base(s: Symbols, a: Algebra) -> Expr:
            size = None if q.exponent is None or size_id is None else s.out(size_id)
            return q.cost_expr(1.0, size, a)

        return self._capital(item, record, base, factor, self._item_doc(item), {}, kind=q.kind)

    def _capital(
        self,
        item: SizedItem,
        record: ItemCost,
        base: FunctionalBuilder,
        factor: float,
        doc: Mapping[str, Any],
        entry_doc: Mapping[str, Any],
        kind: str = "purchased",
    ) -> Refusal | None:
        """`C = C_base·E·u` (`u` = 1.0, the item's accuracy θ) and `C_BM = F_BM·C` (§4.5.1)."""
        cur = self.target.currency
        e_theta = self._theta(
            f"asm:item.{item.item_id}.E", factor, "1", f"escalation to {self.target.year}"
        )
        u_theta = self._theta(
            f"asm:item.{item.item_id}.accuracy",
            1.0,
            "1",
            "cost-correlation accuracy multiplier (§4.9)",
            relative_range=record.relative_range,
        )

        def cost(s: Symbols, a: Algebra) -> Expr:
            return base(s, a) * s.theta(e_theta.theta_id) * s.theta(u_theta.theta_id)

        if kind == "bare_module":
            record.bare_module = f"capex.bare_module.{item.item_id}"
            self.outputs.append(OutputDef(record.bare_module, cur, cost))
            return None
        record.purchased = f"capex.purchased.{item.item_id}"
        self.outputs.append(OutputDef(record.purchased, cur, cost))
        f_bm = doc.get("F_BM", dict(entry_doc.get("bare_module", {})).get("F_BM"))
        if f_bm is None:
            self.missing_fbm.append(item.item_id)
            return None
        f_theta = self._theta(
            f"asm:item.{item.item_id}.F_BM",
            float(sets._plain(f_bm)),
            "1",
            f"items.{item.item_id}.F_BM" if "F_BM" in doc else f"{record.source.get('entry')}",
        )
        record.bare_module = f"capex.bare_module.{item.item_id}"
        purchased = record.purchased
        self.outputs.append(
            OutputDef(
                record.bare_module, cur, lambda s, a: s.theta(f_theta.theta_id) * s.out(purchased)
            )
        )
        return None

    def _entry(
        self, item: SizedItem, doc: Mapping[str, Any]
    ) -> tuple[sets.CostSet, forms.ResolvedEntry] | Refusal:
        """§4.5.3: the item's `correlation`, else the set's first entry of its family."""
        declared = doc.get("correlation")
        set_id = declared["set"] if declared else self.doc.get("correlation_set")
        if set_id is None:
            return Refusal("NO_CORRELATION", item.item_id, "no correlation and no correlation_set")
        try:
            cost_set = sets.load_set(str(set_id))
        except KeyError as error:
            return Refusal("NO_CORRELATION", item.item_id, str(error))
        for ref in dict(self.doc.get("data", {})).get("sets", ()):
            if ref["id"] == set_id and ref["sha256"] != document_sha256(cost_set.document):
                return Refusal("NO_CORRELATION", item.item_id, f"{set_id}: sha256 mismatch")
        if declared:
            try:
                entry = cost_set.entry(str(declared["entry"]))
            except KeyError as error:
                return Refusal("NO_CORRELATION", item.item_id, str(error))
        else:
            orientation = item.options.get("orientation")
            found = sets.entry_for(cost_set, item.family, orientation)
            if found is None:
                return Refusal("NO_CORRELATION", item.item_id, f"{set_id} has no {item.family}")
            entry = found
        if entry.form == "generic-v1":
            return Refusal(
                "NO_CORRELATION",
                item.item_id,
                "generic-v1 entries are not costed in E01",
                kind="unsupported",
            )
        options = self._options(item, doc, entry)
        if isinstance(options, Refusal):
            return options
        resolved = sets.resolve(cost_set, entry.entry_id, options)
        if isinstance(resolved, sets.NoCorrelation):
            return Refusal("NO_CORRELATION", item.item_id, resolved.detail)
        return cost_set, resolved

    def _options(
        self, item: SizedItem, doc: Mapping[str, Any], entry: sets.CostEntry
    ) -> dict[str, str] | Refusal:
        declared = set(dict(entry.document.get("options", {})))
        options = {str(k): str(v) for k, v in dict(doc.get("options", {})).items()}
        mapped: list[tuple[str, tuple[str, ...]]] = [
            ("material", _MATERIAL_OPTIONS),
            ("tray_type", ("tray_type",)),
            ("subtype", _SUBTYPE_OPTIONS),
        ]
        for key, candidates in mapped:
            if key not in doc:
                continue
            names = [n for n in candidates if n in declared]
            if len(names) != 1:
                return Refusal(
                    "NO_CORRELATION", item.item_id, f"`{key}` maps to no option of {entry.entry_id}"
                )
            name, value = names[0], str(doc[key])
            if name in options and options[name] != value:
                return Refusal("NO_CORRELATION", item.item_id, f"`{key}` and options.{name} differ")
            options[name] = value
        return options

    def _input(
        self,
        item: SizedItem,
        record: ItemCost,
        e: forms.ResolvedEntry,
        name: str,
        values: Mapping[str, float],
    ) -> tuple[Any, FunctionalBuilder] | None:
        if name in _SIZE_INPUT:
            quantity = _SIZE_INPUT[name]
            if item.family == "machine.drive" and name == "power":
                # §9.2.7: the motor reads the machine's total shaft power W, not W/η.
                quantity_id = f"size.{item.unit_id}.power"
                if quantity_id not in values:
                    return None
                return values[quantity_id], _out(quantity_id)
            output_id = item.size.get(quantity)
            if output_id is None or output_id not in values:
                return None
            return values[output_id], _out(output_id)
        if name == "design_pressure":
            p = item.design_pressure
            if p is None:
                return None
            if isinstance(p, str):
                value = self.sctx.x(p)
                record.inputs.append(
                    {"name": name, "value": value, "unit": "Pa", "defaulted": False}
                )
                return value, lambda s, a: s.x(p)
            record.inputs.append({"name": name, "value": p, "unit": "Pa", "defaulted": False})
            return float(p), lambda s, a: p
        if name == "thickness":
            doc = self._item_doc(item)
            if "shell_thickness" in doc:
                value, provenance, dflt = (
                    float(doc["shell_thickness"]),
                    f"items.{item.item_id}.shell_thickness",
                    False,
                )
            else:
                value = e.continuous["shell_thickness_in"] * forms.INCH_M
                provenance, dflt = f"{e.set_id} {e.entry_id} shell_thickness_in default", True
                self._defaulted("shell_thickness", value, item.item_id)
            theta = self._theta(f"asm:item.{item.item_id}.t_shell", value, "m", provenance)
            record.inputs.append(
                {"name": "t_shell", "value": value, "unit": "m", "defaulted": dflt}
            )
            return value, lambda s, a: s.theta(theta.theta_id)
        if name == "n_act":
            n_act = item.options.get("N_act")
            if n_act is None:
                return None
            return int(n_act), lambda s, a: int(n_act)
        raise KeyError(f"form input {name!r} has no source")

    def _held(
        self, item_id: str, form: forms.Form, e: forms.ResolvedEntry, sel: forms.Selection
    ) -> forms.Selection:
        """§4.3.2 holding: a held choice replaces the rule's (the program checks its rows)."""
        size, n, pieces = sel.size, sel.n, dict(sel.pieces)
        held = self.ctx.regime.choice(f"{item_id}.size")
        if held is not None and sel.size is not None:
            size = held
            n = (size_units(held) or 1) if not form.inherits_units else sel.n
        for name in list(pieces):
            choice = self.ctx.regime.choice(f"{item_id}.{form.target(name)}.piece")
            if choice is not None:
                pieces[name] = 0 if choice == "floor" else int(choice)
        return replace(sel, size=size, n=n, pieces=pieces)

    def _regime(
        self,
        item_id: str,
        form: forms.Form,
        e: forms.ResolvedEntry,
        sel: forms.Selection,
        x_build: Mapping[str, FunctionalBuilder],
        record: ItemCost,
    ) -> None:
        def quantity(name: str) -> FunctionalBuilder:
            def build(s: Symbols, a: Algebra) -> Expr:
                x = {k: b(s, a) for k, b in x_build.items()}
                return form.quantities(e, x, a, sel.n)[name]

            return build

        def row(r: forms.RangeRow) -> AdmissibilityRow:
            q = quantity(r.quantity)
            sense, bound = float(r.sense), r.bound
            return AdmissibilityRow(
                r.row_id.replace(".", "_"), lambda s, a: sense * (q(s, a) - bound), r.nominal
            )

        grouped: dict[str, list[forms.RangeRow]] = {}
        for r in forms.rows(form, e, sel):
            grouped.setdefault(r.quantity, []).append(r)
        size_name = form.size_name(e)
        if size_name is not None and sel.size is not None:
            entry_id = f"{item_id}.size"
            self.entries.append(
                RegimeEntry(
                    entry_id,
                    "size",
                    sel.size,
                    "§4.3.2 rule 4",
                    tuple(row(r) for r in grouped.get(size_name, ())),
                )
            )
            record.regime[entry_id] = sel.size
        for name, piece in sel.pieces.items():
            entry_id = f"{item_id}.{form.target(name)}.piece"
            choice = "floor" if piece == 0 else str(piece)
            self.entries.append(
                RegimeEntry(
                    entry_id,
                    "piece",
                    choice,
                    "§4.3.2 rule 5; §9.2.5",
                    tuple(row(r) for r in grouped.get(name, ())),
                )
            )
            record.regime[entry_id] = choice

    # -- sums and the chain (§4.7.1) -------------------------------------------------------------

    def chain(self) -> None:
        cur = self.target.currency
        purchased = [r.purchased for r in self.records if r.purchased is not None]
        bare = [r.bare_module for r in self.records if r.bare_module is not None]
        quoted_bm = [r.item_id for r in self.records if r.purchased is None]
        capital_doc = self.doc.get("capital")
        chain: capital.Chain | None = None
        if capital_doc is not None:
            try:
                if "chain" in capital_doc:
                    chain = capital.load_chain(str(capital_doc["chain"]))
                else:
                    chain = capital.chain_from(
                        capital_doc.get("steps", ()),
                        str(capital_doc.get("capital_total")),
                        str(capital_doc.get("fci")),
                    )
            except capital.ChainError as error:
                self.refusals.append(
                    Refusal("ASSESSMENT_OUTPUT_UNKNOWN", "capex.total", str(error))
                )
        if chain is not None and "sum_bare_module" in chain.bases:
            self.refusals.extend(Refusal("BARE_MODULE_FACTOR_MISSING", i) for i in self.missing_fbm)
        refused = self.capital_refused
        self._sum(
            "capex.sum_purchased",
            purchased,
            cur,
            refused or ([f"{i}: bare-module quote" for i in quoted_bm]),
        )
        self._sum(
            "capex.sum_bare_module",
            bare,
            cur,
            refused or [f"{i}: BARE_MODULE_FACTOR_MISSING" for i in self.missing_fbm],
        )
        self.chain_ = chain
        if chain is None:
            self.unavailable["capex.total"] = "no capital chain declared or the chain is malformed"
            self.unavailable["capex.fci"] = self.unavailable["capex.total"]
            return
        for step in chain.steps:
            output_id = f"capex.{step.name}"
            deps = [f"capex.{t.of}" for t in step.terms]
            missing = [d for d in deps if d in self.unavailable]
            if missing:
                self.unavailable[output_id] = f"depends on {missing}"
                continue

            def build(s: Symbols, a: Algebra, step: capital.ChainStep = step) -> Expr:
                return step.value({t.of: s.out(f"capex.{t.of}") for t in step.terms})

            self.outputs.append(OutputDef(output_id, cur, build))
        for alias, name in (("capex.total", chain.capital_total), ("capex.fci", chain.fci)):
            if f"capex.{name}" in self.unavailable:
                self.unavailable[alias] = f"capex.{name} is unavailable"
            else:
                self.outputs.append(OutputDef(alias, cur, _out(f"capex.{name}")))

    def _sum(self, output_id: str, ids: Sequence[str], unit: str, blocked: Sequence[str]) -> None:
        if blocked:
            self.unavailable[output_id] = f"refused or uncosted items: {list(blocked)}"
        else:
            self.outputs.append(OutputDef(output_id, unit, _fold(tuple(ids))))

    # -- operating cost (§4.7.2) -----------------------------------------------------------------

    def _price(
        self, price_id: str, price: Mapping[str, Any], kinds: frozenset[str]
    ) -> Theta | None:
        found = operating.price_on_basis(price_id, price, self.target, self.series, self.rates)
        if isinstance(found, Refusal):
            self.refusals.append(found)
            return None
        if found.per not in kinds:
            self.refusals.append(
                Refusal("PRICE_BASIS_MISMATCH", price_id, f"`per: {found.per}` does not fit")
            )
            return None
        self.limitations.extend(found.limitations)
        return self._theta(
            f"asm:{price_id}",
            found.value,
            f"{self.target.currency}/{found.per}-SI",
            f"{price_id} ({price['value']} per {price['per']}; E = {found.escalation!r})",
        )

    def opex(self) -> None:
        cur = f"{self.target.currency}/yr"
        h = self.op["hours_per_year"].theta_id
        lines: list[str] = []
        blocked: list[str] = list(self.opex_refused)
        for utility in self.doc.get("utilities", ()):
            u = str(utility["utility_id"])
            if utility["kind"] == "electricity":
                users = [i for i in self.sizing.items if i.electricity is not None and i.power]
            else:
                users = [i for i in self.sizing.items if i.utility == u and i.duty is not None]
            if not users:
                continue
            output_id = f"opex.utility.{u}"
            price = self._price(f"utility.{u}.price", utility["price"], operating.ENERGY_PER)
            if price is None:
                blocked.append(output_id)
                self.unavailable[output_id] = "price refused"
                continue
            consume = [i for i in users if i.electricity != "generation"]
            generate = [i for i in users if i.electricity == "generation"]
            export = price
            if generate:
                if "export_price" in utility:
                    got = self._price(
                        f"utility.{u}.export_price", utility["export_price"], operating.ENERGY_PER
                    )
                    if got is None:
                        blocked.append(output_id)
                        self.unavailable[output_id] = "export price refused"
                        continue
                    export = got
                else:
                    self.limitations.append(Limitation("ELECTRICITY_NETTED", u))
                    self._defaulted("electricity_export_price", "import", u)

            self.outputs.append(
                OutputDef(
                    output_id,
                    cur,
                    _energy_cost(
                        tuple(consume), tuple(generate), price.theta_id, export.theta_id, h
                    ),
                )
            )
            lines.append(output_id)
        electric = {i.item_id for i in self.sizing.items if i.electricity is not None}
        if electric and not any(u["kind"] == "electricity" for u in self.doc.get("utilities", ())):
            blocked.append("electricity")
            self.unavailable["opex.utility.electricity"] = "no utility of kind electricity declared"
        revenues: list[str] = []
        masses = self.ctx.view.molar_masses()
        for material in self.doc.get("materials", ()):
            role, s_id = str(material["role"]), str(material["connection"])
            if role == "emission" or "price" not in material:
                continue
            prefix = {"raw_material": "opex.material", "waste": "opex.waste"}.get(role, "revenue")
            output_id = f"{prefix}.{s_id}"
            basis = str(material["basis"])
            kinds = frozenset({"kg", "t"}) if basis != "molar_total" else frozenset({"mol", "kmol"})
            if basis == "component" and str(material["price"]["per"]) in ("mol", "kmol"):
                kinds = frozenset({"mol", "kmol"})
            price = self._price(f"material.{s_id}.price", material["price"], kinds)
            if price is None:
                (revenues if prefix == "revenue" else blocked).append(output_id)
                self.unavailable[output_id] = "price refused"
                continue
            flow = self._flow(s_id, basis, material.get("component"), price.unit, masses)
            self.outputs.append(OutputDef(output_id, cur, _flow_cost(flow, price.theta_id, h)))
            (revenues if prefix == "revenue" else lines).append(output_id)
        fixed = list(self.doc.get("fixed_opex", ()))
        if not fixed:
            self.limitations.append(Limitation("FIXED_OPEX_UNDECLARED"))
        for line in fixed:
            output_id = f"opex.fixed.{line['line']}"
            if "constant" in line:
                t = self._theta(
                    f"asm:fixed.{line['line']}.constant",
                    float(line["constant"]),
                    cur,
                    f"fixed_opex {line['line']}",
                )
                self.outputs.append(OutputDef(output_id, cur, _theta_value(t.theta_id)))
            else:
                of = f"capex.{line['fraction_of']['of']}"
                if of in self.unavailable:
                    blocked.append(output_id)
                    self.unavailable[output_id] = f"{of} is unavailable"
                    continue
                t = self._theta(
                    f"asm:fixed.{line['line']}.fraction",
                    float(line["fraction_of"]["fraction"]),
                    "1/yr",
                    f"fixed_opex {line['line']}",
                )
                self.outputs.append(OutputDef(output_id, cur, _scaled(t.theta_id, of)))
            lines.append(output_id)
        self._sum("opex.total", lines, cur, blocked)
        unpriced = [r for r in revenues if r in self.unavailable]
        self._sum(
            "revenue.total", [r for r in revenues if r not in self.unavailable], cur, unpriced
        )

    def _flow(
        self, stream: str, basis: str, component: str | None, unit: str, masses: Mapping[str, float]
    ) -> FunctionalBuilder:
        if basis == "mass_total":
            return self.sctx.mass_builder(stream)
        if basis == "molar_total" or vapor_id(stream) in self.sctx.variables:
            moles = self.sctx.moles_builder(stream)
            if basis == "component" and "/kg" in unit:
                m = masses[str(component)]
                return lambda s, a: moles(s, a) * m
            return moles
        name = flow_id(stream, str(component))
        if "/kg" in unit:
            m = masses[str(component)]
            return lambda s, a: s.x(name) * m
        return lambda s, a: s.x(name)

    # -- annualisation and the functional unit (§4.7.3, §4.7.4) ----------------------------------

    def annual(self) -> None:
        cur = f"{self.target.currency}/yr"
        i, n = self.op["discount_rate"], self.op["lifetime_years"]
        domain = capital.discount_rate_domain(i.value, n.value)
        if domain is not None:
            self.refusals.append(Refusal("DISCOUNT_RATE_OUT_OF_DOMAIN", "operation", domain))
            self.unavailable["annual.capital_charge"] = domain
        elif "capex.total" in self.unavailable:
            self.unavailable["annual.capital_charge"] = "capex.total is unavailable"
        else:
            self.outputs.append(
                OutputDef(
                    "annual.capital_charge",
                    cur,
                    lambda s, a: capital.crf(s.theta(i.theta_id), s.theta(n.theta_id))
                    * s.out("capex.total"),
                )
            )
        self._derive(
            "tac",
            cur,
            ("annual.capital_charge", "opex.total"),
            lambda s, a: s.out("annual.capital_charge") + s.out("opex.total"),
        )
        self._derive(
            "profit",
            cur,
            ("revenue.total", "tac"),
            lambda s, a: s.out("revenue.total") - s.out("tac"),
        )
        fu = dict(self.doc.get("lca", {})).get("functional_unit")
        if fu is None:
            return
        basis = str(fu["basis"])
        unit = "kg/yr" if basis != "molar_total" else "mol/yr"
        flow = self._flow(
            str(fu["connection"]),
            basis,
            fu.get("component"),
            "/kg" if unit == "kg/yr" else "/mol",
            self.ctx.view.molar_masses(),
        )
        h = self.op["hours_per_year"].theta_id
        self.outputs.append(
            OutputDef("product.annual", unit, lambda s, a: operating.annual(flow(s, a), s.theta(h)))
        )
        self._derive(
            "lcox",
            f"{self.target.currency}/{unit[:-3]}",
            ("tac", "product.annual"),
            lambda s, a: s.out("tac") / s.out("product.annual"),
        )

    def _derive(
        self, output_id: str, unit: str, deps: Sequence[str], build: FunctionalBuilder
    ) -> None:
        missing = [d for d in deps if d in self.unavailable]
        if missing:
            self.unavailable[output_id] = f"depends on {missing}"
        else:
            self.outputs.append(OutputDef(output_id, unit, build))

    # -- the drive's electricity (§9.2.7) --------------------------------------------------------

    def drives(self) -> None:
        """Replace each electric drive's `W/η_drive` (θ) by `W/η_m(W/N)` when the set has a
        `machine.drive` entry; the θ `eta_drive` is then not created (§9.2.7)."""
        set_id = self.doc.get("correlation_set")
        motor: forms.ResolvedEntry | None = None
        if set_id is not None:
            try:
                cost_set = sets.load_set(str(set_id))
            except KeyError:
                cost_set = None
            entry = None if cost_set is None else sets.entry_for(cost_set, "machine.drive")
            if cost_set is not None and entry is not None and entry.form == "sslw-motor-v1":
                found = sets.resolve(cost_set, entry.entry_id, {})
                motor = found if isinstance(found, forms.ResolvedEntry) else None
        self.motor = motor
        if motor is None:
            return
        dropped: set[str] = set()
        items: list[SizedItem] = []
        outputs = list(self.sizing.outputs)
        for item in self.sizing.items:
            if item.family != "machine.drive" or item.item_id in self.excluded:
                items.append(item)
                continue
            shaft = f"size.{item.unit_id}.power"
            n_of = item.unit_id

            def consumed(s: Symbols, a: Algebra, shaft: str = shaft, n_of: str = n_of) -> Expr:
                n = self.selections[n_of].n if n_of in self.selections else 1
                w = s.out(shaft)
                return w / forms.motor_efficiency(motor, (w / n) * forms.KAPPA_W, a)

            dropped.add(f"asm:item.{item.item_id}.eta_drive")
            outputs = [
                OutputDef(o.output_id, o.unit, consumed) if o.output_id == item.size["power"] else o
                for o in outputs
            ]
            items.append(replace(item, inputs=(), power=consumed))
        self.sizing = replace(
            self.sizing,
            items=tuple(items),
            outputs=tuple(outputs),
            theta=tuple(t for t in self.sizing.theta if t.theta_id not in dropped),
        )

    def plan(self) -> ContributionPlan:
        self.included_drive: set[str] = set()
        self.missing_fbm: list[str] = []
        self.basis()
        self.items()
        self.drives_domain()
        self.chain()
        self.opex()
        self.annual()
        records, defaulted, excluded = self.records, self.defaulted, self.excluded
        for item in self.sizing.items:
            for record in item.inputs:
                if record.defaulted:
                    defaulted.append(
                        {"key": record.name, "value": record.value, "target": item.item_id}
                    )
        refusals = [
            r for r in (*self.sizing.refusals, *self.refusals) if not _covered(r.target, excluded)
        ]

        def section(values: Mapping[str, float]) -> dict[str, Any]:
            return {
                "items": [
                    {
                        **r.__dict__,
                        "relative_range": None
                        if r.relative_range is None
                        else list(r.relative_range),
                        "purchased_value": values.get(r.purchased) if r.purchased else None,
                        "bare_module_value": values.get(r.bare_module) if r.bare_module else None,
                    }
                    for r in records
                ],
                "excluded": [{"item": k, "reason": v} for k, v in excluded.items()],
                "defaulted_inputs": list(defaulted),
            }

        theta = {t.theta_id: t for t in (*self.sizing.theta, *self.theta)}
        return ContributionPlan(
            outputs=(*self.sizing.outputs, *self.outputs),
            theta=tuple(theta.values()),
            blocks=self.sizing.blocks,
            regime_entries=(*self.sizing.regime_entries, *self.entries),
            refusals=tuple(refusals),
            limitations=(*self.sizing.limitations, *self.limitations),
            section=section,
            unavailable=tuple(self.unavailable.items()),
        )

    def drives_domain(self) -> None:
        """§9.2.4 V: `0 < η_m ≤ 1` at the machine's per-unit power, else
        `CORRELATION_OUT_OF_RANGE(<U>.drive.eta)`; then the drive's electricity (§9.2.7)."""
        self.drives()
        if self.motor is None:
            return
        for item in self.sizing.items:
            if item.family != "machine.drive" or item.item_id in self.excluded:
                continue
            w = self.item_values.get(f"size.{item.unit_id}.power")
            n = self.selections[item.unit_id].n if item.unit_id in self.selections else 1
            guard = (
                None
                if w is None
                else forms.FORMS["sslw-motor-v1"].domain(self.motor, {"power": w}, n)
            )
            if guard is not None:
                self.refusals.append(
                    Refusal("CORRELATION_OUT_OF_RANGE", f"{item.item_id}.eta", guard.detail)
                )
                self.opex_refused.append(f"{item.item_id}.eta")


class CostContributor:
    """The `cost` contributor (§4.2.2)."""

    name = "cost"

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        return _Planner(ctx, state).plan()


register_contributor("cost", CostContributor)
