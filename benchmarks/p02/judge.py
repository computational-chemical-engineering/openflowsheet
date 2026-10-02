"""The P02 judge: one code path that evaluates the specification's assertions for any backend.

Specification: `docs/derivations/P02-composition-spec.md` §6 (assertion catalogue), §4 (pattern),
§8 (second-order recording rule), §11 (verdict rules). The harnesses under `spikes/p02/` only
produce artifacts; every comparison lives here, against `expected.py` and the 40-digit reference.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from benchmarks.p02 import expected as closed_form
from benchmarks.p02.reference import Reference, ReferenceState, load_reference

PASS = "pass"
FAIL = "fail"
UNSUPPORTED = "unsupported"
NOT_APPLICABLE = "not_applicable"

FD_OFFSETS = (-2, -1, 1, 2)
FD_WEIGHTS = (1.0, -8.0, 8.0, -1.0)  # fourth-order central 5-point first derivative
SOURCE_MAP_ENTRIES = (("eq_B", "lnK_B"), ("kdef_B", "T"), ("hdef_C", "l_C"))
#: Every state a form must have evaluated for its checks to mean anything. A loop that skips a
#: state whose status is not `ok` reports the worst of an empty list, which is zero, so coverage is
#: asserted before any deviation is compared.
REQUIRED_STATES = ("S1", "S2", "S3", "S4", "S5", "S6", "S1p")
#: States the block-level and directional records must cover (specification A04, A07, A15).
REQUIRED_FD_STATES = ("S1", "S2", "S3", "S4", "S5")
#: The out-of-domain probes (A17).
REQUIRED_PROBE_STATES = ("S7a", "S7b")

GENERIC_STATES = ("S1", "S2", "S5")
#: Nonzero floors for entries that vanish at S3/S4 (specification §4.2, A11 and A13). The inlined
#: form's floor is smaller because dlnK/dP is of order 1e-5 in this fixture; both are measured.
NONZERO_FLOOR = {"L": 1e-5, "I": 1e-6}
VANISHING_STATES = ("S3", "S4")
FD_STATES = ("S1", "S2", "S3", "S4", "S5")
#: A17: the failure message must name the variable and quote the offending value.
DOMAIN_PROBE_EXPECTATIONS = {
    "S7a": (r"\b(T|temperature)\b", "450"),
    "S7b": (r"\b(P|pressure)\b", "40000"),
}


@dataclass(frozen=True)
class Check:
    """One manifest `checks[]` entry (specification §6, §11.3)."""

    id: str
    result: str
    expected: str
    tolerance: str
    value: float | str | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "result": self.result,
            "expected": self.expected,
            "tolerance": self.tolerance,
            "value": self.value,
            "message": self.message,
        }


@dataclass
class _Artifacts:
    """The files one backend produced."""

    root: Path
    backend: str
    metadata: dict[str, Any] = field(default_factory=dict)
    residuals: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    jacobians: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    blocks: dict[str, Any] = field(default_factory=dict)
    directional_products: list[dict[str, Any]] = field(default_factory=list)
    directional_stencils: list[dict[str, Any]] = field(default_factory=list)
    second_order: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    raw_structure: dict[str, Any] = field(default_factory=dict)

    @property
    def forms(self) -> tuple[str, ...]:
        return tuple(sorted({form for _, form in self.jacobians}))


def _normalize_metadata(document: Mapping[str, Any]) -> dict[str, Any]:
    """Accept metadata keyed by form, or a single document that names its own form.

    A harness that compiles one form writes one document; a harness that compiles two writes a
    mapping. Normalizing here keeps one judge path instead of two.
    """
    if "form" in document and "model_version" in document:
        return {str(document["form"]): dict(document)}
    return {key: dict(value) for key, value in document.items() if isinstance(value, Mapping)}


def _normalize_second_order(document: Mapping[str, Any]) -> dict[str, Any]:
    """Accept either harness's second-order record, keeping the fields §8 requires.

    Absent records are left absent: the caller reports `unsupported`, never a pass.
    """
    if not document:
        return {}
    normalized: dict[str, Any] = {"opaque_blocks": [], "supplementary_symbolic_blocks": []}
    for source_key, target_key in (
        ("opaque_blocks", "opaque_blocks"),
        ("probes", "opaque_blocks"),
        ("supplementary_symbolic_blocks", "supplementary_symbolic_blocks"),
        ("H5", "supplementary_symbolic_blocks"),
    ):
        records = document.get(source_key)
        if isinstance(records, Mapping):
            records = [records]
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            normalized[target_key].append(
                {
                    "probe_id": record.get("probe_id") or record.get("probe") or "",
                    "status": record.get("status", ""),
                    "form": record.get("form", "L"),
                    "row": record.get("row") or record.get("lambda_row") or "",
                    "outcome": record.get("outcome", ""),
                    "entries": dict(record.get("entries") or record.get("values_returned") or {}),
                    "exception_type": record.get("exception_type", ""),
                    "message": record.get("message") or record.get("exception_message") or "",
                }
            )
    normalized["declared_hessian_capability"] = document.get("declared_hessian_capability")
    return normalized


def _read(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_artifacts(root: Path, backend: str) -> _Artifacts:
    """Read one backend's result directory."""
    directory = root / backend
    artifacts = _Artifacts(root=directory, backend=backend)
    artifacts.metadata = _normalize_metadata(_read(directory / "metadata.json") or {})
    artifacts.blocks = _read(directory / "block_records.json") or {}
    artifacts.directional_products = _read(directory / "directional_products.json") or []
    artifacts.directional_stencils = _read(directory / "directional_stencils.json") or []
    artifacts.second_order = _normalize_second_order(_read(directory / "second_order.json") or {})
    artifacts.counts = _read(directory / "callback_counts.json") or {}
    artifacts.environment = _read(directory / "environment.json") or {}
    artifacts.raw_structure = _read(directory / "raw_structure.json") or {}
    states_directory = directory / "states"
    if states_directory.exists():
        for state_directory in sorted(states_directory.iterdir()):
            for form in ("L", "I"):
                residual = _read(state_directory / f"residual_{form}.json")
                jacobian = _read(state_directory / f"jacobian_{form}.json")
                if residual is not None:
                    artifacts.residuals[(state_directory.name, form)] = residual
                if jacobian is not None:
                    artifacts.jacobians[(state_directory.name, form)] = jacobian
    return artifacts


# --- helpers -----------------------------------------------------------------------------------


def _entries(payload: Mapping[str, Any]) -> dict[str, float]:
    """The stored entries of an exported CSC, keyed `"<row>|<col>"`."""
    row_ids: list[str] = payload["row_ids"]
    col_ids: list[str] = payload["col_ids"]
    indptr: list[int] = payload["indptr"]
    indices: list[int] = payload["indices"]
    data: list[float] = payload["data"]
    result: dict[str, float] = {}
    for column, col_id in enumerate(col_ids):
        for k in range(indptr[column], indptr[column + 1]):
            result[f"{row_ids[indices[k]]}|{col_id}"] = float(data[k])
    return result


def _scale_ratio(key: str) -> float:
    row, col = key.split("|")
    return closed_form.ROW_SCALES[row] / closed_form.COLUMN_SCALES[col]


def _worst(
    items: Iterable[tuple[float, str]],
) -> tuple[float, str]:
    worst_value, worst_where = 0.0, ""
    for value, where in items:
        if value > worst_value:
            worst_value, worst_where = value, where
    return worst_value, worst_where


def _states_with_perturbed(reference: Reference) -> dict[str, ReferenceState]:
    """The registered states plus S1p, the perturbed state the linear-solve evidence uses.

    S1p carries S1's parameters and the perturbed vector from `linear_solve`. Without it the D03
    matrix is only ever checked for solve consistency and condition number, so a wrong non-affine
    entry there would meet no value assertion.
    """
    states = dict(reference.states)
    perturbed = reference.linear_solve.get("S1_perturbed_newton_step", {}).get("x_pert")
    if perturbed and "S1" in states:
        x_l = {key: float(value) for key, value in perturbed.items()}
        states["S1p"] = ReferenceState(
            state_id="S1p",
            purpose="perturbed Newton state for the linear-solve evidence (specification §9)",
            on_solution=False,
            oracle_phase_state=None,
            parameters=states["S1"].parameters,
            x_l=x_l,
            x_i={name: x_l[name] for name in closed_form.VARIABLE_IDS_I if name in x_l},
            residual_l={},
            residual_i={},
            jacobian_l={},
            jacobian_i={},
            numerically_zero_l=(),
            numerically_zero_i=(),
        )
    return states


def _expected_for(state: ReferenceState, form: str) -> tuple[dict[str, float], dict[str, float]]:
    if form == "L":
        return (
            closed_form.residual_l_form(state.x_l, state.parameters),
            closed_form.jacobian_l_form(state.x_l, state.parameters),
        )
    return (
        closed_form.residual_i_form(state.x_i, state.parameters),
        closed_form.jacobian_i_form(state.x_i, state.parameters),
    )


def _fd_derivative(samples: Sequence[float], step: float) -> float:
    return sum(weight * value for weight, value in zip(FD_WEIGHTS, samples, strict=True)) / (
        12.0 * step
    )


def _state_sha256(x: Mapping[str, float], order: Sequence[str]) -> str:
    """The specification §10.4 state hash, recomputed here rather than taken from the harness."""
    text = ",".join(f"{(0.0 if x[name] == 0.0 else x[name]):.17g}" for name in order)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coverage(
    artifacts: _Artifacts,
    form: str,
    required: Sequence[str],
    check_id: str,
    expected: str,
    tolerance: str,
) -> Check | None:
    """Return a failing or unsupported Check when a required state was not evaluated.

    Absent record: `unsupported` — the evidence was never produced. Present but not `ok`: `fail` —
    the backend was asked and could not answer, which is a composition failure, not a gap.
    """
    missing: list[str] = []
    not_ok: list[str] = []
    for state_id in required:
        payload = artifacts.jacobians.get((state_id, form))
        residual = artifacts.residuals.get((state_id, form))
        if payload is None and residual is None:
            missing.append(state_id)
        elif (payload is not None and payload.get("status") != "ok") or (
            residual is not None and residual.get("status") != "ok"
        ):
            not_ok.append(state_id)
    if not_ok:
        return Check(
            check_id,
            FAIL,
            expected,
            tolerance,
            len(not_ok),
            f"required states not evaluated: {', '.join(not_ok)}",
        )
    if missing:
        return Check(
            check_id,
            UNSUPPORTED,
            expected,
            tolerance,
            len(missing),
            f"no records for required states: {', '.join(missing)}",
        )
    return None


def _check(
    check_id: str, ok: bool, expected: str, tolerance: str, value: Any, message: str = ""
) -> Check:
    return Check(
        id=check_id,
        result=PASS if ok else FAIL,
        expected=expected,
        tolerance=tolerance,
        value=value,
        message=message,
    )


# --- assertions (specification §6) -------------------------------------------------------------


def check_a00() -> Check:
    """A00 — the judge's own closed forms reproduce the 40-digit reference."""
    reference = load_reference()
    deviations: list[tuple[float, str]] = []
    for state in reference.states.values():
        for form, (residual, jacobian), expected_pairs in (
            ("L", _expected_for(state, "L"), (state.residual_l, state.jacobian_l)),
            ("I", _expected_for(state, "I"), (state.residual_i, state.jacobian_i)),
        ):
            expected_residual, expected_jacobian = expected_pairs
            if set(residual) != set(expected_residual) or set(jacobian) != set(expected_jacobian):
                return _check(
                    "P02.A00.judge",
                    False,
                    "same keys",
                    "exact",
                    "key mismatch",
                    f"{state.state_id} {form}: key sets differ",
                )
            for key, value in expected_residual.items():
                tolerance = 1e-13 * (abs(value) + closed_form.ROW_SCALES[key])
                deviations.append(
                    (abs(residual[key] - value) / tolerance, f"{state.state_id} {form} r[{key}]")
                )
            for key, value in expected_jacobian.items():
                tolerance = 1e-13 * (abs(value) + _scale_ratio(key))
                deviations.append(
                    (abs(jacobian[key] - value) / tolerance, f"{state.state_id} {form} J[{key}]")
                )
    worst, where = _worst(deviations)
    return _check(
        "P02.A00.judge",
        worst <= 1.0,
        "expected.py == reference values",
        "1e-13 * (|E| + s_r/s_c)",
        worst,
        f"worst at {where} ({len(deviations)} values)",
    )


def check_a01(artifacts: _Artifacts, form: str) -> list[Check]:
    """A01 — identity maps are the specification's orderings, and the source map is by name."""
    variables = closed_form.VARIABLE_IDS_L if form == "L" else closed_form.VARIABLE_IDS_I
    equations = closed_form.EQUATION_IDS_L if form == "L" else closed_form.EQUATION_IDS_I
    problems: list[str] = []
    for (state_id, payload_form), payload in artifacts.jacobians.items():
        if payload_form != form or payload["status"] != "ok":
            continue
        if tuple(payload["col_ids"]) != tuple(variables):
            problems.append(f"{state_id}: col_ids differ from specification order")
        if tuple(payload["row_ids"]) != tuple(equations):
            problems.append(f"{state_id}: row_ids differ from specification order")
    source_map = artifacts.jacobians.get(("S1", form), {}).get("source_map", [])
    if form == "L":
        mapped = {(entry["row_id"], entry["col_id"]) for entry in source_map}
        if not set(SOURCE_MAP_ENTRIES) <= mapped:
            problems.append(f"S1: source map lacks {sorted(set(SOURCE_MAP_ENTRIES) - mapped)}")
        for entry in source_map:
            payload = artifacts.jacobians[("S1", form)]
            index = entry.get("csc_index")
            if index is None or not 0 <= index < len(payload["data"]):
                problems.append(f"S1: source map csc_index {index} outside the exported structure")
                continue
            column = max(
                position for position, start in enumerate(payload["indptr"][:-1]) if start <= index
            )
            row_id = payload["row_ids"][payload["indices"][index]]
            col_id = payload["col_ids"][column]
            if (row_id, col_id) != (entry["row_id"], entry["col_id"]):
                problems.append(
                    f"S1: source map entry {entry['row_id']}|{entry['col_id']} points at "
                    f"{row_id}|{col_id}"
                )
    return [
        _check(
            f"P02.A01.{artifacts.backend}.{form}",
            not problems,
            "identity maps equal the specification orderings; source map by name",
            "exact",
            len(problems),
            "; ".join(problems[:3]),
        )
    ]


def check_block_level(artifacts: _Artifacts) -> list[Check]:
    """A02, A05, A06 — the blocks' own declared Jacobians, read by (row, col)."""
    reference = load_reference()
    checks: list[Check] = []
    if not artifacts.blocks:
        return [
            Check(
                f"P02.A02.{artifacts.backend}",
                UNSUPPORTED,
                "block-level Jacobian export",
                "1e-13 relative",
                None,
                "block_records.json absent",
            ),
        ]
    k_deviations: list[tuple[float, str]] = []
    h_deviations: list[tuple[float, str]] = []
    pattern_problems: list[str] = []
    for state_id, record in artifacts.blocks.items():
        state = reference.states[state_id]
        temperature, pressure = state.x_l["T"], state.x_l["P"]
        flows = [state.x_l[f"l_{c}"] for c in closed_form.COMPONENTS]

        d_t = closed_form.d_ln_k_d_temperature(temperature, pressure)
        d_p = closed_form.d_ln_k_d_pressure(temperature, pressure)
        k_entries = record["blockK"]["jacobian_entries"]
        for i in range(3):
            for column, expected_value in ((0, d_t[i]), (1, d_p[i])):
                got = k_entries.get(f"{i}|{column}")
                if got is None:
                    pattern_problems.append(f"{state_id}: block K missing entry {i}|{column}")
                    continue
                k_deviations.append(
                    (
                        abs(got - expected_value) / (1e-13 * abs(expected_value)),
                        f"{state_id} K[{i},{column}]",
                    )
                )

        h_record = record["blockH"]
        expected_h_keys = {f"{i}|{column}" for i in range(3) for column in (i, 3, 4)}
        if set(h_record["jacobian_entries"]) != expected_h_keys:
            pattern_problems.append(
                f"{state_id}: block H pattern is {sorted(h_record['jacobian_entries'])}"
            )
        if h_record["jacobian_nnz"] != 9:
            pattern_problems.append(f"{state_id}: block H nnz {h_record['jacobian_nnz']} != 9")
        h_liquid = closed_form.h_liquid(temperature, pressure)
        h_row_scale = closed_form.ROW_SCALES["hdef_A"]
        for i in range(3):
            for key, expected_value, column_id in (
                (f"{i}|{i}", h_liquid[i], f"l_{closed_form.COMPONENTS[i]}"),
                (f"{i}|3", flows[i] * closed_form.C_P, "T"),
                (f"{i}|4", flows[i] * closed_form.V_MOLAR[i], "P"),
            ):
                got = h_record["jacobian_entries"].get(key)
                if got is None:
                    continue
                # Specification A06: 1e-14 x s_r/s_c of the corresponding hdef entry. A single flat
                # floor would be 1e-9 for every entry, which at the pressure column is 3e-5 in
                # relative terms and would accept 1e-10 where the closed form is exactly zero.
                tolerance = 1e-12 * abs(expected_value) + 1e-14 * (
                    h_row_scale / closed_form.COLUMN_SCALES[column_id]
                )
                h_deviations.append((abs(got - expected_value) / tolerance, f"{state_id} H[{key}]"))

    worst_k, where_k = _worst(k_deviations)
    worst_h, where_h = _worst(h_deviations)
    checks.append(
        _check(
            f"P02.A02.{artifacts.backend}",
            worst_k <= 1.0 and not pattern_problems,
            "block K Jacobian == closed form",
            "1e-13 relative",
            worst_k,
            f"worst at {where_k}",
        )
    )
    checks.append(
        _check(
            f"P02.A05.{artifacts.backend}",
            not pattern_problems,
            "block H declared pattern is exactly the 9 specified entries",
            "exact",
            len(pattern_problems),
            "; ".join(pattern_problems[:3]),
        )
    )
    checks.append(
        _check(
            f"P02.A06.{artifacts.backend}",
            worst_h <= 1.0,
            "block H Jacobian == closed form",
            "1e-12 relative + 1e-14 s_r/s_c",
            worst_h,
            f"worst at {where_h}",
        )
    )
    return checks


def check_a03(artifacts: _Artifacts) -> Check:
    """A03 — the S1 callback columns equal the independent P01 20-digit reference."""
    p01_path = Path(__file__).resolve().parents[1] / "syn001" / "reference_values.yaml"
    import yaml  # noqa: PLC0415

    with p01_path.open(encoding="utf-8") as handle:
        p01 = yaml.safe_load(handle)
    derivatives = p01["lnK_derivatives_at_360K_P_r"]
    payload = artifacts.jacobians.get(("S1", "L"))
    if payload is None or payload["status"] != "ok":
        return Check(
            f"P02.A03.{artifacts.backend}",
            UNSUPPORTED,
            "S1 L-form Jacobian",
            "1e-13 relative",
            None,
            "S1 jacobian absent",
        )
    entries = _entries(payload)
    deviations: list[tuple[float, str]] = []
    for i, component in enumerate(closed_form.COMPONENTS):
        for key, expected_value in (
            (f"kdef_{component}|T", -float(derivatives["dlnK_dT_per_K"][i])),
            (f"kdef_{component}|P", -float(derivatives["dlnK_dP_per_Pa"][i])),
        ):
            deviations.append(
                (abs(entries[key] - expected_value) / (1e-13 * abs(expected_value)), key)
            )
    worst, where = _worst(deviations)
    return _check(
        f"P02.A03.{artifacts.backend}",
        worst <= 1.0,
        "assembled kdef columns == P01 reference derivatives",
        "1e-13 relative",
        worst,
        f"worst at {where}",
    )


def check_finite_differences(artifacts: _Artifacts) -> list[Check]:
    """A04, A07 — the blocks' reported derivatives against a fourth-order difference.

    The stencil samples are the block values *as evaluated through the backend*; the difference
    is formed here so the harness never computes the check it is judged by.
    """
    if not artifacts.blocks:
        return [
            Check(
                f"P02.A04.{artifacts.backend}",
                UNSUPPORTED,
                "stencil samples",
                "1e-9 relative",
                None,
                "block_records.json absent",
            ),
            Check(
                f"P02.A07.{artifacts.backend}",
                UNSUPPORTED,
                "stencil samples",
                "1e-9 relative",
                None,
                "block_records.json absent",
            ),
        ]
    deviations: dict[str, list[tuple[float, str]]] = {"blockK": [], "blockH": []}
    for state_id, record in artifacts.blocks.items():
        for block_name, block in record.items():
            outputs = block["declared_shape"][0]
            for column, stencil in block["stencil"].items():
                step = float(stencil["step"][0])
                samples = stencil["samples"]
                for row in range(outputs):
                    ordered = [samples[position * outputs + row] for position in range(4)]
                    derivative = _fd_derivative(ordered, step)
                    reported = block["jacobian_entries"].get(f"{row}|{column}", 0.0)
                    denominator = max(abs(reported), 1e-30)
                    deviations[block_name].append(
                        (
                            abs(derivative - reported) / (1e-9 * denominator),
                            f"{state_id} {block_name}[{row}|{column}]",
                        )
                    )
    checks: list[Check] = []
    for block_name, check_id, floor in (
        ("blockK", "A04", "measured floors 5.0e-13 (T), 6.3e-12 (P)"),
        ("blockH", "A07", "measured floors 3.9e-15, 3.2e-13, 3.7e-13"),
    ):
        worst, where = _worst(deviations[block_name])
        checks.append(
            _check(
                f"P02.{check_id}.{artifacts.backend}",
                worst <= 1.0,
                f"{block_name} reported Jacobian == fourth-order difference",
                f"1e-9 relative ({floor})",
                worst,
                f"worst at {where}",
            )
        )
    return checks


def check_pattern(artifacts: _Artifacts, form: str) -> list[Check]:
    """A08, A09 — the assembled pattern, and its invariance across states."""
    expected_pattern = set(closed_form.PATTERN_L if form == "L" else closed_form.PATTERN_I)
    gap = _coverage(
        artifacts,
        form,
        REQUIRED_STATES,
        f"P02.A08.{artifacts.backend}.{form}",
        f"assembled pattern == specification ({len(expected_pattern)} entries) at every "
        "registered state",
        "exact",
    )
    if gap is not None:
        return [
            gap,
            Check(
                f"P02.A09.{artifacts.backend}.{form}",
                gap.result,
                "one canonical structure at every state",
                "exact",
                gap.value,
                gap.message,
            ),
        ]
    problems: list[str] = []
    provenance_problems: list[str] = []
    structures: dict[str, tuple[tuple[int, ...], tuple[int, ...]]] = {}
    for (state_id, payload_form), payload in sorted(artifacts.jacobians.items()):
        if payload_form != form or payload["status"] != "ok":
            continue
        entries = set(_entries(payload))
        extra = sorted(entries - expected_pattern)
        missing = sorted(expected_pattern - entries)
        if extra:
            problems.append(f"{state_id}: {len(extra)} entries outside the pattern ({extra[:3]})")
        if missing:
            problems.append(f"{state_id}: {len(missing)} pattern entries missing ({missing[:3]})")
        if payload.get("pattern_provenance") != "backend-declared":
            provenance_problems.append(f"{state_id}: {payload.get('pattern_provenance')}")
        structures[state_id] = (tuple(payload["indptr"]), tuple(payload["indices"]))
    distinct = {structure for structure in structures.values()}
    return [
        _check(
            f"P02.A08.{artifacts.backend}.{form}",
            not problems and not provenance_problems,
            f"assembled pattern == specification ({len(expected_pattern)} entries), "
            "provenance backend-declared",
            "exact",
            len(problems) + len(provenance_problems),
            "; ".join((problems + provenance_problems)[:3]),
        ),
        _check(
            f"P02.A09.{artifacts.backend}.{form}",
            len(distinct) <= 1,
            "one canonical structure at every state",
            "exact",
            len(distinct),
            f"{len(structures)} states compared",
        ),
    ]


def check_values(artifacts: _Artifacts, form: str) -> list[Check]:
    """A10, A11, A12 — assembled values, vanishing entries, and residuals."""
    reference = load_reference()
    gap = _coverage(
        artifacts,
        form,
        REQUIRED_STATES,
        f"P02.A10.{artifacts.backend}.{form}",
        "every assembled entry == closed form at every registered state",
        "1e-10 |E| + 1e-14 s_r/s_c",
    )
    if gap is not None:
        return [
            gap,
            Check(
                f"P02.A11.{artifacts.backend}.{form}",
                gap.result,
                "vanishing entries stored and exactly 0.0",
                "exact zero",
                gap.value,
                gap.message,
            ),
            Check(
                f"P02.A12.{artifacts.backend}.{form}",
                gap.result,
                "residual == closed form",
                "1e-12 (s_r + |E|)",
                gap.value,
                gap.message,
            ),
        ]
    states = _states_with_perturbed(reference)
    value_deviations: list[tuple[float, str]] = []
    residual_deviations: list[tuple[float, str]] = []
    vanishing_problems: list[str] = []
    nonzero_problems: list[str] = []

    for (state_id, payload_form), payload in sorted(artifacts.jacobians.items()):
        if payload_form != form or payload["status"] != "ok" or state_id not in states:
            continue
        state = states[state_id]
        expected_residual, expected_jacobian = _expected_for(state, form)
        entries = _entries(payload)
        for key, expected_value in expected_jacobian.items():
            tolerance = 1e-10 * abs(expected_value) + 1e-14 * _scale_ratio(key)
            value_deviations.append(
                (abs(entries[key] - expected_value) / tolerance, f"{state_id} {key}")
            )
        vanishing = set(state.numerically_zero_l if form == "L" else state.numerically_zero_i)
        if state_id in VANISHING_STATES:
            for key in vanishing:
                if key not in entries:
                    vanishing_problems.append(f"{state_id}: {key} not stored")
                elif entries[key] != 0.0:
                    vanishing_problems.append(f"{state_id}: {key} = {entries[key]!r}, not 0.0")
        generic = GENERIC_STATES + (("S6",) if form == "I" else ())
        if state_id in generic:
            for other in VANISHING_STATES:
                for key in (
                    reference.states[other].numerically_zero_l
                    if form == "L"
                    else reference.states[other].numerically_zero_i
                ):
                    floor = NONZERO_FLOOR[form]
                    if abs(entries.get(key, 0.0)) < floor:
                        nonzero_problems.append(
                            f"{state_id}: {key} = {entries.get(key)!r} below the {floor:g} floor"
                        )
        residual_payload = artifacts.residuals.get((state_id, form))
        if residual_payload and residual_payload["status"] == "ok":
            values = dict(
                zip(residual_payload["equation_ids"], residual_payload["values"], strict=True)
            )
            for key, expected_value in expected_residual.items():
                scale = closed_form.ROW_SCALES[key]
                if state.on_solution:
                    tolerance = 1e-12 * scale
                else:
                    tolerance = 1e-12 * (scale + abs(expected_value))
                residual_deviations.append(
                    (abs(values[key] - expected_value) / tolerance, f"{state_id} {key}")
                )

    worst_value, where_value = _worst(value_deviations)
    worst_residual, where_residual = _worst(residual_deviations)
    return [
        _check(
            f"P02.A10.{artifacts.backend}.{form}",
            worst_value <= 1.0,
            "every assembled entry == closed form",
            "1e-10 |E| + 1e-14 s_r/s_c",
            worst_value,
            f"worst at {where_value} ({len(value_deviations)} entries)",
        ),
        _check(
            f"P02.A11.{artifacts.backend}.{form}",
            not vanishing_problems and not nonzero_problems,
            "vanishing entries stored and exactly 0.0; the same entries nonzero elsewhere",
            "exact zero / >= 1e-5",
            len(vanishing_problems) + len(nonzero_problems),
            "; ".join((vanishing_problems + nonzero_problems)[:3]),
        ),
        _check(
            f"P02.A12.{artifacts.backend}.{form}",
            worst_residual <= 1.0,
            "residual == closed form",
            "1e-12 (s_r + |E|)",
            worst_residual,
            f"worst at {where_residual}",
        ),
    ]


def _lifted_consistent_states() -> tuple[str, ...]:
    """The states at which A14 applies (specification §6 A14, amended).

    The Schur identity is the chain rule for `x -> r_R(x, y(x))` with `y(x)` solving the defining
    rows, so it holds only where the registered lifted values satisfy them. The reference records
    which states those are.
    """
    record = load_reference().raw.get("schur_identity_check", {})
    consistent = tuple(
        state_id
        for state_id, entry in record.items()
        if isinstance(entry, Mapping) and entry.get("lifted_consistent")
    )
    return consistent or ("S1", "S2", "S3", "S4")


def check_schur(artifacts: _Artifacts) -> Check:
    """A14 — at the lifted-consistent states, eliminating the lifted variables gives the I-form."""
    reference = load_reference()
    applicable = _lifted_consistent_states()
    gap = _coverage(
        artifacts,
        "L",
        applicable,
        f"P02.A14.{artifacts.backend}",
        f"Schur elimination == inlined closed form at {', '.join(applicable)}",
        "1e-10 |E| + 1e-14 s_r/s_c",
    )
    if gap is not None:
        return gap
    lifted = tuple(f"lnK_{c}" for c in closed_form.COMPONENTS) + tuple(
        f"hL_{c}" for c in closed_form.COMPONENTS
    )
    defining = tuple(f"kdef_{c}" for c in closed_form.COMPONENTS) + tuple(
        f"hdef_{c}" for c in closed_form.COMPONENTS
    )
    inline_rows = closed_form.EQUATION_IDS_I
    inline_columns = closed_form.VARIABLE_IDS_I
    deviations: list[tuple[float, str]] = []
    for (state_id, form), payload in sorted(artifacts.jacobians.items()):
        if form != "L" or payload["status"] != "ok" or state_id not in reference.states:
            continue
        if state_id not in applicable:
            continue
        entries = _entries(payload)

        def block(
            rows: Sequence[str], columns: Sequence[str], values: dict[str, float] = entries
        ) -> npt.NDArray[np.float64]:
            return np.array(
                [[values.get(f"{row}|{column}", 0.0) for column in columns] for row in rows],
                dtype=np.float64,
            )

        reduced = block(inline_rows, inline_columns) - block(inline_rows, lifted) @ block(
            defining, inline_columns
        )
        state = reference.states[state_id]
        _, expected_inline = _expected_for(state, "I")
        for row_index, row in enumerate(inline_rows):
            for column_index, column in enumerate(inline_columns):
                key = f"{row}|{column}"
                expected_value = expected_inline.get(key, 0.0)
                tolerance = 1e-10 * abs(expected_value) + 1e-14 * (
                    closed_form.ROW_SCALES[row] / closed_form.COLUMN_SCALES[column]
                )
                deviations.append(
                    (
                        abs(reduced[row_index, column_index] - expected_value) / tolerance,
                        f"{state_id} {key}",
                    )
                )
    worst, where = _worst(deviations)
    return _check(
        f"P02.A14.{artifacts.backend}",
        worst <= 1.0,
        "Schur elimination of the lifted variables == inlined closed form",
        "1e-10 |E| + 1e-14 s_r/s_c",
        worst,
        f"worst at {where}",
    )


def check_directional(artifacts: _Artifacts, form: str) -> list[Check]:
    """A15, A16 — the directional derivative, and the forward/reverse identity."""
    reference = load_reference()
    checks: list[Check] = []
    deviations: list[tuple[float, str]] = []
    input_problems: list[str] = []
    for record in artifacts.directional_stencils:
        if record["form"] != form:
            continue
        registered_direction = reference.directions.get(f"u_{form}")
        if registered_direction is not None and tuple(
            float(value) for value in record.get("direction", ())
        ) != tuple(registered_direction):
            input_problems.append(f"{record['state_id']}: direction is not the registered u_{form}")
        variables = closed_form.VARIABLE_IDS_L if form == "L" else closed_form.VARIABLE_IDS_I
        if tuple(float(value) for value in record.get("column_scales", ())) != tuple(
            closed_form.COLUMN_SCALES[name] for name in variables
        ):
            input_problems.append(
                f"{record['state_id']}: column scales are not the registered ones"
            )
        if float(record.get("epsilon", 0.0)) != 1e-3:
            input_problems.append(f"{record['state_id']}: epsilon is {record.get('epsilon')!r}")
        state = reference.states[record["state_id"]]
        _, expected_jacobian = _expected_for(state, form)
        variables = closed_form.VARIABLE_IDS_L if form == "L" else closed_form.VARIABLE_IDS_I
        equations = closed_form.EQUATION_IDS_L if form == "L" else closed_form.EQUATION_IDS_I
        step = float(record["epsilon"])
        direction = record["direction"]
        scales = record["column_scales"]
        for row_index, row in enumerate(equations):
            samples = [record["samples"][str(offset)][row_index] for offset in FD_OFFSETS]
            derivative = _fd_derivative(samples, step)
            exact = sum(
                expected_jacobian.get(f"{row}|{column}", 0.0) * scales[index] * direction[index]
                for index, column in enumerate(variables)
            )
            tolerance = 1e-9 * (closed_form.ROW_SCALES[row] + abs(exact))
            deviations.append((abs(derivative - exact) / tolerance, f"{record['state_id']} {row}"))
    worst, where = _worst(deviations)
    if input_problems:
        checks.append(
            Check(
                f"P02.A15.{artifacts.backend}.{form}",
                FAIL,
                "the stencil uses the registered direction, scales and step",
                "exact",
                len(input_problems),
                "; ".join(input_problems[:3]),
            )
        )
    elif not deviations:
        checks.append(
            Check(
                f"P02.A15.{artifacts.backend}.{form}",
                UNSUPPORTED,
                "fourth-order directional difference == J D_c u",
                "1e-9 (s_r + |exact|)",
                None,
                "no directional stencil records for this form",
            )
        )
    else:
        checks.append(
            _check(
                f"P02.A15.{artifacts.backend}.{form}",
                worst <= 1.0,
                "fourth-order directional difference == J D_c u",
                "1e-9 (s_r + |exact|)",
                worst,
                f"worst at {where} ({len(deviations)} rows)",
            )
        )

    capabilities = artifacts.metadata.get(form, {}).get("capabilities", {})
    products = [record for record in artifacts.directional_products if record["form"] == form]
    variables = closed_form.VARIABLE_IDS_L if form == "L" else closed_form.VARIABLE_IDS_I
    equations = closed_form.EQUATION_IDS_L if form == "L" else closed_form.EQUATION_IDS_I
    direction_u = reference.directions.get(f"u_{form}")
    direction_v = reference.directions.get(f"v_{form}")

    if capabilities.get("jvp") == "exact" and capabilities.get("vjp") == "exact" and products:
        # The judge recomputes the products from the exported matrix and the registered
        # directions, rather than trusting the scalars the harness computed about itself.
        deviations_product: list[tuple[float, str]] = []
        identity_deviations: list[tuple[float, str]] = []
        for record in products:
            payload = artifacts.jacobians.get((record["state_id"], form))
            if payload is None or payload["status"] != "ok" or not direction_u or not direction_v:
                continue
            entries = _entries(payload)
            matrix = np.array(
                [
                    [entries.get(f"{row}|{column}", 0.0) for column in variables]
                    for row in equations
                ],
                dtype=np.float64,
            )
            u = np.array(direction_u, dtype=np.float64)
            v = np.array(direction_v, dtype=np.float64)
            forward = matrix @ u
            reverse = matrix.T @ v
            reported_forward = np.array(record.get("jvp", []), dtype=np.float64)
            reported_reverse = np.array(record.get("vjp", []), dtype=np.float64)
            if reported_forward.shape == forward.shape:
                scale = np.abs(matrix) @ np.abs(u)
                worst_row = float(
                    np.max(np.abs(reported_forward - forward) / (1e-12 * scale + 1e-300))
                )
                deviations_product.append((worst_row, f"{record['state_id']} jvp"))
            if reported_reverse.shape == reverse.shape:
                scale = np.abs(matrix).T @ np.abs(v)
                worst_row = float(
                    np.max(np.abs(reported_reverse - reverse) / (1e-12 * scale + 1e-300))
                )
                deviations_product.append((worst_row, f"{record['state_id']} vjp"))
            left = float(v @ reported_forward) if reported_forward.size else float(v @ forward)
            right = float(reported_reverse @ u) if reported_reverse.size else float(reverse @ u)
            bound = float(np.abs(v) @ np.abs(matrix) @ np.abs(u))
            identity_deviations.append(
                (abs(left - right) / (1e-12 * bound + 1e-300), record["state_id"])
            )
        worst_product, where_product = _worst(deviations_product)
        worst_identity, where_identity = _worst(identity_deviations)
        if not deviations_product:
            checks.append(
                Check(
                    f"P02.A16.{artifacts.backend}.{form}",
                    UNSUPPORTED,
                    "exported products == the assembled matrix applied to the registered "
                    "directions",
                    "1e-12 sum |J_rj u_j|",
                    None,
                    "no comparable product records",
                )
            )
        else:
            checks.append(
                _check(
                    f"P02.A16.{artifacts.backend}.{form}",
                    worst_product <= 1.0 and worst_identity <= 1.0,
                    "exported forward and reverse products equal the assembled matrix applied to "
                    "the registered directions, and v^T(Ju) == (J^T v)^T u",
                    "1e-12 sum |J_rj u_j|",
                    max(worst_product, worst_identity),
                    f"worst product at {where_product}, worst identity at {where_identity}",
                )
            )
    else:
        checks.append(
            Check(
                f"P02.A16.{artifacts.backend}.{form}",
                NOT_APPLICABLE,
                "jvp/vjp declared exact",
                "1e-12",
                None,
                f"capabilities: jvp={capabilities.get('jvp')}, vjp={capabilities.get('vjp')}",
            )
        )
    return checks


def check_domain_and_counts(artifacts: _Artifacts, form: str) -> list[Check]:
    """A17, A18 — typed domain failures, and the callback-count thresholds."""
    missing_probes = [
        state_id
        for state_id in REQUIRED_PROBE_STATES
        if (state_id, form) not in artifacts.residuals
        and (state_id, form) not in artifacts.jacobians
    ]
    if missing_probes:
        gap = Check(
            f"P02.A17.{artifacts.backend}.{form}",
            UNSUPPORTED,
            "out-of-domain probes evaluated",
            "exact",
            len(missing_probes),
            f"no records for {', '.join(missing_probes)}",
        )
        return [
            gap,
            Check(
                f"P02.A18.{artifacts.backend}.{form}",
                UNSUPPORTED,
                "callback counts",
                "exact",
                None,
                gap.message,
            ),
        ]
    count_gap = _coverage(
        artifacts,
        form,
        REQUIRED_STATES,
        f"P02.A18.{artifacts.backend}.{form}",
        "one value call per residual and one Jacobian call per Jacobian at every registered state",
        "exact",
    )
    problems: list[str] = []
    for state_id in ("S7a", "S7b"):
        for kind, payloads in (
            ("residual", artifacts.residuals),
            ("jacobian", artifacts.jacobians),
        ):
            payload = payloads.get((state_id, form))
            if payload is None:
                problems.append(f"{state_id}: no {kind} record")
                continue
            if payload["status"] != "invalid_trial_state":
                problems.append(f"{state_id}: {kind} status {payload['status']}")
            message = payload.get("message", "")
            pattern, value = DOMAIN_PROBE_EXPECTATIONS[state_id]
            if not re.search(pattern, message):
                problems.append(f"{state_id}: {kind} message does not name the variable")
            if value not in message:
                problems.append(f"{state_id}: {kind} message does not give the offending value")
            if kind == "residual" and payload.get("values") is not None:
                problems.append(f"{state_id}: residual returned numbers with a failure status")
            if kind == "jacobian" and payload.get("nnz"):
                problems.append(f"{state_id}: jacobian returned entries with a failure status")
    for state_id in REQUIRED_PROBE_STATES:
        for kind, payloads in (
            ("residual", artifacts.residuals),
            ("jacobian", artifacts.jacobians),
        ):
            payload = payloads.get((state_id, form))
            if payload is None:
                continue
            calls = sum(
                counter.get("value_calls", 0) + counter.get("jacobian_calls", 0)
                for counter in payload.get("counters", {}).values()
            )
            if calls != 1:
                problems.append(
                    f"{state_id}: {kind} recorded {calls} block calls, expected exactly one — "
                    "the failing block should stop the evaluation"
                )
    for state_id in ("S6",):
        payload = artifacts.residuals.get((state_id, form))
        if payload is not None and payload["status"] != "ok":
            problems.append(f"{state_id}: boundary state rejected ({payload['status']})")

    count_problems: list[str] = []
    thresholds = {"blockK": 3, "blockH": 6}
    for (state_id, payload_form), payload in artifacts.residuals.items():
        if payload_form != form or payload["status"] != "ok":
            continue
        for block, counters in payload["counters"].items():
            if counters["value_calls"] != 1:
                count_problems.append(
                    f"{state_id} residual {block}: {counters['value_calls']} value calls"
                )
            if counters["jacobian_calls"] != 0:
                count_problems.append(
                    f"{state_id} residual {block}: {counters['jacobian_calls']} jacobian calls"
                )
    for (state_id, payload_form), payload in artifacts.jacobians.items():
        if payload_form != form or payload["status"] != "ok":
            continue
        for block, counters in payload["counters"].items():
            if counters["jacobian_calls"] != 1:
                count_problems.append(
                    f"{state_id} jacobian {block}: {counters['jacobian_calls']} jacobian calls"
                )
            if counters["value_calls"] > 1:
                count_problems.append(
                    f"{state_id} jacobian {block}: {counters['value_calls']} value calls"
                )
            if counters["value_calls"] >= thresholds.get(block, 3):
                count_problems.append(
                    f"{state_id} jacobian {block}: finite-difference fallback suspected "
                    f"({counters['value_calls']} value calls)"
                )
    return [
        _check(
            f"P02.A17.{artifacts.backend}.{form}",
            not problems,
            "out-of-domain states return invalid_trial_state with no numbers; "
            "the boundary state succeeds",
            "exact",
            len(problems),
            "; ".join(problems[:3]),
        ),
        count_gap
        or _check(
            f"P02.A18.{artifacts.backend}.{form}",
            not count_problems,
            "one value call per residual, one Jacobian call per Jacobian, no FD fallback",
            "exact",
            len(count_problems),
            "; ".join(count_problems[:3]),
        ),
    ]


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "spikes" / "p02" / "schemas-draft"
DRAFT_SCHEMAS = {
    "metadata": "compiled-problem-metadata.draft.schema.json",
    "residual": "evaluation-result.draft.schema.json",
    "jacobian": "jacobian-result.draft.schema.json",
}


def check_schema_conformance(artifacts: _Artifacts, form: str) -> Check:
    """A20 (schema half) — every emitted document validates against its draft schema.

    The schemas are drafts under `spikes/p02/schemas-draft/` on purpose: `interfaces-frozen.md`
    freezes a field set when the schema is first delivered under `schemas/`, and the P02 envelope
    is deliberately minimal (specification §10.4, open question Q5, K01 promotes them).
    """
    import jsonschema  # noqa: PLC0415

    schemas = {}
    for kind, filename in DRAFT_SCHEMAS.items():
        path = SCHEMA_ROOT / filename
        if not path.exists():
            return Check(
                f"P02.A20.schema.{artifacts.backend}.{form}",
                UNSUPPORTED,
                "draft schemas present",
                "draft 2020-12",
                None,
                f"{path} absent",
            )
        with path.open(encoding="utf-8") as handle:
            schemas[kind] = json.load(handle)

    problems: list[str] = []
    documents: list[tuple[str, str, Any]] = []
    if form in artifacts.metadata:
        documents.append(("metadata", form, artifacts.metadata[form]))
    for (state_id, payload_form), payload in artifacts.residuals.items():
        if payload_form == form:
            documents.append(("residual", state_id, payload))
    for (state_id, payload_form), payload in artifacts.jacobians.items():
        if payload_form == form:
            documents.append(("jacobian", state_id, payload))
    for kind, label, document in documents:
        try:
            jsonschema.validate(document, schemas[kind])
        except jsonschema.ValidationError as error:
            problems.append(f"{kind} {label}: {error.message[:120]}")
    return _check(
        f"P02.A20.schema.{artifacts.backend}.{form}",
        not problems,
        f"{len(documents)} documents validate against the draft schemas",
        "JSON Schema draft 2020-12",
        len(problems),
        "; ".join(problems[:3]),
    )


def check_envelope(artifacts: _Artifacts, form: str) -> list[Check]:
    """A19, A20 — capability consistency and the result envelope."""
    metadata = artifacts.metadata.get(form, {})
    capabilities = metadata.get("capabilities", {})
    problems: list[str] = []
    if capabilities.get("jacobian") != "exact_sparse_csc":
        problems.append(f"jacobian capability {capabilities.get('jacobian')!r}")
    if capabilities.get("hessian") not in {"exact", "absent"}:
        problems.append(f"hessian capability {capabilities.get('hessian')!r}")
    second_order = artifacts.second_order.get("opaque_blocks", [])
    if capabilities.get("hessian") == "absent" and any(
        record.get("outcome") == "returned" for record in second_order
    ):
        problems.append("hessian declared absent but the probe returned numbers")
    if capabilities.get("hessian") == "exact" and any(
        record.get("outcome") == "raised" for record in second_order
    ):
        problems.append("hessian declared exact but the probe raised")

    reference = load_reference()
    states = _states_with_perturbed(reference)
    variables = closed_form.VARIABLE_IDS_L if form == "L" else closed_form.VARIABLE_IDS_I
    envelope_problems: list[str] = []
    required_residual = {
        "status",
        "phase_signature",
        "model_version",
        "constants_sha256",
        "state_sha256",
        "counters",
        "accuracy",
    }
    required_jacobian = required_residual | {
        "format",
        "row_ids",
        "col_ids",
        "indptr",
        "indices",
        "data",
        "nnz",
        "pattern_provenance",
        "source_map",
    }
    for (state_id, payload_form), payload in artifacts.residuals.items():
        if payload_form != form:
            continue
        missing = required_residual - set(payload)
        if missing:
            envelope_problems.append(f"{state_id} residual missing {sorted(missing)}")
        jacobian = artifacts.jacobians.get((state_id, form))
        if jacobian is None:
            envelope_problems.append(f"{state_id}: no jacobian record")
            continue
        missing = required_jacobian - set(jacobian)
        if missing:
            envelope_problems.append(f"{state_id} jacobian missing {sorted(missing)}")
        if jacobian.get("state_sha256") != payload.get("state_sha256"):
            envelope_problems.append(
                f"{state_id}: state hashes differ between residual and jacobian"
            )
        if jacobian.get("model_version") != payload.get("model_version"):
            envelope_problems.append(f"{state_id}: model versions differ")
        state = states.get(state_id)
        if state is not None:
            x = state.x_l if form == "L" else state.x_i
            if all(name in x for name in variables):
                recomputed = _state_sha256(x, variables)
                if payload.get("state_sha256") != recomputed:
                    envelope_problems.append(
                        f"{state_id}: state hash does not match the specification §10.4 hash of x"
                    )
            if payload.get("phase_signature") != state.oracle_phase_state:
                envelope_problems.append(
                    f"{state_id}: phase signature {payload.get('phase_signature')!r} is not the "
                    f"registered {state.oracle_phase_state!r}"
                )
    return [
        _check(
            f"P02.A19.{artifacts.backend}.{form}",
            not problems,
            "declared capabilities agree with every probe outcome",
            "exact",
            len(problems),
            "; ".join(problems[:3]),
        ),
        _check(
            f"P02.A20.{artifacts.backend}.{form}",
            not envelope_problems,
            "envelope fields present; residual and Jacobian share state hash and version",
            "exact",
            len(envelope_problems),
            "; ".join(envelope_problems[:3]),
        ),
    ]


def check_second_order(artifacts: _Artifacts) -> Check:
    """A22 — every probed entry is exact, absent, or fabricated; any fabrication fails."""
    reference = load_reference()
    expectations = reference.second_order
    metadata_hessian = {
        form: artifacts.metadata.get(form, {}).get("capabilities", {}).get("hessian")
        for form in artifacts.forms
    }
    classifications: list[str] = []
    problems: list[str] = []
    recorded = artifacts.second_order.get("opaque_blocks", [])
    probes = [record for record in recorded if record.get("status") != NOT_APPLICABLE]
    if not probes:
        return Check(
            f"P02.A22.{artifacts.backend}",
            UNSUPPORTED,
            "every probed entry is exact or absent; none fabricated",
            "1e-10 |E| + 1e-14",
            None,
            "no second-order probe records",
        )
    required_probes = {"H1", "H2", "H3"} | ({"H4"} if "I" in artifacts.forms else set())
    missing_probes = sorted(required_probes - {record.get("probe_id") for record in recorded})
    if missing_probes:
        problems.append(f"no record for probes {', '.join(missing_probes)}")
    for record in probes:
        outcome = record.get("outcome")
        if outcome not in {"raised", "returned"}:
            problems.append(
                f"{record['probe_id']}: outcome {outcome!r} is neither raised nor returned"
            )
            classifications.append(f"{record['probe_id']}=unclassifiable")
            continue
        if outcome == "returned" and not record.get("entries"):
            problems.append(f"{record['probe_id']}: returned numbers but recorded no entries")
            classifications.append(f"{record['probe_id']}=unclassifiable")
            continue
        if outcome == "raised":
            if metadata_hessian.get(record["form"]) != "absent":
                problems.append(
                    f"{record['probe_id']}: raised but metadata declares "
                    f"{metadata_hessian.get(record['form'])!r}"
                )
            classifications.append(f"{record['probe_id']}=absent")
            continue
        for name, value in record.get("entries", {}).items():
            expected_value = _second_order_expectation(expectations, record["probe_id"], name)
            if expected_value is None:
                problems.append(f"{record['probe_id']} {name}: no registered expectation")
                continue
            tolerance = 1e-10 * abs(expected_value) + 1e-14
            if abs(value - expected_value) <= tolerance:
                classifications.append(f"{record['probe_id']}.{name}=exact")
            else:
                classifications.append(f"{record['probe_id']}.{name}=fabricated")
                problems.append(
                    f"{record['probe_id']} {name}: {value!r} != {expected_value!r} (fabricated)"
                )
    return _check(
        f"P02.A22.{artifacts.backend}",
        not problems,
        "every probed entry is exact or absent; none fabricated",
        "1e-10 |E| + 1e-14",
        "; ".join(classifications[:4]),
        "; ".join(problems[:3]),
    )


#: Registered second-order expectations, keyed (probe id, harness entry name) -> reference key.
SECOND_ORDER_KEYS: dict[tuple[str, str], tuple[str, str]] = {
    ("H1", "d2/dv_AdL"): ("algebraic_only", "d2 eq_A / d v_A d L"),
    ("H1", "d2/dlnK_AdlnK_A"): ("algebraic_only", "d2 eq_A / d lnK_A^2"),
    ("H2", "d2/dTdT"): ("callback_boundary", "d2 kdef_A / dT^2"),
    ("H2", "d2/dTdP"): ("callback_boundary", "d2 kdef_A / dT dP"),
    ("H2", "d2/dPdP"): ("callback_boundary", "d2 kdef_A / dP^2"),
    ("H3", "d2/dl_AdT"): ("callback_boundary", "d2 hdef_A / d l_A dT"),
    ("H3", "d2/dl_AdP"): ("callback_boundary", "d2 hdef_A / d l_A dP"),
    ("H4", "d2/dTdl_A"): ("I_form_mixed_via_first_derivative_only", "d2 eq_A / dT d l_A"),
    ("H4", "d2/dTdT"): ("I_form_pure_callback_second_order", "d2 eq_A / dT^2"),
}


def _second_order_expectation(
    expectations: Mapping[str, Any], probe_id: str, entry_name: str
) -> float | None:
    """The registered closed-form value for one probed second-order entry (specification §8)."""
    address = SECOND_ORDER_KEYS.get((probe_id, entry_name))
    if address is None:
        return None
    section, key = address
    block = expectations.get(section)
    if not isinstance(block, Mapping) or key not in block:
        return None
    return float(block[key])


def classify_supplementary(artifacts: _Artifacts) -> Check:
    """H5 — the supplementary record: what second order does with a symbolic block Jacobian.

    This is a capability fact for K01, never mixed with H1-H4 and never part of the verdict.
    """
    records = artifacts.second_order.get("supplementary_symbolic_blocks", [])
    if not records:
        return Check(
            f"P02.H5.{artifacts.backend}",
            NOT_APPLICABLE,
            "supplementary symbolic-Jacobian probe",
            "1e-10 |E| + 1e-14",
            None,
            "not recorded",
        )
    expectations = load_reference().second_order
    outcomes: list[str] = []
    for record in records:
        if record.get("status") == NOT_APPLICABLE:
            outcomes.append(f"{record['probe_id']}=not_applicable")
            continue
        if record.get("outcome") == "raised":
            outcomes.append(f"{record['probe_id']}=absent")
            continue
        for name, value in record.get("entries", {}).items():
            expected_value = _second_order_expectation(expectations, record["probe_id"], name)
            if expected_value is None:
                outcomes.append(f"{record['probe_id']}.{name}=unregistered")
            elif abs(value - expected_value) <= 1e-10 * abs(expected_value) + 1e-14:
                outcomes.append(f"{record['probe_id']}.{name}=exact")
            else:
                outcomes.append(f"{record['probe_id']}.{name}=fabricated")
    return Check(
        f"P02.H5.{artifacts.backend}",
        PASS,
        "recorded, not gated",
        "1e-10 |E| + 1e-14",
        "; ".join(outcomes),
        "supplementary capability record (specification §8 H5)",
    )


def check_raw_structure(artifacts: _Artifacts) -> Check:
    """A24 — the grey-box route's raw structure, name map and recorded row orientation."""
    if artifacts.backend != "pyomo":
        return Check(
            f"P02.A24.{artifacts.backend}",
            NOT_APPLICABLE,
            "raw grey-box structure",
            "exact",
            None,
            "no grey-box lifting on this route",
        )
    raw = artifacts.raw_structure
    if not raw:
        return Check(
            "P02.A24.pyomo",
            UNSUPPORTED,
            "raw_structure.json",
            "exact",
            None,
            "raw_structure.json absent",
        )

    problems: list[str] = []
    variables, rows, nnz = raw.get("n_primals"), raw.get("n_constraints"), raw.get("nnz")
    fallback = bool(raw.get("fallback_link_form_used"))
    if fallback:
        if (variables, rows, nnz) != (24, 24, 74):
            problems.append(
                f"fallback link form is {variables}x{rows} nnz {nnz}, expected 24x24/74"
            )
    elif (variables, rows, nnz) != (17, 17, 60):
        problems.append(f"primary form is {variables}x{rows} nnz {nnz}, expected 17x17/60")
    if raw.get("pattern_provenance") != "backend-declared":
        problems.append(f"pattern provenance {raw.get('pattern_provenance')!r}")

    equation_map = raw.get("equation_map", [])
    mapped = {entry.get("row_id") for entry in equation_map}
    if mapped != set(closed_form.EQUATION_IDS_L):
        problems.append("equation map is not a bijection onto the specification row ids")
    negated = {
        entry["row_id"]
        for entry in equation_map
        if float(entry.get("sign_applied_to_reach_specification", 1.0)) == -1.0
    }
    defining = {f"kdef_{c}" for c in closed_form.COMPONENTS} | {
        f"hdef_{c}" for c in closed_form.COMPONENTS
    }
    if negated != defining:
        problems.append(f"negated rows are {sorted(negated)}, expected the six defining rows")
    orientation = raw.get("row_orientation", {})
    for required in ("native", "specification", "resolution"):
        if not orientation.get(required):
            problems.append(f"row_orientation lacks {required}")

    return _check(
        "P02.A24.pyomo",
        not problems,
        "raw 17 x 17 nnz 60 with no link rows; name map a bijection; the six defining rows "
        "negated and the native orientation recorded",
        "exact",
        f"{variables}x{rows} nnz {nnz}, {len(negated)} rows negated",
        "; ".join(problems[:3]),
    )


def check_cross_backend(sets: Mapping[str, _Artifacts]) -> list[Check]:
    """A21 — the two backends agree on identical ground."""
    if len(sets) < 2:
        present = ", ".join(sorted(sets)) or "none"
        return [
            Check(
                "P02.A21.cross",
                NOT_APPLICABLE,
                "both result sets present",
                "1e-12 (|E| + 1e-2 s_r/s_c)",
                None,
                f"only {present} available",
            )
        ]
    first, second = (sets[name] for name in sorted(sets))
    deviations: list[tuple[float, str]] = []
    problems: list[str] = []
    for (state_id, form), payload in sorted(first.jacobians.items()):
        other = second.jacobians.get((state_id, form))
        if other is None or payload["status"] != "ok" or other["status"] != "ok":
            continue
        left, right = _entries(payload), _entries(other)
        if set(left) != set(right):
            problems.append(f"{state_id} {form}: patterns differ")
            continue
        for key, value in left.items():
            tolerance = 1e-12 * (abs(value) + 1e-2 * _scale_ratio(key))
            deviations.append((abs(value - right[key]) / tolerance, f"{state_id} {form} {key}"))
    worst, where = _worst(deviations)
    return [
        _check(
            "P02.A21.cross",
            worst <= 1.0 and not problems,
            "identical patterns and values across backends",
            "1e-12 (|E| + 1e-2 s_r/s_c)",
            worst,
            f"worst at {where}; {'; '.join(problems[:2])}",
        )
    ]


def check_a13(artifacts: _Artifacts) -> Check:
    """A13 — the inlined form as a whole: pattern, invariance, values and vanishing entries.

    The underlying comparisons are the `.I` variants of A08-A11; this reports them as the single
    catalogue item the specification numbers, so no assertion is silently missing.
    """
    if "I" not in artifacts.forms:
        return Check(
            f"P02.A13.{artifacts.backend}",
            NOT_APPLICABLE,
            "inlined form",
            "n/a",
            None,
            "grey-box outputs are NLP variables; no inline composition mechanism",
        )
    parts = check_pattern(artifacts, "I") + check_values(artifacts, "I")
    failures = [check for check in parts if check.result == FAIL]
    numeric = [check.value for check in parts if isinstance(check.value, float)]
    return Check(
        f"P02.A13.{artifacts.backend}",
        FAIL if failures else PASS,
        "inlined pattern, invariance, values and vanishing entries",
        "as A08-A11",
        max(numeric) if numeric else None,
        "; ".join(f"{check.id}: {check.message}" for check in failures)[:200],
    )


def judge_backend(root: Path, backend: str) -> list[Check]:
    """Evaluate every applicable assertion for one backend's result set."""
    artifacts = load_artifacts(root, backend)
    if not artifacts.jacobians:
        return [
            Check(
                f"P02.results.{backend}",
                UNSUPPORTED,
                "a result set",
                "n/a",
                None,
                f"no artifacts under {artifacts.root}",
            )
        ]
    checks: list[Check] = []
    forms = artifacts.forms
    for form in forms:
        checks.extend(check_a01(artifacts, form))
    checks.extend(check_block_level(artifacts))
    checks.append(check_a03(artifacts))
    checks.extend(check_finite_differences(artifacts))
    for form in forms:
        checks.extend(check_pattern(artifacts, form))
        checks.extend(check_values(artifacts, form))
        checks.extend(check_directional(artifacts, form))
        checks.extend(check_domain_and_counts(artifacts, form))
        checks.extend(check_envelope(artifacts, form))
        checks.append(check_schema_conformance(artifacts, form))
    checks.append(check_a13(artifacts))
    checks.append(check_schur(artifacts))
    checks.append(check_second_order(artifacts))
    checks.append(classify_supplementary(artifacts))
    checks.append(check_raw_structure(artifacts))
    return checks


def judge_all(root: Path, backends: Sequence[str] = ("casadi", "pyomo")) -> list[Check]:
    """Judge every backend that produced a result set, plus the cross-backend assertion."""
    checks: list[Check] = [check_a00()]
    available: dict[str, _Artifacts] = {}
    for backend in backends:
        backend_checks = judge_backend(root, backend)
        checks.extend(backend_checks)
        artifacts = load_artifacts(root, backend)
        if artifacts.jacobians:
            available[backend] = artifacts
    checks.extend(check_cross_backend(available))
    return checks


def verdict(checks: Sequence[Check], backend: str) -> str:
    """The per-backend composition verdict of specification §11.1."""
    relevant = [check for check in checks if f".{backend}" in check.id]
    if not relevant:
        return "NO-RESULTS"
    if any(check.result == FAIL for check in relevant):
        return "FAIL-composition"
    if any(check.result == UNSUPPORTED for check in relevant):
        return "BLOCKED-unsupported"
    return "PASS-composition"
