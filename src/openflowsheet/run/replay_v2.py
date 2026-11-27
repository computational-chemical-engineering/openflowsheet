"""Replay of a v2 bundle: ADR 0067 D5's seven steps (F8-WO3).

DRAFT until ADR 0067 is Accepted. `run.replay.replay` dispatches here when the manifest names a
`bundle_format` (step 2); a manifest without one is a v1 bundle and replays there exactly as
before (E-F8-1). In 0.6 the only v2 bundles are F8-WO2's test-only factory's.

The steps run in D5's order and their reasons accumulate in that order:

1. **Integrity:** `run.bundle_v2.verify_bundle`; a failing archive is not re-run.
2. **Format:** a value other than `openflowsheet-bundle-v2` is `bundle_format_unsupported(<value>)`.
3. **Numerical policy:** ADR 0025, unchanged: an unknown policy is inspected, never compared.
4. **Environment:** ADR 0007 D4's mode (`run.replay.decide_mode`), unchanged.
5. **Extensions:** each `extensions_used` row against the current registry's snapshot:
   `extension_unavailable(<kind>, <id>, <version>)` when it holds no such (kind, id, version),
   `extension_changed(<kind>, <id>, <version>)` when its `descriptor_sha256` or `self_sha256`
   differs. A changed built-in reruns as `compatible_reproduction`; anything else here stops the
   replay. Descriptors the run did not use are compared too and only counted
   (`registry_comparison.unused_differences`); evidence fields are never compared.
6. **Data:** each record SHA the lock names resolves from `artifacts/records/` (the identity rule
   re-applied to the bytes: `store_object_corrupt(<sha>)` otherwise) or the local F3 store;
   each SHA neither holds is `data_unavailable(<sha>)`, all listed, sorted.
7. **Rerun and compare:** the caller's rerun (a `RerunV2`), compared as ADR 0007 D4 compares a
   v1 one, over the run's v1 artifacts (the R0 projection of `run.identity` covers
   `solution-state-v2`); the rerun's `registry.usage()` set must lie in `extensions_used`, each
   extra (kind, id) a difference `extension_use_undeclared(<kind>, <id>)`.

Any reason from steps 2, 3, 5 or 6 makes the report `inspected_archived_results` / `NOT_RUN`
(ADR 0007 D4: nothing is rerun), except step 5's changed built-in. As in v1 the rerun is the
caller's, made before `replay` is called; a caller that reruns serves the bundle's embedded
records before its store (`served_stack`). Nothing here opens a network connection.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.records.importers.legacy import available_records
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import RecordStore, RecordStoreError, object_bytes
from openflowsheet.registry import Registry, default_registry
from openflowsheet.registry.tokens import Coded
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME, BundleIntegrity, read_artifact
from openflowsheet.run.bundle_v2 import (
    DATA_LOCK_NAME,
    RECORDS_DIR,
    RECORDS_INDEX_NAME,
    REGISTRY_SNAPSHOT_NAME,
    V2_NAMES,
    locked_records,
    read_manifest,
    record_name,
    verify_bundle,
)
from openflowsheet.run.compare import CURRENT_POLICY_ID, KNOWN_POLICY_IDS, differences
from openflowsheet.run.manifest import Environment, environment
from openflowsheet.run.manifest_v2 import BUNDLE_FORMAT, ExtensionRow, RunManifestV2

# v1's comparison rules apply unchanged to the v1 artifacts a v2 bundle carries (D5 step 7: "as
# ADR 0007 D4"); `run/replay.py` keeps them, so they are reused, not copied.
from openflowsheet.run.replay import (
    ReplayMode,
    ReplayReport,
    ReplayVerdict,
    Rerun,
    _as_recorded,
    _is_verdict_only,
    _verdict_drift,
    decide_mode,
    unknown_policy_reason,
)

#: The reasons `run.replay` states in words, kept word for word.
FAILED_INTEGRITY: Final = "the archive failed its integrity check and was not re-run"
NO_RERUN: Final = "no rerun was supplied"
#: DECISION F8-WO3-5: a rerun that brings no `usage()` set cannot show it used only what the
#: recorded identity declares, so the comparison lists this and the verdict is `MISMATCH`.
NO_USAGE: Final = (
    "registry usage: the rerun recorded no registry.usage() set, so its extensions cannot be "
    "checked against extensions_used (ADR 0067 D5 step 7)"
)

#: A (kind, id, version) reference, as `registry.Usage` records it.
Reference = tuple[str, str, str]


@dataclass(frozen=True)
class RerunV2(Rerun):
    """A v2 rerun: `Rerun` and the (kind, id, version) set `registry.usage()` recorded while it
    ran (`Usage.sorted()`), for D5 step 7's cross-check."""

    usage: tuple[Reference, ...] | None = None


def coded_reason(coded: Coded) -> str:
    """A catalogued reason as D5 spells it: `<code>(<param>, …)`, params in their order."""
    return f"{coded.code}({', '.join(coded.params.values())})"


def bundle_format(directory: Path) -> str | None:
    """The manifest's `bundle_format`, or `None` when it names none (or there is no manifest it
    can read: the v1 reader then refuses it as before)."""
    path = Path(directory) / MANIFEST_NAME
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict) or "bundle_format" not in document:
        return None
    return str(document["bundle_format"])


class ServedStack(StoreStack):
    """D5 step 7's resolution order: the bundle's embedded records, then the local stack (its
    project store, then its legacy store). Writes go to the local project store."""

    def __init__(self, bundle: RecordStore, local: StoreStack) -> None:
        super().__init__(local.project, local.legacy)
        self.bundle = bundle

    def layers(self) -> tuple[RecordStore, ...]:
        return (self.bundle, *super().layers())


def served_stack(directory: Path, local: StoreStack) -> ServedStack:
    """The stack a rerun of the v2 bundle in `directory` reads its records from: every embedded
    record whose bytes pass the identity rule, before `local`."""
    bundle = RecordStore.in_memory()
    for sha in _embedded(Path(directory)):
        record = _embedded_record(Path(directory), sha)
        if record is not None:
            bundle.add(record, expected=sha)
    return ServedStack(bundle, local)


def replay_v2(
    directory: Path,
    rerun: Rerun | None = None,
    *,
    current: Environment | None = None,
    registry: Registry | None = None,
    store: StoreStack | None = None,
) -> ReplayReport:
    """Replay the v2 bundle in `directory` by D5's seven steps. `rerun` is the fresh result (a
    `RerunV2` carries its usage set); `registry` is the current registry (the process registry
    by default) and `store` the local F3 store (by default an empty project store over the
    records this installation provides)."""
    directory = Path(directory)
    here = current if current is not None else environment()
    value = bundle_format(directory)
    if value != BUNDLE_FORMAT:
        return _unsupported(directory, value, here)

    integrity = verify_bundle(directory)  # step 1
    manifest, _ = read_manifest(directory)
    mode, environment_reasons = decide_mode(manifest.environment, here)  # step 4, decided first
    report: dict[str, Any] = {
        "integrity": integrity,
        "recorded_environment": manifest.environment.as_document(),
        "current_environment": here.as_document(),
    }
    if not integrity.ok:
        return ReplayReport(
            mode="inspected_archived_results",
            verdict="NOT_RUN",
            reasons=(FAILED_INTEGRITY, *environment_reasons),
            **report,
        )

    policy_id = manifest.numerical_policy_id  # step 3
    policy_reasons = () if policy_id in KNOWN_POLICY_IDS else (unknown_policy_reason(policy_id),)
    current_registry = registry if registry is not None else default_registry()
    comparison, extension_reasons, stops, changed_builtin = _registry_comparison(
        manifest, read_artifact(directory, REGISTRY_SNAPSHOT_NAME), current_registry.snapshot()
    )  # step 5
    local = store if store is not None else _installation_stack()
    availability, data_reasons = _data_availability(directory, local)  # step 6
    report |= {"registry_comparison": comparison, "data_availability": availability}
    reasons = (*policy_reasons, *environment_reasons, *extension_reasons, *data_reasons)

    if mode == "exact_replay" and changed_builtin:
        mode = "compatible_reproduction"
    if policy_reasons or stops or data_reasons or mode == "inspected_archived_results":
        return ReplayReport(
            mode="inspected_archived_results",
            verdict="NOT_RUN",
            reasons=(*reasons, *(() if rerun is not None else (NO_RERUN,))),
            **report,
        )
    if rerun is None:
        return ReplayReport(mode=mode, verdict="NOT_RUN", reasons=(*reasons, NO_RERUN), **report)
    return _compared(directory, manifest, rerun, mode, reasons, report)  # step 7


def _unsupported(directory: Path, value: str | None, here: Environment) -> ReplayReport:
    """Step 2's refusal of a format this build does not read. Its layout is unknown, so step 1
    re-hashes only what every format's manifest indexes: each file under `artifacts/` against
    the `artifacts` map (DECISION F8-WO3-3)."""
    document = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    indexed = document.get("artifacts") or {}
    root = directory / ARTIFACT_DIR
    missing = sorted(name for name in indexed if not (root / name).is_file())
    tampered = sorted(
        name
        for name, sha in indexed.items()
        if (root / name).is_file() and file_sha256(root / name) != sha
    )
    present = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    unexpected = sorted(present - set(indexed))
    integrity = BundleIntegrity(
        ok=not (missing or tampered or unexpected),
        missing=tuple(missing),
        tampered=tuple(tampered),
        unexpected=tuple(unexpected),
    )
    reason = coded_reason(Coded("bundle_format_unsupported", {"value": str(value)}))
    recorded = document.get("environment")
    return ReplayReport(
        mode="inspected_archived_results",
        verdict="NOT_RUN",
        integrity=integrity,
        recorded_environment=dict(recorded) if isinstance(recorded, dict) else {},
        current_environment=here.as_document(),
        reasons=(reason,),
    )


def _registry_comparison(
    manifest: RunManifestV2, recorded: Mapping[str, Any], current: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str], bool, bool]:
    """Step 5: the report member, the reasons in `extensions_used` order, whether a reason stops
    the replay, and whether a used built-in changed (DECISION F8-WO3-4: built-in is the current
    registry's `origin`)."""
    rows = _snapshot_rows(current)
    used = {(kind, ident, version) for kind, ident, version, _, _ in manifest.extensions_used}
    changed: list[list[str]] = []
    missing: list[list[str]] = []
    reasons: list[str] = []
    stops = changed_builtin = False
    for kind, ident, version, descriptor, self_sha in manifest.extensions_used:
        params = {"kind": kind, "id": ident, "version": version}
        row = rows.get((kind, ident, version))
        if row is None:
            missing.append([kind, ident, version])
            reasons.append(coded_reason(Coded("extension_unavailable", params)))
            stops = True
        elif (row["descriptor_sha256"], row["self_sha256"]) != (descriptor, self_sha):
            changed.append([kind, ident, version])
            reasons.append(coded_reason(Coded("extension_changed", params)))
            if row["origin"] == "builtin":
                changed_builtin = True
            else:
                stops = True
    return (
        {
            "recorded_registry_sha256": manifest.environment_registry.registry_sha256,
            "current_registry_sha256": current["registry_sha256"],
            "changed": changed,
            "missing": missing,
            "unused_differences": _unused_differences(recorded, current, used),
        },
        reasons,
        stops,
        changed_builtin,
    )


def _snapshot_rows(snapshot: Mapping[str, Any]) -> dict[Reference, Mapping[str, Any]]:
    return {(row["kind"], row["id"], row["version"]): row for row in snapshot["extensions"]}


def _unused_differences(
    recorded: Mapping[str, Any], current: Mapping[str, Any], used: set[Reference]
) -> int:
    """How many descriptors the run did not use are present on one side only or differ in
    `descriptor_sha256` or `self_sha256` (evidence fields are never compared)."""

    def identities(snapshot: Mapping[str, Any]) -> dict[Reference, tuple[str, str]]:
        return {
            key: (row["descriptor_sha256"], row["self_sha256"])
            for key, row in _snapshot_rows(snapshot).items()
            if key not in used
        }

    before, after = identities(recorded), identities(current)
    return sum(1 for key in set(before) | set(after) if before.get(key) != after.get(key))


def _installation_stack() -> StoreStack:
    """The local store when the caller names none: an empty project store over the records
    this installation provides (ADR 0061 D8)."""
    return StoreStack(RecordStore.in_memory(), LegacyStore(available_records))


def _embedded(directory: Path) -> list[str]:
    index = read_artifact(directory, RECORDS_INDEX_NAME)
    return [entry["sha256"] for entry in index["records"] if entry["embedded"]]


def _embedded_record(directory: Path, sha: str) -> Mapping[str, Any] | None:
    """The embedded record `sha` when its bytes are the canonical bytes of an identity
    projection hashing to `sha` (ADR 0061's identity rule), else `None`."""
    data = (directory / ARTIFACT_DIR / record_name(sha)).read_bytes()
    try:
        record = json.loads(data)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    computed, canonical = object_bytes(record)
    return record if (computed, canonical) == (sha, data) else None


def _data_availability(directory: Path, local: StoreStack) -> tuple[dict[str, Any], list[str]]:
    """Step 6: the report member and the reasons, by SHA."""
    lock = read_artifact(directory, DATA_LOCK_NAME)
    embedded = set(_embedded(directory))
    counts = {"embedded": 0, "from_store": 0}
    missing: list[str] = []
    reasons: list[str] = []
    for sha in locked_records(lock):
        if sha in embedded:
            if _embedded_record(directory, sha) is None:
                reasons.append(coded_reason(Coded("store_object_corrupt", {"sha": sha})))
            else:
                counts["embedded"] += 1
            continue
        try:
            local.object_bytes(sha)
        except RecordStoreError as error:
            if error.coded is None:
                raise
            if error.coded.code == "data_unavailable":
                missing.append(sha)
            reasons.append(coded_reason(error.coded))
            continue
        counts["from_store"] += 1
    return {**counts, "missing": missing}, reasons


def _v1_artifacts(names: Iterable[str]) -> list[str]:
    """The run's own artifacts of a v2 bundle: every indexed name but D3's lock, snapshot, index
    and embedded records."""
    return sorted(
        name for name in names if name not in V2_NAMES and not name.startswith(f"{RECORDS_DIR}/")
    )


def _compared(
    directory: Path,
    manifest: RunManifestV2,
    rerun: Rerun,
    mode: ReplayMode,
    reasons: tuple[str, ...],
    report: dict[str, Any],
) -> ReplayReport:
    """Step 7: `run.replay.replay`'s comparison over the v1 artifacts, then the usage check."""
    policy_id = manifest.numerical_policy_id
    names = _v1_artifacts(manifest.artifacts)
    found: list[str] = []
    bitwise = True
    changed_near_threshold: list[str] = []
    drifted: set[str] = set()
    kinds = rerun.variable_kinds if policy_id == CURRENT_POLICY_ID else None
    for name in names:
        archived = read_artifact(directory, name)
        fresh = rerun.artifacts.get(name)
        if fresh is None:
            found.append(f"{name}: the rerun produced no such artifact")
            continue
        fresh, recorded_differently = _as_recorded(name, fresh, archived, policy_id)
        found += recorded_differently
        found += [
            f"{name}{entry}"
            for entry in differences(fresh, archived, policy_id=policy_id, variable_kinds=kinds)
        ]
        if fresh != archived:
            bitwise = False
        drift = _verdict_drift(name, fresh, archived)
        changed_near_threshold += drift
        if drift:
            drifted.add(name)
    for name in sorted(set(rerun.artifacts) - set(names)):
        found.append(f"{name}: the rerun produced an artifact the archive does not have")
        bitwise = False
    found += _undeclared_use(manifest.extensions_used, rerun)

    real = [entry for entry in found if not _is_verdict_only(entry, drifted)]
    verdict: ReplayVerdict = "MATCH" if not real else "MISMATCH"
    return ReplayReport(
        mode=mode,
        verdict=verdict,
        reasons=reasons,
        differences=tuple(found),
        bitwise_floats=bitwise,
        verdict_changed_near_threshold=tuple(changed_near_threshold),
        **report,
    )


def _undeclared_use(declared: tuple[ExtensionRow, ...], rerun: Rerun) -> list[str]:
    """Step 7's cross-check: `extension_use_undeclared(<kind>, <id>)` for each (kind, id) the
    rerun resolved at a (kind, id, version) `extensions_used` does not hold, sorted."""
    usage = rerun.usage if isinstance(rerun, RerunV2) else None
    if usage is None:
        return [NO_USAGE]
    rows = {(kind, ident, version) for kind, ident, version, _, _ in declared}
    extra = sorted(
        {(kind, ident) for kind, ident, version in usage if (kind, ident, version) not in rows},
        key=lambda pair: (pair[0].encode("utf-8"), pair[1].encode("utf-8")),
    )
    return [
        coded_reason(Coded("extension_use_undeclared", {"kind": kind, "id": ident}))
        for kind, ident in extra
    ]
