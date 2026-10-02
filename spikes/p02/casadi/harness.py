"""P02 CasADi harness: the SYN-001 flash subsystem through opaque sparse callbacks.

Specification: `docs/derivations/P02-composition-spec.md`, §2 (subsystem), §3 (blocks), §5
(states), §7 (measurements), §8 (second order), §10.2 (CasADi constructs), §10.4 (envelope).

The block formulas are implemented here from specification §2.3 and are deliberately *not*
imported from `benchmarks.p02.expected`: that module is the judge's independent expectation.

Run through `spikes/p02/casadi/run.sh`, which uses `.venv-casadi`.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tracemalloc
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import casadi as ca
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from spikes.p02.common import (  # noqa: E402
    EVALUATION_ORDER,
    STATUS_INVALID_TRIAL_STATE,
    STATUS_OK,
    CounterSet,
    ResultWriter,
    StateInput,
    canonical_csc,
    environment_record,
    jacobian_payload,
    load_directions,
    load_states,
    measure_memory,
    metadata_payload,
    repeat_microseconds,
    residual_payload,
    timed,
)

# --- constants and block formulas (specification §2.2, §2.3) -----------------------------------

R = 8.31446261815324
T_REF = 300.0
P_REF = 100000.0
C_P = 100.0
T_BOIL = (320.0, 360.0, 400.0)
L_VAP = (25000.0, 30000.0, 35000.0)
V_MOLAR = (1e-4, 1e-4, 1e-4)
COMPONENTS = ("A", "B", "C")
T_MIN, T_MAX, P_MIN, P_MAX = 280.0, 440.0, 50000.0, 200000.0

VARIABLES_L = (
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
EQUATIONS_L = (
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
VARIABLES_I = ("v_A", "v_B", "v_C", "l_A", "l_B", "l_C", "V", "L", "T", "P", "Q")
EQUATIONS_I = (
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "energy",
    "tspec",
    "pspec",
)

COLUMN_SCALES = {
    **{f"{prefix}_{c}": 3.0 for prefix in ("v", "l") for c in COMPONENTS},
    "V": 3.0,
    "L": 3.0,
    **{f"lnK_{c}": 1.0 for c in COMPONENTS},
    **{f"hL_{c}": 1e5 for c in COMPONENTS},
    "T": 100.0,
    "P": 1e5,
    "Q": 1e5,
}
ROW_SCALES = {
    **{f"bal_{c}": 3.0 for c in COMPONENTS},
    "Vdef": 3.0,
    "Ldef": 3.0,
    **{f"eq_{c}": 9.0 for c in COMPONENTS},
    **{f"kdef_{c}": 1.0 for c in COMPONENTS},
    **{f"hdef_{c}": 1e5 for c in COMPONENTS},
    "energy": 1e5,
    "tspec": 100.0,
    "pspec": 1e5,
}


class DomainError(ValueError):
    """A state outside the closed SYN-001 domain (specification §2.2)."""


def check_domain(temperature: float, pressure: float) -> None:
    if not T_MIN <= temperature <= T_MAX:
        raise DomainError(f"temperature {temperature!r} K outside [{T_MIN}, {T_MAX}] K")
    if not P_MIN <= pressure <= P_MAX:
        raise DomainError(f"pressure {pressure!r} Pa outside [{P_MIN}, {P_MAX}] Pa")


def ln_k_values(temperature: float, pressure: float) -> list[float]:
    check_domain(temperature, pressure)
    return [
        math.log(P_REF / pressure)
        + (L_VAP[i] / R) * (1.0 / T_BOIL[i] - 1.0 / temperature)
        + V_MOLAR[i] * (pressure - P_REF) / (R * temperature)
        for i in range(3)
    ]


def ln_k_jacobian(temperature: float, pressure: float) -> list[tuple[int, int, float]]:
    """Declared-dense 3x2 Jacobian of block K, as (row, col, value) triples."""
    check_domain(temperature, pressure)
    triples: list[tuple[int, int, float]] = []
    for i in range(3):
        d_t = (L_VAP[i] - V_MOLAR[i] * (pressure - P_REF)) / (R * temperature * temperature)
        d_p = -1.0 / pressure + V_MOLAR[i] / (R * temperature)
        triples.append((i, 0, d_t))
        triples.append((i, 1, d_p))
    return triples


def enthalpy_flows(flows: Sequence[float], temperature: float, pressure: float) -> list[float]:
    check_domain(temperature, pressure)
    return [
        flows[i] * (C_P * (temperature - T_REF) + V_MOLAR[i] * (pressure - P_REF)) for i in range(3)
    ]


def enthalpy_jacobian(
    flows: Sequence[float], temperature: float, pressure: float
) -> list[tuple[int, int, float]]:
    """Declared-sparse 3x5 Jacobian of block H: exactly 9 entries (specification §3.2)."""
    check_domain(temperature, pressure)
    triples: list[tuple[int, int, float]] = []
    for i in range(3):
        triples.append((i, i, C_P * (temperature - T_REF) + V_MOLAR[i] * (pressure - P_REF)))
        triples.append((i, 3, flows[i] * C_P))
        triples.append((i, 4, flows[i] * V_MOLAR[i]))
    return triples


def _fill(sparsity: ca.Sparsity, triples: Sequence[tuple[int, int, float]]) -> ca.DM:
    """Fill a sparse DM by (row, col).

    CasADi stores values column-major, so assigning a value vector in triplet declaration order
    silently permutes the matrix. Assigning by index pair cannot.
    """
    matrix = ca.DM(sparsity)
    for row, col, value in triples:
        matrix[row, col] = value
    return matrix


# --- callbacks (specification §3, §10.2) -------------------------------------------------------


class _JacobianCallback(ca.Callback):
    """The Jacobian of a block, itself an opaque Callback (specification §3)."""

    def __init__(self, name: str, owner: _Block) -> None:
        ca.Callback.__init__(self)
        self.owner = owner
        self.construct(name, {"enable_fd": False})

    def get_n_in(self) -> int:
        return 2

    def get_n_out(self) -> int:
        return 1

    def get_sparsity_in(self, index: int) -> ca.Sparsity:
        return (
            ca.Sparsity.dense(self.owner.n_in, 1)
            if index == 0
            else ca.Sparsity.dense(self.owner.n_out, 1)
        )

    def get_sparsity_out(self, index: int) -> ca.Sparsity:
        del index
        return self.owner.jacobian_sparsity

    def eval(self, arg: Sequence[ca.DM]) -> list[ca.DM]:
        inputs = [float(arg[0][i]) for i in range(self.owner.n_in)]
        self.owner.counters.record_jacobian()
        try:
            triples = self.owner.jacobian_triples(inputs)
        except DomainError as error:
            self.owner.domain_error = str(error)
            raise
        return [_fill(self.owner.jacobian_sparsity, triples)]


class _Block(ca.Callback):
    """A property block: opaque value and opaque declared-sparse first derivative."""

    def __init__(
        self,
        name: str,
        counters: CounterSet,
        n_in: int,
        n_out: int,
        symbolic_jacobian: bool = False,
    ) -> None:
        ca.Callback.__init__(self)
        self.block_name = name
        self.counters = counters.block(name)
        self.n_in_count = n_in
        self.n_out_count = n_out
        self.symbolic_jacobian = symbolic_jacobian
        self.domain_error: str | None = None
        self._jacobian: _JacobianCallback | ca.Function | None = None
        self.construct(name, {"enable_fd": False})

    # geometry -----------------------------------------------------------------------------
    @property
    def n_in(self) -> int:
        return self.n_in_count

    @property
    def n_out(self) -> int:
        return self.n_out_count

    @property
    def jacobian_sparsity(self) -> ca.Sparsity:
        raise NotImplementedError

    def values(self, inputs: Sequence[float]) -> list[float]:
        raise NotImplementedError

    def jacobian_triples(self, inputs: Sequence[float]) -> list[tuple[int, int, float]]:
        raise NotImplementedError

    # casadi interface ---------------------------------------------------------------------
    def get_n_in(self) -> int:
        return 1

    def get_n_out(self) -> int:
        return 1

    def get_sparsity_in(self, index: int) -> ca.Sparsity:
        del index
        return ca.Sparsity.dense(self.n_in, 1)

    def get_sparsity_out(self, index: int) -> ca.Sparsity:
        del index
        return ca.Sparsity.dense(self.n_out, 1)

    def eval(self, arg: Sequence[ca.DM]) -> list[ca.DM]:
        inputs = [float(arg[0][i]) for i in range(self.n_in)]
        self.counters.record_value()
        try:
            return [ca.DM(self.values(inputs))]
        except DomainError as error:
            self.domain_error = str(error)
            raise

    def has_jacobian(self) -> bool:
        return True

    def has_jac_sparsity(self, oind: int, iind: int) -> bool:
        """Declare that this block knows its own Jacobian sparsity.

        Without this, CasADi propagates the *dependency* structure of an opaque Callback, which
        assumes every output depends on every input, and the block's declared structural zeros
        reappear as stored zeros in the assembled system (measured: 66 entries instead of 60).
        """
        del oind, iind
        return True

    def get_jac_sparsity(self, oind: int, iind: int, symmetric: bool) -> ca.Sparsity:
        del oind, iind, symmetric
        return self.jacobian_sparsity

    def symbolic_jacobian_function(self, name: str) -> ca.Function:
        """A differentiable `Function` of the closed-form derivatives (specification §8, H5)."""
        raise NotImplementedError

    def get_jacobian(
        self, name: str, inames: Sequence[str], onames: Sequence[str], opts: dict[str, Any]
    ) -> ca.Callback | ca.Function:
        del inames, onames, opts
        if self._jacobian is None:
            self._jacobian = (
                self.symbolic_jacobian_function(name)
                if self.symbolic_jacobian
                else _JacobianCallback(name, self)
            )
        return self._jacobian


class KBlock(_Block):
    """Block K: (T, P) -> (lnK_A, lnK_B, lnK_C); Jacobian declared dense 3x2 (§3.1)."""

    def __init__(self, counters: CounterSet, symbolic_jacobian: bool = False) -> None:
        super().__init__("blockK", counters, n_in=2, n_out=3, symbolic_jacobian=symbolic_jacobian)

    def symbolic_jacobian_function(self, name: str) -> ca.Function:
        theta = ca.MX.sym("theta", 2)
        nominal = ca.MX.sym("nominal_out", 3)
        temperature, pressure = theta[0], theta[1]
        columns = []
        for i in range(3):
            d_t = (L_VAP[i] - V_MOLAR[i] * (pressure - P_REF)) / (R * temperature * temperature)
            d_p = -1.0 / pressure + V_MOLAR[i] / (R * temperature)
            columns.append(ca.horzcat(d_t, d_p))
        return ca.Function(name, [theta, nominal], [ca.vertcat(*columns)])

    @property
    def jacobian_sparsity(self) -> ca.Sparsity:
        return ca.Sparsity.dense(3, 2)

    def values(self, inputs: Sequence[float]) -> list[float]:
        return ln_k_values(inputs[0], inputs[1])

    def jacobian_triples(self, inputs: Sequence[float]) -> list[tuple[int, int, float]]:
        return ln_k_jacobian(inputs[0], inputs[1])


class HBlock(_Block):
    """Block H: (l_A, l_B, l_C, T, P) -> component liquid enthalpy flows; 9 nonzeros (§3.2)."""

    def __init__(self, counters: CounterSet, symbolic_jacobian: bool = False) -> None:
        super().__init__("blockH", counters, n_in=5, n_out=3, symbolic_jacobian=symbolic_jacobian)

    def symbolic_jacobian_function(self, name: str) -> ca.Function:
        zeta = ca.MX.sym("zeta", 5)
        nominal = ca.MX.sym("nominal_out", 3)
        flows = [zeta[i] for i in range(3)]
        temperature, pressure = zeta[3], zeta[4]
        matrix = ca.MX(3, 5)
        for i in range(3):
            matrix[i, i] = C_P * (temperature - T_REF) + V_MOLAR[i] * (pressure - P_REF)
            matrix[i, 3] = flows[i] * C_P
            matrix[i, 4] = flows[i] * V_MOLAR[i]
        return ca.Function(name, [zeta, nominal], [matrix])

    @property
    def jacobian_sparsity(self) -> ca.Sparsity:
        rows = [0, 1, 2, 0, 1, 2, 0, 1, 2]
        cols = [0, 1, 2, 3, 3, 3, 4, 4, 4]
        return ca.Sparsity.triplet(3, 5, rows, cols)

    def values(self, inputs: Sequence[float]) -> list[float]:
        return enthalpy_flows(inputs[0:3], inputs[3], inputs[4])

    def jacobian_triples(self, inputs: Sequence[float]) -> list[tuple[int, int, float]]:
        return enthalpy_jacobian(inputs[0:3], inputs[3], inputs[4])


# --- the compiled forms (specification §2.4, §2.6) ---------------------------------------------


@dataclass
class CompiledForm:
    """One compiled form and everything the harness needs from it."""

    form: str
    variables: tuple[str, ...]
    equations: tuple[str, ...]
    residual: ca.Function
    jacobian: ca.Function
    jvp: ca.Function
    vjp: ca.Function
    symbols: dict[str, ca.MX]
    expression: ca.MX
    vector: ca.MX
    blocks: dict[str, _Block]


def _residual_expressions(
    symbols: dict[str, ca.MX], blocks: dict[str, _Block], parameters: dict[str, float], form: str
) -> dict[str, ca.MX]:
    v = [symbols[f"v_{c}"] for c in COMPONENTS]
    liquid = [symbols[f"l_{c}"] for c in COMPONENTS]
    total_v, total_l = symbols["V"], symbols["L"]
    temperature, pressure, duty = symbols["T"], symbols["P"], symbols["Q"]
    feed = parameters["feed"]

    k_call = blocks["blockK"](ca.vertcat(temperature, pressure))
    h_call = blocks["blockH"](ca.vertcat(liquid[0], liquid[1], liquid[2], temperature, pressure))

    if form == "L":
        ln_k = [symbols[f"lnK_{c}"] for c in COMPONENTS]
        h_lifted = [symbols[f"hL_{c}"] for c in COMPONENTS]
    else:
        ln_k = [k_call[i] for i in range(3)]
        h_lifted = [h_call[i] for i in range(3)]

    rows: dict[str, ca.MX] = {}
    for i, c in enumerate(COMPONENTS):
        rows[f"bal_{c}"] = v[i] + liquid[i] - feed[i]
    rows["Vdef"] = total_v - (v[0] + v[1] + v[2])
    rows["Ldef"] = total_l - (liquid[0] + liquid[1] + liquid[2])
    for i, c in enumerate(COMPONENTS):
        rows[f"eq_{c}"] = v[i] * total_l - ca.exp(ln_k[i]) * liquid[i] * total_v
    if form == "L":
        for i, c in enumerate(COMPONENTS):
            rows[f"kdef_{c}"] = symbols[f"lnK_{c}"] - k_call[i]
        for i, c in enumerate(COMPONENTS):
            rows[f"hdef_{c}"] = symbols[f"hL_{c}"] - h_call[i]
    vapor_enthalpy = [C_P * (temperature - T_REF) + L_VAP[i] for i in range(3)]
    rows["energy"] = (
        sum(v[i] * vapor_enthalpy[i] for i in range(3))
        + sum(h_lifted[i] for i in range(3))
        - parameters["h_feed"]
        - duty
    )
    rows["tspec"] = temperature - parameters["t_spec"]
    rows["pspec"] = pressure - parameters["p_spec"]
    return rows


def compile_form(
    form: str, state: StateInput, counters: CounterSet, symbolic_jacobian: bool = False
) -> CompiledForm:
    """Build the residual and Jacobian Functions of one form (specification §10.2)."""
    variables = VARIABLES_L if form == "L" else VARIABLES_I
    equations = EQUATIONS_L if form == "L" else EQUATIONS_I
    symbols = {name: ca.MX.sym(name) for name in variables}
    blocks: dict[str, _Block] = {
        "blockK": KBlock(counters, symbolic_jacobian),
        "blockH": HBlock(counters, symbolic_jacobian),
    }
    parameters = {
        "feed": state.feed,
        "h_feed": state.h_feed,
        "t_spec": state.t_spec,
        "p_spec": state.p_spec,
    }
    rows = _residual_expressions(symbols, blocks, parameters, form)
    vector = ca.vertcat(*[symbols[name] for name in variables])
    expression = ca.vertcat(*[rows[name] for name in equations])
    residual = ca.Function("residual", [vector], [expression])
    jacobian = ca.Function("jacobian", [vector], [ca.jacobian(expression, vector)])
    seed = ca.MX.sym("seed", len(variables))
    adjoint_seed = ca.MX.sym("adjoint_seed", len(equations))
    jvp = ca.Function("jvp", [vector, seed], [ca.jtimes(expression, vector, seed, False)])
    vjp = ca.Function(
        "vjp", [vector, adjoint_seed], [ca.jtimes(expression, vector, adjoint_seed, True)]
    )
    return CompiledForm(
        form=form,
        variables=variables,
        equations=equations,
        residual=residual,
        jacobian=jacobian,
        jvp=jvp,
        vjp=vjp,
        symbols=symbols,
        expression=expression,
        vector=vector,
        blocks=blocks,
    )


# --- evaluation (specification §6, §10.4) ------------------------------------------------------

SOURCE_MAP_ENTRIES = (("eq_B", "lnK_B"), ("kdef_B", "T"), ("hdef_C", "l_C"))


def _domain_message(form: CompiledForm) -> str:
    for block in form.blocks.values():
        if block.domain_error:
            return f"{block.block_name}: {block.domain_error}"
    return ""


def _clear_domain_errors(form: CompiledForm) -> None:
    for block in form.blocks.values():
        block.domain_error = None


def _named_entries(matrix: ca.DM, form: CompiledForm) -> dict[tuple[str, str], float]:
    rows, cols = matrix.sparsity().get_triplet()
    values = matrix.nonzeros()
    return {
        (form.equations[row], form.variables[col]): float(value)
        for row, col, value in zip(rows, cols, values, strict=True)
    }


def evaluate_state(
    form: CompiledForm, state: StateInput, counters: CounterSet, writer: ResultWriter
) -> dict[str, Any]:
    """Evaluate one state and write its residual and Jacobian payloads."""
    x_map = state.x_l if form.form == "L" else state.x_i
    x = ca.DM([x_map[name] for name in form.variables])
    phase = state.oracle_phase_state

    _clear_domain_errors(form)
    counters.reset()
    try:
        evaluated = form.residual(x)
        residual_values: list[float] | None = [
            float(evaluated[i]) for i in range(len(form.equations))
        ]
        status, message = STATUS_OK, ""
    except RuntimeError as error:
        residual_values, status = None, STATUS_INVALID_TRIAL_STATE
        message = _domain_message(form) or str(error).splitlines()[0]
    residual_counters = counters.snapshot()
    writer.write_state(
        state.state_id,
        form.form,
        "residual",
        residual_payload(
            status=status,
            model_version=f"P02-{form.form}-form-v1",
            x=x_map,
            variable_ids=form.variables,
            equation_ids=form.equations,
            values=residual_values,
            counters=residual_counters,
            phase_signature=phase,
            message=message,
        ),
    )

    _clear_domain_errors(form)
    counters.reset()
    matrix = None
    source_map: list[dict[str, Any]] = []
    try:
        jacobian_dm = form.jacobian(x)
        entries = _named_entries(jacobian_dm, form)
        matrix = canonical_csc(entries, form.equations, form.variables)
        jacobian_status, jacobian_message = STATUS_OK, ""
        if state.state_id == "S1":
            csc_index = {}
            for column, col_id in enumerate(matrix.col_ids):
                for k in range(matrix.indptr[column], matrix.indptr[column + 1]):
                    csc_index[(matrix.row_ids[matrix.indices[k]], col_id)] = k
            for row_id, col_id in SOURCE_MAP_ENTRIES:
                if (row_id, col_id) in entries:
                    source_map.append(
                        {
                            "csc_index": csc_index[(row_id, col_id)],
                            "row_id": row_id,
                            "col_id": col_id,
                            "native_row": f"{form.residual.name()}[{form.equations.index(row_id)}]",
                            "native_col": col_id,
                            "value": entries[(row_id, col_id)],
                        }
                    )
    except RuntimeError as error:
        jacobian_status = STATUS_INVALID_TRIAL_STATE
        jacobian_message = _domain_message(form) or str(error).splitlines()[0]
    jacobian_counters = counters.snapshot()
    writer.write_state(
        state.state_id,
        form.form,
        "jacobian",
        jacobian_payload(
            status=jacobian_status,
            model_version=f"P02-{form.form}-form-v1",
            x=x_map,
            variable_ids=form.variables,
            matrix=matrix,
            counters=jacobian_counters,
            phase_signature=phase,
            pattern_provenance="backend-declared",
            source_map=source_map,
            message=jacobian_message,
        ),
    )
    return {
        "state_id": state.state_id,
        "form": form.form,
        "residual_status": status,
        "jacobian_status": jacobian_status,
        "residual_counters": residual_counters,
        "jacobian_counters": jacobian_counters,
        "nnz": 0 if matrix is None else matrix.nnz,
    }


DIRECTIONAL_EPSILON = 1e-3
DIRECTIONAL_OFFSETS = (-2, -1, 1, 2)


def directional_stencil(
    form: CompiledForm, state: StateInput, directions: dict[str, tuple[float, ...]]
) -> dict[str, Any]:
    """Residual samples along `x + ε D_c u` for the judge's fourth-order check (A15)."""
    x_map = state.x_l if form.form == "L" else state.x_i
    base = [x_map[name] for name in form.variables]
    direction = directions[f"u_{form.form}"]
    scales = [COLUMN_SCALES[name] for name in form.variables]
    samples: dict[str, list[float]] = {}
    for offset in DIRECTIONAL_OFFSETS:
        step = offset * DIRECTIONAL_EPSILON
        point = ca.DM([base[i] + step * scales[i] * direction[i] for i in range(len(base))])
        evaluated = form.residual(point)
        samples[str(offset)] = [float(evaluated[i]) for i in range(len(form.equations))]
    return {
        "state_id": state.state_id,
        "form": form.form,
        "epsilon": DIRECTIONAL_EPSILON,
        "offsets": list(DIRECTIONAL_OFFSETS),
        "direction": list(direction),
        "column_scales": scales,
        "samples": samples,
    }


def directional_products(
    form: CompiledForm, state: StateInput, directions: dict[str, tuple[float, ...]]
) -> dict[str, Any]:
    """Forward and reverse products and the vᵀ(Ju) = (Jᵀv)ᵀu identity (A16)."""
    x_map = state.x_l if form.form == "L" else state.x_i
    x = ca.DM([x_map[name] for name in form.variables])
    u = ca.DM(list(directions[f"u_{form.form}"]))
    v = ca.DM(list(directions[f"v_{form.form}"]))
    forward = form.jvp(x, u)
    reverse = form.vjp(x, v)
    assembled = form.jacobian(x)
    left = float(ca.dot(v, forward))
    right = float(ca.dot(reverse, u))
    scale = float(ca.norm_1(ca.fabs(v).T @ ca.fabs(assembled) @ ca.fabs(u)))
    return {
        "state_id": state.state_id,
        "form": form.form,
        "jvp": [float(value) for value in forward.nonzeros()],
        "vjp": [float(value) for value in reverse.nonzeros()],
        "jvp_minus_assembled_max": float(ca.mmax(ca.fabs(forward - assembled @ u))),
        "vjp_minus_assembled_max": float(ca.mmax(ca.fabs(reverse - assembled.T @ v))),
        "v_dot_Ju": left,
        "JTv_dot_u": right,
        "identity_abs_difference": abs(left - right),
        "identity_scale": scale,
    }


# --- block-level exports (specification §6 A02, A04, A05, A06, A07) ----------------------------

#: Finite-difference steps per block input (specification §6 A04, A07).
STENCIL_STEPS = {
    "blockK": {0: 0.1, 1: 100.0},
    # Block H's pressure step is 5 000 Pa, not 1e4: at S2 (P = 60 000 Pa) a 1e4 step would evaluate
    # at 40 000 Pa, outside the closed domain, and the only way to make that work would be to drop
    # block H's domain guard (specification §2.2, A07, amended).
    "blockH": {0: 0.01, 1: 0.01, 2: 0.01, 3: 0.1, 4: 5000.0},
}
STENCIL_OFFSETS = (-2, -1, 1, 2)


def _block_inputs(block_name: str, x_map: dict[str, float]) -> list[float]:
    if block_name == "blockK":
        return [x_map["T"], x_map["P"]]
    return [x_map["l_A"], x_map["l_B"], x_map["l_C"], x_map["T"], x_map["P"]]


def block_records(form: CompiledForm, state: StateInput) -> dict[str, Any]:
    """Block values and declared Jacobians, evaluated *through CasADi*, plus stencil samples.

    The judge differences the stencil samples itself (A04, A07): the harness never computes the
    comparison it is judged by.
    """
    x_map = state.x_l if form.form == "L" else state.x_i
    records: dict[str, Any] = {}
    for name, block in form.blocks.items():
        inputs = _block_inputs(name, x_map)
        jacobian_function = block.jacobian()
        values = block(ca.DM(inputs))
        jacobian = jacobian_function(ca.DM(inputs), values)
        rows, cols = jacobian.sparsity().get_triplet()
        entries = {
            f"{row}|{col}": float(value)
            for row, col, value in zip(rows, cols, jacobian.nonzeros(), strict=True)
        }
        stencil: dict[str, dict[str, list[float]]] = {}
        for index, step in STENCIL_STEPS[name].items():
            samples: list[float] = []
            for offset in STENCIL_OFFSETS:
                perturbed = list(inputs)
                perturbed[index] = inputs[index] + offset * step
                sample = block(ca.DM(perturbed))
                samples.extend(float(sample[i]) for i in range(block.n_out))
            stencil[str(index)] = {"step": [step], "samples": samples}
        records[name] = {
            "inputs": inputs,
            "values": [float(values[i]) for i in range(block.n_out)],
            "jacobian_entries": entries,
            "jacobian_nnz": jacobian.sparsity().nnz(),
            "declared_shape": [block.n_out, block.n_in],
            "stencil": stencil,
            "stencil_offsets": list(STENCIL_OFFSETS),
        }
    return records


# --- second-order probe (specification §8) -----------------------------------------------------

SECOND_ORDER_REQUESTS = (
    ("H1", "L", "eq_A", (("v_A", "L"), ("lnK_A", "lnK_A"))),
    ("H2", "L", "kdef_A", (("T", "T"), ("T", "P"), ("P", "P"))),
    ("H3", "L", "hdef_A", (("l_A", "T"), ("l_A", "P"))),
    ("H4", "I", "eq_A", (("T", "l_A"), ("T", "T"))),
)


def second_order_probe(
    forms: dict[str, CompiledForm], state: StateInput, symbolic: bool
) -> list[dict[str, Any]]:
    """Request second-order information and record exactly what happened (specification §8)."""
    records: list[dict[str, Any]] = []
    for probe_id, form_name, row_id, pairs in SECOND_ORDER_REQUESTS:
        form = forms[form_name]
        x_map = state.x_l if form_name == "L" else state.x_i
        x = ca.DM([x_map[name] for name in form.variables])
        multiplier = ca.DM.zeros(len(form.equations))
        multiplier[form.equations.index(row_id)] = 1.0
        record: dict[str, Any] = {
            "probe_id": probe_id,
            "form": form_name,
            "row": row_id,
            "symbolic_block_jacobian": symbolic,
            "entries": {},
        }
        try:
            scalar = ca.dot(ca.DM(multiplier), form.expression)
            hessian_expression, _ = ca.hessian(scalar, form.vector)
            hessian_function = ca.Function("hessian_probe", [form.vector], [hessian_expression])
            hessian_value = hessian_function(x)
            record["outcome"] = "returned"
            for first, second in pairs:
                i = form.variables.index(first)
                j = form.variables.index(second)
                record["entries"][f"d2/d{first}d{second}"] = float(hessian_value[i, j])
        except (RuntimeError, NotImplementedError) as error:
            record["outcome"] = "raised"
            record["exception_type"] = type(error).__name__
            record["message"] = " ".join(str(error).strip().split())[:1200]
        records.append(record)
    return records


# --- measurements (specification §7) -----------------------------------------------------------


def compile_sample(state: StateInput) -> dict[str, Any]:
    """One fresh-process compile sample: M02, M03, M04, M06, M07."""
    import numpy  # noqa: PLC0415

    baseline_rss = measure_memory()
    sample: dict[str, Any] = {
        "numpy_version": numpy.__version__,
        "rss_after_numpy_mib": baseline_rss,
    }
    sample["rss_after_backend_import_mib"] = measure_memory()

    timings: dict[str, float] = {}
    counters = CounterSet()
    tracemalloc.start()
    with timed(timings, "compile_L_ms"):
        form_l = compile_form("L", state, counters)
    _, peak_l = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    sample["compile_phase_counters_L"] = counters.snapshot()

    counters_i = CounterSet()
    with timed(timings, "compile_I_ms"):
        compile_form("I", state, counters_i)
    sample["compile_phase_counters_I"] = counters_i.snapshot()

    x = ca.DM([state.x_l[name] for name in form_l.variables])
    with timed(timings, "first_residual_ms"):
        form_l.residual(x)
    with timed(timings, "first_jacobian_ms"):
        form_l.jacobian(x)

    sample["timings_ms"] = timings
    sample["tracemalloc_peak_compile_mib"] = peak_l / (1024 * 1024)
    sample["rss_after_compile_mib"] = measure_memory()
    return sample


def evaluation_timing(form: CompiledForm, state: StateInput) -> dict[str, Any]:
    """M05 at two levels, so the two backends are compared on the same work.

    `backend_*` is the call plus construction of the input from the NumPy vector, which is what
    `set_primals` plus evaluation is on the other route. `boundary_*` adds what the
    `CompiledProblem` boundary does with the result: naming the entries and assembling the
    canonical CSC. Reporting only the first would compare a bare function call against another
    route's full boundary.
    """
    x_map = state.x_l if form.form == "L" else state.x_i
    vector = np.array([x_map[name] for name in form.variables], dtype=float)

    def backend_residual() -> None:
        form.residual(ca.DM(vector))

    def backend_jacobian() -> None:
        form.jacobian(ca.DM(vector))

    def boundary_residual() -> None:
        evaluated = form.residual(ca.DM(vector))
        [float(evaluated[i]) for i in range(len(form.equations))]

    def boundary_jacobian() -> None:
        matrix = form.jacobian(ca.DM(vector))
        canonical_csc(_named_entries(matrix, form), form.equations, form.variables)

    return {
        "backend_residual": repeat_microseconds(backend_residual, repetitions=200, warmup=20),
        "backend_jacobian": repeat_microseconds(backend_jacobian, repetitions=200, warmup=20),
        "boundary_residual": repeat_microseconds(boundary_residual, repetitions=200, warmup=20),
        "boundary_jacobian": repeat_microseconds(boundary_jacobian, repetitions=200, warmup=20),
        "note": "backend_* includes constructing the DM from the NumPy state vector; boundary_* "
        "adds the named-entry extraction and canonical CSC assembly the judge reads",
    }


def _run_memory_samples(count: int) -> list[dict[str, Any]]:
    """Spawn `count` staged-import probes (M01, M06): see `memory_probe.py`."""
    probe = Path(__file__).resolve().parent / "memory_probe.py"
    samples: list[dict[str, Any]] = []
    for _ in range(count):
        result = subprocess.run(
            [sys.executable, str(probe)],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        samples.append(json.loads(result.stdout))
    return samples


def _run_compile_samples(count: int) -> list[dict[str, Any]]:
    """Spawn `count` fresh interpreters, each producing one compile sample."""
    samples: list[dict[str, Any]] = []
    for _ in range(count):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--task", "compile-sample"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        samples.append(json.loads(result.stdout))
    return samples


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P02 CasADi harness")
    parser.add_argument("--task", default="main", choices=("main", "compile-sample"))
    parser.add_argument("--compile-samples", type=int, default=5)
    arguments = parser.parse_args(argv)

    states = load_states()
    if arguments.task == "compile-sample":
        print(json.dumps(compile_sample(states["S1"])))
        return 0

    writer = ResultWriter("casadi")
    directions = load_directions()
    counters = CounterSet()
    forms = {name: compile_form(name, states["S1"], counters) for name in ("L", "I")}

    summaries: list[dict[str, Any]] = []
    for state_id in EVALUATION_ORDER:
        state = states[state_id]
        for form_name in ("L", "I"):
            form = compile_form(form_name, state, counters)
            summaries.append(evaluate_state(form, state, counters, writer))

    products = [
        directional_products(
            compile_form(form_name, states[state_id], counters), states[state_id], directions
        )
        for state_id in ("S1", "S2", "S3", "S4", "S5")
        for form_name in ("L", "I")
    ]

    samples = _run_compile_samples(arguments.compile_samples)
    memory_samples = _run_memory_samples(arguments.compile_samples)
    timing_keys = ("compile_L_ms", "compile_I_ms", "first_residual_ms", "first_jacobian_ms")
    aggregated = {
        key: {
            "median_ms": _median([sample["timings_ms"][key] for sample in samples]),
            "min_ms": min(sample["timings_ms"][key] for sample in samples),
            "samples": arguments.compile_samples,
        }
        for key in timing_keys
    }
    evaluation = {
        form_name: evaluation_timing(forms[form_name], states["S1"]) for form_name in ("L", "I")
    }

    writer.write(
        "metadata.json",
        {
            form_name: metadata_payload(
                model_version=f"P02-{form_name}-form-v1",
                form=form_name,
                backend="casadi",
                backend_version=ca.__version__,
                variable_ids=forms[form_name].variables,
                equation_ids=forms[form_name].equations,
                column_scales={k: COLUMN_SCALES[k] for k in forms[form_name].variables},
                row_scales={k: ROW_SCALES[k] for k in forms[form_name].equations},
                capabilities={
                    "jacobian": "exact_sparse_csc",
                    "jvp": "exact",
                    "vjp": "exact",
                    "hessian": "absent",
                },
                callback_blocks=[
                    {
                        "name": "blockK",
                        "inputs": ["T", "P"],
                        "outputs": ["lnK_A", "lnK_B", "lnK_C"],
                        "declared_jacobian_nnz": 6,
                    },
                    {
                        "name": "blockH",
                        "inputs": ["l_A", "l_B", "l_C", "T", "P"],
                        "outputs": ["H_A", "H_B", "H_C"],
                        "declared_jacobian_nnz": 9,
                    },
                ],
            )
            for form_name in ("L", "I")
        },
    )
    writer.write(
        "environment.json",
        environment_record(
            "casadi", ca.__version__, {"asl_required": False, "build_step_required": False}
        ),
    )
    writer.write(
        "timings.json", {"compile": aggregated, "evaluation": evaluation, "samples": samples}
    )
    writer.write(
        "memory.json",
        {
            key: _median([sample[key] for sample in memory_samples])
            for key in (
                "rss_after_numpy_mib",
                "rss_after_backend_import_mib",
                "rss_after_compile_mib",
                "tracemalloc_peak_compile_mib",
            )
        }
        | {
            "import_ms": {
                "numpy": _median([sample["numpy_import_ms"] for sample in memory_samples]),
                "backend": _median([sample["backend_import_ms"] for sample in memory_samples]),
            },
            "samples": memory_samples,
            "note": "measured by memory_probe.py in staged-import subprocesses; the harness "
            "imports the backend at module scope and so cannot measure this in process",
        },
    )
    writer.write(
        "callback_counts.json",
        {
            "per_state": summaries,
            "compile_phase": [
                {
                    "sample": index,
                    "L": sample["compile_phase_counters_L"],
                    "I": sample["compile_phase_counters_I"],
                }
                for index, sample in enumerate(samples)
            ],
        },
    )
    writer.write("directional_products.json", products)
    writer.write(
        "directional_stencils.json",
        [
            directional_stencil(
                compile_form(form_name, states[state_id], counters), states[state_id], directions
            )
            for state_id in ("S1", "S2", "S3", "S4", "S5")
            for form_name in ("L", "I")
        ],
    )
    writer.write(
        "block_records.json",
        {
            state_id: block_records(compile_form("L", states[state_id], counters), states[state_id])
            for state_id in ("S1", "S2", "S3", "S4", "S5")
        },
    )
    writer.write(
        "second_order.json",
        {
            "opaque_blocks": second_order_probe(forms, states["S1"], symbolic=False),
            "supplementary_symbolic_blocks": second_order_probe(
                {
                    name: compile_form(name, states["S1"], CounterSet(), symbolic_jacobian=True)
                    for name in ("L", "I")
                },
                states["S1"],
                symbolic=True,
            ),
            "note": "The supplementary record (specification §8, H5) replaces each block's "
            "opaque Jacobian Callback by a symbolic Function of the same closed forms. It is a "
            "capability fact for K01 and is never mixed with H1-H4.",
        },
    )
    writer.write(
        "source_map_example.json",
        {
            "entries": SOURCE_MAP_ENTRIES,
            "see": "states/S1/jacobian_L.json -> source_map",
        },
    )
    print(f"wrote {writer.directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
