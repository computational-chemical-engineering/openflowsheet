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

**`solution-state-v2`** (ADR 0062 D8; F2-WO6a) is the file of a v2-compiled run: v1's fields plus
`material_layout` (`MaterialLayout.document()`: per connection its definition, the definition's
SHA-256 and its slots without `variable_index`) and `state_points` (`[{point, signature}]`, the
phase signatures' renderings). `document_v2` writes it beside the untouched v1 `document`;
`inconsistencies_v2` is its cross-check. Legacy runs and runs of a lowered document (D12) write v1.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from functools import cache
from importlib.resources.abc import Traversable
from typing import Any, Final

from openflowsheet.canonical import state_sha256
from openflowsheet.material.definitions import LEGACY_TEMPLATE
from openflowsheet.material.layout import ConnectionLayout, MaterialLayout, Slot
from openflowsheet.resources import packaged

__all__ = [
    "NAME",
    "SCHEMA_VERSION",
    "SCHEMA_VERSION_V2",
    "document",
    "document_v2",
    "inconsistencies",
    "inconsistencies_v2",
    "layout_variable_ids",
]

NAME: Final[str] = "solution-state.json"
SCHEMA_VERSION: Final[str] = "solution-state-v1"
#: The published schema, as the package carries it (T08 W4.2, `openflowsheet.resources`).
_SCHEMA: Final[Traversable] = packaged("schemas/solution-state.schema.json")
#: ADR 0062 D8: the file of a v2-compiled run.
SCHEMA_VERSION_V2: Final[str] = "solution-state-v2"
_SCHEMA_V2: Final[Traversable] = packaged("schemas/solution-state-v2.schema.json")
#: The fields `solution-state-v2` shares with v1 (D8: "v1's fields").
_V1_FIELDS: Final = ("state_sha256", "variable_ids", "variables")
_SHA256_LENGTH: Final = 64


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


# -- solution-state-v2 (ADR 0062 D8) -------------------------------------------------------------


def document_v2(
    variable_ids: Sequence[str],
    vector: Sequence[float],
    layout: MaterialLayout,
    state_points: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """The `solution-state-v2` document of a v2-compiled run: v1's `document` of the state, with
    `schema_version` v2, `layout.document()` and the `(point, signature)` pairs in their order.

    Raises `ValueError` where `document` does, when a slot's variable is not the one its id names
    in `variable_ids` (the layout was built over another problem), when a definition SHA-256 is not
    recorded (D8: a v2-compiled run records each), or when a state point is repeated or empty."""
    state = document(variable_ids, vector)
    ids = state["variable_ids"]
    for connection in layout.connections:
        if len(connection.definition_sha256) != _SHA256_LENGTH:
            raise ValueError(f"{connection.connection}: no definition SHA-256 recorded")
        for slot in connection.slots:
            rendered = connection.variable_id(slot)
            if not 0 <= slot.variable_index < len(ids) or ids[slot.variable_index] != rendered:
                raise ValueError(f"{rendered} is not variable {slot.variable_index}")
    points = [(str(point), str(signature)) for point, signature in state_points]
    if len({point for point, _ in points}) != len(points):
        raise ValueError("a state point is repeated")
    if any(not point or not signature for point, signature in points):
        raise ValueError("a state point or its signature is empty")
    state["schema_version"] = SCHEMA_VERSION_V2
    state["material_layout"] = layout.document()
    state["state_points"] = [{"point": p, "signature": s} for p, s in points]
    return state


@cache
def _validator_v2() -> Any:
    from jsonschema import Draft202012Validator

    return Draft202012Validator(json.loads(_SCHEMA_V2.read_text(encoding="utf-8")))


def layout_variable_ids(material_layout: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each slot's variable id in a `material_layout`, in order, rendered as
    `ConnectionLayout.variable_id` renders it (an `nTP-v1` connection's are today's ids, every
    other connection's D7's): a reader finds each slot's variable by it in `variable_ids`."""
    rendered = []
    for entry in material_layout:
        definition = entry["definition"]
        slots = tuple(
            Slot(slot["substream"], slot["field"], tuple(slot["index"]), slot["quantity_kind"], -1)
            for slot in entry["slots"]
        )
        connection = ConnectionLayout(
            entry["connection"],
            definition,
            entry["definition_sha256"],
            LEGACY_TEMPLATE if definition == LEGACY_TEMPLATE else definition,
            None,
            slots,
            (),
        )
        rendered += [connection.variable_id(slot) for slot in slots]
    return rendered


def inconsistencies_v2(state: Any, certificate: Mapping[str, Any] | None) -> tuple[str, ...]:
    """`inconsistencies` for a `solution-state-v2` document, in its order, then D8's own check.

    1. the document is valid against `schemas/solution-state-v2.schema.json`;
    2. to 5. `inconsistencies`' checks 2 to 5 on v1's fields (its schema check is check 1's);
    6. `layout_variable_ids`: every slot of `material_layout` names, by its rendered id, a
       variable of `variable_ids`, and no two slots name one.

    Check 6 needs the shape check 1 guarantees and is not run without it.
    """
    reasons: list[str] = []
    errors = sorted(_validator_v2().iter_errors(state), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = "".join(f"/{part}" for part in first.absolute_path)
        reasons.append(f"schema({where}: {first.message})")
    shared = (
        {"schema_version": SCHEMA_VERSION} | {k: state[k] for k in _V1_FIELDS if k in state}
        if isinstance(state, Mapping)
        else state
    )
    reasons += [r for r in inconsistencies(shared, certificate) if not r.startswith("schema(")]
    if not errors:
        rendered = layout_variable_ids(state["material_layout"])
        if len(set(rendered)) != len(rendered) or not set(rendered) <= set(state["variable_ids"]):
            reasons.append("layout_variable_ids")
    return tuple(reasons)
