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

- **`bases-v1`** iff `revision_binding` exposes `SELECTABLE_BASES` (every `ComponentBasis` its
  `component_basis` can return) and `MODEL_BASES` (model id -> the provider ids of the bases on
  which the binder accepts it, the table its own `model_unsupported` refusal reads): one route per
  basis, in `SELECTABLE_BASES` order, from `basis_provider(b).describe()` and the provider's
  records; the route's models are those `MODEL_BASES` puts on `b`. A provider whose records and
  phases are not registered here (`PROVIDER_LINES`) refuses rather than being guessed.
- **`0.1.1`** iff `__version__ == "0.1.1"` **and** `revision_binding` has no `basis_provider`:
  one implicit route — the binder builds every revision over `Syn001Provider`, admits exactly
  `canonical_components`' set, and accepts every model of `MODEL_BUILDERS`.

Either way a revision binds on one basis (`routes_per_revision = 1`).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
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


def _component_rows(
    records_path: Path, ids: Sequence[str], phases: Mapping[str, list[str]]
) -> list[dict[str, Any]]:
    """W27-R23's component rows, in `ids` order, from a `components.yaml` of records."""
    import yaml  # noqa: PLC0415

    records = yaml.safe_load(records_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in records["components"]}
    missing = [cid for cid in ids if cid not in by_id]
    if missing:
        raise SnapshotUnsupportedError(
            f"registry_snapshot: unsupported(no record for {missing} in {records_path.name})"
        )
    rows = []
    for cid in ids:
        record = by_id[cid]
        identifiers = record.get("identifiers") or {}
        rows.append(
            {
                "id": cid,
                "name": record.get("name"),
                "formula": identifiers.get("formula"),
                "cas": identifiers.get("cas"),
                "synthetic": bool(record.get("synthetic")),
                "phases": phases[cid],
            }
        )
    return rows


def _routes_0_1_1(binding: ModuleType) -> list[dict[str, Any]]:
    """0.1.1's binder: one implicit route over SYN-001 (`revision_binding.bind_revision_flowsheet`
    constructs `Syn001Provider()`; `canonical_components` admits a permutation of its set)."""
    from openflowsheet.models.revision_flowsheet import canonical_components  # noqa: PLC0415
    from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: PLC0415

    capabilities = Syn001Provider().describe()
    admitted = canonical_components(list(capabilities.components))
    if tuple(admitted) != tuple(capabilities.components):
        raise SnapshotUnsupportedError(
            "registry_snapshot: unsupported(the binder's component set is not the provider's)"
        )
    every = sorted(PHASE_KINDS[str(p)] for p in capabilities.phases)
    components = _component_rows(SYN001_RECORDS, admitted, {cid: every for cid in admitted})
    return [
        {
            "provider_id": capabilities.provider_id,
            "components": components,
            "model_ids": sorted(binding.MODEL_BUILDERS),
        }
    ]


# -- bases-v1 (W27-R63 item 1) -------------------------------------------------------------------


def _syn001_line(components: Sequence[str], every: list[str]) -> tuple[Path, dict[str, list[str]]]:
    """SYN-001: `benchmarks/syn001/components.yaml`; every phase of `describe()` for every
    component (as at 0.1.1)."""
    return SYN001_RECORDS, {cid: every for cid in components}


def _pr_c1_line(components: Sequence[str], every: list[str]) -> tuple[Path, dict[str, list[str]]]:
    """`pr-c1-v1`: the records `pr_c1.load_records` reads (`pr_c1.RECORDS_PATH`, whose CAS RN and
    formula the typed records do not carry); `vapor` for the indices in `pr_c1.LIGHT`, every
    phase of `describe()` for the others."""
    from openflowsheet.thermo import pr_c1  # noqa: PLC0415

    phases = {
        cid: (["vapor"] if index in pr_c1.LIGHT else every) for index, cid in enumerate(components)
    }
    return registration.ROOT / pr_c1.RECORDS_PATH, phases


#: W27-R63's per-provider lines: where each provider keeps its records and how it admits phases,
#: given the basis' components (in order) and `describe().phases` as phase kinds.
PROVIDER_LINES: Final[
    Mapping[str, Callable[[Sequence[str], list[str]], tuple[Path, dict[str, list[str]]]]]
] = {
    "syn001": _syn001_line,
    "pr-c1-v1": _pr_c1_line,
}


def _routes_bases_v1(binding: ModuleType, list_models_ids: Sequence[str]) -> list[dict[str, Any]]:
    """W27-R63 item 1: one route per selectable basis, read from the binder's own tables."""
    model_bases: dict[str, frozenset[str]] = {
        str(m): frozenset(str(p) for p in providers) for m, providers in binding.MODEL_BASES.items()
    }
    builders = {str(m) for m in binding.MODEL_BUILDERS}
    listed = {str(m) for m in list_models_ids}
    if not set(model_bases) == builders == listed:
        raise SnapshotUnsupportedError(
            "registry_snapshot: unsupported(MODEL_BASES, MODEL_BUILDERS and list_models differ: "
            f"MODEL_BASES-only {sorted(set(model_bases) - builders)}, "
            f"MODEL_BUILDERS-only {sorted(builders - set(model_bases))}, "
            f"list_models-only {sorted(listed - builders)}, "
            f"not in list_models {sorted(builders - listed)})"
        )
    routes: list[dict[str, Any]] = []
    on_a_route: set[str] = set()
    for basis in binding.SELECTABLE_BASES:
        provider_id = str(basis.provider_id)
        ids = tuple(str(c) for c in basis.components)
        capabilities = binding.basis_provider(basis).describe()
        if capabilities.provider_id != provider_id or tuple(capabilities.components) != ids:
            raise SnapshotUnsupportedError(
                f"registry_snapshot: unsupported(basis {provider_id!r} {list(ids)}: its provider "
                f"describes {capabilities.provider_id!r} {list(capabilities.components)})"
            )
        line = PROVIDER_LINES.get(provider_id)
        if line is None:
            raise SnapshotUnsupportedError(
                f"registry_snapshot: unsupported(provider {provider_id!r}: no registered records "
                "and phases, W27-R63)"
            )
        every = sorted(PHASE_KINDS[str(p)] for p in capabilities.phases)
        records_path, phases = line(ids, every)
        model_ids = sorted(m for m, on in model_bases.items() if provider_id in on)
        on_a_route.update(model_ids)
        routes.append(
            {
                "provider_id": provider_id,
                "components": _component_rows(records_path, ids, phases),
                "model_ids": model_ids,
            }
        )
    on_no_route = sorted(set(model_bases) - on_a_route)
    if on_no_route:
        raise SnapshotUnsupportedError(
            f"registry_snapshot: unsupported(models on no selectable basis {on_no_route})"
        )
    return routes


def reading_for(binding: ModuleType, version: str) -> str:
    """W27-R63: the registered reading of this binder, or a refusal."""
    if hasattr(binding, "SELECTABLE_BASES") and hasattr(binding, "MODEL_BASES"):
        return "bases-v1"
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
    reading = reading_for(binding, version)
    document, digest = list_models_document()
    if reading == "bases-v1":
        routes = _routes_bases_v1(binding, [m["model_id"] for m in document["models"]])
    else:
        routes = _routes_0_1_1(binding)
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
