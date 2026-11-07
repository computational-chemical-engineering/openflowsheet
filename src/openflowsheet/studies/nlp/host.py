"""The NLP host: what M03's closure, formulation, gray box and verification need of a flowsheet.

OPT design §4.1 (ADR 0071 D4). One protocol, two hosts: `Syn001NlpHost` is M03's SYN-001 tear
path, wrapping today's study functions verbatim (`studies/syn001.py`); OPT's `RevisionNlpHost`
(WO-2) is a stored revision on the `revision_eo` route. Every M03 module takes a host where it
took a `Syn001Flowsheet`, and still accepts the flowsheet itself (`as_host`), so no caller of
M03 changes and the SYN-001 records stay bit-identical (gate G2).

A host answers, at a **certified point** (a production solve from the registered initializer
and its K04 certificate at given decision values):

- `certify(decisions)`: the point; never raises for a failed solve (its outcome says so, as
  `CertifiedSolve`), raises `DecisionRefusedError` for decision values the host refuses before
  any solve (an ill-formed request, not a point that failed);
- `held_system(point)`: the square system the NLP's equalities are (§4.2.1) — for SYN-001 every
  row but its two alias rows, every column free, no label rows;
- `regimes(point)`: the attempt signature and every phase split's regime and margin (§4.2.4);
- `sensitivity(point, parameters, outputs, held=units)`: M03's sensitivity (ADR 0031) on the held
  system; `held` is Q4's held mode (§4.7), passed only by V5;
- `twin(decision_ids)`: the parametric twin with the decisions symbolic, compiled once per
  decision ids and cached by the host (the same function at every start);
- `phase_rows(point)`: the phase-regime admissibility rows (§4.7, WO-5); `None` for SYN-001;
- `model_record()`, `domain()`: the base problem's identity and the provider's declared domain.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Protocol

from openflowsheet.compile.casadi_backend import (
    ParametricTwin,
    compile_parametric_twin,
    compile_problem,
)
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.region import AttemptSystem
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.studies.sensitivity import (
    Mode,
    OutputFunctional,
    SensitivityResult,
    SplitRegime,
    StudyParameter,
)
from openflowsheet.studies.syn001 import (
    CertifiedSolve,
    solve_certified,
    split_regimes,
    syn001_sensitivity,
    with_pinned,
)
from openflowsheet.verify.certificate import SolutionCertificate

HostKind = Literal["syn001-tear", "revision-eo"]


class DecisionRefusedError(ValueError):
    """Decision values a host refuses before any solve: an ill-formed request, not a point that
    failed. The message is the host's own (for SYN-001, `with_pinned`'s), and the refusal it
    wraps is its `__cause__`."""


@dataclass(frozen=True)
class CertifiedPoint:
    """A production solve at `parameters` and its certificate (§4.1). `outcome` is `CONVERGED`
    only when the solve converged **and** the certificate is `VERIFIED` (as `CertifiedSolve`);
    `state` is the solve's final state, `None` without one. `parameters` are the decision
    parameters exactly as the host's binding holds them; `spec` is the bound problem at them
    (`None` where the host refused the specification); `signature` the final attempt signature
    (`None` for SYN-001, which has one region attempt); `bundle_ref` the revision bundle's
    reference where the host writes bundles. `handle` is the host's own, never compared or
    serialised."""

    outcome: str
    message: str
    state: Mapping[str, float] | None
    certificate: SolutionCertificate | None
    signature: Any
    bundle_ref: str | None
    parameters: Mapping[str, float]
    spec: ProblemSpec | None = field(default=None, compare=False, repr=False)
    handle: Any = field(default=None, compare=False, repr=False)

    @property
    def verified(self) -> bool:
        return self.outcome == "CONVERGED"


@dataclass(frozen=True)
class HeldSystem:
    """The NLP's square equality system at a certified point (§4.2.1): `rows` of `spec` and the
    `labels` `(row_id, t_out, t_label)` appended after them, square in the `free` columns; the
    `held` columns fixed at their certified values; `eliminated` the plan's alias rows, which the
    system excludes; `signature` the attempt signature it was taken from."""

    spec: ProblemSpec
    rows: tuple[str, ...]
    free: tuple[str, ...]
    held: Mapping[str, float]
    labels: tuple[tuple[str, str, str], ...]
    eliminated: tuple[str, ...]
    signature: Any = None

    def __post_init__(self) -> None:
        if len(self.rows) + len(self.labels) != len(self.free):
            raise ValueError(
                f"the held system is not square: {len(self.rows)} rows + {len(self.labels)} "
                f"labels against {len(self.free)} free columns"
            )
        equations = set(self.spec.equation_ids)
        unknown = sorted((set(self.rows) | set(self.eliminated)) - equations)
        if unknown:
            raise ValueError(f"rows not in the problem: {unknown}")
        aliased = sorted(set(self.rows) & set(self.eliminated))
        if aliased:
            raise ValueError(f"alias rows in the held system: {aliased}")
        free, held = set(self.free), set(self.held)
        if free & held or free | held != set(self.spec.variable_ids) or len(free) != len(self.free):
            raise ValueError("the free and held columns do not partition the problem's variables")

    @classmethod
    def of_attempt(
        cls, spec: ProblemSpec, attempt: AttemptSystem, eliminated: Sequence[str]
    ) -> HeldSystem:
        """The held system of a region's converged attempt (`RegionResult.final_system`) over
        `spec`, with the plan's eliminated alias rows `eliminated` (§4.2.1)."""
        return cls(
            spec=spec,
            rows=tuple(attempt.rows),
            free=tuple(attempt.free),
            held=MappingProxyType(dict(attempt.held)),
            labels=tuple(attempt.labels),
            eliminated=tuple(eliminated),
            signature=attempt.signature,
        )


@dataclass(frozen=True)
class RegimeRecord:
    """The attempt signature at a point and every phase split's regime and margin (§4.2.4)."""

    signature: Any
    splits: tuple[SplitRegime, ...]

    def declared(self) -> dict[str, str]:
        """Each split's regime by unit: the formulation's declared regimes."""
        return {split.unit_id: str(split.regime) for split in self.splits}


class NlpHost(Protocol):
    """What the NLP needs of a flowsheet (§4.1). See the module docstring."""

    kind: HostKind
    #: M03 D6: every start must certify (SYN-001); a revision needs one (§4.5).
    require_every_start: bool

    def model_record(self) -> dict[str, Any]: ...

    def domain(self) -> Mapping[str, tuple[float, float]]: ...

    def base_spec(self) -> ProblemSpec: ...

    def certify(self, decisions: Mapping[str, float]) -> CertifiedPoint: ...

    def held_system(self, point: CertifiedPoint) -> HeldSystem: ...

    def regimes(self, point: CertifiedPoint) -> RegimeRecord: ...

    def sensitivity(
        self,
        point: CertifiedPoint,
        parameters: Sequence[StudyParameter],
        outputs: Sequence[OutputFunctional],
        *,
        mode: Mode = "both",
        held: Sequence[str] = (),
    ) -> SensitivityResult: ...

    def twin(self, decision_ids: Sequence[str]) -> ParametricTwin: ...

    def phase_rows(self, point: CertifiedPoint) -> Any: ...


@dataclass
class _Syn001Point:
    """`Syn001NlpHost`'s handle on a point: the pinned flowsheet, its certified solve, and the
    held system once taken."""

    sheet: Syn001Flowsheet
    solve: CertifiedSolve
    system: HeldSystem | None = None


class Syn001NlpHost:
    """M03's SYN-001 tear path as an NLP host: today's study functions, verbatim."""

    kind: HostKind = "syn001-tear"
    require_every_start: bool = True

    def __init__(self, flowsheet: Syn001Flowsheet) -> None:
        self.flowsheet = flowsheet
        self._twins: dict[tuple[str, ...], ParametricTwin] = {}

    def model_record(self) -> dict[str, Any]:
        """The base problem's identity, or `None` fields where the flowsheet does not compile."""
        try:
            metadata = compile_problem(self.flowsheet.spec()).metadata
        except SpecificationError:
            return {"model_version": None, "constants_sha256": None}
        return {
            "model_version": metadata.model_version,
            "constants_sha256": metadata.constants_sha256,
        }

    def domain(self) -> Mapping[str, tuple[float, float]]:
        domain = self.flowsheet.provider.describe().domain
        return {"T": domain["T"], "P": domain["P"]}

    def base_spec(self) -> ProblemSpec:
        """The flowsheet's problem as given; raises `SpecificationError` where a unit refuses."""
        return self.flowsheet.spec()

    def certify(self, decisions: Mapping[str, float]) -> CertifiedPoint:
        """`with_pinned`, then `solve_certified` (M03 spec §6, §8.5 V1)."""
        try:
            sheet = with_pinned(self.flowsheet, decisions)
        except ValueError as error:
            raise DecisionRefusedError(*error.args) from error
        solve = solve_certified(sheet)
        return CertifiedPoint(
            outcome=solve.outcome,
            message=solve.message,
            state=solve.final_state,
            certificate=solve.certificate,
            signature=None,
            bundle_ref=None,
            parameters=MappingProxyType({name: float(value) for name, value in decisions.items()}),
            spec=sheet.spec() if solve.result is not None else None,
            handle=_Syn001Point(sheet, solve),
        )

    def held_system(self, point: CertifiedPoint) -> HeldSystem:
        """Every row but the tear plan's two alias rows; every column free; no labels."""
        handle = _handle(point)
        if handle.system is None:
            handle.system = self._system_of(handle.sheet)
        return handle.system

    def pinned_system(self) -> HeldSystem:
        """The held system of this host's flowsheet as it is pinned: M03's calling form of
        `FullSpaceNlp`, which passes the flowsheet already pinned at the start."""
        return self._system_of(self.flowsheet)

    @staticmethod
    def _system_of(sheet: Syn001Flowsheet) -> HeldSystem:
        tear = Syn001TearProblem(sheet)
        eliminated = tuple(row.row_id for row in tear.partition.elimination.eliminated)
        dropped = set(eliminated)
        return HeldSystem(
            spec=tear.spec,
            rows=tuple(name for name in tear.spec.equation_ids if name not in dropped),
            free=tuple(tear.spec.variable_ids),
            held=MappingProxyType({}),
            labels=(),
            eliminated=eliminated,
        )

    def regimes(self, point: CertifiedPoint) -> RegimeRecord:
        """The tear path's two TP-type splits at the point's state (`split_regimes`)."""
        if point.state is None:
            raise ValueError("the point carries no state to take regimes at")
        return RegimeRecord(None, split_regimes(_handle(point).sheet, point.state))

    def sensitivity(
        self,
        point: CertifiedPoint,
        parameters: Sequence[StudyParameter],
        outputs: Sequence[OutputFunctional],
        *,
        mode: Mode = "both",
        held: Sequence[str] = (),
    ) -> SensitivityResult:
        """`syn001_sensitivity` at the point's solve, with its certificate. SYN-001 has no
        phase rows (`phase_rows` is `None`), so nothing is ever held by one."""
        if held:
            raise ValueError(f"SYN-001 holds no regime by a phase row: held={list(held)}")
        handle = _handle(point)
        return syn001_sensitivity(
            handle.sheet,
            handle.solve.result,
            parameters=parameters,
            outputs=outputs,
            mode=mode,
            certificate=point.certificate,
        )

    def twin(self, decision_ids: Sequence[str]) -> ParametricTwin:
        """The base flowsheet's twin with `decision_ids` symbolic, compiled once per ids."""
        key = tuple(decision_ids)
        if key not in self._twins:
            self._twins[key] = compile_parametric_twin(self.flowsheet.spec(), key)
        return self._twins[key]

    def phase_rows(self, point: CertifiedPoint) -> None:
        """SYN-001 holds its regimes by V4 alone (M03): no phase rows."""
        return None


def _handle(point: CertifiedPoint) -> _Syn001Point:
    if not isinstance(point.handle, _Syn001Point):
        raise TypeError("the point was not certified by a SYN-001 host")
    return point.handle


def as_host(host: NlpHost | Syn001Flowsheet) -> NlpHost:
    """`host`, or the SYN-001 host of a flowsheet (M03's calling form)."""
    if isinstance(host, Syn001Flowsheet):
        return Syn001NlpHost(host)
    return host
