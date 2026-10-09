"""The replay bundle: an archive a third party can re-run, or failing that, inspect. K05.

ADR 0006 D1.3 and mode C: a bundle **references** the backend by hash and never embeds it.
That is a distribution rule (the CasADi wheel carries bytes the project may not redistribute)
and it is also the honest one — a bundle that contained its own interpreter would be claiming
to be a reproduction when it is a copy.

**Integrity is per artifact and the index is hashed too.** Every artifact is stored under its
own SHA-256 and listed in the manifest's `artifacts` map; verifying a bundle re-hashes each
file and compares. A bundle whose index says one thing and whose bytes say another is
`tampered`, which is a typed result and not an exception — blueprint §8.3 wants replay to
*report* what it found, including that.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

from openflowsheet.canonical import canonical_json, file_sha256
from openflowsheet.run.manifest import Environment, RunManifest

MANIFEST_NAME = "run-manifest.json"
ARTIFACT_DIR = "artifacts"


class BundleError(RuntimeError):
    """A bundle that cannot be read at all. A bundle that reads but disagrees is `tampered`."""


@dataclass(frozen=True)
class BundleIntegrity:
    """What verification found. `ok` is a conclusion, not the absence of one."""

    ok: bool
    missing: tuple[str, ...] = ()
    tampered: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()

    def as_document(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "missing": list(self.missing),
            "tampered": list(self.tampered),
            "unexpected": list(self.unexpected),
        }


def write_bundle(
    directory: Path, manifest: RunManifest, artifacts: Mapping[str, Any]
) -> RunManifest:
    """Write the bundle and return the manifest with its `artifacts` index filled in.

    The index is built *from the bytes written*, not from what the caller said it was writing:
    the manifest's job is to describe the archive, and a hash supplied alongside the content it
    is supposed to describe is a hash of an intention.
    """
    from dataclasses import replace  # noqa: PLC0415

    directory = Path(directory)
    (directory / ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)

    index: dict[str, str] = {}
    for name, document in sorted(artifacts.items()):
        path = directory / ARTIFACT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json(document))
        index[name] = file_sha256(path)

    complete = replace(manifest, artifacts=index)
    (directory / MANIFEST_NAME).write_bytes(canonical_json(complete.as_document()))
    return complete


def read_manifest(directory: Path) -> tuple[RunManifest, dict[str, Any]]:
    """Read a bundle's manifest, and return the raw document beside the typed one.

    Both, because the typed one recomputes `structural_sha256` from its contents while the raw
    one carries what was written. Comparing them is how a manifest edited after the fact is
    caught, and `verify_bundle` does exactly that.
    """
    path = Path(directory) / MANIFEST_NAME
    if not path.is_file():
        raise BundleError(f"no {MANIFEST_NAME} in {directory}")
    document = json.loads(path.read_text(encoding="utf-8"))

    # S8: built from the dataclass's own fields rather than a hand-kept key list. The list
    # was a whitelist in disguise — the exact shape `NON_STRUCTURAL`'s removal-list design was
    # chosen to avoid — and a field added to `RunManifest` but forgotten here would have read
    # back as its default and made every bundle carrying it fail integrity.
    recorded = document["environment"]
    fields = {
        name: document[name]
        for name in (entry.name for entry in dataclass_fields(RunManifest))
        if name in document and name != "environment"
    }
    manifest = RunManifest(environment=Environment(**recorded), **fields)

    # A field added to `RunManifest` and not read here would be silently dropped, and the
    # self-hash would then always disagree. Better to say so than to let it read as tampering.
    missing = sorted(set(document) - set(manifest.as_document()))
    if missing:
        raise BundleError(
            f"{MANIFEST_NAME} carries fields this reader does not know: {missing}. A manifest "
            "it cannot fully reconstruct is one it cannot check."
        )
    return manifest, document


def read_artifact(directory: Path, name: str) -> Any:
    path = Path(directory) / ARTIFACT_DIR / name
    if not path.is_file():
        raise BundleError(f"the bundle has no artifact {name!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_bundle(directory: Path) -> BundleIntegrity:
    """Re-hash every artifact against the index, and the manifest against itself."""
    directory = Path(directory)
    manifest, document = read_manifest(directory)

    missing: list[str] = []
    tampered: list[str] = []
    for name, recorded in sorted(manifest.artifacts.items()):
        path = directory / ARTIFACT_DIR / name
        if not path.is_file():
            missing.append(name)
        elif file_sha256(path) != recorded:
            tampered.append(name)

    present = {
        str(path.relative_to(directory / ARTIFACT_DIR))
        for path in (directory / ARTIFACT_DIR).rglob("*")
        if path.is_file()
    }
    unexpected = sorted(present - set(manifest.artifacts))

    # T07 ruling round 2 F1.4: a revision bundle's `solution-state.json`, intact by its hash, is
    # cross-checked against itself and the certificate beside it, which an index rebuilt by a
    # forger cannot see. A bundle without the file — every K05 bundle — is untouched.
    _cross_check_solution_state(directory, manifest.artifacts, missing, tampered)
    # T07 W3-Q4: a revision bundle's `solve-path.json` must name a request that resolves, on its
    # recorded route, to the policy the manifest hashed; otherwise the file is forged.
    _cross_check_solve_path(directory, manifest, missing, tampered)

    # The manifest against itself. **Both** hashes: `structural_sha256` is identity and
    # excludes the environment and the artifact index by design, so it cannot detect an edit
    # to either — the Fable review of K05 measured exactly that, twice. `manifest_sha256`
    # covers the whole document and is what integrity actually rests on.
    if document.get("manifest_sha256") != manifest.manifest_sha256:
        tampered.append(MANIFEST_NAME)
    elif document.get("structural_sha256") != manifest.structural_sha256:
        tampered.append(MANIFEST_NAME)

    return BundleIntegrity(
        ok=not (missing or tampered or unexpected),
        missing=tuple(missing),
        tampered=tuple(sorted(tampered)),
        unexpected=tuple(unexpected),
    )


def _cross_check_solution_state(
    directory: Path, index: Mapping[str, str], missing: list[str], tampered: list[str]
) -> None:
    """Put `solution-state.json` in `tampered` when it is inconsistent (ruling round 2 F1.4).

    Only a file that is indexed, present and intact is judged; the certificate it is judged
    against is the parsed `solution-certificate.json` when that is indexed, present and intact,
    else `None` (a state with no certificate is itself a reason)."""
    from openflowsheet.run.solution_state import NAME, inconsistencies

    if NAME not in index or NAME in missing or NAME in tampered:
        return
    certificate_name = "solution-certificate.json"
    certificate = None
    if (
        certificate_name in index
        and certificate_name not in missing
        and certificate_name not in tampered
    ):
        try:
            certificate = read_artifact(directory, certificate_name)
        except ValueError:  # indexed bytes that are not JSON: no certificate to judge against
            certificate = None
    try:
        state = read_artifact(directory, NAME)
    except ValueError:  # bytes that hash as indexed but are not JSON
        tampered.append(NAME)
        return
    if inconsistencies(state, certificate if isinstance(certificate, Mapping) else None):
        tampered.append(NAME)


SOLVE_PATH_NAME = "solve-path.json"


def _cross_check_solve_path(
    directory: Path, manifest: RunManifest, missing: list[str], tampered: list[str]
) -> None:
    """Put `solve-path.json` in `tampered` when its request does not give the manifest's policy.

    T07 W3-Q4 (decision log, 2026-09-27): `policy_requested`, resolved on the recorded
    `solve_path` by the application registry (ruling round 1 R2.3), must hash to the manifest's
    `policy_sha256` — either as resolved, or with the one change admission makes to a resolved
    policy, a `max_property_calls` lowered to the value `solve-policy.json` records (§8.3).
    Only an indexed, present and intact file is judged, and an unknown route or policy id is
    itself a reason. A bundle without the file — every K05 bundle — is untouched.

    The registry is the application's: imported here, as `run.session` imports the binder's
    inputs, so that `run/` has no import-time dependency on `application/`.
    """
    from dataclasses import replace  # noqa: PLC0415

    from openflowsheet.application.policies import (  # noqa: PLC0415
        INNER_ROUTE,
        ROUTE_DEFAULT_POLICY,
        resolve_policy,
    )
    from openflowsheet.run.manifest import policy_sha256  # noqa: PLC0415

    index = manifest.artifacts
    if SOLVE_PATH_NAME not in index or SOLVE_PATH_NAME in missing or SOLVE_PATH_NAME in tampered:
        return
    try:
        recorded = read_artifact(directory, SOLVE_PATH_NAME)
    except ValueError:  # bytes that hash as indexed but are not JSON
        tampered.append(SOLVE_PATH_NAME)
        return
    route = recorded.get("solve_path") if isinstance(recorded, Mapping) else None
    requested = recorded.get("policy_requested") if isinstance(recorded, Mapping) else None
    # M02 design note §4.4: `revision_coupled` resolves its default through its inner route.
    known = [path for path in (*ROUTE_DEFAULT_POLICY, *INNER_ROUTE) if path == route]
    resolved = resolve_policy(requested, known[0]) if known and isinstance(requested, str) else None
    if resolved is None:
        tampered.append(SOLVE_PATH_NAME)
        return
    candidates = [resolved]
    policy_name = "solve-policy.json"
    if policy_name in index and policy_name not in missing and policy_name not in tampered:
        try:
            recorded_policy = read_artifact(directory, policy_name)
        except ValueError:
            recorded_policy = None
        calls = (
            recorded_policy.get("max_property_calls")
            if isinstance(recorded_policy, Mapping)
            else None
        )
        if (
            isinstance(calls, int)
            and not isinstance(calls, bool)
            and 1 <= calls < resolved.max_property_calls
        ):
            candidates.append(replace(resolved, max_property_calls=calls))
    if all(policy_sha256(candidate) != manifest.policy_sha256 for candidate in candidates):
        tampered.append(SOLVE_PATH_NAME)
