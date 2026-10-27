"""E01 WO-B4 (design §5.3, §9.5, §9.6): the package against track B's independent cost
expectations, `benchmarks/e01/cost_hand/cost_hand.yaml` (written by `cost_hand.py`, which imports
nothing from `openflowsheet` and transcribes SSLW.py itself).

- A14: every SSLW form at its registered sizes (S_min, geometric mean, S_max), floor bounds and
  the points 1e-6 inside them, and at P1's (TH-C1, TH-R1) and P3's (M1) sizes: rel ≤ 1e-10;
- A10: the exchanger hand case; A11: TH-R1's flash drum; A12: M1's column shell (every D_j², j*,
  D and H), the last two from `recorded_states.yaml`;
- the chain (escalation, `ebtf-prisma-v1`, CRF, tac) on P1's report fixture.

The recorded states are the solved states' inputs to A11/A12 (stage flows, T, P; the provider's
saturated volumes for TH-R1's water). Regenerate with
`python tests/test_e01_b_cost_hand.py --write-states`; a test re-solves and compares (rel 1e-9,
the platform last bits of a solved state, as tests/test_e01_a_report.py).
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s11_column_support import column_registered  # noqa: E402
from s11_column_support import committed_case as column_case  # noqa: E402
from s11_thermal_support import committed_case, solve  # noqa: E402
from test_s11_thermal_binding import register  # noqa: E402

from openflowsheet.application.policies import T06_REVISION_V2  # noqa: E402
from openflowsheet.application.revision_binding import bind_revision_flowsheet  # noqa: E402
from openflowsheet.canonical import state_sha256  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.revision_flowsheet import component_basis  # noqa: E402
from openflowsheet.models.thermal.kernel import Failure, phase_properties, saturation  # noqa: E402
from openflowsheet.orchestrator.executor import execute_plan  # noqa: E402
from openflowsheet.orchestrator.revision import plan_revision  # noqa: E402
from openflowsheet.thermo import syn001  # noqa: E402
from openflowsheet.thermo.iapws95 import Iapws95Provider  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
HAND = REPO / "benchmarks" / "e01" / "cost_hand"
STATES = HAND / "recorded_states.yaml"
FIXTURES = REPO / "tests" / "fixtures" / "schemas" / "assessment_report" / "valid"
CONTEXT = EvaluationContext(model_version="e01-b4", constants_sha256="0" * 64)


# -- the recorded states (A11, A12) ----------------------------------------------------------------
@contextmanager
def _registered() -> Iterator[pytest.MonkeyPatch]:
    patch = pytest.MonkeyPatch()
    try:
        register(patch)
        yield patch
    finally:
        patch.undo()


@cache
def _solved(case: str) -> tuple[dict[str, Any], dict[str, float], str]:
    """(document, state, state_sha256) of an S11 case."""
    with _registered() as patch:
        if case == "M1":
            with column_registered(patch, frozenset({"syn001", "wilson-ig-v2"})):
                document = column_case("M1")
                binding = bind_revision_flowsheet(document)
                plan, _ = plan_revision(binding, T06_REVISION_V2)
                run = execute_plan(
                    plan=plan,
                    flowsheet=binding.flowsheet,
                    spec=binding.spec,
                    policy=T06_REVISION_V2,
                )
        else:
            document = committed_case(case)
            binding, run = solve(document)
    assert run.state is not None
    state = dict(run.state)
    return document, state, state_sha256(state, binding.spec.variable_ids)


def _repr(x: float) -> str:
    return repr(float(x))


def _th_r1_drum() -> dict[str, Any]:
    """TH-R1's flash D: products S5 (vapour) and S6 (liquid), saturated water at their P; the
    IAPWS-95 provider's saturated v of each phase (S11's saturation routine)."""
    document, state, digest = _solved("TH-R1")
    water = Iapws95Provider()
    molar_mass = component_basis(document).molecular_weights["H2O"]

    def v_sat(pressure: float, phase: str) -> float:
        sat = saturation(water, pressure, CONTEXT)
        assert not isinstance(sat, Failure), sat
        jets = phase_properties(water, CONTEXT, sat.temperature, pressure, phase, ("v",))
        assert not isinstance(jets, Failure), jets
        return float(jets["v"][0])

    assert state["S5.sat.L"] == 0.0 and state["S6.sat.V"] == 0.0
    v_v, v_l = v_sat(state["S5.P"], "VAPOR"), v_sat(state["S6.P"], "LIQUID")
    return {
        "state_sha256": digest,
        "inputs": {
            "S5.sat.V": _repr(state["S5.sat.V"]),
            "S5.P": _repr(state["S5.P"]),
            "S6.sat.L": _repr(state["S6.sat.L"]),
            "S6.P": _repr(state["S6.P"]),
            "M_H2O_kg_mol": _repr(molar_mass),
            "v_sat_V_m3_mol": _repr(v_v),
            "v_sat_L_m3_mol": _repr(v_l),
        },
        "vdot_V_m3s": _repr(state["S5.sat.V"] * v_v),
        "vdot_L_m3s": _repr(state["S6.sat.L"] * v_l),
        "rho_V_kgm3": _repr(molar_mass / v_v),
        "rho_L_kgm3": _repr(molar_mass / v_l),
        "note": "vdot = n v_sat(P), rho = M / v_sat(P), rounded to binary64 here (inputs of A11)",
    }


def _m1_column() -> dict[str, Any]:
    """M1's column S02 (7 stages, condenser 1 and reboiler 7): the vapour and liquid leaving each
    tray stage 2..6 (`S02.stage.<j>.v.<c>`, `.l.<c>`), T and P; molar masses from the document's
    component basis; liquid molar volumes syn001's `V_MOLAR` (§9.4 identity)."""
    document, state, digest = _solved("M1")
    components = list(syn001.COMPONENTS)
    masses = component_basis(document).molecular_weights
    stages: dict[str, Any] = {}
    for j in range(2, 7):
        p = f"S02.stage.{j}"
        vapour = {c: state[f"{p}.v.{c}"] for c in components}
        liquid = {c: state[f"{p}.l.{c}"] for c in components}
        assert math.isclose(sum(vapour.values()), state[f"{p}.V"], rel_tol=1e-12)
        assert math.isclose(sum(liquid.values()), state[f"{p}.L"], rel_tol=1e-12)
        stages[str(j)] = {
            "T_K": _repr(state[f"{p}.T"]),
            "P_Pa": _repr(state[f"{p}.P"]),
            "vapor_mol_s": {c: _repr(x) for c, x in vapour.items()},
            "liquid_mol_s": {c: _repr(x) for c, x in liquid.items()},
        }
    return {
        "state_sha256": digest,
        "molar_mass_kg_mol": {c: _repr(masses[c]) for c in components},
        "liquid_molar_volume_m3_mol": {
            c: _repr(v) for c, v in zip(components, syn001.V_MOLAR, strict=True)
        },
        "R_thermo_syn001": _repr(syn001.R),
        "stages": stages,
    }


def _recorded() -> dict[str, Any]:
    return {
        "id": "e01-cost-hand-recorded-states-v1",
        "writer": "tests/test_e01_b_cost_hand.py --write-states",
        "a11_th_r1_drum": _th_r1_drum(),
        "a12_m1_column": _m1_column(),
    }


def _write_states() -> None:
    text = yaml.safe_dump(_recorded(), sort_keys=False, allow_unicode=True, width=100)
    STATES.write_text(text, encoding="utf-8")


# -- the expectations file -------------------------------------------------------------------------
def _hand() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((HAND / "cost_hand.yaml").read_text(encoding="utf-8"))
    return data


def _rel(got: float, want: float) -> float:
    return abs(got - want) / abs(want)


def test_the_expectations_are_current_and_independent() -> None:
    script = HAND / "cost_hand.py"
    data = _hand()
    assert data["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    run = subprocess.run(
        [sys.executable, "-I", str(script), "--check"], capture_output=True, text=True
    )
    assert run.returncode == 0, run.stdout + run.stderr
    text = script.read_text(encoding="utf-8")
    assert "import openflowsheet" not in text and "from openflowsheet" not in text
    for reach in ("importlib", "src/openflowsheet", "files(", "sys.path"):
        assert reach not in text, reach  # no route to the package's code or data
    assert data["transcribed_from"]["file_sha256"] == (
        "362b0a22e78ad578c4ce6408224aa6193fc6330cb7041fc1d4aaee0e060b1184"
    )


def test_the_recorded_states_are_the_solved_states() -> None:
    """The committed inputs of A11/A12 equal a fresh solve's (rel 1e-9, platform last bits); the
    states are the report fixtures' (state_sha256)."""
    committed = yaml.safe_load(STATES.read_text(encoding="utf-8"))
    fresh = _recorded()

    def compare(a: Any, b: Any, where: str) -> None:
        if isinstance(a, dict):
            assert set(a) == set(b), where
            for k in a:
                compare(a[k], b[k], f"{where}.{k}")
            return
        try:
            x, y = float(a), float(b)
        except ValueError:
            assert a == b, where
            return
        assert math.isclose(x, y, rel_tol=1e-9, abs_tol=0.0) or x == y, (where, a, b)

    for key in ("a11_th_r1_drum", "a12_m1_column"):
        block = dict(committed[key])
        digest = block.pop("state_sha256")
        compare(block, {k: v for k, v in fresh[key].items() if k != "state_sha256"}, key)
        fixture = "p1_th_r1" if key.startswith("a11") else "p3_m1"
        report = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
        assert digest == report["state_sha256"], key
    assert (
        float(committed["a12_m1_column"]["R_thermo_syn001"])
        == _hand()["sizing"]["A12"]["R"]["value"]
    )


# -- A14: the forms at the registered sizes --------------------------------------------------------
def _package_inputs(entry: str, inputs: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    """The package's input names (forms.py `inputs`) for one of cost_hand's cases."""
    if entry == "exchanger.shell_tube":
        return {"area": inputs["area_m2"], "design_pressure": inputs["P_Pa"]}, 1
    if entry.startswith("vessel."):
        return {
            "diameter": inputs["D_m"],
            "length": inputs["L_m"],
            "thickness": inputs["t_shell_m"],
        }, 1
    if entry == "column.trays":
        return {"diameter": inputs["D_m"], "n_act": int(inputs["N_act"])}, 1
    if entry == "pump":
        return {
            "vol_flow": inputs["vol_flow_m3s"],
            "head": inputs["head_m"],
            "power": inputs["power_W"],
        }, 1
    if entry == "motor.electric":
        return {"power": inputs["shaft_power_W"]}, int(inputs["N"])
    if entry == "compressor":
        return {"power": inputs["power_W"]}, 1
    if entry == "turbine":
        return {"power": -inputs["power_W"]}, 1  # §4.4.5: the turbine item's power is −W
    raise AssertionError(entry)


def _package_options(options: Mapping[str, Any]) -> dict[str, str]:
    out = {k: v for k, v in options.items() if k != "orientation"}
    if "platforms_ladders" in out:
        out["platforms_ladders"] = "true" if out["platforms_ladders"] else "false"
    return {k: str(v) for k, v in out.items()}


#: cost_hand's regime names → the package's `Selection.pieces` keys and piece numbers.
_PIECES = {
    "pressure": ("pressure_psig", {"floor": 0, "1": 1}),
    "platforms.L": ("platform_length_ft", {"floor": 0, "1": 1, "2": 2}),
    "platforms.D": ("platform_diameter_ft", {"floor": 0, "1": 1}),
}
#: Cases at an exact floor bound: either regime gives the same cost (the floor is continuous),
#: so the package's choice there is not asserted.
_AT_BOUND = ("S_min", "floor bound (100 psig)", "at their floor bounds")


def _evaluate(entry: str, options: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any:
    from openflowsheet.assessment.cost.forms import FORMS, select  # noqa: PLC0415
    from openflowsheet.assessment.cost.sets import NoCorrelation, load_set, resolve  # noqa: PLC0415
    from openflowsheet.compile.reference import FloatAlgebra  # noqa: PLC0415

    resolved = resolve(load_set("sslw-idaes-v1"), entry, _package_options(options))
    assert not isinstance(resolved, NoCorrelation), (entry, options, resolved)
    form = FORMS[resolved.form]
    x, units = _package_inputs(entry, inputs)
    sel = select(form, resolved, x, units=units)
    if not hasattr(sel, "size"):
        return sel, None
    return sel, float(form.cost(resolved, x, sel, FloatAlgebra()))


def _cases() -> list[tuple[str, dict[str, Any]]]:
    return [(entry, case) for entry, block in _hand()["forms"].items() for case in block["cases"]]


def test_a14_every_form_at_its_registered_sizes() -> None:
    worst: dict[str, float] = {}
    for entry, case in _cases():
        sel, cost = _evaluate(entry, case["options"], case["inputs"])
        where = f"{entry}: {case['label']}"
        if case.get("refused"):
            assert cost is None, (where, sel)
            continue
        assert cost is not None, (where, sel)
        want = case["regime"]
        if not any(tag in case["label"] for tag in _AT_BOUND):
            if "size" in want:
                assert sel.size == want["size"], (where, sel)
            for name, choice in want.items():
                if name in _PIECES:
                    key, numbers = _PIECES[name]
                    assert sel.pieces[key] == numbers[choice], (where, sel)
        rel = _rel(cost, case["C_P"]["value"])
        worst[entry] = max(worst.get(entry, 0.0), rel)
        assert rel <= 1e-10, (where, cost, case["C_P"])
    print("A14 registered sizes, worst rel per entry:", {k: f"{v:.2e}" for k, v in worst.items()})


def test_a14_p1_and_p3_sizes() -> None:
    """The package's forms at the fixtures' sizes, and the fixtures' purchased costs (escalated by
    the WPU11 2006 → 2023 factor) against cost_hand's: rel ≤ 1e-10."""
    hand = _hand()
    factor = hand["chain"]["escalation"]["factor"]["value"]
    worst = 0.0
    for name, block in hand["p_sizes"].items():
        report = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert report["state_sha256"] == block["state_sha256"], name
        items = {i["item_id"]: i for i in report["items"]}
        for row in block["items"]:
            item = items[row["item"]]
            assert item["source"]["entry"] == row["entry"], row["item"]
            assert item["escalation"]["factor"] == pytest.approx(factor, rel=1e-15)
            _, cost = _evaluate(row["entry"], row["options"], row["inputs"])
            assert cost is not None
            for got, want in (
                (cost, row["C_P"]["value"]),
                (item["purchased_value"], row["purchased_at_basis"]["value"]),
            ):
                worst = max(worst, _rel(got, want))
                assert _rel(got, want) <= 1e-10, (name, row["item"], got, want)
            regime = {k.removeprefix(row["item"] + "."): v for k, v in item["regime"].items()}
            for key, choice in row["regime"].items():
                assert regime[key if key == "size" else f"{key}.piece"] == choice, (name, key)
    print(f"A14 P-sizes worst rel {worst:.2e}")


# -- A10, A11, A12 ---------------------------------------------------------------------------------
def test_a10_the_exchanger_hand_case() -> None:
    from openflowsheet.assessment.sizing.families import underwood  # noqa: PLC0415

    a10 = _hand()["design_note"]["A10"]
    dtlm = underwood(a10["dT1"]["value"], a10["dT2"]["value"])
    assert _rel(dtlm, a10["dT_lm"]["value"]) <= 1e-13
    assert _rel(1.0e6 / (500.0 * 1.0 * dtlm), a10["area_m2"]["value"]) <= 1e-13
    assert a10["dT_lm"]["value"] == pytest.approx(71.95947205233731, rel=1e-13)
    assert a10["area_m2"]["value"] == pytest.approx(27.79342236620868, rel=1e-13)


def test_a11_the_th_r1_flash_drum() -> None:
    a11 = _hand()["sizing"]["A11"]
    report = json.loads((FIXTURES / "p1_th_r1.json").read_text(encoding="utf-8"))
    assert report["state_sha256"] == a11["state_sha256"]
    drum = next(i for i in report["items"] if i["item_id"] == "D.drum")
    size = drum["size"]
    for got, want in (
        (size["diameter"], a11["D_m"]),
        (size["height"], a11["L_m"]),
        (size["volume"], a11["V_m3"]),
    ):
        assert _rel(got, want["value"]) <= 1e-12, (got, want)
    controlling = next(
        e for e in report["regime"]["entries"] if e["entry_id"] == "D.drum.controlling"
    )
    assert controlling["choice"] == a11["controlling"]
    # The losing member's admissibility is 1 − D_V²/D_L² (the row the package holds).
    lose = 1.0 - a11["D2_V"]["value"] / a11["D2_L"]["value"]
    assert controlling["admissibility"]["over_V"] == pytest.approx(lose, rel=1e-12)


def test_a12_the_m1_column_shell() -> None:
    a12 = _hand()["sizing"]["A12"]
    report = json.loads((FIXTURES / "p3_m1.json").read_text(encoding="utf-8"))
    assert report["state_sha256"] == a12["state_sha256"]
    items = {i["item_id"]: i for i in report["items"]}
    shell = items["S02.shell"]
    assert _rel(shell["size"]["diameter"], a12["D_m"]["value"]) <= 1e-12
    assert _rel(shell["size"]["height"], a12["H_m"]["value"]) <= 1e-12
    n_act = next(i["value"] for i in items["S02.trays"]["inputs"] if i["name"] == "N_act")
    assert n_act == a12["N_act"]
    controlling = next(
        e for e in report["regime"]["entries"] if e["entry_id"] == "S02.shell.controlling"
    )
    assert controlling["choice"] == str(a12["j_star"])
    # Every D_j²: the package's rows are 1 − D_j²/D_{j*}² for the trays j ≠ j*.
    d2_star = shell["size"]["diameter"] ** 2
    for j, stage in a12["stages"].items():
        if int(j) == a12["j_star"]:
            assert _rel(d2_star, stage["D2_m2"]["value"]) <= 1e-12
            continue
        d2 = d2_star * (1.0 - controlling["admissibility"][f"over_{j}"])
        assert _rel(d2, stage["D2_m2"]["value"]) <= 1e-12, j


# -- the chain, CRF, escalation on P1 --------------------------------------------------------------
def test_the_chain_crf_and_tac_on_p1() -> None:
    chain = _hand()["chain"]
    report = json.loads((FIXTURES / "p1_th_c1.json").read_text(encoding="utf-8"))
    p1 = chain["p1_th_c1"]
    for key in ("capex.TDC", "capex.EPC", "capex.CAPEX", "capex.sum_purchased"):
        assert _rel(report["capex"][key], p1[key]["value"]) <= 1e-12, key
    assert _rel(report["capex"]["capex.total"], p1["capex.CAPEX"]["value"]) <= 1e-12
    for item, value in p1["bare_module"].items():
        assert _rel(report["capex"][f"capex.bare_module.{item}"], value["value"]) <= 1e-12, item
    assert (
        _rel(report["annual"]["annual.capital_charge"], p1["annual.capital_charge"]["value"])
        <= 1e-12
    )
    assert _rel(report["annual"]["tac"], p1["tac"]["value"]) <= 1e-12
    assert float(p1["opex.total_input"]) == report["opex"]["opex.total"]
    esc = chain["escalation"]
    for item in report["items"]:
        assert item["escalation"]["base"] == ["2006", esc["base"][1]]
        assert item["escalation"]["target"] == esc["target"]
        assert _rel(item["escalation"]["factor"], esc["factor"]["value"]) <= 1e-15
    assert esc["same_basis_factor"]["value"] == 1.0
    assert chain["crf_0.08_20"]["value"] == pytest.approx(0.10185220882315059, abs=2.8e-17)


# -- A15: the IDAES evaluation (benchmarks/e01/brightway/idaes_crosscheck.yaml) -------------------
IDAES = REPO / "benchmarks" / "e01" / "brightway"


def test_a15_the_idaes_evaluation_is_current() -> None:
    """The committed IDAES run is of this script, on these cases, with the pinned SSLW.py."""
    data = yaml.safe_load((IDAES / "idaes_crosscheck.yaml").read_text(encoding="utf-8"))
    script = IDAES / "idaes_crosscheck.py"
    assert data["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert (
        data["cases_sha256"] == hashlib.sha256((HAND / "cost_hand.yaml").read_bytes()).hexdigest()
    )
    env = data["environment"]
    assert env["idaes_pse"] == "2.13.0"
    assert env["SSLW.py_sha256"] == _hand()["transcribed_from"]["file_sha256"]


def test_a15_package_and_transcription_against_idaes() -> None:
    """Every non-refused case and every P-size item: the package's C_P and cost_hand's against
    IDAES's at the effective inputs, rel ≤ 1e-9 (escalated, never loosened, if larger)."""
    data = yaml.safe_load((IDAES / "idaes_crosscheck.yaml").read_text(encoding="utf-8"))
    hand = _hand()
    worst = {"package": 0.0, "hand": 0.0}
    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for entry, block in hand["forms"].items():
        live = [c for c in block["cases"] if not c.get("refused")]
        assert [c["label"] for c in live] == [r["label"] for r in data["forms"][entry]], entry
        pairs += [(entry, c, r) for c, r in zip(live, data["forms"][entry], strict=True)]
    for name, block in hand["p_sizes"].items():
        assert [r["item"] for r in block["items"]] == [r["item"] for r in data["p_sizes"][name]]
        pairs += [
            (row["entry"], row, r)
            for row, r in zip(block["items"], data["p_sizes"][name], strict=True)
        ]
    for entry, case, idaes in pairs:
        _, cost = _evaluate(entry, case["options"], case["inputs"])
        assert cost is not None
        for who, got in (("package", cost), ("hand", case["C_P"]["value"])):
            rel = _rel(got, idaes["C_P"])
            worst[who] = max(worst[who], rel)
            assert rel <= 1e-9, (who, entry, case.get("label", case.get("item")), got, idaes)
    print(f"A15 worst rel vs IDAES: package {worst['package']:.2e}, hand {worst['hand']:.2e}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-states"]:
        raise SystemExit("usage: python tests/test_e01_b_cost_hand.py --write-states")
    _write_states()
