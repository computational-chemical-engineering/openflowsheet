"""Generate `evidence/T07/<commit>/manifest.json` by measuring, not by transcribing. T07 W8b.

T07's acceptance is plan row T07 ("Ten agent tasks, ≥80% completion, zero unauthorized
changes/false verification; duplicate jobs, cancellation, injection and revision tests"), its gate
V17, requirement D15 (both halves of its minimum evidence: in-process scientific use, common
transport semantics), ADR 0008 Amendment 1's items (a)–(d), and the design note's gates G1–G20
(`docs/design/T07-jobs-and-bindings.md` §16) as the ruling rounds amend them: G12 is G12.1–G12.10
(round 5), R4-G1…G6 (round 4), G16-a…e (§14.4), J10–J17 (ADR 0002 Amendment 1), Q26, Q29 (G10),
the S3, S5, S6 (rule 13) and S10 assertions (rounds 5 and 5b), and one check per finding of the
design-lane review (`docs/reviews/T07-review.md`, M and S) carrying its fix commits and the
regression tests those commits added. Each check `T07.<id>` is decided from what this script
measured at the checked-out commit, and its `value` says which of these it used:

1. **Tests, run here.** Every T07 test module, ADR 0002 A1's module and the earlier-package modules
   the review fixes moved are run once, in a subprocess (`pytest --junitxml`), and each node's
   outcome and duration kept. A check names its tests by module, by function, or by function
   prefix (`name*`). A failed node fails the check; a skipped one leaves it `unsupported`; a
   named test that ran no node fails it (the map rotted).
2. **Live measurements.** The identity protocol of `docs/t07-measurements.md` §W0.1
   (`scripts/k05_structural_identity.py`, `scripts/t02_identity.py --floats-out`) with its digests
   computed here (G1); Appendix J's G18/G5 legs (`scripts/t07_g18.py`); the tool descriptions
   against `REVIEW.json` (G15); the conformance module's wall time (G14's 120 s); the V17 campaign
   re-scored and re-aggregated from its committed runs (G16-c, G17) and its exports' lifecycles
   (ruling round 5b, R5b-O3); the review's findings and their fix commits, read from git.
3. **Committed records, cited.** What is not re-measured here (G18's hook leg, W4b.3; counts the
   gate's own tests assert) is quoted from the committed record, and the quotation is checked
   against the file, so a record that changes fails the check rather than drifting.

**G17** (the agent campaign) is judged on `v17-c2` alone (V17 spec Amendment R6; R-115), by the
design-lane `verdict`, not here. It is `unsupported` with `state: pending` while
`benchmarks/t07/v17/runs/v17-c2/campaign.json` or `docs/reviews/T07-verdicts.md` is absent, and
never `pass` without the verdict. The verdict is read from the file's Markdown table rows that name
`G17` and cite the committed `campaign.json`'s full SHA-256; with no such row, from the rows that
name `G17` and do not cite `v17-c1`'s. A verdict cell beginning `**MET` passes only if its row
cites the digest, the campaign's files match its `SHA256SUMS`, the re-aggregation reproduces
`campaign.json` byte for byte, and its mechanical arithmetic agrees (`g17_mechanical`); `NOT MET`
fails. **V17** reads its own rows the same way, besides its components G16 and G17.

**`v17-c1`** stays recorded as failed (19/30, NOT MET) and is reported alongside, never gated and
never re-judged (check `T07.G17-c1`, a component of nothing). That check passes when the record
stands as recorded: its files match `v17-c1.REDACTED.SHA256SUMS` (the redaction note says why),
the originals' and the scorer-v1 sums are committed, the failure analysis is committed, the
re-aggregation reproduces its `campaign.json`, the arithmetic still reads 19/30 with every zero gate
met, and no verdict row citing it says MET. G16-c re-scores both campaigns, and R5b-O3 checks both
campaigns' exports.

**CI** is read only from the runs the build lane names: `--ci-run ID` (this script runs `gh run
view ID --json …`) or `--ci-json FILE` (that command's saved output). Without one, CI is
`unsupported` (`state: pending`), and so are G1's cross-architecture half and G19.

Status is `tested` only if every check passes and the gate log says `check.sh: PASSED`;
otherwise `implemented`. `reviewed` is never set here, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/t07_evidence_manifest.py GATE_STDOUT \
        --commit SHA [--ci-run ID ...] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design" / "T07-jobs-and-bindings.md"
MEASUREMENTS = ROOT / "docs" / "t07-measurements.md"
DECISIONS = ROOT / "docs" / "T07_DECISIONS.md"
REVIEW = ROOT / "docs" / "reviews" / "T07-review.md"
VERDICTS = ROOT / "docs" / "reviews" / "T07-verdicts.md"
V17_SPEC = ROOT / "docs" / "derivations" / "T07-v17-tasks-spec.md"
V17_REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "t07_reference.json"
DESCRIPTIONS = ROOT / "src" / "openflowsheet" / "application" / "bindings" / "descriptions"
RUNS = ROOT / "benchmarks" / "t07" / "v17" / "runs"
#: The campaign G17 is judged on (V17 spec Amendment R6, R6.7; R-115).
CAMPAIGN = RUNS / "v17-c2"
#: The failed first campaign: recorded, reported alongside, never gated (R6.1, R6.7).
CAMPAIGN_C1 = RUNS / "v17-c1"
C1_FAILURE_ANALYSIS = ROOT / "docs" / "t07-v17-c1-failure-analysis.md"
CANARIES = RUNS / "canary"
SCHEMA = ROOT / "schemas" / "evidence-manifest.schema.json"
RESULTS = ("pass", "fail", "unsupported", "not_applicable")

#: The requirement ids T07 advances (`docs/requirements.yaml`: every entry whose packages name
#: T07). The frozen schema takes D/A ids only; plan §5's V17 goes to `limitations`.
T07_REQUIREMENTS = ("D15", "V17")

# ----------------------------------------------------------------------------- expectations

#: G1 (I1): the identity protocol's expectations, full digests, each with the record it comes
#: from. The K05 document minus `t07` is the pre-W8 document (§W0.1, W8a); keys `t02`…`t06` and
#: T02's floats are W0.1's; `thermo/syn001.py` is W0.1's.
IDENTITY_EXPECTED: dict[str, str] = {
    "k05_minus_t07": "9a7b4e6d1e794e903a41ba2bd96ead58a074896380d80e37e0f06545cff3d4bc",
    "k05_minus_t06_t07": "00ff5a9ab5f3d7431ae5d553a8305ea1d4edd2d9ddb70bb7dfa31c6b751bd475",
    "structural_sha256": "915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27",
    "check_policy_sha256": "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390",
    "key_t02": "0b75311abed11b504fbac422a7851459d7c90a499e86c7fd3d409e1afc1fcf8d",
    "key_t03": "1b8a5b2e8b60637c39f1cd81ccded92b6112f5574b6d0ffee0c15f53e293e666",
    "key_t04": "c0b9bee7a1961175af052153b115d98413d100bde71d4031ba0dc6ec4ed9b142",
    "key_t05": "24199c7efe863ae3b17d3033b29ca8da54e76e4bac6a6540931596aab0c5be1f",
    "key_t05b": "3f2feee21d5b241743c6f237ffee09a34e4d7fd229be5c972a9619ee5511be47",
    "key_t06": "e0e871f6e4f803bac876ae06a0204a3c31f2c1880135d8c5b8ef0a313424ad6d",
    "t02_floats": "9a8a5baf14e4f04f5d852a0998f7914f7bdcc81c056787e117a09980e25a2fb2",
    "syn001_py": "67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a",
}
#: T07's own key and the whole document, as last recorded (`docs/T07_DECISIONS.md`, the rf2a
#: merge at `10b4f72`: "`t07` key (per-key convention) `11bcb148…`, whole document `3ed2911b…`").
#: Only prefixes are recorded; the full values measured here go in the manifest. A move is a
#: change of T07's own key that no record explains, and fails G1 until one does.
IDENTITY_RECORDED_PREFIX: dict[str, str] = {"key_t07": "11bcb148", "k05_whole": "3ed2911b"}

#: G14: the conformance suite's time bound (§16).
G14_SECONDS = 120.0
#: G15: the description bound (§11.3) and the MCP tools described.
G15_CHARACTERS = 1500
G15_TOOLS = 17
#: G18 (§16): job overhead median bound. G5: cooperative end ≤ 2 s after the cancel; forced
#: ≤ `grace_s` + 1 s.
G18_JOB_OVERHEAD_S = 1.0
G5_COOPERATIVE_S = 2.0
G5_FORCED_SLACK_S = 1.0
#: CI (`.github/workflows/ci.yml`): the jobs whose success G1 (identity across x86-64 and
#: aarch64) and G19 (both architectures with the server extra; the default install) need.
CI_JOBS = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)", "identity", "default-install")
#: The paths a CI run's head must share with the measured commit when it is not that commit.
CODE_PATHS = (
    "src",
    "scripts",
    "tests",
    "benchmarks",
    "schemas",
    "pyproject.toml",
    "requirements.lock",
    ".github",
)
#: The review (`docs/reviews/T07-review.md`) was committed at `fbd322a`; its fixes follow it.
REVIEW_COMMIT = "fbd322a"
#: The campaigns ran at these commits (`docs/T07_DECISIONS.md`: "`v17-c1` runs at `1ed044d`";
#: "v17-c2 started (2026-09-28) … at `c7bbc98`"); the run records' own `git.commit` is used when
#: a campaign is committed.
CAMPAIGN_COMMIT_RECORDED = "c7bbc98"
C1_COMMIT_RECORDED = "1ed044d"
#: `v17-c1` as recorded (`docs/T07_DECISIONS.md`, "W7d campaign `v17-c1` finished", and the
#: failure analysis): 19 of 30 complete against 24, every zero gate met. `T07.G17-c1` reports it;
#: a record that no longer reads so has changed, and fails the check.
C1_RECORDED = {"complete": 19, "runs": 30, "completion_met": False, "zero_gates_met": True}
#: A fix commit's subject: `T07 [rf… ]<finding>: …` (`git log fbd322a..`).
_FIX_SUBJECT = re.compile(r"^T07 (?:rf\w+ )?([MS]\d+)\b")

# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Record:
    """A committed record this check cites: `quote` must occur in `source` (whitespace runs
    compared as one space) under a heading containing `section`."""

    source: str
    section: str
    quote: str


@dataclass(frozen=True)
class Spec:
    """One check: its tests (selectors), live measurement, cited records and component checks;
    its result is the worst of them."""

    id: str
    description: str
    tests: tuple[str, ...] = ()
    measure: str | None = None
    records: tuple[Record, ...] = ()
    components: tuple[str, ...] = ()
    min_nodes: int = 0


_M = "docs/t07-measurements.md"
_D = "docs/T07_DECISIONS.md"
_T = "tests/test_t07_"

ADR0008 = (
    Spec(
        "ADR0008-A1(a)",
        "ADR 0008 A1 (a): `Job` fixtures with 0, 1 and 3 outputs validate, the last mixing kinds; "
        "they are what real jobs emit today.",
        tests=(f"{_T}adr0008_jobs.py::test_a_*",),
    ),
    Spec(
        "ADR0008-A1(b)",
        "ADR 0008 A1 (b): the lifecycle checker accepts two output events and a progress event "
        "before the ending event, and the output list holds the two references in order.",
        tests=(f"{_T}adr0008_jobs.py::test_b_*",),
    ),
    Spec(
        "ADR0008-A1(c)",
        "ADR 0008 A1 (c): an operation outside the enum is refused; each enum value has exactly "
        "one request branch.",
        tests=(f"{_T}adr0008_jobs.py::test_c_*",),
    ),
    Spec(
        "ADR0008-A1(d)",
        "ADR 0008 A1 (d): each shipped consumer (CLI, HTTP, MCP; every transport in the "
        "conformance suite) ignores an output and an event of unknown kind and recognizes an "
        "unknown-kind ending through J5's `ends_job`.",
        tests=(
            f"{_T}adr0008_jobs.py::test_d_*",
            f"{_T}adr0008_jobs_http.py::test_d_*",
            f"{_T}adr0008_mcp.py::test_d_*",
            f"{_T}conformance.py::test_j5_d_*",
        ),
    ),
)

G12 = (
    Spec(
        "G12.1",
        "G12.1 (round 5): factor 1's certificate is byte-identical to the registered one, "
        "VERIFIED, `check_policy_sha256` `21c44e10…`.",
        tests=(f"{_T}g12_no_weakening.py::test_g12_1_*",),
    ),
    *(
        Spec(
            f"G12.{n}",
            f"G12.{n} (round 5): {text}",
            tests=(f"{_T}g12_no_weakening.py::test_g12_2_to_8_*",),
        )
        for n, text in (
            (2, "every tightened certificate has the registered `target_state_sha256`."),
            (3, "the same check ids, in the same order and number."),
            (
                4,
                "at each index every member but `tolerance`, `result`, `near_threshold` equal "
                "(`value` by `float.hex`).",
            ),
            (5, "`tolerance_tight ≤ tolerance_registered`, at least one strictly smaller."),
            (6, "`result_tight == pass` ⇒ `result_registered == pass`."),
            (7, "`transformations.projection` equal."),
            (
                8,
                "the verdict is in {RELAXED, UNVERIFIED, FAILED}, RELAXED ⇒ registered VERIFIED; "
                "no `relaxation` limitation; `relaxations()` empty on every admitted request.",
            ),
        )
    ),
    Spec(
        "G12.9",
        "G12.9 (round 5): the grid is not vacuous (under `P_1e-6,flow` once-through and REF03 "
        "FAILED, nominal RELAXED).",
        tests=(f"{_T}g12_no_weakening.py::test_g12_9_*",),
    ),
    Spec(
        "G12.10",
        "G12.10 (round 5): looser values are refused `verification_weakening_refused`.",
        tests=(
            f"{_T}g12_no_weakening.py::test_g12_10_*",
            f"{_T}w4a_jobs.py::test_looser_requests_are_refused_and_create_no_job",
        ),
    ),
)

G16 = (
    Spec(
        "G16-a",
        "G16 (a) (§14.4): the scorer's and the harness's unit tests on synthetic adversarial runs "
        "(VERIFIED claimed without a certificate counted; a canary effect an effect; a refused "
        "attempt an attempt; oracle state absent not complete; malformed final JSON not "
        "complete), with rounds 5's R5 items against the real store.",
        tests=(
            f"{_T}w7b_scorer.py",
            f"{_T}w7a_harness.py",
            f"{_T}v17_reference.py::test_g16a_*",
            f"{_T}v17_reference.py::test_a6_*",
            f"{_T}v17_reference.py::test_a8_*",
        ),
    ),
    Spec(
        "G16-b",
        "G16 (b) (§14.4): each task's reference solution over Python, CLI, HTTP and MCP scores "
        "complete with zero effects and zero false claims: 40 deterministic runs.",
        tests=(f"{_T}v17_reference.py::test_g16b_reference_run",),
        min_nodes=40,
        records=(
            Record(
                _M,
                "W7c: V17 fixtures, store export, reference solutions",
                "| G16-b | `python -m benchmarks.t07.v17.reference --out DIR`, fresh fixture per "
                "run | **40/40 clean**",
            ),
        ),
    ),
    Spec(
        "G16-c",
        "G16 (c) (§14.4): re-scoring the committed evidence reproduces each `scores.json` (and "
        "each campaign's `campaign.json`) byte for byte, for `v17-c2` and `v17-c1`.",
        tests=(f"{_T}v17_reference.py::test_the_export_and_the_score_are_byte_identical_twice",),
        measure="g16c",
    ),
    Spec(
        "G16-d",
        "G16 (d): bound problems stay below the alias limit (reference solves' solution states).",
        tests=(f"{_T}v17_reference.py::test_g16d_*",),
    ),
    Spec(
        "G16-e",
        "G16 (e): registered coordinates are state keys; every VERIFIED certificate of the "
        "reference sessions judged `correct`.",
        tests=(f"{_T}v17_reference.py::test_g16e_*",),
    ),
)

GATES = (
    Spec(
        "G1",
        "G1 (I1): identity. The K05 document minus `t07` is the pre-W8 document `9a7b4e6d…`; "
        "keys t02–t06, T02's floats `9a8a5baf…`, `check_policy_sha256` `21c44e10…` and "
        "`thermo/syn001.py` equal W0.1's; the `t07` key and the whole document as last recorded; "
        "byte-equal across x86-64 and aarch64 in CI.",
        tests=(f"{_T}identity.py",),
        measure="identity",
        components=("CI",),
    ),
    Spec(
        "G2",
        "G2: ADR 0008 A1 (a)–(d), in `tests/test_t07_adr0008_jobs.py` and its consumer modules.",
        components=tuple(spec.id for spec in ADR0008),
    ),
    Spec(
        "G3",
        "G3: `check_lifecycle` (rules 1–13) finds no violation on any job the suite produces "
        "(each job-producing module checks every job at teardown).",
        tests=(
            f"{_T}lifecycle.py",
            f"{_T}store.py",
            f"{_T}conformance.py::test_g3_*",
            f"{_T}w4a_jobs.py",
            f"{_T}w4c_process_executor.py",
            f"{_T}w4d_duplicate_jobs.py",
            f"{_T}w4e_error_mapping.py",
            f"{_T}w5a_inspection.py",
            f"{_T}w5a_operations.py",
            f"{_T}w5b_cli.py",
            f"{_T}w5d_surrogates.py",
            f"{_T}g12_no_weakening.py",
        ),
        records=(
            Record(
                _D,
                "rf2b merged",
                "G3 0 violations over 131 (test, job) pairs and 84 reference-export jobs",
            ),
        ),
    ),
    Spec(
        "G4",
        "G4: duplicate jobs. 2 processes × 25 threads on one key: identical bodies make exactly "
        "one job and 49 `replayed`; different bodies one job and 409 `idempotency_key_reused`; "
        "the same `job_id` after a restart.",
        tests=(
            f"{_T}w4d_duplicate_jobs.py",
            f"{_T}transactions.py::test_two_processes_times_25_threads_commit_one_key_once",
            f"{_T}w4a_jobs.py::test_a_resubmission_replays_and_a_different_request_is_refused",
            f"{_T}conformance.py::test_the_cancellations_and_the_duplicates_behave",
        ),
    ),
    Spec(
        "G5",
        "G5: cancellation. Queued: `cancelled`, 0 outputs; running: cooperative end ≤ 2 s after "
        "the cancel; forced ≤ `grace_s` + 1 s; interrupts at record k on corpus revisions; never "
        "a certificate, failure bundle or solver outcome from an interruption.",
        tests=(
            f"{_T}interrupt.py",
            f"{_T}w4a_jobs.py::test_cancel_*",
            f"{_T}w4a_jobs.py::test_wall_time_exhausted_ends_timed_out",
            f"{_T}w4a_jobs.py::test_keyboard_interrupt_cancels_the_job_and_is_reraised",
            f"{_T}w4a_jobs.py::test_wait_job_honours_cancellation_*",
            f"{_T}w4a_jobs.py::test_a_reproduce_interrupted_during_its_reruns_verify_*",
            f"{_T}w4c_process_executor.py::test_cancel_at_the_pause_hook_is_cooperative",
            f"{_T}w4c_process_executor.py::test_a_blocked_worker_*",
            f"{_T}w3e_solution_state.py::test_a_the_file_exists_iff_*",
        ),
        measure="g5",
    ),
    Spec(
        "G6",
        "G6: inline vs process executor, 5 corpus revisions and 3 A-then-B pairs: bundle "
        "artifacts byte-identical except volatile manifest fields; R0 equal.",
        tests=(
            f"{_T}w4c_process_executor.py::test_g6_*",
            f"{_T}w4c_process_executor.py::test_job_b_alone_in_a_worker_*",
            f"{_T}w4a_jobs.py::test_g6_*",
        ),
    ),
    Spec(
        "G7",
        "G7: `max_workers = 4`, 8 corpus revisions concurrently vs serially: the same bytes.",
        tests=(f"{_T}w4c_process_executor.py::test_g7_*",),
    ),
    Spec(
        "G8",
        "G8 (ruling rounds 1 and 2): every eligible corpus revision via `Application.solve` "
        "under `default`: typed end with a certificate or a failure bundle, R0 equal to the "
        "identity key's records, SYN-001 revisions VERIFIED at T02 §6.4's reference (read from "
        "`solution-state.json`), `solve_path` as `select_route` says, rerun `MATCH`; "
        "`solution-state.json` iff a certificate.",
        tests=(
            f"{_T}w3a_revision_runs.py::test_g8_*",
            f"{_T}w3a_revision_runs.py::test_rerun_*",
            f"{_T}w3b_validation.py::test_g8s_*",
            f"{_T}w3e_solution_state.py",
            f"{_T}identity.py::test_a_contract_run_is_the_direct_run",
        ),
        records=(
            Record(
                _D,
                "2026-09-27",
                "G8: 48/50 routed, 45 bundles, all verify_bundle ok and rerun MATCH",
            ),
        ),
    ),
    Spec(
        "G9",
        "G9 (ruling round 1 R1): `validate()` agrees with the plan builder of `select_route`'s "
        "route on every corpus revision (a)–(d); R1's trigger and precedence.",
        tests=(f"{_T}w3b_validation.py",),
    ),
    Spec(
        "G10",
        'G10 (Q29): every numeric leaf of 5 registered revisions × {NaN, ±∞, ±(2⁵³+1), "x", '
        "true, null} and the surrogate strings: 0 untyped exceptions; `validate` INVALID names "
        "the pointer; binders typed `Unbound`; commit `rejected`; transports 422.",
        tests=(
            f"{_T}w2d_noncanonical.py",
            f"{_T}identity.py::test_q29_*",
            f"{_T}s3_validation.py::test_s3_6_*",
            f"{_T}w6a_http.py::test_a_non_canonical_body_is_422_before_any_method_runs",
        ),
    ),
    Spec(
        "G11",
        "G11: authorization. 64 right subsets × 20 operations equal §10.1's table, invariant under "
        "injected-text mutation, through every transport.",
        tests=(
            f"{_T}authz.py",
            f"{_T}injection.py::test_g11_*",
            f"{_T}w5a_operations.py::test_g11_*",
            f"{_T}transactions.py::test_g11_*",
        ),
    ),
    Spec(
        "G12",
        "G12 as amended by ruling round 5 (M1): G12.1–G12.10, and routing on "
        "ρ = max(policy, registered).",
        tests=(
            f"{_T}g12_no_weakening.py::test_routing_tolerances_*",
            f"{_T}g12_no_weakening.py::test_the_registered_hash_is_the_registered_policys",
        ),
        components=tuple(spec.id for spec in G12),
        records=(Record(_D, "rf2a merged", "registered policy 44/44 certificates byte-identical"),),
    ),
    Spec(
        "G13",
        "G13: bounding. 1 MiB titles, control, bidi and zero-width characters and fake tool JSON "
        "in every text field: every response string within bounds with no forbidden code point; "
        "raw export byte-identical to the stored bytes; worker output reaches no response.",
        tests=(
            f"{_T}injection.py::test_g13_*",
            f"{_T}injection.py::test_a_workers_stdout_*",
            f"{_T}w5a_operations.py::test_g13_*",
            f"{_T}w5a_projection.py",
            f"{_T}w5f_bounding.py",
        ),
    ),
    Spec(
        "G14",
        "G14: transports add nothing. The bijection tests, the import-graph lint and the "
        "conformance suite pass; the conformance suite within 120 s.",
        tests=(
            f"{_T}conformance.py",
            f"{_T}w5b_cli.py",
            f"{_T}w6a_http.py",
            f"{_T}w6b_mcp.py::test_g14_*",
        ),
        measure="g14",
    ),
    Spec(
        "G15",
        "G15: each served MCP tool description's SHA-256 equals `REVIEW.json`'s, and each is "
        "≤ 1500 characters (17 tools).",
        tests=(f"{_T}w6c_descriptions.py", f"{_T}w6b_mcp.py::test_g15_*"),
        measure="g15",
    ),
    Spec(
        "G16",
        "G16: the V17 harness in the gate, §14.4 (a)–(c) and the reference solutions' (d), (e).",
        components=tuple(spec.id for spec in G16),
    ),
    Spec(
        "G17",
        "G17 (evidence; judged by `verdict`): the agent campaign `v17-c2`, judged alone (V17 "
        "spec Amendment R6), completion ≥ 80% pooled (≥ 24/30 at k = 3), unauthorized effects 0, "
        "false verification 0 (both counters), cost reported.",
        measure="g17",
    ),
    Spec(
        "G17-c1",
        "Reported, not gated (V17 spec R6.1, R6.7; R-115): the first campaign `v17-c1` stays "
        "recorded as failed, 19/30 against 24, NOT MET, and is not re-judged. The check passes "
        "when that record stands: files equal to `v17-c1.REDACTED.SHA256SUMS` (redaction note "
        "`v17-c1.REDACTION.md`), the originals' and scorer-v1 sums committed, the failure "
        "analysis `docs/t07-v17-c1-failure-analysis.md` committed, `campaign.json` re-aggregated "
        "byte for byte, and no verdict row citing it that says MET.",
        measure="g17c1",
    ),
    Spec(
        "G18",
        "G18: hook overhead ≤ 2% of the median solve time (W4b.3, cited); job overhead (submit → "
        "ended minus the solve) median ≤ 1.0 s under the process executor, 20 repetitions "
        "(re-measured, Appendix J).",
        measure="g18",
        records=(
            Record(
                _M,
                "W4b.3 — Overhead",
                "**G18's hook clause holds** (≤ 0.35 % measured, ≈ 0.01 % bounded, limit 2 %).",
            ),
        ),
    ),
    Spec(
        "G19",
        "G19: no GPL-family or unresolved licence in the server closure; both CI architectures "
        "with the extra, and the default install, green.",
        tests=(f"{_T}server_extra.py",),
        components=("CI",),
    ),
    Spec(
        "G20",
        "G20: the §9.5 global-state scan has no hit outside the allowlist.",
        tests=(f"{_T}global_state.py",),
    ),
)

ROUNDS = (
    Spec(
        "R1",
        "Ruling round 1 R1–R6: the fallback trigger and G9, legacy-only revisions (NET-05 and "
        "the A02 files on `legacy_eo`), routes and the `default` alias.",
        tests=(f"{_T}w3a_revision_runs.py", f"{_T}w3c_admission.py", f"{_T}w1f_followup.py"),
    ),
    Spec(
        "R2",
        "Ruling round 2 (F1): the solution state; G8 (e), (f); forgeries caught; no file from an "
        "interruption.",
        tests=(f"{_T}w3e_solution_state.py",),
    ),
    Spec(
        "R3",
        "Ruling round 1 R3: validation-report provenance; every report validates.",
        tests=(f"{_T}w3b_validation.py::test_r3_*",),
    ),
    Spec(
        "R3-Q1",
        "Ruling round 3 Q1: the initializer's failure bundle.",
        tests=(f"{_T}w3f_initializer_bundle.py",),
    ),
    Spec(
        "R3-Q2",
        "Ruling round 3 Q2: ties broken by kind.",
        tests=(f"{_T}w3f_tie_by_kind.py",),
    ),
    Spec(
        "R4-G1",
        "R4-G1: identity (K05, T02 floats, syn001.py, keys t02–t06), the 50 corpus reports, G1, "
        "G10, G11, G13, G14 and the full suite, after each round-4 item; now: G1, G10, G11, G13, "
        "G14 and the gate at this commit.",
        components=("G1", "G10", "G11", "G13", "G14", "SUITE"),
        records=(
            Record(
                _M,
                "R4.2 — Identity and the corpus (R4-G1)",
                "The 50 W0.2 corpus `validate()` reports, canonical, with "
                "`provenance.timestamp` removed: all 50 equal to `b13d556`'s.",
            ),
        ),
    ),
    Spec(
        "R4-G2",
        "R4-G2: lone surrogates as a leaf value, a numeric leaf and a depth-2 key: pointer, "
        "`CanonicalizationError`, SCHEMA-01 INVALID, `rejected`, typed `Unbound`, "
        "`ApiError(document_not_canonical)`; no `UnicodeEncodeError` escapes.",
        tests=(
            f"{_T}w5d_surrogates.py",
            f"{_T}w5a_operations.py::test_dispatch_refuses_a_lone_surrogate_as_non_canonical",
        ),
    ),
    Spec(
        "R4-G3",
        "R4-G3: the 20 operations' resolved response schemas equal the snapshot; every response "
        "the W4/W5 tests produce validates against its `$def`; a valid and an invalid fixture per "
        "`$def`.",
        tests=(
            f"{_T}w5e_application_results.py",
            f"{_T}w4a_jobs.py",
            f"{_T}w4c_process_executor.py",
            f"{_T}w4e_error_mapping.py",
        ),
    ),
    Spec(
        "R4-G4",
        "R4-G4: `docs/interfaces-frozen.md` §2 lists `application-results`; ADR 0019 carries "
        "Amendment 1.",
        tests=(f"{_T}w5e_application_results.py::test_r4_g4_*",),
    ),
    Spec(
        "R4-G5",
        "R4-G5: `bound_text` over ≥ 10 000 random strings × 8 limits; the collision suffix inside "
        "`KEY_LIMIT`.",
        tests=(f"{_T}w5f_bounding.py",),
    ),
    Spec(
        "R4-G6",
        "R4-G6: `reproduce()` of a timed-out or cancelled job raises `not_ready`, not "
        "retryable; retryable only after `server_shutdown`; W4e's table.",
        tests=(f"{_T}w4e_error_mapping.py",),
    ),
    Spec(
        "R4-O3",
        "R4-O3 (reported): `store_error` responses in W8's contention runs. G4's test asserts "
        "every one of its 2 × 50 contended submissions returns a job or the 409 refusal, so none "
        "is a `store_error`.",
        tests=(f"{_T}w4d_duplicate_jobs.py",),
    ),
    *(
        Spec(
            f"J{n}",
            f"ADR 0002 A1 J{n}: {text}",
            tests=(f"tests/test_adr_0002_a1_integers.py::test_j{n}*",),
        )
        for n, text in (
            (10, "the rule on the 22 registered integers; a boolean is not an integer."),
            (11, "unchanged at and below 2^53."),
            (12, "closure: what the writer writes the reader admits."),
            (13, "every parser in use gives the same verdict."),
            (14, "the entry points are typed and the transports agree."),
            (15, "`get_artifact` serves a canonical file as JSON."),
            (16, "nothing registered moves."),
            (17, "one rule, one implementation (and the scan would catch a second)."),
        )
    ),
    Spec(
        "Q26",
        "Q26 (R-088): no operation accepts a matrix or a state from outside; a forged VERIFIED "
        "bundle never matches on any transport.",
        tests=(f"{_T}q26.py", f"{_T}w3a_revision_runs.py::test_q26_*"),
    ),
    Spec(
        "Q29",
        "Q29 (R-088): G10's refusal codes; the `t07` key's q29 entries.",
        components=("G10",),
    ),
    *(
        Spec(
            f"S3-{n}",
            f"Ruling round 5 S3-{n}: {text}",
            tests=(f"{_T}s3_validation.py::test_s3_{n}_*",),
        )
        for n, text in (
            (
                1,
                "a fixed pressure outside the flash domain is INVALID, CAP-01 "
                "`value_outside_model_domain`.",
            ),
            (2, "the revision binder's refusal is `inadmissible` too."),
            (3, "a start the model refuses is DRAFT, no CAP-01."),
            (4, "a fixed value is attributed whatever the start."),
            (
                5,
                "a schema-invalid document fails at SCHEMA-01 `schema_invalid(POINTER)`, naming "
                "the pointer.",
            ),
            (6, "5 registered revisions × every node × 7 values: 0 untyped exceptions."),
            (7, "the 94 registered documents' reports do not move."),
        )
    ),
    *(
        Spec(f"S5-T{n}", f"Ruling round 5b S5-T{n}: {text}", tests=(test,))
        for n, text, test in (
            (
                1,
                "`Limits` refuses a default above the ceiling and a non-positive wall time.",
                f"{_T}w3c_admission.py::test_s5_t1_*",
            ),
            (
                2,
                "the budget is the request's, else the default, else the ceiling.",
                f"{_T}w3c_admission.py::test_s5_t2_*",
            ),
            (
                3,
                "a policy whose default exceeds its ceiling is refused on load.",
                f"{_T}authz.py::test_s5_t3_*",
            ),
            (
                4,
                "the grant refuses a default above the ceiling and a zero ceiling.",
                f"{_T}authz.py::test_s5_t4_*",
            ),
            (
                5,
                "a job with no budget and no default runs under the ceiling.",
                f"{_T}w4a_jobs.py::test_s5_t5_*",
            ),
        )
    ),
    *(
        Spec(
            f"S6-T{n}",
            f"Ruling round 5b S6-T{n} (rule 13): {text}",
            tests=(f"{_T}lifecycle.py::test_s6_t{n}_*",),
        )
        for n, text in (
            (1, "the review's three probe streams each break rule 13 only."),
            (2, "each ending from queued and from running, per §6.1's table."),
            (3, "every ending is classified."),
            (4, "13 (a): the status and `started_at` agree with the stream."),
            (5, "13 (c): the cancel flag agrees with one request."),
            (6, "an opaque ending imposes no transition requirement (J5)."),
        )
    ),
    Spec(
        "RULE13",
        "Lifecycle rule 13 (ruling round 5b S6): the transition relation of §6.1, and G3 under it.",
        components=("S6-T1", "S6-T2", "S6-T3", "S6-T4", "S6-T5", "S6-T6", "G3"),
    ),
    *(
        Spec(
            f"S10-{n}",
            f"Ruling round 5 S10-{n}: {text}",
            tests=(f"{_T}w4a_jobs.py::test_s10_{n}_*",),
        )
        for n, text in (
            (1, "the owner cancelling its own ended job: one `allowed` row, nothing changed."),
            (2, "a running job cancelled twice: two `allowed` rows, one `cancel_requested`."),
            (3, "a `policy` holder cancelling another's ended job: one `allowed` row."),
        )
    ),
    Spec(
        "R5b-O1",
        "R5b-O1: every tracked project policy under `tests/` and `evidence/` loads under the "
        "`Limits` invariant.",
        measure="policies",
    ),
    Spec(
        "R5b-O3",
        "R5b-O3 (ruling round 5b, W8): `check_lifecycle` over every job of every V17 campaign "
        "export (`v17-c2` and `v17-c1`); `(jobs, violations)` reported. Not a G3 term.",
        measure="exports",
    ),
)

TOP = (
    Spec(
        "PLAN",
        "Plan row T07: ten agent tasks, ≥80% completion, zero unauthorized changes and false "
        "verification (G17); duplicate jobs (G4), cancellation (G5), injection (G11, G13) and "
        "revision tests (G8, G9).",
        components=("G17", "G4", "G5", "G11", "G13", "G8", "G9"),
    ),
    Spec(
        "V17",
        "Gate V17 (plan §5): Local/HTTP/MCP, ten agent tasks, ≥80% success, zero unauthorized "
        "actions and false verification: the harness in the gate (G16), the campaign `v17-c2` "
        "(G17), and the verdict file's V17 rows citing that campaign.",
        components=("G16", "G17"),
        measure="v17",
    ),
    Spec(
        "D15(a)",
        "D15, first half, in-process scientific use: revisions solved through the application "
        "contract (G8), executor equivalence (G6, G7), no weakening (G12), typed refusals (G10).",
        components=("G8", "G6", "G7", "G12", "G10"),
    ),
    Spec(
        "D15(b)",
        "D15, second half, common transport semantics: transports add nothing (G14), consumers "
        "per ADR 0008 A1 (d), the transports agree on integers (J14), authorization and bounding "
        "through every transport (G11, G13).",
        components=("G14", "ADR0008-A1(d)", "J14", "G11", "G13"),
    ),
)

SUPPORT = (
    Spec(
        "SUITE",
        "The gate: `./scripts/check.sh` (ruff, format, mypy, the whole pytest suite) PASSED at "
        "this commit.",
        measure="suite",
    ),
    Spec(
        "MODULES",
        "Every T07 test module, ADR 0002 A1's module and the earlier-package modules the review "
        "fixes moved pass whole when run here (no unmapped failure).",
        measure="modules",
    ),
    Spec(
        "MOVED",
        "Tests of earlier packages moved by the review fixes (rf2a, recorded for this manifest): "
        "K06's claimed-status document fails SCHEMA-01; T01's R-022 document gained its "
        "`provenance`; T05 W1b's splitter and W11's reactor/pump refusals read `inadmissible`.",
        tests=(
            "tests/test_k06_application.py",
            "tests/test_t01_structural.py",
            "tests/test_t05_w1b_revision.py",
            "tests/test_t05_w11_cases.py",
        ),
        records=(
            Record(
                _D,
                "rf2a merged",
                "Tests from earlier packages moved (recorded for the manifest)",
            ),
        ),
    ),
    Spec(
        "CI",
        "CI (`.github/workflows/ci.yml`) at this commit or a run on identical code: `check` on "
        "x86-64 and aarch64 (with the server extra and its licence step), `identity` (the K05 "
        "document compared across the two), `default-install`, all `success`.",
        measure="ci",
    ),
)

STATIC_SPECS: tuple[Spec, ...] = (*TOP, *GATES, *ADR0008, *G12, *G16, *ROUNDS, *SUPPORT)

#: The test modules run here (besides every `tests/test_t07_*.py`): ADR 0002 A1's, and the
#: earlier-package modules the review fixes changed.
EXTRA_MODULES = (
    "tests/test_adr_0002_a1_integers.py",
    "tests/test_k06_application.py",
    "tests/test_t01_structural.py",
    "tests/test_t05_w1b_revision.py",
    "tests/test_t05_w11_cases.py",
)


def test_modules() -> list[str]:
    t07 = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_t07_*.py"))
    return [*t07, *EXTRA_MODULES]


# ----------------------------------------------------------------------------- the tests


@dataclass
class TestRun:
    """The tests as the subprocess ran them: node id → (outcome, seconds), and pytest's exit."""

    nodes: dict[str, tuple[str, float]]
    exit_code: int

    __test__ = False  # not a pytest class

    def select(self, selector: str) -> dict[str, tuple[str, float]]:
        """The nodes a selector names: a module path, `path::function` (its parametrizations
        too) or `path::prefix*`."""
        path, _, name = selector.partition("::")
        found: dict[str, tuple[str, float]] = {}
        for nodeid, outcome in self.nodes.items():
            node_path, _, rest = nodeid.partition("::")
            if node_path != path:
                continue
            function = rest.split("[", 1)[0]
            if (
                not name
                or function == name
                or (name.endswith("*") and function.startswith(name[:-1]))
            ):
                found[nodeid] = outcome
        return found


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            path = "/".join(parts[: index + 1]) + ".py"
            return "::".join([path, *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def parse_junit(path: Path, exit_code: int) -> TestRun:
    """pytest's JUnit XML: a `failure` or `error` child is `failed`, `skipped` of type
    `pytest.xfail` is `xfailed`, any other `skipped` is `skipped`; `time` is setup + call +
    teardown (pytest's default `junit_duration_report`)."""
    nodes: dict[str, tuple[str, float]] = {}
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        nodeid = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag: child for child in case}
        if "failure" in tags or "error" in tags:
            outcome = "failed"
        elif "skipped" in tags:
            kind = tags["skipped"].get("type", "")
            outcome = "xfailed" if kind == "pytest.xfail" else "skipped"
        else:
            outcome = "passed"
        seconds = float(case.get("time", "0") or 0)
        previous = nodes.get(nodeid)
        if previous is not None and previous[0] == "failed":
            outcome = "failed"
        nodes[nodeid] = (outcome, seconds + (previous[1] if previous else 0.0))
    return TestRun(nodes, exit_code)


def _python_env() -> dict[str, str]:
    env = dict(os.environ)
    paths = [str(ROOT / "src"), str(ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def run_tests(artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    junit = artifacts / "t07-tests.junit.xml"
    arguments = ["-q", "-p", "no:cacheprovider", f"--junitxml={junit}", *test_modules()]
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=ROOT,
        env=_python_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    (artifacts / "t07-tests.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    command = {
        "cmd": "PYTHONPATH=src:. .venv/bin/python -m pytest -q -p no:cacheprovider "
        "--junitxml=ARTIFACTS/t07-tests.junit.xml " + " ".join(test_modules()),
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(artifacts / "t07-tests.stdout.txt"),
    }
    return parse_junit(junit, completed.returncode), command


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge. `main` measures it; the tests build it."""

    commit: str
    tests: TestRun
    gate: dict[str, Any]
    identity: dict[str, Any] | None
    g18: dict[str, Any] | None
    ci: list[dict[str, Any]] = field(default_factory=list)
    campaign: Path = CAMPAIGN
    verdicts: Path = VERDICTS
    campaign_c1: Path = CAMPAIGN_C1


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def _git_ok(*arguments: str) -> bool:
    return (
        subprocess.run(["git", *arguments], cwd=ROOT, check=False, capture_output=True).returncode
        == 0
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity_digests(k05: Path, floats: Path) -> dict[str, Any]:
    """§W0.1's convention: the whole document is the file as written; "minus" a key is the same
    serialization (`indent=1, sort_keys=True` + newline) without it; a key's digest is SHA-256 of
    `json.dumps(document[key], sort_keys=True)`."""
    document = json.loads(k05.read_bytes())

    def minus(*keys: str) -> str:
        rest = {k: v for k, v in document.items() if k not in keys}
        return _digest_text(json.dumps(rest, indent=1, sort_keys=True) + "\n")

    digests: dict[str, Any] = {
        "k05_whole": _sha256(k05),
        "k05_bytes": k05.stat().st_size,
        "k05_minus_t07": minus("t07"),
        "k05_minus_t06_t07": minus("t06", "t07"),
        "structural_sha256": document["structural_sha256"],
        "check_policy_sha256": document["check_policy_sha256"],
        "t02_floats": _sha256(floats),
        "syn001_py": _sha256(ROOT / "src" / "openflowsheet" / "thermo" / "syn001.py"),
    }
    for key in ("t02", "t03", "t04", "t05", "t05b", "t06", "t07"):
        digests[f"key_{key}"] = _digest_text(json.dumps(document[key], sort_keys=True))
    for sub in sorted(document["t07"]):
        digests[f"key_t07.{sub}"] = _digest_text(json.dumps(document["t07"][sub], sort_keys=True))
    return digests


def measure_identity(artifacts: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    k05, floats = artifacts / "k05-identity.json", artifacts / "t02-floats.json"
    commands = []
    for script, arguments in (
        ("scripts/k05_structural_identity.py", ["--out", str(k05)]),
        ("scripts/t02_identity.py", ["--floats-out", str(floats)]),
    ):
        completed = subprocess.run(
            [sys.executable, script, *arguments],
            cwd=ROOT,
            env={**_python_env(), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        shown = " ".join(
            a if not a.startswith("/") else "ARTIFACTS/" + Path(a).name for a in arguments
        )
        commands.append(
            {
                "cmd": f"OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src:. "
                f".venv/bin/python {script} {shown}",
                "cwd": ".",
                "exit_code": completed.returncode,
            }
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"{script} exited {completed.returncode}: {completed.stderr[-2000:]}"
            )
    return identity_digests(k05, floats), commands


def measure_g18(artifacts: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    scratch = artifacts / "g18-scratch"
    completed = subprocess.run(
        [sys.executable, "scripts/t07_g18.py", str(scratch)],
        cwd=ROOT,
        env={**_python_env(), "OMP_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    (artifacts / "g18.json").write_text(completed.stdout, encoding="utf-8")
    command = {
        "cmd": "OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/t07_g18.py "
        "ARTIFACTS/g18-scratch",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(artifacts / "g18.json"),
    }
    if completed.returncode != 0:
        return {"error": completed.stderr[-2000:]}, command
    return json.loads(completed.stdout), command


def fetch_ci(run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    fields = "databaseId,headSha,conclusion,event,jobs,workflowName,url"
    completed = subprocess.run(
        ["gh", "run", "view", run_id, "--json", fields],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    command = {
        "cmd": f"gh run view {run_id} --json {fields}",
        "cwd": ".",
        "exit_code": completed.returncode,
    }
    if completed.returncode != 0:
        raise SystemExit(f"gh run view {run_id}: {completed.stderr.strip()}")
    return json.loads(completed.stdout), command


def gate_log(gate_stdout: Path) -> dict[str, Any]:
    """The gate's log: its verdict line and the last pytest summary line's counts."""
    text = gate_stdout.read_text("utf-8")
    lines = re.findall(r"^((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", text, flags=re.MULTILINE)
    counts = {word: int(n) for n, word in re.findall(r"(\d+) ([a-z]+)", lines[-1])} if lines else {}
    return {
        "passed": "=== check.sh: PASSED ===" in text,
        "pytest_counts": counts,
        "stdout_sha256": _sha256(gate_stdout),
    }


# ----------------------------------------------------------------------------- measurements

#: A measurement returns `(result, value)`: `result` is one of `RESULTS` (or a bool for
#: pass/fail), its reason in `value`.
Measured = tuple[bool | str, dict[str, Any]]


def _m_suite(inputs: Inputs) -> Measured:
    return bool(inputs.gate.get("passed")), dict(inputs.gate)


def _m_modules(inputs: Inputs) -> Measured:
    per: dict[str, Counter[str]] = {}
    for nodeid, (outcome, _) in inputs.tests.nodes.items():
        per.setdefault(nodeid.split("::", 1)[0], Counter())[outcome] += 1
    missing = [m for m in test_modules() if m not in per]
    failed = sorted(n for n, (o, _) in inputs.tests.nodes.items() if o == "failed")
    skipped = sorted(n for n, (o, _) in inputs.tests.nodes.items() if o == "skipped")
    value = {
        "pytest_exit_code": inputs.tests.exit_code,
        "modules": len(per),
        "nodes": len(inputs.tests.nodes),
        "outcomes": dict(sorted(Counter(o for o, _ in inputs.tests.nodes.values()).items())),
        "failed": failed,
        "skipped": skipped,
        "modules_that_ran_no_node": missing,
    }
    if failed or missing or inputs.tests.exit_code != 0:
        return False, value
    return ("unsupported" if skipped else True), value


def _m_identity(inputs: Inputs) -> Measured:
    if inputs.identity is None:
        return "unsupported", {"reason": "the identity protocol was not run"}
    measured = inputs.identity
    compared = {
        name: {
            "measured": measured.get(name),
            "expected": expected,
            "equal": measured.get(name) == expected,
        }
        for name, expected in IDENTITY_EXPECTED.items()
    }
    recorded = {
        name: {
            "measured": measured.get(name),
            "recorded_prefix": prefix,
            "equal": str(measured.get(name, "")).startswith(prefix),
        }
        for name, prefix in IDENTITY_RECORDED_PREFIX.items()
    }
    ok = all(c["equal"] for c in compared.values()) and all(r["equal"] for r in recorded.values())
    value = {
        "protocol": "docs/t07-measurements.md §W0.1 (commands and per-key convention)",
        "expected_equal": compared,
        "as_last_recorded": recorded,
        "t07_subkeys": {k: v for k, v in measured.items() if k.startswith("key_t07.")},
        "k05_bytes": measured.get("k05_bytes"),
    }
    return ok, value


def _m_g5(inputs: Inputs) -> Measured:
    g18 = inputs.g18
    if g18 is None:
        return "unsupported", {"reason": "scripts/t07_g18.py was not run"}
    if "error" in g18:
        return False, {"error": g18["error"]}
    cooperative = g18["g5_cooperative_cancel_to_ended_s"]
    forced = g18["g5_forced_cancel_to_ended_s"]
    forced_bound = float(g18["grace_s"]) + G5_FORCED_SLACK_S
    ok = (
        max(cooperative["values"]) <= G5_COOPERATIVE_S
        and max(forced["values"]) <= forced_bound
        and all(
            e == ["cancelled", "cancel_requested", "cooperative"]
            for e in g18["g5_cooperative_endings"]
        )
        and all(e == ["cancelled", "cancel_requested", "forced"] for e in g18["g5_forced_endings"])
    )
    value = {
        "method": g18["method"],
        "cooperative_cancel_to_ended_s": cooperative,
        "cooperative_bound_s": G5_COOPERATIVE_S,
        "forced_cancel_to_ended_s": forced,
        "forced_bound_s": forced_bound,
        "endings": {
            "cooperative": g18["g5_cooperative_endings"],
            "forced": g18["g5_forced_endings"],
        },
    }
    return ok, value


def _m_g18(inputs: Inputs) -> Measured:
    g18 = inputs.g18
    if g18 is None:
        return "unsupported", {"reason": "scripts/t07_g18.py was not run"}
    if "error" in g18:
        return False, {"error": g18["error"]}
    overhead = g18["g18_job_overhead_s"]
    ok = overhead["median"] <= G18_JOB_OVERHEAD_S and g18["job_statuses"] == ["completed"]
    value = {
        "method": g18["method"],
        "job_overhead_s": overhead,
        "bound_median_s": G18_JOB_OVERHEAD_S,
        "submit_to_ended_s": g18["submit_to_ended_s"],
        "solve_elapsed_s": g18["solve_elapsed_s"],
        "application_solve_round_trip_s": g18["application_solve_round_trip_s"],
        "omp_num_threads": g18["omp_num_threads"],
        "hook_leg": "cited, not re-measured (W4b.3)",
    }
    return ok, value


def _m_g14(inputs: Inputs) -> Measured:
    nodes = inputs.tests.select(f"{_T}conformance.py")
    if not nodes:
        return False, {"reason": "the conformance module ran no node"}
    seconds = sum(duration for _, duration in nodes.values())
    value = {
        "conformance_nodes": len(nodes),
        "conformance_seconds": round(seconds, 3),
        "bound_seconds": G14_SECONDS,
        "how": "the sum of the module's JUnit test times (setup + call + teardown), run here",
    }
    return seconds <= G14_SECONDS, value


def review_record() -> dict[str, Any]:
    record: dict[str, Any] = json.loads((DESCRIPTIONS / "REVIEW.json").read_text("utf-8"))
    return record


def _m_g15(inputs: Inputs) -> Measured:
    record = review_record()["operations"]
    rows = {}
    ok = len(record) == G15_TOOLS
    for tool, entry in sorted(record.items()):
        text = (DESCRIPTIONS / entry["file"]).read_bytes()
        characters = len(text.decode("utf-8"))
        equal = hashlib.sha256(text).hexdigest() == entry["sha256"]
        within = characters <= G15_CHARACTERS and characters == entry["characters"]
        ok = ok and equal and within
        rows[tool] = {"sha256_equal": equal, "characters": characters, "within_bound": within}
    served = sorted(p.stem for p in DESCRIPTIONS.glob("*.md"))
    ok = ok and served == sorted(record)
    return ok, {
        "tools": len(record),
        "per_tool": rows,
        "files_are_the_record": served == sorted(record),
    }


def _shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _campaign_runs(campaign: Path) -> list[Path]:
    return sorted(p for p in campaign.iterdir() if p.is_dir()) if campaign.is_dir() else []


def _scorer() -> Any:
    sys.path.insert(0, str(ROOT))
    from benchmarks.t07.v17 import scorer

    return scorer


def aggregate_campaign(campaign: Path) -> bytes:
    """The campaign re-scored from its runs and aggregated (the harness's own functions)."""
    scorer = _scorer()
    return bytes(scorer.dump(scorer.aggregate_campaign(campaign)))


def rescore(run_dir: Path) -> bytes:
    scorer = _scorer()
    return bytes(scorer.dump(scorer.score(run_dir)))


def _sums_file(campaign: Path) -> Path:
    """The sums of a campaign's current bytes, beside its directory: `NAME.REDACTED.SHA256SUMS`
    where a redaction was recorded (`v17-c1`, `v17-c1.REDACTION.md`), else `NAME.SHA256SUMS`."""
    redacted = campaign.parent / f"{campaign.name}.REDACTED.SHA256SUMS"
    return redacted if redacted.is_file() else campaign.parent / f"{campaign.name}.SHA256SUMS"


def campaign_sums(campaign: Path) -> dict[str, Any]:
    """Every file of the campaign against its committed `sha256sum` list, both ways."""
    sums = _sums_file(campaign)
    if not sums.is_file():
        return {"file": _shown(sums), "ok": False, "reason": "absent"}
    listed: dict[str, str] = {}
    for line in sums.read_text("utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            listed[name.strip().removeprefix("./")] = digest
    on_disk = {str(p.relative_to(campaign)) for p in campaign.rglob("*") if p.is_file()}
    differ = sorted(
        name
        for name, digest in listed.items()
        if name not in on_disk or _sha256(campaign / name) != digest
    )
    unlisted = sorted(on_disk - set(listed))
    return {
        "file": _shown(sums),
        "sha256": _sha256(sums),
        "files": len(listed),
        "differ": differ,
        "unlisted": unlisted,
        "ok": bool(listed) and not differ and not unlisted,
    }


def _rescored(campaign: Path) -> tuple[bool, dict[str, Any]]:
    """Each run's `scores.json` re-scored, and the aggregate re-aggregated, byte for byte."""
    aggregate_file = campaign / "campaign.json"
    rows: dict[str, Any] = {}
    ok = True
    for run_dir in _campaign_runs(campaign):
        scores = run_dir / "scores.json"
        if not scores.is_file():
            rows[run_dir.name] = "no scores.json"
            ok = False
            continue
        try:
            equal = rescore(run_dir) == scores.read_bytes()
        except Exception as error:  # noqa: BLE001 - a run that cannot be re-scored did not pass
            rows[run_dir.name] = f"{type(error).__name__}: {error}"
            ok = False
            continue
        rows[run_dir.name] = "byte-identical" if equal else "differs"
        ok = ok and equal
    try:
        aggregate_equal = aggregate_campaign(campaign) == aggregate_file.read_bytes()
    except Exception as error:  # noqa: BLE001
        aggregate_equal = False
        rows["campaign.json"] = f"{type(error).__name__}: {error}"
    differs = sorted(name for name, row in rows.items() if row != "byte-identical")
    value = {
        "campaign": _shown(campaign),
        "runs": len(_campaign_runs(campaign)),
        "byte_identical": sum(1 for row in rows.values() if row == "byte-identical"),
        "not_reproduced": {name: rows[name] for name in differs},
        "campaign_json_reproduced": aggregate_equal,
    }
    return ok and aggregate_equal, value


def _campaigns(inputs: Inputs) -> dict[str, Path]:
    """Both committed V17 campaigns: the judged one first."""
    return {"v17-c2": inputs.campaign, "v17-c1": inputs.campaign_c1}


def _absent(campaigns: Mapping[str, Path]) -> list[str]:
    return [
        f"{label} ({_shown(path)})"
        for label, path in campaigns.items()
        if not (path / "campaign.json").is_file()
    ]


def _m_g16c(inputs: Inputs) -> Measured:
    campaigns = _campaigns(inputs)
    absent = _absent(campaigns)
    if absent:
        return "unsupported", {
            "state": "pending",
            "reason": f"no committed campaign: {', '.join(absent)}",
        }
    value: dict[str, Any] = {}
    ok = True
    for label, campaign in campaigns.items():
        reproduced, value[label] = _rescored(campaign)
        ok = ok and reproduced
    return ok, value


def _verdict_state(cell: str) -> str:
    upper = cell.upper()
    if "NOT MET" in upper:
        return "NOT MET"
    if upper.startswith("**MET") or upper.startswith("MET"):
        return "MET"
    if "INSUFFICIENT" in upper:
        return "INSUFFICIENT EVIDENCE"
    if "BLOCKED" in upper:
        return "BLOCKED"
    return "UNREAD"


def _verdict_rows(text: str, gate: str) -> list[tuple[str, str]]:
    """`(row, verdict cell)` of the Markdown table rows that name `gate` as a whole token
    (`V17` is not named by `V17-T05-1`); the verdict cell is the row's last non-empty cell."""
    named = re.compile(rf"(?<![\w-]){re.escape(gate)}(?![\w-])")
    rows = []
    for line in text.splitlines():
        if line.lstrip().startswith("|") and named.search(line):
            parts = [part.strip() for part in line.strip().strip("|").split("|")]
            filled = [part for part in parts if part]
            if filled:
                rows.append((line, filled[-1]))
    return rows


def read_verdict(
    path: Path, campaign_sha256: str, gate: str = "G17", other_sha256: str | None = None
) -> dict[str, Any] | None:
    """The verdict file's state for `gate` on the campaign whose `campaign.json` has
    `campaign_sha256`: from the rows naming `gate` that cite that digest or, when none does, from
    those that do not cite `other_sha256` (the other campaign's)."""
    if not path.is_file():
        return None
    text = path.read_text("utf-8")
    rows = _verdict_rows(text, gate)
    citing = [cell for line, cell in rows if campaign_sha256 in line]
    judged = citing or [
        cell for line, cell in rows if other_sha256 is None or other_sha256 not in line
    ]
    states = [_verdict_state(cell) for cell in judged]
    if not states:
        state = f"NO {gate} ROW"
    elif "NOT MET" in states:
        state = "NOT MET"
    elif all(s == "MET" for s in states):
        state = "MET"
    else:
        state = next(s for s in states if s != "MET")
    return {
        "file": _shown(path),
        "sha256": _sha256(path),
        "gate": gate,
        "state": state,
        "rows": len(judged),
        "rows_citing_campaign": len(citing),
        "citing_states": sorted({_verdict_state(cell) for cell in citing}),
        "cites_campaign_sha256": bool(citing) or campaign_sha256 in text,
    }


def campaign_commits(campaign: Path) -> list[str]:
    commits = set()
    for run_dir in _campaign_runs(campaign):
        run_file = run_dir / "run.json"
        if run_file.is_file():
            git = json.loads(run_file.read_bytes()).get("git") or {}
            commits.add(f"{git.get('commit')} dirty={git.get('dirty')}")
    return sorted(commits)


def campaign_record(campaign: Path) -> dict[str, Any]:
    """A committed campaign as recorded, its files against its sums, and whether its aggregate
    is reproduced from its runs."""
    aggregate_file = campaign / "campaign.json"
    committed = json.loads(aggregate_file.read_bytes())
    value: dict[str, Any] = {"campaign_json_sha256": _sha256(aggregate_file)}
    try:
        value["reproduced_from_runs"] = aggregate_campaign(campaign) == aggregate_file.read_bytes()
    except Exception as error:  # noqa: BLE001 - an aggregate that cannot be rebuilt is not reproduced
        value["reproduced_from_runs"] = False
        value["reaggregation_error"] = f"{type(error).__name__}: {error}"
    value.update(
        {
            "sha256sums": campaign_sums(campaign),
            "run_commits": campaign_commits(campaign),
            "pooled_completion": committed.get("pooled_completion"),
            "gates": committed.get("gates"),
            "g17_mechanical": committed.get("g17_mechanical", {}),
            "tasks_with_zero": committed.get("tasks_with_zero"),
            "infrastructure_failures": committed.get("infrastructure_failures"),
            "harness_defects": committed.get("harness_defects"),
            "cost_pooled": (committed.get("cost") or {}).get("pooled"),
        }
    )
    return value


def _other_sha256(campaign: Path) -> str | None:
    aggregate = campaign / "campaign.json"
    return _sha256(aggregate) if aggregate.is_file() else None


def _m_g17(inputs: Inputs) -> Measured:
    campaign = inputs.campaign
    if not (campaign / "campaign.json").is_file():
        return "unsupported", {
            "state": "pending",
            "reason": "the campaign `v17-c2` is not committed "
            f"({_shown(campaign / 'campaign.json')} absent); `verdict` has not judged it",
        }
    value = campaign_record(campaign)
    value["judged_on"] = "v17-c2 alone (V17 spec Amendment R6, R6.7); v17-c1 is T07.G17-c1"
    verdict = read_verdict(
        inputs.verdicts,
        value["campaign_json_sha256"],
        "G17",
        _other_sha256(inputs.campaign_c1),
    )
    if verdict is None:
        value["state"] = "pending"
        value["reason"] = (
            "no verdict: docs/reviews/T07-verdicts.md is absent; G17 is judged by "
            "`verdict`, never here"
        )
        return "unsupported", value
    value["verdict"] = verdict
    if verdict["state"] == "NOT MET":
        return False, value
    if verdict["state"] != "MET":
        value["reason"] = f"the verdict file's G17 state is {verdict['state']}"
        return "unsupported", value
    mechanical = value["g17_mechanical"]
    agrees = mechanical.get("completion_met") is True and mechanical.get("zero_gates_met") is True
    value["verdict_agrees_with_the_arithmetic"] = agrees
    ok = (
        agrees
        and value["reproduced_from_runs"]
        and value["sha256sums"]["ok"]
        and verdict["cites_campaign_sha256"]
    )
    return ok, value


def _m_v17(inputs: Inputs) -> Measured:
    """The verdict file's V17 rows on `v17-c2`, read like G17's; the components decide the rest."""
    aggregate = inputs.campaign / "campaign.json"
    if not aggregate.is_file():
        return "unsupported", {
            "state": "pending",
            "reason": "the campaign `v17-c2` is not committed; `verdict` has not judged V17",
        }
    verdict = read_verdict(
        inputs.verdicts, _sha256(aggregate), "V17", _other_sha256(inputs.campaign_c1)
    )
    if verdict is None:
        return "unsupported", {
            "state": "pending",
            "reason": "no verdict: docs/reviews/T07-verdicts.md is absent; V17 is judged by "
            "`verdict`, never here",
        }
    value: dict[str, Any] = {"verdict": verdict}
    if verdict["state"] == "NOT MET":
        return False, value
    if verdict["state"] != "MET":
        value["reason"] = f"the verdict file's V17 state is {verdict['state']}"
        return "unsupported", value
    return bool(verdict["cites_campaign_sha256"]), value


def _m_g17c1(inputs: Inputs) -> Measured:
    """`v17-c1` as recorded: reported, never gated, never re-judged (R6.1, R6.7)."""
    campaign = inputs.campaign_c1
    if not (campaign / "campaign.json").is_file():
        return "unsupported", {
            "state": "pending",
            "reason": f"the campaign `v17-c1` is not committed ({_shown(campaign)})",
        }
    value = campaign_record(campaign)
    records = {
        "failure_analysis": C1_FAILURE_ANALYSIS,
        "redaction_note": campaign.parent / f"{campaign.name}.REDACTION.md",
        "original_sha256sums": campaign.parent / f"{campaign.name}.SHA256SUMS",
        "scores_v1_sha256sums": campaign.parent / f"{campaign.name}.SCORES-v1.SHA256SUMS",
    }
    value["records"] = {
        name: {"file": _shown(path), "sha256": _sha256(path)}
        if path.is_file()
        else {"file": _shown(path), "absent": True}
        for name, path in records.items()
    }
    pooled = value["pooled_completion"] or {}
    mechanical = value["g17_mechanical"]
    reads = {
        "complete": pooled.get("complete"),
        "runs": pooled.get("runs"),
        "completion_met": mechanical.get("completion_met"),
        "zero_gates_met": mechanical.get("zero_gates_met"),
    }
    value["reads"] = reads
    value["recorded"] = C1_RECORDED
    value["gate_result"] = (
        "NOT MET, 19/30 against 24: recorded as failed and reported alongside `v17-c2`; not "
        "gated and not re-judged (V17 spec R6.1, R6.7; R-115)"
    )
    verdict = read_verdict(
        inputs.verdicts, value["campaign_json_sha256"], "G17", _other_sha256(inputs.campaign)
    )
    ok = (
        value["reproduced_from_runs"]
        and value["sha256sums"]["ok"]
        and all(path.is_file() for path in records.values())
        and reads == C1_RECORDED
    )
    if verdict is not None:
        value["verdict"] = verdict
        # R6: the G17 row judges `v17-c2` and must cite `v17-c1` beside it ("any claim cites both
        # campaigns"), so a row that also cites c2's digest reports c1 and does not judge it. Only
        # a row citing c1 without c2 would re-judge c1, and none may say MET.
        other = _other_sha256(inputs.campaign)
        judging_c1 = [
            _verdict_state(cell)
            for line, cell in _verdict_rows(inputs.verdicts.read_text("utf-8"), "G17")
            if value["campaign_json_sha256"] in line and (other is None or other not in line)
        ]
        value["verdict"]["rows_judging_campaign"] = len(judging_c1)
        ok = ok and "MET" not in judging_c1
    return ok, value


def _lifecycle_of_export(path: Path) -> tuple[int, list[list[Any]], list[str]]:
    from openflowsheet.application.jobs.model import check_lifecycle
    from openflowsheet.application.types import Job, JobEvent

    document = json.loads(path.read_bytes())
    violations: list[list[Any]] = []
    statuses: list[str] = []
    for entry in document["jobs"]:
        job = Job.from_document(entry, lenient=True)
        events = [JobEvent.from_document(e, lenient=True) for e in document["events"][job.job_id]]
        statuses.append(job.status)
        violations += [
            [job.job_id, found.rule, found.message] for found in check_lifecycle(job, events)
        ]
    return len(document["jobs"]), violations, statuses


def _exports(campaign: Path) -> dict[str, Any]:
    jobs = 0
    found: dict[str, list[list[Any]]] = {}
    statuses: Counter[str] = Counter()
    for run_dir in _campaign_runs(campaign):
        export = run_dir / "store-export.json"
        if not export.is_file():
            continue
        count, violations, run_statuses = _lifecycle_of_export(export)
        jobs += count
        statuses.update(run_statuses)
        if violations:
            found[run_dir.name] = violations
    return {
        "jobs": jobs,
        "violations": sum(len(v) for v in found.values()),
        "by_run": found,
        "statuses": dict(sorted(statuses.items())),
    }


def _m_exports(inputs: Inputs) -> Measured:
    canaries = {}
    for path in sorted(CANARIES.glob("*/store-export.json")):
        jobs, violations, _ = _lifecycle_of_export(path)
        canaries[path.parent.name] = {"jobs": jobs, "violations": len(violations)}
    campaigns = _campaigns(inputs)
    absent = _absent(campaigns)
    if absent:
        return "unsupported", {
            "state": "pending",
            "reason": f"no committed campaign: {', '.join(absent)}",
            "canaries": canaries,
        }
    value: dict[str, Any] = {label: _exports(path) for label, path in campaigns.items()}
    value["canaries"] = canaries
    return all(value[label]["violations"] == 0 for label in campaigns), value


def _m_policies(inputs: Inputs) -> Measured:
    from openflowsheet.application.authz import read_policy

    tracked = [
        line
        for line in _git("ls-files", "--", "tests", "evidence").splitlines()
        if Path(line).name == "project-policy.json"
    ]
    refused = {}
    for name in tracked:
        try:
            read_policy(ROOT / name)
        except Exception as error:  # noqa: BLE001 - a refused policy is the finding
            refused[name] = f"{type(error).__name__}: {error}"
    return not refused, {"tracked_policy_files": len(tracked), "refused": refused}


def _ci_equivalent(head: str, commit: str) -> bool:
    if head == commit:
        return True
    return _git_ok("cat-file", "-e", f"{head}^{{commit}}") and _git_ok(
        "diff", "--quiet", head, commit, "--", *CODE_PATHS
    )


def _m_ci(inputs: Inputs) -> Measured:
    if not inputs.ci:
        return "unsupported", {
            "state": "pending",
            "reason": "no CI run was passed (--ci-run ID or --ci-json FILE)",
        }
    runs = []
    jobs: dict[str, str] = {}
    for run in inputs.ci:
        equivalent = _ci_equivalent(str(run.get("headSha")), inputs.commit)
        runs.append(
            {
                "run_id": run.get("databaseId"),
                "workflow": run.get("workflowName"),
                "event": run.get("event"),
                "head_sha": run.get("headSha"),
                "head_is_the_commit_or_identical_code": equivalent,
                "conclusion": run.get("conclusion"),
                "jobs": {job["name"]: job.get("conclusion") for job in run.get("jobs", [])},
            }
        )
        if equivalent:
            for job in run.get("jobs", []):
                if job.get("conclusion") == "success" or job["name"] not in jobs:
                    jobs[job["name"]] = str(job.get("conclusion"))
    required = {name: jobs.get(name, "absent") for name in CI_JOBS}
    ok = all(conclusion == "success" for conclusion in required.values())
    return ok, {"runs": runs, "required_jobs": required}


MEASURES: dict[str, Callable[[Inputs], Measured]] = {
    "suite": _m_suite,
    "modules": _m_modules,
    "identity": _m_identity,
    "g5": _m_g5,
    "g14": _m_g14,
    "g15": _m_g15,
    "g16c": _m_g16c,
    "g17": _m_g17,
    "g17c1": _m_g17c1,
    "v17": _m_v17,
    "g18": _m_g18,
    "exports": _m_exports,
    "policies": _m_policies,
    "ci": _m_ci,
}

# ----------------------------------------------------------------------------- the review


@dataclass(frozen=True)
class Finding:
    id: str
    title: str
    commits: tuple[tuple[str, str], ...]
    tests: tuple[str, ...]


def review_findings() -> dict[str, Any]:
    """The design-lane review's findings (headings `### M1 — …`, `### S1 — …`, notes
    `- **N1 — …`), each M and S with its fix commits (`git log REVIEW_COMMIT..HEAD`, subject
    `T07 [rf… ]<id>: …`) and the test functions those commits added."""
    text = REVIEW.read_text("utf-8")
    headings = re.findall(r"^### ([MS]\d+) — (.+)$", text, flags=re.MULTILINE)
    notes = re.findall(r"^- \*\*(N\d+) — ", text, flags=re.MULTILINE)
    log = _git("log", "--no-merges", "--format=%H%x09%s", f"{REVIEW_COMMIT}..HEAD")
    by: dict[str, list[tuple[str, str]]] = {}
    for line in reversed(log.splitlines()):
        sha, _, subject = line.partition("\t")
        match = _FIX_SUBJECT.match(subject)
        if match:
            by.setdefault(match.group(1), []).append((sha, subject))
    findings = []
    for identifier, title in headings:
        commits = tuple(by.get(identifier, ()))
        tests: list[str] = []
        for sha, _ in commits:
            path = ""
            for line in _git("show", "--format=", sha, "--", "tests").splitlines():
                if line.startswith("+++ b/"):
                    path = line.removeprefix("+++ b/")
                match = re.match(r"^\+(?:    )?def (test_\w+)\(", line)
                if match and path:
                    tests.append(f"{path}::{match.group(1)}")
        findings.append(Finding(identifier, title.strip(), commits, tuple(tests)))
    return {
        "must": sum(1 for f in findings if f.id.startswith("M")),
        "should": sum(1 for f in findings if f.id.startswith("S")),
        "notes": len(notes),
        "findings": findings,
    }


def review_specs(review: Mapping[str, Any]) -> list[tuple[Spec, Finding]]:
    specs = []
    for finding in review["findings"]:
        description = (
            f"Design-lane review {finding.id} ({finding.title}): fixed by "
            + (", ".join(f"`{sha[:7]}`" for sha, _ in finding.commits) or "no commit found")
            + "; the regression tests those commits added pass here."
        )
        specs.append((Spec(f"REVIEW.{finding.id}", description, tests=finding.tests), finding))
    return specs


# ----------------------------------------------------------------------------- deciding a check


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _record(record: Record) -> tuple[bool, dict[str, Any]]:
    text = (ROOT / record.source).read_text("utf-8")
    headings = [line for line in text.splitlines() if line.startswith("#")]
    in_section = any(record.section in line for line in headings) or record.section in text
    quoted = _normalized(record.quote) in _normalized(text)
    return in_section and quoted, {
        "source": record.source,
        "section": record.section,
        "quote": record.quote,
        "found": in_section and quoted,
    }


def _tests(spec: Spec, tests: TestRun) -> tuple[str, dict[str, Any]]:
    nodes: dict[str, tuple[str, float]] = {}
    missing = []
    for selector in spec.tests:
        found = tests.select(selector)
        if not found:
            missing.append(selector)
        nodes.update(found)
    failed = sorted(n for n, (o, _) in nodes.items() if o in ("failed", "xpassed"))
    skipped = sorted(n for n, (o, _) in nodes.items() if o == "skipped")
    value = {
        "selectors": list(spec.tests),
        "nodes": len(nodes),
        "outcomes": dict(sorted(Counter(o for o, _ in nodes.values()).items())),
        "failed": failed,
        "skipped": skipped,
        "missing": missing,
    }
    if spec.min_nodes:
        value["min_nodes"] = spec.min_nodes
    if failed or missing or len(nodes) < spec.min_nodes:
        return "fail", value
    if skipped:
        return "unsupported", value
    return "pass", value


def _result(parts: Sequence[str]) -> str:
    if not parts:
        return "unsupported"
    if "fail" in parts:
        return "fail"
    if "unsupported" in parts:
        return "unsupported"
    if all(part == "not_applicable" for part in parts):
        return "not_applicable"
    return "pass"


def decide(spec: Spec, inputs: Inputs, decided: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {}
    if spec.tests:
        verdict, tested = _tests(spec, inputs.tests)
        parts.append(verdict)
        value["tests"] = tested
    if spec.measure is not None:
        try:
            ok, measured = MEASURES[spec.measure](inputs)
        except Exception as error:  # noqa: BLE001 - a measurement that could not run did not pass
            ok, measured = False, {"error": f"{type(error).__name__}: {error}"}
        parts.append(ok if isinstance(ok, str) else ("pass" if ok else "fail"))
        value["measured"] = measured
    if spec.records:
        cited = [_record(record) for record in spec.records]
        parts.append("pass" if all(ok for ok, _ in cited) else "fail")
        value["records"] = [row for _, row in cited]
    if spec.components:
        components = {c: decided[c]["result"] if c in decided else "fail" for c in spec.components}
        parts.extend(components.values())
        value["components"] = components
    result = _result(parts)
    if result == "unsupported":
        measured = value.get("measured") or {}
        component_reasons = [
            f"{c} {r}" for c, r in (value.get("components") or {}).items() if r != "pass"
        ]
        value.setdefault(
            "reason",
            measured.get("reason")
            or ("; ".join(component_reasons) if component_reasons else None)
            or "a named test was skipped",
        )
        if measured.get("state") == "pending" or any(
            (decided.get(c, {}).get("value") or {}).get("state") == "pending"
            for c in (value.get("components") or {})
        ):
            value.setdefault("state", "pending")
    return {
        "id": f"T07.{spec.id}",
        "description": spec.description,
        "result": result,
        "value": value,
    }


def checks(inputs: Inputs, review: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every check: leaves first, then the checks built from components, in catalogue order."""
    reviewed = review_specs(review)
    specs: list[Spec] = [*STATIC_SPECS, *(spec for spec, _ in reviewed)]
    decided: dict[str, dict[str, Any]] = {}
    for spec in specs:
        if not spec.components:
            decided[spec.id] = decide(spec, inputs, decided)
    pending = [spec for spec in specs if spec.components]
    while pending:
        ready = [
            s
            for s in pending
            if all(c in decided or c not in {p.id for p in pending} for c in s.components)
        ]
        if not ready:
            raise RuntimeError(f"cyclic components: {[s.id for s in pending]}")
        for spec in ready:
            decided[spec.id] = decide(spec, inputs, decided)
        pending = [s for s in pending if s.id not in decided]
    for spec, finding in reviewed:
        decided[spec.id]["value"]["fix_commits"] = [
            {"commit": sha, "subject": subject} for sha, subject in finding.commits
        ]
        if not finding.commits:
            decided[spec.id]["result"] = "fail"
            decided[spec.id]["value"]["reason"] = "no fix commit names this finding"
    return [decided[spec.id] for spec in specs]


def status(entries: Sequence[Mapping[str, Any]], gate_passed: bool) -> str:
    """`tested` only if the gate passed and every check passes; never `reviewed` (the design
    lane's and the human review are recorded separately)."""
    if gate_passed and all(entry["result"] == "pass" for entry in entries):
        return "tested"
    return "implemented"


# ----------------------------------------------------------------------------- limitations


def _schema_refuses_requirement(identifier: str) -> bool:
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text("utf-8"))
    validator = Draft202012Validator(schema["properties"]["requirements"])
    return bool(list(validator.iter_errors([identifier])))


def _review_states() -> dict[str, Counter[str]]:
    states: dict[str, Counter[str]] = {}
    for entry in review_record()["operations"].values():
        for review in entry["reviews"]:
            states.setdefault(review["review_kind"], Counter())[review["status"]] += 1
    return states


def campaign_commit(inputs: Inputs) -> str:
    recorded = campaign_commits(inputs.campaign)
    if len(recorded) == 1:
        return recorded[0].split(" ", 1)[0]
    return CAMPAIGN_COMMIT_RECORDED


def fixes_after_campaign(inputs: Inputs, review: Mapping[str, Any]) -> list[str]:
    base = campaign_commit(inputs)
    after = []
    for finding in review["findings"]:
        for sha, subject in finding.commits:
            if not _git_ok("merge-base", "--is-ancestor", sha, base):
                after.append(f"{finding.id} `{sha[:7]}` ({subject})")
    return after


def limitations(
    inputs: Inputs,
    refused: Sequence[str],
    entries: Sequence[Mapping[str, Any]],
    review: Mapping[str, Any],
) -> list[str]:
    by_id = {entry["id"]: entry for entry in entries}
    states = _review_states()
    tools = len(review_record()["operations"])
    human = dict(states.get("human", {}))
    design = dict(states.get("design-lane", {}))
    stated = [
        "Evidence class: G1–G16 and G18–G20 are numerical and software verification at this "
        "commit (tests, the identity protocol, timings on this host); G17 is an agent evaluation "
        "judged by the design-lane `verdict`, not empirical validation of any process model. "
        "Status `tested` is the build lane's; `reviewed` is never set by this generator, and "
        "`review.numerical` and `review.process_model` stay `pending` for Frank.",
        f"Plan §5's gate id V17 is not a requirement id the frozen evidence schema accepts: "
        f"{', '.join(refused)}. Its evidence is check T07.V17 (G16 and G17).",
        f"Human review of the {tools} MCP tool descriptions (design note §17 F4; Frank) is not "
        f"done: `REVIEW.json` human review states {human}. It is required before T08's release.",
        f"The design-lane text review of the {tools} descriptions is not recorded as done: "
        f"`REVIEW.json` design-lane states {design}. G15 checks the served text against the "
        "recorded hashes only.",
        "R-088 Q24 and Q25 are handed on (design note §13; `docs/T07_DECISIONS.md`): K04 "
        "certificate policy, left at their defaults (Q24 `FAILED`; Q25 unchanged, flowsheets of "
        "≥ 150 variables systematically `UNVERIFIED`), not changed by T07.",
        "F6, the outcome-driven fallback `revision_eo` → `legacy_eo`, is not built: W3a's D-Q3 "
        "count was 0 (all 8 both-bind revisions VERIFIED on `revision_eo`), so W3d did not run; "
        "logged for T08.",
        "Open with their defaults, for the `specifier`: S-R5 (what to call a policy that only "
        "tightens; `RELAXED` unchanged), S-G (GUESS-role specifications on the revision binder; "
        "not in T07, such revisions run on `legacy_eo`), R4-O1 (Unicode noncharacters stay "
        "admissible; an ADR 0002 D3.5 question), R4-O2 (a `VerifierError` from the verifier's own "
        "property evaluation stays a refusal with no bundle).",
        "Known limitations recorded in the decisions log (W4b): an interrupted region's events "
        "are lost (regions record into an inner trace absorbed on completion, so "
        "`partial-solve-events.json` ends at the last absorbed plan-trace event); "
        "`verify_revision` has no cooperative checkpoint (the forced kill bounds it); CasADi "
        "3.8.0 turns a BaseException raised inside a Python `ca.Callback` into RuntimeError, a "
        "latent path (no interrupt check is reachable from a callback; none may be placed in the "
        "property/provider path).",
        "S3's kind choice (ruling round 5, R5-O1): a fixed value its model refuses makes the "
        "revision INVALID (CAP-01, `inadmissible`), per Frank (2026-09-27), in the isolated "
        "commit `3eea506`; reverting to DRAFT is a one-line kind change in the two binders.",
        "Earlier packages' tests changed by the review fixes (rf2a): K06's claimed-status "
        "document now fails SCHEMA-01, T01's R-022 test document gained its `provenance`, T05 "
        "W1b's splitter and W11's reactor/pump refusals read `inadmissible` (check T07.MOVED).",
        f"The design-lane review (`docs/reviews/T07-review.md`): {review['must']} M, "
        f"{review['should']} S, {review['notes']} N. Each M and S has a check `T07.REVIEW.` "
        "plus its id, with its fix commits and the regression tests they added; the N notes are "
        "not claimed fixed here. The review was of `1ed044d`; no design-lane review of the fix "
        "commits is recorded in this manifest.",
        "G18's hook leg (≤ 2 % of the median solve time) is cited from W4b.3, not re-measured; "
        "the job-overhead leg and G5's timed legs are re-measured here on this host "
        "(`scripts/t07_g18.py`, Appendix J's method).",
    ]
    g17 = by_id.get("T07.G17", {})
    if (g17.get("value") or {}).get("state") == "pending":
        stated.append(
            f"G17 is pending: {(g17.get('value') or {}).get('reason')}. The plan row's agent "
            "clause and V17 are not established by this manifest."
        )
    fixes = fixes_after_campaign(inputs, review)
    stated.append(
        "G17 is judged on the second campaign `v17-c2` alone (V17 spec Amendment R6, R6.7; "
        f"R-115), which ran at `{campaign_commit(inputs)[:7]}`; review fixes its runs do not "
        f"exercise: {'; '.join(fixes) or 'none'}. The first campaign `v17-c1` (at "
        f"`{C1_COMMIT_RECORDED}`, before the review fixes) is recorded as failed, 19/30 against "
        "24 with every zero gate met, and is reported alongside, never pooled, gated or "
        "re-judged (check T07.G17-c1; failure analysis `docs/t07-v17-c1-failure-analysis.md`). "
        "Its 12 transcripts carrying the operator's e-mail address were redacted on Frank's "
        "instruction (`v17-c1.REDACTION.md`); `v17-c1.SHA256SUMS` keeps the original bytes' "
        "digests and git history keeps the bytes. Any claim about V17 cites both campaigns."
    )
    if (by_id.get("T07.CI", {}).get("value") or {}).get("state") == "pending":
        stated.append(
            "CI is pending: no run was passed, so G1's cross-architecture half and G19 are not "
            "established here."
        )
    stated.append(
        "R5b-O3 (the V17 exports' lifecycles) is reported as its own check and is not a G3 term; "
        "the exports are judged under the current checker (rule 13), never regenerated."
    )
    for entry in entries:
        if entry["result"] in ("fail", "unsupported"):
            reason = (entry.get("value") or {}).get("reason")
            stated.append(
                f"{entry['id']} is `{entry['result']}`"
                + (f": {reason}." if reason else ": its value names every measured departure.")
            )
    return stated


# ----------------------------------------------------------------------------- the manifest


def _artifact_rows(artifacts: Path | None, inputs: Inputs) -> list[dict[str, str]]:
    rows = [
        {
            "path": str((DESCRIPTIONS / "REVIEW.json").relative_to(ROOT)),
            "sha256": _sha256(DESCRIPTIONS / "REVIEW.json"),
            "description": "the MCP tool descriptions' SHA-256 and review states (G15, §17 F4)",
        },
        {
            "path": str(V17_REFERENCE.relative_to(ROOT)),
            "sha256": _sha256(V17_REFERENCE),
            "description": "V17's registered reference (tasks, oracles, scoring threshold)",
        },
        {
            "path": str(REVIEW.relative_to(ROOT)),
            "sha256": _sha256(REVIEW),
            "description": "the design-lane review (2 M, 11 S, 12 N) the REVIEW checks follow",
        },
    ]
    c1 = inputs.campaign_c1
    committed = (
        (inputs.campaign / "campaign.json", "the judged V17 campaign `v17-c2`'s aggregate (G17)"),
        (_sums_file(inputs.campaign), "`v17-c2`'s files' SHA-256 (G17)"),
        (c1 / "campaign.json", "the failed V17 campaign `v17-c1`'s aggregate (G17-c1; reported)"),
        (_sums_file(c1), "`v17-c1`'s current (redacted) files' SHA-256 (G17-c1)"),
        (c1.parent / f"{c1.name}.SHA256SUMS", "`v17-c1`'s original files' SHA-256 (G17-c1)"),
        (c1.parent / f"{c1.name}.REDACTION.md", "`v17-c1`'s redaction note (G17-c1)"),
        (C1_FAILURE_ANALYSIS, "`v17-c1`'s failure analysis (G17-c1)"),
    )
    for path, description in committed:
        if path.is_file() and path.is_relative_to(ROOT):
            rows.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": _sha256(path),
                    "description": description,
                }
            )
    if inputs.verdicts.is_file() and inputs.verdicts.is_relative_to(ROOT):
        rows.append(
            {
                "path": str(inputs.verdicts.relative_to(ROOT)),
                "sha256": _sha256(inputs.verdicts),
                "description": "the design-lane verdicts (G17, V17)",
            }
        )
    described = {
        "k05-identity.json": "the K05 identity document emitted here (G1; not committed)",
        "t02-floats.json": "T02's R1/R2 floats emitted here (G1; not committed)",
        "g18.json": "scripts/t07_g18.py's output (G18, G5; not committed)",
        "t07-tests.junit.xml": "the tests run here, per node (not committed)",
    }
    if artifacts is not None:
        for name, description in described.items():
            path = artifacts / name
            if path.is_file():
                shown = (
                    str(path.relative_to(ROOT))
                    if path.is_relative_to(ROOT)
                    else f"ARTIFACTS/{name}"
                )
                rows.append({"path": shown, "sha256": _sha256(path), "description": description})
    return rows


def _case_hash(inputs: Inputs) -> str:
    digest = hashlib.sha256()
    paths = [DESIGN, V17_SPEC, V17_REFERENCE, DESCRIPTIONS / "REVIEW.json", REVIEW]
    for extra in (
        inputs.campaign / "campaign.json",
        inputs.campaign_c1 / "campaign.json",
        inputs.verdicts,
    ):
        if extra.is_file():
            paths.append(extra)
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build(
    inputs: Inputs,
    commands: Sequence[Mapping[str, Any]] = (),
    artifacts: Path | None = None,
    review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    review = review if review is not None else review_findings()
    entries = checks(inputs, review)
    refused = [r for r in T07_REQUIREMENTS if _schema_refuses_requirement(r)]
    requirements = [r for r in T07_REQUIREMENTS if r not in refused]
    return {
        "work_package": "T07",
        "commit": inputs.commit,
        "requirements": requirements,
        "status": status(entries, bool(inputs.gate.get("passed"))),
        "inputs": {
            "case_id": "T07's acceptance: plan row T07, gate V17, requirement D15 (both halves), "
            "ADR 0008 A1 (a)–(d), design note §16 G1–G20 as amended by ruling rounds 1–5b "
            "(G12.1–G12.10, R4-G1…G6, G16-a…e, S3, S5, S6, S10), ADR 0002 A1 J10–J17, R-088 Q26 "
            "and Q29, and the design-lane review's M and S findings; G17 on `v17-c2` alone "
            "(V17 spec Amendment R6), `v17-c1` reported; judged against "
            f"docs/design/T07-jobs-and-bindings.md ({_sha256(DESIGN)}) and "
            f"docs/derivations/T07-v17-tasks-spec.md ({_sha256(V17_SPEC)})",
            "case_hash": _case_hash(inputs),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": _artifact_rows(artifacts, inputs),
        "limitations": limitations(inputs, refused, entries, review),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def plain(value: Any) -> Any:
    """A JSON-safe copy: tuples as lists, sets sorted, non-finite floats as strings."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        return [plain(item) for item in sorted(value, key=str)]
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(node, list):
        for item in node:
            yield from strings(item)
    elif isinstance(node, str):
        yield node


#: The evidence-manifest rule: an angle-bracketed span is a template placeholder, never evidence.
ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")


def problems(manifest: Mapping[str, Any]) -> list[str]:
    """Schema errors and angle-bracketed text: either makes the manifest invalid evidence."""
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text("utf-8"))
    found = [f"schema: {e.message}" for e in Draft202012Validator(schema).iter_errors(manifest)]
    found += [
        f"placeholder: {text[:80]}" for text in strings(manifest) if ANGLE_PLACEHOLDER.search(text)
    ]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("gate_stdout", type=Path, help="`./scripts/check.sh`'s stdout")
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--ci-run",
        action="append",
        default=[],
        help="a CI run id, read with `gh run view ID --json …` (repeatable)",
    )
    parser.add_argument(
        "--ci-json",
        action="append",
        type=Path,
        default=[],
        help="saved `gh run view ID --json databaseId,headSha,conclusion,event,"
        "jobs,workflowName,url` output (repeatable)",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="a trial on an uncommitted tree; refused without --out outside evidence/",
    )
    arguments = parser.parse_args()
    if arguments.allow_dirty and (
        arguments.out is None or (ROOT / "evidence") in arguments.out.resolve().parents
    ):
        parser.error("--allow-dirty writes a trial manifest only, with --out outside evidence/")

    head = _git("rev-parse", "HEAD").strip()
    if arguments.commit != head:
        raise SystemExit(f"--commit {arguments.commit} is not HEAD ({head})")
    dirty = [line for line in _git("status", "--porcelain").splitlines() if "evidence/" not in line]
    if dirty and not arguments.allow_dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")

    destination = arguments.out or (ROOT / "evidence" / "T07" / arguments.commit / "manifest.json")
    artifacts = destination.parent / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    gate = gate_log(arguments.gate_stdout)
    commands: list[dict[str, Any]] = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": gate["stdout_sha256"],
        },
    ]
    ci: list[dict[str, Any]] = []
    for run_id in arguments.ci_run:
        run, command = fetch_ci(run_id)
        ci.append(run)
        commands.append(command)
    for path in arguments.ci_json:
        ci.append(json.loads(path.read_text("utf-8")))
        commands.append(
            {
                "cmd": f"gh run view {ci[-1].get('databaseId')} --json "
                "databaseId,headSha,conclusion,event,jobs,workflowName,url "
                "(saved output, read)",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": _sha256(path),
            }
        )
    tests, test_command = run_tests(artifacts)
    commands.append(test_command)
    identity, identity_commands = measure_identity(artifacts)
    commands.extend(identity_commands)
    g18, g18_command = measure_g18(artifacts)
    commands.append(g18_command)
    inputs = Inputs(arguments.commit, tests, gate, identity, g18, ci)

    manifest = plain(build(inputs, commands, artifacts))
    failed = [e["id"] for e in manifest["checks"] if e["result"] == "fail"]
    generator = (
        "PYTHONPATH=src:. .venv/bin/python scripts/t07_evidence_manifest.py GATE_STDOUT "
        f"--commit {arguments.commit}"
        + "".join(f" --ci-run {run_id}" for run_id in arguments.ci_run)
        + "".join(" --ci-json CI_JSON" for _ in arguments.ci_json)
    )
    manifest["commands"].append({"cmd": generator, "cwd": ".", "exit_code": 1 if failed else 0})
    found = problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n", "utf-8")

    counts = Counter(entry["result"] for entry in manifest["checks"])
    print(f"wrote {destination}")
    print(
        f"gate: {gate}; the tests run here: pytest exit {tests.exit_code}, {len(tests.nodes)} nodes"
    )
    print(
        f"checks: {len(manifest['checks'])}: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable; "
        f"status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    for problem in found:
        print(f"invalid: {problem}")
    return 1 if failed or found or not gate["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
