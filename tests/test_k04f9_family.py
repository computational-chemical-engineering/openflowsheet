"""K04-F9 X04, X25: T04 F9's population — the A02 family scan's converged states — certified at the
verifier's projection (spec §5.1, §6, §8; ADR 0013 D1; `ref.closed_form.a02_family_projection`).

The scan is T04 A11's: 10 targets × 18 guesses under the default policy (`test_t04_edge3`), each
run's final region result judged by `verify_bound` on its bound declaration with its region plan.
Before F9 the S3 checks — the independent split of S3 and the heater and flash balances, which
read S3's fresh flash — failed at 15 of the 179 converged states (27.28 × at worst) and sat near
their thresholds at 9 more; at the projection every one is `VERIFIED`.

The raw values are read through the unprojected check functions (`checks.energy_checks`,
`checks.admissibility_checks` at `x_final`), so each exposed state also shows the projection doing
the work (raw ≥ 0.1, projected ≤ 1e-3: F9's bound discriminates by ≥ 100).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import cache
from typing import Any

from k04f9_support import PROJECTED, PROJECTED_BOUND, REF, s3_ratios
from test_t04_edge3 import T04, family_run, region_step

from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import SolutionCertificate, verify_bound
from openflowsheet.verify.checks import admissibility_checks, energy_checks

FAMILY = REF["closed_form"]["a02_family_projection"]
EXPOSED = {
    (int(entry["T_target_K"]), float(entry["guess_K"])): entry for entry in FAMILY["exposed_states"]
}
#: Regression values (self-generated, measured 2026-09-25, K04-F9 W5; spec X04 and the `measured`
#: section: "15 states, 29 flags", all on the heater's equilibrium rows at ≥ 0.1 τ_eq). Reported to
#: the design lane when they move, never re-pinned.
FLAGGED_STATES = 15
FLAGS = 29


@dataclass(frozen=True)
class Member:
    target: int
    guess: float
    outcome: str
    certificate: SolutionCertificate | None
    raw: dict[str, float]


@cache
def family() -> tuple[tuple[Member, ...], float]:
    """Every run of the scan, its certificate when it converged, and the raw S3 ratios at
    `x_final`; with the wall time (reported in the evidence, not asserted)."""
    scan = T04["policy_simulation"]["a02_family_scan"]
    started = time.perf_counter()
    members: list[Member] = []
    provider = Syn001Provider()
    for target in scan["targets_K"]:
        for guess in scan["guesses_K"]:
            document, run = family_run(target, guess)
            if run.result.outcome != "CONVERGED":
                members.append(Member(int(target), float(guess), run.result.outcome, None, {}))
                continue
            step = region_step(run.result)
            (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
            binding = bind_revision(document)
            assert isinstance(binding, Binding)
            issued = verify_bound(binding, document, step.detail, solve_plan=planned.solve_plan)
            metadata = compile_problem(binding.spec).metadata
            context = EvaluationContext(
                model_version=metadata.model_version,
                constants_sha256=metadata.constants_sha256,
                phase_signature=None,
            )
            state = step.detail.state
            raw = s3_ratios(
                energy_checks(provider, state, context)
                + admissibility_checks(provider, state, context)
            )
            members.append(Member(int(target), float(guess), "CONVERGED", issued, raw))
    return tuple(members), time.perf_counter() - started


def _converged() -> list[Member]:
    return [member for member in family()[0] if member.certificate is not None]


def test_x04_every_converged_family_state_is_verified_at_the_projection(
    record_property: Any,
) -> None:
    """179 of 180 runs converge, and each is `VERIFIED` with `judged_at = projection`."""
    members, elapsed = family()
    record_property("family_certification_seconds", round(elapsed, 1))
    assert len(members) == 180
    converged = _converged()
    assert len(converged) == FAMILY["converged"] == 179
    for member in converged:
        assert member.certificate is not None
        assert member.certificate.transformations["projection"] == PROJECTED, member
        assert member.certificate.verification_status == "VERIFIED", (
            member.target,
            member.guess,
            [(c.id, c.value) for c in member.certificate.checks if c.result != "pass"],
        )


def test_x04_the_exposed_states_s3_checks_are_resolved_at_the_projection() -> None:
    """At each of `ref`'s 24 exposed states (raw S3 value ≥ 0.1 of its threshold) every S3 check
    on the certificate — judged at `x̃` — is ≤ 1e-3 of its tolerance; raw, at `x_final`, the
    largest is ≥ 0.1 (the bound discriminates)."""
    by_key = {(m.target, m.guess): m for m in _converged()}
    assert len(EXPOSED) == 24 and set(EXPOSED) <= set(by_key)
    for key in EXPOSED:
        member = by_key[key]
        assert member.certificate is not None
        projected = s3_ratios(member.certificate.checks)
        assert projected and max(projected.values()) <= PROJECTED_BOUND, (key, projected)
        assert max(member.raw.values()) >= 0.1, (key, member.raw)
    # The rest of the population was never exposed: raw < 0.1 there.
    for key, member in by_key.items():
        if key not in EXPOSED:
            assert max(member.raw.values()) < 0.1, (key, member.raw)


def test_x04_every_flag_on_the_family_is_a_residual_rows() -> None:
    """No fresh-flash check is near its threshold anywhere in the family; the flags left are the
    rows' (Newton stopped at 0.1–0.4 τ; spec §11: those verdicts are not promised)."""
    flagged = {
        (m.target, m.guess): [c for c in m.certificate.checks if c.near_threshold]
        for m in _converged()
        if m.certificate is not None and any(c.near_threshold for c in m.certificate.checks)
    }
    for key, flags in flagged.items():
        assert all(c.category == "residual" for c in flags), (key, [c.id for c in flags])
    assert (len(flagged), sum(len(f) for f in flagged.values())) == (FLAGGED_STATES, FLAGS)


def test_x25_the_projection_is_the_specified_map() -> None:
    """At each exposed state the largest S3 value over its threshold at `x̃` agrees with the twin's
    40-digit projection to `max(0.05 · ref, 1e-5)`: a projection over another matrix or scaling
    would leave values of the first-order size."""
    by_key = {(m.target, m.guess): m for m in _converged()}
    for key, entry in EXPOSED.items():
        member = by_key[key]
        assert member.certificate is not None
        got = max(s3_ratios(member.certificate.checks).values())
        expected = float(entry["projected_largest_over_threshold"])
        assert abs(got - expected) <= max(0.05 * expected, 1e-5), (key, got, expected)
