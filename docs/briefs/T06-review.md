# Brief — T06 implementation review

**To:** `reviewer` (design lane). **From:** build lane, 2026-09-26. **Branch:** `wp/T06`, range
`63364f8..HEAD` (documents in the range are the design lane's). **Deliverable:**
`docs/reviews/T06-review.md` in the shape of `docs/reviews/T05b-review.md` (verdict; must-fix /
should-fix / notes with `file:line` and a falsifiable test; FOR FRANK). Do not edit `src/`/`tests/`
or design documents; do not commit; never set `reviewed`.

**Design under review:** `docs/derivations/T06-corpus-spec.md` (+ Amendments 1–4), ADRs 0014, 0015
(F4 restart), 0016 (unit-conversion-v2), 0017 (F6 flash fix; SYN-001 identity re-registered hash-only),
0018 (terminal Newton refinement) — all Proposed; design note `docs/design/T06-F4-recovery.md`; twin
`docs/derivations/scripts/t06_reference.py` (347 claims, `e97f61ce…`); register R-066…R-087; the ruling
briefs `docs/briefs/T06-amendment-{1,2,3}.md`, `T06-scoring-round.md`. Frank's answers:
`docs/T06_DECISIONS.md`.

**What was run:** gate 3987 green; CI green on both architectures at `4d1e2ed` (structural
`915c97e8…` equal). **Scoring run 1 FAILED** (S = 431/440, 4 unexplained F-OTHER-ROOT on THM-09 —
stopped early; not re-judged). **Scoring run 2 PASSED** on x86-64 and aarch64 (S = 434/440 each; CI
dispatch 36270294833; `ensemble-compare` success). References: DWSIM and IDAES 8/8 AGREE, PC-1/PC-2
DISAGREE as designed (IDAES under the registered SmoothVLE ε).

**Where the build lane is least sure (spend your effort here):**
1. **`thermo/syn001.py`'s F6 fix (ADR 0017)** and A78's two-step proof — the only provider edit since P01.
2. **The Newton terminal refinement (ADR 0018)** in `numerics/newton.py`/`linear.py`/`region.py` —
   "never changes an outcome"; the three engineer readings logged in `docs/T06_DECISIONS.md` (budget
   run-out inside a refinement marks `BUDGET_EXHAUSTED`; "rejected trial"; chord back-solve failure).
3. **F4's sequential restart** (`orchestrator/executor.py`, `revision.py`): P0–P5, and that rescued
   starts are honest successes; ensemble scoring code (`benchmarks/t06/ensemble.py`) — success rule,
   classification, clustering, gate.
4. **The verifier changes:** W2 alias shift, W3 seeded `onenormest`, W14 identity refusal, W19
   corrected closure, W20 counter, R-016 independence.
5. **Unit conversion v2 and component-order mapping** (`units/`, both bindings, the four readers).
6. **Tests weakened after measurement** — examine each against CLAUDE.md "no relaxed checks": A50's
   float comparison to 1e-12 relative (cross-machine), T05b B34 (a)'s moved closure values now recorded
   not asserted (machine-dependent false-success location), A92's floor registered at 9.4e-4 vs the
   text's 9.5e-4, X26's roundoff-floor split (T05b) — say for each whether it is legitimate.

**Do not spend time on:** style; DWSIM/IDAES internals; the evidence manifest (written after you).
