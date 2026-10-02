"""`solution-state.json`: the state a revision bundle's certificate judged (T07 ruling round 2).

Design note `docs/design/T07-jobs-and-bindings.md`, ruling round 2 (V17 F1), ADR 0020 D4 as
amended. A revision bundle carries the verifier's state **iff** it carries a certificate — of any
verdict — so never beside a failure bundle, never for an interrupted solve and never after a
`VerifierError`: a value file beside a failure would be read as an answer (K04 §10, F1.6).

    {"schema_version": "solution-state-v1",
     "state_sha256":   canonical.state_sha256(values in variable_ids order),
     "variable_ids":   the verifier's spec.variable_ids, in order,
     "variables":      {id: binary64 in unprefixed SI}}

The file has no run id (two jobs that solved the same thing write the same bytes, G6/G7) and no
copy of the verdict (a verdict without its `checks` would turn a D2.4-forgiven drift in the
certificate into a `MISMATCH`). Only `variable_ids` enters R0 (`run.identity`): the digest is
float-derived, and a state's last bits are not an R0 promise (ADR 0007, ADR 0008 D2.1).

`inconsistencies` is the cross-check `verify_bundle` runs on the file; it lives here, beside
`bundle.py` and `identity.py`, so that none of them imports `application/`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from functools import cache
from importlib.resources.abc import Traversable
from typing import Any, Final

from openflowsheet.canonical import state_sha256
from openflowsheet.resources import packaged

__all__ = ["NAME", "SCHEMA_VERSION", "document", "inconsistencies"]

NAME: Final[str] = "solution-state.json"
SCHEMA_VERSION: Final[str] = "solution-state-v1"
#: The published schema, as the package carries it (T08 W4.2, `openflowsheet.resources`).
_SCHEMA: Final[Traversable] = packaged("schemas/solution-state.schema.json")


def document(variable_ids: Sequence[str], vector: Sequence[float]) -> dict[str, Any]:
    """The file's document for the dense state `vector` over `variable_ids` (in that order).

    Raises `ValueError` on a length mismatch, a repeated id or a non-finite value: each would be a
    state that does not identify a point of the declaration."""
    ids = [str(name) for name in variable_ids]
    values = [float(value) for value in vector]
    if len(ids) != len(values):
        raise ValueError(f"{len(values)} values for {len(ids)} variable ids")
    if len(set(ids)) != len(ids):
        raise ValueError("a variable id is repeated")
    for name, value in zip(ids, values, strict=True):
        if not math.isfinite(value):
            raise ValueError(f"non-finite value for {name}: {value!r}")
    return {
        "schema_version": SCHEMA_VERSION,
        "state_sha256": state_sha256(values, ids),
        "variable_ids": ids,
        "variables": dict(zip(ids, values, strict=True)),
    }


@cache
def _validator() -> Any:
    from jsonschema import Draft202012Validator

    return Draft202012Validator(json.loads(_SCHEMA.read_text(encoding="utf-8")))


def inconsistencies(state: Any, certificate: Mapping[str, Any] | None) -> tuple[str, ...]:
    """One reason per failed check of ruling round 2 F1.4, in its order; `()` when consistent.

    1. the document is valid against `schemas/solution-state.schema.json`;
    2. `set(variables) == set(variable_ids)`;
    3. `canonical.state_sha256` of `variables` in `variable_ids` order is `state_sha256`;
    4. a certificate is beside it;
    5. the certificate's `target_state_sha256` is `state_sha256`.

    Checks 2 and 3 need the shape check 1 guarantees, and 3 needs 2; a check that cannot be
    evaluated is not run, and the check that made it impossible is the reason reported.
    """
    reasons: list[str] = []
    errors = sorted(_validator().iter_errors(state), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = "".join(f"/{part}" for part in first.absolute_path)
        reasons.append(f"schema({where}: {first.message})")
    shaped = (
        isinstance(state, Mapping)
        and isinstance(state.get("variables"), Mapping)
        and isinstance(state.get("variable_ids"), list)
        and all(isinstance(value, int | float) for value in state["variables"].values())
    )
    if shaped:
        variables, ids = state["variables"], state["variable_ids"]
        if set(variables) != set(ids):
            reasons.append("variables_not_variable_ids")
        elif state_sha256({k: float(v) for k, v in variables.items()}, ids) != state.get(
            "state_sha256"
        ):
            reasons.append("state_sha256_mismatch")
    if certificate is None:
        reasons.append("certificate_missing")
    elif not isinstance(state, Mapping) or certificate.get("target_state_sha256") != state.get(
        "state_sha256"
    ):
        reasons.append("certificate_state_mismatch")
    return tuple(reasons)
