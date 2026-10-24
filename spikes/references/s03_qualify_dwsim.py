"""S03 WO-S03-3: blind qualification and runs of the column cases in DWSIM 9.0.5.

Authority: `docs/derivations/S03-spec.md` §2.2 (levels), §2.3 (the pre-registered "where available"
rule), §2.4 (structural questions), §5.1 (matched semantics), §5.2 (the column-solver ladder), §6
(thresholds) and §7.1 rules 2, 2c and 2d (computed here from DWSIM's own record only).

For every case of `s03_cases.json` (RC1-RC5, the ten perturbed cases, PC-P and PC-L) this script
builds DWSIM's own rigorous `DistillationColumn` on SYN-001 (T06's user compounds and Raoult's Law
package, imported from `t06_qualify_dwsim`, i.e. `docs/reference-environments.md` §5.0), records a
structural inspection of the built model before it is solved, and runs it under every rung of §5.2's
ladder (tolerance-major, then method). A run that passes rules 2-2c and 2d's specification residual
is rerun at ten times the column tolerance (§5.1 row 15) for 2d's movement check. Every attempt is
recorded. The selection follows §5.2: the first rung that passes for every case is the uniform
setting; otherwise each case takes its own first passing rung (§2.3 step 1 for the levels).

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
RULE2C_SPEC_RELATIVE = 1e-4
RULE2D_SPEC_RELATIVE = 1e-8  # purity: 1e-8 absolute on the mole fraction
RULE2D_RERUN_FRACTION = 0.1

# §5.2's methods, by the label `s03_cases.json` uses, mapped to the name DWSIM's column dispatches on
# (`Column.SolvingMethodName`). DWSIM's own dispatcher decides whether a name is available; a name it
# does not know ends the run with its error "Unable to find column solver with name ...", recorded.
DWSIM_METHOD_NAME = {
    "Napthali-Sandholm": "Napthali-Sandholm (Simultaneous Correction)",
    "Russell inside-out": "Russell (Inside-Out)",
    "Wang-Henke": "Wang-Henke (Bubble Point)",
    "Burningham-Otto": "Burningham-Otto (Sum Rates)",
}
# §5.2 method 3: sum rates for RC3, RC4 and their perturbations; bubble point for every other case.
SUM_RATES_BASES = ("RC3", "RC4")

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


def ladder(case_id: str, dw: dict[str, Any]) -> list[tuple[float, str]]:
    """§5.2's rungs for one case, tightest tolerance first, then the method order."""
    order = list(dw["column_method_order"])
    third = "Burningham-Otto" if case_id.split("-")[0] in SUM_RATES_BASES else "Wang-Henke"
    methods = [order[0], order[1], third]
    return [(float(t), m) for t in dw["column_tolerance_ladder"] for m in methods]


def quantity_tolerance(kind: str, value: float) -> float:
    """§6's tolerance with the tool's own value standing in for v (the script reads no other)."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


# ---- the model at each level (§2.2, §5.1) -----------------------------------------------------


def realization(case: dict[str, Any], level: str) -> dict[str, Any]:
    """DWSIM's realization of a case at a level, or the reason it has none (no tool is touched)."""
    cond, reb = case["condenser"], case["reboiler"]
    specs = case["specifications"]
    if level == "L3":
        return {"expressible": False, "reason": "L3 is not admissible for DWSIM (spec §2.2)"}
    r: dict[str, Any] = {"level": level, "condenser_spec": None, "reboiler_spec": None}
    if cond == "partial":
        kind = specs["condenser"]["kind"]
        value = float(specs["condenser"]["value"])
        if level == "L1":
            r["condenser_type"] = "Full_Reflux"
            r["liquid_distillate"] = "none: DWSIM's Full_Reflux condenser has no liquid product"
            if kind == "reflux_ratio":
                r["condenser_spec"] = ("Stream_Ratio", value, "", "")
            elif kind == "purity":
                comp = probe.compound_name(specs["condenser"]["component"])
                r["condenser_spec"] = ("Component_Fraction", value, COMPONENT_FRACTION_UNIT, comp)
            else:
                return {
                    "expressible": False,
                    "reason": (
                        f"condenser specification {kind}: DWSIM's native rate option on the "
                        "condenser (Product_Molar_Flow_Rate) is the liquid distillate LSS(0) "
                        "(RigorousColumn/NewtonRaphson/BubblePoint, v9.0.5), which a Full_Reflux "
                        "condenser holds at 0; S02's D is the vapour distillate V_1 (spec §5.1 "
                        "row 9). No native option of the Full_Reflux condenser is V_1"
                    ),
                }
        else:
            if kind != "distillate_rate":
                return {
                    "expressible": False,
                    "reason": (
                        f"L2(a) needs DWSIM's Partial_Condenser with its liquid distillate fixed at "
                        f"0; DWSIM fixes that rate only through the condenser specification slot, "
                        f"which the registered {kind} specification occupies"
                    ),
                }
            r["condenser_type"] = "Partial_Condenser"
            r["vapor_flow_rate_mol_per_s"] = value
            r["liquid_distillate"] = "fixed at 0 mol/s by the condenser specification (L2 a)"
            r["condenser_spec"] = ("Product_Molar_Flow_Rate", 0.0, "mol/s", "")
    elif cond == "total":
        if level != "L1":
            return {"expressible": False, "reason": "no L2(a) realization distinct from L1"}
        r["condenser_type"] = "Total_Condenser"
        r["condenser_spec"] = ("Stream_Ratio", float(specs["condenser"]["value"]), "", "")
        assert specs["condenser"]["kind"] == "reflux_ratio"
    else:
        if level != "L1":
            return {"expressible": False, "reason": "no L2(a) realization distinct from L1"}
        r["reboiled_absorber"] = True
    if reb == "partial":
        kind = specs["reboiler"]["kind"]
        value = float(specs["reboiler"]["value"])
        if kind == "boilup_ratio":
            r["reboiler_spec"] = ("Stream_Ratio", value, "", "")
        elif kind == "bottoms_rate":
            r["reboiler_spec"] = ("Product_Molar_Flow_Rate", value, "mol/s", "")
        elif kind == "duty":
            r["reboiler_spec"] = ("Heat_Duty", value / 1000.0, "kW", "")
        else:
            raise ValueError(kind)
    else:
        if level != "L1" and cond != "partial":
            return {"expressible": False, "reason": "no L2(a) realization distinct from L1"}
        r["refluxed_absorber"] = True
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
    """§5.1 row 9, computed from DWSIM's own flows (and duties) and set against the registered value."""
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
        else:
            raise ValueError(kind)
        absolute = got - reg
        relative = absolute / abs(reg)
        accuracy = abs(absolute) if kind == "purity" else abs(relative)
        out[end] = {
            "kind": kind, "definition": definition, "registered": reg, "dwsim": got,
            "relative_difference": relative, "absolute_difference": absolute,
            "rule2c_passes": bool(math.isfinite(relative) and abs(relative) <= RULE2C_SPEC_RELATIVE),
            "rule2d_measure": accuracy,
            "rule2d_passes": bool(math.isfinite(accuracy) and accuracy <= RULE2D_SPEC_RELATIVE),
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


def qualify(automation: Any, data: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    dw = data["tool_settings"]["DWSIM"]
    max_it = int(dw["column_max_iterations"])
    cases = data["cases"]
    per: dict[str, dict[str, Any]] = {cid: {"levels": {}, "attempts": [], "passing": []}
                                      for cid in ids}
    full_records: dict[tuple[str, str, float, str], dict[str, Any]] = {}
    for level in ("L1", "L2", "L3"):
        todo = [cid for cid in ids if not per[cid]["passing"]]
        for cid in todo:
            real = realization(cases[cid], level)
            entry: dict[str, Any] = {"realization": real}
            if real["expressible"]:
                try:
                    entry["structural_inspection"] = Model(automation, cases[cid],
                                                           real).inspection()
                except Exception as exc:
                    real = {**real, "expressible": False,
                            "reason": f"model not built: {type(exc).__name__}: {exc}"}
                    entry["realization"] = real
            per[cid]["levels"][level] = entry
        runnable = [cid for cid in todo if per[cid]["levels"][level]["realization"]["expressible"]]
        if not runnable:
            continue
        rungs = {cid: ladder(cid, dw) for cid in runnable}
        for k in range(len(rungs[runnable[0]])):  # rung-major: every case at rung k, then k + 1
            for cid in runnable:
                tol, method = rungs[cid][k]
                real = per[cid]["levels"][level]["realization"]
                summ, full = attempt(automation, cid, cases[cid], real, tol, method, max_it)
                summ["rung_index"] = k
                per[cid]["attempts"].append(summ)
                if summ["passes"]:
                    per[cid]["passing"].append((level, k))
                    full_records[(cid, level, tol, method)] = full
                print(f"dwsim {cid} {level} rung {k} ({tol:g}, {method}): "
                      f"{'PASS' if summ['passes'] else 'fail ' + str(summ.get('failed_rule'))}",
                      file=sys.stderr, flush=True)
    # §5.2 selection: a rung under which every case passes (at its level) is the uniform setting.
    n_rungs = len(ladder(ids[0], dw))
    uniform = next((k for k in range(n_rungs)
                    if all(any(p[1] == k for p in per[cid]["passing"]) for cid in ids)), None)
    selection: dict[str, Any] = {"uniform_rung_index": uniform, "per_case": {}}
    for cid in ids:
        passing = per[cid]["passing"]
        if not passing:
            selection["per_case"][cid] = None
            continue
        level = passing[0][0]
        k = uniform if uniform is not None else min(p[1] for p in passing if p[0] == level)
        tol, method = ladder(cid, dw)[k]
        selection["per_case"][cid] = {"level": level, "rung_index": k, "tolerance": tol,
                                      "method": method, "uniform": uniform is not None}
    return {"per_case": per, "selection": selection, "full_records": full_records}


def not_available_reason(per: dict[str, Any]) -> str:
    parts = []
    for level, entry in per["levels"].items():
        real = entry["realization"]
        if not real["expressible"]:
            parts.append(f"{level}: {real['reason']}")
        else:
            fails = sorted({f"{a['failed_rule']}: {a['reason']}" for a in per["attempts"]
                            if a["level"] == level})
            parts.append(f"{level}: no rung passed rules 2-2d ({'; '.join(fails)})")
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
            "column_other": "DWSIM defaults (SolverScheme, Broyden acceleration, internal "
                            "initial estimates); stage efficiency 1; CondenserDeltaP 0",
        },
        "sign_conversion": SIGN_CONVERSION,
    }
    q = qualify(automation, data, ids)
    qual = {**common, "wall_time_total_s": time.perf_counter() - t0,
            "selection": q["selection"], "cases": {}}
    status = 0
    for cid in ids:
        per = q["per_case"][cid]
        sel = q["selection"]["per_case"][cid]
        qual["cases"][cid] = {"available": sel is not None, "level": sel and sel["level"],
                              "levels": per["levels"], "attempts": per["attempts"]}
        rec: dict[str, Any] = {**common, "case": cid, "case_definition": data["cases"][cid],
                               "attempts": per["attempts"]}
        if sel is None:
            reason = not_available_reason(per)
            qual["cases"][cid]["not_available_reason"] = reason
            rec.update(available=False, level=None, not_available_reason=reason,
                       structural_inspection={k: v.get("structural_inspection")
                                              for k, v in per["levels"].items()})
            status = 1
        else:
            real = per["levels"][sel["level"]]["realization"]
            full = q["full_records"][(cid, sel["level"], sel["tolerance"], sel["method"])]
            insp = per["levels"][sel["level"]]["structural_inspection"]
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
