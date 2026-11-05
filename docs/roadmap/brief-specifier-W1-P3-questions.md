# Specifier brief: W1 P3 scientific questions and the entropy datum (Amendment 4; the `std.*` equation sheet)

Status: brief, 2026-11-05. The one specifier round after the P3 architect pass (orchestrator decision 2026-11-05,
`docs/roadmap/decisions.md`). It batches the seven questions ADR 0065–0067 list (each with the architect's default) and
ADR 0063 risk 5. One reviewer pass on the P3 ADR set follows and checks the ADRs against your amendment. ADR 0060–0067
are Proposed; design against them as written.

## Two deliverables

**A. "Amendment 4 (2026-11-05)"** at the end of `docs/roadmap/foundation-rulings.md`, in the form of §14/§15: per item
a numbered clause (new Q-numbered rule or an amended one), falsifiable assertions with the exit that gains them (F4,
F6, F7, F8, TX), the exact edit each ADR needs, the note edits, and "Not established". Items:

1. **Entropy datum for a record without s° (ADR 0063 risk 5).** `docs/adr/0063-F4-property-methods.md` D4 (80–100),
   risk 5 (205–208); review finding `docs/reviews/W1-P2-review.md` S6 (108–115); ADR 0061 risk 6 (592): no legacy record
   has s°; PR-C1 has no entropy (`src/openflowsheet/thermo/pr_c1.py:761`). Q2.R1/R4 (rulings 185–236). Default: S shift
   only for methods providing `s`; a component without s° takes s = 0 in its anchor phase, notice
   `entropy_datum(<c>)`; any reaction or equilibrium reading its `s` or `g` refused `component_not_reaction_consistent`.
   Say whether a PS/TS specification or an isentropic unit (std.compressor/turbine, ADR 0065) on such a component is
   admitted (entropy differences at fixed composition are datum-free) — that is the practical question.
2. **SQ-F6-1** routing of exactly one active FLUID phase and τ_ρ: ADR 0065 D9 (202–216), questions (470–479). Default:
   by `character` (O-11's identification rule, rulings §11; Q4.R5–R6 at 451–558), τ_ρ = 1e-6 relative. Note this gives
   O-11 (Frank's open preference) a numerical consequence; state it so Frank can be told.
3. **SQ-F6-3** steady saturation closure of `std.pid`: ADR 0065 D10 (217–235). Default as D10 (σ·e sign rule).
4. **SQ-F6-4** `heat_direction` tolerance and equal-temperature contact: ADR 0065 D11 (236–245); existing check at
   `src/openflowsheet/verify/table.py:965`. Default: that check's tolerance; equality passes.
5. **SQ-F7-1** τ_idx for `dae_index_near_singular`: `docs/adr/0066-F7-problem-ir-run-kinds.md` D7 (152–160), questions
   (346–352). Default: K04's `ILL_CONDITIONED` threshold on the scaled ∂g/∂z (`docs/derivations/K04-certificate-spec.md`).
6. **SQ-F7-2** simultaneous events, τ_ev and order: ADR 0066 D5 (111–137). Default: the integrator's event-location
   tolerance; (priority, id) order; one re-initialisation after the group.
7. **SQ-F8-1** grazing events under `forced_replay`: `docs/adr/0067-F8-identity-replay-evidence.md` (175–185, 286–290);
   ADR 0007 D2.4. Default: τ_g = event-location tolerance; `MATCH` with near-threshold semantics; other mismatches
   `forced_replay_divergence`.

**B. SQ-F6-2: the equation sheet `docs/derivations/F6-std-seed.md`** (ADR 0065 D13-area, lines 296–310; risk 1 at 458).
For each `std.*` unit — feed, sink, mixer, splitter, heater, valve, flash, pump (`work_model: isentropic |
incompressible`), compressor, turbine (isentropic reference = PS state point, ADR 0064 D4), `std.pid` (steady) — the
`h_mass` row set (division-free, Q1.R2), its zero-flow forms (Q1.R4, Q5.R7; ADR 0012 D4(c)/D12 mechanism), the
reactivation kind (Q1.R6, S3; rulings 992) and `t_seed`, with the T-form rows it restates. Sources of the approved
T-form rows: `docs/derivations/SYN-001.md` (units section), `docs/derivations/S11-units-design.md`, ADR 0051, ADR 0012
D12; Q1.R1–R6 at rulings 31–82. Gates E-F6-6 and E-F6-16 (ADR 0065 exits). Give, per unit, at least one analytic or
closed-form check a test can assert (not a self-generated fixture).

## Constraints

Released numbers stay; `nTP-v1` byte-identical; no identity-bearing legacy module edited (S1); R-924 (admit with
declared limits; refuse typed, never placeholder success). Adopt earlier rulings; amend them only explicitly, in the
§13–§15 form. Every tolerance you fix states the measurement that would amend it (rule 6), like §11's O-rows.

## Order and budget

Do A first (it is short), then B. If your context approaches ~250k tokens before B is complete, finish the unit in
hand, write `docs/roadmap/W1-P3-specifier-handoff.md` (≤ 40 lines: done, next, open) and stop.

## Deliverable rules

Report ≤ 25 lines: per item the ruling in one line (and whether it differs from the default), the sheet's state, edits
the ADRs need (count), "Not established". Do not commit; do not edit the ADRs or `target-architecture.md`; no production
code; no subagents; never touch `~/.config/procsim/` or `.claude/worktrees/`; do not read `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`; no web fetches; no git state changes (other agents work concurrently).
