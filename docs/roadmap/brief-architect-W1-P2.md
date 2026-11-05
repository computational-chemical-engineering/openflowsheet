# Architect brief: design wave W1, pass P2 — F2 material model, F4 property methods, F5 phase equilibrium

Status: brief, 2026-11-05. Roadmap W1 (ADR 0057, R-928): P1 (F1, F3) is designed (ADR 0060, 0061: reviewed, fixes
applied, Proposed pending Frank's acceptance); this is P2; P3 (F6, F7, F8) follows; one reviewer pass per ADR set. F2 is
built in 0.5, F4 and F5 in 0.6. **The v2 core grammar freezes at the end of W1**: F2's core is the frozen part; the F4–F6
slots stay `preview` until the end of 0.6 (R-929).

## The question

Turn `target-architecture.md`'s F2, F4 and F5 into three buildable foundation ADRs — **ADR-F2** (material model and
`ProcessRevision` v2), **ADR-F4** (property methods and thermo face), **ADR-F5** (phase-equilibrium framework) — each
with normative schemas or schema drafts, interface additions, the migration proof (legacy bitwise where the note says
bitwise), numbered exit tests, risks, and work orders the build lane can execute without a further design decision. The
specifier's rulings are adopted verbatim; your job is the software design around them.

## Why it needs the architect

F2 fixes the v2 document and state grammar every later package reads and that freezes at W1's end; F4 and F5 carry
every property and phase computation of the simulator. Their identity rules decide whether released numbers and
replays survive (F0 gates every foundation merge).

## Inputs (all committed; read narrowly)

- `docs/roadmap/target-architecture.md`: §2.1 material model (lines 122–274), §2.2 phase equilibrium (275–349), §2.3
  property and data layer (350–441), §3 F2 (755–780), F4 (797–817), F5 (818–841), §4 dependency graph (891–977), §7
  risks (1051–1091), §8 frozen-interface changes (1092–1122), §9.11 (1299–end). The note is the design you refine; depart
  only with a recorded reason.
- `docs/roadmap/foundation-rulings.md` — authoritative on scientific semantics. Q1 (31–184), Q2 (185–359), Q3 (360–450),
  Q4 (451–558), Q5 (559–676), Q6 (677–741), Q7 (742–788), Q8 (789–849); §10 (ADR changes the rulings need); §11 open
  questions; **§14 Amendment 2** (1012–1040: its table gives, per item, the exact edits ADR-F2/F4/F5 adopt — read every
  row; findings A2-b, A2-c) and **§15 Amendment 3** (1041–end: Q2.R9, the no-data anchor; finding A3-a for ADR-F4). If a
  ruling makes your design unworkable, say so in the ADR's risks; do not rule differently.
- P1's ADRs, which yours must fit: `docs/adr/0060-F1-extension-registry.md` (kinds, descriptors, tokens, admission,
  self-hash = `implementation_sha256`) and `docs/adr/0061-F3-component-data.md` (`record-v2`, anchor derivation D6,
  data lock = `data_sha256`, the legacy importer). Review: `docs/reviews/W1-P1-review.md`.
- `docs/roadmap/00-core-inventory.md` (2026-11-01; current for these areas): §1 stream state and labels, §3 providers,
  §5 compilation and solving, §6 the revision document, §7 frozen interfaces, §9 replay and identity.
- `docs/roadmap/decisions.md` and the register through R-940 (`docs/decision-register.md`, R-928…R-940 at its end).
- F0, the corpus identity gate (`docs/briefs/F0-build.md`; merging): every work order you write is judged by
  `scripts/corpus_identity.py --check` (M1–M9, 35 frozen legacy module files).

## Items handed to P2 by earlier passes (resolve each in the right ADR)

- §14 table rows A1-a (ADR-F2 adopts Q3.R5, Q3.A6; ADR-F4 cites Q3.R5, adopts Q3.A5), A1-b (ADR-F4: Q2.R2, R4, R8,
  Q2.A9), S5 (ADR-F5: the Q4/Q5 clauses; ADR-F2: the family vocabulary and rendering, qualifiers on every family — a
  core-grammar item of the freeze).
- §15 Q2.R9 and Q2.A10/A11 (ADR-F4); A3-a: an assertion that catches a real-gas method (PR-C1) anchoring at its vapour
  instead of its ideal-gas state.
- A2-c: a confined phase beside a FLUID model that can form a phase rich in its component — two representations; decide
  with X21 in view (note §9.4).
- From P1: the quantity kinds `molar_entropy` and `segment_molar_enthalpy` are not registered (`schemas/units.json`
  spells `J/(mol K)`); ADR-F2 adds them. MSG's build raised the same spelling question — give one answer.
- §10's ADR changes the rulings need, where they fall in F2/F4/F5.

## Constraints and invariants

- Frozen interfaces and schemas change only by ADR; additions to the application contract are ADR 0019 amendments
  (0058 = Amendment 6; P1 proposed 7 and 8 — number yours after them). `nTP-v1` stays byte-identical (Q1.R5); every v1
  `content_hash` unchanged; `StreamState ↔ EvaluationState` bitwise for every corpus stream (F2 exit).
- No identity-bearing legacy module is edited (S1; F0 M9). Legacy providers become property sources through adapters in
  new modules.
- F4: no scale, step bound or tolerance taken from `|ĥ|` (S7); one convention per v2 flowsheet; batching exit
  (≤ 0.1 × unbatched per point at N = 300 on the re-implemented cubic kernel; delegating ≤ 1.05 ×).
- F5: decision equivalence over the corpus; legacy providers stay `split` (Amendment 2).
- Python 3.11+, CasADi as today; Linux x86-64/aarch64 CI now, Windows/macOS with X07a.

## Genuinely open (decide)

1. ADR-F2: the concrete `EvaluationState` and widened provider types; the connection-definition registry entries; the
   id grammar implementation; `solution-state-v2`; the `ProcessRevision` v2 schema; which parts are core (frozen at W1's
   end) and which preview.
2. ADR-F4: the vocabulary registry and legacy adapters; `compose` and the source stack; convention shift, anchors
   (including Q2.R9's `ig` via φ° for Helmholtz methods) and bridges; method sets, sides and the boundary rule; the
   batched `MaterialModel` and the re-implemented cubic kernel; how a v2 method's `implementation_sha256` (ADR 0060's
   self-hash) composes with delegated legacy modules.
3. ADR-F5: the N-phase flash and stability analysis structure, trial-set registration, the contract value with the
   discrete-coordinate signature, regime discovery (the FB-04 turbine exit), indicators, the verifier checks.
4. Work-order order across the three ADRs and against F1/F3, and what each unblocks (X09, X08, X17, PrISMa, X11 rest).

## How the answer will be verified

F0 on every work order; each ADR's exit tests; the full gate; CI on both architectures; then one `reviewer` pass on the
P2 ADR set before acceptance.

## Deliverable

- `docs/adr/0062-F2-material-model.md`, `docs/adr/0063-F4-property-methods.md`, `docs/adr/0064-F5-phase-equilibrium.md`,
  all **Proposed**: decision, rejected alternatives, schemas (draft files under `schemas/` marked draft if you write
  them), interface additions, migration proof, numbered exit tests, risks, work orders (files, acceptance tests, identity
  yes/no, sonnet-eligible marked).
- A list of edits `target-architecture.md` needs (do not edit it).
- If your context approaches ~250k tokens before all three are done, finish the ADR in hand, write
  `docs/roadmap/W1-P2-handoff.md` (≤ 40 lines: done, next, open), and stop — a fresh architect continues.
- Report ≤ 30 lines.

Do not commit; write no production code; no subagents. Do not edit `foundation-rulings.md`, `target-architecture.md`,
ADR 0060/0061, or anything under `.claude/worktrees/`. Never touch `~/.config/procsim/`. No web fetches.

## Out of scope

F1, F3 (designed), F6–F8 (P3, except naming what F6 must carry: A2-b port routing of FLUID phases, zero-holdup forms),
MSG, release lines.
