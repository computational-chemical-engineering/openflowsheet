"""S03 WO-S03-3/3b: blind qualification and runs of the column cases in DWSIM 9.0.5.

Authority: `docs/derivations/S03-spec.md` §2.2 (levels), §2.3 (the pre-registered "where available"
rule), §2.4 (structural questions), §5.1 (matched semantics), §5.2 with §17.2 (the column-solver
ladder, Amendment 1), §6 with §17.4 (thresholds, specification definitions) and §7.1 rules 2, 2c and
2d (computed here from DWSIM's own record only).

For every case of `s03_cases.json` (RC1-RC7, the ten perturbed cases, PC-P and PC-L) this script
builds DWSIM's own rigorous `DistillationColumn` on SYN-001 (T06's user compounds and Raoult's Law
package, imported from `t06_qualify_dwsim`, i.e. `docs/reference-environments.md` §5.0). It walks
§17.2's order: L1, for each tolerance (tightest first) and each method of
`column_method_order_amendment_1` in order, the structural inspection, then the run if the model is
expressible under that method; then L2(a), only under a method for which L1 was structurally
inexpressible. A run that passes rules 2-2c and 2d's specification residual is rerun at ten times
the column tolerance (§5.1 row 15) for 2d's movement check. Every position of the order is recorded,
as an attempt or as the structural reason none was made. The selection follows §5.2: the first rung
that passes for every case is the uniform setting; otherwise each case takes its own first passing
position (§2.3 step 1 for the levels).

Levels for DWSIM (§2.2): L1 is the native column and its native specifications; L2 is form (a) only
(a tool variable fixed at a value S02's semantics implies exactly); L3 is not admissible for DWSIM.

Blind (§2.3 step 2, §8): the only input file of this project is `s03_cases.json`; the only modules
of this project imported are T06's SYN-001 definitions (`t06_fixtures`, `dwsim_representability`,
`t06_qualify_dwsim`) and the runtime loader `dwsim_runtime`. No value of this project's solver, of
the generator or of any classifier output is read. It prints one line per case and one summary line.

    .venv-dwsim/bin/python spikes/references/s03_qualify_dwsim.py [--out DIR] [--only CASE ...]

Not part of `scripts/check.sh`: the gate never runs a tool.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import dwsim_representability as probe
import dwsim_runtime
import t06_fixtures as fx
import t06_qualify_dwsim as t06d

CASES_PATH = fx.REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json"
ENV_DIR = fx.REPO_ROOT / ".venv-dwsim"
DEFAULT_OUT = fx.REPO_ROOT / "benchmarks" / "s03" / "references"

# §6: allowances a_k, the relative term, and the rule 2/2c/2d thresholds.
ALLOWANCE = {"T": 1e-5, "flow": 3.1e-7, "duty": 1e-2}
RELATIVE = 1e-6
RULE2_COMPONENT_MOL_PER_S = 3.1e-8
RULE2_ENERGY_W = 1e-3
RULE2C_PRESSURE_PA = 1e-3
RULE2C_INTERMEDIATE_DUTY_W = 1e-3
RULE2C_ZERO_DISTILLATE_MOL_PER_S = 3.1e-8
RULE2C_SPEC_RELATIVE = 1e-4  # every kind (§17.4)
# Rule 2d's specification threshold per kind (§17.4): (basis, threshold). "absolute" is on the
# fraction (purity, recovery); "relative" is on the specified value.
RULE2D_SPEC = {
    "reflux_ratio": ("relative", 1e-8), "boilup_ratio": ("relative", 1e-8),
    "distillate_rate": ("relative", 1e-8), "bottoms_rate": ("relative", 1e-8),
    "duty": ("relative", 1e-8), "purity": ("absolute", 1e-8),
    "recovery": ("absolute", 1e-9), "temperature": ("relative", 1e-9),
}
RULE2D_RERUN_FRACTION = 0.1

# §17.2's methods, by the label `s03_cases.json` uses, mapped to the name DWSIM's column dispatches
# on (`Column.SolvingMethodName`).
NS, WH = "Napthali-Sandholm", "Wang-Henke"
DWSIM_METHOD_NAME = {
    NS: "Napthali-Sandholm (Simultaneous Correction)",
    WH: "Wang-Henke (Bubble Point)",
}
PERCENT_PER_FRACTION = 100.0  # DWSIM's Component_Recovery value is a percentage (§17.4: x 0.01)

SIGN_CONVERSION = (
    "Q_condenser = -1000 E(Q-COND) and Q_reboiler = +1000 E(Q-REB), W, Q > 0 into the stage; "
    "E in kW as DWSIM reports its energy streams (condenser: heat removed; reboiler: heat supplied)"
)
COMPONENT_FRACTION_UNIT = "M"  # DWSIM: "M"/"Molar" selects a mole fraction (NewtonRaphson.vb)


def load_cases() -> dict[str, Any]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    dw = data["tool_settings"]["DWSIM"]
    # T06's definitions are imported, not re-entered (§5.1 row 1); check they are the registered ones.
    for i, c in enumerate(fx.COMPONENTS):
        assert fx.dwsim_hvap_j_per_mol(c, True) == float(dw["dH_vap_J_per_mol"][i])
        assert fx.dwsim_hvap_j_per_mol(c, False) == float(dw["dH_vap_J_per_mol_PC-L"][i])
        assert fx.dwsim_hform_ig_j_per_mol(c) == float(dw["dH_vap_J_per_mol"][i])
        assert fx.T_BOIL[c] == float(dw["placeholders"]["NBP_K"][i])
    assert fx.PLACEHOLDER_TC == float(dw["placeholders"]["T_c_K"])
    assert fx.PLACEHOLDER_PC == float(dw["placeholders"]["P_c_Pa"])
    assert fx.PLACEHOLDER_OMEGA == float(dw["placeholders"]["omega"])
    assert fx.DWSIM_PP_OPTIONS["LiquidDensity_CorrectExpDataForPressure"] is bool(
        dw["liquid_density_pressure_correction"]
    )
    for key, value in fx.DWSIM_FLASH_SETTINGS.items():
        assert float(value) == (1e-10 if "Tolerance" in key else 1000.0), key
    return data


def ladder(dw: dict[str, Any]) -> list[tuple[float, str]]:
    """§17.2's positions within a level: tightest tolerance first, then the amended method order."""
    methods = list(dw["column_method_order_amendment_1"]["methods"])
    assert all(m in DWSIM_METHOD_NAME for m in methods), methods
    return [(float(t), m) for t in dw["column_tolerance_ladder"] for m in methods]


def quantity_tolerance(kind: str, value: float) -> float:
    """§6's tolerance with the tool's own value standing in for v (the script reads no other)."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


# ---- the model at each level (§2.2, §5.1) -----------------------------------------------------


# Structural reasons (§2.4 Q-X6: the tool's definition in its own variables), from DWSIM 9.0.5's
# source (`RigorousColumn.vb`, `RigorousColumnSolvers/NewtonRaphson.vb`, `BubblePoint.vb`).
NS_PARTIAL_REFLUX_RATIO = (
    "Napthali-Sandholm's condenser Stream_Ratio is L(0)/LSS(0) (NewtonRaphson.vb l. 446-448), the "
    "reflux over the liquid distillate, which a Full_Reflux condenser holds at 0; S02's reflux "
    "ratio on a partial condenser is L_1/V_1 (spec §5.1 row 9, §17.2 F2): not this specification. "
    "Wang-Henke's is L(0)/(LSS(0) + V(0)) = L_1/V_1"
)
PARTIAL_DISTILLATE_RATE = (
    "condenser specification distillate_rate: DWSIM's native rate option on the condenser "
    "(Product_Molar_Flow_Rate) is the liquid distillate LSS(0) (NewtonRaphson.vb l. 443-445, "
    "BubblePoint.vb l. 977-983), which a Full_Reflux condenser holds at 0; S02's D is the vapour "
    "distillate V_1 (spec §5.1 row 9). No native option of the Full_Reflux condenser is V_1"
)
INTERIOR_TEMPERATURE = (
    "DWSIM's reboiler Temperature specification is the reboiler stage's temperature Tj(ns), "
    "our stage {n} (NewtonRaphson.vb l. 492-494 and 919; BubblePoint.vb l. 291-293 and "
    "659-661); its condenser one is Tj(0), our stage 1. ColumnSpec.StageNumber selects no "
    "stage: the column reads it only as the -1 sentinel of its default distillate-rate "
    "specification and in a log line (RigorousColumn.vb l. 3646-3660 and 4651-4665), and no "
    "other method of the loaded DWSIM assemblies calls its accessors (settings."
    "stage_number_readers, an IL scan made by this script). The registered specification is T "
    "of stage {s} (spec §17.4): another stage, not this specification"
)
NO_L2A = (
    "no L2(a) realization: DWSIM's only one is a Partial_Condenser with its liquid distillate "
    "fixed at 0 and a vapour-rate specification, for a partial condenser's distillate_rate "
    "(spec §17.2)"
)


def end_option(case: dict[str, Any], end: str,
               method: str) -> tuple[str, float, str, str] | str:
    """DWSIM's native option for one registered end specification under one method (§5.1 row 9,
    §17.4), as SetCondenserSpec/SetReboilerSpec arguments, or the structural reason for none."""
    spec = case["specifications"][end]
    kind, value = spec["kind"], float(spec["value"])
    n = int(case["stage_count"])
    if end == "condenser":
        partial = case["condenser"] == "partial"
        if kind == "reflux_ratio":
            if partial and method == NS:
                return NS_PARTIAL_REFLUX_RATIO
            return ("Stream_Ratio", value, "", "")
        if kind == "purity" and partial:
            comp = probe.compound_name(spec["component"])
            return ("Component_Fraction", value, COMPONENT_FRACTION_UNIT, comp)
        if kind == "distillate_rate" and partial:
            return PARTIAL_DISTILLATE_RATE
    else:
        if kind == "boilup_ratio":
            return ("Stream_Ratio", value, "", "")
        if kind == "bottoms_rate":
            return ("Product_Molar_Flow_Rate", value, "mol/s", "")
        if kind == "duty":
            return ("Heat_Duty", value / 1000.0, "kW", "")
        if kind == "recovery":
            comp = probe.compound_name(spec["component"])
            return ("Component_Recovery", value * PERCENT_PER_FRACTION, "%", comp)
        if kind == "temperature":
            if int(spec["stage"]) != n:
                return INTERIOR_TEMPERATURE.format(n=n, s=int(spec["stage"]))
            return ("Temperature", value, "K", "")
    raise ValueError(f"unregistered {end} specification {kind} on a {case[end]} {end}")


def realization(case: dict[str, Any], level: str, method: str) -> dict[str, Any]:
    """DWSIM's realization of a case at a level under a method, or the reason it has none."""
    cond, reb = case["condenser"], case["reboiler"]
    specs = case["specifications"]
    r: dict[str, Any] = {"level": level, "method": method, "condenser_spec": None,
                         "reboiler_spec": None}
    reasons: list[str] = []
    if level == "L3":
        return {**r, "expressible": False, "reason": "L3 is not admissible for DWSIM (spec §2.2)"}
    if level == "L2":
        if not (cond == "partial" and specs["condenser"]["kind"] == "distillate_rate"):
            return {**r, "expressible": False, "reason": NO_L2A}
        r["condenser_type"] = "Partial_Condenser"
        r["vapor_flow_rate_mol_per_s"] = float(specs["condenser"]["value"])
        r["liquid_distillate"] = "fixed at 0 mol/s by the condenser specification (L2 a)"
        r["condenser_spec"] = ("Product_Molar_Flow_Rate", 0.0, "mol/s", "")
    elif cond in ("partial", "total"):
        if cond == "partial":
            r["condenser_type"] = "Full_Reflux"
            r["liquid_distillate"] = "none: DWSIM's Full_Reflux condenser has no liquid product"
        else:
            r["condenser_type"] = "Total_Condenser"
        native = end_option(case, "condenser", method)
        if isinstance(native, str):
            reasons.append(f"condenser: {native}")
        else:
            r["condenser_spec"] = native
    else:
        r["reboiled_absorber"] = True
    if reb == "partial":
        native = end_option(case, "reboiler", method)
        if isinstance(native, str):
            reasons.append(f"reboiler: {native}")
        else:
            r["reboiler_spec"] = native
    else:
        r["refluxed_absorber"] = True
    if reasons:  # every end's reason is recorded, not only the first
        return {**r, "expressible": False, "reason": " || ".join(reasons)}
    r["expressible"] = True
    return r


class Model:
    """One DWSIM flowsheet holding one column, built from a case and a realization."""

    def __init__(self, automation: Any, case: dict[str, Any], real: dict[str, Any]) -> None:
        from DWSIM.UnitOperations.UnitOperations import Column

        self.case = case
        self.real = real
        variant = case["tool_variant"]["DWSIM"]
        self.mapped_latent = not variant.startswith("dH_vap_J_per_mol_PC-L")
        self.sh = t06d.Sheet(automation, mapped_latent=self.mapped_latent)
        n = int(case["stage_count"])
        col = self.sh.add("DistillationColumn", "COL")
        if real.get("reboiled_absorber"):
            col.ReboiledAbsorber = True
        if real.get("refluxed_absorber"):
            col.RefluxedAbsorber = True
        col.SetNumberOfStages(n)
        self.col = col
        self.inlets: list[str] = []
        for k, inlet in enumerate(case["inlets"]):
            tag = f"IN{k + 1}-{inlet['port']}"
            flows = dict(zip(fx.COMPONENTS, map(float, inlet["n_mol_per_s"]), strict=True))
            ms = self.sh.feed_from(tag, {"flows": flows, "T": float(inlet["T_K"]),
                                         "P": float(inlet["P_Pa"])})
            col.ConnectFeed(ms, int(inlet["stage"]) - 1)
            self.inlets.append(tag)
        self.products = ["TOP", "BOTTOM"]
        top = self.sh.product("TOP")
        if "condenser_type" in real:
            col.CondenserType = getattr(Column.condtype, real["condenser_type"])
            if real["condenser_type"] == "Total_Condenser":
                col.ConnectDistillate(top)
                col.TotalCondenserSubcoolingDeltaT = 0.0
            else:
                col.ConnectVaporProduct(top)
            if real["condenser_type"] == "Partial_Condenser":
                col.ConnectDistillate(self.sh.product("LIQ-DIST"))
                self.products.append("LIQ-DIST")
                col.VaporFlowRateUnit = "mol/s"
                col.VaporFlowRate = real["vapor_flow_rate_mol_per_s"]
            col.ConnectCondenserDuty(self.sh.energy_stream("Q-COND"))
        else:
            col.ConnectVaporProduct(top)
        col.ConnectBottoms(self.sh.product("BOTTOM"))
        if case["reboiler"] != "none":
            col.ConnectReboilerDuty(self.sh.energy_stream("Q-REB"))
        if real["condenser_spec"] is not None:
            col.SetCondenserSpec(*real["condenser_spec"])
        if real["reboiler_spec"] is not None:
            col.SetReboilerSpec(*real["reboiler_spec"])
        pressures = [float(p) for p in case["stage_pressures_Pa"]]
        for st, p in zip(col.Stages, pressures, strict=True):
            st.P = p
            st.Efficiency = 1.0
        col.CondenserDeltaP = 0.0

    def set_solver(self, method_name: str, tol: float, max_iterations: int) -> None:
        self.col.SolvingMethodName = method_name
        self.col.ExternalLoopTolerance = tol
        self.col.InternalLoopTolerance = tol
        self.col.MaxIterations = max_iterations

    def inspection(self) -> dict[str, Any]:
        """§2.4's answers, read from the built model before it is solved."""
        col, case, real = self.col, self.case, self.real
        names = [str(s.Name) for s in col.Stages]
        n = int(case["stage_count"])
        streams = {str(si.StreamID): si for si in col.MaterialStreams.Values}
        feed_stages = []
        for tag, inlet in zip(self.inlets, case["inlets"], strict=True):
            si = streams[self.sh.streams[tag].Name]
            feed_stages.append({
                "inlet": tag, "registered_stage": int(inlet["stage"]),
                "dwsim_associated_stage": str(si.AssociatedStage),
                "dwsim_stage_index_0_based": names.index(str(si.AssociatedStage)),
                "declared_phase": inlet["phase"], "enters_whole": True,
            })
        specs = {}
        for key in ("C", "R"):
            if col.Specs.ContainsKey(key):
                s = col.Specs[key]
                specs[key] = {"SType": str(s.SType), "SpecValue": float(s.SpecValue),
                              "SpecUnit": str(s.SpecUnit), "ComponentID": str(s.ComponentID)}
        return {
            "property_package": {
                "package": "Raoult's Law", "compounds": [probe.compound_name(c) for c in self.sh.compounds],
                "t06_definitions": "t06_qualify_dwsim.Sheet (user compounds, Raoult's Law)",
                "vaporization_enthalpy_mapped": self.mapped_latent,
                "applies_to": "the whole column: one property package per DWSIM flowsheet",
            },
            "stage_map": {
                "stage_count_registered": n, "stage_count_dwsim": len(names),
                "index_base": "DWSIM Stages list, 0-based: our j is index j - 1",
                "map": {str(j + 1): {"dwsim_index": j, "dwsim_name": names[j]}
                        for j in range(len(names))},
            },
            "feed_stages": feed_stages,
            "condenser_realization": self._condenser_text(),
            "reboiler_realization": (
                "kettle: DWSIM's reboiler stage (last stage), liquid bottoms and vapour boil-up"
                if case["reboiler"] != "none" else
                "absent: DWSIM RefluxedAbsorber, the last stage is an ordinary stage fed by the "
                "bottom inlet"),
            "specifications": {
                "registered": case["specifications"], "dwsim": specs,
                "realization": {k: real.get(k) for k in (
                    "condenser_type", "vapor_flow_rate_mol_per_s", "liquid_distillate",
                    "condenser_spec", "reboiler_spec") if k in real},
            },
            "pressures": {
                "stage_P_Pa": [float(s.P) for s in col.Stages],
                "CondenserDeltaP": float(col.CondenserDeltaP),
                "ColumnPressureDrop": fx.finite(float(col.ColumnPressureDrop)),
                "pressure_drop_relation": "none: every stage pressure is set directly",
            },
            "intermediate_stages": {
                "efficiency": [float(s.Efficiency) for s in col.Stages],
                "duty_input_kW": [float(s.Q.Value or 0.0) for s in col.Stages],
                "side_draws": [str(si.StreamBehavior) for si in col.MaterialStreams.Values
                               if str(si.StreamBehavior) == "Sidedraw"],
                "hydraulics": "none: DWSIM's equilibrium-stage MESH model",
            },
            "initialization": {
                "InitialEstimatesProvider": str(col.InitialEstimatesProvider),
                "UseTemperatureEstimates": bool(col.UseTemperatureEstimates),
                "UseVaporFlowEstimates": bool(col.UseVaporFlowEstimates),
                "UseLiquidFlowEstimates": bool(col.UseLiquidFlowEstimates),
                "UseCompositionEstimates": bool(col.UseCompositionEstimates),
                "note": "DWSIM's own estimator; no value of this project is entered",
            },
        }

    def _condenser_text(self) -> str:
        t = self.real.get("condenser_type")
        if t == "Full_Reflux":
            return ("partial (S02): DWSIM Full_Reflux, vapour distillate from stage 1, all its "
                    "liquid refluxed")
        if t == "Partial_Condenser":
            return ("partial (S02) at L2(a): DWSIM Partial_Condenser, vapour product rate set, "
                    "liquid distillate fixed at 0")
        if t == "Total_Condenser":
            return "total: DWSIM Total_Condenser, subcooling 0 K (saturated liquid)"
        return "absent: DWSIM ReboiledAbsorber, stage 1 is an ordinary stage fed by the top inlet"


# ---- one run and its rule values --------------------------------------------------------------


def run_model(automation: Any, model: Model) -> dict[str, Any]:
    col, sh = model.col, model.sh
    rec: dict[str, Any] = {}
    t0 = time.perf_counter()
    errors = automation.CalculateFlowsheet4(sh.fs)
    rec["wall_time_s"] = time.perf_counter() - t0
    messages = [str(e.Message) for e in errors] if errors is not None else []
    calculated = {str(o.GraphicObject.Tag): bool(o.Calculated)
                  for o in sh.fs.SimulationObjects.Values}
    rec["solver_errors"] = messages
    rec["column_error_message"] = str(col.ErrorMessage or "")
    rec["calculated"] = calculated
    rec["converged"] = bool(not messages and all(calculated.values()) and col.Calculated
                            and not rec["column_error_message"])
    rec["termination"] = ("calculated, no error reported" if rec["converged"] else
                          (messages[0] if messages else rec["column_error_message"] or
                           "an object was not calculated"))
    if not rec["converged"]:
        return rec

    def arr(a: Any) -> list[float]:
        return [float(v) for v in a]

    rec["profile"] = {
        "T_K": arr(col.Tf), "L_mol_per_s": arr(col.Lf), "V_mol_per_s": arr(col.Vf),
        "LSS_mol_per_s": arr(col.LSSf), "VSS_mol_per_s": arr(col.VSSf),
        "x": [arr(v) for v in col.xf], "y": [arr(v) for v in col.yf],
        "P_Pa": [float(s.P) for s in col.Stages],
        "stage_duty_input_kW": [float(s.Q.Value or 0.0) for s in col.Stages],
        "internal_iterations": int(col.ic), "external_iterations": int(col.ec),
    }
    rec["streams"] = {t: t06d.stream_record(ms) for t, ms in sh.streams.items()}
    rec["energy_streams_kW"] = {t: probe.nullable(es.EnergyFlow) for t, es in sh.energy.items()}
    rec["column_reported"] = {
        "CondenserDuty_kW": float(col.CondenserDuty), "ReboilerDuty_kW": float(col.ReboilerDuty),
        "RefluxRatio": float(col.RefluxRatio),
        "specs_calculated": {k: fx.finite(float(col.Specs[k].CalculatedValue))
                             for k in ("C", "R") if col.Specs.ContainsKey(k)},
    }
    return rec


def duties_w(model: Model, rec: dict[str, Any]) -> dict[str, float]:
    """Q > 0 into the stage (ADR 0001 D4.1) from DWSIM's energy streams (kW).

    DWSIM's condenser energy stream is a product of the column (heat removed, reported positive);
    its reboiler energy stream is a feed (heat supplied, reported positive). So Q_condenser =
    -1000 E(Q-COND) and Q_reboiler = +1000 E(Q-REB). Rule 2's energy balance checks the signs.
    """
    e = rec["energy_streams_kW"]
    out = {}
    if "Q-COND" in e:
        out["Q_condenser"] = -1000.0 * float(e["Q-COND"] or 0.0)
    if "Q-REB" in e:
        out["Q_reboiler"] = 1000.0 * float(e["Q-REB"] or 0.0)
    return out


def quantities(model: Model, rec: dict[str, Any]) -> dict[str, float]:
    """The registered quantities of the case, in our stage numbering, from DWSIM's own record."""
    prof, streams = rec["profile"], rec["streams"]
    q = duties_w(model, rec)
    out: dict[str, float] = {}
    for name, _kind in model.case["quantities"]:
        if name.startswith(("T[", "L[", "V[")):
            j = int(name[2:-1])
            key = {"T": "T_K", "L": "L_mol_per_s", "V": "V_mol_per_s"}[name[0]]
            out[name] = prof[key][j - 1]
        elif name == "reflux":
            out[name] = prof["L_mol_per_s"][0]
        elif name.startswith("top["):
            out[name] = streams["TOP"]["overall_mol_per_s"][name[4:-1]]
        elif name.startswith("bottom["):
            out[name] = streams["BOTTOM"]["overall_mol_per_s"][name[7:-1]]
        elif name in q:
            out[name] = q[name]
        else:
            raise KeyError(f"no DWSIM value for registered quantity {name}")
    return out


def spec_values(model: Model, rec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """§5.1 row 9 with §17.4, from DWSIM's own flows, duties and temperatures, against the
    registered value; rule 2c at 1e-4 relative for every kind, rule 2d at the kind's threshold."""
    case, prof, streams = model.case, rec["profile"], rec["streams"]
    n = int(case["stage_count"])
    top = streams["TOP"]
    out = {}
    for end, spec in case["specifications"].items():
        kind, reg = spec["kind"], float(spec["value"])
        if kind == "reflux_ratio":
            if case["condenser"] == "total":
                got = prof["L_mol_per_s"][0] / top["molar_flow_mol_per_s"]
                definition = "reflux L(0) / distillate D"
            else:
                got = prof["L_mol_per_s"][0] / prof["V_mol_per_s"][0]
                definition = "L[1] / V[1]"
        elif kind == "boilup_ratio":
            got = prof["V_mol_per_s"][n - 1] / prof["L_mol_per_s"][n - 1]
            definition = "V[N] / L[N]"
        elif kind == "distillate_rate":
            got = top["molar_flow_mol_per_s"]
            definition = "vapour distillate V_1 (TOP stream)" if case["condenser"] == "partial" \
                else "distillate D (TOP stream)"
        elif kind == "bottoms_rate":
            got = streams["BOTTOM"]["molar_flow_mol_per_s"]
            definition = "bottoms L_N (BOTTOM stream)"
        elif kind == "duty":
            got = duties_w(model, rec)["Q_reboiler"]
            definition = "reboiler duty, W, into the stage"
        elif kind == "purity":
            got = top["overall_mol_per_s"][spec["component"]] / top["molar_flow_mol_per_s"]
            definition = f"mole fraction of {spec['component']} in the vapour distillate"
        elif kind == "recovery":
            c = spec["component"]
            product = "TOP" if end == "condenser" else "BOTTOM"
            fed = sum(streams[t]["overall_mol_per_s"][c] for t in model.inlets)
            got = streams[product]["overall_mol_per_s"][c] / fed
            definition = (f"{product} stream flow of {c} over the inlets' total flow of {c} "
                          "(n_c / F_c)")
        elif kind == "temperature":
            stage = int(spec["stage"])
            got = prof["T_K"][stage - 1]
            definition = f"T of our stage {stage} (DWSIM stage index {stage - 1})"
        else:
            raise ValueError(kind)
        absolute = got - reg
        relative = absolute / abs(reg)
        basis, threshold = RULE2D_SPEC[kind]
        accuracy = abs(absolute) if basis == "absolute" else abs(relative)
        out[end] = {
            "kind": kind, "definition": definition, "registered": reg, "dwsim": got,
            "relative_difference": relative, "absolute_difference": absolute,
            "rule2c_passes": bool(math.isfinite(relative)
                                  and abs(relative) <= RULE2C_SPEC_RELATIVE),
            "rule2d_basis": basis, "rule2d_threshold": threshold, "rule2d_measure": accuracy,
            "rule2d_passes": bool(math.isfinite(accuracy) and accuracy <= threshold),
        }
    return out


def rule_values(model: Model, rec: dict[str, Any]) -> dict[str, Any]:
    """Rules 2, 2c and 2d's specification residual (§7.1), from DWSIM's own record only."""
    case, streams, prof = model.case, rec["streams"], rec["profile"]
    n = int(case["stage_count"])
    rule2 = fx.component_balance([streams[t]["overall_mol_per_s"] for t in model.inlets],
                                 [streams[t]["overall_mol_per_s"] for t in model.products])

    def mh(tag: str) -> float:
        s = streams[tag]
        return float(s["mass_flow_kg_per_s"]) * float(s["mass_enthalpy_kJ_per_kg"]) * 1000.0

    q = duties_w(model, rec)
    energy = (sum(mh(t) for t in model.inlets) + sum(q.values())
              - sum(mh(t) for t in model.products))
    r2 = {
        "converged": rec["converged"],
        "component_balance": rule2,
        "energy_balance_W": energy,
        "energy_terms": {"inlets_W": {t: mh(t) for t in model.inlets},
                         "products_W": {t: mh(t) for t in model.products}, "duties_W": q},
        "passes": bool(rec["converged"] and rule2["passes"] and math.isfinite(energy)
                       and abs(energy) <= RULE2_ENERGY_W),
    }
    names = [str(s.Name) for s in model.col.Stages]
    feed_ok = []
    for tag, inlet in zip(model.inlets, case["inlets"], strict=True):
        si = {str(s.StreamID): s for s in model.col.MaterialStreams.Values}[
            model.sh.streams[tag].Name]
        feed_ok.append(str(si.AssociatedStage) == names[int(inlet["stage"]) - 1])
    reg_p = [float(p) for p in case["stage_pressures_Pa"]]
    p_dev = max([abs(p - r) for p, r in zip(prof["P_Pa"], reg_p, strict=True)]
                + [abs(streams[t]["P_Pa"] - reg_p[0 if t != "BOTTOM" else n - 1])
                   for t in model.products])
    ends = set()
    if case["condenser"] != "none":
        ends.add(0)
    if case["reboiler"] != "none":
        ends.add(n - 1)
    inter = [abs(1000.0 * d) for i, d in enumerate(prof["stage_duty_input_kW"]) if i not in ends]
    inter_max = max(inter) if inter else 0.0
    checks: dict[str, Any] = {
        "stage_count": {"value": len(names), "registered": n, "passes": len(names) == n},
        "feed_stage": {"value": feed_ok, "passes": all(feed_ok)},
        "pressure_max_abs_dev_Pa": {"value": p_dev, "passes": p_dev <= RULE2C_PRESSURE_PA},
        "intermediate_duty_max_abs_W": {"value": inter_max,
                                        "passes": inter_max <= RULE2C_INTERMEDIATE_DUTY_W},
    }
    if case["condenser"] == "partial":
        liq = prof["LSS_mol_per_s"][0]
        if "LIQ-DIST" in streams:
            liq = max(abs(liq), abs(streams["LIQ-DIST"]["molar_flow_mol_per_s"]))
        checks["zero_liquid_distillate_mol_per_s"] = {
            "value": liq, "passes": abs(liq) <= RULE2C_ZERO_DISTILLATE_MOL_PER_S}
    specs = spec_values(model, rec)
    checks["specification"] = {"value": specs,
                               "passes": all(s["rule2c_passes"] for s in specs.values())}
    r2c = {"checks": checks, "passes": all(c["passes"] for c in checks.values())}
    r2d_spec = {"passes": all(s["rule2d_passes"] for s in specs.values()),
                "max_measure": max(s["rule2d_measure"] for s in specs.values())}
    return {"rule2": r2, "rule2c": r2c, "rule2d_specification": r2d_spec}


def rerun_movement(case: dict[str, Any], base: dict[str, float],
                   rerun: dict[str, float]) -> dict[str, Any]:
    kinds = dict(case["quantities"])
    ratios = {k: abs(rerun[k] - base[k]) / quantity_tolerance(kinds[k], base[k]) for k in base}
    worst = max(ratios, key=lambda k: ratios[k])
    return {"ratio_to_tolerance": ratios, "max_ratio": ratios[worst], "max_quantity": worst,
            "tolerance_value_used": "the tool's own value (the script reads no other)",
            "passes": bool(math.isfinite(ratios[worst])
                           and ratios[worst] <= RULE2D_RERUN_FRACTION)}


def attempt(automation: Any, cid: str, case: dict[str, Any], real: dict[str, Any], tol: float,
            method: str, max_it: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """One (level, rung) attempt with its accuracy rerun; returns (summary, full record or None)."""
    summary: dict[str, Any] = {"level": real["level"], "tolerance": tol, "method": method,
                               "dwsim_method_name": DWSIM_METHOD_NAME[method]}
    full: dict[str, Any] | None = None
    try:
        model = Model(automation, case, real)
        model.set_solver(DWSIM_METHOD_NAME[method], tol, max_it)
        rec = run_model(automation, model)
        summary.update(converged=rec["converged"], termination=rec["termination"],
                       wall_time_s=rec["wall_time_s"])
        if not rec["converged"]:
            summary.update(passes=False, failed_rule="2", reason=rec["termination"])
            return summary, None
        rules = rule_values(model, rec)
        qs = quantities(model, rec)
        summary["rule2_component_max_mol_per_s"] = rules["rule2"]["component_balance"][
            "max_abs_mol_per_s"]
        summary["rule2_energy_W"] = rules["rule2"]["energy_balance_W"]
        summary["rule2c_failed_checks"] = [k for k, c in rules["rule2c"]["checks"].items()
                                           if not c["passes"]]
        summary["rule2d_specification_max"] = rules["rule2d_specification"]["max_measure"]
        full = {"record": rec, "rules": rules, "quantities": qs}
        if not rules["rule2"]["passes"]:
            summary.update(passes=False, failed_rule="2", reason="tool-internal balance")
            return summary, full
        if not rules["rule2c"]["passes"]:
            summary.update(passes=False, failed_rule="2c",
                           reason=f"semantics: {summary['rule2c_failed_checks']}")
            return summary, full
        if not rules["rule2d_specification"]["passes"]:
            summary.update(passes=False, failed_rule="2d", reason="specification residual")
            return summary, full
        rerun_tol = tol * 10.0
        model2 = Model(automation, case, real)
        model2.set_solver(DWSIM_METHOD_NAME[method], rerun_tol, max_it)
        rec2 = run_model(automation, model2)
        rerun: dict[str, Any] = {"tolerance": rerun_tol, "converged": rec2["converged"],
                                 "termination": rec2["termination"],
                                 "wall_time_s": rec2["wall_time_s"]}
        if rec2["converged"]:
            q2 = quantities(model2, rec2)
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
                       traceback=traceback.format_exc(limit=4))
        return summary, full


# ---- qualification and selection (§2.3, §5.2) -------------------------------------------------


def stage_number_readers(automation: Any) -> dict[str, Any]:
    """Every method of the loaded DWSIM assemblies whose IL calls a ColumnSpec.StageNumber accessor.

    Q-X6 for an interior-stage temperature specification (spec §17.12 Q-A1-1): whether any DWSIM
    code could read a stage for a column specification. Each call/callvirt operand is resolved
    against its own module; a match is a method of ColumnSpec named *StageNumber*.
    """
    import System
    from System.Reflection import BindingFlags

    sh = t06d.Sheet(automation, mapped_latent=True)
    spec_type = sh.add("DistillationColumn", "COL-SCAN").Specs["R"].GetType()
    flags = (BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance
             | BindingFlags.Static | BindingFlags.DeclaredOnly)
    callers: set[tuple[str, str, str, str]] = set()
    n_methods, assemblies = 0, []
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        name = str(asm.GetName().Name)
        if "DWSIM" not in name:
            continue
        assemblies.append(name)
        try:
            types = list(asm.GetTypes())
        except Exception as exc:  # ReflectionTypeLoadException: keep the types that loaded
            types = [t for t in getattr(exc, "Types", []) if t is not None]
        for t in types:
            try:
                members = list(t.GetMethods(flags)) + list(t.GetConstructors(flags))
            except Exception:
                continue
            for m in members:
                try:
                    body = m.GetMethodBody()
                except Exception:
                    continue
                if body is None:
                    continue
                il = bytes(body.GetILAsByteArray())
                n_methods += 1
                for i in range(len(il) - 4):
                    if il[i] not in (0x28, 0x6F):  # call, callvirt
                        continue
                    token = int.from_bytes(il[i + 1:i + 5], "little")
                    if token >> 24 not in (0x06, 0x0A, 0x2B):  # MethodDef, MemberRef, MethodSpec
                        continue
                    try:
                        target = m.Module.ResolveMethod(token)
                    except Exception:
                        continue
                    if (target is not None and target.DeclaringType is not None
                            and str(target.DeclaringType.FullName) == str(spec_type.FullName)
                            and "StageNumber" in str(target.Name)):
                        callers.add((name, str(t.FullName), str(m.Name), str(target.Name)))
    return {"column_spec_type": str(spec_type.FullName), "assemblies": sorted(assemblies),
            "methods_scanned": n_methods,
            "callers": [{"assembly": a, "type": t, "method": m, "accessor": acc}
                        for a, t, m, acc in sorted(callers)]}


def qualify(automation: Any, data: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    """§17.2's order for every case; positions run rung-major across cases (B3-6, compute only)."""
    dw = data["tool_settings"]["DWSIM"]
    max_it = int(dw["column_max_iterations"])
    cases = data["cases"]
    rungs = ladder(dw)
    methods = list(dict.fromkeys(m for _, m in rungs))
    per: dict[str, dict[str, Any]] = {cid: {"levels": {}, "attempts": [], "passing": []}
                                      for cid in ids}
    full_records: dict[tuple[str, str, float, str], dict[str, Any]] = {}
    for li, level in enumerate(("L1", "L2")):
        for cid in ids:
            by_method: dict[str, Any] = {}
            for method in methods:
                if level == "L2" and per[cid]["levels"]["L1"]["by_method"][method][
                        "realization"]["expressible"]:
                    continue  # §17.2: L2(a) only under a method where L1 is inexpressible
                real = realization(cases[cid], level, method)
                entry: dict[str, Any] = {"realization": real}
                if real["expressible"]:
                    try:
                        entry["structural_inspection"] = Model(automation, cases[cid],
                                                               real).inspection()
                    except Exception as exc:
                        real = {**real, "expressible": False,
                                "reason": f"model not built: {type(exc).__name__}: {exc}"}
                        entry["realization"] = real
                by_method[method] = entry
            per[cid]["levels"][level] = {"by_method": by_method}
        for k, (tol, method) in enumerate(rungs):
            for cid in ids:
                entry = per[cid]["levels"][level]["by_method"].get(method)
                if entry is None:
                    continue  # not a position of §17.2's order for this case
                real = entry["realization"]
                if not real["expressible"]:
                    summ: dict[str, Any] = {
                        "level": level, "tolerance": tol, "method": method,
                        "dwsim_method_name": DWSIM_METHOD_NAME[method],
                        "structurally_expressible": False, "converged": None,
                        "passes": False, "failed_rule": "structural", "reason": real["reason"]}
                    full = None
                else:
                    summ, full = attempt(automation, cid, cases[cid], real, tol, method, max_it)
                    summ["structurally_expressible"] = True
                summ["rung_index"] = k
                per[cid]["attempts"].append(summ)
                if summ["passes"]:
                    per[cid]["passing"].append((li, k))
                    full_records[(cid, level, tol, method)] = full
                print(f"dwsim {cid} {level} rung {k} ({tol:g}, {method}): "
                      f"{'PASS' if summ['passes'] else 'fail ' + str(summ.get('failed_rule'))}",
                      file=sys.stderr, flush=True)
    for cid in ids:
        per[cid]["levels"]["L3"] = {"realization": realization(cases[cid], "L3", "")}
    # §5.2 selection: a rung under which every case passes (at its level) is the uniform setting;
    # otherwise each case takes the first passing position of §17.2's order (L1 before L2).
    uniform = next((k for k in range(len(rungs))
                    if all(any(p[1] == k for p in per[cid]["passing"]) for cid in ids)), None)
    selection: dict[str, Any] = {"uniform_rung_index": uniform, "per_case": {},
                                 "ladder": "column_method_order_amendment_1"}
    for cid in ids:
        passing = sorted(per[cid]["passing"])
        if not passing:
            selection["per_case"][cid] = None
            continue
        li = passing[0][0]
        k = uniform if uniform is not None else passing[0][1]
        tol, method = rungs[k]
        selection["per_case"][cid] = {"level": ("L1", "L2")[li], "rung_index": k,
                                      "tolerance": tol, "method": method,
                                      "uniform": uniform is not None}
    return {"per_case": per, "selection": selection, "full_records": full_records}


def not_available_reason(per: dict[str, Any]) -> str:
    parts = []
    for level, entry in per["levels"].items():
        if "by_method" not in entry:
            parts.append(f"{level}: {entry['realization']['reason']}")
            continue
        for method, sub in entry["by_method"].items():
            real = sub["realization"]
            if not real["expressible"]:
                parts.append(f"{level} {method}: structurally inexpressible: {real['reason']}")
            else:
                fails = sorted({f"{a['failed_rule']}: {a['reason']}" for a in per["attempts"]
                                if a["level"] == level and a["method"] == method})
                parts.append(f"{level} {method}: no tolerance passed rules 2-2d "
                             f"({'; '.join(fails)})")
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--only", nargs="*", help="case ids (default: all)")
    args = parser.parse_args()
    out_dir = args.out.resolve()  # absolute: dwsim_runtime.start changes the working directory
    (out_dir / "qualification").mkdir(parents=True, exist_ok=True)
    (out_dir / "results").mkdir(parents=True, exist_ok=True)
    data = load_cases()
    ids = args.only or list(data["cases"])
    env_dir = ENV_DIR.resolve()
    fingerprint = fx.fingerprint("dwsim", env_dir)
    t0 = time.perf_counter()
    automation = dwsim_runtime.start(env_dir)
    import System

    common = {
        "tool": "DWSIM",
        "versions": {
            "dwsim": str(automation.GetVersion()),
            "pythonnet": importlib.metadata.version("pythonnet"),
            "dotnet_runtime": str(System.Environment.Version),
            "python": sys.version.split()[0],
        },
        "environment_fingerprint": fingerprint,
        "input_file": "docs/derivations/scripts/s03_cases.json",
        "settings": {
            "registered": data["tool_settings"]["DWSIM"],
            "flash_settings_applied": fx.DWSIM_FLASH_SETTINGS,
            "property_package_options_applied": fx.DWSIM_PP_OPTIONS,
            "method_names_dwsim": DWSIM_METHOD_NAME,
            "ladder": "column_method_order_amendment_1 (spec §17.2)",
            "recovery_percent_conversion": "DWSIM Component_Recovery value = 100 x the registered "
                                           "recovery fraction (spec §17.4)",
            "column_other": "DWSIM defaults (SolverScheme, Broyden acceleration, internal "
                            "initial estimates); stage efficiency 1; CondenserDeltaP 0",
        },
        "sign_conversion": SIGN_CONVERSION,
    }
    if any(spec["kind"] == "temperature" for cid in ids
           for spec in data["cases"][cid]["specifications"].values()):
        common["settings"]["stage_number_readers"] = stage_number_readers(automation)
    q = qualify(automation, data, ids)
    qual = {**common, "wall_time_total_s": time.perf_counter() - t0,
            "selection": q["selection"], "cases": {}}
    status = 0
    for cid in ids:
        per = q["per_case"][cid]
        sel = q["selection"]["per_case"][cid]
        qual["cases"][cid] = {"available": sel is not None, "level": sel and sel["level"],
                              "ladder": "column_method_order_amendment_1",
                              "levels": per["levels"], "attempts": per["attempts"]}
        rec: dict[str, Any] = {**common, "case": cid, "case_definition": data["cases"][cid],
                               "attempts": per["attempts"]}
        if sel is None:
            reason = not_available_reason(per)
            qual["cases"][cid]["not_available_reason"] = reason
            rec.update(available=False, level=None, not_available_reason=reason,
                       structural_inspection={
                           level: {m: sub.get("structural_inspection")
                                   for m, sub in entry.get("by_method", {}).items()}
                           for level, entry in per["levels"].items()})
            status = 1
        else:
            chosen = per["levels"][sel["level"]]["by_method"][sel["method"]]
            real = chosen["realization"]
            full = q["full_records"][(cid, sel["level"], sel["tolerance"], sel["method"])]
            insp = chosen["structural_inspection"]
            rec.update(
                available=True, level=sel["level"], realization=real,
                settings_used={"column_tolerance": sel["tolerance"], "method": sel["method"],
                               "dwsim_method_name": DWSIM_METHOD_NAME[sel["method"]],
                               "rung_index": sel["rung_index"], "uniform": sel["uniform"],
                               "max_iterations": int(data["tool_settings"]["DWSIM"][
                                   "column_max_iterations"])},
                stage_map=insp["stage_map"], feed_stages=insp["feed_stages"],
                condenser_realization=insp["condenser_realization"],
                reboiler_realization=insp["reboiler_realization"],
                specifications=insp["specifications"], structural_inspection=insp,
                converged=full["record"]["converged"], termination=full["record"]["termination"],
                raw_output=full["record"], rule_values=full["rules"],
                registered_quantities=full["quantities"],
                accuracy_rerun=full["rerun"],
            )
        path = out_dir / "results" / f"dwsim-{cid}.json"
        path.write_text(json.dumps(fx.finite(rec), indent=1) + "\n", encoding="utf-8")
        print(f"dwsim {cid}: available={sel is not None} level={sel and sel['level']} "
              f"rung={sel and (sel['tolerance'], sel['method'])}", flush=True)
    path = out_dir / "qualification" / "dwsim.json"
    path.write_text(json.dumps(fx.finite(qual), indent=1) + "\n", encoding="utf-8")
    n_ok = sum(1 for cid in ids if q["selection"]["per_case"][cid] is not None)
    print(f"dwsim SUMMARY: {n_ok}/{len(ids)} cases available; uniform rung "
          f"{q['selection']['uniform_rung_index']}; fingerprint matches "
          f"{fingerprint['matches']}", flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
