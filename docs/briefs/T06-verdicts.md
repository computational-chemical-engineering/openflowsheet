# Brief — T06 verdicts on evidence

**To:** `verdict` (design lane). **From:** build lane, 2026-09-26. **Branch:** `wp/T06`.
**Deliverable:** `docs/reviews/T06-verdicts.md`: per verdict — met / not met / insufficient evidence /
blocked, the reasoning, and what it does not establish. Do not edit code; do not commit.

**Verdicts requested:**
1. **The eight reference comparisons (D19, V16; spec §9 as amended; plan §6.4):** per fixture × tool
   (REF-01…08 × DWSIM, IDAES) and the positive controls PC-1/PC-2: `AGREE` / `DISAGREE` /
   `NOT_COMPARABLE` with reasons, on the committed evidence `benchmarks/t06/references/comparison.json`,
   `results/` (+`SHA256SUMS`), `docs/t06-reference-qualification.md`, `docs/reference-environments.md`,
   and the rulings that set the tool inputs (IDAES `constr_viol_tol` 1e-9; SmoothVLE ε = 1e-8 K with
   rule 2b; DWSIM ΔH_vap mapping; MUMPS; REF-07 extent disclosure). Include whether the independence
   and blindness requirements were met, and V16's counts (eight comparisons; two both-reference cases).
2. **The nominal robustness gate (V20, A29–A31; spec §7 as amended):** on scoring run 2 — local
   x86-64 and CI dispatch run 36270294833 on both architectures (S = 434/440 each; classes; CP bound
   0.9733; `ensemble-compare`). Run files in
   `/tmp/claude-1003/-home-frankp-Codes-Process-Simulator/c1654ca5-cf40-4fac-b53a-1914bdd081e5/scratchpad/scoring/`
   (`run2_x86.json`, `run2_report.txt`) and the CI logs (`gh run view 36270294833 --log`). Note that
   run 1 FAILED (S = 431, four unexplained F-OTHER-ROOT) and was not re-judged; ADR 0018 was adopted
   in between (Frank approved) — say whether run 2's pass is legitimate given the preregistration rules
   (§6.2: budgets and ceilings registered before scoring; starts committed before any solve).
3. **No false verification (V20):** across the corpus and both runs — any `VERIFIED` state far from its
   registered root, or any caught false success missed.
Evidence and history: `docs/T06_DECISIONS.md`, `docs/t06-measurements.md`.
