"""T06 W13 (ADR 0017, F6): SYN-001's TP flash classifies by its own Rachford–Rice bracket.

At a stream within one rounding of saturation the classification's `fl(Σ zK)` (or `fl(Σ z/K)`)
and the bracket's `fl(f(0))`, `fl(f(1))` fall on opposite sides of their exact value's zero; the
flash then used to fail its bracket test at iteration 0 and report `not_converged` ("did not reach
1e-14 in 200 iterations"). ADR 0017 D1: it returns the single phase the bracket's signs name.

A75: the two registered states `ref.closed_form.f6_states` (found on `ref-x86-64`; the twin puts
the exact `β` within 1.2e-15 and 5.6e-16 of the answer). A76: a seeded re-flash probe of both
products of every two-phase feed. A77 (F4's C3 registration) is in `test_t06_f4_restart.py` and
`test_t06_f4_g6.py`; A78/A79 (the identity proof) are in `docs/t06-measurements.md`.
"""

from __future__ import annotations

import math
import platform

import pytest
from conftest import REPO_ROOT, load_yaml
from test_t06_f4_g7 import u

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import FlashRequest, StreamState
from openflowsheet.thermo.syn001 import COMPONENTS, Syn001Provider, ln_k

CONTEXT = EvaluationContext(model_version="t06-w13", constants_sha256="0" * 64)
F6_STATES = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")["closed_form"][
    "f6_states"
]
#: The registered states were found on this platform; `exp` is the platform's (spec A75, A76).
REFERENCE_MACHINE = platform.machine() == "x86_64"


def _state(name: str) -> StreamState:
    entry = F6_STATES[name]
    return StreamState(
        n=tuple(float.fromhex(value) for value in entry["n_hex"]),
        temperature=float.fromhex(entry["T_hex"]),
        pressure=float.fromhex(entry["P_hex"]),
    )


def _d1_condition(state: StreamState) -> str | None:
    """ADR 0017 D1's condition in the provider's own arithmetic (`ln_k`, its sums in its order):
    the first two tests put the feed two-phase and the bracket's two values share a sign. Returns
    the phase those signs name, or `None` when D1's branch would not decide."""
    count = len(COMPONENTS)
    total = state.total_flow
    k = tuple(math.exp(ln_k(state.temperature, state.pressure, i)) for i in range(count))
    z = tuple(value / total for value in state.n)
    if sum(z[i] * k[i] for i in range(count)) <= 1.0:
        return None
    if sum(z[i] / k[i] for i in range(count)) <= 1.0:
        return None

    def residual(beta: float) -> float:
        return sum(z[i] * (k[i] - 1.0) / (1.0 + beta * (k[i] - 1.0)) for i in range(count))

    f_low, f_high = residual(0.0), residual(1.0)
    if f_low * f_high <= 0.0:
        return None
    return "LIQUID" if f_low < 0.0 else "VAPOR"


@pytest.mark.parametrize(
    ("name", "phase", "beta"), [("F6-liquid", "LIQUID", 0.0), ("F6-vapour", "VAPOR", 1.0)]
)
def test_a75_a_registered_saturated_state_returns_its_single_phase(
    name: str, phase: str, beta: float
) -> None:
    """`ok`, the phase the bracket names, `β` 0 or 1, the other outlet dormant at the feed's `T`
    and `P`, the flowing outlet the feed bit for bit; no message (the ordinary single-phase
    result). Failed before ADR 0017 (`not_converged`, measured)."""
    state = _state(name)
    result = Syn001Provider().flash(FlashRequest(state=state), CONTEXT)
    assert (result.status, result.phase_signature, result.message) == ("ok", phase, "")
    assert result.vapor_fraction == beta
    assert F6_STATES[name]["fixed_signature"] == phase
    assert float(F6_STATES[name]["fixed_vapor_fraction"]) == beta
    flowing, dormant = (
        (result.liquid, result.vapor) if phase == "LIQUID" else (result.vapor, result.liquid)
    )
    assert flowing == state
    assert flowing is not None and dormant is not None
    assert [v.hex() for v in flowing.n] == [v.hex() for v in state.n]
    assert dormant.n == (0.0,) * len(COMPONENTS)
    assert (dormant.temperature, dormant.pressure) == (state.temperature, state.pressure)
    assert result.k_values is not None and set(result.k_values) == set(COMPONENTS)
    # The twin's bound: the exact vapour fraction is within 1e-14 of the answer (claim
    # `F6.fixed_answer_within_1e-14_of_exact_beta`), which is why the single phase is right.
    exact = float(F6_STATES[name]["beta_exact"])
    assert abs(beta - exact) <= float(F6_STATES[name]["beta_bound"])


@pytest.mark.skipif(not REFERENCE_MACHINE, reason="the states were found on ref-x86-64 (A75)")
@pytest.mark.parametrize(("name", "phase"), [("F6-liquid", "LIQUID"), ("F6-vapour", "VAPOR")])
def test_a75_control_d1s_branch_decides_the_registered_states(name: str, phase: str) -> None:
    """The first two tests put the state two-phase and the bracket's signs agree, so ADR 0017's
    branch, not `Σ zK ≤ 1` or `Σ z/K ≤ 1`, is what answers."""
    assert _d1_condition(_state(name)) == phase


def _reflash_feeds() -> list[StreamState]:
    """A76's feeds: `sha256-counter-v1` keys `F6-reflash-v1|<i:04d>|<field>`, i = 0…9999."""
    feeds = []
    for i in range(10_000):
        prefix = f"F6-reflash-v1|{i:04d}|"
        feeds.append(
            StreamState(
                n=tuple(u(f"{prefix}n.{c}") for c in COMPONENTS),
                temperature=280.0 + 160.0 * u(f"{prefix}T"),
                pressure=5e4 + 1.5e5 * u(f"{prefix}P"),
            )
        )
    return feeds


def test_a76_every_product_of_a_two_phase_flash_re_flashes_ok() -> None:
    """Both products of every two-phase feed, re-flashed at the feed's `(T, P)`: no status other
    than `ok`. Measured before ADR 0017 on this host: 21 of 2 940 re-flashes `not_converged` (8
    liquid, 13 vapour). On `ref-x86-64` at least one product meets D1's condition, so the probe
    exercises the branch it guards."""
    provider = Syn001Provider()
    two_phase = 0
    statuses: dict[str, int] = {}
    decided_by_d1 = 0
    for feed in _reflash_feeds():
        result = provider.flash(FlashRequest(state=feed), CONTEXT)
        assert result.status == "ok", (feed, result.message)
        if result.phase_signature != "TWO_PHASE":
            continue
        two_phase += 1
        for product in (result.liquid, result.vapor):
            assert product is not None
            again = provider.flash(FlashRequest(state=product), CONTEXT)
            statuses[again.status] = statuses.get(again.status, 0) + 1
            if _d1_condition(product) is not None:
                decided_by_d1 += 1
                assert again.phase_signature == _d1_condition(product)
    assert two_phase > 0
    assert statuses == {"ok": 2 * two_phase}
    if REFERENCE_MACHINE:
        assert decided_by_d1 >= 1
