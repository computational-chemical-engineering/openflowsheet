"""Generate `evidence/T06/<commit>/manifest.json` by measuring, not by transcribing. T06.

T06's assertion catalogue is `docs/derivations/T06-corpus-spec.md` §13, `T6-A01`…`T6-A100`, as
amended through Amendment 5 (the closing round, `docs/briefs/T06-closing-round.md` §2). Each check
`T06.Ann` is decided from three kinds of measurement, all made by this script at the measured
commit, and its `value` says which it used:

1. **The gate's tests, run in this process.** Every T06 test module (`tests/test_t06_*.py`) and
   every earlier-package test the corpus reuses (`test_t06_w5_corpus.MEASURED_BY`: a case an
   earlier package already measures is not measured twice) are run once, in this process, by
   `pytest.main` with a recorder plugin; each node's outcome is kept. A test is attached to an
   assertion by the assertion number in its name (`test_a97e_…` → A97; `test_a99c_a31_…` → A99
   and A31), by the corpus row that names the assertion (the registry's `corpus[].assertion` and
   W5's `MEASURED_BY`), or by `EXTRA_TESTS` below, which names the tests an assertion is carried
   by where neither does. A check whose tests include a failure is `fail`; one whose named test
   no longer exists is `fail` (the map has rotted).
2. **The committed records, recomputed.** The ensemble, the holdout and the reference comparisons
   are never re-run here (spec §6.6 (A5), §7.6 (A5); W32's brief). Their assertions are measured
   from the committed files — `benchmarks/t06/ensemble/runs/` (run 1, run 2, run 2r, `holdout1`,
   with `SHA256SUMS` and the registry's `ensemble.runs`) and `benchmarks/t06/references/` — with
   the harness's own pure functions (`benchmarks.t06.ensemble.classify`, `report`,
   `a98_discrepancies`; `scripts/t06_ensemble.py`'s `render` and `compare`): every report, A98
   text and comparison is recomputed and compared byte for byte, and every headline is recounted
   from the records.
3. **Live measurements the gate does not make.** The K05 identity document is emitted twice, with
   SYN-001's implementation hash and with the pre-ADR-0017 one (A44, A78, A79, A87 (a)); A87 (b)
   solves the revision cases' registered starts under `newton` and `newton_refined`; A43 runs
   `validate()` over every registered revision file. Their expectations are the values recorded
   in `docs/t06-measurements.md` at the commits that registered them, quoted below with the
   section they come from.

Cross-platform items (A30, A35, A45, A79's CI half) are read from the committed CI run files and
from the CI runs' own records: pass `--ci DIR`, a directory holding `gh run view <id> --json
headSha,conclusion,event,jobs` output as `<id>.json` for each CI run cited, and the identity run's
downloaded `structural-identity-*` artifacts. Without it those halves are `unsupported`, never
`pass`.

Run 1's FAIL is reported as it stands: §7.3's gate is judged on run 2 (A30, A95), and run 1's
record — S = 431, its four THM-09 `F-OTHER-ROOT`s and NET-11 start 16 — is carried in the values
and the limitations. The holdout is reported and never gated (A99): no check compares its rate
with a threshold.

Usage:
    PYTHONPATH=src:. python scripts/t06_evidence_manifest.py <gate-stdout> --commit <sha> \
        --ci DIR [--out PATH]
"""

# ruff: noqa: E402 - the imports after the first block follow the `sys.path` setup that makes the
# gate's `tests/` and `scripts/` importable.

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import pytest
import test_t06_w4_registry as w4_registry
import test_t06_w5_corpus as w5_corpus
import yaml

from benchmarks.t06 import ensemble

SPEC = ROOT / "docs" / "derivations" / "T06-corpus-spec.md"
TWIN = ROOT / "benchmarks" / "t06" / "reference_values.yaml"
REGISTRY_FILE = ROOT / "benchmarks" / "registry.yaml"
RUNS_DIR = ROOT / "benchmarks" / "t06" / "ensemble" / "runs"
STARTS_FILE = ROOT / "benchmarks" / "t06" / "ensemble" / "starts-nominal-v1.json"
HOLDOUT_FILE = ROOT / "benchmarks" / "t06" / "ensemble" / "starts-nominal-holdout1.json"
REFERENCES = ROOT / "benchmarks" / "t06" / "references"
VERDICTS = ROOT / "docs" / "reviews" / "T06-verdicts.md"
REGISTRY: dict[str, Any] = yaml.safe_load(REGISTRY_FILE.read_text("utf-8"))
ENSEMBLE: dict[str, Any] = REGISTRY["ensemble"]
CLASSES = ("ref-x86-64", "ci-x86-64", "ci-aarch64")
GATE_CLASSES = tuple(ENSEMBLE["gate"]["machine_classes"])
RESULTS = ("pass", "fail", "unsupported", "not_applicable")
IDS = tuple(f"A{number:02d}" for number in range(1, 101))


def _script() -> ModuleType:
    """`scripts/t06_ensemble.py`, the harness's command line (its `render`, `compare`, `a98`)."""
    spec = importlib.util.spec_from_file_location(
        "t06_ensemble_manifest", ROOT / "scripts" / "t06_ensemble.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = _script()


# ----------------------------------------------------------------------------- the catalogue

#: §13's rows, each as the check's description: the assertion as amended, in brief. The spec's
#: row is the authority; the description says what this check measured against.
DESCRIPTIONS: dict[str, str] = {
    "A01": "`ref.corpus` is transcribed into the registry: 49 cases, each with id, class, "
    "fixture, expected kind, path, eligibility and denominator flag (30 in the denominator), "
    "equal to the twin's table.",
    "A02": "Every `verified_at_reference` case (27: the 22 eligible, THM-04, NUM-04, ADV-01, "
    "STA-03, STA-04) reaches `CONVERGED`, `VERIFIED` and S3 at T02 §6.4's allowances from its "
    "registered start under its registered policy (the revision path under `T06-revision-v2`, "
    "the tear path under `SYN-001-K03`, NET-05 under its A02 policy).",
    "A03": "NUM-01, NUM-02 and NET-04 (`converged_to_closed_form`) meet their K03/T02 "
    "registrations.",
    "A04": "STR-02 is `DRAFT`, STR-01…05 `NOT_RUN`, message and implicated as §3.2; never "
    "compiled or solved.",
    "A05": "STR-03 as T01 A09.",
    "A06": "STR-04 as T01 A18.",
    "A07": "STR-05: CH-UP `STRUCTURALLY_CLOSED`, `CONVERGED`, `UNVERIFIED`, `RANK_DEFICIENT` "
    "rank 30 of 31, no `fail`; CH-UP-DP `VERIFIED`, `NO_RANK_LOSS_DETECTED`.",
    "A08": "STR-06: `INVALID`, `COMP-03 FAIL` implicated `SPEC-feed-n-B`, the message names `D`; "
    "no compile, no solve (spy).",
    "A09": "STA-03 before Amendment 1 (`INVALID`, `DIM-01 FAIL`) — superseded by A55–A57.",
    "A10": "STA-04 before Amendment 1 (`components_unsupported`) — superseded by A59–A60.",
    "A11": "STA-02: every B coordinate of the certified state is `+0.0`.",
    "A12": "THM-05: `reference_convention_not_reaction_consistent(SYN-001-ref-v0)`.",
    "A13": "THM-06: K02's cache tests pass unchanged.",
    "A14": "ADV-01: the contract's cycling trigger and edge 3's three λ-trials; `VERIFIED` at "
    "A02-355's root; HOM-N `ACTIVE_SET_CYCLING`.",
    "A15": "ADV-02…ADV-05 as T04 A06/A07, A14 and T03 A19.",
    "A16": "ADV-06 H: no `VERIFIED` or `RELAXED`; a typed outcome or a `FAILED`/`UNVERIFIED` "
    "certificate.",
    "A17": "ADV-06 M: `CONVERGED`, `UNVERIFIED`, `limitations` exactly "
    "`[derivative_limitation]`, every §4.1–§4.7 check `pass`.",
    "A18": "ADV-06 L: `VERIFIED`.",
    "A19": "VER-01…VER-05 as K04 §9 and §7.6; VER-02/VER-03 `INCONCLUSIVE(identity_mismatch)` "
    "through A82.",
    "A20": "No case of a kind other than `verified_at_reference` ends `VERIFIED`, except the "
    "registered sub-fixtures (STR-05's twin, ADV-06 L, VER-01's twin, VER-04's SQ-1).",
    "A21": "The draw reproduces every KAT: `k53` equal; `u`, `δ` equal to the hex known "
    "answers, `δ = (2u − 1)/5`.",
    "A22": "The selected coordinates per case follow §6.2 (pins, splits and absent components "
    "excluded), equal to the list the starts file records.",
    "A23": "Every accepted coordinate lies in its box; every joint start assembled without "
    "refusal.",
    "A24": "Absent components are `+0.0` in every start.",
    "A25": "The starts file regenerates byte-identically on `ref-x86-64` with the live "
    "provider's block; its SHA-256 equals the registry's (`3a7bd49c…`).",
    "A26": "Generation completes before any solve, and the manifest records its time and counts.",
    "A27": "440 records, one per (case, start); the classification per §7.1–§7.2 is a pure "
    "function of the record.",
    "A28": "Zero `F-CRASH`.",
    "A29": "Zero unexplained `F-OTHER-ROOT` — judged on run 2, the gate's run (§7.3 (A5)); run "
    "1's four are carried as recorded.",
    "A30": "Gate: `S ≥ 418` of 440, no `F-CRASH`, no unexplained `F-OTHER-ROOT`, on "
    "`ref-x86-64` and on `ci-aarch64` — judged on run 2 (§7.3 (A5)); run 1's FAIL stands.",
    "A31": "Per-case rates, classes, branch census, Clopper–Pearson bounds, numerical and cost "
    "reports exist and recompute from the records.",
    "A32": "At every certified ensemble state and every certificate the corpus issues, the "
    "estimate is at most the exact `‖Ĵ⁻¹‖₁` × (1 + 1e-12), and the status decided with the exact "
    "norm equals the recorded one.",
    "A33": "Every certificate in the corpus and the ensemble carries the three statements and "
    "the shared-provider qualification on exactly the prefixed checks whose result is `pass` or "
    "`fail`.",
    "A34": "Replay of the first start of every case and of every retained failure on the same "
    "machine class: `MATCH` on every field.",
    "A35": "Cross-platform per-start classification disagreements are counted and listed "
    "(reported).",
    "A36": "Every start's four wall times and counters are recorded; the ceiling is 60 s.",
    "A37": "Two screens of one matrix with arbitrary `np.random` use between them give "
    "bit-identical `rcond₁` and `b`; the global state is restored.",
    "A38": "After W3 every registered certificate's verdict, regularity status and check ids "
    "are unchanged; `rcond₁` and `b` within M5's 20-seed spread.",
    "A39": "NET-11 after W2: `VERIFIED` at the twin (S3's allowances).",
    "A40": "A constructed state where both pressure shifts leave the domain: alias certificate "
    "`unsupported(pressure_shift_outside_domain)`, `UNVERIFIED`, no exception.",
    "A41": "After W2 every registered certificate is bit-identical (the shift is up at every "
    "registered pressure column).",
    "A42": "A witness stencil point outside the domain: `derivative_witness` `unsupported`, "
    "`UNVERIFIED`, no exception.",
    "A43": "`DIM-01` and `COMP-03` pass on every registered revision; every registered "
    "revision's status unchanged.",
    "A44": "The `t02`…`t05b` identity keys and the structural hash unchanged since ADR 0017's "
    "re-baseline (which moved them by substitution only, A78–A79).",
    "A45": "The `t06` identity key is equal on x86-64 and aarch64.",
    "A46": "TRI-16/32/64 and SQ-0/1/2 unchanged after W3, as K04 §7.6.",
    "A47": "Our side of REF-01…REF-08: `VERIFIED` at the twin within §9.4's tolerance / 10.",
    "A48": "The tool environments reproduce `docs/reference-environments.md` §3's fingerprints.",
    "A49": "Every tool record carries §9.3's settings and mappings (IDAES `constr_viol_tol`, "
    "`mumps`, SmoothVLE ε = 1e-8 K; DWSIM `LegacyMode`; REF-08's guess).",
    "A50": "(a) `comparison.json` recomputes byte for byte from the committed tool and our-side "
    "records and the twin; (b) each committed `ours-*.json` equals a live solve: non-floats "
    "exact, floats to 1e-12 relative, no field exempt, no `certificate_sha256`.",
    "A51": "PC-1 (DWSIM) and PC-2 (DWSIM, IDAES) classify `DISAGREE`; (PC-1, IDAES) "
    "`not_applicable`.",
    "A52": "The tool scripts import neither `openflowsheet` nor the twin's output.",
    "A53": "V16's two counts computed from the verdicts.",
    "A54": "Every verdict carries its reason; every `NOT_COMPARABLE` names access or science.",
    "A55": "STA-03 on the legacy path, each variant: `READY_FOR_SIMULATION`, the conversion "
    "recorded, the bound flowsheet and the tear solve and certificate byte-identical to "
    "SYN-001-nominal's.",
    "A56": "STA-03 on the revision path and `verify_bound`'s read: binding, trace and "
    "certificate byte-identical to SYN-001-nominal's; the R3 control.",
    "A57": "STA-03's negative and alternate encodings: unconverted units and kinds refused "
    "typed; `mass_flow` converts as A55.",
    "A58": "`unit-conversion-v1`'s known answers — superseded by A67 (W12 replaced v1).",
    "A59": "STA-04 binds and solves byte-identically to C2 under `T05b-v2` and "
    "`T06-revision-v1`; `VERIFIED`; `validate()` `DRAFT`.",
    "A60": "All six orders of C2's components solve byte-identically to C2; malformed lists "
    "refused `components_unsupported`.",
    "A61": "Legacy permutation: SYN-001-nominal with `[C, A, B]` and `[B, A, C]` validates, "
    "binds, solves and certifies byte-identically to nominal's.",
    "A62": "§8.7: SYN-001-nominal's feed at 450, 279 and 400 K: `INITIALIZATION_FAILED`, typed "
    "message, no exception.",
    "A63": "NET-02's edge-off control under `T05b-v2` and `T05-W13`: `BOUND_BLOCKED` at "
    "iteration 1, `eo_recovery: unsupported`.",
    "A64": "NET-02 under the revision policy: `CONVERGED` through the restart, `VERIFIED`, "
    "within S3's allowances.",
    "A65": "`T06-revision-v1` differs from `T05b-v2` in exactly `policy_id` and "
    "`globalization.eo_recovery`; its hash is in the manifest and the `t06` key.",
    "A66": "Rescued starts: per case `s_first + s_rescued = s`, rescued iff `eo_recovery: "
    "taken` with the restart's provenance; both counts and both bounds reported.",
    "A67": "`unit-conversion-v2`'s known answers, bit for bit.",
    "A68": "Unit, kind and value refusals, typed through `validate()` and both bindings; no "
    "compile, no solve.",
    "A69": "Metamorphic pairs on the tear path bind to SYN-001-nominal bit for bit; the "
    "solves and certificates byte-identical; the R3 control.",
    "A70": "Metamorphic pairs on the revision path bind to their SI twins bit for bit; the "
    "exactly five differing twins; the C3 `61 %` and C1 `180 kPa` solves.",
    "A71": "A nonzero pressure drop: (a) C2 binds; (b) C2 refused at planning; (c) NET-06 "
    "solves with `S3.P = S4.P = S5.P = 97 500 Pa`.",
    "A72": "Reader rules: STR-06's diagnosis in mass units; C3's specification conflict; "
    "converted bounds.",
    "A73": "T05's refusal test after W12: eight cases, eight codes, re-pointed mutations.",
    "A74": "`DIM-01`'s message and its record order.",
    "A75": "ADR 0017: `flash` at the registered saturated states returns the single phase; "
    "D1's branch decides.",
    "A76": "ADR 0017: the seeded re-flash probe (10 000 feeds) returns only `ok`.",
    "A77": "ADR 0017: F4's registrations — C3's restart keeps eight passes; G6 converges for "
    "every cyclic case.",
    "A78": "ADR 0017 D3 (1): with the old implementation hash, every identity document is "
    "byte-identical to the pre-commit one.",
    "A79": "ADR 0017 D3 (2)–(3): with the real hash, every moved value differs only by the "
    "substitution; the new digests recorded; the CI identity job equal on x86-64 and aarch64.",
    "A80": "Start arithmetic: every recorded start coordinate equals `x_init + S·δ` recomputed "
    "bit for bit.",
    "A81": "R-015: the K03 fixture regeneration's registered difference; the K05 run-manifest "
    "fixture regenerates identically.",
    "A82": "VER-02/VER-03: a stale or mismatched identity is refused "
    "`INCONCLUSIVE(identity_mismatch)`; the certificate is `UNVERIFIED`.",
    "A83": "IDAES SmoothVLE: ε = 1e-8 K on every block; rule 2b's shift ≤ 1e-7 K; the "
    "default-ε records retained as `NOT_COMPARABLE(semantics)`.",
    "A84": "The report carries §7.4's statement verbatim and the acyclic sentence with 10 "
    "cases; `s_first/20` beside `s/20`.",
    "A85": "Step 5 at a perturbed start: (a) the premise, (b) the rule, (c) zero perturbation, "
    "(d) the regime census.",
    "A86": "`T06-revision-v2` differs from v1 in exactly `policy_id` and `globalization.eo_core`; "
    "its hash is in the manifest, the registry and the `t06` key; the schema accepts it.",
    "A87": "ADR 0018 is inert on everything registered: (a) registered traces, certificates, "
    "fixtures and the K05 identity unchanged; (b) where the rule never fires, `newton_refined` "
    "is R0-equal to `newton` with a bit-identical final state.",
    "A88": "The rule on constructed problems: fires and keeps, does not fire, a root passed in, "
    "a double root reverted, abandonments typed.",
    "A89": "THM-09 under `T06-revision-v2`, starts 1, 2, 5, 10, 6, 19: `CONVERGED`, `VERIFIED`, "
    "one refinement kept, S3's worst ratio ≤ 0.1.",
    "A90": "Run 2r's records (A5): per attempt whether the rule fired and how it ended; fired / "
    "kept / reverted / abandoned per case; on `ref-x86-64` exactly the verdicts' "
    "reconstruction (17 / 17 / 0 / 0 at the 17 listed starts, each in its last attempt).",
    "A91": "§8.8's closure: ≤ 1e-9 K at registered roots; NET-11 start 16's recorded state "
    "fails at 3.34 K; a refused `lnK` is `unsupported`; D7 precedence.",
    "A92": "§8.8's re-registrations: T05b B34 (a)'s tally with every `FAILED` beyond "
    "`100 τ_T`; B16 and B26; the one T04 fixture.",
    "A93": "Counters equal the meter; at `BUDGET_EXHAUSTED(property_calls)` exactly "
    "`max_property_calls`.",
    "A94": "A cost remedy, only if one is proposed.",
    "A95": "Run 1's record kept unedited (`dfa7d09`, `T06-revision-v1`, S = 431, gate FAIL, the "
    "four THM-09 `F-OTHER-ROOT`s); run 2, run 2r and `holdout1` separate records; every run "
    "file committed with its SHA-256 equal to the registry's and, for runs 1 and 2, the "
    "verdicts' §0.",
    "A96": "ADR 0018 D4′ at the plan level: THM-09 start 1 under `newton` and `newton_refined`, "
    "uncapped and at caps N₀, N₁ − 1 and N₁.",
    "A97": "Run records and the machine class: (a) the v2 record; (b) `machine_class()`; (c) "
    "equal counters twice in one process; (d) `refinements`; (e) the registry's "
    "`ensemble.runs`.",
    "A98": "Run 2r: (a) `src/` after run 2 changes only ADR 0018's docstring and S5's reading; "
    "(b) per class every start's class and `S` equal run 2's; (c) A90 on `ref-x86-64`; (d) "
    "replay `MATCH` on every class.",
    "A99": "The holdout: (a) its starts file; (b) committed before any holdout solve; (c) "
    "reports recompute, the holdout header, no gate line, both bounds; (d) no `F-CRASH`. "
    "Reported, never gated.",
    "A100": "Integers without a binary64 reading (`2⁵³ + 1`, `10⁴⁰⁰`) get the result `±∞` "
    "gets on every path and field; `2⁵³` gets `2.0**53`'s.",
}

#: Assertions no measurement applies to, with why (the spec's own words where it gives them).
NOT_APPLICABLE: dict[str, str] = {
    "A09": "superseded by Amendment 1: STA-03 is a solved case; A55–A57 carry it (T06 spec "
    "§13, A09's row)",
    "A10": "superseded by Amendment 1: STA-04 is a solved case; A59–A60 carry it (T06 spec "
    "§13, A10's row)",
    "A58": "superseded by A67 when W12 replaced `unit-conversion-v1` with `unit-conversion-v2` "
    "(T06 spec §13, A58's row; ADR 0016); v1's known answers are A67's "
    "`v1_known_answers_under_v2`",
    "A94": "no cost remedy was proposed for adoption: W21's attribution landed none and left its "
    "one candidate (an exact `lnK` memo scoped to a band route, saving not measured) to the "
    "design lane (`docs/t06-measurements.md`, W21), so the three `F-BUDGET` starts stay "
    "`F-BUDGET` in run 2 and run 2r (spec §6.6 (A4), Q23); the row applies only if one is "
    "proposed",
}


# ----------------------------------------------------------------------------- the gate's tests

_K03_FIXTURES = "tests/test_k03_schemas.py::test_the_fixtures_are_what_the_code_emits_today"
_K04_FIXTURES = "tests/test_k04_schemas.py::test_a31_the_fixtures_are_what_the_verifier_emits_today"
_T04_FIXTURES = "tests/test_t04_schemas.py::test_a26_the_t04_fixtures_are_what_the_code_emits_today"
_K05_FIXTURES = "tests/test_k05_schemas.py::test_the_fixtures_are_what_a_real_run_emits_today"
_K05_MANIFEST = (
    "tests/test_k05_schemas.py::test_the_manifest_fixtures_certificate_hash_is_the_emitted_one"
)
_K04_REGULARITY = "tests/test_k04_regularity.py::"
_B34 = "tests/test_t05b_candidate_answers.py::"
_IDENTITY = "tests/test_t06_identity.py::"

#: The tests that carry an assertion where neither its number in a test's name nor a corpus row
#: names them (see the module note). Each is a function-level node id; every parametrization runs.
EXTRA_TESTS: dict[str, tuple[str, ...]] = {
    "A28": (
        "tests/test_t06_w6_ensemble.py::"
        "test_a_run_restores_every_entry_point_and_records_a_crash_rather_than_raising",
    ),
    "A30": ("tests/test_t06_w29_runs.py::test_a97e_each_headline_recomputes_from_its_records",),
    "A41": (_K03_FIXTURES, _K04_FIXTURES, _T04_FIXTURES),
    "A43": (
        "tests/test_t06_w1a_units.py::test_str06_component_references_are_checked",
        "tests/test_t06_w1a_units.py::test_comp03_reads_component_keyed_parameter_names",
    ),
    "A44": (_K03_FIXTURES, _K04_FIXTURES, _T04_FIXTURES, _K05_FIXTURES),
    "A45": (
        _IDENTITY + "test_the_key_carries_the_registered_records",
        _IDENTITY + "test_the_ensemble_definition_is_the_registered_one",
        _IDENTITY + "test_the_key_is_floats_free_and_deterministic",
    ),
    "A46": (
        _K04_REGULARITY + "test_a23_one_construction_three_statuses_and_a_useless_u_diagonal",
        _K04_REGULARITY + "test_a24_an_exactly_singular_matrix_is_rank_deficient_not_a_crash",
        _K04_REGULARITY + "test_a25_the_bound_is_recorded_and_the_verdict_is_verified",
        _K04_REGULARITY + "test_a34_a_tolerance_tight_enough_trips_the_absolute_limit",
    ),
    "A65": (
        "tests/test_t06_f4_policy.py::"
        "test_wo6_the_revision_policy_differs_from_t05b_v2_in_exactly_two_fields",
        "tests/test_t06_f4_policy.py::"
        "test_wo6_the_revision_policy_document_is_schema_valid_and_differs_in_two_values",
        "tests/test_t06_w4_registry.py::test_every_registered_policy_is_the_constructed_one",
    ),
    "A77": (
        "tests/test_t06_f4_restart.py::test_wo3_c3_keeps_all_eight_passes",
        "tests/test_t06_f4_g6.py::test_g6_the_cyclic_registered_cases_are_the_listed_ones",
        "tests/test_t06_f4_g6.py::test_g6_the_restart_start_converges_to_the_registered_root",
    ),
    "A79": (_K03_FIXTURES, _K04_FIXTURES, _T04_FIXTURES, _K05_FIXTURES, _K05_MANIFEST),
    "A81": (
        _K03_FIXTURES,
        "tests/test_k03_schemas.py::test_the_property_counters_are_measurably_not_reproducible",
        _K05_FIXTURES,
        _K05_MANIFEST,
    ),
    "A87": (
        "tests/test_t06_w18_refinement.py::test_refinement_none_is_k03_newton",
        "tests/test_t06_w18_literal.py::test_w18_no_committed_fixture_names_the_new_value",
        "tests/test_t06_w18_literal.py::test_w18_the_default_is_unchanged",
        _K03_FIXTURES,
        _K04_FIXTURES,
        _T04_FIXTURES,
        _K05_FIXTURES,
    ),
    "A92": (
        _B34 + "test_a92_the_floor_is_a_decade_beyond_the_near_threshold_band",
        _B34 + "test_b34a_the_certificate_tally",
        _B34 + "test_b34a_the_outcome_counts",
        _B34 + "test_b34a_both_declaration_orders_agree_on_the_certificate",
        "tests/test_t05b_zero_flow.py::test_b16_dz3_verified",
        "tests/test_t05b_zero_flow.py::test_b16_dz3_what_the_fresh_flash_reads_at_newtons_stop",
        "tests/test_t05b_dormancy.py::test_b26_dz10_verified",
        "tests/test_t05b_dormancy.py::test_b26_dz10_what_the_fresh_flash_reads_at_newtons_stop",
        _T04_FIXTURES,
    ),
}

#: An assertion number in a T06 test's name: `test_a97e_…`, `test_a99c_a31_…`, `test_a88_b_…`.
_NAMED = re.compile(r"(?:^|_)a(\d{2,3})[a-z]*(?=_|$)")


def _function(nodeid: str) -> str:
    return nodeid.split("[", 1)[0]


def _named(function: str) -> list[str]:
    """The assertions a T06 test names; none for another package's test (its numbers are its
    own catalogue's)."""
    path, _, name = function.partition("::")
    if not Path(path).name.startswith("test_t06_"):
        return []
    return [f"A{int(number):02d}" for number in _NAMED.findall(name.removeprefix("test"))]


def _corpus_tests() -> dict[str, set[str]]:
    """A02…A20, A39, A55–A60, A63, A64: the corpus rows that name each assertion (the registry's
    `corpus[].assertion`, controls included) and the tests W5's `MEASURED_BY` names for them."""
    by: dict[str, set[str]] = {}
    for case in w4_registry.CASES:
        named = [case["assertion"], *(c["assertion"] for c in case.get("controls", ()))]
        for text in named:
            for assertion in (part.strip() for part in text.split(",")):
                identifier = "A" + assertion.removeprefix("T6-A")
                by.setdefault(identifier, set()).update(w5_corpus.MEASURED_BY[case["id"]])
    return by


class _Recorder:
    """A pytest plugin: every node's outcome (`passed`, `failed`, `skipped`, `xfailed`,
    `xpassed`), the worst over setup, call and teardown; a collection error is a failure."""

    RANK: Mapping[str, int] = {"passed": 0, "xfailed": 1, "skipped": 2, "xpassed": 3, "failed": 4}

    def __init__(self) -> None:
        self.outcomes: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: Any) -> None:
        if hasattr(report, "wasxfail"):
            outcome = "xfailed" if report.skipped else "xpassed"
        else:
            outcome = str(report.outcome)
        previous = self.outcomes.get(report.nodeid, "passed")
        if self.RANK[outcome] >= self.RANK[previous]:
            self.outcomes[report.nodeid] = outcome

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.outcomes[report.nodeid or "collection"] = "failed"


@dataclass
class GateTests:
    """The gate's tests as this process ran them, and the tests each assertion names."""

    outcomes: dict[str, str]
    exit_code: int
    by_assertion: dict[str, set[str]] = field(default_factory=dict)

    def summary(self, identifier: str) -> tuple[str | None, dict[str, Any]]:
        """`fail` if a node failed or xpassed, or a named test ran no node (the map rotted);
        `unsupported` if a node was skipped; `None` when the assertion names no test."""
        functions = sorted(self.by_assertion.get(identifier, ()))
        if not functions:
            return None, {"functions": []}
        nodes = {
            nodeid: outcome
            for nodeid, outcome in self.outcomes.items()
            if _function(nodeid) in functions
        }
        ran = {_function(nodeid) for nodeid in nodes}
        missing = [function for function in functions if function not in ran]
        failed = sorted(n for n, o in nodes.items() if o in ("failed", "xpassed"))
        skipped = sorted(n for n, o in nodes.items() if o == "skipped")
        value = {
            "functions": functions,
            "nodes": len(nodes),
            "outcomes": dict(sorted(Counter(nodes.values()).items())),
            "failed": failed,
            "skipped": skipped,
            "missing": missing,
        }
        if failed or missing:
            return "fail", value
        if skipped:
            return "unsupported", value
        return "pass", value


def run_gate_tests() -> GateTests:
    """Run every T06 test module and every other test an assertion names, once, here."""
    corpus = _corpus_tests()
    named = {name for names in [*corpus.values(), *EXTRA_TESTS.values()] for name in names}
    outside = sorted(n for n in named if not Path(n.split("::")[0]).name.startswith("test_t06_"))
    t06 = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("test_t06_*.py"))
    recorder = _Recorder()
    with contextlib.chdir(ROOT):
        exit_code = int(
            pytest.main(["-q", "-p", "no:cacheprovider", *t06, *outside], plugins=[recorder])
        )
    tests = GateTests(recorder.outcomes, exit_code)
    for nodeid in recorder.outcomes:
        for identifier in _named(_function(nodeid)):
            tests.by_assertion.setdefault(identifier, set()).add(_function(nodeid))
    for identifier, names in [*corpus.items(), *EXTRA_TESTS.items()]:
        tests.by_assertion.setdefault(identifier, set()).update(names)
    return tests


# ----------------------------------------------------------------------------- committed records

#: A measurement returns `(ok, value)`: `ok` decides `pass`/`fail` together with the tests, or is
#: one of `unsupported`/`not_applicable` with its reason in `value`.
Measured = tuple[bool | str, dict[str, Any]]


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=ROOT, check=False
    )
    return completed.returncode == 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Run:
    """One committed run file and its registry entry (`ensemble.runs`)."""

    entry: Mapping[str, Any]
    document: Mapping[str, Any]

    @property
    def run_id(self) -> str:
        return str(self.entry["run_id"])

    @property
    def machine_class(self) -> str:
        return str(self.entry["machine_class"])

    @property
    def label(self) -> str:
        return f"{self.run_id}@{self.machine_class}"

    @property
    def path(self) -> Path:
        return ROOT / str(self.entry["file"])

    @property
    def records(self) -> Sequence[Mapping[str, Any]]:
        records: Sequence[Mapping[str, Any]] = self.document["records"]
        return records


@cache
def runs() -> tuple[Run, ...]:
    return tuple(
        Run(entry, json.loads((ROOT / entry["file"]).read_bytes())) for entry in ENSEMBLE["runs"]
    )


def run(run_id: str, machine: str) -> Run:
    (found,) = [r for r in runs() if (r.run_id, r.machine_class) == (run_id, machine)]
    return found


@cache
def _published(starts_file: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((ROOT / starts_file).read_bytes())
    return document


@cache
def summary(run_id: str, machine: str) -> dict[str, Any]:
    """The harness's `report` (§7.3–§7.4) recomputed from the committed records."""
    found = run(run_id, machine)
    published = _published(str(found.document["starts_file"]))
    result: dict[str, Any] = ensemble.report(found.records, found.document["cases"], published)
    return result


def _classes(found: Run) -> dict[tuple[str, int], str]:
    return {(r["case"], int(r["start"])): ensemble.classify(r) for r in found.records}


def _listed(found: Run, name: str) -> list[str]:
    return [f"{case}/{start:02d}" for (case, start), c in _classes(found).items() if c == name]


def _sums() -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in (RUNS_DIR / "SHA256SUMS").read_text("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    return sums


def _stem(found: Run) -> str:
    return found.path.stem


def _headline(found: Run) -> dict[str, Any]:
    s = summary(found.run_id, found.machine_class)
    return {
        "S": s["S"],
        "S_first": s["S_first"],
        "S_rescued": s["S_rescued"],
        "N": s["N"],
        "classes": s["classes"],
        "cp_lower": s["cp_lower"],
        "cp_lower_first": s["cp_lower_first"],
        "gate_rule_applied": "PASS" if s["gate"]["pass"] else "FAIL",
    }


# -- A25, A26: the starts files -----------------------------------------------------------------


def _m_a25() -> Measured:
    nominal, holdout = _sha256(STARTS_FILE), _sha256(HOLDOUT_FILE)
    value = {
        "starts_sha256": nominal,
        "registry_starts_sha256": ENSEMBLE["starts_sha256"],
        "holdout_sha256": holdout,
        "registry_holdout_sha256": ENSEMBLE["holdout"]["starts_sha256"],
    }
    return nominal == ENSEMBLE["starts_sha256"] and holdout == value[
        "registry_holdout_sha256"
    ], value


def _file_history(path: Path) -> list[tuple[str, str]]:
    """Every commit that changed the file, oldest first: `(sha, committer date)`."""
    lines = _git("log", "--format=%H %cI", "--", str(path.relative_to(ROOT))).splitlines()
    return [tuple(line.split(" ", 1)) for line in reversed(lines)]  # type: ignore[misc]


def _m_a26() -> Measured:
    """Generation completes before any solve: the last commit that wrote each starts file is an
    ancestor of every run record's commit that scored it; the generation counts are the file's."""
    value: dict[str, Any] = {}
    ok = True
    for name, path, run_ids in (
        ("nominal", STARTS_FILE, ("run1", "run2", "run2r")),
        ("holdout1", HOLDOUT_FILE, (ensemble.HOLDOUT_RUN_ID,)),
    ):
        history = _file_history(path)
        written = history[-1][0]
        scored = sorted({str(r.entry["commit"]) for r in runs() if r.run_id in run_ids})
        before = {
            commit: _is_ancestor(written, commit) and written != _git("rev-parse", commit).strip()
            for commit in scored
        }
        counts = _published(str(path.relative_to(ROOT)))["counts"]
        ok = ok and all(before.values()) and counts["starts_accepted"] == ensemble.N
        ok = ok and counts["generation_failures"] == 0
        value[name] = {
            "file": str(path.relative_to(ROOT)),
            "written_by": [{"commit": sha, "committed_at": date} for sha, date in history],
            "precedes_every_scoring_commit": before,
            "counts": counts,
        }
    return ok, value


# -- A27–A36, A66, A84: the ensemble's records ---------------------------------------------------


def _m_a27() -> Measured:
    value: dict[str, Any] = {}
    ok = True
    for found in runs():
        published = _published(str(found.document["starts_file"]))
        expected = sorted(
            (entry["case"], int(start["start"]))
            for entry in published["cases"]
            for start in entry["starts"]
        )
        keys = [(r["case"], int(r["start"])) for r in found.records]
        pure = all(
            ensemble.classify(r) == ensemble.classify(json.loads(json.dumps(r)))
            for r in found.records
        )
        mine = len(keys) == ensemble.N and sorted(keys) == expected and pure
        ok = ok and mine
        value[found.label] = {"records": len(keys), "distinct": len(set(keys)), "pure": pure}
    return ok, value


def _m_a28() -> Measured:
    crashes = {found.label: _listed(found, "F-CRASH") for found in runs()}
    return all(not listed for listed in crashes.values()), {"F-CRASH": crashes}


def _m_a29() -> Measured:
    """§7.3 (A5): the gate's run is run 2; run 1's four are carried as recorded, not re-judged."""
    other = {found.label: _listed(found, "F-OTHER-ROOT") for found in runs()}
    run1 = run("run1", "ref-x86-64")
    worst = {
        f"{r['case']}/{int(r['start']):02d}": r["worst"]
        for r in run1.records
        if ensemble.classify(r) == "F-OTHER-ROOT"
    }
    judged = [label for label in other if label.startswith("run2@")]
    value = {
        "judged_on": judged,
        "F-OTHER-ROOT": other,
        "run1_worst_s3_ratio": worst,
        "run1_diagnosis": "spec Amendment 4: the registered root stopped inside THM-09's "
        "row-tolerance window (1.005–3.447 allowances), not a second root; not explained under "
        "§7.2, so run 1's gate term fails and stands (R-087)",
    }
    return all(not other[label] for label in judged), value


def _m_a30() -> Measured:
    value: dict[str, Any] = {}
    for found in runs():
        value[found.label] = {**_headline(found), "commit": found.entry["commit"]}
        if found.entry.get("ci_run") is not None:
            value[found.label]["ci_run"] = found.entry["ci_run"]
    judged = {machine: value[f"run2@{machine}"]["gate_rule_applied"] for machine in GATE_CLASSES}
    value["gate"] = {
        "judged_on": "run 2 (spec §7.3 (A5)); run 2r is a reproduction and holdout1 is never "
        "gated, so neither is a gate result",
        "S_min": ensemble.S_MIN,
        "classes": judged,
        "run1": "FAIL (S = 431 clears 418; four unexplained F-OTHER-ROOT fail the gate term); "
        "the record stands (R-087)",
    }
    return all(verdict == "PASS" for verdict in judged.values()), value


def _render(found: Run) -> str:
    text: str = HARNESS.render(found.document)[0]
    return text


def _m_a31() -> Measured:
    """Every committed report recomputes byte for byte from its run file; the judged run 2 text
    is `report`'s standard output with W28's A90 line appended since."""
    value: dict[str, Any] = {}
    ok = True
    for found in runs():
        if found.run_id not in ("run2r", ensemble.HOLDOUT_RUN_ID):
            continue
        report = RUNS_DIR / f"{_stem(found)}.report.txt"
        equal = report.read_text("utf-8") == _render(found)
        ok = ok and equal
        value[str(report.relative_to(ROOT))] = {"recomputes_byte_for_byte": equal}
    (judged,) = [t for t in ENSEMBLE["judged_texts"] if t["file"].endswith(".report.txt")]
    run2 = run("run2", "ref-x86-64")
    appended = "\nRefinements (ADR 0018; A90 (A5)): not recorded.\n"
    text = _render(run2)
    equal = text.endswith(appended) and (ROOT / judged["file"]).read_text("utf-8") == (
        text.removesuffix(appended) + "\n"
    )
    ok = ok and equal
    value[judged["file"]] = {"recomputes_byte_for_byte": equal, "a90_line_appended_since": True}
    for found in runs():
        s = summary(found.run_id, found.machine_class)
        cases = s["per_case"]
        consistent = sum(c["s"] for c in cases.values()) == s["S"] and len(cases) == 22
        ok = ok and consistent and s["all_cases"]
        value.setdefault("per_case_sums", {})[found.label] = consistent
    return ok, value


def _m_a32() -> Measured:
    value = {found.label: summary(found.run_id, found.machine_class)["a32"] for found in runs()}
    ok = all(v["not_lower"] == 0 and v["disagreements"] == 0 for v in value.values())
    return ok, value


def _m_a33() -> Measured:
    """Judged on the records written under A33 as amended (A4): runs 2, 2r and the holdout.
    Run 1's records predate A4's wording (137 failures, all `not_applicable` entries)."""
    failures = {
        found.label: summary(found.run_id, found.machine_class)["a33_failures"] for found in runs()
    }
    judged = {label: n for label, n in failures.items() if not label.startswith("run1@")}
    return all(n == 0 for n in judged.values()), {"a33_failures": failures}


def _replayed(text: str) -> tuple[list[tuple[str, int]], set[str], int]:
    """The replay's verdict lines `CASE  NN MATCH|DIFFER`, their words, and how many other lines
    the text holds (the judged run-2 text interleaves stderr: tracebacks the kernel printed for
    evaluation failures the solver caught and typed; a `DIFFER` never hides among them)."""
    lines = text.splitlines()
    matches = [re.fullmatch(r"(\S+)\s+(\d{2}) (MATCH|DIFFER)", line) for line in lines]
    found = [m for m in matches if m is not None]
    other = sum(1 for line in lines if "MATCH" not in line and "DIFFER" not in line)
    stray = len(lines) - len(found) - other
    words = {m[3] for m in found} | ({"a MATCH or DIFFER outside the format"} if stray else set())
    return [(m[1], int(m[2])) for m in found], words, other


def _replay_expected(found: Run) -> list[tuple[str, int]]:
    first: dict[str, int] = {}
    for record in found.records:
        first.setdefault(record["case"], int(record["start"]))
    return [
        (r["case"], int(r["start"]))
        for r in found.records
        if int(r["start"]) == first[r["case"]] or ensemble.classify(r) != "SUCCESS"
    ]


def _m_a34() -> Measured:
    value: dict[str, Any] = {}
    ok = True
    texts = [
        (run("run2", "ref-x86-64"), ROOT / t["file"])
        for t in ENSEMBLE["judged_texts"]
        if t["file"].endswith(".replay.txt")
    ]
    texts += [
        (found, RUNS_DIR / f"{_stem(found)}.replay.txt")
        for found in runs()
        if found.run_id in ("run2r", ensemble.HOLDOUT_RUN_ID)
    ]
    for found, path in texts:
        replayed, words, other = _replayed(path.read_text("utf-8"))
        covers = replayed == _replay_expected(found)
        ok = ok and covers and words == {"MATCH"}
        value[str(path.relative_to(ROOT))] = {
            "replayed": len(replayed),
            "all_match": words == {"MATCH"},
            "first_starts_and_failures": covers,
            "other_lines": other,
        }
    return ok, value


def _disagreements(left: Run, right: Run) -> dict[str, Any]:
    mine, theirs = _classes(left), _classes(right)
    bits = {
        (r["case"], int(r["start"])): [(n, float(v).hex()) for n, v in r.get("state") or []]
        for r in left.records
    }
    other = {
        (r["case"], int(r["start"])): [(n, float(v).hex()) for n, v in r.get("state") or []]
        for r in right.records
    }
    rescued_l = {(r["case"], int(r["start"])): ensemble.rescued(r) for r in left.records}
    rescued_r = {(r["case"], int(r["start"])): ensemble.rescued(r) for r in right.records}
    return {
        "classification": [
            f"{case} {start:02d}: {mine[(case, start)]} vs {theirs[(case, start)]}"
            for case, start in sorted(mine)
            if mine[(case, start)] != theirs.get((case, start))
        ],
        "rescue_status": [
            f"{case} {start:02d}"
            for case, start in sorted(mine)
            if mine[(case, start)] == theirs.get((case, start)) == "SUCCESS"
            and rescued_l[(case, start)] != rescued_r[(case, start)]
        ],
        "final_states_differing_bitwise": sum(
            1 for key in bits if bits[key] and other.get(key) and bits[key] != other[key]
        ),
    }


def _m_a35() -> Measured:
    """Counted and listed — reported, not promised. The committed comparisons recompute."""
    value: dict[str, Any] = {}
    ok = True
    for run_id in ("run2", "run2r", ensemble.HOLDOUT_RUN_ID):
        found = [run(run_id, machine) for machine in CLASSES]
        for i, left in enumerate(found):
            for right in found[i + 1 :]:
                value[f"{left.label} vs {right.label}"] = _disagreements(left, right)
        if run_id == "run2":
            continue
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            HARNESS.compare(argparse.Namespace(results=[str(f.path) for f in found]))
        committed = (RUNS_DIR / f"{run_id}.compare.txt").read_text("utf-8")
        ok = ok and buffer.getvalue() == committed
        value[f"{run_id}.compare.txt recomputes"] = buffer.getvalue() == committed
    return ok, value


TIMES = ("compile", "init", "solve", "verify", "total")
COUNTERS = (
    "cache_hits",
    "factorizations",
    "jacobian_calls",
    "property_calls",
    "requested_evaluations",
    "residual_calls",
)


def _m_a36() -> Measured:
    value: dict[str, Any] = {}
    ok = True
    for found in runs():
        recorded = all(
            set(TIMES) <= set(r["times"])
            and (r["generation_failure"] is not None or set(COUNTERS) <= set(r["counters"] or {}))
            for r in found.records
        )
        longest = max(float(r["times"]["total"]) for r in found.records)
        ok = ok and recorded and longest <= ensemble.CEILING_S
        value[found.label] = {"recorded": recorded, "max_total_s": longest}
    value["ceiling_s"] = ensemble.CEILING_S
    return ok, value


#: A66: the restart's initializer, as the spec names it (`initializer_source`).
RESTART_INITIALIZER = "traversal-G0-pass8-v1"


def _m_a66() -> Measured:
    """Per case `s_first + s_rescued = s`; `rescued` recounted from the records by the spec's
    rule, independently of the harness's function, and the two counts compared."""
    value: dict[str, Any] = {}
    ok = True
    for found in runs():
        s = summary(found.run_id, found.machine_class)
        recount = sum(
            1
            for r in found.records
            if ensemble.classify(r) == "SUCCESS"
            and r.get("eo_recovery") == "taken"
            and RESTART_INITIALIZER in (r.get("sources") or [])
        )
        sums = all(c["s_first"] + c["s_rescued"] == c["s"] for c in s["per_case"].values())
        ok = ok and sums and recount == s["S_rescued"]
        value[found.label] = {"S_rescued": s["S_rescued"], "recounted": recount, "sums": sums}
    return ok, value


#: A84 (A3): the ten acyclic cases, as the row lists them (the registry's `ensemble.cases` order).
A84_ACYCLIC = (
    "STR-01",
    "STA-01",
    "STA-05",
    "NUM-03",
    "THM-01",
    "THM-02",
    "THM-07",
    "THM-08",
    "THM-09",
    "THM-10",
)


def _m_a84() -> Measured:
    """Every committed report carries §7.4's statements verbatim and the acyclic sentence with
    the row's ten cases, and no finding against the text."""
    sentence = ensemble.ACYCLIC_STATEMENT.format(n=len(A84_ACYCLIC), ids=", ".join(A84_ACYCLIC))
    value: dict[str, Any] = {"acyclic": list(A84_ACYCLIC)}
    ok = True
    reports = [RUNS_DIR / f"{_stem(f)}.report.txt" for f in runs() if f.run_id != "run1"]
    reports = [path for path in reports if path.exists()]
    reports += [ROOT / t["file"] for t in ENSEMBLE["judged_texts"] if "report" in t["file"]]
    for path in reports:
        text = path.read_text("utf-8")
        carried = (
            ensemble.RESCUE_STATEMENT in text
            and sentence in text
            and ensemble.DESIGNS_STATEMENT in text
            and "finding against the text" not in text
            and "s_c^first/20" in text
        )
        ok = ok and carried
        value[str(path.relative_to(ROOT))] = carried
    return ok, value


# -- A90, A95, A98, A99: run 1's record, run 2r and the holdout ---------------------------------


def _m_a90() -> Measured:
    """Met on run 2r's records (A5), not on run 2's, which carry none. On `ref-x86-64` the
    refinements are exactly the verdicts' §2.4 reconstruction (the harness's
    `A90_EXPECTED_REF_X86_64`, checked against the spec's list by the gate's test)."""
    value: dict[str, Any] = {}
    ok = True
    for machine in CLASSES:
        rerun = run("run2r", machine)
        counted = summary("run2r", machine)["refinements"]
        fired = sorted(f"{case}/{start:02d}" for case, start, *_ in counted["fired_at"])
        entry: dict[str, Any] = {
            key: counted[key]
            for key in ("fired", "kept", "reverted", "abandoned", "abandoned_budget")
        }
        entry["abandoned_by_reason"] = counted["abandoned_by_reason"]
        entry["fired_at"] = fired
        entry["not_last"] = counted["not_last"]
        entry["worst_s3_ratio"] = counted["worst_ratio"]
        entry["F-OTHER-ROOT"] = _listed(rerun, "F-OTHER-ROOT")
        if machine == ensemble.REFERENCE_CLASS:
            expected = sorted(
                f"{case}/{start:02d}" for case, start in ensemble.A90_EXPECTED_REF_X86_64
            )
            found = ensemble.a98_discrepancies(
                rerun.document, run("run2", machine).document, ensemble.A90_EXPECTED_REF_X86_64
            )
            refinement_problems = [p for p in found["discrepancies"] if "A90" in p]
            entry["expected_fired_at"] = expected
            entry["discrepancies"] = refinement_problems
            ok = ok and fired == expected and not refinement_problems
            ok = ok and (counted["kept"], counted["reverted"], counted["abandoned"]) == (
                len(expected),
                0,
                0,
            )
        value[f"run2r@{machine}"] = entry
    thm09 = [
        r for r in run("run2r", "ci-aarch64").records if (r["case"], r["start"]) == ("THM-09", 3)
    ]
    value["verdicts_open_question"] = {
        "THM-09/03 on ci-aarch64": {
            "class": ensemble.classify(thm09[0]),
            "refinements": thm09[0]["refinements"],
        }
    }
    value["run2"] = "not recorded: run 2's v1 records carry no refinement record (A90 (A5))"
    return ok, value


def _verdict_hashes() -> set[str]:
    text = VERDICTS.read_text("utf-8")
    section = text.split("## 0.", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"`([0-9a-f]{64})`", section))


def _m_a95() -> Measured:
    sums = _sums()
    files: dict[str, Any] = {}
    ok = True
    for found in runs():
        name = str(found.path.relative_to(RUNS_DIR))
        digest = _sha256(found.path)
        equal = digest == found.entry["sha256"] == sums.get(name)
        ok = ok and equal
        files[name] = {"sha256": digest, "registry_and_sha256sums_equal": equal}
    judged = {r.entry["sha256"] for r in runs() if r.run_id in ("run1", "run2")}
    in_verdicts = judged <= _verdict_hashes() and len(judged) == 4
    run1 = run("run1", "ref-x86-64")
    record = {
        "commit": run1.entry["commit"],
        "policies": sorted(run1.document["policies"]),
        **_headline(run1),
        "F-OTHER-ROOT": _listed(run1, "F-OTHER-ROOT"),
        "diagnosis": "spec Amendment 4 (A4.3): the registered root inside the certificate's own "
        "`b`, not a false verification and not explained under §7.2; NET-11/16 was a missed "
        "false success (verdicts §3.4)",
    }
    ok = ok and in_verdicts and record["gate_rule_applied"] == "FAIL" and record["S"] == 431
    ok = ok and record["policies"] == ["SYN-001-K03", "T04-W12", "T06-revision-v1"]
    ok = ok and all(case.startswith("THM-09/") for case in record["F-OTHER-ROOT"])
    ok = ok and len(record["F-OTHER-ROOT"]) == 4
    records = sorted({r.run_id for r in runs()})
    value = {
        "files": files,
        "runs_1_and_2_are_the_verdicts_section_0_bytes": in_verdicts,
        "run1": record,
        "separate_records": records,
        "gate_verdict": "run 2's (spec §7.3 (A5))",
    }
    return ok and records == ["holdout1", "run1", "run2", "run2r"], value


#: Run 2's commit (the registry's run 2 entries), from which A98 (a) measures `src/`.
RUN2_COMMIT = "f636452"
#: A98 (b): the row's numbers.
A98_S = 434
A98_S_FIRST = {"ref-x86-64": 370, "ci-x86-64": 370, "ci-aarch64": 367}


def _closing_commit() -> str:
    commit: str = run("run2r", "ref-x86-64").document["commit"]
    return commit


def _m_a98() -> Measured:
    closing = _closing_commit()
    changed = sorted(_git("diff", "--name-only", RUN2_COMMIT, closing, "--", "src/").split())
    commits = _git(
        "log", "--no-merges", "--format=%h %s", f"{RUN2_COMMIT}..{closing}", "--", "src/"
    ).splitlines()
    work_orders = sorted(line.split(" ", 1)[1].split(":", 1)[0] for line in commits)
    value: dict[str, Any] = {
        "a": {
            "diff": f"git diff {RUN2_COMMIT} {closing} -- src/",
            "files": changed,
            "commits": commits,
            "work_orders": work_orders,
        }
    }
    ok = work_orders == ["T06 W24", "T06 W25"]
    for machine in CLASSES:
        expected = ensemble.A90_EXPECTED_REF_X86_64 if machine == ensemble.REFERENCE_CLASS else None
        found = ensemble.a98_discrepancies(
            run("run2r", machine).document, run("run2", machine).document, expected
        )
        mine = (
            not found["discrepancies"]
            and found["S"] == [A98_S, A98_S]
            and found["S_first"] == [A98_S_FIRST[machine]] * 2
            and found["starts"] == ensemble.N
        )
        ok = ok and mine
        value[machine] = {
            "discrepancies": found["discrepancies"],
            "S": found["S"],
            "S_first": found["S_first"],
            "final_states_differing_bitwise_reported": len(found["state_bitwise_differences"]),
            "refinements": found["refinements"],
            "cpu_model": run("run2r", machine).document["host"].get("cpu_model"),
        }
        text = (RUNS_DIR / f"{_stem(run('run2r', machine))}.a98.txt").read_text("utf-8")
        ok = ok and text.rstrip("\n").endswith("\n0 discrepancies")
    replays = _m_a34()[1]
    value["d"] = {k: v for k, v in replays.items() if "run2r" in k}
    ok = ok and all(v["all_match"] and v["first_starts_and_failures"] for v in value["d"].values())
    return ok, value


def _m_a99() -> Measured:
    relative = str(HOLDOUT_FILE.relative_to(ROOT))
    (added,) = _git("log", "--diff-filter=A", "--format=%H", "--", relative).split()
    at_addition = _git(
        "ls-tree", "-r", "--name-only", added, "--", str(RUNS_DIR.relative_to(ROOT))
    ).split()
    value: dict[str, Any] = {
        "a": {
            "starts_sha256": _sha256(HOLDOUT_FILE),
            "registry": ENSEMBLE["holdout"]["starts_sha256"],
        },
        "b": {
            "starts_committed_at": added,
            "holdout_run_files_at_that_commit": [n for n in at_addition if "holdout" in n],
        },
    }
    ok = value["a"]["starts_sha256"] == value["a"]["registry"]
    ok = ok and not value["b"]["holdout_run_files_at_that_commit"]
    for machine in CLASSES:
        found = run(ensemble.HOLDOUT_RUN_ID, machine)
        s = summary(found.run_id, machine)
        ancestor = _is_ancestor(added, str(found.document["commit"]))
        text = (RUNS_DIR / f"{_stem(found)}.report.txt").read_text("utf-8")
        lines = text.splitlines()
        header = lines[0] == "# " + ensemble.HOLDOUT_HEADER.format(run_id=found.run_id)
        no_gate = not any(re.search(r"\bgate S >=", line) for line in lines)
        s_run2 = int(run("run2", machine).entry["S"])
        crashes = _listed(found, "F-CRASH")
        ok = ok and ancestor and header and no_gate and text == _render(found) and not crashes
        value[machine] = {
            "commit_descends_from_the_starts_commit": ancestor,
            "S": s["S"],
            "S_first": s["S_first"],
            "S_rescued": s["S_rescued"],
            "cp_lower": s["cp_lower"],
            "cp_lower_first": s["cp_lower_first"],
            "S_holdout_minus_S_run2": s["S"] - s_run2,
            "classes": s["classes"],
            "F-CRASH": crashes,
            "F-OTHER-ROOT": _listed(found, "F-OTHER-ROOT"),
            "refinements": {
                key: s["refinements"][key] for key in ("fired", "kept", "reverted", "abandoned")
            },
            "report_recomputes": text == _render(found),
            "holdout_header": header,
            "no_gate_line": no_gate,
        }
    compare = _m_a35()[1]
    value["c_compare"] = {k: v for k, v in compare.items() if "holdout1" in k}
    ok = ok and bool(value["c_compare"].get("holdout1.compare.txt recomputes"))
    value["gated"] = False
    return ok, value


# -- A47, A51, A53, A54: the reference comparison ------------------------------------------------


@cache
def _comparison() -> dict[str, Any]:
    document: dict[str, Any] = json.loads((REFERENCES / "comparison.json").read_bytes())
    return document


def _m_a47() -> Measured:
    """Our side within §9.4's tolerance / 10 of the twin, from each row's `ours_vs_twin_ratio`
    (the ratio to the tolerance; the gate's test solves live)."""
    worst: dict[str, float] = {}
    for row in _comparison()["rows"]:
        if not row["fixture"].startswith("REF-"):
            continue
        for quantity in row.get("quantities", []):
            ratio = float(quantity["ours_vs_twin_ratio"])
            worst[row["fixture"]] = max(worst.get(row["fixture"], 0.0), ratio)
    return len(worst) == 8 and all(r <= 0.1 for r in worst.values()), {
        "worst_ours_vs_twin_ratio": worst
    }


def _m_a51() -> Measured:
    rows = {(r["fixture"], r["tool"]): r["classification"] for r in _comparison()["rows"]}
    controls = {f"{f}/{t}": c for (f, t), c in rows.items() if f.startswith("PC-")}
    expected = {
        "PC-1/DWSIM": "DISAGREE",
        "PC-1/IDAES": "not_applicable",
        "PC-2/DWSIM": "DISAGREE",
        "PC-2/IDAES": "DISAGREE",
    }
    return controls == expected, {"classifications": controls}


def _m_a53() -> Measured:
    agree: dict[str, set[str]] = {}
    for row in _comparison()["rows"]:
        if row["fixture"].startswith("REF-") and row["classification"] == "AGREE":
            agree.setdefault(row["fixture"], set()).add(row["tool"])
    at_least_one = sorted(agree)
    both = sorted(f for f, tools in agree.items() if tools == {"DWSIM", "IDAES"})
    committed = _comparison()["v16_counts"]
    value = {
        "compared_by_at_least_one_tool": len(at_least_one),
        "compared_by_both_tools": len(both),
        "of": 8,
        "committed_v16_counts_equal": committed["at_least_one"] == at_least_one
        and committed["both"] == both,
    }
    return value["committed_v16_counts_equal"] and len(both) == 8, value


def _m_a54() -> Measured:
    rows = [*_comparison()["rows"], *_comparison()["superseded_default_eps"]["rows"]]
    missing = [f"{r['fixture']}/{r['tool']}" for r in rows if not r.get("reason")]
    unnamed = [
        f"{r['fixture']}/{r['tool']}"
        for r in rows
        if r["classification"] == "NOT_COMPARABLE" and not r.get("category")
    ]
    categories = sorted({str(r.get("category")) for r in rows if r.get("category")})
    value = {"rows": len(rows), "without_reason": missing, "not_comparable_unnamed": unnamed}
    value["categories"] = categories
    return not missing and not unnamed, value


# ----------------------------------------------------------------------------- live measurements

#: SYN-001's implementation hash before and after ADR 0017 (`docs/t06-measurements.md`, W13).
HASH_OLD = "75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce"
HASH_NEW = "67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a"
#: The K05 identity document's registered digests (`docs/t06-measurements.md`): A79's re-baseline
#: (W13, `9ede861`) of the keys `t02`…`t05b`, the structural and artifact hashes and the document
#: without `t06` (W9, `00ff5a9a…`), unchanged at W18; the `t06` key registered at W18.
#: `json.dumps(key, sort_keys=True)` per key; the document as `k05_structural_identity.py`
#: writes it.
A79_DIGESTS: Mapping[str, str] = {
    "t02": "0b75311abed11b504fbac422a7851459d7c90a499e86c7fd3d409e1afc1fcf8d",
    "t03": "1b8a5b2e8b60637c39f1cd81ccded92b6112f5574b6d0ffee0c15f53e293e666",
    "t04": "c0b9bee7a1961175af052153b115d98413d100bde71d4031ba0dc6ec4ed9b142",
    "t05": "24199c7efe863ae3b17d3033b29ca8da54e76e4bac6a6540931596aab0c5be1f",
    "t05b": "3f2feee21d5b241743c6f237ffee09a34e4d7fd229be5c972a9619ee5511be47",
    "structural_sha256": "915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27",
    "artifact_r0_sha256": "77508d4ac3373f523f87c89ba83841173f94ba12c608deb3c8ab83053576471d",
    "document_without_t06": "00ff5a9ab5f3d7431ae5d553a8305ea1d4edd2d9ddb70bb7dfa31c6b751bd475",
}
T06_KEY_W18 = "e0e871f6e4f803bac876ae06a0204a3c31f2c1880135d8c5b8ef0a313424ad6d"
#: A78's table (W13): the pre-commit document under the old hash, as the measurement log prints
#: it (8-hex prefixes; the document as prefix and suffix).
A78_PREFIXES: Mapping[str, str] = {
    "t02": "6a912013",
    "t03": "12bdbcdb",
    "t04": "bdb5d94a",
    "t05": "ddbd0f71",
    "t05b": "4f29500e",
    "structural_sha256": "4ce030ca",
    "artifact_r0_sha256": "9285e860",
    "document_without_t06": "91fac608",
}
A78_DOCUMENT_SUFFIX = "cdf06"
#: A79's substitution: the label strings that carry the implementation hash.
SUBSTITUTION = ((HASH_OLD, HASH_NEW), (HASH_OLD[:12], HASH_NEW[:12]))


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _document_digest(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (json.dumps(document, indent=1, sort_keys=True) + "\n").encode()
    ).hexdigest()


def _digests(document: Mapping[str, Any]) -> dict[str, str]:
    digests = {key: _digest(document[key]) for key in ("t02", "t03", "t04", "t05", "t05b", "t06")}
    digests["structural_sha256"] = str(document["structural_sha256"])
    digests["artifact_r0_sha256"] = str(document["artifact_r0_sha256"])
    digests["document_without_t06"] = _document_digest(
        {k: v for k, v in document.items() if k != "t06"}
    )
    digests["document"] = _document_digest(document)
    return digests


_OLD_HASH_EMITTER = (
    "import runpy, sys\n"
    "import openflowsheet.thermo.syn001 as provider\n"
    f"provider._implementation_sha256 = lambda: {HASH_OLD!r}\n"
    "sys.argv = ['k05_structural_identity.py', '--out', sys.argv[1]]\n"
    "runpy.run_path('scripts/k05_structural_identity.py', run_name='__main__')\n"
)


@cache
def identity_documents() -> dict[str, dict[str, Any]]:
    """The K05 identity document emitted here twice, each in its own process: with SYN-001's
    implementation hash, and with the pre-ADR-0017 hash substituted in the provider (A78's
    protocol, `docs/t06-measurements.md` W13)."""
    documents: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for name, command in (
            ("real_hash", [sys.executable, "scripts/k05_structural_identity.py", "--out"]),
            ("old_hash", [sys.executable, "-c", _OLD_HASH_EMITTER]),
        ):
            out = Path(scratch) / f"{name}.json"
            subprocess.run(
                [*command, str(out)], cwd=ROOT, check=True, capture_output=True, text=True
            )
            documents[name] = json.loads(out.read_text("utf-8"))
    return documents


def _leaves(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield from _leaves(item, f"{path}/{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _leaves(item, f"{path}/{index}")
    else:
        yield path, node


def _substituted(value: Any) -> Any:
    if isinstance(value, str):
        for old, new in SUBSTITUTION:
            value = value.replace(old, new)
    return value


def _m_a44() -> Measured:
    digests = _digests(identity_documents()["real_hash"])
    compared = {key: digests[key] == expected for key, expected in A79_DIGESTS.items()}
    value = {"measured": digests, "equal_to_the_registered": compared}
    return all(compared.values()), value


def _m_a78() -> Measured:
    digests = _digests(identity_documents()["old_hash"])
    compared = {key: digests[key].startswith(prefix) for key, prefix in A78_PREFIXES.items()}
    compared["document_without_t06_suffix"] = digests["document_without_t06"].endswith(
        A78_DOCUMENT_SUFFIX
    )
    value = {
        "protocol": "the K05 identity document emitted with `thermo.syn001._implementation_sha256` "
        f"returning {HASH_OLD[:8]}… (A78's hook), compared with A78's table "
        "(docs/t06-measurements.md, "
        "W13): the pre-ADR-0017 document minus the `t06` key T06 W9 added later",
        "measured": digests,
        "equal_to_the_registered": compared,
        "not_re_measured": "A78's suite-level half (the full suite under the old hash: 3 678 of "
        "3 681, the three failures F6's own; 662 certificates identical) is the W13 record at "
        "`9ede861`",
    }
    return all(compared.values()), value


def _ci_documents(ci: Path | None) -> dict[str, dict[str, Any]]:
    if ci is None:
        return {}
    return {
        path.parent.name: json.loads(path.read_text("utf-8"))
        for path in sorted(ci.rglob("identity.json"))
    }


def _ci_runs(ci: Path | None) -> dict[str, dict[str, Any]]:
    """`gh run view <id> --json headSha,conclusion,event,jobs` for each cited CI run."""
    if ci is None:
        return {}
    return {
        path.stem: json.loads(path.read_text("utf-8"))
        for path in sorted(ci.glob("*.json"))
        if path.stem.isdigit()
    }


def _identity_run(ci: Path | None) -> tuple[str, dict[str, Any]] | None:
    """The CI run whose `identity` job produced the downloaded artifacts: the one run cited with
    a successful `identity` job."""
    found = [
        (run_id, meta)
        for run_id, meta in _ci_runs(ci).items()
        if any(j["name"] == "identity" and j["conclusion"] == "success" for j in meta["jobs"])
    ]
    return found[0] if len(found) == 1 else None


def _cross_platform(ci: Path | None) -> Measured:
    """The downloaded CI identity documents (x86-64 and aarch64) against each other and against
    the one emitted here; the CI run's head differs from the measured tree in no file the identity
    reads from `src/` (measured by `git diff`)."""
    documents = _ci_documents(ci)
    identity = _identity_run(ci)
    if len(documents) < 2 or identity is None:
        return "unsupported", {
            "reason": "no CI identity artifacts given (--ci): the cross-platform half is CI's "
            "`identity` job, which this machine cannot run"
        }
    run_id, meta = identity
    head = str(meta["headSha"])
    src_diff = _git("diff", "--name-only", head, "HEAD", "--", "src/").split()
    local = identity_documents()["real_hash"]
    by_platform = {name: _digests(doc) for name, doc in documents.items()}
    value = {
        "ci_run": int(run_id),
        "ci_head": head,
        "ci_identity_job": "success",
        "src_changed_since_ci_head": src_diff,
        "platforms": sorted(documents),
        "document": {name: d["document"] for name, d in by_platform.items()},
        "t06_key": {name: d["t06"] for name, d in by_platform.items()},
        "local_document": _digests(local)["document"],
        "local_t06_key": _digests(local)["t06"],
    }
    equal = len({d["document"] for d in by_platform.values()} | {value["local_document"]}) == 1
    value["all_equal"] = equal
    return equal and not src_diff and len(documents) == 2, value


def _m_a45(ci: Path | None) -> Measured:
    ok, value = _cross_platform(ci)
    if ok == "unsupported":
        return ok, value
    value["t06_key_registered_at_w18"] = T06_KEY_W18
    t06 = {*value["t06_key"].values(), value["local_t06_key"]}
    return bool(ok) and t06 == {T06_KEY_W18}, value


def _m_a79(ci: Path | None) -> Measured:
    """(2)–(3): the real-hash document equals the old-hash one with the substitution applied,
    leaf by leaf, except the two structural digests; the digests are A79's; (3) the CI pair."""
    documents = identity_documents()
    new, old = dict(_leaves(documents["real_hash"])), dict(_leaves(documents["old_hash"]))
    differing = sorted(
        path for path in set(new) | set(old) if _substituted(old.get(path)) != new.get(path)
    )
    labels = sum(1 for v in old.values() if isinstance(v, str) and HASH_OLD[:12] in v)
    digests = _digests(documents["real_hash"])
    registered = all(digests[key] == expected for key, expected in A79_DIGESTS.items())
    implementation = documents["real_hash"].get("model_version", "")
    value: dict[str, Any] = {
        "leaves": len(new),
        "label_occurrences_substituted": labels,
        "differing_after_substitution": differing,
        "digests_equal_to_a79": registered,
        "model_version": implementation,
    }
    ok = differing == ["/artifact_r0_sha256", "/structural_sha256"] and registered
    ok = ok and HASH_NEW[:12] in str(implementation)
    cross, cross_value = _cross_platform(ci)
    value["ci"] = cross_value
    if cross == "unsupported":
        value["reason"] = cross_value["reason"]
        return ("unsupported" if ok else False), value
    return ok and bool(cross), value


# -- A87: ADR 0018 inert where it does not fire -------------------------------------------------


def _events(result: Any) -> list[dict[str, Any]]:
    """Every event's document without the closing chord's `linear` record (D5, non-R0)."""
    return [
        {k: v for k, v in event.as_document().items() if k != "linear"}
        for event in result.trace.events
    ]


def _fired(result: Any) -> bool:
    return any(
        (event.message or "").startswith("terminal_refinement(")
        for event in result.trace.of_kind("attempt_closed")
    )


def _m_a87() -> Measured:
    """(a) the K05 identity document without `t06` is the registered one (no registered policy
    selects the rule) and the fixture generators' outputs are today's (the gate's tests);
    (b) the registered-start solves of the revision cases under `T06-revision-v2` and under the
    same document with `eo_core = "newton"`: where the rule does not fire, every event equal but
    the closing `linear` record, the final state bit-identical."""
    from openflowsheet.application.revision_binding import (
        RevisionBinding,
        bind_revision_flowsheet,
    )
    from openflowsheet.orchestrator.execution import ExecutionPlan
    from openflowsheet.orchestrator.executor import execute_plan
    from openflowsheet.orchestrator.revision import plan_revision

    identity = _digests(identity_documents()["real_hash"])["document_without_t06"]
    value: dict[str, Any] = {
        "a_document_without_t06": identity,
        "a_registered": A79_DIGESTS["document_without_t06"],
    }
    ok = identity == A79_DIGESTS["document_without_t06"]
    compared: dict[str, str] = {}
    for item in w5_corpus.REVISION_RUNS:
        if item.policy != "T06-revision-v2":
            continue
        refined = w4_registry.CONSTRUCTED[item.policy]
        plain = replace(refined, globalization=replace(refined.globalization, eo_core="newton"))
        results = []
        for policy in (refined, plain):
            binding = bind_revision_flowsheet(w5_corpus._document(item.fixture, item.revision))
            assert isinstance(binding, RevisionBinding), binding
            plan, _ = plan_revision(binding, policy)
            assert isinstance(plan, ExecutionPlan), plan
            results.append(
                execute_plan(
                    plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy
                )
            )
        with_rule, without = results
        label = f"{item.case}:{item.fixture}"
        if _fired(with_rule):
            compared[label] = "fired"
            continue
        same_state = (with_rule.state is None and without.state is None) or (
            with_rule.state is not None
            and without.state is not None
            and {k: float(v).hex() for k, v in with_rule.state.items()}
            == {k: float(v).hex() for k, v in without.state.items()}
        )
        same = (
            with_rule.outcome == without.outcome
            and same_state
            and _events(with_rule) == _events(without)
            and with_rule.counters == without.counters
        )
        ok = ok and same
        compared[label] = "equal" if same else "DIFFERS"
    value["b"] = compared
    value["b_fired_in"] = sorted(k for k, v in compared.items() if v == "fired")
    return ok and bool(compared), value


# -- A43: validation over every registered revision ---------------------------------------------

#: The statuses a registered assertion names for a revision file (the rest are recorded).
A43_STATUSES: Mapping[str, str] = {
    "SYN-001-nominal.yaml": "READY_FOR_SIMULATION",  # P01
    "SYN-001-conflicting-heater-spec.yaml": "INVALID",  # T01 A09 (STR-03)
    "SYN-001-T06-STR02.yaml": "DRAFT",  # A04
    "SYN-001-T06-STR06.yaml": "INVALID",  # A08
    "SYN-001-T06-STA03-kgs.yaml": "READY_FOR_SIMULATION",  # A55
    "SYN-001-T06-STA03-degC.yaml": "READY_FOR_SIMULATION",  # A55
    "SYN-001-T06-STA04.yaml": "DRAFT",  # A59 (F5)
}
#: A08: STR-06's `COMP-03` is the registered failure.
A43_COMP03_FAIL = frozenset({"SYN-001-T06-STR06.yaml"})


def _m_a43() -> Measured:
    from openflowsheet.application.validation import validate

    value: dict[str, Any] = {}
    ok = True
    for path in sorted(ROOT.glob("benchmarks/*/cases/*.yaml")):
        report = validate(yaml.safe_load(path.read_text("utf-8")))
        results = {check.id: check.result for check in report.checks}
        comp = "FAIL" if path.name in A43_COMP03_FAIL else "PASS"
        mine = results.get("DIM-01") == "PASS" and results.get("COMP-03") == comp
        mine = mine and A43_STATUSES.get(path.name, report.status) == report.status
        ok = ok and mine
        value[str(path.relative_to(ROOT))] = {
            "status": report.status,
            "DIM-01": results.get("DIM-01"),
            "COMP-03": results.get("COMP-03"),
        }
    value["statuses_asserted"] = dict(A43_STATUSES)
    value["statuses_recorded_only"] = "every other file's status is recorded, not compared: the "
    value["statuses_recorded_only"] += "pre-W1 baseline (spec §2, M3) covers the corpus cases only"
    return ok, value


# -- values the gate's tests assert, read back from their own cached computations ---------------


def _m_a01() -> Measured:
    corpus = w4_registry.CASES
    denominator = sum(1 for case in corpus if case.get("in_success_denominator"))
    return len(corpus) == 49 and denominator == 30, {
        "cases": len(corpus),
        "in_success_denominator": denominator,
    }


def _m_a92() -> Measured:
    """B34 (a)'s ten `FAILED` closures (recorded, not asserted beyond the floor) and the floor."""
    import test_t05b_candidate_answers as b34

    closures: dict[str, float] = {}
    for key, certificate in b34.certificates().items():
        if certificate.verification_status != "FAILED":
            continue
        (check,) = [
            c for c in certificate.checks if c.id == "phase_admissibility.U-PHF2.S2.closure"
        ]
        closures[repr(key)] = float(check.value) if check.value is not None else math.nan
    floor = float(b34.DEW_POINT_CLOSURE_FLOOR)
    smallest = min(closures.values())
    value = {
        "floor_K": floor,
        "failed": len(closures),
        "closures_K": closures,
        "smallest_over_floor": smallest / floor,
    }
    return len(closures) == 10 and smallest >= floor, value


def _m_a96() -> Measured:
    import test_t06_w24_budget as w24

    n0, n1 = w24._n0(), w24._n1()
    return n1 > n0, {"N0_newton_property_calls": n0, "N1_newton_refined_property_calls": n1}


# ----------------------------------------------------------------------------- the checks

MEASURES: dict[str, Callable[[Path | None], Measured]] = {
    "A01": lambda ci: _m_a01(),
    "A25": lambda ci: _m_a25(),
    "A26": lambda ci: _m_a26(),
    "A27": lambda ci: _m_a27(),
    "A28": lambda ci: _m_a28(),
    "A29": lambda ci: _m_a29(),
    "A30": lambda ci: _m_a30(),
    "A31": lambda ci: _m_a31(),
    "A32": lambda ci: _m_a32(),
    "A33": lambda ci: _m_a33(),
    "A34": lambda ci: _m_a34(),
    "A35": lambda ci: _m_a35(),
    "A36": lambda ci: _m_a36(),
    "A43": lambda ci: _m_a43(),
    "A44": lambda ci: _m_a44(),
    "A45": _m_a45,
    "A47": lambda ci: _m_a47(),
    "A51": lambda ci: _m_a51(),
    "A53": lambda ci: _m_a53(),
    "A54": lambda ci: _m_a54(),
    "A66": lambda ci: _m_a66(),
    "A78": lambda ci: _m_a78(),
    "A79": _m_a79,
    "A84": lambda ci: _m_a84(),
    "A87": lambda ci: _m_a87(),
    "A90": lambda ci: _m_a90(),
    "A92": lambda ci: _m_a92(),
    "A95": lambda ci: _m_a95(),
    "A96": lambda ci: _m_a96(),
    "A98": lambda ci: _m_a98(),
    "A99": lambda ci: _m_a99(),
}

#: What a check's `value` holds besides its measurements, where the assertion is part record.
RECORDED: dict[str, str] = {
    "A38": "the 20-seed spread is M5's (`docs/t06-measurements.md`); the gate's test re-derives "
    "the certificate as a function of its solve alone",
    "A41": "W2's inertness (every registered certificate bit-identical) is the W2 commit's own "
    "measurement, recorded in its message; here the registered certificate fixtures are what the "
    "verifier emits today",
    "A46": "K04 §7.6's registrations, asserted by K04's tests, run here",
    "A81": "(a)'s 44-value difference is W15's record at `b3d9c95` (spec A81 (A3)); (b) is the "
    "K05 fixture test, run here",
}


def _result(parts: Sequence[str]) -> str:
    if not parts:
        return "unsupported"
    if "fail" in parts:
        return "fail"
    if "unsupported" in parts:
        return "unsupported"
    return "pass"


def check(identifier: str, tests: GateTests, ci: Path | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": f"T06.{identifier}", "description": DESCRIPTIONS[identifier]}
    if identifier in NOT_APPLICABLE:
        entry["result"] = "not_applicable"
        entry["value"] = {"reason": NOT_APPLICABLE[identifier]}
        return entry
    parts: list[str] = []
    value: dict[str, Any] = {}
    verdict, tested = tests.summary(identifier)
    if verdict is not None:
        parts.append(verdict)
        value["tests"] = tested
    if identifier in MEASURES:
        try:
            ok, measured_value = MEASURES[identifier](ci)
        except Exception as error:  # noqa: BLE001 - a measurement that could not run did not pass
            ok, measured_value = False, {"error": f"{type(error).__name__}: {error}"}
        parts.append(ok if isinstance(ok, str) else ("pass" if ok else "fail"))
        value["measured"] = measured_value
    if identifier in RECORDED:
        value["record"] = RECORDED[identifier]
    entry["result"] = _result(parts)
    if entry["result"] == "unsupported":
        value.setdefault(
            "reason",
            (value.get("measured") or {}).get("reason")
            or "no measurement of this assertion could be made here",
        )
    entry["value"] = value
    return entry


# ----------------------------------------------------------------------------- limitations

#: The requirement ids T06 advances (`docs/requirements.yaml`: every entry whose packages name
#: T06). The frozen schema takes D/A ids only; the plan's V16, V18 and V20 go to `limitations`.
T06_REQUIREMENTS = ("D05", "D11", "D14", "D19", "D20", "A04", "A08", "A09", "V16", "V18", "V20")


def _schema_refuses_requirement(identifier: str) -> bool:
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "schemas" / "evidence-manifest.schema.json").read_text("utf-8"))
    validator = Draft202012Validator(schema["properties"]["requirements"])
    return bool(list(validator.iter_errors([identifier])))


def _holdout_line(machine: str) -> str:
    s = summary(ensemble.HOLDOUT_RUN_ID, machine)
    run2 = int(run("run2", machine).entry["S"])
    return (
        f"{machine}: S = {s['S']} of {s['N']} (S^first = {s['S_first']}, S^rescued = "
        f"{s['S_rescued']}; S_holdout − S_run2 = {s['S'] - run2:+d}), one-sided 95 % "
        f"Clopper–Pearson lower bound {s['cp_lower']:.6f} on S and {s['cp_lower_first']:.6f} on "
        f"S^first, classes {s['classes']}"
    )


def _limitations(
    commit: str, refused: Sequence[str], checks: Sequence[Mapping[str, Any]]
) -> list[str]:
    run1 = run("run1", "ref-x86-64")
    run1_headline = _headline(run1)
    closing = _closing_commit()
    since_closing = _git("diff", "--name-only", closing, commit).split()
    tops = sorted({"/".join(path.split("/")[:2]) for path in since_closing})
    run2 = {machine: summary("run2", machine) for machine in CLASSES}
    disagreements = sorted(
        {
            f"{run_id} {line.split(':', 1)[0]}"
            for run_id in ("run2", "run2r", ensemble.HOLDOUT_RUN_ID)
            for i, left in enumerate(CLASSES)
            for right in CLASSES[i + 1 :]
            for line in _disagreements(run(run_id, left), run(run_id, right))["classification"]
        }
    )
    not_last = {
        f"{run_id}@{machine}": len(summary(run_id, machine)["refinements"]["not_last"])
        for run_id in ("run2r", ensemble.HOLDOUT_RUN_ID)
        for machine in CLASSES
    }
    stated = [
        # What kind of evidence this is (the verdicts' §5.1).
        "Evidence class: the reference comparisons are numerical verification against "
        "independent implementations of the same synthetic equations; the ensemble and the holdout "
        "are numerical robustness evidence for 22 registered cases' start distributions. Neither "
        "is empirical validation or optimality evidence. Status `tested` is the build lane's; "
        "`reviewed` and the human numerical and process-modeling sign-off are not claimed "
        "(review fields pending).",
        "Plan §5's verification items V16, V18 and V20 (T06's gates) are not requirement ids "
        "the frozen evidence schema accepts: "
        + ", ".join(refused)
        + ". Their evidence is here by assertion: V16 by A01–A20 and A47–A54 (8 of 8 fixtures "
        "compared by both tools, A53), V18 by A37–A46 and A91–A92, V20 by A28–A30 on run 2 with "
        "A16, A19, A20 and A99; the verdicts (`docs/reviews/T06-verdicts.md`) judged V16's "
        "comparison clause and V20 on run 2 MET, and V20's no-false-verification clause NOT MET "
        "for run 1.",
        # Run 1 and the gate.
        f"Run 1 FAILED the registered gate and stands as recorded (R-087, A95): `dfa7d09`, "
        f"`T06-revision-v1`, S = {run1_headline['S']} of 440 (S^first {run1_headline['S_first']}, "
        f"rescued {run1_headline['S_rescued']}), classes {run1_headline['classes']}; the four "
        f"`F-OTHER-ROOT`s ({', '.join(_listed(run1, 'F-OTHER-ROOT'))}) are the registered root "
        "stopped inside the row-tolerance window (spec Amendment 4), not explained under §7.2, so "
        "the gate term fails; NET-11 start 16 was a missed false success (a false `TWO_PHASE` "
        "label certified `VERIFIED`, counted SUCCESS; the verdicts §3.4). Run 1 is not re-judged.",
        "The gate verdict is run 2's (spec §7.3 (A5)): run 2 re-scored run 1's 440 starts after a "
        "solver remedy (ADR 0018, `T06-revision-v2`) and a verifier correction (§8.8), both "
        "registered by Amendment 4 after run 1 was seen; the verdict agent judged the re-score "
        "legitimate under R-087 and plan §6.5 with qualifications that travel (§2.3): run 2 is "
        "not an out-of-sample test of `T06-revision-v2`, so its Clopper–Pearson bound ("
        f"{run2['ref-x86-64']['cp_lower']:.4f} on ref-x86-64) is start-sampling uncertainty for a "
        "solver whose last change was informed by these draws; the holdout is the out-of-sample "
        "estimate.",
        "Run 2r (A98) is a reproduction at the closing commit, not a second gate result. Per "
        "class, S (S^first + S^rescued) and A98's discrepancies against run 2: "
        + "; ".join(
            f"{m} {summary('run2r', m)['S']} ({summary('run2r', m)['S_first']} + "
            f"{summary('run2r', m)['S_rescued']}), "
            + str(
                len(
                    ensemble.a98_discrepancies(run("run2r", m).document, run("run2", m).document)[
                        "discrepancies"
                    ]
                )
            )
            for m in CLASSES
        )
        + ". It supplies A90's refinement records, which run 2's v1 records lack: A90 is judged "
        "on run 2r's records, not on run 2's.",
        "The holdout `holdout1` (spec §7.6 (A5), R-089) is reported and never gated; it is "
        "out-of-sample only for the start draw (the nominal law at start indices 20…39): "
        + "; ".join(_holdout_line(machine) for machine in CLASSES)
        + ". It says nothing more about other process designs than run 2 does.",
        "Platform dependence: the gate holds on each architecture, but per-start outcomes are "
        "not portable (A35, reported). The starts classified differently on two classes: "
        + ", ".join(disagreements)
        + "; final states that differ bitwise and rescue-status differences are counted per "
        "pair in A35's value.",
        "Every committed run file keeps the bytes it was written with: run 1's and run 2's v1 "
        "files say `machine_class: ref-x86-64` on every host (the pre-A5 literal, the verdicts' "
        "P2); their class is the registry's, from `architecture` and the CI job (A97 (e)), and "
        "they carry no commit, lock hash or `cache_condition` (P3; run 2's commit is the "
        "decisions log's `f636452`, corroborated by the verdicts). The v2 files (run 2r, "
        "`holdout1`) carry all of them.",
        f"The ensemble and holdout records were written at the closing commit `{closing[:7]}`; "
        "this "
        f"manifest measures `{commit[:7]}`, which differs from it in no `src/` file and in "
        + (", ".join(tops) if tops else "nothing")
        + " (the W31 records and bookkeeping, a test fix for A97 (c)'s machine-dependent counts, "
        "this generator).",
        "CI: the two ensemble dispatches (36270294833 at `f636452`; 36278604955 at `6018ebc`) "
        "concluded `failure` because a `check` job failed on a pinned machine-dependent value "
        "that no ensemble job uses (T05b B34 (a)'s closure value on aarch64, fixed at `4d1e2ed`; "
        "A97 (c)'s absolute property-call count on aarch64, fixed at `7ec1b59`); their ensemble "
        "and compare jobs succeeded and their `identity` jobs were skipped. The cross-platform "
        "identity (A45, A79) is from the push run whose `identity` job succeeded (see the "
        "commands), with no `src/` change between its head and the measured commit.",
        # The reference comparisons (the verdicts' §5.2).
        "IDAES agrees at the registered near-sharp SmoothVLE ε (1e-8 K), a setting the design "
        "lane ruled after W8's disagreement; at IDAES's default smoothing REF-03 (1.36×) and "
        "REF-08 (302×) disagree, and those records are retained `NOT_COMPARABLE(semantics)` "
        "(A83). Nothing is claimed about IDAES at its default smoothing.",
        # Registered remaining limitations and scope defaults.
        "T05b spec §17, §18 Q9 (Frank's default; a K04 follow-up): a lifted flash whose root lies "
        "exactly on its dew or bubble point with the other product zero is not certified "
        "(`UNVERIFIED`, `RANK_DEFICIENT`); STR-05's expectation (A07) rests on that default, and "
        "if the follow-up certifies it STR-05 needs a new fixture (T06 spec Q9). T05b B34 (a)'s "
        "dew-point runs that stop nearby are caught `FAILED` (A92); where a false success lands is "
        "machine-dependent.",
        "T07's hand-on questions (R-088; spec §16 Q24–Q29), each with its default in force and "
        "no T06 change: Q24 a saturation-closure failure inside the rows' own window stays "
        "`FAILED(false_success_detected)`; Q25 the alias shift `997·(j+1)` Pa is unchanged (from "
        "about 20 streams every such certificate is `UNVERIFIED(pressure_shift_outside_domain)`); "
        "Q26 W14's identity refusal is defence in depth; Q27 no concurrent verification within "
        "one process (W3 seeds the global RNG); Q28 event messages stay outside R0; Q29 a "
        "non-canonical number in a field no reader reads escapes as an untyped "
        "`CanonicalizationError` (a K06 boundary gap older than T06).",
        "Further registered scope defaults (spec §16): Q2 `validate()` of a revision-built "
        "flowsheet stays `DRAFT` until T07 (F5); Q6 K05 run sessions and bundles are not "
        "generalized to revision-built flowsheets (harness-level replay only); Q13 results are "
        "keyed by component id, not presented in a declared order; Q14 one exact ASCII spelling "
        "per unit, no aliases; Q15 gauge pressure refused; Q18 `plan_revision` raises for a "
        "declaration T01 does not close (T07 returns T01's report first); Q22 a `TWO_PHASE` split "
        "with a vanishing phase is not converted by the solver (the verifier catches the label); "
        "Q23 no cost remedy: THM-08/3, THM-08/12 and THM-09/4 stay `F-BUDGET`.",
        "ADR 0018 D4′ (M1, A96): `newton_refined` spends property budget in its refinement, so a "
        "solve `newton` finishes can end `BUDGET_EXHAUSTED(property_calls)` (THM-09 start 1 at "
        "caps 365–385); Frank kept `newton_refined` as T07's default knowing this (2026-09-27). "
        "A refined state that a converged closure converts would open a different later path "
        "(D4′ (ii)); fired refinements recorded outside a start's last attempt, per run and "
        f"class (A90): {not_last}.",
        "Frank's decisions this evidence rests on (`docs/T06_DECISIONS.md`): the gate on the point "
        "estimate `S ≥ 418` on both classes with the Clopper–Pearson bound reported (Q7); rescued "
        "starts counted as successes and reported (2026-09-26); unit conversion at the boundary "
        "(ADR 0016) and component order mapped (Q3, Q4, Q11); ADR 0015's and ADR 0018's enum "
        "widenings and ADR 0017's identity move approved; `newton_refined` as T07's default (kept "
        "2026-09-27); the holdout run in T06 (2026-09-27). Standing directives: fewest "
        "limitations; robustness with recorded fallbacks; the T05/T05b defaults agreed.",
        "ADRs 0014–0018 are `Proposed` at the measured commit; each says it is accepted when this "
        "manifest is `tested`. The acceptance is a separate bookkeeping step.",
        "Not run: the stress profiles (spec §6.7: box, log, trivial-split) — registered, reported "
        "and never gated; T06's gate does not depend on them.",
        "Spec §15, what T06 does not establish: no uniqueness claim for any root (the branch "
        "census reports what the ensemble found); no performance claim (the 60 s ceiling is a "
        "hang guard; costs are within-platform); a rescued start is evidence about the solver with "
        "its fallbacks, not Newton's basin, and THM-08's and THM-09's `p_c^first` is not a "
        "near-root basin (single-phase openings); no solution-accuracy promise from a certificate "
        "beyond ADR 0018's first-order target where a refinement is kept; §8.8 checks saturation, "
        "not the split's amounts; units v2 is ADR 0016's table and nothing else; ADR 0017 removes "
        "one failure mode of SYN-001's flash; no block-level rank localization at T06's sizes.",
        "Part-record assertions: A78's suite-level half (the full suite under the old hash), A41's "
        "W2 inertness, A38's 20-seed spread and A81 (a)'s fixture difference are the records of "
        "the commits that measured them (`docs/t06-measurements.md`, the W2 and W15 commits); what "
        "is measurable at this commit is measured and named in each check's value.",
    ]
    for entry in checks:
        if entry["result"] in ("unsupported", "not_applicable"):
            reason = entry["value"].get("reason", "")
            stated.append(f"{entry['id']} is `{entry['result']}`: {reason}.")
        elif entry["result"] == "fail":
            stated.append(f"{entry['id']} is `fail`: its value names every measured departure.")
    return stated


# ----------------------------------------------------------------------------- the manifest


def _gate(gate_stdout: Path) -> dict[str, Any]:
    """The gate's log: its verdict line and the last pytest summary line's counts."""
    text = gate_stdout.read_text("utf-8")
    lines = re.findall(r"^((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", text, flags=re.MULTILINE)
    counts = {word: int(n) for n, word in re.findall(r"(\d+) ([a-z]+)", lines[-1])} if lines else {}
    return {"passed": "=== check.sh: PASSED ===" in text, "pytest_counts": counts}


def _artifacts() -> list[dict[str, str]]:
    described = {
        ".json": "run file (committed, unedited; registry `ensemble.runs`)",
        ".report.txt": "report recomputed byte for byte from its run file (A31, A99 (c))",
        ".replay.txt": "replay of each case's first start and every retained failure (A34)",
        ".a98.txt": "run 2r against run 2's same-class file (A98 (b)–(c))",
        ".compare.txt": "cross-class per-start classification disagreements (A35)",
    }
    artifacts = [
        {
            "path": str(STARTS_FILE.relative_to(ROOT)),
            "sha256": _sha256(STARTS_FILE),
            "description": "the published nominal starts (spec §6.5; registry `starts_sha256`)",
        },
        {
            "path": str(HOLDOUT_FILE.relative_to(ROOT)),
            "sha256": _sha256(HOLDOUT_FILE),
            "description": "holdout1's starts, committed before any holdout solve (spec §7.6 (A5))",
        },
    ]
    for name, digest in _sums().items():
        suffix = next(s for s in described if name.endswith(s))
        prefix = "judged text of run 2 (the verdicts' §0): " if name.startswith("judged/") else ""
        artifacts.append(
            {
                "path": str((RUNS_DIR / name).relative_to(ROOT)),
                "sha256": digest,
                "description": prefix + described[suffix],
            }
        )
    for name in ("comparison.json", "SHA256SUMS"):
        path = REFERENCES / name
        if not path.exists():
            path = REFERENCES / "results" / name
        artifacts.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": _sha256(path),
                "description": "the reference comparison table (A50, A53)"
                if name == "comparison.json"
                else "the reference records' digests (A50 (a))",
            }
        )
    return artifacts


def _case_hash() -> str:
    """One digest over the registered inputs the checks judge, in this order."""
    digest = hashlib.sha256()
    for path in (
        REGISTRY_FILE,
        TWIN,
        STARTS_FILE,
        HOLDOUT_FILE,
        RUNS_DIR / "SHA256SUMS",
        REFERENCES / "comparison.json",
        SPEC,
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _ci_commands(ci: Path | None) -> list[dict[str, Any]]:
    commands = []
    for run_id, meta in _ci_runs(ci).items():
        jobs = ", ".join(f"{j['name']} {j['conclusion']}" for j in meta["jobs"])
        commands.append(
            {
                "cmd": f"GitHub Actions workflow `ci` run {run_id} ({meta['event']}, head "
                f"{meta['headSha']}): {jobs}",
                "cwd": ".",
                "exit_code": 0 if meta["conclusion"] == "success" else 1,
            }
        )
    return commands


def build(
    commit: str, gate_stdout: Path, ci: Path | None, allow_dirty: bool = False
) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD").strip()
    if commit != head:
        raise SystemExit(f"--commit {commit} is not HEAD ({head}): measure the commit checked out")
    dirty = [line for line in _git("status", "--porcelain").splitlines() if "evidence/" not in line]
    if dirty and not allow_dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    gate = _gate(gate_stdout)
    tests = run_gate_tests()
    checks = [check(identifier, tests, ci) for identifier in IDS]
    refused = [r for r in T06_REQUIREMENTS if _schema_refuses_requirement(r)]
    requirements = [r for r in T06_REQUIREMENTS if r not in refused]
    failed = [entry["id"] for entry in checks if entry["result"] == "fail"]
    commands = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": _sha256(gate_stdout),
        },
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/t06_evidence_manifest.py GATE_STDOUT "
            f"--commit {commit}" + (" --ci CI_DIR" if ci else ""),
            "cwd": ".",
            "exit_code": 1 if failed else 0,
        },
        *_ci_commands(ci),
    ]
    return {
        "work_package": "T06",
        "commit": commit,
        "requirements": requirements,
        "status": "implemented" if failed or not gate["passed"] else "tested",
        "inputs": {
            "case_id": "T06's registered corpus (49 cases, benchmarks/registry.yaml `corpus`), the "
            "robustness ensemble (22 cases × 20 published starts, `ensemble`; runs 1, 2 and 2r) "
            "and "
            "the holdout (`ensemble.holdout`, start indices 20…39), and the eight reference "
            "fixtures with PC-1/PC-2 (`reference_fixtures`); judged against "
            f"benchmarks/t06/reference_values.yaml ({_sha256(TWIN)}) and "
            f"docs/derivations/T06-corpus-spec.md ({_sha256(SPEC)}) as amended through "
            "Amendment 5",
            "case_hash": _case_hash(),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": _artifacts(),
        "limitations": _limitations(commit, refused, checks),
        "review": {"numerical": "pending", "process_model": "pending"},
        "_gate": gate,
        "_tests_exit_code": tests.exit_code,
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


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


#: The evidence-manifest rule: an angle-bracketed span is a template placeholder, never evidence.
ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--ci",
        type=Path,
        default=None,
        help="directory with `gh run view ID --json headSha,conclusion,event,jobs` as ID.json "
        "and the identity run's structural-identity-* artifacts",
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

    built = plain(
        build(arguments.commit, arguments.gate_stdout, arguments.ci, arguments.allow_dirty)
    )
    gate, tests_exit = built.pop("_gate"), built.pop("_tests_exit_code")
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "schemas" / "evidence-manifest.schema.json").read_text("utf-8"))
    schema_errors = [e.message for e in Draft202012Validator(schema).iter_errors(built)]
    placeholders = [text for text in _strings(built) if ANGLE_PLACEHOLDER.search(text)]
    destination = arguments.out or (ROOT / "evidence" / "T06" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(built, indent=1, allow_nan=False) + "\n", encoding="utf-8")

    counts = Counter(entry["result"] for entry in built["checks"])
    print(f"wrote {destination}")
    print(f"gate: {gate}; the tests run here: pytest exit {tests_exit}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, {counts['unsupported']} "
        f"unsupported, {counts['not_applicable']} not applicable; status {built['status']}"
    )
    for entry in built["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    if placeholders:
        print(f"angle-bracketed text in the manifest (never valid evidence): {placeholders[:5]}")
    if schema_errors:
        print(f"the manifest has {len(schema_errors)} schema errors: {schema_errors[:3]}")
    return 1 if counts["fail"] or placeholders or schema_errors or not gate["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
