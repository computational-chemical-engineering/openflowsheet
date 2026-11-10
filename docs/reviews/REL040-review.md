# REL040 prep (`wp/REL040p` at `5d0c4121`) — the package's single `reviewer` pass

Design lane (`reviewer`), 2026-11-09. Brief: `docs/briefs/REL040-reviewer.md`. Read in the `rel040p` worktree against
`docs/reviews/REL040-s6-ruling.md` §2, §3, §6, §8 and §11. Scope: WO-1 (`5d862052`), the class `path` (`81716c0a`),
WO-3 (`cb2a3a6c`), WO-4 (`4ba52083`), WO-7 (`26ad9d7f`), RP.L11 (`9743871e`), the x05 entry (`c46ef9fc`), S6dbg F-A
(`3e25b294`), the test-only commits `0282e4d6` and `d7258775`, Q-S6e (`c8be15dc`), and the RP text `4f8deeb2` and
`0b62c12d`.

## Verdict

**Sound, with one should-fix (S-1). One fix-round item before the merge. Nothing needs Frank.**

The tools do what the ruling's rules say, and they fail closed wherever I pushed on them. The one gap is between the
REAL proof's rule and §2's claim for it. §2 says the proof "establishes that nothing moved except the host's platform
string at its one bound leaf, and the digests that string feeds". The tool admits *any* digest move that is a
bijection. WO-7 closed that gap for log digests only. The same argument (§11.3: content that no key or fingerprint
derives must be equal, not relabelled) applies to three more value digests. A demonstration follows under S-1.

## What I ran (TRS2: load 12–15 of 48, serial, one process)

- At `5d0c4121`: `tests/test_m05_retake_digest_only.py`, `tests/test_m01_idaes_retake_diff.py`,
  `tests/test_m07_journey_record.py` and `tests/test_m05_wo9_gates.py`. Result: 118 passed, 3 deselected.
- The live REAL proof, run on the committed stem against the kept re-take `.cache/s6r/real-0b62c12d/`, reproduces the
  logged line byte for byte. The 103 changed digests are exactly the set the platform feeds: the fingerprint digest
  (1), the experiment keys (48), `request_sha256` (48), the coupling records' digests (4), `artifacts.experiment_store`
  (1) and `artifacts.ledger` (1).
- **S77's pair**, run with the head's tool (`git archive 56fb2fa~1` against `56fb2fa`, the five stems, no options),
  gives PASS 42/80/71/92/38 with `path=0 platform=0 other=0 environment=equal`. That is WO-1's logged result. S6R-27 (4)
  asked for this check after WO-7, and the log did not carry it; it is now evidenced.
- **The S-1 demonstration.** I copied the live re-take and moved each of the 16 coupling iterations'
  `inner.state_sha256` to a new, distinct value. The proof printed
  `RETAKE-DIGEST-ONLY PASS … changed-digests=119 … version=0 platform=4 other=0 environment=equal`.

## Findings

**S-1 (should fix): value digests are relabelled, not compared.** `scripts/m05_retake_diff.py:170` (`LOG_DIGEST`) and
`:198–204`. Three digest leaves hash computed values that the record holds nowhere in clear:
- coupling `.iterations[i].inner.state_sha256`, the inner converged state;
- coupling `.iterations[i].inner.constants_sha256`;
- the ledger's `[i].requests[j].inputs_sha256`: 151 leaves, many of them in-process calls with no clear inputs.

No experiment key, fingerprint or code identity feeds any of them. None of them moved in REAL's live re-take or in
S77's pair (both measured above). Under the tool at `5d0c4121`, a one-ulp change in an inner-state member that reaches
no walked clear leaf passes as `digest`. A uniform or bijective move of all such leaves passes too, as demonstrated.
That is below §8.0's stated resolution ("one ulp in one leaf"). **Fix:** WO-R1.

The other moved-able digests are different in kind. They are keys, request and record digests, and code or input
identity (`boundary_sha256`, `trf_module_sha256.*`, `trsp_executable_sha256`, `revision_sha256`, `truth[].sha256`,
`model.artifact_ref`, and so on). K3's code may legitimately move them (R-458's design; S77's pair moves
`boundary_sha256`), and the bitwise clear leaves are their guard. Leave them in the map. §2's sentence should say so
(WO-R1 (d)).

**N-1 (Q-S6e): reading at the journey's commit, ruled below.** `tests/test_m07_journey_record.py:211`. Optional: add
`git merge-base --is-ancestor <commit> HEAD` before `git show`. Without it, a local object store still holding a
deleted scratch commit (this package made and deleted J′ twice) can satisfy the test, which CI's fresh clone would not.
The docstring could also note that the test needs full history. Every CI job that runs pytest has `fetch-depth: 0`
(`ci.yml:93, 226, 975`). A `git archive` scratch repository, the method G3 used, fails these 3 cases.

**N-2: WO-3's comparator is Python `!=`, not bitwise.** `scripts/m01_evidence_manifest.py:887–892`, as used by
`scripts/m01_idaes_retake_diff.py:64`. Under it, `-0.0 == 0.0`, `1 == 1.0` and `True == 1`. The ruling (§3, WO-3) ties
the proof to step 11's own comparator on purpose, so the proof is exactly as strict as W22 (b). Record it as that
comparator's limit; do not change it on this branch. The docstring's "the comparison is exact" (`:11`) should say
"step 11's equality".

**N-3: REAL's pass rule beyond `PASS` is read by eye.** Given `--old-version` together with `--old-platform`, the tool
can print `PASS … environment=distributions` (`scripts/m05_retake_diff.py:495–497`). A-11 requires
`environment=equal`, and an operator who copies the five's command could miss it. Optional: refuse `--old-version` when
any coupling pair carries `PLATFORM_PATH`.

**N-4: step 15 chooses the M05 record by directory, not by R3.** `scripts/release_rc_local.py:538–539`. It uses
`journey/<J>/m05/` whenever that directory exists, where A-11 item 4 says "for a re-run". The two are equivalent for
the three committed journeys, all of which re-ran R3. Optional: read `rungs.R3.m05_record.carried_from`.

**N-5: child logs are lost when the run raises.** `scripts/m05_wo9_real.py:460–463`. `keep_child_logs` runs only after
`run_real` returns, so a crashing re-take loses the most useful logs. Optional: `try/finally` inside the
`TemporaryDirectory` block.

**Checked and sound:**
- **WO-1.** `platform` admits the one exact leaf, with old equal to p and new equal to the running platform. Every
  other fingerprint leaf is pinned, digests included, because they enter the map as x→x first. The binding holds on
  both sides. A platform on a non-reactor unit is `other`.
- **WO-1 (b), the archive walk.** Partners are paired by relabelled name. A missing, extra or unmapped file is
  `other`. The comparison runs leaf by leaf, with timing in attempts only. Dict key order and int/float type are
  compared strictly.
- **The class `path`.** It is resolved under the completed map, and every 64-hex run must be a `<k[:2]>/<k>` with an
  image.
- **WO-3** admits only `environment.platform`, with both pins, and the two registered inputs at the tree file's
  SHA-256, tracked and unmodified. Everything else is `other`.
- **WO-4's fields.** Their glob and layout match `ExperimentStore`.
- **RP.L11** matches ADR 0074 D2 (a k-digit number is the k-th letter followed by its digits; more than 26 digits and
  leading zeros are refused) and is applied to `role: gate` only.
- **The x05 entry** matches the logged intent.
- **F-A** forwards the overrides and turns an undecided start into an explicit `SystemExit`.
- **A-11 in RP §17.4** is §6 verbatim, with item 7 added after item 6. All 11 quoted replacements are present, the
  replaced text is gone, and §7.1's clean-worktree text is §11.2 verbatim and in place.

## Ruling on Q-S6e

**Confirmed: read the offered file at the journey's own `commit`.** A2.3 (R-454) states a fact about the run. The
offered file was tracked and unmodified *when R3 was offered it*, and it hashed to `offered.sha256`. The new test
checks all three facts at that commit:
- `git show` fails for an untracked path;
- the blob at a commit is unmodified by construction;
- the sha256 and the anchor are read from that blob.

The old reading checked the same facts against the current tree. That was correct only until the first re-take of the
record it names, which A-11 now makes every cut's. Nothing in the release path depended on the current-tree binding:
C = J + journey carries J's REAL record, so the newest journey's offered file is C's by construction. N-1's ancestry
assertion is optional.

## O-6 (other tests bound to the committed records)

S6R-29 settles the default tier exactly: the same 19216 ids, and only the three Q-S6e cases changed status. By grep,
`tests/test_m01_idaes_conformance.py`, `tests/test_m05_wo9_gates.py` and `tests/test_m07_journey.py` read the committed
records, and they passed at J′. **Not examined:** CI jobs outside the default selection (`rc-coolprop` 17b, browser,
ensemble), and nlp- or reactor-tier tests outside steps 11 and 14's selections.

## Fix-round work order (build lane, `wp/REL040p`, before the merge)

**WO-R1 (Opus).**
- (a) In `scripts/m05_retake_diff.py`, widen WO-7 (a)'s exact class to leaves at paths ending
  `.inner.state_sha256`, `.inner.constants_sha256`, and `.requests[<n>].inputs_sha256`. They are compared exactly,
  never enter the map, and a difference is `other` naming the leaf and both values. Update the module docstring.
- (b) Add tests in `tests/test_m05_retake_digest_only.py`, on synthetic stems:
  - each of the three moved alone gives `FAIL`, `other=1`, naming the leaf;
  - every `state_sha256` moved bijectively gives `FAIL`, `other=<n>`. This case discriminates, because it passes at
    `5d0c4121`.
- (c) Lines that must not change:
  - S6R-10's two exact lines;
  - S77's pair: 42/80/71/92/38, `other=0`;
  - the live REAL proof on `.cache/s6r/real-0b62c12d/`: the logged line byte for byte.

  If any of them moves, stop and report.
- (d) Log in `docs/RP_DECISIONS.md` one sentence that qualifies §2's claim: the REAL proof holds clear leaves bitwise
  and log and value digests exactly. Every other digest is held only to a bijection, with the clear leaves as its
  guard.

N-1 to N-5 may be folded into the same round. None of them blocks the merge.

## Frank

Nothing needs Frank. S-1 tightens a tool within the ruling's pass rule (`PASS`, `version=0`, `other=0`,
`environment=equal`) and changes no criterion.
