"""The optimization request: its rules, its starts, its formulation, and its static readiness.

OPT design §4.3, §4.5 (static phase), §4.11; ADR 0071 D2, D8, D10 (WO-3).

**The request** (`schemas/optimization-request.schema.json`) names a stored revision's `role:
fixed` specifications as decisions, each with a box, a scale and the internal SI unit of its kind;
an objective with a sense and a scale; inequality constraints; the starts; an optional
assessment. The revision is never edited. `request_problems` is the schema plus the rules a JSON
Schema cannot state; a request with problems has no formulation.

**The formulation** (`request_formulation`) is M03's `NlpFormulation` through the decision map
(`revision_host.decision_map`): decision ids are the parameter ids the bind probes found; an
expression's `decision:<specification>` is that parameter, a state id is itself, an
`assessment:<id>` is unchanged. The objective is stored as `minimize s·expr/scale`, s = +1 for
`minimize` and −1 for `maximize`, coefficient by coefficient as `(s·c)/scale`.

**The starts**, in order: (0) the revision's own values (the base binding's parameters, so in
internal units by construction); the `explicit` ones; Halton points k = 1…m of the unscrambled
sequence, dimension j on the j-th prime, `lower + u·(upper − lower)` with u the radical inverse
in binary64 (no random number generator).

**Static readiness** (`static_readiness`) solves nothing: the reasons of design §4.5's static row
in its order, and the checks that could not run with why. The assessment checks that need the
program (`ASSESSMENT_OUTPUT_UNKNOWN` against what it publishes, `ASSESSMENT_PARAMETER_*`) are the
start phase's: E01 plans a program at a solved state (`AssessmentProgram.build`), so statically
only "an `assessment:` name with no assessment" is decided (OPT D-18).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final, Literal

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.resources import packaged
from openflowsheet.studies.nlp.closure import (
    READINESS_ORDER,
    ReadinessCode,
    ReadinessReason,
    SolverAvailability,
    SolverProbe,
    audited_solver,
)
from openflowsheet.studies.nlp.formulation import (
    HESSIAN_APPROXIMATION,
    Decision,
    InequalityConstraint,
    NlpFormulation,
    QuadraticExpression,
    is_assessment_name,
)
from openflowsheet.studies.nlp.revision_host import (
    ROUTE,
    DecisionBox,
    DecisionMap,
    RevisionUnboundError,
    decision_map,
)

REQUEST_FORMAT: Final = "openflowsheet-optimization-request-v1"
SCHEMA_REFERENCE: Final = "optimization-request.schema.json"
#: Design §4.3: 1…32 starts in total, else `TOO_MANY_STARTS`.
MAX_STARTS: Final = 32
#: The request's name of a decision's own value in an expression.
DECISION_PREFIX: Final = "decision:"
#: Design §4.5's static row, in its order: the codes `static_readiness` decides.
STATIC_CODES: Final[tuple[ReadinessCode, ...]] = (
    "REVISION_MISMATCH",
    "REVISION_UNBOUND",
    "OPTIMIZATION_ROUTE_UNAVAILABLE",
    "UNKNOWN_DECISION",
    "DECISION_UNIT_NOT_INTERNAL",
    "DECISION_NOT_CONTINUOUS",
    "BOUNDS_UNDECLARED",
    "START_OUTSIDE_BOUNDS",
    "TOO_MANY_STARTS",
    "UNKNOWN_VARIABLE",
    "ASSESSMENT_OUTPUT_UNKNOWN",
    "ASSESSMENT_PARAMETER_STRUCTURAL",
    "ASSESSMENT_PARAMETER_DECISION",
    "HESSIAN_UNAVAILABLE",
    "NLP_SOLVER_UNAVAILABLE",
)
#: One prime per Halton dimension; a request has at most 64 decisions (the schema's `maxItems`).
HALTON_PRIMES: Final[tuple[int, ...]] = tuple(
    n for n in range(2, 312) if all(n % d for d in range(2, math.isqrt(n) + 1))
)[:64]

Sense = Literal["minimize", "maximize"]


# -- the document --------------------------------------------------------------------------------


@cache
def _request_validator() -> Draft202012Validator:
    """The request schema's validator, built as `application.types.schema_errors` builds it: the
    published schemas registered by `$id` in file-name order, the request schema by `$ref` to its
    `$id`. `studies` never imports `application` (M04's rule), so the reading is repeated here;
    `test_opt_request` holds the two to the same errors."""
    published: dict[str, Any] = {}
    for entry in sorted(packaged("schemas").iterdir(), key=lambda entry: entry.name):
        if entry.name.endswith(".schema.json"):
            document = json.loads(entry.read_text(encoding="utf-8"))
            published[document["$id"]] = document
    registry: Registry[Any] = Registry().with_resources(
        (schema_id, DRAFT202012.create_resource(document))
        for schema_id, document in published.items()
    )
    (reference,) = [name for name in published if name.endswith("/" + SCHEMA_REFERENCE)]
    return Draft202012Validator({"$ref": reference}, registry=registry)


def _pointer(path: Sequence[str | int]) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


def _schema_errors(request: Any) -> list[str]:
    """Every error of `request` against the request schema, as `<pointer>: <message>` in pointer
    order (`application.types.schema_errors`'s form)."""
    found = sorted(_request_validator().iter_errors(request), key=lambda e: list(e.absolute_path))
    return [f"{_pointer(list(error.absolute_path))}: {error.message}" for error in found]


def request_problems(request: Any) -> list[tuple[str, str]]:
    """Every problem of `request` as `(pointer, message)`: none for a well-formed request.

    First a node with no canonical JSON form (ADR 0002, as the revision reader refuses it), then
    the schema's errors in pointer order, then the rules the schema cannot state."""
    pointer = first_noncanonical(request)
    if pointer is not None:
        return [(pointer, f"document_not_canonical({pointer})")]
    errors = _schema_errors(request)
    if errors:
        return [_split(error) for error in errors]
    problems: list[tuple[str, str]] = []
    decisions = [entry["specification_id"] for entry in request["decisions"]]
    for index, name in enumerate(decisions):
        if name in decisions[:index]:
            problems.append((f"/decisions/{index}", f"specification {name!r} repeats"))
    for index, start in enumerate((request.get("starts") or {}).get("explicit", ())):
        if len(start) != len(decisions):
            problems.append(
                (
                    f"/starts/explicit/{index}",
                    f"{len(start)} values for {len(decisions)} decisions",
                )
            )
    expressions = [("/objective/expression", request["objective"]["expression"])]
    seen: set[str] = set()
    for index, constraint in enumerate(request.get("constraints", ())):
        if constraint["id"] in seen:
            problems.append((f"/constraints/{index}/id", f"{constraint['id']!r} repeats"))
        seen.add(constraint["id"])
        expressions.append((f"/constraints/{index}/expression", constraint["expression"]))
    for where, expression in expressions:
        if not expression.get("linear") and not expression.get("quadratic"):
            problems.append((where, "an expression names at least one variable"))
        pairs = [(term["a"], term["b"]) for term in expression.get("quadratic", ())]
        for index, pair in enumerate(pairs):
            if pair in pairs[:index]:
                problems.append((f"{where}/quadratic/{index}", f"the pair {list(pair)} repeats"))
    return problems


def _split(error: str) -> tuple[str, str]:
    pointer, _, message = error.partition(": ")
    return pointer, message


def request_sha256(request: Mapping[str, Any]) -> str:
    """ADR 0002: SHA-256 of the request's canonical JSON bytes, as given."""
    return document_sha256(request)


@dataclass(frozen=True)
class OptimizationRequest:
    """A well-formed request (`request_problems` empty) with the schema's defaults applied."""

    document: Mapping[str, Any]
    problem_id: str
    revision_sha256: str | None
    decisions: tuple[DecisionBox, ...]
    scales: tuple[float, ...]
    sense: Sense
    objective: Mapping[str, Any]
    objective_scale: float
    constraints: tuple[Mapping[str, Any], ...]
    include_revision: bool
    explicit: tuple[tuple[float, ...], ...]
    halton: int
    assessment: Mapping[str, Any] | None
    max_iter: int
    max_wall_time_s: float
    hessian: str
    sha256: str = field(compare=False, default="")

    @classmethod
    def of(cls, request: Mapping[str, Any]) -> OptimizationRequest:
        """The request read; raises `ValueError` naming the first problem of an ill-formed one."""
        problems = request_problems(request)
        if problems:
            pointer, message = problems[0]
            raise ValueError(f"request_invalid({pointer}): {message}")
        starts = request.get("starts") or {}
        options = request.get("options") or {}
        objective = request["objective"]
        return cls(
            document=request,
            problem_id=request["problem_id"],
            revision_sha256=request.get("revision_sha256"),
            decisions=tuple(
                DecisionBox(
                    entry["specification_id"],
                    _number(entry["lower"]),
                    _number(entry["upper"]),
                    entry["unit"],
                )
                for entry in request["decisions"]
            ),
            scales=tuple(float(entry["scale"]) for entry in request["decisions"]),
            sense=objective["sense"],
            objective=objective["expression"],
            objective_scale=float(objective.get("scale", 1)),
            constraints=tuple(request.get("constraints", ())),
            include_revision=bool(starts.get("include_revision", True)),
            explicit=tuple(
                tuple(float(value) for value in start) for start in starts.get("explicit", ())
            ),
            halton=int(starts.get("halton", 0)),
            assessment=request.get("assessment"),
            max_iter=int(options.get("max_iter", 500)),
            max_wall_time_s=float(options.get("max_wall_time_s", 120)),
            hessian=request.get("hessian", HESSIAN_APPROXIMATION),
            sha256=request_sha256(request),
        )

    @property
    def specification_ids(self) -> tuple[str, ...]:
        return tuple(box.specification_id for box in self.decisions)

    @property
    def start_count(self) -> int:
        return int(self.include_revision) + len(self.explicit) + self.halton

    def names(self) -> tuple[str, ...]:
        """Every name the objective and the constraints use, in first-mention order."""
        named: list[str] = []
        for expression in (self.objective, *(c["expression"] for c in self.constraints)):
            named.extend(expression.get("linear", {}))
            for term in expression.get("quadratic", ()):
                named.extend((term["a"], term["b"]))
        return tuple(dict.fromkeys(named))


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


# -- starts --------------------------------------------------------------------------------------


def radical_inverse(k: int, base: int) -> float:
    """The van der Corput radical inverse of `k ≥ 0` in `base`, in binary64:
    `f ← f/b; u ← u + f·digit` over the base-`b` digits of `k`, least significant first."""
    if k < 0 or base < 2:
        raise ValueError(f"radical_inverse needs k ≥ 0 and base ≥ 2 (k={k}, base={base})")
    u, f = 0.0, 1.0
    while k > 0:
        k, digit = divmod(k, base)
        f = f / base
        u = u + f * digit
    return u


def halton_point(k: int, dimension: int) -> tuple[float, ...]:
    """The k-th point (k ≥ 1) of the unscrambled Halton sequence in the unit cube, dimension j on
    the j-th prime."""
    if dimension > len(HALTON_PRIMES):
        raise ValueError(f"at most {len(HALTON_PRIMES)} Halton dimensions")
    return tuple(radical_inverse(k, prime) for prime in HALTON_PRIMES[:dimension])


def request_starts(
    request: OptimizationRequest, revision_values: Sequence[float] | None
) -> tuple[tuple[float, ...], ...]:
    """Design §4.3's starts in order. `revision_values` is start 0 (one value per decision, in
    request order), required when `include_revision`. Halton points need every box finite."""
    starts: list[tuple[float, ...]] = []
    if request.include_revision:
        if revision_values is None:
            raise ValueError("start 0 needs the revision's values")
        starts.append(tuple(float(value) for value in revision_values))
    starts.extend(request.explicit)
    for k in range(1, request.halton + 1):
        unit = halton_point(k, len(request.decisions))
        point = []
        for box, u in zip(request.decisions, unit, strict=True):
            if box.lower is None or box.upper is None:
                raise ValueError(f"{box.specification_id}: a Halton start needs a finite box")
            point.append(box.lower + u * (box.upper - box.lower))
        starts.append(tuple(point))
    return tuple(starts)


# -- the formulation -----------------------------------------------------------------------------


def _expression(
    document: Mapping[str, Any],
    parameters: Mapping[str, str],
    *,
    factor: float = 1.0,
    divisor: float = 1.0,
    text: str | None = None,
) -> QuadraticExpression:
    """`document` with names translated and every coefficient `(factor·c)/divisor`."""

    def name(raw: str) -> str:
        if raw.startswith(DECISION_PREFIX):
            return parameters[raw[len(DECISION_PREFIX) :]]
        return raw

    def scaled(value: Any) -> float:
        return (factor * float(value)) / divisor

    quadratic: dict[tuple[str, str], float] = {}
    for term in document.get("quadratic", ()):
        quadratic[(name(term["a"]), name(term["b"]))] = scaled(term["coefficient"])
    return QuadraticExpression(
        linear={name(key): scaled(value) for key, value in document.get("linear", {}).items()},
        quadratic=quadratic,
        constant=scaled(document.get("constant", 0)),
        text=document.get("text", "") if text is None else text,
    )


def objective_text(request: OptimizationRequest) -> str:
    """Design §4.3: the stored objective's text — the request's when it is minimised unscaled,
    else `(…)/scale`, negated `-(…)` for `maximize`; the scale in its canonical JSON spelling."""
    text = request.objective.get("text", "")
    if request.sense == "minimize" and request.objective_scale == 1.0:
        return text  # type: ignore[no-any-return]
    sign = "-" if request.sense == "maximize" else ""
    if request.objective_scale == 1.0:
        return f"{sign}({text})"
    scale = canonical_json(request.document["objective"]["scale"]).decode("ascii")
    return f"{sign}({text})/{scale}"


def request_formulation(
    request: OptimizationRequest,
    decisions: DecisionMap,
    starts: Sequence[Sequence[float]],
) -> NlpFormulation:
    """M03's formulation of `request` through the decision map (design §4.4's first paragraph).

    The assessment binding is not built here: E01 takes its output scales at a certified state,
    the first start that passes (§4.5), so the job's start phase adds it."""
    parameters = dict(decisions.parameters)
    sign = -1.0 if request.sense == "maximize" else 1.0
    return NlpFormulation(
        problem_id=request.problem_id,
        decisions=tuple(
            Decision(parameters[box.specification_id], box.lower, box.upper, scale)
            for box, scale in zip(request.decisions, request.scales, strict=True)
        ),
        objective=_expression(
            request.objective,
            parameters,
            factor=sign,
            divisor=request.objective_scale,
            text=objective_text(request),
        ),
        constraints=tuple(
            InequalityConstraint(
                constraint["id"],
                _expression(constraint["expression"], parameters),
                _number(constraint["lower"]),
                _number(constraint["upper"]),
            )
            for constraint in request.constraints
        ),
        starts=tuple(tuple(float(value) for value in start) for start in starts),
        hessian=request.hessian,
    )


# -- static readiness ----------------------------------------------------------------------------


@dataclass(frozen=True)
class StaticReadiness:
    """Design §4.5's static phase: the request's problems, every failing reason in the table's
    order, the checks that could not run (code → why), and what the phase found."""

    problems: tuple[tuple[str, str], ...]
    reasons: tuple[ReadinessReason, ...]
    not_run: Mapping[ReadinessCode, str]
    solver: SolverAvailability
    request: OptimizationRequest | None = None
    decisions: DecisionMap | None = None
    starts: tuple[tuple[float, ...], ...] | None = None
    formulation: NlpFormulation | None = None

    @property
    def ready(self) -> bool:
        return not self.problems and not self.reasons and not self.not_run

    @property
    def codes(self) -> tuple[ReadinessCode, ...]:
        return tuple(dict.fromkeys(reason.code for reason in self.reasons))


def static_readiness(
    request: Mapping[str, Any],
    revision: Mapping[str, Any],
    *,
    surrogates: Any = None,
    solver_probe: SolverProbe = audited_solver,
) -> StaticReadiness:
    """Design §4.5's static row for `request` on the stored `revision`: binds the revision and
    the decision probes, solves nothing. Every failing reason is listed, in the table's order; a
    check whose input is missing (a request with problems, a revision not on `revision_eo`) is
    in `not_run`. Ready iff no problem, no reason and nothing not run; then `formulation` is the
    request's `NlpFormulation`."""
    from openflowsheet.application.binding import refusal_code
    from openflowsheet.application.revision_run import NoRoute, select_route

    solver = solver_probe()
    problems = tuple(request_problems(request))
    reasons: list[ReadinessReason] = []
    not_run: dict[ReadinessCode, str] = {}

    def skip(codes: Sequence[ReadinessCode], why: str) -> None:
        for code in codes:
            not_run.setdefault(code, why)

    if not solver.available:
        reasons.append(ReadinessReason("NLP_SOLVER_UNAVAILABLE", solver.detail))
    if problems:
        pointer, message = problems[0]
        skip(
            [code for code in STATIC_CODES if code != "NLP_SOLVER_UNAVAILABLE"],
            f"the request is not well formed: {pointer or '/'}: {message}",
        )
        return StaticReadiness(problems, _ordered(reasons), not_run, solver)
    parsed = OptimizationRequest.of(request)

    # Request-only checks: they need no revision.
    if parsed.revision_sha256 is not None:
        stored = document_sha256(revision)
        if parsed.revision_sha256 != stored:
            reasons.append(
                ReadinessReason(
                    "REVISION_MISMATCH",
                    f"the request names revision {parsed.revision_sha256}; the stored revision "
                    f"is {stored}",
                )
            )
    for box, scale in zip(parsed.decisions, parsed.scales, strict=True):
        decision = Decision(box.specification_id, box.lower, box.upper, scale)
        if not decision.bounded:
            reasons.append(
                ReadinessReason(
                    "BOUNDS_UNDECLARED",
                    f"{box.specification_id}: the box [{box.lower!r}, {box.upper!r}] is not "
                    "finite with lower < upper",
                    box.specification_id,
                )
            )
    for index, start in enumerate(parsed.explicit, start=int(parsed.include_revision)):
        reasons.extend(_outside(parsed, index, start))
    count = parsed.start_count
    if not 1 <= count <= MAX_STARTS:
        reasons.append(
            ReadinessReason("TOO_MANY_STARTS", f"{count} starts; a request has 1 to {MAX_STARTS}")
        )
    named = parsed.names()
    for name in named:
        if name.startswith(DECISION_PREFIX) and (
            name[len(DECISION_PREFIX) :] not in parsed.specification_ids
        ):
            reasons.append(
                ReadinessReason(
                    "UNKNOWN_VARIABLE", f"{name!r} names no decision of the request", name
                )
            )
    assessment_named = [name for name in named if is_assessment_name(name)]
    if assessment_named and parsed.assessment is None:
        reasons.extend(
            ReadinessReason(
                "ASSESSMENT_OUTPUT_UNKNOWN",
                f"{name} is named and the request has no assessment",
                name.split(":", 1)[1],
            )
            for name in assessment_named
        )
    if parsed.hessian != HESSIAN_APPROXIMATION:
        reasons.append(
            ReadinessReason(
                "HESSIAN_UNAVAILABLE",
                f"Hessian {parsed.hessian!r} requested; Capabilities.hessian is absent and the "
                f"only policy is Ipopt's {HESSIAN_APPROXIMATION} approximation",
            )
        )

    # The revision: its route, then the decision probes and the state names on its binding.
    revision_codes: list[ReadinessCode] = [
        "UNKNOWN_DECISION",
        "DECISION_UNIT_NOT_INTERNAL",
        "DECISION_NOT_CONTINUOUS",
        "UNKNOWN_VARIABLE",
    ]
    if parsed.include_revision:
        revision_codes.append("START_OUTSIDE_BOUNDS")
    route = select_route(revision, surrogates=surrogates)
    if isinstance(route, NoRoute):
        reasons.append(
            ReadinessReason(
                "REVISION_UNBOUND",
                f"REVISION_UNBOUND({refusal_code(route.revision.detail)}): "
                f"{route.revision.kind}({route.revision.detail})",
            )
        )
        skip(revision_codes, "the revision does not bind")
        return _finish(problems, reasons, not_run, solver, parsed)
    if route.solve_path != ROUTE:
        reasons.append(
            ReadinessReason(
                "OPTIMIZATION_ROUTE_UNAVAILABLE",
                f"the revision solves on {route.solve_path}; optimisation needs {ROUTE}",
                route.solve_path,
            )
        )
        skip(revision_codes, f"the revision is not on {ROUTE}")
        return _finish(problems, reasons, not_run, solver, parsed)
    spec = route.binding.spec
    for name in named:
        if (
            not name.startswith(DECISION_PREFIX)
            and not is_assessment_name(name)
            and name not in spec.variable_ids
        ):
            reasons.append(
                ReadinessReason(
                    "UNKNOWN_VARIABLE", f"{name!r} is not a variable of {spec.label!r}", name
                )
            )
    probed = [box for box in parsed.decisions if _ends(box)]
    unprobed = [box.specification_id for box in parsed.decisions if not _ends(box)]
    try:
        found = decision_map(revision, probed, surrogates=surrogates) if probed else None
    except RevisionUnboundError as error:
        unbound = error.unbound
        reasons.append(
            ReadinessReason(
                "REVISION_UNBOUND",
                f"REVISION_UNBOUND({refusal_code(unbound.detail)}): {error}",
            )
        )
        skip(revision_codes, "the revision does not bind")
        return _finish(problems, reasons, not_run, solver, parsed)
    mapping: DecisionMap | None = None
    if isinstance(found, tuple):
        reasons.extend(
            ReadinessReason(refusal.code, refusal.detail, refusal.specification_id)
            for refusal in found
        )
    elif found is not None:
        mapping = found
    if unprobed:
        # No finite end, no probe: BOUNDS_UNDECLARED is the reason, continuity was not judged.
        skip(
            ["DECISION_NOT_CONTINUOUS"],
            f"no finite box end to probe for {','.join(unprobed)} (BOUNDS_UNDECLARED)",
        )
    revision_values: tuple[float, ...] | None = None
    if mapping is not None and not unprobed:
        base = route.binding.spec.parameters
        revision_values = tuple(base[mapping.parameters[name]] for name in parsed.specification_ids)
        if parsed.include_revision:
            reasons.extend(_outside(parsed, 0, revision_values))
    elif parsed.include_revision:
        skip(["START_OUTSIDE_BOUNDS"], "start 0 needs every decision's parameter")
    return _finish(problems, reasons, not_run, solver, parsed, mapping, revision_values)


def _ends(box: DecisionBox) -> bool:
    return any(v is not None and math.isfinite(v) for v in (box.lower, box.upper))


def _outside(
    request: OptimizationRequest, index: int, start: Sequence[float]
) -> list[ReadinessReason]:
    reasons = []
    for box, value in zip(request.decisions, start, strict=True):
        if box.lower is None or box.upper is None or not box.lower < box.upper:
            continue  # BOUNDS_UNDECLARED's case: no box to be outside of (M03's rule)
        if not box.lower <= value <= box.upper:
            reasons.append(
                ReadinessReason(
                    "START_OUTSIDE_BOUNDS",
                    f"start {index}: {box.specification_id} = {value!r} is outside "
                    f"[{box.lower!r}, {box.upper!r}]",
                    box.specification_id,
                )
            )
    return reasons


def _ordered(reasons: Sequence[ReadinessReason]) -> tuple[ReadinessReason, ...]:
    order = {code: index for index, code in enumerate(READINESS_ORDER)}
    return tuple(sorted(reasons, key=lambda reason: order[reason.code]))


def _finish(
    problems: tuple[tuple[str, str], ...],
    reasons: list[ReadinessReason],
    not_run: dict[ReadinessCode, str],
    solver: SolverAvailability,
    request: OptimizationRequest,
    mapping: DecisionMap | None = None,
    revision_values: tuple[float, ...] | None = None,
) -> StaticReadiness:
    ordered = _ordered(reasons)
    starts = formulation = None
    if not ordered and not not_run and mapping is not None:
        starts = request_starts(request, revision_values)
        formulation = request_formulation(request, mapping, starts)
    return StaticReadiness(
        problems, ordered, dict(not_run), solver, request, mapping, starts, formulation
    )
