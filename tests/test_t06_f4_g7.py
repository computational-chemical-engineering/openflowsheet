"""T06 F4 WO8, gate G7: NET-02's independent-perturbation regression under `T06-revision-v2`.

Design note `docs/design/T06-F4-recovery.md` §8 G7 and Appendix C step 6. Twenty perturbed starts
drawn by T06 spec §6.2–§6.4's nominal law with the key prefix **`F4-probe-v1`** — never the
gate's `T06-ens-v1`, so these starts are independent of the ensemble's and nothing here is tuned
on the gate's own draws (R-075's watch list). Every start must end `CONVERGED` and `VERIFIED`
within T02 §6.4's allowances of the twin root, by the first solve or through edge 3's restart. The
split between the two is recorded, not gated: the design probe measured 9 and 11; on the committed
case file this law gives 6 and 14 (first solves 8 `BOUND_BLOCKED`, 6 `ACTIVE_SET_CYCLING`).

The law, as the spec states it for the revision path: the selected coordinates are every stream
coordinate and unit-owned scalar that no fixed specification pins — NET-02's pins are the feed
`S1` (all five coordinates), the heater's outlet temperature `S3.T` and the flash duty `U-PHF.Q`
(spec §4.3) — set to `x_init + S δ` with `x_init` the registered initializer's start and `S` the
plan's column scale; each draw outside the box domain (flows ≥ 0, `T ∈ [280, 440]` K,
`P ∈ [5e4, 2e5]` Pa) is redrawn (cap 64). The lifted splits are then re-derived from the
perturbed streams by `initial_state`'s step 5: the heater (a TP closure) by the provider's TP
flash of `S3`, the flash's product totals as sums; a refused re-flash redraws the start (cap 64).
The start enters where `traversal-G0-v1`'s does.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_support import CORPUS, T06_REVISION_POLICY, case_document, registered_root, worst_ratio

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.thermo import StreamState
from openflowsheet.verify.certificate import verify_revision

CASE = "SYN-001-T06-NET02"
PREFIX = "F4-probe-v1"
STARTS = 20
CAP = 64
PINNED = frozenset({"S1.n.A", "S1.n.B", "S1.n.C", "S1.T", "S1.P", "S3.T", "U-PHF.Q"})
LIFTED = frozenset(
    {"S3.vap.A", "S3.vap.B", "S3.vap.C", "S3.liq.A", "S3.liq.B", "S3.liq.C", "S3.V", "S3.L"}
    | {"S4.N", "S5.N"}
)
#: Spec §6.2's registered physical nominals by column kind (the plan's `column_scales`).
SCALE: dict[str, float] = {
    "molar_flow": 3.0,
    "temperature": 100.0,
    "pressure": 1e5,
    "heat_rate": 1e5,
}
#: Spec §6.4's box by column kind: `(lower, upper)`; a duty is unbounded.
BOX: dict[str, tuple[float, float]] = {
    "molar_flow": (0.0, float("inf")),
    "temperature": (280.0, 440.0),
    "pressure": (5e4, 2e5),
    "heat_rate": (float("-inf"), float("inf")),
}


def u(key: str) -> float:
    """Spec §6.3's `sha256-counter-v1`: the first 8 bytes big-endian, `>> 11`, times 2⁻⁵³."""
    return (int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") >> 11) * 2.0**-53


def delta(key: str) -> float:
    """`δ = 0.2 (2u − 1)` rounded once, as `(2u − 1) / 5`: the exact product's nearest double.
    (The binary64 product with the double `0.2` is off by an ulp at some keys.)"""
    return (2.0 * u(key) - 1.0) / 5.0


def test_g7_the_draw_reproduces_the_registered_known_answers() -> None:
    """`k53` and `u` exactly; `δ` is the nearest double to the exact `0.2 (2u − 1)` and agrees
    with the registered 17-digit rendering of that exact value to its precision."""
    reference = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
    answers = reference["closed_form"]["draw_known_answers"]
    assert len(answers) == 10
    for answer in answers:
        key = answer["key"]
        k53 = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") >> 11
        assert k53 == answer["k53"], key
        assert u(key) == float(Decimal(answer["u"])), key
        exact = Decimal(2.0 * u(key) - 1.0) * Decimal("0.2")
        assert delta(key) == float(exact), key
        assert abs(Decimal(answer["delta"]) - exact) < Decimal("1e-17"), key


@dataclass(frozen=True)
class Start:
    values: dict[str, float]
    joint: int


def perturbed_start(binding: RevisionBinding, plan: ExecutionPlan, index: int) -> Start:
    flowsheet, spec = binding.flowsheet, binding.spec
    scales = plan.steps[-1].solve_plan.column_scales
    registered = revision.traversal_start(flowsheet, spec.variable_ids)
    assert isinstance(registered, revision.TraversalStart)
    assert registered.band_routes == ()
    selected = [c for c in spec.variable_ids if c not in PINNED and c not in LIFTED]
    for joint in range(CAP):
        values = dict(registered.values)
        for column in selected:
            low, high = BOX[spec.variable_kinds[column]]
            for attempt in range(CAP):
                key = f"{PREFIX}|nominal|{CASE}|{index:02d}|{joint:02d}|{column}|{attempt:02d}"
                scale = scales[column]
                assert scale == SCALE[spec.variable_kinds[column]], column
                drawn = registered.values[column] + scale * delta(key)
                if low <= drawn <= high:
                    values[column] = drawn
                    break
            else:
                raise AssertionError(f"F-GEN: {column} of start {index} outside the box")
        stream = StreamState(
            tuple(values[f"S3.n.{c}"] for c in flowsheet.components),
            values["S3.T"],
            values["S3.P"],
        )
        split = tp_state(flowsheet.provider, stream, flowsheet.context)
        if split.status != "ok" or split.vapor is None or split.liquid is None:
            continue
        for position, component in enumerate(flowsheet.components):
            values[f"S3.vap.{component}"] = split.vapor.n[position]
            values[f"S3.liq.{component}"] = split.liquid.n[position]
        values["S3.V"], values["S3.L"] = sum(split.vapor.n), sum(split.liquid.n)
        values["S4.N"] = sum(values[f"S4.n.{c}"] for c in flowsheet.components)
        values["S5.N"] = sum(values[f"S5.n.{c}"] for c in flowsheet.components)
        return Start({c: values[c] for c in spec.variable_ids}, joint)
    raise AssertionError(f"F-GEN: start {index} refused {CAP} times")


@dataclass(frozen=True)
class Outcome:
    outcome: str
    edge: str | None
    verdict: str | None
    ratio: float
    joint: int
    #: The first solve's outcome when the restart ran.
    failed: str | None = None


@cache
def solved(index: int) -> Outcome:
    binding = bind_revision_flowsheet(case_document(CASE))
    assert isinstance(binding, RevisionBinding)
    policy = T06_REVISION_POLICY
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan)
    start = perturbed_start(binding, plan, index)
    real = revision.traversal_start
    calls = 0

    def first_call_perturbed(*args: Any) -> Any:
        nonlocal calls
        calls += 1
        return revision.TraversalStart(start.values) if calls == 1 else real(*args)

    revision.traversal_start = first_call_perturbed  # type: ignore[assignment]
    try:
        run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    finally:
        revision.traversal_start = real  # type: ignore[assignment]
    assert calls == 1
    (step,) = run.steps
    if run.outcome != "CONVERGED":
        return Outcome(run.outcome, step.eo_recovery, None, float("inf"), start.joint)
    document = case_document(CASE)
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert run.state is not None
    ratio, _ = worst_ratio(run.state, registered_root(CORPUS[CASE]))
    failed = step.recovered_from.outcome if step.recovered_from is not None else None
    verdict = certificate.verification_status
    return Outcome(run.outcome, step.eo_recovery, verdict, ratio, start.joint, failed)


@pytest.mark.parametrize("index", range(STARTS))
def test_g7_every_perturbed_start_is_verified_at_the_root(index: int) -> None:
    outcome = solved(index)
    assert (outcome.outcome, outcome.verdict) == ("CONVERGED", "VERIFIED"), outcome
    assert outcome.ratio <= 1.0, outcome
    assert outcome.edge in (None, "taken"), outcome


def test_g7_twenty_of_twenty_with_the_split_recorded() -> None:
    outcomes = [solved(index) for index in range(STARTS)]
    verified = [o for o in outcomes if o.verdict == "VERIFIED" and o.ratio <= 1.0]
    rescued = [o for o in verified if o.edge == "taken"]
    first = sorted(str(o.failed) for o in rescued)
    print(
        f"G7: {len(verified)}/{STARTS} VERIFIED; first solve {len(verified) - len(rescued)}, "
        f"through the restart {len(rescued)} (first solves {first}); joint redraws "
        f"{[o.joint for o in outcomes]}; worst {max(o.ratio for o in outcomes):.3g}"
    )
    assert len(verified) == STARTS
