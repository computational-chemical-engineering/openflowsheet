"""ADR 0076 I-15: forced refusals of the region's admissibility test, per raiser and path.

The region (`orchestrator.region`, K03 §8.2) raises a refusal from three places: the ideal-K
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

import logging
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
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
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.region import (
    LiftedSplit,
    _LiftedOps,
    _screen,
    admissibility_value,
)
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.studies.nlp.revision_host import DecisionMap, RevisionNlpHost, decision_map
from openflowsheet.thermo import PropertyRequest, PropertyResult
from openflowsheet.thermo.pr_c1 import COMPONENTS as PR_C1_COMPONENTS
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.syn001 import Syn001Provider, _flash_failure
from openflowsheet.verify.certificate import CheckPolicy

CONTEXT = EvaluationContext(model_version="S19-I15@" + "0" * 64, constants_sha256="0" * 64)
#: `_LiftedOps.converged` reads the policy's `admissibility_epsilon` only.
POLICY_EPSILON = SolvePolicy(policy_id="s19-i15", residual_tolerances={}, scales={})


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
    with pytest.raises(RuntimeError) as refused:
        _converge(raiser)
    assert str(refused.value) == text


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
