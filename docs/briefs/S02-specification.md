# S02 — MESH column: specification only (design lane, `specifier`)

Package S02 (plan v1.2 §4.5, `docs/implementation-plan.md:282`; depends on S01). Branch `wp/S02` from `wp/S01`
(S01 unmerged at start). This cloud step is **specification only** — no production code.

## The question
Specify the equilibrium-stage MESH column on top of S01's countercurrent cascade: stage indexing; feed, condenser,
reboiler, pressure-profile and specification conventions; the valid specification combinations and the invalid-spec /
phase refusals; four matched column cases with analytic or independent expectations; and the test specification
(numbered falsifiable assertions) and work orders for the build lane.

## Facts with anchors
- Plan: S02 row `docs/implementation-plan.md:282`; X31 `:357` ("Four matched column cases, invalid specs/phases, two
  independent references where available" — S03 owns the two independent references).
- Blueprint `docs/blueprint-v3.1.md:600-602` (MESH with explicit component and energy balances, equilibrium relations,
  summation/state conventions, pressure profile, feeds, condenser and reboiler, stage indexing, valid specification
  combinations; staged activation and continuation; one trustworthy full-Newton strategy first; inside-out only after a
  measured need; nonideal/azeotropic cases only with validated data).
- S01 (the subsystem S02 builds on): `docs/derivations/S01-spec.md` (§2 rows and DOF, §4 phase coupling, §5 refusals,
  §6 initializer, §7 solve path, §14 non-claims :256, §17 Amendment 1 :289); code
  `src/openflowsheet/models/syn001/cascade.py`, `cascade_solve.py`; reference `docs/derivations/scripts/s01_reference.py`;
  decisions `docs/S01_DECISIONS.md` (its last open questions: T05b §6.6 vs S01's v2 policy; S01 scope L-rows now or in S02).
- Providers: SYN-001 only (`src/openflowsheet/thermo/syn001.py`; ideal, 3 components, T 280–440 K, P 0.5–2 bar).
  PR routes are vapour-only (ADR 0026, ADR 0043 Proposed) — no column VLE. State what S02 can and cannot claim with
  SYN-001 alone; real-chemistry columns need a liquid-capable method (out of scope).
- Register numbering: **R-530…R-539**. ADR number if needed: **0044** (0043 is L01's).

## Exit test
`docs/derivations/S02-spec.md` with: conventions (stage numbering, condenser/reboiler as stages or not, total vs
partial condenser, reflux/boil-up specs, pressure profile); DOF accounting and the admissible specification sets;
typed refusals for invalid specs and phases; four registered matched cases with expectations from an independent
generator `docs/derivations/scripts/s02_reference.py` (`--check`, ruff-clean; mpmath in the venv
`/home/user/openflowsheet/.venv`); numbered assertions `S02.A01…`; work orders (~120k each); manifest check list;
non-claims. Register entries; `DECISION:` lines in `docs/S02_DECISIONS.md`; Frank questions in `docs/FRANK_QUESTIONS.md`.

## Out of scope
Implementation; S03's independent references and perturbation studies; inside-out; rate-based; new property methods.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/S02-handoff.md`, stop. Report ≤ 150 words.
