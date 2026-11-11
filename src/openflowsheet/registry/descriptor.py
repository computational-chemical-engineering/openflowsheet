"""The extension descriptor: schema, normalisation, hash and computed fields (ADR 0060 D1, D2, D9).

A descriptor is declared by its author (`schemas/extension-descriptor.schema.json`) and
*registered* by the registry, which adds fields no author declares: `self_sha256` (D3),
`descriptor_sha256`, `origin`, `distribution`, `distribution_version`, `entry_point`,
`effective_status`, `evidence_class` and `stability`.

**Normalisation (D2).** A token's `:0` is dropped; each clause's tokens are sorted (UTF-8 bytes) and
deduplicated; clauses are deduplicated and sorted by their token tuples; `provides` keeps, per
(space, name), the highest level and is sorted; `implementation.modules` is sorted; `limitations`
are sorted by canonical JSON. `descriptor_sha256` is `document_sha256` (ADR 0002 D3) of the
normalised descriptor without `status`.

**Evidence never moves an identity (D9).** `status`, attestations, `evidence_class` and the
notices enter no `descriptor_sha256`, `registry_sha256` or admission verdict; they change only
`effective_status`, `evidence_class` and the notices a result carries.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.registry.tokens import Coded, normalise_provides, normalise_requires

if TYPE_CHECKING:
    from jsonschema import Draft202012Validator

DESCRIPTOR_FORMAT: Final = "openflowsheet-extension-v1"
PACKAGE_FORMAT: Final = "openflowsheet-extension-package-v1"
SCHEMA_NAME: Final = "extension-descriptor.schema.json"

#: D1's closed kind list (22 kinds) is the schema's `kind` enum, its one statement in the package.

#: D2's evidence statuses, in increasing order.
STATUSES: Final = ("declared", "implemented", "tested", "reviewed", "released")
_RANK: Final = {status: rank for rank, status in enumerate(STATUSES)}

#: D1: kinds whose payload is core at the end of W1, whatever the origin.
CORE_KINDS: Final = frozenset({"record_type", "correlation_form", "data_source", "message_entries"})
#: D1: kinds whose legacy form is core and whose v2 form is `preview` until its ADR is Accepted.
LEGACY_FORM_KINDS: Final = frozenset({"property_method", "unit_model", "connection_definition"})
#: D1: built-in descriptors of this kind are core; extension descriptors are `preview` in 0.5.
BUILTIN_CORE_KINDS: Final = frozenset({"functional_contributor"})

#: The payload schema of a kind, by its `$defs` name in the descriptor schema. A kind not listed
#: has no payload schema yet (its owner ADR adds it): its payload need only be an object.
PAYLOAD_DEFS: Final[Mapping[str, str]] = MappingProxyType(
    {"message_entries": "payload_message_entries"}
)
#: D6's legacy-form payload schemas, by kind. They apply to the descriptors of the built-in table
#: named `legacy` only, which must be of one of these kinds; a descriptor of these kinds from
#: anywhere else has the v2 form, `preview` until its ADR is Accepted (D1).
LEGACY_PAYLOAD_DEFS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "property_method": "payload_property_method_legacy",
        "unit_model": "payload_unit_model_legacy",
        "connection_definition": "payload_connection_definition_legacy",
    }
)


def version_key(version: str) -> tuple[int, int, int]:
    """D2: a version compared numerically as (major, minor, patch)."""
    major, minor, patch = (int(part) for part in version.split("."))
    return (major, minor, patch)


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def sort_key(kind: str, identifier: str, version: str) -> tuple[bytes, bytes, tuple[int, int, int]]:
    """D7: registered descriptors iterate sorted by (kind, id, version key), UTF-8 byte order."""
    return (_utf8(kind), _utf8(identifier), version_key(version))


# ---------------------------------------------------------------------------------------------
# Schema


def _schema() -> Mapping[str, Any]:
    import json  # noqa: PLC0415

    from openflowsheet.resources import packaged  # noqa: PLC0415

    loaded: Mapping[str, Any] = json.loads(
        packaged(f"schemas/{SCHEMA_NAME}").read_text(encoding="utf-8")
    )
    return loaded


@cache
def _validator(pointer: str) -> Draft202012Validator:
    """A validator for the descriptor schema's subschema at `pointer` (`""` for the root), from
    the packaged schema file, which is immutable for the process's life (T07 G20 allowlist)."""
    from jsonschema import Draft202012Validator  # noqa: PLC0415
    from referencing import Registry  # noqa: PLC0415
    from referencing.jsonschema import DRAFT202012  # noqa: PLC0415

    schema = _schema()
    resources = Registry().with_resource(schema["$id"], DRAFT202012.create_resource(schema))
    return Draft202012Validator({"$ref": f"{schema['$id']}#{pointer}"}, registry=resources)


def _pointer(path: Iterable[str | int]) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


def _path_key(path: Iterable[str | int]) -> tuple[tuple[int, int, str], ...]:
    return tuple((0, part, "") if isinstance(part, int) else (1, 0, part) for part in path)


def schema_problem(document: object, pointer: str = "") -> str | None:
    """The JSON pointer of the first schema error of `document` against the descriptor schema's
    subschema at `pointer` (deepest-first in path order, so the result is deterministic), or
    `None` when it is valid."""
    errors = list(_validator(pointer).iter_errors(document))
    if not errors:
        return None
    first = min(errors, key=lambda error: (_path_key(error.absolute_path), error.message))
    return _pointer(first.absolute_path)


def descriptor_problem(document: Mapping[str, Any], *, legacy_form: bool = False) -> str | None:
    """The pointer, relative to the descriptor, of its first problem: the envelope schema, a node
    with no canonical JSON form (ADR 0002 D3), the kind's payload schema (its legacy form's when
    `legacy_form`, D6), then D5's `conn:<id>` of a connection definition (`P_d` always contains
    it). `None` when the descriptor is valid."""
    found = schema_problem(document)
    if found is not None:
        return found
    found = first_noncanonical(document)
    if found is not None:
        return found
    if legacy_form and document["kind"] not in LEGACY_PAYLOAD_DEFS:
        return "/kind"
    definition = (LEGACY_PAYLOAD_DEFS if legacy_form else PAYLOAD_DEFS).get(document["kind"])
    if definition is not None:
        inner = schema_problem(document["payload"], f"/$defs/{definition}")
        if inner is not None:
            return "/payload" + inner
    if document["kind"] == "connection_definition":
        own = f"conn:{document['id']}"
        if own not in normalise_provides(document["provides"]):
            return "/provides"
    return None


# ---------------------------------------------------------------------------------------------
# Normalisation and hash


def normalise(document: Mapping[str, Any]) -> dict[str, Any]:
    """D2's normal form of a schema-valid descriptor; idempotent."""
    normal = copy.deepcopy(dict(document))
    normal["requires"] = [list(clause) for clause in normalise_requires(document["requires"])]
    normal["provides"] = list(normalise_provides(document["provides"]))
    implementation = dict(normal["implementation"])
    implementation["modules"] = sorted(set(implementation["modules"]), key=_utf8)
    normal["implementation"] = implementation
    normal["limitations"] = sorted(normal["limitations"], key=canonical_json)
    return normal


def descriptor_sha256(document: Mapping[str, Any]) -> str:
    """D2: `document_sha256` of the normalised descriptor without `status` (an evidence field)."""
    normal = normalise(document)
    del normal["status"]
    return document_sha256(normal)


# ---------------------------------------------------------------------------------------------
# Evidence (D9) and stability (D1)


@dataclass(frozen=True)
class Attestation:
    """A project's record that a non-built-in descriptor was reviewed (D9). It counts only for
    the (id, version, descriptor_sha256, self_sha256) it names, so it never outlives the code or
    the descriptor it reviewed. No attestation store exists in 0.5 (ADR 0060 risk 6)."""

    id: str
    version: str
    descriptor_sha256: str
    self_sha256: str


def origin(document: Mapping[str, Any], *, builtin: bool) -> str:
    """D9: `contributed` iff `contributed_by` is present, else `builtin` or `installed`."""
    if "contributed_by" in document:
        return "contributed"
    return "builtin" if builtin else "installed"


def effective_status(status: str, *, builtin: bool, attested: bool) -> str:
    """D9: a built-in's declared status; a non-built-in's `reviewed` or `released` counts only
    with a matching attestation, else it is capped at `tested`."""
    if builtin or attested or _RANK[status] < _RANK["reviewed"]:
        return status
    return "tested"


def evidence_class(effective: str, *, builtin: bool, attested: bool) -> str:
    """D9: `core` (built-in, effective status at least `reviewed`), `reviewed` (non-built-in with
    an attestation), `unreviewed` otherwise."""
    if builtin:
        return "core" if _RANK[effective] >= _RANK["reviewed"] else "unreviewed"
    return "reviewed" if attested else "unreviewed"


def stability(kind: str, *, builtin: bool, legacy_form: bool) -> str:
    """D1's payload stability of one registered descriptor: `core` or `preview`."""
    if kind in CORE_KINDS:
        return "core"
    if kind in LEGACY_FORM_KINDS:
        return "core" if legacy_form else "preview"
    if kind in BUILTIN_CORE_KINDS:
        return "core" if builtin else "preview"
    return "preview"


# ---------------------------------------------------------------------------------------------
# The registered descriptor


@dataclass(frozen=True)
class Registered:
    """A registered descriptor: the normalised declared document and D2's computed fields.

    `unresolved` holds the spellings of the descriptor's tokens (`requires` and `provides`) whose
    registry-derived name no registered descriptor gives (D4), sorted; the registry fills it once
    every descriptor is registered."""

    document: Mapping[str, Any]
    descriptor_sha256: str
    self_sha256: str
    origin: str
    distribution: str
    distribution_version: str
    entry_point: str | None
    effective_status: str
    evidence_class: str
    stability: str
    unresolved: tuple[str, ...] = field(default=())

    @property
    def kind(self) -> str:
        return str(self.document["kind"])

    @property
    def id(self) -> str:
        return str(self.document["id"])

    @property
    def version(self) -> str:
        return str(self.document["version"])

    @property
    def status(self) -> str:
        return str(self.document["status"])

    @property
    def requires(self) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(clause) for clause in self.document["requires"])

    @property
    def provides(self) -> tuple[str, ...]:
        return tuple(self.document["provides"])

    @property
    def payload(self) -> Mapping[str, Any]:
        payload: Mapping[str, Any] = self.document["payload"]
        return payload

    def sort_key(self) -> tuple[bytes, bytes, tuple[int, int, int]]:
        return sort_key(self.kind, self.id, self.version)

    def evidence_notices(self) -> tuple[Coded, ...]:
        """D9's flag for this descriptor: `extension_unreviewed(<id>, <origin>)` when it is
        `unreviewed`, `preview_kind(<kind>, <id>)` when its kind's payload is `preview`."""
        notices = []
        if self.evidence_class == "unreviewed":
            notices.append(Coded("extension_unreviewed", {"id": self.id, "origin": self.origin}))
        if self.stability == "preview":
            notices.append(Coded("preview_kind", {"kind": self.kind, "id": self.id}))
        return tuple(notices)

    def snapshot_row(self) -> dict[str, Any]:
        """D10: this descriptor's row of the snapshot's `extensions`."""
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "self_sha256": self.self_sha256,
            "descriptor_sha256": self.descriptor_sha256,
            "origin": self.origin,
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "entry_point": self.entry_point,
            "status": self.status,
            "effective_status": self.effective_status,
            "evidence_class": self.evidence_class,
            "stability": self.stability,
        }

    def as_document(self) -> dict[str, Any]:
        """D11's `CapabilityDescriptor`: the declared fields (normalised) and D2's computed ones."""
        document = copy.deepcopy(dict(self.document))
        document.update(
            {
                key: value
                for key, value in self.snapshot_row().items()
                if key not in ("kind", "id", "version", "status")
            }
        )
        return document
