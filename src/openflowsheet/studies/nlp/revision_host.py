"""The revision NLP host: a stored revision on the `revision_eo` route (OPT design §4.2, WO-2).

`RevisionNlpHost` answers the `NlpHost` protocol (`studies/nlp/host.py`) for a revision document:

- **certify** writes the decisions into a copy of the document (§4.2.2's edit), binds it with the
  recorded route's binder (`routes.bind`, `bind_route`, R2.5: never re-routes) and solves it with
  `routes.solve` (`solve_route`) from the registered initializer, cold (`warm_start=None`, D6);
  with a bundle sink it writes the bundle `run_revision_session` writes for that document
  (`routes.write_bundle`, `write_revision_bundle`); `routes` is the application's
  (`host.RevisionRoutes`, OPT review M2);
- **held system** (§4.2.1) is the region's converged attempt (`RegionResult.final_system`) plus
  the plan's eliminated alias rows;
- **regimes** (§4.2.4) are the final attempt signature and every lifted split's kind, regime and
  TP margin at its own converged (T, P) (D7);
- **sensitivity** is M03's core (ADR 0031) on that held system (`SensitivityHost.system`);
- **twin** is compiled once per decision ids from the base problem and cached;
- **bounds** (§4.2.3) over the held system's free columns;
- the **zero subsystem** (§9 A-2): at every certified point the free flows exactly `0.0` and the
  rows that only they enter are held at `+0.0` and dropped when they are as many (`HeldSystem.
  zero`), else bounded `[0, ∞)`; V4 compares it between a start and its re-solve.

The decision map (§4.2.2) is found by two bind probes per decision (`decision_map`): a decision is
a `role: fixed` specification, and its NLP variable is the single `ProblemSpec` parameter whose
value moves, bitwise, to the written value, with nothing else in the binding moving.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import struct
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from openflowsheet.compile.casadi_backend import (
    ParametricTwin,
    TwinEvaluationError,
    compile_parametric_twin,
    compile_problem,
)
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionFlowsheet, si_unit
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
from openflowsheet.orchestrator.region import LiftedSplit, RegionResult, admissibility_value
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import region_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.manifest import started_now
from openflowsheet.studies.nlp.boundary import (
    CERTIFICATE,
    PHASE_BOUNDARY_FORM,
    BoundaryVerdict,
    boundary_set,
    certificate_target,
    judge,
)
from openflowsheet.studies.nlp.formulation import VariableBound
from openflowsheet.studies.nlp.host import (
    CertifiedPoint,
    DecisionRefusedError,
    HeldSystem,
    HostKind,
    RegimeRecord,
    RevisionRoutes,
    ZeroSubsystem,
)
from openflowsheet.studies.nlp.phase import PhaseRows, phase_rows
from openflowsheet.studies.sensitivity import (
    CertificateEvidence,
    Mode,
    OutputFunctional,
    SensitivityHost,
    SensitivityRequest,
    SensitivityResult,
    SplitRegime,
    StudyParameter,
    evaluate_sensitivity,
)
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.checks import VerifierError

ROUTE: Literal["revision_eo"] = "revision_eo"

#: The bounds K03's Newton core applies by quantity kind in the production solve
#: (`orchestrator/region.py` `_region_problem`: `lower_bounds` 0 on `molar_flow`, nothing else).
K03_KIND_BOUNDS: Mapping[str, tuple[float | None, float | None]] = MappingProxyType(
    {"molar_flow": (0.0, None)}
)

DecisionCode = Literal["UNKNOWN_DECISION", "DECISION_UNIT_NOT_INTERNAL", "DECISION_NOT_CONTINUOUS"]

#: Where a certify writes its bundle: called once per certify with the candidate document, it
#: returns the bundle directory and the run id (OPT design §4.8 names both per start).
BundleSink = Callable[[Mapping[str, Any]], tuple[Path, str]]


@dataclass(frozen=True)
class DecisionBox:
    """A request decision as the probes read it (§4.2.2): the specification, its box and the
    unit the box is stated in."""

    specification_id: str
    lower: float | None
    upper: float | None
    unit: str


@dataclass(frozen=True)
class DecisionRefusal:
    """Why a decision has no parameter (§4.2.2): the code, the specification, the detail."""

    code: DecisionCode
    specification_id: str
    detail: str


@dataclass(frozen=True)
class DecisionMap:
    """`{specification id → parameter id}` in request order (`revision.decision_parameters`)."""

    parameters: Mapping[str, str]

    @property
    def specifications(self) -> dict[str, str]:
        """The inverse: `{parameter id → specification id}`."""
        return {parameter: spec for spec, parameter in self.parameters.items()}

    def as_document(self) -> dict[str, str]:
        return dict(self.parameters)


class RevisionUnboundError(ValueError):
    """The base revision does not bind on `revision_eo`: the binder's refusal is `unbound`."""

    def __init__(self, unbound: Any) -> None:
        self.unbound = unbound
        super().__init__(f"{unbound.kind}({unbound.detail})")


def _bits(value: float) -> bytes:
    return struct.pack("<d", float(value))


def _specification(document: Mapping[str, Any], specification_id: str) -> Mapping[str, Any] | None:
    for entry in document.get("specifications", ()):
        if entry.get("id") == specification_id:
            return entry  # type: ignore[no-any-return]
    return None


def document_at(document: Mapping[str, Any], values: Mapping[str, float]) -> dict[str, Any]:
    """§4.2.2 step 3's edit: a copy of `document` with each named specification's `value` set to
    its value and, where its `unit` is not the SI unit of its kind, its `unit` set to that SI
    unit (the value is stated in it). Every other byte of the document is kept."""
    edited = copy.deepcopy(dict(document))
    found: set[str] = set()
    for entry in edited.get("specifications", ()):
        name = entry.get("id")
        if name in values:
            found.add(name)
            entry["value"] = float(values[name])
            unit = si_unit(entry["kind"])
            if entry.get("unit") != unit:
                entry["unit"] = unit
    missing = sorted(set(values) - found)
    if missing:
        raise ValueError(f"specifications not in the document: {missing}")
    return edited


def _moved(base: Any, probe: Any) -> tuple[list[str], list[str]]:
    """What a probe changed: the structural members that differ, and the parameters whose value
    differs bitwise (§4.2.2 step 4)."""
    structural = [
        name
        for name, same in (
            ("variable_ids", probe.spec.variable_ids == base.spec.variable_ids),
            ("equation_ids", probe.spec.equation_ids == base.spec.equation_ids),
            (
                "configuration_sha256",
                probe.flowsheet.configuration_sha256 == base.flowsheet.configuration_sha256,
            ),
            ("label", probe.flowsheet.label == base.flowsheet.label),
            ("row_units", dict(probe.row_units) == dict(base.row_units)),
            ("parameter_ids", set(probe.spec.parameters) == set(base.spec.parameters)),
        )
        if not same
    ]
    if structural:
        return structural, []
    moved = [
        name
        for name, value in base.spec.parameters.items()
        if _bits(probe.spec.parameters[name]) != _bits(value)
    ]
    return [], moved


def decision_map(
    document: Mapping[str, Any],
    decisions: Sequence[DecisionBox],
    *,
    routes: RevisionRoutes,
    surrogates: Any = None,
) -> DecisionMap | tuple[DecisionRefusal, ...]:
    """§4.2.2: each decision's parameter by bind probes at its box's finite ends, or every
    decision's refusal in request order. Binds `document` once plus at most twice per decision;
    solves nothing. Raises `RevisionUnboundError` when the base document does not bind.

    A probe may move at most one parameter, to the written value bitwise, and nothing else; a
    probe at the base value moves none. Across a decision's probes exactly one parameter is
    named, and at every probe it holds the written value."""
    base = routes.bind(ROUTE, document, surrogates=surrogates)
    if not routes.is_route(base):
        raise RevisionUnboundError(base)
    binding = base.binding
    parameters: dict[str, str] = {}
    refusals: list[DecisionRefusal] = []
    for decision in decisions:
        name = decision.specification_id

        def refuse(code: DecisionCode, detail: str, name: str = name) -> None:
            refusals.append(DecisionRefusal(code, name, detail))

        entry = _specification(document, name)
        if entry is None or entry.get("role") != "fixed" or "value" not in entry:
            refuse("UNKNOWN_DECISION", f"{name} is not a role: fixed specification with a value")
            continue
        try:
            unit = si_unit(entry["kind"])
        except KeyError:
            refuse("DECISION_UNIT_NOT_INTERNAL", f"{name}: no SI unit for kind {entry['kind']!r}")
            continue
        if decision.unit != unit:
            refuse(
                "DECISION_UNIT_NOT_INTERNAL",
                f"{name}: the box is in {decision.unit!r}, the internal unit is {unit!r}",
            )
            continue
        ends = [v for v in (decision.lower, decision.upper) if v is not None and math.isfinite(v)]
        probes: list[tuple[float, list[str], Mapping[str, float]]] = []
        why = ""
        for value in ends:
            probe = routes.bind(ROUTE, document_at(document, {name: value}), surrogates=surrogates)
            if not routes.is_route(probe):
                why = f"{probe.kind}({probe.detail})"
                break
            structural, moved = _moved(binding, probe.binding)
            if structural:
                why = f"the probe at {value!r} changed {','.join(structural)}"
                break
            if len(moved) > 1:
                why = f"the probe at {value!r} moved {','.join(moved)}"
                break
            probes.append((value, moved, probe.binding.spec.parameters))
        named = sorted({parameter for _, moved, _ in probes for parameter in moved})
        if not why and len(named) != 1:
            why = (
                f"the probes moved {named}"
                if named
                else "no probe moved a parameter (no end of the box is off the base value)"
            )
        if not why:
            (parameter,) = named
            # A probe at the base value moves nothing; there too the parameter holds the value.
            wrong = [value for value, _, held in probes if _bits(held[parameter]) != _bits(value)]
            if wrong:
                why = f"the probe at {wrong[0]!r} did not set {parameter} to it"
            elif parameter in parameters.values():
                why = f"{parameter} is already another decision's parameter"
            else:
                parameters[name] = parameter
                continue
        refuse("DECISION_NOT_CONTINUOUS", f"DECISION_NOT_CONTINUOUS({name}): {why}")
    if refusals:
        return tuple(refusals)
    return DecisionMap(MappingProxyType(parameters))


def two_phase_margin(
    split: LiftedSplit, state: Mapping[str, float], kinds: Mapping[str, str]
) -> float | None:
    """§9 A-3: a TWO_PHASE split's margin, `min(Σ vapour side, Σ liquid side) / N0` over the
    sides' `molar_flow` columns, N0 K03's registered `molar_flow` nominal (the one the phase rows
    use, D-35); `None` when a side has no `molar_flow` column."""
    sides = []
    for side in (split.vapor, split.liquid):
        flows = [float(state[name]) for name in side if kinds.get(name) == "molar_flow"]
        if not flows:
            return None
        sides.append(math.fsum(flows))
    return min(sides) / float(REGISTERED_NOMINALS["molar_flow"])


@dataclass
class _RevisionPoint:
    """`RevisionNlpHost`'s handle on a point: the candidate document, its route and solve, and
    what the host derived from them once (the held system, the compiled problem)."""

    document: Mapping[str, Any]
    route: Any
    run: Any
    system: HeldSystem | None = None
    compiled: CompiledProblem | None = field(default=None, repr=False)
    phase: PhaseRows | None = field(default=None, repr=False)
    #: §9 A-1: V1's phase-boundary judgment where it passed; the point then has a held system
    #: although its certificate is not `VERIFIED`.
    boundary: BoundaryVerdict | None = field(default=None, repr=False)

    @property
    def region(self) -> RegionResult | None:
        """The solve's region result: the last plan step's (`revision_eo` plans one region)."""
        if self.run is None or self.run.run is None or not self.run.run.steps:
            return None
        detail = self.run.run.steps[-1].detail
        return detail if isinstance(detail, RegionResult) else None


def _handle(point: CertifiedPoint) -> _RevisionPoint:
    if not isinstance(point.handle, _RevisionPoint):
        raise TypeError("the point was not certified by a revision host")
    return point.handle


class RevisionNlpHost:
    """A stored revision on `revision_eo` as an NLP host (OPT design §4.2). See the module
    docstring. `decisions` is the request's decision map (`decision_map`); `routes` the
    application's route operations; `sink`, where given, places each certify's bundle;
    `policy_requested` is the solve policy's id as requested, for the bundle's `solve-path.json`
    (`None`: the routes' default policy id)."""

    kind: HostKind = "revision-eo"
    #: §4.5: a revision needs one certified start, not every one.
    require_every_start: bool = False

    def __init__(
        self,
        document: Mapping[str, Any],
        decisions: DecisionMap,
        *,
        routes: RevisionRoutes,
        solve_policy: SolvePolicy,
        check_policy: CheckPolicy,
        policy_requested: str | None = None,
        sink: BundleSink | None = None,
        surrogates: Any = None,
    ) -> None:
        route = routes.bind(ROUTE, document, surrogates=surrogates)
        if not routes.is_route(route):
            raise RevisionUnboundError(route)
        self.document = copy.deepcopy(dict(document))
        self.decisions = decisions
        self.routes = routes
        self.route = route
        self.solve_policy = solve_policy
        self.check_policy = check_policy
        self.policy_requested = (
            routes.default_policy_id if policy_requested is None else policy_requested
        )
        self.sink = sink
        self.surrogates = surrogates
        self._specifications = decisions.specifications
        self._twins: dict[tuple[str, ...], ParametricTwin] = {}
        self._compiled: CompiledProblem | None = None

    # -- identity --------------------------------------------------------------------------------

    @property
    def binding(self) -> Any:
        return self.route.binding

    def _base_compiled(self) -> CompiledProblem:
        if self._compiled is None:
            self._compiled = compile_problem(self.binding.spec)
        return self._compiled

    def model_record(self) -> dict[str, Any]:
        metadata = self._base_compiled().metadata
        return {
            "model_version": metadata.model_version,
            "constants_sha256": metadata.constants_sha256,
        }

    def domain(self) -> Mapping[str, tuple[float, float]]:
        domain = self.binding.flowsheet.provider.describe().domain
        return {"T": domain["T"], "P": domain["P"]}

    def base_spec(self) -> ProblemSpec:
        spec: ProblemSpec = self.binding.spec
        return spec

    # -- the certified point ---------------------------------------------------------------------

    def document_at(self, decisions: Mapping[str, float]) -> dict[str, Any]:
        """The base document with `decisions` (by parameter id) written in (§4.2.2's edit).
        Raises `DecisionRefusedError` for a parameter that is not a decision of this host."""
        unknown = sorted(set(decisions) - set(self._specifications))
        if unknown:
            raise DecisionRefusedError(f"not decisions of this revision: {unknown}")
        return document_at(
            self.document,
            {self._specifications[name]: float(value) for name, value in decisions.items()},
        )

    def certify(self, decisions: Mapping[str, float]) -> CertifiedPoint:
        """The candidate document at `decisions` (parameter ids), bound by `revision_eo`'s binder
        and solved by `solve_route` cold (D6), through `routes`; its bundle written when the host
        has a sink.

        Outcomes as `CertifiedSolve`'s: `CONVERGED` only with a `VERIFIED` certificate; the plan
        run's outcome; `CERTIFICATE_NOT_VERIFIED` (also when the verifier refused to judge);
        `SPECIFICATION_REFUSED` (the binder refused the candidate); `UNSUPPORTED` (the route has
        no registered bundle mapping or T02 refused the plan)."""
        document = self.document_at(decisions)
        parameters = MappingProxyType({name: float(value) for name, value in decisions.items()})
        started, clock = started_now(), time.monotonic()
        route = self.routes.bind(ROUTE, document, surrogates=self.surrogates)
        if not self.routes.is_route(route):
            return CertifiedPoint(
                outcome="SPECIFICATION_REFUSED",
                message=f"{route.kind}({route.detail})",
                state=None,
                certificate=None,
                signature=None,
                bundle_ref=None,
                parameters=parameters,
                handle=_RevisionPoint(document, None, None),
            )
        held = route.binding.spec.parameters
        drifted = [name for name in parameters if _bits(held[name]) != _bits(parameters[name])]
        if drifted:
            # §4.2.2 makes the written value the parameter's, bitwise; anything else is a defect.
            raise ValueError(f"defect: the binding does not hold the decisions {drifted} written")
        bound = MappingProxyType({name: float(held[name]) for name in parameters})
        try:
            result = self.routes.solve(
                route,
                document,
                policy=self.solve_policy,
                check_policy=self.check_policy,
                warm_start=None,
            )
        except self.routes.unsupported as error:
            return self._unsolved(document, route, "UNSUPPORTED", str(error), bound)
        except VerifierError as error:
            message = f"verifier_refused: {str(error).splitlines()[0] if str(error) else ''}"
            return self._unsolved(document, route, "CERTIFICATE_NOT_VERIFIED", message, bound)
        bundle_ref = None
        if self.sink is not None:
            directory, run_id = self.sink(document)
            self.routes.write_bundle(
                result,
                document,
                directory,
                run_id=run_id,
                policy=self.solve_policy,
                check_policy=self.check_policy,
                policy_requested=self.policy_requested,
                started=started,
                clock=clock,
            )
            bundle_ref = str(directory)
        handle = _RevisionPoint(document, route, result)
        region = handle.region
        outcome = result.outcome
        message = region.message if region is not None else ""
        certificate = result.certificate
        if outcome == "CONVERGED":
            if certificate is None or certificate.verification_status != "VERIFIED":
                status = certificate.verification_status if certificate is not None else None
                outcome, message = "CERTIFICATE_NOT_VERIFIED", f"certificate {status}"
        state = result.state
        if state is None and result.run is not None:
            state = result.run.state
        signature = None
        if region is not None and region.attempts:
            signature = region.attempts[-1].signature
        return CertifiedPoint(
            outcome=outcome,
            message=(message.splitlines() or [""])[0],
            state=MappingProxyType(dict(state)) if state is not None else None,
            certificate=certificate,
            signature=signature,
            bundle_ref=bundle_ref,
            parameters=bound,
            spec=route.binding.spec,
            handle=handle,
        )

    @staticmethod
    def _unsolved(
        document: Mapping[str, Any],
        route: Any,
        outcome: str,
        message: str,
        parameters: Mapping[str, float],
    ) -> CertifiedPoint:
        return CertifiedPoint(
            outcome=outcome,
            message=message,
            state=None,
            certificate=None,
            signature=None,
            bundle_ref=None,
            parameters=parameters,
            spec=route.binding.spec,
            handle=_RevisionPoint(document, route, None),
        )

    # -- what the NLP is at a point ----------------------------------------------------------------

    def bound_flowsheet(self, point: CertifiedPoint) -> RevisionFlowsheet:
        """The flowsheet the point's candidate document binds to (an assessment's view, D-32);
        `ValueError` for a point the binder refused."""
        route = _handle(point).route
        if route is None:
            raise ValueError("the point's document was refused by the binder")
        return route.binding.flowsheet  # type: ignore[no-any-return]

    def held_system(self, point: CertifiedPoint) -> HeldSystem:
        """The region's converged attempt over the candidate's problem, with the plan's alias rows
        (§4.2.1). Only a certified point has one: `VERIFIED`, or passed by V1 on the
        phase-boundary form (§9 A-1, `phase_boundary`)."""
        handle = _handle(point)
        if handle.system is None:
            region = handle.region
            admitted = point.verified or handle.boundary is not None
            if not admitted or region is None or region.final_system is None:
                raise ValueError(f"the point is not certified ({point.outcome}): no held system")
            assert handle.run is not None and handle.run.solve_plan is not None
            eliminated = tuple(row.row_id for row in handle.run.solve_plan.eliminated_rows)
            assert point.spec is not None
            system = HeldSystem.of_attempt(point.spec, region.final_system, eliminated)
            handle.system = self._held_zero(point, system)
        return handle.system

    def _held_zero(self, point: CertifiedPoint, system: HeldSystem) -> HeldSystem:
        """§9 A-2: the attempt's system with its zero subsystem (Z, R) held where |R| = |Z| > 0
        (rows − R, free − Z, held + {z: +0.0}, labels unchanged), recorded `unresolved` where
        |R| ≠ |Z|, and unchanged (`zero` `None`) where Z = ∅ — no evaluation is made then."""
        assert point.state is not None
        kinds = system.spec.variable_kinds
        columns = tuple(
            name for name in system.free if kinds[name] == "molar_flow" and point.state[name] == 0.0
        )
        if not columns:
            return system
        rows = self._zero_rows(point, system, frozenset(columns))
        if len(rows) != len(columns):
            return dataclasses.replace(system, zero=ZeroSubsystem("unresolved", columns, rows))
        dropped, zeros = frozenset(rows), frozenset(columns)
        return HeldSystem(
            spec=system.spec,
            rows=tuple(row for row in system.rows if row not in dropped),
            free=tuple(name for name in system.free if name not in zeros),
            held=MappingProxyType({**system.held, **{name: 0.0 for name in columns}}),
            labels=system.labels,
            eliminated=system.eliminated,
            signature=system.signature,
            zero=ZeroSubsystem("held", columns, rows),
        )

    def _zero_rows(
        self, point: CertifiedPoint, system: HeldSystem, zeros: frozenset[str]
    ) -> tuple[str, ...]:
        """§9 A-2's R: the held rows (labels excluded) whose exact Jacobian at the point is `0.0`
        over every free column outside `zeros` and every decision, and non-zero over some column
        of `zeros`. Free-column entries from the compiled problem's Jacobian at the point (held
        columns at their certified values), decision entries from the twin's `∂F/∂p`."""
        assert point.spec is not None and point.state is not None
        spec = system.spec
        x = np.array([float(point.state[name]) for name in spec.variable_ids], dtype=np.float64)
        metadata = self._compiled_at(point).metadata
        jacobian = self._compiled_at(point).jacobian(
            x,
            EvaluationContext(
                model_version=metadata.model_version,
                constants_sha256=metadata.constants_sha256,
                phase_signature=None,
            ),
        )
        if jacobian.status != "ok":
            raise ValueError(
                f"defect: the Jacobian at a certified point is {jacobian.status}: "
                f"{jacobian.message}"
            )
        candidates, free = set(system.rows), set(system.free)
        touches_zero: set[str] = set()
        touches_other: set[str] = set()
        for position, column in enumerate(jacobian.col_ids):
            if column not in free:
                continue
            into = touches_zero if column in zeros else touches_other
            for offset in range(jacobian.indptr[position], jacobian.indptr[position + 1]):
                row = jacobian.row_ids[jacobian.indices[offset]]
                if row in candidates and jacobian.data[offset] != 0.0:
                    into.add(row)
        decision_ids = tuple(self._specifications)
        parameters = self.twin(decision_ids).jacobian_p(
            x, {name: float(point.parameters[name]) for name in decision_ids}
        )
        for position in range(len(parameters.col_ids)):
            for offset in range(parameters.indptr[position], parameters.indptr[position + 1]):
                row = parameters.row_ids[parameters.indices[offset]]
                if row in candidates and parameters.data[offset] != 0.0:
                    touches_other.add(row)
        return tuple(row for row in system.rows if row in touches_zero and row not in touches_other)

    def regimes(self, point: CertifiedPoint) -> RegimeRecord:
        """The final attempt signature and every lifted split's (kind, regime, margin) (§4.2.4,
        §9 A-3): the margin is the region closure's own test at the converged state, for TP- and
        PH-type splits alike —

        - LIQUID / VAPOR: `1 − admissibility_value` (`orchestrator/region.py`; ideal K: `Σ x K`
          or `Σ y/K` over the side's composition, γ–φ: `Σ x K(x)` or the incipient-liquid `ΣW`),
          `None` where the closure judges by another form (`pr-c1-v1`) or the test raises;
        - TWO_PHASE: the smaller side's `molar_flow` total over K03's registered `molar_flow`
          nominal (the closure holds it by `V, L ≥ 0` only), `None` without such a column;
        - ZERO_FLOW: `None` (V4's exact-dormancy check)."""
        system = self.held_system(point)
        assert point.state is not None
        route = _handle(point).route
        assert route is not None
        flowsheet = route.binding.flowsheet
        splits = region_splits(instances_of(flowsheet), flowsheet.units(), flowsheet.components)
        regimes = dict(item for item in system.signature if len(item) == 2)
        provider = flowsheet.provider
        kinds = system.spec.variable_kinds
        metadata = self._compiled_at(point).metadata
        context = EvaluationContext(
            model_version=metadata.model_version,
            constants_sha256=metadata.constants_sha256,
            phase_signature=None,
        )
        records: list[SplitRegime] = []
        for split in splits.splits:
            if split.unit not in regimes:
                continue
            regime = regimes[split.unit]
            kind = splits.closure_types.get(split.unit, "TP")
            margin: float | None = None
            if regime in ("LIQUID", "VAPOR"):
                value = admissibility_value(provider, context, split, regime, point.state)
                margin = None if value is None else 1.0 - value
            elif regime == "TWO_PHASE":
                margin = two_phase_margin(split, point.state, kinds)
            records.append(SplitRegime(split.unit, split.stream, kind, regime, margin))
        return RegimeRecord(system.signature, tuple(records))

    def _compiled_at(self, point: CertifiedPoint) -> CompiledProblem:
        handle = _handle(point)
        if handle.compiled is None:
            assert point.spec is not None
            handle.compiled = compile_problem(point.spec)
        return handle.compiled

    def sensitivity(
        self,
        point: CertifiedPoint,
        parameters: Sequence[StudyParameter],
        outputs: Sequence[OutputFunctional],
        *,
        mode: Mode = "both",
        held: Sequence[str] = (),
    ) -> SensitivityResult:
        """M03's sensitivity (ADR 0031) at the point on its held system, with its certificate
        (Q1′) and its splits' margins (Q4, Q4′). The twin is the host's cached one when the
        requested parameters include every decision (the same function), else the point's own.
        `held`: the split units Q4 records as held by an active phase row (§4.7; V5 only)."""
        system = self.held_system(point)
        assert point.spec is not None and point.state is not None
        spec = point.spec
        compiled = self._compiled_at(point)
        host = SensitivityHost(
            spec=spec,
            compiled=compiled,
            scaling=Scaling.from_spec(spec),
            eliminated_rows=system.eliminated,
            system=system,
        )
        decision_ids = tuple(self._specifications)

        def twin_factory(problem: ProblemSpec, ids: Sequence[str]) -> ParametricTwin:
            if set(decision_ids) <= set(ids):
                return self.twin(tuple(ids))
            return compile_parametric_twin(problem, ids)

        x = np.array([float(point.state[name]) for name in spec.variable_ids], dtype=np.float64)
        metadata = compiled.metadata
        request = SensitivityRequest(
            context=EvaluationContext(
                model_version=metadata.model_version,
                constants_sha256=metadata.constants_sha256,
                phase_signature=None,
            ),
            parameters=tuple(parameters),
            outputs=tuple(outputs),
            mode=mode,
        )
        return evaluate_sensitivity(
            host,
            x,
            request,
            certificate=(
                CertificateEvidence.of(point.certificate, self.basis(point) or CERTIFICATE)
                if point.certificate is not None
                else None
            ),
            splits=self.regimes(point).splits,
            twin_factory=twin_factory,
            held=tuple(held),
        )

    def basis(self, point: CertifiedPoint) -> str | None:
        """The basis V1 verified the point on (§9 A-1): `certificate` (`VERIFIED`),
        `phase_boundary_form` (passed `phase_boundary`), else `None`."""
        if point.verified:
            return CERTIFICATE
        return PHASE_BOUNDARY_FORM if _handle(point).boundary is not None else None

    def phase_boundary(
        self,
        point: CertifiedPoint,
        held: HeldSystem,
        phase: PhaseRows | None,
        *,
        tau_active: float,
    ) -> BoundaryVerdict:
        """§9 A-1: V1's second basis at a re-solve whose certificate is not `VERIFIED`, judged
        against the start's held system `held` and phase rows `phase` (its guarded rows, the
        float reference path at x̂, `|a/N0| ≤ tau_active`). Where it passes the point is admitted:
        it has a held system, regimes and sensitivities (Q1′ on this basis); its certificate and
        bundle are unchanged."""
        handle = _handle(point)
        state = point.state
        route = handle.route
        converged = (
            handle.run is not None
            and handle.run.outcome == "CONVERGED"
            and route is not None
            and point.spec is not None
        )

        def boundary() -> tuple[tuple[LiftedSplit, Any], ...] | str:
            assert state is not None and route is not None
            if phase is None or not phase.rows:
                return ()
            try:
                values = phase.values(state)
            except TwinEvaluationError as error:
                return str(error)
            flowsheet = route.binding.flowsheet
            splits = region_splits(
                instances_of(flowsheet), flowsheet.units(), flowsheet.components
            ).splits
            return boundary_set(
                phase.rows, values, splits, tau_active=tau_active, unguarded=phase.unguarded
            )

        verdict = judge(
            converged=converged,
            certificate=point.certificate,
            policy=self.check_policy,
            held_signature=held.signature,
            signature=point.signature,
            state=state,
            boundary=boundary,
            target=lambda: certificate_target(
                route.binding,
                handle.document,
                state,  # type: ignore[arg-type]
            ),
        )
        if verdict.passed:
            handle.boundary = verdict
        return verdict

    def twin(self, decision_ids: Sequence[str]) -> ParametricTwin:
        """The base problem's twin with `decision_ids` symbolic, compiled once per ids: the same
        function at every point, since the decision map admits no other change (§4.2.2)."""
        key = tuple(decision_ids)
        if key not in self._twins:
            self._twins[key] = compile_parametric_twin(self.binding.spec, key)
        return self._twins[key]

    def bounds(self, point: CertifiedPoint) -> dict[str, VariableBound]:
        """§4.2.3 over the held system's free columns: T and P by the provider's domain; a flow
        `[0, ∞)` (an unresolved zero subsystem's columns with reason `zero_at_start_unresolved`,
        §9 A-2; a held one's are not free); a duty unbounded; any other kind K03's bound for it in
        the production solve, or unbounded where K03 has none."""
        system = self.held_system(point)
        domain = self.domain()
        kinds = system.spec.variable_kinds
        zero = system.zero
        unresolved = set(zero.columns if zero is not None and zero.status == "unresolved" else ())
        bounds: dict[str, VariableBound] = {}
        for name in system.free:
            kind = kinds[name]
            if kind == "temperature":
                bounds[name] = VariableBound(*domain["T"], "provider_domain")
            elif kind == "pressure":
                bounds[name] = VariableBound(*domain["P"], "provider_domain")
            elif kind == "molar_flow":
                if name in unresolved:
                    bounds[name] = VariableBound(0.0, None, "zero_at_start_unresolved")
                else:
                    bounds[name] = VariableBound(0.0, None, "nonnegative_flow")
            elif kind == "heat_rate":
                bounds[name] = VariableBound(None, None, "heat_rate_unbounded")
            elif kind in K03_KIND_BOUNDS:
                bounds[name] = VariableBound(*K03_KIND_BOUNDS[kind], f"k03_kind_bound({kind})")
            else:
                bounds[name] = VariableBound(None, None, f"no_declared_bound({kind})")
        return bounds

    def phase_rows(self, point: CertifiedPoint) -> PhaseRows:
        """The start's held-regime admissibility rows (§4.7), once per point: one per held
        LIQUID/VAPOR lifted split with a margin (its `regimes` record) and one per declared
        single-phase thermal port; `undefined` names the held regimes no row can hold."""
        handle = _handle(point)
        if handle.phase is None:
            assert point.spec is not None and point.state is not None
            route = handle.route
            assert route is not None
            flowsheet = route.binding.flowsheet
            lifted = {
                split.unit: split
                for split in region_splits(
                    instances_of(flowsheet), flowsheet.units(), flowsheet.components
                ).splits
            }
            metadata = self._compiled_at(point).metadata
            handle.phase = phase_rows(
                point.spec,
                point.state,
                [
                    (
                        record,
                        lifted[record.unit_id].feed,
                        lifted[record.unit_id].temperature,
                        lifted[record.unit_id].pressure,
                    )
                    for record in self.regimes(point).splits
                ],
                flowsheet.provider,
                flowsheet.components,
                EvaluationContext(
                    model_version=metadata.model_version,
                    constants_sha256=metadata.constants_sha256,
                    phase_signature=None,
                ),
            )
        return handle.phase
