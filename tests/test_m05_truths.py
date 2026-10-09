"""M05 WO-4, WO-4a: the truth adapters, the finite-difference policy `M05-fd-v2` and its
gradient-quality check (§17.2's acceptance (i)-(iv)), §16.4's `meta` contract, R-300 E2's guard and
the runner under concurrent distinct keys (design note §6.3-§6.5, §16.4, §17.2, §17.5; ADR 0038
D5; R-262, R-265, R-297, R-300).

Default gate: no Pyomo, no reactor environment. The parent truth runs M02's `ExperimentRunner` on
the shipped stand-in (`standin-x025-v1`) and on the test-only smooth truth
`m05-synthetic-interior-v1` (`tests/support/m05_synthetic.py`), both in process, into a temporary
experiment store.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.trust_region.holders import (
    BASIS_FD_POINT,
    FDCHECK_POINT,
    TRF_FD_POINT,
    TRF_START_VALUE,
    ColdBudget,
    EFHolder,
    RunState,
    TruthBox,
    TruthRefused,
)
from openflowsheet.studies.trust_region.truths import (
    ETA,
    ForwardDifference,
    ParentExperimentTruth,
    fd_workers,
    gradient_check,
    in_process_meta,
    physical_cores,
)
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_synthetic as synthetic  # noqa: E402

CONTEXT = EvaluationContext(model_version="m05-wo4", constants_sha256="0" * 64)
STANDIN = variants.registered_variant("standin-x025-v1")
N_TUBES = 1000.0
#: The C1 loop's reactor inlet at the stand-in's fixed point w* = (0.25, 0 K) (M02 WO-9,
#: `C1-LOOP-M02-v1` at the inner solve's converged state, rounded to registered literals here:
#: the truths only need a flowing inlet inside the hard domain).
INLET = (4.468562874251506, 1.4895209580838327, 0.18966378354114583, 0.1, 0.15, 673.15, 1.0e7)
#: Output scales s_k as the projection gives them for (X, ΔT) ≈ (0.18, 86 K) (§6.1).
SCALES = (0.25, 128.0)


def runner(root: Path) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root), PrC1Provider(), CONTEXT, backend_for=synthetic.backend_for
    )


def standin_truth(root: Path, **options: Any) -> ParentExperimentTruth:
    return ParentExperimentTruth(runner(root), STANDIN, N_TUBES, **options)


def interior_truth(root: Path, **options: Any) -> ParentExperimentTruth:
    return ParentExperimentTruth(runner(root), synthetic.synthetic_variant(), N_TUBES, **options)


def holder_of(truth: Any) -> EFHolder:
    return EFHolder("reactor", TruthBox(truth), SCALES, kind="truth")


def store_files(root: Path) -> Iterator[Path]:
    base = root / "experiments"
    for path in sorted(base.rglob("*")):
        if path.is_file() and "locks" not in path.relative_to(base).parts:
            yield path


# == the meta contract (§16.4) ==================================================================


def test_the_parent_meta_maps_the_experiment_outcome_exactly(tmp_path: Path) -> None:
    truth = standin_truth(tmp_path)
    assert truth.describe() == {
        "kind": "parent_experiment",
        "id": "standin-x025-v1",
        "sha256": STANDIN.sha256,
        "synthetic": True,
        "gradient": "finite_difference",
    }
    conversion, rise, meta = truth.evaluate(INLET)
    outcome = truth.run(INLET)  # the same key again: served by the store
    envelope = outcome.result["envelope"] if outcome.result is not None else None
    assert envelope is not None and envelope["status"] == "ok"
    assert meta == {
        "status": "ok",
        "cache_hit": False,
        "experiment_key": outcome.key,
        "executions": 1,
        "extrapolated": envelope["domain_status"] == "extrapolated",
        "code": envelope["code"],
    }
    # (X, ΔT) are the envelope's projected extent over n_N2,in and its outlet T less T_in.
    assert conversion == envelope["xi"] / INLET[1]
    assert rise == envelope["outlet"]["T"] - INLET[5]
    assert abs(conversion - 0.25) <= 1e-15 and rise == 0.0
    again = truth.evaluate(INLET)[2]
    assert again == {**meta, "cache_hit": True, "executions": 0}
    # Every attempt the store holds is one this truth's metas counted.
    assert len(truth.runner.records.attempts(outcome.key)) == meta["executions"]


def test_a_parent_refusal_is_typed_and_carries_its_meta(tmp_path: Path) -> None:
    """Outside the hard domain the boundary refuses before evaluating: `out_of_domain`, one
    `not_executed` attempt written, which the refusal's meta counts."""
    box = TruthBox(standin_truth(tmp_path))
    hot = (*INLET[:5], 900.0, INLET[6])
    with pytest.raises(TruthRefused) as refused:
        box.values(hot)
    assert (refused.value.status, refused.value.reason) == ("out_of_domain", "out_of_domain")
    meta = refused.value.meta
    assert meta["status"] == "out_of_domain" and meta["executions"] == 1
    attempts = box.truth.runner.records.attempts(meta["experiment_key"])  # type: ignore[attr-defined]
    assert [a["execution"]["status"] for a in attempts] == ["not_executed"]


class InProcessTruth:
    """A cheap in-process truth (a test function, as a surrogate would be): §16.4's fixed meta."""

    finite_difference = None

    def describe(self) -> Mapping[str, Any]:
        return {"kind": "test", "id": "in-process", "sha256": None, "gradient": "analytic"}

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        return 0.2, 80.0, in_process_meta()

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        return [[0.0] * 7, [0.0] * 7]


def test_an_in_process_truth_returns_the_fixed_meta_and_never_counts_against_a_budget() -> None:
    assert in_process_meta() == {
        "status": "ok",
        "cache_hit": False,
        "experiment_key": None,
        "executions": 0,
        "extrapolated": False,
    }
    holder = holder_of(InProcessTruth())
    assert not holder.box.parent  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="never counts against a parent budget"):
        holder.begin_run(RunState("r"), [ColdBudget("study", 10)])
    holder.begin_run(RunState("r"))
    holder.request_values(INLET)
    holder.end_run()
    (entry,) = holder.ledger
    assert (entry.served, entry.experiment_key, entry.executions, entry.extrapolated) == (
        "cold",
        None,
        0,
        False,
    )
    assert holder.truth_identity["kind"] == "test"


def test_the_ledger_records_the_truths_meta_per_request(tmp_path: Path) -> None:
    holder = holder_of(standin_truth(tmp_path))
    holder.begin_run(RunState("r"))
    holder.request_values(INLET)
    holder.request_values(INLET)
    holder.end_run()
    first, second = holder.ledger
    assert first.served == "cold" and first.executions == 1 and first.purpose == TRF_START_VALUE
    assert second.served == "memo_hit" and second.executions == 0 and second.purpose is None
    assert first.experiment_key == second.experiment_key is not None
    assert first.as_document()["experiment_key"] == first.experiment_key
    # A second holder on the same store: a store hit, no execution.
    other = holder_of(standin_truth(tmp_path))
    other.request_values(INLET)
    (hit,) = other.ledger
    assert (hit.served, hit.executions, hit.experiment_key) == (
        "store_hit",
        0,
        first.experiment_key,
    )


# == M05-fd-v2 (§6.5) ===========================================================================


def test_the_steps_floors_sides_and_exact_differences(tmp_path: Path) -> None:
    truth = standin_truth(tmp_path)
    policy = truth.finite_difference
    assert policy is not None and policy.eta == ETA == 2.0**-14
    assert policy.workers == fd_workers() == max(1, min(7, physical_cores() - 1))
    floors = policy.floors(INLET)
    assert floors == (*(1e-3 * math.fsum(INLET[:5]),) * 5, 1.0, 1e5)
    points = policy.points(INLET)
    for j, point in enumerate(points):
        h = ETA * max(abs(INLET[j]), floors[j])
        assert point[j] == INLET[j] + h  # the +h side inside the domain
        assert point[:j] + point[j + 1 :] == INLET[:j] + INLET[j + 1 :]
        # h_eff = w' − w is exact (Sterbenz): adding it back gives w' bitwise.
        assert INLET[j] + (point[j] - INLET[j]) == point[j]
    # At the hard domain's T bound the +h side leaves it: −h.
    edge = (*INLET[:5], 773.15, INLET[6])
    assert policy.points(edge)[5][5] == 773.15 - ETA * 773.15
    # Neither side admissible: a typed refusal naming the coordinate.
    nowhere = ForwardDifference(lambda point: point == INLET)
    with pytest.raises(TruthRefused) as refused:
        nowhere.points(INLET)
    assert refused.value.code == "fd_no_admissible_side:n_H2"


def test_the_holder_forms_an_fd_jacobian_from_seven_ledgered_points(tmp_path: Path) -> None:
    holder = holder_of(interior_truth(tmp_path))
    holder.begin_run(RunState("r"))
    holder.request_values(INLET)
    jacobian = holder.request_jacobian(INLET)
    again = holder.request_jacobian(INLET)
    holder.end_run()
    assert again == jacobian
    entries = [entry.as_document() for entry in holder.ledger]
    assert [(e["call"], e["served"], e["purpose"]) for e in entries] == [
        ("value", "cold", TRF_START_VALUE),
        ("value", "memo_hit", None),  # the base point, inside the Jacobian
        *[("value", "cold", TRF_FD_POINT)] * 7,
        ("jacobian", "cold", None),
        ("jacobian", "memo_hit", None),
    ]
    policy = holder.box.finite_difference  # type: ignore[attr-defined]
    points = policy.points(INLET)
    base = holder.request_values(INLET)
    values = [holder.request_values(point) for point in points]
    assert jacobian == policy.quotients(INLET, base, points, values)
    with pytest.raises(TypeError, match="no gradient of its own"):
        holder.box.truth.gradient(INLET)  # type: ignore[attr-defined]


def test_a_budget_cap_inside_an_fd_batch_admits_exactly_the_cap(tmp_path: Path) -> None:
    """G7's cap on an FD gradient: the base point and four of the seven points are admitted,
    the other three are refused uncharged, and the Jacobian is a budget refusal."""
    holder = holder_of(interior_truth(tmp_path))
    cap = ColdBudget("run", 5)
    holder.begin_run(RunState("r"), [cap])
    holder.request_values(INLET)
    with pytest.raises(TruthRefused) as refused:
        holder.request_jacobian(INLET)
    holder.end_run()
    assert refused.value.code == "budget:budget_exhausted"
    assert cap.used == 5
    assert (
        sum(1 for entry in holder.ledger if entry.served == "cold" and entry.call == "value") == 5
    )
    stored = {path.parent.name for path in store_files(tmp_path) if path.name == "result.json"}
    assert len(stored) == 5


def test_the_analytic_gradient_is_the_closed_form_of_the_values(tmp_path: Path) -> None:
    """The synthetic truth's closed form against its own values: (X, ΔT) through the runner equal
    the closed form at the process z within 4 ulps, and its gradient against central differences
    of the closed form (h = 1e-6 relative) within 1e-8 relative."""
    truth = synthetic.SyntheticTruth(runner(tmp_path), synthetic.synthetic_variant(), N_TUBES)
    assert truth.describe()["gradient"] == "analytic"
    conversion, rise, _ = truth.evaluate(INLET)
    closed = synthetic.interior(synthetic.process_z(INLET, N_TUBES))
    assert conversion == pytest.approx(closed[0], rel=1e-15)
    assert rise == pytest.approx(closed[1], rel=1e-15)
    gradient = truth.gradient(INLET)
    for j in range(7):
        h = 1e-6 * abs(INLET[j])
        up = list(INLET)
        down = list(INLET)
        up[j] += h
        down[j] -= h
        high = synthetic.interior(synthetic.process_z(up, N_TUBES))
        low = synthetic.interior(synthetic.process_z(down, N_TUBES))
        for k in range(2):
            central = (high[k] - low[k]) / (up[j] - down[j])
            assert gradient[k][j] == pytest.approx(central, rel=1e-8, abs=1e-14)


def test_the_gradient_check_passes_on_an_exact_map_and_reuses_its_points(tmp_path: Path) -> None:
    """The stand-in's map is constant: G(η/4) = G(η) = G(4η) = 0, so τ̂ = ν̂ = 0 and the check
    passes at η, `clean`; the basis gradient at the same w₀ (`basis_fd_point`) is served from the
    memo: seven entries, no cold request."""
    holder = holder_of(standin_truth(tmp_path))
    check = gradient_check(holder, INLET)
    assert check.status == "pass" and check.eta == ETA and len(check.candidates) == 1
    assert check.selected_class == "clean" and check.stopped == "passed"
    assert check.candidates[0]["truncation"] <= 1e-9 and check.candidates[0]["noise"] <= 1e-9
    checked = [entry for entry in holder.ledger if entry.purpose == FDCHECK_POINT]
    assert len(checked) == 1 + 7 * 3
    before = len(holder.ledger)
    jacobian = holder.request_jacobian(INLET, purpose=BASIS_FD_POINT)
    basis = [entry for entry in holder.ledger[before:] if entry.purpose == BASIS_FD_POINT]
    assert len(basis) == 7 and all(entry.served == "memo_hit" for entry in basis)
    assert jacobian == check.gradient


# == M05-fd-v2's gradient check (§17.2, R-297) ===================================================


def scaled_exact(inlet: Sequence[float]) -> list[list[float]]:
    """The synthetic truth's exact gradient in the check's scaling, G_kj = g_kj·m_j/s_k."""
    policy = ForwardDifference(lambda point: True, workers=1)
    scale = [max(abs(v), f) for v, f in zip(inlet, policy.floors(inlet), strict=True)]
    exact = synthetic.interior_gradient(inlet, N_TUBES)
    return [[exact[k][j] * scale[j] / SCALES[k] for j in range(7)] for k in range(2)]


def inf_norm(matrix: Sequence[Sequence[float]]) -> float:
    return max(abs(value) for row in matrix for value in row)


def difference(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> float:
    return inf_norm(
        [[x - y for x, y in zip(ra, rb, strict=True)] for ra, rb in zip(a, b, strict=True)]
    )


@pytest.fixture(scope="module")
def interior_check(tmp_path_factory: pytest.TempPathFactory) -> Any:
    holder = holder_of(interior_truth(tmp_path_factory.mktemp("fd-v2")))
    return holder, gradient_check(holder, INLET)


def test_fd_v2_i_richardson_recovers_the_exact_gradient(
    interior_check: Any, record_property: Any
) -> None:
    """§17.2 (i): ‖(4·G(η/4) − G(η))/3 − G_exact‖_∞ ≤ 1e-5·max(1, ‖G_exact‖_∞) at TR-E2's start
    inlet (predicted ≈ 5e-7)."""
    _, check = interior_check
    exact = scaled_exact(INLET)
    fine, mid = check.scaled[ETA / 4.0], check.scaled[ETA]
    richardson = [
        [(4.0 * f - m) / 3.0 for f, m in zip(rf, rm, strict=True)]
        for rf, rm in zip(fine, mid, strict=True)
    ]
    error = difference(richardson, exact)
    record_property("M05.fd_v2.richardson_error", error)
    assert error <= 1e-5 * max(1.0, inf_norm(exact))


def test_fd_v2_ii_the_truncation_estimate_bounds_the_error(
    interior_check: Any, record_property: Any
) -> None:
    """§17.2 (ii): ‖G(η) − G_exact‖_∞ ≤ 2τ̂ + 1e-6·max(1, ‖G_exact‖_∞) (predicted 0.044 against
    about 0.10)."""
    _, check = interior_check
    exact = scaled_exact(INLET)
    error = difference(check.scaled[ETA], exact)
    truncation = check.candidates[0]["truncation"]
    record_property("M05.fd_v2.error_at_eta", error)
    record_property("M05.fd_v2.truncation_estimate", truncation)
    assert error <= 2.0 * truncation + 1e-6 * max(1.0, inf_norm(exact))


def test_fd_v2_iii_the_check_passes_at_eta_truncation_dominated(
    interior_check: Any, record_property: Any
) -> None:
    """§17.2 (iii): no escalation, class `truncation_dominated` (predicted ν̂ ≈ 4e-6 against
    2.27e-3); 1 + 21 check requests; the basis gradient at w₀ is the check's G(η), its seven
    points memo hits."""
    holder, check = interior_check
    (candidate,) = check.candidates
    record_property("M05.fd_v2.noise_estimate", candidate["noise"])
    record_property("M05.fd_v2.allowance", candidate["allowance"])
    assert (check.status, check.eta, check.stopped) == ("pass", ETA, "passed")
    assert check.selected_class == candidate["class"] == "truncation_dominated"
    assert candidate["noise"] <= candidate["allowance"] < candidate["truncation"]
    assert sum(1 for entry in holder.ledger if entry.purpose == FDCHECK_POINT) == 1 + 7 * 3
    before = len(holder.ledger)
    assert holder.request_jacobian(INLET, purpose=BASIS_FD_POINT) == check.gradient
    basis = [entry for entry in holder.ledger[before:] if entry.purpose == BASIS_FD_POINT]
    assert len(basis) == 7 and all(entry.served == "memo_hit" for entry in basis)
    document = check.as_document()
    assert document["policy"] == "M05-fd-v2" and document["selected_eta"] == ETA
    assert document["half_steps"]["T"] == 0.5 * ETA * INLET[5]
    json.dumps(document)


class NoisyInteriorTruth(ParentExperimentTruth):
    """§17.2 (iv): the synthetic truth with deterministic pseudo-noise of relative amplitude 1e-6
    on (X, ΔT), a function of the exact input bits (SHA-256 mapped to [−1, 1])."""

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        import hashlib
        import struct

        conversion, rise, meta = super().evaluate(inlet)
        digest = hashlib.sha256(struct.pack(">7d", *inlet)).digest()
        u, v = (int.from_bytes(digest[i : i + 8], "big") / 2.0**63 - 1.0 for i in (0, 8))
        return conversion * (1.0 + 1e-6 * u), rise * (1.0 + 1e-6 * v), meta


def test_fd_v2_iv_noise_is_detected(tmp_path: Path, record_property: Any) -> None:
    """§17.2 (iv): with the pseudo-noise the check is `noise_dominated` at 2⁻¹⁴ and
    ν̂(2⁻¹²) < ν̂(2⁻¹⁴)."""
    truth = NoisyInteriorTruth(runner(tmp_path), synthetic.synthetic_variant(), N_TUBES)
    check = gradient_check(holder_of(truth), INLET)
    first, second = check.candidates[0], check.candidates[1]
    for item in check.candidates:
        record_property(f"M05.fd_v2.noisy.{item['eta']!r}", [item["noise"], item["class"]])
    record_property("M05.fd_v2.noisy.result", [check.status, check.eta, check.stopped])
    assert (first["eta"], first["class"]) == (2.0**-14, "noise_dominated")
    assert second["eta"] == 2.0**-12 and second["noise"] < first["noise"]


class CurvedMap:
    """An in-process map for the escalation's stops: X = 0.2·exp(k (T − T₀)/T₀) (+ pseudo-noise of
    relative amplitude `noise`), ΔT = 350 X, through the FD policy with `admissible`."""

    def __init__(self, k: float, noise: float, admissible: Any = None) -> None:
        self.k, self.noise = k, noise
        self.finite_difference = ForwardDifference(admissible or (lambda point: True), workers=1)

    def describe(self) -> Mapping[str, Any]:
        return {"kind": "test", "id": "curved-map", "sha256": None, "gradient": "finite_difference"}

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        raise TypeError("curved-map: the holder forms its gradient by finite differences")

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        import hashlib
        import struct

        digest = hashlib.sha256(struct.pack(">7d", *inlet)).digest()
        u = int.from_bytes(digest[:8], "big") / 2.0**63 - 1.0
        conversion = 0.2 * math.exp(self.k * (inlet[5] - INLET[5]) / INLET[5])
        conversion *= 1.0 + self.noise * u
        return conversion, 350.0 * conversion, in_process_meta()


def test_fd_v2_a_residual_growing_with_eta_stops_the_escalation() -> None:
    """§17.2: escalation continues only while ν̂ falls by at least 2 per step. With strong
    curvature (k = 5000) ν̂ fails at 2⁻¹⁴ and grows at 2⁻¹²: the check stops there
    (`noise_not_falling`), proceeds at the smaller ν̂'s η and is `fd_unstable`."""
    holder = EFHolder("reactor", TruthBox(CurvedMap(5000.0, 0.0)), SCALES, kind="truth")
    check = gradient_check(holder, INLET)
    assert [item["eta"] for item in check.candidates] == [2.0**-14, 2.0**-12]
    assert check.candidates[1]["noise"] > check.candidates[0]["noise"] / 2.0
    assert (check.status, check.stopped, check.eta) == ("fd_unstable", "noise_not_falling", ETA)
    assert sum(1 for entry in holder.ledger if entry.purpose == FDCHECK_POINT) == 1 + 7 * 4


def test_fd_v2_a_side_that_cannot_take_the_next_step_stops_the_escalation() -> None:
    """§17.2: each column's side is chosen once, at 4η; when the next candidate's largest step
    (16η) leaves the hard domain on that side, escalation stops (`side_limit`). Here T may rise by
    8η·T₀ only, so the + side is chosen and 16η is refused."""
    t_max = INLET[5] + 8.0 * ETA * INLET[5]
    truth = CurvedMap(0.0, 1e-6, admissible=lambda point: point[5] <= t_max)
    holder = EFHolder("reactor", TruthBox(truth), SCALES, kind="truth")
    check = gradient_check(holder, INLET)
    assert check.sides == (1,) * 7
    assert [item["class"] for item in check.candidates] == ["noise_dominated"]
    assert (check.status, check.stopped) == ("fd_unstable", "side_limit")


def test_fd_v2_the_sides_hold_for_all_three_steps() -> None:
    """§17.2: a column whose + side is admissible at η but not at 4η takes the − side for all
    three steps."""
    t_max = INLET[5] + 2.0 * ETA * INLET[5]
    policy = ForwardDifference(lambda point: point[5] <= t_max, workers=1)
    assert policy.sides(INLET, ETA)[5] == 1 and policy.sides(INLET, 4.0 * ETA)[5] == -1
    truth = CurvedMap(0.0, 0.0, admissible=lambda point: point[5] <= t_max)
    holder = EFHolder("reactor", TruthBox(truth), SCALES, kind="truth")
    check = gradient_check(holder, INLET)
    assert check.sides[5] == -1
    for eta in (ETA / 4.0, ETA, 4.0 * ETA):
        assert truth.finite_difference.points(INLET, eta, check.sides)[5][5] < INLET[5]


# == R-300 E2: the coupling coordinates are M02's ================================================


@pytest.mark.xfail(
    strict=True,
    raises=ModuleNotFoundError,
    reason=(
        "R-300 E2's guard needs M02's coupled-route residual (orchestrator/coupling.py "
        "_unit_terms, application/coupled_run.py answer_of), which is on wp/M02 and not yet on "
        "wp/M05; it runs, and must pass, once the branches meet (M05 build log F4)"
    ),
)
def test_e2_the_coupling_coordinates_are_m02s(tmp_path: Path) -> None:
    """R-300 E2: at TR-E2's start inlet and two of its FD points, M05's (X, ΔT) equal, bitwise,
    the coupling coordinates M02's coupled route reads from the same envelope — through M02's own
    path: `answer_of` on the outcome, then `_unit_terms` at w = (0, 0), whose residual
    r = F(w) − w is then F itself."""
    from openflowsheet.application.coupled_run import answer_of
    from openflowsheet.orchestrator.coupling import CouplingBlock, UnitInlet, _unit_terms

    truth = interior_truth(tmp_path)
    block = CouplingBlock.from_document(STANDIN.coupling)
    points = truth.finite_difference.points(INLET)
    for inlet in (INLET, points[1], points[5]):
        conversion, rise, _ = truth.evaluate(inlet)
        outcome = truth.run(inlet)
        answer = answer_of(
            outcome.request, outcome.result, outcome.envelope, outcome.attempts, outcome.cache_hit
        )
        state = truth.stream(inlet)
        unit = UnitInlet(n=state.n, T=state.temperature, P=state.pressure, n_key=state.n[1])
        terms = _unit_terms(unit, answer, (0.0, 0.0), block)
        assert (terms["r_xi"], terms["r_T"]) == (conversion, rise), inlet


# == concurrency (§6.5, R-250) ==================================================================


def _bare(path: Path) -> Any:
    """A store record as compared across runs: an attempt's measured wall time is the one field
    that is not a function of the request (M02 §3.3 records it), so it is left out."""
    document = json.loads(path.read_bytes())
    if path.parent.name == "attempts":
        document["execution"]["timing"].pop("wall_s")
    return document


def test_seven_distinct_keys_run_concurrently_and_serially_give_identical_records(
    tmp_path: Path,
) -> None:
    """The WO-4 concurrency test: the seven FD experiments of one gradient, run on seven worker
    threads and on one, into two stores. Every request and result record is byte-identical; every
    attempt record is identical but for its measured wall time; the Jacobians are bitwise equal
    and the ledgers equal entry by entry (wall time aside). `ExperimentRunner.run` is therefore
    safe for distinct keys after the handshake, and no `run_batch` is needed."""
    jacobians = []
    ledgers = []
    for name, workers in (("concurrent", 7), ("serial", 1)):
        root = tmp_path / name
        holder = holder_of(interior_truth(root, workers=workers))
        jacobians.append(holder.request_jacobian(INLET))
        ledgers.append([{**entry.as_document(), "wall_s": None} for entry in holder.ledger])
    assert jacobians[0] == jacobians[1]
    assert ledgers[0] == ledgers[1]
    concurrent = {
        p.relative_to(tmp_path / "concurrent"): p for p in store_files(tmp_path / "concurrent")
    }
    serial = {p.relative_to(tmp_path / "serial"): p for p in store_files(tmp_path / "serial")}
    assert concurrent.keys() == serial.keys()
    assert sum(1 for path in concurrent if path.name == "result.json") == 8
    for relative, path in concurrent.items():
        if path.parent.name == "attempts":
            assert _bare(path) == _bare(serial[relative]), relative
        else:
            assert path.read_bytes() == serial[relative].read_bytes(), relative


def test_g7_mechanics_on_a_unit_run(tmp_path: Path) -> None:
    """G7's arithmetic on one run of requests a TRF run makes (values, then gradients at accepted
    points, a rejected trial, repeats), on the FD parent truth: cold + store hit + memo hit equals
    requests; every attempt record in the store is attributed to the ledger — per key, the store's
    attempts equal the executions the ledger's entries at that key caused; no non-finite value is
    returned."""
    holder = holder_of(interior_truth(tmp_path))
    holder.begin_run(RunState("unit"), [ColdBudget("run", 250)])
    moved = (*INLET[:5], 675.0, INLET[6])
    trial = (*INLET[:5], 676.5, INLET[6])
    returned = [holder.request_values(INLET), holder.request_values(INLET)]
    holder.request_jacobian(INLET)
    returned += [holder.request_values(moved), holder.request_values(trial)]
    holder.request_jacobian(moved)
    returned.append(holder.request_values(moved))
    holder.end_run()
    assert all(math.isfinite(value) for values in returned for value in values)
    values = [entry for entry in holder.ledger if entry.call == "value"]
    served = {
        kind: sum(1 for e in values if e.served == kind)
        for kind in ("cold", "store_hit", "memo_hit")
    }
    assert (
        sum(served.values())
        == len(values)
        == holder.summary()["value_cold"]
        + holder.summary()["value_store_hit"]
        + holder.summary()["value_memo_hit"]
    )
    assert served["cold"] == 3 + 7 + 7
    executed: dict[str, int] = {}
    for entry in values:
        if entry.experiment_key is not None:
            executed[entry.experiment_key] = (
                executed.get(entry.experiment_key, 0) + entry.executions
            )
    records = holder.box.truth.runner.records  # type: ignore[attr-defined]
    keys = {
        path.parent.parent.name for path in store_files(tmp_path) if path.parent.name == "attempts"
    }
    assert keys == set(executed)
    assert all(len(records.attempts(key)) == executed[key] for key in keys)
