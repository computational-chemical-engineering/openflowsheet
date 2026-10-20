# M07 recon digest (recon, 2026-10-09)

Paths are relative to the repo root (main). `wp/<branch>:<path>` = only on that branch (`git show`). Worktrees under
`.claude/worktrees/`. **Since this digest: M02 is merged into main (`9f6a9be`; manifest `tested` at `ba90619`).**

## 1. Plan and blueprint
- Plan M07 row (docs/implementation-plan.md l.269): `| M07 | M05, M06: real reference journey and v0.2 gate. | Before/after
  design decisions, costs, uncertainty and truth checks; W21–W27; reproducible report and artifacts. | MOD/SYS | Design / Build |`
- S01 l.281 (countercurrent equilibrium-stage subsystem, M07); R03 l.286 (Peclet/CFD refinement, M07, conditional: only with a
  validated family and authorized compute, else experimental and outside release claims); D14 l.309 (certificates: model
  verification separated from empirical validation/optimality; K04, T06, M07).
- W21–W27 (l.350–356): W21 PyMRM boundary/accuracy/execution/provenance (M01/M02); W22 one validated nonideal property route
  (M01); W23 surrogate conservation/domain/derivative/default UQ/promotion (M04); W24 fixed-topology optimization, eligible
  trust-region example, parent-model checks (M03/M05); **W25 end-to-end real reactor refinement with honest evidence limits
  (M07)**; W26 diagnostic web shell through shared contract (M06); W27 external agent benchmark adaptation attempted,
  inaccessible assets disclosed (M06).
- Plan §5.1 l.54: verdict PASS/FAIL/BLOCKED with evidence; BLOCKED never counts as pass; "all tests pass" without a fixed
  inventory does not close a gate. l.273–275: if inputs are unavailable keep the adapter testable with a synthetic model, but
  do not claim the real scientific journey is complete.
- Blueprint docs/blueprint-v3.1.md §2.3 l.64–70: scientific journey = reactor–separator–recycle whose reactor progresses from
  a simple model to a PyMRM distributed model and a derived surrogate; compare operating-point decisions, conversion/
  selectivity, duties, pressure drop where modeled, computational cost; synthetic never presented as validated real
  chemistry; more expensive models introduced because their effect on the decision can be measured. §14.4 l.588–597:
  end-to-end refinement reports before/after decisions, constraints, discrepancy and compute cost; insufficient evidence or
  exhausted budget is a valid honest outcome. l.586: real-chemistry journey specified for v0.2 with data and comparison
  feasibility established.

## 2. Gates
- v0.1: gates V11–V20 (docs/requirements.yaml); spec docs/derivations/T08-release-spec.md (§4 l.89–176, §8 RC l.413–443);
  ADR 0021 (D3 per-release FAIL acceptance, D5 tag is Frank's); scripts/v0_1_gate.py (GATES l.93, RC_STEPS l.101,
  judge_gate l.421); verdicts in docs/reviews/T08-verdicts.md; RC record docs/t08-rc-record.md; tests
  tests/test_t08_w4_v0_1_gate.py. docs/RELEASING.md l.134: a 0.2.x release needs scripts/v0_2_gate.py and its own RC.
- v0.1 numerical journey = K06 flash-recycle demo (gate G06; `cli solve SYN-001-nominal --out ./bundle`, `inspect`,
  `replay`). examples/README.md: M07's real reactor refinement journey is a later contribution under examples/; "an example
  is a demonstration, never gate evidence by itself".
- v0.2 alpha gate (wp/V02-alpha-gate @ c97da19, worktree `alpha-gate`; not on main): spec
  docs/derivations/V02-alpha-release-spec.md (§3 claims l.105, §6 W21/W22 l.271–437, §7 script l.438, §8 RC l.629, §14
  Needs Frank l.951); ADR 0028 (Proposed; R-238, R-239); scripts/v0_2_gate.py (GateSet l.115, GATE_SETS l.142,
  judge_gate l.576); tests tests/test_m07a_v0_2_gate.py. Registry entry `v0.2-alpha-gate-v1`: covers 0.2.0aN; claimed
  V11–V20, W21, W22; not_claimed W23–W27; evidence package M07a; packages M01, M02; verdict doc
  docs/reviews/V02-alpha-verdicts.md; rc record docs/v02-alpha-rc-record.md. Spec §7.1 l.450 / ADR 0028 l.215: **M07 adds
  `v0.2-gate-v1` for 0.2.0, 0.2.0bN, 0.2.0rcN, re-judging every claimed gate at its own C.** The script judges nothing; it
  reads verdicts and decides only whether a tag may be proposed.

## 3. What M07 consumes
- **M05** (.claude/worktrees/m05/docs/design/M05-trust-region.md; ADRs 0038–0040 on wp/M05): TRF adapter + fixed-topology
  refinement study on C1. D10 decision = reactor inlet T_in, φ (purge) fixed at 0.02, objective max liquid NH₃ product.
  **REAL box is [653.15, 693.15] K by R-313/R-315 (the note's D10/N-F6/§11 text still says [643.15, 733.15] — stale; WO-6
  implemented REAL_BOX [653.15, 693.15]).** D11 loop: stage A (TRF on promoted surrogate) → B (parent checks P1–P5) → C
  (TRF on parent) → B, ≤ 3 iterations. D13 budgets 400 cold / 4 h per study; 250 cold / 30 iterations per TRF run. D16: no
  job operation in M05; M07 decides. Statuses: TRF_CONVERGED, TRF_TRUTH_REFUSED(...), TRF_STALLED_INCONSISTENT; candidate
  PARENT_LOCAL_EVIDENCE; study DECISION_STABLE, BUDGET_EXHAUSTED. Record schema trust-region-study-v1 (§9.1 l.672–704):
  spec, environment, runs[], candidates[] (checks P1–P5, poll, noise_floor, status, limitations), accounting, status,
  claims {global_optimality false, trf_theory, stationarity}, limitations, artifacts. Gates G1–G13 (l.823–840); G11 REAL
  opt-in. §11 l.767–798: may claim W24's M05 half on TR-E2 + synthetic FD; may NOT claim global optimality, TRF guarantees
  on the real reactor, a validated plant optimum (R-169), or W25. §15.1 Needs Frank: N-F1 objective, N-F2 δ_T 0.5 K, N-F3
  real budget 400/4 h (alt: targeted check only, stage C on the real parent left to M07), N-F5 surrogate only if promoted,
  N-F7 no job op (alt: additive op in M07). Status: WO-1…7 done; real parent adapter, WO-5c (`at_coupling`, R-309), WO-8 runs
  remain.
- **M04** (wp/M04:docs/derivations/M04-spec.md; ADRs 0036, 0037): promotion §7 l.380–443 (PROMOTABLE / NOT_PROMOTABLE /
  INSUFFICIENT_EVIDENCE); §7.4 l.443: a promoted surrogate may not claim coverage at a solved operating point or optimizer
  candidate (needs a parent evaluation, `targeted_check`, M05/M07). §3.1: T_in box [653.15, 693.15] K. N4 l.813: M07 must
  supply its T_in decision range. Synthetic prefix-plan PROMOTABLE; real C1 run WO-11 not yet done. Surrogate registered
  on wp/M04 (`c1.reactor_surrogate`, W27 row R-301).
- **M02** (merged; docs/design/M02-pymrm-adapter.md): reactor v3 domain R-315 = rung V5: T_in [653.15, 693.15] K, P [9, 11]
  MPa, H₂/N₂ [2.5, 3.5], inerts [0.035, 0.2], per-tube flow [0.5, 2] × F_nom; below floor → `out_of_domain`; timeout 450 s.
  l.1775: the journey's design space is v3's box. l.1891 / R-306: M07 builds its real revision directly (as
  benchmarks/m02/c1-loop-real.json does). G12 real loop state: 673.15 K, 10⁷ Pa, H₂/N₂ 3.000, inerts 4.3 %, 0.811 × F_nom;
  3 outer iterations, VERIFIED, replay MATCH. Execution: external subprocess, "not a sandbox", Linux-only, R3. A real
  evaluation 25–45 s (≤ 150 s under load). Risk K6: Q-F4 corners failed → narrower design space for M05/M07.
- **M06** (main): W26 tested (G1–G15). W27 (docs/derivations/M06-W27-registration.md): the 45-case Tier 1 sample is drawn at
  M07 from the v0.2 candidate's coverage by a seeded rule (seed "W27-OpenIDAES-450-sample-v1"); Tier 0 classifier re-run at
  M07 against the candidate registry; frame 450 minus ARTIFACT_INCOMPLETE (449); 3 canaries disjoint from the sample; model
  = most recent Claude model by exact id. Frank approved the 45 runs (USD 15–45). Q3–Q5, Q7 open with defaults. M06 WO-17
  (3 canaries + 45-run campaign) runs at M07 and needs: v0.2 binder reading in `snapshot.READINGS`, M01/M02 id rows, U14
  rewrite for campaign records, a `specifier` read of registration §20.
- **M03** (wp/M03): sensitivities (ADR 0031: M07 journey inherits them); W24 optimizer part BLOCKED until Frank answers N1
  (nlp extra licences: EPL-2.0, CeCILL-C, LGPL-2.1-only libiconv, GPL-3.0 WITH GCC RLE runtime libs, …).

## 4. Chemistry (docs/v02-real-chemistry-dossier.md)
§1 N₂ + 3H₂ ⇌ 2NH₃, ΔH₂₉₈ = −92 kJ/mol. §3 loop: fresh feed → mixer (recycle) → preheater → reactor → cooler → HP flash
(liquid NH₃) → vapour → purge splitter → recycle; zero-ΔP convention (ADR 0022 D2). §9: decision = reactor inlet T (alt:
purge); equilibrium reactor favours ever-lower T, kinetic reactor has an interior optimum, so fidelity changes the decision
qualitatively — "not yet demonstrated on the loop — M01/M07 work". §7 IDAES 2.13.0 reference loop records c1-idaes.json, no
comparison claimed. §12 does not establish: validation, registered reference values, correct kinetics (K_NH₃ per R-152),
reproduction of solved cases, rights, vapour-only adequacy.

## 5. Needs Frank relevant to M07
M05 N-F1 (objective), N-F3 (budget); W27 Q3–Q5; alpha N3 claim set; M02 N7 (shipped domain; V5 selected); M03 N1 (licences).

## 6. Numbering
Highest register heading: main R-318 (after the M02 merge; wp/M04 R-302, wp/M05 R-300). Next free ADR: 0041 (0029 unused).
Check the branch being merged before using a number.

## 7. Pattern
Per-release gate script with a version-pattern registry (scripts/v0_2_gate.py GATE_SETS); claimed/not_claimed tuples;
DECISION lines in Needs-Frank sections; journey as demonstration, not evidence (examples/README.md).

## 8. Not found
No M07 spec/design anywhere; no standalone "C1 journey" paragraph (blueprint §2.3 is the authority); W25 claim wording does
not exist yet.
