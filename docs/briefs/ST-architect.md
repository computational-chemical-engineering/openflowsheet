# Architect brief: ST — stream table and energy summary (0.4)

Status: brief, 2026-11-06. Package ST (ADR 0056 Amendment 1, line 83: FB-06 with FB-02; roadmap `docs/roadmap/roadmap.md`
line 36). One architect pass (this), the build, one reviewer pass. Orchestrator decision 2026-11-06
(`docs/roadmap/decisions.md`): ST gets a design pass because it adds to the frozen application contract.

## The question

Design the post-solve stream table and energy-balance summary — what is computed, from what, how it is exposed on all
four transports and as an artifact, and what identity it may and may not touch — as one short design note plus the
ADR (an ADR 0019 amendment) the build lane implements without a further design decision.

## Why it needs the architect

It adds an operation (or artifact) to the frozen application contract (ADR 0019; next free amendment number **13** —
0058 = 6, 0060 = 7, 0061 = 8, 0062 = 9, 0065 = 10, 0066 = 11, 0067 = 12), it must not move any F0 identity measure, and
it must be shaped so that v2 (F2/F4, frozen at W1, R-941) extends it additively rather than replacing it.

## What the user asked (FB-06, FB-02; `docs/USER_FEEDBACK.md` lines 15, 27)

A tutorial user needed ~25 lines of internal API (`Iapws95Provider`, `EvaluationContext`, `PropertyRequest`, phase chosen
by hand) to check H(S5) − H(S1) on a Rankine cycle, and could not find the steam quality of a stream. Asked for: a
post-solve stream table (T, P, molar and mass flow, composition, vapour fraction, h, s, density) and an overall
energy-balance summary, via API, artifact and CLI.

## Current state

Read the recon digest **whole**: `docs/briefs/ST-recon-digest.md` (219 lines; file:line anchors with excerpts). Key
facts from it: the one `OPERATIONS` table (`application/operations.py:293`) feeds Python, CLI, HTTP and MCP; nothing
returns per-stream derived values today (closest: `get_artifact` on `<bundle>/solution-state.json`, raw variables);
`solution-state.json` is written only when a certificate exists (`application/revision_run.py:858`); reusable helpers
exist in the verifier (`verify/checks.py:326 enthalpy_flow`, `verify/forms.py:95`, `verify/thermal.py:132,150`); density
is not a provider property; `s` exists only for IAPWS-95 and Wilson v2; the verifier already computes the overall
envelope energy (`verify/table.py:1220`); the web shell streams screen shows n, T, P only. ADR 0058 (MSG, the `explain`
operation, D7 at lines 62–69) is the pattern for adding an operation on all four transports; MSG is being built on
`wp/MSG` concurrently — say which files both packages touch so the merges do not collide.

## Constraints and invariants

- The note's ST constraints (`docs/roadmap/target-architecture.md` §2.6, rule C5 and "Constraints on the 0.4 packages",
  lines ~762–772, read them): projections derived **after the solve from the verified state**, through the legacy
  providers until F4 and through the thermo face after it; **per phase and per substream from the start**; **never in
  certificate identity**; ST keys phases by Q4.R1's structured triple (family an open registered vocabulary) and
  substreams by id, never by rendered strings; records the convention id with each h and s; extends its artifact schema
  only additively.
- F0 (`scripts/corpus_identity.py --check`, M1–M9) must stay PASS: no `content_hash`, `model_version`,
  `constants_sha256`, `r0_sha256`, `state_sha256`, certificate, cache key, 0.3.0 replay or frozen legacy module may
  change. Say explicitly whether a new artifact in new runs' bundles touches any of these, and how 0.3.0 bundles (no
  table) are served.
- R-924: admit with declared limits. A quantity a provider cannot give (density, s on most providers) is reported
  absent with a typed reason and a catalogued code (MSG C3: every code needs a catalogue entry), never invented.
- X04 (units) comes later and works at the boundary only: ST returns SI with units named; display conversion is X04's.
- Scientific semantics (the definition of vapour fraction/quality on a mass vs mole basis, what "h" means across
  providers with different reference conventions, density where the provider has no volume) are design-lane: if a
  definition is not already fixed by an ADR or the rulings (`docs/roadmap/foundation-rulings.md` Q1, Q2, Q4), state
  your default and list it as a specifier question; do not leave it to the build lane.

## Genuinely open (decide)

1. Operation vs artifact vs both: an Inspection operation computing on demand from a run's bundle, a run artifact
   written at solve time, or both (and then which is authoritative).
2. Request/response schema, including per-phase rows, substreams, the energy summary (per unit and overall, with the
   verifier's envelope figure), absent-with-reason values, convention ids.
3. Which provider calls compute each quantity (reuse the verifier helpers or not), and determinism.
4. CLI and MCP shape (a `streams` command / tool?), web shell display (in scope or later), docs.
5. Work orders, each with files, acceptance tests (including an analytic check: e.g. an IAPWS-95 Rankine case where
   H(S5) − H(S1) equals the turbine/pump duties from the run, and a two-phase stream whose quality equals the lever rule
   from saturated h_L, h_V), identity yes/no, sonnet-eligible marked.

## Deliverable

- `docs/design/ST-stream-table.md` (design note, ≤ ~400 lines) and `docs/adr/0068-stream-table.md` (Proposed; ADR 0019
  Amendment 13; decision, rejected alternatives, schemas, migration proof, numbered exit tests, risks, work orders,
  specifier questions with defaults).
- Report ≤ 25 lines. Do not commit; no production code; no subagents; no git state changes (other agents work
  concurrently); nothing under `.claude/worktrees/`; never read, stat or touch `~/.config/procsim/`; do not read
  `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; no web fetches.

## Out of scope

v2 projections through the thermo face (F4, 0.6: only say how the design extends to them), X04's unit conversion, X16's
PFD reports, MSG's catalogue internals beyond registering ST's codes.
