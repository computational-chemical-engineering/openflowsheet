"""M02 WO-14 (design note §14.5): D9's `at_coupling` guard (AC-1) and D7's reproducibility class.

- AC-1 (D9, R-309): `coupled_run.at_coupling(binding, w)` raises `ValueError` naming every key of
  `w`, sorted, that is not the `unit_id` of a `C1Reactor` of the binding — another unit's id or no
  unit's — and changes nothing; the binding's own reactor ids are accepted, and the values reach
  the rebuilt unit as passed (no coercion).
- D7 (R-307): R3 iff the run's provider is in `run.session.EXTERNAL_PROVIDERS` (empty today),
  never from provenance text: SYN-001 → R1; a C1 `revision_eo` run → R1; the stand-in coupled run
  → R1; a provider whose provenance says "external" and which is not in the set → R1 (and R3 once
  registered). The synthetic out-of-process coupled run → R3 is
  `tests/test_m02_wo10_coupled.py::test_r3_an_out_of_process_coupled_run_is_r3_and_its_checks_say_so`.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import LiveExperiments, at_coupling, external_units
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import Route, run_revision_session, select_route
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.run import session
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


def test_d7_the_stand_in_coupled_run_is_r1(tmp_path: Path) -> None:
    runner = ExperimentRunner(
        ExperimentStore(tmp_path / "records", ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m02-wo14", constants_sha256="0" * 64),
    )
    route, manifest = solved(LOOP_PATH, tmp_path, LiveExperiments(runner))
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
