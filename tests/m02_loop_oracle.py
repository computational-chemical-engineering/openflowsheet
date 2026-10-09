"""G8 (c)'s independent solve of `C1-LOOP-M02-v1` with the stand-in (M02 design note §8.1, §10.1).
Not collected.

Sequential substitution on the recycle, written from the case's statement and two primitives
only — `pr-c1-v1`'s own TP flash and vapour enthalpy (`thermo.pr_c1`) and the stand-in's closed
form (ξ = 0.25 n_N2,in, T_out = T_in, P_out = P_in) — with no binding, no compiled rows, no Newton
and no traversal:

    S1 makeup (fixed) + S8 recycle -> S2 (adiabatic: Ḣ_V(S2) = Ḣ_V(S1) + Ḣ_V(S8), T2 by bisection)
    S3 = S2 at 673.15 K -> reactor: S4 = S3 + ν ξ, ξ = 0.25 n_N2(S3), T4 = T3
    flash S4 at 253.15 K, 1e7 Pa -> S5 vapour, S6 liquid
    splitter: S8 = 0.98 S5 (the recycle's share), S7 = 0.02 S5

Every stream at 1e7 Pa. The duties are Ḣ_out − Ḣ_in (vapour blocks, the flash's liquid by its
own phase). The iteration stops when one more pass moves no recycle flow (bitwise), or after
`MAX_PASSES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider

NU: Final = (-3.0, -1.0, 2.0, 0.0, 0.0)
MAKEUP: Final = (0.74625, 0.24875, 0.0, 0.002, 0.003)
T_MAKEUP: Final = 300.0
P: Final = 1.0e7
T_REACTOR_IN: Final = 673.15
T_FLASH: Final = 253.15
CONVERSION: Final = 0.25
RECYCLE_SHARE: Final = 0.98
MAX_PASSES: Final = 20000
CONTEXT: Final = EvaluationContext(model_version="g8c-oracle", constants_sha256="0" * 64)


@dataclass(frozen=True)
class LoopSolution:
    #: Stream id -> (n, T, P), the case's stream ids S1..S8.
    streams: dict[str, tuple[tuple[float, ...], float, float]]
    xi: float
    duties: dict[str, float]
    passes: int


def _hdot(provider: PrC1Provider, n: tuple[float, ...], t: float, phase: str = "VAPOR") -> float:
    if all(value == 0.0 for value in n):
        return 0.0
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=t, pressure=P), phase=phase, properties=("h",)
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    return sum(n) * result.values["h"]


def _mixer_temperature(provider: PrC1Provider, n: tuple[float, ...], target: float) -> float:
    """T with Ḣ_V(n, T) = target, by bisection (Ḣ_V increases with T)."""
    low, high = 200.0, 400.0
    assert _hdot(provider, n, low) < target < _hdot(provider, n, high)
    for _ in range(200):
        middle = 0.5 * (low + high)
        if middle in (low, high):
            break
        if _hdot(provider, n, middle) < target:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def solve_loop() -> LoopSolution:
    provider = PrC1Provider()
    recycle = (0.0,) * len(COMPONENTS)
    t_recycle = T_FLASH
    passes = 0
    while True:
        passes += 1
        n3 = tuple(a + b for a, b in zip(MAKEUP, recycle, strict=True))
        xi = CONVERSION * n3[1]
        n4 = tuple(n + nu * xi for n, nu in zip(n3, NU, strict=True))
        flashed = provider.flash(
            FlashRequest(state=StreamState(n=n4, temperature=T_FLASH, pressure=P)), CONTEXT
        )
        assert flashed.status == "ok" and flashed.vapor is not None and flashed.liquid is not None
        n5 = tuple(flashed.vapor.n)
        nxt = tuple(RECYCLE_SHARE * value for value in n5)
        if nxt == recycle or passes >= MAX_PASSES:
            recycle = nxt
            break
        recycle = nxt
    n6 = tuple(flashed.liquid.n)
    n7 = tuple((1.0 - RECYCLE_SHARE) * value for value in n5)
    n8 = recycle
    n1 = MAKEUP
    n2 = tuple(a + b for a, b in zip(n1, n8, strict=True))
    h1, h8 = _hdot(provider, n1, T_MAKEUP), _hdot(provider, n8, t_recycle)
    t2 = _mixer_temperature(provider, n2, h1 + h8)
    n3 = n2
    xi = CONVERSION * n3[1]
    n4 = tuple(n + nu * xi for n, nu in zip(n3, NU, strict=True))
    h2 = _hdot(provider, n2, t2)
    h3 = _hdot(provider, n3, T_REACTOR_IN)
    h4 = _hdot(provider, n4, T_REACTOR_IN)
    h5 = _hdot(provider, n5, T_FLASH)
    h6 = _hdot(provider, n6, T_FLASH, "LIQUID")
    return LoopSolution(
        streams={
            "S1": (n1, T_MAKEUP, P),
            "S2": (n2, t2, P),
            "S3": (n3, T_REACTOR_IN, P),
            "S4": (n4, T_REACTOR_IN, P),
            "S5": (n5, T_FLASH, P),
            "S6": (n6, T_FLASH, P),
            "S7": (n7, T_FLASH, P),
            "S8": (n8, T_FLASH, P),
        },
        xi=xi,
        duties={
            "preheater": h3 - h2,
            "reactor": h4 - h3,
            "flash": h5 + h6 - h4,
        },
        passes=passes,
    )
