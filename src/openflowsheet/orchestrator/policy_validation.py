"""Registration checks of a project solve policy (ADR 0078 D4.3, X06).

A project may register a solve-policy document (`solve-policy.schema.json`, unchanged) under a
`user.` id; a job then names it as it names an offered policy. `solve_policy_problems` is the
check registration runs, pure and in D4.3's order:

(a) the schema; (b) the id pattern (`solve_policy_id_invalid`); (c) the round trip
`canonical(SolvePolicy.from_document(d).as_document()) == canonical(d)`, so no member is
defaulted, dropped or reinterpreted; (d) every member the schema leaves open, checked against
the registry the solver reads it from (`solve_policy_invalid`):

- `initializer_chain` entries: `POLICY_INITIALIZERS`, the start sources a registered policy's
  chain names (the executor reads `compatible_warm_start` from it; `traversal-G0-v1` is the
  registered initializer it falls back to);
- `linear_solver`: the one linear solver the solver runs, `REGISTERED_LINEAR_SOLVER` (ADR 0004
  D1, SuperLU with its recorded options), member for member: the executor never reads another, so
  a policy declaring one would record what did not run;
- the keys of `residual_tolerances` and `scales`: `QUANTITY_KINDS`, the solver's registered
  residual kinds (`models.lifted_tolerance.KIND_TOLERANCE`);
- the open strings under `recycle`: `recycle.policy_id` in `RECYCLE_POLICY_IDS`; `tear_streams`
  names streams of one flowsheet and has no registry, so a registered policy carries none (every
  value is unknown at registration). `globalization` has no open string: every member is a
  `const`, an `enum`, a number or a fraction pattern.

The certificate does not depend on any of this: the verifier reads no solve policy (D4.2).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, NamedTuple

from openflowsheet.canonical import canonical_json
from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE
from openflowsheet.numerics.solve_record import RecyclePolicy, SolvePolicy
from openflowsheet.orchestrator.revision import INITIALIZER_ID
from openflowsheet.orchestrator.warm_start import WARM_START_SOURCE
from openflowsheet.schema_check import schema_errors

__all__ = [
    "POLICY_INITIALIZERS",
    "PROJECT_POLICY_ID",
    "QUANTITY_KINDS",
    "RECYCLE_POLICY_IDS",
    "REGISTERED_LINEAR_SOLVER",
    "SOLVE_POLICY_ID_INVALID",
    "SOLVE_POLICY_INVALID",
    "PolicyProblem",
    "is_project_policy_id",
    "solve_policy_problems",
]

SCHEMA: Final = "solve-policy.schema.json"
#: ADR 0078 D4.1: the id a project policy is registered under.
PROJECT_POLICY_ID: Final = re.compile(r"^user\.[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
#: D4.3 (b): `detail.code` of an id outside `PROJECT_POLICY_ID` (`invalid_request`).
SOLVE_POLICY_ID_INVALID: Final = "solve_policy_id_invalid"
#: D4.3 (c), (d): `detail.code` of a member the solver would not read as written.
SOLVE_POLICY_INVALID: Final = "solve_policy_invalid"

#: D4.3 (d): the start sources a policy's `initializer_chain` may name.
POLICY_INITIALIZERS: Final = frozenset({WARM_START_SOURCE, INITIALIZER_ID})
#: D4.3 (d): the linear solver the solver runs (`SolvePolicy`'s default, ADR 0004 D1).
REGISTERED_LINEAR_SOLVER: Final[Mapping[str, Any]] = SolvePolicy(
    policy_id="-", residual_tolerances={}, scales={}
).linear_solver
#: D4.3 (d): the quantity kinds `residual_tolerances` and `scales` may be keyed by.
QUANTITY_KINDS: Final = frozenset(KIND_TOLERANCE)
#: D4.3 (d): the recycle policies the solver knows (ADR 0009 D2).
RECYCLE_POLICY_IDS: Final = frozenset({RecyclePolicy().policy_id})
#: `_paired`'s stand-in for the member one side of a pair of mappings lacks.
_ABSENT: Final = object()


class PolicyProblem(NamedTuple):
    """One refusal: the RFC 6901 pointer into the document, the message, and the `detail.code`
    (`None` for a schema error, which is a plain `invalid_request`)."""

    pointer: str
    message: str
    code: str | None


def is_project_policy_id(policy_id: str) -> bool:
    """D4.1: whether `policy_id` is a project policy's id (`user.` and the pattern, matched whole:
    `match` would let `$` accept a trailing newline; X06 ruling R1-1, S1)."""
    return PROJECT_POLICY_ID.fullmatch(policy_id) is not None


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def solve_policy_problems(document: Any) -> list[PolicyProblem]:
    """D4.3's checks of `document`, in order; empty when it may be registered. A schema error
    ends the list (the later checks read a valid document)."""
    errors = schema_errors(SCHEMA, document)
    if errors:
        split = [error.split(": ", 1) for error in errors]
        return [PolicyProblem(pointer, message, None) for pointer, message in split]
    problems: list[PolicyProblem] = []
    policy_id = document["policy_id"]
    if not is_project_policy_id(policy_id):
        problems.append(
            PolicyProblem(
                "/policy_id",
                f"{SOLVE_POLICY_ID_INVALID}: a project policy's id matches "
                f"{PROJECT_POLICY_ID.pattern}, not {policy_id!r}",
                SOLVE_POLICY_ID_INVALID,
            )
        )
    try:
        written = SolvePolicy.from_document(document).as_document()
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        written = None
        problems.append(_invalid("", f"the solver cannot read it: {error}"))
    if written is not None and canonical_json(written) != canonical_json(document):
        problems.append(
            _invalid(_first_difference(document, written), "the solver would read it otherwise")
        )
    problems.extend(_registry_problems(document))
    return problems


def _invalid(pointer: str, message: str) -> PolicyProblem:
    return PolicyProblem(pointer, f"{SOLVE_POLICY_INVALID}: {message}", SOLVE_POLICY_INVALID)


def _registry_problems(document: Mapping[str, Any]) -> list[PolicyProblem]:
    """D4.3 (d) on a schema-valid document: each open member against its registry."""
    problems: list[PolicyProblem] = []
    for index, source in enumerate(document["initializer_chain"]):
        if source not in POLICY_INITIALIZERS:
            problems.append(
                _invalid(
                    f"/initializer_chain/{index}",
                    f"no registered start source {source!r} (registered: "
                    f"{sorted(POLICY_INITIALIZERS)})",
                )
            )
    if canonical_json(document["linear_solver"]) != canonical_json(REGISTERED_LINEAR_SOLVER):
        pointer = _first_difference(REGISTERED_LINEAR_SOLVER, document["linear_solver"])
        problems.append(
            _invalid(
                "/linear_solver" + pointer,
                "the solver runs one linear solver, "
                f"{REGISTERED_LINEAR_SOLVER['name']!r} with its registered options (ADR 0004 D1)",
            )
        )
    for member in ("residual_tolerances", "scales"):
        for kind in sorted(document[member]):
            if kind not in QUANTITY_KINDS:
                problems.append(
                    _invalid(
                        f"/{member}/{_escape(kind)}",
                        f"no registered quantity kind {kind!r} (registered: "
                        f"{sorted(QUANTITY_KINDS)})",
                    )
                )
    recycle = document["recycle"]
    if recycle["policy_id"] not in RECYCLE_POLICY_IDS:
        problems.append(
            _invalid(
                "/recycle/policy_id",
                f"no registered recycle policy {recycle['policy_id']!r} (registered: "
                f"{sorted(RECYCLE_POLICY_IDS)})",
            )
        )
    if "tear_streams" in recycle:
        problems.append(
            _invalid(
                "/recycle/tear_streams",
                "a tear set names one flowsheet's streams; a project policy names none",
            )
        )
    return problems


def _first_difference(expected: Any, actual: Any) -> str:
    """The pointer of the first member where `actual` differs from `expected` (`""` when the
    values differ as wholes)."""
    for token, left, right in _paired(expected, actual):
        if left is _ABSENT or right is _ABSENT:
            return "/" + token
        if canonical_json(left) != canonical_json(right):
            return "/" + token + _first_difference(left, right)
    return ""


def _paired(expected: Any, actual: Any) -> list[tuple[str, Any, Any]]:
    """The members `_first_difference` compares, in its order, as `(pointer token, expected's,
    actual's)`, `_ABSENT` for a key one side lacks: the keys of two mappings, sorted, or the
    items of two lists of one length; none for any other pair."""
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        return [
            (_escape(str(key)), expected.get(key, _ABSENT), actual.get(key, _ABSENT))
            for key in sorted(set(expected) | set(actual))
        ]
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return [
            (str(index), left, right)
            for index, (left, right) in enumerate(zip(expected, actual, strict=True))
        ]
    return []
