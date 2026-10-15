# V02 alpha gate — design-lane read of WO-5, WO-8, WO-9 (before WO-10 cuts `C_α`)

| | |
| --- | --- |
| Date | 2026-10-15 |
| Lane | design (`reviewer`), one pass, on `docs/briefs/V02-alpha-read.md` |
| Branch | `wp/V02-alpha-gate` @ `360eef3` (WO-5 `b44f684`+`69cfc8e`, WO-8 `e808406`+`f6a748a`, WO-9 `5252040`) |
| Against | `docs/derivations/V02-alpha-release-spec.md` §3, §5.3, §8, §10 (A37, A50, A52), §15; ADR 0028 D3; ADR 0021 D4; T08 spec §5.7, §6.3 |
| Ran | `pytest -q tests/test_m07a_surface_chain.py tests/test_m07a_harvest.py tests/test_m07a_changelog.py`: 18 passed, 2 skipped (the two `PENDING` clauses). `sha256sum` of `validate.md` and `commit_change.md` at `v0.1.0` and on the branch. The full gate was not re-run (8558 at `f6a748a`, the brief's number). |
| Register | R-319, R-320, R-321 (this read) |

## Verdict

**WO-10 may cut `C_α` once F1, F2 and F4 have landed.** F3 is closed by R-319 in this commit. F5 can wait until the cut,
because `CHANGELOG.md` is not in ADR 0021 D2.4's `TREES`. F4 must land before `C_α` or not at all: it edits
`benchmarks/`, which is frozen from `C_α` to the tag. The chain itself (WO-5) is sound. The harvest draft (WO-8) is right
except for three items. The prose of the section (WO-9) does not overstate the claim set.

## Findings, most severe first

**F1 — must fix (before WO-10 commits M07a's manifest).** `scripts/t08_support_matrix.py` `HARVEST_EXCLUDED = ()` and
`tests/test_m07a_harvest.py::test_m07a_a50_nothing_is_excluded_from_the_harvest`. WO-10 writes
`evidence/M07a/<C_α>/manifest.json` after `C_α`. On that commit, `harvest_items()` reads the manifest, and none of its
limitations are classified in the envelope. `check_a21` (`test_t08_w2_support_envelope.py`, `t08_support_matrix.py
--check`) then fails. Classifying the items is not possible either, because `benchmarks/` is frozen after `C_α`. Setting
the exclusion then fails the A50 test, which asserts `== ()`. Either way `check.sh` is red on the RC branch from the
manifest commit on, and the merge into `main` carries the failure. The script comment already anticipates this, but the
test contradicts it. **Correction (R-320):** set `HARVEST_EXCLUDED = ("evidence/M07a/",)` now; the exclusion is vacuous at
`C_α`. Change the A50 test to assert that the exclusion is exactly that one directory, and that no manifest of the
candidate falls under it: no `evidence/M07a/` manifest in the working tree, and after the cut none in `git ls-tree C_α`.
`HARVEST_SIZE` does not change. This is T08's precedent (Amendment R8 2): a package's own manifest, written after its
candidate, belongs to the next harvest. A50's "with `HARVEST_EXCLUDED` empty" now reads "excluding no manifest at
`C_α`". M07 removes the exclusion and harvests M07a's manifest.

**F2 — must fix (before the RC branch merges into `main`).** `tests/test_m07a_changelog.py`, clauses (g) and (e). Both
read the working tree: (g) globs `evidence/*/*/manifest.json`, and (e) reads `support_envelope.yaml`. Three failures
follow:
- M07a's own manifest adds a row the table does not have, and the brief asks for this to be ruled.
- Every later merge (M04, M03, M05) adds a manifest and fails (g).
- The first L-row added on `main` after the tag fails (e).

These are the failures R-216 and R-217 met for the v0.1.0 notes. ADR 0028 D3 already sets the rule: the table covers
"every package manifest **at the candidate**". **Correction (R-320):** once the heading names `C_α`, (g) computes MR-5's
set from `git ls-tree -r C_α -- evidence`, taking committer time from `git log -1 --format=%ct C_α -- <path>`, and (e)
reads `git show C_α:benchmarks/t08/support_envelope.yaml`. While the marker is present, both keep reading the working
tree. **M07a has no row.** Its manifest is written after `C_α`, and it is the record of this gate rather than a package
of the candidate. Say so in one clause of the section's review-table sentence. (g) should also check the third column
against each manifest's `review` fields. Today that column is free text, and nothing tests it. It is correct now: K and
P are signed 2026-09-23, everything else is pending.

**F3 — must fix; done here (R-319).** B-WO5-1: R-234 said "M02's digest is registered at the merge commit", and no entry
did it. Two values are now registered:
- `D_2` = `383b4e2c004810663a3e3f80c591730bc95894e35736619eacac0f51e51b5403`. The M02 manifest records it at `ba90619`
  (`served_sha256`; `without_m02_sha256` = `D_1`). It is reproduced on this branch after the `main` merge (`46176a7`):
  A37 item 1 passes in the run above.
- B-WO5-5: item 4's "R-133's files" are `commit_change` `fd7ff7a8…` and `validate` `1025385a…`. Both equal `REVIEW.json`
  at `PUBLIC_ROOT`, and both equal `sha256sum` of `git show v0.1.0:…/descriptions/<name>.md`, which I checked.

`m07a_rc.py`'s two constants should cite R-319. The test's equality with the manifest stays.

**F4 — should fix, before `C_α` (R-321).** These are corrections to the WO-8 draft, judged by T08 §5.7's rule: the first
applicable class in the order E, B, S, P, and "a defect handed on is never P".
- `[8]` (library-only): **E**, to a new row **L43**, not P. It is user-facing. `docs/recovery-edges.yaml` E1 and E2 are
  `enabled: library-only` because every shipped loop unit declares exact derivatives, so `auto` resolves to
  `newton_tear`, and no application policy requests `anderson`. The matrix nevertheless says "recycles … by tear with
  safeguarded Anderson and restart" (`topologies`) and "Anderson recycle" (`globalization_and_recovery`), and "unlisted
  is unsupported" makes "listed" read as supported. Proposed L43 text: *"The Anderson recycle, its stagnation restart
  (recovery edge E1) and the stalled-recycle EO merge (E2) are library capabilities: every shipped unit that can sit in
  a loop declares exact derivatives, so `auto` resolves to `newton_tear`, and no application-offered policy requests
  `anderson` (`docs/recovery-edges.yaml`, `enabled: library-only`, R-130). V13 (b)'s and V14 (c)'s evidence for them is
  library-level."* Where no test pins the two statements, append "(L43)" to each. Regenerating the matrix and the
  section's limitation list follows from A52 (e).
- `[9]` (A34 did not audit the certificates the replays re-emit): **B**, to a new **B13**, not P. MR-11 widens A34 to
  step 12, but not to step 5's replays, so the gap is still open at the alpha. B13 is appended to T08 spec §6.3 with an
  amendment marker, as B10–B12 were. `backlog_ids()` reads it there.
- `[2]`, `checks[42]`, `checks[67]` (V14 (b)): **E** to `L01` **and `B8`**. B8 is the handed-on PTC-R1 qualification,
  and ADR 0028's D3 row names its owner after the alpha. `check_a21` accepts B ids among an E item's pointers.
- Confirmed as drafted: B-WO8-1 (46 restatements, each E to its own row); B-WO8-3 (`[5]` E L07; `[11]` E L07, L15;
  `[7]` E L42, whose K_NH₃ and property-value parts were closed by R-152 and M01, so the note should cite R-152); the P
  items `[0]`, `[1]`, `[3]`, `[4]`, `[6]`, `[10]`; B-WO8-5 (the v0.1 quote is P00–T07's, by T08 Amendment R8 2);
  B-WO8-6.

**F5 — should fix, at the cut.** `CHANGELOG.md` `## v0.2.0a1`:
- (a) "a diagnostic web shell …, which edits nothing" drops L-WEB-1's qualifier. Use its words: "edits nothing (Solve
  and Cancel are its only effects)".
- (b) The "Certificates and extras" bullet is ADR 0028 D3's gate rules, not something the release is not. Its first
  sentence also asserts an RC outcome before the RC has run (step 10 over step 12's certificates, Q5 "needs a fact"). If
  Q5 goes the other way, V18 (b) is FAIL and the sentence is false. Drop the bullet, and drop its two entries from
  `PHRASES`, which §10.1 does not list. Otherwise move it under the gate table and keep it only if M07a.A39 passes.
- (c) "V14 (b) is judged FAIL at `C_α`" pre-states the alpha verdict. Keep it, but WO-10 checks every verdict-dependent
  sentence against `docs/reviews/V02-alpha-verdicts.md` before it removes the markers.

Against the claim set (V11–V20, W21, W22), "What it does" claims nothing of W23–W27. It names the web shell as shipped and
unclaimed, and it follows spec l.26's own wording for W22. It holds. Using ADR 0021 D4 for the six headings is correct;
ADR 0028 D2 reuses ADR 0021.

**F6 — note: M04 is link `c_3` if it lands first.** `wp/M04` moves the served list. Its `without_m04` is used in
`test_t08_w2_surface_digest.py`. If M04 merges before `C_α`, §5.3's four requirements apply: an R entry,
`LINKS += (c_3, without_m04, D_3)`, and Frank's V17 carry naming c_3. Otherwise A37 item 1 fails and V17 is `BLOCKED`.
Separately, M04's `test_m04s_surface_move_decomposes_onto_m02s` checks the composed strip against `D_1`, but not
`d(without_m04(T)) = D_2`. Item 2 checks that intermediate step, so M04's reviewer should add it. The state file's
preference, cutting before M03, should extend to M04.

**F7 — note: after the tag.** Clause (c) runs `v0_2_gate.py --markdown` against the live ledger. When M07 writes 0.2.0's
verdicts into the same rows (FD-α5), (c) fails, as MR-9 found for v0.1.0. M07 owes the alpha section MR-9's treatment,
reading at the alpha's public commit. Step 10 (MR-11) also has to be given step 12's certificates: `t08_rc.py
certificates` takes `inputs`, and CI runs only steps 4–7. WO-10 runs it over step 12's output on `ref-x86-64`.

## WO-5: sound

`chain()` applies each strip to the previous strip's output and compares it with `D_{k−1}`, ending at `D_0`, with item 3
computed on the fully stripped list. Item 1, an exact served digest, is the binding check. Given it, items 2 and 3 are
deterministic, so `without_m02` being pattern-based cannot hide a later change. Controls (i)–(iv) are read correctly
(B-WO5-6), and each fails at the link §5.3 names. Item 3 by substitution (B-WO5-4) is valid only because
`served_texts_are_the_files` holds in the same record, and it does. The G16-b copy matches `t08_rc.step_surface`'s loop
line for line, except for the check id (B-WO5-3). G16-b is in the gate already (`test_t07_v17_reference.py`, 40 runs).
CI (B-WO5-7): every RC job's `if` carries `rc_alpha`, and only the 0.1 surface step stays `rc`-only. B-WO5-2: confirmed.

## Not examined

`scripts/v0_2_gate.py` (WO-2) and its tests; WO-3 (`release.yml`, `changelog_section.py`); WO-4, WO-6 and WO-7;
`benchmarks/m07a/reference_values.yaml`; the restated rows' texts item by item (`check_a21` holds their hashes); the
reachability tests behind R-130's library-only rows under M02's units (the gate passes them).
