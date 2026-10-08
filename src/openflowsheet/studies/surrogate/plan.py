"""The registered reference distribution and sample plan of a surrogate study (M04 spec §3–§5).

P_ref `m04-c1-box7-v1` is the uniform distribution on a box in the seven inlet coordinates
u = (T, P, r = n_H2/n_N2, y_NH3, y_Ar, y_CH4, F = n_tot/N_tubes) (spec §3.1, ADR 0036 D1). A plan
is derived here from registered constants alone; `benchmarks/m04/plan-it1.json` is the bitwise
expectation of the tests (M04.A02) and is never read by this package (T08's no-walk-up rule).

Experiment identity is exact (ADR 0033): one ulp is a new experiment. Every floating-point
operation below is therefore in the registered order and nothing is rearranged for speed:

* the box bounds are the decimal literals of spec §3.1 parsed to binary64; the centre and the
  half-width are `(lo + hi) * 0.5` and `(hi - lo) * 0.5`;
* seed(i, split) = 20261008·1000 + 10·i + j, j = 1 training, 2 calibration, 3 test, 4 gradient;
* SplitMix64 words (R-184's generator); draw j of a split consumes words 7j … 7j+6 in coordinate
  order; U = (w >> 11)·2⁻⁵³, exact in binary64; u_k = lo_k + (hi_k − lo_k)·U;
* gradient centres: the same formula on the inner box c ∓ 0.95 h; stencil u ± (0.05 h_k) e_k, plus
  before minus, coordinates in order;
* the request at N_tubes = 1: y_N2 = (1 − y_NH3 − y_Ar − y_CH4)/(1 + r) left to right,
  y_H2 = r·y_N2, n = (F·y_H2, F·y_N2, F·y_NH3, F·y_Ar, F·y_CH4), T = u₁, P = u₂.

The sampler is a pure function of its seed: there is no generator object and no global state
(G20). The input map u(s) and the scaled input z = (u − c)/h live here too, because the plan
guard judges every request by them and the surrogate (`quadratic`) is a function of the same z.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.thermo import StreamState

#: The registered reference distribution (spec §4, ADR 0036 D1).
REFERENCE_DISTRIBUTION_ID: Final = "m04-c1-box7-v1"
#: The sampler (spec §5.1): SplitMix64 words, U = (w >> 11)·2⁻⁵³.
SAMPLER_ID: Final = "splitmix64-u53-v1"
#: The input map u(s) and its affine scaling to [−1, 1]⁷ (spec §3.1).
INPUT_MAP_ID: Final = "c1-inlet-u7-v1"

Split = Literal["training", "calibration", "test", "gradient"]
SPLITS: Final[tuple[Split, ...]] = ("training", "calibration", "test", "gradient")

#: seed(i, split) = SEED_BASE·1000 + 10·i + j (spec §5.1).
SEED_BASE: Final = 20261008
#: Registered counts of iteration 1 (spec §5.2) and of its prefix (spec §9.3); the gradient split
#: counts centres, each with 2 × 7 stencil experiments.
COUNTS: Final[Mapping[Split, int]] = {
    "training": 144,
    "calibration": 118,
    "test": 300,
    "gradient": 5,
}
PREFIX_COUNTS: Final[Mapping[Split, int]] = {
    "training": 72,
    "calibration": 39,
    "test": 60,
    "gradient": 2,
}
#: The gradient centres are drawn from c ∓ GRADIENT_INNER·h; the stencil step is GRADIENT_STEP_Z·h.
GRADIENT_INNER: Final = 0.95
GRADIENT_STEP_Z: Final = 0.05
#: Every plan request is one tube (spec §5.1).
PLAN_N_TUBES: Final = 1.0

_MASK: Final = (1 << 64) - 1
_GOLDEN: Final = 0x9E3779B97F4A7C15
_MIX1: Final = 0xBF58476D1CE4E5B9
_MIX2: Final = 0x94D049BB133111EB


@dataclass(frozen=True)
class BoxCoordinate:
    """One coordinate of the reference box (spec §3.1): its bounds as binary64 literals."""

    name: str
    unit: str
    lo: float
    hi: float

    @property
    def centre(self) -> float:
        return (self.lo + self.hi) * 0.5

    @property
    def half_width(self) -> float:
        return (self.hi - self.lo) * 0.5


#: The reference box in coordinate order (spec §3.1; `reference_values.json` → `constants.box`).
BOX: Final[tuple[BoxCoordinate, ...]] = (
    BoxCoordinate("T", "K", 653.15, 693.15),
    BoxCoordinate("P", "Pa", 9.0e6, 1.0e7),
    BoxCoordinate("r_H2_N2", "1", 2.5, 3.0),
    BoxCoordinate("y_NH3", "1", 0.02, 0.04),
    BoxCoordinate("y_Ar", "1", 0.01, 0.03),
    BoxCoordinate("y_CH4", "1", 0.01, 0.04),
    BoxCoordinate("F_tube", "mol/s", 0.0057, 0.0086),
)
DIMENSION: Final = len(BOX)


class PlanRefusedError(ValueError):
    """A plan refused at study start, before any experiment (spec §5.4, M04.A03).

    `code` is `plan_invalid` (a request outside the box, the parent's hard domain or its data
    domain, or a repeated request), `plan_not_registered_for_parent` (`it1-prefix` for a parent
    that is not synthetic) or `plan_not_registered` (an id without a committed plan, spec §5.5).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# -- the sampler (spec §5.1) ----------------------------------------------------------------------


def seed(iteration: int, split: Split) -> int:
    """seed(i, split) = 20261008·1000 + 10·i + j (spec §5.1)."""
    if iteration < 1:
        raise ValueError(f"iteration {iteration} is not a positive integer")
    return SEED_BASE * 1000 + 10 * iteration + (SPLITS.index(split) + 1)


def splitmix64(seed_value: int, count: int) -> tuple[int, ...]:
    """The first `count` SplitMix64 words from `seed_value` (R-184; constants of Steele et al.)."""
    state = seed_value & _MASK
    words = []
    for _ in range(count):
        state = (state + _GOLDEN) & _MASK
        z = state
        z = ((z ^ (z >> 30)) * _MIX1) & _MASK
        z = ((z ^ (z >> 27)) * _MIX2) & _MASK
        words.append(z ^ (z >> 31))
    return tuple(words)


def unit_uniform(word: int) -> float:
    """U = (w >> 11)·2⁻⁵³ ∈ [0, 1): the 53-bit integer and the power of two are exact in binary64,
    so the product is exact."""
    return float(word >> 11) * 2.0**-53


def inner_box() -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The gradient centres' box, lo′ = c − 0.95 h and hi′ = c + 0.95 h (binary64, that order)."""
    lo = tuple(b.centre - GRADIENT_INNER * b.half_width for b in BOX)
    hi = tuple(b.centre + GRADIENT_INNER * b.half_width for b in BOX)
    return lo, hi


def draws(iteration: int, split: Split, count: int) -> tuple[tuple[float, ...], ...]:
    """The first `count` draws u of `split` in iteration `iteration` (spec §5.1).

    Draw j consumes words 7j … 7j+6, so the first c draws of a longer request are the c draws of
    a shorter one: a prefix of an i.i.d. sequence is i.i.d. (spec §9.3).
    """
    if split == "gradient":
        lo, hi = inner_box()
    else:
        lo = tuple(b.lo for b in BOX)
        hi = tuple(b.hi for b in BOX)
    words = splitmix64(seed(iteration, split), DIMENSION * count)
    return tuple(
        tuple(
            lo[k] + (hi[k] - lo[k]) * unit_uniform(words[DIMENSION * j + k])
            for k in range(DIMENSION)
        )
        for j in range(count)
    )


def request_of(u: Sequence[float]) -> StreamState:
    """The one-tube experiment inlet of a draw u (spec §5.1; binary64 operations in this order)."""
    t, p, r, y_nh3, y_ar, y_ch4, f = u
    y_n2 = (1.0 - y_nh3 - y_ar - y_ch4) / (1.0 + r)
    y_h2 = r * y_n2
    return StreamState(
        n=(f * y_h2, f * y_n2, f * y_nh3, f * y_ar, f * y_ch4), temperature=t, pressure=p
    )


def stencil_point(u: Sequence[float], k: int, sign: Literal[1, -1]) -> tuple[float, ...]:
    """u ± (0.05 h_k) e_k (spec §5.1)."""
    step = GRADIENT_STEP_Z * BOX[k].half_width
    v = list(u)
    v[k] = u[k] + step if sign > 0 else u[k] - step
    return tuple(v)


# -- the input map (spec §3.1) --------------------------------------------------------------------


def coordinates(state: StreamState, n_tubes: float) -> tuple[float, ...] | None:
    """u(s) = (T, P, n_H2/n_N2, y_NH3, y_Ar, y_CH4, n_tot/N_tubes), or `None` where undefined.

    n_tot = (((n₁ + n₂) + n₃) + n₄) + n₅ (spec §3.1). The map is undefined where a division is:
    n_N2 = 0 (no H2/N2 ratio) or n_tot = 0 (no composition) — exact zeros, ADR 0001 D3.1. It is
    not restricted to physical flows, so a residual built on it stays defined at a Newton iterate.
    """
    n = state.n
    n_tot = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    if n[1] == 0.0 or n_tot == 0.0:
        return None
    return (
        state.temperature,
        state.pressure,
        n[0] / n[1],
        n[2] / n_tot,
        n[3] / n_tot,
        n[4] / n_tot,
        n_tot / n_tubes,
    )


def scaled(u: Sequence[float]) -> tuple[float, ...]:
    """z_k = (u_k − c_k)/h_k: the box is [−1, 1]⁷ (spec §3.1)."""
    return tuple((u[k] - b.centre) / b.half_width for k, b in enumerate(BOX))


# -- the plan (spec §5) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Draw:
    """One draw of the training, calibration or test split: its u and its experiment inlet."""

    index: int
    u: tuple[float, ...]
    request: StreamState


@dataclass(frozen=True)
class StencilPoint:
    """One gradient-check experiment: coordinate `coordinate` moved by `sign`·0.05 h."""

    coordinate: str
    sign: Literal[1, -1]
    u: tuple[float, ...]
    request: StreamState


@dataclass(frozen=True)
class GradientCentre:
    """A gradient centre and its 14 stencil experiments (the centre itself is not run)."""

    index: int
    u: tuple[float, ...]
    request: StreamState
    stencil: tuple[StencilPoint, ...]


@dataclass(frozen=True)
class SamplePlan:
    """A registered plan: the draws of every split, in plan order, fixed before the parent runs."""

    plan_id: str
    iteration: int
    seeds: Mapping[Split, int]
    training: tuple[Draw, ...]
    calibration: tuple[Draw, ...]
    test: tuple[Draw, ...]
    gradient: tuple[GradientCentre, ...]

    @property
    def counts(self) -> dict[Split, int]:
        return {
            "training": len(self.training),
            "calibration": len(self.calibration),
            "test": len(self.test),
            "gradient": len(self.gradient),
        }

    def requests(self) -> tuple[tuple[str, StreamState], ...]:
        """Every experiment of the plan in plan order, labelled `<split>[<index>]` or
        `gradient[<index>].<coordinate><sign>`: training, calibration, test, then the stencils."""
        out: list[tuple[str, StreamState]] = []
        for split, rows in (
            ("training", self.training),
            ("calibration", self.calibration),
            ("test", self.test),
        ):
            out.extend((f"{split}[{row.index}]", row.request) for row in rows)
        for centre in self.gradient:
            out.extend(
                (
                    f"gradient[{centre.index}].{point.coordinate}{'+' if point.sign > 0 else '-'}",
                    point.request,
                )
                for point in centre.stencil
            )
        return tuple(out)


def build_plan(plan_id: str, iteration: int, counts: Mapping[Split, int]) -> SamplePlan:
    """The plan of `iteration` with the first `counts[split]` draws of every split (spec §5.1)."""

    def rows(split: Split) -> tuple[Draw, ...]:
        return tuple(
            Draw(index=j, u=u, request=request_of(u))
            for j, u in enumerate(draws(iteration, split, counts[split]))
        )

    centres = []
    for j, u in enumerate(draws(iteration, "gradient", counts["gradient"])):
        stencil = []
        for k, coordinate in enumerate(BOX):
            for sign in (1, -1):
                v = stencil_point(u, k, sign)
                stencil.append(StencilPoint(coordinate.name, sign, v, request_of(v)))
        centres.append(GradientCentre(j, u, request_of(u), tuple(stencil)))
    return SamplePlan(
        plan_id=plan_id,
        iteration=iteration,
        seeds={split: seed(iteration, split) for split in SPLITS},
        training=rows("training"),
        calibration=rows("calibration"),
        test=rows("test"),
        gradient=tuple(centres),
    )


#: The registered plans (spec §5.2, §9.3). `it<i>` for i ≥ 2 is registered only when its plan file
#: is emitted by the generator and committed (spec §5.5), which has not happened.
REGISTERED_PLANS: Final[Mapping[str, tuple[int, Mapping[Split, int], bool]]] = {
    # plan id: (iteration, counts, synthetic parents only)
    "it1": (1, COUNTS, False),
    "it1-prefix": (1, PREFIX_COUNTS, True),
}


def registered_plan(plan_id: str, *, synthetic_parent: bool) -> SamplePlan:
    """The registered plan `plan_id` for a parent, or `PlanRefusedError` (spec §10.3, M04.A03).

    `it1-prefix` (spec §9.3) exists to keep the default gate cheap and is accepted only for a
    synthetic parent: its power is not the registered plan's.
    """
    if plan_id not in REGISTERED_PLANS:
        raise PlanRefusedError(
            "plan_not_registered",
            f"plan {plan_id!r} is not registered (registered: {sorted(REGISTERED_PLANS)})",
        )
    iteration, counts, synthetic_only = REGISTERED_PLANS[plan_id]
    if synthetic_only and not synthetic_parent:
        raise PlanRefusedError(
            "plan_not_registered_for_parent",
            f"plan {plan_id!r} is registered for synthetic parents only",
        )
    return build_plan(plan_id, iteration, counts)


# -- the plan guard (spec §5.1, §5.4) -------------------------------------------------------------


def plan_violations(
    plan: SamplePlan, domain_violations: Callable[[StreamState], Sequence[str]]
) -> tuple[str, ...]:
    """Why `plan` may not run, in plan order; empty when it may.

    Every request must lie in the reference box (judged by the input map, as the surrogate will
    judge it) and must have no `domain_violations` — the caller's union of the parent's hard
    domain and its data domain, taken from the parent's variant (spec §5.1: the box lies inside
    both, so a request outside either means the plan or the variant is not the registered one).
    No request may repeat another: a repeat is the same experiment counted twice (ADR 0033).
    """
    found: list[str] = []
    seen: dict[tuple[float, ...], str] = {}
    for label, request in plan.requests():
        u = coordinates(request, PLAN_N_TUBES)
        if u is None:
            found.append(f"{label}: the input map is undefined")
            continue
        outside = [BOX[k].name for k, z in enumerate(scaled(u)) if not -1.0 <= z <= 1.0]
        if outside:
            found.append(f"{label}: outside the reference box in {outside}")
        found.extend(f"{label}: {reason}" for reason in domain_violations(request))
        key = (*request.n, request.temperature, request.pressure)
        if key in seen:
            found.append(f"{label}: repeats {seen[key]}")
        else:
            seen[key] = label
    return tuple(found)


def check_plan(plan: SamplePlan, domain_violations: Callable[[StreamState], Sequence[str]]) -> None:
    """Refuse `plan` with `plan_invalid` before any experiment when it has a violation."""
    found = plan_violations(plan, domain_violations)
    if found:
        raise PlanRefusedError("plan_invalid", "; ".join(found))
