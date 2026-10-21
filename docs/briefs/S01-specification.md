# S01 — countercurrent equilibrium-stage subsystem: derivation and test specification (design lane, `specifier`)

Package S01 (plan v1.2 §4.5, `docs/implementation-plan.md:281`; v0.3's first package; Frank started v0.3 in the
cloud queue of 2026-10-21). Branch `wp/S01` from `main` `3c10e97`. Lane: Design lead / Build second.

## The question
Specify, so that a build-lane engineer can implement and test it without further scientific choices, a
**countercurrent equilibrium-stage subsystem**: N equilibrium stages, liquid down / vapour up, with explicit DOF,
energy/phase coupling, an initializer, and Newton continuation — on the **existing property providers only**.
It is the precursor of S02's MESH column (`docs/implementation-plan.md:282`; blueprint `docs/blueprint-v3.1.md:600-602`:
"A countercurrent equilibrium-stage subsystem is the precursor. A once-through flash train is not claimed to reproduce
column coupling … Ship one trustworthy full-Newton strategy first; add inside-out only after a measured need").

## Facts with anchors
- Providers: **SYN-001** `src/openflowsheet/thermo/syn001.py` — synthetic ideal 3-component (A, B, C) fixture,
  closed-form `ln K_i(T,P)` (:292), `∂lnK/∂T` (:301), `∂lnK/∂P` (:306), `h^L` (:318), `h^V` (:323); constants :47-59
  (c_p 100, T_b 320/360/400 K, L 25/30/35 kJ/mol, domain T 280–440 K, P 0.5–2 bar). Derivation
  `docs/derivations/SYN-001.md` (§2 enthalpies :34, §3 K-values :58, §6 energy bookkeeping :157). **PR C1**
  `src/openflowsheet/thermo/pr_c1.py` is vapour-only (ADR 0026; LIQUID regime deferred) — not usable for VLE stages.
- Row shapes: `src/openflowsheet/models/rows.py` (balance orientation inflow − outflow = ADR 0008 D3.3, :1-40;
  `equilibrium_row`, `energy_row`, …). Every equation declares `accumulation` (ADR 0008 D3; readiness test
  `tests/test_adr_0008_transient_readiness.py` M1–M5). Unit pattern: `src/openflowsheet/models/syn001/flash.py`
  (`TPFlash` :205), `ph_flash.py`, `ph_kernel.py`, `saturation_band.py`.
- Contracts to compose with, not reopen: ADR 0001 (units, state, zero flow), ADR 0005 (phase-attempt contract,
  D2–D5), ADR 0010 (globalization; D2 typed homotopy `specification_continuation`), ADR 0011 (PH closure, reaction
  datum), ADR 0012 (saturation band, phase contract v2, zero flow). Numerics: `src/openflowsheet/numerics/newton.py`,
  `orchestrator/homotopy.py`, `orchestrator/phase_contract.py`.
- Spec style to follow: `docs/derivations/T05-unit-models-spec.md` (contract / causal evaluator / registered cases);
  reference generators under `docs/derivations/scripts/*_reference.py` (independent high-precision expectations).
- Register numbering for this package: **R-505…R-519**. ADR numbers: next free is **0043**.

## Deliverable (exit test for this design step)
`docs/derivations/S01-spec.md` (and an ADR 0043 if a decision needs one) containing:
1. Variables, equations, and an explicit **DOF count** for N stages × 3 components; the specification set (feeds,
   stage pressures, per-stage duty or adiabatic) and what is fixed vs free; units and sign conventions.
2. **Energy/phase coupling**: how a stage that leaves the two-phase region is handled (ADR 0005/0012 vocabulary),
   zero-flow behaviour, and the typed failures.
3. **Initializer** (e.g. a constant-K/constant-molar-overflow start with an analytic solution) and **Newton
   continuation** (homotopy parameter, path, step control, what is recorded) — stated as an algorithm with
   acceptance criteria, not code.
4. **Numbered falsifiable assertions** `S01.A01…` each with an **analytic or independent expectation** (e.g. Kremser
   at the constant-K endpoint; N = 1 equals the existing SYN-001 flash; overall component and energy closure; an
   independent reference generator `docs/derivations/scripts/s01_reference.py` at high precision for registered
   cases; perturbation/phase-disappearance cases; invalid-spec refusals). Tolerances justified.
5. Work orders for the build lane, sized ~120k context each, with which assertions each closes; and the evidence
   manifest's check list (status `tested` needs every assertion's test to pass).
6. What the spec does not establish (no column conventions — that is S02; no real-chemistry validation).

## Out of scope
New property methods or providers; condenser/reboiler/column specification conventions (S02); inside-out methods;
rate-based models; any change to frozen interfaces (plan §2.1) or schemas without an ADR.

## Agent rules
Context cap about 120k; at the cap commit, write a handoff of ≤ 30 lines to `docs/briefs/S01-handoff.md`, stop.
Report ≤ 150 words. Defensible choices: one `DECISION:` line each in `docs/S01_DECISIONS.md`. Questions only Frank
can answer: `docs/FRANK_QUESTIONS.md` with your default, then continue on the default.
