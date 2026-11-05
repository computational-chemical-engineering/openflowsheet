# Reviewer brief: W1 P3 — ADR 0065 (F6), 0066 (F7), 0067 (F8), with Amendment 4 and the `std.*` sheet

Status: brief, 2026-11-06. The single design-lane review of the P3 ADR set (roadmap W1), the last before the v2 core
freezes at W1's end (R-929: core frozen; method, phase-assertion and template slots `preview` until the end of 0.6).

## What to review

- `docs/adr/0065-F6-unit-model-framework.md` (480 lines), `docs/adr/0066-F7-problem-ir-run-kinds.md` (352),
  `docs/adr/0067-F8-identity-replay-evidence.md` (304; ends with the cross-ADR build order), all Proposed, written against
  `docs/roadmap/brief-architect-W1-P3.md` (read it: question, inputs with line ranges, items handed to P3, constraints).
  Note edit list: `docs/roadmap/W1-P3-note-edits.md` (30 edits).
- The specifier round that followed (brief `docs/roadmap/brief-specifier-W1-P3-questions.md`):
  `docs/roadmap/foundation-rulings.md` §16 Amendment 4 (1314–1431; clauses also inserted in place: Q1.R10, Q2.R10,
  Q4.R9, Q5.R9–R11, Q9.R8; O-14…O-18 in §11), and `docs/derivations/F6-std-seed.md` (301 lines; generator
  `docs/derivations/scripts/f6_std_seed_reference.py --check`: PASS, 107 claims). The specifier lists **18 ADR edits**
  (11 from Amendment 4: 0063 ×3, 0065 ×4, 0066 ×3, 0067 ×1; 7 from the sheet: 0065 D6, D7, D8, D16 and exits, 0063 D7,
  0062 D10) — not yet applied.
- They must fit P1/P2: ADR 0060–0064 (reviews `docs/reviews/W1-P1-review.md`, `docs/reviews/W1-P2-review.md`; fixes
  applied), and adopt the rulings verbatim (Q1.R4–R10, Q4.R9, Q5.R7–R11, Q9, §10 item 8, §14 A2-a/A2-b, §16).

## The architect's summary (orientation, not evidence)

F6 core: `UnitModel` v2, ModelManifest v2, `UnitDeclaration`, `compiled-problem-structure-v2` (`sources`), unit-owned
vid fields (Q W x xi N A U K r; parameters p z), per-side admission, zero-flow forms, reactivation kinds, A2-b routing
(D9), steady `std.pid` (D10), expression format, roles, matrix and retirement rules; preview: templates, per-side method
overrides, phase assertions, expression uses, equipment classes. F7 core: `state_rate`, new F1 kind `holdup_kind`
(built-in only; ADR 0008 U1/U1b amended), `DynamicSpec` (G = F − Mẋ), `differential_map` (new nullable field on
`CompiledProblemMetadata`), events/discrete states, index check, run-kind and solver-route payloads, `submit_run`, job
operation `run`, trajectory/checkpoint/ledger formats. F8 core: only v2-compiled runs and `run` jobs carry F8 records;
bundle layout, rights-aware embedding, 7-step replay comparing used extensions only, evidence report outside every
identity; decision records and `forced_replay` designed now, built with TX. Riskiest per the architect: v2
`model_version` includes the compiler self-hash and the data lock (every compiler edit re-registers the v2 corpus);
Q1.A11/A12 pass at F7's exit only on a test-only reference integrator; v1-path and lowered runs write nothing new and
replay on the shipped legacy record index.

**Departures the architect recorded (rule on each):** (1) v2 structure document omits the revision `content_hash` (ADR
0002 D2.7); (2) the v1 adapter takes only legacy units without a phase-selecting point; (3) F6 seeds only `std.pid`
(ratio, lead–lag, selector, split range → TX); (4) time inputs in a dynamic scenario document, not a `schedule` member
of `Specification` (ADR 0008 C7 relocated); (5) `differential_map` hashed in the v2 structure document, dynamic only;
(6) **ADR 0060 D9 narrowed** (evidence notices in the evidence report, not the certificate); (7) the ADR 0052
extension-contributor amendment goes to X01 rest under ADR 0067 D11's four constraints; (8) **ADR 0063 D7 amended
additively** (`MaterialModel` reports which record entries each state point read, for Q9.R6).

**The specifier's findings for later:** ADR 0065's syn001 equivalence leg has no SYN-001 composition in ADR 0063; ADR
0007 D2.4 has no band for a threshold at zero; no ADR names the verifier check that fails when a stream's PH point is
refused. Assign each to an ADR or a later package. Amendment 4 also says ADR 0066 D7's "PR liquid in a fixed volume →
`dae_index_near_singular`" example is wrong (a liquid that expands with T is regular) — the F7 exit in the note carries
the same example.

## Look hardest at

- **The freeze:** is every core item complete and unambiguous enough to freeze at W1's end — unit-owned vid fields and
  injectivity with ADR 0062 D7's grammar, `UnitDeclaration`, ModelManifest v2, `holdup_kind`, `DynamicSpec`, the F8
  manifest members? What is mislabelled core or preview?
- **Identity (F0 M1–M9):** anything that moves a legacy hash, fingerprint, cache key or replay; `differential_map` as a
  new field on a frozen dataclass (written only when set — does any v1 hash see it?); the compiler self-hash in v2
  `model_version` (departure 5 and the riskiest decision); 0.3.0 bundles replaying unchanged under F8's 7-step replay.
- **Completeness for the build lane:** can every work order be built without a further design decision? Name each
  missing one. Do the work orders and exits carry the specifier's 18 edits correctly once applied?
- **Numerics:** F6 D9 routing and its discrete coordinate; `std.pid` saturation closure (Q5.R9) and steady/dynamic
  bitwise agreement; F7 index/rank check, consistent re-initialisation, dormancy and the drain event (Q1.R8), event
  grouping (Q1.R10); the sheet's row sets, zero-flow forms and closed-form checks (are F6S.A1–A12 independent
  expectations, not self-generated?).
- **Frozen interfaces** touched (note §8 rows for ADR-F6/F7/F8; ADR 0008 C10 reversed by `state_rate`; ADR 0019
  amendments from 10): each change made by the ADR that is allowed to make it.

## Rulings wanted

1. Each of the eight departures: accept (with reason) or require a fix.
2. The specifier's three findings for later: which ADR or package owns each.
3. Any other departure from the note or the rulings you find.

## Deliverable

`docs/reviews/W1-P3-review.md`: findings ranked must-fix / should-fix / note, each with ADR section and a failure
scenario; the rulings; a verdict per ADR (accept after listed fixes / revise / reject) with exact edits, merged with the
specifier's 18 where they touch the same text (one consolidated edit list per ADR). Do not edit ADRs or rulings. Report
≤ 30 lines. Do not commit, no code, no subagents, no git state changes, nothing under `.claude/worktrees/` or
`~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; no web
fetches.

## Not to spend time on

Style, prose, F1–F5 internals beyond their interfaces with F6–F8, MSG, TX/X25/X26 designs themselves.
