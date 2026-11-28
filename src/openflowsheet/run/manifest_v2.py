"""The v2 `RunManifest`: a v2-compiled run's manifest. ADR 0067 D2, D9 (F8-WO1).

DRAFT until ADR 0067 is Accepted. A v2 manifest is a v1 manifest (`run/manifest.py`) with D2's
members beside it:

    member                 content                                   class (D9)
    bundle_format          "openflowsheet-bundle-v2"; selects D5's   excluded (NON_STRUCTURAL)
                           reader
    data_lock_sha256       ADR 0061 D10's SHA of the run's data lock R0
    extensions_used        ADR 0060 D8's set, [kind, id, version,    R0, top level
                           descriptor_sha256, self_sha256] rows
    run_kind, documents    a `run` job's kind and documents          R0; absent in 0.6
                           (ADR 0066 D11)
    environment.registry   {registry_sha256, snapshot_sha256}        excluded (in `environment`)

**D1: only v2-compiled runs carry them.** A v1-path run (a v1 document, or a v2 document lowered
by ADR 0062 D12) writes `RunManifest` exactly as before, so its manifest, its `structural_sha256`
and its bundle are byte-identical to pre-F8 (E-F8-10). Nothing in 0.6 writes a `RunManifestV2`
outside tests: v2-compiled runs come with F6, and F8-WO2's test-only factory is the first writer.

**The classes need no code of their own.** `structural_document` removes `NON_STRUCTURAL` from
the whole document, so a member is structural unless that list names it: `bundle_format` is
listed, `environment.registry` sits inside the listed `environment`, and the R0 members are
hashed by default. An absent member is not in the document at all, so it is not hashed (D2).
`MEMBER_CLASSES` states D9's table, and a test checks the structural document against it.

**`forced_replay` is reserved, not built** (D8, ADR 0019 Amendment 12): a replay report in that
mode is refused `construct_unavailable(forced_replay, TX)` until F8-WO7 builds it with TX.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from openflowsheet.registry.descriptor import Registered, sort_key
from openflowsheet.registry.tokens import Coded
from openflowsheet.run.manifest import Environment, RunManifest

#: D2: the value of `bundle_format`; its presence selects D5's reader.
BUNDLE_FORMAT: Final = "openflowsheet-bundle-v2"

#: D9's classes of D2's members (`environment.registry` by its path). `R0` members enter
#: `structural_sha256`; `excluded` ones enter no identity.
MEMBER_CLASSES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bundle_format": "excluded",
        "data_lock_sha256": "R0",
        "extensions_used": "R0",
        "run_kind": "R0",
        "documents": "R0",
        "environment.registry": "excluded",
    }
)

#: D8 (Amendment 12): replay modes the schema reserves, by the package that builds each. A report
#: in such a mode is refused `construct_unavailable(<mode>, <package>)`.
RESERVED_REPLAY_MODES: Final[Mapping[str, str]] = MappingProxyType({"forced_replay": "TX"})

#: One `extensions_used` row: (kind, id, version, descriptor_sha256, self_sha256).
ExtensionRow = tuple[str, str, str, str, str]


def _row_key(row: ExtensionRow) -> tuple[bytes, bytes, tuple[int, int, int]]:
    return sort_key(row[0], row[1], row[2])


def extensions_used_rows(descriptors: Iterable[Registered]) -> tuple[ExtensionRow, ...]:
    """D2's `extensions_used` of the registered `descriptors` a run used (ADR 0060 D8's set, as
    `Registry.extensions_used(...).descriptors` gives it): one row per descriptor, sorted by
    (kind, id, version key), each at most once."""
    rows = {
        (entry.kind, entry.id, entry.version, entry.descriptor_sha256, entry.self_sha256)
        for entry in descriptors
    }
    ordered = tuple(sorted(rows, key=_row_key))
    _check_rows(ordered)
    return ordered


def _check_rows(rows: tuple[ExtensionRow, ...]) -> None:
    keys = [_row_key(row) for row in rows]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ValueError(
            "extensions_used must be sorted by (kind, id, version key) with each (kind, id, "
            "version) once"
        )


@dataclass(frozen=True)
class EnvironmentRegistry:
    """D2's `environment.registry`: the registry the run saw (ADR 0060 D10) and the SHA of its
    snapshot document (`artifacts/registry-snapshot.json`, D3). Provenance, never identity."""

    registry_sha256: str
    snapshot_sha256: str

    def as_document(self) -> dict[str, str]:
        return {"registry_sha256": self.registry_sha256, "snapshot_sha256": self.snapshot_sha256}


@dataclass(frozen=True)
class RunManifestV2(RunManifest):
    """A v2-compiled run's manifest: `RunManifest` and D2's members.

    `data_lock_sha256`, `extensions_used` and `environment_registry` are required: every
    v2-compiled run has a data lock, a registry and a set of extensions it used (F8 decision
    WO1-3). `run_kind` and `documents` belong to `run` jobs (ADR 0066 D11, 0.8) and are absent
    when `None`. `bundle_format` is fixed.
    """

    data_lock_sha256: str = field(kw_only=True)
    extensions_used: tuple[ExtensionRow, ...] = field(kw_only=True)
    environment_registry: EnvironmentRegistry = field(kw_only=True)
    run_kind: tuple[str, str] | None = field(default=None, kw_only=True)
    documents: Mapping[str, str] | None = field(default=None, kw_only=True)
    bundle_format: str = field(default=BUNDLE_FORMAT, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "extensions_used", tuple(tuple(row) for row in self.extensions_used)
        )
        _check_rows(self.extensions_used)
        if self.run_kind is not None:
            object.__setattr__(self, "run_kind", tuple(self.run_kind))
        if self.documents is not None:
            object.__setattr__(self, "documents", MappingProxyType(dict(self.documents)))

    def _base_document(self) -> dict[str, Any]:
        """The v1 document, `environment.registry` in its environment and D2's top-level
        members beside it; `run_kind` and `documents` only when present."""
        document = super()._base_document()
        document["environment"]["registry"] = self.environment_registry.as_document()
        document["bundle_format"] = self.bundle_format
        document["data_lock_sha256"] = self.data_lock_sha256
        document["extensions_used"] = [list(row) for row in self.extensions_used]
        if self.run_kind is not None:
            document["run_kind"] = list(self.run_kind)
        if self.documents is not None:
            document["documents"] = dict(self.documents)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> RunManifestV2:
        """The manifest `as_document` wrote (its two self-hashes are recomputed, not read).
        A document without `bundle_format` is a v1 manifest and is refused here."""
        if document.get("bundle_format") != BUNDLE_FORMAT:
            raise ValueError(
                f"not a v2 manifest: bundle_format {document.get('bundle_format')!r}, "
                f"expected {BUNDLE_FORMAT!r}"
            )
        recorded = dict(document["environment"])
        registry = recorded.pop("registry")
        names = {entry for entry in cls.__dataclass_fields__ if entry != "bundle_format"}
        members = {
            name: document[name]
            for name in names
            if name in document and name not in ("environment", "environment_registry")
        }
        if "run_kind" in members:
            members["run_kind"] = tuple(members["run_kind"])
        members["extensions_used"] = tuple(tuple(row) for row in members["extensions_used"])
        return cls(
            environment=Environment(**recorded),
            environment_registry=EnvironmentRegistry(**registry),
            **members,
        )


class ReplayModeRefusedError(ValueError):
    """A replay report in a mode Amendment 12 reserves (D8): `coded` is
    `construct_unavailable(<mode>, <package>)`."""

    def __init__(self, coded: Coded) -> None:
        super().__init__(f"{coded.code}({coded.params['construct']}, {coded.params['foundation']})")
        self.coded = coded


def refuse_reserved_mode(report: Mapping[str, Any]) -> None:
    """D8: refuse a replay report whose `mode` is reserved (`forced_replay`, built with TX by
    F8-WO7) with `construct_unavailable(<mode>, <package>)`; any other report passes."""
    mode = report.get("mode")
    if isinstance(mode, str) and mode in RESERVED_REPLAY_MODES:
        raise ReplayModeRefusedError(
            Coded(
                "construct_unavailable",
                {"construct": mode, "foundation": RESERVED_REPLAY_MODES[mode]},
            )
        )
