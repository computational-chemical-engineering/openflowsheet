"""Serialization of the `CompiledProblem` boundary types, and the rules a schema cannot express.

`docs/interfaces-frozen.md` §1 says canonical metadata is serializable while executable objects stay
runtime-local. This module is that boundary: dataclass in, JSON-ready document out, and back.

It lives beside `compiled.py` rather than inside it because `compiled.py` is frozen — its method
names, arity and return-type names are fixed — and a serializer is not part of that contract.

**Why `check_*` exists next to the schemas.** JSON Schema validates each field in isolation. Every
property that actually makes a CSC triple mean something is *cross-field*: that `indptr` has one
more entry than `col_ids`, that `indices` are valid rows, that rows ascend within a column, that
`values` is present exactly when the status is `ok`, that `row_accumulation` keys exactly
`equation_ids`. A document can satisfy all three schemas and still describe a matrix that does not
exist. These functions are what the round-trip fixtures run alongside the schema, the same way
`openflowsheet.units.check_quantity` runs alongside the P01 schemas.

They raise rather than return a bool: a caller that forgets to check a returned flag gets a silent
pass, which is the failure mode this whole module exists to prevent.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from openflowsheet.canonical import split_model_version, structure_sha256
from openflowsheet.compiled import (
    Capabilities,
    CompiledProblemMetadata,
    EvaluationResult,
    JacobianResult,
)


class DocumentError(ValueError):
    """A document is internally inconsistent in a way no JSON Schema can state."""


# -- encoding ---------------------------------------------------------------------------------


def metadata_to_document(metadata: CompiledProblemMetadata) -> dict[str, Any]:
    return {
        "model_version": metadata.model_version,
        "backend": metadata.backend,
        "backend_version": metadata.backend_version,
        "variable_ids": list(metadata.variable_ids),
        "equation_ids": list(metadata.equation_ids),
        "parameter_ids": list(metadata.parameter_ids),
        "column_scales": dict(metadata.column_scales),
        "row_scales": dict(metadata.row_scales),
        "row_accumulation": dict(metadata.row_accumulation),
        "capabilities": {
            "jacobian": metadata.capabilities.jacobian,
            "jvp": metadata.capabilities.jvp,
            "vjp": metadata.capabilities.vjp,
            "hessian": metadata.capabilities.hessian,
        },
        "constants_sha256": metadata.constants_sha256,
    }


def evaluation_result_to_document(result: EvaluationResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "values": None if result.values is None else list(result.values),
        "equation_ids": list(result.equation_ids),
        "phase_signature": result.phase_signature,
        "model_version": result.model_version,
        "constants_sha256": result.constants_sha256,
        "state_sha256": result.state_sha256,
        "counters": {block: dict(counts) for block, counts in result.counters.items()},
        "accuracy": result.accuracy,
        "message": result.message,
    }


def jacobian_result_to_document(result: JacobianResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "row_ids": list(result.row_ids),
        "col_ids": list(result.col_ids),
        "format": result.format,
        "indptr": list(result.indptr),
        "indices": list(result.indices),
        "data": list(result.data),
        # Redundant with `len(data)` on purpose: the P02 composition specification §10.4 emits it,
        # and a consumer handed four anonymous arrays needs one number it can check them against.
        # `check_jacobian_document` asserts the redundancy has not drifted.
        "nnz": result.nnz,
        "phase_signature": result.phase_signature,
        "model_version": result.model_version,
        "constants_sha256": result.constants_sha256,
        "state_sha256": result.state_sha256,
        "counters": {block: dict(counts) for block, counts in result.counters.items()},
        "pattern_provenance": result.pattern_provenance,
        "source_map": [dict(entry) for entry in result.source_map],
        "message": result.message,
    }


# -- decoding ---------------------------------------------------------------------------------


def metadata_from_document(document: Mapping[str, Any]) -> CompiledProblemMetadata:
    capabilities = document["capabilities"]
    return CompiledProblemMetadata(
        model_version=document["model_version"],
        backend=document["backend"],
        backend_version=document["backend_version"],
        variable_ids=tuple(document["variable_ids"]),
        equation_ids=tuple(document["equation_ids"]),
        parameter_ids=tuple(document["parameter_ids"]),
        column_scales=dict(document["column_scales"]),
        row_scales=dict(document["row_scales"]),
        row_accumulation=dict(document["row_accumulation"]),
        capabilities=Capabilities(
            jacobian=capabilities["jacobian"],
            jvp=capabilities["jvp"],
            vjp=capabilities["vjp"],
            hessian=capabilities["hessian"],
        ),
        constants_sha256=document["constants_sha256"],
    )


def evaluation_result_from_document(document: Mapping[str, Any]) -> EvaluationResult:
    values = document["values"]
    return EvaluationResult(
        status=document["status"],
        values=None if values is None else tuple(float(value) for value in values),
        equation_ids=tuple(document["equation_ids"]),
        phase_signature=document["phase_signature"],
        model_version=document["model_version"],
        constants_sha256=document["constants_sha256"],
        state_sha256=document["state_sha256"],
        counters={block: dict(counts) for block, counts in document["counters"].items()},
        accuracy=document["accuracy"],
        message=document["message"],
    )


def jacobian_result_from_document(document: Mapping[str, Any]) -> JacobianResult:
    return JacobianResult(
        status=document["status"],
        row_ids=tuple(document["row_ids"]),
        col_ids=tuple(document["col_ids"]),
        indptr=tuple(int(value) for value in document["indptr"]),
        indices=tuple(int(value) for value in document["indices"]),
        data=tuple(float(value) for value in document["data"]),
        phase_signature=document["phase_signature"],
        model_version=document["model_version"],
        constants_sha256=document["constants_sha256"],
        state_sha256=document["state_sha256"],
        counters={block: dict(counts) for block, counts in document["counters"].items()},
        pattern_provenance=document["pattern_provenance"],
        source_map=tuple(dict(entry) for entry in document["source_map"]),
        format=document["format"],
        message=document["message"],
    )


# -- the cross-field rules ----------------------------------------------------------------------


def check_metadata_document(document: Mapping[str, Any]) -> None:
    """Rules relating one field of a metadata document to another.

    Includes ADR 0002 D2.9: the structure digest inside `model_version` is **recomputed** from this
    document's own id lists and accumulation kinds, and a mismatch is refused. That is what makes
    the digest a check rather than a claim — a document can otherwise assert any structure it likes.
    """
    for key in ("variable_ids", "equation_ids", "parameter_ids"):
        names: Sequence[str] = document[key]
        if len(set(names)) != len(names):
            raise DocumentError(f"{key} contains duplicates; a later entry would shadow an earlier")

    equations = set(document["equation_ids"])
    variables = set(document["variable_ids"])

    accumulation = set(document["row_accumulation"])
    if accumulation != equations:
        raise DocumentError(
            "row_accumulation must have exactly one entry per equation id (ADR 0008 D4.4). "
            f"Missing {sorted(equations - accumulation)}; "
            f"unknown {sorted(accumulation - equations)}"
        )

    try:
        _, declared = split_model_version(document["model_version"])
    except ValueError as error:
        raise DocumentError(str(error)) from error
    recomputed = structure_sha256(
        document["variable_ids"],
        document["equation_ids"],
        document["parameter_ids"],
        document["row_accumulation"],
    )
    if declared != recomputed:
        raise DocumentError(
            "model_version's structure digest does not match this document's own structure "
            f"(ADR 0002 D2.9). Declared {declared}, recomputed {recomputed} from variable_ids, "
            "equation_ids, parameter_ids and row_accumulation."
        )

    for key, allowed, label in (
        ("column_scales", variables, "variable"),
        ("row_scales", equations, "equation"),
    ):
        unknown = sorted(set(document[key]) - allowed)
        if unknown:
            raise DocumentError(f"{key} names {unknown}, which are not {label} ids")
        for name, value in document[key].items():
            if not math.isfinite(value) or value <= 0.0:
                raise DocumentError(
                    f"{key}[{name!r}] is {value}; a scale divides, so a non-finite or "
                    "non-positive one is a division by zero or a silent sign flip"
                )


def check_evaluation_document(document: Mapping[str, Any]) -> None:
    """Rules relating status, values and the equation ordering."""
    values = document["values"]
    if document["status"] == "ok":
        if values is None:
            raise DocumentError("status is 'ok' but values is null")
        if len(values) != len(document["equation_ids"]):
            raise DocumentError(
                f"{len(values)} values for {len(document['equation_ids'])} equations"
            )
        non_finite = [
            equation
            for equation, value in zip(document["equation_ids"], values, strict=True)
            if not math.isfinite(value)
        ]
        if non_finite:
            raise DocumentError(
                f"status is 'ok' but {non_finite} are NaN or infinite. A decoded NaN satisfies "
                "`type: number`; it is not a residual this boundary may report as ok."
            )
    elif values is not None:
        raise DocumentError(
            f"status is {document['status']!r} but values is present. An unevaluated residual is "
            "absent, never a list of numbers a caller might use."
        )


def check_jacobian_document(document: Mapping[str, Any]) -> None:
    """The rules that make four anonymous integer arrays describe a matrix that exists."""
    indptr: Sequence[int] = document["indptr"]
    indices: Sequence[int] = document["indices"]
    data: Sequence[float] = document["data"]
    n_rows, n_columns = len(document["row_ids"]), len(document["col_ids"])

    if len(set(document["row_ids"])) != n_rows or len(set(document["col_ids"])) != n_columns:
        raise DocumentError("row_ids and col_ids must each be unique; identity travels by name")
    if len(indptr) != n_columns + 1:
        raise DocumentError(
            f"indptr has {len(indptr)} entries for {n_columns} columns; CSC needs one more than "
            "there are columns"
        )
    if indptr[0] != 0:
        raise DocumentError(f"indptr starts at {indptr[0]}, not 0")
    if list(indptr) != sorted(indptr):
        raise DocumentError("indptr is not non-decreasing")
    if not (len(indices) == len(data) == document["nnz"] == indptr[-1]):
        raise DocumentError(
            f"nnz disagreement: len(indices)={len(indices)}, len(data)={len(data)}, "
            f"nnz={document['nnz']}, indptr[-1]={indptr[-1]}"
        )

    out_of_range = sorted({index for index in indices if not 0 <= index < n_rows})
    if out_of_range:
        raise DocumentError(f"indices {out_of_range} are not rows of a {n_rows}-row matrix")

    for column in range(n_columns):
        rows = list(indices[indptr[column] : indptr[column + 1]])
        if rows != sorted(rows):
            raise DocumentError(
                f"column {column} ({document['col_ids'][column]!r}) lists rows out of ascending "
                "order; the canonical CSC ordering is column-major with rows ascending"
            )
        if len(set(rows)) != len(rows):
            raise DocumentError(f"column {column} stores the same row twice")

    if document["status"] == "ok":
        non_finite = [value for value in data if not math.isfinite(value)]
        if non_finite:
            raise DocumentError(f"status is 'ok' but {len(non_finite)} entries are NaN or infinite")
    elif data:
        raise DocumentError(f"status is {document['status']!r} but {len(data)} entries are present")


def check_pairing(evaluation: Mapping[str, Any], jacobian: Mapping[str, Any]) -> None:
    """A residual and a Jacobian claiming to describe the same function at the same state.

    `docs/interfaces-frozen.md` §1 and ADR 0008 D2.4. This is the check that catches the two being
    quietly taken from different states or different problems — the failure that makes a Newton
    step wrong in a way no single document reveals.
    """
    for field_name in ("model_version", "constants_sha256", "state_sha256", "phase_signature"):
        if evaluation[field_name] != jacobian[field_name]:
            raise DocumentError(
                f"{field_name} differs between the residual and the Jacobian: "
                f"{evaluation[field_name]!r} vs {jacobian[field_name]!r}"
            )
    if list(evaluation["equation_ids"]) != list(jacobian["row_ids"]):
        raise DocumentError("the residual's equation_ids and the Jacobian's row_ids differ")
