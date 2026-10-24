# S03 brief: the package's single `reviewer` pass

Branch `wp/S03`, worktree `.claude/worktrees/s03`, head `05e94fab` (pushed to `5a06e53c`). The range under review is
`main...wp/S03`: 86 files and +157k lines, most of it tool records. Production code is small:
- `src/openflowsheet/models/syn001/cascade.py`, +34 lines (S11, `property_method_refusal`);
- `column.py`, +8 lines (the call).

## 1. What it was built against

`docs/derivations/S03-spec.md`, plus Amendment 1 (§17) and Amendment 2 (§18). Register entries R-628…R-643. The
build-lane choices are in `docs/S03_BUILD_DECISIONS.md`. The verdict is `docs/reviews/S03-verdicts.md`, written by the
`verdict` agent, which confirmed all 40 labels independently.

## 2. The work orders, in order

| WO | Content | Where |
| --- | --- | --- |
| WO-S03-1 | S11 refusal and our-side runner | `scripts/s03_references_ours.py`; tests `test_s03_s11_refusal.py`, `test_s03_ours.py` |
| WO-S03-3 + 3b | DWSIM blind qualification and runs | `spikes/references/s03_qualify_dwsim.py`, `s03_qualify.sh`, a merge script |
| WO-S03-2 + 2b | IDAES blind qualification, then a re-run on §18's closed path ladder | `s03_qualify_idaes.py`, `s03_idaes_p0_reproduction.py` |
| WO-S03-1b, 1c | Our side for RC6, RC7 and the PC-LI alias | — |
| WO-S03-4 | Classifier, `comparison.json`, `tests/test_s03_references.py` (A01–A03, A08–A14), manifest generator | manifest `evidence/S03/959131dc…` `implemented`, 21/24 |
| WO-S03-5 | Verdict | — |

## 3. What was run, and the numbers

- **S11:** 15 tests pass. The cascade and column files with S11 in place give 574 passed and 0 failed. With S11
  disabled, 13 of the 15 fail.
- **Our side:** every case is within 0.1 tolerance of the twin. The worst are RC3 at 3.5e-3 and RC6 at 0.0202.
- **IDAES P0** reproduced the `6d9486a0` records exactly, 20 of 20. Path dependence is at most 7.8e-5 tolerance.
- **Classification:**
  - 23 AGREE and 2 DISAGREE, the controls PC-L and PC-LI at 243.3 tolerances.
  - 13 NOT_COMPARABLE(capability) and 2 not_applicable.
  - X31 is not met (2 of 4 cases with two references). D19 has two references on 9 states, one on 5, and none on the
    RC4 family.
- **Locally:** `pytest tests/test_s03_references.py tests/test_s03_ours.py` gives 290 passed (verdict agent, x86-64).
- **CI run 40131170434 fails** on three things:
  1. **A10 against a live solve,** on both architectures. Spec l.504 says "classifications exact; values and ratios
     1e-12 relative". The RC1-BR response-table difference ours(RC1-BR) − ours(RC1) agrees only to 3.4e-12
     relative, because differences of near-equal numbers amplify last-bit changes.
     - The engineer suggests comparing our input values exactly, as A07 does, plus the classifications exactly, and
       keeping the byte-identical check on the document recomputed from the committed files.
     - The verdict agent notes that the classified ratio nearest a boundary is 1.10, so a last-bit change cannot flip
       a label.
  2. **The harvest:** M07a `HARVEST_SIZE` and T08 A21 fail until the S03 manifest is harvested, the same step as S05's
     and S07's. This is not a review item; the build lane does it after your pass.
  3. **Ruff E501 in the tool scripts:** 33 lines in `s03_qualify_idaes.py` and 2 in `s03_qualify_dwsim.py`. These
     scripts are the provenance of the records, and A03 scans them at HEAD.

## 4. Questions batched for your ruling

1. **A10:** what "values and ratios 1e-12 relative" applies to. Rule the exact replacement text.
2. **E501 in the tool scripts.** The options are:
   - (a) a per-file `E501` ignore in the ruff config;
   - (b) a pure line-wrap reformat at HEAD, with A03 rescanned, the records unchanged, and their recorded commit ids
     still naming the run commits;
   - (c) something else.
   The session's default is (a), because it leaves the provenance scripts byte-identical.
3. **B2b-1**, the session decision under "Session (orchestrator) decisions after WO-S03-2b". §18.1's "Ipopt rejects"
   is read as the solver rejecting an option, so the options-file route stands. If you reverse it, six IDAES pairs
   reopen.
4. **The classifier choices** B4-4, B4-9 and B4-10 (`docs/S03_BUILD_DECISIONS.md` l.380–410).
5. **§17.8 condition 2's wording,** which the verdict says contradicts its own "by construction" statement. Rule the
   erratum text.
6. **The general review:**
   - S11's placement and its zero-evaluation guarantee;
   - the blindness enforcement (A03) and whether it actually prevents leakage;
   - whether the classifier implements §7/§17.3/§18 faithfully;
   - whether the tests verify what they claim.

## 5. Where I am least sure

- Whether IDAES's path ladder P1 (warm-start options) changes the solution found, rather than only the route to it.
  P0's results stood wherever P0 passed, and path dependence is ≤ 7.8e-5 tolerance.
- Whether DWSIM's RC1-family agreements are meaningful, since its accuracy rerun moved them 0.071–0.093 against a
  0.1 budget.

## 6. Not worth your time

Formatting, the tool records' bulk, and re-deriving the tolerances (T06's formula, already reviewed for T06).

## 7. Deliverable

- `docs/reviews/S03-review.md`, with findings ranked by severity and a ruling on each §4 question, giving exact text
  where a spec or test changes.
- If spec errata are needed, write them into `docs/derivations/S03-spec.md` as a short §19, with a register entry
  after R-643.
- Commit docs-only on wp/S03. Do not push and do not set `reviewed`. Report in at most 25 lines.
