"""S03 WO-S03-2: blind qualification and runs of the column cases in IDAES 2.13.0.

Authority: `docs/derivations/S03-spec.md` §2.2 (levels), §2.3 (the pre-registered "where available"
rule), §2.4 (structural questions), §5.1 (matched semantics, rows 12, 13 and 15), §6 (thresholds),
§7.1 rules 2, 2b, 2c and 2d (computed here from IDAES's own record only) and Amendment 1 (§17.1 RC6
and RC7 as L2(b) equations, §17.4 specification definitions and per-kind thresholds, §17.6 imports,
§17.10's WO-S03-2 delta).

For every case of `s03_cases.json` (RC1-RC7, the ten perturbed cases and PC-P; PC-L gets the
registered `not_applicable` record) this script tries the levels L1, L2, L3 in turn. At each level it
builds IDAES's model on SYN-001 (the `GenericParameterBlock` of `idaes_representability`, i.e.
`docs/reference-environments.md` §5.0, with T06's SmoothVLE and Ipopt settings), records a structural
inspection of the built model before it is solved, and, if the model is structurally expressible,
runs it under the registered settings. A run that passes rules 2-2c and 2d's specification residual is
rerun at `floor_rerun` (§5.1 row 15) for 2d's movement check. The case's level is the first one that is
structurally expressible and passes rules 2-2d; every attempt is recorded.

Levels for IDAES (§2.2):
* L1: `TrayColumn` with its native specification variables only (`Condenser.reflux_ratio`,
  `Reboiler.boilup_ratio`, `Reboiler.heat_duty`).
* L2: `TrayColumn` plus (a) a tool variable fixed at a value S02 implies exactly, or (b) a
  specification equation on IDAES's own variables, written from S02 §2.1 / S06 §2, in place of a
  native specification.
* L3: IDAES's stage-level units (`Tray`, `Condenser`, `Flash`, `Reboiler`) joined by `Arc`s, with L2's
  realizations.

Blind (§2.3 step 2, §8, §17.6): the only input file of this project is `s03_cases.json`; the only
modules of this project imported are T06's SYN-001 definitions (`t06_fixtures`, `t06_qualify_idaes`,
`idaes_representability`). No value of this project's solver, of the generator or of any classifier
output is read. It prints one line per case and one summary line.

    .venv-idaes/bin/python spikes/references/s03_qualify_idaes.py [--out DIR] [--only CASE ...]

Not part of `scripts/check.sh`: the gate never runs a tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import traceback
from decimal import Decimal
from pathlib import Path
from typing import Any

# Single-threaded MUMPS/BLAS: deterministic linear algebra, and no oversubscription of a shared host.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import t06_fixtures as fx  # noqa: E402
import t06_qualify_idaes as t06i  # noqa: E402

CASES_PATH = fx.REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json"
ENV_DIR = fx.REPO_ROOT / ".venv-idaes"
DEFAULT_OUT = fx.REPO_ROOT / "benchmarks" / "s03" / "references"

# §6: allowances a_k, the relative term, and the rule 2/2c/2d thresholds; §17.4: rule 2d per kind.
ALLOWANCE = {"T": 1e-5, "flow": 3.1e-7, "duty": 1e-2}
RELATIVE = 1e-6
RULE2_ENERGY_W = 1e-3
RULE2C_PRESSURE_PA = 1e-3
RULE2C_INTERMEDIATE_DUTY_W = 1e-3
RULE2C_ZERO_DISTILLATE_MOL_PER_S = 3.1e-8
RULE2C_SPEC_RELATIVE = 1e-4
RULE2D_SPEC = {  # kind -> (threshold, basis)
    "reflux_ratio": (1e-8, "relative"), "boilup_ratio": (1e-8, "relative"),
    "distillate_rate": (1e-8, "relative"), "bottoms_rate": (1e-8, "relative"),
    "duty": (1e-8, "relative"), "purity": (1e-8, "absolute"),
    "recovery": (1e-9, "absolute"), "temperature": (1e-9, "relative"),
}
RULE2D_RERUN_FRACTION = 0.1
# §5.1 row 12: the registered temperature profile, linear from 320 K (stage 1) to 400 K (stage N).
PROFILE_T_TOP_K, PROFILE_T_BOTTOM_K = 320.0, 400.0

SIGN_CONVERSION = (
    "identity: IDAES's heat_duty (Condenser, Reboiler, Flash) is the heat into the control volume, "
    "W, so Q_condenser = condenser heat_duty and Q_reboiler = reboiler heat_duty, Q > 0 into the stage"
)
INITIALIZATION = [
    "Initial guesses (§5.1 row 12): every tray inlet that is not a case inlet starts at the registered "
    "linear temperature profile (320 K at stage 1 to 400 K at stage N; a liquid inlet at the profile "
    "temperature of the stage above, a vapour inlet at that of the stage below), at IDAES's nominal "
    "flow of 1 mol/s (the property package's state-bound default), at the first inlet's composition "
    "and the registered pressure. Nothing of this project's results or the generator is used.",
    "L1/L2: IDAES's own `TrayColumn.initialize()`. L3: IDAES's own unit initializers (`Tray`, "
    "`Condenser`, `Flash`, `Reboiler`) in `TrayColumn.initialize`'s order: the trays holding a case "
    "inlet first, then the end units from the nearest of them (propagate_state), then every other "
    "tray with its liquid inlet from the nearest initialized unit above and its vapour inlet from "
    "the nearest one below. Both are followed by one full model solve with IDAES's initializer "
    "solver (`get_solver()`, MUMPS; `TrayColumn.initialize` does not check its own last solve). An "
    "initializer exception is recorded and does not end the attempt; the final solve decides.",
    "The initializers run at IDAES's default SmoothVLE eps (0.01 K, 5e-4 K). The registered "
    "eps_1 = eps_2 = 1e-8 K is set on every SmoothVLE state block after initialization and before the "
    "final solve, so the final solve and the accuracy rerun solve exactly the registered equations "
    "(rule 2b checks every block). Measured: at 1e-8 K IDAES's column initializer fails on the "
    "saturated inter-stage streams (docs/S03_BUILD_DECISIONS.md, WO-S03-2).",
    "A specification equation (L2 b) on the end unit's own variables is a constraint of that unit and "
    "is active in its initializer. One on another stage's variables (a stage temperature) is "
    "deactivated during the initializers, with the end's native variable it replaces fixed at IDAES's "
    "own initial value for it (`Reboiler.boilup_ratio`: 0.5), and restored before the full solves.",
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases() -> dict[str, Any]:
    import idaes_representability as probe

    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    ids = data["tool_settings"]["IDAES"]
    # T06's definitions are imported, not re-entered (§5.1 row 1); check they are the registered ones.
    assert fx.IDAES_SOLVER_OPTIONS == {
        "linear_solver": ids["linear_solver"], "tol": float(ids["tol"]),
        "constr_viol_tol": float(ids["constr_viol_tol"]), "max_iter": int(ids["max_iter"]),
    }
    assert fx.IDAES_SMOOTH_VLE_EPS_K == {"eps_1": float(ids["smooth_vle"]["eps_1_K"]),
                                         "eps_2": float(ids["smooth_vle"]["eps_2_K"])}
    assert probe.CRIT_T == float(ids["placeholders"]["temperature_crit_K"])
    assert probe.CRIT_P == float(ids["placeholders"]["pressure_crit_Pa"])
    for i, c in enumerate(probe.COMPONENTS):
        assert probe.L_VAP[c] == float(ids["h_form_ig_J_per_mol"][i])
        assert float(ids["h_form_liq_J_per_mol"][i]) == 0.0
    assert tuple(data["components"]) == probe.COMPONENTS
    return data


def final_options(data: dict[str, Any], rerun: bool) -> dict[str, Any]:
    opts = dict(fx.IDAES_SOLVER_OPTIONS)
    if rerun:
        fr = data["tool_settings"]["IDAES"]["floor_rerun"]
        opts.update(tol=float(fr["tol"]), constr_viol_tol=float(fr["constr_viol_tol"]))
    return opts


def quantity_tolerance(kind: str, value: float) -> float:
    """§6's tolerance with the tool's own value standing in for v (the script reads no other)."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


def profile_t(case: dict[str, Any], j: int) -> float:
    n = int(case["stage_count"])
    return PROFILE_T_TOP_K + (j - 1) * (PROFILE_T_BOTTOM_K - PROFILE_T_TOP_K) / (n - 1)


def inlet_state(inlet: dict[str, Any]) -> tuple[dict[str, float], float, float]:
    flows = {c: float(v) for c, v in zip(("A", "B", "C"), inlet["n_mol_per_s"], strict=True)}
    return flows, float(inlet["T_K"]), float(inlet["P_Pa"])


# ---- the realization at each level (§2.2, §5.1); no tool is touched here ------------------------

L1_NATIVE = {"condenser": {"reflux_ratio"}, "reboiler": {"boilup_ratio", "duty"}}


def realization(case: dict[str, Any], level: str) -> dict[str, Any]:
    """IDAES's realization of a case at a level, or the reason it has none."""
    cond, reb, specs = case["condenser"], case["reboiler"], case["specifications"]
    r: dict[str, Any] = {"level": level}
    if level in ("L1", "L2"):
        r["unit"] = "TrayColumn"
        if cond == "none" or reb == "none":
            missing = "condenser" if cond == "none" else "reboiler"
            return {**r, "expressible": False, "reason": (
                f"IDAES's TrayColumn always builds a Condenser and a kettle Reboiler; the case has no "
                f"{missing} (S02 'none' end), and no L1 or L2 realization removes a unit")}
        if cond == "partial":
            # The structural facts are read from a built model in Model.partial_condenser_facts().
            return {**r, "expressible": False, "inspect_partial_condenser": True, "reason": (
                "S02's partial condenser (vapour distillate, all liquid refluxed) is not IDAES's "
                "partial Condenser: that unit splits its liquid into reflux and a liquid distillate "
                "by reflux_split_fraction = RR/(1+RR), so its reflux_ratio is reflux over liquid "
                "distillate (not L_1/V_1, §5.1 row 9), and its liquid distillate flow is an Expression "
                "(1 - RR/(1+RR))*F_liq, not a variable: there is no tool variable to fix at 0 (L2 a), and "
                "the expression is 0 only at reflux_ratio = infinity. See structural_inspection")}
        native = {end: s["kind"] in L1_NATIVE[end] for end, s in specs.items()}
        if level == "L1":
            if not all(native.values()):
                bad = [f"{e}: {specs[e]['kind']}" for e, ok in native.items() if not ok]
                return {**r, "expressible": False, "reason": (
                    f"no native IDAES column specification variable for {bad} (native: "
                    "Condenser.reflux_ratio = reflux/distillate, Reboiler.boilup_ratio = "
                    "vapour/bottoms, Reboiler.heat_duty)")}
        elif all(native.values()):
            return {**r, "expressible": False, "reason": "no L2 realization distinct from L1"}
        r["condenser"] = "total"
        r["specifications"] = {end: ("native" if native[end] else "L2(b)") for end in specs}
        return {**r, "expressible": True}
    r["unit"] = "composition of Tray, Condenser/Flash and Reboiler joined by Arcs"
    r["condenser"] = {"partial": "Flash", "total": "Condenser(total)", "none": None}[cond]
    r["reboiler"] = {"partial": "Reboiler", "none": None}[reb]
    r["specifications"] = {
        end: ("native" if (s["kind"] in L1_NATIVE[end] and not (end == "condenser"
                                                               and cond == "partial"))
              else "L2(b)") for end, s in specs.items()}
    return {**r, "expressible": True}


# ---- the model --------------------------------------------------------------------------------


class Model:
    """One IDAES flowsheet holding one column, built from a case and a realization.

    `stages[j]` is the unit of our stage j (S02 §1.1, 1-based, top to bottom); `kinds[j]` is one of
    'condenser_total', 'condenser_flash', 'tray', 'reboiler'.
    """

    def __init__(self, data: dict[str, Any], case: dict[str, Any], real: dict[str, Any]) -> None:
        import pyomo.environ as pyo
        from idaes_representability import new_flowsheet

        self.data, self.case, self.real = data, case, real
        self.n = int(case["stage_count"])
        self.m = new_flowsheet()
        self.stages: dict[int, Any] = {}
        self.kinds: dict[int, str] = {}
        self.inlets: list[dict[str, Any]] = []  # {"tag", "port", "state", "stage"}
        self.products: dict[str, dict[str, Any]] = {}
        self.spec_info: dict[str, dict[str, Any]] = {}
        self.nonlocal_specs: list[tuple[Any, Any]] = []  # (constraint, native var it replaces)
        if real["unit"] == "TrayColumn":
            self._build_tray_column()
        else:
            self._build_composition()
        for inlet in self.inlets:
            flows, t, p = inlet_state(inlet["case"])
            from idaes_representability import fix_port

            fix_port(inlet["port"], flows, t, p)
        self._apply_specifications()
        self.pyo = pyo
        # Everything the build fixed (inlets, the top pressure, native specifications); an
        # initializer that raises may leave other variables fixed, which _release_inlet_states undoes.
        self.fixed_at_build = {id(v) for v in self.m.component_data_objects(pyo.Var)
                               if v.fixed}

    # -- builders --

    def _build_tray_column(self) -> None:
        from idaes.models_extra.column_models import TrayColumn
        from idaes.models_extra.column_models.condenser import CondenserType, TemperatureSpec

        case, m, n = self.case, self.m, self.n
        (feed,) = case["inlets"]
        assert feed["port"] == "feed"
        m.fs.col = TrayColumn(
            number_of_trays=n - 2, feed_tray_location=int(feed["stage"]) - 1,
            condenser_type=CondenserType.totalCondenser,
            condenser_temperature_spec=TemperatureSpec.atBubblePoint,
            property_package=m.fs.props, has_heat_transfer=False, has_pressure_change=False,
        )
        col = m.fs.col
        self.stages[1], self.kinds[1] = col.condenser, "condenser_total"
        for k in range(1, n - 1):
            if k == int(feed["stage"]) - 1:
                tray = col.feed_tray
            elif k < int(feed["stage"]) - 1:
                tray = col.rectification_section[k]
            else:
                tray = col.stripping_section[k]
            self.stages[k + 1], self.kinds[k + 1] = tray, "tray"
        self.stages[n], self.kinds[n] = col.reboiler, "reboiler"
        col.condenser.condenser_pressure.fix(float(case["stage_pressures_Pa"][0]))
        # col.feed extends the feed tray's feed port; the tray's own port names the stage it enters.
        self.inlets.append({"tag": "feed", "port": col.feed_tray.feed, "case": feed,
                            "state": col.feed_tray.properties_in_feed[0],
                            "stage": int(feed["stage"])})
        self.products["TOP"] = {"port": col.condenser.distillate,
                                "state": col.condenser.control_volume.properties_out[0],
                                "phase": "Liq"}
        self.products["BOTTOM"] = {"port": col.reboiler.bottoms,
                                   "state": col.reboiler.control_volume.properties_out[0],
                                   "phase": "Liq"}
        self.unit_pressure_fixed = {"condenser_pressure": float(case["stage_pressures_Pa"][0])}

    def _build_composition(self) -> None:
        import pyomo.environ as pyo
        from idaes.models.unit_models import Flash
        from idaes.models_extra.column_models import Condenser, Reboiler, Tray
        from idaes.models_extra.column_models.condenser import CondenserType, TemperatureSpec
        from pyomo.network import Arc

        case, m, n = self.case, self.m, self.n
        props = m.fs.props
        cond, reb = case["condenser"], case["reboiler"]
        p_reg = [float(p) for p in case["stage_pressures_Pa"]]
        first = 1 if cond == "none" else 2
        last = n if reb == "none" else n - 1
        feed_stages = {int(i["stage"]) for i in case["inlets"] if i["port"] == "feed"}
        # One Tray block per stage: is_feed_tray is a per-block option.
        for j in range(first, last + 1):
            tray = Tray(property_package=props, is_feed_tray=j in feed_stages,
                        has_heat_transfer=False, has_pressure_change=False,
                        has_liquid_side_draw=False, has_vapor_side_draw=False)
            m.fs.add_component(f"stage{j}", tray)
            self.stages[j], self.kinds[j] = tray, "tray"
        self.unit_pressure_fixed = {}
        if cond == "partial":
            m.fs.stage1 = Flash(property_package=props, has_heat_transfer=True,
                                has_pressure_change=True)
            m.fs.stage1.control_volume.properties_out[0].pressure.fix(p_reg[0])
            self.unit_pressure_fixed["Flash outlet pressure"] = p_reg[0]
            self.stages[1], self.kinds[1] = m.fs.stage1, "condenser_flash"
            m.fs.arc_v_1 = Arc(source=self.stages[2].vap_out, destination=m.fs.stage1.inlet)
            m.fs.arc_l_1 = Arc(source=m.fs.stage1.liq_outlet, destination=self.stages[2].liq_in)
            # Flash's default ideal_separation: its outlets are the vapour and liquid phases of the
            # control volume's outlet state.
            self.products["TOP"] = {"port": m.fs.stage1.vap_outlet,
                                    "state": m.fs.stage1.control_volume.properties_out[0],
                                    "phase": "Vap"}
        elif cond == "total":
            m.fs.stage1 = Condenser(property_package=props,
                                    condenser_type=CondenserType.totalCondenser,
                                    temperature_spec=TemperatureSpec.atBubblePoint)
            m.fs.stage1.condenser_pressure.fix(p_reg[0])
            self.unit_pressure_fixed["condenser_pressure"] = p_reg[0]
            self.stages[1], self.kinds[1] = m.fs.stage1, "condenser_total"
            m.fs.arc_v_1 = Arc(source=self.stages[2].vap_out, destination=m.fs.stage1.inlet)
            m.fs.arc_l_1 = Arc(source=m.fs.stage1.reflux, destination=self.stages[2].liq_in)
            self.products["TOP"] = {"port": m.fs.stage1.distillate,
                                    "state": m.fs.stage1.control_volume.properties_out[0],
                                    "phase": "Liq"}
        else:
            self.products["TOP"] = {"port": self.stages[1].vap_out,
                                    "state": self.stages[1].properties_out[0], "phase": "Vap"}
        for j in range(first, last):
            m.fs.add_component(f"arc_l_{j}", Arc(source=self.stages[j].liq_out,
                                                 destination=self.stages[j + 1].liq_in))
            m.fs.add_component(f"arc_v_{j + 1}", Arc(source=self.stages[j + 1].vap_out,
                                                     destination=self.stages[j].vap_in))
        if reb == "partial":
            m.fs.add_component(f"stage{n}", Reboiler(property_package=props, has_boilup_ratio=True,
                                                     has_pressure_change=False))
            r = m.fs.component(f"stage{n}")
            self.stages[n], self.kinds[n] = r, "reboiler"
            m.fs.add_component(f"arc_l_{n - 1}", Arc(source=self.stages[n - 1].liq_out,
                                                     destination=r.inlet))
            m.fs.add_component(f"arc_v_{n}", Arc(source=r.vapor_reboil,
                                                 destination=self.stages[n - 1].vap_in))
            self.products["BOTTOM"] = {"port": r.bottoms,
                                       "state": r.control_volume.properties_out[0],
                                       "phase": "Liq"}
        else:
            self.products["BOTTOM"] = {"port": self.stages[n].liq_out,
                                       "state": self.stages[n].properties_out[0], "phase": "Liq"}
        for inlet in case["inlets"]:
            j = int(inlet["stage"])
            tray = self.stages[j]
            if inlet["port"] == "feed":
                port, state = tray.feed, tray.properties_in_feed[0]
            elif inlet["port"] == "top":
                assert j == 1 and cond == "none"
                port, state = tray.liq_in, tray.properties_in_liq[0]
            elif inlet["port"] == "bottom":
                assert j == n and reb == "none"
                port, state = tray.vap_in, tray.properties_in_vap[0]
            else:
                raise ValueError(inlet["port"])
            self.inlets.append({"tag": inlet["port"], "port": port, "case": inlet, "state": state,
                                "stage": j})
        pyo.TransformationFactory("network.expand_arcs").apply_to(m)

    # -- specifications (§5.1 row 9, §17.4; L2(b) rows from S02 §2.1 / S06 §2) --

    def _apply_specifications(self) -> None:
        import pyomo.environ as pyo

        case, n = self.case, self.n
        inlet_c = {c: sum(Decimal(i["n_mol_per_s"][k]) for i in case["inlets"])
                   for k, c in enumerate(("A", "B", "C"))}
        f_total = sum(inlet_c.values())
        for end, spec in case["specifications"].items():
            kind, value = spec["kind"], float(spec["value"])
            how = self.real["specifications"][end]
            unit = self.stages[1] if end == "condenser" else self.stages[n]
            info: dict[str, Any] = {"kind": kind, "registered": spec, "realization": how}
            expr = None
            if how == "native":
                if kind == "reflux_ratio":
                    unit.reflux_ratio.fix(value)
                    info["tool"] = "Condenser.reflux_ratio fixed (reflux / distillate)"
                elif kind == "boilup_ratio":
                    unit.boilup_ratio.fix(value)
                    info["tool"] = "Reboiler.boilup_ratio fixed (vapor_reboil / bottoms)"
                elif kind == "duty":
                    unit.heat_duty.fix(value)
                    info["tool"] = "Reboiler.heat_duty fixed, W, heat into the reboiler"
                else:
                    raise ValueError(kind)
            else:
                native = None
                if end == "condenser":
                    top = self.products["TOP"]["port"]
                    if self.kinds[1] == "condenser_total":
                        unit.reflux_ratio.unfix()
                        native = unit.reflux_ratio
                    if kind == "reflux_ratio":
                        liq = unit.liq_outlet if self.kinds[1] == "condenser_flash" else unit.reflux
                        expr = liq.flow_mol[0] - value * top.flow_mol[0] == 0
                        info["tool"] = "L_1 - RR*·V_1 = 0 (S02 §2.1)"
                    elif kind == "distillate_rate":
                        expr = top.flow_mol[0] - value == 0
                        info["tool"] = "V_1 - D* = 0 (S02 §2.1)"
                    elif kind == "purity":
                        c = spec["component"]
                        pi_star = float(f_total) * value  # S06 §2: π* = fl(x*·F)
                        expr = (float(f_total) * top.flow_mol[0] * top.mole_frac_comp[0, c]
                                - pi_star * top.flow_mol[0] == 0)
                        info["tool"] = (f"F·n_{c} - π*·P = 0 with F = {float(f_total)!r}, "
                                        f"π* = fl(x*·F) = {pi_star!r} (S06 §2)")
                    else:
                        raise ValueError(kind)
                else:
                    bottom = self.products["BOTTOM"]["port"]
                    unit.boilup_ratio.unfix()
                    native = unit.boilup_ratio
                    if kind == "bottoms_rate":
                        expr = bottom.flow_mol[0] - value == 0
                        info["tool"] = "L_N - B* = 0 (S02 §2.1)"
                    elif kind == "recovery":
                        c = spec["component"]
                        nu_star = float(inlet_c[c]) * value  # S06 §2: ν* = fl(r*·F_c)
                        expr = bottom.flow_mol[0] * bottom.mole_frac_comp[0, c] - nu_star == 0
                        info["tool"] = (f"n_{c} - ν* = 0 on the bottoms, ν* = fl(r*·F_{c}) = "
                                        f"{nu_star!r} mol/s (S06 §2)")
                    elif kind == "temperature":
                        s = int(spec["stage"])
                        expr = self.stage_state(s).temperature - value == 0
                        info["tool"] = f"T_{s} - T* = 0 on our stage {s} ({self.stages[s].name}) (S06 §2)"
                    else:
                        raise ValueError(kind)
                spec_block = unit if kind != "temperature" else self.m.fs
                name = f"s03_spec_{end}"
                spec_block.add_component(name, pyo.Constraint(expr=expr))
                con = spec_block.component(name)
                info["equation"] = f"{con.name}: {con.expr}"
                info["replaces"] = None if native is None else native.name
                if kind == "temperature":
                    self.nonlocal_specs.append((con, native))
            self.spec_info[end] = info

    # -- helpers --

    def stage_state(self, j: int) -> Any:
        u = self.stages[j]
        return u.properties_out[0] if self.kinds[j] == "tray" else u.control_volume.properties_out[0]

    def stage_outlets(self, j: int) -> tuple[Any, Any]:
        """(liquid leaving, vapour leaving) ports of our stage j (None where absent)."""
        u, k = self.stages[j], self.kinds[j]
        if k == "tray":
            return u.liq_out, u.vap_out
        if k == "condenser_flash":
            return u.liq_outlet, u.vap_outlet
        if k == "condenser_total":
            return u.reflux, None
        return u.bottoms, u.vapor_reboil

    def stage_duty(self, j: int) -> float | None:
        u = self.stages[j]
        hd = u.component("heat_duty")
        return None if hd is None else float(self.pyo.value(hd[0]))

    def state_blocks(self, j: int) -> list[Any]:
        from idaes.core.base.property_base import StateBlockData

        return [b for b in self.stages[j].component_data_objects(self.pyo.Block, descend_into=True)
                if isinstance(b, StateBlockData)]

    def guess_tray_inlets(self) -> None:
        """§5.1 row 12's profile on every tray inlet that is not a case inlet (see INITIALIZATION)."""
        inlet_ports = {id(i["port"]) for i in self.inlets}
        flows, _t, _p = inlet_state(self.case["inlets"][0])
        total = sum(flows.values())
        for j, u in self.stages.items():
            if self.kinds[j] != "tray":
                continue
            for name, jj in (("liq_in", max(j - 1, 1)), ("vap_in", min(j + 1, self.n))):
                port = getattr(u, name)
                if id(port) in inlet_ports:
                    continue
                port.temperature[0].set_value(profile_t(self.case, jj))
                port.flow_mol[0].set_value(1.0)
                port.pressure[0].set_value(float(self.case["stage_pressures_Pa"][j - 1]))
                for c in ("A", "B", "C"):
                    port.mole_frac_comp[0, c].set_value(flows[c] / total)

    # -- §2.4 --

    def inspection(self) -> dict[str, Any]:
        """§2.4's answers, read from the built model before it is solved."""
        pyo, case, n = self.pyo, self.case, self.n
        props = self.m.fs.props
        blocks = [b for j in self.stages for b in self.state_blocks(j)]
        stage_map = {str(j): {"unit": self.stages[j].name, "kind": self.kinds[j],
                              "idaes_class": type(self.stages[j]).__name__}
                     for j in sorted(self.stages)}
        feed = []
        for i in self.inlets:
            feed.append({"inlet": i["tag"], "registered_stage": int(i["case"]["stage"]),
                         "idaes_unit": i["port"].parent_block().name, "idaes_port": i["port"].name,
                         "unit_is_our_stage": i["port"].parent_block() is self.stages[i["stage"]],
                         "declared_phase": i["case"]["phase"],
                         "enters_whole": "yes: the whole stream enters this port; IDAES's Tray "
                                         "mixes its feed, liquid and vapour inlets into one "
                                         "equilibrium stage"})
        k1 = self.kinds.get(1)
        if k1 == "condenser_flash":
            cond_text = ("partial (S02) at L3: IDAES Flash; its vapour outlet is the distillate and its "
                         "liquid outlet is joined by an Arc to stage 2's liquid inlet (all liquid "
                         "refluxed); no liquid-distillate stream exists")
        elif k1 == "condenser_total":
            c = self.stages[1]
            cond_text = (f"total: IDAES Condenser, condenser_type={c.config.condenser_type.name}, "
                         f"temperature_spec={c.config.temperature_spec.name} (eq_total_cond_spec: "
                         "T = bubble temperature of the outlet; no subcooling)")
        else:
            cond_text = "absent: the top inlet enters stage 1's liquid inlet (an ordinary Tray)"
        if self.kinds.get(n) == "reboiler":
            reb_text = ("kettle: IDAES Reboiler (equilibrium stage with duty; bottoms = liquid, "
                        "vapor_reboil = vapour, returned to stage N-1)")
        else:
            reb_text = "absent: the bottom inlet enters stage N's vapour inlet (an ordinary Tray)"
        pressure_fixed = {v.name: float(v.value) for b in blocks for v in [b.pressure] if v.fixed}
        trays = [u for j, u in self.stages.items() if self.kinds[j] == "tray"]
        return {
            "property_package": {
                "every_state_block_uses_fs_props": all(b.params is props for b in blocks),
                "state_block_count": len(blocks),
                "package": "idaes_representability.build_property_package: GenericParameterBlock, "
                           "SYN-001 constants, Ideal EoS, SmoothVLE, h_form_ig = L_i, h_form_liq = 0",
            },
            "stage_map": {"stage_count_registered": n, "stage_count_idaes": len(self.stages),
                          "map": stage_map,
                          "rule": "our j (S02 §1.1, condenser = 1 and reboiler = N when present); "
                                  "TrayColumn tray k = j - 1"},
            "feed_stages": feed,
            "condenser_realization": cond_text,
            "reboiler_realization": reb_text,
            "specifications": self.spec_info,
            "pressures": {
                "fixed_pressure_variables_Pa": pressure_fixed,
                "unit_pressure_specifications_Pa": self.unit_pressure_fixed,
                "registered_Pa": [float(p) for p in case["stage_pressures_Pa"]],
                "trays_have_pressure_change": [bool(u.config.has_pressure_change) for u in trays],
                "pressure_relation": "none: each Tray's outlet pressure equals its liquid inlet's "
                                     "(pressure_drop_equation without deltaP), the Reboiler has no "
                                     "pressure change, and the top unit's pressure is fixed",
            },
            "intermediate_stages": {
                "trays_have_heat_transfer": [bool(u.config.has_heat_transfer) for u in trays],
                "trays_side_draws": [bool(u.config.has_liquid_side_draw or
                                          u.config.has_vapor_side_draw) for u in trays],
                "efficiency": "1: IDAES's Tray is an equilibrium stage (no efficiency parameter)",
                "hydraulics": "none: no holdup, hydraulics, entrainment or weeping in Tray",
            },
            "initialization": INITIALIZATION,
            "degrees_of_freedom": int(_dof(self.m)),
        }

    # -- §2.4 for an inexpressible partial condenser: the facts, from a built model --

    @staticmethod
    def partial_condenser_facts() -> dict[str, Any]:
        from idaes.core.util.exceptions import ConfigurationError
        from idaes.models_extra.column_models import Condenser
        from idaes.models_extra.column_models.condenser import CondenserType, TemperatureSpec
        from idaes_representability import new_flowsheet

        m = new_flowsheet()
        out: dict[str, Any] = {}
        try:
            m.fs.c0 = Condenser(property_package=m.fs.props,
                                condenser_type=CondenserType.partialCondenser,
                                temperature_spec=TemperatureSpec.atBubblePoint)
            out["partial_at_bubble_point"] = "accepted"
        except ConfigurationError as exc:
            out["partial_at_bubble_point"] = f"ConfigurationError: {exc}"
        m.fs.c = Condenser(property_package=m.fs.props,
                           condenser_type=CondenserType.partialCondenser,
                           temperature_spec=TemperatureSpec.customTemperature)
        c = m.fs.c
        out["reflux_split_fraction"] = str(c.reflux_split_fraction.expr)
        dist = c.distillate.vars["flow_mol"]
        out["distillate_flow_mol_component_type"] = dist.ctype.__name__
        out["distillate_flow_mol_is_variable"] = dist.ctype.__name__ == "Var"
        out["distillate_flow_mol"] = str(dist[0].expr) if hasattr(dist[0], "expr") else str(dist[0])
        out["reflux_flow_mol"] = str(c.reflux.vars["flow_mol"][0].expr)
        out["vapor_outlet_flow_mol"] = str(c.vapor_outlet.vars["flow_mol"][0].expr)
        out["ports"] = [p.local_name for p in (c.reflux, c.distillate, c.vapor_outlet)]
        return out

    # -- initialization (§5.1 row 12; INITIALIZATION) and solves --

    def initialize(self) -> list[str]:
        """§5.1 row 12 and INITIALIZATION: unit initializers, then one full initializer solve."""
        from idaes.core.solvers import get_solver

        events: list[str] = []
        self.guess_tray_inlets()
        for con, native in self.nonlocal_specs:
            con.deactivate()
            native.fix(native.value if native.value is not None else 0.5)
            events.append(f"{con.name} deactivated and {native.name} fixed at {native.value} "
                          "for the initializers")
        if self.real["unit"] == "TrayColumn":
            self._init_unit(self.m.fs.col, events)
        else:
            self._init_composition(events)
        for con, native in self.nonlocal_specs:
            con.activate()
            native.unfix()
            events.append(f"{con.name} restored, {native.name} unfixed")
        res = get_solver().solve(self.m, tee=False)
        events.append(f"full initializer solve: {res.solver.termination_condition}")
        return events

    def _init_unit(self, unit: Any, events: list[str]) -> None:
        try:
            unit.initialize()
            events.append(f"{unit.name}.initialize: returned")
        except Exception as exc:
            events.append(f"{unit.name}.initialize: {type(exc).__name__}: {exc}")
            self._release_inlet_states()

    def _init_composition(self, events: list[str]) -> None:
        """`TrayColumn.initialize`'s order on a composition: the trays holding a case inlet first,
        then the end units from the nearest of them, then every other tray with its liquid from the
        nearest initialized unit above and its vapour from the nearest initialized unit below."""
        from idaes.core.util.initialization import propagate_state

        n = self.n
        trays = [j for j in sorted(self.stages) if self.kinds[j] == "tray"]
        anchors = sorted({i["stage"] for i in self.inlets})
        done: set[int] = set()
        for j in anchors:
            self._init_unit(self.stages[j], events)
            done.add(j)
        if self.kinds[1] != "tray":
            propagate_state(source=self.stage_outlets(anchors[0])[1],
                            destination=self.stages[1].inlet)
            self._init_unit(self.stages[1], events)
            done.add(1)
        if self.kinds[n] != "tray":
            propagate_state(source=self.stage_outlets(anchors[-1])[0],
                            destination=self.stages[n].inlet)
            self._init_unit(self.stages[n], events)
            done.add(n)
        for j in trays:
            if j in done:
                continue
            above = max((k for k in done if k < j), default=None)
            below = min((k for k in done if k > j), default=None)
            if above is not None:
                propagate_state(source=self.stage_outlets(above)[0], destination=self.stages[j].liq_in)
            if below is not None:
                propagate_state(source=self.stage_outlets(below)[1], destination=self.stages[j].vap_in)
            self._init_unit(self.stages[j], events)

    def _release_inlet_states(self) -> None:
        """After an initializer exception: unfix every variable it left fixed beyond the build's."""
        keep = self.fixed_at_build | {id(native) for _con, native in self.nonlocal_specs}
        for v in self.m.component_data_objects(self.pyo.Var):
            if v.fixed and id(v) not in keep:
                v.unfix()

    def solve_final(self, options: dict[str, Any], logfile: Path) -> dict[str, Any]:
        """Set the registered SmoothVLE eps, then the registered final solve (§5.1 row 13)."""
        import pyomo.environ as pyo
        from pyomo.opt import SolverStatus

        rec: dict[str, Any] = {"smooth_vle_eps_set_on": t06i.set_smooth_vle_eps(self.m),
                               "degrees_of_freedom": int(_dof(self.m))}
        solver = pyo.SolverFactory("ipopt")
        for k, v in options.items():
            solver.options[k] = v
        rec["ipopt_options"] = options
        t0 = time.perf_counter()
        result = solver.solve(self.m, tee=False, logfile=str(logfile), load_solutions=False)
        rec["wall_time_solve_s"] = time.perf_counter() - t0
        rec["solver_status"] = str(result.solver.status)
        rec["termination_condition"] = str(result.solver.termination_condition)
        rec["ipopt"] = t06i.parse_ipopt_log(logfile.read_text(encoding="utf-8", errors="replace"))
        # Converged means Ipopt met the requested tolerances ("Optimal Solution Found"); Pyomo also
        # calls "Solved To Acceptable Level" optimal, which is not counted (T06 §9.3).
        rec["converged"] = bool(pyo.check_optimal_termination(result)) and (
            rec["ipopt"].get("exit") == "Optimal Solution Found.")
        if not rec["converged"]:
            result.solver.status = SolverStatus.warning
            rec["last_iterate_loaded_although_not_converged"] = True
        self.m.solutions.load_from(result)
        rec["termination"] = rec["ipopt"].get("exit", rec["termination_condition"])
        return rec


def _dof(m: Any) -> int:
    from idaes.core.util.model_statistics import degrees_of_freedom

    return degrees_of_freedom(m)


# ---- the record of one solved model and its rule values ------------------------------------------


def _v(x: Any) -> float:
    import pyomo.environ as pyo

    return float(pyo.value(x))


def port_flows(port: Any) -> dict[str, float]:
    return {c: _v(port.flow_mol[0] * port.mole_frac_comp[0, c]) for c in ("A", "B", "C")}


def raw_output(model: Model) -> dict[str, Any]:
    """Per stage T, P, L, V, x, y and duty; products and inlets with their enthalpy flows (own datum)."""
    out: dict[str, Any] = {"stages": {}}
    for j in sorted(model.stages):
        sb = model.stage_state(j)
        liq, vap = model.stage_outlets(j)
        out["stages"][str(j)] = {
            "unit": model.stages[j].name, "T_K": _v(sb.temperature), "P_Pa": _v(sb.pressure),
            "L_mol_per_s": None if liq is None else _v(liq.flow_mol[0]),
            "V_mol_per_s": None if vap is None else _v(vap.flow_mol[0]),
            "x": None if liq is None else [_v(liq.mole_frac_comp[0, c]) for c in ("A", "B", "C")],
            "y": None if vap is None else [_v(vap.mole_frac_comp[0, c]) for c in ("A", "B", "C")],
            "duty_W": model.stage_duty(j),
        }
    out["products"] = {}
    for tag, p in model.products.items():
        flow = _v(p["port"].flow_mol[0])
        h = _v(p["state"].enth_mol if p["phase"] is None else p["state"].enth_mol_phase[p["phase"]])
        out["products"][tag] = {"port": p["port"].name, "flow_mol_per_s": flow,
                                "component_mol_per_s": port_flows(p["port"]),
                                "enth_mol_J_per_mol": h, "enthalpy_flow_W": flow * h,
                                "enthalpy_source": p["state"].name + (
                                    ".enth_mol" if p["phase"] is None
                                    else f".enth_mol_phase[{p['phase']}]"),
                                "T_K": _v(p["port"].temperature[0]),
                                "P_Pa": _v(p["port"].pressure[0])}
    out["inlets"] = {}
    for i in model.inlets:
        flow, h = _v(i["state"].flow_mol), _v(i["state"].enth_mol)
        out["inlets"][i["tag"]] = {"port": i["port"].name, "flow_mol_per_s": flow,
                                   "component_mol_per_s": port_flows(i["port"]),
                                   "enth_mol_J_per_mol": h, "enthalpy_flow_W": flow * h,
                                   "enthalpy_source": i["state"].name + ".enth_mol"}
    return out


def quantities(model: Model, raw: dict[str, Any]) -> dict[str, float]:
    """The registered quantities of the case, in our stage numbering, from IDAES's own record."""
    st = raw["stages"]
    out: dict[str, float] = {}
    for name, _kind in model.case["quantities"]:
        if name.startswith(("T[", "L[", "V[")):
            key = {"T": "T_K", "L": "L_mol_per_s", "V": "V_mol_per_s"}[name[0]]
            out[name] = st[name[2:-1]][key]
        elif name == "reflux":
            out[name] = st["1"]["L_mol_per_s"]
        elif name.startswith("top["):
            out[name] = raw["products"]["TOP"]["component_mol_per_s"][name[4:-1]]
        elif name.startswith("bottom["):
            out[name] = raw["products"]["BOTTOM"]["component_mol_per_s"][name[7:-1]]
        elif name == "Q_condenser":
            out[name] = st["1"]["duty_W"]
        elif name == "Q_reboiler":
            out[name] = st[str(model.n)]["duty_W"]
        else:
            raise KeyError(f"no IDAES value for registered quantity {name}")
        if out[name] is None:
            raise KeyError(f"IDAES record has no value for {name}")
    return out


def spec_values(model: Model, raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """§5.1 row 9 with §17.4, from IDAES's own flows (and T, duty), against the registered value."""
    case, st, n = model.case, raw["stages"], model.n
    top, bottom = raw["products"]["TOP"], raw["products"]["BOTTOM"]
    inlet_c = {c: sum(i["component_mol_per_s"][c] for i in raw["inlets"].values())
               for c in ("A", "B", "C")}
    out = {}
    for end, spec in case["specifications"].items():
        kind, reg = spec["kind"], float(spec["value"])
        prod = top if end == "condenser" else bottom
        if kind == "reflux_ratio":
            if case["condenser"] == "total":
                got, definition = st["1"]["L_mol_per_s"] / top["flow_mol_per_s"], "reflux / D"
            else:
                got, definition = st["1"]["L_mol_per_s"] / st["1"]["V_mol_per_s"], "L[1] / V[1]"
        elif kind == "boilup_ratio":
            got = st[str(n)]["V_mol_per_s"] / st[str(n)]["L_mol_per_s"]
            definition = "V[N] / L[N]"
        elif kind == "distillate_rate":
            got, definition = top["flow_mol_per_s"], "distillate (TOP product) flow"
        elif kind == "bottoms_rate":
            got, definition = bottom["flow_mol_per_s"], "bottoms L_N (BOTTOM product) flow"
        elif kind == "duty":
            got, definition = st[str(n)]["duty_W"], "reboiler duty, W, into the stage"
        elif kind == "purity":
            c = spec["component"]
            got = prod["component_mol_per_s"][c] / prod["flow_mol_per_s"]
            definition = f"n_{c}/P of the {end} end's product"
        elif kind == "recovery":
            c = spec["component"]
            got = prod["component_mol_per_s"][c] / inlet_c[c]
            definition = f"n_{c}/F_{c}: the {end} end's product flow of {c} over the inlets' total"
        elif kind == "temperature":
            s = int(spec["stage"])
            got, definition = st[str(s)]["T_K"], f"T of our stage {s}"
        else:
            raise ValueError(kind)
        absolute = got - reg
        relative = absolute / abs(reg)
        threshold, basis = RULE2D_SPEC[kind]
        accuracy = abs(absolute) if basis == "absolute" else abs(relative)
        out[end] = {
            "kind": kind, "definition": definition, "registered": reg, "idaes": got,
            "relative_difference": relative, "absolute_difference": absolute,
            "rule2c_threshold_relative": RULE2C_SPEC_RELATIVE,
            "rule2c_passes": bool(math.isfinite(relative) and abs(relative) <= RULE2C_SPEC_RELATIVE),
            "rule2d_threshold": threshold, "rule2d_basis": basis, "rule2d_measure": accuracy,
            "rule2d_passes": bool(math.isfinite(accuracy) and accuracy <= threshold),
        }
    return out


def rule_values(model: Model, raw: dict[str, Any], variables: dict[str, Any],
                eps: dict[str, float], converged: bool) -> dict[str, Any]:
    """Rules 2, 2b, 2c and 2d's specification residual (§7.1), from IDAES's own record only."""
    case, n = model.case, model.n
    rule2 = fx.component_balance([i["component_mol_per_s"] for i in raw["inlets"].values()],
                                 [p["component_mol_per_s"] for p in raw["products"].values()])
    duties = {k: d for k, d in (("Q_condenser", raw["stages"]["1"]["duty_W"]),
                                ("Q_reboiler", raw["stages"][str(n)]["duty_W"]))
              if d is not None and model.kinds[1 if k == "Q_condenser" else n] != "tray"}
    energy = (sum(i["enthalpy_flow_W"] for i in raw["inlets"].values()) + sum(duties.values())
              - sum(p["enthalpy_flow_W"] for p in raw["products"].values()))
    r2 = {"converged": converged, "component_balance": rule2, "energy_balance_W": energy,
          "energy_threshold_W": RULE2_ENERGY_W, "duties_W": duties,
          "passes": bool(converged and rule2["passes"] and math.isfinite(energy)
                         and abs(energy) <= RULE2_ENERGY_W)}
    r2b = fx.smooth_vle_self_check(variables, eps)
    reg_p = [float(p) for p in case["stage_pressures_Pa"]]
    p_dev = 0.0
    for j in model.stages:
        for b in model.state_blocks(j):
            p_dev = max(p_dev, abs(_v(b.pressure) - reg_p[j - 1]))
    inter = [abs(raw["stages"][str(j)]["duty_W"] or 0.0) for j in model.stages
             if model.kinds[j] == "tray"]
    checks: dict[str, Any] = {
        "stage_count": {"value": len(model.stages), "registered": n,
                        "passes": len(model.stages) == n and sorted(model.stages) == list(
                            range(1, n + 1))},
        "feed_stage": {"value": [i["port"].parent_block() is model.stages[i["stage"]]
                                 and i["stage"] == int(i["case"]["stage"]) for i in model.inlets]},
        "pressure_max_abs_dev_Pa": {"value": p_dev, "threshold": RULE2C_PRESSURE_PA,
                                    "passes": p_dev <= RULE2C_PRESSURE_PA},
        "intermediate_duty_max_abs_W": {
            "value": max(inter) if inter else 0.0, "threshold": RULE2C_INTERMEDIATE_DUTY_W,
            "note": "IDAES Trays built with has_heat_transfer=False carry no heat term (Q = 0)",
            "passes": (max(inter) if inter else 0.0) <= RULE2C_INTERMEDIATE_DUTY_W},
    }
    checks["feed_stage"]["passes"] = all(checks["feed_stage"]["value"])
    if case["condenser"] == "partial":
        checks["zero_liquid_distillate_mol_per_s"] = {
            "value": 0.0, "threshold": RULE2C_ZERO_DISTILLATE_MOL_PER_S,
            "note": "no liquid-distillate stream exists: the Flash's liquid outlet is joined to "
                    "stage 2's liquid inlet by an Arc",
            "passes": True}
    specs = spec_values(model, raw)
    checks["specification"] = {"value": specs,
                               "passes": all(s["rule2c_passes"] for s in specs.values())}
    r2c = {"checks": checks, "passes": all(c["passes"] for c in checks.values())}
    r2d_spec = {"passes": all(s["rule2d_passes"] for s in specs.values()),
                "max_measure_by_end": {e: s["rule2d_measure"] for e, s in specs.items()}}
    return {"rule2": r2, "rule2b": r2b, "rule2c": r2c, "rule2d_specification": r2d_spec}


def rerun_movement(case: dict[str, Any], base: dict[str, float],
                   rerun: dict[str, float]) -> dict[str, Any]:
    kinds = dict(case["quantities"])
    ratios = {k: abs(rerun[k] - base[k]) / quantity_tolerance(kinds[k], base[k]) for k in base}
    worst = max(ratios, key=lambda k: ratios[k])
    return {"ratio_to_tolerance": ratios, "max_ratio": ratios[worst], "max_quantity": worst,
            "tolerance_value_used": "the tool's own value (the script reads no other)",
            "passes": bool(math.isfinite(ratios[worst])
                           and ratios[worst] <= RULE2D_RERUN_FRACTION)}


def run_once(data: dict[str, Any], case: dict[str, Any], real: dict[str, Any], rerun: bool,
             logfile: Path) -> tuple[Model, dict[str, Any]]:
    model = Model(data, case, real)
    t0 = time.perf_counter()
    events = model.initialize()
    rec: dict[str, Any] = {"initialization_events": events,
                           "wall_time_initialize_s": time.perf_counter() - t0}
    rec.update(model.solve_final(final_options(data, rerun), logfile))
    return model, rec


def attempt(data: dict[str, Any], cid: str, case: dict[str, Any], real: dict[str, Any],
            log_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """One level's run with its accuracy rerun; returns (summary, full record or None)."""
    level = real["level"]
    summary: dict[str, Any] = {"level": level}
    full: dict[str, Any] | None = None
    try:
        model, rec = run_once(data, case, real, False, log_dir / f"idaes-{cid}-{level}.ipopt.log")
        summary.update(converged=rec["converged"], termination=rec["termination"],
                       ipopt_iterations=rec["ipopt"].get("iterations"),
                       wall_time_solve_s=rec["wall_time_solve_s"])
        raw = raw_output(model)
        variables, eps = t06i.all_variables(model.m), t06i.smooth_vle_parameters(model.m)
        raw.update(variables=variables, smooth_vle_parameters=eps,
                   constraint_residuals=t06i.constraint_residuals(model.m))
        rules = rule_values(model, raw, variables, eps, rec["converged"])
        full = {"record": rec, "raw": raw, "rules": rules}
        summary["rule2_component_max_mol_per_s"] = rules["rule2"]["component_balance"][
            "max_abs_mol_per_s"]
        summary["rule2_energy_W"] = rules["rule2"]["energy_balance_W"]
        summary["rule2b_max_shift_K"] = rules["rule2b"]["max_shift_K"]
        summary["rule2c_failed_checks"] = [k for k, c in rules["rule2c"]["checks"].items()
                                           if not c["passes"]]
        summary["rule2d_specification"] = rules["rule2d_specification"]["max_measure_by_end"]
        if not rec["converged"]:
            summary.update(passes=False, failed_rule="2", reason=rec["termination"])
            return summary, full
        full["quantities"] = qs = quantities(model, raw)
        if not rules["rule2"]["passes"]:
            summary.update(passes=False, failed_rule="2", reason="tool-internal balance")
            return summary, full
        if not rules["rule2b"]["passes"]:
            summary.update(passes=False, failed_rule="2b",
                           reason=f"smooth_vle_shift({rules['rule2b']['max_shift_K']})")
            return summary, full
        if not rules["rule2c"]["passes"]:
            summary.update(passes=False, failed_rule="2c",
                           reason=f"semantics: {summary['rule2c_failed_checks']}")
            return summary, full
        if not rules["rule2d_specification"]["passes"]:
            summary.update(passes=False, failed_rule="2d", reason="specification residual")
            return summary, full
        model2, rec2 = run_once(data, case, real, True,
                                log_dir / f"idaes-{cid}-{level}-rerun.ipopt.log")
        rerun: dict[str, Any] = {"ipopt_options": rec2["ipopt_options"],
                                 "converged": rec2["converged"],
                                 "termination": rec2["termination"],
                                 "ipopt": rec2["ipopt"],
                                 "initialization_events": rec2["initialization_events"],
                                 "wall_time_solve_s": rec2["wall_time_solve_s"]}
        if rec2["converged"]:
            raw2 = raw_output(model2)
            q2 = quantities(model2, raw2)
            rerun["quantities"] = q2
            rerun["movement"] = rerun_movement(case, qs, q2)
            rerun["passes"] = rerun["movement"]["passes"]
            summary["rerun_max_ratio"] = rerun["movement"]["max_ratio"]
        else:
            rerun["passes"] = False
        full["rerun"] = rerun
        if not rerun["passes"]:
            summary.update(passes=False, failed_rule="2d", reason="accuracy rerun")
            return summary, full
        summary.update(passes=True, failed_rule=None, reason="passes rules 2-2d")
        return summary, full
    except Exception as exc:  # every failure is recorded, none is hidden
        summary.update(passes=False, failed_rule="2", reason=f"{type(exc).__name__}: {exc}",
                       traceback=traceback.format_exc(limit=6))
        return summary, full


# ---- qualification (§2.3) ---------------------------------------------------------------------


def qualify_case(data: dict[str, Any], cid: str, log_dir: Path,
                 partial_facts: dict[str, Any]) -> dict[str, Any]:
    case = data["cases"][cid]
    per: dict[str, Any] = {"levels": {}, "attempts": [], "selected": None, "full": None}
    for level in ("L1", "L2", "L3"):
        real = realization(case, level)
        entry: dict[str, Any] = {"realization": {k: v for k, v in real.items()
                                                 if k != "inspect_partial_condenser"}}
        if real.get("inspect_partial_condenser"):
            entry["structural_inspection"] = {"condenser_realization": partial_facts,
                                              "expressible": False}
        if real["expressible"]:
            try:
                entry["structural_inspection"] = Model(data, case, real).inspection()
            except Exception as exc:
                real = {**real, "expressible": False,
                        "reason": f"model not built: {type(exc).__name__}: {exc}"}
                entry["realization"] = real
                entry["traceback"] = traceback.format_exc(limit=6)
        per["levels"][level] = entry
        if not real["expressible"]:
            print(f"idaes {cid} {level}: not expressible", file=sys.stderr, flush=True)
            continue
        summ, full = attempt(data, cid, case, real, log_dir)
        per["attempts"].append(summ)
        print(f"idaes {cid} {level}: {'PASS' if summ['passes'] else 'fail ' + str(summ['failed_rule'])}"
              f" ({summ.get('reason')})", file=sys.stderr, flush=True)
        if summ["passes"]:
            per["selected"], per["full"] = level, full
            break
        per["levels"][level]["failed_full_record"] = full
    return per


def not_available_reason(per: dict[str, Any]) -> str:
    parts = []
    for level, entry in per["levels"].items():
        real = entry["realization"]
        if not real["expressible"]:
            parts.append(f"{level}: {real['reason']}")
        else:
            fails = [f"{a['failed_rule']}: {a['reason']}" for a in per["attempts"]
                     if a["level"] == level]
            parts.append(f"{level}: failed rules 2-2d ({'; '.join(fails)})")
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--log-dir", type=Path,
                        default=fx.REPO_ROOT / "evidence" / "S03" / "artifacts" /
                        "s03-qualification" / "idaes-ipopt")
    parser.add_argument("--only", nargs="*", help="case ids (default: all)")
    args = parser.parse_args()
    out_dir, log_dir = args.out.resolve(), args.log_dir.resolve()
    for d in (out_dir / "qualification", out_dir / "results", log_dir):
        d.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("IDAES_DATA", str(ENV_DIR / "idaes-data"))
    t_start = time.perf_counter()
    import logging

    import idaes
    import pyomo

    logging.getLogger("idaes").setLevel(logging.WARNING)  # the attempts record what happened

    idaes.cfg.ipopt.options.linear_solver = fx.IDAES_SOLVER_OPTIONS["linear_solver"]
    data = load_cases()
    ids = args.only or list(data["cases"])
    fingerprint = fx.fingerprint("idaes", ENV_DIR)
    common = {
        "tool": "IDAES",
        "versions": {"idaes_pse": idaes.__version__, "pyomo": pyomo.__version__,
                     "python": sys.version.split()[0]},
        "environment_fingerprint": fingerprint,
        "input_file": "docs/derivations/scripts/s03_cases.json",
        "cases_sha256": file_sha256(CASES_PATH),
        "settings": {
            "registered": data["tool_settings"]["IDAES"],
            "final_solve_ipopt_options": fx.IDAES_SOLVER_OPTIONS,
            "rerun_ipopt_options": final_options(data, True),
            "smooth_vle_eps_K": fx.IDAES_SMOOTH_VLE_EPS_K,
            "initializer_ipopt_options": dict(idaes.cfg.ipopt.options),
            "threads": {k: os.environ.get(k) for k in
                        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            "property_package": "idaes_representability.build_property_package (SYN-001, "
                                "Ideal EoS, SmoothVLE, h_form_ig = L_i, h_form_liq = 0)",
            "initialization": INITIALIZATION,
            "temperature_profile_K": [PROFILE_T_TOP_K, PROFILE_T_BOTTOM_K],
        },
        "sign_conversion": SIGN_CONVERSION,
    }
    partial_facts = Model.partial_condenser_facts()
    qual: dict[str, Any] = {**common, "cases": {}, "q_s03_7_partial_condenser": partial_facts}
    status = 0
    n_ok = 0
    for cid in ids:
        case = data["cases"][cid]
        if case["tool_variant"]["IDAES"] == "not_applicable":
            reason = ("IDAES's SYN-001 mapping has no vaporization-enthalpy input (T06 §9.4); "
                      "spec §3.3 and §7.2: (PC-L, IDAES) is not_applicable, a registered absence "
                      "outside every count")
            rec = {**common, "case": cid, "case_definition": case, "not_applicable": reason}
            qual["cases"][cid] = {"not_applicable": reason}
            print(f"idaes {cid}: not_applicable", flush=True)
        else:
            t0 = time.perf_counter()
            per = qualify_case(data, cid, log_dir, partial_facts)
            sel = per["selected"]
            qual["cases"][cid] = {"available": sel is not None, "level": sel,
                                  "levels": {k: {kk: vv for kk, vv in v.items()
                                                 if kk != "failed_full_record"}
                                             for k, v in per["levels"].items()},
                                  "attempts": per["attempts"],
                                  "wall_time_s": time.perf_counter() - t0}
            rec = {**common, "case": cid, "case_definition": case, "attempts": per["attempts"]}
            if sel is None:
                reason = not_available_reason(per)
                qual["cases"][cid]["not_available_reason"] = reason
                rec.update(available=False, level=None, not_available_reason=reason,
                           levels=per["levels"])
                status = 1
            else:
                n_ok += 1
                full = per["full"]
                insp = per["levels"][sel]["structural_inspection"]
                rec.update(
                    available=True, level=sel, realization=per["levels"][sel]["realization"],
                    settings_used={"final_solve_ipopt_options": full["record"]["ipopt_options"],
                                   "smooth_vle_eps_K": fx.IDAES_SMOOTH_VLE_EPS_K},
                    stage_map=insp["stage_map"], feed_stages=insp["feed_stages"],
                    condenser_realization=insp["condenser_realization"],
                    reboiler_realization=insp["reboiler_realization"],
                    specifications=insp["specifications"], structural_inspection=insp,
                    converged=full["record"]["converged"],
                    termination=full["record"]["termination"],
                    solve=full["record"], raw_output=full["raw"], rule_values=full["rules"],
                    registered_quantities=full["quantities"], accuracy_rerun=full["rerun"],
                    levels_before={k: v for k, v in per["levels"].items() if k != sel},
                )
            print(f"idaes {cid}: available={sel is not None} level={sel}", flush=True)
        path = out_dir / "results" / f"idaes-{cid}.json"
        path.write_text(json.dumps(fx.finite(rec), indent=1) + "\n", encoding="utf-8")
    qual["wall_time_total_s"] = time.perf_counter() - t_start
    path = out_dir / "qualification" / "idaes.json"
    path.write_text(json.dumps(fx.finite(qual), indent=1) + "\n", encoding="utf-8")
    n_cases = sum(1 for cid in ids if data["cases"][cid]["tool_variant"]["IDAES"] != "not_applicable")
    print(f"idaes SUMMARY: {n_ok}/{n_cases} cases available; fingerprint matches "
          f"{fingerprint['matches']}", flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
