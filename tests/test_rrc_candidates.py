"""RRC WO-5b (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §8.1, §8.2):
the registered revision-continuation pairs and the candidate table.

- **G9**: the committed table (`benchmarks/rrc/results-ref-x86-64.json`) holds every candidate of
  `cases.yaml` under all three policies, and §8.1's first-in-order rules applied to it select the
  registered pairs; `cases.yaml` is the file registered (its digest).
- **G4** (NET-02 rescue, Family N's pair) and **G5** (L-COL-9's column rescue, Family C's pair),
  re-run through the registered harness (`benchmarks.rrc.run_candidates.run_case`, the code that
  wrote the table): the control in the trigger set, `RRC-revision-v1` `CONVERGED`, `VERIFIED` and
  `taken` in-process and in the store, and the pair's independent checks (G4: the closed-form twin
  root within T06's allowances and the restart's root to 1e-8 scaled; G5: S11.A29's closure).
  The registered values (regression) are held too.
- **G2** (a)–(f) on the G5 pair (`tests/test_rrc_edge3.py::test_g2_every_level_has_its_identity`
  is G2 on the G4 pair, N1).
- **G7** on the G5 pair: `replay --rerun` from the bundle alone is `MATCH`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from s11_column_support import RECYCLE_CASE, column_case_spec
from t06_support import ALLOWANCE, CORPUS, registered_root
from test_s02_column_wo2 import FLOW_ABS, FLOW_REL

from benchmarks.rrc import run_candidates as harness
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import RRC_REVISION_V1, T06_REVISION_V2
from openflowsheet.application.types import ReplayPolicy
from openflowsheet.canonical import encode_doubles
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.homotopy import level_values, rebind
from openflowsheet.run.identity import r0_projection

RRC = Path(__file__).resolve().parents[1] / "benchmarks" / "rrc"
REFERENCE: dict[str, Any] = yaml.safe_load((RRC / "reference_values.yaml").read_text("utf-8"))
RESULTS: dict[str, Any] = json.loads((RRC / REFERENCE["results"].rsplit("/", 1)[1]).read_text())
PAIRS: dict[str, Any] = REFERENCE["pairs"]
POLICIES = ("control", "T06-revision-v2", "RRC-revision-v1")


@cache
def entry(candidate: str) -> dict[str, Any]:
    """One candidate re-run through the registered harness, every policy and the store leg."""
    found: dict[str, Any] = json.loads(json.dumps(harness.run_case(candidate), default=str))
    return found


# ------------------------------------------------------------------ G9: the table


def test_g9_the_cases_are_the_registered_file() -> None:
    digest = hashlib.sha256((RRC / "cases.yaml").read_bytes()).hexdigest()
    assert digest == REFERENCE["cases_sha256"]


def test_g9_every_candidate_is_reported_under_every_policy() -> None:
    families = harness.CASES["families"]
    ids = [e["id"] for e in families["N"]["sources"]]
    ids += [e["id"] for e in families["C"]["targets"]]
    ids += [e["id"] for e in families["F"]["cases"]]
    assert len(ids) == 3 + 5 + 2
    assert [c["id"] for c in RESULTS["candidates"]] == ids
    for candidate in RESULTS["candidates"]:
        assert candidate["source"]["outcome"] is not None, candidate["id"]
        assert set(candidate["runs"]) == set(POLICIES), candidate["id"]
        for name in POLICIES:
            run = candidate["runs"][name]
            assert run["outcome"] is not None and "iterations" in run, (candidate["id"], name)
        if not candidate["forced_edge"]:
            assert candidate["store"]["target"]["job_status"] == "completed", candidate["id"]


def test_g9_the_selection_rules_pick_the_registered_pairs() -> None:
    by_id = {c["id"]: c for c in RESULTS["candidates"]}
    families = harness.CASES["families"]
    for family, key, gate in (("N", "sources", "G4"), ("C", "targets", "G5")):
        criteria = families[family]["selection_criteria"]
        chosen = next(
            e["id"] for e in families[family][key] if harness._qualifies(by_id[e["id"]], criteria)
        )
        assert chosen == PAIRS[gate]["candidate"] == RESULTS["selected"][family]


def test_the_harness_reads_the_registered_references_as_the_tests_do() -> None:
    """The harness is self-contained (`benchmarks` imports no test module); its copies of the
    T06 allowances, the twin-root reader and S02's flow tolerance are the tests' own."""
    assert dict(harness.ALLOWANCE) == dict(ALLOWANCE)
    assert harness.CORPUS == CORPUS
    assert harness.registered_root(CORPUS[harness.NET02]) == registered_root(CORPUS[harness.NET02])
    assert (harness.FLOW_REL, harness.FLOW_ABS) == (FLOW_REL, FLOW_ABS)
    (feed,) = column_case_spec(RECYCLE_CASE).inlets()
    flows = harness.feed_flows(harness._base(RECYCLE_CASE))
    assert flows == tuple(zip("ABC", (float(n) for n in feed.state.n), strict=True))


# ------------------------------------------------------------------ G4, G5: the pairs


def _held(found: dict[str, Any], registered: Mapping[str, Any]) -> None:
    """The regression values of one registered pair (outcomes, counts, λ-trials, the member)."""
    control, restart = found["runs"]["control"], found["runs"]["T06-revision-v2"]
    assert (control["outcome"], control["iterations"], control["item0"]["in_trigger_set"]) == (
        registered["control"]["outcome"],
        registered["control"]["iterations"],
        registered["control"]["in_trigger_set"],
    )
    assert (restart["outcome"], restart["verification_status"], restart["iterations"]) == (
        registered["T06-revision-v2"]["outcome"],
        registered["T06-revision-v2"]["verification_status"],
        registered["T06-revision-v2"]["iterations"],
    )
    rrc, want = found["runs"]["RRC-revision-v1"], registered["RRC-revision-v1"]
    assert (rrc["outcome"], rrc["verification_status"]) == ("CONVERGED", "VERIFIED")
    assert (rrc["eo_recovery"], rrc["record_status"], rrc["record_reason"]) == (
        "taken",
        "taken",
        None,
    )
    assert rrc["continued"] == want["continued"]
    assert rrc["iterations"] == want["iterations"]
    assert rrc["homotopy"]["lambda_levels"] == [str(level) for level in want["lambda_levels"]]
    assert rrc["homotopy"]["rejected"] == want["rejected_trials"]
    # The store's selection and assembly reach the same root as the in-process candidate.
    store = found["store"]["target"]
    assert (store["outcome"], store["verification_status"]) == ("CONVERGED", "VERIFIED")
    assert (store["member_status"], store["member_reason"]) == (want["member_status"], None)
    assert store["member_continued"] == want["continued"]
    assert store["member_source_revision_id"] == store["source_revision_id"]
    assert store["state_sha256"] == rrc["state_sha256"]
    # G2 (f): the source's signature pins no column, and the recovery item opens at its root.
    assert {unit: regime for unit, regime in found["checks"]["source_signature"]} == registered[
        "source_signature"
    ]
    assert found["checks"]["g2f_opening_equals_source_full_state"] is True


def test_g4_net02_is_rescued_from_its_registered_source() -> None:
    """§8.2 G4: control `BOUND_BLOCKED`; `RRC-revision-v1` `CONVERGED`, `VERIFIED`; the closed-form
    twin root within T06's allowances; the restart's root to 1e-8 scaled."""
    registered = PAIRS["G4"]
    found = entry(registered["candidate"])
    assert found["source_eligible"] is True
    assert found["runs"]["control"]["outcome"] == "BOUND_BLOCKED"
    _held(found, registered)
    checks, independent = found["checks"], registered["independent_checks"]
    ratio, _ = checks["net02_closed_form_worst_ratio"]
    assert ratio <= independent["closed_form"]["criterion"]
    assert checks["scaled_distance_to_t06_root"] <= independent["restart_root"]["criterion"]


def test_g5_a_column_case_failing_first_is_rescued_and_closes() -> None:
    """§8.2 G5 (L-COL-9): the control in the trigger set; `RRC-revision-v1` `CONVERGED`,
    `VERIFIED`, `taken`; S11.A29's per-component closure within the flow tolerance."""
    registered = PAIRS["G5"]
    found = entry(registered["candidate"])
    assert found["source_eligible"] is True
    assert found["runs"]["control"]["item0"]["in_trigger_set"] is True
    _held(found, registered)
    checks, independent = found["checks"], registered["independent_checks"]
    assert checks["a29_closure"]["met"] is True
    assert checks["a29_closure"]["worst_ratio"] <= independent["a29_closure"]["criterion"]
    assert checks["scaled_distance_to_t06_root"] <= independent["restart_root"]["criterion"]


# ------------------------------------------------------------------ G2 on the G5 pair


@cache
def g5_solved() -> tuple[harness.Solved, harness.Solved, Any]:
    _, source_doc, target_doc, _ = harness._find(PAIRS["G5"]["candidate"])
    source = harness.solve(source_doc, T06_REVISION_V2)
    certificate = source.certificate()
    assert certificate is not None and certificate.verification_status == "VERIFIED"
    ancestor = harness.candidate(source, certificate)
    continued = harness.solve(target_doc, RRC_REVISION_V1, revision_continuation=ancestor)
    restarted = harness.solve(target_doc, T06_REVISION_V2)
    return continued, restarted, ancestor


def test_g2_every_level_of_the_column_pair_has_its_identity() -> None:
    """G2 (a)–(f) on the G5 pair's trace and records, as `test_rrc_edge3` holds them on G4's."""
    solved, restarted, source = g5_solved()
    step = solved.step
    assert step is not None
    spec, record = solved.binding.spec, step.revision_continuation
    assert record is not None and record.status == "taken"
    continuation = step.detail.homotopy.continuation
    events = [event.as_document() for event in solved.run.trace.of_kind("homotopy_step")]
    levels = {event["lambda_value"]: event["level_constants_sha256"] for event in events}
    for text in levels:  # (d) dyadic
        lam = Fraction(text)
        assert lam.denominator & (lam.denominator - 1) == 0, text
    # (a) λ = 0 is the ancestor's certified problem.
    opening = rebind(spec, level_values(continuation, spec.parameters, {}, Fraction(0)))
    assert declaration_identity(opening) == (source.model_version, source.constants_sha256)
    assert levels["0"] == source.constants_sha256
    # (b), (e): every λ < 1 level differs from the target only at `D`, formed in exact rationals.
    model_version, constants = declaration_identity(spec)
    for text, recorded in levels.items():
        lam = Fraction(text)
        if lam == 1:
            continue
        values = level_values(continuation, spec.parameters, {}, lam)
        level = rebind(spec, values).parameters
        moved = [
            pid
            for pid in spec.parameter_ids
            if encode_doubles((level[pid],)) != encode_doubles((spec.parameters[pid],))
        ]
        assert set(moved) <= set(record.parameter_ids), (text, moved)
        assert declaration_identity(rebind(spec, values)) == (model_version, recorded)
        for pid, start in zip(record.parameter_ids, record.start_values, strict=True):
            target = Fraction(spec.parameters[pid])
            assert values[pid] == float(target + (1 - lam) * (Fraction(start) - target))
    # (c) λ = 1 is the target: the failed solve's identity, the certificate's, the restart's.
    assert levels["1"] == constants
    failed = step.recovered_from.contexts[0].evaluation_context
    assert (failed.model_version, failed.constants_sha256) == (model_version, constants)
    for certificate in (solved.certificate(), restarted.certificate()):
        assert certificate is not None and certificate.root_fingerprint is not None
        fingerprint = certificate.root_fingerprint
        assert (fingerprint["model_version"], fingerprint["constants_sha256"]) == (
            model_version,
            constants,
        )
    # (f) the recovery item opens at the ancestor's root.
    assert step.detail.branch_provenance[1]["opening_state_sha256"] == source.full_state_sha256


# ------------------------------------------------------------------ G7 on the G5 pair


@pytest.fixture(scope="module")
def g5_store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[LocalApplication, str]]:
    _, source_doc, target_doc, _ = harness._find(PAIRS["G5"]["candidate"])
    root = tmp_path_factory.mktemp("rrc-g5")
    with LocalApplication.create(root / "p", project_id="rrc-g5") as app:
        source = harness._store_solve(
            app, harness._store_commit(app, source_doc), "T06-revision-v2"
        )
        assert (source["outcome"], source["verification_status"]) == ("CONVERGED", "VERIFIED")
        target = harness._store_solve(
            app, harness._store_commit(app, target_doc), "RRC-revision-v1"
        )
        assert target["member_status"] == "taken"
        yield app, target["job_id"]


def test_g7_the_column_pairs_bundle_reruns_to_match(g5_store: tuple[LocalApplication, str]) -> None:
    app, job_id = g5_store
    directory = app.files_root / "jobs" / job_id / "bundle"
    recorded = {
        path.name: json.loads(path.read_bytes())
        for path in sorted((directory / "artifacts").iterdir())
    }
    report = app.reproduce(directory, ReplayPolicy(rerun=True))
    assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
    assert report.verdict == "MATCH", (report.differences, report.reasons)
    assert report.differences == ()
    rerun_id = app.list_jobs(limit=200).items[-1].job_id
    rerun = {
        path.name: json.loads(path.read_bytes())
        for path in sorted((app.files_root / "jobs" / rerun_id / "rerun" / "artifacts").iterdir())
    }
    member = recorded["solve-path.json"]["revision_continuation"]
    assert rerun["solve-path.json"]["revision_continuation"] == member
    assert r0_projection(rerun) == r0_projection(recorded)
