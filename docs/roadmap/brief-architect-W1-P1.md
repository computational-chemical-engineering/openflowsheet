# Architect brief: design wave W1, pass P1 — F1 extension registry and F3 component data

Status: brief, 2026-11-05. Roadmap §"Design waves" W1 (ADR 0057, R-928): after the specifier's Amendment 2, architect
passes P1 (F1, F3), P2 (F2, F4, F5) and P3 (F6, F7, F8), with one reviewer pass per ADR set. This is P1. F1 and F3 are
built in 0.5; the v2 core freezes at the end of W1.

## The question

Turn `target-architecture.md`'s F1 and F3 into two buildable foundation ADRs — **ADR-F1** (extension registry and
computed admission) and **ADR-F3** (component data core) — each with the normative schemas, the interfaces they add to the
frozen contract, the migration proof for every legacy provider, unit and record, numbered exit tests, and work orders the
build lane can execute in 0.5 without a further design decision.

## Why it needs the architect

F1 is the single registration point every later foundation and package plugs into (F2–F8 kinds, X01, X11, the agentic
layer's contributed extensions, MSG's message entries); F3's record identity and data lock enter every v2 provider's
`data_sha256`. Both freeze at the end of W1, and both must register or import every legacy object without moving one
identity byte (F0 checks it).

## Inputs (all committed; read narrowly)

- `docs/roadmap/target-architecture.md`: §2.3 (lines 350–441; records, data lock, composition, source stack), §2.6
  (lines 617–650; rules C1–C3, the 0.4 constraints), §2.4.4 (S1 byte-level freeze, line ~473), §3 F1 (737–754) and F3
  (781–796), §4 dependency graph, §7 risks, §8 frozen-interface changes (1092–1122), §9.11 (foundation changes forced
  by the sketches). The note is the design you refine; depart from it only with a recorded reason.
- `docs/roadmap/foundation-rulings.md`: Q7 (amount bases, lines 555–601), Q9 (records, identity, rights, provenance,
  663–727), Q2.R2/R4/R8 as amended by Amendment 2 §14 (the anchor is now a record field — F3 must carry it), Q8.R7 if
  `record_type` touches isotherms. Authoritative on scientific semantics: if a ruling makes your design unworkable, say
  so in the ADR's risks; do not rule differently.
- `docs/roadmap/00-core-inventory.md` (2026-11-01, still current for these areas): §2 components and records, §3
  providers (`FRESH_PROVIDERS`, providers built by id), §4 units (`MODEL_BUILDERS`, `MODEL_BASES`), §7 frozen
  interfaces, §8 application contract, §9 replay and identity, §11 E01's `register_contributor`.
- `docs/design/MSG-messages.md` §4.11 (on `wp/MSG`'s base, committed on main): the `messages.catalogue.register()` slot
  F1's `message_entries` kind must use. MSG fixes nothing else about F1.
- `docs/agentic-layer/preliminary-plan.md` §8.1 (lines 238–256; R-931): extensions contributed by an agent carry
  `contributed, unreviewed` until a reviewer pass and the configured approval; every result using one carries the flag.
- F0 (just built, `wp/F0`, merging): `docs/briefs/F0-build.md`, `benchmarks/f0/corpus.json`; M9's frozen set now
  includes the 27 legacy unit-model modules (R-940). Self-hashes over LF-normalised bytes (S1, `.gitattributes`).

## Constraints and invariants

- Frozen interfaces (plan §2.1, `docs/interfaces-frozen.md`) and schemas (§2.2) change only by ADR; additions to
  `Application`/`Inspection` (e.g. `list_capabilities`, `check_admission`, `search`, `get`, `register`, `validate`) are an
  ADR 0019 amendment, as ADR 0058 did (Amendment 6). Existing schemas round-trip unchanged.
- No identity-bearing legacy module is edited (S1, F0 M9). Legacy providers and units register from new modules.
- F1 exit: admission over the legacy pairs equals `MODEL_BASES` exactly, as sets; snapshot hash identical across runs and
  platforms. F3 exit: imported records equal the YAML loaders' values bitwise; data-lock hash stable across platforms.
- Rights (R-706, Q9.R3): vetting never moves an identity. Windows store rules (N12) as the note states.
- One OPERATIONS row per capability on all four transports (C1).
- Python 3.11+, the repository's style; Linux and aarch64 CI today, Windows/macOS legs come with X07a (0.5).

## Already decided, not open

Everything in `docs/roadmap/decisions.md` and the register through R-940: the kinds list of F1's scope (extend it only
with reason), content-addressed write-once store, rights separate from identity, MSG's catalogue slot, the
`contributed, unreviewed` evidence class, the freeze points.

## Genuinely open (decide)

1. The descriptor schema (fields, versioning, self-hash, requirements/provisions), and the admission function's form.
2. Discovery, ordering and trust for entry-point extensions; when registration closes; how a contributed extension is
   flagged and how the flag propagates into results and certificates.
3. How legacy providers and units are registered without byte edits, and the proof that admission equals `MODEL_BASES`.
4. `ComponentRecord` v2 schema, the volatile set, identity-key resolution, the store layout, the data lock's place in
   identity, the rights register's form, and the importer/user-file adapter.
5. Which parts are core (frozen at W1's end) and which stay `preview` until 0.6.
6. The order of work orders across F1 and F3, and what of X01/X11 rest each unblocks.

## How the answer will be verified

F0 (`scripts/corpus_identity.py --check`) on every work order; the exit tests above; the full gate; CI on both
architectures; then one `reviewer` pass on the ADR set before it is Accepted.

## Deliverable

- `docs/adr/0060-F1-extension-registry.md` and `docs/adr/0061-F3-component-data.md`, both **Proposed**: decision,
  rejected alternatives, schemas (or schema files under `schemas/` marked draft), interface additions, migration proof,
  numbered exit tests, risks, and work orders (files, acceptance tests, identity yes/no, sonnet-eligible marked).
- A short list of edits `target-architecture.md` needs; do not edit it yourself.
- Report ≤ 30 lines.

Do not commit; the orchestrator commits. Write no production code. Do not start subagents. Do not edit
`foundation-rulings.md`, `target-architecture.md`, or anything in `.claude/worktrees/`. Never read, stat or touch
`~/.config/procsim/`. Do not fetch from the web.

## Out of scope

F2, F4–F8 (P2, P3), X01/X11 rest beyond naming what each work order unblocks, MSG, release procedure.
