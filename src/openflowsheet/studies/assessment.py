"""Assessment outputs in sensitivity studies; the trust-region hook (E01 design §4.10.1, §4.10.4).

An assessment output `y = G(x, p)` (a cost, an impact, a derived ratio; `assessment/`) is a
function of the certified state and, directly, of the pinned inputs the assessment reads. Its
sensitivity is `dy/dp = ∇ₓG·X + ∂G/∂p`, with `X = dx/dp` the host's.
`assessment_sensitivity` builds it without touching `sensitivity.py`:

1. `program.linearize(x*, {}, outputs, symbolic = request's parameters ∩ the program's)` gives
   `∇ₓG` (outputs x host variables) and `∂G/∂p`;
2. each output with a non-empty `∇ₓG` row becomes an `OutputFunctional` `assessment:<id>` with
   the stored nonzeros as coefficients, appended to the request; `evaluate_sensitivity` runs on
   the host unchanged, so the outputs share its qualification, factorization and modes;
3. the direct term `∂G/∂p` is added to the forward and the adjoint block alike;
4. an output with an empty `∇ₓG` row (every item in `floor`, say) gets `∂G/∂p` alone, labelled
   `STATE_INDEPENDENT`;
5. a refusal of the underlying request propagates unchanged: no host block, every value `None`
   (a state-independent output too, since the state is not qualified); a refused column is
   `None` in the state-dependent rows;
6. every admissibility row with scaled slack ≤ τ_active at x* is listed under
   `regime_bounds_active`, and each output whose closure contains it carries limitation
   `REGIME_BOUNDARY_ACTIVE` (the row beside it): the derivative is one-sided (§4.10.1 erratum
   2026-10-29, E01 review S2). An output's closure is the entries with a row sharing a column of
   `[∇ₓG ∂G/∂p]` with it, the NLP's rule (`studies.nlp.formulation.assessment_closure`); each
   output also records its closure's smallest slack.

`revision_sensitivity_host` is `syn001.host_of` for any revision flowsheet: its spec, the compiled
problem, K03 scales from the spec's kinds, and the alias rows eliminated at `x*` by the
certificate's procedure (`orchestrator/rank.py`, the pressure-shifted second state).

`trf_objective_from_assessment` is the documented route from an assessment output to a
trust-region objective; on day one it refuses `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)` (A37).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.assessment.program import (
    AssessmentProgram,
    Limitation,
    Linearization,
    Refusal,
)
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.rank import eliminate_alias_rows, pressure_shifted_state
from openflowsheet.studies.nlp.verification import TAU_ACTIVE
from openflowsheet.studies.sensitivity import (
    CertificateEvidence,
    OutputFunctional,
    SensitivityBlock,
    SensitivityHost,
    SensitivityRequest,
    SensitivityResult,
    SplitRegime,
    evaluate_sensitivity,
)

__all__ = [
    "OUTPUT_PREFIX",
    "AssessmentSensitivity",
    "assessment_sensitivity",
    "evaluation_context",
    "revision_sensitivity_host",
    "trf_objective_from_assessment",
]

#: The prefix of an assessment output among a study's outputs (`QuadraticExpression`'s names too).
OUTPUT_PREFIX: Final = "assessment:"

Dependence = Literal["STATE_DEPENDENT", "STATE_INDEPENDENT"]


@dataclass(frozen=True)
class AssessmentSensitivity:
    """`dy/dp` of the requested assessment outputs (rows) over the request's parameters
    (columns), forward and/or adjoint as the request's mode; `None` where the host's column, or
    the whole request, is refused. `base` is the host's result for the augmented request (its
    own outputs first, then `assessment:<id>` for every state-dependent output)."""

    outputs: tuple[str, ...]
    parameter_ids: tuple[str, ...]
    scales: Mapping[str, float]
    dependence: Mapping[str, Dependence]
    forward: SensitivityBlock | None
    adjoint: SensitivityBlock | None
    base: SensitivityResult | None
    refusals: tuple[Refusal, ...] = ()
    #: Step 6: `(row, scaled slack)` of every admissibility row with slack ≤ τ_active at x*.
    regime_bounds_active: tuple[tuple[str, float], ...] = ()
    #: Step 6: each output's closure's smallest scaled slack, `None` when its closure is empty.
    regime_slack: Mapping[str, float | None] = dataclasses.field(default_factory=dict)
    limitations: tuple[Limitation, ...] = ()

    def as_document(self) -> dict[str, Any]:
        return {
            "outputs": [
                {
                    "id": name,
                    "scale": self.scales[name],
                    "dependence": self.dependence[name],
                    "regime_slack": self.regime_slack.get(name),
                }
                for name in self.outputs
            ],
            "parameters": list(self.parameter_ids),
            "forward": None if self.forward is None else self.forward.as_document(),
            "adjoint": None if self.adjoint is None else self.adjoint.as_document(),
            "regime_bounds_active": [
                {"id": row, "slack": slack} for row, slack in self.regime_bounds_active
            ],
            "limitations": [lim.as_document() for lim in self.limitations],
            "refusals": [r.as_document() for r in self.refusals],
        }


def _rows(lin: Linearization, outputs: Sequence[str]) -> list[dict[str, float]]:
    """`∇ₓG` row by output: the stored nonzeros as `{variable_id: value}` (CSC → rows)."""
    rows: list[dict[str, float]] = [{} for _ in outputs]
    matrix = lin.d_dx
    for j, variable_id in enumerate(matrix.col_ids):
        for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
            rows[matrix.indices[k]][variable_id] = float(matrix.data[k])
    return rows


def _direct(
    lin: Linearization, outputs: Sequence[str], parameters: Sequence[str]
) -> npt.NDArray[np.float64]:
    """`∂G/∂p` as a dense outputs x `parameters` array (0 for a pin the program does not read)."""
    direct = np.zeros((len(outputs), len(parameters)))
    column = {name: j for j, name in enumerate(parameters)}
    matrix = lin.d_dp
    for j, name in enumerate(matrix.col_ids):
        for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
            direct[matrix.indices[k], column[name]] = float(matrix.data[k])
    return direct


def _block(
    host_block: SensitivityBlock | None,
    base_rows: Mapping[str, int],
    outputs: Sequence[str],
    direct: npt.NDArray[np.float64],
    request: SensitivityRequest,
    scales: Mapping[str, float],
) -> SensitivityBlock:
    """The host's `∇ₓG·X` (its row of the augmented request) plus `∂G/∂p`; `None` where the
    host's entry is `None`. With no host block (a refused request) every entry is `None`."""
    unscaled: list[tuple[float | None, ...]] = []
    scaled: list[tuple[float | None, ...]] = []
    for i, name in enumerate(outputs):
        unscaled_row: list[float | None] = []
        scaled_row: list[float | None] = []
        for j, parameter in enumerate(request.parameters):
            value: float | None
            if host_block is None:
                value = None
            elif name in base_rows:
                host = host_block.unscaled[base_rows[name]][j]
                value = None if host is None else host + float(direct[i, j])
            else:
                value = float(direct[i, j])
            unscaled_row.append(value)
            scaled_row.append(None if value is None else value * parameter.scale / scales[name])
        unscaled.append(tuple(unscaled_row))
        scaled.append(tuple(scaled_row))
    return SensitivityBlock(tuple(scaled), tuple(unscaled))


def assessment_sensitivity(
    program: AssessmentProgram,
    host: SensitivityHost,
    request: SensitivityRequest,
    state: npt.NDArray[np.float64],
    outputs: Sequence[str],
    certificate: CertificateEvidence | None = None,
    *,
    scales: Mapping[str, float] | None = None,
    splits: Sequence[SplitRegime] = (),
) -> AssessmentSensitivity:
    """§4.10.1: `dy/dp` of the assessment `outputs` (ids without the prefix) at the certified
    `state` (in `host.spec.variable_ids` order) for `request`'s parameters and mode.

    `scales` gives an output's scale; by default `max(|y(x*)|, 1)` (§4.10.2's output scale). A
    refusal of `program.linearize` (an unavailable or unknown output) is returned with no host
    run. Raises `ValueError` when the program's host variables are not the host's."""
    variable_ids = host.spec.variable_ids
    if tuple(program.context.host_spec.variable_ids) != tuple(variable_ids):
        raise ValueError("the program was built over a different host problem")
    if not outputs:
        # A32: no assessment output, no linearization; the host's result is the direct one.
        base = evaluate_sensitivity(host, state, request, certificate=certificate, splits=splits)
        return AssessmentSensitivity((), request.parameter_ids, {}, {}, None, None, base)
    x = {name: float(value) for name, value in zip(variable_ids, state, strict=True)}
    known = set(program.parameter_ids)
    symbolic = [p for p in request.parameter_ids if p in known]
    lin = program.linearize(x, {}, list(outputs), symbolic)
    if isinstance(lin, Refusal):
        return AssessmentSensitivity(
            outputs=tuple(outputs),
            parameter_ids=request.parameter_ids,
            scales={},
            dependence={},
            forward=None,
            adjoint=None,
            base=None,
            refusals=(lin,),
        )
    assert isinstance(lin, Linearization)
    chosen = {
        name: float((scales or {}).get(name, max(abs(lin.values[name]), 1.0))) for name in outputs
    }
    for name, value in chosen.items():
        if not (math.isfinite(value) and value > 0.0):
            raise ValueError(f"output {name!r}: the scale must be finite and > 0")
    rows = _rows(lin, outputs)
    functionals = tuple(
        OutputFunctional(f"{OUTPUT_PREFIX}{name}", row, chosen[name])
        for name, row in zip(outputs, rows, strict=True)
        if row
    )
    dependence: dict[str, Dependence] = {
        name: "STATE_DEPENDENT" if row else "STATE_INDEPENDENT"
        for name, row in zip(outputs, rows, strict=True)
    }
    augmented = dataclasses.replace(request, outputs=(*request.outputs, *functionals))
    base = evaluate_sensitivity(host, state, augmented, certificate=certificate, splits=splits)
    offset = len(request.outputs)
    base_rows = {
        functional.output_id.removeprefix(OUTPUT_PREFIX): offset + i
        for i, functional in enumerate(functionals)
    }
    direct = _direct(lin, outputs, request.parameter_ids)
    forward = (
        _block(base.forward, base_rows, outputs, direct, request, chosen)
        if request.mode in ("forward", "both")
        else None
    )
    adjoint = (
        _block(base.adjoint, base_rows, outputs, direct, request, chosen)
        if request.mode in ("adjoint", "both")
        else None
    )
    active, slack, limitations = _regime_boundaries(program, x, lin, outputs, symbolic)
    return AssessmentSensitivity(
        outputs=tuple(outputs),
        parameter_ids=request.parameter_ids,
        scales=chosen,
        dependence=dependence,
        forward=forward,
        adjoint=adjoint,
        base=base,
        regime_bounds_active=active,
        regime_slack=slack,
        limitations=limitations,
    )


def _pattern(lin: Linearization, name: str) -> set[str]:
    """The columns (host variables, then requested parameters) of `name`'s stored nonzeros."""
    found: set[str] = set()
    for matrix in (lin.d_dx, lin.d_dp):
        i = matrix.row_ids.index(name)
        for j, column in enumerate(matrix.col_ids):
            if i in matrix.indices[matrix.indptr[j] : matrix.indptr[j + 1]]:
                found.add(column)
    return found


def _regime_boundaries(
    program: AssessmentProgram,
    x: Mapping[str, float],
    lin: Linearization,
    outputs: Sequence[str],
    symbolic: Sequence[str],
) -> tuple[tuple[tuple[str, float], ...], dict[str, float | None], tuple[Limitation, ...]]:
    """Step 6: the active admissibility rows at x*, each output's closure's smallest slack, and
    `REGIME_BOUNDARY_ACTIVE` on each output whose closure holds an active row."""
    rows = list(program.admissibility_ids)
    if not rows:
        return (), dict.fromkeys(outputs), ()
    adm = program.linearize(x, {}, rows, symbolic)
    assert isinstance(adm, Linearization), adm
    slack = {row: float(adm.values[row]) for row in rows}
    active = tuple((row, slack[row]) for row in rows if slack[row] <= TAU_ACTIVE)
    entries = [
        [f"adm.{entry.entry_id}.{row.row_id}" for row in entry.admissibility]
        for entry in program.entries
    ]
    adm_pattern = {row: _pattern(adm, row) for row in rows}
    smallest: dict[str, float | None] = {}
    limitations: list[Limitation] = []
    for name in outputs:
        used = _pattern(lin, name)
        closure = [
            row
            for names in entries
            if any(adm_pattern[row] & used for row in names)
            for row in names
        ]
        smallest[name] = min((slack[row] for row in closure), default=None)
        limitations.extend(
            Limitation("REGIME_BOUNDARY_ACTIVE", name, {"row": row})
            for row, _ in active
            if row in closure
        )
    return active, smallest, tuple(limitations)


def evaluation_context(compiled: Any) -> EvaluationContext:
    """The context a compiled revision problem evaluates under (as the executor builds it)."""
    return EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )


def revision_sensitivity_host(flowsheet: Any, state: Mapping[str, float]) -> SensitivityHost:
    """`syn001.host_of` for a `RevisionFlowsheet`: `flowsheet.spec()`, its compiled problem, K03
    scales from the spec's declared kinds, and the alias rows `eliminate_alias_rows` removes at
    `state` with the pressure-shifted second state of the certificate (`verify/certificate.py`;
    without a second state the elimination is structural, as there)."""
    spec = flowsheet.spec()
    compiled = compile_problem(spec)
    vector = np.array([float(state[name]) for name in spec.variable_ids])
    context = evaluation_context(compiled)
    jacobian = compiled.jacobian(vector, context)
    if jacobian.status != "ok":
        raise ValueError(f"the Jacobian at the state returned {jacobian.status}")
    coefficients: dict[str, dict[str, float]] = {name: {} for name in jacobian.row_ids}
    for column, name in enumerate(jacobian.col_ids):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            row = jacobian.row_ids[jacobian.indices[offset]]
            coefficients[row][name] = float(jacobian.data[offset])

    def rows(values: Mapping[str, float]) -> dict[str, float]:
        result = compiled.residual(np.array([float(values[n]) for n in spec.variable_ids]), context)
        if result.status != "ok" or result.values is None:
            raise ValueError(f"the residual returned {result.status}")
        return dict(zip(result.equation_ids, result.values, strict=True))

    at_state = rows(state)
    second = at_state
    shifted, reason = pressure_shifted_state(
        spec.variable_ids,
        spec.variable_kinds,
        state,
        flowsheet.provider.describe().domain["P"],
    )
    if not reason:
        second = rows(shifted)
    elimination = eliminate_alias_rows(
        row_ids=spec.equation_ids,
        coefficients=coefficients,
        column_kinds=spec.variable_kinds,
        residuals=[at_state, second],
    )
    return SensitivityHost(
        spec=spec,
        compiled=compiled,
        scaling=Scaling.from_spec(spec),
        eliminated_rows=tuple(row.row_id for row in elimination.eliminated),
    )


def trf_objective_from_assessment(program: AssessmentProgram, output_id: str) -> Refusal:
    """The only route from an assessment output to a trust-region objective (§4.10.4). Day one:
    `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)`, before anything is built or solved (A37; §7 Q1)."""
    del program
    return Refusal(
        "ASSESSMENT_OUTPUT_IN_TRF",
        output_id,
        "a trust-region objective naming an assessment output is not offered (design §7 Q1)",
        kind="unsupported",
    )
