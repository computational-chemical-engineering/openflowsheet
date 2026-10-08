"""Generate `evidence/M01/<C>/manifest.json` by measuring, not by transcribing. M01 WO-7.

M01 spec §13 (the catalogue), §14 WO-7 and WO-8 item 6. The manifest carries one check per
assertion `M01.A01`…`A52`, read from the spec's §9 itself, so that an assertion cannot be left out:
an id without a measurement here, or a measurement without an id there, stops the script. Each
check is decided from what this script ran at `C`:

1. **The M01 tests**, run once here (`pytest --junitxml` over `tests/test_m01_*.py`). An assertion
   names its nodes by the prefix `test_aNN_`; the record halves of A41–A46 and A48 are A52's nodes
   `test_a52_aNN_` (spec §8.15). A failed or skipped node fails the check; a prefix that ran no node
   fails it too, except where the assertion is judged by another command (A33, A34, A38–A40).
2. **Direct measurements**, made here at `C` with the provider and the stand-in against
   `benchmarks/m01/reference_values.yaml`: each numerical check records the worst measured value,
   its tolerance and the margin tolerance/value. A value is judged against its tolerance here as
   well, so a check passes only if its nodes pass *and* its measurement is inside the bound.
3. **The generator** `m01_reference.py --check` (A34: 88 claims, the files byte-identical).
4. **The external records**: `external_crosscheck.py --check` run in its own environment (A02,
   A38–A40), and `idaes_conformance.py` re-run in the IDAES environment with its record compared
   with the committed one (A37). The interpreters are given on the command line; neither ever runs
   in the project environment.
5. **The probe record** `reactor-probe.json`, read, never re-run (spec §8.15; R-200): A41–A46 and
   A48 are its record halves, A47 has none and is M02's (`not_applicable` here).
6. **The gate**: the stdout of `scripts/check.sh` at `C`, required to end `check.sh: PASSED`.
7. **A33**: `git diff` of the frozen paths between the branch base and `C`.

Status is `tested` only if every check is `pass` (A47 is `not_applicable` by the spec's own
assignment to M02, §8.14–8.15, and is not in §13's catalogue), the gate is green, and every
command exited 0; otherwise `implemented`. `reviewed` is never set, and both review fields stay
`pending`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m01_evidence_manifest.py --commit C \\
        --gate-log GATE_STDOUT --crosscheck-python PY --idaes-python PY [--base B] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "derivations" / "M01-spec.md"
M01 = ROOT / "benchmarks" / "m01"
REFERENCE = M01 / "reference_values.yaml"
CROSSCHECK = M01 / "external-crosscheck.json"
IDAES_RECORD = M01 / "idaes-conformance.json"
PROBE = M01 / "reactor-probe.json"
#: Spec §9.7 A33: the paths whose registered values M01 must not move.
FROZEN = (
    "benchmarks/syn001",
    "benchmarks/t05",
    "benchmarks/t05b",
    "benchmarks/t06",
    "benchmarks/t08",
    "src/openflowsheet/models/syn001",
    "evidence/K05",
    "evidence/T07",
    "tests/fixtures",
    "scripts/k05_structural_identity.py",
)
#: The A33 paths' edits the spec itself orders: the envelope tracks the new provider (T08.A20) and
#: T08.A32's amended record rule (spec §3.5). Statements, not registered values.
ORDERED_EDITS = ("benchmarks/t08/support_envelope.yaml",)
REQUIREMENTS = ("D08",)
RESULTS = ("pass", "fail", "unsupported", "not_applicable")

sys.path.insert(0, str(ROOT / "src"))

from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.c1 import ELEMENT_MATRIX  # noqa: E402
from openflowsheet.models.c1.boundary import project, tube_inlet  # noqa: E402
from openflowsheet.models.c1.reactor_standin import ReactorStandin  # noqa: E402
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState  # noqa: E402
from openflowsheet.thermo.pr_c1 import (  # noqa: E402
    COMPONENTS,
    DERIVATIVE_INPUTS,
    PROPERTIES,
    PrC1Provider,
    cp_ig,
    h_ig,
    parameters,
)

CONTEXT = EvaluationContext(model_version="m01-evidence", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def catalogue() -> list[str]:
    """`A01`…: every assertion of spec §9, in order (`- **M01.Axx**` bullets)."""
    found = re.findall(r"^- \*\*M01\.(A\d\d)\*\*", SPEC.read_text(encoding="utf-8"), re.MULTILINE)
    if len(found) != len(set(found)):
        raise SystemExit(f"duplicate assertion ids in {SPEC.name}")
    return found


# ----------------------------------------------------------------------------- the tests


@dataclass
class TestRun:
    """Node id → outcome (`passed`, `failed`, `skipped`) as `pytest --junitxml` recorded it."""

    nodes: dict[str, str]
    exit_code: int

    __test__ = False  # not a pytest class

    def select(self, prefix: str) -> dict[str, str]:
        """The nodes whose function name starts with `prefix` (any M01 module)."""
        return {
            node: outcome
            for node, outcome in self.nodes.items()
            if node.partition("::")[2].split("[", 1)[0].startswith(prefix)
        }


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def run_tests(artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    modules = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/test_m01_*.py"))
    junit, stdout = artifacts / "m01-tests.junit.xml", artifacts / "m01-tests.stdout.txt"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
        + modules,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    nodes: dict[str, str] = {}
    for case in ElementTree.parse(junit).getroot().iter("testcase"):
        node = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag for child in case}
        if tags & {"failure", "error"} or nodes.get(node) == "failed":
            nodes[node] = "failed"
        else:
            nodes[node] = "skipped" if "skipped" in tags else "passed"
    command = {
        "cmd": "PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider "
        "--junitxml=ARTIFACTS/m01-tests.junit.xml " + " ".join(modules),
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(stdout),
    }
    return TestRun(nodes, completed.returncode), command


def _run(cmd: Sequence[str], log: Path, shown: str, env: Mapping[str, str] | None = None) -> Any:
    completed = subprocess.run(
        list(cmd), cwd=ROOT, capture_output=True, text=True, check=False, env=env
    )
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    command = {
        "cmd": shown,
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(log),
    }
    return completed, command


# ----------------------------------------------------------------------------- measurements

CLOSED: Mapping[str, Any] = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))["closed_form"]
PHASE_STATES: Mapping[str, Any] = CLOSED["phase_states"]
FLASH: Mapping[str, Any] = CLOSED["flash_states"]
BOUNDARY: Mapping[str, Any] = CLOSED["boundary"]


def _rel(value: float, expected: float) -> float:
    """Spec §9's "rel" for dimensionless and J/mol quantities."""
    return abs(value - expected) / max(abs(expected), 1.0)


def _ratio(value: float, expected: float) -> float:
    """Spec §9's "rel" for molar volumes and flows: |impl/ref − 1|."""
    return abs(value / expected - 1.0)


def _state(sid: str) -> StreamState:
    s = PHASE_STATES[sid]
    return StreamState(n=tuple(s["n_mol_s"]), temperature=s["T_K"], pressure=s["P_Pa"])


def _evaluate(sid: str, properties: Sequence[str], derivatives: Sequence[str] = ()) -> Any:
    request = PropertyRequest(
        state=_state(sid),
        phase=PHASE_STATES[sid]["phase"],
        properties=tuple(properties),
        derivatives=tuple(derivatives),
    )
    return PROVIDER.evaluate_phase(request, CONTEXT)


def _flash(fid: str, scale_nh3: float = 1.0) -> Any:
    s = FLASH[fid]
    n = list(s["n_mol_s"])
    n[2] *= scale_nh3
    state = StreamState(n=tuple(n), temperature=s["T_K"], pressure=s["P_Pa"])
    return PROVIDER.flash(FlashRequest(state=state), CONTEXT)


#: A measurement: a mapping of quantity → (worst measured, tolerance, sense), sense `le` (the value
#: must not exceed the bound) or `ge` (must reach it); plus free-form facts.
Measured = dict[str, Any]


def _bound(value: float, tolerance: float, sense: str = "le") -> dict[str, Any]:
    within = value <= tolerance if sense == "le" else value >= tolerance
    margin = (tolerance / value if value else math.inf) if sense == "le" else value / tolerance
    return {
        "value": value,
        "tolerance": tolerance,
        "sense": "<=" if sense == "le" else ">=",
        "within": within,
        "margin": "infinite (exactly 0)" if math.isinf(margin) else float(f"{margin:.3g}"),
    }


def m_a05() -> Measured:
    par = parameters()
    worst = max(
        max(
            _rel(par.kappa[i], CLOSED["components"][c]["kappa"]),
            _ratio(par.a_c[i], CLOSED["components"][c]["a_c_Pa_m6_per_mol2"]),
            _ratio(par.b[i], CLOSED["components"][c]["b_m3_per_mol"]),
        )
        for i, c in enumerate(COMPONENTS)
    )
    crit = CLOSED["nh3_eos_critical"]
    critical = max(
        _ratio(par.nh3_critical_temperature, crit["T_K"]),
        _ratio(par.nh3_critical_pressure, crit["P_Pa"]),
        _ratio(par.nh3_critical_volume, crit["v_m3_per_mol"]),
    )
    return {"kappa_a_c_b": _bound(worst, 1e-14), "nh3_eos_critical": _bound(critical, 1e-13)}


def m_a06() -> Measured:
    worst, datum = 0.0, 0.0
    for i, c in enumerate(COMPONENTS):
        ref = CLOSED["components"][c]
        worst = max(
            worst,
            _rel(cp_ig(298.15, i), ref["cp_ig_298_15"]),
            _rel(cp_ig(700.0, i), ref["cp_ig_700"]),
            _rel(h_ig(268.15, i), ref["h_ig_268_15"]),
            _rel(h_ig(700.0, i), ref["h_ig_700"]),
        )
        datum = max(datum, abs(h_ig(298.15, i) - parameters().formation_enthalpy[i]))
    return {"cp_h_ig": _bound(worst, 1e-12), "h_ig_298_15_minus_dfH_J_mol": _bound(datum, 1e-9)}


def _evaluated() -> list[str]:
    return [sid for sid, s in PHASE_STATES.items() if s["status_or_reason"] == "ok"]


def m_a07() -> Measured:
    worst = 0.0
    for sid in _evaluated():
        expected = PHASE_STATES[sid]["values"]
        result = _evaluate(sid, tuple(expected))
        for name, value in expected.items():
            measure = _ratio if name == "v" else _rel
            worst = max(worst, measure(result.values[name], value))
    return {"Z_h_v_lnphi": _bound(worst, 1e-12), "states": _evaluated()}


def m_a09() -> Measured:
    gaps = {}
    for sid in ("V1", "V2"):
        values = list(_evaluate(sid, [f"lnphi_{c}" for c in COMPONENTS]).values.values())
        gaps[sid] = min(abs(a - b) for i, a in enumerate(values) for b in values[i + 1 :])
    departures = []
    for sid in _evaluated():
        s = PHASE_STATES[sid]
        h = _evaluate(sid, ("h",)).values["h"]
        total = sum(s["n_mol_s"])
        ideal = (
            h_ig(s["T_K"], 2)
            if s["phase"] == "LIQUID"
            else sum(n / total * h_ig(s["T_K"], i) for i, n in enumerate(s["n_mol_s"]))
        )
        departures.append(abs(h - ideal))
    return {
        "min_pairwise_lnphi_gap": _bound(min(gaps.values()), 1e-6, "ge"),
        "by_state": gaps,
        "min_abs_h_departure_J_mol": _bound(min(departures), 1.0, "ge"),
    }


def m_a10() -> Measured:
    worst = 0.0
    for sid, expected in CLOSED["derivatives"].items():
        result = _evaluate(sid, tuple(expected), DERIVATIVE_INPUTS)
        s = PHASE_STATES[sid]
        scale = {"T": s["T_K"], "P": s["P_Pa"]}
        total = sum(s["n_mol_s"])
        for name, by_input in expected.items():
            value = result.values[name]
            for wanted, reference in by_input.items():
                k = scale.get(wanted, total)
                got = result.derivatives[name][wanted]
                worst = max(
                    worst, abs(k * got - k * reference) / max(abs(value), 1.0, abs(k * reference))
                )
    return {"scaled_derivative_error": _bound(worst, 1e-9), "states": list(CLOSED["derivatives"])}


def m_a11() -> Measured:
    liquid = _evaluate("L1", ("h", "Z", "v", "lnphi_NH3"), DERIVATIVE_INPUTS)
    zeros = all(entry[f"n_{c}"] == 0.0 for entry in liquid.derivatives.values() for c in COMPONENTS)
    smallest = min(
        abs(entry[f"n_{c}"])
        for sid in ("V1", "V2")
        for entry in _evaluate(sid, PROPERTIES, DERIVATIVE_INPUTS).derivatives.values()
        for c in COMPONENTS
    )
    return {
        "L1_n_derivatives_exactly_zero": zeros,
        "min_vapour_n_derivative": _bound(smallest, 1e-12, "ge"),
    }


def m_a12() -> Measured:
    worst = {
        "homogeneity_Z_v_h": 0.0,
        "lnphi_homogeneity": 0.0,
        "gibbs_duhem": 0.0,
        "symmetry": 0.0,
    }
    for sid in ("V1", "V2"):
        n = PHASE_STATES[sid]["n_mol_s"]
        total = sum(n)
        y = [value / total for value in n]
        result = _evaluate(sid, PROPERTIES, DERIVATIVE_INPUTS)
        dn = {p: [result.derivatives[p][f"n_{c}"] for c in COMPONENTS] for p in PROPERTIES}
        for name in ("Z", "v", "h"):
            terms = [nj * d for nj, d in zip(n, dn[name], strict=True)]
            worst["homogeneity_Z_v_h"] = max(
                worst["homogeneity_Z_v_h"], abs(sum(terms)) / sum(abs(t) for t in terms)
            )
        block = [[total * value for value in dn[f"lnphi_{c}"]] for c in COMPONENTS]
        m = max(abs(value) for row in block for value in row)
        for i in range(5):
            row = abs(sum(y[j] * block[i][j] for j in range(5))) / m
            column = abs(sum(y[j] * block[j][i] for j in range(5))) / m
            worst["lnphi_homogeneity"] = max(worst["lnphi_homogeneity"], row)
            worst["gibbs_duhem"] = max(worst["gibbs_duhem"], column)
            for j in range(5):
                worst["symmetry"] = max(worst["symmetry"], abs(block[i][j] - block[j][i]) / m)
    measured: Measured = {name: _bound(value, 1e-12) for name, value in worst.items()}
    measured["scale"] = (
        "lnphi identities over M = max|J_ij| (Amendment 1, R-196); Z, v, h over their own row "
        "sums of |n_j dX/dn_j|"
    )
    return measured


def _two_phase() -> list[str]:
    return [fid for fid, s in FLASH.items() if s["phase_signature"] == "TWO_PHASE"]


def m_a15() -> Measured:
    y, beta, flows = 0.0, 0.0, 0.0
    for fid in _two_phase():
        expected, result = FLASH[fid], _flash(fid)
        y = max(y, _ratio(result.k_values["NH3"], expected["y_star"]))
        beta = max(beta, abs(result.vapor_fraction - expected["vapor_fraction"]))
        flows = max(
            flows,
            _ratio(result.vapor.n[2], expected["v_nh3"]),
            _ratio(result.liquid.n[2], expected["l_nh3"]),
        )
    return {
        "y_star_rel": _bound(y, 1e-11),
        "vapor_fraction_abs": _bound(beta, 1e-12),
        "nh3_flows_rel": _bound(flows, 1e-11),
        "states": _two_phase(),
    }


def m_a16() -> Measured:
    worst = 0.0
    for fid in _two_phase():
        result = _flash(fid)
        lnphi = []
        for phase, outlet in (("VAPOR", result.vapor), ("LIQUID", result.liquid)):
            request = PropertyRequest(state=outlet, phase=phase, properties=("lnphi_NH3",))
            lnphi.append(PROVIDER.evaluate_phase(request, CONTEXT).values["lnphi_NH3"])
        worst = max(worst, abs(math.log(result.k_values["NH3"]) + lnphi[0] - lnphi[1]))
    return {"equilibrium_residual": _bound(worst, 1e-12)}


def m_a21() -> Measured:
    base, doubled = _flash("F1"), _flash("F1", 2.0)
    return {"y_star_bitwise_equal": base.k_values["NH3"].hex() == doubled.k_values["NH3"].hex()}


def m_a22() -> Measured:
    worst = 0.0
    for fid in _two_phase():
        feed, result = FLASH[fid]["n_mol_s"], _flash(fid)
        for k in range(5):
            if feed[k]:
                gap = abs(result.vapor.n[k] + result.liquid.n[k] - feed[k])
                worst = max(worst, gap / math.ulp(feed[k]))
    return {"closure_in_ulp_of_feed": _bound(worst, 1.0)}


def m_a23() -> Measured:
    reaction = CLOSED["reaction"]
    nu = reaction["nu"]
    at_ref = sum(nu[i] * h_ig(298.15, i) for i in range(5))
    hot = sum(nu[i] * h_ig(673.15, i) for i in range(5))
    return {
        "dh_r_298_15_abs_J_mol": _bound(abs(at_ref - reaction["dh_r_ig_298_15_J_mol"]), 1e-9),
        "dh_r_673_15_rel": _bound(_rel(hot, reaction["dh_r_ig_673_15_J_mol"]), 1e-12),
    }


STANDIN = BOUNDARY["standin"]
PROJECTION = BOUNDARY["projection"]
INLET = StreamState(
    n=tuple(STANDIN["inlet_n_mol_s"]), temperature=STANDIN["T_in_K"], pressure=STANDIN["P_in_Pa"]
)


def _unit(**overrides: Any) -> ReactorStandin:
    return ReactorStandin(unit_id="R1", provider=PROVIDER, context=CONTEXT, **overrides)


def _h(state: StreamState) -> float:
    request = PropertyRequest(state=state, phase="VAPOR", properties=("h",))
    return float(state.total_flow * PROVIDER.evaluate_phase(request, CONTEXT).values["h"])


def m_a25() -> Measured:
    result = _unit().evaluate(INLET)
    outlet = max(
        _ratio(got, ref)
        for got, ref in zip(result.outlet.n, STANDIN["outlet_n_mol_s"], strict=True)
    )
    return {
        "xi_rel": _bound(_ratio(result.xi, STANDIN["xi_mol_s"]), 1e-14),
        "outlet_rel": _bound(outlet, 1e-14),
        "T_P_out_bitwise": (result.outlet.temperature, result.outlet.pressure)
        == (INLET.temperature, INLET.pressure),
        "Q_rel": _bound(_ratio(result.Q, STANDIN["Q_W"]), 1e-10),
        "H_in_H_out_rel": _bound(
            max(
                _ratio(_h(INLET), STANDIN["H_in_W"]),
                _ratio(_h(result.outlet), STANDIN["H_out_W"]),
            ),
            1e-11,
        ),
    }


def m_a26() -> Measured:
    n_in = STANDIN["inlet_n_mol_s"]
    total = sum(n_in)
    p = project(n_in, PROJECTION["raw_outlet_mol_s"])
    projected = max(
        _ratio(p.xi, PROJECTION["xi_mol_s"]),
        *(
            _ratio(got, ref)
            for got, ref in zip(p.outlet, PROJECTION["projected_outlet_mol_s"], strict=True)
        ),
    )
    defect = max(
        abs(got - ref) for got, ref in zip(p.defect, PROJECTION["defect_mol_s"], strict=True)
    )
    balances = max(
        abs(
            sum(e * n for e, n in zip(row, p.outlet, strict=True))
            - sum(e * n for e, n in zip(row, n_in, strict=True))
        )
        for row in ELEMENT_MATRIX
    )
    return {
        "xi_and_projected_outlet_rel": _bound(projected, 1e-12),
        "inerts_bitwise_and_CH4_defect_zero": p.outlet[3] == n_in[3]
        and p.outlet[4] == n_in[4]
        and p.defect[4] == 0.0,
        "defect_vector_over_n_tot_in": _bound(defect / total, 1e-13),
        "defect_rel_abs": _bound(abs(p.defect_rel - PROJECTION["defect_rel"]), 1e-13),
        "element_balances_over_n_tot_in": _bound(balances / total, 1e-13),
        "amended_by": "Amendment 1 (R-195): 1e-13 x n_tot,in, from relative 1e-12 and 1e-15",
    }


def m_a29() -> Measured:
    worst = 0.0
    base = _unit(n_tubes=3.0).evaluate(INLET)
    for k in (2.0, 7.0):
        scaled = _unit(n_tubes=3.0 * k).evaluate(replace(INLET, n=tuple(k * v for v in INLET.n)))
        worst = max(
            worst,
            _ratio(scaled.xi, k * base.xi),
            _ratio(scaled.Q, k * base.Q),
            *(_ratio(a, k * b) for a, b in zip(scaled.outlet.n, base.outlet.n, strict=True)),
        )
    return {"scaled_result_rel": _bound(worst, 1e-15), "k": [2.0, 7.0]}


def m_a37() -> Measured:
    record = json.loads(IDAES_RECORD.read_text(encoding="utf-8"))
    z, lnphi = 0.0, 0.0
    for sid in ("V1", "V2", "L1"):
        entry = record["phase_states"][sid]
        names = [name for name in entry["values"] if name.startswith("lnphi_")]
        ours = _evaluate(sid, ("Z", *names)).values
        z = max(z, abs(ours["Z"] - entry["values"]["Z"]) / abs(entry["values"]["Z"]))
        lnphi = max(lnphi, *(abs(ours[name] - entry["values"][name]) for name in names))
    beta, y = 0.0, 0.0
    for fid in ("F1", "F11"):
        entry, ours = record["flash_states"][fid], _flash(fid)
        beta = max(beta, abs(ours.vapor_fraction - entry["vapor_fraction"]))
        y = max(y, abs(ours.k_values["NH3"] - entry["y_star"]) / abs(entry["y_star"]))
    return {
        "Z_rel": _bound(z, 1e-9),
        "lnphi_abs": _bound(lnphi, 1e-9),
        "vapor_fraction_abs": _bound(beta, 1e-8),
        "y_star_rel": _bound(y, 1e-8),
    }


def _w22() -> Mapping[str, Any]:
    return dict(json.loads(CROSSCHECK.read_text(encoding="utf-8")))


def m_a38() -> Measured:
    rows = _w22()["w22_pure_nh3_vs_reference_eos"]["by_temperature_K"]
    temperatures = ("240", "260", "268.15", "280", "300", "320")
    deviations = {t: abs(rows[t]["P_sat_rel_dev"]) for t in temperatures}
    return {
        "max_abs_P_sat_rel_dev": _bound(max(deviations.values()), 0.02),
        "by_temperature_K": deviations,
        "kind": "validation band (spec §11), not a numerical tolerance",
    }


def _fugacity(keys: Sequence[str], band: float) -> Measured:
    rows = _w22()["w22_pure_component_fugacity_vs_reference_eos"]
    deviations = {key: abs(rows[key]["lnphi_pr_minus_ref"]) for key in keys}
    return {
        "max_abs_dlnphi": _bound(max(deviations.values()), band),
        "by_state": deviations,
        "kind": "validation band (spec §11), not a numerical tolerance",
    }


def m_a39() -> Measured:
    return _fugacity(("NH3-LIQUID-268.15-1e7", "NH3-LIQUID-250-2.5e7"), 0.05)


def m_a40() -> Measured:
    keys = [f"{c}-VAPOR-{t}-1e7" for c in ("H2", "N2", "Ar", "CH4") for t in ("268.15", "673.15")]
    return _fugacity([*keys, "NH3-VAPOR-673.15-1e7"], 0.05)


PROBE_RECORD: Mapping[str, Any] = json.loads(PROBE.read_text(encoding="utf-8"))
_ENTRIES = (
    *PROBE_RECORD["grid"],
    PROBE_RECORD["pinned"],
    *PROBE_RECORD["neighbouring_inlet_temperatures"],
)


def m_a41() -> Measured:
    accepted = (PROBE_RECORD["pinned"], *PROBE_RECORD["neighbouring_inlet_temperatures"])
    cold = PROBE_RECORD["cold_start_true_inlet"]
    return {
        "accepted_at_num_z_800": {
            str(e["T_in_K"]): e["m01_accepted"] is True and e["num_z"] == 800 for e in accepted
        },
        "cold_start_true_inlet_rejected": {str(e["dt_init"]): e["accepted"] is False for e in cold},
        "cold_start_dt_init_registered": sorted(e["dt_init"] for e in cold) == [1e-6, 1e-3, 1e-1],
    }


def m_a42() -> Measured:
    return {"max_rel_diff": _bound(PROBE_RECORD["path_independence"]["max_rel_diff"], 1e-6)}


def m_a43() -> Measured:
    repeats = PROBE_RECORD["repeats"]
    return {"runs": repeats["runs"], "two_runs": repeats["runs"] == 2, **repeats}


def m_a44() -> Measured:
    return {
        "bitwise_identical": PROBE_RECORD["backflow_override"]["bitwise_identical"],
        "min_u_ret_min": min(e["u_ret_min"] for e in _ENTRIES),
        "u_ret_positive_in_every_entry": all(e["u_ret_min"] > 0.0 for e in _ENTRIES),
    }


def m_a45() -> Measured:
    worst = max(
        abs(v) for e in _ENTRIES if e["m01_accepted"] for v in e["element_defect_rel"].values()
    )
    return {"max_element_defect_rel_accepted": _bound(worst, 1e-7)}


def m_a46() -> Measured:
    return {"max_abs_dP_over_P": _bound(max(abs(e["dP_over_P"]) for e in _ENTRIES), 1e-3)}


def m_a47() -> Measured:
    pinned = PROBE_RECORD["pinned"]
    return {
        "to_reproduce": {"outlet_n_mol_s": pinned["outlet_n_mol_s"], "T_out_K": pinned["T_out_K"]},
        "record_half": "none (spec §8.15: '—'); the adapter half is M02's",
    }


def m_a48() -> Measured:
    grid = [e["num_z"] for e in PROBE_RECORD["grid"]]
    accepted = [e["m01_accepted"] for e in PROBE_RECORD["grid"]]
    return {
        "grid_num_z": grid,
        "grid_registered": grid == [100, 200, 400, 800, 1600, 3200],
        "accepted_exactly_the_first_four": accepted == [True] * 4 + [False] * 2,
        "discretization_estimate": "reference_values.yaml derived_from_measured."
        "discretization_estimate, recomputed by claim DX-01 (A34)",
    }


def m_a52() -> Measured:
    pinned = PROBE_RECORD["pinned"]
    inlet = StreamState(
        n=tuple(pinned["inlet_n_mol_s"]), temperature=pinned["T_in_K"], pressure=pinned["P_in_Pa"]
    )
    tube = tube_inlet(inlet, n_tubes=1.0)
    flow = abs(tube.flow - pinned["F_ret_in_mol_s"]) / math.ulp(pinned["F_ret_in_mol_s"])
    composition = [
        abs(got - ref) / math.ulp(ref)
        for got, ref in zip(tube.composition, pinned["y_in"], strict=True)
    ]
    return {
        "mapping_F_ulp": _bound(flow, 2.0),
        "mapping_y_ulp": _bound(max(composition), 2.0),
        "y_ulp_by_component": dict(zip(COMPONENTS, composition, strict=True)),
    }


MEASUREMENTS: dict[str, Callable[[], Measured]] = {
    "A05": m_a05,
    "A06": m_a06,
    "A07": m_a07,
    "A09": m_a09,
    "A10": m_a10,
    "A11": m_a11,
    "A12": m_a12,
    "A15": m_a15,
    "A16": m_a16,
    "A21": m_a21,
    "A22": m_a22,
    "A23": m_a23,
    "A25": m_a25,
    "A26": m_a26,
    "A29": m_a29,
    "A37": m_a37,
    "A38": m_a38,
    "A39": m_a39,
    "A40": m_a40,
    "A41": m_a41,
    "A42": m_a42,
    "A43": m_a43,
    "A44": m_a44,
    "A45": m_a45,
    "A46": m_a46,
    "A47": m_a47,
    "A48": m_a48,
    "A52": m_a52,
}


def _bounds(measured: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    for value in measured.values():
        if isinstance(value, Mapping) and "within" in value:
            yield value


def _facts_hold(measured: Mapping[str, Any]) -> bool:
    """Every bound within, every boolean fact true."""
    if not all(bound["within"] for bound in _bounds(measured)):
        return False
    return all(value is not False for value in _walk_booleans(measured))


def _walk_booleans(node: Any) -> Iterator[bool]:
    if isinstance(node, bool):
        yield node
    elif isinstance(node, Mapping):
        for key, value in node.items():
            if key not in ("within",):  # a bound's verdict is judged by `_bounds`
                yield from _walk_booleans(value)


# ----------------------------------------------------------------------------- the checks


@dataclass
class Inputs:
    """What the checks judge. `main` measures it."""

    commit: str
    tests: TestRun
    gate_passed: bool
    gate_summary: str
    generator: dict[str, Any]
    crosscheck: dict[str, Any]
    idaes: dict[str, Any]
    frozen_diff: dict[str, Any]
    measured: dict[str, Measured] = field(default_factory=dict)


#: Assertions judged by a command rather than by `test_aNN_` nodes of their own.
_BY_COMMAND = {"A33", "A34", "A38", "A39", "A40"}
#: The record halves of A41–A46 and A48 are A52's nodes (spec §8.15).
_RECORD_HALF = {"A41", "A42", "A43", "A44", "A45", "A46", "A48"}


def _selector(aid: str) -> str:
    number = aid[1:]
    return f"test_a52_a{number}_" if aid in _RECORD_HALF else f"test_a{number}_"


def _description(aid: str) -> str:
    """The assertion's first sentence from the spec, as its description."""
    text = SPEC.read_text(encoding="utf-8")
    match = re.search(rf"^- \*\*M01\.{aid}\*\* — (.+?)(?:\n(?=- |\n|###)|\Z)", text, re.M | re.S)
    if match is None:
        raise SystemExit(f"M01.{aid}: no bullet in {SPEC.name}")
    body = " ".join(match[1].split())
    return f"M01 spec §9, M01.{aid}: {body[:600]}{'…' if len(body) > 600 else ''}"


def check(aid: str, inputs: Inputs) -> dict[str, Any]:
    nodes = inputs.tests.select(_selector(aid))
    counts = {o: sum(v == o for v in nodes.values()) for o in ("passed", "failed", "skipped")}
    value: dict[str, Any] = {}
    if nodes:
        value["tests"] = {"selector": f"tests/test_m01_*.py::{_selector(aid)}*", **counts}
    nodes_ok = bool(nodes) and counts["failed"] == counts["skipped"] == 0
    if aid in _BY_COMMAND and not nodes:
        nodes_ok = True
    facts_ok = True
    if aid in inputs.measured:
        value["measured"] = inputs.measured[aid]
        facts_ok = _facts_hold(inputs.measured[aid])
    extra_ok = True
    if aid == "A02" or aid in ("A38", "A39", "A40"):
        value["crosscheck"] = inputs.crosscheck
        extra_ok = inputs.crosscheck["exit_code"] == 0
    if aid == "A37":
        value["idaes_rerun"] = inputs.idaes
        extra_ok = inputs.idaes["exit_code"] == 0 and inputs.idaes["numbers_identical"]
    if aid == "A33":
        value["frozen_paths_diff"] = inputs.frozen_diff
        value["gate"] = inputs.gate_summary
        extra_ok = inputs.frozen_diff["unordered_edits"] == [] and inputs.gate_passed
    if aid == "A34":
        value["generator"] = inputs.generator
        extra_ok = inputs.generator["exit_code"] == 0 and inputs.generator["claims"] == 88
    entry: dict[str, Any] = {"id": f"M01.{aid}", "description": _description(aid)}
    if aid == "A47":
        entry["result"] = "not_applicable"
        entry["description"] += (
            " — Not M01's to run: the adapter half is M02's and A47 has no record half (spec "
            "§8.14, §8.15; R-200). Recorded so the hand-off is visible; not in §13's catalogue."
        )
    else:
        entry["result"] = "pass" if nodes_ok and facts_ok and extra_ok else "fail"
    entry["value"] = value
    return entry


def status(
    checks: Sequence[Mapping[str, Any]], commands: Sequence[Mapping[str, Any]], gate: bool
) -> str:
    allowed = {"M01.A47": "not_applicable"}
    every = all(c["result"] == allowed.get(c["id"], "pass") for c in checks)
    return (
        "tested"
        if every and gate and all(c["exit_code"] == 0 for c in commands)
        else ("implemented")
    )


# ----------------------------------------------------------------------------- main


def _frozen_diff(base: str, commit: str) -> dict[str, Any]:
    changed = _git("diff", "--name-only", base, commit, "--", *FROZEN).split()
    return {
        "base": base,
        "commit": commit,
        "paths": list(FROZEN),
        "changed": changed,
        "ordered_by_the_spec": [p for p in changed if p in ORDERED_EDITS],
        "unordered_edits": [p for p in changed if p not in ORDERED_EDITS],
        "note": "support_envelope.yaml: the property_model axis lists pr-c1-v1 (T08.A20 holds the "
        "axes to the code) and L40's text admits M01's five vetted records (spec §3.5, R-158); "
        "no registered value moves",
    }


def _foreign_env() -> dict[str, str]:
    """The environment for an interpreter that is not the project's: no PYTHONPATH, which would
    put `src/openflowsheet.egg-info` into its `pip freeze` (and so into the IDAES record's
    `pip_freeze_sha256`)."""
    return {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}


def _idaes(python: Path, data: Path | None, artifacts: Path) -> tuple[dict[str, Any], Any]:
    out = artifacts / "idaes-conformance.json"
    env = _foreign_env()
    if data is not None:
        env["IDAES_DATA"] = str(data)
    _, command = _run(
        [str(python), "-I", "benchmarks/m01/idaes_conformance.py", "--out", str(out)],
        artifacts / "idaes-conformance.stdout.txt",
        ".venv-idaes/bin/python -I benchmarks/m01/idaes_conformance.py --out "
        "ARTIFACTS/idaes-conformance.json",
        env,
    )
    if command["exit_code"] != 0:
        return {"exit_code": command["exit_code"], "numbers_identical": False}, command
    committed = json.loads(IDAES_RECORD.read_text(encoding="utf-8"))
    rerun = json.loads(out.read_text(encoding="utf-8"))
    differing = sorted(_differences(committed, rerun))
    # The one input hash Amendment 1 moved (reference_values.yaml gained assertion_margins; its
    # closed_form, which the record transcribes, is unchanged) is reported, not ignored.
    expected_only = ["inputs.reference_values_yaml_sha256"]
    return {
        "exit_code": 0,
        "rerun_sha256": _sha256(out),
        "committed_sha256": _sha256(IDAES_RECORD),
        "differing_members": differing,
        "numbers_identical": differing in ([], expected_only),
        "note": "every member of the re-run equals the committed record except, if listed, the "
        "input hash of reference_values.yaml, which Amendment 1 changed outside closed_form",
    }, command


def _differences(a: Any, b: Any, path: str = "") -> Iterator[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            yield from _differences(a.get(key), b.get(key), f"{path}.{key}" if path else key)
    elif a != b:
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--gate-log", required=True, type=Path)
    parser.add_argument("--crosscheck-python", required=True, type=Path)
    parser.add_argument("--idaes-python", required=True, type=Path)
    parser.add_argument("--idaes-data", type=Path, default=None)
    parser.add_argument("--base", default=None, help="the branch base for A33 (default: merge-base")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = arguments.commit
    if _git("rev-parse", "HEAD").strip() != commit or _git(
        "status", "--porcelain", "--", "src", "tests", "benchmarks", "docs/derivations", "scripts"
    ):
        raise SystemExit(f"run at a clean checkout of {commit}: the code under test must be C's")
    ids = catalogue()
    expected = [f"A{n:02d}" for n in range(1, 53)]
    if ids != expected:
        raise SystemExit(f"spec §9's assertions are {ids}, not A01-A52")
    if not set(MEASUREMENTS) <= set(ids):
        raise SystemExit(f"measurements without an assertion: {set(MEASUREMENTS) - set(ids)}")

    destination = arguments.out or (ROOT / "evidence" / "M01" / commit / "manifest.json")
    artifacts = destination.parent / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    gate_text = arguments.gate_log.read_text(encoding="utf-8")
    verdicts = [line for line in gate_text.splitlines() if line.startswith("=== check.sh: ")]
    gate_passed = verdicts[-1:] == ["=== check.sh: PASSED ==="]
    summary = re.findall(r"^(\d+ passed.*) in [\d.]+s", gate_text, re.MULTILINE)
    gate_summary = f"check.sh {'PASSED' if gate_passed else 'FAILED'}; pytest: "
    gate_summary += summary[-1] if summary else "no summary line"

    tests, test_command = run_tests(artifacts)
    completed, generator_command = _run(
        [sys.executable, "docs/derivations/scripts/m01_reference.py", "--check"],
        artifacts / "m01-reference-check.stdout.txt",
        "PYTHONPATH=src .venv/bin/python docs/derivations/scripts/m01_reference.py --check",
        {**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    claims = re.search(r"^(\d+) claims hold", completed.stdout, re.MULTILINE)
    generator = {
        "exit_code": completed.returncode,
        "claims": int(claims[1]) if claims else None,
        "last_line": completed.stdout.strip().splitlines()[-1] if completed.stdout else "",
    }
    completed, crosscheck_command = _run(
        [
            str(arguments.crosscheck_python),
            "-I",
            "benchmarks/m01/external_crosscheck.py",
            "--check",
        ],
        artifacts / "external-crosscheck-check.stdout.txt",
        "VENV/bin/python -I benchmarks/m01/external_crosscheck.py --check  (VENV: chemicals 1.5.2, "
        "thermo 0.6.1, CoolProp 8.0.0, cantera 3.2.0, pyyaml 6.0.2; the script's pins)",
        _foreign_env(),
    )
    crosscheck = {
        "exit_code": completed.returncode,
        "output": completed.stdout.strip(),
        "record_sha256": _sha256(CROSSCHECK),
    }
    idaes, idaes_command = _idaes(arguments.idaes_python, arguments.idaes_data, artifacts)
    base = arguments.base or _git("merge-base", commit, "main").strip()

    inputs = Inputs(
        commit=commit,
        tests=tests,
        gate_passed=gate_passed,
        gate_summary=gate_summary,
        generator=generator,
        crosscheck=crosscheck,
        idaes=idaes,
        frozen_diff=_frozen_diff(base, commit),
        measured={aid: measure() for aid, measure in MEASUREMENTS.items()},
    )
    checks = [check(aid, inputs) for aid in ids]
    checks.append(
        {
            "id": "M01.gate",
            "description": "M01 spec §13: `./scripts/check.sh` green at C, with M01.A01, A03-A36 "
            "and A49-A52 among its tests.",
            "result": "pass" if gate_passed else "fail",
            "value": gate_summary,
        }
    )
    commands = [
        {
            "cmd": "PYTHONPATH=src PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate_passed else 1,
            "stdout_sha256": _sha256(arguments.gate_log),
        },
        test_command,
        generator_command,
        crosscheck_command,
        idaes_command,
        {
            "cmd": f"git diff --name-only {base} {commit} -- {' '.join(FROZEN)}",
            "cwd": ".",
            "exit_code": 0,
        },
    ]
    manifest = build(commit, checks, commands, status(checks, commands, gate_passed))
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    counts = {r: sum(c["result"] == r for c in checks) for r in RESULTS}
    print(f"wrote {destination}: status {manifest['status']}")
    print(", ".join(f"{n} {r}" for r, n in counts.items()))
    failed = [c["id"] for c in checks if c["result"] == "fail"]
    if failed:
        print("FAILED:", ", ".join(failed))
    tight = [
        f"{c['id']} {name}: {bound['value']:.3g} vs {bound['tolerance']:.3g}, "
        f"margin {bound['margin']}"
        for c in checks
        for name, bound in (c.get("value", {}).get("measured") or {}).items()
        if isinstance(bound, Mapping)
        and "margin" in bound
        and isinstance(bound["margin"], float)
        and bound["margin"] < 10.0
    ]
    if tight:
        print("within 10x of the bound:\n  " + "\n  ".join(tight))
    return 1 if failed else 0


def _artifact(path: str, description: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path), "description": description}


def build(
    commit: str, checks: list[dict[str, Any]], commands: list[dict[str, Any]], verdict: str
) -> dict[str, Any]:
    probe_commit = _git(
        "log", "-1", "--format=%H", "--", "benchmarks/m01/reactor-probe.json"
    ).strip()
    return {
        "work_package": "M01",
        "commit": commit,
        "requirements": list(REQUIREMENTS),
        "status": verdict,
        "inputs": {
            "case_id": "M01 registered states (V1-V5, L1, L2, U1-U6, F1-F14), the stand-in at "
            "V1's inlet, the projection's registered perturbation, the IDAES and CoolProp records, "
            "the reactor probe record v2",
            "case_hash": _sha256(REFERENCE),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [
            _artifact("docs/derivations/M01-spec.md", "The specification, Amendment 1 included."),
            _artifact("benchmarks/m01/components.yaml", "The five C1 records (A01, A03)."),
            _artifact(
                "benchmarks/m01/reference_values.yaml", "The generator's 50-digit expectations."
            ),
            _artifact(
                "benchmarks/m01/external-crosscheck.json",
                "Retrieval equality and W22 (A02, A38-A40).",
            ),
            _artifact("benchmarks/m01/idaes-conformance.json", "IDAES 2.13 conformance (A37)."),
            _artifact(
                "benchmarks/m01/reactor-probe.json",
                f"The probe record v2 (A41-A46, A48, A52), last written at {probe_commit}.",
            ),
            _artifact(
                "benchmarks/m01/reactor-overlay.json", "The five-species overlay rows (§8.6)."
            ),
            _artifact("src/openflowsheet/thermo/pr_c1.py", "The provider pr-c1-v1."),
            _artifact("src/openflowsheet/models/c1/boundary.py", "The reactor boundary."),
            _artifact("src/openflowsheet/models/c1/reactor_standin.py", "The synthetic stand-in."),
        ],
        "limitations": [
            "W21 and W22 are v0.2 requirement ids the manifest schema's `requirements` pattern "
            "([DA]nn) cannot carry; this evidence bears on both, and their verdicts are the "
            "`verdict` lane's, not this manifest's.",
            "The reactor is not run here: A41-A46 and A48 are checked as the probe record's halves "
            f"(spec §8.15, M01.A52) on the record last written at {probe_commit}, whose bytes A34 "
            "pins. reactor_probe.py was not re-run for this manifest. The adapter halves of "
            "A41-A48, including all of A47, are M02's (R-200).",
            "The stand-in c1.reactor_standin is synthetic: A25-A32 and A49-A51 certify the "
            "boundary code, never the reactor (spec §8.13, R-199).",
            "W22 is validated for pure-component behaviour only (A38-A40, spec §11); there is no "
            "mixture VLE validation, and k_ij = 0.",
            "The probe record's numbers come from one machine and one environment. Two record "
            "values sit within 10x of their bounds by the spec's own registration: A45's element "
            "defect at the design grid (2.66e-8 against 1e-7; the refusal threshold 1e-6 is 37x "
            "above it) and A52's mapping of the recorded n (1 ulp against 2). Both are constants "
            "of a committed record, not computations the gate repeats.",
            "Human numerical and process-modeling review remain `pending`; `reviewed` is never "
            "self-set.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


if __name__ == "__main__":
    raise SystemExit(main())
