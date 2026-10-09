"""The W27 registry snapshot: what the build under test can represent (W27-R22, R23).

Normative text: registration §5.7 and §17 Q1. The snapshot is built mechanically from the build at
hand: models from `list_models` (through `operations.dispatch`, whose canonical-JSON SHA-256 is
recorded beside the snapshot's own, F2/G14); routes from the providers the **revision binder** can
select, each with its provider id, its component records (`identifiers`, `synthetic`), the phases
it admits per component, and the model ids the binder accepts with it — read from the binder's own
tables, never from a hand-written list.

How a binder exposes selectable routes is binder-specific, and the reading is chosen by what the
binder exposes (W27-R63, registration §21.4), never by the package version alone: M02's binder
selects its basis by `record_source` and still says `0.1.1`. A binder no registered reading fits is
refused (`SnapshotUnsupportedError`, `registry_snapshot: unsupported(route enumeration)`, §17 Q1's
default) until an amendment registers its reading.

- **`0.1.1`** iff `__version__ == "0.1.1"` **and** `revision_binding` has no `basis_provider`:
  one implicit route — the binder builds every revision over `Syn001Provider`, admits exactly
  `canonical_components`' set, and accepts every model of `MODEL_BUILDERS`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from types import ModuleType
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


def _routes_0_1_1(binding: ModuleType) -> list[dict[str, Any]]:
    """0.1.1's binder: one implicit route over SYN-001 (`revision_binding.bind_revision_flowsheet`
    constructs `Syn001Provider()`; `canonical_components` admits a permutation of its set)."""
    import yaml  # noqa: PLC0415

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
            "model_ids": sorted(binding.MODEL_BUILDERS),
        }
    ]


def reading_for(binding: ModuleType, version: str) -> str:
    """W27-R63: the registered reading of this binder, or a refusal."""
    if version == "0.1.1" and not hasattr(binding, "basis_provider"):
        return "0.1.1"
    raise SnapshotUnsupportedError(
        f"registry_snapshot: unsupported(route enumeration) for openflowsheet {version}"
    )


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


def build_snapshot(version: str | None = None, binding: ModuleType | None = None) -> dict[str, Any]:
    """W27-R22's document for the build at hand (`version` and `binding` default to this build's
    `__version__` and `revision_binding`). Refuses a binder no registered reading fits (W27-R63)."""
    from openflowsheet import __version__  # noqa: PLC0415
    from openflowsheet.application import revision_binding  # noqa: PLC0415

    version = __version__ if version is None else version
    binding = revision_binding if binding is None else binding
    reading_for(binding, version)
    routes = _routes_0_1_1(binding)
    document, digest = list_models_document()
    return {
        "schema": SCHEMA,
        "package_version": version,
        "git_commit": git_commit(),
        "list_models_sha256": digest,
        "models": [{"model_id": m["model_id"]} for m in document["models"]],
        "routes": routes,
        "routes_per_revision": 1,
        "basis": "built by benchmarks.m06.w27.snapshot from the build at git_commit",
    }
