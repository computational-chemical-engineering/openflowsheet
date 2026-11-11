"""The registry's two operations (ADR 0060 D11, ADR 0019 Amendment 7): `list_capabilities` and
`check_admission`, over a built registry (`openflowsheet.registry`).

Both read the registry only: no project state, no file, no clock. `LocalApplication` authorizes
the call (`read`) and audits a refusal; the CLI's `capabilities` and `admission` commands call the
same functions on the process registry, without a project.

`capability_page` lists the registered descriptors sorted by (kind, id, version key), filtered by
kind and id prefix. The cursor is the base64url (no padding) of the canonical JSON of the last
item's `[kind, id, version]`; the next page holds the items after it in that order, so a cursor
stays valid whatever was registered since, and a page never repeats an item.

`admission_report` takes the pair form: D5 on the unit, method and definition named, the
versions defaulting to the highest registered. The definition defaults to the unit's one `conn:`
requirement when it names exactly one. An unknown id or version is `not_found` with
`detail {kind, id, version?, suggestions}`. Admission is a query, not a use: nothing is recorded
in the usage record (F1 decision W3-11).

The draft form (F1-WO4b) takes a schema_version 1 revision: one pair per unit instance, in
document order, (the instance's model id, the provider id `component_basis(document)` selects,
`nTP-v1`), each at the highest registered versions (the revision's `model.version` is not a
registry version and is not read; F1 decision W4b-2); `admitted` is their conjunction. It reads
`schema_version`, the component set and the instances' ids and model ids, nothing else:
admission does not validate a revision (D5; W4b-1). A later `schema_version` is
`revision_unsupported` (ADR-F2's validator reads v2). `components_unsupported` from the basis
selection is `revision_unsupported` with the binder's refusal as `unbound` (`<kind>(<code>)`, as
a solve's) and its `hint`. A model id no unit model is registered under is `not_found` with
`detail.suggestions`, as in the pair form (W4b-3).
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from openflowsheet.application.contract import api_error
from openflowsheet.application.types import (
    AdmissionPair,
    AdmissionReport,
    CapabilityDescriptor,
    CapabilityPage,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.render import closest
from openflowsheet.models.revision_flowsheet import RevisionError, component_basis
from openflowsheet.registry import Registered, Registry
from openflowsheet.registry.descriptor import sort_key
from openflowsheet.registry.legacy import CONNECTION_DEFINITION
from openflowsheet.registry.tokens import Coded, parse

#: D11: a page's default and largest size.
DEFAULT_LIMIT: Final[int] = 50
MAX_LIMIT: Final[int] = 200
#: D2's version grammar, which a cursor's version must meet.
_VERSION: Final = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
#: The kind names `not_found` uses in its message.
_KIND_TEXT: Final[Mapping[str, str]] = {
    "unit_model": "unit model",
    "property_method": "property method",
    "connection_definition": "stream definition",
}


# ======================================================================= list_capabilities


def encode_cursor(entry: Registered) -> str:
    """D11: the cursor after `entry`."""
    text = canonical_json([entry.kind, entry.id, entry.version])
    return base64.urlsafe_b64encode(text).decode("ascii").rstrip("=")


def _after(cursor: str) -> tuple[bytes, bytes, tuple[int, int, int]]:
    """The sort key a cursor continues after; `invalid_request` at `/cursor` for one this list
    did not issue."""
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError, binascii.Error):
        decoded = None
    if (
        not isinstance(decoded, list)
        or len(decoded) != 3
        or not all(isinstance(member, str) for member in decoded)
        or not _VERSION.match(decoded[2])
    ):
        raise api_error(
            "invalid_request", "the cursor is not one this list issued", pointer="/cursor"
        )
    kind, identifier, version = decoded
    return sort_key(kind, identifier, version)


def capability_page(
    registry: Registry,
    *,
    kind: str | Sequence[str] | None = None,
    id_prefix: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> CapabilityPage:
    """D11 `list_capabilities`: the registered descriptors of `kind` (one kind or several; all
    when `None`) whose id starts with `id_prefix`, after `cursor`, at most `limit`."""
    kinds = None if kind is None else ((kind,) if isinstance(kind, str) else tuple(kind))
    entries = [
        entry
        for entry in registry.descriptors(kinds)
        if id_prefix is None or entry.id.startswith(id_prefix)
    ]
    if cursor is not None:
        after = _after(cursor)
        entries = [entry for entry in entries if entry.sort_key() > after]
    page = entries[:limit]
    return CapabilityPage(
        registry_sha256=registry.registry_sha256,
        items=tuple(CapabilityDescriptor(entry.as_document()) for entry in page),
        next_cursor=encode_cursor(page[-1]) if len(entries) > limit else None,
    )


# ========================================================================= check_admission


def _registered(registry: Registry, kind: str, identifier: str, version: str | None) -> Registered:
    """The descriptor (kind, id, version), the highest version when `version` is `None`, read
    without recording a use; `not_found` with close ids (or the id's versions) otherwise."""
    of_kind = registry.descriptors((kind,))
    versions = [entry for entry in of_kind if entry.id == identifier]
    if not versions:
        raise api_error(
            "not_found",
            f"no {_KIND_TEXT[kind]} with this id is registered",
            kind=kind,
            id=identifier,
            suggestions=closest(identifier, (entry.id for entry in of_kind)),
        )
    if version is None:
        return versions[-1]  # `descriptors` sorts by version key last
    for entry in versions:
        if entry.version == version:
            return entry
    raise api_error(
        "not_found",
        f"no {_KIND_TEXT[kind]} with this id and version is registered",
        kind=kind,
        id=identifier,
        version=version,
        suggestions=[entry.version for entry in versions],
    )


def default_definition(unit: Registered) -> str | None:
    """D11: the definition a pair takes when it names none — the unit's one `conn:`
    requirement, when its `requires` name exactly one definition — else `None`."""
    names = {
        token.name
        for clause in unit.requires
        for token in map(parse, clause)
        if token.space == "conn"
    }
    return names.pop() if len(names) == 1 else None


def _pair(
    registry: Registry, pair: Mapping[str, Any], instance: str | None = None
) -> tuple[AdmissionPair, tuple[Coded, ...]]:
    unit = _registered(registry, "unit_model", pair["unit"], pair.get("unit_version"))
    method = _registered(registry, "property_method", pair["method"], pair.get("method_version"))
    definition_id = pair.get("definition")
    if definition_id is None:
        definition_id = default_definition(unit)
        if definition_id is None:
            raise api_error(
                "invalid_request",
                f"name the definition: unit model {unit.id} does not require exactly one "
                "stream definition",
                pointer="/pair/definition",
            )
    definition = _registered(registry, "connection_definition", definition_id, None)
    admission = registry.admit(
        unit.id,
        method.id,
        definition.id,
        unit_version=unit.version,
        method_version=method.version,
    )
    verdict = AdmissionPair(
        instance=instance,
        unit=unit.id,
        unit_version=unit.version,
        method=method.id,
        method_version=method.version,
        definition=definition.id,
        admitted=admission.admitted,
        refusal=None if admission.refusal is None else admission.refusal.as_document(),
        notices=tuple(notice.as_document() for notice in admission.notices),
    )
    return verdict, admission.notices


def _invalid(pointer: str, message: str) -> Exception:
    return api_error("invalid_request", message, pointer=f"/revision{pointer}")


def _draft_pairs(revision: Mapping[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    """D11's draft form: the provider id the revision's component set selects, and its
    (instance id, model id) pairs in document order. Reads `schema_version`, `component_set` and
    each instance's `id` and `model.id`, and nothing else (F1 decision W4b-1)."""
    version = revision.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise _invalid("/schema_version", "a revision states its schema_version, an integer")
    if version != 1:
        raise api_error(
            "revision_unsupported",
            f"check_admission reads a schema_version 1 revision in this build, not {version}",
        )
    if not isinstance(revision.get("component_set", {}), Mapping):
        raise _invalid("/component_set", "component_set is an object")
    instances = revision.get("instances")
    if not isinstance(instances, Sequence) or isinstance(instances, str) or not instances:
        raise _invalid("/instances", "instances is a non-empty array of unit instances")
    found: list[tuple[str, str]] = []
    for index, instance in enumerate(instances):
        where = f"/instances/{index}"
        if not isinstance(instance, Mapping):
            raise _invalid(where, "a unit instance is an object")
        identifier = instance.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise _invalid(f"{where}/id", "a unit instance has an id, a non-empty string")
        model = instance.get("model")
        model_id = model.get("id") if isinstance(model, Mapping) else None
        if not isinstance(model_id, str) or not model_id:
            raise _invalid(f"{where}/model/id", "a unit instance names its model by id")
        found.append((identifier, model_id))
    try:
        method = component_basis(revision).provider_id
    except RevisionError as error:
        raise api_error(
            "revision_unsupported",
            "the revision's component set selects no property method",
            unbound=f"{error.kind}({error.code})",
            hint=error.hint,
        ) from error
    return method, found


def _union(notices: Sequence[tuple[Coded, ...]]) -> tuple[Mapping[str, Any], ...]:
    """Every pair's notices once each, in the registry's notice order (code, then params by
    name; F1 decisions W1-12, W4a-4)."""
    unique = {notice.sort_key(): notice for each in notices for notice in each}
    return tuple(unique[key].as_document() for key in sorted(unique))


def admission_report(
    registry: Registry,
    *,
    pair: Mapping[str, Any] | None = None,
    revision: Mapping[str, Any] | None = None,
) -> AdmissionReport:
    """D11 `check_admission`. The pair form: one pair's verdict. The draft form (`revision`, a
    schema_version 1 document): one verdict per unit instance, `admitted` their conjunction."""
    if (pair is None) == (revision is None):
        raise api_error("invalid_request", "send exactly one of pair and revision")
    if revision is not None:
        method, instances = _draft_pairs(revision)
        verdicts = [
            _pair(
                registry,
                {"unit": model, "method": method, "definition": CONNECTION_DEFINITION},
                instance,
            )
            for instance, model in instances
        ]
    else:
        assert pair is not None
        verdicts = [_pair(registry, pair)]
    pairs = tuple(verdict for verdict, _ in verdicts)
    return AdmissionReport(
        registry_sha256=registry.registry_sha256,
        admitted=all(entry.admitted for entry in pairs),
        pairs=pairs,
        notices=_union([notices for _, notices in verdicts]),
    )
