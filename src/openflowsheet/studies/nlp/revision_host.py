"""The revision NLP host: a stored revision on the `revision_eo` route (OPT design §4.2, WO-2).

`RevisionNlpHost` answers the `NlpHost` protocol (`studies/nlp/host.py`) for a revision document:

- **certify** writes the decisions into a copy of the document (§4.2.2's edit), binds it with the
  recorded route's binder (`bind_route`, R2.5: never re-routes) and solves it with `solve_route`
  from the registered initializer, cold (`warm_start=None`, D6); with a bundle sink it writes the
  bundle `run_revision_session` writes for that document (`write_revision_bundle`);
- **held system** (§4.2.1) is the region's converged attempt (`RegionResult.final_system`) plus
  the plan's eliminated alias rows;
- **regimes** (§4.2.4) are the final attempt signature and every lifted split's kind, regime and
  TP margin at its own converged (T, P) (D7);
- **sensitivity** is M03's core (ADR 0031) on that held system (`SensitivityHost.system`);
- **twin** is compiled once per decision ids from the base problem and cached;
- **bounds** (§4.2.3) over the held system's free columns.

The decision map (§4.2.2) is found by two bind probes per decision (`decision_map`): a decision is
a `role: fixed` specification, and its NLP variable is the single `ProblemSpec` parameter whose
value moves, bitwise, to the written value, with nothing else in the binding moving.
"""

from __future__ import annotations

import copy
import math
import struct
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from openflowsheet.application.binding import Unbound
from openflowsheet.application.policies import DEFAULT_POLICY_ID
from openflowsheet.application.revision_binding import RevisionBinding, SurrogateResolver
from openflowsheet.application.revision_run import (
    Route,
    RouteRun,
    RunUnsupportedError,
    bind_route,
    solve_route,
    write_revision_bundle,
)
from openflowsheet.compile.casadi_backend import (
    ParametricTwin,
    compile_parametric_twin,
    compile_problem,
)
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.revision_flowsheet import si_unit
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import region_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.manifest import started_now
from openflowsheet.studies.nlp.formulation import VariableBound
from openflowsheet.studies.nlp.host import (
    CertifiedPoint,
    DecisionRefusedError,
    HeldSystem,
    HostKind,
    RegimeRecord,
)
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
from openflowsheet.studies.syn001 import tp_margin
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

    def __init__(self, unbound: Unbound) -> None:
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


def _moved(base: RevisionBinding, probe: RevisionBinding) -> tuple[list[str], list[str]]:
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
    surrogates: SurrogateResolver | None = None,
) -> DecisionMap | tuple[DecisionRefusal, ...]:
    """§4.2.2: each decision's parameter by bind probes at its box's finite ends, or every
    decision's refusal in request order. Binds `document` once plus at most twice per decision;
    solves nothing. Raises `RevisionUnboundError` when the base document does not bind.

    A probe may move at most one parameter, to the written value bitwise, and nothing else; a
    probe at the base value moves none. Across a decision's probes exactly one parameter is
    named, and at every probe it holds the written value."""
    base = bind_route(ROUTE, document, surrogates=surrogates)
    if not isinstance(base, Route):
        raise RevisionUnboundError(base)
    binding: RevisionBinding = base.binding
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
            probe = bind_route(ROUTE, document_at(document, {name: value}), surrogates=surrogates)
            if not isinstance(probe, Route):
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


@dataclass
class _RevisionPoint:
    """`RevisionNlpHost`'s handle on a point: the candidate document, its route and solve, and
    what the host derived from them once (the held system, the compiled problem)."""

    document: Mapping[str, Any]
    route: Route | None
    run: RouteRun | None
    system: HeldSystem | None = None
    compiled: CompiledProblem | None = field(default=None, repr=False)

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
    docstring. `decisions` is the request's decision map (`decision_map`); `sink`, where given,
    places each certify's bundle; `policy_requested` is the solve policy's id as requested, for
    the bundle's `solve-path.json`."""

    kind: HostKind = "revision-eo"
    #: §4.5: a revision needs one certified start, not every one.
    require_every_start: bool = False

    def __init__(
        self,
        document: Mapping[str, Any],
        decisions: DecisionMap,
        *,
        solve_policy: SolvePolicy,
        check_policy: CheckPolicy,
        policy_requested: str = DEFAULT_POLICY_ID,
        sink: BundleSink | None = None,
        surrogates: SurrogateResolver | None = None,
    ) -> None:
        route = bind_route(ROUTE, document, surrogates=surrogates)
        if not isinstance(route, Route):
            raise RevisionUnboundError(route)
        self.document = copy.deepcopy(dict(document))
        self.decisions = decisions
        self.route = route
        self.solve_policy = solve_policy
        self.check_policy = check_policy
        self.policy_requested = policy_requested
        self.sink = sink
        self.surrogates = surrogates
        self._specifications = decisions.specifications
        self._twins: dict[tuple[str, ...], ParametricTwin] = {}
        self._compiled: CompiledProblem | None = None

    # -- identity --------------------------------------------------------------------------------

    @property
    def binding(self) -> RevisionBinding:
        return self.route.binding  # type: ignore[no-any-return]

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
        return self.binding.spec

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
        and solved by `solve_route` cold (D6); its bundle written when the host has a sink.

        Outcomes as `CertifiedSolve`'s: `CONVERGED` only with a `VERIFIED` certificate; the plan
        run's outcome; `CERTIFICATE_NOT_VERIFIED` (also when the verifier refused to judge);
        `SPECIFICATION_REFUSED` (the binder refused the candidate); `UNSUPPORTED` (the route has
        no registered bundle mapping or T02 refused the plan)."""
        document = self.document_at(decisions)
        parameters = MappingProxyType({name: float(value) for name, value in decisions.items()})
        started, clock = started_now(), time.monotonic()
        route = bind_route(ROUTE, document, surrogates=self.surrogates)
        if not isinstance(route, Route):
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
            result = solve_route(
                route,
                document,
                policy=self.solve_policy,
                check_policy=self.check_policy,
                warm_start=None,
            )
        except RunUnsupportedError as error:
            return self._unsolved(document, route, "UNSUPPORTED", str(error), bound)
        except VerifierError as error:
            message = f"verifier_refused: {str(error).splitlines()[0] if str(error) else ''}"
            return self._unsolved(document, route, "CERTIFICATE_NOT_VERIFIED", message, bound)
        bundle_ref = None
        if self.sink is not None:
            directory, run_id = self.sink(document)
            write_revision_bundle(
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
        route: Route,
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

    def held_system(self, point: CertifiedPoint) -> HeldSystem:
        """The region's converged attempt over the candidate's problem, with the plan's alias rows
        (§4.2.1). Only a certified point has one."""
        handle = _handle(point)
        if handle.system is None:
            region = handle.region
            if not point.verified or region is None or region.final_system is None:
                raise ValueError(f"the point is not certified ({point.outcome}): no held system")
            assert handle.run is not None and handle.run.solve_plan is not None
            eliminated = tuple(row.row_id for row in handle.run.solve_plan.eliminated_rows)
            assert point.spec is not None
            handle.system = HeldSystem.of_attempt(point.spec, region.final_system, eliminated)
        return handle.system

    def regimes(self, point: CertifiedPoint) -> RegimeRecord:
        """The final attempt signature and every lifted split's (kind, regime, margin) (§4.2.4).

        The margin is `tp_margin` at the split's own converged T and P on its feed flows for TP-
        and PH-type splits alike (D7: the region's closure judges both by the TP test there);
        `None` for `ZERO_FLOW`."""
        system = self.held_system(point)
        assert point.state is not None
        route = _handle(point).route
        assert route is not None
        flowsheet = route.binding.flowsheet
        splits = region_splits(instances_of(flowsheet), flowsheet.units(), flowsheet.components)
        regimes = dict(item for item in system.signature if len(item) == 2)
        provider = flowsheet.provider
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
            if regime != "ZERO_FLOW":
                _, margin = tp_margin(
                    provider,
                    [float(point.state[name]) for name in split.feed],
                    float(point.state[split.temperature]),
                    float(point.state[split.pressure]),
                    context,
                    flowsheet.components,
                )
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
    ) -> SensitivityResult:
        """M03's sensitivity (ADR 0031) at the point on its held system, with its certificate
        (Q1′) and its splits' margins (Q4, Q4′). The twin is the host's cached one when the
        requested parameters include every decision (the same function), else the point's own."""
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
                CertificateEvidence.of(point.certificate) if point.certificate is not None else None
            ),
            splits=self.regimes(point).splits,
            twin_factory=twin_factory,
        )

    def twin(self, decision_ids: Sequence[str]) -> ParametricTwin:
        """The base problem's twin with `decision_ids` symbolic, compiled once per ids: the same
        function at every point, since the decision map admits no other change (§4.2.2)."""
        key = tuple(decision_ids)
        if key not in self._twins:
            self._twins[key] = compile_parametric_twin(self.binding.spec, key)
        return self._twins[key]

    def bounds(self, point: CertifiedPoint) -> dict[str, VariableBound]:
        """§4.2.3 over the held system's free columns: T and P by the provider's domain; a flow
        `[0, ∞)`, or unbounded where it is exactly zero at the point; a duty unbounded; any other
        kind K03's bound for it in the production solve, or unbounded where K03 has none."""
        system = self.held_system(point)
        assert point.state is not None
        domain = self.domain()
        kinds = system.spec.variable_kinds
        bounds: dict[str, VariableBound] = {}
        for name in system.free:
            kind = kinds[name]
            if kind == "temperature":
                bounds[name] = VariableBound(*domain["T"], "provider_domain")
            elif kind == "pressure":
                bounds[name] = VariableBound(*domain["P"], "provider_domain")
            elif kind == "molar_flow":
                if point.state[name] == 0.0:
                    bounds[name] = VariableBound(None, None, "zero_at_start_pinned_by_regime")
                else:
                    bounds[name] = VariableBound(0.0, None, "nonnegative_flow")
            elif kind == "heat_rate":
                bounds[name] = VariableBound(None, None, "heat_rate_unbounded")
            elif kind in K03_KIND_BOUNDS:
                bounds[name] = VariableBound(*K03_KIND_BOUNDS[kind], f"k03_kind_bound({kind})")
            else:
                bounds[name] = VariableBound(None, None, f"no_declared_bound({kind})")
        return bounds

    def phase_rows(self, point: CertifiedPoint) -> None:
        """The held-regime admissibility rows are WO-5's (§4.7); until then a revision holds its
        regimes by V4 alone, as SYN-001 does (gate G9's pre-WO-5 expectation)."""
        return None
