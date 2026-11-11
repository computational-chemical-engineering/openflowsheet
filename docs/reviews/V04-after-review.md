# V04-after: review (single reviewer pass)

Date 2026-11-11. Branch `wp/V04-after`, head `2d200d63`, range `main..HEAD` (`main` = `b6cdf552` = `v0.4.0`).
Design: `docs/reviews/HOSTMOVE-ruling.md` (R-1020, RP amendment A-13, T06 amendment H-1); RP §7.4 and §17.5 (A-12's
F-4 and F-5). Build logs: `docs/RP_DECISIONS.md` from "## 0.4.0 after the tag (V04-after, SMM-TR09)" (`:646`).

Read: the ruling in full; R-1020; A-13 as applied in RP; R-149; the diffs of `scripts/m05_retake_diff.py`,
`tests/support/m05_replay.py`, `scripts/m05_wo8_runs.py`, `benchmarks/t06/ensemble.py`, `scripts/t06_ensemble.py`,
`benchmarks/registry.yaml`, `scripts/m03_ipopt_inventory.py`, `scripts/v0_2_gate.py`, the envelope and catalogue rows,
the fixtures, the T06 test edits and the T06 spec amendment; the HM test modules' structure and HM-10's count;
`tests/t08_rename_substitution.py`; `tests/test_t08_ptc_r1_diagnostic.py`.

Run on SMM-TR09 (2950X) at `2d200d63`:
- the five proofs, `scripts/m05_retake_diff.py --digest-only <v0.4.0 archive>/…/trust-region-study-<case>
  benchmarks/m05/records/trust-region-study-<case> --old-version 0.4.0 --old-host SMM-TRS2`, in `.venv-nlp` with the
  ruling's environment line: five `PASS` lines equal to HM-19's (41/146/20/4, 79/320/35/7, 70/215/20/4, 91/285/26/3,
  37/124/20/4), each `path=0 platform=0 other=0 environment=host host=3`, each exit 0;
- an independent leaf diff (a walker of my own, not the tool) of every file under the five stems, `v0.4.0` against
  HEAD: no leaf added or removed; 1090 differing 64-hex leaves; the only other differing leaves are `machine`, `cpu` and
  `cpu_count` (5 each, the sidecars), `openflowsheet_version` (22 = 4+7+4+3+4), `run_commit` (5, provenance) and
  `wall_s` (126). No number moved;
- F0, `scripts/corpus_identity.py --check`: `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 35/35` (HM-37 reproduced);
- `scripts/t06_ensemble.py check` and `check --holdout`: each exit 1 with the three differences of the build log
  (HM-34 reproduced);
- `generator.py` and `syn001.py` with `openflowsheet` replaced by `process_runtime` hash to `7f426aa9…` and
  `67e47281…`, R-149's registered old values. The live files hash to R-149's new values, and both published start
  sets hold the old ones, at `v0.1.0`, `v0.2.0`, `v0.3.0`, `v0.4.0` and HEAD;
- `hostmove_host_leaves.py --check`: PASS. HM-26's `git diff --quiet c57c2ca0 HEAD -- …`: exit 0;
- `tests/test_t08_ptc_r1_diagnostic.py`: 2 passed, 6 skipped (SF-1).

## Verdict

**Accept after fixes (MF-1).** The host move weakens neither G10 nor replay identity nor any registered criterion.
G10's replay (`m05_wo8_runs.compare`) and AM-23 are untouched and exact; the sidecar keeps its three host keys; the
reactor fingerprint, every experiment key and every store are unchanged. The new class `host` exists only with
`--old-host`, admits exactly R-1020's closed list, holds each re-take value to what the running host measures through
the writer's own function, keeps its leaves out of the digest map, and leaves every other leaf bitwise. Without the
flag the tool is the one at `c57c2ca0` (HM-03, HM-18). No committed number changed: the five proofs reproduce, and an
independent walker agrees. RP §7.4 holds: 0.5.0.dev0, the working envelope `v0.2-envelope-dev`, and the five re-taken
and proved with `--old-host`. R-1009's widened grammar is a superset, and the four released verdict documents read
equal under both patterns. REL.A04 holds for the reason given: `LIMITATION` is read only inside `verdict_document`
(`scripts/v0_2_gate.py:386,423,532,541`). The one blocking item is procedural and cheap to close: the reference class
moved although its own proof, HM-34, fails.

## Must fix

- **MF-1: `ref-x86-64` moved while HM-34 fails** (`benchmarks/registry.yaml:2686-2689`, `scripts/t06_ensemble.py:127-142`;
  ruling `docs/reviews/HOSTMOVE-ruling.md:282`). The ruling stops WO-H5 on any failure of §7.3, and "the class does
  not move". `a7606285` moved it, and HM-34 then failed: `check` and `check --holdout` exit 1 on SMM-TR09 with
  `generator_sha256`, `provider.implementation_sha256` and `host.cpu_model`. The failure is R-149's, not H-1's (ruling
  (a)). Remedy, the default of (a): `check` undoes R-149's substitution on the regenerated document before both
  comparisons, as A25's and A99 (a)'s tests do. HM-34 is then rerun live and must print `identical but for
  host.cpu_model (AMD Ryzen Threadripper 2950X 16-Core Processor)`, exit 0, for both files. Conditions:
  1. it replaces exactly R-149's two registered pairs (`509b01fb…` to `7f426aa9…`, `4e4c37cc…` to `67e47281…`;
     `tests/t08_rename_substitution.py:33-43`), and only where the live value is the registered new one. Any other
     value stays a difference, reported or failing as today. No `assert` as control flow (`renamed_back_starts`
     asserts, which `python -O` strips): an explicit comparison;
  2. two synthetic tests beside HM-33 in `tests/test_t06_hostmove_ref_class.py`: new hashes in the regeneration, old
     in the published file, only `cpu_model` differing, gives exit 0 and the line; a generator hash that is neither
     registered value gives exit 1 on `ref-x86-64`;
  3. one design-lane line that records it, as an addendum to the ruling's §7.3 item 3 citing R-149's "their tests
     compare the live hashes substituted back". No new register entry: R-149 registers the substitution, R-1020 the
     class.

  If (a) is not taken, the ruling's own alternative applies: revert `a7606285` and `e6a43e87`, so that the class does
  not move, and F0's M4 is again not judged on SMM-TR09.

## Should fix

- **SF-1: a host-conditioned judgement still lapses on the RC host, outside H12's ten modules**
  (`tests/test_t08_ptc_r1_diagnostic.py:35,43`; ruling `:271` (§7.3 item 1), `:320` (§8); R-1020's "Watch for"). The
  PTC-R1 diagnostic reads `benchmarks/t08/ptc_r1/results-<machine_class>.json` and returns nothing unless the
  committed CPU model is the running one (ADR 0007 F1). On SMM-TR09 the class now resolves to `ref-x86-64`, the CPU
  guard fires, and 6 tests skip with "no committed PTC-R1 results for ref-x86-64 on this CPU model". Before the branch
  they skipped there as `unregistered(x86_64)`, so the branch changes nothing; but the bitwise re-run of the committed
  PTC-R1 record now runs on no live host, and R-1020 names exactly this case ("a class-conditioned test skipping
  there"). The skip is reported, not silent, and PTC-R1's RC item runs on the CI dispatch, so no gate is weakened.
  Remedy: one line in the ruling's §8 classifying it (conditioned on the CPU by ADR 0007 F1, not by the class; skips by
  design on a CPU without its own record). Default: classify only. A record for the 2950X is T08's choice, at the first
  SMM-TR09 cut at the earliest.
- **SF-2: HM-25 is not met as written** (ruling `:518`; build log `docs/RP_DECISIONS.md:771-778`). It asks
  `scripts/m03_nlp_check.sh` to exit 0; the bare script exits 1 on the pre-existing `mpmath` collection error (ruling
  (b)). The two inventory legs pass, with the host-state line. Remedy: rerun HM-25 in RP §6.5's form, as step 14 runs
  it (`scripts/m03_nlp_check.sh <prefix> <cache> -- <the modules that grep -l 'mark.nlp' tests/test_*.py lists>`,
  `scripts/release_rc_local.py:1505`), and record its exit 0 and the host-state line in the build log. No code change.

## Rulings on the open items

- **(a) HM-34.** Verified, with one correction. The live self-hashes are R-149's new values, and the published start
  sets hold the old ones, at every tag from `v0.1.0` to `v0.4.0`. So `check` exited 1 ("same host: a defect") on the
  generating host, SMM-TRS2, at every release since `v0.1.0`. On every other host it exited 0 and reported, which is
  why CI never saw it (`.github/workflows/ci.yml:360-361` runs it on runners). "Every host" in the build log
  (`docs/RP_DECISIONS.md:821`) should read "on the reference host; reported elsewhere". The suggested change is
  admissible under R-149: R-149 registers the substitution and states that the start sets are compared "substituted
  back" (`docs/decision-register.md:3486`). Undoing exactly that pair moves no value and hides no other difference;
  it is what A25's test already does. It belongs in this package: HM-34 is this package's assertion, and §7.3 forbids
  the class move while it fails. Default: MF-1.
- **(b) `mpmath` in the nlp tier.** Neither the lock nor marks, and not in this package. Adding `mpmath` to
  `benchmarks/m03/nlp-test.lock` moves `distributions_sha256` in every M05 environment sidecar, because the
  nlp-test-tools are on the G10 re-takes' path (`docs/RP_DECISIONS.md:674`). AM-23 would then fail on the five and
  REAL until re-taken: a G10 re-baseline for a collection error. It would also break HM-26 here, which diffs
  `benchmarks/m03/` whole. Marks do not help: the four modules hold no `nlp` test, and the import fails before markers
  are read. RP §6.5 (R-907) already selects the `mark.nlp` modules and step 14 uses that form, so the release path is
  unaffected. Default: in a later M03 or RP maintenance package, `m03_nlp_check.sh`'s pytest leg defaults to §6.5's
  module list when it is given no pytest arguments. Here: SF-2 only.
- **(c) The fingerprint and attempt CPU leaves held to the running host when unchanged.** Right; keep it. WO-H1 (c)
  and (d) state no condition, (b) states one. The asymmetry can only make a proof fail, never admit: it fails a REAL
  proof run on another machine than the one that took the re-take, which RP §7.1 never does. Reversing it buys
  nothing. Pin the choice with one test (an unmoved REAL-like pair with the running host patched elsewhere fails,
  naming the re-take leaf), so that the one-line reversal cannot pass unseen.
- **(d) A90 not marked.** Mark it **(H-1)**, and A98 (b) as well (`docs/derivations/T06-corpus-spec.md:855,868`).
  H-1's items 3 and 4 amend both; WO-H5's list of places was shorter than H-1's own items. Note-level.
- **(e) 36 against 41 files.** The commit is right and the ruling's count is stale. The five stems hold 42 files. The
  same-host re-takes of 0.3.0 and 0.4.0 changed 36, because the sidecars did not move; this one changed 41, with
  `loop-s.ledger.json` byte-equal. HM-21 (every path under the five stems) holds. Default: an erratum line at ruling
  `:115` and `:495`: "41: the 36 of a same-host re-take and the five sidecars". Note-level.

## Notes

- **N-1: L-WS-2's sentence beyond RP's default** (`benchmarks/t08/support_envelope.yaml:677-690`). Accept. It states a
  limitation, not a capability; it is what `tests/test_x02_wo2_contract.py:314-336` asserts (selection explicit,
  status `rejected`, reason `route`, the solve as without it, replay `MATCH`), and `route` is in ADR 0070's reason set.
  It narrows the claim.
- **N-2: WO-H2 re-took fresh at `64074f8a`** rather than reusing H3's files, the work order's first option. Accepted:
  `run_commit` then names a commit that holds the proof tool, and both sets print the same five lines.
- **N-3: `release/lines/0.5.json` (`inherits: "0.4"`) is not written.** RP §7.4 says "then", not "in the same change".
  It needs an owner before the next gate-set change on `main`.
- **N-4: H-1's ensemble evidence is aggregate.** HM-38's 437 `SUCCESS` and 3 `F-FALSE-SUCCESS-CAUGHT` equal REL040's
  record on SMM-TRS2 (`evidence/REL040/84c665477b512548f38a6335f51648732b1fe5bb/rc/ensemble/rc-ensemble-ref-x86-64.json`),
  and F0's M4, M6 and M7 show identity per state, trail and mode. A per-start comparison of step 6's record against
  REL040's costs one script at the first SMM-TR09 cut, where step 6 runs anyway.
- **N-5: where MF-1's substitution lives.** `scripts/t06_ensemble.py` already puts `tests/` on its path and imports
  from it, so reusing `tests/t08_rename_substitution.py`'s constants is in the file's pattern. One rule for the script
  and the tests, wherever it lives, is the point.

## What this review does not establish

- That AM-23 passes at HEAD (HM-20), or HM-35, HM-36 and HM-38: not rerun, taken as the build log records them.
- That REAL reproduces at the first SMM-TR09 K3 (WO-H4).
- The full default tier or the gate on SMM-TR09, or CI at HEAD.
- The bodies of HM-22 to HM-24 and HM-30 to HM-33 beyond their structure, and the docs-site and support-matrix
  regenerations (their generators' `--check` results are in the build log).

## Frank

Nothing to decide. MF-1's fix applies R-149 as Frank approved it. The ruling's information line for the first SMM-TR09
cut (§12) stands.
