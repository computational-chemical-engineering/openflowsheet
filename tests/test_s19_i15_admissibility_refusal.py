"""ADR 0076 I-15: forced refusals of the region's admissibility test, per raiser and path.

The region (`orchestrator.region_phase`, K03 §8.2) raises a refusal from three places: the ideal-K
evaluation (the provider will not give `lnK`), the gamma-phi kernel (`BandError`) and the
`pr-c1-v1` kernel (`classify` without a regime). Each reaches three paths:

- the screen converts it to an `invalid_trial_state` evaluation with the refusal's text;
- `admissibility_value` returns `None`;
- the converged path (`_LiftedOps.converged`) lets it propagate, and every handler of a route
  solve ends typed: the jobs runner `failed(verifier_refused)`, the trust-region parent the
  outcome `verifier_refused(<text>)`, the NLP host `CERTIFICATE_NOT_VERIFIED` with
  `verifier_refused: <first line>`.

The raisers are forced through the provider (a refusing `lnK`, a temperature outside the records'
domain, a refusing flash), never by patching the region. The route-solve fakes run the real
converged path with the refusing provider, so a handler sees the exception the region raises.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import commit
from test_m05_parent import DECISION, NOMINAL, services_module, standin
from test_opt_revision_host import G4_CASES, POLICY, _box, _document, _unit
from test_s10c_region import CONTEXT as GAMMA_PHI_CONTEXT
from test_s10c_region import PROVIDER as GAMMA_PHI_PROVIDER
from test_s10c_region import SPLIT as GAMMA_PHI_SPLIT
from test_s10c_region import Z, _state

from openflowsheet.application import revision_run
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_routes import ApplicationRevisionRoutes
from openflowsheet.application.revision_run import registered_case, registered_flowsheet
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.lifted import AdmissibilityRefusal
from openflowsheet.numerics.solve_record import SolvePolicy
from openflowsheet.orchestrator.region import (
    LiftedSplit,
    _LiftedOps,
    _reference_k_values,
    _screen,
    admissibility_value,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.studies.nlp.revision_host import DecisionMap, RevisionNlpHost, decision_map
from openflowsheet.studies.trust_region.checks import ParentSolve
from openflowsheet.studies.trust_region.parent import P2_A_SOURCE
from openflowsheet.thermo import PropertyRequest, PropertyResult
from openflowsheet.thermo.pr_c1 import COMPONENTS as PR_C1_COMPONENTS
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.syn001 import Syn001Provider, _flash_failure
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.checks import VerifierError, k_values

CONTEXT = EvaluationContext(model_version="S19-I15@" + "0" * 64, constants_sha256="0" * 64)
#: `_LiftedOps.converged` reads the policy's `admissibility_epsilon` only.
POLICY_EPSILON = SolvePolicy(policy_id="s19-i15", residual_tolerances={}, scales={})
#: M04.A19's PROMOTABLE smooth prefix-plan manifest: stage A's surrogate on the stand-in parent.
A19_MANIFEST = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "schemas"
    / "surrogate_manifest"
    / "valid"
    / "a19_smooth_prefix.json"
)


class _RefusingK(Syn001Provider):
    """SYN-001 whose `lnK` is refused: the ideal-K raiser."""

    def evaluate_phase(self, request: PropertyRequest, context: Any) -> PropertyResult:  # type: ignore[override]
        if request.properties == ("lnK",):
            return PropertyResult(status="out_of_domain", phase_signature=None, values={})
        return super().evaluate_phase(request, context)


class _RefusingFlash(PrC1Provider):
    """`pr-c1-v1` whose TP flash is refused: `classify` answers no regime."""

    def flash(self, request: Any, context: Any) -> Any:  # type: ignore[override]
        del request, context
        return _flash_failure("not_converged", "injected: the kernel's flash")


def _split(unit: str, stream: str, components: tuple[str, ...]) -> LiftedSplit:
    return LiftedSplit(
        unit=unit,
        stream=stream,
        feed=tuple(f"{stream}.n.{c}" for c in components),
        temperature=f"{unit}.T",
        pressure=f"{unit}.P",
        vapor=tuple(f"{unit}.v.{c}" for c in components),
        liquid=tuple(f"{unit}.l.{c}" for c in components),
        vapor_total=f"{unit}.V",
        liquid_total=f"{unit}.L",
        equilibrium_rows=(),
        vapor_definition=f"{unit}.Vdef",
        liquid_definition=f"{unit}.Ldef",
    )


def _liquid(
    split: LiftedSplit, flows: tuple[float, ...], temperature: float, pressure: float
) -> dict[str, float]:
    """A LIQUID branch at the state (`V = 0 < L`): `flows` in the feed and on the liquid side."""
    state = dict(zip(split.feed, flows, strict=True))
    state.update(zip(split.liquid, flows, strict=True))
    state.update(dict.fromkeys(split.vapor, 0.0))
    state[split.vapor_total] = 0.0
    state[split.liquid_total] = sum(flows)
    state[split.temperature] = temperature
    state[split.pressure] = pressure
    return state


IDEAL_SPLIT = _split("F", "S", ("A", "B", "C"))
PR_C1_SPLIT = _split("F", "S", PR_C1_COMPONENTS)


def _gamma_phi_state() -> dict[str, float]:
    state: dict[str, float] = _state("liquid", Z, 250.0)  # outside the records' T domain
    state[GAMMA_PHI_SPLIT.vapor_total] = 0.0
    state[GAMMA_PHI_SPLIT.liquid_total] = sum(Z)
    return state


#: raiser -> (provider, context, split, LIQUID state, today's text of the refusal).
RAISERS: Mapping[
    str, Callable[[], tuple[Any, EvaluationContext, LiftedSplit, dict[str, float], str]]
] = {
    "ideal_k": lambda: (
        _RefusingK(),
        CONTEXT,
        IDEAL_SPLIT,
        _liquid(IDEAL_SPLIT, (1.0, 2.0, 3.0), 350.0, 101325.0),
        "the verifier's own K-values returned out_of_domain",
    ),
    "gamma_phi_band": lambda: (
        GAMMA_PHI_PROVIDER,
        GAMMA_PHI_CONTEXT,
        GAMMA_PHI_SPLIT,
        _gamma_phi_state(),
        "the kernel refused F's regime (S): out_of_domain: ln phi^L at T = 250.0 K: out_of_domain: "
        "temperature 250.0 K outside [300.0, 400.0] K",
    ),
    "pr_c1_classify": lambda: (
        _RefusingFlash(),
        CONTEXT,
        PR_C1_SPLIT,
        _liquid(PR_C1_SPLIT, (0.0, 0.0, 1.0, 0.0, 0.0), 300.0, 2.0e7),
        "the kernel refused F's regime (S): not_converged: injected: the kernel's flash",
    ),
}


def _converge(raiser: str) -> None:
    """The real converged path (`_LiftedOps.converged`, T03 §4.7(a)) at the raiser's state."""
    provider, context, split, state, _ = RAISERS[raiser]()
    ops = _LiftedOps(
        splits=(split,),
        regimes={split.unit: "LIQUID"},
        end_state=state,
        free=(),
        provider=provider,
        context=context,
        policy=POLICY_EPSILON,
        region=None,  # type: ignore[arg-type]  # unread before the admissibility test
        spec=None,  # type: ignore[arg-type]
        identity=("", ""),
    )
    ops.converged(None)  # type: ignore[arg-type]
    raise AssertionError("the forced refusal did not raise")


# -- the screen and admissibility_value ----------------------------------------------------------


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_screen_converts_a_refusal_to_an_invalid_trial_state(raiser: str) -> None:
    provider, context, split, state, text = RAISERS[raiser]()
    screen = _screen(
        splits=(split,),
        regimes={split.unit: "LIQUID"},
        provider=provider,
        context=context,
        epsilon=0.0,
    )
    evaluation = screen(state)
    assert (evaluation.status, evaluation.message) == ("invalid_trial_state", text)  # type: ignore[union-attr]


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_admissibility_value_is_none_under_a_refusal(raiser: str) -> None:
    provider, context, split, state, _ = RAISERS[raiser]()
    assert admissibility_value(provider, context, split, "LIQUID", state) is None


# -- the converged path ----------------------------------------------------------------------------


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_converged_path_lets_a_refusal_propagate(raiser: str) -> None:
    *_, text = RAISERS[raiser]()
    with pytest.raises(AdmissibilityRefusal) as refused:
        _converge(raiser)
    assert str(refused.value) == text


def test_the_refusal_is_a_runtime_error_and_not_the_verifiers() -> None:
    """ADR 0076 I-15: `AdmissibilityRefusal` is a `RuntimeError`, not a `VerifierError` (R-016)."""
    assert AdmissibilityRefusal.__mro__[1] is RuntimeError
    assert not issubclass(AdmissibilityRefusal, VerifierError)
    assert not issubclass(VerifierError, AdmissibilityRefusal)


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "p", project_id="s19-i15")
    try:
        yield application
    finally:
        application.close()


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_jobs_runner_ends_a_converged_refusal_verifier_refused(
    app: LocalApplication,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raiser: str,
) -> None:
    *_, text = RAISERS[raiser]()
    monkeypatch.setattr(revision_run, "execute_plan", lambda *_, **__: _converge(raiser))
    revision_id = commit(app, CORPUS["SYN-001-nominal"]())
    with caplog.at_level(logging.WARNING):
        result = app.solve(revision_id, "default")
    job = app.get_job(result.job_id)
    assert job.ending is not None and (job.status, job.ending.reason) == (
        "failed",
        "verifier_refused",
    )
    assert result.error is not None
    assert (result.error.code, result.error.message) == ("unsupported", "verifier_refused")
    assert result.error.detail["solve_path"] == "revision_eo"
    assert result.error.detail["exception"] == "AdmissibilityRefusal"  # ADR 0076: deliberate
    assert text not in str(result.error.as_document())  # D9 (4): the text goes to the log only
    assert f"verifier refused: {text}" in caplog.messages
    assert result.outputs == () and not (app.files_root / "jobs" / job.job_id / "bundle").exists()


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_trust_region_parent_outcome_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiser: str
) -> None:
    *_, text = RAISERS[raiser]()
    monkeypatch.setattr(services_module, "solve_route", lambda *_, **__: _converge(raiser))
    refused = standin(tmp_path).solve({DECISION: NOMINAL}, solve_id="x", purpose="start")
    assert (refused.outcome, refused.certificate, refused.state) == (
        f"verifier_refused({text})",
        None,
        None,
    )
    assert not refused.certified and refused.executions == 0


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_trust_region_p2_reference_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiser: str
) -> None:
    """Stage A's P2 reference (`C1Parent.surrogate_reference`): the surrogate-backed
    `revision_eo` re-solve selects its route for real and ends `verifier_refused`."""
    solves: list[str] = []

    def refuse(*_: Any, **__: Any) -> None:
        solves.append(raiser)
        _converge(raiser)

    monkeypatch.setattr(services_module, "solve_route", refuse)
    manifest = json.loads(A19_MANIFEST.read_text(encoding="utf-8"))
    reference = standin(tmp_path).surrogate_reference(manifest)
    targeted = ParentSolve(
        solve_id="x",
        purpose="start",
        decisions={DECISION: NOMINAL},
        revision_sha256="",
        outcome="CONVERGED",
        certificate=None,
    )
    refused = reference(targeted)
    assert solves == [raiser]
    assert (refused.source, refused.state) == (f"{P2_A_SOURCE}:verifier_refused", {})
    assert math.isnan(refused.objective)


class _ConvergedRefusal(ApplicationRevisionRoutes):
    """The application's routes, whose solve runs the forced converged path instead."""

    def __init__(self, raiser: str) -> None:
        self.raiser = raiser

    def solve(self, *_: Any, **__: Any) -> Any:  # type: ignore[override]
        _converge(self.raiser)


@pytest.mark.parametrize("raiser", list(RAISERS))
def test_the_nlp_host_outcome_is_unchanged(raiser: str) -> None:
    *_, text = RAISERS[raiser]()
    routes = _ConvergedRefusal(raiser)
    document = _document("TH-R1")
    name = G4_CASES["TH-R1"]
    found = decision_map(document, [_box(document, name, _unit(document, name))], routes=routes)
    assert isinstance(found, DecisionMap), found
    host = RevisionNlpHost(
        document, found, solve_policy=POLICY, check_policy=CheckPolicy(), routes=routes
    )
    (parameter,) = host.decisions.parameters.values()
    point = host.certify({parameter: host.base_spec().parameters[parameter]})
    assert (point.outcome, point.message) == (
        "CERTIFICATE_NOT_VERIFIED",
        f"verifier_refused: {text}",
    )
    assert (point.state, point.certificate) == (None, None)


# -- the ideal-K restatement (after the step) ------------------------------------------------------

#: F0's RC bundle set as written at v0.3.0 (M7's corpus): 52 runs. The 44 revision runs that
#: converged hold their state (`solution-state.json`); the five K05 runs, whose session writes no
#: state, are solved again below; the other three G8 runs (`HOMOTOPY_STALLED`,
#: `INITIALIZATION_FAILED` twice) have no converged state and so no `(T, P)` to pin.
F0_BUNDLES = REPO_ROOT / "tests" / "fixtures" / "f0" / "v0.3.0-bundles"
K05_CASES = sorted(path.name for path in (F0_BUNDLES / "k05").iterdir())


def _f0_temperatures_and_pressures() -> list[tuple[float, float]]:
    """Every stream `(T, P)` in the F0 bundles' solution states, sorted: a superset of the lifted
    splits' `(T, P)` (a split's temperature and pressure are stream variables of the state).
    The K05 runs' lifted splits are pinned by `test_the_k05_k_values_are_the_verifier_k_values`."""
    found: set[tuple[float, float]] = set()
    for path in sorted(F0_BUNDLES.glob("*/*/artifacts/solution-state.json")):
        variables = json.loads(path.read_text(encoding="utf-8"))["variables"]
        for name, value in variables.items():
            pressure = f"{name[:-2]}.P"
            if name.endswith(".T") and pressure in variables:
                found.add((float(value), float(variables[pressure])))
    return sorted(found)


F0_STATES = _f0_temperatures_and_pressures()


def test_the_f0_bundles_hold_states() -> None:
    """The K pin below is not vacuous: 44 bundles with a solution state, 59 distinct `(T, P)`;
    five K05 runs; 52 bundles in all."""
    assert len(list(F0_BUNDLES.glob("*/*/artifacts/solution-state.json"))) == 44
    assert len(F0_STATES) == 59
    assert K05_CASES == [
        "SYN-001-all-liquid-310K",
        "SYN-001-all-vapor-420K",
        "SYN-001-high-recycle",
        "SYN-001-nominal",
        "SYN-001-once-through",
    ]
    assert len(list(F0_BUNDLES.glob("*/*/run-manifest.json"))) == 52


@pytest.mark.parametrize(("temperature", "pressure"), F0_STATES)
def test_the_region_k_values_are_the_verifier_k_values_bitwise(
    temperature: float, pressure: float
) -> None:
    """`_reference_k_values` restates `verify.checks.k_values` (R-016): bitwise equal K at every
    F0 state, by `float.hex`. A converged F0 state is inside SYN-001's domain, so neither side may
    refuse here; the refusals are pinned below."""
    provider = Syn001Provider()
    expected = [value.hex() for value in k_values(provider, temperature, pressure, CONTEXT)]
    found = [value.hex() for value in _reference_k_values(provider, temperature, pressure, CONTEXT)]
    assert found == expected


@pytest.mark.parametrize("case", K05_CASES)
def test_the_k05_k_values_are_the_verifier_k_values(case: str) -> None:
    """The K05 runs reach the ideal-K test through `orchestrator/tear.py`'s lifted splits; their
    bundles hold no state, so the case is solved again as F0 solves it (`run_session`'s
    `solve_tear` under its default policy). The state is the bundle's, bitwise: its hash is the
    certificate's `target_state_sha256`. K is then bitwise equal at every lifted split's
    `(T, P)`."""
    registered = registered_case(case)
    assert registered is not None, case
    flowsheet = registered_flowsheet(registered)
    policy = SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={})
    result, _ = solve_tear(flowsheet, policy=policy)
    certificate = json.loads(
        (F0_BUNDLES / "k05" / case / "artifacts" / "solution-certificate.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.checkpoint is not None
    assert result.checkpoint.full_state_sha256 == certificate["target_state_sha256"]
    state = result.final_state
    assert state is not None
    provider = Syn001Provider()
    for split in syn001_lifted_splits(flowsheet.components):
        temperature, pressure = state[split.temperature], state[split.pressure]
        expected = [value.hex() for value in k_values(provider, temperature, pressure, CONTEXT)]
        found = _reference_k_values(provider, temperature, pressure, CONTEXT)
        assert [value.hex() for value in found] == expected, split.unit


#: provider name -> (provider, T, P) at which both sides refuse.
K_REFUSALS: Mapping[str, Callable[[], tuple[Any, float, float]]] = {
    "syn001_below_t_domain": lambda: (Syn001Provider(), 250.0, 101325.0),
    "syn001_above_p_domain": lambda: (Syn001Provider(), 350.0, 1.0e7),
    "refusing_lnk": lambda: (_RefusingK(), 350.0, 101325.0),
}


@pytest.mark.parametrize("case", list(K_REFUSALS))
def test_a_k_refusal_has_the_verifiers_text(case: str) -> None:
    """Where the verifier's `k_values` raises `VerifierError`, the region's restatement raises
    `AdmissibilityRefusal` with the same text."""
    provider, temperature, pressure = K_REFUSALS[case]()
    with pytest.raises(VerifierError) as verifier:
        k_values(provider, temperature, pressure, CONTEXT)
    with pytest.raises(AdmissibilityRefusal) as region:
        _reference_k_values(provider, temperature, pressure, CONTEXT)
    assert str(region.value) == str(verifier.value)
