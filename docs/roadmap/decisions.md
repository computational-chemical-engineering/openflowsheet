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
