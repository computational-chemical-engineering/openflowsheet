"""The surrogate study: a registered plan through M02's experiment runner, then the evidence (M04
spec §5, §6, §7, §10.3; ADR 0036).

`run_study(runner, variant, plan_id, max_cold_experiments)` is the body of the `surrogate_study`
job operation, and the library entry point a test uses with an injected backend:

1. **The plan, refused before anything runs** (spec §5.1, §10.3, M04.A03). The registered plan
   for the parent (`it1-prefix` only for a synthetic one), every request inside the reference box,
   the parent's hard domain and the data domain, none repeated; else `PlanRefusedError`.
2. **The budget, refused before anything runs** (spec §5.4, M04.A20). Every request's key is
   computed (the job's handshake runs once, R-236) and the cache misses counted; more misses than
   `max_cold_experiments` ends the study INSUFFICIENT_EVIDENCE (`budget_below_plan`) with no
   experiment record written and no manifest. A plan is never truncated to fit a budget.
3. **The experiments, one by one, cache first** (spec §10.3; N5's default, sequential): every
   request of the plan in plan order through `ExperimentRunner.run`, whatever the earlier outcomes
   — a running plan is never stopped early on the strength of interim results.
4. **The evidence** (`evaluate`): the fit of the `ok` training draws, the joint scores of the
   calibration and test draws with a failed draw at +∞ (kept in n and m, R-244), the band, the
   coverage test, the admissibility of every calibration and test prediction, the gradient check,
   the parent's `extrapolated` flags, and the verdict function of spec §7.3.
5. **The records** (`manifest`): the SurrogateManifest and the ModelEvidence, whose content is a
   function of the records alone, so that with every record cached the manifest is bitwise the
   same (M04.A32).

A draw whose experiment has no deterministic result (a transient failure beyond M02's retries,
spec §5.3's last row) makes the plan incomplete: the verdict is INSUFFICIENT_EVIDENCE
(`plan_incomplete`) and the draw is named in its split's `incomplete` list. Its score is recorded
as `null`, like a failure's, so the stored scores still determine the recorded band; the verdict
does not rest on them.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.adapters.experiments.runner import ExperimentOutcome, ExperimentRunner
from openflowsheet.adapters.variants import Variant, hard_domain
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import data_domain_violations, hard_domain_violations
from openflowsheet.studies.surrogate.conformal import (
    WIDTH_DT_K,
    WIDTH_X,
    StudyEvidence,
    StudyVerdict,
    Verdict,
    score,
    study_verdict,
)
from openflowsheet.studies.surrogate.plan import (
    PLAN_N_TUBES,
    SamplePlan,
    Split,
    check_plan,
    coordinates,
    registered_plan,
    scaled,
)
from openflowsheet.studies.surrogate.quadratic import (
    QuadraticFit,
    QuadraticSurrogate,
    fit_quadratic,
    inadmissible_outputs,
)
from openflowsheet.thermo import StreamState

__all__ = [
    "MODEL_ID",
    "CentreEvidence",
    "Observation",
    "StudyOutcome",
    "SurrogateEvaluation",
    "evaluate",
    "observe",
    "prepare",
    "run_study",
    "surrogate_id",
]

#: The surrogate unit's model id (spec §8.1).
MODEL_ID: Final = "c1.reactor_surrogate"
_N2: Final = 1

ObservationStatus = Literal["ok", "failed", "incomplete"]
CentreStatus = Literal["ok", "parent_failed", "incomplete", "not_evaluated"]


def surrogate_id(variant: Variant, plan_id: str) -> str:
    """`m04q7-<parent variant id>-<plan id>` (spec §8.2)."""
    return f"m04q7-{variant.variant_id}-{plan_id}"


# -- one request's outcome -------------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    """What the study reads from one experiment of the plan.

    `ok`: a deterministic `ok` result, with X = ξ/n_N2,in and ΔT = T_out − T_in (M02's coupling
    coordinates, ADR 0034 D1). `failed`: a deterministic result that is not `ok` (refused, not
    converged, not accepted) — scored +∞, never fitted. `incomplete`: no deterministic result.
    `status`/`code` are the reactor envelope's; `fingerprint_sha256` the result's environment.
    """

    label: str
    key: str
    request: StreamState
    status: ObservationStatus
    envelope_status: str
    code: str
    x: float | None
    dt: float | None
    extrapolated: bool
    fingerprint_sha256: str | None

    @property
    def z(self) -> tuple[float, ...]:
        u = coordinates(self.request, PLAN_N_TUBES)
        assert u is not None  # every plan request has a defined input map (the plan guard)
        return scaled(u)


def observe(label: str, request: StreamState, outcome: ExperimentOutcome) -> Observation:
    """The observation of one plan request from its runner outcome (served or written)."""
    if outcome.result is None:
        envelope = outcome.envelope
        return Observation(
            label,
            outcome.key,
            request,
            "incomplete",
            str(envelope["status"]),
            str(envelope["code"]),
            None,
            None,
            False,
            None,
        )
    result = outcome.result
    envelope = result["envelope"]
    fingerprint = str(result["provenance"]["fingerprint_sha256"])
    if envelope["status"] != "ok":
        return Observation(
            label,
            outcome.key,
            request,
            "failed",
            str(envelope["status"]),
            str(envelope["code"]),
            None,
            None,
            False,
            fingerprint,
        )
    # A stored record spells an integral binary64 as an integer (ADR 0002): read it as the float.
    x = float(envelope["xi"]) / request.n[_N2]
    dt = float(envelope["outlet"]["T"]) - request.temperature
    return Observation(
        label,
        outcome.key,
        request,
        "ok",
        "ok",
        str(envelope["code"]),
        x,
        dt,
        envelope["domain_status"] == "extrapolated",
        fingerprint,
    )


# -- the evidence ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class CentreEvidence:
    """One gradient centre (spec §7.2): its stencil observations and, when every stencil
    experiment is `ok` and a predictor exists, the errors e_X and e_ΔT."""

    index: int
    status: CentreStatus
    stencil: tuple[Observation, ...]
    errors: tuple[float, float] | None


@dataclass(frozen=True)
class SurrogateEvaluation:
    """Everything the records hold about a completed plan, and the verdict (spec §7)."""

    plan: SamplePlan
    observations: Mapping[Split, tuple[Observation, ...]]
    fit: QuadraticFit
    calibration_scores: tuple[float | None, ...]
    test_scores: tuple[float | None, ...]
    #: |e_X| and |e_ΔT| of the `ok` test draws, in plan order (reported, not judged; spec §7.1).
    test_errors: tuple[tuple[float, float], ...]
    inadmissible: int
    extrapolated: int
    centres: tuple[CentreEvidence, ...]
    verdict: StudyVerdict


def _gradient_errors(
    surrogate: QuadraticSurrogate, centre_z: Sequence[float], stencil: Sequence[Observation]
) -> tuple[float, float]:
    """e_o = ‖∇_z f̃_o(z_c) − D_o‖₂ / max(‖D_o‖₂, w_o), D_o,k the parent's central difference in z
    with z recomputed from the stencil requests (spec §7.2); stencil order is (+, −) per k."""
    gradients = surrogate.gradient(centre_z)
    errors = []
    for o, (gradient, width) in enumerate(zip(gradients, (WIDTH_X, WIDTH_DT_K), strict=True)):
        difference = []
        for k in range(len(centre_z)):
            plus, minus = stencil[2 * k], stencil[2 * k + 1]
            f_plus = plus.x if o == 0 else plus.dt
            f_minus = minus.x if o == 0 else minus.dt
            assert f_plus is not None and f_minus is not None
            difference.append((f_plus - f_minus) / (plus.z[k] - minus.z[k]))
        misfit = math.sqrt(
            math.fsum((g - d) ** 2 for g, d in zip(gradient, difference, strict=True))
        )
        norm = math.sqrt(math.fsum(d * d for d in difference))
        errors.append(misfit / max(norm, width))
    return errors[0], errors[1]


def evaluate(
    plan: SamplePlan, observations: Mapping[Split, Sequence[Observation]]
) -> SurrogateEvaluation:
    """The fit, the scores, the gradient check and the verdict of a run plan (spec §3.4, §6, §7).

    `observations` holds every request of the plan in plan order: one per draw of the training,
    calibration and test splits, and 14 per gradient centre (`SamplePlan.requests`' order).
    """
    rows = {split: tuple(found) for split, found in observations.items()}
    expected = plan.counts
    for split in ("training", "calibration", "test"):
        if len(rows[split]) != expected[split]:
            raise ValueError(
                f"{split}: {len(rows[split])} observations for {expected[split]} draws"
            )
    stencils = len(plan.gradient[0].stencil) if plan.gradient else 0
    if len(rows["gradient"]) != stencils * len(plan.gradient):
        raise ValueError("gradient: one observation per stencil experiment")

    training = [o for o in rows["training"] if o.status == "ok"]
    fit = fit_quadratic(
        [o.z for o in training],
        [o.x for o in training if o.x is not None],
        [o.dt for o in training if o.dt is not None],
    )
    surrogate = fit.surrogate

    def scored(found: Sequence[Observation]) -> tuple[tuple[float | None, ...], int]:
        scores: list[float | None] = []
        inadmissible = 0
        for o in found:
            if surrogate is None:
                scores.append(None)
                continue
            u = coordinates(o.request, PLAN_N_TUBES)
            assert u is not None
            x_hat, dt_hat = surrogate.predict(scaled(u))
            # Every calibration and test prediction is judged, whatever the parent returned
            # (spec §7.1 item 6): an inadmissible prediction in the box is the predictor's defect.
            inadmissible += bool(inadmissible_outputs(x_hat, dt_hat, u[2]))
            if o.status == "ok" and o.x is not None and o.dt is not None:
                scores.append(score(o.x, o.dt, x_hat, dt_hat))
            else:
                scores.append(None)
        return tuple(scores), inadmissible

    calibration_scores, bad_calibration = scored(rows["calibration"])
    test_scores, bad_test = scored(rows["test"])
    test_errors: tuple[tuple[float, float], ...] = ()
    if surrogate is not None:
        test_errors = tuple(
            (abs(o.x - x_hat), abs(o.dt - dt_hat))
            for o in rows["test"]
            if o.status == "ok" and o.x is not None and o.dt is not None
            for x_hat, dt_hat in (surrogate.predict(o.z),)
        )

    centres = []
    width = len(plan.gradient[0].stencil) if plan.gradient else 0
    for j, centre in enumerate(plan.gradient):
        stencil = rows["gradient"][j * width : (j + 1) * width]
        status: CentreStatus
        errors = None
        if any(o.status == "incomplete" for o in stencil):
            status = "incomplete"
        elif any(o.status == "failed" for o in stencil):
            status = "parent_failed"
        elif surrogate is None:
            status = "not_evaluated"
        else:
            status = "ok"
            u = coordinates(centre.request, PLAN_N_TUBES)
            assert u is not None
            errors = _gradient_errors(surrogate, scaled(u), stencil)
        centres.append(CentreEvidence(centre.index, status, tuple(stencil), errors))

    extrapolated = sum(1 for found in rows.values() for o in found if o.extrapolated)
    plan_complete = all(o.status != "incomplete" for found in rows.values() for o in found)
    gradient_errors = (
        None
        if any(c.errors is None for c in centres)
        else tuple(e for c in centres for e in c.errors or ())
    )
    verdict = study_verdict(
        StudyEvidence(
            budget_ok=True,
            plan_complete=plan_complete,
            training_ok=fit.training_ok,
            singular_value_ratio=fit.singular_value_ratio,
            calibration_scores=calibration_scores,
            test_scores=test_scores,
            gradient_errors=gradient_errors,
            inadmissible=bad_calibration + bad_test,
            extrapolated=extrapolated,
        )
    )
    return SurrogateEvaluation(
        plan=plan,
        observations=rows,
        fit=fit,
        calibration_scores=calibration_scores,
        test_scores=test_scores,
        test_errors=test_errors,
        inadmissible=bad_calibration + bad_test,
        extrapolated=extrapolated,
        centres=tuple(centres),
        verdict=verdict,
    )


# -- the study ------------------------------------------------------------------------------------


def _domain_violations(variant: Variant) -> Callable[[StreamState], list[str]]:
    """The parent's hard domain (the variant's, with its per-tube flow bound) and the kinetics'
    data domain (M01's, which `adapters.experiments` requires the variant to declare)."""
    domain = hard_domain(variant)

    def violations(state: StreamState) -> list[str]:
        found = hard_domain_violations(state, domain, PLAN_N_TUBES)
        found.extend(f"outside the data domain in {name}" for name in data_domain_violations(state))
        return found

    return violations


def prepare(variant: Variant, plan_id: str, plan: SamplePlan | None = None) -> SamplePlan:
    """The registered plan `plan_id` for `variant`, checked; `PlanRefusedError` before anything
    runs (spec §5.1, §10.3). `plan` replaces the registered plan for a test of the guard."""
    registered = registered_plan(plan_id, synthetic_parent=variant.synthetic)
    chosen = registered if plan is None else plan
    check_plan(chosen, _domain_violations(variant))
    return chosen


@dataclass(frozen=True)
class StudyOutcome:
    """What a study produced: the verdict and both reason lists, the evaluation and the two
    records (`None` for a budget refusal, which runs and records nothing), and how many plan
    experiments were executed (`cold_experiments`) or served by the cache (`cache_hits`)."""

    verdict: Verdict
    insufficient: tuple[str, ...]
    not_promotable: tuple[str, ...]
    surrogate_id: str
    evaluation: SurrogateEvaluation | None
    manifest: Mapping[str, Any] | None
    evidence: Mapping[str, Any] | None
    cold_experiments: int
    cache_hits: int
    #: The cache misses counted at study start (spec §5.4).
    cache_misses: int


def run_study(
    runner: ExperimentRunner,
    variant: Variant,
    plan_id: str,
    max_cold_experiments: int,
    *,
    plan: SamplePlan | None = None,
    between: Callable[[], None] | None = None,
) -> StudyOutcome:
    """Run the study (module docstring). `PlanRefusedError` when the plan may not run.

    `between` is called before every experiment (a job's cancellation check): what it raises
    propagates, with every record written so far kept."""
    from openflowsheet.studies.surrogate.manifest import build_records

    if max_cold_experiments < 0:
        raise ValueError(f"max_cold_experiments = {max_cold_experiments} is negative")
    chosen = prepare(variant, plan_id, plan)
    identifier = surrogate_id(variant, plan_id)
    labelled = chosen.requests()
    keys = [
        str(runner.request(variant, state, COMPONENTS, PLAN_N_TUBES)["experiment_key"])
        for _, state in labelled
    ]
    misses = sum(1 for key in keys if runner.records.result(key) is None)
    if misses > max_cold_experiments:
        refused = study_verdict(
            StudyEvidence(
                budget_ok=False,
                plan_complete=False,
                training_ok=0,
                singular_value_ratio=None,
                calibration_scores=(),
                test_scores=(),
                gradient_errors=None,
                inadmissible=0,
                extrapolated=0,
            )
        )
        return StudyOutcome(
            refused.verdict,
            refused.insufficient,
            refused.not_promotable,
            identifier,
            None,
            None,
            None,
            0,
            0,
            misses,
        )

    observations: dict[Split, list[Observation]] = {
        "training": [],
        "calibration": [],
        "test": [],
        "gradient": [],
    }
    cold = hits = 0
    for (label, state), key in zip(labelled, keys, strict=True):
        if between is not None:
            between()
        outcome = runner.run(variant, state, COMPONENTS, PLAN_N_TUBES)
        if outcome.key != key:  # the same runner, variant and inlet: one identity (ADR 0033)
            raise RuntimeError(f"{label}: the run's key {outcome.key} is not the counted {key}")
        if outcome.cache_hit:
            hits += 1
        else:
            cold += 1
        split: Split = label.split("[", 1)[0]  # type: ignore[assignment]
        observations[split].append(observe(label, state, outcome))
    evaluation = evaluate(chosen, observations)
    manifest, evidence = build_records(variant, plan_id, identifier, evaluation)
    return StudyOutcome(
        evaluation.verdict.verdict,
        evaluation.verdict.insufficient,
        evaluation.verdict.not_promotable,
        identifier,
        evaluation,
        manifest,
        evidence,
        cold,
        hits,
        misses,
    )
