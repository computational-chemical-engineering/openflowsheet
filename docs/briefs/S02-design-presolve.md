# S02 — the pre-solve does not converge: opening rule and edge-3 trigger (design lane, `architect`)

Branch `wp/S02`, worktree `/home/user/ofs-s02`. WO-1, ruling round 1 and WO-2 (partial) are committed
(`dbfc35f`, `47eb3aa`, `324eb8e`). WO-3 waits on this.

## The question
S02 spec §7.3's pre-solve (TP-type, one attempt, opening `x_K` projected by the TP closure, S01 spec §17.10) does not
converge on any registered case M1–M4. Design the opening/globalization rule that does, within the existing
contracts (ADR 0005, ADR 0010, ADR 0012, T05b-phase-contract-v2), and answer whether `LINEAR_SOLVE_FAILED` at a
structurally singular phase pattern (S02 §4.3, R-533, Q-S02-3) should trigger recovery edge 3 or be prevented by the
phase contract. The blueprint's direction: "Initialization uses staged activation and continuation. Ship one
trustworthy full-Newton strategy first" (`docs/blueprint-v3.1.md:600`).

## Measured facts (WO-2; `docs/S02_DECISIONS.md:57-59`, handoff `docs/briefs/S02-WO2-handoff.md`)
- M1: `LINEAR_SOLVE_FAILED`; opening V,V,V,2P×4 — `x_K`'s stages 1–3 superheated at `T_j⁰` (Σz/K 0.72–0.88); stage 1
  VAPOR under a reflux-ratio spec is §4.2's singularity. M2/M4: `ATTEMPTS_EXHAUSTED`. M3: `ATTEMPTS_EXHAUSTED`,
  opening 2P,L,L,L,L (stages 2–5 subcooled, ΣzK 0.79–0.92). Variants likewise.
- Scratch alternatives: default `max_attempts` → M2–M4 converge to `ref`, M1 `LINEAR_SOLVE_FAILED`; PH-type
  pre-solve → M2–M4 converge, M1 `BOUND_BLOCKED`; both → M1 `ACTIVE_SET_CYCLING`.
- M1's target from the generator's own `x⁰`: 2P×7 `BOUND_BLOCKED` → (L,2P×6) `BOUND_BLOCKED` → (L,L,2P×5)
  `LINEAR_SOLVE_FAILED` (rank 94 of 95; §4.3's singular pairs). `LINEAR_SOLVE_FAILED` is not an ADR 0010 D3 trigger;
  forced edge 3 reaches `ref.target` (2.4e-8 of the tolerance).
- Step 4–5 from `x⁰` are correct (A06 M2–M4 pass; deviation ≤ 7.5e-3 of tolerance; A10 floor 6.4e-11).

## Anchors
Spec `docs/derivations/S02-spec.md` §4 (phases, §4.2–§4.3 singularities), §6 initializer, §7 solve path, §17
Amendment 1; S01 spec `docs/derivations/S01-spec.md` §6–§7, §17; code `src/openflowsheet/models/syn001/column.py`,
`column_solve.py`, S01's `cascade_solve.py`; `src/openflowsheet/orchestrator/region.py`, `phase_contract.py`,
`homotopy.py`, `attempts.py`; ADR 0010 D2–D3 (`docs/adr/0010-globalization-homotopy-ptc.md`), ADR 0005 D3–D4.

## Exit test
A design, measured on M1–M4 and the variants in scratch code (do not commit production code), written as a dated
"Amendment 2" of `docs/derivations/S02-spec.md`: the opening rule / staged activation / continuation as an algorithm
with acceptance criteria, the edge-3 trigger answer (if it changes ADR 0010's trigger set or a frozen interface, an
ADR 0044 is required — say so and draft it), updated assertions (A05–A07 and any new), and a work order for the
build lane. Register entries **R-546…R-549**. If M1 cannot be reached without a capability outside S02's scope, say
so, register M1's expected outcome as a typed failure, and keep it as a stated non-claim — never weaken a tolerance.
Also rule on Q-S02-WO2-3 (A07's `same_root` across specification sets). Report ≤ 150 words.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/S02-design-handoff.md`, stop.
