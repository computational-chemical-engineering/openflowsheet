"""M02 WO-14 (design note §14.5): D9's `at_coupling` guard (AC-1), D7's reproducibility class and
D8's coupled replay digests.

- AC-1 (D9, R-309): `coupled_run.at_coupling(binding, w)` raises `ValueError` naming every key of
  `w`, sorted, that is not the `unit_id` of a `C1Reactor` of the binding — another unit's id or no
  unit's — and changes nothing; the binding's own reactor ids are accepted, and the values reach
  the rebuilt unit as passed (no coercion).
- D7 (R-307): R3 iff the run's provider is in `run.session.EXTERNAL_PROVIDERS` (empty today),
  never from provenance text: SYN-001 → R1; a C1 `revision_eo` run → R1; the stand-in coupled run
  → R1; a provider whose provenance says "external" and which is not in the set → R1 (and R3 once
  registered). The synthetic out-of-process coupled run → R3 is
  `tests/test_m02_wo10_coupled.py::test_r3_an_out_of_process_coupled_run_is_r3_and_its_checks_say_so`.
- D8 (R-308), on the stand-in loop (G8 (a)/(d)'s revision): RP-1, rebuilding the final inner model
  at the record's final w reproduces the recorded `constants_sha256`; RP-2, a rerun whose final w
  is one ulp off (a test seam on the driver's clip) is `MATCH` with `bitwise_floats: false`, its
  constants digest differing, and its certificate VERIFIED (R-317 (a): the EXT-COUPLING checks
  read the request recomputed at the rerun's inlet); RP-3, a bundle whose recorded final w is one
  ulp from the w its digest was computed at (a test seam on the inner solve's w) is `MISMATCH`
  `coupling_constants`. Item
  3's `coupling_iterate(<k>)` and item 1's shape rule are checked on their own.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    at_coupling,
    envelope_differences,
    external_units,
    final_constants,
    iterate_differences,
    record_differences,
)
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import (
    Route,
    _constants_for_shape,
    reproduce_bundle,
    run_revision_session,
    select_route,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator import coupling
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.run import session
from openflowsheet.run.bundle import read_artifact, read_manifest
from openflowsheet.run.compare import CURRENT_POLICY_ID
from openflowsheet.run.session import EXTERNAL_PROVIDERS, _reproducibility_class
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import CheckPolicy

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
HEATER_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-heater.json"


def binding() -> Any:
    route = select_route(json.loads(LOOP_PATH.read_text(encoding="utf-8")))
    assert isinstance(route, Route)
    return route.binding


# == D9: at_coupling refuses unknown unit ids (AC-1) ===============================================


def test_ac1_at_coupling_refuses_every_key_that_is_not_a_reactor_of_the_binding() -> None:
    bound = binding()
    (reactor,) = external_units(bound)
    other = next(m.unit_id for m in bound.flowsheet.instances if not isinstance(m, C1Reactor))
    w = {"zz-nowhere": (0.2, 1.0), reactor.unit_id: (0.25, 0.0), other: (0.2, 1.0)}
    with pytest.raises(ValueError) as raised:
        at_coupling(bound, w)
    named = sorted(["zz-nowhere", other])
    assert str(raised.value) == (
        "not an embedded C1 reactor of this flowsheet: " + ", ".join(map(repr, named))
    )
    with pytest.raises(ValueError, match="'R'"):
        at_coupling(bound, {"R": (0.25, 0.0)})


def test_ac1_at_coupling_accepts_the_bindings_reactors_and_passes_the_floats_through() -> None:
    bound = binding()
    (reactor,) = external_units(bound)
    x = math.nextafter(0.25, 1.0)
    moved = at_coupling(bound, {reactor.unit_id: (x, -0.0)})
    (unit,) = external_units(moved)
    assert unit.conversion is x
    assert math.copysign(1.0, unit.temperature_rise) == -1.0  # −0.0 kept, bit for bit
    assert declaration_identity(at_coupling(bound, {}).spec) == declaration_identity(bound.spec)


# == D7: the reproducibility class from a registered set (R-307) =================================


def solved(path: Path, directory: Path, experiments: Any = None) -> Any:
    document = json.loads(path.read_text(encoding="utf-8"))
    route = select_route(document)
    assert isinstance(route, Route)
    manifest = run_revision_session(
        route,
        document,
        directory / "bundle",
        run_id="run-wo14",
        policy=T06_REVISION_V2,
        check_policy=CheckPolicy(),
        policy_requested="default",
        experiments=experiments,
    )
    return route, manifest


class ProvenanceSaysExternal(PrC1Provider):
    """`pr-c1-v1` under another id, whose provenance text contains "external"."""

    def describe(self) -> Any:
        capabilities = super().describe()
        return dataclasses.replace(
            capabilities,
            provider_id="test-external-text",
            data_provenance="evaluated in process; see external-crosscheck.json (external)",
        )


def test_d7_the_registered_set_is_empty_today() -> None:
    assert EXTERNAL_PROVIDERS == frozenset()


def test_d7_syn001_is_r1() -> None:
    assert _reproducibility_class(SimpleNamespace(provider=Syn001Provider())) == "R1"


def test_d7_a_c1_revision_eo_run_is_r1(tmp_path: Path) -> None:
    assert "external" in PrC1Provider().describe().data_provenance.lower()  # the old rule's R3
    route, manifest = solved(HEATER_PATH, tmp_path)
    assert route.solve_path == "revision_eo"
    assert manifest.outcome == "CONVERGED"
    assert manifest.reproducibility_class == "R1"


def live(tmp_path: Path) -> LiveExperiments:
    runner = ExperimentRunner(
        ExperimentStore(tmp_path / "records", ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m02-wo14", constants_sha256="0" * 64),
    )
    return LiveExperiments(runner)


def test_d7_the_stand_in_coupled_run_is_r1(tmp_path: Path) -> None:
    route, manifest = solved(LOOP_PATH, tmp_path, live(tmp_path))
    assert route.solve_path == "revision_coupled"
    assert (manifest.outcome, manifest.reproducibility_class) == ("CONVERGED", "R1")


def test_d7_provenance_text_does_not_make_r3_the_registered_set_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flowsheet = SimpleNamespace(provider=ProvenanceSaysExternal())
    assert "external" in flowsheet.provider.describe().data_provenance
    assert _reproducibility_class(flowsheet) == "R1"
    monkeypatch.setattr(session, "EXTERNAL_PROVIDERS", frozenset({"test-external-text"}))
    assert _reproducibility_class(flowsheet) == "R3"


# == D8: coupled replay digests (R-308) ==========================================================


#: The registered coupling block's X̂ scale (u = X̂ / s_X).
SCALE_X = 0.1


class OneUlpOnTheFirstClip:
    """RP-2's seam: the driver's `np`, whose first `clip` (the step to k = 1) returns X̂'s scaled
    coordinate moved up by the fewest ulps that move X̂ = u s_X (u's grid is coarser than X̂'s, so
    X̂ moves by one or two of its ulps: two at this point); the iteration then runs on from there
    as usual."""

    def __init__(self) -> None:
        self.moved = False

    def __getattr__(self, name: str) -> Any:
        return getattr(np, name)

    def clip(self, *args: Any, **kwargs: Any) -> Any:
        out = np.clip(*args, **kwargs)
        if not self.moved:
            self.moved = True
            out = out.copy()
            target = math.nextafter(float(out[0]) * SCALE_X, math.inf)
            while float(out[0]) * SCALE_X < target:
                out[0] = np.nextafter(out[0], np.inf)
        return out


def reproduced(tmp_path: Path) -> Any:
    return reproduce_bundle(
        tmp_path / "bundle", rerun=True, rerun_directory=tmp_path / "rerun", run_id="run-rerun"
    )


def test_rp1_the_recomputed_final_constants_equal_the_recorded(tmp_path: Path) -> None:
    route, manifest = solved(LOOP_PATH, tmp_path, live(tmp_path))
    record = read_artifact(tmp_path / "bundle", "external-coupling.json")
    pair = final_constants(route.binding, record)
    assert pair is not None
    recorded, recomputed = pair
    assert recomputed == recorded == manifest.constants_sha256
    assert record["iterations"][-1]["w"][0] == pytest.approx(0.25, abs=1e-15)
    report = reproduced(tmp_path).report
    assert (report.verdict, report.bitwise_floats, report.differences) == ("MATCH", True, ())


def test_rp2_a_rerun_one_ulp_off_at_the_final_w_matches_not_bitwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    solved(LOOP_PATH, tmp_path, live(tmp_path))
    record = read_artifact(tmp_path / "bundle", "external-coupling.json")
    monkeypatch.setattr(coupling, "np", OneUlpOnTheFirstClip())
    reproduction = reproduced(tmp_path)
    report = reproduction.report
    # R-317 (a): the EXT-COUPLING checks compare the rerun's inlet with the request recomputed
    # there, so the certificate stays VERIFIED (was: FAILED, false_success_detected).
    certificate = read_artifact(tmp_path / "rerun", "solution-certificate.json")
    assert certificate["verification_status"] == "VERIFIED"
    assert certificate["false_success_detected"] is False
    checks = [c for c in certificate["checks"] if c["id"].startswith("EXT-COUPLING:")]
    assert len(checks) == 2 and all(c["result"] == "pass" for c in checks)
    # R-317 (b): ρ and r_ξ are floored at their thresholds, the re-evaluated envelope's defects at
    # the molar-flow floor and 1e-6 (they differed: ρ 2.0e-12 vs 0, r_ξ -8.3e-17 vs 0, defect_rel
    # 1.1e-16 vs 2.7e-17; build log D120).
    assert (report.verdict, report.differences) == ("MATCH", ())
    assert report.bitwise_floats is False
    rerun = read_artifact(tmp_path / "rerun", "external-coupling.json")
    (final, recorded) = (rerun["iterations"][-1], record["iterations"][-1])
    assert final["k"] == recorded["k"] == 1
    one_ulp = math.nextafter(recorded["w"][0], math.inf)
    assert final["w"][0] in (one_ulp, math.nextafter(one_ulp, math.inf))  # the last bits
    assert final["w"][1] == recorded["w"][1]
    # The case exercises the old failure: the rerun's digest differs from the record's.
    assert final["inner"]["constants_sha256"] != recorded["inner"]["constants_sha256"]
    assert reproduction.rerun_manifest is not None
    assert (
        reproduction.rerun_manifest.constants_sha256
        != read_manifest(tmp_path / "bundle")[0].constants_sha256
    )


def test_rp3_a_recorded_w_one_ulp_from_its_digests_w_is_coupling_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = coupling._w_of
    calls: list[int] = []

    def moved(u: Any, units: Any, scales: Any) -> Any:
        """The inner solve (and the run's w) one ulp up in X̂ after k = 0; the record's w is
        the driver's own (u times the scales), so it stays where it was."""
        w = real(u, units, scales)
        calls.append(1)
        if len(calls) == 1:
            return w
        return {unit: (math.nextafter(xw, math.inf), dtw) for unit, (xw, dtw) in w.items()}

    with monkeypatch.context() as patch:
        patch.setattr(coupling, "_w_of", moved)
        route, _ = solved(LOOP_PATH, tmp_path, live(tmp_path))
    record = read_artifact(tmp_path / "bundle", "external-coupling.json")
    final = record["iterations"][-1]
    (unit,) = external_units(route.binding)
    x, dt = (float(value) for value in final["w"])
    at_digest = at_coupling(route.binding, {unit.unit_id: (math.nextafter(x, math.inf), dt)})
    assert final["inner"]["constants_sha256"] == declaration_identity(at_digest.spec)[1]
    report = reproduced(tmp_path).report
    assert report.verdict == "MISMATCH"
    found = [entry for entry in report.differences if entry.startswith("coupling_constants:")]
    assert len(found) == 1 and final["inner"]["constants_sha256"] in found[0]


def test_d8_iterates_are_compared_under_the_policy_as_coupling_iterate() -> None:
    recorded = {
        "iterations": [
            {"k": 0, "w": [0.15, 80.0], "u": [1.5, 8.0]},
            {"k": 1, "w": [0.25, 0.0], "u": [2.5, 0.0]},
        ]
    }
    same = {"iterations": [dict(item) for item in recorded["iterations"]]}
    same["iterations"][1] = {**same["iterations"][1], "w": [math.nextafter(0.25, 1.0), 0.0]}
    assert iterate_differences(same, recorded, CURRENT_POLICY_ID) == []
    moved = {"iterations": [dict(item) for item in recorded["iterations"]]}
    moved["iterations"][1] = {**moved["iterations"][1], "u": [2.5 * (1.0 + 1e-6), 0.0]}
    found = iterate_differences(moved, recorded, CURRENT_POLICY_ID)
    assert len(found) == 1 and found[0].startswith("coupling_iterate(1).u")


def test_d8_constants_digests_are_compared_for_shape() -> None:
    archived = {"a": {"constants_sha256": "a" * 64}, "b": [{"constants_sha256": "b" * 64}]}
    fresh = {"a": {"constants_sha256": "c" * 64}, "b": [{"constants_sha256": "not a digest"}]}
    assert _constants_for_shape(fresh, archived) == {
        "a": {"constants_sha256": "a" * 64},
        "b": [{"constants_sha256": "not a digest"}],
    }


# == R-317 (b): the record's floats at their registered floors =====================================


def a_record() -> dict[str, Any]:
    unit = {"inlet": {"n": [3.0, 1.0, 0.0], "T": 673.15, "P": 1e7}, "r_xi": 0.0, "r_T": 0.0}
    unit |= {"n_N2_in": 1.0, "n_tot_in": 4.0, "xi_E": 0.25, "T_E": 673.15}
    return {
        "coupling_block": {"tau_xi_rel": 1e-5, "tau_T_K": 1e-2},
        "iterations": [
            {
                "k": 0,
                "w": [0.15, 80.0],
                "rho": 8000.0,
                "step": {"kind": "broyden", "du": [1.0, -8.0], "B": [[-1.0, 0.0], [0.0, -1.0]]},
                "units": {"reactor": unit},
            }
        ],
    }


def test_r317_rho_r_xi_r_t_and_flows_are_floored_and_the_secant_is_reported() -> None:
    recorded = a_record()
    fresh = a_record()
    item, unit = fresh["iterations"][0], fresh["iterations"][0]["units"]["reactor"]
    item["rho"] = 8000.0 * (1 + 1e-12)  # relative, inside 1e-9
    item["step"] = {"kind": "broyden", "du": [1.5, -7.0], "B": [[-2.0, 0.1], [0.3, -1.0]]}
    unit |= {"r_xi": 9e-6, "r_T": -9e-3, "n_N2_in": 1.0 + 1e-8}
    unit["inlet"]["n"][2] = 3e-8
    shaped, found = record_differences(fresh, recorded, CURRENT_POLICY_ID)
    assert found == []
    assert shaped == recorded  # each floored or reported float taken from the record
    # Outside: ρ by more than 1 near zero, r_ξ by more than τ_ξ, a flow by more than τ_flow;
    # w is relative and left for `replay`.
    unit |= {"r_xi": 2e-5, "n_N2_in": 1.0 + 1e-7}
    item["rho"] = 8001.5
    fresh["iterations"][0]["w"] = [0.15 * (1 + 1e-6), 80.0]
    shaped, found = record_differences(fresh, recorded, CURRENT_POLICY_ID)
    where = sorted(line.split(":")[0] for line in found)
    assert where == [
        "external-coupling.json<root>.iterations[0].rho",
        "external-coupling.json<root>.iterations[0].units.reactor.n_N2_in",
        "external-coupling.json<root>.iterations[0].units.reactor.r_xi",
    ]
    assert "coupling_block.tau_xi_rel" in next(line for line in found if "r_xi" in line)
    assert shaped["iterations"][0]["w"] == fresh["iterations"][0]["w"]
    # A step kind that differs is R0: left for `replay` to compare exactly.
    item["step"]["kind"] = "reset"
    shaped, _ = record_differences(fresh, recorded, CURRENT_POLICY_ID)
    assert shaped["iterations"][0]["step"]["kind"] == "reset"


def test_r317_a_reevaluated_envelope_is_floored_at_its_thresholds() -> None:
    recorded = {"outlet": {"n": [3.0, 0.0], "T": 700.0}, "xi": 0.25, "defect": [0.0, 1e-16]}
    recorded |= {"defect_rel": 2.7e-17}
    fresh = {"outlet": {"n": [3.0, 1e-9], "T": 700.0}, "xi": 0.25, "defect": [4e-16, 0.0]}
    fresh |= {"defect_rel": 9e-7}
    assert envelope_differences(fresh, recorded, CURRENT_POLICY_ID) == []
    fresh |= {"defect_rel": 1.1e-6, "xi": 0.25 * (1 + 1e-6)}
    found = envelope_differences(fresh, recorded, CURRENT_POLICY_ID)
    assert sorted(line.split(":")[0] for line in found) == ["<root>.defect_rel", "<root>.xi"]
