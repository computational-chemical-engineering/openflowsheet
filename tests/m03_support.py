"""Shared helpers for the M03 tests (specification `docs/derivations/M03-studies-spec.md`).

`reference()` is `benchmarks/m03/reference_values.json`, produced by the design lane's closed-form
generator `docs/derivations/scripts/m03_reference.py` (mpmath, 60 digits; it imports nothing from
`openflowsheet`). Its bytes are pinned to the SHA-256 the specification's header records, so a test
cannot be judged against a file the specification does not cite: regenerating the JSON is a
specification change, and the hash here moves with it or the loader refuses.

Every number in the file is a decimal string (20 significant digits, or the `repr` of a registered
binary64 input); `number()` is the one conversion, so no test parses one differently.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.compile.spec import EquationSpec, ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import FRESH_FEED_FLOWS, Syn001Flowsheet
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.attempts import SolveResult
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.studies.sensitivity import OutputFunctional, SensitivityHost, StudyParameter
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
REFERENCE_PATH: Final = REPO_ROOT / "benchmarks" / "m03" / "reference_values.json"
#: The SHA-256 `docs/derivations/M03-studies-spec.md`'s header records for the JSON.
REFERENCE_SHA256: Final = "5f3fc150032157d31042f8b17ca5560e4c0e7233384a3eaade0404bde5915981"
GENERATOR_PATH: Final = REPO_ROOT / "docs" / "derivations" / "scripts" / "m03_reference.py"


@cache
def reference() -> dict[str, Any]:
    """The M03 reference values, refused unless the bytes are the specification's."""
    raw = REFERENCE_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REFERENCE_SHA256:
        raise ValueError(
            f"{REFERENCE_PATH.relative_to(REPO_ROOT)} has SHA-256 {digest}, but the M03 "
            f"specification records {REFERENCE_SHA256}; the tests judge against the file the "
            "specification cites, or not at all"
        )
    loaded: dict[str, Any] = json.loads(raw)
    return loaded


def number(value: str | int | float) -> float:
    """A reference value as the nearest binary64 (the file's decimal strings, or a literal)."""
    return float(value)


def constant(name: str) -> float:
    """A registered constant of the specification (`constants` in the JSON), as binary64."""
    return number(reference()["constants"][name])


# -- SYN-001's registered states (spec §4.2, §4.6, §6) --------------------------------------------

#: The flowsheet's unit-evaluation context, as the K04 tests build it. The compiled problem's own
#: identity is assigned by the compiler and does not depend on it.
FLOWSHEET_CONTEXT: Final = EvaluationContext(
    model_version="M03@" + "0" * 64, constants_sha256="0" * 64
)

#: Spec §2's parameter ids, in the JSON's order, and the `Syn001Flowsheet` field each one pins
#: (spec §4.5). `U-FEED.n_spec.A` is the first entry of `feed_flows`.
REGISTERED_PARAMETERS: Final = (
    "U-SPLIT.split_fraction",
    "U-FLASH.T_spec",
    "U-HEAT.T_spec",
    "U-FEED.T_spec",
    "U-FEED.n_spec.A",
)
PRESSURE_PARAMETERS: Final = ("U-FLASH.P_spec", "U-FEED.P_spec")
_FIELDS: Final = {
    "U-SPLIT.split_fraction": "split_fraction",
    "U-FLASH.T_spec": "flash_temperature",
    "U-HEAT.T_spec": "heater_temperature",
    "U-FEED.T_spec": "feed_temperature",
}


def flowsheet(pinned: Mapping[str, str | float]) -> Syn001Flowsheet:
    """SYN-001 with the given pinned inputs (binary64 `repr`s or floats); the rest nominal."""
    fields: dict[str, Any] = {}
    for parameter_id, value in pinned.items():
        if parameter_id == "U-FEED.n_spec.A":
            fields["feed_flows"] = (number(value), *FRESH_FEED_FLOWS[1:])
        else:
            fields[_FIELDS[parameter_id]] = number(value)
    return Syn001Flowsheet(provider=Syn001Provider(), context=FLOWSHEET_CONTEXT, **fields)


def registered_pinned(state: str) -> dict[str, str]:
    """The pinned binary64 inputs of a registered state: P1-P3 (§4.2), B1-B3 (§4.6), or a sweep
    point `sweep@<T_f>` (§6)."""
    loaded = reference()
    if state in loaded["sensitivity_states"]:
        return dict(loaded["sensitivity_states"][state]["pinned_doubles"])
    if state in ("B1", "B2", "B3"):
        return dict(loaded["boundary_states"][state]["pinned_doubles"])
    if state.startswith("sweep@"):
        sweep = loaded["sweep"]
        return {
            "U-SPLIT.split_fraction": sweep["split_fraction"],
            sweep["parameter"]: state.removeprefix("sweep@"),
        }
    raise KeyError(state)


def converged_sweep_states() -> tuple[str, ...]:
    """The sweep points the specification registers as converged (§6), as `sweep@<T_f>`."""
    sweep = reference()["sweep"]
    return tuple(
        f"sweep@{point[sweep['parameter']]}"
        for point in sweep["points"]
        if point["expected_outcome"] == "CONVERGED"
    )


@cache
def solved(state: str) -> tuple[Syn001Flowsheet, SolveResult]:
    """The production tear solve of a registered state from the registered initializer."""
    sheet = flowsheet(registered_pinned(state))
    result, _ = solve_tear(sheet)
    if result.outcome != "CONVERGED" or result.final_state is None:
        raise AssertionError(f"{state}: the registered state did not converge: {result.outcome}")
    return sheet, result


# -- the toys (spec §5) ---------------------------------------------------------------------------


def x_squared_spec(p: float, *, convert: bool = False) -> ProblemSpec:
    """`x² − p` with `p` pinned. With `convert`, the builder calls `float()` on the parameter —
    harmless to the base problem, impossible for the twin (A04)."""

    def build(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, Any],
        _: Any,
    ) -> Any:
        del blocks
        value = float(parameters["p"]) if convert else parameters["p"]
        return variables["x"] ** 2 - value

    return ProblemSpec(
        label="M03-toy-x-squared" + ("-float" if convert else ""),
        variable_ids=("x",),
        equations=(EquationSpec("R", build, "algebraic"),),
        parameter_ids=("p",),
        parameters={"p": p},
    )


def linear_spec(delta: float, p: tuple[float, float] = (1.0, 3.0)) -> ProblemSpec:
    """`A(δ) x − p` with `A(δ) = [[1, 2], [3, 6 + δ]]` and `p` pinned (`F_p = −I`)."""

    def first(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, Any],
        _: Any,
    ) -> Any:
        del blocks
        return variables["x1"] + 2.0 * variables["x2"] - parameters["p1"]

    def second(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, Any],
        _: Any,
    ) -> Any:
        del blocks
        return 3.0 * variables["x1"] + (6.0 + delta) * variables["x2"] - parameters["p2"]

    return ProblemSpec(
        label="M03-toy-linear",
        variable_ids=("x1", "x2"),
        equations=(
            EquationSpec("R1", first, "algebraic"),
            EquationSpec("R2", second, "algebraic"),
        ),
        parameter_ids=("p1", "p2"),
        parameters={"p1": p[0], "p2": p[1]},
    )


def toy_host(spec: ProblemSpec) -> tuple[SensitivityHost, EvaluationContext]:
    """A toy compiled with unit scales and no eliminated rows (spec §5), and its own context."""
    compiled = compile_problem(spec)
    scaling = Scaling(
        column={name: 1.0 for name in spec.variable_ids},
        row={name: 1.0 for name in spec.equation_ids},
        provenance="M03 spec §5: unit scales",
    )
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    return SensitivityHost(spec, compiled, scaling), context


def toy_parameter(parameter_id: str) -> StudyParameter:
    """A toy parameter: scale 1 (spec §5), and a domain wide enough to hold every toy state."""
    return StudyParameter(parameter_id, scale=1.0, lower=-10.0, upper=10.0)


def registered_parameters() -> tuple[StudyParameter, ...]:
    """Spec §2's five registered SYN-001 parameters with the JSON's scales.

    The domains are the provider's (temperatures [280, 440] K) and the physical ones (the split
    fraction in [0, 1), a positive feed); spec §3.1 asks for a finite declared domain, and no
    M03 qualification reads it."""
    domains = {
        "U-SPLIT.split_fraction": (0.0, 0.999),
        "U-FLASH.T_spec": (280.0, 440.0),
        "U-HEAT.T_spec": (280.0, 440.0),
        "U-FEED.T_spec": (280.0, 440.0),
        "U-FEED.n_spec.A": (1e-6, 10.0),
    }
    return tuple(
        StudyParameter(entry["id"], number(entry["scale"]), *domains[entry["id"]])
        for entry in reference()["constants"]["parameters"]
    )


def pressure_parameters() -> tuple[StudyParameter, ...]:
    """The two pressure specifications (spec §4.6, Alias), at the registered pressure scale."""
    return tuple(StudyParameter(name, 1.0e5, 5.0e4, 2.0e5) for name in PRESSURE_PARAMETERS)


def registered_outputs() -> tuple[OutputFunctional, ...]:
    """Spec §2's twelve outputs: eleven variables and `Q_total`, with the JSON's scales."""
    return tuple(
        OutputFunctional(
            entry["id"],
            {
                name: float(value)
                for name, value in entry.get("coefficients", {entry["id"]: 1}).items()
            },
            number(entry["scale"]),
        )
        for entry in reference()["constants"]["outputs"]
    )


def syn001_host(state: str) -> tuple[SensitivityHost, Syn001TearProblem, npt.NDArray[np.float64]]:
    """The SYN-001 tear problem of a registered state as a core host, and `x*`."""
    sheet, result = solved(state)
    assert result.final_state is not None
    tear = Syn001TearProblem(sheet)
    host = SensitivityHost(
        tear.spec,
        tear.compiled,
        tear.scaling,
        tuple(row.row_id for row in tear.partition.elimination.eliminated),
    )
    return host, tear, np.array(state_vector(tear.spec, result.final_state))


# -- the finite-difference oracle (spec §4.5; R-010: a test oracle, never a production path) ------

#: Spec §4.5: `h_j = 1e-4 · s_pj`, and the 4th-order central stencil's offsets and weights.
FD_RELATIVE_STEP: Final = 1e-4
_STENCIL: Final = ((-2, 1.0), (-1, -8.0), (1, 8.0), (2, -1.0))


def output_values(
    sheet: Syn001Flowsheet, outputs: Sequence[OutputFunctional]
) -> npt.NDArray[np.float64]:
    """Solve `sheet` with the production K03 solver from the registered initializer; `y = C x`."""
    result, _ = solve_tear(sheet)
    if result.outcome != "CONVERGED" or result.final_state is None:
        raise AssertionError(f"an FD stencil point did not converge: {result.outcome}")
    state = result.final_state
    return np.array(
        [
            math.fsum(
                coefficient * state[name] for name, coefficient in output.coefficients.items()
            )
            for output in outputs
        ]
    )


def fd_sensitivity(
    state: str,
    parameters: Sequence[StudyParameter],
    outputs: Sequence[OutputFunctional],
) -> npt.NDArray[np.float64]:
    """Spec §4.5's oracle, scaled: `Ŝ_FD = [−y(+2h) + 8y(+h) − 8y(−h) + y(−2h)] / (12h) · s_p / s_y`
    from four re-solves per parameter, each pinned input replaced at `p_j + m h_j`."""
    pinned = registered_pinned(state)
    output_scales = np.array([output.scale for output in outputs])
    columns = []
    for parameter in parameters:
        base = number(pinned[parameter.parameter_id])
        step = FD_RELATIVE_STEP * parameter.scale
        total = np.zeros(len(outputs))
        for offset, weight in _STENCIL:
            moved = {**pinned, parameter.parameter_id: base + offset * step}
            total += weight * output_values(flowsheet(moved), outputs)
        derivative = total / (12.0 * step)
        columns.append(derivative * parameter.scale / output_scales)
    return np.column_stack(columns)


# -- the estimation example (spec §7) -------------------------------------------------------------


def _measurement(entry: Mapping[str, Any]) -> Any:
    from openflowsheet.studies.estimation import Measurement

    return Measurement(
        measurement_id=entry["id"],
        coefficients={name: float(value) for name, value in entry["coefficients"].items()},
        sigma=number(entry["sigma"]),
        observed=number(entry["observed"]),
    )


def estimation_problem(fit_id: str) -> Any:
    """Spec §7's FIT-I or FIT-U, read from the JSON: the observations are the stored `repr`s of
    the generator's binary64 values (spec §7.2) — nothing here, or in `src`, regenerates them."""
    from openflowsheet.studies.estimation import DataProvenance, EstimationProblem

    section = reference()["estimation"]
    data = section["data"]
    chosen = set(section["fits"][fit_id]["measurements"])
    measurements = tuple(
        _measurement(entry) for entry in data["measurements"] if entry["id"] in chosen
    )
    parameters = tuple(
        StudyParameter(
            entry["id"], number(entry["scale"]), number(entry["lower"]), number(entry["upper"])
        )
        for entry in section["theta"]
    )
    return EstimationProblem(
        fit_id=fit_id,
        flowsheet=flowsheet({}),
        parameters=parameters,
        start=tuple(number(entry["start"]) for entry in section["theta"]),
        measurements=measurements,
        validation=tuple(_measurement(entry) for entry in data["validation"]),
        provenance=DataProvenance(
            evidence_class=section["evidence_class"],
            statement=section["statement"],
            seed=int(data["seed"]),
            noise_model={
                name: data[name] for name in ("generator", "uniform", "normal", "observation")
            },
            theta_true={name: number(value) for name, value in data["theta_true"].items()},
        ),
    )
