"""T06's ensemble generator: the sampling law `sha256-counter-v1` and the start assembly.

Spec `docs/derivations/T06-corpus-spec.md` §6.2–§6.5 as amended by Amendments 1 and 2 (work
order M7, the first half of W6). Nothing here solves: a start is drawn, assembled and checked
against its domain, and the published starts file (§6.5) is written from those records alone.

**The draw (§6.3 (A2)), in binary64 exactly.** `k = int.from_bytes(SHA-256(key)[:8], "big") >> 11`;
`u = k · 2.0**-53` (exact, `k < 2⁵³`); `w = 2.0*u − 1.0` (exact); **`δ = w / 5.0`** — one
correctly rounded division, which is the exact `0.2·(2u − 1)` rounded once. The literal
`0.2 * w` is *not* the law: it differs by one ulp at 35 % of keys. A coordinate is
`x = x_init + S*δ`: two separately rounded operations (CPython never fuses them), `S` the
registered scale — 3 mol/s for flows and extents, 100 K, 1e5 Pa, 1e5 W for duty and work, each
exact. The key is `T06-ens-v1|<profile>|<case>|<start:02d>|<joint:02d>|<coordinate>|<attempt:02d>`
with `<case>` the case's registered fixture id (the known answers' spelling:
`SYN-001-nominal`, `SYN-001-A02-360`, `SYN-001-UL-C1`, `SYN-001-T06-NET03`, …).

**The domain (§6.4).** Per coordinate, the plan's declared bounds (flows ≥ 0) intersected with
the provider's declared domain for `T` and `P`; a draw outside is redrawn with `attempt + 1`, cap
64. Per start, the assembly must succeed — on the tear path the SYN-001 traversal must admit the
tear (K03 §10.1's mixer check), on the revision path §2.2's step 5 must not refuse — else the whole
start is redrawn with `joint + 1`, cap 64, and the refusal recorded with its reason. A start that
cannot be generated within the caps is `F-GEN`; the generator reports it and never substitutes a
start.

**The coordinates (§6.2).** Per path: *tear* — the three tear flows `S6.n.<c>` about
`SYN-001-tear-init-v2`; *legacy EO with a freed guess* (NET-05) — the freed guess `S3.T` about
its registered value; *revision EO* — every stream coordinate `S.n.<c>`, `S.T`, `S.P` and every
unit-owned scalar `<U>.Q`, `<U>.W`, `<U>.xi` that no fixed specification pins, about
`traversal-G0-v1`'s start, after which every lifted split's columns are recomputed from the
perturbed streams by `revision.lifted_split_values` — `initial_state`'s own step 5 — with no PH
closure (the split is a function of the stream). A component that no feed carries and no
reaction touches is absent: its flows are held at `+0.0` and not selected.

The published document holds, per case, what is common to its starts (the initializer state,
the coordinates with their scales and boxes) and, per start, the draws, the rejections, the
start vector, the re-derived splits' regimes and the start's conditioning.

**This module is frozen with the file it wrote.** Its bytes' SHA-256 is recorded in the published
starts (`generator_sha256`), so an edit here makes the regeneration check fail by design: a changed
generator is a new starts file, which only a design-lane amendment made before any ensemble solve
may authorize (§6.4).
"""

from __future__ import annotations

import hashlib
import math
import platform
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np
import scipy

from openflowsheet.application.binding import Binding
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.canonical import canonical_json
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001.conversion_reactor import ConversionReactor, extent_id
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.ph_kernel import PHState
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.tear import Syn001TearProblem, build_plan
from openflowsheet.orchestrator.trace import SolvePlan, SolvePolicy
from openflowsheet.thermo import StreamState

__all__ = [
    "COORDINATE_CAP",
    "FORMAT",
    "INITIALIZERS",
    "JOINT_CAP",
    "KEY_PREFIX",
    "PROFILE",
    "RNG_ID",
    "SCALES",
    "STARTS_PER_CASE",
    "Assembled",
    "CaseSetup",
    "Coordinate",
    "CoordinateDraw",
    "GenerationFailure",
    "JointRefusal",
    "Start",
    "absent_components",
    "delta",
    "delta_of",
    "document",
    "draw_coordinate",
    "draw_key",
    "generate_case",
    "generate_start",
    "generator_sha256",
    "host",
    "k53",
    "legacy_setup",
    "perturbed",
    "revision_setup",
    "tear_setup",
    "uniform",
    "write",
]

#: Spec §6.3: the RNG/version identifier and the key's fixed prefix.
RNG_ID: Final = "sha256-counter-v1"
KEY_PREFIX: Final = "T06-ens-v1"
#: The gate's profile (§6.7's stress profiles are registered and run after the nominal gate).
PROFILE: Final = "nominal"
STARTS_PER_CASE: Final = 20
#: Spec §6.4's caps.
COORDINATE_CAP: Final = 64
JOINT_CAP: Final = 64
#: Spec §6.2: the registered physical nominals the `SolvePlan` records, by column kind. A plan
#: that records another scale is a defect of the premise, raised, never re-scaled here.
SCALES: Final[Mapping[str, float]] = {
    "molar_flow": 3.0,
    "temperature": 100.0,
    "pressure": 1e5,
    "heat_rate": 1e5,
}
#: The registered initializer of each path (`registry.yaml` `corpus.initializers`).
INITIALIZERS: Final[Mapping[str, str]] = {
    "revision_eo": revision.INITIALIZER_ID,
    "tear": "SYN-001-tear-init-v2",
    "legacy_eo": "T02-A02-pre-solve-v1",
}
#: The starts document's format id.
FORMAT: Final = "t06-ensemble-starts-v1"

SolvePath = Literal["revision_eo", "tear", "legacy_eo"]


# -- the draw (§6.3) ------------------------------------------------------------------------------


def draw_key(
    case: str,
    start: int,
    joint: int,
    coordinate: str,
    attempt: int,
    *,
    profile: str = PROFILE,
    prefix: str = KEY_PREFIX,
) -> str:
    return f"{prefix}|{profile}|{case}|{start:02d}|{joint:02d}|{coordinate}|{attempt:02d}"


def k53(key: str) -> int:
    """The first 8 bytes of SHA-256 of the key (UTF-8), big-endian, shifted right by 11."""
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") >> 11


def uniform(key: str) -> float:
    """`u = k · 2⁻⁵³`, exact: a 53-bit uniform on `[0, 1)`."""
    return k53(key) * 2.0**-53


def delta_of(u: float) -> float:
    """`δ = (2u − 1) / 5`: `2u − 1` is exact, the division is the one rounding (§6.3 (A2))."""
    w = 2.0 * u - 1.0
    return w / 5.0


def delta(key: str) -> float:
    return delta_of(uniform(key))


def perturbed(x_init: float, scale: float, step: float) -> float:
    """`x_init + S*δ` in two roundings: the product, then the sum."""
    product = scale * step
    return x_init + product


# -- coordinates and their draws --------------------------------------------------------------


@dataclass(frozen=True)
class Coordinate:
    """A selected coordinate: its id, its registered scale and its box (§6.4), `±inf` open."""

    id: str
    scale: float
    lower: float
    upper: float

    def admits(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass(frozen=True)
class CoordinateDraw:
    """One coordinate's accepted draw: the value, its `u`, the attempt it was accepted at, and
    each earlier attempt's side of the box (`below` or `above`)."""

    coordinate: str
    value: float
    u: float
    attempt: int
    rejected: tuple[str, ...]


def draw_coordinate(
    case: str, start: int, joint: int, coordinate: Coordinate, x_init: float
) -> CoordinateDraw | None:
    """§6.3–§6.4 for one coordinate: attempts `00…63` until the value lies in the box; `None`
    when the cap is exhausted (the start is then `F-GEN`)."""
    rejected: list[str] = []
    for attempt in range(COORDINATE_CAP):
        u = uniform(draw_key(case, start, joint, coordinate.id, attempt))
        value = perturbed(x_init, coordinate.scale, delta_of(u))
        if coordinate.admits(value):
            return CoordinateDraw(coordinate.id, value, u, attempt, tuple(rejected))
        rejected.append("below" if value < coordinate.lower else "above")
    return None


# -- the start assembly per path (§6.2) --------------------------------------------------------


@dataclass(frozen=True)
class JointRefusal:
    """A start-level refusal (§6.4): `kernel_refused` (revision step 5; the refusing unit, the
    kernel's status, the code `kernel_refused(<stream>)`) or `traversal_refused` (the tear
    path's traversal; its status and message's first line)."""

    reason: Literal["kernel_refused", "traversal_refused"]
    unit: str
    status: str
    code: str

    def as_document(self) -> dict[str, Any]:
        return {"reason": self.reason, "unit": self.unit, "status": self.status, "code": self.code}


@dataclass(frozen=True)
class Assembled:
    """An assembled start: the start vector (the full state over `variable_ids` on the revision
    path, `t` on the tear path, the guess for NET-05) and the regimes of its splits."""

    vector: dict[str, float]
    regimes: dict[str, str]


@dataclass(frozen=True)
class CaseSetup:
    """What every start of a case shares: its ids, path, initializer and initializer state, the
    selected coordinates, the columns held at `+0.0`, and the path's assembly and conditioning."""

    case: str
    fixture: str
    path: SolvePath
    initializer: str
    #: Over the start vector's ids (the revision path's `variable_ids`, the tear, the guess).
    x_init: Mapping[str, float]
    coordinates: tuple[Coordinate, ...]
    #: Every column of an absent component (§6.2's special parameterization), `+0.0` in `x_init`.
    held_zero: tuple[str, ...]
    assemble: Callable[[dict[str, float]], Assembled | JointRefusal]
    conditioning: Callable[[Assembled], dict[str, Any]]


def absent_components(units: Sequence[Any], components: Sequence[str]) -> tuple[str, ...]:
    """§6.2: the components whose flow is zero in every feed and whose stoichiometric coefficient
    is zero in every reaction, in `components` order. Read off the bound units; a flowsheet with
    no feed has no such reading and is a defect of the case."""
    feeds = [unit for unit in units if isinstance(unit, FeedSource)]
    reactors = [unit for unit in units if isinstance(unit, ConversionReactor)]
    if not feeds:
        raise ValueError("no feed source: the absent components are undefined")
    absent = []
    for component in components:
        carried = any(
            dict(zip(f.components, f.flows, strict=True))[component] != 0.0 for f in feeds
        )
        reacts = any(
            dict(zip(r.components, r.stoichiometry, strict=True))[component] != 0.0
            for r in reactors
        )
        if not carried and not reacts:
            absent.append(component)
    return tuple(absent)


def _box(
    kind: str, bound: tuple[float | None, float | None] | None, domain: Any
) -> tuple[float, float]:
    lower, upper = bound if bound is not None else (None, None)
    low = -math.inf if lower is None else float(lower)
    high = math.inf if upper is None else float(upper)
    if kind in ("temperature", "pressure"):
        d_low, d_high = domain["T" if kind == "temperature" else "P"]
        low, high = max(low, float(d_low)), min(high, float(d_high))
    return low, high


def _coordinate(column: str, kind: str, plan: SolvePlan, domain: Any) -> Coordinate:
    scale = float(plan.column_scales[column])
    if scale != SCALES[kind]:
        raise ValueError(
            f"{column}: the plan records scale {scale!r}, the registered nominal of a {kind} "
            f"column is {SCALES[kind]!r} (spec §6.2)"
        )
    low, high = _box(kind, plan.bounds.get(column), domain)
    return Coordinate(column, scale, low, high)


def _regime(vapor: float, liquid: float) -> str:
    """The region's regime words (T05b spec §6.2) of a split's re-derived totals."""
    if vapor == 0.0 and liquid == 0.0:
        return "ZERO_FLOW"
    if vapor == 0.0:
        return "LIQUID"
    if liquid == 0.0:
        return "VAPOR"
    return "TWO_PHASE"


def _conditioning(
    compiled: CompiledProblem,
    spec: ProblemSpec,
    context: EvaluationContext,
    scaling: Scaling,
    eliminated: frozenset[str],
    state: Mapping[str, float],
) -> dict[str, Any]:
    """The start's conditioning (§6.5): `‖F̂(x_start)‖∞` over the declaration's rows less the
    plan's eliminated alias rows, scaled by the plan's row scales, and the exact `rcond₁` of the
    scaled Jacobian on the same rows (dense inverse; every T06 matrix has `n ≤ 128`). Reported,
    never gated: it is the declaration's regime-free matrix, not the region's reduced one."""
    vector = np.array([float(state[name]) for name in spec.variable_ids], dtype=np.float64)
    evaluation = compiled.residual(vector, context)
    if evaluation.status != "ok" or evaluation.values is None:
        return {
            "residual_inf_scaled": None,
            "rcond_1": None,
            "reason": f"residual_{evaluation.status}",
        }
    kept = [row for row in evaluation.equation_ids if row not in eliminated]
    by_row = dict(zip(evaluation.equation_ids, evaluation.values, strict=True))
    residual = max(abs(float(by_row[row]) / scaling.row[row]) for row in kept)
    jacobian = compiled.jacobian(vector, context)
    if jacobian.status != "ok":
        return {
            "residual_inf_scaled": residual,
            "rcond_1": None,
            "reason": f"jacobian_{jacobian.status}",
        }
    rows: list[int] = []
    columns: list[int] = []
    for column in range(len(jacobian.col_ids)):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            rows.append(jacobian.indices[offset])
            columns.append(column)
    entries = scaling.scale_jacobian_entries(
        jacobian.data, rows, columns, jacobian.row_ids, jacobian.col_ids
    )
    dense = np.zeros((len(jacobian.row_ids), len(jacobian.col_ids)))
    for row, column, value in zip(rows, columns, entries, strict=True):
        dense[row, column] += value
    keep = [index for index, row in enumerate(jacobian.row_ids) if row not in eliminated]
    matrix = dense[keep, :]
    if matrix.shape[0] != matrix.shape[1]:
        return {
            "residual_inf_scaled": residual,
            "rcond_1": None,
            "reason": f"not_square({matrix.shape[0]}x{matrix.shape[1]})",
        }
    try:
        inverse = np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        return {"residual_inf_scaled": residual, "rcond_1": 0.0, "reason": "singular"}
    rcond = 1.0 / (float(np.linalg.norm(matrix, 1)) * float(np.linalg.norm(inverse, 1)))
    return {"residual_inf_scaled": residual, "rcond_1": rcond, "reason": None}


def revision_setup(
    case: str,
    fixture: str,
    binding: RevisionBinding,
    policy: SolvePolicy,
    pinned: Sequence[str],
) -> CaseSetup:
    """The revision path's setup. `pinned` is every column a `role: fixed` specification pins
    (`models.revision_flowsheet.pin_specifications`)."""
    flowsheet, spec = binding.flowsheet, binding.spec
    plan, _ = revision.plan_revision(binding, policy)
    if not isinstance(plan, ExecutionPlan):
        raise ValueError(f"{case}: the registered plan was refused: {plan}")
    (step,) = [step for step in plan.steps if step.kind == "solve_eo"]
    solve_plan = step.solve_plan
    assert solve_plan is not None
    registered = revision.traversal_start(flowsheet, spec.variable_ids)
    if isinstance(registered, revision.InitialStateFailure):
        raise ValueError(f"{case}: the registered initializer failed: {registered.message}")
    x_init = dict(registered.values)

    absent = absent_components(flowsheet.units(), flowsheet.components)
    splits = {
        split.unit: split
        for split in lifted_splits(revision.instances_of(flowsheet), flowsheet.components)
    }
    absent_columns = {
        flow_id(stream, component) for stream in flowsheet.streams for component in absent
    } | {
        column
        for split in splits.values()
        for index, component in enumerate(flowsheet.components)
        if component in absent
        for column in (split.vapor[index], split.liquid[index])
    }
    held_zero = tuple(name for name in spec.variable_ids if name in absent_columns)
    for name in held_zero:
        if x_init[name] != 0.0 or math.copysign(1.0, x_init[name]) < 0.0:
            raise ValueError(
                f"{case}: absent-component column {name} is {x_init[name]!r} at x_init"
            )
    candidates = {
        name
        for stream in flowsheet.streams
        for name in (
            *(flow_id(stream, component) for component in flowsheet.components),
            temperature_id(stream),
            pressure_id(stream),
        )
    } | {
        name
        for unit in flowsheet.units()
        for name in (duty_id(unit.unit_id), work_id(unit.unit_id), extent_id(unit.unit_id))
    }
    fixed, zero = set(pinned), set(held_zero)
    domain = flowsheet.provider.describe().domain
    coordinates = tuple(
        _coordinate(name, spec.variable_kinds[name], solve_plan, domain)
        for name in spec.variable_ids
        if name in candidates and name not in fixed and name not in zero
    )
    no_closures: dict[str, PHState | None] = dict.fromkeys(splits)

    def assemble(values: dict[str, float]) -> Assembled | JointRefusal:
        streams = {
            stream: StreamState(
                n=tuple(values[flow_id(stream, component)] for component in flowsheet.components),
                temperature=values[temperature_id(stream)],
                pressure=values[pressure_id(stream)],
            )
            for stream in flowsheet.streams
        }
        resplit = revision.lifted_split_values(flowsheet, values, streams, no_closures)
        if isinstance(resplit, revision.SplitRefusal):
            return JointRefusal(
                "kernel_refused", resplit.unit, resplit.status, f"kernel_refused({resplit.stream})"
            )
        merged = {**values, **resplit}
        regimes = {
            unit: _regime(merged[split.vapor_total], merged[split.liquid_total])
            for unit, split in splits.items()
        }
        return Assembled({name: merged[name] for name in spec.variable_ids}, regimes)

    compiled = compile_problem(spec)
    model_version, constants = declaration_identity(spec)
    context = EvaluationContext(
        model_version=model_version, constants_sha256=constants, phase_signature=None
    )
    scaling = Scaling.from_spec(spec)
    eliminated = frozenset(row.row_id for row in solve_plan.eliminated_rows)

    def conditioning(start: Assembled) -> dict[str, Any]:
        return _conditioning(compiled, spec, context, scaling, eliminated, start.vector)

    return CaseSetup(
        case=case,
        fixture=fixture,
        path="revision_eo",
        initializer=INITIALIZERS["revision_eo"],
        x_init=x_init,
        coordinates=coordinates,
        held_zero=held_zero,
        assemble=assemble,
        conditioning=conditioning,
    )


def tear_setup(case: str, fixture: str, binding: Binding, policy: SolvePolicy) -> CaseSetup:
    """The tear path's setup: the three tear flows about `SYN-001-tear-init-v2`, admitted by one
    traversal (K03 §10.1's check), conditioned at the traversal's reconstruction."""
    flowsheet = binding.flowsheet
    tear = Syn001TearProblem(flowsheet)
    solve_plan = build_plan(tear, policy)
    initial = flowsheet.initial_recycle()
    variables = tear.partition.tear_variables
    x_init = dict(zip(variables, initial.n, strict=True))
    absent = absent_components(flowsheet.units(), flowsheet.components)
    held_zero = tuple(
        name
        for name, component in zip(variables, flowsheet.components, strict=True)
        if component in absent
    )
    domain = flowsheet.provider.describe().domain
    coordinates = tuple(
        _coordinate(name, tear.spec.variable_kinds[name], solve_plan, domain)
        for name in variables
        if name not in held_zero
    )

    def assemble(values: dict[str, float]) -> Assembled | JointRefusal:
        recycle = tear.tear_state([values[name] for name in variables])
        traversal = flowsheet.traverse(recycle)
        if traversal.status != "ok":
            first = traversal.message.splitlines()[0] if traversal.message else ""
            return JointRefusal("traversal_refused", "", str(traversal.status), first)
        regimes = {
            stream: str(signature)
            for stream, signature in sorted(traversal.phase_signatures.items())
        }
        return Assembled({name: values[name] for name in variables}, regimes)

    eliminated = frozenset(row.row_id for row in tear.partition.elimination.eliminated)

    def conditioning(start: Assembled) -> dict[str, Any]:
        state = tear.reconstruct(tear.tear_state([start.vector[name] for name in variables]))
        return _conditioning(
            tear.compiled, tear.spec, tear.context, tear.scaling, eliminated, state
        )

    return CaseSetup(
        case=case,
        fixture=fixture,
        path="tear",
        initializer=INITIALIZERS["tear"],
        x_init=x_init,
        coordinates=coordinates,
        held_zero=held_zero,
        assemble=assemble,
        conditioning=conditioning,
    )


#: NET-05's freed guess (spec §6.2): the specification id and the coordinate it seeds.
GUESS_SPECIFICATION: Final = "GUESS-heater-outlet-T"
GUESS_COORDINATE: Final = "S3.T"


def legacy_setup(
    case: str, fixture: str, document: Mapping[str, Any], binding: Binding
) -> CaseSetup:
    """NET-05's setup: the freed guess `S3.T` about its registered value, in the provider's `T`
    domain. Every other start coordinate is the pre-solve's function of it (§6.2), so the start
    has no assembly beyond the guess and no conditioning before a solve."""
    (guess,) = [entry for entry in document["specifications"] if entry["id"] == GUESS_SPECIFICATION]
    if guess.get("unit") != "K" or guess["target"]["object_id"] != "S3":
        raise ValueError(f"{case}: {GUESS_SPECIFICATION} is not S3's temperature in K")
    x_init = {GUESS_COORDINATE: float(guess["value"])}
    low, high = binding.flowsheet.provider.describe().domain["T"]
    coordinates = (Coordinate(GUESS_COORDINATE, SCALES["temperature"], float(low), float(high)),)

    def assemble(values: dict[str, float]) -> Assembled | JointRefusal:
        return Assembled({GUESS_COORDINATE: values[GUESS_COORDINATE]}, {})

    def conditioning(start: Assembled) -> dict[str, Any]:
        return {
            "residual_inf_scaled": None,
            "rcond_1": None,
            "reason": "the region start is the pre-solve's function of the guess (spec §6.2)",
        }

    return CaseSetup(
        case=case,
        fixture=fixture,
        path="legacy_eo",
        initializer=INITIALIZERS["legacy_eo"],
        x_init=x_init,
        coordinates=coordinates,
        held_zero=(),
        assemble=assemble,
        conditioning=conditioning,
    )


# -- generation -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Start:
    """One generated start: its draws for the accepted joint attempt, the joint refusals before
    it (each with the number of coordinate rejections that attempt made), and the assembly."""

    index: int
    joint: int
    draws: tuple[CoordinateDraw, ...]
    joint_rejections: tuple[tuple[int, int, JointRefusal], ...]
    assembled: Assembled
    conditioning: Mapping[str, Any]


@dataclass(frozen=True)
class GenerationFailure:
    """`F-GEN` (spec §6.4, §7.2): the start could not be generated within the caps."""

    index: int
    reason: str
    joint_rejections: tuple[tuple[int, int, JointRefusal], ...]


def generate_start(setup: CaseSetup, index: int) -> Start | GenerationFailure:
    refusals: list[tuple[int, int, JointRefusal]] = []
    for joint in range(JOINT_CAP):
        values = dict(setup.x_init)
        draws: list[CoordinateDraw] = []
        for coordinate in setup.coordinates:
            drawn = draw_coordinate(
                setup.fixture, index, joint, coordinate, setup.x_init[coordinate.id]
            )
            if drawn is None:
                return GenerationFailure(
                    index, f"coordinate_cap({coordinate.id}, joint {joint})", tuple(refusals)
                )
            values[coordinate.id] = drawn.value
            draws.append(drawn)
        assembled = setup.assemble(values)
        if isinstance(assembled, JointRefusal):
            refusals.append((joint, sum(len(d.rejected) for d in draws), assembled))
            continue
        for name in setup.held_zero:
            if name in assembled.vector and (
                assembled.vector[name] != 0.0 or math.copysign(1.0, assembled.vector[name]) < 0.0
            ):
                raise ValueError(f"{setup.case} start {index}: {name} is not +0.0")
        return Start(
            index, joint, tuple(draws), tuple(refusals), assembled, setup.conditioning(assembled)
        )
    return GenerationFailure(index, "joint_cap", tuple(refusals))


def generate_case(setup: CaseSetup) -> tuple[list[Start], list[GenerationFailure]]:
    starts: list[Start] = []
    failures: list[GenerationFailure] = []
    for index in range(STARTS_PER_CASE):
        result = generate_start(setup, index)
        if isinstance(result, Start):
            starts.append(result)
        else:
            failures.append(result)
    return starts, failures


def generator_sha256() -> str:
    """The generator code's SHA-256 (§6.5): this module's bytes."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _bound(value: float) -> float | None:
    return None if math.isinf(value) else value


def _draw_document(draw: CoordinateDraw) -> dict[str, Any]:
    return {
        "coordinate": draw.coordinate,
        "u": draw.u,
        "attempt": draw.attempt,
        "rejected": list(draw.rejected),
    }


def _refusals(refusals: Sequence[tuple[int, int, JointRefusal]]) -> list[dict[str, Any]]:
    return [
        {"joint": joint, "coordinate_rejections": count, **refusal.as_document()}
        for joint, count, refusal in refusals
    ]


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text("utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def host() -> dict[str, str]:
    """The generating host (the reference machine class's fingerprint, §7.5): what the byte-for-
    byte regeneration check compares before it promises bytes."""
    return {
        "machine_class": "ref-x86-64",
        "architecture": platform.machine(),
        "cpu_model": _cpu_model(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def document(
    generated: Sequence[tuple[CaseSetup, Sequence[Start], Sequence[GenerationFailure]]],
    *,
    policies: Mapping[str, str],
    provider: Mapping[str, str],
    machine: Mapping[str, str],
) -> dict[str, Any]:
    """The published starts document (§6.5). `policies` maps each case to its registered policy
    id; `provider` is the provider's identity (`describe()`'s three hashes); `machine` the
    generating host (`host()`)."""
    cases: list[dict[str, Any]] = []
    accepted = coordinate_rejections = joint_rejections = failed = 0
    reasons: dict[str, int] = {}
    for setup, starts, failures in generated:
        records = []
        for start in starts:
            accepted += 1
            coordinate_rejections += sum(len(d.rejected) for d in start.draws)
            coordinate_rejections += sum(count for _, count, _ in start.joint_rejections)
            joint_rejections += len(start.joint_rejections)
            for _, _, refusal in start.joint_rejections:
                label = f"{refusal.reason}({refusal.unit}:{refusal.status})"
                reasons[label] = reasons.get(label, 0) + 1
            records.append(
                {
                    "start": start.index,
                    "key_prefix": f"{KEY_PREFIX}|{PROFILE}|{setup.fixture}|{start.index:02d}",
                    "joint_attempts": start.joint + 1,
                    "joint_rejections": _refusals(start.joint_rejections),
                    "draws": [_draw_document(d) for d in start.draws],
                    "vector": dict(start.assembled.vector),
                    "regimes": dict(start.assembled.regimes),
                    "conditioning": dict(start.conditioning),
                }
            )
        failed += len(failures)
        cases.append(
            {
                "case": setup.case,
                "fixture": setup.fixture,
                "path": setup.path,
                "policy": policies[setup.case],
                "initializer": setup.initializer,
                "x_init": dict(setup.x_init),
                "coordinates": [
                    {
                        "id": c.id,
                        "scale": c.scale,
                        "lower": _bound(c.lower),
                        "upper": _bound(c.upper),
                    }
                    for c in setup.coordinates
                ],
                "held_zero": list(setup.held_zero),
                "starts": records,
                "generation_failures": [
                    {
                        "start": f.index,
                        "reason": f.reason,
                        "joint_rejections": _refusals(f.joint_rejections),
                    }
                    for f in failures
                ],
            }
        )
    return {
        "format": FORMAT,
        "specification": "docs/derivations/T06-corpus-spec.md §6.2-§6.5 (Amendments 1 and 2)",
        "rng": RNG_ID,
        "key_prefix": KEY_PREFIX,
        "profile": PROFILE,
        "key": f"{KEY_PREFIX}|<profile>|<fixture>|<start:02d>|<joint:02d>|<coordinate id>"
        "|<attempt:02d>",
        "arithmetic": "u = k*2^-53; delta = (2.0*u - 1.0)/5.0; "
        "x = x_init + S*delta (two roundings)",
        "generator": "benchmarks/t06/generator.py",
        "generator_sha256": generator_sha256(),
        "provider": dict(provider),
        "host": dict(machine),
        "caps": {"coordinate_attempts": COORDINATE_CAP, "joint_attempts": JOINT_CAP},
        "starts_per_case": STARTS_PER_CASE,
        "counts": {
            "cases": len(cases),
            "starts_accepted": accepted,
            "generation_failures": failed,
            "coordinate_rejections": coordinate_rejections,
            "joint_rejections": joint_rejections,
            "joint_rejection_reasons": reasons,
        },
        "cases": cases,
    }


def write(path: Path, starts: Mapping[str, Any]) -> str:
    """Write the document's canonical JSON bytes (ADR 0002) and return their SHA-256, which is
    then the file's and the registry's `starts_sha256`."""
    raw = canonical_json(starts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
