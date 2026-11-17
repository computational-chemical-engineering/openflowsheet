"""The job request documents of the application contract v1 (T07 design note §5.3, J3; ADR 0019
D2; ADR 0076 I-12a).

`as_document` always writes every member, defaults included, so a request's document is its
normalized form and `request_sha256` of an omitted default equals that of the default spelt out
(§5.3).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Self

from openflowsheet.application.documents import checked
from openflowsheet.application.jobs.model import JobOperation
from openflowsheet.canonical import document_sha256
from openflowsheet.schema_check import validate_document

#: §5.3 as amended by ruling round 1 R2.3: `policies.DEFAULT_POLICY_ID`, the reserved id that
#: resolves at admission to the route's registered policy; the schema default of
#: `solve_body.policy_id`.
DEFAULT_SOLVE_POLICY_ID: Final[str] = "default"


# ===================================================================== JobRequest §5.3 (J3)


@dataclass(frozen=True)
class Budgets:
    """§5.3 `$defs/budgets`. `None`: the capability's default, else no limit (§8.3)."""

    wall_time_s: float | None = None

    def as_document(self) -> dict[str, Any]:
        return {"wall_time_s": self.wall_time_s}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(wall_time_s=document.get("wall_time_s"))


@dataclass(frozen=True)
class WarmStartDeclaration:
    """`$defs/solve_body/warm_start` (ADR 0070, ADR 0019 Amendment 15): a declared start, never a
    constraint. `job_id` names a solve job of this project whose solution state seeds the inner
    start (`explicit-v1`); `coupling` declares the outer iterate w₀ per coupled unit, as
    `{unit: (X, dT_K)}`. The certificate judges the converged answer."""

    job_id: str | None = None
    coupling: Mapping[str, tuple[float, float]] | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        if self.job_id is not None:
            document["job_id"] = self.job_id
        if self.coupling is not None:
            document["coupling"] = {
                unit: {"X": x, "dT_K": dt} for unit, (x, dt) in self.coupling.items()
            }
        return document

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        coupling = document.get("coupling")
        return cls(
            job_id=document.get("job_id"),
            coupling=None
            if coupling is None
            else {unit: (item["X"], item["dT_K"]) for unit, item in coupling.items()},
        )


@dataclass(frozen=True)
class SolveBody:
    """§5.3 `$defs/solve_body`. `warm_start` (ADR 0070) appears in the document, and so in
    `request_sha256`, only when it is declared: a request without it is unchanged."""

    revision_id: str
    policy_id: str = DEFAULT_SOLVE_POLICY_ID
    check_tolerances: Mapping[str, float] = field(default_factory=dict)
    max_property_calls: int | None = None
    warm_start: WarmStartDeclaration | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "revision_id": self.revision_id,
            "policy_id": self.policy_id,
            "check_tolerances": dict(self.check_tolerances),
            "max_property_calls": self.max_property_calls,
        }
        if self.warm_start is not None:
            document["warm_start"] = self.warm_start.as_document()
        return document

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        warm_start = document.get("warm_start")
        return cls(
            revision_id=document["revision_id"],
            policy_id=document.get("policy_id", DEFAULT_SOLVE_POLICY_ID),
            check_tolerances=dict(document.get("check_tolerances", {})),
            max_property_calls=document.get("max_property_calls"),
            warm_start=None if warm_start is None else WarmStartDeclaration._build(warm_start),
        )


@dataclass(frozen=True)
class ReproduceBody:
    """§5.3 `$defs/reproduce_body`."""

    bundle_artifact_id: str
    rerun: bool = True

    def as_document(self) -> dict[str, Any]:
        return {"bundle_artifact_id": self.bundle_artifact_id, "rerun": self.rerun}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            bundle_artifact_id=document["bundle_artifact_id"],
            rerun=document.get("rerun", True),
        )


@dataclass(frozen=True)
class ExperimentModel:
    """`experiment.schema.json#/$defs/model_ref`: a variant-backed model (M02 design note §6.1)."""

    id: str
    version: str
    artifact_ref: str

    def as_document(self) -> dict[str, Any]:
        return {"id": self.id, "version": self.version, "artifact_ref": self.artifact_ref}


@dataclass(frozen=True)
class ExperimentInlet:
    """`experiment.schema.json#/$defs/inputs`: a process inlet in SI units (mol/s, K, Pa), copied
    exactly — no Quantity, no conversion (M02 design note §3.5)."""

    components: tuple[str, ...]
    n: tuple[float, ...]
    temperature: float  # `T`, K
    pressure: float  # `P`, Pa

    def as_document(self) -> dict[str, Any]:
        return {
            "components": list(self.components),
            "n": list(self.n),
            "T": self.temperature,
            "P": self.pressure,
        }


@dataclass(frozen=True)
class ExperimentBody:
    """`experiment.schema.json#/$defs/experiment_body` (ADR 0033 D9; M02 design note §3.5): one
    experiment per job. The inlet is the experiment's definition, a model input — never a solver
    state (R-235)."""

    model: ExperimentModel
    inlet: ExperimentInlet
    n_tubes: float
    cache: Literal["use", "bypass"] = "use"

    def as_document(self) -> dict[str, Any]:
        return {
            "model": self.model.as_document(),
            "inlet": self.inlet.as_document(),
            "n_tubes": self.n_tubes,
            "cache": self.cache,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        model, inlet = document["model"], document["inlet"]
        return cls(
            model=ExperimentModel(
                id=model["id"], version=model["version"], artifact_ref=model["artifact_ref"]
            ),
            inlet=ExperimentInlet(
                components=tuple(inlet["components"]),
                n=tuple(inlet["n"]),
                temperature=inlet["T"],
                pressure=inlet["P"],
            ),
            n_tubes=document["n_tubes"],
            cache=document.get("cache", "use"),
        )


@dataclass(frozen=True)
class SurrogateStudyParent:
    """`surrogate-manifest.schema.json#/$defs/surrogate_study_body/parent`: a registered variant by
    id and SHA-256."""

    model_id: str
    variant_id: str
    variant_sha256: str

    def as_document(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "variant_id": self.variant_id,
            "variant_sha256": self.variant_sha256,
        }


@dataclass(frozen=True)
class SurrogateStudyBody:
    """`surrogate-manifest.schema.json#/$defs/surrogate_study_body` (ADR 0037 D6; M04 spec §10.3):
    one registered plan of one parent, within a budget of cold experiments."""

    parent: SurrogateStudyParent
    plan_id: str
    max_cold_experiments: int

    def as_document(self) -> dict[str, Any]:
        return {
            "parent": self.parent.as_document(),
            "plan_id": self.plan_id,
            "budget": {"max_cold_experiments": self.max_cold_experiments},
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        parent = document["parent"]
        return cls(
            parent=SurrogateStudyParent(
                model_id=parent["model_id"],
                variant_id=parent["variant_id"],
                variant_sha256=parent["variant_sha256"],
            ),
            plan_id=document["plan_id"],
            max_cold_experiments=document["budget"]["max_cold_experiments"],
        )


@dataclass(frozen=True)
class OptimizeBody:
    """`optimization-request.schema.json#/$defs/optimize_body` (ADR 0071, ADR 0019 Amendment 16;
    OPT design §4.10): `solve_body`'s members and the optimization request, judged in the job."""

    revision_id: str
    request: Mapping[str, Any]
    policy_id: str = DEFAULT_SOLVE_POLICY_ID
    check_tolerances: Mapping[str, float] = field(default_factory=dict)
    max_property_calls: int | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "request": copy.deepcopy(dict(self.request)),
            "policy_id": self.policy_id,
            "check_tolerances": dict(self.check_tolerances),
            "max_property_calls": self.max_property_calls,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            revision_id=document["revision_id"],
            request=copy.deepcopy(dict(document["request"])),
            policy_id=document.get("policy_id", DEFAULT_SOLVE_POLICY_ID),
            check_tolerances=dict(document.get("check_tolerances", {})),
            max_property_calls=document.get("max_property_calls"),
        )

    def solve_body(self) -> SolveBody:
        """The solve members as a `SolveBody`: the start and V1 re-solves are production solves,
        whose policies resolve as a `solve` job's do (`admission.resolve_policies`)."""
        return SolveBody(
            revision_id=self.revision_id,
            policy_id=self.policy_id,
            check_tolerances=dict(self.check_tolerances),
            max_property_calls=self.max_property_calls,
        )


JobBody = SolveBody | ReproduceBody | ExperimentBody | SurrogateStudyBody | OptimizeBody

#: J3: one body type per operation, as one `oneOf` branch per enum value in the schema.
_BODY_TYPES: Final[
    Mapping[
        str,
        type[SolveBody]
        | type[ReproduceBody]
        | type[ExperimentBody]
        | type[SurrogateStudyBody]
        | type[OptimizeBody],
    ]
] = {
    "solve": SolveBody,
    "reproduce": ReproduceBody,
    "experiment": ExperimentBody,
    "surrogate_study": SurrogateStudyBody,
    "optimize": OptimizeBody,
}


@dataclass(frozen=True)
class JobRequest:
    """§5.3 `job.schema.json#/$defs/job_request`: the operation selects the body (J3)."""

    operation: JobOperation
    idempotency_key: str
    body: JobBody
    budgets: Budgets = field(default_factory=Budgets)

    def __post_init__(self) -> None:
        expected = _BODY_TYPES.get(self.operation)
        if expected is None:
            raise ValueError(f"operation {self.operation!r} is not one of {sorted(_BODY_TYPES)}")
        if not isinstance(self.body, expected):
            raise ValueError(
                f"operation {self.operation!r} takes a {expected.__name__}, "
                f"not a {type(self.body).__name__}"
            )

    def as_document(self) -> dict[str, Any]:
        """The normalized request: every optional member written, at its default if omitted."""
        return {
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
            "budgets": self.budgets.as_document(),
            "body": self.body.as_document(),
        }

    @property
    def request_sha256(self) -> str:
        """§5.3: SHA-256 of the canonical JSON of the normalized request. Not policy-resolved."""
        return document_sha256(self.as_document())

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "job.schema.json#/$defs/job_request"
        validate_document(reference, document)
        return checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        operation = document["operation"]
        if operation not in _BODY_TYPES:
            # A schema-valid operation this build cannot run: refused here, typed, never routed
            # to another operation's body.
            raise ValueError(f"operation {operation!r} is not executable by this build")
        return cls(
            operation=operation,
            idempotency_key=document["idempotency_key"],
            body=_BODY_TYPES[operation]._build(document["body"]),
            budgets=Budgets._build(document.get("budgets", {})),
        )


def normalize_job_request(document: Mapping[str, Any]) -> dict[str, Any]:
    """§5.3: the request with every omitted optional member filled by its schema default."""
    return JobRequest.from_document(document).as_document()


def request_sha256(document: Mapping[str, Any]) -> str:
    """§5.3: the hash of the *normalized* request, so an omitted default equals it spelt out."""
    return JobRequest.from_document(document).request_sha256
