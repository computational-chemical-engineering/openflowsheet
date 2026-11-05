# Roadmap decisions log (append-only)

Each entry gives the date, the question, the choice, who made it and where it is applied.

- **2026-11-01** Frank: the roadmap starts now (stages 1–5), while feature development stays paused.
- **2026-11-02** Frank: the S8 state-structure sketches go into the final architect pass. They cover X18 electrolytes,
  X19 solids, X20 polymers, X21 assays, X22 rate-based columns and TX, and per M1 also X12, X14, X25 and X26. They are
  done before the v2 grammar is frozen.
- **2026-11-02** Frank: FB-04 (1), the quick fix to the legacy turbine in 0.4, is dropped. The turbine case gets solved
  properly by F5 and `std.turbine`. Until then MSG's message explains the limitation and the workaround.
- **2026-11-02** DECISION (orchestrator, on the review's default; Frank may overturn): a legacy family is closed to new
  v2 work once `std.*` reaches parity with it. The reviewer's retirement rule applies. Alternative: keep both open.
  Reversible by: editing the F6 exit.
- **2026-11-02** DECISION (orchestrator, on the review's default): the v2 core grammar is frozen at the end of design
  wave W1. The F4–F6 slots stay `preview` until the end of 0.6. Alternative: freeze everything at W1. Reversible by:
  moving the freeze point.
- **2026-11-02** DECISION (orchestrator, on the specifier's default O-6): water is the default first liquid-ordering
  key. Alternative: component order only. Reversible by: Q4.R3's default.
- **2026-11-02** DECISION (orchestrator, on the specifier's default O-7, which the review endorses): state documents
  carry mass-specific `ĥ`; reports show both specific and molar h. Alternative: molar h. Reversible by: Q1.R1, before
  the v2 freeze.
- **2026-11-02** Frank: ADR 0057 accepted as is ("Accept as is"): dynamics in 0.7, the design toolkit in 0.8. Register
  entries R-928 (roadmap), R-929 (freeze points, legacy retirement) and R-930 (`state_rate` control rows).
- **2026-11-05** W1 specifier (Amendment 2 to the foundation rulings, §14): all five open items adopt their defaults,
  made exact — A1-a (Q3.R5: integer C with C A = A′Π), A1-b (Q2.R2: anchor is a record field), S5 (Q4.R6/R8: `FLUID`
  family, `root_switch`, confined phases by declared support; legacy providers stay `split`), holdup dormancy (Q1.R8),
  non-material holdups (Q1.R9: `wall_energy`, `angular_momentum`). Findings for the architect passes: ADR-F7 amends
  ADR 0008 U1/U1b; A2-b (ADR-F6 routing of FLUID phases); A2-c (X21/F5 confined vs FLUID). Frank: O-11, A2-a
  (`docs/FRANK_QUESTIONS.md`).
- **2026-11-05** W1 architect P1: ADR 0060 (F1 extension registry) and ADR 0061 (F3 component data), Proposed. Open for
  the P1 reviewer pass (with a specifier read where scientific): ADR 0061 D12 legacy provenance table; records with no
  formation data and no phase tag (`syn001`, `s05`, `s07`) → null anchor + `anchor_undetermined` (Q2.R2 silent);
  `molar_entropy`, `segment_molar_enthalpy` quantity kinds for ADR-F2 (P2).
- **2026-11-05** DECISION (orchestrator): `pr-lib-v1` stays a v2-only basis — ADR 0050 D10 and R-615 stand; the note's
  "X01 rest: `pr-lib-v1` selectable" means selectable on v2 flowsheets. Alternative: reverse D10 (new ADR). Reversible
  by: an ADR amending ADR 0050 D10.
- **2026-11-05** W1 P1 review (`docs/reviews/W1-P1-review.md`): ADR 0060 and 0061 accept after the listed fixes (5
  must-fix, 16 should-fix). Rulings: D12 provenance table confirmed with four identity-bearing changes; `assess_rights`
  accepted with four request checks; the no-data anchor (`syn001`, `s05`, `s07`) referred to the specifier — build
  default null + `anchor_undetermined`, deadline before ADR-F4 is Accepted.
- **2026-11-05** DECISION (orchestrator, on the reviewer's preference): finding 2 — `functional_contributor`
  extensions are `preview` in 0.5 (listed, not passed to E01) until an ADR 0052 amendment (ADR-F8 or X01 rest).
  Finding 12 — core admission covers single-side units; ADR-F6 adds per-side `requires` additively. Finding 19 —
  whole-source rights rows keyed by `source_sha256`; `legacy.` reserved for the importer; "latest" = insertion order.
  Reversible by: editing ADR 0060 D8/D12 or ADR 0061 D11 before F1/F3 are built.
