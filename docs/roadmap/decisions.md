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
- **2026-11-06** Main CI 42132502629 (after the F0 merge) FAILED `check` on both archs: 38 ruff errors, all in the
  specifier's `docs/derivations/scripts/f6_std_seed_reference.py`, committed as docs-only without lint. Fixed in
  b9a05e16 (generator JSON byte-identical, `--check` PASS 107); F0's code itself was green. Procedure: lint any `.py`
  a design agent writes before committing. Amendment 5 (§17, cbf2230e): SQ-ST-1…6 adopted with precisions (Q1.R11–R12,
  Q2.R11, Q4.R10–R12; new flag `flash_near_phase_boundary`, G16; G2/G4 tolerances 8ε); SQ-F6-5 changed for
  `vapor: null` (Q4.R13: the vapour group takes the first liquid port). New finding A5-a (verifier reason
  `temperature_degenerate_unlifted` is an untyped string) → ST/MSG reviewer. 21 edits applied by one implementer pass.
- **2026-11-06** ST WO-1/WO-2 on `wp/ST` (c79a99db…dff3e439, pushed): G1–G7, G9, G10, G14, G16 pass (TH-C1 energy gap
  1.4e-10 W; Table 8 max rel 3.8e-10); **G8 fails** on T05b:SC-1 (temperature-degenerate lifted split, raw flash lists
  LIQUID only, Ḣ 2016 W off) — strict xfail, design-lane question E1 for ST's reviewer (default: reported failing). F0
  PASS. Registry entry deferred until `wp/MSG` merges (4 package-data tests red on `wp/ST` until WO-3). Batched for the
  reviewer: E1, D1-1 (verifier's per-component h uses Python `sum`, compensated from 3.12 — ST copies it for bitwise
  G7; also a 3.11-vs-3.12 identity question for the verifier itself), D1-3, D1-6/D1-7 schema departures.
- **2026-11-06** ADR 0055 WO-R1 done (6714958d): RP, line files 0.3/0.4, acceptances, release-line-v1 schema; D2
  deferred throughout. Findings F-1 (gate resolution needs `role`), F-2 (`git ls-tree` does no glob matching), F-3
  (ADR 0055's acceptance condition names REL.A11–A16, A21, deferred with D2) and Q-1…Q-15 go to the single reviewer
  pass over WO-R2…R6 together with WO-R1's design review of `gates[*]`. DECISION (orchestrator): build WO-R2/R3 on
  `wp/RP` now on RP's text. Alternative: wait for the review of RP first. Reversible by: rework on the branch.
- **2026-11-06** RP WO-R2/R3 done on `wp/RP` (fdc4f9a0, aa73d933, 2bac7fa9): REL.A01–A10 pass (A03 limited to the
  fixture comparison at this checkout); F0 PASS. Questions Q-B1…Q-B5 batched for the reviewer. Next: WO-R6 + WO-R4
  (brief `docs/briefs/REL-build-WO-R4-R6.md`), including one `release_rc` dispatch on `wp/RP` for REL.A17/N-4.

## 2026-11-06 — RP WO-R4/R6 hand-back; WO-R6 split

The WO-R4/R6 engineer stopped at the context cap: WO-R4 done (REL.A17 17/17; dispatch 42156856877 success, `check`
skipped, 8 RC jobs green; push 42156850745 `check` green both legs with `junit-<arch>`), `wheel_data_check.py` PASS
11/11, RP.L01–L10 PASS, full gate PASS 14995 at `bd672ff7`. Choices C-1…C-8, questions Q-C1 (`release-audit` in ADR
0055's WO-R4 row vs RP's D2 deferral), Q-C2 (junit evidence from the push run) go to the RP reviewer batch.
DECISION: rest of WO-R6 → two fresh engineers in sequence: WO-R6b (`release_rc.py` local steps 2–7, 9–16) then WO-R6c
(`release_evidence_manifest.py`, REL.A20, evidence manifest, gate). Alternative: one engineer for both (would overrun the
cap again). Reversible by: merging the two briefs.

## 2026-11-06 — MSG WO-9/10 done; review launched

`wp/MSG` head `8d955cd7` (pushed): WO-9 corpus + seven catalogue entries, WO-10 web shell; manifest
`evidence/MSG/b1a82351…` `implemented` (blocked on the `explain.md` reviews, D7-8, and D9-10). Full suite at `b1a82351`:
1 failed (description reviews, by design), 15065 passed. MSG-G0 (c) FAIL 156/109, all from F0's later v0.3.0 replay
fixtures (D9-10). Reviewer brief `docs/briefs/MSG-reviewer.md` (`4ddc2fb7`) batches nine questions incl. the WO-5 route
under F0 M9, D9-2, D9-10, gate changes, A5-a. RP WO-R6b done (`596dee3a`); WO-R6c engineer running.

## 2026-11-06 — MSG review (`2aee6dd3`) → WO-11/12

Not merge-ready: M1 (≈60 required entries still stubs), M2 (`pressure_rise` says turbine for valves), M3 (MSG-G0 must
PASS: F0 replaces (a)/(c)), M4 (missing gate records), M5 (explain.md: design lane approved with two edits; Frank's
review still blocks), M6 (c_4 register entry), M7 (WO-5a). Q1: sidecar at `revision_flowsheet.py:1029-1034` outside
M9; C01's main numbers deferred to F6 v2. Q2/Q3/Q4/Q6 as the engineer's defaults; D4-1 overruled; A5-a is the
verifier's.
DECISION: WO-5a (M7) before merge → yes. Alternative: merge with strict xfails, WO-5a after. Reversible by: reverting
WO-5a's commits.
DECISION: M1 → complete all required entries, no declared-stub limitation. Alternative: ship stubs declared (Frank's
call). Reversible by: Frank's late answer.
Brief `docs/briefs/MSG-build-WO11-12.md`.

## 2026-11-06 — MSG WO-11 done (`bc3ecf8b`)

WO-5a sidecar (outside M9), M2, Q2, Q6, Q7, S1–S4; C01 action, C02/C11 numbers, C06–C08/C10 codes lifted; 3 xfails
remain (C01 numbers → F6 v2; C08 "degc", C10 instance B need the revision at render time). F0 PASS; MSG-G0 a 0, b 0/562.
DECISION: render errors from the error document alone (C08/C10 stay declared gaps) → yes. Alternative: load the revision
at render time. Reversible by: a later MSG change adding revision context.
DECISION: `worker_lost`/`owner_lost`/`store_error` keep kind `bug` with specific actions. Alternative: an `environment`
kind (closed schema → ADR 0058 amendment). Reversible by: that amendment.
Next: WO-12 (M1, M3, M4, M6; full gate; manifest). R-942's number re-checked at the merge.

## 2026-11-06 — RP WO-R6c done (`05e3e069`); review launched

`release_evidence_manifest.py`: REL.A20 FAIL as RP states it (RP.S18 "every other check passes" sees changed-form
fails; Q-C5). Full gate at `3e7ccf00`: 29 fail + 1 error, all browser smoke under load (alone 31 pass). Manifest
`evidence/S15/3e7ccf00…` `implemented` (schema refuses `RP` and `REL040`, Q-C6). Reviewer brief
`docs/briefs/RP-reviewer.md` batches F-1…F-3, Q-1…Q-15, gates[*], ADR 0055 acceptance restatement, Q-B*, Q-C1…C6.

## 2026-11-06 — RP review (`d1b4a593`) → WO-R7

RP sound once amended (A-1…A-8). Must-fix: M-1 standing-mode decision items unpinned (mutation passed 40/40), M-2
REL.A20 via A-1 (S18 to changed form), M-3 ADR 0055 restated acceptance. Before K3: schema ADR for `REL[0-9]{3,}`;
ADR 0055 Accepted on the restated condition. Should-fix S-1…S-7.
DECISION: fold S-1…S-5, S-7 and C-12's check into WO-R7 now; S-6 (rehearse never-run steps) as a pre-K3 task.
Alternative: all should-fix at the cut. Reversible by: dropping those commits.
DECISION: F-8 (up to two messages to Frank per release, ADR D5 says one) → keep two, first only when non-empty (reviewer's
recommendation), asked of Frank. Reversible by: Frank's answer + an RP amendment.
Brief `docs/briefs/REL-build-WO-R7.md`.

## 2026-11-07 — workstation reboot; restart

Both engineers died with the reboot. State recovered from the worktrees:
- **MSG** WO-12 complete and pushed (`35403f42`): §4.2.6 list complete (68 codes pinned), MSG-G0 PASS (b, d), R-943,
  manifest `evidence/MSG/9c76b939…` `implemented`. Push CI 42217363836: both `check` legs and `default-install` fail on
  exactly one test, `explain: human pending` (18196 / 18168 passed). Only Frank's `explain.md` review blocks `tested`.
- **RP** WO-R7 code complete but unpushed at the reboot (`fd28ff7b`, now pushed): A-1…A-8 (R-942…R-949), ADR 0055
  restated (M-3), REL.A20 PASS with controls, M-1 mutation now 6 fail (was 0), S-1…S-5, S-7, C-12, C-23…C-29. F0 PASS.
  Full gate restarted by the orchestrator (load ~16); then the manifest re-take.
- **Register collision:** `wp/MSG` uses R-942 (Q1 amendment) and R-943 (c_4); `wp/RP` uses R-942…R-949. Whichever
  merges second renumbers its entries (and every reference) to the next free numbers.
DECISION: no second design-lane pass over WO-12's 51 completed entry texts. Alternative: a fresh reviewer prose check.
Reversible by: running that check before 0.4.0's cut (user-facing text, no numerics).
DECISION: X05 starts now (no prerequisite; roadmap design pass "none" but it touches replay identity and lifts R-140):
recon → specifier for the ADR and test spec → build. Alternative: wait for RP/MSG merges. Reversible by: parking it.

## 2026-11-07 — second crash; restart

The workstation crash killed RP's full gate (at 55 %, no result) and the X05 specifier (context ~255k; it left
`docs/derivations/scripts/x05_reference.py` untracked, no ADR). Restarted: RP's full gate at `fd28ff7b` (orchestrator,
background); a fresh X05 specifier that adopts or revises the predecessor's script and writes ADR 0069.
DECISION: fresh specifier rather than resuming the crashed one. Alternative: SendMessage to the 255k-context agent.
Reversible by: n/a (the script carries its decisions; the fresh agent may revise them and must say so).
DECISION: X02 recon now (architect pass next, roadmap). Alternative: wait. Reversible by: parking it.

## 2026-11-07 — X05 ADR 0069 (`6b12ab54`, `004d7faa`) → build

ADR 0069 Proposed: packaged lock via symlink (D1), exact version check over a fixed 9-distribution runtime closure
(D2/D3), same hash in checkout and wheel (D4), no schema change (D5), T08.A19 retired → X05.A11, A13–A17 (D7);
25 assertions, 36 cases; reference script `--check` PASS. Frank: Q-F1…F3 (defaults yes/no/no) + acceptance.
DECISION: build X05 now on `wp/X05` (WO-1…3, one Opus engineer, then a reviewer) before Frank accepts ADR 0069, with
Q-F1's pins as an isolated commit. Alternative: wait for acceptance. Reversible by: not merging; reverting the pin commit.
CPU rule (hub, 2026-11-07): one full gate at a time on TRS2; ≤ ~36 busy cores.

## 2026-11-07 — X02 design (`6b807f0e`, `f9e72ff5`): note + ADR 0070 (Am. 15)

Found a shipped defect (Part C): under `T08-warm-v1` a coupled run with > 1 outer iteration does not record its first
warm start (bundle from the final inner run, `revision_run.py:837`; label `route_initializer`, `coupled_run.py:682`);
its replay starts cold. Design: `solve_body.warm_start {job_id?, coupling?}` (D1), outer start checked then accepted or
recorded rejected (D3), warm reactor variant with `child_warm.py` loading the pinned `child.py` (D4), warm experiment
key member `start.profile_sha256` only when used (D5), certificate unchanged + disclosure (D6). WO-1…6; G0 cold
identity incl. every recorded experiment key; G5 on the workstation. Frank Q1…Q6 (defaults).
DECISION: X02 build waits for a free agent slot after RP's manifest re-take (RP is nearer to merge and needed for the
0.4.0 cut). Alternative: start X02 WO-1 now and queue RP. Reversible by: reordering.

## 2026-11-07 — RP manifest `tested`; X02 WO-1/2 done

RP: manifest `evidence/S15/fd28ff7b…` `tested` (REL.A01–A10, A17–A20 PASS; gate PASS 15070 at `fd28ff7b`; CI
42320544169 green); main merged into `wp/RP` (`98540811`, F0 PASS); CI on the merge head running, then merge to main.
X02 (`wp/X02`): WO-1 fixed the shipped defect (failing-first: bundle lacked `warm_start`, reproduce MISMATCH; after: 5/5
incl. control), WO-2 contract (Am. 15 schemas, admission A1/A2, `explicit-v1`, c_4 link `0af895a0…`, Q26 pins). F0 PASS.
Questions batched for the X02 reviewer: provisional R-950; c_4 clash with `wp/MSG` (second merger becomes c_5);
x₀ rejection reason form. Next: WO-3 (outer start), WO-4 (external-start plumbing) on a fresh engineer.

## 2026-11-07 — RP merged (`ad1ffd74`); X02 WO-3/4 done

RP merged into main (CI 42374299572 green at `98540811`; F0 PASS on main). X02 WO-3 (outer start; G3 a–f pass: restart
1 outer iteration vs 2, w bitwise equal; replay MATCH) and WO-4 (external-start plumbing; G4 a–f on the synthetic warm
child; G0: 163 recorded experiment keys recompute with 0 differences; F0 PASS). For the X02 reviewer: D-11 (the note's
G3 (c) premise false — every grid point converges on the registered loop; test uses a lowered H₂ make-up), D-13 (a
declared iterate can move one ulp through u = w₀/s), D-14 (recovery-edges E9 row), D-20, D-21 (global-state allowlist
35 → 36). Next: WO-5 (warm reactor variant + workstation campaign), fresh engineer, within the CPU rule.

## 2026-11-07 — X02 WO-5 measured: the warm reactor variant does not pay

G5 (`evidence/X02/69c4a24d…`): (a) cold new variant = v3 bitwise at 8/8 inlets; (b) warm vs cold max rel 1.92e-7
(> 1e-7; registering against `precision_floor_rel` 1e-6 breaks I3's decade gap); (c) warm ~21 % slower overall (287 vs
133 s, 383 vs 420 s) — the note's §3.1 premise (10–15 % faster) is false; (e) Part A on v3: restart 1 outer iteration,
1 call, 25 s vs 4 iterations, 175 s cold. G5d not run.
DECISION: do not register the warm variant in X02; Frank's Q1 default flips to no (re-asked with the numbers). The X02
reviewer rules whether `child_warm.py` stays in `src/` unregistered or leaves the package (campaign script and records
kept as evidence). Alternative: register with a manifest note / raise the floor. Reversible by: registering later with
the handoff's commands.
Next: the single X02 reviewer pass (WO-1…5 + batched questions), then WO-6 close-out (fixes, full gate, manifest).

## 2026-11-07 — X02 review (`a7139dee`) → WO-6

Sound for identity; no code defect (reviewer re-ran 88 + 294 tests; cold coupled run main vs branch: 9 artifacts + R0
identical). Must-fix: M-1 (note/ADR still promise the warm variant; amendments A-1…A-9), M-2 (recovery-edges E9
`enabled: default`). Ruling 1: the warm variant leaves the package (child_warm.py, tests, provisional variant, campaign
script); evidence and WO-4 plumbing stay. S-1…S-4 incl. S-2 G5d on v3 (~10 reactor calls). Register: R-950 for c_4;
second of X02/MSG to merge renumbers. Do not squash (evidence pins 69c4a24d, 005d206f). WO-6 engineer launched.

## 2026-11-07 — X05 built (`82030102`); one CI dispatch; review launched

X05 WO-1…3: A01–A20, A22 (a) (52 F0 bundles MATCH from the wheel, outside the tree), A23–A25 static PASS; F0 PASS;
gate PASS 14934 at `42c84f1d`; push CI 42379232642 green; manifest `evidence/X05/42c84f1d…` `tested` with 4 checks
unsupported pending `dist`/`clean-install`.
DECISION: one `workflow_dispatch` of `ci.yml` on `wp/X05` (run 42391223708) to run `dist`/`clean-install` for A20's
sdist half, A21, A22 (b), A25's CI half, Q-N2. Alternative: leave them unsupported. Reversible by: n/a (CI only).
Reviewer brief `docs/briefs/X05-reviewer.md`.

## 2026-11-07 — X05 review (`8121f245`) → WO-4 fix round

Code sound (49 + 14 tests, reference `--check` PASS). Must-fix: M1 — my dispatch 42391223708 lacked the RC input, so
`dist`/`clean-install` were skipped (cancelled); re-dispatch after the main merge with main's `release_rc` input. M2 —
merge main; RP `release-procedure.md:422` step 4 `a19.*` → `x05.*`. S1: `run/lock.py:175` re-raised memo exception
grows its traceback (`with_traceback(None)` + depth assertion).
DECISION: adding `[4, "x05.*"]` and `tests/test_x05_*.py` to a 0.4 gate in `release/lines/0.4.json` → deferred to the
0.4.0 cut's specifier pass (RP §13: gate criteria and `rc_items` are design-lane fields). Alternative: build-lane edit
now (R-921 watch item). Reversible by: the cut's specifier pass adding it.
At merge: ADR 0069 Accepted only on Frank's word; register lines above R-950.

## 2026-11-07 — X02 WO-6 (`wp/X02` `8d15e28c`) stopped at G5d (iii); ruling D-32

WO-6 done: M-1 (A-1…A-9, ADR 0070 edits), ruling 1 (warm child, variant, campaign script removed), M-2 (E9 default),
S-1/S-3 (111 targeted tests), R-950 kept as c_4. G5d on v3 (`evidence/X02/dcb499ee…/g5d-v3.json`): (i) cold VERIFIED 4
outer, 193.7 s; (ii) same-revision restart VERIFIED 1 outer, 1 call, 24.7 s; (iii) neighbour (SPEC-S3-T +2 K, moves û
83.7 bounds): cold VERIFIED 4 outer, 181.5 s; warm VERIFIED **4** outer, 222.7 s; Δû bound held (3.76e-4 ≤ 1.64e-3).
The note's "warm takes fewer outer iterations" criterion failed → escalated.
DECISION: G5d (iii) → the criterion stays in the note and the manifest as **failed** (not removed, not relaxed); the
premise (an outer start near a neighbour's fixed point saves outer iterations) is recorded false for this edit; ADR 0070
Consequences bullet 1 withdraws any neighbour-speedup claim; the package's claims rest on (ii) and identity, as D-29 did
for the warm reactor. Alternative: drop the criterion from the gate (engineer's default; rejected: narrows a gate after
it failed) or hold X02 for a new design. Reversible by: Frank's X02 Q7.
X02 still merges only after Frank accepts ADR 0070 (Q5 as stated). WO-7 (close-out) next: ADR/note text, full gate, F0,
manifest `S16` (frozen pattern refuses `X02`; R-878 rule as RP's S15), CI.

## 2026-11-07 — OPT design (`e4316d9c`): note + ADR 0071 (Am. 16)

Recon (M03 NLP is a SYN-001-only library; no surface; E01 cost/LCA unreachable) → architect brief
`docs/briefs/OPT-architect.md` → design. Key: `revision_eo` only (coupled refused: no exact derivative; legacy declared,
refused); separate optimisation request document; decisions target `role: fixed` specifications; M03 behind an
`NlpHost` protocol, SYN-001 bit-identical; V1 truth = cold re-solve on the production route; job operation `optimize`
(ADR 0019 Am. 16), validate lift (R-129); replay re-checks the certified chain, not Ipopt. WO-1…WO-7, gates G1–G21.
Frank OPT Q1–Q8 (defaults). Architect least sure of: F1 bit-identical last-attempt residual (G4), F2 duty-spec margin
vs `orchestrator/region.py`, F3 Ipopt inline vs worker identity (G12), F4 thermal port regimes — for the reviewer.
DECISION: OPT build starts now on `wp/OPT` (WO-1) while X02 closes and X05 waits for CI. Alternative: wait for Frank's
Q1–Q8. Reversible by: the defaults are isolated per WO; a late answer reworks the WO it touches.

## 2026-11-07 — X02 WO-7 done (`wp/X02` `c05a9e84`); OPT WO-1/WO-2 done (`wp/OPT` `508086b0`)

X02: gate PASS 15138 at `2ab11b66`; F0 PASS; CI 42398109849 / 42405646392 green; manifest
`evidence/X02/2ab11b66…` `tested` (18 checks; G5b and G5d (iii) `fail` + accepted_fail, G5c not_applicable).
DECISION: X02 D-33 (filed as `X02`, not `S16`) → accepted: ADR 0059 D1 (Accepted, R-938) admits `X[0-9]{2}`; my brief's
premise was stale. Alternative: S16 alias (ADR 0059 rejects aliases). Reversible by: moving the directory in one commit.
DECISION: X02 D-34 (`tested` with two `fail` checks of withdrawn claims, T08 precedent) → accepted; both failures are
of claims the package no longer makes (warm variant unregistered, neighbour speed-up withdrawn). Alternative:
`implemented`. Reversible by: Frank's X02 Q7 / a manifest re-take.
X02 merges after Frank accepts ADR 0070 (Q5). OPT: WO-1 SYN-001 bit-identical (dump `cmp`, both envs), F0 PASS; WO-2
F1 holds (8 cases, 0 entries differ), F2 holds for composition-independent K; D-12 (Q4′ refuses splits not judged by
tp_margin) → for OPT's reviewer.

## 2026-11-07 — X05 merged into main (`3e93c9a7`)

No-squash merge of `wp/X05` `1e5b3252` (main had moved by docs only). Push CI 42405801772/42405801801 green; RC
dispatch 42397255469 green; gate PASS 15138 at `830e7556`. On main after merge: F0 PASS (M1–M9), support matrix 0
problems, harvest + X05 lock tests 54 passed. ADR 0069 stays Proposed; its register lines wait for Frank. Worktree
removed.

## 2026-11-07 — X10 inventory (`wp/X10` `c45e8e08`) and review (`827abed4`) → fix round

150 pairs (30 models × 5 selectable providers): off CoolProp 41 VERIFIED, 1 UNVERIFIED, 2 bound-not-solved, 76
refused, 0 errors; CoolProp 10 VERIFIED with the extra. Review: faithful measurement; M-1 — `c1.reactor_surrogate` on
`benchmarks/m04/c1-surrogate.json` is UNVERIFIED on the user path (same policy `T06-revision-v2` as M04's test, which
solves a different flowsheet): the derivative witness step h = 3e-5 mol/s is 14–21 % of the per-tube flows
(J − FD falls 4× per halving: truncation, not a Jacobian defect) → harvest class E + support-matrix row. S-1…S-4, D-2
wording. My brief's premise (a policy difference) was wrong.
DECISION: open a design-lane follow-up "derivative-witness step relative to the state (small-flow `pr-c1-v1`
revisions)" for the scaling/certificate policy owner, not inside X10. Alternative: fix in X10 (out of its measurement
scope). Reversible by: folding it into X10 gaps (0.6).
I stopped X10's first full gate (stale after the fix round); one gate runs after the fixes.

## 2026-11-07 — OPT WO-3, WO-4, WO-4b done (`wp/OPT` `2dcb5772`)

WO-3: request schema, Halton starts, static readiness, platform-aware probe (linux-x86_64 only), validate lift
(library path; the application member waits for WO-6's surface link, D-19). WO-4/4b: optimiser on revision flowsheets;
analytic gates vs mpmath (30 digits): OPT-A1 Q rel 1.0e-11, λ exact; OPT-A2/A2b all starts verified, errors ≤ 2.2e-10;
OPT-N1 NOT_VERIFIED `PHASE_REGIME_CHANGED(U-PHF)`; legacy/coupled routes refused; OPT-C0 cost objective rel 1.0e-11,
KKT verified. G2 SYN-001 identical both envs; F0 PASS; 765 + 196 tests. Open for the design lane: D-12, D-18, D-24,
D-28, D-30, D-32.
C-MW (297 columns) cannot verify: (1) components exactly zero at the start (ethanol) are unbounded by §4.2.3's
`zero_at_start_pinned_by_regime` rule but are not pinned on C-MW → Ipopt drives them negative, twin DomainError;
(2) its 19 held TWO_PHASE stages carry no margin → V4/V5 refuse.
DECISION: continue with WO-5 (which builds §4.7's held mode and may settle (2)); put (1) — a false premise in §4.2.3 —
and whatever of (2) WO-5 leaves to OPT's single reviewer pass, not a mid-build architect consult: C-MW is G17's
performance record, not a pass/fail gate, and no analytic gate depends on it. Alternative: a fresh architect consult
now. Reversible by: consulting before WO-6 if WO-5 finds the premise blocks it.

## 2026-11-07 — OPT WO-5 (`wp/OPT` `826cc4c4`): G10 fails as designed → architect consult

WO-5 built the phase rows, held mode, `phase_bounds_active`; G1/G2 PASS; G7/G8/C0 within tolerance (not byte-identical:
new LIQUID rows); G10's Ipopt part passes (|T − T_b| = 9.1e-10 K) but V1's cold re-solve at the bubble point is
ILL_CONDITIONED (rcond ≈ 2.27e-6·ΔQ; branches meet) → `NOT_VERIFIED` (D-37, xfail strict). C-MW: TWO_PHASE null
margins still fail V4/V5 (D-12); zero-at-start ethanol still unbounded.
DECISION: consult a fresh architect now (brief `docs/briefs/OPT-architect-consult.md`): three premises are false by
measurement, which is the case the budget rule names for a mid-build consult; WO-6 waits for the amendment so it does
not build on the old text. Alternative: fold into the reviewer pass after WO-7. Reversible by: n/a (a consult).

## 2026-11-08 — OPT design amendment (`9318904a`, note §9, ADR 0071)

A-1 (D-37): V1 may pass on a "phase-boundary form" (the certificate's matrix minus the active splits' pinned columns
and dropped rows; same screen/thresholds/grade); K04 and ordinary certificates unchanged; the record names the basis.
A-2: zero-at-start free flows form a zero subsystem, held at 0 when square (exact), else bounded [0, ∞); V4
`ZERO_SUBSYSTEM_CHANGED`. A-3: margins are the closure's own test (TWO_PHASE: smaller phase flow / N0); rows only where
guarded; else admitted "unguarded" and listed (R-924) — replaces D-12's refusal. New WO-5b (A-2, A-3), WO-5c (A-1);
gates G10 amended, G10a–d, G22–G24. Frank: Q7 reworded, Q9 new. Architect least sure of F6 (other certificate checks at
T_b), F7 (C-MW zero subsystem square), F8 (pr-c1 closure value semantics).

## 2026-11-08 — X10 merged into main (`6b641fd6`); OPT WO-5b done

X10: gate PASS 15161 at `5c5e562d` (first run at `a17a55c9` FAILED on ruff E501 in my merge comment; fixed, re-run);
CI 42421631998/42421631954 green; on main after merge F0 PASS, support matrix 0 problems. Worktree removed.
OPT WO-5b (`3554636d`): A-2/A-3 built; G22 PASS (C-MW both starts KKT-verified, 0 DomainError; zero subsystem 63/63
square, ethanol exactly 0.0 on re-solve: F7 holds); F8: pr-c1 margins None. D-42 (γ–φ held single-phase splits never
certify under K04's witness) and D-44 (earlier G2 `--nlp` dumps compared UNSUPPORTED reports — environment variables
missing; `optimize_revision` lacked M03's audit probe) → WO-5c re-takes G2 against `ad971d32` and fixes the probe.

## 2026-11-08 — OPT WO-5c done (`wp/OPT` `1d909ef9`+); RRC design pass started

WO-5c: A-1 built; F6 held (at T_b every certificate check but regularity passes); G10 PASS (KKT_POINT_VERIFIED on the
phase-boundary form; |Q−Q*|/Q* 1.9e-11; λ vs closed-form λ* rel 1.9e-11); G10a–d PASS; D-46 unaudited stack refused.
G2 re-taken properly (D-44): base `ad971d32` vs `1d909ef9` identical in the audited env (`b6bbafdb…`, solved reports)
and default env (`6e028e8d…`). For the reviewer: D-45 (Q1′ accepts the boundary basis), D-50 (G10d tolerances
disagree). WO-6 started. RRC: recon → brief `docs/briefs/RRC-architect.md` → architect running (ADR 0072).

## 2026-11-08 — RRC design (`1566da46`): note + ADR 0072; OPT WO-6 part 1

RRC: "revision continuation" — ADR 0010 D2's map p(λ) = p* + (1−λ)(p_src − p*) from the nearest ancestor revision with
a VERIFIED solve (same model_version/constants), moving only differing operating values (default-deny allowlist);
policy `RRC-revision-v1` (new `eo_recovery` value, not default); order spec-continuation → revision continuation →
ADR 0015 restart, one recovery per step; no registered record moves; three frozen schemas widen additively (Frank
FQ1). WO-1…6, gates G1–G10 + F1/F2. Least sure: whether any column case fails without edge 3 (L-COL-9 lift), NET-02
path regime, stored pinned zeros.
DECISION: RRC build starts now on `wp/RRC` (WO-1, WO-2) beside OPT WO-6b; WO-3 (executor) rebases after OPT merges.
Merge only after Frank's FQ1. Alternative: wait for Frank. Reversible by: the branch stays unmerged.
OPT WO-6 part 1 (`fe615cb6`): `optimize` job built; 13 surface/Q26 tests fail until part 2 (WO-6b running).
DECISION: OPT D-58 (Q26 allow-lists the request's numeric problem-definition containers by full path, as R-235's
`body/inlet/n`) → accepted pending the reviewer. Alternative: drop numeric starts (changes the request schema).
Reversible by: reverting the isolated commit.

## 2026-11-08 — RRC WO-1/WO-2 done (`wp/RRC` `db5934cb`)

Policy value, `RRC-revision-v1` (defined, not offered: D-1), exact-rational revision levels, three schema widenings
(only their file hashes move: solve-policy, attempt-context, solution-certificate; MCP tool-list digest, registry and
the four offered policies' hashes unchanged), precondition checks R5/R6/R8/R9a. F0 PASS; 557 + 43 targeted tests; edge-3
files untouched. WO-3 waits for OPT's executor changes. D-1 (offering the policy moves `get_project.solve_policies`) →
for RRC's reviewer, done in WO-4.
DECISION: the derivative-witness step policy (X10 L-X10-1: surrogate UNVERIFIED at small flows; OPT D-42: γ–φ held
single-phase splits never certify) → queued as one design-lane item after OPT and RRC, not started now: any change to
K04's witness moves certificate bytes of registered records (an identity move that needs Frank). Alternative: a
specifier pass now. Reversible by: starting it earlier.

## 2026-11-08 — OPT WO-6/WO-7 done (`wp/OPT` `48733e55`); reviewer started

WO-6: `optimize` job, c_4 link (D_4 `3fb06cad…`, strip → D_3 `455d01eb…`), replay (re-checks the certified chain; x86
fixture MATCH without Ipopt), CLI, G11–G16. WO-7: §4.9 near-threshold rule (D-68); G19 interior cost optimum vs golden
section 0.23 Pa (tol 10 Pa), TAC vs hand rel 6e-16; G20 LCA vs bisection 2.6e-10 K, GWP bitwise; user guide page;
manifest `evidence/OPT/a46ea80f…` `implemented` (OPT.D61 `fail`, G21 + G13.aarch64 `unsupported`). F0 PASS; G2
`b6bbafdb…` unchanged.
OPT cannot reach `tested` until the two changed binding descriptions (`validate.md`, `submit_job.md`) carry the
design-lane review (OPT's reviewer, now) and Frank's human review (`test_every_description_is_reviewed_by_both_lanes`,
T07 §11.3). Added to Frank's list. D-70 (Ipopt crawl on OPT-L from the feasible side) → declared limitation L-OPT-2,
for the reviewer.

## 2026-11-08 — OPT review (`d25c16fb`, CI addendum `638523b3`) → fix round WO-8

Verdict sound: no path to a false KKT_POINT_VERIFIED; no ordinary certificate changes; A-1 sound; unguarded admission
fails safe. Must-fix M1 (replay floors each verification float at its judging check's tolerance — not new T08-v2
floor names; aarch64 differed 4.4e-16 abs on `stationarity_residual_inf`), M2 (studies → application imports: invert
the dependency), M3 (six fixture `solve-policy.json` registered as archived outputs, R-939 addendum), M4 (routes.js),
M5 (`without_opt` strip for M02's solve snapshot), M6 (M03 message byte-identical without the extra on aarch64).
S1–S5. D-61: both descriptions pass the design-lane review; Frank's human review open. CI run 42431066903 (at
`de18aca2`) failed 7/7/10 on x86/default-install/aarch64, all covered by M1–M6 or D-61.

## 2026-11-08 — OPT WO-8 fix round done (`wp/OPT` `496e003a`); full gate + CI running

M1 (replay floors per judging check), M2 (`RevisionRoutes` protocol in `studies/nlp/host.py`, supplied by
`application/revision_routes.py`; no application import under `studies/`), M3–M6, S2–S5 done; S1 declared for 0.4
(D-84); D-61 design-lane reviews recorded (human pending). F0 PASS; G2 identical (default `6e028e8d…`, audited
`b6bbafdb…`); audited G7–G10/G12/G13/G19/G20 21 passed; G22 all three verify. Incident: a nested sub-agent outlived its
parent engineer; I committed its edits as WIP while it was still working; no work lost (memory note added).
DECISION: RRC WO-3 (executor integration) starts now on `wp/RRC` from main instead of waiting for OPT's merge (OPT now
waits on Frank: description reviews + ADR 0071); whichever merges second resolves the executor conflict (OPT adds
`RegionResult.final_system`). Alternative: wait. Reversible by: rebasing `wp/RRC` onto `wp/OPT`.

## 2026-11-08 — RRC WO-3/4/5 done (`wp/RRC` `dc205d90`); OPT gate FAIL at `496e003a`

RRC: WO-3 executor integration (G2/G3/G6 pass; F1 4.4e-13, F2 2.0e-14 scaled); WO-4 application (ancestor lookup,
`solve-path.json` member, replay from the bundle alone: 4 bundles MATCH; `RRC-revision-v1` offered — served
`solve_policies` digest `74e41d71…` → `94c6ae7c…`, MCP tool list unchanged); WO-5 pre-registered candidate table
committed before any run (`cba5e8e2`): 10 candidates × 3 policies all reported; G4 N1 (NET-02) BOUND_BLOCKED → VERIFIED,
1.96e-9 scaled from the restart's root; G5 C3 (M1-recycle) BOUND_BLOCKED → VERIFIED → **L-COL-9 narrowed**, L21
narrowed. F0 PASS throughout. For the reviewer: D-11 (which edits are continuable, by parameter family), D-5, D-10.
OPT full gate at `496e003a`: FAIL — 2 failed / 15335 passed (D-61 human reviews, expected; T07 global-state allowlist
hit `@cache` in `studies/nlp/request.py` from M2) + mypy 3 errors in `benchmarks/opt/` → WO-8c fix running.

## 2026-11-08 — RRC review (`ed522d7c`) → fix round WO-7

Mechanism sound; no code must-fix; nothing changes under the four existing policies. M1 (FQ1 wording: enums widen, no
member added) → corrected in `docs/FRANK_QUESTIONS.md` now. M2: not a superset of `T06-revision-v2` — all five
qualifying candidates also converge under T06-revision-v2's restart, in fewer iterations; a stalled continuation can
fail where T06 succeeds → declare in guide, L21, E3c. S1 amend G2(f)/§5.8 (opening hash covers free columns only); S2
D-11 partition test; S3 guide wording; S4 renumbering includes the MR-7 test (at acceptance).
DECISION: N1 (a specification that pins an instance parameter `parameters.<key>` is always refused) → extend §5.4 with
D-11's family rule as the reviewer recommends, in the fix round. Alternative: keep refusing (fails safe). Reversible
by: reverting that commit.
DECISION: N2 → FQ3 re-asked with the measurements; default unchanged (one recovery per step, opt-in). Merge order:
OPT first, RRC rebases and runs its one full gate there.

## 2026-11-08 — RRC WO-7 done (`wp/RRC` `fe572ad5`)

Review fixes M2 (not-a-superset declared: guide, L21, E3c), S1 (G2(f)/§5.8 hash over free columns), S2 (22 + 7 = 29
family partition test), S3, N1 (`parameters.<key>` judged by the family rule), E3c row, interfaces-frozen, CHANGELOG,
D-5/D-6/D-10 note amendments. F0 PASS; RRC tests 71 passed; mypy/ruff clean; support matrix 0 problems. Waiting: OPT
merge (then rebase + full gate + CI), Frank FQ1 and ADR 0072 (then R-RRC renumbering and ADR D5 wording).

## 2026-11-08 — WIT specification (`5b9eb0f6`, K04 spec §4.8.1–9, ADR 0073 Proposed)

Rule per column: small positive flows whose registered central difference fails → re-differenced at halved steps with
a fourth-order stencil (k ≤ 8), resolved when successive estimates agree within 1e-8, never reading the AD Jacobian;
Wilson dormant vapour side → R-831's forward set; Wilson dormant liquid side → not differenced, declared (as R-281).
No certificate that passes today moves (57 F0 certificates; ADV-06 and GP-C3 354 K values unchanged by prototype);
intended moves only for today's failures (L-X10-1 surrogate → VERIFIED; OPT D-42 GP-C3 held splits verify).
Assertions WIT.A01–A14. Frank Q-WIT-1 (default yes).
DECISION: build WIT now on `wp/WIT`, evidence filed under `evidence/K04/` (a K04 follow-up, as the M02 follow-up was
filed under M02; ADR 0059 D1 has no WIT id). Alternative: amend ADR 0059 D1 for a WIT id. Reversible by: moving the
manifest directory. A reviewer pass follows (it touches certificates).

## 2026-11-08 — OPT full gate at `7b7aa770`: 1 failed / 15336 passed

The single failure is `test_every_description_is_reviewed_by_both_lanes` (only Frank's two human reviews pending,
D-61); mypy and ruff clean. OPT is otherwise ready: after Frank's review of `validate.md`/`submit_job.md` (recorded in
`REVIEW.json`) and his acceptance of ADR 0071, re-run CI, re-take the manifest as `tested` at that head, merge (no
squash), F0 on main; then RRC rebases. Merge-time items: surface link c_4 vs X02/MSG (whoever merges later renumbers),
global-state cache count (OPT and X02 each move 35 → 36: the combined count is 37), HARVEST_SIZE, R-960 provisional.

## 2026-11-08 — WIT built (`wp/WIT` `c32e3e4b`), review `1476a017` → fix round

Build: WIT.A01–A14 pass; surrogate VERIFIED; GP-C3 held splits verify; F0 PASS; passing certificates bitwise.
Review: must-fix F-1 (a round-off plateau — all four stencil values bitwise equal at two levels — lets the escalation
"agree" on ≈ 0 and pass a dropped AD term; reproduced on test doubles) → §4.8.3 (c) sentence + WIT.A15. F-2 (skip
ZERO_FLOW splits in classes 2/4), F-3 (two untested paths), F-4 (flash-style dormant-vapour split unmeasured).
E-1 ruled honest → M-6 part a (test, docstrings, §4.8.6, R-282 note) now; part b (the `c1.tp_flash` manifest
sentence moves its artifact hash and F0 M9 entry) → Frank Q-WIT-2.
DECISION: D-1 → amend ADR 0073 D5 to give Wilson's dormant-liquid columns their own reason (not
`pr_c1_zero_flow_columns`), while no registered certificate carries one. Alternative: reuse the pr-c1 reason literally.
Reversible by: reverting that commit.

## 2026-11-08 — WIT fix round done (`wp/WIT` `dbf884ad`); full gate + CI running

F-1 fixed (flat level cannot resolve a column whose coarser stencil was not flat; WIT.A15 7/9 fail before, 9/9 pass
after); no verdict changed on re-measure (A08, A09, E-1 window). F-2, F-3, F-4 (flash-style dormant vapour holds,
GP-C1 tp_flash 335/340 K VERIFIED), D-1 (`wilson_dormant_liquid_columns`), M-6 part a. F0 PASS; 31 + 3315 tests.
DECISION: WIT merges after its full gate, CI on both legs and a `tested` manifest under `evidence/K04/`, with ADR 0073
Proposed and Q-WIT-1 on its default (as X05 merged on a Proposed ADR); M-6 part b waits for Frank (Q-WIT-2).
Alternative: hold for Frank's acceptance of ADR 0073. Reversible by: revert the merge.

## 2026-11-08 — WIT manifest id

DECISION: under which id does WIT's evidence manifest file? → `X10a` (`evidence/X10a/dbf884ad…/manifest.json`).
`K04` (my brief) breaks the v0.1.0 pins (A01.K04.one_manifest, A21 harvest count, the CHANGELOG v0.1.0 review table,
which globs `[PKT]*`); `K04a` falls into the same glob; `WIT` is not admitted by the frozen manifest id pattern (ADR
0059 D1) and would need an ADR. WIT is the follow-up that closes X10's L-X10-1, and `X[0-9]{2}[a-z]?` admits `X10a`
with no schema change. Alternative: an ADR 0059 amendment admitting `WIT`. Reversible by: moving the directory and
the harvest `manifest:` paths, re-emitting the support matrix.

## 2026-11-08 — WIT merged

`wp/WIT` merged into main `f92af170` (no squash; manifest `evidence/X10a/dbf884ad…` tested, `d0dbd128`). Gate PASS
15194 at `dbf884ad`; CI 42459637834 green on both legs; on main after merge: F0 PASS M1–M9, support matrix `--check`
0 problems, harvest/changelog/manifest tests 471 passed. Worktree removed. OPT's merge must now update M-4 (D-42/D-82).

## 2026-11-08 — ST WO-3…6 on top of wp/MSG

DECISION: with every other 0.4 package waiting for Frank, does ST wait for MSG to reach main? → no: ST WO-3…6 build on
`wp/MSG` merged into `wp/ST` (brief `docs/briefs/ST-build-WO3-6.md`). MSG is reviewed and complete; only Frank's human
review of the `explain.md` text is pending, which does not touch the registry/catalogue machinery ST needs.
Alternative: wait idle. Reversible by: `wp/ST` re-merges main after MSG lands; if Frank's review changes MSG beyond the
text, re-merge `wp/MSG` and re-run ST's targeted tests. WO-7 (manifest, gate, review) waits for MSG on main.

## 2026-11-08 — ADR 0074 (release package id) written; applied as S15a

ADR 0074 (`930f912d`, Proposed): id `REL` + per-component code (digit below 10; k-digit number = k-th lower-case
letter + digits): 0.4.0 → `REL040` unchanged, 1.10.0 → `REL1b100`, 11.0.0 → `RELb1100` (N-4 settled). Accepted on its
build-lane condition like ADR 0059 (no Frank decision). Findings recorded, none acted on now: O-3 (nothing ties a line
file's `evidence_package` to its line → RP amendment RP.L11 before the 0.5 line file), O-4 (ADR 0055 D1 item 5 pointer
at K-2), O-5 (trailing-newline `$`, no change).
DECISION: where does ADR 0074 get applied? → package `S15a` (RP's K-1 follow-up), branch `wp/S15a`, full gate + CI +
manifest before merge. Alternative: fold into `wp/REL040` at the cut. Reversible by: rename the evidence dir.
DECISION: register id for ADR 0074 → R-970 (R-950…R-969 held provisionally by X02/OPT; RRC drafts unnumbered).
Alternative: next sequential R-950 and renumber the open branches. Reversible by: renumbering at merge.

## 2026-11-08 — S15a built (ADR 0074 applied)

`wp/S15a` `51c9e7f5` (schema + RID tests alone: 2 files) and `d7cb4dbb` (A-9 as RP §17.2, R-970, ADR 0074 Accepted on
its condition). RID.A01–A12 pass; `test_evidence_manifests.py` 488 (410 + 78); 11 related files 600 passed; F0 PASS
(the schema does not enter F0). Full gate and CI started at `d7cb4dbb`; manifest `evidence/S15a/…` after them.

## 2026-11-08 — ST WO-3…6 done; reviewer pass

`wp/ST` `6f55fc19` (main + `wp/MSG` merged + WO-3…6; D3-1…D6-3 in `docs/ST_DECISIONS.md`): G5, G11–G13, G15, A48
PASS; F0 PASS; served MCP digest `eaff4585…` → `6705fb05…` (c_5 on top of MSG's c_4); targeted 569 passed + G8 xfail
(E1). Known red: description reviews. ST's single reviewer pass starts now (brief `docs/briefs/ST-reviewer.md`); WO-7
(manifest, full gate, CI) after the review and after MSG lands on main. New Frank item: `get_stream_table.md` review.

## 2026-11-08 — ST review → fix round

Review `fb6a81f7`: not merge-ready. M1: E1 is a defect in ST's phase rule (R3 TP-flashes temperature-degenerate
lifted splits: vf 0 and H flow 2016 W low on T05b:SC-1, SC-3 likewise at units), ruling (b) scoped → rule R1′ (carried
lifted split, as the verifier reads it), G8 unchanged; amends ADR 0068 / design D4 (recorded before Frank accepts).
S1 per-unit G8; S2 no-bundle `not_found` variant; S3 description approved after 3 edits (design-lane act in
REVIEW.json, digest re-recorded); S4 route from `solve-path.json`. MSG-merge notes: MSG lands as a merge commit; c_4
contention with X02 → ST becomes c_6, re-measure G12 at merge; drop ST's duplicate R-942/R-943. Fix round brief
`docs/briefs/ST-fix-round.md`.

## 2026-11-08 — ST fix round done (`wp/ST` `e16f7e6f`)

M1 R1′ (`e2079456`): SC-1 envelope 2016.0 → 0.0 W, U-VLV 2016.0 → 0.0; SC-3 U-VLV/U-PHF ±2016 → 0; S2 H flow equals the
verifier's bitwise; only SC-1/SC-3 of 44 served 0.3.0 documents change; G8 passes (xfail removed, max 1.76e-4). S1
per-unit check (146 rows; corpus judged at the projection, max 2.703 of tol → direct SC-1/SC-3 unit test added);
A02-360's 2.73e-3 W is the projection (ST Ḣ = `checks.enthalpy_flow` bitwise). S2, S3 (served `ebb4ca84…`; design-lane
approval recorded in REVIEW.json), S4 (44 documents byte-identical), text amendments, D4-1. F0 PASS; 457 targeted.
Open for a design-lane confirmation at WO-7 (none reached by any corpus case): M1-1, M1-2 (mixture h → n·h as
`_phase_flow`), M1-3 (Q4.R12 (b)(ii) dropped), S1-1, and the products-style flash feed with a degeneracy row. ST's
WO-7 (manifest, full gate, CI) waits for MSG on main (Frank's `explain.md` read) and ADR 0068.

## 2026-11-08 — Frank: no local full gate before a merge when CI is green

Frank: "I feel the checks cost too much time. If CI passes why do it once more?" Measured on WIT: the local gate runs
the same `scripts/check.sh` as CI, but with fewer tests (15 194 passed / 3 206 skipped, 3 143 of them CoolProp, not
installed on TRS2) than CI (x86-64 18 291 / 109; aarch64 18 263 / 107); it adds only ~25 host-specific tests (CPU-
pinned floats, BLAS-thread control, dev-history checks), and costs 1 h 45 on the shared machine.
Rule now (CLAUDE.md "Gate by risk", amended): CI green on both architectures is the merge condition; F0 runs on main
after the merge; the local full gate runs only before a release-candidate cut or tag. S15a's running gate stopped.

## 2026-11-08 — S15a merged

`wp/S15a` merged into main `74747966` (manifest `c89c6e2b`, tested on CI 42469977863, first merge under the
green-CI rule). On main: F0 PASS, support matrix 0 problems, harvest/changelog/manifest tests 507 passed. HARVEST_SIZE
(76, 988, 126). Worktree removed. RP K-1 closed; K-2 (ADR 0055) and S-6 rehearsal remain before 0.4.0's K3.

## 2026-11-08 — Decision board for Frank

Frank asked for a way to read and answer pending items over remote control. Built a claude.ai artifact (private to
Frank) https://claude.ai/artifact/WBLrhuGuG9zosGy46Z1b2A: page `docs/decisions-board/index.html`, 40 items in its
`items` collection generated by `docs/decisions-board/build_items.py` (description texts pulled from the branches with
their diffs, ADR summaries with GitHub links, every Frank question with its default and alternatives); answers come back
in the `answers` collection, which the session reads and acts on. New questions: add to `build_items.py`, regenerate,
write the new item; close an answered one with `status: "closed"`. `FRANK_QUESTIONS.md` stays the record.

## 2026-11-08 — Frank answered all 40 board items

Record: `docs/FRANK_QUESTIONS.md` "Answers — Frank, 2026-11-08". All descriptions approved; ADRs 0055, 0068–0073
accepted; 0060–0067 stay Proposed; every default confirmed except two reversals: **ST O3** (web-shell display now, in
ST) and **X05 Q-F1** (do not pin the four transitive dependencies; revert `a58ef5a5`'s effect).
DECISION: merge order → MSG, X02, OPT, RRC, ST (ST needs MSG; RRC needs OPT; X02/OPT both claim surface link c_4, so
each later merge re-measures its link). Small follow-ups on their own branches: X05a (Q-F1 reversal), X10b (WIT M-6b,
Q-WIT-2). Alternative: X02 first. Reversible by: merge order only.
DECISION: register numbers by block to avoid collisions between branches merging in any order → X02 R-950…959, OPT
R-960…969, S15a R-970 (used), MSG R-975…979 (its R-942/R-943 renumbered), main-side acceptances (0055, 0069, 0073)
R-980…989, RRC R-990…999, ST R-1000…1009. Alternative: renumber sequentially at each merge. Reversible by: renumbering.

## 2026-11-08 — X05a built (Frank's Q-F1 = no)

`wp/X05a` `b43d94bc`: revert of `a58ef5a5` alone (`f5736deb`); A25 restated as its inverse (static: Requires-Dist =
the five direct pins only; floating path: an off-lock transitive member → `lock_sha256 = ""`, members named); ADR 0069
Accepted with Amendment 1 (Q-F1), ADR 0007 Am. 2; R-985…R-987, R-140 "Lifted by X05". 548 passed, 11 skipped;
`x05_reference.py --check` PASS; F0 PASS. D-10 (engineer): A25's CI half became a new `t08_rc.py lock-check --state
installed-free` that computes its expectation from the installed versions (CI's unconstrained install no longer
verifies by construction). DECISION: keep D-10 (it checks the honest outcome; dropping the CI half would remove a
check). Alternative: drop the CI half. Reversible by: revert D-10's commit. CI running; manifest `evidence/X05a/` after.

## 2026-11-08 — MSG merge prep done; human reviews must be recorded by Frank

`wp/MSG` `ff5443e3`: main merged twice (DM-1…DM-5), HARVEST_SIZE (78, 997, 129), MSG's R-942/R-943 → R-975/R-976
(RP's untouched), L41 re-synced after X05's text (catalogue sha `e4f940cc…` → `2252445a…`, two fixtures), D_4
`eaff4585…` unchanged; F0 PASS; only the description-review test fails. The permission system refused the agent's edit
recording Frank's human review in REVIEW.json — correct: a human review is not an agent's act. Not worked around.
Frank records all four (explain; validate, submit_job; get_stream_table) with a script he runs himself
(`record_frank_reviews.py` in the session scratchpad: checks each text's sha256 against the one shown on the board,
then commits on wp/MSG, wp/OPT, wp/ST). The filed MSG manifest `9c76b939…` keeps citing R-942/R-943 (evidence at its
commit); the new manifest cites R-975/R-976.

## 2026-11-08 — X05a merged

CI `42500882154` green on `b43d94bc` (both architectures, identity, default-install). Manifest
`evidence/X05a/b43d94bc…/manifest.json` tested (`9b21a881`, after merging main as `1f9cdadb`); HARVEST_SIZE
(76, 988, 126) → (77, 993, 126). Merged `dd16dab8`; F0 PASS on main; harvest + manifest tests 505 passed. The other
branches (MSG, X10b) re-take HARVEST_SIZE at their merge.

## 2026-11-08 — MSG merged

CI `42502713324` green on `5e9274db` (Frank's human review of `explain` included). Manifest
`evidence/MSG/5e9274db…/manifest.json` tested, merged with main in `38e46c2a`; HARVEST_SIZE (80, 1007, 129). Merged
`ed874b17`; on main F0 PASS, harvest/manifests/surface chain/`test_msg_*` 718 passed, 3 xfailed. Surface chain: MSG
holds c_4 (D_4 `eaff4585…`); X02 is next in the merge order (MSG, X02, OPT, RRC, ST) and re-measures its link as c_5.
Note: worktrees have no `.venv`; the main checkout's editable install imports main's `src`, so a worktree test run
with it tests main's code. CI is the authority for branch code; re-run targeted tests on main after each merge.

## 2026-11-08 — ST design-lane confirmations (`wp/ST` `e1a05916`)

Specifier: M1-1, M1-2 (n_tot·h = γ–φ `_phase_flow` bitwise; test DC-5), M1-3 (reason corrected), S1-1 confirmed. The
products-style case cannot occur (binder admits undeclared streams only from heater-style splits), but a neighbouring
defect does: R1′ fired on any degeneracy row naming the stream, incl. a flash drum's row on its inlet → ruling 5: R1′
only on `independent_split.<U>.<S>`, no-number branch on `temperature_degenerate_unlifted(<S>)`; DC-1…DC-6. ADR 0068
D3 amended (dated, quoted) after Frank's acceptance; no served output changes → board item `st-adr0068-am1`
(default: stands). DECISION: proceed on the amendment without waiting. Alternative: hold ST for Frank. Reversible by:
reverting WO-8a's ruling-5 commit. Next: ST WO-8a (merge main, ruling 5, R-942/943 clean-up), then WO-8b (web shell).

## 2026-11-08 — X02 merge prep done (`wp/X02` `51ef7460`); X10b CI green

X02: main merged (`f36b4a56`, 13 conflicts, D-35); link c_5 D_5 `f51b69bf…` (strip X02 → MSG's D_4 `eaff4585…`
exactly: no interaction, D_4 not re-recorded; D-36); global-state cache count 36 → 38 (main 37 + X02; D-37); ADR 0070
and ADR 0019 Am. 15 Accepted, R-950 final (c_5), R-951…R-955 (D-38); 1508 passed, 2 skipped (worktree `src`,
`PYTHONPATH=src`); ruff, format, mypy clean; F0 PASS. CI watched; then manifest re-take at the head, merge.
X10b: CI `42503117602` green on `c57d449a`; manifest brief `docs/briefs/X10b-manifest.md`.
Main: ruff E501 on two harvest comment lines after the MSG merge, fixed `89b7e008`. From now on the post-merge check
on main is F0 **and** `ruff check` + `ruff format --check` (the merge commit's text is not what CI tested).

## 2026-11-08 — X10b merged

Manifest `evidence/X10b/c57d449a…` tested (`d50d6c06`, after merging main `9bf45e98`; `case_hash` = sha256 of
`models/c1/flash.py` at that commit, `b1b47c28…`, the registered move); HARVEST_SIZE (81, 1015, 129). Merged
`d5035a76`; on main ruff clean, F0 PASS, harvest/manifests/L01/G7 tests 660 passed, 1 skipped. WIT's follow-ups are
done. X02 re-takes HARVEST_SIZE at its merge.

## 2026-11-08 — ST WO-8a done (`wp/ST` `9da2e022`)

Main merged twice (`420993d0`, `a333c762`); R-942/943 duplicates dropped (register = main's); ruling 5 in
`stream_table._inputs`/`_decide` (lifted by the split's own row, unlifted by exact reason); DC-1…DC-6 pass (DC-2/3/4
fail on the old code); 44 served 0.3.0 documents byte-identical; G7 41 bitwise, G8 1.756e-4, G8u 2.7027 unchanged;
1581 passed; F0 PASS. Three tests red since `e1a05916` (not WO-8a's): T08.A20 (envelope lacks `get_stream_table`) and
ADR 0025 A1 ×2 (`data_sha256`, `implementation_sha256` unclassified). Both have build-lane precedents (envelope
admission; per-package ADDENDA as M04/M05/E01/OPT) → WO-8b part 1, stop if a field hashes floats. ST's link is c_5
on the branch; at WO-7 it follows X02 (c_5) and OPT (c_6) → c_7. Next: WO-8b (the three tests + web-shell table).

## 2026-11-08 — ST WO-8b (`wp/ST` `3ba9edc3`): web-shell table done; one design-lane classification open

T08.A20: `get_stream_table` admitted to the envelope on four transports (22 → 23 operations), precedent MSG WO-7
`631a9f3f` after ADR acceptance (ADR 0068 accepted by Frank). Web shell (Frank's O3): streams screen shows the full
table below n/T/P (per stream total + per phase, `phase_source`, boundary flag, SI columns, null → "—" with reason;
`flash_failed` notice; unit/overall energy table); `routes.js` regenerated (was stale: a fourth pre-existing red);
the shell calls 18 operations; message catalogue `7573d7ea…` → `3ac1279a…`. DECISION (engineer): fetch the whole
table, no on-screen pager. Reversible by: `streamTableOf`. 2246 passed incl. browser smoke 32 (ran locally), node 98;
F0 PASS. Open: ADR 0025 D2.3 for `data_sha256` (SYN-001 hashes registered float literals) and
`implementation_sha256` → specifier ruling (brief `docs/briefs/ST-adr0025-classification.md`); default exact (as
`constants_sha256`).

## 2026-11-08 — X02 CI red on MSG G2 → catalogue entries (`d26bcd38`)

CI `42512488771` on `51ef7460`: 1 failure on all legs, `test_msg_coverage` G2 (X02's three codes had no MSG catalogue
entry; the merge-prep brief did not list `tests/test_msg_*`). Fix D-39: `warm_start_source_missing`,
`warm_start_unit_unknown` → `refusal` entries (kind `input` from MSG's kind table; unit param typed `text`);
`coupling_warm_start` allow-listed (trace label, never rendered). Catalogue `2252445a…` → `9ac2578a…`; D_4, D_5
unchanged; 378 passed; F0 PASS. Open (non-blocking): the two entries' prose is an engineer's draft → design-lane prose
check batched with OPT's new catalogue entries. Lesson: merge-prep briefs after MSG list `tests/test_msg_*` (OPT's does).

## 2026-11-08 — ST CI red at 8ce17244 (run 42517844608), fixed at eb1e0936

Three test bugs, no product code: `get_stream_table` had no pre-ST snapshot in `test_m02_schemas` G1c and
`test_m04_study_job` A42 (now skipped via `ST_OPERATIONS`, as MSG's `explain`); `test_st_core` Q1.A15c assumed
IAPWS/H2O for every run, but the CoolProp leg adds TH-C2 (R134a) — now uses the run's own provider and basis.
Missed locally because worktree tests imported main's `src` (the venv trap). ST_DECISIONS CI-1/CI-2. CI re-run pending.

## 2026-11-08 — X02 merged (35aa61e1)

`wp/X02` merged `--no-ff` after CI `42521075017` green on `d26bcd38` (both archs, identity, default-install);
manifest `evidence/X02/d26bcd38…/manifest.json` tested (c72e41fe, which also merged main; HARVEST_SIZE (83, 1029, 135)).
On main after the merge: ruff check + format OK; F0 PASS (M1–M9); targeted 1208 passed, 2 skipped. Surface chain now
c_5 (D_5 `f51b69bf…`); global-state caches 38. Next per the merge order: OPT merge prep (docs/briefs/OPT-merge-prep.md).
Open: design-lane prose check of X02's D-39 catalogue entries (batched with OPT's); X02 reviewer pass pending.

## 2026-11-09 — OPT merge prep done (wp/OPT a1963353); D-91 register numbering ruled

Merge prep per docs/briefs/OPT-merge-prep.md: OPT D-86…D-93 (merge of main, c_6 D_6 `3fdc797a…` with stripping OPT
giving D_5 exactly, caches 39, M-4 verified, ADR 0071 + ADR 0019 Am. 16 Accepted, MSG catalogue G2 entries, corpus C12
re-pointed to `nlp_solver_unavailable`; F0 PASS; targeted tests green). DECISION (D-91): ADR 0071's ten drafts → R-961…
R-969 in ADR order and the tenth (R-860 lifts) at R-988 (unused everywhere). Alternative: fold two drafts into one entry.
Reversible by: renumbering before merge. Brief docs/briefs/OPT-register-numbers.md. Design-lane batch (non-blocking):
prose of X02 D-39 + OPT D-92 catalogue entries, and OPT D-93 (which mistake C12 should register).

## 2026-11-09 — ST CI green at eb1e0936 (run 42527883250); OPT register numbered; RRC brief

ST green on both archs, identity and default-install after the CI-1/CI-2 test fixes; ST still waits for WO-7 (after
RRC merges: main merge, its chain link, ADR 0068 Accepted + amendment, R-1000…, manifest, CI). OPT: ADR 0071 drafts
numbered R-961…R-969, R-988 (c1b9b125, D-94); CI pending. RRC merge-prep brief written (docs/briefs/RRC-merge-prep.md):
ADR 0072 Accepted, FQ1 yes, FQ2–FQ4 default, drafts → R-990…R-995; starts after OPT merges.

## 2026-11-09 — OPT merged (937223ad)

`wp/OPT` merged `--no-ff` after CI `42534167073` green on `c1b9b125`; manifest `evidence/OPT/c1b9b125…` tested
(03e40679; audited env 21 passed, G2 hashes and G22 identical to WO-8b, D-95; G21 local full gate "unsupported", not
claimed; HARVEST_SIZE (85, 1039, 139)). On main after the merge: ruff OK; F0 PASS (M1–M9); targeted 1609 passed,
2 skipped, 21 deselected (nlp), 3 xfailed. Surface chain c_6 (D_6 `3fdc797a…`); caches 39. Next: RRC merge prep
(docs/briefs/RRC-merge-prep.md). Design-lane batch now ready: X02 D-39 + OPT D-92 prose, OPT D-93 (C12).

## 2026-11-09 — MSG catalogue prose ruling for X02/OPT codes (f7da1420)

`docs/reviews/MSG-catalogue-X02-OPT.md`: X02 entries kept/`why` rewritten; OPT `nlp_solver_unavailable` and
`request_invalid` (arg → `member`, root variant) rewritten; 7 stubs re-titled, kinds final, all `review: true` cleared
(138 → 129); allow-list reasons corrected; C12 keeps `nlp_solver_unavailable` but forces the solver probe unavailable
(latent install dependence); `task_unsupported` prose rewritten. Work order §5 (10 steps), acceptance A1–A9. F1 (G1
misses `OPT.*` check ids; loader forbids `.`) → separate MSG follow-up; F2 (U05 CLI pin install dependence) latent.
DECISION: apply the work order on a short branch after RRC merges and before ST's WO-7 → both then take it with one
main merge. Alternative: apply now (RRC, mid-merge of main, would have to re-merge the catalogue digest). Reversible
by: applying it earlier.

## 2026-11-09 — RRC merge prep done (wp/RRC fcba6656); CI pending

RRC D-39…D-45: main merged (8 conflicts, both sides kept; RRC's `revision_continuation` passes through OPT's
`write_revision_bundle`); no surface link (served digest = D_6 exactly; ST takes c_7); caches 39; ADR 0072 Accepted,
R-990…R-995; catalogue: 3 refusal-reason labels allow-listed (digest → `14921a20…`); no ADR 0025 addendum (no new
sha256 name); G8 had no CI coverage → new `tests/test_rrc_g8_determinism.py` (N1, C3 twice in fresh processes, x86-64
R0 pins; aarch64 leg checks cross-arch — a different R0 there is a G8 failure to escalate, not a pin to move); T08 B27
excludes RRC's policy as S11 did its column (design-lane glance at the manifest). F0 PASS; targeted tests green.

## 2026-11-09 — MSG catalogue ruling applied on wp/MSGp (8906f870)

Ruling §5 applied verbatim at base 9295f0fc; A1–A5, A7–A9 exact (digest `5e5026c5…`, review 138 → 129). A6: beyond the
stated U05 stderr lines, U05's stdout `detail.explanation` (why/action/gap) also moves — the refusal document carries its
explanation (MSG §3.7); `code`, `message`, `pointer` unchanged, `PINS_T07_SHA256` holds. DECISION: accept as the
ruling's direct consequence, no new ruling → noted for the design lane's next MSG read. Alternative: a ruling round
now. Reversible by: a later ruling. Next: after RRC merges, merge main into wp/MSGp, regenerate the digest-carrying
fixtures (RRC's allow-list also moves the digest), CI, merge — before ST's WO-7.

## 2026-11-09 — RRC CI red on V17-T10 (run 42547017088); ruling a109eea6 applied (wp/RRC 6b892b03)

Only failure: `test_g16b_reference_run[V17-T10-*]` T10-C3 (exact set of offered policies; RRC's R-995 adds
`RRC-revision-v1`). Ruling `docs/reviews/RRC-v17-t10.md`: a fourth reference document `t07_reference_rrc.json` in
T08's form (Amendment RRC-1, GC-18, R-996, RRC D-46), sha `621003a8…`; the three frozen documents unchanged; exclusion
rejected (it would make the expected answer false). Applied: A1–A8 exact (negative control fails GC-18 as stated);
G16-b 40/40; F0 PASS. Q1 (`t07_reference.py --check` in CI): no (85.6 s). CI re-run pending.

- 2026-11-09 — RRC CI green at 6b892b03 (run 42558001650, both archs, identity, default-install). Manifest engineer
  launched (brief docs/briefs/RRC-manifest.md). DECISION: wp/MSGp merges with its own MSG follow-up manifest at the
  re-based head (pattern evidence/MSG/5e9274db…), not folded into OPT's evidence; brief docs/briefs/MSGp-remerge.md
  (merge main after RRC, keep both sides' hand-written entries, regenerate, re-measure A1–A9 with the digest moving by
  RRC's additions only). Alternative: OPT follow-up manifest. Reversible by: dropping the manifest commit pre-merge.

- 2026-11-09 — RRC merged into main (cefee08d; evidence/RRC/6b892b03… tested, CI 42558001650; manifest 64e628a8,
  HARVEST_SIZE (86, 1046, 140)). Post-merge on main: ruff clean, F0 PASS (M1–M9), targeted tests (rrc, V17 reference,
  t08, harvest, manifests, msg, surface chain, global state) 1555 passed, 2 skipped, 3 xfailed. Note: manifest
  requirements D01/D20 only — the schema pattern `^[DA][0-9]{2}$` rejects V20. Next: wp/MSGp re-merge
  (docs/briefs/MSGp-remerge.md), then ST WO-7.

- 2026-11-09 — wp/MSGp re-based on main after RRC: merge 1602f72a (parents 8906f870, ed7718ae); only the two
  message_entry fixtures conflicted (generated, regenerated). A1 379/83/129 (main after RRC 379/83/138; RRC added no
  entries); A2 digest e3725b30… (main 14921a20…); A3–A9 hold, merged diff vs main per file = 8906f870's. Tests 1425
  passed, 2 skipped, 3 xfailed; msg check PASS; F0 PASS; ruff clean. D-96 amended. CI watched; manifest after green.

- 2026-11-09 — wp/MSGp merged into main (74ceab73; evidence/MSG/1602f72a… tested, CI 42570096932; manifest 3ba9ded9).
  Post-merge on main: ruff clean, F0 PASS, MSG check PASS (379/83/129), targeted tests 860 passed + 1 failed: the
  harvest size, because the MSGp brief (mine) omitted the harvest step. Fixed on main in one follow-up commit: 8 MSG
  limitations classified P in support_envelope.yaml, support matrix re-emitted (--check 0 problems), HARVEST_SIZE
  (86, 1046, 140) → (87, 1054, 140); harvest/t08/manifests 1132 passed, 2 skipped. Lesson: every manifest brief carries
  the harvest step. Next: ST WO-7 (docs/briefs/ST-WO7.md).

- 2026-11-09 — ST WO-7 on wp/ST (head 45122519: merge ced1519e, fixes db500230, docs): 12 conflicts, all both-sides;
  ST link c_5 → c_7 (R-1000), D_7 553b7612…, without_st = D_6 3fdc797a…; ADDENDA m02, m05, e01, opt, st; ADR 0068
  Accepted (Frank 2026-11-08), D3 amendment kept; register R-1000…1006. Numbers unchanged vs handoff (44 served docs
  byte-identical, G7 41 bitwise, G8 max 1.756e-4, G8u 2.7027, caches 39, A20 23); catalogue 386/90/129 `03818ed5…`;
  F0 PASS; ruff clean. CI watched; manifest brief docs/briefs/ST-manifest.md (harvest step included).

- 2026-11-09 — 0.4.0 readiness (Frank asked). Recon: ADR 0055 parts 1–3 are largely built (release_gate.py with
  standing acceptances, release_rc*.py, release_evidence_manifest.py, tests); WO-R5 deferred by Frank. Open before the
  cut: x05 gate entry in release/lines/0.4.json, schema ADR for REL[0-9]{3,}, ADR 0074 O-3 (RP.L11), S-6 rehearsal,
  local full gate; ST merge; X04 (no spec exists → specifier pass, brief docs/briefs/X04-specifier.md). Line
  acceptance needs ADR-F1…F8 Accepted but Frank kept 0060–0067 Proposed → board item rel04-line-acceptance (default:
  move the condition to 0.5). DECISION: X04 gets a specifier pass (ADR 0075 + test spec) before any build →
  alternative: drop X04 to 0.5. Reversible by: roadmap amendment.

- 2026-11-09 — ST merged into main (a053690d; evidence/ST/45122519… tested, CI 42585666096; manifest de2316e0, harvest
  5 limitations + 1 check, HARVEST_SIZE (88, 1059, 141)). The X04 specifier's commit ced0082f, made in the main
  checkout on top of the local merge, pushed the merge before the post-merge checks finished; the checks then passed:
  ruff clean, F0 PASS, MSG check 386/90/129, matrix 0 problems, targeted tests 1519 passed, 2 skipped, 3 xfailed.
  Lesson: no merge in the main checkout while a docs agent commits there. Wave MSG → X02 → OPT → RRC → ST complete.
- 2026-11-09 — X04 specified: ADR 0075 (Proposed), test spec A1–A40, WO-1…WO-5, generator x04_reference.py (17
  claims). Board: adr-0075, x04-fq1…fq4. Finding: catalogue `J/(mol*K)` vs ADR 0062 `J/(mol K)` (align at F2).
  DECISION: build starts on the Proposed ADR (engineer A, docs/briefs/X04-build-A.md); merge needs Frank's accept.
  Alternative: wait for the accept. Reversible by: branch not merged.

- 2026-11-09 — Correction: the "schema ADR admitting REL[0-9]{3,}" is done — ADR 0074 (Accepted 2026-11-08, D1 applied
  in 51c9e7f5; `work_package` admits REL ids). Remaining release prep in one build item, brief
  docs/briefs/REL040-prep.md (wp/REL040p): x05 gate entry in release/lines/0.4.json; RP.L11 (ADR 0074 O-3 default);
  S-6 rehearsal (`release_rc.py local`, every step, records in the scratchpad only; no tag/release/publish).

- 2026-11-09 — X04 engineer A: WO-1 (display core, 44dd16db) and WO-2 (ambient, D9 catalogue entries; cbd220b6,
  2811d0fd) on wp/X04 (82251ffc); A1–A13 pass (498 + 41 tests), F0 PASS, MSG check 391 entries; decisions D-1…D-4.
  Known red: surface chain (11; get_project's output schema moves the served digest) and 5 R4-G3 snapshot tests.
  DECISION: X04 takes chain link c_8 with register block R-1010…1019 (precedent X02 c_5, OPT c_6, ST c_7 by the build
  lane), taken with SNAPSHOT_X04/without_x04 in X04's final work order after WO-4/WO-5 → alternative: a design-lane
  ruling first. Reversible by: dropping that commit. WO-3 next (brief docs/briefs/X04-build-A2.md).

- 2026-11-09 — X04 WO-3 done on wp/X04 (df59a3df): render display numbers, get_job_result display_units (schemas,
  OPERATIONS, description sentence, ADR 0019 Amendment 17, interfaces-frozen), A15–A20, A31–A33, A36 (38 passed); D-5
  (unsupported refusal's detail.reason = full message head). F0 PASS; MSG check 391/95. Known red 29: surface chain 14,
  R4-G3 5, t08_w2 surface digest 9, description review 1 — all for X04's final work order (c_8, snapshot, digest,
  reviews: design-lane in the reviewer pass, human on the board). Next: engineer B WO-4 (docs/briefs/X04-build-B.md).

- 2026-11-09 — X04 WO-4 done on wp/X04 (bb4b21cd): stream-table display members, get_stream_table display_units,
  schema, formats + `streams --display-units`, description (D-7: 1499/1500 chars), tests 29/29; D-6…D-12. Battery
  1573 passed; known red unchanged (29 + description review). F0 PASS. DECISION: the reviewer pass (WO-1–WO-4, brief
  docs/briefs/X04-reviewer.md) runs before WO-5 and the final work order, so a fix round lands before the chain link and
  snapshot are taken. Alternative: WO-5 first. Reversible by: order only.

- 2026-11-09 — X04 review (6ed59a98, docs/reviews/X04-review.md): sound, no must-fix; S1 parity case, S2 kinded-SI
  catalogue test, S3 both descriptions approved with edits (texts in the review), S4 bundle-mode length bound; N1–N3
  doc edits; D-7 changed, others kept; no second reviewer pass needed. Next: fix round + WO-5 (docs/briefs/X04-fix-WO5.md),
  then the final work order (c_8, SNAPSHOT_X04, digest). Frank's human review of both descriptions goes on the board
  once the texts are written (sha256 shown).

- 2026-11-09 — X04 fix round + WO-5 done (wp/X04 c4358784): descriptions verbatim from the review
  (get_job_result 1485 chars sha 3c96f32e…, get_stream_table 1500 chars sha b7ce4ed4…; design-lane reviewed); S1, S2,
  S4; N1–N3; A37–A40 (web units control, L-X04-1…3, guide page docs-site/guide/display-units.md, D-13); D-14, D-15.
  Battery 1856 passed, 29 known red. F0 PASS; MSG check 394. Board: x04-get-job-result, x04-get-stream-table (Frank's
  human review; he records it with scratchpad/record_frank_reviews_x04.py). Final work order brief
  docs/briefs/X04-final-WO.md. D-13…D-15 left for a design-lane glance (non-blocking).

- 2026-11-09 — X04 final work order done (wp/X04 4c818959): main merged (034bc43c, no conflicts); c_8 R-1010, D_8
  6be1c002…, without_x04 = D_7 553b7612… exactly; SNAPSHOT_X04 (9 responses); t08_w2 X04_SERVED_SHA256 + decomposition
  test; register R-1011…1016 (ADR 0075, Proposed); D-16…D-18. Battery 2486 passed, 3 xfailed, 1 failed = the
  description-review test ("2 open: get_job_result, get_stream_table: human pending"). F0 PASS; MSG check 394/95.
  Waiting on Frank: ADR 0075 accept and his two human reviews (script record_frank_reviews_x04.py). CI watched at
  4c818959 (expected red on that one test only).

- 2026-11-09 — 0.4.0 release prep on wp/REL040p (pushed, not merged): c46ef9fc `[4, "x05.*"]` + tests in V18 of
  release/lines/0.4.json; 9743871e RP.L11 (ADR 0074 O-3) in RP §3.4 + A-10 §17.3, release_gate.py own D2 encoder, R-1007;
  a1a00e17 S-6 log. S-6 rehearsal at 9743871e (release_rc dispatch 42604498076 green both legs incl. x05 clean-install):
  steps 2, 6–10, 12, 13, 16 pass; step 11 fails (IDAES record: environment.platform, reference_values_yaml_sha256 →
  re-take question); step 14 fails (NLP-1 inventory TypeError, start without final_decisions; M05 REAL replay
  diverges at 673.15 K); step 15 fails (needs a 0.4 journey J; same divergence); 17: E01-G6-nlp fails (same TypeError).
  0.4.0 is blocked on these. Debug brief docs/briefs/REL040-s6-debug.md (opus-engineer, wp/S6dbg).

- 2026-11-09 — S6dbg (wp/S6dbg 3e25b294, 76d191f2): F-A fixed — the NLP-1 inventory script's `_typed_options` patch took
  no arguments; since OPT WO-4 (f2f4ef5e) solve_start passes the request's options, so every start failed before Ipopt
  (class a; fix + nlp test; inventory reproduces, G1–G6 PASS; nlp 212 passed; F0 PASS). F-B is the host kernel:
  environment_fingerprint_sha256 hashes platform.platform(); 6.12.111 (record, 2026-10-16) → 6.12.113 (since the
  2026-11-06 reboot); v0.3.0's code diverges the same way. Class c → design-lane ruling with step 11's IDAES record and
  the 0.4 journey J (brief docs/briefs/REL040-s6-ruling.md). Also: `pytest -m nlp` over all tests stops at collection
  (4 modules import mpmath, absent in .venv-nlp) — S-6 runs a selected list; noted.

- 2026-11-09 — S-6 ruling (9f7cd613, docs/reviews/REL040-s6-ruling.md): REAL record re-taken at K3 at every cut on the
  RC host and committed in J (A-11, R-1008; options "drop kernel from fingerprint" and "ignore fingerprint" rejected);
  step 11's IDAES record differs only in environment.platform (reference-values change was insert-only, M01 Am. 1) →
  joins the re-take, proved by new m01_idaes_retake_diff.py; J recorded at the cut, same kernel for J and C; no Frank
  question. Work order WO-1…WO-6 (S6R-01…25) on wp/REL040p with S6dbg merged in (brief docs/briefs/REL040-s6-apply.md).

- 2026-11-09 — Frank's board answers: ADR 0075 **accepted**; both X04 descriptions approved (he records them with
  record_frank_reviews_x04.py); X04 FQ1–FQ3 defaults; **FQ4 = °C in human text** (not the default degC); 0.4 line
  acceptance: "ADR-F1…F8 Accepted" moved to 0.5 (roadmap amended here); ADR 0068 D3 amendment stands. Board pinned to
  Frank's claude.ai sidebar (he asked). DECISION: FQ4 is built on a side branch wp/X04fq4 (from wp/X04 4c818959) so
  Frank's review script can run on the clean wp/X04 worktree; merged back after → alternative: wait for the script.
  Reversible by: not merging the side branch.

- 2026-11-09 — Frank recorded his human reviews of get_job_result/get_stream_table on wp/X04 (a39ebfff, his script).
  FQ4 done on wp/X04fq4 (ADR 0075 Accepted da8f4597; °C/°F in human text via units.display.text_unit, D7.7; D-19…D-21),
  merged into wp/X04 (3e16b359). X04 CI 42624006442 at 4c818959 red: m02/m04 strip chains lack without_x04, B50 surface
  content lacks X04, default-install collection error (anyio via the mcp binding in test_x04_messages), plus the
  then-pending human reviews (digest docs/briefs/X04-ci-red-digest.md). DECISION: D-21 (display_out_of_range shows
  "degF" in text) → apply FQ4's rule via text_unit; alternative: design-lane wording ruling; reversible by one-line
  revert. Fix brief docs/briefs/X04-ci-fix.md, with one local full default suite run (the targeted batteries missed
  these files).

- 2026-11-09 — S-6 ruling applied on wp/REL040p (00f15a01): WO-1…WO-5 (platform class + pinned fingerprint + archive
  walk; build decision class `path` 81716c0a; --retake-into; m01_idaes_retake_diff.py; steps record both platforms;
  A-11, R-1008). S6R-01…15, 17–20, 23 pass. WO-6 answer: the kernel change moved no REAL or IDAES number (other=0).
  S6R-22 FAIL on non-numbers: sidecar 17→18 distributions (a git-ignored egg-info in the worktree) and one attempt's
  stderr (empty-file digest with two images). DECISION: Q-S6a keep `path`, Q-S6b clean = fresh `git worktree add`,
  Q-S6c stderr stays in identity; rerun from a fresh worktree first (brief docs/briefs/REL040-s6-rerun.md), design
  lane confirms at its next ruling → alternative: rule first. Reversible by: the ruling.
- 2026-11-09 — S-6 fresh rerun (99ac9e6e on wp/REL040p): proof PASS `path=128 version=0 platform=4 other=0
  environment=equal`; S6R-22/23/25 PASS, no stderr written; S6R-24 blocked by a test pinning the old kernel.
  DECISION: Q-S6d → that test reads the committed record's platform (0282e4d6). Alternative: J updates P0/P1. Reversible
  by reverting 0282e4d6. Confirmation of Q-S6a–d + X04 D-22 → brief docs/briefs/REL040-s6-confirm.md.
- 2026-11-09 — X04 CI fix round: wp/X04 at 0f7d9b87 (without_x04 chains, B50 R-1015 member, MCP importorskip, D-21
  via D-22 catalogue param type `display_unit`, notices page regenerated). Local full suite 1 failed (stale doc page,
  then fixed). CI watched.
- 2026-11-09 — S-6 confirmation round (ruling §11, 513195c1): Q-S6a–d confirmed (Q-S6c sharpened: WO-7 compares log
  digests exactly); WO-8 (IDAES re-take test pins the kernel too), S6R-29, A-11 item 7 → brief
  docs/briefs/REL040-s6-wo78.md. A `reviewer` pass on wp/REL040p (WO-1, 3, 4, 7a) follows before its merge.
  X04 D-22: ADR 0075 note + interfaces-frozen clause applied verbatim on wp/X04 (1d456c46), docs only.
- 2026-11-09 — TRS2 reset 18:33 (load ~34; hardware fault suspected, reported by Frank). The REL040p engineer was cut
  off after WO-8 d7258775, WO-7 26ad9d7f, A-11 item 7 0b62c12d (pushed); S6R-29 and WO-7's live proof line not run.
  X04 CI green at 0f7d9b87 (42659368086); D-22 note 1d456c46 pushed; manifest brief docs/briefs/X04-manifest.md.
  DECISION: until Frank says otherwise, TRS2 runs one serial process at a time, targeted tests only; S6R-29's
  default-tier run and any K3 work wait for his go. Alternative: resume the ≤ 36-core rule. Reversible by: Frank's word.
- 2026-11-09 — Frank (relayed by the TRS2 crash session): restart jobs and agents; ≤ ~36 busy threads machine-wide,
  `uptime` first, ask vof before using more than ~12 cores, no pytest/mypy in many worktrees at once; tell hub on a
  reset. The quiet-machine decision above is superseded. REL040p finish → docs/briefs/REL040-s6-wo78-finish.md.
- 2026-11-09 — X04 merged into main (720e5138; evidence/X04/0f7d9b87…, tested, 41 pass + FULLGATE unsupported; CI
  42659368086). HARVEST_SIZE (89, 1063, 142). Post-merge: ruff clean, F0 PASS (M1–M9), targeted 1801 passed 3 xfailed.
  Board items adr-0075 and x04-fq4 closed.
- 2026-11-09 — REL040p: S6R-29 (78221727) found M07's A2.3 test bound to the working-tree REAL record. DECISION:
  Q-S6e → read the offered record at the journey's own commit (c8be15dc). Alternative: J rewrites three journeys.
  Reversible by reverting c8be15dc; ruled in the reviewer pass. Main merged in (5d0c4121; register conflict R-1007/1008
  vs R-1010…1016 resolved by keeping both). Reviewer brief docs/briefs/REL040-reviewer.md.
- 2026-11-09 — REL040 review (86da7a27): sound; S-1 (three more digests relabelled instead of compared) → WO-R1;
  Q-S6e confirmed; nothing for Frank. Fix brief docs/briefs/REL040-fix-R1.md (WO-R1 + N-1, N-3, N-5; N-4 not done).
- 2026-11-10 — REL040 fix round: WO-R1 5b8575a4, N-1 cfa46e70, N-3 c95288f4, N-5 a385a417 (wp/REL040p 829aadf4); live
  REAL proof and S77 unchanged; the S-1 demonstration now FAILs (other=16). DECISION: REL040p's evidence form →
  evidence/REL040/829aadf4…/manifest.json (the 0.4 line's own package, prep manifest; the RC adds the candidate's).
  Alternative: a separate id (REL040p). Reversible by moving the file. Brief docs/briefs/REL040-manifest.md.
- 2026-11-10 — REL040 prep merged into main (6f39045c; evidence/REL040/829aadf4…, tested 18 + FULLGATE unsupported;
  CI 42716958104). Post-merge: ruff clean, F0 PASS, targeted 1746 passed. HARVEST_SIZE (90, 1068, 143). Next: 0.4.0
  RC cut, waiting for Frank's go.
