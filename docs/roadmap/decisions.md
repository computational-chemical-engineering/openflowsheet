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
- **2026-11-05** Specifier Amendment 3 (rulings §15, Q2.R9): a `mol`-basis record with no anchor, charge, formation data
  or phase tag takes `ig` with notice `anchor_defaulted(<id>)` (not in identity); `kg`/`segment_mol` keep null +
  `anchor_undetermined`. `ig` means the method's ideal-gas state (φ° for Helmholtz methods). Legacy importer: 127
  records (syn001 3, s05 1, s07 123) anchor `ig`. Open: O-12 (CoolProp not evaluated here), O-13 (aarch64 unmeasured);
  findings A3-a (ADR-F4: catch a real-gas method anchoring at its vapour), A3-b (ADR 0061 D8 dedup findings owner).
- **2026-11-05** W1 architect P2: ADR 0062 (F2), 0063 (F4), 0064 (F5), Proposed. One spelling rule for units
  (`schemas/units.json` ASCII form, e.g. `J/(mol K)`), answering MSG's question too. ADR 0063 D2 narrows ADR 0061 D10's
  `data_sha256` per method; the ADR 0061 edit is held until the P2 reviewer pass confirms it.
- **2026-11-05** W1 P2 review (`docs/reviews/W1-P2-review.md`): ADR 0062–0064 accept after listed fixes (4 must-fix:
  non-TP flashes as one Newton system with T; dispatch to T05b only for v1-path runs, FB-04 full check moves to F6's
  exit; a lowered run is a v1 run in every artifact; delegating methods refuse `records_not_delegable`). Ruling 1:
  per-method `data_sha256` accepted (ADR 0061 D10 sentence and risk 8 replaced as the review gives). Departures: Q4.R7
  narrowing rejected; scales placement must be fixed; the rest accepted. PR-C1's ideal-gas part is separable
  (`pr_c1.h_ig`, `pr_c1.py:315`).
- **2026-11-05** DECISION (orchestrator, reviewer's defaults): phase-removal threshold 1e-12 of the total amount,
  fixed later by the O-2 measurement; entropy shift for records without s° takes the review's default, referred to the
  specifier (batched with P3's specifier needs). Reversible by: one constant in ADR 0064; the specifier ruling.
- **2026-11-05** W1 P3 started: architect brief `docs/roadmap/brief-architect-W1-P3.md` (be742832). DECISION
  (orchestrator): P3's ADRs take 0065 (F6), 0066 (F7), 0067 (F8); ADR 0019 amendments from 10; the architect lists
  scientific questions with defaults instead of ruling, and one specifier round follows P3 batching them with ADR 0063
  risk 5 (entropy shift). Alternative: a specifier pass on the entropy shift now. Reversible by: renumbering before
  commit; running the specifier earlier.
- **2026-11-05** W1 P3 architect pass done: ADR 0065 (F6), 0066 (F7), 0067 (F8) Proposed (e740c7ca), 30 note edits in
  `docs/roadmap/W1-P3-note-edits.md`. Eight departures recorded in the ADRs, two of them touching P1/P2 ADRs (ADR 0060
  D9 narrowed: evidence notices in the evidence report, not the certificate; ADR 0063 D7 amended additively:
  `MaterialModel` reports record entries read per state point) — flagged for the P3 reviewer. Seven specifier
  questions (SQ-F6-1…4, SQ-F7-1…2, SQ-F8-1) batched with ADR 0063 risk 5 into one specifier round
  (`docs/roadmap/brief-specifier-W1-P3-questions.md`, bf1d9107); the P3 reviewer runs after it. SQ-F6-1's default gives
  O-11 a numerical consequence: Frank to be told with O-11.
- **2026-11-06** W1 P3 specifier round done (06c13731): Amendment 4 (§16) — Q2.R10 entropy datum (default adopted,
  refusal narrowed to amount-changing uses; PS/TS specs and isentropic units admitted), Q4.R9 (SQ-F6-1), Q5.R9 (SQ-F6-3),
  Q5.R10 (SQ-F6-4), Q5.R11 (SQ-F7-1; ADR 0066 D7's PR-liquid example wrong), Q1.R10 (SQ-F7-2), Q9.R8 (SQ-F8-1, changed:
  τ_g on g's quantity kind, not time); O-14…O-18. `docs/derivations/F6-std-seed.md` complete for 11 units (generator
  --check PASS, 107 claims). 18 ADR edits pending, folded into the P3 reviewer's consolidated list
  (`docs/roadmap/brief-reviewer-W1-P3.md`, 7bd2ad04). O-11 now has a numerical consequence; FRANK_QUESTIONS updated.
- **2026-11-06** W1 P3 review (`docs/reviews/W1-P3-review.md`, 08c7b165): ADR 0065, 0066, 0067 accept after fixes
  (M1 v2 `model_version` gains a `configuration` source and label `FSR2-<cfg>`; M2 `control_volumes`; M3
  `{specification}` signal sink; M4 `phase_routing.vapor`; M5 syn001 leg `equivalence_pending`; M6 E-F7-4 example);
  all eight architect departures accepted; no second architect pass. DECISION (orchestrator, reviewer's defaults):
  S1 → a changed built-in replays as `compatible_reproduction` (`extension_changed`), others stay `NOT_RUN`.
  Alternative: every changed extension `NOT_RUN`. Reversible by: ADR 0067 D5 step 5. S7 → retirement closes families
  for v2-compiled revisions only. Alternative: gate lowering too and re-base ADR 0062's lowering fixtures. Reversible
  by: ADR 0065 D17. M4's ≥2-FLUID-phase routing takes the reviewer's default, recorded as SQ-F6-5 for the next
  specifier round (does not block the freeze). Edits applied by one engineer pass.
- **2026-11-06** W1 closed (R-941, 97fe738a); note Revision 3 (31520fea, 6e9d62bc). F0 merged (97f07dce). DECISION
  (orchestrator): ST starts with a recon digest and one short architect pass, because a stream-table operation on all
  four transports is an addition to the frozen application contract (an ADR 0019 amendment, design lane), although the
  roadmap lists ST as needing no design pass. Alternative: build lane designs the operation and the reviewer checks it.
  Reversible by: dropping the architect pass if the recon shows an existing operation can carry the table additively.
- **2026-11-06** MSG WO-7/8 done on `wp/MSG` (6a5435ad…6a0c9b0b; gate: description-review test red by design until
  `explain.md` reviews; f6 wall-time budget red under load). DECISION (orchestrator): **WO-5 parked** — it must edit
  `models/thermal/{flash,heater,machines,mixer,valve}.py`, frozen byte-for-byte by F0 M9 (R-940; S1). The design-lane
  question (how C01/C02's numbers reach `failure.explanation` without editing frozen modules, e.g. a post-hoc
  provider evaluation in the application layer, or an M9 exception by ADR) goes to MSG's reviewer pass. WO-9's number
  assertions for C01/C02 are strict xfails until then. Alternative: architect consult now. Reversible by: unparking
  WO-5 after the ruling.
- **2026-11-06** ST architect pass done (9d822640): `docs/design/ST-stream-table.md`, ADR 0068 Proposed (ADR 0019 Am.
  13): `Inspection.get_stream_table(job_id)` computes on read from the bundle, nothing stored; CLI `openflowsheet
  streams`; no F0 measure can move. WO-1 (new files only) may start now; WO-2+ after `wp/MSG` merges (shared files).
  O6 resolved by the orchestrator: G3/E3 read Table 8 expectations from `s05_reference.json` `/saturation/450`
  (values agree), not from the architect's recollection. SQ-ST-1…6 → a specifier round with SQ-F6-5 (Amendment 5);
  defaults apply until ruled. O3 (web shell display deferred) → Frank, with ADR 0068's acceptance.
