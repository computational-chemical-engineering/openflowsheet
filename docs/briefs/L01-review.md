# L01 — independent review and ruling round (design lane, `reviewer`)

Branch `wp/L01` (worktree `/home/user/ofs-l01`), 37 commits on `wp/C-merge`. The package's single `reviewer` pass;
it carries the batched design-lane questions. L01's provider touches derivatives and phase/root logic.

## The question
1. Do WO-1 (records, cross-check) and WO-2 (`src/openflowsheet/thermo/pr_lib.py`, `l01_reference.py`) meet
   `docs/derivations/L01-spec.md` and ADR 0043, and do the tests verify what A01–A22 claim (mutation-minded)?
   Residual/derivative consistency; the root rule (largest root; `vapour_root_metastable`, `vapour_root_liquid_like`);
   independence of `l01_reference.py` from `pr_lib.py`; `pr_c1.py` and `benchmarks/m01/` untouched.
2. Rule on the open questions in `docs/L01_DECISIONS.md:26-43`: A12 for C3H8 (+0.577 % at 600 K vs 0.5 %; comparand,
   bound, or stop C3H8 — a bound changes only with a derivation that the registered one was wrong); A12's scope
   (copied C1 records: CH4 −0.47 %/+0.68 %); O2's critical point; spec numbers (CO2 v/b 1.5146 vs 1.52; A19's 5.5×
   vs 6.14× against PR's own vapour pressure); spec §4.4 vs §11 on when `PACKAGED` gains the path.
3. **T08.A32** (`tests/test_t08_w2_inventory.py:440-460`; T08 release spec §4.8/§9) admits only M01's real records
   anywhere in the repository and fails on `benchmarks/l01/components.yaml`. Draft the amendment (rule text, register
   entry, the test change as a work order) that admits a second vetted record file with a rights statement per
   record — or rule that L01's records cannot be admitted and why. Rights themselves are Frank's (L01-Q4 in
   `docs/FRANK_QUESTIONS.md`); do not decide them.
Register entries **R-528…R-529**, then continue at **R-540…** if more are needed (R-530…R-539 belong to S02).

## Exit test
`docs/reviews/L01-review.md` (must-fix / should-fix / note with file:line and a failure scenario; the rulings; the
fix work order), a dated amendment in `docs/derivations/L01-spec.md`, register entries. Do not edit production code;
do not set `reviewed`. Env: `PYTHONPATH=$PWD/src /home/user/openflowsheet/.venv/bin/python -m pytest -q tests/test_l01_*.py`.

## Out of scope
W27 amendments (L01-Q1), new methods, held-out data.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/L01-review-handoff.md`, stop. Report ≤ 150 words.
