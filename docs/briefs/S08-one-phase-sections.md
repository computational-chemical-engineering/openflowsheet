# S08 brief: one-phase column sections (design lane, `architect`)

Branch `wp/S08`, worktree `.claude/worktrees/s08`, from `main` `390e0af5`. Queue entry: `docs/CLOUD_WORK.md` l.53 (Frank,
2026-10-24, Q-S03-4 "Yes, plan a package"). Entry conditions: S03 spec §17.7 and R-632.

## 1. The question

How should the SYN-001 column reach a regular root whose signature has a dry or flooded section (some stages `VAPOR` or
`LIQUID`), instead of ending in a typed failure? The decision must take the form of an ADR against ADR 0005 D4 that
chooses between **a block rule in the phase contract** and **a model-side screen** (or a third route you can defend),
plus a design note with work orders and gates, so that the build lane has nothing scientific left to choose.

## 2. Why it needs the architect

It changes the phase-attempt contract (ADR 0005, one decision function shared by both controllers, Accepted) or adds a
second place where phase is decided, which the register rejected once (R-632). A wrong choice regresses every column,
cascade and flowsheet case that runs through `orchestrator/phase_contract.py`.

## 3. Current state (recon digest, main `390e0af5`)

**The stage model.** Each stage is one lifted split, PH-type (`feed = m_j`, the energy row fixes `T_j`):
`src/openflowsheet/models/syn001/cascade.py:9-16`; S01 spec `docs/derivations/S01-spec.md` §2 (l.34-62). Rows
(`cascade.py:662` `declared_rows`): `mix` :791, `mole` :799, `eq` :810 (via `models/rows.py:137`
`equilibrium_row`), `Ldef`/`Vdef` :823/:832, `energy` :867. The equilibrium row is division-free,
`v_ij L_j − K_i(T_j, P_j) l_ij V_j`, so the trivial splits V=0 or L=0 satisfy it and the phase contract must exclude them
(`rows.py:137-146`). K-values come from `provider.evaluate_phase` (`cascade.py:423`); there is no per-stage flash.

**Regime forms** (`cascade.py:960` `regime_form`; column version `column.py:1543`): `TWO_PHASE` pins nothing; `LIQUID`
pins `v_j`, `V_j` and drops `eq`, `Vdef`; `VAPOR` symmetric; `ZERO_FLOW` swaps `energy` for a label row.

**Phase selection** is the solver's active-set signature, decided in `orchestrator/region.py` (`:1606`
`screened_regime`, `:1626` `tp_regime`, `:527` `_band_regime`, `:644` `_contract_kernel`, `:781` `_pin`) and the
controller `orchestrator/phase_contract.py` (`decide` :463; `WallObserver` :189; disappearance :358, firing on
`BOUND_BLOCKED` on a watched variable :443; terminal `ACTIVE_SET_CYCLING` :404-407, :499;
`CONTRACT_V2 = "T05b-phase-contract-v2"` :47). Single-phase admissibility screen: `cascade_solve.py:426-447`
→ `tp_state.py:113` `single_phase_admissible`. Policy `S01_DEFAULT_V1` (`cascade_solve.py:103-109`).

**ADR 0005 D4 (Accepted), pasted:**
- *Restart point:* among the phase-rejected trials of the most recent line search that had one, the largest-α candidate
  whose reported signature is adjacent to the frozen one; if none is, the largest-α candidate. The new signature is the
  candidate's; on the lifted path each changed unit's split is set from the kernel at that state.
- *Disappearance (lifted):* a phase of a `TWO_PHASE` unit leaves when the attempt ends `BOUND_BLOCKED` on one of its
  watched variables (its total while the stream flows, a component while the stream's component is positive). A landing
  alone is an overshoot and the attempt continues. Single-phase units watch nothing.
- *Closure conversions (lifted), retained from T02:* an inadmissible converged state restarts in the kernel's regime; a
  failed attempt the kernel disagrees with at its end state restarts in the kernel's regime.
- *Precedence and gate:* as T03 §4.8; the restart gate checks the attempt budget, then cycling, then D6's opening checks.
- *Cycle rule unchanged:* `no_repeated_signature`, `max_attempts = 5`.
- All of this is **one function** called by both controllers, and one wall-observer class serves both.

**The block rule** (S02 spec §4.3, generator-verified). If stage j is `LIQUID` and stage j+1 emits vapour, a circulation
δ with composition `v_{j+1}/V_{j+1}` added to `l_j` and `v_{j+1}`, with a `T_j` shift, is a null vector of the Jacobian at
**every** state with that signature (`‖Jδ‖∞/‖δ‖∞ ≤ 5.2e-53`, `σ_min ≤ 4.4e-41`); the mirror holds for a `VAPOR` stage below
a liquid-emitting one. Consequence: a cascade signature can be regular only if it reads `VAPOR^a TWO_PHASE^b LIQUID^c` top
to bottom (ignoring `ZERO_FLOW`). A column whose condenser and reboiler are both partial under ratio or rate
specifications is all two-phase at a regular root.

**The failing case, P1** (S02 spec l.247, A12 l.286; M3 at Q_r* = 3 kW). Its only regular signature is LIQUID×5, with
the closed form `l_j = top`. Measured (`tests/test_s02_column_wo3.py:268`, held as a regression value; its docstring says
a move of this branch is re-registered with the design lane, not re-baselined):
- outcome `HOMOTOPY_STALLED`, cause `homotopy_stalled(BOUND_BLOCKED)`;
- attempts: target `BOUND_BLOCKED` on 2P×5; target `LINE_SEARCH_FAILED` on `(2P, L, 2P, 2P, 2P)` — a signature that
  breaks the block rule, so singular — closing `ACTIVE_SET_CYCLING`; then edge 3 `HOMOTOPY_STALLED` from 2P×5.
- Before the target solve, an isothermal pre-solve gate refuses any signature that is not all `TWO_PHASE`:
  `INITIALIZATION_FAILED`, `initialization_failed(s01-isothermal-presolve-v1, not_two_phase)`
  (`cascade_solve.py:675-691`). Homotopy stall sites: `orchestrator/homotopy.py:346`, `:384`.
- A related refusal: `column_solve.py:570` `single_phase_specified_stage` →
  `unsupported(temperature_specification_on_single_phase_stage:<j>)` (`tests/test_s06_column_wo2.py:732`).

**Every other registered flowing column case is all two-phase at its root**: S01 C1–C5 cascades (C4 `(2P, L, L)` and C5
`(V, 2P)` are cascades and conform to the block rule), S02 M1–M4, S06 J1–J8, S03 RC1–RC5 and their perturbations.

**Providers.** Columns accept only the SYN-001 provider (`cascade.py:397-420`, S03's S11 refusal); keep that.

## 4. Constraints and invariants

- Every registered S01, S02, S06 and S03 case stays bit-identical (states, outcomes, attempt records, certificates),
  unless you state and justify a change; the gate is `scripts/gate.sh` plus CI on x86-64 and aarch64.
- The phase contract is shared by every lifted solve (flash units, flowsheets, cascades). A change to `decide` must leave
  every non-column attempt record identical; say how that is proved.
- Interfaces in plan §2.1 and schemas in §2.2 are frozen; a new outcome string, cause grammar or schema field needs the
  ADR to say so.
- Exact property caches key on exact canonical inputs; residual and Jacobian describe the same function at the same
  state. No placeholder success path: anything not covered still ends typed.

## 5. Already decided, and what is open

Decided: S08 exists (Frank); P1 is the first use case; S03 keeps its limitation text until S08 lands; the SYN-001-only
refusal stays. R-632's rejections stand as the starting position: *a block rule in the contract* was rejected as "model
structure inside the single decision function … would not cover the measured end-stage restarts"; *a screen around
`solve_region`* as "a second decision function". **Reversing either takes the new ADR**, which must say what changed.

Open (decide):
1. The route: block rule in D4, a model-side screen, an initialization route (for example a pre-solve that may land on a
   non-all-two-phase block-conforming signature), a homotopy route, or another. Why the others fail.
2. What happens to the pre-solve's `not_two_phase` gate.
3. Whether more registered use cases are needed (a flooded bottom section, a dry top section, a partly one-phase column)
   and their generator-verified roots; the design note registers them or names who does (`specifier`).
4. The new attempt-record expectations for P1 (it reaches LIQUID×5 = the closed form) and what A12's held branch becomes.
5. The work orders, each with its acceptance test, sized ~150k context each.

## 6. Already tried and rejected (measured)

- R-533 / S02 §18.3 / R-632: the block rule in the contract was declined twice; the reason recorded is model structure in
  the decision function, and that it would not cover the measured end-stage restarts (`(2P, L, 2P, 2P, 2P)` is an
  interior L, not an end-stage restart).
- ADR 0044 (edge 3 after `LINEAR_SOLVE_FAILED` in a restart) and ADR 0015 (edge 3 sequential re-initialization) did not
  rescue P1: edge 3 ends `HOMOTOPY_STALLED` from 2P×5.

## 7. Verification

The design must name: P1's expected outcome and signature and the closed-form check; any new cases with
generator-verified roots (mpmath generators, as `docs/derivations/scripts/`); the bit-identity proof for every existing
case (attempt-record digests before and after); mutation tests that show the new path is the one doing the work.

## 8. Deliverable

- `docs/adr/0048-s08-one-phase-column-sections.md` (status Proposed) against ADR 0005 D4, with the rejected alternatives.
- `docs/derivations/S08-design.md`: the design, the registered cases (or a `specifier` work order to register them),
  numbered falsifiable assertions, work orders, gates.
- Register entries after the current last entry in `docs/decision-register.md`.
- A docs-only commit on `wp/S08`. Do not push. Report in at most 25 lines.

## 9. Out of scope

Other property methods in columns (S10-C), the third reference tool (S09), reboiler/condenser specification types not
already registered, transient behaviour.
