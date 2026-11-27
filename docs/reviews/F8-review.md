# F8 review (ADR 0067, identity, replay and evidence v2), WO1 to WO3 and WO5, with the F8 ruling batch

Design lane, `reviewer`, 2026-11-27. Brief: `docs/briefs/F8-reviewer.md`. Branch `wp/F8` at `5406f812` (F8's own diff
`df796cc2..5406f812`, 24 commits). Read against ADR 0067 D1 to D7 and D9, exits E-F8-1 to -6, -8, -10, "New catalogue
codes" and the work-order table; ADR 0019 Amendment 12; `docs/F8_DECISIONS.md` (every entry);
`evidence/F8/32981fb3…/manifest.json`; `docs/X07a-platform-ruling.md` section 5.2. Runs (logs under
`~/.cache/line06/f8rev/`): `tests/test_f8_*.py tests/test_k05_replay.py tests/test_x07a_*.py` 170 passed (122 + 30 + 18,
the measured counts); three probe scripts (`probe.py`, `probe2.py`, `probe3.py`, scratch, not committed) for M1, M2,
S1 and S3.

## Verdict

**Not ready to merge; ready after one fix round (F8-FR below), then subject to ADR 0067's acceptance.** The core is
sound. D2's members are classed as D9 says and absent members are not hashed, so every v1 `structural_sha256` stands
(F0 M3/M4, E-F8-10). The dispatch cannot send a v1 bundle to the v2 reader: no v1 writer emits `bundle_format`, and
E-F8-1's 52 x 4 pinned reports go through the dispatch. D4 embeds only when every source is `permitted`, and
`embeddable` refuses the empty case. Rights enter no hash: `r0_projection` is an allow-list that never names the v2
documents, and E-F8-3 flips embedding both ways with identity fixed. Step 5 compares only `descriptor_sha256` and
`self_sha256`, and `status` is outside `descriptor_sha256` (`registry/descriptor.py:188-191`). The D7 loader enforces
E-D7-3. The D7 fold matches section 5.2 word for word (E-D7-1 to -5, including the heading, the OQ5 closure and the
row-5 label).

Two defects block the merge. Both are cases where the new path crashes and the v1 path, or D5 step 2, gives a typed
report. First, the v2 integrity check raises on a malformed `records-index.json` or `data-lock.json` (M1). Second, the
served `reproduce` with a rerun, and the CLI's `inspect`, read every bundle with the v1 reader, so a v2 bundle or an
unknown-format bundle raises `TypeError` (M2). Six should-fix items, mostly about test strength and the record, go in
the same round.

## Findings

### Must fix

**M1. Step 1 raises on a tampered lock or records index. It does not report the failure.**
`src/openflowsheet/run/bundle_v2.py:253-265` (`_cross_check_v2`) parses both files and indexes into them unguarded.
The hash check above has already flagged them, but this code still runs on them. Measured through `run.replay.replay`
on a GP-C1 factory bundle:

| tamper | result |
| --- | --- |
| index not JSON | `JSONDecodeError` |
| index `[]` | `AttributeError` |
| index `{"records":[{}]}` | `KeyError('sha256')` |
| lock not JSON | `JSONDecodeError` |

For comparison, `garbage` written into each of the ten artifacts of a 0.3.0 v1 bundle gives
`inspected_archived_results` with `integrity.ok False`, ten out of ten. So D5 step 1 ("`verify_bundle`, unchanged" in
behaviour: a failing archive is reported and not re-run) does not hold for the two documents F8 added. Note F8-WO3-11
("step 1 never raises on a tampered archive") states a property that is false. **Fix:** parse both files under
`try` (`ValueError`). Require `index` to be a dict whose `records` is a list of dicts, each with a string `sha256` and
a boolean `embedded`. On any failure, append the file name to `tampered` and return. Correct WO3-11 in the decisions
file.

**M2. The served `reproduce` (rerun) and the CLI `inspect` bypass the dispatch and crash on any bundle that carries
`bundle_format`.**
`src/openflowsheet/application/revision_replay.py:312-315` (`_rerunnable_manifest`) and
`src/openflowsheet/application/cli.py:248-249` (`command_inspect`) call `run.bundle.verify_bundle` and `read_manifest`
directly. Measured with `reproduce_bundle` on the TH-C1 factory bundle:
- v2 bundle, `rerun=False`: an inspected report (dispatch works).
- v2 bundle, `rerun=True`: `TypeError: Environment.__init__() got an unexpected keyword argument 'registry'`.
- The same bundle marked `openflowsheet-bundle-v3`, `rerun=False`: `bundle_format_unsupported(openflowsheet-bundle-v3)`.
- The same bundle marked `openflowsheet-bundle-v3`, `rerun=True`: the same `TypeError`.

The job runner (`jobs/runner.py:887`) catches only `BundleError` and typed ends, so a `reproduce` job with `rerun: true`
ends untyped. D5 says "one dispatch line in `run/replay.py`". That premise assumed every entry point goes through
`replay`, and the application layer contradicts it. CLAUDE.md requires "unimplemented capabilities return explicit
unsupported results". This is exactly the forward-compatibility case D5 step 2 exists for: a 0.6 installation handed
a bundle from a later line.

**Fix:**
1. In `_rerunnable_manifest`, before `verify_bundle`: if `replay_v2.bundle_format(directory) is not None`, stage
   `compare` and return `Reproduction(_inspected(directory, reason))`.
   - For `openflowsheet-bundle-v2`, the reason is
     `coded_reason(Coded("construct_unavailable", {"construct": "v2 bundle rerun", "foundation": "F8-WO6"}))`, since
     no v2 rerun is wired before WO6.
   - For any other value, give no extra reason: the report already says `bundle_format_unsupported`.
2. In `command_inspect`, read a v2 bundle with `bundle_v2.read_manifest` and `verify_bundle` (`RunManifestV2` is a
   `RunManifest`). Refuse any other `bundle_format` with the coded reason and a non-zero exit.

No v1 byte moves, because v1 bundles carry no `bundle_format`. Log the construct name as a DECISION.

### Should fix

**S1. The unknown-format report drops the integrity failure from its reasons.** `src/openflowsheet/run/replay_v2.py:214-228`.
Measured: a `-v3` bundle with a garbage `solution-state.json` gives `integrity.ok False` with reasons
`('bundle_format_unsupported(x-v3)',)` only. D5 accumulates reasons in step order and step 1 comes first. The v1 path
and the v2 path both add `FAILED_INTEGRITY` whenever integrity fails. **Fix:** reasons become
`(FAILED_INTEGRITY, bundle_format_unsupported(...))` when `not integrity.ok`. Also guard
`document.get("artifacts")` being a non-dict (it is treated as empty and every file is `unexpected`). Amend WO3-3.

**S2. D5 steps 3 and 4 on the v2 path, and the order across steps, are untested.** `src/openflowsheet/run/replay_v2.py:183-187`.
Every v2 test replays in the recorded environment under a known policy, so these mutations survive:
- Swapping `policy_reasons` and `environment_reasons` at l.183.
- Dropping the `mode == "exact_replay"` guard at l.185. A changed lock plus a changed built-in would then become
  `compatible_reproduction` and rerun on a changed lock, which ADR 0007 D4 forbids.

**Fix:** add three tests:
- (a) The other registered architecture plus a changed used built-in gives `compatible_reproduction`, with reasons
  (the environment's, then `extension_changed(...)`), rerun and compared.
- (b) A changed lock plus a changed used built-in gives `inspected_archived_results` / `NOT_RUN`.
- (c) An unknown policy plus a missing used extension plus one absent referenced record gives `NOT_RUN`, with reasons
  exactly (policy, `extension_unavailable`, `data_unavailable`) in that order.

Run the two mutations above as controls and record them.

**S3. E-F8-6's first clause is vacuous on this line, and the record does not say so.**
`tests/test_f8_replay_v2.py:466-472`. Measured: the factory's reruns record `usage == ()` for both GP-C1 and TH-C1
(nine `extensions_used` rows each), so `set(usage) <= declared` holds for any manifest. The hidden-resolve control
(l.475) is the real evidence. **Fix:**
- The test asserts `usage == ()` with a comment naming WO6, so it fails when real v2 runs arrive and the clause has
  to be judged for real.
- The manifest's E-F8-6 row and its limitations say "holds vacuously (empty usage set); the undeclared-use control is
  the evidence".

**S4. Amendment 12's "Not unchanged" omits the R4-G3 moves.** `docs/adr/0019-application-contract-v1.md:334-337`.
F8 re-pinned nine R4-G3 responses: `SNAPSHOT_F8`, F8-WO1b gate numbers (`solve`, `reproduce`, `submit_job`, `get_job`,
`cancel_job`, `list_jobs`, `list_job_events`, `wait_job`, `get_job_result`). Every sibling amendment states its R4-G3
effect. Also at l.329, "D5's other codes" means ADR 0067's "New catalogue codes", not a D5 list. **Fix:**
- Add the R4-G3 sentence: which responses moved, the `SNAPSHOT_F8` table, and that `without_f8` returns each response
  to its prior pin exactly.
- Replace "D5's other codes" with "ADR 0067's other new codes".

**S5. Per-platform records: close leftovers (a) and (b)(i) now, while no record exists.**
`src/openflowsheet/run/platform_refs.py:151-156, 177-198`.
- **(a)** `select_reference` loads `<case>.json` and refuses a per-platform record whose `reference_sha256` is not
  that file's `record_sha256`. That is two lines, and it closes the window between a re-record and the sweep. It is
  fail-closed and costs one file read.
- **(b)(i)** Fix `path` as an RFC 6901 JSON Pointer into `artifacts` (for example `/solution-state.json/...`; the
  test now writes `solution-state.json/...`). `invariant_problems` checks that the value at `path` is
  `reference_value` in the reference record and `platform_value` in the per-platform record.
- **(c)** Add a test `set(replay.REGISTERED_PLATFORMS) <= set(PLATFORM_IDS)`, so a registered pair without an id
  cannot be dropped silently.
- **(b)(ii)** is recorded as an obligation for the first real per-platform record, not built now: "the record departs
  from the reference beyond policy only at its departures", which needs the record to name its policy. Put it in
  `F8_DECISIONS.md` and in D7's WO5 row note.

Mutation controls: drop (a), and swap `reference_value` and `platform_value` in a departure. Each must fail one test.

**S6. The evidence manifest is re-taken at the merge head, not carried.** `evidence/F8/32981fb3…/manifest.json` is
`status: tested` with a `fail` row (`F8.INHERITED-RED`). After wp/F2 is merged into wp/F8:
- Re-take the manifest at that head with `test_j16` green and the S3 wording.
- Set `HARVEST_SIZE` from a run of `test_m07a_harvest`, not from the sum (110, 1184, 154) of F8-CO-4. A shared or
  renamed row would make the sum wrong.

### Notes

- **N1.** A v2 manifest with `bundle_format` stripped reaches the v1 reader and raises the same `TypeError`. This is
  pre-existing: `run/bundle.py`'s `read_manifest` builds `Environment(**…)` before its unknown-member check. Optional
  hardening, which moves no v1 byte: catch `TypeError` there as `BundleError`.
- **N2.** `"bundle_format": null` is reported as `bundle_format_unsupported(None)`, a Python spelling. It is cosmetic.
- **N3.** `replay_v2._compared` copies v1's comparison loop and imports three private helpers of `run/replay.py`.
  `bundle_v2` imports two private cross-checks of `run/bundle.py`. Both are accepted for this line (the byte-identity
  proof). A later extraction of the shared loop is a refactor provable by E-F8-1.
- **N4.** `_v1_artifacts` (`replay_v2.py:345-350`) excludes only D3's three names and `records/`. Two obligations:
  WO4 must add `run-evidence.json` (D6: outside every identity), and TX must add `decision-records/` and
  `trajectory/`. Otherwise a rerun's evidence document would be compared as an artifact.
- **N5.** D6's "explicit exclusion list of `r0_projection`" is realised by the projection's allow-list. That is
  stronger, and it is accepted.
- **N6.** `write_bundle` does not check that each `extensions_used` row appears in the snapshot with equal SHAs.
  `verify_bundle` does not re-check the snapshot's `registry_sha256` against `environment.registry`. Both are cheap
  guards in WO2-3's spirit, and WO6 is the natural place for them.
- **N7.** E-D7-4 (a bitwise expectation never takes a per-platform record) has no enforcement point, because nothing
  marks a case as bitwise. This is for the first registration. D7 still carries "unless ADR 0025's existing layout
  already names one", which is moot after E-D7-2. Delete it at acceptance; this is optional.
- **N8.** E-F8-1's `self` and `other_platform` scenarios reach the comparison for only 8 of 52 bundles. 44 stop at
  "declared kinds not supplied" (`T08-numerical-policy-v2`, no `variable_kinds` in the script's `Rerun`). The exit
  (byte-identical reports) holds, and F0 M7 covers the real comparison. Supplying kinds in
  `scripts/f8_v1_replay_reports.py` would widen it; this is optional.

## The ruling batch

1. **F8-WO1-1 (`bundle-v2.schema.json`, `unevaluatedProperties`): keep.** R-1032's structure for the same ADR 0025
   A1(d) case. Closure is kept and tested: an unknown top-level or `environment` key is refused. Every committed v1
   manifest validates, and the v2 policy bytes `6b449911…` are unchanged. The schema declares draft 2020-12, so
   `unevaluatedProperties` is in force.
2. **F8-WO3-1 (step 7's served stack): keep for this line, and change ADR 0067's WO6 row (an edit before acceptance,
   on the acceptance card).** The reading is honest and measured: the v1 revision's binder reads the packaged legacy
   YAML, whose bytes equal the embedded records. Nothing in `src/` consumes `served_stack`. WO6's acceptance becomes:
   - "E-F8-2 on real v2 runs";
   - E-F8-4's embedded clause with a v2-compiled rerun that reads `served_stack` while the local store lacks the
     record;
   - E-F8-6's first clause on a non-empty usage set;
   - the application's `reproduce` of a v2 bundle reruns through `served_stack`, with the project's store (WO3-8) and
     a `RerunV2` (WO3-5), replacing M2's interim refusal.
3. **F8-WO3-2 to WO3-10: keep all, with two amendments.**
   - WO3-2 (`differences`, so the verdict follows the comparison): keep.
   - WO3-3: keep, amended by S1.
   - WO3-4 (built-in by the current registry's `origin`, "of the running distribution"): keep.
   - WO3-5: keep. The rule is fail-closed, and WO6 owes the `RerunV2` (item 2).
   - WO3-6 (test-only, reaches into `_entries`): keep.
   - WO3-7: keep. The order is right on reading, but it was unpinned; S2 pins it.
   - WO3-8: keep for this line. WO6 owes the project store (item 2).
   - WO3-9: keep.
   - WO3-10: keep. The ADR marks only `extension_use_undeclared` (bug) and the notices, so `refusal` for the other
     three follows the ADR's list.
4. **F8-WO5-1 to WO5-4 and R1 to R4: keep.** WO5-3 and WO5-4 are superseded by R4 and R3, as logged. R3's
   measurement is right: the counters are cumulative, and the last event's three solver counters are R0. The
   leftovers are ruled in S5:
   - (a) is closed in the fix round;
   - (b) is split: (b)(i) is closed now, (b)(ii) is an obligation for the first real per-platform record;
   - (c) gets a test.

   Neither (a) nor (b) is merge-blocking on its own, because no per-platform record exists anywhere and the sweep
   catches a stale one in the same commit's CI. Both are cheap, and (b)(i) fixes the format before the first record.
   So both go into this round.
5. **F8-CO-1: change (S4).** **F8-CO-2: keep**: `not_applicable` with the reason in `value` is the schema's honest
   value. **F8-CO-3 and F8-CO-4: keep**, with the pin measured at the F2-into-F8 merge (S6).

## Fix-round work order F8-FR (one Opus engineer, `wp/F8` after wp/F2 is merged into it, rules `docs/LINE06_RULES.md`)

1. M1: guard `_cross_check_v2`, and add a test parametrised over the four tampers in M1's table, through `replay`.
   Correct WO3-11.
2. M2: dispatch in `_rerunnable_manifest` and `command_inspect`. Add tests: `reproduce_bundle(rerun=True)` on the
   factory bundle and on a `-v3` copy returns inspected / `NOT_RUN` with the stated reasons, and CLI `inspect` on both
   does not raise. Log the construct name.
3. S1: the integrity reason in `_unsupported`, with a test and an amended WO3-3.
4. S2: tests (a) to (c), with the two mutation controls recorded.
5. S3: the explicit `usage == ()` assertion.
6. S5: (a), (b)(i), (c), with their controls, and (b)(ii) logged as an obligation.
7. S4: the Amendment 12 text.
8. In ADR 0067's WO6 row, the obligations of ruling 2, marked as an edit before acceptance (DECISION F8-FR-1).
9. S6: at the head, F0, the surface suites, `tests/test_f8_*`, `test_k05_replay`, the MSG suites, `test_x07a_*` and
   the harvest test; `HARVEST_SIZE` from the run; then re-take the manifest with the S3 wording.

The round moves no served digest. M2 changes behaviour only for bundles that carry `bundle_format`. If any surface
digest moves, it is a STOP.

## What needs the user

Nothing beyond the ADR 0067 acceptance card, which already goes to the user. No ruling here changes an Accepted
decision: ADR 0067 and Amendment 12 are Proposed. The card should list the edits made before acceptance:
- the D7 fold (F8-WO5-0);
- the WO6 row (ruling 2);
- optionally N7's deletion.

## Not examined

- The F2 part of the branch (`docs/reviews/F2-review.md`).
- The schema files beyond the members named above.
- The support-envelope rows' content (CO-4).
- `records/stack.py`'s layer resolution, beyond what the tests exercise.
- `jobs/runner.py`'s handling of the new artifact kinds (no v2 bundle reaches a job in 0.6, apart from M2).
- The R4-G3 and MCP digest values themselves (taken from the passing surface suites).
- ruff and mypy were not run.
