"""F8-WO2 (ADR 0067 D3, D4): the test-only v2 bundle factory. Not collected.

In 0.6 no production run writes a v2 bundle (v2-compiled runs come with F6, F8-WO6), so this is
the only writer: `record_v2` reruns a registered corpus case exactly as RC step 4 and F0 run it
(`scripts/corpus_identity.py` `solve`), then records the run as v2 with `run.bundle_v2`. The v1
run itself is unchanged, and so is its v1 bundle; the v2 bundle is written beside it.

What a v2-compiled run would carry and a v1 revision does not name is derived here, test-only
(F8 decisions WO2-1 to WO2-3):

- the **data lock** (ADR 0061 D10): the revision's `component_set.components` in revision order,
  each bound to the record of that id in the legacy file `component_set.record_source` names
  (the committed legacy index); every parameter set that file holds; and one `methods` row, the
  revision's property provider (`component_basis`) bound on the substream `mixed`;
- **`extensions_used`** (ADR 0060 D8): each instance's unit model, the provider, the material
  connection `nTP-v1`, the record types the lock holds and the data source `legacy-yaml`, each at
  its highest registered version;
- `environment.registry`: the process registry's SHA and the SHA of its snapshot.

F8-WO3 adds the replay side (ADR 0067 D5): `rerun_v2` reruns a v2 bundle's recorded revision as
`application.revision_replay` reruns a v1 one, under `registry.usage()`, into a `RerunV2`;
`rerecord` is the re-record tool for the registered v2 cases (`V2_CASES`): it reruns a bundle's
recorded documents and writes them as a new v2 bundle under the current registry; and
`edited_registry` is the test-only registry E-F8-5 changes (DECISION F8-WO3-6).
"""

from __future__ import annotations

import copy
import dataclasses
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.application import revision_run
from openflowsheet.application.revision_replay import declared_kinds
from openflowsheet.canonical import document_sha256
from openflowsheet.material.definitions import LEGACY_TEMPLATE
from openflowsheet.models.revision_flowsheet import component_basis
from openflowsheet.records.importers.legacy import available_records, committed_index
from openflowsheet.records.lock import build_lock, data_lock_sha256, method_entry
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import RecordStore
from openflowsheet.registry import Registry as ExtensionRegistry
from openflowsheet.registry import default_registry, usage
from openflowsheet.registry.descriptor import Registered
from openflowsheet.run import bundle_v2
from openflowsheet.run.bundle import read_artifact, read_manifest
from openflowsheet.run.bundle_v2 import write_bundle
from openflowsheet.run.manifest import RunManifest
from openflowsheet.run.manifest_v2 import EnvironmentRegistry, RunManifestV2, extensions_used_rows
from openflowsheet.run.replay_v2 import RerunV2, served_stack

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402

#: DECISION F8-WO2-2: the substream a v1 revision's one `nTP-v1` material binds its method on.
SUBSTREAM: Final = "mixed"
#: DECISION F8-WO2-3: the data source every legacy record comes from (ADR 0061 D12).
LEGACY_SOURCE: Final = "legacy-yaml"

SCHEMAS: Final = REPO_ROOT / "schemas"
#: The registered v2 cases: the corpus cases the factory records as v2 (F8-WO2), by (run set,
#: name). `rerecord` re-records a bundle of any of them.
V2_CASES: Final = (("s11-gp", "GP-C1"), ("s11-th", "TH-C1"))


def _schema_registry() -> Registry:
    resources = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


SCHEMA_REGISTRY: Final = _schema_registry()


def schema_errors(name: str, document: Any) -> list[str]:
    """Every error of `document` against the schema in `schemas/<name>` (by its `$id`)."""
    reference = load_json(SCHEMAS / name)["$id"]
    validator = Draft202012Validator({"$ref": reference}, registry=SCHEMA_REGISTRY)
    return [error.message for error in validator.iter_errors(document)]


def _legacy_file(path: str) -> Mapping[str, Any]:
    for entry in committed_index()["files"]:
        if entry["path"] == path:
            return entry
    raise KeyError(f"the legacy index holds no file {path!r}")


def lock_inputs(
    revision: Mapping[str, Any],
) -> tuple[list[tuple[str, str]], list[str], list[dict[str, str]]]:
    """The data lock's inputs of a v1 revision: (component id, record SHA) pairs in revision
    order, the parameter-set SHAs of its record source, and its one `methods` row."""
    component_set = revision["component_set"]
    records = _legacy_file(component_set["record_source"])["records"]
    by_id = {r["id"]: r["sha256"] for r in records if r["record_type"] == "component"}
    components = [(ident, by_id[ident]) for ident in component_set["components"]]
    sets = [r["sha256"] for r in records if r["record_type"] == "parameter_set"]
    provider = default_registry().resolve("property_method", component_basis(revision).provider_id)
    return components, sets, [method_entry(SUBSTREAM, provider)]


def references(
    revision: Mapping[str, Any], lock: Mapping[str, Any]
) -> list[tuple[str, str, str | None]]:
    """The (kind, id, version) references a v1 revision's run makes, each at its highest
    registered version (`None`)."""
    found: list[tuple[str, str, str | None]] = [
        ("unit_model", instance["model"]["id"], None) for instance in revision["instances"]
    ]
    found += [("property_method", row["method"], row["version"]) for row in lock["methods"]]
    found += [("connection_definition", LEGACY_TEMPLATE, None)]
    found += [("record_type", "component", None), ("data_source", LEGACY_SOURCE, None)]
    if lock["parameter_sets"]:
        found.append(("record_type", "parameter_set", None))
    return found


@dataclasses.dataclass(frozen=True)
class Recorded:
    """One corpus case recorded as v2: its v1 bundle, its v2 bundle and the inputs of the v2
    writer, so that a test can write it again (`rewrite`)."""

    v1: Path
    v2: Path
    manifest: RunManifestV2
    artifacts: Mapping[str, Any]
    lock: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    stack: StoreStack

    def rewrite(
        self,
        directory: Path,
        *,
        stack: StoreStack | None = None,
        repository: Sequence[Mapping[str, Any]] | None = None,
    ) -> RunManifestV2:
        """The same run written as a v2 bundle again, to `directory`, under the registers as
        they stand now: `stack`'s project register (the recording stack's when `None`) and
        `repository` (the package's when `None`)."""
        return write_bundle(
            directory,
            self.manifest,
            self.artifacts,
            lock=self.lock,
            snapshot=self.snapshot,
            stack=self.stack if stack is None else stack,
            repository=repository,
        )


def legacy_stack() -> StoreStack:
    """A fresh stack: an empty in-memory project store over the legacy store (ADR 0061 D8)."""
    return StoreStack(RecordStore.in_memory(), LegacyStore(available_records))


def record_v2(
    run_set: str,
    name: str,
    directory: Path,
    stack: StoreStack,
    *,
    registry: ExtensionRegistry | None = None,
) -> Recorded:
    """Rerun the registered corpus case (`run_set`, `name`) to `directory/v1` as F0 runs it, and
    record it as a v2 bundle in `directory/v2`, its records read from (and its lock's records
    adopted into) `stack`, under `registry` (the process registry by default)."""
    v1 = directory / "v1"
    gate.solve(run_set, name, v1)
    revision = read_artifact(v1, "revision.json")
    components, sets, methods = lock_inputs(revision)
    lock = build_lock(components, sets, methods, {}, stack)
    return _record(v1, directory / "v2", lock, stack, registry)


def _record(
    v1: Path,
    v2: Path,
    lock: Mapping[str, Any],
    stack: StoreStack,
    registry: ExtensionRegistry | None,
) -> Recorded:
    """The v1 bundle in `v1` written as a v2 bundle in `v2` with `lock`, under `registry`."""
    manifest, _ = read_manifest(v1)
    artifacts = {item: read_artifact(v1, item) for item in sorted(manifest.artifacts)}
    revision = artifacts["revision.json"]
    registry = registry if registry is not None else default_registry()
    snapshot = registry.snapshot()
    used = registry.extensions_used(references(revision, lock))
    assert used.unregistered == (), used.unregistered

    fields = {
        entry.name: getattr(manifest, entry.name) for entry in dataclasses.fields(RunManifest)
    }
    recorded = RunManifestV2(
        **fields,
        data_lock_sha256=data_lock_sha256(lock),
        extensions_used=extensions_used_rows(used.descriptors),
        environment_registry=EnvironmentRegistry(
            registry.registry_sha256, document_sha256(snapshot)
        ),
    )
    complete = write_bundle(v2, recorded, artifacts, lock=lock, snapshot=snapshot, stack=stack)
    return Recorded(v1, v2, complete, artifacts, lock, snapshot, stack)


def rerun_v2(bundle: Path, directory: Path) -> RerunV2:
    """Rerun the revision the v2 bundle in `bundle` records into `directory`, as
    `application.revision_replay` reruns a v1 revision bundle (its recorded document, the route
    selected from it, the default policy, as F0 solved it) and as RC step 5 compares one (the
    route's declared kinds), with `registry.usage()` recording what the run resolves.

    The recorded revision is a v1 document: its binder reads the packaged legacy files, not a
    record store, so the stack `replay_v2.served_stack` gives a caller is not consulted
    (DECISION F8-WO3-1)."""
    from openflowsheet.application.revision_run import select_route  # noqa: PLC0415
    from openflowsheet.orchestrator.policies import (  # noqa: PLC0415
        DEFAULT_POLICY_ID,
        resolve_policy,
    )
    from openflowsheet.verify.verdict import CheckPolicy  # noqa: PLC0415

    manifest, _ = bundle_v2.read_manifest(bundle)
    revision = read_artifact(bundle, "revision.json")
    route = select_route(revision)
    assert isinstance(route, revision_run.Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    with usage() as used:
        # Read at call time, so that a test may wrap it (E-F8-6's hidden `resolve`).
        fresh = revision_run.run_revision_session(
            route,
            revision,
            directory,
            run_id=manifest.run_id,
            policy=policy,
            check_policy=CheckPolicy(),
            policy_requested=DEFAULT_POLICY_ID,
        )
    return RerunV2(
        {item: read_artifact(directory, item) for item in sorted(fresh.artifacts)},
        variable_kinds=declared_kinds(route.binding.spec),
        usage=used.sorted(),
    )


def rerecord(
    bundle: Path,
    directory: Path,
    local: StoreStack,
    *,
    registry: ExtensionRegistry | None = None,
) -> Recorded:
    """The re-record tool for a registered v2 case (test tooling, not a served operation): rerun
    the documents the v2 bundle in `bundle` records into `directory/v1` and write the run as a
    new v2 bundle in `directory/v2` under `registry` (the process registry by default). The
    lock is the bundle's own (a rerun never re-resolves data, D5); its records are read with
    the bundle's embedded ones served before `local`, so a case whose records the local store
    lacks can still be re-recorded. Use it when a built-in changed on purpose: the old bundle
    replays `compatible_reproduction` with `extension_changed`, the re-recorded one exactly."""
    lock = read_artifact(bundle, bundle_v2.DATA_LOCK_NAME)
    rerun_v2(bundle, directory / "v1")
    return _record(directory / "v1", directory / "v2", lock, served_stack(bundle, local), registry)


def edited_registry(
    edits: Mapping[tuple[str, str, str], Mapping[str, Any] | None],
) -> ExtensionRegistry:
    """A test-only copy of the process registry in which each descriptor (kind, id, version) of
    `edits` has the given `Registered` fields replaced (for example `self_sha256` or `origin`), or
    is removed (`None`); every other descriptor is the process registry's. The copy is shallow:
    the process registry is not changed."""
    base = default_registry()
    entries: dict[Any, Registered] = {}
    found = set()
    for key, entry in base._entries.items():
        reference = (entry.kind, entry.id, entry.version)
        if reference not in edits:
            entries[key] = entry
            continue
        found.add(reference)
        change = edits[reference]
        if change is not None:
            entries[key] = dataclasses.replace(entry, **change)
    assert found == set(edits), sorted(set(edits) - found)
    edited = copy.copy(base)
    edited._entries = entries
    return edited
