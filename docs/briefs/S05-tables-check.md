# S05 — IAPWS terms and the Tables 6–8 check (build lane, workstation; web access)

Worktree `.claude/worktrees/s05t`, branch `wp/S05-tables` from `main`. Frank (C10-Q1, 2026-10-23): S05's IAPWS-95
coefficients came from CoolProp's `Water` JSON (the cloud could not reach iapws.org); nothing ships until IAPWS's terms
are read and the values are confirmed against the release's Tables 6–8 (`docs/derivations/S05-IAPWS95-spec.md` §10 Q-1).
1. Fetch the IAPWS R6-95(2018) release (iapws.org, the PDF) into an ignored scratch dir (never commit the PDF); record URL,
   fetch date and SHA-256. Quote verbatim whatever iapws.org says on use/reproduction of its releases.
2. Compare every coefficient the generator/provider uses (`docs/derivations/scripts/s05_reference.py`, the provider's
   data) with Tables 1, 2 and 6 (ideal-gas and residual parts) and check the generator's values against Tables 7–8
   (the published test values), digit by digit as printed. Use a small script (scratch), print one summary line.
3. Write the result into a new section of `docs/C10_DECISIONS.md` (or the S05 decisions file): table counts compared,
   mismatches (expect none), terms quoted. Do not change any coefficient; a mismatch → STOP and report it.
Rules: you do not decide shipping (Frank's). Commit, push the branch, do not merge. Env: `/home/frankp/Codes/OpenFlowsheet/.venv`,
`PYTHONPATH=$PWD/src:$PWD`. Report ≤120 words.
