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
in the usage record (F1 decision W3-11). The draft form (a revision document) is F1-WO4b's; until
then it is refused `unsupported`.
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
from openflowsheet.registry import Registered, Registry
from openflowsheet.registry.capability import admit
from openflowsheet.registry.descriptor import sort_key
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


def _pair(registry: Registry, pair: Mapping[str, Any]) -> tuple[AdmissionPair, tuple[Coded, ...]]:
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
    admission = admit(unit, method, definition)
    verdict = AdmissionPair(
        instance=None,
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
    """D11 `check_admission`. The pair form: one pair's verdict. The draft form (`revision`) is
    refused `unsupported` until F1-WO4b."""
    if revision is not None or pair is None:
        raise api_error(
            "unsupported",
            "check_admission on a revision document is not available in this build; send a "
            "pair {unit, method, definition}",
        )
    verdicts = [_pair(registry, pair)]
    pairs = tuple(verdict for verdict, _ in verdicts)
    return AdmissionReport(
        registry_sha256=registry.registry_sha256,
        admitted=all(entry.admitted for entry in pairs),
        pairs=pairs,
        notices=_union([notices for _, notices in verdicts]),
    )
