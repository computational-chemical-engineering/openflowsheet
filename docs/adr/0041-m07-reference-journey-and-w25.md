# ADR 0041 — M07: the reference journey takes one decision through four rungs, compares decisions by the parent's objective against its noise floor, and W25 is met by honest reporting, not by a changed decision

**Status:** Proposed, 2026-10-16. Accepted when M07's evidence manifest is `tested` for M07.A00–A26 and the design-lane
review of the journey's work orders (WO-1, WO-4) is recorded.
**Author:** design lane (`specifier`), M07; brief `docs/briefs/M07-specification.md` with the 2026-10-16 updates.
**Normative text:** `docs/derivations/M07-spec.md` §3–§6, §11; reference `benchmarks/m07/registration.json`
(`docs/derivations/scripts/m07_reference.py`, `--check`).
**Register:** R-331…R-337; Amendment 1: R-420…R-427.

## Context

Blueprint §2.3 asks for a reactor–separator–recycle journey whose reactor rises in fidelity, with decisions compared;
§14.4 makes W25 "reports before/after decisions, constraints, discrepancy and compute cost", with insufficient evidence
or an exhausted budget a valid outcome. M04's real surrogate is `NOT_PROMOTABLE` (R-364). M05's study runs on the
parent without it (M05 §7.6). No equilibrium reactor exists in the repository. The REAL decision box is
[653.15, 693.15] K (R-330).

## Decision

- **D1 — One decision, four rungs.** SPEC-S3-T of `C1-LOOP-M02-v1`, objective `c1-obj-nh3-liquid-v1`, purge 0.02.
  R0 = the synthetic stand-in on a nine-point grid (653.15 + 5k K); R1 = PyMRM v3 on the same grid; R2 = the M04
  surrogate only if its recorded verdict is `PROMOTABLE`, otherwise `SURROGATE_NOT_PROMOTABLE` with zero evaluations;
  R3 = M05's REAL study (spec §4.2).
- **D2 — Decisions are compared by the parent.** Each pair (R0→R1, R1→R3) is judged on parent values at both decisions
  with ε = the sum of M05's noise floors; the five-way fidelity-effect class of spec §4.4.4; truth check TC-1 against the
  parent grid; bound activity at 10⁻⁶ scaled. The journey never reports a decision from R0 or R2 (spec §4.4.7).
- **D3 — W25 is met by its eight clauses** (spec §5), none of which requires a changed decision, a converged study, an
  interior decision or a promotable surrogate. `TC1_CONTRADICTED` is a reported limitation and a finding, not a FAIL.
- **D4 — Budget `M07-budget-v1`** (460 cold experiments, 6 h), checked before each evaluation; exhaustion is reported.
- **D5 — No new job operation**; one script `scripts/m07_journey.py`. Reactor-dependent evidence carries between
  commits only by byte-identity of the registered determining files, else it is re-run.
- **D6 — Refusal is a result**: `UNSUPPORTED(reactor_environment_unavailable)`, `UNSUPPORTED(m05_study_unavailable)`.
  *Amendment 1 (2026-10-16, spec §18 A1.3, R-422):* and `UNSUPPORTED(surrogate_loop_unavailable)`, R2's refusal under a
  `PROMOTABLE` verdict without a surrogate-backed loop. W25 (a) is then not met.

## Alternatives rejected

- *Judge W25 on whether fidelity changed the decision.* That makes the outcome the criterion; the blueprint makes the
  report the criterion and names the honest negatives.
- *Compare each rung's decision by its own model's objective.* The stand-in's J is flat by construction; only the
  parent can measure what a decision is worth.
- *A dense grid or a grid-only journey without M05.* Nine points already cost ~1 h on the real reactor; M05's study is
  the refinement the plan names.
- *An equilibrium-reactor rung.* No such model exists; adding one is a package of work (spec §15 N3).
- *A job operation for the journey.* Extends a frozen interface for one script (M05 N-F7 deferred it here).
- *Re-run every reactor rung at the RC commit unconditionally.* Up to 5 h per RC for no information when the
  determining files are identical and the solves are bitwise (G12).

## Affected requirements

W25 (owned), W24 (consumes M05's record, claims nothing new), W23 (reads M04's verdict), D14 (verification kept apart
from validation and optimality).

## Migration impact

None on frozen interfaces or schemas. New files: `scripts/m07_journey.py`, `benchmarks/m07/**`, tests.

## Acceptance evidence

M07.A00–A15 in the default gate; M07.A20–A26 from the opt-in real journey at J; M07.A61 at C.
