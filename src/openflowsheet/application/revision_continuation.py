"""Revision continuation's application half (ADR 0072; RRC design note §5.3, §5.4, §5.8, §5.9).

The orchestrator never reads a store: under `RRC-revision-v1` on `revision_eo` the application
finds the source, assembles it and hands the orchestrator a `RevisionContinuationCandidate` or a
typed `RevisionContinuationRefusal` (`orchestrator/revision_continuation.py`), and afterwards
writes what happened into `solve-path.json` as the `revision_continuation` member, from which a
rerun rebuilds the same input without a store (ADR 0024 D4/D5's pattern).

**Selection `store-nearest-verified-ancestor-v1`** (`find_source`; run only, never on rerun):
walk `parent_revision` from the target, the target excluded; for each ancestor, parent first,
ADR 0024's `latest_verified_solution` over that one revision; the first hit wins and nothing
further is searched. None: `absent(no_verified_ancestor)`.

**Assembly** (`assemble`; the first failure decides, each a `rejected` refusal):

- **A1 integrity**: a certificate with the identity, the root's digest and a final signature,
  else `integrity(certificate)`; the solution-state document intact (schema, ids, its own
  `state_sha256`) and its `state_sha256` the certificate's `root_fingerprint.full_state_sha256`,
  else `integrity(state_sha256)`.
- **A2 source identity** (run only): the ancestor document binds with the target's binder
  configuration, else `source_binding(<code>)`; its `declaration_identity` is the certificate's
  `(model_version, constants_sha256)`, else `source_identity(<first differing field>)`.
- **A3 continuable** (§5.4, `not_continuable`): a registered allowlist of operating values;
  everything else is refused, default deny.

A rerun (`recorded_source`) does no lookup and no binding: a recorded `absent` and a recorded A2
refusal are passed as they are; otherwise the candidate is rebuilt from the member and A1 and A3
run again, then the orchestrator's pure checks.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revisions import CONTENT_HASH_EXCLUDED
from openflowsheet.application.transactions import ELEMENT_MEMBERS, element_diff
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.revision_continuation import (
    RECORD,
    SELECTION,
    RevisionContinuationCandidate,
    RevisionContinuationRecord,
    RevisionContinuationRefusal,
)
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.orchestrator.warm_start import intact

if TYPE_CHECKING:
    from openflowsheet.application.revision_binding import SurrogateResolver
    from openflowsheet.application.store import ProjectStore

__all__ = [
    "CONTINUABLE_FIELDS",
    "CONTINUABLE_MEMBERS",
    "CONTINUABLE_PARAMETERS",
    "CONTINUABLE_SPECIFICATION_PATHS",
    "REVISION_RECOVERY",
    "ContinuationSource",
    "assemble",
    "continues_revisions",
    "find_source",
    "not_continuable",
    "recorded_source",
]

#: §5.2: the `eo_recovery` value under which the application supplies a source (`RRC-revision-v1`).
REVISION_RECOVERY: Final = "homotopy_or_revision_continuation_or_sequential_restart"
#: §5.4: the top-level members a continuable difference may change (they describe the revision).
CONTINUABLE_MEMBERS: Final[frozenset[str]] = CONTENT_HASH_EXCLUDED | {"title", "description"}
#: §5.4: a specification's target paths whose value may be continued — all of `_PATH_KINDS`; a
#: target `parameters.<key>` is continuable when its family is in `CONTINUABLE_PARAMETERS`.
CONTINUABLE_SPECIFICATION_PATHS: Final[frozenset[str]] = frozenset(
    {"state.n", "state.T", "state.P", "outlet.T", "outlet.P", "duty.Q"}
)
#: §5.4 (R0): the unit parameter families whose value may be continued — operating values only;
#: a key's family is its text before the first `.` (`stage_pressure.3`). A parameter registered
#: later is not continuable until a register entry adds it here.
CONTINUABLE_PARAMETERS: Final[frozenset[str]] = frozenset(
    {
        "pressure_drop",
        "split_fraction",
        "efficiency",
        "outlet_vapor_fraction",
        "conversion",
        "split",
        "coolant_flow",
        "T_coolant",
        "stage_pressure",
        "stage_duty",
        "condenser_reflux_ratio",
        "condenser_distillate_rate",
        "condenser_duty",
        "condenser_purity",
        "condenser_recovery",
        "condenser_temperature",
        "reboiler_boilup_ratio",
        "reboiler_bottoms_rate",
        "reboiler_duty",
        "reboiler_purity",
        "reboiler_recovery",
        "reboiler_temperature",
    }
)
#: §5.4: the fields of a specification or parameter whose change is a continuable one.
CONTINUABLE_FIELDS: Final[frozenset[str]] = frozenset({"value", "unit", "meaning"})
#: §5.9: the reasons only A2 gives; a rerun passes them as recorded (it binds nothing).
_A2_HEADS: Final = ("source_identity(", "source_binding(")


def continues_revisions(policy: SolvePolicy) -> bool:
    """Whether `policy`'s edge 3 continues revisions: the source is looked up, and the member
    written, iff it does (on `revision_eo`; §5.3, §5.8)."""
    return policy.globalization.eo_recovery == REVISION_RECOVERY


def _number(value: float) -> str:
    """A document constant as its canonical float string (ADR 0002 D3.3; `-0.0` is `0`)."""
    return canonical_json(float(value)).decode()


@dataclass(frozen=True)
class ContinuationSource:
    """What the application found and assembled, and the member's provenance (§5.8).

    `found` is what the orchestrator is given. The other fields are what the member records:
    the ancestor's ids, its stored revision (`as_document()`), the solution-state document as
    read, the certificate's identity, root digest and final signature, and the ancestor
    declaration's pinned inputs (A2's binding; `None` when A2 did not run)."""

    found: RevisionContinuationCandidate | RevisionContinuationRefusal
    source_job_id: str | None = None
    source_revision_id: str | None = None
    source_document: Mapping[str, Any] | None = None
    candidate: Any = None
    source_identity: Mapping[str, str] | None = None
    source_signature: tuple[tuple[str, str], ...] | None = None
    source_parameters: Mapping[str, float] | None = field(default=None)

    def member(self, record: RevisionContinuationRecord | None) -> dict[str, Any]:
        """`solve-path.json`'s `revision_continuation` member. `record` is the executor's
        (`PlanResult.revision_continuation`): `None` when edge 3 never consulted the source,
        which is `not_reached` for an assembled candidate and the refusal itself otherwise."""
        if record is not None:
            status, reason = record.status, record.reason
        elif isinstance(self.found, RevisionContinuationRefusal):
            status, reason = self.found.status, self.found.reason
        else:
            status, reason = "not_reached", None
        continued = None
        if record is not None and record.status == "taken":
            continued = {
                "parameter_ids": list(record.parameter_ids),
                "start_values": [_number(value) for value in record.start_values],
            }
        return {
            "record": RECORD,
            "selection": SELECTION,
            "status": status,
            "reason": reason,
            "continued": continued,
            "source_job_id": self.source_job_id,
            "source_revision_id": self.source_revision_id,
            "source_identity": (
                dict(self.source_identity) if self.source_identity is not None else None
            ),
            "source_signature": (
                [[unit, regime] for unit, regime in self.source_signature]
                if self.source_signature is not None
                else None
            ),
            "source_document": (
                copy.deepcopy(dict(self.source_document))
                if self.source_document is not None
                else None
            ),
            "source_parameters": (
                {pid: _number(value) for pid, value in sorted(self.source_parameters.items())}
                if self.source_parameters is not None
                else None
            ),
            "candidate": copy.deepcopy(self.candidate),
        }


# -- A3: the continuable differences (§5.4) -------------------------------------------------------


def not_continuable(
    source_document: Mapping[str, Any], target_document: Mapping[str, Any]
) -> str | None:
    """A3: the first difference §5.4 does not allow, as `not_continuable(<member>[:<id>[:<path>]])`,
    or `None` when every difference is a continuable one.

    Top-level members first, in code-point order (a changed member outside
    `CONTINUABLE_MEMBERS` and `element_diff`'s three); then `element_diff`'s elements in its order
    — member, id — and within an element its paths in code-point order. `connections` are never
    continuable; an added or removed item never is; an unpairable member is named alone.

    The two orders are `_member_difference` and `_element_difference`."""
    found = _member_difference(source_document, target_document)
    if found is not None:
        return found
    return _element_difference(source_document, target_document)


def _member_difference(
    source_document: Mapping[str, Any], target_document: Mapping[str, Any]
) -> str | None:
    """The first top-level member, in code-point order, that is outside `CONTINUABLE_MEMBERS` and
    `element_diff`'s three and is added, removed or changed, as `not_continuable(<member>)`; `None`
    when there is none."""
    for key in sorted(set(source_document) | set(target_document)):
        if key in CONTINUABLE_MEMBERS or key in ELEMENT_MEMBERS:
            continue
        if key not in source_document or key not in target_document:
            return f"not_continuable({key})"
        if source_document[key] != target_document[key]:
            return f"not_continuable({key})"
    return None


def _element_difference(
    source_document: Mapping[str, Any], target_document: Mapping[str, Any]
) -> str | None:
    """The first of `element_diff`'s elements, in its order, that §5.4 does not allow: an
    unpairable member as `not_continuable(<member>)`, an added or removed item as
    `not_continuable(<member>:<id>)`, a changed item's first offending path (`_offending_path`)
    as `not_continuable(<member>:<id>:<path>)`; `None` when there is none."""
    for element in element_diff(source_document, target_document):
        member, item_id = element.member, element.id
        if item_id is None:
            return f"not_continuable({member})"
        if element.change != "changed":
            return f"not_continuable({member}:{item_id})"
        (item,) = [entry for entry in target_document[member] if entry["id"] == item_id]
        for path in element.paths:
            if _offending_path(member, item, path):
                return f"not_continuable({member}:{item_id}:{'.'.join(path)})"
    return None


def _offending_path(member: str, item: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    """Whether one changed path of a paired `member` item is outside §5.4's allowlist."""
    if member == "specifications":
        target = item.get("target")
        target_path = target.get("path") if isinstance(target, Mapping) else None
        # A specification may pin an instance parameter (`parameters.<key>`, S11 §10.5); it is
        # judged by the instance rule's family test (D-11, review N1).
        return not (
            len(path) == 1
            and path[0] in CONTINUABLE_FIELDS
            and (
                target_path in CONTINUABLE_SPECIFICATION_PATHS
                or (
                    isinstance(target_path, str)
                    and target_path.startswith("parameters.")
                    and target_path.removeprefix("parameters.").split(".", 1)[0]
                    in CONTINUABLE_PARAMETERS
                )
            )
        )
    if member == "instances":
        # A parameter key names its family before the first `.`: `stage_pressure.3`,
        # `feed_stage.S-IN1`, `damkohler.B`, as the binder reads a key's kind
        # (`models/revision_flowsheet.py`, `_PARAMETER_KINDS.get(name.split(".")[0])`).
        return not (
            len(path) >= 3
            and path[0] == "parameters"
            and path[1].split(".", 1)[0] in CONTINUABLE_PARAMETERS
            and path[-1] in CONTINUABLE_FIELDS
        )
    return True


# -- A1, A2 and the candidate ---------------------------------------------------------------------


def _certificate_fields(
    certificate: Any,
) -> tuple[dict[str, str], tuple[tuple[str, str], ...]] | None:
    """The certificate's identity (`model_version`, `constants_sha256`, the root's
    `full_state_sha256`) and its final `branch_provenance` signature; `None` when it does not
    carry them (A1's `integrity(certificate)`)."""
    if not isinstance(certificate, Mapping):
        return None
    fingerprint = certificate.get("root_fingerprint")
    provenance = certificate.get("branch_provenance")
    if not isinstance(fingerprint, Mapping) or not isinstance(provenance, list) or not provenance:
        return None
    found = {
        "model_version": certificate.get("model_version"),
        "constants_sha256": certificate.get("constants_sha256"),
        "full_state_sha256": fingerprint.get("full_state_sha256"),
    }
    signature = provenance[-1].get("signature") if isinstance(provenance[-1], Mapping) else None
    identity = {key: value for key, value in found.items() if isinstance(value, str)}
    if len(identity) != len(found) or not isinstance(signature, list):
        return None
    pairs: list[tuple[str, str]] = []
    for entry in signature:
        if not (
            isinstance(entry, list | tuple)
            and len(entry) == 2
            and all(isinstance(part, str) for part in entry)
        ):
            return None
        pairs.append((entry[0], entry[1]))
    return identity, tuple(pairs)


def _integrity(candidate: Any, identity: Mapping[str, str] | None) -> str | None:
    """A1 on what a run read or a rerun recorded: the reason, or `None` when it holds."""
    if identity is None:
        return "integrity(certificate)"
    if not intact(candidate) or candidate["state_sha256"] != identity["full_state_sha256"]:
        return "integrity(state_sha256)"
    return None


def _candidate(
    source: ContinuationSource,
    identity: Mapping[str, str],
    signature: tuple[tuple[str, str], ...],
    parameters: Mapping[str, float],
) -> RevisionContinuationCandidate:
    state = source.candidate
    return RevisionContinuationCandidate(
        job_id=source.source_job_id,
        revision_id=source.source_revision_id,
        model_version=identity["model_version"],
        constants_sha256=identity["constants_sha256"],
        full_state_sha256=identity["full_state_sha256"],
        signature=signature,
        state={name: float(state["variables"][name]) for name in state["variable_ids"]},
        parameters=dict(parameters),
    )


def assemble(
    source_document: Mapping[str, Any],
    state_document: Any,
    certificate: Any,
    target_document: Mapping[str, Any],
    *,
    source_job_id: str | None = None,
    source_revision_id: str | None = None,
    surrogates: SurrogateResolver | None = None,
) -> ContinuationSource:
    """§5.3's assembly at run time: A1, A2, A3 in that order, the first failure deciding. The
    source is bound as the target was (`surrogates`, the binder's one configuration input)."""
    provenance = ContinuationSource(
        found=RevisionContinuationRefusal("absent", "no_verified_ancestor"),
        source_job_id=source_job_id,
        source_revision_id=source_revision_id,
        source_document=source_document,
        candidate=state_document,
    )
    fields = _certificate_fields(certificate)
    identity, signature = fields if fields is not None else (None, None)
    provenance = _with(provenance, source_identity=identity, source_signature=signature)
    reason = _integrity(state_document, identity)
    if reason is not None:
        return _with(provenance, found=RevisionContinuationRefusal("rejected", reason))
    assert identity is not None and signature is not None
    binding = bind_revision_flowsheet(copy.deepcopy(dict(source_document)), surrogates=surrogates)
    if not isinstance(binding, RevisionBinding):
        reason = f"source_binding({binding.detail})"
        return _with(provenance, found=RevisionContinuationRefusal("rejected", reason))
    model_version, constants = declaration_identity(binding.spec)
    if model_version != identity["model_version"]:
        reason = "source_identity(model_version)"
    elif constants != identity["constants_sha256"]:
        reason = "source_identity(constants_sha256)"
    if reason is not None:
        return _with(provenance, found=RevisionContinuationRefusal("rejected", reason))
    parameters = dict(binding.spec.parameters)
    provenance = _with(provenance, source_parameters=parameters)
    reason = not_continuable(source_document, target_document)
    if reason is not None:
        return _with(provenance, found=RevisionContinuationRefusal("rejected", reason))
    return _with(provenance, found=_candidate(provenance, identity, signature, parameters))


def _with(source: ContinuationSource, **changes: Any) -> ContinuationSource:
    return replace(source, **changes)


def _read_json(path: Path) -> Any:
    """A stored artifact, or `None` when it is missing or does not parse (A1 then refuses)."""
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None


def find_source(
    store: ProjectStore,
    root: Path,
    job_id: str,
    revision_id: str,
    target_document: Mapping[str, Any],
    *,
    surrogates: SurrogateResolver | None = None,
) -> ContinuationSource:
    """§5.3's selection, then the assembly, for `job_id` (a solve of `revision_id`), as the store
    is when the job starts. Any principal's job counts, as for ADR 0024's lookup."""
    with store.reading() as connection:
        found = None
        for ancestor in store.lineage(connection, revision_id)[1:]:
            found = store.latest_verified_solution(connection, (ancestor,), excluding=job_id)
            if found is not None:
                break
        if found is None:
            return ContinuationSource(RevisionContinuationRefusal("absent", "no_verified_ancestor"))
        source_job_id, source_revision_id, relpath = found
        certificate_path = store.job_artifact_relpath(
            connection, source_job_id, "solution_certificate"
        )
        revision = store.get_revision(connection, source_revision_id)
    assert revision is not None, source_revision_id
    return assemble(
        revision.as_document(),
        _read_json(root / relpath),
        _read_json(root / certificate_path) if certificate_path is not None else None,
        target_document,
        source_job_id=source_job_id,
        source_revision_id=source_revision_id,
        surrogates=surrogates,
    )


# -- rerun (§5.9) ---------------------------------------------------------------------------------


def recorded_source(
    member: Mapping[str, Any], target_document: Mapping[str, Any]
) -> ContinuationSource:
    """A rerun's source, from the bundle's own member and its `revision.json`: no lookup, no
    binding. A recorded `absent` or A2 refusal is that refusal; otherwise A1 and A3 run again on
    the recorded documents and the candidate is rebuilt from `source_identity`,
    `source_signature`, `source_parameters` and `candidate`."""
    identity = member.get("source_identity")
    signature = member.get("source_signature")
    parameters = member.get("source_parameters")
    source = ContinuationSource(
        found=RevisionContinuationRefusal("absent", "no_verified_ancestor"),
        source_job_id=member.get("source_job_id"),
        source_revision_id=member.get("source_revision_id"),
        source_document=member.get("source_document"),
        candidate=member.get("candidate"),
        source_identity=(
            {key: str(identity[key]) for key in identity} if isinstance(identity, Mapping) else None
        ),
        source_signature=(
            tuple((str(unit), str(regime)) for unit, regime in signature)
            if isinstance(signature, list)
            else None
        ),
        source_parameters=(
            {str(pid): float(text) for pid, text in parameters.items()}
            if isinstance(parameters, Mapping)
            else None
        ),
    )
    status, reason = member.get("status"), str(member.get("reason"))
    if status == "absent":
        return _with(source, found=RevisionContinuationRefusal("absent", reason))
    if status == "rejected" and reason.startswith(_A2_HEADS):
        return _with(source, found=RevisionContinuationRefusal("rejected", reason))
    reason_found = _integrity(source.candidate, source.source_identity)
    if reason_found is None:
        if not isinstance(source.source_document, Mapping):
            raise ValueError("a recorded revision continuation with no source document")
        reason_found = not_continuable(source.source_document, target_document)
    if reason_found is not None:
        return _with(source, found=RevisionContinuationRefusal("rejected", reason_found))
    if (
        source.source_identity is None
        or source.source_signature is None
        or source.source_parameters is None
    ):
        raise ValueError("a recorded revision continuation that cannot be rebuilt")
    return _with(
        source,
        found=_candidate(
            source, source.source_identity, source.source_signature, source.source_parameters
        ),
    )
