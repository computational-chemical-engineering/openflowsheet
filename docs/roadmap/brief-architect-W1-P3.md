# Architect brief: design wave W1, pass P3 — F6 unit-model framework, F7 problem IR and run kinds, F8 identity and replay

Status: brief, 2026-11-05. Roadmap W1 (ADR 0057, R-928): P1 (F1, F3: ADR 0060, 0061) and P2 (F2, F4, F5: ADR 0062,
0063, 0064) are designed and reviewed, fixes applied, all Proposed pending Frank's acceptance — design on them as
written. This is P3, the last architect pass of W1; one reviewer pass on the P3 set follows, then the v2 core freezes.
F6 is built in 0.6, F7 in 0.7 (with TX), F8 in 0.5 (bundle/data-lock parts) and 0.7 (`forced_replay`, with TX).

## The question

Turn `target-architecture.md`'s F6, F7 and F8 into three buildable foundation ADRs — **ADR-F6** (unit-model framework
v2), **ADR-F7** (problem IR v2 and run kinds), **ADR-F8** (identity, replay and evidence v2) — each with normative
schemas or schema drafts, interface additions, the migration proof (legacy bitwise where the note says bitwise),
numbered exit tests, risks, and work orders the build lane can execute without a further design decision. The
specifier's rulings are adopted verbatim; your job is the software design around them.

## Why it needs the architect

F6 fixes how every v2 unit declares ports, sides, state points, zero-flow forms and variables — the last core-grammar
items before the W1 freeze (ADR 0062 D7 leaves the unit-owned vid fields to ADR-F6 "before the W1 freeze"). F7 decides
the DAE/IR shape all transient work (TX, X25, X26) builds on and amends frozen interfaces. F8 decides what a bundle
carries and whether 0.3.0 replays survive. F0 gates every foundation merge.

## Inputs (all committed; read narrowly)

- `docs/roadmap/target-architecture.md`: §2.4 unit-model framework (442–535), §2.5 problem and solver (536–616), §2.6
  application contract (617–650), §2.7 identity, replay, evidence (651–680), §3 F6/F7/F8 (842–890), §4 dependency graph
  (891–977), §7 risks (1051–1091), §8 frozen-interface changes (1092–1122: rows for ADR-F6/F7/F8), §9.2, §9.5–9.10 (the
  sketches resting on F6/F7: 1146–1298), §9.11 (1299–end). The note is the design you refine; depart only with a
  recorded reason.
- `docs/roadmap/foundation-rulings.md` — authoritative on scientific semantics. Q1 (31–184: R4, R6, R7, R8, R9; A9–A12),
  Q4.R6 and the density decision at 506, Q5.R7 and line 596 (manifest-declared phases), Q8.R6, Q9 (850–914: R7
  `data_unavailable`, A1–A3), §10 item 8 (ADR 0008 U1/U1b in ADR-F7), §11 O-10, §13 S3 (992), §14 rows Q1.R8/Q1.R9
  (1023–1024) and findings A2-a/A2-b (1026–1032). If a ruling makes your design unworkable, say so in the ADR's risks;
  do not rule differently.
- P1/P2 ADRs, which yours must fit:
  - ADR 0060 (F1): kinds `unit_model` v2 form, `semantic_role`, `equipment_class` (ADR-F6), `solver_route`, `run_kind`
    (ADR-F7) — table at 53–71; D12 core admission single-side, ADR-F6 adds per-side `requires` additively (400, 580);
    `registry.usage()` ContextVar and F8's comparison (329); evidence-class propagation into `RunManifest.environment`
    and outside R0 (346–363); `functional_contributor` extensions `preview` until an ADR 0052 amendment (ADR-F8 or X01
    rest, 535).
  - ADR 0061 (F3): data lock and `data_lock_sha256` per run (286); rights register keyed by `source_sha256`, bundle
    writer (298–314); `data_unavailable` (545).
  - ADR 0062 (F2): D4 zero-flow row forms are ADR-F6's (145); D7 vid field table — unit-owned fields added by ADR-F6
    (191); fingerprint for v2-compiled runs (210); D9 energy/signal connections, probes and parameter sinks refused
    `construct_unavailable(<construct>, F6)` until ADR-F6's units read them (205–225); `semantic_role` vocabulary owned
    by ADR-F6 (251); ADR 0019 Amendment 9.
  - ADR 0063 (F4): a unit evaluates each side = manifest-declared port group (111); c_ref, ΔT_ref measured in F4/F6
    (risk 3).
  - ADR 0064 (F5): the full FB-04 turbine `VERIFIED` is ADR-F6's exit (E-F5-6 moved, 126, 150).
  - Reviews: `docs/reviews/W1-P1-review.md`, `docs/reviews/W1-P2-review.md`.
- Legacy ADRs F6–F8 amend or must respect: ADR 0008 (transient readiness; D3 accumulation declarations, Amendment 1
  A1.1 U1/U1b at 603–646), ADR 0012 (zero-flow D4(c)/D12), ADR 0005 (phase-attempt contract), ADR 0050 D3, ADR 0052
  (assessment functionals), ADR 0054 (semantic role), ADR 0019 (application contract; 0058 = Amendment 6, 0060/0061 =
  7 and 8, 0062 = 9 — number yours from 10).
- `docs/roadmap/00-core-inventory.md`: §4 unit models (238–350), §5 compilation and solving (351–463), §7 frozen
  interfaces (526–561), §8 application contract (562–641), §9 replay and identity (642–end).
- `docs/roadmap/decisions.md` and the register through R-940 (`docs/decision-register.md`; R-929 freeze points at
  18373).
- F0 (`docs/briefs/F0-build.md`): every work order is judged by `scripts/corpus_identity.py --check` (M1–M9; M7 replays
  the 52 committed 0.3.0 bundles; M9 = 35 frozen legacy module files).

## Items handed to P3 by earlier passes (resolve each in the right ADR)

- **ADR-F6:** A2-b port routing of FLUID phases (density order or `character`), fixed at openings and recorded; zero-flow
  and zero-holdup row forms (Q1.R4, Q5.R7, Q1.R8 with F7); causal outlet evaluation declared for reactivation (Q1.R6,
  S3, exit Q1.A9); Q5.A8; the unit-owned vid fields (core, before the freeze); per-side `requires`/admission (additive
  to ADR 0060 D12); sides as port groups for ADR 0063; `semantic_role` vocabulary over ADR 0054; `equipment_class`;
  reading ADR 0062 D9's energy/signal constructs; the v2 compiler and definition SHAs in the fingerprint for
  v2-compiled runs (ADR 0062 D8); the FB-04 turbine `VERIFIED` exit; the `std.*` seed vs legacy equivalence and the
  retirement rule (R-929); c_ref/ΔT_ref measurement.
- **ADR-F7:** Q1.R7–R9, Q1.A10–A12 (holdups, dormancy and the drain event, non-material holdups); the ADR 0008 A1.1
  U1/U1b amendment (§10 item 8: U1 checks registered holdup kinds, never an enthalpy; U–H.8 stays out, Q-A5 and A2-a);
  O-10's tolerances as defaults; `state_rate` (reverses ADR 0008 C10 — say so); `differential_map`; `ValidationReport`
  tasks; `solver_route` and `run_kind` registries; `submit_run`; progress events; chunked trajectory artifact;
  per-kind checkpoints (§8 rows).
- **ADR-F8:** data lock in bundles with rights-aware embedding; Q9.R7 `data_unavailable` → `NOT_RUN`; registry snapshot
  in `Environment` compared on replay; evidence-class fields outside R0; per-platform reference records (with X07a);
  decision records and `forced_replay` design (TX builds); whether `functional_contributor` gets its ADR 0052 amendment
  here or in X01 rest — decide.

## Constraints and invariants

- Frozen interfaces and schemas change only by ADR; additions to the application contract are ADR 0019 amendments
  (from 10). Every v1 `content_hash`, `model_version`, `r0_sha256`, `state_sha256`, cache key and replay unchanged
  (F0 M1–M8); no identity-bearing legacy module edited (S1, M9). v1 units run through an adapter (§8 row).
- R-929: the v2 **core** grammar freezes at the end of W1; method, phase-assertion and template slots stay `preview`
  until the end of 0.6. For each ADR say exactly which parts are core and which preview.
- R-924/R-927: admit with declared limits; unbuilt constructs and run kinds refused typed, never placeholder success.
- Python 3.11+, CasADi as today; Linux x86-64/aarch64 CI now, Windows/macOS with X07a.

## Genuinely open (decide)

1. ADR-F6: the concrete `UnitModel` v2 / `UnitDeclaration` / `ModelManifest` v2 types and schema; the v1 adapter; the
   `std.*` seed's equations source (design-approved equations only — say which exist and which need a specifier spec);
   coverage-matrix generator; templates and flattening with stable ids; the expression grammar and compiler; signal
   ports, manipulable parameters and steady controllers; seams for external/co-simulated/CAPE-OPEN units; the
   architecture test; the core/preview split.
2. ADR-F7: `DynamicSpec`, the structural index and rank checks, discrete states and events, functional programs, the
   run-kind registry and `submit_run`, the trajectory artifact and checkpoint designs — and which of these 0.7 builds
   versus only reserves now.
3. ADR-F8: bundle layout v2 (backward-compatible reading of 0.3.0 bundles), the data-lock embedding rule against the
   rights register, replay comparison of the registry snapshot, evidence-class fields, decision records.
4. Work-order order across the three ADRs and against F1–F5, and what each unblocks (TX, X12, X14, X17, X19, X22, X25,
   X26, CAPE-OPEN).
5. **Scientific questions for the specifier.** List any point where your design needs a ruling not in
   `foundation-rulings.md` (with your default). They will be batched into one specifier round together with ADR 0063
   risk 5 (entropy shift for a record without s°). Do not rule them yourself.

## How the answer will be verified

F0 on every work order; each ADR's exit tests; the full gate; CI on both architectures; then one `reviewer` pass on the
P3 ADR set before acceptance.

## Deliverable

- `docs/adr/0065-F6-unit-model-framework.md`, `docs/adr/0066-F7-problem-ir-run-kinds.md`,
  `docs/adr/0067-F8-identity-replay-evidence.md`, all **Proposed**: decision, rejected alternatives, schemas (draft
  files under `schemas/` marked draft if you write them), interface additions, migration proof, numbered exit tests,
  risks, work orders (files, acceptance tests, identity yes/no, sonnet-eligible marked), and a "Specifier questions"
  section (item 5).
- A list of edits `target-architecture.md` needs (do not edit it).
- If your context approaches ~250k tokens before all three are done, finish the ADR in hand, write
  `docs/roadmap/W1-P3-handoff.md` (≤ 40 lines: done, next, open), and stop — a fresh architect continues.
- Report ≤ 30 lines.

Do not commit; write no production code; no subagents. Do not edit `foundation-rulings.md`, `target-architecture.md`,
ADR 0060–0064, or anything under `.claude/worktrees/`. Never touch `~/.config/procsim/`. No web fetches.

## Out of scope

F1–F5 (designed; raise a conflict as a risk, do not redesign), MSG, ST, release lines, TX/X25/X26 themselves (only what
F7/F8 must carry for them).
