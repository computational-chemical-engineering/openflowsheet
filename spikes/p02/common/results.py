"""The result envelope both harnesses write (specification §10.4).

Defining the payload builders once is what makes the two backends comparable: the judge reads one
shape, and a difference between the routes is a difference in the numbers, never in the format.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from spikes.p02.common.export import CanonicalCsc, constants_sha256, state_sha256, write_json

RESULTS_ROOT: Final = Path(__file__).resolve().parents[1] / "results"

STATUS_OK: Final = "ok"
STATUS_INVALID_TRIAL_STATE: Final = "invalid_trial_state"
STATUS_UNSUPPORTED: Final = "unsupported"
STATUS_ERROR: Final = "error"


def metadata_payload(
    *,
    model_version: str,
    form: str,
    backend: str,
    backend_version: str,
    variable_ids: Sequence[str],
    equation_ids: Sequence[str],
    column_scales: Mapping[str, float],
    row_scales: Mapping[str, float],
    capabilities: Mapping[str, str],
    callback_blocks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """`CompiledProblemMetadata` as P02 uses it (specification §10.4)."""
    return {
        "model_version": model_version,
        "form": form,
        "backend": backend,
        "backend_version": backend_version,
        "variable_ids": list(variable_ids),
        "equation_ids": list(equation_ids),
        "column_scales": dict(column_scales),
        "row_scales": dict(row_scales),
        "capabilities": dict(capabilities),
        "constants_sha256": constants_sha256(),
        "callback_blocks": [dict(block) for block in callback_blocks],
    }


def residual_payload(
    *,
    status: str,
    model_version: str,
    x: Mapping[str, float],
    variable_ids: Sequence[str],
    equation_ids: Sequence[str],
    values: Sequence[float] | None,
    counters: Mapping[str, Mapping[str, int]],
    phase_signature: str | None,
    message: str = "",
) -> dict[str, Any]:
    """`EvaluationResult` (specification §10.4). `values` is in equation order, or None."""
    return {
        "status": status,
        "message": message,
        "phase_signature": phase_signature,
        "model_version": model_version,
        "constants_sha256": constants_sha256(),
        "state_sha256": state_sha256(x, variable_ids),
        "equation_ids": list(equation_ids),
        "values": None if values is None else [float(value) for value in values],
        "counters": {name: dict(counter) for name, counter in counters.items()},
        "accuracy": "exact-double",
    }


def jacobian_payload(
    *,
    status: str,
    model_version: str,
    x: Mapping[str, float],
    variable_ids: Sequence[str],
    matrix: CanonicalCsc | None,
    counters: Mapping[str, Mapping[str, int]],
    phase_signature: str | None,
    pattern_provenance: str,
    source_map: Sequence[Mapping[str, Any]] = (),
    raw_shape: Sequence[int] | None = None,
    raw_nnz: int | None = None,
    message: str = "",
) -> dict[str, Any]:
    """`JacobianResult` (specification §10.4)."""
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "phase_signature": phase_signature,
        "model_version": model_version,
        "constants_sha256": constants_sha256(),
        "state_sha256": state_sha256(x, variable_ids),
        "counters": {name: dict(counter) for name, counter in counters.items()},
        "accuracy": "exact-double",
        "pattern_provenance": pattern_provenance,
        "source_map": [dict(entry) for entry in source_map],
    }
    payload.update(
        matrix.as_dict()
        if matrix is not None
        else {
            "format": "csc",
            "row_ids": [],
            "col_ids": [],
            "indptr": [],
            "indices": [],
            "data": [],
            "nnz": 0,
        }
    )
    if raw_shape is not None:
        payload["raw_shape"] = list(raw_shape)
    if raw_nnz is not None:
        payload["raw_nnz"] = raw_nnz
    return payload


@dataclass
class ResultWriter:
    """Writes one backend's result set under `spikes/p02/results/<backend>/`."""

    backend: str
    root: Path = field(default_factory=lambda: RESULTS_ROOT)

    @property
    def directory(self) -> Path:
        return self.root / self.backend

    def write(self, name: str, payload: Any) -> Path:
        return write_json(self.directory / name, payload)

    def write_state(self, state_id: str, form: str, kind: str, payload: Any) -> Path:
        return write_json(self.directory / "states" / state_id / f"{kind}_{form}.json", payload)
