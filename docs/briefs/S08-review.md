# S08 brief: the package's single `reviewer` pass, with batched rulings

Branch `wp/S08`, worktree `.claude/worktrees/s08`, head `2ae64c2b`. Range `390e0af5..HEAD` (17 commits; src/tests/scripts
+3125/−64 in 10 files).

## 1. What it was built against

`docs/derivations/S08-design.md` (architect, `943276d8`) and ADR 0048 (Proposed), R-728…R-732; S02 Amendment 4 pointer.
Route: Stage A is today's path, unchanged; Stage B runs only when Stage A ends typed (trigger (i)) or is rejected by the
new S02 §8 item 6 (trigger (ii)), and solves block openings `V^a 2P^b L^c` built from the column's sources under the
unchanged phase contract. Item 6: every `TWO_PHASE` stage within 1e-4 K of its bubble and dew temperatures.
Build log: `docs/S08_DECISIONS.md`.

## 2. Work orders

| WO | Content | Commits |
| --- | --- | --- |
| WO-G (specifier) | `docs/derivations/scripts/s08_reference.py`/`.json`: P2, P3, F1, D1 at 50 digits, 84 claims; R-732 | `0d15a11c` (merged `7240d6f8`) |
| WO-1 | item 6: `column_solve.py` `TWO_PHASE_SATURATION_TOLERANCE`, `saturation_errors`, `acceptance_failures`; `tests/test_s08_item6.py` | `bff48c4d`, `56c26474` |
| WO-2 | step 0: design probes `s08_design/*.py` lint-cleaned (re-run: every stdout line in `measured.txt`); `models/syn001/column_blocks.py` (sources, candidates, `block_endpoint`, refusals); `tests/test_s08_blocks.py` | `d25cbebc`, `57a09675`, `7d551cd5` |
| WO-3 | Stage B in `column_solve.py` (`target_attempt`, `initializer_source`, triggers, loop, §5.6 records, §5.7 endings); `tests/test_s08_reentry.py`; P1 held branch moved to `reentry.stage_a` | `a837c3c3`, `2bbe58fd`, `090ab3d8` |
| WO-4 | `tests/test_s08_roots.py`, `tests/test_s08_identity.py`; `scripts/s08_identity.py` (G1); S03 §10.1/§14 sentence; manifest generator, manifest `evidence/S08/38457cb8…` tested 24/26; ledger S08 | `2a671fd1`…`2ae64c2b` |

## 3. What was run

- G1: `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL` (11.5 s; U1/U2 `stage_a` also equal the merge base).
- G2: no diff on frozen paths (orchestrator/, numerics/, thermo/, compile/, schemas/ untouched).
- Suites S01/S02/S06/S03/S08: 890 passed (WO-3); manifest run green. Roots vs WO-G in state-tolerance units: P2 0, P3
  2.4e-9, F1 2.8e-3, D1 6.0e-3 (Stage A), D1 1.2e-6 (Stage B, Stage A stubbed). Item-6 worst registered 2.42e-6 K.
  Iterations from block endpoints: P1 0, P2 0, P3 4, F1 4. Wall: P1 0.53–0.92 s (Stage B 0.009 s), P3 0.50–0.87 s.
- Not yet: the T08 harvest (two harvest-only test failures expected), the full gate, CI.

## 4. Rulings wanted, batched

1. **Build decisions** W1-1…W1-5, W2-1…W2-6, W3-1…W3-8, W4-1…W4-8 (`docs/S08_DECISIONS.md`). Look hardest at:
   - W3-5: §5.7 item 3's message names the tried candidates via `add_note`, because `AcceptanceDefectError` lives in
     frozen `cascade_solve.py`;
   - W3-6: Stage A failing only item 6 while also having a single-phase temperature-specified stage now runs Stage B
     instead of raising;
   - W3-8: WO-1's item-6 test skips P1's Stage-B root after asserting it has no two-phase stage;
   - W2-4: a `BandError` inside the sweeps propagates instead of refusing the candidate;
   - W4-5: A14 (b)'s mutation goes through `_core_flows` only.
2. **Stale S03 sentences** (W4-7): §10.1's "P1 does end that way (`HOMOTOPY_STALLED`…)" and "that outcome is S02 A12's
   typed branch", and §14's "A later package is queued for it…". Give exact replacement text.
3. **Requirements** (W4-8): neither the note nor ADR 0048 names one; the manifest lists none. Rule which (X31 was
   suggested), and whether S06 belongs in `depends_on` (it is not a ledger package).
4. **Frank's three questions from the design, defaults recorded**: Q1 scope (block roots the sources generate: yes),
   Q3 contract defect (stage ids misread as dormancy items → follow-up package), Q4 trace-vapour roots in flash units
   and S01 cascades (follow-up package). Confirm the defaults are technically sound; do not decide for Frank.

## 5. General review

- Does Stage B really leave Stage A untouched, and is G1 a sufficient proof (what could change that G1 does not see)?
- Item 6's tolerance and its interaction with the existing acceptance checks; could it reject a correct root?
- The block endpoint's energy solve and refusals: is a refusal ever a hidden success, or a success a hidden refusal?
- Do the tests verify what they claim (no circular expectations; WO-G's roots are independent)?
- The design's premise that restarts fail because they open from the failed attempt's end state: does the evidence
  (`docs/derivations/scripts/s08_design/measured.txt`) support it?

## 6. Where I am least sure

F1's root agreement at 2.8e-3 and D1's at 6.0e-3 of the state tolerance (Stage A), against P3's 2.4e-9; and trigger
(ii)'s reliance on every failure string starting with `ITEM_6_PREFIX` (W3-2).

## 7. Not worth your time

Formatting; re-deriving WO-G's roots; the design probes' history.

## 8. Deliverable

`docs/reviews/S08-review.md`, findings by severity, a ruling on each §4 item with exact text where a spec, test or record
changes; spec errata in `docs/derivations/S08-design.md` as a dated amendment section with register entries after R-732.
A docs-only commit on wp/S08. Do not push; do not set `reviewed`. Report in at most 25 lines.
