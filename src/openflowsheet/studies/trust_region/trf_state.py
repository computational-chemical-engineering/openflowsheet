"""TRF's pin, its registered configurations, and its state read from its own log — without Pyomo
(M05 design note §6.7; ADR 0038 D1, D4, D8; R-260, R-263).

Everything here is plain Python so that the default gate can test it: the version and module-hash
pin and the readiness it gives, the subproblem options `M05-trsp-ipopt-v1` and the configuration
`M05-trf-config-v1`, the basis a run must be given and its completeness check, the parser of the
`pyomo.contrib.trustregion` INFO records, the filter rebuilt from θ-type steps, and the outcome
read from the captured `EXIT:` lines checked against the logged values and against θ re-checked
from the returned model. `trf.py` is the half that imports Pyomo and runs it.

**Why the log.** Pyomo 6.10.1's TRF keeps its iteration history, its filter and its exit reason in
locals of `trust_region_method`; the only views it gives are the INFO records of
`IterationRecord.detailLogger` and the `print`s of its two `EXIT:` lines. Reading those is the
unmodified framework's own account; patching its internals would break the pin (R-260). The
records format every number with `%s`, which for a Python float is its `repr`, so `float()` of the
logged text is the exact binary64 TRF held.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import re
import sys
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from openflowsheet.studies.trust_region.holders import RunState

# -- the pin (D1, D4; G2) -------------------------------------------------------------------------

#: R-260: the framework is Pyomo 6.10.1's `contrib.trustregion`, unmodified. A Pyomo upgrade is a
#: new ADR, so these change only with one.
PYOMO_VERSION: Final = "6.10.1"
TRF_PACKAGE: Final = "pyomo.contrib.trustregion"
#: SHA-256 of the five modules TRF's behaviour lives in, measured in the audited environment
#: (`docs/m03-ipopt-audit.md`'s, Pyomo 6.10.1 from its pip lock). WO-1's inventory
#: (`benchmarks/m05/trsp-inventory-x86_64.json`) records the same files; the two must agree.
TRF_MODULE_SHA256: Final[Mapping[str, str]] = {
    "TRF.py": "69b5c8f854201dc2dbb78826540808a3353aad80838df74221e3f67e97d36973",
    "interface.py": "ef13ef90c89dd5d9381ebc47f0c200dc58d316bd6e6cf22f96567e853969cd9e",
    "filter.py": "616655ce04626589122602af1f7dfb5fb37ff0f5728c4ace1e0ea3da1b3248ae",
    "funnel.py": "52e1840e35d93582c04316f0447a0f37fa0b843ec14c2aa2cb9b3c6e00592378",
    "util.py": "25dcfb844d8730a8a6f82280cd554fc8e3c385b13a54216b52a8a2838fdcf40c",
}
#: R-263: the subproblem solver is this exact Ipopt 3.14.20 ASL executable (`<sys.prefix>/bin/ipopt`
#: of the audited environment), which WO-1's [A10] extension inventories.
TRSP_EXECUTABLE_SHA256: Final = "2d7bcf8835ac26437a81a6bf840e9c6c5a87c36540bc467d6fe7ddec63924a63"

ReadinessCode = Literal[
    "TRUST_REGION_FRAMEWORK_UNAVAILABLE",
    "TRUST_REGION_FRAMEWORK_UNPINNED",
    "TRSP_SOLVER_UNAUDITED",
]


@dataclass(frozen=True)
class ReadinessReason:
    code: ReadinessCode
    detail: str

    def as_document(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class FrameworkReadiness:
    """The framework half of `trust_region_readiness` (design note §6.8): the `nlp` environment,
    the pin and the subproblem executable. The projection and start halves are the study's."""

    status: Literal["READY", "UNSUPPORTED"]
    reasons: tuple[ReadinessReason, ...]

    @property
    def codes(self) -> tuple[ReadinessCode, ...]:
        return tuple(dict.fromkeys(reason.code for reason in self.reasons))

    def as_document(self) -> dict[str, Any]:
        return {"status": self.status, "reasons": [r.as_document() for r in self.reasons]}


def trsp_executable() -> Path:
    """Where the audited subproblem executable is: the running environment's own `bin/ipopt`."""
    return Path(sys.prefix) / "bin" / "ipopt"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def framework_readiness(
    *,
    version: str | None = None,
    module_dir: Path | None = None,
    executable: Path | None = None,
) -> FrameworkReadiness:
    """Every failing reason among the environment, the pin and the executable, or `READY`.

    The keyword arguments replace what is measured, so a test can present a patched version
    string, a changed module byte or another executable (G2) without touching the environment.
    Pyomo is located without importing it; it is imported (for `pyomo.version`) only when present.
    """
    if version is None and importlib.util.find_spec("pyomo") is None:
        return FrameworkReadiness(
            "UNSUPPORTED",
            (
                ReadinessReason(
                    "TRUST_REGION_FRAMEWORK_UNAVAILABLE",
                    "Pyomo is not installed: the trust-region adapter exists only in the audited "
                    "`nlp` environment of docs/m03-ipopt-audit.md, and the `nlp` extra is not "
                    "declared for distribution until N1 (design note §7.6)",
                ),
            ),
        )
    reasons: list[ReadinessReason] = []
    if version is None:
        version = str(importlib.import_module("pyomo.version").version)
    if version != PYOMO_VERSION:
        reasons.append(
            ReadinessReason(
                "TRUST_REGION_FRAMEWORK_UNPINNED",
                f"pyomo.version.version is {version!r}; the adapter is pinned to {PYOMO_VERSION}",
            )
        )
    if module_dir is None:
        try:
            spec = importlib.util.find_spec(TRF_PACKAGE)
        except (ImportError, ValueError):  # the parent packages do not import
            spec = None
        locations = None if spec is None else spec.submodule_search_locations
        module_dir = Path(next(iter(locations))) if locations else None
    if module_dir is None:
        reasons.append(
            ReadinessReason("TRUST_REGION_FRAMEWORK_UNPINNED", f"{TRF_PACKAGE} is not present")
        )
    else:
        for name, expected in TRF_MODULE_SHA256.items():
            path = module_dir / name
            measured = file_sha256(path) if path.is_file() else None
            if measured != expected:
                reasons.append(
                    ReadinessReason(
                        "TRUST_REGION_FRAMEWORK_UNPINNED",
                        f"{TRF_PACKAGE}/{name} has SHA-256 {measured}; pinned {expected}",
                    )
                )
    if executable is None:
        executable = trsp_executable()
    if not executable.is_file():
        reasons.append(
            ReadinessReason("TRSP_SOLVER_UNAUDITED", f"no subproblem executable at {executable}")
        )
    else:
        measured_executable = file_sha256(executable)
        if measured_executable != TRSP_EXECUTABLE_SHA256:
            reasons.append(
                ReadinessReason(
                    "TRSP_SOLVER_UNAUDITED",
                    f"{executable} has SHA-256 {measured_executable}; the audited executable "
                    f"is {TRSP_EXECUTABLE_SHA256}",
                )
            )
    return FrameworkReadiness("UNSUPPORTED" if reasons else "READY", tuple(reasons))


# -- the registered configurations (D4, D8) -------------------------------------------------------

#: The `SolverFactory` name of the subproblem solver (`trf.TrspIpopt`).
TRSP_SOLVER_ALIAS: Final = "openflowsheet_trsp_ipopt"
TRSP_OPTIONS_ID: Final = "M05-trsp-ipopt-v1"
#: Design note §6.7's table, verbatim. `print_level 0`: the options test adds `output_file`,
#: `file_print_level 5` and `print_user_options yes` to a copy, never to this.
TRSP_OPTIONS: Final[Mapping[str, str | int | float]] = {
    "linear_solver": "mumps",
    "hessian_approximation": "exact",
    "bound_relax_factor": 0.0,
    "honor_original_bounds": "yes",
    "mu_strategy": "monotone",
    "tol": 1e-8,
    "constr_viol_tol": 1e-8,
    "compl_inf_tol": 1e-8,
    "dual_inf_tol": 1e-6,
    "acceptable_iter": 0,
    "max_iter": 500,
    "max_wall_time": 120.0,
    "nlp_scaling_method": "user-scaling",
    "print_level": 0,
}

TRF_CONFIG_ID: Final = "M05-trf-config-v1"
#: Design note §6.7's `M05-trf-config-v1`, all but `step_size_termination`, which comes from the
#: study's decision tolerances (`step_size_termination`). Passed to `solve()`, never to the
#: `SolverFactory` constructor (probe P8).
TRF_CONFIG_V1: Final[Mapping[str, Any]] = {
    "solver": TRSP_SOLVER_ALIAS,
    "keepfiles": False,
    "tee": False,
    "verbose": False,
    "trust_radius": 0.25,
    "minimum_radius": 1e-4,
    "maximum_radius": 1.0,
    "maximum_iterations": 30,
    "feasibility_termination": 1e-5,
    "minimum_feasibility": 1e-4,
    "switch_condition_kappa_theta": 0.1,
    "switch_condition_gamma_s": 2.0,
    "radius_update_param_gamma_c": 0.5,
    "radius_update_param_gamma_e": 2.5,
    "ratio_test_param_eta_1": 0.05,
    "ratio_test_param_eta_2": 0.2,
    "globalization_strategy": "filter",
    "maximum_feasibility": 50.0,
    "param_filter_gamma_theta": 0.01,
    "param_filter_gamma_f": 0.01,
}


def step_size_termination(tolerances: Sequence[float], half_widths: Sequence[float]) -> float:
    """σ = 0.5 · min_j(δ_j / h_j): half the smallest decision tolerance in scaled units."""
    if len(tolerances) != len(half_widths) or not tolerances:
        raise ValueError("one tolerance and one half-width per decision, at least one decision")
    return 0.5 * min(delta / width for delta, width in zip(tolerances, half_widths, strict=True))


def trf_config_v1(sigma: float) -> dict[str, Any]:
    """`M05-trf-config-v1` with its step-size termination σ."""
    return {**TRF_CONFIG_V1, "step_size_termination": sigma}


# -- the basis (D7; R-277) ------------------------------------------------------------------------

#: What an `EFBasis` is, for the record (design note §6.6): `zero` is TRF's default b ≡ 0, TR-E1's
#: only; `constant`, `affine_taylor` and `surrogate` are M05-basis-v1's.
BasisKind = Literal["zero", "constant", "affine_taylor", "surrogate"]
TRF_CONFIGURATION_REFUSED: Final = "TRF_CONFIGURATION_REFUSED"
#: The projection's `shape_check` status of TR-E1, the one projection a zero basis is allowed on.
SHAPE_CHECK_EXEMPT_ORACLE: Final = "exempt_oracle"


@dataclass(frozen=True)
class EFBasis:
    """One `ExternalFunction`'s basis b(w) (design note §6.6). `build` is given the EF's arguments
    as TRF's clone holds them — `ef_expr.args`, never the original model's variables — and returns
    the Pyomo expression (or number) TRF uses as b; `kind` is what the run records."""

    kind: BasisKind
    build: Callable[[Sequence[Any]], Any]


def _zero(args: Sequence[Any]) -> int:
    return 0


def zero_basis(ef_names: Collection[str]) -> dict[str, EFBasis]:
    """TRF's default b ≡ 0 for every EF, made explicit — test-only, for TR-E1 (R-277). It returns
    the integer 0 that TRF's own default `lambda comp, ef: 0` returns, so TR-E1 run with it is the
    native example. `run_trf` refuses it on any projection other than TR-E1's exempt oracle."""
    return {name: EFBasis("zero", _zero) for name in ef_names}


def basis_refusals(
    ef_names: Collection[str], basis: Mapping[str, EFBasis] | None, shape_check: str
) -> tuple[str, ...]:
    """R-277: why `basis` is not a configuration a run may use on a projection with these EF names
    and shape-check status, as `TRF_CONFIGURATION_REFUSED(<reason>)` codes; empty if it may.

    - `basis_missing:<ef>`: no basis at all, or none for this EF — TRF would fill in b ≡ 0;
    - `basis_unknown:<name>`: a basis for no EF of the projection;
    - `zero_basis_not_oracle:<ef>`: a zero basis on a projection that is not TR-E1's oracle."""
    given = {} if basis is None else dict(basis)
    names = sorted(ef_names)
    reasons = [f"basis_missing:{name}" for name in names if name not in given]
    reasons += [f"basis_unknown:{name}" for name in sorted(set(given) - set(names))]
    if shape_check != SHAPE_CHECK_EXEMPT_ORACLE:
        reasons += [
            f"zero_basis_not_oracle:{name}"
            for name in names
            if name in given and given[name].kind == "zero"
        ]
    return tuple(f"{TRF_CONFIGURATION_REFUSED}({reason})" for reason in reasons)


# -- the INFO records (D8) ------------------------------------------------------------------------

StepType = Literal["f", "theta", "rejected"]

_ITERATION = re.compile(r"^\*{6} Iteration (\d+) \*{6}$")
_VALUE = re.compile(r"^(trustRadius|feasibility|objectiveValue|stepNorm) = (\S+)$")
_STEP_TYPES: Final[Mapping[str, StepType]] = {
    "INFO: f-type step": "f",
    "INFO: theta-type step": "theta",
    "INFO: step rejected": "rejected",
}
_FIELDS: Final = {
    "trustRadius": "radius",
    "feasibility": "theta",
    "objectiveValue": "objective",
    "stepNorm": "step_norm",
}
EXIT_OPTIMAL: Final = "EXIT: Optimal solution found."
EXIT_FEASIBLE: Final = "EXIT: Feasible solution found."
WARNING_INSUFFICIENT_PROGRESS: Final = "WARNING: Insufficient progress."
_MAX_ITERATIONS = re.compile(r"^EXIT: Maximum iterations reached: (\d+)\.$")


@dataclass(frozen=True)
class IterationRecord:
    """One TRF iteration as its INFO record logged it.

    `radius` is the trust radius TRF logged: for an accepted step (`f`, `theta`) the radius
    *after* that step's update, for a rejected step the radius the step was taken with
    (`TRF.py`: `updateIteration(trustRadius=...)` runs only on acceptance). `step_type` is `None`
    for iteration 0, which is the PMP and takes no step."""

    k: int
    theta: float
    objective: float
    radius: float
    step_norm: float
    step_type: StepType | None

    def as_document(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "theta": self.theta,
            "objective": self.objective,
            "radius": self.radius,
            "radius_logged": "used" if self.step_type == "rejected" else "updated",
            "step_norm": self.step_norm,
            "type": self.step_type,
        }


class TrfLogError(ValueError):
    """The INFO records do not read as TRF 6.10.1 writes them: the pin's premise is broken."""


@dataclass
class _Partial:
    k: int
    values: dict[str, float] = field(default_factory=dict)
    step_type: StepType | None = None


class TrfLogHandler(logging.Handler):
    """Collects `pyomo.contrib.trustregion`'s records for one run and advances its `RunState`.

    Every message is kept verbatim (`messages`); INFO records are parsed as they arrive so that a
    holder asking for its iteration mid-run gets the right one; WARNING and above are kept in
    `warnings`. Nothing is raised from `emit` — a record that does not parse is kept in
    `unparsed`, and `iterations()` refuses the whole log afterwards."""

    def __init__(self, run: RunState | None = None) -> None:
        super().__init__(level=logging.INFO)
        self.run = run
        self.messages: list[str] = []
        self.warnings: list[str] = []
        self.unparsed: list[str] = []
        self._partials: list[_Partial] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.consume(record.getMessage(), record.levelno)

    def consume(self, message: str, level: int = logging.INFO) -> None:
        self.messages.append(message)
        if level >= logging.WARNING:
            self.warnings.append(message)
            return
        header = _ITERATION.match(message)
        if header is not None:
            k = int(header.group(1))
            self._partials.append(_Partial(k))
            if self.run is not None:
                self.run.last_logged_iteration = k
            return
        current = self._partials[-1] if self._partials else None
        value = _VALUE.match(message)
        if value is not None and current is not None and value.group(1) not in current.values:
            try:
                current.values[value.group(1)] = float(value.group(2))
            except ValueError:
                self.unparsed.append(message)
            return
        step_type = _STEP_TYPES.get(message)
        if step_type is not None and current is not None and current.step_type is None:
            current.step_type = step_type
            return
        self.unparsed.append(message)

    def iterations(self) -> tuple[IterationRecord, ...]:
        """The parsed records, refused unless they are exactly TRF 6.10.1's: numbered 0, 1, 2, …,
        each with its four values, iteration 0 with no step type and every later one with one."""
        if self.unparsed:
            raise TrfLogError(f"unrecognized TRF log records: {self.unparsed[:3]}")
        records = []
        for index, partial in enumerate(self._partials):
            if partial.k != index:
                raise TrfLogError(f"iteration {partial.k} logged in position {index}")
            if set(partial.values) != set(_FIELDS):
                raise TrfLogError(f"iteration {partial.k} logged {sorted(partial.values)}")
            if (partial.step_type is None) != (partial.k == 0):
                raise TrfLogError(f"iteration {partial.k} has step type {partial.step_type}")
            records.append(
                IterationRecord(
                    k=partial.k,
                    theta=partial.values["feasibility"],
                    objective=partial.values["objectiveValue"],
                    radius=partial.values["trustRadius"],
                    step_norm=partial.values["stepNorm"],
                    step_type=partial.step_type,
                )
            )
        return tuple(records)


def reconstruct_filter(
    iterations: Sequence[IterationRecord], gamma_f: float, gamma_theta: float
) -> tuple[tuple[float, float], ...]:
    """TRF's filter, rebuilt: each θ-type step offers (f − γ_f θ, (1 − γ_θ) θ), computed by the
    same binary64 operations as `TRF.py`, and is added by `Filter.addToFilter`'s rule — skipped if
    an entry dominates it, removing every entry it dominates. Elements are `(f, θ)`."""
    entries: list[tuple[float, float]] = []
    for record in iterations:
        if record.step_type != "theta":
            continue
        offered = (record.objective - gamma_f * record.theta, (1 - gamma_theta) * record.theta)
        # `Filter.addToFilter`, step for step: it walks a copy, removes what the new element
        # dominates as it goes, and returns early (keeping those removals) when it is dominated.
        for entry in list(entries):
            if offered[0] >= entry[0] and offered[1] >= entry[1]:
                break
            if offered[0] <= entry[0] and offered[1] <= entry[1]:
                entries.remove(entry)
        else:
            entries.append(offered)
    return tuple(entries)


def last_accepted(iterations: Sequence[IterationRecord]) -> IterationRecord | None:
    """The iterate TRF's model holds at exit: the last accepted step's, or the PMP's. A rejected
    step's variables are reset by `rejectStep`, so its record is never the final state."""
    for record in reversed(iterations):
        if record.step_type != "rejected":
            return record
    return None


# -- the outcome (design note §6.7 "Outcomes") -----------------------------------------------------

Outcome = str
TRF_CONVERGED: Final = "TRF_CONVERGED"
#: R-279: "Optimal" with no accepted TRSP step — not a convergence claim; the study sends the point
#: to stage B's parent checks (WO-6).
TRF_EXIT_WITHOUT_STEP: Final = "TRF_EXIT_WITHOUT_STEP"
TRF_FEASIBLE_STALLED: Final = "TRF_FEASIBLE_STALLED"
#: R-279: "Feasible" with θ re-checked above the feasibility termination — no candidate; the
#: retry policy treats it as an abort.
TRF_STALLED_INCONSISTENT: Final = "TRF_STALLED_INCONSISTENT"
TRF_MAX_ITERATIONS: Final = "TRF_MAX_ITERATIONS"
TRF_SUBPROBLEM_FAILED: Final = "TRF_SUBPROBLEM_FAILED"
#: The outcomes after which the run keeps TRF's clone and a candidate exists.
RETURNS_MODEL: Final = frozenset(
    {TRF_CONVERGED, TRF_EXIT_WITHOUT_STEP, TRF_FEASIBLE_STALLED, TRF_MAX_ITERATIONS}
)


def truth_refused(code: str) -> Outcome:
    return f"TRF_TRUTH_REFUSED({code})"


def trf_error(name: str) -> Outcome:
    return f"TRF_ERROR({name})"


def accepted_steps(iterations: Sequence[IterationRecord]) -> int:
    """The number of accepted TRSP steps (f- or θ-type); iteration 0, the PMP, is no step."""
    return sum(1 for record in iterations if record.step_type in ("f", "theta"))


def classify_exit(
    *,
    exit_lines: Sequence[str],
    warnings: Sequence[str],
    iterations: Sequence[IterationRecord],
    theta_recheck: float,
    feasibility_termination: float,
    step_size_termination: float,
    maximum_iterations: int,
) -> Outcome:
    """The outcome of a run that returned, from its `EXIT:` lines checked against its log and
    against `theta_recheck`, θ recomputed from the model TRF returned (R-279: probe P14 shows that
    either `EXIT:` line can be false).

    - `EXIT: Optimal solution found.` needs the last logged iteration's θ and step norm — the
      values `TRF.py`'s termination test read — within the configured terminations, and
      `theta_recheck` within the feasibility termination. Then it is `TRF_CONVERGED` after at
      least one accepted TRSP step, and `TRF_EXIT_WITHOUT_STEP` after none.
    - `EXIT: Feasible solution found.` needs TRF's `Insufficient progress` warning. Then it is
      `TRF_FEASIBLE_STALLED` with `theta_recheck` within the feasibility termination, and
      `TRF_STALLED_INCONSISTENT` above it (`TRF.py`'s stall test compares θ with itself after an
      accepted step, so it fires at any θ).
    - `TRF_MAX_ITERATIONS`: no printed `EXIT:` line, TRF's maximum-iterations warning naming the
      configured count, and that many iterations logged after iteration 0.

    Anything else is `TRF_ERROR(exit_mismatch)`: the printed outcome, the logged values and the
    model disagree, and none of them is believed."""
    if not iterations:
        return trf_error("exit_mismatch")
    last = iterations[-1]
    feasible = theta_recheck <= feasibility_termination
    if list(exit_lines) == [EXIT_OPTIMAL]:
        if (
            last.theta <= feasibility_termination
            and last.step_norm <= step_size_termination
            and feasible
        ):
            return TRF_CONVERGED if accepted_steps(iterations) else TRF_EXIT_WITHOUT_STEP
        return trf_error("exit_mismatch")
    if list(exit_lines) == [EXIT_FEASIBLE]:
        if WARNING_INSUFFICIENT_PROGRESS in warnings:
            return TRF_FEASIBLE_STALLED if feasible else TRF_STALLED_INCONSISTENT
        return trf_error("exit_mismatch")
    if not exit_lines:
        reached = [m for m in (_MAX_ITERATIONS.match(w) for w in warnings) if m is not None]
        if (
            len(reached) == 1
            and int(reached[0].group(1)) == maximum_iterations
            and last.k == maximum_iterations
        ):
            return TRF_MAX_ITERATIONS
    return trf_error("exit_mismatch")
