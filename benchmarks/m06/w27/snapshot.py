"""The W27 registry snapshot: what the build under test can represent (W27-R22, R23).

Normative text: registration §5.7 and §17 Q1. The snapshot is built mechanically from the build at
hand: models from `list_models` (through `operations.dispatch`, whose canonical-JSON SHA-256 is
recorded beside the snapshot's own, F2/G14); routes from the providers the **revision binder** can
select, each with its provider id, its component records (`identifiers`, `synthetic`), the phases
it admits per component, and the model ids the binder accepts with it — read from the binder's own
tables, never from a hand-written list.

How a binder exposes selectable routes is version-specific. A reading is registered here per
package version; for any other version the builder refuses (`SnapshotUnsupportedError`,
`registry_snapshot: unsupported(route enumeration)`, §17 Q1's default) until an amendment registers
the reading for that binder (M01/M02 at M07). At 0.1.1 there is one implicit route: the binder
builds every revision over `Syn001Provider`, admits exactly `canonical_components`' set, and
accepts every model of `MODEL_BUILDERS`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from typing import Any, Final

from benchmarks.m06.w27 import registration

SCHEMA: Final[str] = "w27-registry-snapshot-v1"
#: `syn001/components.yaml` is the SYN-001 records' source (the provider carries ids only).
SYN001_RECORDS: Final = registration.ROOT / "benchmarks" / "syn001" / "components.yaml"
#: The provider's phase names, as the classifier's phase kinds (W27-R06).
PHASE_KINDS: Final[Mapping[str, str]] = {"LIQUID": "liquid", "VAPOR": "vapor", "SOLID": "solid"}


class SnapshotUnsupportedError(RuntimeError):
    """§17 Q1: this build's route enumeration is not registered; no snapshot is built."""


def list_models_document() -> tuple[dict[str, Any], str]:
    """`list_models` through the operations table, and the SHA-256 of its canonical JSON."""
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415
    from openflowsheet.application.operations import dispatch  # noqa: PLC0415
    from openflowsheet.canonical import canonical_json  # noqa: PLC0415

    app = LocalApplication.in_memory()
    try:
        document: dict[str, Any] = dispatch(app, "list_models", {})
    finally:
        app.close()
    return document, registration.sha256_bytes(canonical_json(document))


def _routes_0_1_1() -> list[dict[str, Any]]:
    """0.1.1's binder: one implicit route over SYN-001 (`revision_binding.bind_revision_flowsheet`
    constructs `Syn001Provider()`; `canonical_components` admits a permutation of its set)."""
    import yaml  # noqa: PLC0415

    from openflowsheet.application.revision_binding import MODEL_BUILDERS  # noqa: PLC0415
    from openflowsheet.models.revision_flowsheet import canonical_components  # noqa: PLC0415
    from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: PLC0415

    capabilities = Syn001Provider().describe()
    admitted = canonical_components(list(capabilities.components))
    if tuple(admitted) != tuple(capabilities.components):
        raise SnapshotUnsupportedError(
            "registry_snapshot: unsupported(the binder's component set is not the provider's)"
        )
    records = yaml.safe_load(SYN001_RECORDS.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in records["components"]}
    phases = sorted(PHASE_KINDS[str(p)] for p in capabilities.phases)
    components = []
    for cid in admitted:
        record = by_id[cid]
        identifiers = record.get("identifiers") or {}
        components.append(
            {
                "id": cid,
                "name": record.get("name"),
                "formula": identifiers.get("formula"),
                "cas": identifiers.get("cas"),
                "synthetic": bool(record.get("synthetic")),
                "phases": phases,
            }
        )
    return [
        {
            "provider_id": capabilities.provider_id,
            "components": components,
            "model_ids": sorted(MODEL_BUILDERS),
        }
    ]


#: Registered readings of the binder's route tables, by package version (§17 Q1). Each returns
#: `routes`; `routes_per_revision` is the binder's (one route per revision at 0.1.1).
READINGS: Final[Mapping[str, tuple[Callable[[], list[dict[str, Any]]], int]]] = {
    "0.1.1": (_routes_0_1_1, 1),
}


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(registration.ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_snapshot(version: str | None = None) -> dict[str, Any]:
    """W27-R22's document for the build at hand. Refuses an unregistered binder reading."""
    from openflowsheet import __version__  # noqa: PLC0415

    version = __version__ if version is None else version
    if version not in READINGS:
        raise SnapshotUnsupportedError(
            f"registry_snapshot: unsupported(route enumeration) for openflowsheet {version}"
        )
    reading, per_revision = READINGS[version]
    document, digest = list_models_document()
    return {
        "schema": SCHEMA,
        "package_version": version,
        "git_commit": git_commit(),
        "list_models_sha256": digest,
        "models": [{"model_id": m["model_id"]} for m in document["models"]],
        "routes": reading(),
        "routes_per_revision": per_revision,
        "basis": "built by benchmarks.m06.w27.snapshot from the build at git_commit",
    }
