"""The `revision_coupled` route's composition: external units, the inner solve at w, the
experiments, the coupling checks and the record (M02 design note §4, §7; ADR 0034 D2–D6;
register R-225, R-227).

`orchestrator.coupling.couple` iterates (X̂, ΔT̂) per external unit and knows nothing of bindings or
experiments; this module hands it the two callables it needs and turns its end into what
`revision_run` writes:

- **External units** are the bound `C1Reactor` instances (variant-backed: `c1.reactor`, the
  stand-in), in instance-id order. A revision with one is on `revision_coupled` (§4.4).
- **The inner solve at w** re-binds the revision with each unit's coupling parameters at w
  (`at_coupling`: the inner `ProblemSpec` is re-compiled, its constants change), plans it with
  `plan_revision` and solves it with `execute_plan` — from the route's initializer chain at
  k = 0, from the base iterate's solution after (`user_start`). Each inner solve records into
  its own trace; its events are appended to the job's trace, so an interruption's partial trace
  keeps every inner solve's events.
- **The experiments** are an `Experiments` object: `LiveExperiments` runs them through the job's
  `ExperimentRunner` (one handshake per job, frozen, §6.1); `revision_run`'s replay hands a
  recorded backend instead (§7.2). The answer is read from the result's boundary envelope:
  ξ_E and T_E are the projected extent and the outlet temperature (M01 §8.9).
- **The floor (§4.2).** δξ = ε_eval Σ|ν_i| n_i / Σν_i² over the reacting components and
  δT = ε_eval T_E, with ε_eval the result's `accuracy.precision_floor_rel` and n the envelope's
  (projected) outlet flows — the raw outlet, which the note names, is within the defect limit
  (10⁻⁶ relative) of it, so the floor estimate moves by that much at most (build log D53).
- **The certificate (§4.4).** Two `residual` checks per unit, `EXT-COUPLING:<unit>:xi` (value
  |ξ_E − X̂ n_N2,in| / n_tot,in, tolerance τ_ξ) and `…:T` (|T_E − T_in − ΔT̂| in K, tolerance
  τ_T), each failing too when the experiment's request inputs are not the certified state's
  inlet bit for bit; `near_threshold` when that check's floor ratio is below 10. One
  `external_model` limitation per unit; `derivative_provenance.external_map` says `unavailable`.
- **The record (§7.1)**, `external-coupling.json`: every variant, the frozen identities, the
  coupling block, every trial point with its experiments' documents embedded, the outcome and
  the reason.
- **R3 (§7.2).** A run that used an out-of-process variant is R3; with in-process variants only,
  the class is the flowsheet's own.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, Protocol

from openflowsheet.adapters.experiments.backends import unmeasured_fingerprint
from openflowsheet.adapters.experiments.request import build_request, experiment_key
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.adapters.variants import Variant
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.canonical import document_sha256
from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.c1 import NU
from openflowsheet.models.c1.reactor import KEY_COMPONENT, C1Reactor
from openflowsheet.orchestrator.coupling import (
    CouplingBlock,
    CouplingRun,
    ExternalAnswer,
    InnerSolve,
    UnitInlet,
    couple,
)
from openflowsheet.orchestrator.execution import PlanRefusal, declaration_identity
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.orchestrator.warm_start import WarmStartCandidate
from openflowsheet.resources import packaged
from openflowsheet.run import solution_state
from openflowsheet.run.compare import KIND_FLOOR, differences, floored_difference
from openflowsheet.thermo import StreamState
from openflowsheet.verify import CheckResult, Limitation
from openflowsheet.verify.certificate import ExternalEvidence

__all__ = [
    "COUPLING_NAME",
    "COUPLING_VERSION",
    "CoupledSolve",
    "CouplingUnsupportedError",
    "Experiments",
    "LiveExperiments",
    "RecordedExperiments",
    "ReplayDivergenceError",
    "answer_of",
    "at_coupling",
    "compact_record",
    "coupling_evidence",
    "coupling_record_problem",
    "external_units",
    "final_constants",
    "iterate_differences",
    "reproducibility_class",
    "solve_coupled",
    "unit_variant",
]

#: ADR 0034 D6: the bundle member beside ADR 0020 D4's files.
COUPLING_NAME: Final = "external-coupling.json"
COUPLING_VERSION: Final = "external-coupling-v1"
ROUTE: Final = "revision_coupled"
#: §4.2: a floor ratio below this sets `near_threshold` on the coupling check.
FLOOR_RATIO_MIN: Final = 10.0


class CouplingUnsupportedError(ValueError):
    """A coupled revision this build cannot iterate (`code`, reported `unsupported(<code>)`)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# -- the external units ---------------------------------------------------------------------------


def external_units(binding: RevisionBinding) -> tuple[C1Reactor, ...]:
    """The bound external units (variant-backed embedded reactors), in instance-id order."""
    found = [unit for unit in binding.flowsheet.instances if isinstance(unit, C1Reactor)]
    return tuple(sorted(found, key=lambda unit: unit.unit_id))


def unit_variant(unit: C1Reactor) -> Variant:
    """The variant the binder resolved for `unit` (its document, hash-pinned by the revision)."""
    return Variant(document=unit.variant, sha256=document_sha256(unit.variant))


def coupling_block(units: Sequence[C1Reactor]) -> tuple[CouplingBlock, Mapping[str, Any]]:
    """The one coupling block every unit's variant carries (the record has one, §7.1)."""
    documents = [dict(unit_variant(unit).coupling) for unit in units]
    if any(document != documents[0] for document in documents[1:]):
        raise CouplingUnsupportedError("coupling_blocks_differ")
    return CouplingBlock.from_document(documents[0]), documents[0]


def at_coupling(binding: RevisionBinding, w: Mapping[str, tuple[float, float]]) -> RevisionBinding:
    """`binding` with each named unit's coupling parameters (X̂, ΔT̂) at `w`; the spec rebuilt.

    Raises `ValueError` naming every key of `w` (sorted) that is not the `unit_id` of a
    `C1Reactor` of the binding (§14.5 D9, R-309). The values are not coerced: callers pass Python
    floats, and they reach the rebuilt units bit for bit."""
    reactors = {
        model.unit_id for model in binding.flowsheet.instances if isinstance(model, C1Reactor)
    }
    unknown = sorted(set(w) - reactors)
    if unknown:
        raise ValueError(
            "not an embedded C1 reactor of this flowsheet: " + ", ".join(map(repr, unknown))
        )
    instances = tuple(
        replace(model, conversion=w[model.unit_id][0], temperature_rise=w[model.unit_id][1])
        if isinstance(model, C1Reactor) and model.unit_id in w
        else model
        for model in binding.flowsheet.instances
    )
    flowsheet = replace(binding.flowsheet, instances=instances)
    return replace(binding, flowsheet=flowsheet, spec=flowsheet.spec())


def final_constants(binding: RevisionBinding, record: Mapping[str, Any]) -> tuple[str, str] | None:
    """§14.5 D8 (R-308) item 2, the R0 guard on the inner solve's constants digest: `(recorded,
    recomputed)`, the record's final inner `constants_sha256` and that of the final inner model
    rebuilt at the record's final w (the recorded floats, bit for bit) through `at_coupling`, or
    `None` when the record holds no final digest. The two must be equal exactly: the same bits go
    through the same canonical encoding on every platform."""
    iterations = record.get("iterations") or []
    if not iterations:
        return None
    final = iterations[-1]
    recorded = (final.get("inner") or {}).get("constants_sha256")
    if not isinstance(recorded, str):
        return None
    flat = [float(value) for value in final["w"]]  # a JSON integer (e.g. 80) is that float
    w = {
        unit.unit_id: (flat[2 * j], flat[2 * j + 1])
        for j, unit in enumerate(external_units(binding))
    }
    return recorded, declaration_identity(at_coupling(binding, w).spec)[1]


def iterate_differences(
    fresh: Mapping[str, Any], recorded: Mapping[str, Any], policy_id: str
) -> list[str]:
    """§14.5 D8 (R-308) item 3: each rerun iteration's `w` and `u` against the record's, under the
    archive's numerical policy, as `coupling_iterate(<k>)…` differences. Iterations are paired in
    order; a different count is the record comparison's (integer control flow, R0)."""
    found: list[str] = []
    for mine, theirs in zip(fresh["iterations"], recorded["iterations"], strict=False):
        for key in ("w", "u"):
            found += [
                f"coupling_iterate({theirs['k']}).{key}{line}"
                for line in differences(mine[key], theirs[key], policy_id=policy_id)
            ]
    return found


# -- the record's floats as a replay compares them (R-317 (b), ADR 0007 D2.2–D2.3) ----------------

#: M02's addendum to the numerical policy (design note §3.6), runtime data since R-317: its rules
#: say how a replay compares each float of the coupling record and of a re-evaluated envelope.
EXTERNAL_POLICY: Final = "benchmarks/m02/numerical_policy_external.yaml"


def _external_rules() -> dict[str, tuple[tuple[re.Pattern[str], Any], ...]]:
    import yaml  # noqa: PLC0415

    document = yaml.safe_load(packaged(EXTERNAL_POLICY).read_text(encoding="utf-8"))
    rules = document["numerical_policy_external"]["rules"]
    return {
        name: tuple((re.compile(rule["path"]), rule.get("compare")) for rule in entries)
        for name, entries in rules.items()
    }


_RULES: Final = _external_rules()


def _comparison(rules: Sequence[tuple[re.Pattern[str], Any]], path: str) -> Any:
    """The `compare` of the first rule whose path matches `path`, `None` when it names none."""
    for pattern, compare in rules:
        if pattern.fullmatch(path):
            return compare
    return None


def _floor(compare: Any, block: Mapping[str, Any]) -> tuple[float, str] | None:
    """A rule's `compare` as an absolute floor and its source, `None` for `relative` (and none)."""
    if isinstance(compare, dict) and "floor" in compare:
        return float(compare["floor"]), "its registered threshold, R-317"
    if isinstance(compare, dict) and "block" in compare:
        name = str(compare["block"])
        return abs(float(block[name])), f"the record's coupling_block.{name}, R-317"
    if isinstance(compare, dict) and "kind" in compare:
        kind = str(compare["kind"])
        return KIND_FLOOR[kind], f"tau_kind of {kind}, R-317"
    return None


def _real(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _classified(
    fresh: Any,
    recorded: Any,
    path: str,
    rules: Sequence[tuple[re.Pattern[str], Any]],
    block: Mapping[str, Any],
    policy_id: str,
    found: list[str],
) -> Any:
    """`fresh` with each float a rule floors or reports replaced by `recorded`'s at the same
    place, each one outside its floor added to `found`; everything else is left as it is, for
    `differences` (and `replay`) to compare under the archive's policy."""
    if isinstance(fresh, dict) and isinstance(recorded, dict):
        return {
            key: _classified(value, recorded[key], f"{path}.{key}", rules, block, policy_id, found)
            if key in recorded
            else value
            for key, value in fresh.items()
        }
    if isinstance(fresh, list) and isinstance(recorded, list) and len(fresh) == len(recorded):
        return [
            _classified(mine, theirs, f"{path}[{index}]", rules, block, policy_id, found)
            for index, (mine, theirs) in enumerate(zip(fresh, recorded, strict=True))
        ]
    if not (_real(fresh) and _real(recorded)):
        return fresh
    compare = _comparison(rules, path)
    if compare == "shape":
        # A secant quantity, reported and not compared (D2.2's comparability window): its R0
        # consequences — the step's kind and k — are compared exactly.
        return recorded
    floor = _floor(compare, block)
    if floor is None:
        return fresh
    found += floored_difference(
        fresh, recorded, f"<root>{path}", floor[0], floor[1], policy_id=policy_id
    )
    return recorded


def record_differences(
    fresh: Mapping[str, Any], recorded: Mapping[str, Any], policy_id: str
) -> tuple[dict[str, Any], list[str]]:
    """R-317 (b): a rerun's `external-coupling.json` against the record. Returns `fresh` with each
    float the addendum floors or reports (`compare` of `rules.coupling`) replaced by the record's,
    and every one outside its floor as an `external-coupling.json<root>…` difference. The rest —
    relative floats, exact members, structure — is `replay`'s, under the archive's policy."""
    found: list[str] = []
    shaped = _classified(
        fresh, recorded, "", _RULES["coupling"], recorded["coupling_block"], policy_id, found
    )
    return shaped, [f"{COUPLING_NAME}{line}" for line in found]


#: Where a failure bundle carries the record's compact copy (`compact_record`).
COMPACT_PATH: Final = ".observations.external_coupling"
_DIGEST: Final = re.compile(r"[0-9a-f]{64}")


def compact_differences(
    fresh: Mapping[str, Any], recorded: Mapping[str, Any], block: Mapping[str, Any], policy_id: str
) -> tuple[dict[str, Any], list[str]]:
    """Build log D130 (D124): a rerun's compact copy of the record (a failure bundle's
    `observations.external_coupling`) against the archive's. Its floats sit at the record's own
    paths, so `rules.coupling` classifies them as `record_differences` does (R-317 (b)), against
    the archived record's `coupling_block`; `record_sha256` digests the record's floats and is
    compared for shape (R-318's reason): a well-formed digest on both sides is replaced by the
    archive's, anything else is left for `replay`, so a malformed one is a difference."""
    found: list[str] = []
    shaped = _classified(fresh, recorded, "", _RULES["coupling"], block, policy_id, found)
    mine, theirs = shaped.get("record_sha256"), recorded.get("record_sha256")
    if (
        isinstance(mine, str)
        and isinstance(theirs, str)
        and _DIGEST.fullmatch(mine)
        and _DIGEST.fullmatch(theirs)
    ):
        shaped["record_sha256"] = theirs
    return shaped, [
        f"failure-bundle.json{line.replace('<root>', f'<root>{COMPACT_PATH}', 1)}" for line in found
    ]


def envelope_differences(
    fresh: Mapping[str, Any], recorded: Mapping[str, Any], policy_id: str
) -> list[str]:
    """R-317 (b): a re-evaluated envelope against the recorded one, each float at the floor of
    `rules.result`'s `.envelope.<field>` rule (`defect_rel` at 10⁻⁶, ADR 0027 D3; `defect` and the
    outlet flows at the molar-flow floor; the rest relative), as `<root>…` differences."""
    found: list[str] = []
    rules = tuple(
        (re.compile(pattern.pattern.removeprefix(r"\.envelope")), compare)
        for pattern, compare in _RULES["result"]
        if pattern.pattern.startswith(r"\.envelope")
    )
    shaped = _classified(fresh, recorded, "", rules, {}, policy_id, found)
    return found + differences(shaped, recorded, policy_id=policy_id)


def inlet_of(binding: RevisionBinding, unit: C1Reactor, state: Mapping[str, float]) -> UnitInlet:
    """`unit`'s inlet, read exactly from `state` (§4.2)."""
    stream = binding.flowsheet.wiring[unit.unit_id].one("inlet")
    n = tuple(float(state[flow_id(stream, component)]) for component in unit.components)
    return UnitInlet(
        n=n,
        T=float(state[temperature_id(stream)]),
        P=float(state[pressure_id(stream)]),
        n_key=n[unit.components.index(KEY_COMPONENT)],
    )


def reproducibility_class(units: Sequence[C1Reactor], flowsheet_class: str) -> str:
    """§7.2: R3 iff any variant used is out of process; else the flowsheet's own class."""
    if any(unit_variant(unit).kind == "out_of_process" for unit in units):
        return "R3"
    return flowsheet_class


# -- the experiments ------------------------------------------------------------------------------


class Experiments(Protocol):
    """One experiment of one external unit at one inlet, and the job's frozen identities."""

    def evaluate(self, unit: C1Reactor, variant: Variant, inlet: UnitInlet) -> ExternalAnswer: ...

    def frozen(self, variant: Variant) -> Mapping[str, Any] | None: ...


def _floors(result: Mapping[str, Any], envelope: Mapping[str, Any]) -> tuple[float, float] | None:
    """§4.2's propagated precision floors (δξ, δT), or `None` when ε_eval is zero."""
    eps = float(result["accuracy"]["precision_floor_rel"])
    if eps == 0.0:
        return None
    outlet = envelope["outlet"]
    weighted = sum(abs(nu) * float(n) for nu, n in zip(NU, outlet["n"], strict=True) if nu != 0)
    return eps * weighted / sum(nu * nu for nu in NU), eps * float(outlet["T"])


def answer_of(
    request: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    envelope: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    cache_hit: bool,
    *,
    attributed: Mapping[str, Any] | None = None,
) -> ExternalAnswer:
    """An experiment's outcome as the coupling reads it (§4.2–§4.3): transient when there is no
    deterministic result; `ok`, `zero_flow` or a deterministic refusal from its envelope.
    `attributed` is the request the answer is attributed to (R-317 (a)), `request` (the one sent)
    unless a replay recomputed it."""
    attributed_request = dict(request if attributed is None else attributed)
    documents = {
        "request": dict(request),
        "result": None if result is None else dict(result),
        "attempts": [dict(attempt) for attempt in attempts],
        "cache_hit": cache_hit,
    }
    code = str(envelope["code"])
    if result is None:
        return ExternalAnswer(
            "transient", code, documents=documents, attributed_request=attributed_request
        )
    if envelope["status"] != "ok":
        return ExternalAnswer(
            "refused", code, documents=documents, attributed_request=attributed_request
        )
    if code == "ZERO_FLOW":
        return ExternalAnswer(
            "zero_flow", code, documents=documents, attributed_request=attributed_request
        )
    floors = _floors(result, envelope)
    return ExternalAnswer(
        "ok",
        code,
        xi=float(envelope["xi"]),
        T_out=float(envelope["outlet"]["T"]),
        floor_xi=None if floors is None else floors[0],
        floor_T=None if floors is None else floors[1],
        documents=documents,
        attributed_request=attributed_request,
    )


def frozen_document(variant: Variant, environment: Any) -> dict[str, Any]:
    """§7.1's `frozen` entry of a unit: the variant and the job's frozen fingerprint."""
    fingerprint = environment.fingerprint
    if fingerprint is None:  # the job's handshake measured none (R-236)
        status = environment.failure.status if environment.failure is not None else "unknown"
        fingerprint = unmeasured_fingerprint(variant, status)
    return {
        "variant_sha256": variant.sha256,
        "fingerprint_sha256": environment.sha256,
        "fingerprint": dict(fingerprint),
    }


class LiveExperiments:
    """Experiments through the job's `ExperimentRunner` (records, cache, retry, frozen handshake).
    `on_evaluated` is called after each experiment (the job emits the records it wrote)."""

    def __init__(
        self, runner: ExperimentRunner, *, on_evaluated: Callable[[], None] | None = None
    ) -> None:
        self.runner = runner
        self.on_evaluated = on_evaluated

    def evaluate(self, unit: C1Reactor, variant: Variant, inlet: UnitInlet) -> ExternalAnswer:
        outcome = self.runner.run(
            variant,
            StreamState(n=inlet.n, temperature=inlet.T, pressure=inlet.P),
            unit.components,
            unit.n_tubes,
        )
        if self.on_evaluated is not None:
            self.on_evaluated()
        return answer_of(
            outcome.request, outcome.result, outcome.envelope, outcome.attempts, outcome.cache_hit
        )

    def frozen(self, variant: Variant) -> Mapping[str, Any] | None:
        environment = self.runner.frozen_environment(variant)
        return None if environment is None else frozen_document(variant, environment)


class ReplayDivergenceError(RuntimeError):
    """§7.2: a recomputed request that is not the record's (`difference` names
    `external_request(<k>, <unit>)`); the replay is a `MISMATCH` and nothing is served."""

    def __init__(self, difference: str) -> None:
        super().__init__(difference)
        self.difference = difference


def _identity(request: Mapping[str, Any]) -> dict[str, Any]:
    """A request's identity members: everything but its inputs and its key (§7.2)."""
    return {key: value for key, value in request.items() if key not in ("inputs", "experiment_key")}


class RecordedExperiments:
    """§7.2's recorded backend: the coupling re-run against `external-coupling.json`.

    The n-th experiment the rerun asks for is the record's n-th (in its iterations' order). Its
    request is recomputed at the rerun's inlet: the identity members (model, variant, provider,
    n_tubes, sweep ratio, fingerprint) must equal the record's exactly, and the inputs agree
    within ADR 0007 D2 (bitwise is observed, not required) — else `ReplayDivergenceError`. Then an
    **out-of-process** result is served from the record (`replayed`), and an **in-process** one
    (the stand-in) is re-evaluated in `scratch` and its envelope compared with the record's
    (`envelope_differences`, R-317 (b)); the rerun reads the re-evaluated
    envelope. Either way the rerun's record embeds the recorded documents, so the two records
    differ only where the coupling's numbers do."""

    def __init__(
        self, record: Mapping[str, Any], *, provider: Any, scratch: Path, policy_id: str
    ) -> None:
        self.record = record
        self.provider = provider
        self.policy_id = policy_id
        self.queue = [
            (int(item["k"]), unit_id, entry)
            for item in record["iterations"]
            for unit_id, entry in item["units"].items()
        ]
        self.position = 0
        self.replayed = 0
        self.reevaluated = 0
        self.differences: list[str] = []
        self.runner = ExperimentRunner(
            ExperimentStore(scratch, ListArtifactSink()),
            provider,
            EvaluationContext(model_version="replay-from-record", constants_sha256="0" * 64),
        )

    def evaluate(self, unit: C1Reactor, variant: Variant, inlet: UnitInlet) -> ExternalAnswer:
        if self.position >= len(self.queue):
            raise ReplayDivergenceError(
                f"external_request(-, {unit.unit_id}): the record holds no further experiment"
            )
        k, unit_id, entry = self.queue[self.position]
        self.position += 1
        where = f"external_request({k}, {unit.unit_id})"
        if unit_id != unit.unit_id:
            raise ReplayDivergenceError(f"{where}: the record's experiment is {unit_id}'s")
        recorded = entry["request"]
        state = StreamState(n=inlet.n, temperature=inlet.T, pressure=inlet.P)
        fresh = None
        if variant.kind == "out_of_process":
            frozen = self.record["frozen"].get(unit.unit_id)
            if frozen is None:
                raise ReplayDivergenceError(f"{where}: the record froze no environment")
            request = build_request(
                variant,
                self.provider.describe(),
                unit.n_tubes,
                unit.components,
                state,
                str(frozen["fingerprint_sha256"]),
            )
        else:
            fresh = self.runner.run(variant, state, unit.components, unit.n_tubes)
            request = dict(fresh.request)
        if _identity(request) != _identity(recorded):
            names = sorted(
                key
                for key in set(_identity(request)) | set(_identity(recorded))
                if request.get(key) != recorded.get(key)
            )
            raise ReplayDivergenceError(f"{where}: identity differs in {names}")
        found = differences(request["inputs"], recorded["inputs"], policy_id=self.policy_id)
        if found:
            raise ReplayDivergenceError(f"{where}.inputs{found[0]}")
        result = entry["result"]
        if fresh is None:
            self.replayed += 1
            envelope = result["envelope"] if result is not None else _transient(entry)
        else:
            self.reevaluated += 1
            envelope = dict(fresh.envelope)
            if result is None or fresh.result is None:
                if (result is None) != (fresh.result is None):
                    self.differences.append(f"external_result({k}, {unit.unit_id}): outcome class")
            else:
                self.differences += [
                    f"external_result({k}, {unit.unit_id}){line}"
                    for line in envelope_differences(
                        envelope, result["envelope"], policy_id=self.policy_id
                    )
                ]
        # R-317 (a): the rerun's record embeds the recorded (served) documents; the answer is
        # attributed to the request recomputed here, at the rerun's inlet.
        return answer_of(
            recorded, result, envelope, entry["attempts"], entry["cache_hit"], attributed=request
        )

    def frozen(self, variant: Variant) -> Mapping[str, Any] | None:
        for entry in self.record["frozen"].values():
            if entry["variant_sha256"] == variant.sha256:
                return dict(entry)
        return None


def coupling_record_problem(record: Any) -> str | None:
    """§7.2 step 1: why `external-coupling.json` is not a record this replay can read — invalid
    against `experiment.schema.json#/$defs/coupling`, or an embedded request whose key is not its
    content's — or `None`."""
    from openflowsheet.application.types import schema_errors

    errors = schema_errors("experiment.schema.json#/$defs/coupling", record)
    if errors:
        return f"schema: {errors[0]}"
    for item in record["iterations"]:
        for unit_id, entry in item["units"].items():
            request = entry["request"]
            if request is not None and experiment_key(request) != request["experiment_key"]:
                return f"request_key(k={item['k']}, {unit_id})"
    return None


def _transient(entry: Mapping[str, Any]) -> dict[str, Any]:
    """A recorded transient outcome's envelope (the record keeps its attempts, not an envelope):
    `external_<status>` of its last attempt, as the runner's refusal names it."""
    attempts = entry["attempts"]
    status = attempts[-1]["execution"]["status"] if attempts else "unknown"
    return {"status": "error", "code": f"external_{status}"}


# -- the coupled solve ----------------------------------------------------------------------------


@dataclass(frozen=True)
class InnerRun:
    """One inner solve's objects: the binding at its w, the plan (or T02's refusal), T01's report
    and the plan run (`None` when the plan was refused)."""

    binding: RevisionBinding
    plan: Any
    report: Any
    run: PlanResult | None


@dataclass(frozen=True)
class CoupledSolve:
    """The coupling's end and what `revision_run` writes from it."""

    coupling: CouplingRun
    units: tuple[C1Reactor, ...]
    #: The last inner solve's objects (the converged one on `CONVERGED`).
    inner: InnerRun
    #: `external-coupling.json`.
    record: Mapping[str, Any]


def solve_coupled(
    binding: RevisionBinding,
    *,
    policy: SolvePolicy,
    experiments: Experiments,
    trace: Trace | None = None,
    warm_start: WarmStartCandidate | None = None,
    on_iteration: Callable[[int, int], None] | None = None,
) -> CoupledSolve:
    """The outer coupling of `binding`'s external units (§4.3). `warm_start` is the route's
    source-2 candidate, read by the k = 0 inner solve only (under a policy whose chain names it);
    `trace` (the job's) receives every inner solve's events."""
    units = external_units(binding)
    if not units:
        raise CouplingUnsupportedError("no_external_unit")
    block, block_document = coupling_block(units)
    by_id = {unit.unit_id: unit for unit in units}
    unit_variants = {unit.unit_id: unit_variant(unit) for unit in units}

    def solve_inner(w: Mapping[str, tuple[float, float]], start: Any) -> InnerSolve:
        bound = at_coupling(binding, w)
        inner_trace = Trace()
        label = "route_initializer" if start is None else "user_start"
        model_version, constants = declaration_identity(bound.spec)
        try:
            plan, report = plan_revision(bound, policy, trace=inner_trace)
            if isinstance(plan, PlanRefusal):
                payload = InnerRun(bound, plan, report, None)
                return InnerSolve(
                    str(plan.outcome), None, {}, None, label, constants, None, payload
                )
            run = execute_plan(
                plan=plan,
                flowsheet=bound.flowsheet,
                spec=bound.spec,
                policy=policy,
                trace=inner_trace,
                user_start=start,
                warm_start=warm_start if start is None else None,
            )
        finally:
            if trace is not None:
                trace.extend(inner_trace.events)
        payload = InnerRun(bound, plan, report, run)
        iterations = sum(step.iterations for step in run.steps)
        if run.outcome != "CONVERGED" or run.state is None:
            return InnerSolve(
                str(run.outcome), None, {}, iterations, label, constants, None, payload
            )
        state = dict(run.state)
        digest = solution_state.document(bound.spec.variable_ids, state_vector(bound.spec, state))
        return InnerSolve(
            "CONVERGED",
            state,
            {unit.unit_id: inlet_of(bound, unit, state) for unit in units},
            iterations,
            label,
            constants,
            str(digest["state_sha256"]),
            payload,
        )

    def evaluate(unit_id: str, inlet: UnitInlet) -> ExternalAnswer:
        return experiments.evaluate(by_id[unit_id], unit_variants[unit_id], inlet)

    coupling = couple(
        [unit.unit_id for unit in units],
        block,
        solve_inner,
        evaluate,
        on_iteration=on_iteration,
    )
    assert coupling.final is not None and isinstance(coupling.final.payload, InnerRun)
    frozen = {
        unit_id: entry
        for unit_id, variant in unit_variants.items()
        if (entry := experiments.frozen(variant)) is not None
    }
    record = {
        "schema_version": COUPLING_VERSION,
        "route": ROUTE,
        "variants": {unit_id: dict(variant.document) for unit_id, variant in unit_variants.items()},
        "frozen": frozen,
        "coupling_block": dict(block_document),
        "iterations": [dict(item) for item in coupling.iterations],
        "outcome": coupling.outcome,
        "reason": coupling.reason,
    }
    return CoupledSolve(coupling, units, coupling.final.payload, record)


# -- the certificate's evidence (§4.4) -------------------------------------------------------------


def _bits(value: float) -> str:
    return float(value).hex()


def _inputs_equal(request: Mapping[str, Any], inlet: UnitInlet) -> bool:
    """The experiment's request inputs are the certified inlet, bit for bit (signed zero too)."""
    inputs = request["inputs"]
    return [_bits(value) for value in inputs["n"]] == [_bits(value) for value in inlet.n] and (
        _bits(inputs["T"]),
        _bits(inputs["P"]),
    ) == (_bits(inlet.T), _bits(inlet.P))


def _check(
    check_id: str,
    unit: str,
    value: float,
    tolerance: float,
    equal: bool,
    ratio: float | None,
    reproducibility: str,
) -> CheckResult:
    passed = value <= tolerance and equal
    return CheckResult(
        id=check_id,
        category="residual",
        subject=unit,
        result="pass" if passed else "fail",
        scope="evaluated",
        value=value,
        tolerance=tolerance,
        reason=""
        if equal
        else "the experiment's request inputs are not the certified state's inlet bit for bit",
        near_threshold=ratio is not None and ratio < FLOOR_RATIO_MIN,
        independence_qualification=f"external model, {reproducibility}",
    )


def coupling_evidence(solved: CoupledSolve, state: Mapping[str, float]) -> ExternalEvidence:
    """§4.4's checks, limitations and derivative record at the certified `state` (the converged
    inner solution), from the record's final iterate."""
    coupling = solved.coupling
    final = coupling.iterations[-1]
    binding = solved.inner.binding
    checks: list[CheckResult] = []
    limitations: list[Limitation] = []
    block = CouplingBlock.from_document(solved.record["coupling_block"])
    for unit in solved.units:
        variant = unit_variant(unit)
        reproducibility = "R3" if variant.kind == "out_of_process" else "R1"
        entry = final["units"][unit.unit_id]
        inlet = inlet_of(binding, unit, state)
        x_hat, dt_hat = coupling.w[unit.unit_id]
        # R-317 (a): the certified inlet against the request the answer is attributed to — live,
        # the request sent; in a replay, the one recomputed at the rerun's inlet.
        answer = coupling.answers[unit.unit_id]
        attributed = answer.attributed_request
        equal = _inputs_equal(entry["request"] if attributed is None else attributed, inlet)
        n_tot = inlet.n_tot
        xi_value = abs(entry["xi_E"] - x_hat * inlet.n_key) / n_tot if n_tot > 0.0 else 0.0
        t_value = abs(entry["T_E"] - inlet.T - dt_hat)
        checks.append(
            _check(
                f"EXT-COUPLING:{unit.unit_id}:xi",
                unit.unit_id,
                xi_value,
                block.tau_xi_rel,
                equal,
                entry["floor_ratio_xi"],
                reproducibility,
            )
        )
        checks.append(
            _check(
                f"EXT-COUPLING:{unit.unit_id}:T",
                unit.unit_id,
                t_value,
                block.tau_T_K,
                equal,
                entry["floor_ratio_T"],
                reproducibility,
            )
        )
        limitations.append(
            Limitation(
                "external_model",
                {
                    "unit": unit.unit_id,
                    "variant_id": variant.variant_id,
                    "synthetic": variant.synthetic,
                    "reproducibility": reproducibility,
                    "discretization_estimate": variant.accuracy["discretization_estimate"],
                },
            )
        )
    return ExternalEvidence(
        checks=tuple(checks),
        limitations=tuple(limitations),
        derivatives={unit.unit_id: "unavailable" for unit in solved.units},
    )


def compact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """The record without its embedded documents: what a failure bundle's observations carry
    (each experiment by key, cache hit, status and code; the documents are the bundle member's)."""
    iterations = []
    for item in record["iterations"]:
        units = {}
        for unit_id, entry in item["units"].items():
            result = entry["result"]
            units[unit_id] = {
                "experiment_key": entry["request"]["experiment_key"],
                "cache_hit": entry["cache_hit"],
                "status": None if result is None else result["envelope"]["status"],
                "code": None if result is None else result["envelope"]["code"],
                "xi_E": entry["xi_E"],
                "T_E": entry["T_E"],
                "r_xi": entry["r_xi"],
                "r_T": entry["r_T"],
            }
        iterations.append(
            {
                "k": item["k"],
                "w": list(item["w"]),
                "inner_outcome": item["inner"]["outcome"],
                "rho": item["rho"],
                "step": item["step"]["kind"],
                "units": units,
            }
        )
    return {
        "outcome": record["outcome"],
        "reason": record["reason"],
        "record": COUPLING_NAME,
        "record_sha256": document_sha256(record),
        "iterations": iterations,
    }
