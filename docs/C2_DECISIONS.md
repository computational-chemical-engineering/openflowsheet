# C2 — build decisions (OpenIDAES-450 split registration)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: register-number ranges for the cloud queue (branches run unmerged in parallel) → C2 R-486…R-494, C1
  R-495…R-499, C3 R-500…R-504, S01 R-505…R-519, L01 R-520…R-529, S02 R-530…R-539. Alternative: renumber at merge.
  Reversible by: renumbering an unmerged branch's entries before its merge.
- DECISION: split ratio → per-stratum halves, odd strata alternating up/down by seeded stratum rank, no compensation
  across strata (D-1, SPLIT-R06). Alternative: global largest remainder or 60/40. Reversible by: a v2 registration
  before any held-out score is reported.
- DECISION: which R02 the strata use → W27-R02 as committed in `coverage.json` (D-2, R-487). Alternative: R02-F1
  classes. Reversible by: a v2 registration.
- DECISION: seed source → fixed text embedding brief commit `f39746770dd7…`, committed (`0211372`) before the draw
  (`c0649a7`) (D-3, R-489). Alternative: archive SHA-256, free string. Reversible by: a v2 registration.
- DECISION: dynamic cases → in the frame as own strata (D-4, R-493). Alternative: exclude. Reversible by: a v2
  registration.
- DECISION: incomplete case → excluded from both halves; a repaired one is an added case (development, as already
  named) (D-5, R-491). Alternative: assign now. Reversible by: an amendment.
- DECISION: exposed set → W27's 45 + 3 canaries + 17 cases named in committed non-data files at `f397467` (D-6,
  R-488; Frank asked, C2-Q2). Alternative: the 48 only. Reversible by: a v2 registration before any held-out score.
- DECISION: protection → recorded rule + held-out ids never in clear outside 12 all-case files and `heldout/` dirs +
  hash commitment + leak-guard test SPLIT-A09 (D-7, R-490). Alternative: ids in clear with a rule alone. Reversible
  by: adding ids to the record (one-way).
- DECISION: re-split policy → never redraw; generator refuses on input change; removed/changed/added cases by
  amendment, added by seeded per-case coin (D-8, R-491). Alternative: redraw on change. Reversible by: a new
  registration.
- DECISION: F-1 → R02-F1 with class-name fallback, awaiting `topology_units` in a new `case_facts-v2.json` from the
  workstation (D-9, R-492). Alternative: topology_kind-only rule, or a flag. Reversible by: an amendment after the
  development-only measurement (§11 Q-4).
- DECISION: contamination at the first draw (a held-out id used as an example in the pre-draw text) → recorded under
  SPLIT-R11 by hash, mention kept, headline 223 (D-10, R-490). Alternative: edit it out silently. Reversible by: none
  needed.
- DECISION: record location → `benchmarks/c2/openidaes450_split.json` (package-id convention) (D-11). Alternative:
  next to W27's data. Reversible by: moving it with the generator constant.
- DECISION (build lane): evidence manifest for C1/C2/C3 → none; `schemas/evidence-manifest.schema.json`'s
  `work_package` pattern `^[PKTMSR][0-9]{2}[a-z]?$` admits no `C` id, and the schema is frozen. These packages merge
  on the full gate read and CI green on both architectures (the user's queue rule: "tested manifest where the package
  has one"). Alternative: an ADR widening the pattern. Reversible by: that ADR and retro-manifests.
- DECISION (build lane, CI): D-11 reversed → the record moves to `benchmarks/m06/openidaes450/split.json`. CI run
  39688818107 failed W27-A71 (`tests/test_t08_w2_unsupported.py:230`, R-194/R-467): a tracked path naming `openidaes`
  under `benchmarks/` must lie in the adaptation directory `benchmarks/m06/openidaes450/`. `split.json` is not a
  registered record name and not under `runs/`, so W27-A72 holds. The record's bytes and SHA-256 are unchanged (it
  does not name its own path). Alternative: amend U14 (a W27 registration change). Reversible by: moving it back with
  a U14 amendment.
- DECISION (Amendment 1, 2026-10-22, R-555, D-12): a version re-take of a pinned input (`coverage.json` at
  `0.3.0.dev0`, `f85fcd7`) → read the pinned content from git history by blob id, check it against the SHA-256 pin,
  and require the working copy's (`case_id`, `family`, `class`) multiset to equal it; no history means an explicit
  refusal. `split.json` is byte-identical. Alternative: re-pin per re-take; a frozen copy; a read-field digest pin.
  Reversible by: an amendment.
- DECISION (Amendment 2, 2026-10-23, R-581, D-13): who writes `case_facts-v2.json` → C2's own script
  `docs/derivations/scripts/c2_openidaes450_facts_v2.py`, reusing W27's reading helpers by import; W27's generator and
  its preflight pins unchanged; the expected file is WS1's bytes with `source.generator` substituted (`4f5c5a65…`).
  Alternative: WS1's stage in W27's generator with a re-pin; a stage in C9's version 2 generator or in the split
  generator. Reversible by: an amendment moving the writer.
- DECISION (Amendment 2, 2026-10-23, R-582, D-14): how SPLIT-A09 admits it → one exact `ALL_CASE_FILES` entry; the
  split generator pins the file and checks seven identities and the unit-level F-1 states (items 13–15); `f1.status`
  `facts_committed`; `split.json` changes in `f1` only (`a556e417…`). Alternative: a `heldout/` path; a split pair of
  files; a pattern entry. Reversible by: an amendment.
- TESTED (WO-C2-A2, Amendment 2, 2026-10-23, branch `wp/C2-A2`; status `tested`, not reviewed). Workstation, real
  archive present (hard-linked, ignored). Commands and digests, from the repository root:
  `python -I docs/derivations/scripts/c2_openidaes450_facts_v2.py --emit` → `case_facts-v2.json` SHA-256
  `4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef` (170,687 bytes, 452 lines), equal to §15.6's
  derivation from WS1's blob `7b0686e` (which also printed `57d43acb…` and tail `fb0e0fe3…`); no Q-6. `--check`
  exit 0. `PYTHONPATH=src python docs/derivations/scripts/c2_openidaes450_split.py --emit` → `split.json` SHA-256
  `a556e417a8063dbf06242890667e7f5bd4056128cea552c49a81bf40c9cd755c` (25,115 bytes); `--check` exit 0. W27's
  `python -I docs/derivations/scripts/m06_w27_registration.py facts --check` byte-identical (`0ca8cffa…`).
  Tests: `tests/test_c2_openidaes450_split.py` 40 passed, 0 skipped (SPLIT-A25 (a) ran and passed);
  `test_m06_w27_harness.py`, `test_c9_w27_v2.py`, `test_l01_records.py` 157 passed, 1 skipped (L01's retrieval
  re-run, distributions off the pins; not this package). ruff and mypy clean.
- BUILD DECISION (WO-C2-A2): how item 14 is callable below the pin → two module functions, `f1_identities(facts,
  facts_v2)` (item 14) and `f1_unit_level_states(facts, facts_v2)` (item 15); `read_inputs` adds the working copy's
  bytes under `F1_KEY` when the file exists, and `build` applies item 13 to them. `SplitRefusedError` gains an
  optional `label`, so an item-14 refusal reads `SPLIT-R13/A2 <label>: <n> case(s)` exactly; `binding` counts
  failed fields (`<n> field(s)`), since it is not a per-case identity. Alternative: a `build` keyword that skips the
  pin. Reversible by: one commit (`7b3f1dc9`).
- BUILD DECISION (WO-C2-A2): SPLIT-A18 builds its `raw` from the three `INPUTS` only; it now also supplies the
  facts-v2 working copy, as `read_inputs` does (item 13 would otherwise refuse). SPLIT-A20 parses a facts file's
  first line by closing it with `]}`. Reversible by: test edits in `87d86c83`.
- REVIEW FIX (WO-C2-A2 F1/F2): A20 now asserts label None and the pinned SHA in the message (mutation: item 13 comparison deleted -> A20 fails); A25(c) asserts the OK byte-identical line and a synthetic archive differing in one unit id gives exit 1. Tests only. Reversible by: revert the commit.
