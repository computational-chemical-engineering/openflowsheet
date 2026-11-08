"""RRC WO-4 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §5.3, §5.4,
§5.8, §5.9, §8.2): revision continuation's application half.

- **A3** (§5.4): the registered allowlist of continuable differences, default deny, on the
  registered documents (NET-02, S11's M1-recycle, T08's kinetic CSTR).
- **In the store** (WO-4's row), through `LocalApplication` under the inline executor: NET-02
  (split 0.95, failing first under `T06-revision-v2`) continued from its stored split-0.5
  ancestor; G6 (a), (c), (d), (e), (k) — one `initializer_rejected` event with the R0 message,
  then the step's records are the same case's under `T06-revision-v2` except for `policy_id`;
  (d) and (k) force edge 3 after a converged item 0 (S01 A17's precedent, as WO-3's F1/F2).
- **G7**: `replay --rerun` from the bundle alone (no store lookup) is `MATCH`, and the rerun's
  member is the recorded one.
- **The member and the R0 branch** (§5.8): a bundle without the member projects exactly as
  before, the branch carries no float, and no other policy writes the member.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from s11_column_support import RECYCLE_CASE, column_registered, committed_case
from t06_support import case_document
from t07_jobs_support import commit
from t08_cstr_support import liquid_variant_revision

from openflowsheet.application import revision_continuation as application_module
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_continuation import (
    CONTINUABLE_PARAMETERS,
    CONTINUABLE_SPECIFICATION_PATHS,
    not_continuable,
)
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.types import JobRequest, ReplayPolicy, SolveBody
from openflowsheet.models import revision_flowsheet
from openflowsheet.models.revision_flowsheet import TARGET_PATH_KINDS
from openflowsheet.orchestrator import executor
from openflowsheet.run import solution_state
from openflowsheet.run.identity import floats_in, r0_projection

NET02 = "SYN-001-T06-NET02"


def _instance(document: dict[str, Any], unit: str) -> dict[str, Any]:
    (item,) = [item for item in document["instances"] if item["id"] == unit]
    found: dict[str, Any] = item
    return found


def _edited(document: dict[str, Any], edit: Any) -> dict[str, Any]:
    edited = copy.deepcopy(document)
    edit(edited)
    return edited


# -- A3: continuable differences (§5.4) -----------------------------------------------------------


def test_the_specification_paths_are_all_of_the_binders_target_paths() -> None:
    assert set(TARGET_PATH_KINDS) == CONTINUABLE_SPECIFICATION_PATHS


#: D-11 (accepted by the review): the binder's parameter families §5.4 denies — discrete
#: structure (`stage_count`, `feed_stage`) and model constants (`nu`, `damkohler`, `T_ref`,
#: `T_scale`, `coolant_cp`).
DENIED_PARAMETERS = frozenset(
    {"stage_count", "feed_stage", "nu", "damkohler", "T_ref", "T_scale", "coolant_cp"}
)


def test_the_parameter_families_are_partitioned_into_continuable_and_denied() -> None:
    """Review S2, §5.4's register rule: every family the binder types is either continuable or
    denied, never both, so a family added to the binder fails here until a register decision
    places it (default deny keeps the omission safe meanwhile)."""
    families = set(revision_flowsheet._PARAMETER_KINDS)
    assert CONTINUABLE_PARAMETERS.isdisjoint(DENIED_PARAMETERS)
    assert CONTINUABLE_PARAMETERS | DENIED_PARAMETERS == families
    assert (len(CONTINUABLE_PARAMETERS), len(DENIED_PARAMETERS), len(families)) == (22, 7, 29)


def _split(value: float) -> Any:
    def edit(document: dict[str, Any]) -> None:
        _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["value"] = value

    return edit


def _spec_value(document: dict[str, Any]) -> None:
    document["specifications"][0]["value"] = 1.25


def _spec_tolerance(document: dict[str, Any]) -> None:
    document["specifications"][0]["tolerance"]["absolute"] = 1e-10


def _connection_notes(document: dict[str, Any]) -> None:
    document["connections"][0]["notes"] = "edited"


def _retitled(document: dict[str, Any]) -> None:
    document["title"] = "another title"
    document["description"] = "another description"


def _component_set(document: dict[str, Any]) -> None:
    document["component_set"] = {**document["component_set"], "extra": True}


def _added_instance(document: dict[str, Any]) -> None:
    document["instances"].append({**_instance(document, "U-SINK-P"), "id": "U-SINK-Q"})


def _model(document: dict[str, Any]) -> None:
    _instance(document, "U-HEAT")["model"]["version"] = "0.0.1-declared"


def _meaning(document: dict[str, Any]) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["meaning"] = "edited"


def _bounds(document: dict[str, Any]) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["bounds"]["upper"] = 0.99


#: (edit of NET-02, A3's verdict): `None` is continuable.
A3_NET02 = {
    "split_fraction": (_split(0.5), None),
    "split_and_title": (lambda d: [edit(d) for edit in (_split(0.5), _retitled)], None),
    "specification_value": (_spec_value, None),
    "parameter_meaning": (_meaning, None),
    "specification_tolerance": (
        _spec_tolerance,
        "not_continuable(specifications:SPEC-S1-n-A:tolerance.absolute)",
    ),
    "parameter_bounds": (
        _bounds,
        "not_continuable(instances:U-SPLIT:parameters.split_fraction.bounds.upper)",
    ),
    "connection_notes": (_connection_notes, "not_continuable(connections:S1:notes)"),
    "component_set": (_component_set, "not_continuable(component_set)"),
    "added_instance": (_added_instance, "not_continuable(instances:U-SINK-Q)"),
    "model": (_model, "not_continuable(instances:U-HEAT:model.version)"),
}


@pytest.mark.parametrize("case", list(A3_NET02))
def test_a3_on_net02(case: str) -> None:
    edit, expected = A3_NET02[case]
    source = case_document(NET02)
    assert not_continuable(source, _edited(source, edit)) == expected


def test_a3_the_first_offence_is_reported_in_element_diff_order() -> None:
    """Top-level members first, then `instances`, `connections`, `specifications` (§5.3 A3)."""
    source = case_document(NET02)

    def everything(document: dict[str, Any]) -> None:
        _spec_tolerance(document)
        _connection_notes(document)
        _model(document)

    assert not_continuable(source, _edited(source, everything)) == (
        "not_continuable(instances:U-HEAT:model.version)"
    )
    both = _edited(source, lambda d: [edit(d) for edit in (everything, _component_set)])
    assert not_continuable(source, both) == "not_continuable(component_set)"


def test_a3_a_column_stage_count_is_not_continuable_and_its_end_specifications_are() -> None:
    """G6 (d)'s reason; F1's change (reflux and boil-up) and a stage pressure are continuable."""
    source = committed_case(RECYCLE_CASE)
    column = _instance(source, "S02")["parameters"]

    def stages(document: dict[str, Any]) -> None:
        _instance(document, "S02")["parameters"]["stage_count"]["value"] = 8

    def ends(document: dict[str, Any]) -> None:
        parameters = _instance(document, "S02")["parameters"]
        parameters["condenser_reflux_ratio"]["value"] = 4.0
        parameters["reboiler_boilup_ratio"]["value"] = 3.0
        parameters["stage_pressure.3"]["value"] = column["stage_pressure.3"]["value"] * 1.01

    def feed_stage(document: dict[str, Any]) -> None:
        entry = _instance(document, "S02")["parameters"]["feed_stage.S-IN1"]
        entry["value"] = entry["value"] - 1

    assert not_continuable(source, _edited(source, stages)) == (
        "not_continuable(instances:S02:parameters.stage_count.value)"
    )
    assert not_continuable(source, _edited(source, ends)) is None
    assert not_continuable(source, _edited(source, feed_stage)) == (
        "not_continuable(instances:S02:parameters.feed_stage.S-IN1.value)"
    )


def _pinned_by_specification(key: str, value: float) -> Any:
    """The column's `key` moved from its instance parameters to a `role: fixed` specification
    whose target is `parameters.<key>` (S11 §10.5), with `value`."""

    def edit(document: dict[str, Any]) -> None:
        del _instance(document, "S02")["parameters"][key]
        document["specifications"].append(
            {
                "id": "SPEC-S02-pinned",
                "kind": "dimensionless",
                "provenance": "RRC N1 test",
                "role": "fixed",
                "target": {
                    "object_id": "S02",
                    "object_type": "instance",
                    "path": f"parameters.{key}",
                },
                "tolerance": {"absolute": 1e-09, "relative": 1e-08, "scale": 1.0},
                "unit": "1",
                "value": value,
            }
        )

    return edit


def test_a3_a_specification_pinning_a_parameter_is_judged_by_its_family() -> None:
    """Review N1 (§5.4 extended): a specification whose target is `parameters.<key>` is
    continuable iff the key's family is — the reflux ratio 2.0 → 4.0 is, a feed stage is not."""
    base = committed_case(RECYCLE_CASE)
    source = _edited(base, _pinned_by_specification("condenser_reflux_ratio", 2.0))
    target = _edited(base, _pinned_by_specification("condenser_reflux_ratio", 4.0))
    assert not_continuable(source, target) is None
    stage = _instance(base, "S02")["parameters"]["feed_stage.S-IN1"]["value"]
    source = _edited(base, _pinned_by_specification("feed_stage.S-IN1", stage))
    target = _edited(base, _pinned_by_specification("feed_stage.S-IN1", stage - 1))
    assert not_continuable(source, target) == (
        "not_continuable(specifications:SPEC-S02-pinned:value)"
    )


def test_a3_a_kinetic_constant_is_not_continuable_and_the_coolant_is() -> None:
    """G6 (k)'s reason on T08's kinetic CSTR; `coolant_flow` and `T_coolant` are continuable,
    `coolant_cp`, `nu`, `T_ref` and `T_scale` are not."""
    source = liquid_variant_revision()

    def setting(key: str, factor: float) -> Any:
        def edit(document: dict[str, Any]) -> None:
            entry = _instance(document, "U-CSTR")["parameters"][key]
            entry["value"] = entry["value"] * factor

        return edit

    assert not_continuable(source, _edited(source, setting("damkohler.B", 2.0))) == (
        "not_continuable(instances:U-CSTR:parameters.damkohler.B.value)"
    )
    for key in ("coolant_flow", "T_coolant"):
        assert not_continuable(source, _edited(source, setting(key, 1.01))) is None, key
    for key in ("coolant_cp", "nu.A", "T_ref", "T_scale"):
        assert not_continuable(source, _edited(source, setting(key, 1.01))) == (
            f"not_continuable(instances:U-CSTR:parameters.{key}.value)"
        ), key


# -- in the store ---------------------------------------------------------------------------------

RRC = "RRC-revision-v1"
DEFAULT = "default"
SPLIT = "U-SPLIT.split_fraction"


def _net02(split: float | None = None) -> dict[str, Any]:
    """NET-02 as a committable document (its stored ids are the store's), `split_fraction` set."""
    document = case_document(NET02)
    for key in ("revision_id", "parent_revision"):
        document.pop(key, None)
    if split is not None:
        _split(split)(document)
    return document


def _committable(document: dict[str, Any]) -> dict[str, Any]:
    stripped = copy.deepcopy(document)
    for key in ("revision_id", "parent_revision"):
        stripped.pop(key, None)
    return stripped


@dataclass(frozen=True)
class Solved:
    """One solve job's result and its bundle's artifacts, read back from disk."""

    job_id: str
    revision_id: str
    outcome: str | None
    verdict: str | None
    directory: Path
    artifacts: dict[str, Any]

    @property
    def member(self) -> dict[str, Any] | None:
        found: dict[str, Any] | None = self.artifacts["solve-path.json"].get(
            "revision_continuation"
        )
        return found

    @property
    def events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = self.artifacts["solve-events.json"]
        return events

    def messages(self, kind: str) -> list[str]:
        return [event["message"] for event in self.events if event["kind"] == kind]


def _read(directory: Path) -> dict[str, Any]:
    return {
        path.name: json.loads(path.read_bytes())
        for path in sorted((directory / "artifacts").iterdir())
    }


def _solve(app: LocalApplication, revision_id: str, policy_id: str) -> Solved:
    count = len(app.list_jobs(limit=200).items)
    key = f"rrc-{revision_id}-{policy_id}-{count}"
    request = JobRequest("solve", key, SolveBody(revision_id, policy_id=policy_id))
    job = app.submit_job(request).job
    assert job.status == "completed", (job.status, job.error)
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    directory = app.files_root / "jobs" / job.job_id / "bundle"
    return Solved(
        job.job_id,
        revision_id,
        result.outcome,
        result.verification_status,
        directory,
        _read(directory),
    )


@contextmanager
def _project(root: Path, name: str) -> Iterator[LocalApplication]:
    with LocalApplication.create(root / name, project_id=f"rrc-{name}") as app:
        yield app


@dataclass(frozen=True)
class Pair:
    ancestor: Solved
    continued: Solved
    restarted: Solved
    reached_not: Solved


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Pair]:
    """§8.1's N1 in a store: NET-02 at split 0.5 solved under `default`, then its child at 0.95
    (NET-02 itself) under `RRC-revision-v1` and under `default`; then a grandchild back at 0.5
    (retitled), which converges first time under `RRC-revision-v1` (edge 3 never consulted)."""
    with _project(tmp_path_factory.mktemp("rrc-pair"), "pair") as app:
        ancestor = _solve(app, commit(app, _net02(0.5)), DEFAULT)
        target = commit(app, _net02())
        continued = _solve(app, target, RRC)
        restarted = _solve(app, target, DEFAULT)
        back = _net02(0.5)
        back["title"] = "NET-02 back at split 0.5"
        reached_not = _solve(app, commit(app, back), RRC)
        yield Pair(ancestor, continued, restarted, reached_not)


def test_net02_is_continued_from_its_stored_verified_ancestor(pair: Pair) -> None:
    """G4's shape in the store (G4 itself is WO-5's): the member is `taken`, names the ancestor's
    job and revision, and records what the ancestor's bundle holds."""
    ancestor, continued = pair.ancestor, pair.continued
    assert (ancestor.outcome, ancestor.verdict) == ("CONVERGED", "VERIFIED")
    assert (continued.outcome, continued.verdict) == ("CONVERGED", "VERIFIED")
    member = continued.member
    assert member is not None
    certificate = ancestor.artifacts["solution-certificate.json"]
    assert member["record"] == "RRC-revision-continuation-v1"
    assert member["selection"] == "store-nearest-verified-ancestor-v1"
    assert (member["status"], member["reason"]) == ("taken", None)
    assert member["continued"] == {"parameter_ids": [SPLIT], "start_values": ["0.5"]}
    assert (member["source_job_id"], member["source_revision_id"]) == (
        ancestor.job_id,
        ancestor.revision_id,
    )
    assert member["source_identity"] == {
        "model_version": certificate["model_version"],
        "constants_sha256": certificate["constants_sha256"],
        "full_state_sha256": certificate["root_fingerprint"]["full_state_sha256"],
    }
    assert member["source_signature"] == certificate["branch_provenance"][-1]["signature"]
    assert member["candidate"] == ancestor.artifacts[solution_state.NAME]
    # The stored ancestor revision, as its own bundle's `revision.json` records it.
    assert member["source_document"] == ancestor.artifacts["revision.json"]
    assert member["source_document"]["revision_id"] == ancestor.revision_id
    assert member["source_parameters"][SPLIT] == "0.5"
    assert continued.messages("initializer_rejected") == []
    # The recovery item opens at the ancestor's root (G2 (f)): NET-02's opening pins no column,
    # so its free columns are all of `variable_ids` and the opening digest is the root's.
    recovery = continued.artifacts["solution-certificate.json"]["branch_provenance"][1]
    assert recovery["initializer_source"] == "revision_continuation_source"
    assert recovery["opening_state_sha256"] == member["source_identity"]["full_state_sha256"]
    assert recovery["continuation"]["type"] == "revision_continuation"
    assert recovery["continuation"]["parameter_ids"] == [SPLIT]


def test_the_member_is_written_whether_or_not_edge_3_fired(pair: Pair) -> None:
    """§5.8: a source assembled and never consulted is `not_reached`; a run whose lineage has no
    verified ancestor records the lookup's `absent` even when edge 3 never fired."""
    member = pair.reached_not.member
    assert pair.reached_not.outcome == "CONVERGED"
    assert member is not None
    assert (member["status"], member["reason"], member["continued"]) == ("not_reached", None, None)
    # The nearest verified ancestor is the 0.95 revision; its latest verified job is `default`'s.
    assert member["source_job_id"] == pair.restarted.job_id
    assert pair.reached_not.messages("initializer_rejected") == []


def test_no_other_policy_writes_the_member_and_the_r0_branch_is_inert(pair: Pair) -> None:
    for solved in (pair.ancestor, pair.restarted):
        assert "revision_continuation" not in solved.artifacts["solve-path.json"]
        assert "revision_continuation" not in r0_projection(solved.artifacts)
    artifacts = copy.deepcopy(pair.continued.artifacts)
    projected = r0_projection(artifacts)
    assert floats_in(projected) == []
    branch = projected["revision_continuation"]
    member = pair.continued.member
    assert branch["status"] == "taken" and member is not None
    assert branch["source_content_hash"] == member["source_document"]["content_hash"]
    assert "full_state_sha256" not in branch["source_identity"]
    del artifacts["solve-path.json"]["revision_continuation"]
    stripped = r0_projection(artifacts)
    assert {key: value for key, value in projected.items() if key != "revision_continuation"} == (
        stripped
    )


# -- G6: typed refusals in the store --------------------------------------------------------------


def _normalized(solved: Solved, policy_id: str) -> list[dict[str, Any]]:
    """The events without `sequence`, the plan id's policy spelled as `T06-revision-v2`'s."""
    events = [{k: v for k, v in event.items() if k != "sequence"} for event in solved.events]
    for event in events:
        if event["kind"] == "plan_built":
            event["message"] = event["message"].replace(f"-{policy_id}-", "-T06-revision-v2-")
    return events


def _assert_refused_then_restarted(
    rrc: Solved, reference: Solved, status: str, reason: str, *, attempts: bool = True
) -> None:
    """G6's criterion: one `initializer_rejected` event with the R0 message; after it, the step's
    records are the same case's under `T06-revision-v2` except for `policy_id`. `attempts`: the
    restart opens attempts after the event (it does on NET-02 and the column; on the one-unit
    CSTR region its preconditions refuse it, under either policy)."""
    member = rrc.member
    assert member is not None
    assert (member["status"], member["reason"], member["continued"]) == (status, reason, None)
    assert rrc.messages("initializer_rejected") == [f"revision_continuation_{status}: {reason}"]
    events = _normalized(rrc, "RRC-revision-v1")
    kinds = [event["kind"] for event in events]
    at = kinds.index("initializer_rejected")
    assert ("attempt_opened" in kinds[at + 1 :]) is attempts
    del events[at]
    assert events == _normalized(reference, "T06-revision-v2")
    assert (rrc.outcome, rrc.verdict) == (reference.outcome, reference.verdict)
    assert rrc.artifacts.get(solution_state.NAME) == reference.artifacts.get(solution_state.NAME)
    ours = rrc.artifacts.get("solution-certificate.json")
    theirs = reference.artifacts.get("solution-certificate.json")
    assert (ours is None) == (theirs is None)
    if ours is not None and theirs is not None:
        assert ours["branch_provenance"] == theirs["branch_provenance"]


@dataclass(frozen=True)
class Refused:
    rrc: Solved
    reference: Solved


@pytest.fixture(scope="module")
def absent(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Refused]:
    """G6 (a): NET-02 committed with no ancestor solved."""
    with _project(tmp_path_factory.mktemp("rrc-a"), "a") as app:
        target = commit(app, _net02())
        yield Refused(_solve(app, target, RRC), _solve(app, target, DEFAULT))


@pytest.fixture(scope="module")
def tampered(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Refused]:
    """G6 (c): the ancestor's stored `solution-state.json` with one value altered, its digest
    left (ADR 0024 B44's tampering)."""
    with _project(tmp_path_factory.mktemp("rrc-c"), "c") as app:
        ancestor = _solve(app, commit(app, _net02(0.5)), DEFAULT)
        path = ancestor.directory / "artifacts" / solution_state.NAME
        document = json.loads(path.read_bytes())
        name = document["variable_ids"][0]
        document["variables"][name] = document["variables"][name] + 1.0
        path.write_text(json.dumps(document), encoding="utf-8")
        target = commit(app, _net02())
        yield Refused(_solve(app, target, RRC), _solve(app, target, DEFAULT))


def _noted(document: dict[str, Any]) -> dict[str, Any]:
    _connection_notes(document)
    return document


@pytest.fixture(scope="module")
def rewired(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Refused]:
    """G6 (e): NET-02's child that also edits a connection (its notes)."""
    with _project(tmp_path_factory.mktemp("rrc-e"), "e") as app:
        _solve(app, commit(app, _net02(0.5)), DEFAULT)
        target = commit(app, _noted(_net02()))
        yield Refused(_solve(app, target, RRC), _solve(app, target, DEFAULT))


def test_g6_a_no_verified_ancestor(absent: Refused) -> None:
    _assert_refused_then_restarted(absent.rrc, absent.reference, "absent", "no_verified_ancestor")
    assert absent.rrc.member is not None and absent.rrc.member["source_job_id"] is None


def test_g6_c_a_tampered_ancestor_state_is_rejected_for_integrity(tampered: Refused) -> None:
    _assert_refused_then_restarted(
        tampered.rrc, tampered.reference, "rejected", "integrity(state_sha256)"
    )


def test_g6_e_a_connection_edit_is_not_continuable(rewired: Refused) -> None:
    _assert_refused_then_restarted(
        rewired.rrc, rewired.reference, "rejected", "not_continuable(connections:S1:notes)"
    )


def _forced_pair(
    app: LocalApplication,
    monkeypatch: pytest.MonkeyPatch,
    source: dict[str, Any],
    target: dict[str, Any],
) -> Refused:
    """The ancestor solved under `default`, then edge 3 forced after a converged item 0 (S01
    A17's precedent; WO-3's F1/F2), and the target solved under both policies."""
    found = _solve(app, commit(app, _committable(source)), DEFAULT)
    assert (found.outcome, found.verdict) == ("CONVERGED", "VERIFIED")
    revision = commit(app, _committable(target))
    monkeypatch.setattr(executor, "eo_recovery_due", lambda outcome, budget, *, attempts: True)
    return Refused(_solve(app, revision, RRC), _solve(app, revision, DEFAULT))


def test_g6_d_a_column_stage_count_is_not_continuable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = committed_case(RECYCLE_CASE)
    target = copy.deepcopy(source)
    # One stage more, with its stage pressure, so that the target is READY (it binds).
    parameters = _instance(target, "S02")["parameters"]
    count = int(parameters["stage_count"]["value"])
    parameters["stage_count"]["value"] = float(count + 1)
    parameters[f"stage_pressure.{count + 1}"] = copy.deepcopy(parameters[f"stage_pressure.{count}"])
    with column_registered(monkeypatch), _project(tmp_path, "d") as app:
        refused = _forced_pair(app, monkeypatch, source, target)
    _assert_refused_then_restarted(
        refused.rrc,
        refused.reference,
        "rejected",
        "not_continuable(instances:S02:parameters.stage_count.value)",
    )


def test_g6_k_a_kinetic_constant_is_not_continuable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = liquid_variant_revision()
    target = copy.deepcopy(source)
    damkohler = _instance(target, "U-CSTR")["parameters"]["damkohler.B"]
    damkohler["value"] = damkohler["value"] * 1.25
    with _project(tmp_path, "k") as app:
        refused = _forced_pair(app, monkeypatch, source, target)
    _assert_refused_then_restarted(
        refused.rrc,
        refused.reference,
        "rejected",
        "not_continuable(instances:U-CSTR:parameters.damkohler.B.value)",
        attempts=False,
    )


# -- G7: replay from the bundle alone -------------------------------------------------------------


def test_g7_bundles_rerun_to_match_without_a_lookup(
    pair: Pair,
    absent: Refused,
    tampered: Refused,
    rewired: Refused,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§5.9 (ADR 0024 D5's pattern): `replay --rerun` takes the member, does no lookup and binds
    no ancestor, and the rerun's member equals the recorded one."""
    calls: list[str] = []

    def refuse(name: str) -> Callable[..., Any]:
        def called(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError(f"a rerun called {name}")

        return called

    monkeypatch.setattr(
        ProjectStore, "latest_verified_solution", staticmethod(refuse("latest_verified_solution"))
    )
    monkeypatch.setattr(application_module, "find_source", refuse("find_source"))
    monkeypatch.setattr(application_module, "bind_revision_flowsheet", refuse("bind"))
    with _project(tmp_path, "g7") as app:
        for solved in (pair.continued, absent.rrc, tampered.rrc, rewired.rrc):
            report = app.reproduce(solved.directory, ReplayPolicy(rerun=True))
            assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
            assert report.verdict == "MATCH", (solved.job_id, report.differences, report.reasons)
            assert report.differences == ()
            job_id = app.list_jobs(limit=200).items[-1].job_id
            rerun = _read(app.files_root / "jobs" / job_id / "rerun")
            assert rerun["solve-path.json"]["revision_continuation"] == solved.member
            assert r0_projection(rerun) == r0_projection(solved.artifacts)
    assert calls == []
