"""P02 harness — the L-form of specification §2.4 on Pyomo 6.10.1 + PyNumero (ASL).

Specification: `docs/derivations/P02-composition-spec.md`, §2 (subsystem), §3 (blocks), §5
(states), §7 (measurements), §10.3 (this route), §10.4 (envelope). The harness produces
artifacts only; every assertion of §6 is the judge's, and nothing here imports
`benchmarks.p02.expected` — the block formulas below are implemented from §2.3 so that the
judge's expectation stays independent of what it judges.

Run it through `spikes/p02/pyomo/run.sh` from the repository root.

Three points of this route are worth stating up front.

*Ordering.* `PyomoNLPWithGreyBoxBlocks` sorts primal names alphabetically and lists the ASL
constraints before the grey-box output constraints, so neither order is the declaration order
(measured here: constraint 0 is `eq_A`, primal 0 is `L`). Every lookup below goes through
`primals_names()` / `constraint_names()` by name; no position is assumed anywhere.

*Row orientation.* PyNumero writes a grey-box output constraint as ``f(inputs) − output``
(`_ExternalGreyBoxAsNLP._evaluate_constraints_if_necessary_and_cache`), while §2.4 writes
`kdef_i` and `hdef_i` as ``output − f(inputs)``. The two differ by a factor −1 on those six rows
and on those six rows only; `OUTPUT_ROW_SIGN` is the single place that difference is applied, and
`raw_structure.json` records both the native and the exported orientation.

*Domain.* §2.2 as amended requires **both** blocks to guard the closed domain, in their value and
their Jacobian methods, and no guard may be dropped to make a stencil evaluable. The A07 pressure
step is 5 000 Pa for that reason: at 1e4 the stencil at S2 would reach 40 000 Pa, outside the
domain. Every registered stencil point is asserted inside the domain by the reference generator.
Block K and block H both raise, because A17 requires `residual()` **and** `jacobian()` to fail at
S7a and S7b.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pyomo.environ as pyo
import yaml
from pyomo.common.fileutils import find_library
from pyomo.contrib.pynumero.asl import AmplInterface
from pyomo.contrib.pynumero.interfaces.external_grey_box import (
    ExternalGreyBoxBlock,
    ExternalGreyBoxModel,
)
from pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp import PyomoNLPWithGreyBoxBlocks
from pyomo.version import version as pyomo_version
from scipy import __version__ as scipy_version
from scipy.sparse import coo_matrix

from spikes.p02.common import (
    EVALUATION_ORDER,
    STATUS_INVALID_TRIAL_STATE,
    STATUS_OK,
    BlockCounters,
    CounterSet,
    ResultWriter,
    StateInput,
    canonical_csc,
    environment_record,
    jacobian_payload,
    load_states,
    metadata_payload,
    repeat_microseconds,
    residual_payload,
)
from spikes.p02.common.export import CanonicalCsc
from spikes.p02.common.states import REFERENCE_PATH

# --------------------------------------------------------------------------------------------
# Constants (specification §2.2, §2.4)
# --------------------------------------------------------------------------------------------

BACKEND: Final = "pyomo"
FORM: Final = "L"
MODEL_VERSION: Final = "P02-L-form-v1"

R_GAS: Final = 8.31446261815324
T_REF: Final = 300.0
P_REF: Final = 100000.0
CP_MOLAR: Final = 100.0
COMPONENTS: Final = ("A", "B", "C")
T_BOIL: Final = np.array([320.0, 360.0, 400.0])
L_VAP: Final = np.array([25000.0, 30000.0, 35000.0])
V_MOLAR: Final = np.array([1e-4, 1e-4, 1e-4])

T_DOMAIN: Final = (280.0, 440.0)
P_DOMAIN: Final = (50000.0, 200000.0)

VARIABLE_IDS: Final = (
    "v_A",
    "v_B",
    "v_C",
    "l_A",
    "l_B",
    "l_C",
    "V",
    "L",
    "lnK_A",
    "lnK_B",
    "lnK_C",
    "hL_A",
    "hL_B",
    "hL_C",
    "T",
    "P",
    "Q",
)

EQUATION_IDS: Final = (
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "kdef_A",
    "kdef_B",
    "kdef_C",
    "hdef_A",
    "hdef_B",
    "hdef_C",
    "energy",
    "tspec",
    "pspec",
)

COLUMN_SCALES: Final = {
    "v_A": 3.0,
    "v_B": 3.0,
    "v_C": 3.0,
    "l_A": 3.0,
    "l_B": 3.0,
    "l_C": 3.0,
    "V": 3.0,
    "L": 3.0,
    "lnK_A": 1.0,
    "lnK_B": 1.0,
    "lnK_C": 1.0,
    "hL_A": 1e5,
    "hL_B": 1e5,
    "hL_C": 1e5,
    "T": 100.0,
    "P": 1e5,
    "Q": 1e5,
}

ROW_SCALES: Final = {
    "bal_A": 3.0,
    "bal_B": 3.0,
    "bal_C": 3.0,
    "Vdef": 3.0,
    "Ldef": 3.0,
    "eq_A": 9.0,
    "eq_B": 9.0,
    "eq_C": 9.0,
    "kdef_A": 1.0,
    "kdef_B": 1.0,
    "kdef_C": 1.0,
    "hdef_A": 1e5,
    "hdef_B": 1e5,
    "hdef_C": 1e5,
    "energy": 1e5,
    "tspec": 100.0,
    "pspec": 1e5,
}

#: The six rows PyNumero orients as ``f(inputs) − output`` where §2.4 writes
#: ``output − f(inputs)``. This is the only sign convention the harness applies, and it is an
#: exact scaling of a whole row (residual and Jacobian together), so the residual/Jacobian
#: identity is untouched. Set it to +1.0 to export PyNumero's own orientation instead.
OUTPUT_ROW_SIGN: Final = -1.0

GREY_BOX_ROWS: Final = ("kdef_A", "kdef_B", "kdef_C", "hdef_A", "hdef_B", "hdef_C")

#: Native constraint name of each §2.4 equation id (§4.3: the grey-box output constraints *are*
#: the defining rows, up to `OUTPUT_ROW_SIGN`).
NATIVE_EQUATION_NAMES: Final = {
    **{row: row for row in EQUATION_IDS if row not in GREY_BOX_ROWS},
    **{f"kdef_{c}": f"kb.output_constraints[lnK_{c}]" for c in COMPONENTS},
    **{f"hdef_{c}": f"hb.output_constraints[H_{c}]" for c in COMPONENTS},
}

#: Native primal name of each §2.4 variable id: the harness names the Pyomo `Var`s after the
#: specification ids, so the names agree and only the *indices* differ (they are sorted).
NATIVE_VARIABLE_NAMES: Final = {name: name for name in VARIABLE_IDS}

#: Model state used to initialise every compile. Initial values do not enter the compiled
#: function; PyNumero only needs a point at which to probe the declared block structure while
#: `PyomoNLPWithGreyBoxBlocks` counts the Jacobian nonzeros, and that point must be inside the
#: block-K domain even when the state being compiled (S7a, S7b) is not.
INITIAL_STATE_ID: Final = "S1"

#: Entry origins of §4.1, used verbatim in the source map.
ORIGIN_ALGEBRAIC: Final = "algebraic"
ORIGIN_CALLBACK_K: Final = "callback:K"
ORIGIN_CALLBACK_H: Final = "callback:H"


def entry_origin(row_id: str, col_id: str) -> str:
    """The §4.1 origin of one assembled entry."""
    if row_id.startswith("kdef_") and col_id in ("T", "P"):
        return ORIGIN_CALLBACK_K
    if row_id.startswith("hdef_") and col_id in ("T", "P", f"l_{row_id[-1]}"):
        return ORIGIN_CALLBACK_H
    return ORIGIN_ALGEBRAIC


def row_sign(row_id: str) -> float:
    """+1 for the algebraic rows, `OUTPUT_ROW_SIGN` for the six grey-box output rows."""
    return OUTPUT_ROW_SIGN if row_id in GREY_BOX_ROWS else 1.0


# --------------------------------------------------------------------------------------------
# Closed forms (specification §2.3) and the typed domain error (§2.2, A17)
# --------------------------------------------------------------------------------------------


class DomainError(ValueError):
    """Raised inside block K when a trial state leaves the closed domain (§2.2, A17)."""

    def __init__(self, variable: str, value: float, lower: float, upper: float, unit: str) -> None:
        super().__init__(
            f"{variable} = {value!r} {unit} is outside the closed domain "
            f"[{lower!r}, {upper!r}] {unit}"
        )
        self.variable = variable
        self.value = value
        self.lower = lower
        self.upper = upper
        self.unit = unit


def check_domain(temperature: float, pressure: float) -> None:
    """Enforce the closed domain 280–440 K, 50–200 kPa; the bounds are inclusive (S6)."""
    if not T_DOMAIN[0] <= temperature <= T_DOMAIN[1]:
        raise DomainError("T", float(temperature), T_DOMAIN[0], T_DOMAIN[1], "K")
    if not P_DOMAIN[0] <= pressure <= P_DOMAIN[1]:
        raise DomainError("P", float(pressure), P_DOMAIN[0], P_DOMAIN[1], "Pa")


def ln_k(temperature: float, pressure: float) -> np.ndarray:
    """`ln K_i(T, P)` of §2.3."""
    return (
        np.log(P_REF / pressure)
        + (L_VAP / R_GAS) * (1.0 / T_BOIL - 1.0 / temperature)
        + V_MOLAR * (pressure - P_REF) / (R_GAS * temperature)
    )


def ln_k_d_temperature(temperature: float, pressure: float) -> np.ndarray:
    """`∂lnK_i/∂T` of §2.3."""
    return (L_VAP - V_MOLAR * (pressure - P_REF)) / (R_GAS * temperature * temperature)


def ln_k_d_pressure(temperature: float, pressure: float) -> np.ndarray:
    """`∂lnK_i/∂P` of §2.3 (identical for all components; the v_i are equal)."""
    return -1.0 / pressure + V_MOLAR / (R_GAS * temperature)


def liquid_molar_enthalpy(temperature: float, pressure: float) -> np.ndarray:
    """`h_i^L(T, P)` of §2.3, J/mol."""
    return CP_MOLAR * (temperature - T_REF) + V_MOLAR * (pressure - P_REF)


def vapor_molar_enthalpy(temperature: float) -> np.ndarray:
    """`h_i^V(T)` of §2.3, J/mol; independent of P."""
    return CP_MOLAR * (temperature - T_REF) + L_VAP


# --------------------------------------------------------------------------------------------
# The two callback blocks (specification §3)
# --------------------------------------------------------------------------------------------


class KValueBlock(ExternalGreyBoxModel):
    """Block K (§3.1): θ = (T, P) ↦ (lnK_A, lnK_B, lnK_C); Jacobian declared dense, 3 × 2."""

    declared_jacobian_nnz: Final = 6
    declared_shape: Final = (3, 2)

    def __init__(self, counters: BlockCounters) -> None:
        self.counters = counters
        self._inputs = np.zeros(2, dtype=float)

    def input_names(self) -> list[str]:
        return ["T", "P"]

    def output_names(self) -> list[str]:
        return [f"lnK_{c}" for c in COMPONENTS]

    def set_input_values(self, input_values: Sequence[float]) -> None:
        np.copyto(self._inputs, np.asarray(input_values, dtype=float))

    def cached_inputs(self) -> np.ndarray:
        """The input values PyNumero last pushed into the block."""
        return np.array(self._inputs, dtype=float)

    def evaluate_outputs(self) -> np.ndarray:
        self.counters.record_value()
        temperature, pressure = float(self._inputs[0]), float(self._inputs[1])
        check_domain(temperature, pressure)
        return ln_k(temperature, pressure)

    def evaluate_jacobian_outputs(self) -> coo_matrix:
        self.counters.record_jacobian()
        temperature, pressure = float(self._inputs[0]), float(self._inputs[1])
        check_domain(temperature, pressure)
        data = np.concatenate(
            [ln_k_d_temperature(temperature, pressure), ln_k_d_pressure(temperature, pressure)]
        )
        rows = np.array([0, 1, 2, 0, 1, 2])
        cols = np.array([0, 0, 0, 1, 1, 1])
        return coo_matrix((data, (rows, cols)), shape=self.declared_shape)


class EnthalpyBlock(ExternalGreyBoxModel):
    """Block H (§3.2): ζ = (l_A, l_B, l_C, T, P) ↦ (H_A, H_B, H_C) = l_i h_i^L(T, P).

    The declared Jacobian has exactly nine entries: `(H_i, l_i)`, `(H_i, T)`, `(H_i, P)`. The six
    `(H_i, l_j≠i)` entries are structural zeros of ideal mixing and are never stored.
    """

    declared_jacobian_nnz: Final = 9
    declared_shape: Final = (3, 5)

    def __init__(self, counters: BlockCounters) -> None:
        self.counters = counters
        self._inputs = np.zeros(5, dtype=float)

    def input_names(self) -> list[str]:
        return [f"l_{c}" for c in COMPONENTS] + ["T", "P"]

    def output_names(self) -> list[str]:
        return [f"H_{c}" for c in COMPONENTS]

    def set_input_values(self, input_values: Sequence[float]) -> None:
        np.copyto(self._inputs, np.asarray(input_values, dtype=float))

    def cached_inputs(self) -> np.ndarray:
        """The input values PyNumero last pushed into the block."""
        return np.array(self._inputs, dtype=float)

    def evaluate_outputs(self) -> np.ndarray:
        self.counters.record_value()
        flows = self._inputs[:3]
        temperature, pressure = float(self._inputs[3]), float(self._inputs[4])
        check_domain(temperature, pressure)
        return flows * liquid_molar_enthalpy(temperature, pressure)

    def evaluate_jacobian_outputs(self) -> coo_matrix:
        self.counters.record_jacobian()
        flows = self._inputs[:3]
        temperature, pressure = float(self._inputs[3]), float(self._inputs[4])
        check_domain(temperature, pressure)
        data = np.concatenate(
            [liquid_molar_enthalpy(temperature, pressure), flows * CP_MOLAR, flows * V_MOLAR]
        )
        rows = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        cols = np.array([0, 1, 2, 3, 3, 3, 4, 4, 4])
        return coo_matrix((data, (rows, cols)), shape=self.declared_shape)


# --------------------------------------------------------------------------------------------
# The compiled L-form (specification §2.4, §10.3)
# --------------------------------------------------------------------------------------------


def build_model(
    state: StateInput, initial_x: Mapping[str, float], counters: CounterSet
) -> tuple[pyo.ConcreteModel, KValueBlock, EnthalpyBlock]:
    """The 17-variable, 17-equation L-form of §2.4 as a Pyomo model with two grey-box blocks."""
    model = pyo.ConcreteModel()
    for name in VARIABLE_IDS:
        setattr(model, name, pyo.Var(initialize=float(initial_x[name])))

    def var(name: str) -> pyo.Var:
        return getattr(model, name)

    for index, component in enumerate(COMPONENTS):
        setattr(
            model,
            f"bal_{component}",
            pyo.Constraint(
                expr=var(f"v_{component}") + var(f"l_{component}") - float(state.feed[index]) == 0.0
            ),
        )
    model.Vdef = pyo.Constraint(expr=model.V - (model.v_A + model.v_B + model.v_C) == 0.0)
    model.Ldef = pyo.Constraint(expr=model.L - (model.l_A + model.l_B + model.l_C) == 0.0)
    for component in COMPONENTS:
        setattr(
            model,
            f"eq_{component}",
            pyo.Constraint(
                expr=var(f"v_{component}") * model.L
                - pyo.exp(var(f"lnK_{component}")) * var(f"l_{component}") * model.V
                == 0.0
            ),
        )
    model.energy = pyo.Constraint(
        expr=sum(
            var(f"v_{component}") * (CP_MOLAR * (model.T - T_REF) + float(L_VAP[index]))
            for index, component in enumerate(COMPONENTS)
        )
        + model.hL_A
        + model.hL_B
        + model.hL_C
        - float(state.h_feed)
        - model.Q
        == 0.0
    )
    model.tspec = pyo.Constraint(expr=model.T - float(state.t_spec) == 0.0)
    model.pspec = pyo.Constraint(expr=model.P - float(state.p_spec) == 0.0)

    k_block = KValueBlock(counters.block("K"))
    h_block = EnthalpyBlock(counters.block("H"))
    model.kb = ExternalGreyBoxBlock()
    model.kb.set_external_model(
        k_block, inputs=[model.T, model.P], outputs=[model.lnK_A, model.lnK_B, model.lnK_C]
    )
    model.hb = ExternalGreyBoxBlock()
    model.hb.set_external_model(
        h_block,
        inputs=[model.l_A, model.l_B, model.l_C, model.T, model.P],
        outputs=[model.hL_A, model.hL_B, model.hL_C],
    )
    model.p02_objective = pyo.Objective(expr=0.0)
    return model, k_block, h_block


@dataclass
class CompiledLForm:
    """`residual` / `jacobian` at the frozen boundary, plus the name maps A01 demands."""

    state_id: str
    model: pyo.ConcreteModel
    nlp: PyomoNLPWithGreyBoxBlocks
    counters: CounterSet
    k_block: KValueBlock
    h_block: EnthalpyBlock
    native_primals: tuple[str, ...]
    native_constraints: tuple[str, ...]
    col_index: dict[str, int]
    row_index: dict[str, int]
    column_of_native: tuple[str, ...]
    equation_of_native: tuple[str, ...]

    def native_primal_vector(self, x: Mapping[str, float]) -> np.ndarray:
        """`x` re-ordered from §2.4 order into `primals_names()` order, by name."""
        return np.array([float(x[name]) for name in self.column_of_native], dtype=float)

    def residual(self, x: Mapping[str, float]) -> np.ndarray:
        """The §2.4 residual vector in equation order (includes `set_primals`)."""
        self.nlp.set_primals(self.native_primal_vector(x))
        raw = self.nlp.evaluate_constraints()
        return np.array(
            [row_sign(row) * float(raw[self.row_index[row]]) for row in EQUATION_IDS], dtype=float
        )

    def jacobian_entries(self, x: Mapping[str, float]) -> dict[tuple[str, str], float]:
        """The assembled Jacobian keyed by `(row_id, col_id)` (includes `set_primals`)."""
        self.nlp.set_primals(self.native_primal_vector(x))
        return self._entries_from(self.nlp.evaluate_jacobian().tocoo())

    def _entries_from(self, matrix: coo_matrix) -> dict[tuple[str, str], float]:
        entries: dict[tuple[str, str], float] = {}
        for native_row, native_col, value in zip(matrix.row, matrix.col, matrix.data, strict=True):
            row_id = self.equation_of_native[int(native_row)]
            col_id = self.column_of_native[int(native_col)]
            key = (row_id, col_id)
            if key in entries:
                raise RuntimeError(f"duplicate assembled entry {key} in the backend COO")
            entries[key] = row_sign(row_id) * float(value)
        return entries

    def jacobian(self, x: Mapping[str, float]) -> CanonicalCsc:
        """The assembled Jacobian as canonical CSC in the §2.4 row and column order."""
        return canonical_csc(self.jacobian_entries(x), EQUATION_IDS, VARIABLE_IDS)

    def source_map(self, matrix: CanonicalCsc) -> list[dict[str, Any]]:
        """One record per stored entry: §2.4 ids, the native names and the native indices."""
        records: list[dict[str, Any]] = []
        for position, col_id in enumerate(matrix.col_ids):
            for k in range(matrix.indptr[position], matrix.indptr[position + 1]):
                row_id = matrix.row_ids[matrix.indices[k]]
                records.append(
                    {
                        "k": k,
                        "csc_index": k,
                        "row_id": row_id,
                        "col_id": col_id,
                        "native_row": NATIVE_EQUATION_NAMES[row_id],
                        "native_col": NATIVE_VARIABLE_NAMES[col_id],
                        "native_row_index": self.row_index[row_id],
                        "native_col_index": self.col_index[col_id],
                        "origin": entry_origin(row_id, col_id),
                    }
                )
        return records


def compile_l_form(state: StateInput, initial_x: Mapping[str, float]) -> CompiledLForm:
    """Build the model and hand it to `PyomoNLPWithGreyBoxBlocks` (the M02 compile phase)."""
    counters = CounterSet()
    counters.block("K")
    counters.block("H")
    model, k_block, h_block = build_model(state, initial_x, counters)
    nlp = PyomoNLPWithGreyBoxBlocks(model)

    native_primals = tuple(nlp.primals_names())
    native_constraints = tuple(nlp.constraint_names())
    if sorted(native_primals) != sorted(NATIVE_VARIABLE_NAMES[name] for name in VARIABLE_IDS):
        raise RuntimeError(f"primal names are not the §2.4 variables: {native_primals}")
    if sorted(native_constraints) != sorted(NATIVE_EQUATION_NAMES[row] for row in EQUATION_IDS):
        raise RuntimeError(f"constraint names are not the §2.4 equations: {native_constraints}")

    col_index = {col: native_primals.index(NATIVE_VARIABLE_NAMES[col]) for col in VARIABLE_IDS}
    row_index = {row: native_constraints.index(NATIVE_EQUATION_NAMES[row]) for row in EQUATION_IDS}
    column_of_native = [""] * len(native_primals)
    for col_id, index in col_index.items():
        column_of_native[index] = col_id
    equation_of_native = [""] * len(native_constraints)
    for row_id, index in row_index.items():
        equation_of_native[index] = row_id

    return CompiledLForm(
        state_id=state.state_id,
        model=model,
        nlp=nlp,
        counters=counters,
        k_block=k_block,
        h_block=h_block,
        native_primals=native_primals,
        native_constraints=native_constraints,
        col_index=col_index,
        row_index=row_index,
        column_of_native=tuple(column_of_native),
        equation_of_native=tuple(equation_of_native),
    )


def counter_delta(
    before: Mapping[str, Mapping[str, int]], after: Mapping[str, Mapping[str, int]]
) -> dict[str, dict[str, int]]:
    """Per-block difference of two `CounterSet.snapshot()` results."""
    return {
        name: {key: after[name][key] - before[name][key] for key in after[name]} for name in after
    }


# --------------------------------------------------------------------------------------------
# Per-state evaluation at the frozen boundary (specification §10.4, A17, A20)
# --------------------------------------------------------------------------------------------


@dataclass
class StateResult:
    """What one registered state contributes to the exported result set."""

    residual: dict[str, Any]
    jacobian: dict[str, Any]
    counters: dict[str, dict[str, dict[str, int]]]
    matrix: CanonicalCsc | None


def evaluate_state(compiled: CompiledLForm, state: StateInput) -> StateResult:
    """Evaluate `residual()` and `jacobian()` once each, recording the counters of each call."""
    x = state.x_l
    phase = state.oracle_phase_state
    raw_shape = [len(compiled.native_constraints), len(compiled.native_primals)]

    before = compiled.counters.snapshot()
    values: list[float] | None
    try:
        values = [float(value) for value in compiled.residual(x)]
        residual_status, residual_message = STATUS_OK, ""
    except DomainError as error:
        values, residual_status, residual_message = None, STATUS_INVALID_TRIAL_STATE, str(error)
    residual_counts = counter_delta(before, compiled.counters.snapshot())

    before = compiled.counters.snapshot()
    entries: dict[tuple[str, str], float] | None
    try:
        entries = compiled.jacobian_entries(x)
        jacobian_status, jacobian_message = STATUS_OK, ""
    except DomainError as error:
        entries, jacobian_status, jacobian_message = None, STATUS_INVALID_TRIAL_STATE, str(error)
    jacobian_counts = counter_delta(before, compiled.counters.snapshot())

    matrix = None if entries is None else canonical_csc(entries, EQUATION_IDS, VARIABLE_IDS)
    return StateResult(
        residual=residual_payload(
            status=residual_status,
            model_version=MODEL_VERSION,
            x=x,
            variable_ids=VARIABLE_IDS,
            equation_ids=EQUATION_IDS,
            values=values,
            counters=residual_counts,
            phase_signature=phase,
            message=residual_message,
        ),
        jacobian=jacobian_payload(
            status=jacobian_status,
            model_version=MODEL_VERSION,
            x=x,
            variable_ids=VARIABLE_IDS,
            matrix=matrix,
            counters=jacobian_counts,
            phase_signature=phase,
            pattern_provenance="backend-declared",
            source_map=() if matrix is None else compiled.source_map(matrix),
            raw_shape=raw_shape,
            raw_nnz=None if entries is None else len(entries),
            message=jacobian_message,
        ),
        counters={"residual": residual_counts, "jacobian": jacobian_counts},
        matrix=matrix,
    )


# --------------------------------------------------------------------------------------------
# Block-level records (A02, A04, A05, A06, A07) — the block's own values and Jacobian, and the
# fourth-order five-point stencil taken *through the backend* (`set_input_values` +
# `evaluate_outputs`). These calls are made after the per-state counters of A18 are recorded and
# their own counter cost is reported separately.
# --------------------------------------------------------------------------------------------

FD_STATES: Final = ("S1", "S2", "S3", "S4", "S5")
FD_STEPS_K: Final = {"T": 0.1, "P": 100.0}
# Block H's pressure step is 5 000 Pa, not 1e4: at S2 (P = 60 000 Pa) a 1e4 step would evaluate at
# 40 000 Pa, outside the closed domain, and the only way to make that work would be to drop block
# H's domain guard (specification §2.2, A07, amended).
FD_STEPS_H: Final = {"l_A": 0.01, "l_B": 0.01, "l_C": 0.01, "T": 0.1, "P": 5000.0}
FD_WEIGHTS: Final = ((-2, 1.0), (-1, -8.0), (1, 8.0), (2, -1.0))
FD_OFFSETS: Final = tuple(offset for offset, _ in FD_WEIGHTS)


def five_point_derivative(
    evaluate: Callable[[np.ndarray], np.ndarray], point: np.ndarray, index: int, step: float
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Fourth-order central five-point derivative in one coordinate, and its raw samples.

    The samples are returned in `FD_OFFSETS` order so that the judge can form the quotient
    itself; the derivative computed here is a convenience, never the evidence.
    """
    samples: list[np.ndarray] = []
    total: np.ndarray | None = None
    for offset, weight in FD_WEIGHTS:
        shifted = np.array(point, dtype=float)
        shifted[index] += offset * step
        sample = np.array(evaluate(shifted), dtype=float)
        samples.append(sample)
        term = weight * sample
        total = term if total is None else total + term
    if total is None:
        raise RuntimeError("empty stencil")
    return total / (12.0 * step), samples


def block_probe(
    block: KValueBlock | EnthalpyBlock, name: str, run_stencil: bool, steps: Mapping[str, float]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The block's inputs, outputs and declared Jacobian, with one shared set of evaluations.

    Returns the rich record of `blocks.json` and, when the stencil was run, the raw record of
    `block_records.json`, in which the samples are exported undifferenced so the judge forms the
    quotient itself. Both are in the block's own orientation; `OUTPUT_ROW_SIGN` belongs to the
    assembled rows, not to the block.
    """
    input_names = block.input_names()
    output_names = block.output_names()
    point = block.cached_inputs()

    def evaluate(values: np.ndarray) -> np.ndarray:
        block.set_input_values(values)
        return np.array(block.evaluate_outputs(), dtype=float)

    outputs = evaluate(point)
    jacobian = block.evaluate_jacobian_outputs()
    reported: dict[tuple[str, str], float] = {}
    indexed: dict[str, float] = {}
    for row, col, value in zip(jacobian.row, jacobian.col, jacobian.data, strict=True):
        reported[(output_names[int(row)], input_names[int(col)])] = float(value)
        indexed[f"{int(row)}|{int(col)}"] = float(value)

    record: dict[str, Any] = {
        "block": name,
        "inputs": {name_: float(value) for name_, value in zip(input_names, point, strict=True)},
        "outputs": {
            name_: float(value) for name_, value in zip(output_names, outputs, strict=True)
        },
        "declared_jacobian": {
            "shape": list(block.declared_shape),
            "nnz": int(jacobian.nnz),
            "declared_jacobian_nnz": block.declared_jacobian_nnz,
            "stored_explicit_zeros": int(np.sum(np.asarray(jacobian.data) == 0.0)),
            "entries": [
                {
                    "output": output_names[int(row)],
                    "input": input_names[int(col)],
                    "block_row": int(row),
                    "block_col": int(col),
                    "value": float(value),
                }
                for row, col, value in zip(jacobian.row, jacobian.col, jacobian.data, strict=True)
            ],
        },
    }

    raw: dict[str, Any] | None = None
    if run_stencil:
        stencil: list[dict[str, Any]] = []
        raw_stencil: dict[str, Any] = {}
        for col, input_name in enumerate(input_names):
            step = steps[input_name]
            derivative, samples = five_point_derivative(evaluate, point, col, step)
            raw_stencil[str(col)] = {
                "step": [step],
                "samples": [float(value) for sample in samples for value in sample],
            }
            for row, output_name in enumerate(output_names):
                key = (output_name, input_name)
                stencil.append(
                    {
                        "output": output_name,
                        "input": input_name,
                        "step": step,
                        "finite_difference": float(derivative[row]),
                        "declared": key in reported,
                        "reported": reported.get(key),
                    }
                )
        record["finite_difference"] = {
            "stencil": "five-point fourth-order central",
            "steps": dict(steps),
            "entries": stencil,
        }
        raw = {
            "inputs": [float(value) for value in point],
            "values": [float(value) for value in outputs],
            "jacobian_entries": indexed,
            "jacobian_nnz": int(jacobian.nnz),
            "declared_shape": list(block.declared_shape),
            "stencil": raw_stencil,
            "stencil_offsets": list(FD_OFFSETS),
        }

    block.set_input_values(point)
    return record, raw


# --------------------------------------------------------------------------------------------
# Directional derivative of the assembled residual (A15) and the JVP/VJP record (A16)
# --------------------------------------------------------------------------------------------

DIRECTIONAL_EPSILON: Final = 1e-3


def load_directions() -> dict[str, list[float]]:
    """`u_L` and `v_L` of §5, read as harness input (directions, not expectations)."""
    with REFERENCE_PATH.open(encoding="utf-8") as handle:
        document: dict[str, Any] = yaml.safe_load(handle)
    directions = document["directions"]
    return {
        "u_L": [float(value) for value in directions["u_L"]],
        "v_L": [float(value) for value in directions["v_L"]],
    }


def directional_derivative(
    compiled: CompiledLForm, state: StateInput, direction: Sequence[float]
) -> tuple[list[float], dict[str, list[float]]]:
    """`d/dε r(x + ε D_c u)` at ε = 0 by the fourth-order five-point stencil of A15.

    The raw samples are returned beside the quotient, in specification orientation (they come
    from `CompiledLForm.residual`, which has already applied `OUTPUT_ROW_SIGN`), so that the
    judge does the differencing.
    """
    scaled = {
        name: COLUMN_SCALES[name] * value
        for name, value in zip(VARIABLE_IDS, direction, strict=True)
    }
    samples: dict[str, list[float]] = {}
    total = np.zeros(len(EQUATION_IDS), dtype=float)
    for offset, weight in FD_WEIGHTS:
        shifted = {
            name: state.x_l[name] + offset * DIRECTIONAL_EPSILON * scaled[name]
            for name in VARIABLE_IDS
        }
        sample = compiled.residual(shifted)
        samples[str(offset)] = [float(value) for value in sample]
        total = total + weight * sample
    return [float(value) for value in total / (12.0 * DIRECTIONAL_EPSILON)], samples


def jvp_vjp_record(
    matrix: CanonicalCsc, directions: Mapping[str, Sequence[float]]
) -> dict[str, Any]:
    """A16 for this route: the capability is absent, so the scalars come from the assembled
    matrix and are recorded as a fact, never as evidence."""
    entries = matrix.entries()
    u = dict(zip(VARIABLE_IDS, directions["u_L"], strict=True))
    v = dict(zip(EQUATION_IDS, directions["v_L"], strict=True))
    j_times_u = dict.fromkeys(EQUATION_IDS, 0.0)
    jt_times_v = dict.fromkeys(VARIABLE_IDS, 0.0)
    absolute_sum = 0.0
    for key, value in entries.items():
        row_id, col_id = key.split("|")
        j_times_u[row_id] += value * u[col_id]
        jt_times_v[col_id] += value * v[row_id]
        absolute_sum += abs(v[row_id] * value * u[col_id])
    forward = sum(v[row] * j_times_u[row] for row in EQUATION_IDS)
    reverse = sum(jt_times_v[col] * u[col] for col in VARIABLE_IDS)
    return {
        "J_u": [j_times_u[row] for row in EQUATION_IDS],
        "Jt_v": [jt_times_v[col] for col in VARIABLE_IDS],
        "v_dot_J_u": forward,
        "Jt_v_dot_u": reverse,
        "absolute_difference": abs(forward - reverse),
        "absolute_sum_bound": absolute_sum,
    }


def directional_product_record(state_id: str, jvp_record: Mapping[str, Any]) -> dict[str, Any]:
    """The `directional_products.json` record the judge reads for both routes.

    This route declares `jvp`/`vjp` absent, so there is no independent product to compare: the
    vectors below *are* the assembled ones, which is why the two `*_minus_assembled_max` fields
    are exactly zero. `jvp_vjp.json` carries the same numbers with that caveat spelled out.
    """
    return {
        "state_id": state_id,
        "form": FORM,
        "jvp": list(jvp_record["J_u"]),
        "vjp": list(jvp_record["Jt_v"]),
        "jvp_minus_assembled_max": 0.0,
        "vjp_minus_assembled_max": 0.0,
        "v_dot_Ju": jvp_record["v_dot_J_u"],
        "JTv_dot_u": jvp_record["Jt_v_dot_u"],
        "identity_abs_difference": jvp_record["absolute_difference"],
        "identity_scale": jvp_record["absolute_sum_bound"],
    }


# --------------------------------------------------------------------------------------------
# Second-order probe (specification §8). The blocks implement first derivatives only; whatever
# `evaluate_hessian_lag()` does is recorded verbatim.
# --------------------------------------------------------------------------------------------

SECOND_ORDER_PROBES: Final = (
    ("H1", "eq_A", ("d2phi/dv_A dL", "d2phi/dlnK_A2")),
    ("H2", "kdef_A", ("d2phi/dT2", "d2phi/dT dP", "d2phi/dP2")),
    ("H3", "hdef_A", ("d2phi/dl_A dT", "d2phi/dl_A dP")),
)


def second_order_probe(compiled: CompiledLForm, state: StateInput) -> dict[str, Any]:
    """`set_duals(λ)` then `evaluate_hessian_lag()` for each λ of §8, recorded verbatim."""
    probes: list[dict[str, Any]] = []
    for probe_id, row_id, requested in SECOND_ORDER_PROBES:
        duals = np.zeros(len(compiled.native_constraints), dtype=float)
        duals[compiled.row_index[row_id]] = row_sign(row_id)
        record: dict[str, Any] = {
            "probe": probe_id,
            "lambda_row": row_id,
            "native_lambda_row": NATIVE_EQUATION_NAMES[row_id],
            "native_lambda_value": row_sign(row_id),
            "requested_entries": list(requested),
            "mechanism": "nlp.set_primals(x); nlp.set_duals(lambda); nlp.evaluate_hessian_lag()",
        }
        compiled.nlp.set_primals(compiled.native_primal_vector(state.x_l))
        try:
            compiled.nlp.set_duals(duals)
            record["set_duals"] = "ok"
        except Exception as error:  # noqa: BLE001 - the outcome is the measurement
            record["set_duals"] = "raised"
            record["exception_type"] = type(error).__name__
            record["exception_message"] = str(error)
            record["classification"] = "absent"
            record["values_returned"] = None
            probes.append(record)
            continue
        try:
            hessian = compiled.nlp.evaluate_hessian_lag()
        except Exception as error:  # noqa: BLE001 - the outcome is the measurement
            record["outcome"] = "raised"
            record["exception_type"] = type(error).__name__
            record["exception_message"] = str(error)
            record["classification"] = "absent"
            record["values_returned"] = None
        else:
            coo = hessian.tocoo()
            record["outcome"] = "returned"
            record["classification"] = "numbers_returned"
            record["values_returned"] = [
                {
                    "row": compiled.column_of_native[int(row)],
                    "col": compiled.column_of_native[int(col)],
                    "value": float(value),
                }
                for row, col, value in zip(coo.row, coo.col, coo.data, strict=True)
            ]
        probes.append(record)
    return {
        "state": state.state_id,
        "declared_hessian_capability": "absent",
        "blocks_implement": "first derivatives only; no Hessian method is defined on either block",
        "probes": probes,
        "H4": {
            "probe": "H4",
            "status": "not_applicable",
            "reason": "H4 is an I-form entry and this route has no I-form (§10.3)",
        },
        "H5": {
            "probe": "H5",
            "status": "not_applicable",
            "reason": "H5 is the supplementary CasADi symbolic-Jacobian variant (§8)",
        },
    }


# --------------------------------------------------------------------------------------------
# M08 / M09 records
# --------------------------------------------------------------------------------------------

SOURCE_MAP_EXAMPLE_ENTRIES: Final = (("eq_B", "lnK_B"), ("kdef_B", "T"), ("hdef_C", "l_C"))


def expected_entry(row_id: str, col_id: str, x: Mapping[str, float]) -> float:
    """The §2.5 closed form of the three M09 entries, computed here and not read from the judge."""
    index = COMPONENTS.index(row_id[-1])
    temperature, pressure = x["T"], x["P"]
    if (row_id, col_id) == ("eq_B", "lnK_B"):
        return -np.exp(x["lnK_B"]) * x["l_B"] * x["V"]
    if row_id.startswith("kdef_") and col_id == "T":
        return -float(ln_k_d_temperature(temperature, pressure)[index])
    if row_id.startswith("hdef_") and col_id == f"l_{row_id[-1]}":
        return -float(liquid_molar_enthalpy(temperature, pressure)[index])
    raise KeyError(f"no closed form registered for ({row_id}, {col_id})")


def source_map_example(
    compiled: CompiledLForm, state: StateInput, matrix: CanonicalCsc
) -> dict[str, Any]:
    """M09: the three named entries with their CSC index taken from the exported structure."""
    by_key = {
        (record["row_id"], record["col_id"]): record for record in compiled.source_map(matrix)
    }
    entries = []
    for row_id, col_id in SOURCE_MAP_EXAMPLE_ENTRIES:
        record = dict(by_key[(row_id, col_id)])
        record["value"] = matrix.data[record["csc_index"]]
        record["expected"] = expected_entry(row_id, col_id, state.x_l)
        entries.append(record)
    return {"state": state.state_id, "entries": entries}


def structure_size(matrix: CanonicalCsc) -> dict[str, Any]:
    """M08: dimension, nnz and the bytes of `(indptr, indices, data)` at int32/float64."""
    return {
        "rows": len(matrix.row_ids),
        "columns": len(matrix.col_ids),
        "nnz": matrix.nnz,
        "indptr_bytes": 4 * len(matrix.indptr),
        "indices_bytes": 4 * len(matrix.indices),
        "data_bytes": 8 * len(matrix.data),
        "total_bytes": 4 * len(matrix.indptr) + 4 * len(matrix.indices) + 8 * len(matrix.data),
        "assumed_dtypes": {"indptr": "int32", "indices": "int32", "data": "float64"},
    }


def raw_structure_record(
    compiled: CompiledLForm,
    matrix: CanonicalCsc,
    patterns: Mapping[str, tuple[tuple[str, str], ...]],
) -> dict[str, Any]:
    """A24 and M08: what PyNumero actually assembled, and how it maps onto §2.4."""
    reference = patterns[next(iter(patterns))]
    invariant = all(pattern == reference for pattern in patterns.values())
    return {
        "route": (
            "primary: set_external_model(model, inputs=[existing Vars], outputs=[existing Vars])"
        ),
        "fallback_link_form_used": False,
        "n_primals": len(compiled.native_primals),
        "n_constraints": len(compiled.native_constraints),
        "nnz": matrix.nnz,
        "pattern_provenance": "backend-declared",
        "native_primals_names": list(compiled.native_primals),
        "native_constraint_names": list(compiled.native_constraints),
        "variable_map": [
            {
                "col_id": col_id,
                "native_name": NATIVE_VARIABLE_NAMES[col_id],
                "native_index": compiled.col_index[col_id],
            }
            for col_id in VARIABLE_IDS
        ],
        "equation_map": [
            {
                "row_id": row_id,
                "native_name": NATIVE_EQUATION_NAMES[row_id],
                "native_index": compiled.row_index[row_id],
                "kind": "grey_box_output" if row_id in GREY_BOX_ROWS else "algebraic",
                "sign_applied_to_reach_specification": row_sign(row_id),
            }
            for row_id in EQUATION_IDS
        ],
        "row_orientation": {
            "native": "PyNumero writes a grey-box output constraint as f(inputs) - output",
            "specification": "§2.4 writes kdef_i and hdef_i as output - f(inputs)",
            "resolution": (
                "the six grey-box rows are multiplied by -1 (residual and Jacobian together, an "
                "exact row scaling) before export; every other row is exported unchanged"
            ),
            "affected_rows": list(GREY_BOX_ROWS),
            "constant": "OUTPUT_ROW_SIGN",
        },
        "pattern_state_invariant": invariant,
        "pattern_states_checked": list(patterns),
        "structure_size_reduced": structure_size(matrix),
        "structure_size_raw": structure_size(matrix),
        "raw_equals_reduced": (
            "the primary path assembles the L-form natively; the reduced matrix is the raw matrix "
            "permuted into §2.4 order with the six grey-box rows negated, so the two have the "
            "same dimension and the same number of nonzeros"
        ),
    }


# --------------------------------------------------------------------------------------------
# Measurements (specification §7)
# --------------------------------------------------------------------------------------------

IMPORT_CHILD_SOURCE: Final = (
    "import time;"
    "t0 = time.perf_counter_ns();"
    "import pyomo.environ;"
    "import pyomo.contrib.pynumero.interfaces.external_grey_box;"
    "import pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp;"
    "from pyomo.contrib.pynumero.asl import AmplInterface;"
    "t1 = time.perf_counter_ns();"
    "print((t1 - t0) / 1e6)"
)


def memory_child_source(harness_path: str) -> str:
    """The M06 probe: VmRSS and elapsed time at each stage of a fresh interpreter.

    `VmRSS` from `/proc/self/status` is the *current* resident set. The alternative,
    `getrusage(...).ru_maxrss`, is a high-water mark that a spawned process inherits from the
    process that spawned it (measured here: a child of the loaded harness reports 111 MiB before
    importing anything), so it is recorded separately as the peak and the probe is started from a
    minimal launcher (`LAUNCHER_SOURCE`) to keep even that figure meaningful.
    """
    return (
        "import importlib.util, json, resource, sys, time, tracemalloc\n"
        "def vmrss():\n"
        "    for line in open('/proc/self/status'):\n"
        "        if line.startswith('VmRSS:'):\n"
        "            return int(line.split()[1]) / 1024.0\n"
        "    return float('nan')\n"
        "def peak():\n"
        "    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0\n"
        "at_start = vmrss()\n"
        "t0 = time.perf_counter_ns()\n"
        "import numpy\n"
        "t1 = time.perf_counter_ns()\n"
        "after_numpy = vmrss()\n"
        "import pyomo.environ\n"
        "import pyomo.contrib.pynumero.interfaces.external_grey_box\n"
        "import pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp\n"
        "import scipy.sparse\n"
        "from pyomo.contrib.pynumero.asl import AmplInterface\n"
        "t2 = time.perf_counter_ns()\n"
        "after_backend = vmrss()\n"
        f"spec = importlib.util.spec_from_file_location('p02_pyomo_harness', {harness_path!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['p02_pyomo_harness'] = module\n"
        "spec.loader.exec_module(module)\n"
        "state = module.load_states()[module.INITIAL_STATE_ID]\n"
        "after_harness = vmrss()\n"
        "t3 = time.perf_counter_ns()\n"
        "tracemalloc.start()\n"
        "module.compile_l_form(state, state.x_l)\n"
        "traced = tracemalloc.get_traced_memory()[1] / (1024.0 * 1024.0)\n"
        "tracemalloc.stop()\n"
        "t4 = time.perf_counter_ns()\n"
        "after_compile = vmrss()\n"
        "print(json.dumps(dict("
        "vmrss_at_start_mib=at_start,"
        " vmrss_after_numpy_import_mib=after_numpy,"
        " vmrss_after_backend_import_mib=after_backend,"
        " vmrss_after_harness_module_mib=after_harness,"
        " vmrss_after_compile_mib=after_compile,"
        " numpy_import_ms=(t1 - t0) / 1e6,"
        " backend_import_ms=(t2 - t1) / 1e6,"
        " compile_ms=(t4 - t3) / 1e6,"
        " tracemalloc_peak_during_compile_mib=traced,"
        " ru_maxrss_peak_mib=peak())))\n"
    )


def _statistics(samples: Sequence[float]) -> dict[str, Any]:
    ordered = sorted(samples)
    return {
        "median_ms": ordered[len(ordered) // 2],
        "min_ms": ordered[0],
        "samples_ms": list(samples),
    }


def _summary(samples: Sequence[float]) -> dict[str, Any]:
    """Median and minimum of a unitless sample, with the raw values kept."""
    ordered = sorted(samples)
    return {"median": ordered[len(ordered) // 2], "min": ordered[0], "samples": list(samples)}


#: `ru_maxrss` is a high-water mark that a child inherits from the process that spawned it
#: (measured here: a child of this harness reports 111 MiB before importing anything, because
#: `subprocess` spawns through `posix_spawn` and the counter carries over). M06 therefore starts
#: its child from this minimal launcher instead, whose own footprint is recorded as the floor.
LAUNCHER_SOURCE: Final = (
    "import subprocess, sys;"
    "result = subprocess.run([sys.executable, '-c', sys.argv[1]], capture_output=True, text=True);"
    "sys.stderr.write(result.stderr);"
    "sys.stdout.write(result.stdout);"
    "raise SystemExit(result.returncode)"
)


def _run_child(command: Sequence[str]) -> tuple[str, float]:
    start = time.perf_counter_ns()
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return completed.stdout.strip(), (time.perf_counter_ns() - start) / 1e6


def measure_import_time(processes: int) -> dict[str, Any]:
    """M01: a fresh subprocess per repetition; the backend import and the whole process."""
    in_child: list[float] = []
    wall: list[float] = []
    baseline: list[float] = []
    for _ in range(processes):
        stdout, elapsed = _run_child([sys.executable, "-c", IMPORT_CHILD_SOURCE])
        in_child.append(float(stdout))
        wall.append(elapsed)
        _, empty = _run_child([sys.executable, "-c", "pass"])
        baseline.append(empty)
    return {
        "processes": processes,
        "backend_import_ms": _statistics(in_child),
        "subprocess_wall_ms": _statistics(wall),
        "empty_interpreter_wall_ms": _statistics(baseline),
        "note": (
            "backend_import_ms times the import statements inside a child that imports nothing at "
            "module scope, so the import is measured from a clean interpreter; subprocess_wall_ms "
            "is interpreter start to child exit, and empty_interpreter_wall_ms is the same "
            "measurement for a child that imports nothing at all. The ASL library is not loaded "
            "by these imports: it is loaded inside PyomoNLPWithGreyBoxBlocks construction and its "
            "cost is therefore in M02, not in M01"
        ),
    }


def run_compile_child() -> dict[str, Any]:
    """M02, M04, M07 in a fresh process: compile, then the first residual and Jacobian call."""
    states = load_states()
    state = states[INITIAL_STATE_ID]
    start = time.perf_counter_ns()
    compiled = compile_l_form(state, state.x_l)
    compile_ms = (time.perf_counter_ns() - start) / 1e6
    compile_counts = compiled.counters.snapshot()

    start = time.perf_counter_ns()
    compiled.residual(state.x_l)
    first_residual_ms = (time.perf_counter_ns() - start) / 1e6
    start = time.perf_counter_ns()
    compiled.jacobian_entries(state.x_l)
    first_jacobian_ms = (time.perf_counter_ns() - start) / 1e6
    return {
        "state": state.state_id,
        "compile_ms": compile_ms,
        "first_residual_ms": first_residual_ms,
        "first_jacobian_ms": first_jacobian_ms,
        "compile_phase_counters": compile_counts,
    }


def measure_compile_and_first_call(processes: int) -> dict[str, Any]:
    """M02, M04 and M07 over `processes` fresh subprocesses of this file."""
    reports: list[dict[str, Any]] = []
    for _ in range(processes):
        stdout, _ = _run_child([sys.executable, str(Path(__file__).resolve()), "--mode", "compile"])
        reports.append(json.loads(stdout))
    counters = [report["compile_phase_counters"] for report in reports]
    return {
        "processes": processes,
        "compile_ms": _statistics([report["compile_ms"] for report in reports]),
        "first_residual_ms": _statistics([report["first_residual_ms"] for report in reports]),
        "first_jacobian_ms": _statistics([report["first_jacobian_ms"] for report in reports]),
        "compile_phase_counters": counters[0],
        "compile_phase_counters_identical_across_processes": all(
            entry == counters[0] for entry in counters
        ),
    }


def measure_memory_profile(processes: int) -> dict[str, Any]:
    """M06: the staged probe above, run in `processes` fresh interpreters."""
    source = memory_child_source(str(Path(__file__).resolve()))
    reports: list[dict[str, float]] = []
    for _ in range(processes):
        stdout, _ = _run_child([sys.executable, "-c", LAUNCHER_SOURCE, source])
        reports.append(json.loads(stdout))
    keys = (
        "vmrss_at_start_mib",
        "vmrss_after_numpy_import_mib",
        "vmrss_after_backend_import_mib",
        "vmrss_after_harness_module_mib",
        "vmrss_after_compile_mib",
        "numpy_import_ms",
        "backend_import_ms",
        "compile_ms",
        "tracemalloc_peak_during_compile_mib",
        "ru_maxrss_peak_mib",
    )
    return {
        "processes": processes,
        "method": (
            "VmRSS from /proc/self/status, read in a fresh interpreter at each stage; this is the "
            "current resident set, not a high-water mark. ru_maxrss_peak_mib is reported "
            "separately as the peak, and the probe is started from a minimal launcher because "
            "ru_maxrss is inherited by a spawned process from the process that spawned it"
        ),
        "stages": {key: _summary([report[key] for report in reports]) for key in keys},
        "note": (
            "the ASL library is loaded inside PyomoNLPWithGreyBoxBlocks construction, together "
            "with the .nl write, so its cost falls in the compile stage and not in the backend "
            "import stage; vmrss_after_harness_module_mib is taken after this harness module "
            "itself is loaded, so the compile cost is vmrss_after_compile_mib minus that figure. "
            "compile_ms here runs under tracemalloc and is slower than the M02 headline in "
            "timings.json, which is measured without it"
        ),
    }


def measure_evaluation_time(
    compiled: CompiledLForm, state: StateInput, repetitions: int, warmup: int
) -> dict[str, Any]:
    """M05: 20 warm-up then 200 timed calls each, `set_primals` included in every call."""
    x = state.x_l
    native = compiled.native_primal_vector(x)

    def residual_call() -> None:
        compiled.nlp.set_primals(native)
        compiled.nlp.evaluate_constraints()

    def jacobian_call() -> None:
        compiled.nlp.set_primals(native)
        compiled.nlp.evaluate_jacobian()

    return {
        "state": state.state_id,
        "warmup": warmup,
        "repetitions": repetitions,
        "backend_residual_us": repeat_microseconds(residual_call, repetitions, warmup),
        "backend_jacobian_us": repeat_microseconds(jacobian_call, repetitions, warmup),
        "boundary_residual_us": repeat_microseconds(
            lambda: compiled.residual(x), repetitions, warmup
        ),
        "boundary_jacobian_us": repeat_microseconds(
            lambda: compiled.jacobian(x), repetitions, warmup
        ),
        "note": (
            "backend_* is set_primals plus the PyNumero evaluation; boundary_* is the full "
            "CompiledProblem call, which adds the name-keyed permutation into §2.4 order and, for "
            "the Jacobian, the canonical CSC assembly"
        ),
    }


# --------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------


def environment_document() -> dict[str, Any]:
    """§7 environment record plus the ASL acquisition facts of §10.3 (P03 installability)."""
    library = find_library("pynumero_ASL")
    digest = None
    if library is not None and Path(library).is_file():
        digest = hashlib.sha256(Path(library).read_bytes()).hexdigest()
    return environment_record(
        BACKEND,
        pyomo_version,
        {
            "asl_available": bool(AmplInterface.available()),
            "asl_library_path": library,
            "asl_library_sha256": digest,
            "asl_acquisition": (
                "libpynumero_ASL.so was built with `pyomo build-extensions` (setuptools, cmake and "
                "a C/C++ compiler in the venv); `pyomo download-extensions` does not provide it on "
                "this platform. APPSI does not build for lack of pybind11 and is not used by this "
                "route (§10.3)"
            ),
            "scipy_version": scipy_version,
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        },
    )


def metadata_document() -> dict[str, Any]:
    """`CompiledProblemMetadata` for this route (§10.4, A19)."""
    return metadata_payload(
        model_version=MODEL_VERSION,
        form=FORM,
        backend=BACKEND,
        backend_version=pyomo_version,
        variable_ids=VARIABLE_IDS,
        equation_ids=EQUATION_IDS,
        column_scales=COLUMN_SCALES,
        row_scales=ROW_SCALES,
        capabilities={
            "jacobian": "exact_sparse_csc",
            "jvp": "absent",
            "vjp": "absent",
            "hessian": "absent",
        },
        callback_blocks=[
            {
                "name": "K",
                "inputs": ["T", "P"],
                "outputs": [f"lnK_{c}" for c in COMPONENTS],
                "declared_jacobian_nnz": KValueBlock.declared_jacobian_nnz,
                "declared_shape": list(KValueBlock.declared_shape),
                "declared_dense": True,
            },
            {
                "name": "H",
                "inputs": [f"l_{c}" for c in COMPONENTS] + ["T", "P"],
                "outputs": [f"H_{c}" for c in COMPONENTS],
                "declared_jacobian_nnz": EnthalpyBlock.declared_jacobian_nnz,
                "declared_shape": list(EnthalpyBlock.declared_shape),
                "declared_dense": False,
            },
        ],
    )


def run_all(processes: int, repetitions: int, warmup: int) -> int:
    """Produce the whole result set under `spikes/p02/results/pyomo/`."""
    writer = ResultWriter(BACKEND)
    environment = environment_document()
    writer.write("environment.json", environment)
    if not environment["asl_available"]:
        print(
            "libpynumero_ASL is not available; only environment.json was written", file=sys.stderr
        )
        return 1

    writer.write("metadata.json", metadata_document())
    states = load_states()
    initial_x = states[INITIAL_STATE_ID].x_l
    directions = load_directions()

    patterns: dict[str, tuple[tuple[str, str], ...]] = {}
    counter_records: dict[str, Any] = {}
    block_records: dict[str, Any] = {}
    directional_records: dict[str, Any] = {}
    block_raw_records: dict[str, Any] = {}
    directional_stencils: list[dict[str, Any]] = []
    directional_products: list[dict[str, Any]] = []
    jvp_records: dict[str, Any] = {}
    reference: CompiledLForm | None = None
    reference_matrix: CanonicalCsc | None = None

    for state_id in EVALUATION_ORDER:
        state = states[state_id]
        compiled = compile_l_form(state, initial_x)
        compile_counts = compiled.counters.snapshot()
        result = evaluate_state(compiled, state)
        writer.write_state(state_id, FORM, "residual", result.residual)
        writer.write_state(state_id, FORM, "jacobian", result.jacobian)

        record: dict[str, Any] = dict(result.counters)
        record["compile_phase"] = compile_counts
        auxiliary: dict[str, Any] = {}

        if result.matrix is not None:
            patterns[state_id] = tuple(sorted(result.matrix.entries()))
            jvp_records[state_id] = jvp_vjp_record(result.matrix, directions)
            directional_products.append(directional_product_record(state_id, jvp_records[state_id]))

        before = compiled.counters.snapshot()
        if state.expect_domain_error:
            block_records[state_id] = {
                "status": STATUS_INVALID_TRIAL_STATE,
                "message": result.residual["message"],
            }
        else:
            compiled.nlp.set_primals(compiled.native_primal_vector(state.x_l))
            run_stencil = state_id in FD_STATES
            k_record, k_raw = block_probe(compiled.k_block, "K", run_stencil, FD_STEPS_K)
            h_record, h_raw = block_probe(compiled.h_block, "H", run_stencil, FD_STEPS_H)
            block_records[state_id] = {"status": STATUS_OK, "K": k_record, "H": h_record}
            if k_raw is not None and h_raw is not None:
                block_raw_records[state_id] = {"blockK": k_raw, "blockH": h_raw}
        auxiliary["block_probe"] = counter_delta(before, compiled.counters.snapshot())

        if state_id in FD_STATES:
            before = compiled.counters.snapshot()
            derivative, samples = directional_derivative(compiled, state, directions["u_L"])
            directional_records[state_id] = {"finite_difference": derivative}
            directional_stencils.append(
                {
                    "state_id": state_id,
                    "form": FORM,
                    "epsilon": DIRECTIONAL_EPSILON,
                    "offsets": list(FD_OFFSETS),
                    "direction": list(directions["u_L"]),
                    "column_scales": [COLUMN_SCALES[name] for name in VARIABLE_IDS],
                    "samples": samples,
                }
            )
            auxiliary["directional_derivative"] = counter_delta(
                before, compiled.counters.snapshot()
            )

        record["auxiliary_phases"] = auxiliary
        counter_records[state_id] = record
        if state_id == INITIAL_STATE_ID:
            reference = compiled
            reference_matrix = result.matrix

    if reference is None or reference_matrix is None:
        raise RuntimeError(f"the reference state {INITIAL_STATE_ID} did not produce a matrix")

    writer.write("block_records.json", block_raw_records)
    writer.write("directional_stencils.json", directional_stencils)
    writer.write("directional_products.json", directional_products)
    writer.write("second_order.json", second_order_probe(reference, states[INITIAL_STATE_ID]))
    writer.write(
        "source_map_example.json",
        source_map_example(reference, states[INITIAL_STATE_ID], reference_matrix),
    )
    writer.write("raw_structure.json", raw_structure_record(reference, reference_matrix, patterns))
    writer.write(
        "blocks.json",
        {
            "specification": "§3.1, §3.2; A02, A04, A05, A06, A07",
            "finite_difference_states": list(FD_STATES),
            "note": (
                "values and Jacobians are read from the block objects after nlp.set_primals, i.e. "
                "through the backend's own set_input_values; the stencil calls are made after the "
                "A18 per-call counters are recorded and their cost is in "
                "callback_counts.json -> per_state -> auxiliary_phases"
            ),
            "states": block_records,
        },
    )
    writer.write(
        "directional_derivative.json",
        {
            "specification": "A15",
            "epsilon": DIRECTIONAL_EPSILON,
            "stencil": "five-point fourth-order central",
            "direction": "u_L of §5, applied as D_c u_L with the §2.4 column scales",
            "u_L": directions["u_L"],
            "equation_ids": list(EQUATION_IDS),
            "states": directional_records,
        },
    )
    writer.write(
        "jvp_vjp.json",
        {
            "specification": "A16",
            "capabilities": {"jvp": "absent", "vjp": "absent"},
            "status": "not_applicable",
            "reason": (
                "PyNumero's grey-box route exposes no forward or reverse directional product; the "
                "scalars below come from the exported assembled matrix and are trivially exact, "
                "recorded as a fact and not as evidence (§10.3, A16)"
            ),
            "states": jvp_records,
        },
    )
    writer.write(
        "i_form.json",
        {
            "form": "I",
            "status": "not_applicable",
            "reason": "grey-box outputs are NLP variables; no inline composition mechanism",
            "specification": "§4.3 level 3, §10.3",
            "note": (
                "the I-form matrix for this route is obtained by the exact Schur elimination of "
                "A14 from the exported L-form; the harness assembles no I-form and reports none"
            ),
        },
    )

    timings = {
        "M01_import_time": measure_import_time(processes),
        "M02_M04_M07_compile": measure_compile_and_first_call(processes),
        "M05_evaluation_time": measure_evaluation_time(
            reference, states[INITIAL_STATE_ID], repetitions, warmup
        ),
        "M08_structure_size": structure_size(reference_matrix),
    }
    writer.write("timings.json", timings)
    writer.write("memory.json", {"M06_memory": measure_memory_profile(processes)})
    writer.write(
        "callback_counts.json",
        {
            "blocks": ["K", "H"],
            "protocol": (
                "a call is one invocation of the block's Python value or Jacobian method (§3.3); "
                "residual and jacobian counts are deltas across one boundary call (A18), "
                "compile_phase is the count accumulated by PyomoNLPWithGreyBoxBlocks construction "
                "(M07), and auxiliary_phases are the harness's own block and stencil probes, which "
                "are not part of A18"
            ),
            "M07_compile_phase_fresh_process": timings["M02_M04_M07_compile"][
                "compile_phase_counters"
            ],
            "per_state": counter_records,
        },
    )
    print(f"wrote {writer.directory}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P02 Pyomo/PyNumero harness")
    parser.add_argument("--mode", choices=("run", "compile"), default="run")
    parser.add_argument("--processes", type=int, default=5)
    parser.add_argument("--repetitions", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    arguments = parser.parse_args(argv)
    if arguments.mode == "compile":
        print(json.dumps(run_compile_child()))
        return 0
    return run_all(arguments.processes, arguments.repetitions, arguments.warmup)


if __name__ == "__main__":
    raise SystemExit(main())
