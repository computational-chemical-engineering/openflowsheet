"""The extension registry: one registration point for every kind of extension (ADR 0060).

This layer was introduced by package F1 (roadmap 0.5). A registry holds registered descriptors
(`descriptor`), each with its capability tokens (`tokens`) and the self-hash of its implementation
set (`selfhash`); `capability` is the pure admission function over three of them, and `snapshot`
the identity of what is loaded (`registry_sha256`) and the snapshot document.

`Registry.build` builds an independent registry from built-in tables and already loaded extension
packages, then closes it: `register` afterwards raises `RuntimeError("registry_closed")`. The order
of every input is irrelevant: descriptors iterate sorted by (kind, id, version key) and the
snapshot's lists are sorted.

A package is registered whole or not at all (D7). It is quarantined, with one typed reason, when
its document fails the schema or the namespace prefix (`extension_invalid`), a token is unknown or
reserved (`capability_unknown`, `reserved_capability`), or a self-hash path is missing
(`self_hash_unavailable`). Its validation reads only the package itself and the static tables, so
one package's quarantine never quarantines another. A built-in failing any of these is a bug and
raises `RegistryBuildError`.

Not here yet (F1-WO2, WO3): the generated built-in tables and `default_registry()`, entry-point
discovery (namespace rules, deduplication, `extension_load_failed`), message-catalogue
registration, the validation of `limitations` codes against the catalogue, factory resolution and
the usage recorder.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from openflowsheet.registry.capability import Admission, Verdict, admission_matrix, admit
from openflowsheet.registry.descriptor import (
    Attestation,
    Registered,
    descriptor_problem,
    descriptor_sha256,
    effective_status,
    evidence_class,
    normalise,
    origin,
    schema_problem,
    stability,
    version_key,
)
from openflowsheet.registry.selfhash import SelfHashUnavailableError, self_sha256
from openflowsheet.registry.snapshot import Quarantine, registry_sha256, snapshot_document
from openflowsheet.registry.tokens import (
    REGISTRY_SPACES,
    Coded,
    parse,
    token_problem,
)

__all__ = [
    "Admission",
    "Attestation",
    "Coded",
    "ExtensionPackage",
    "Quarantine",
    "Registered",
    "Registry",
    "RegistryBuildError",
    "Source",
    "Verdict",
    "admit",
]

#: The distribution every built-in descriptor belongs to.
BUILTIN_DISTRIBUTION = "openflowsheet"
#: The built-in table whose descriptors are D6's legacy forms (`stability` core for their kinds).
LEGACY_TABLE = "legacy"


class RegistryBuildError(ValueError):
    """A built-in descriptor fails validation: a bug, which fails the build (D4, D7, D8)."""

    def __init__(self, reason: Coded) -> None:
        super().__init__(f"{reason.code}{dict(reason.params)}")
        self.reason = reason


@dataclass(frozen=True)
class Source:
    """Where a descriptor comes from: its distribution and the import root its `modules` are
    relative to (D3). `legacy_form` marks D6's legacy built-ins."""

    distribution: str
    distribution_version: str
    entry_point: str | None
    import_root: Path
    builtin: bool
    legacy_form: bool = False


@dataclass(frozen=True)
class ExtensionPackage:
    """An extension package document already loaded from its entry point (D7), with the
    distribution that declared it and the import root of its top-level package."""

    distribution: str
    distribution_version: str
    entry_point: str
    import_root: Path
    document: object


def _builtin_root() -> Path:
    import openflowsheet  # noqa: PLC0415

    assert openflowsheet.__file__ is not None
    return Path(openflowsheet.__file__).resolve().parent.parent


def _attested(
    document: Mapping[str, Any], digest: str, self_sha: str, attestations: frozenset[Attestation]
) -> bool:
    return Attestation(document["id"], document["version"], digest, self_sha) in attestations


def _registered(
    document: Mapping[str, Any], source: Source, attestations: frozenset[Attestation]
) -> Registered:
    """Normalise one schema-valid descriptor and compute D2's fields (self-hash may raise)."""
    normal = normalise(document)
    digest = descriptor_sha256(normal)
    self_sha = self_sha256(source.import_root, normal["implementation"]["modules"])
    attested = not source.builtin and _attested(normal, digest, self_sha, attestations)
    effective = effective_status(normal["status"], builtin=source.builtin, attested=attested)
    return Registered(
        document=normal,
        descriptor_sha256=digest,
        self_sha256=self_sha,
        origin=origin(normal, builtin=source.builtin),
        distribution=source.distribution,
        distribution_version=source.distribution_version,
        entry_point=source.entry_point,
        effective_status=effective,
        evidence_class=evidence_class(effective, builtin=source.builtin, attested=attested),
        stability=stability(normal["kind"], builtin=source.builtin, legacy_form=source.legacy_form),
    )


def _token_problem(
    document: Mapping[str, Any], source: Source, namespace: str | None
) -> Coded | None:
    """D4's validation of every token of one normalised descriptor, `requires` then `provides`."""
    for clause in document["requires"]:
        for token in clause:
            found = token_problem(
                token, providing=False, builtin=source.builtin, namespace=namespace
            )
            if found is not None:
                return found
    for token in document["provides"]:
        found = token_problem(token, providing=True, builtin=source.builtin, namespace=namespace)
        if found is not None:
            return found
    return None


class Registry:
    """A set of registered descriptors, open while it is built and closed afterwards (D8)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, tuple[int, int, int]], Registered] = {}
        self._quarantined: list[Quarantine] = []
        self._closed = False

    # -- building ------------------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        builtin_tables: Mapping[str, Sequence[Mapping[str, Any]]],
        packages: Iterable[ExtensionPackage] = (),
        attestations: Iterable[Attestation] = (),
        builtin_root: Path | None = None,
        builtin_version: str | None = None,
    ) -> Registry:
        """Build and close an independent registry (D8 steps 1, 3, 5, 6 over loaded packages).

        `builtin_tables` maps a table name to its descriptors; `builtin_root` is the import root
        of built-in `modules` (default: the directory containing the `openflowsheet` package);
        `attestations` are the project's review records (D9; none exist in 0.5)."""
        if builtin_version is None:
            import openflowsheet  # noqa: PLC0415

            builtin_version = openflowsheet.__version__
        root = _builtin_root() if builtin_root is None else builtin_root
        attested = frozenset(attestations)
        registry = cls()
        for table in sorted(builtin_tables, key=lambda name: name.encode("utf-8")):
            source = Source(
                BUILTIN_DISTRIBUTION, builtin_version, None, root, True, table == LEGACY_TABLE
            )
            for document in builtin_tables[table]:
                registry.register(registry._builtin(document, source, attested))
        for package in packages:
            registry._add_package(package, attested)
        registry._resolve()
        registry._closed = True
        return registry

    def _builtin(
        self, document: Mapping[str, Any], source: Source, attestations: frozenset[Attestation]
    ) -> Registered:
        identity = f"{document.get('kind')}:{document.get('id')}@{document.get('version')}"
        pointer = descriptor_problem(document, legacy_form=source.legacy_form)
        if pointer is not None:
            raise RegistryBuildError(
                Coded("extension_invalid", {"entry_point": identity, "pointer": pointer})
            )
        found = _token_problem(normalise(document), source, None)
        if found is not None:
            raise RegistryBuildError(found)
        try:
            return _registered(document, source, attestations)
        except SelfHashUnavailableError as error:
            raise RegistryBuildError(
                Coded("self_hash_unavailable", {"id": str(document["id"]), "path": error.path})
            ) from None

    def _add_package(self, package: ExtensionPackage, attestations: frozenset[Attestation]) -> None:
        """Register a package whole or quarantine it with its first problem (D7)."""

        def quarantine(reason: Coded) -> None:
            self._quarantined.append(
                Quarantine(
                    package.distribution, package.distribution_version, package.entry_point, reason
                )
            )

        def invalid(pointer: str) -> None:
            quarantine(
                Coded("extension_invalid", {"entry_point": package.entry_point, "pointer": pointer})
            )

        document = package.document
        pointer = schema_problem(document, "/$defs/package")
        if pointer is not None:
            return invalid(pointer)
        assert isinstance(document, Mapping)
        namespace = str(document["namespace"])
        source = Source(
            package.distribution,
            package.distribution_version,
            package.entry_point,
            package.import_root,
            False,
        )
        registered: list[Registered] = []
        seen: set[tuple[str, str, tuple[int, int, int]]] = set()
        for index, descriptor in enumerate(document["descriptors"]):
            where = f"/descriptors/{index}"
            found = descriptor_problem(descriptor)
            if found is not None:
                return invalid(where + found)
            if not str(descriptor["id"]).startswith(namespace + "."):
                return invalid(where + "/id")
            key = (descriptor["kind"], descriptor["id"], version_key(descriptor["version"]))
            if key in seen:
                return invalid(where)
            seen.add(key)
            problem = _token_problem(normalise(descriptor), source, namespace)
            if problem is not None:
                return quarantine(problem)
            try:
                registered.append(_registered(descriptor, source, attestations))
            except SelfHashUnavailableError as error:
                return quarantine(
                    Coded(
                        "self_hash_unavailable", {"id": str(descriptor["id"]), "path": error.path}
                    )
                )
        clashes = [e for e in registered if (e.kind, e.id, version_key(e.version)) in self._entries]
        if clashes:
            # Discovery quarantines both packages of a namespace before they reach this (D7).
            raise RegistryBuildError(Coded("namespace_conflict", {"namespace": namespace}))
        for entry in registered:
            self.register(entry)
        return None

    def register(self, entry: Registered) -> None:
        """Add one registered descriptor; (kind, id, version) is unique. Raises
        `RuntimeError("registry_closed")` once the registry is built."""
        if self._closed:
            raise RuntimeError("registry_closed")
        key = (entry.kind, entry.id, version_key(entry.version))
        if key in self._entries:
            raise ValueError(f"{entry.kind} {entry.id} {entry.version} is already registered")
        self._entries[key] = entry

    def _resolve(self) -> None:
        """D4: record, on each descriptor, its tokens whose registry-derived name no registered
        descriptor gives. Static tokens were validated when they were registered."""
        names: set[tuple[str, str]] = set()
        by_kind = {kind: space for space, kind in REGISTRY_SPACES.items() if kind is not None}
        for entry in self._entries.values():
            if entry.kind in by_kind:
                names.add((by_kind[entry.kind], entry.id))
            names.update(
                (token.space, token.name)
                for token in map(parse, entry.provides)
                if token.space == "x"
            )
        for key, entry in self._entries.items():
            tokens = {token for clause in entry.requires for token in clause} | set(entry.provides)
            unresolved = sorted(
                (
                    token
                    for token in tokens
                    if parse(token).space in REGISTRY_SPACES
                    and (parse(token).space, parse(token).name) not in names
                ),
                key=lambda token: token.encode("utf-8"),
            )
            self._entries[key] = replace(entry, unresolved=tuple(unresolved))

    # -- reading -------------------------------------------------------------------------------

    @property
    def closed(self) -> bool:
        return self._closed

    def descriptors(self, kinds: Sequence[str] | None = None) -> tuple[Registered, ...]:
        """The registered descriptors (of `kinds`, if given), sorted by (kind, id, version key)."""
        selected = (e for e in self._entries.values() if kinds is None or e.kind in kinds)
        return tuple(sorted(selected, key=Registered.sort_key))

    def resolve(self, kind: str, identifier: str, version: str | None = None) -> Registered:
        """The descriptor (kind, id, version), the highest version when `version` is `None`;
        `KeyError` when none is registered."""
        if version is not None:
            return self._entries[(kind, identifier, version_key(version))]
        versions = [e for e in self._entries.values() if e.kind == kind and e.id == identifier]
        if not versions:
            raise KeyError((kind, identifier))
        return max(versions, key=Registered.sort_key)

    def admit(
        self,
        unit: str,
        method: str,
        definition: str,
        *,
        unit_version: str | None = None,
        method_version: str | None = None,
    ) -> Admission:
        """D5 on the registered unit, method and definition named (highest versions by default)."""
        return admit(
            self.resolve("unit_model", unit, unit_version),
            self.resolve("property_method", method, method_version),
            self.resolve("connection_definition", definition),
        )

    def admission_matrix(self, definition: str) -> tuple[Verdict, ...]:
        """D5's matrix over every registered unit × method on `definition`."""
        return admission_matrix(self, self.resolve("connection_definition", definition))

    @property
    def quarantined(self) -> tuple[Quarantine, ...]:
        return tuple(self._quarantined)

    @property
    def registry_sha256(self) -> str:
        return registry_sha256(self._entries.values())

    def snapshot(self) -> dict[str, Any]:
        """D10's snapshot document."""
        return snapshot_document(self._entries.values(), self._quarantined)
