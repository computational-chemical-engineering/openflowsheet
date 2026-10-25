# S09 — BioSTEAM as a third column reference: levels, SYN-001 mapping, solve ladder, harness checks, controls, the three-tool X31 rule and test specification

Design lane (`specifier`), 2026-10-26. Package S09 (`docs/CLOUD_WORK.md:54`; Frank, Q-A2-4 "Plan a 3rd tool",
2026-10-24; Q-S09-1 "BioSTEAM first", 2026-10-25, `docs/FRANK_QUESTIONS.md`). Brief
`docs/briefs/S09-third-reference-tool.md`. Base: `main` at `390e0af5`, with S03 merged (`docs/derivations/S03-spec.md`
§0–§19, verdicts `docs/reviews/S03-verdicts.md`, review `docs/reviews/S03-review.md`).

Generator `docs/derivations/scripts/s09_reference.py` (stdlib and mpmath at 50 digits; imports nothing from `src/`).
`--emit` writes `docs/derivations/scripts/s09_cases.json`; `--check` re-derives **167 claims**, refuses on a failed one
and byte-compares the file (SHA-256 `d4514b4e…5bab7`) in under a second. It pins three S03 files by SHA-256 (§0).

Register **R-740 to R-747**. R-728…R-732 are held by S08 on `wp/S08` (unmerged); R-733…R-739 are left unused so
that the two packages cannot collide.

## 0. Authority and scope

Normative for S09. It composes with S03 (all of §0–§19), T06 §9, ADR 0014 D7, ADR 0001 (units, signs) and ADR 0005
D4, and reopens none of them. **S09 adds one tool. It does not re-judge IDAES or DWSIM**: every S03 case, quantity,
tolerance, rule, threshold, control rule (§17.3 with §18.3), record and classification stands, byte for byte. S09 reads
three S03 files and pins them:

| File | SHA-256 |
| --- | --- |
| `docs/derivations/scripts/s03_cases.json` | `c901d6c90f4b700b92ff98e2a01ae7e8f1d5557b80dd647e3b14e089d3703f39` |
| `docs/derivations/scripts/s03_reference.json` | `95ef9bd2551267e37c225764b5ed159d9f14911c2bb8b05a5905b8b65cec0c67` |
| `benchmarks/s03/references/comparison.json` | `5c7d139c0547f17bfa318f33b106cdb5749b9eaacbccb07cf1dedd570593585d` |

**What S09 adds**, as specification content of the kind T06 §9.3's rows and S03 §5 are:
- a third reference tool, BioSTEAM, with its expressibility levels, including one new level form for a
  sequential-modular tool (§2);
- BioSTEAM's SYN-001 definition and its readback self-check (§4);
- a registered solve path, ladder and outer loop (§5);
- harness checks that replace the tool's convergence report, which BioSTEAM does not make trustworthy (§6);
- BioSTEAM's positive control (§7);
- the X31 reference clause and D19's statement for three tools (§8);
- a ruling on the feasibility spike's blindness exposure (§9).

**No ADR is needed** (R-740). No frozen interface (`docs/interfaces-frozen.md`) and no accepted ADR changes:
- no `Protocol`, schema, quantity kind, check category or registered root changes, and no code under `src/` is
  specified;
- ADR 0014 D7's reference semantics are applied to a third tool unchanged: every compared state at `P = P_r`, the tool's
  SYN-001 mapping, solver settings registered as inputs, the tolerance `a_k + 1e-6 |v|`, a mechanical classification
  before the `verdict` agent's verdict, positive controls that must classify `DISAGREE`, and a gate that never runs a
  tool;
- the blueprint names BioSTEAM as "useful for overlapping conceptual/assessment cases" beside the principal references
  DWSIM and IDAES (`docs/blueprint-v3.1.md:531`, D19 row `:45`). A third reference is consistent with it. ChemSep, the
  blueprint's optional column reference, is not used here (§15 Q-S09-2).

S03 §18.10 Q-A2-4 expected "a new package with its own ADR". §16 F-1 records why none is needed, and how to add one if
the reviewer or Frank disagrees.

**Lane.** Design leads, build follows. Build-lane chunks run as subagents in worktrees, and the design lane reviews them
before the merge (CLAUDE.md).

**What it establishes:** §1–§13. **What it does not establish:** §14. Read §14 before citing anything here.

## 1. The brief's questions, decided

| Question (brief §6) | Decision | Where |
| --- | --- | --- |
| 1. Levels | L1: the native `MultiStageEquilibrium` with native stage specifications whose definitions equal S03 §5.1 row 9. **L2(c), new:** the same native column, with one registered specification (S02 §2.1 or S06 §2, verbatim) met by a registered one-dimensional outer loop that adjusts the native specification of the same end. Admissible under conditions C1–C6. L2(a) adds nothing L1 lacks for BioSTEAM; L2(b) and L3 are not admissible | §2.2 |
| 2. Property method | Supplying SYN-001's pure-component closed forms through BioSTEAM's documented property hooks is T06's mapping principle applied to a third tool, not user-written thermodynamics. The definition is registered, imported from T06's pinned constants, readback-checked per run, and keeps the tool's default enthalpy datum. The spike's `T_ref` subclass is not registered | §4 |
| 3. Ladder and checks | Four rungs, the tool's documented default algorithm chain run one algorithm per rung, all four run at every attempted level. `early_termination=False`, tolerance 1e-10, 500 iterations, two passes with re-specification. Convergence is the harness's: per-stage component balance, per-stage equilibrium, the iteration cap and exceptions (rule 2); specification read-back and total-condenser vapour (rule 2c); S03's specification thresholds, a rerun at 1e-9 and path dependence across rungs (rule 2d) | §5, §6 |
| 4. Blindness and work orders | The spike's settings are not registered as such. The ladder is derived from the tool's documentation and source and from residual checks on non-registered probe columns. The qualification is run by a fresh build-lane agent whose brief carries no tool, ours or twin value, from a harness written from this document. Four work orders | §9, §12 |
| 5. Controls | PC-LB: RC1 with BioSTEAM's `Hvap_i = L_i + P_r v_i`. Its tool model is PC-LI's, so its discrimination is the registered 243.292 tolerances. PC-P runs too | §7 |

## 2. The tool, its levels and the "where available" rule

### 2.1 The tool

**BioSTEAM 2.54.0** with thermosteam 0.54.2, thermo 0.6.1, chemicals 1.5.2, flexsolve 0.5.10, numba 0.68.0, numpy
2.5.4 and scipy 1.18.1, on CPython 3.13.5 (full closure: `docs/derivations/scripts/s09_spike/freeze.txt`). It is built
by `scripts/build-reference-envs.sh biosteam` into `.venv-biosteam/` and fingerprinted in
`docs/reference-environments.md` §9 (WO-S09-1).

- **Licence.** Both `LICENSE.txt` files state the University of Illinois/NCSA Open Source License, an OSI-approved
  permissive licence. The wheel METADATA says "MIT", which is inconsistent; MIT applied only to versions 0.1–0.9. The
  `LICENSE.txt` text governs. Nothing of BioSTEAM is redistributed: the environment is git-ignored.
- **Independence.** No IDAES, Pyomo, DWSIM or Ipopt code is in the stack (one commented-out `cyipopt` import). BioSTEAM
  shares no code, data file or property package with this project. It shares SYN-001's constants, entered as user
  input (§4), and the column semantics of S03 §5, matched by construction. Its closure contains numpy and scipy (this
  project pins other versions), and `thermo`, `chemicals` and CoolProp 8.0.0 (this project's optional S07 provider pins
  the same CoolProp). None of these three is used by the registered definition, which has no database method (§4.3).
- **Disclosure (D19).** *A comparison verifies a second, independent implementation of the same equations. It is
  numerical verification, not empirical validation* (S03 §2.1, verbatim). The twin is the third corner and is not
  independent.

### 2.2 What "expressible" means for BioSTEAM

The matched model of a case is S03 §2.2's: S02 §2's rows (S06 §2's inverse row for RC5–RC7) on SYN-001 after the tool's
mapping, at the case's registered inputs. BioSTEAM expresses a case if it builds that model from its own unit and
property package at one of these levels.

| Level | What is allowed for BioSTEAM |
| --- | --- |
| L1 | `biosteam.MultiStageEquilibrium` with its native stage specifications (`Reflux`, `Boilup`, `Duty`, `Flow`, `Temperature`) and its native `bottom_side_draws`, each with S03 §5.1 row 9's definition (or §17.4's) after an exact conversion that is recorded |
| L2(a) | S03's form (a tool variable fixed at a value S02 implies exactly). **No BioSTEAM realization adds anything L1 lacks**: an intermediate stage's duty of 0 is the native default specification, a native partial condenser has no liquid distillate, and every pressure is an input. L2(a) is recorded as inapplicable and never attempted |
| **L2(c)** | **New, sequential-modular tools only.** L1's column with exactly one registered specification that has no native option realized by §5.4's outer loop: the specification equation is written verbatim from S02 §2.1 or S06 §2 on the tool's own record, and the loop adjusts the native specification of the end that carries the registered one (condenser: `Reflux` on stage 0; reboiler: `Boilup` on stage N−1) |
| L2(b) | Not admissible: S03 restricts it to an equation-oriented tool |
| L3 | Not admissible: S03 §2.2's reason for DWSIM applies. A cascade of `StageEquilibrium` units joined by system-level recycles would be the harness author's column, converged by tear iteration |

**Never admissible, at any level** (S03 §2.2, with the property-method item extended to name this tool's definition):
- user-written thermodynamics, phase equilibrium, balance or enthalpy equations;
- a property method other than T06's SYN-001 definitions **or S09 §4.2's BioSTEAM definition**;
- any value taken from this project's results, the twin, `s03_reference.json` or a comparison output;
- a change to a registered input (pressure, stage count, feed stage, inlet state, specification value).

A case that needs one of these is `NOT_COMPARABLE(capability: <what>)`. **A different model is never substituted.**

**Why L2(c) is admissible.** S03's L2(b) admits a specification equation, written verbatim from S02 §2.1 or S06 §2, in
place of a native specification. It was restricted to an equation-oriented tool because a sequential-modular tool has
nowhere to put an extra equation except an outer iteration. L2(c) is that outer iteration, admitted under six
conditions, each checked per record:
- **C1 (the model is the tool's).** Every evaluation of the loop is a complete native solve under §5.2's path. Every
  MESH equation of every stage is BioSTEAM's. The harness adds exactly one equation, the registered specification, and
  adjusts exactly one native specification value.
- **C2 (same end, one specification).** The adjusted native specification belongs to the end whose slot the registered
  specification occupies (S02/S06's slots). At most one specification per case is realized this way. Every S03 case
  has at most one specification without a native option, so no case needs two.
- **C3 (registered loop).** Starts, expansion, solver, termination and failure modes are fixed in §5.4, the same for
  every case and kind. Nothing is tuned per case.
- **C4 (accuracy, per record).** The final state's specification residual, computed from the tool's own record by S03
  §5.1 row 9 and §17.4, must pass rule 2d's per-kind threshold (S03 §17.4). The loop terminates at one tenth of it
  (generator claim C7). S03 §17.4's response claim then bounds the specification error's effect on every registered
  quantity by 0.005 tolerance (one tenth of the 0.05 claimed at the threshold).
- **C5 (the answer cannot be steered by the loop).** The registered quantities at a state where the specification holds
  are determined by the specification (C4). A loop that found another root would classify `DISAGREE`, never `AGREE`
  (S03 §7.1's principle: an inaccurate reference costs a false `DISAGREE`, never a false `AGREE`). The loop's starts
  and bracket can change availability only.
- **C6 (disclosure).** Every evaluation (x, g(x), the inner rule values) is recorded. L2(c) is attempted only where the
  L1 inspection recorded the registered specification as structurally inexpressible (Q-X6).

*What L2(c) is not.* It is not DWSIM's rejected L3: the column structure, every stage and every connection is the
tool's native unit, and only one scalar is iterated, against a specification whose residual is checked per record.

### 2.3 The pre-registered "where available" rule for BioSTEAM

1. **Order.** For each case: L1, then L2(c). At each level, first record the structural inspection (§2.4), read from the
   built model before it is solved. Then, if it is expressible, run **all four rungs** of §5.3 (each through §5.4's
   loop at L2(c)). The level passes if some rung passes rules 2–2d and §6.4's path dependence does not fire. The
   selected attempt is the first passing rung in §5.3's order. The search stops at the first level that passes.
2. **Blind.** The tool scripts read `docs/derivations/scripts/s03_cases.json`, `docs/derivations/scripts/s09_cases.json`
   and T06's pinned SYN-001 constants (`spikes/references/t06_fixtures.py`), and nothing else of this project (§9, A03).
3. **Committed before comparison.** The qualification records are committed before the S09 classifier first runs.
   The qualification commit must be an ancestor of the comparison commit (A16). After that, no input, level, setting
   or mapping changes except by an amendment of this document.
4. **Available.** BioSTEAM is available for a case if and only if step 1 found a level. Otherwise the record is
   `NOT_COMPARABLE(capability: <reason>)`, with every attempt, and the reason names a missing feature, a convergence
   failure or an accuracy failure as such (S03 verdict F-3).

### 2.4 Structural questions (per case and level, before the run)

S03 §2.4's Q-X1–Q-X9, answered from BioSTEAM's objects, plus Q-X10.

| Id | BioSTEAM answer recorded | Record field |
| --- | --- | --- |
| Q-X1 | `thermo` classes and each chemical's active methods; §4.3's readback values | `property_package` |
| Q-X2 | `len(column.stages)` and the map: our j → BioSTEAM stage j − 1 (stage 0 is the top) | `stage_map` |
| Q-X3 | `feed_stages`: each inlet enters whole at stage `stage − 1` | `feed_stages` |
| Q-X4 | partial condenser: stage 0 is an equilibrium stage whose vapour is the top product, with no side draw; total: stage 0 specified `('Reflux', inf)` with `bottom_side_draws={0: 1/(1+RR*)}`; none: stage 0 carries no specification and receives the `top` inlet | `condenser_realization` |
| Q-X5 | kettle: stage N − 1 carries the reboiler end's specification; none: stage N − 1 carries none and receives the `bottom` inlet | `reboiler_realization` |
| Q-X6 | per end: the native specification name and stored value with its conversion (§5.6); or "no native option with S03 §5.1 row 9's definition" and, at L2(c), the adjusted specification and the registered equation | `specifications` |
| Q-X7 | each stage's `P` read back from the built model | `pressures` |
| Q-X8 | every other stage: `specified_variable == 'Q'` with `Q == 0`, no side draw, no reaction, no `partition_data` | `intermediate_stages` |
| Q-X9 | BioSTEAM's own initializer; no initial point from this project | `initialization` |
| Q-X10 | `MultiStageEquilibrium.default_algorithms` and `default_methods`, read at run time, equal §5.3's rungs and methods | `ladder_source` |

### 2.5 Expected realizations (to be confirmed or refuted by inspection; none is assumed)

| Cases | Expected level | Expected realization (BioSTEAM stage indices) |
| --- | --- | --- |
| RC1, RC1-RR, RC1-BR, RC1-z, PC-P, PC-LB | L1 | stage 0 `('Reflux', RR*)`, stage 6 `('Boilup', BR*)` |
| RC2, RC2-RR, RC2-B, RC2-z | L1 | stage 0 `('Reflux', inf)` and `bottom_side_draws={0: 1/(1+RR*)}`; stage 6 `('Flow', B*/F)`, F = 1 mol/s |
| RC3, RC3-Q, RC3-z | L1 | the `top` inlet on stage 0, which carries no specification; stage 4 `('Duty', 3.6 Q*)` in kJ/h |
| RC4, RC4-D, RC4-z | L2(c) | stage 0 `Reflux` adjusted until `V_1 = D*`; no other specification |
| RC5 | L2(c) | stage 0 `Reflux` adjusted until the purity of A in `v_1` is 0.85; stage 6 `('Boilup', 1.5)` |
| RC6 | L2(c) | the total condenser at RR 1.5; stage 6 `Boilup` adjusted until the recovery of C in `l_7` is 0.99 |
| RC7 | L2(c) | stage 0 `('Reflux', 2)`; stage 6 `Boilup` adjusted until the temperature of our stage 6 (index 5) is 368 K. Stage 5 stays adiabatic |

BioSTEAM's `Temperature` specification replaces that stage's energy balance. On RC7's stage 6 it would make the stage
carry the duty and leave the reboiler adiabatic, which is not RC7's model. That native realization is structurally
inexpressible (Q-X6), and L2(c) is the admissible one.

## 3. Registered pairs

BioSTEAM runs **20 pairs**: S03's seventeen compared cases (RC1–RC7 and the ten perturbed cases), PC-P, and PC-LB (§7).
`s09_cases.json → pairs`.
- (PC-L, BioSTEAM) and (PC-LI, BioSTEAM) are `not_applicable`: they are DWSIM's and IDAES's mapping inputs. No record is
  written. They are registered absences outside every count.
- **Our side** is S03's committed `benchmarks/s03/references/results/ours-<case>.json`, unchanged. PC-LB's our side is
  RC1's record (alias `{"PC-LB": "RC1"}`). No new solve on our side.
- *Why every S03 case, not only the gaps.* The gap cases (the RC3 and RC4 families, RC7, RC1-BR) decide X31. The
  others are where IDAES and DWSIM already agree, so a BioSTEAM `DISAGREE` there would expose a BioSTEAM harness
  defect before it could pass unnoticed on a gap case. Each run costs seconds, and the rule is uniform (S03 §2.3).

## 4. SYN-001 in BioSTEAM (the property-method ruling)

### 4.1 Ruling

**Admissible.** Supplying SYN-001's closed forms through `Chemical.blank` and the `add_method` hooks is the BioSTEAM
realization of T06's SYN-001 definitions. It is neither "user-written thermodynamics" nor "a property method other
than T06's SYN-001 definitions" in S03 §2.2's sense.

1. *T06 is the precedent.* IDAES takes SYN-001's Psat as a user-written `pressure_sat_comp` class, and DWSIM takes it as
   a user compound with equation forms and constants (`docs/reference-environments.md` §5.0). SYN-001 is synthetic, so
   every tool can only take it as user input. T06 qualified those mappings (16 of 16 pairs `AGREE`).
2. *What stays the tool's.* The registered hooks enter pure-component data only: a vapour-pressure correlation, a
   constant latent heat, constant heat capacities, a liquid volume, a boiling point and a molar mass. Everything §2.2
   forbids the harness to write stays BioSTEAM's: the K-value form `γ Psat PCF / (φ P)` with ideal activity, ideal
   fugacity and mock Poynting objects, the mixture enthalpy, the flash, and every stage's MESH equations.
3. *It is checked per run.* §4.3's readback is part of Q-X1, and a failure is rule 2c.
4. *One definition cannot drift.* The constants are imported from `spikes/references/t06_fixtures.py`, pinned at S03
   §17.6's SHA-256 (generator claim C4b), as S03 §5.1 row 1 requires of the other tools.

**Equation differences**, as `docs/reference-environments.md` §5.0 records them for the other tools:
- K is `Psat/P`: no Poynting factor.
- `h^L` has no `v_i (P − P_r)` term: a liquid stream's enthalpy is the same at P_r and 1.5 P_r (`s09_design/datum_probe.log`).
- At `P = P_r` both differences vanish exactly (S03 §3), and every S03 comparison state is at `P_r`.
- PC-P (1.5e5 Pa) carries both differences (§7).

### 4.2 The registered definition (normative; `s09_cases.json → tool_settings.BioSTEAM.mapping`)

| Item | Registered |
| --- | --- |
| Constants | `T_BOIL`, `L_VAP`, `CP`, `V_LIQ`, `MW`, `P_REF`, `R_GAS` from `spikes/references/t06_fixtures.py` |
| Chemical | `thermosteam.Chemical.blank(ID, phase_ref='l', MW=1000*MW, Tb=T_BOIL[ID])` |
| Psat | `Psat.add_method(f=lambda t: P_REF*exp((L/R_GAS)*(1/T_b − 1/t)), Tmin=200.0, Tmax=600.0)` |
| Hvap | `Hvap.add_method(f=lambda t: L, Tmin=200.0, Tmax=600.0)`, the constant `L_VAP[ID]`; PC-LB: §7's value |
| Heat capacity | `Cn.l.add_method(CP)`, `Cn.g.add_method(CP)` |
| Liquid volume | `V.l.add_method(V_LIQ)` (it enters no compared quantity at `P_r`) |
| Finish | `reset_free_energies()`; `Chemicals([A, B, C]).compile(skip_checks=True)` |
| Thermo | `IdealThermo(chemicals, mixture=IdealMixture.from_chemicals(chemicals), skip_checks=True)`. Without the explicit mixture, `IdealThermo(chemicals)` raises `AttributeError` in thermosteam 0.54.2 (a tool defect, recorded, not patched) |
| Datum | **The tool's default**, `Chemical.T_ref = 298.15 K`. Then `h^L_i = c_p (T − 298.15)` and `h^V_i = h^L_i + L_i`, which differ from SYN-001's by `c_p (T_r − 298.15) = 185 J/mol`, the same constant for every component and phase (claim C4). It cancels in every balance; stream enthalpies are not compared (S03 §4) |
| Basis | molar specifications: `specifications_by_weight=False` |

**Not registered: the spike's `T_ref` subclass.** The spike overrode thermosteam's read-only class attribute `T_ref`
to 300 K with a two-line subclass. The default datum gives the same balances without overriding a tool attribute its
authors made read-only, which removes the risk that another code path reads the module's 298.15 K. DWSIM's 298.15 K
datum is the precedent (`docs/reference-environments.md` §5.0).

### 4.3 Readback self-check (part of Q-X1; a failure is rule 2c `semantics: property_mapping(<item>)`)

Run in each case's process, before any solve, on the thermo object that case uses:

| Check | Expected | Threshold | Measured floor (`s09_design/datum_probe.log`, spike `check_pure.log`) |
| --- | --- | --- | --- |
| `Psat_i(T)` at T = 310, 347, 385, 430 K | `s09_cases.json → readback.Psat_Pa` (25 digits, claim C5) | 1e-14 relative | 0.0 |
| `h^V_i(T) − h^L_i(T) − Hvap_i` at the same T | 0 | 1e-12 relative to `Hvap_i` | 3.6e-12 J/mol on 30 000 (1.2e-16) |
| `[h^L_i(T₂) − h^L_i(T₁)] − c_p (T₂ − T₁)`, consecutive T | 0 | 1e-9 J/mol | 0.0 |
| `h^L_i(T) − c_p (T − 300)` | 185 J/mol for every i | 1e-9 J/mol | 185.000000000002 |
| liquid stream `H(T, 1.5 P_r) − H(T, P_r)` | 0 | exact | 0.0 |
| active methods of `Psat` and `Hvap` | exactly `{'USER_METHOD'}` | exact | as expected |
| `thermo.Gamma`, `Phi`, `PCF`, `mixture`, `include_excess_energies` | `IdealActivityCoefficients`, `IdealFugacityCoefficients`, `MockPoyntingCorrectionFactors`, `IdealMixture`, `False` | exact | as expected |

*Above the floor, below an error worth catching.* 1e-14 relative on Psat is about 45 ulps (a different `exp` would
pass). An error in L_i, T_b or the datum constants is at least a part in 10⁵ (L is entered to five digits), so 1e-12
relative on the latent heat is ten million times smaller than any entry error.

## 5. The registered solve path, ladder and outer loop (`s09_cases.json → tool_settings.BioSTEAM`)

### 5.1 Common settings

| Setting | Value | Reason (tool source, `biosteam/units/stage.py` in 2.54.0) |
| --- | --- | --- |
| `early_termination` | `False` | With `True`, the solver raises "residual error is not decreasing sufficiently" (`:2792`). `_run` catches it and returns the best point without raising (`:2741–2752`). A slow convergence would then end in a silent stop |
| `tolerance`, `relative_tolerance` | `1e-10` | the step tolerances of flexsolve's iteration. S03's DWSIM ladder starts at 1e-10. The accuracy is checked by rules 2 and 2d, not by this number |
| `maxiter` | 500 | default 100. Iterations are not compared. The measured passes need at most 107 (`s09_design/floor_probe.log`) |
| `max_attempts` | 1 | default 2. With one algorithm per rung, a second attempt only resumes after a swallowed failure. With one attempt, any swallowed failure ends the run, and the harness sees the state it left |
| `use_cache` | `True`, at construction | so that pass 2 (§5.2) resumes from the tool's own point. It does not affect pass 1: the first-pass state with and without it agreed to 12 digits in the spike (`rc4_sweep.log` against `rc4_respec.log`, pass 0) |
| `specifications_by_weight` | `False` | molar specifications (S03 §5.1 row 9) |
| `phases` | `('g', 'l')` | VLE |
| everything else | the tool's defaults (`optimize_result=False`, `damping=0`, no homotopy without reactions, `vle_decomposition` default), recorded per run | — |

### 5.2 The solve path: two passes (every run, every case, every rung)

- **P1.** Build the inlets and the column. Inlets: `Stream(None, A=…, B=…, C=…, T, P, phase, units='kmol/hr')` from
  `s03_cases.json`. Column: `MultiStageEquilibrium(None, ins=inlets, outs=[…], N_stages=N, feed_stages=[s−1, …],
  P=[P]*N, phases=('g','l'), stage_specifications={…}, [bottom_side_draws=…], maxiter=500, max_attempts=1,
  use_cache=True)`. Then set `algorithms = (rung,)`, `methods = (method,)`, `early_termination = False` and both
  tolerances.
- **P2.** `simulate()`: pass 1.
- **P3.** Re-store every registered native specification value **through the stage's attribute setter**, exactly as the
  constructor's `specify_variables` stored it (`:914–967`):
  - `Reflux` r: `stage.B = 1/r` (`inf` for r = 0, and 0 for r = inf);
  - `Boilup` b: `stage.B = b`;
  - `Duty` q: `stage.Q = 3.6 q` (kJ/h);
  - `Flow` f: `stage.F = f`;
  - `Temperature` t: `stage.T = t`.
- **P4.** `simulate()`: pass 2. **The record is pass 2.** Pass 1 is recorded but never selected.

**Why two passes.** With exactly one stage specification, the tool's initializer (`:3273–3298`) overwrites the
specified stage's stored B with the bulk flash's V/L. The spike saw this on RC4. The non-registered probe A1
(`s09_design/respec_probe.log`) shows it at Reflux 1: after pass 1, B = 0.01538 (L₁/V₁ = 65.0).
- With two specifications the overwrite does not occur, and pass 2 resumes from a converged point.
- Applying P3–P4 to every run keeps the path uniform.

**Why the attribute setter and not `specify_variables`.** The probe measured both:
- `specify_variables(Reflux=1, P=P_r, wt=False)` clears `partition.T`. The cached point is discarded, the initializer
  runs again, and pass 2 ends at B = 0.01538 again, with all of rule 2's residuals passing (sequential modular:
  equilibrium 3.2e-13, stage balance 2.0e-11 mol/s, adiabatic duty 4.6e-8 W). That is a converged state of the wrong
  specification, which only rule 2c's read-back and definition checks catch (§6.3).
- Called without `P=…`, `specify_variables` also resets the stage pressure to 101325 Pa (`:956–962`).
- The setter route ends at B = 1 and L₁/V₁ = 1 in both phenomena and sequential modular, which agree on `V_1` to 1.1e-11
  mol/s.

### 5.3 The ladder (closed)

| Rung | `algorithms` | `methods` |
| --- | --- | --- |
| R1 | `('inside out',)` | `('fixed-point',)` |
| R2 | `('phenomena',)` | `('fixed-point',)` |
| R3 | `('simultaneous correction',)` | `('hybr',)` |
| R4 | `('sequential modular',)` | `('fixed-point',)` |

- **Source.** This is `MultiStageEquilibrium.default_algorithms` and `default_methods` (`:2185–2200`): the tool's own
  default chain, run one algorithm per rung, in the tool's own order (Q-X10 reads them at run time).
- **Every rung runs** at every attempted level, including after a rung has passed, so that §6.4's path dependence is
  checked.
- **Selection.** The first rung in R1…R4 order that passes rules 2–2d, at a level where path dependence does not fire.
- **Closure.** No other algorithm (`phenomena modular`), method (`wegstein`), tolerance, damping, homotopy or initializer
  variant is registered. A case with no passing rung at any level is `NOT_COMPARABLE(capability: …)`, final for S09.
  A **harness defect** (a record showing a path other than §5.2's) is corrected and the run repeated, and every run is
  disclosed (S03 §18.1).
- **What the probes showed** (non-registered columns, `s09_design/floor_probe.log`). These are facts about the tool,
  not expectations for the registered cases:
  - R2 and R4 passed all five probe columns;
  - R1 passed three, and returned **without an exception** a state that fails rule 2 on S1 (stage balance 0.315 mol/s,
    adiabatic duty 1160 W) and A1 (0.22 mol/s);
  - R3 raised on three ("Failed to extrapolate vapor pressure … at T = −6.06e-6 K"). On D1 and on D1T's first
    evaluation it returned **without an exception** states whose stage balances pass but whose equilibrium residuals
    are 0.25 and 0.36.

  Where two or more rungs passed, they agreed to ≤ 8.6e-5 tolerance.

### 5.4 The outer loop of L2(c)

For the one registered specification s* without a native option (kind k, end e):
- **Adjusted variable** x: the native specification of end e. Condenser: `Reflux` on stage 0. Reboiler: `Boilup` on
  stage N − 1. The other end keeps its native specification.
- **Residual.** g(x) = (s(x) − s*)/|s*| for a relative kind (ratio, rate, duty, temperature), and s(x) − s* for an
  absolute kind (purity, recovery). s(x) is computed from the tool's own record at x by S03 §5.1 row 9 and §17.4: the
  same function rules 2c and 2d use.
- **Evaluation.** Each g(x) is a **fresh build** and the full path P1–P4 at the rung's settings, with x as the adjusted
  specification. Its state must pass rule 2 (§6.2) and rule 2c's pressure and read-back checks, or the attempt fails
  with `inner_failed(x, <check>)`.
- **Starts and bracket.**
  - Evaluate g(1) and g(2). If |g| ≤ ytol at either, that point is the root.
  - If g(1)·g(2) < 0, the bracket is [1, 2].
  - Otherwise expand by factors of 2: up (4, 8, 16, 32) if |g(2)| ≤ |g(1)|, else down (0.5, 0.25, 0.125, 0.0625). The
    first sign change against the previous point gives the bracket.
  - No sign change in four steps: the attempt fails with `no_bracket([1/16, 32])`.
- **Solver.** BioSTEAM's own process-specification solver, `flexsolve.IQ_interpolation(g, a, b, g(a), g(b), None, 0.0,
  ytol, (), 50, False, True, True)`. These are the positional arguments `x, xtol, ytol, args, maxiter, checkroot,
  checkiter, checkbounds`, as `BoundedNumericalSpecification` passes them. An exception it raises (iteration limit,
  bounds) fails the attempt with its message.
- **Termination.** ytol = rule 2d's threshold for kind k, divided by 10 (claim C7): 1e-9 for a ratio, rate, duty or
  purity, and 1e-10 for a recovery or temperature, on the basis of S03 §17.4.
- **The record.** One final fresh evaluation at the returned x. It is deterministic (§5.7), so it reproduces the last
  evaluation. |g| ≤ ytol, or the attempt fails with `final_residual`.
- **Recorded.** Every evaluation: x, g(x), the inner rule 2 values, both passes' iteration counts.

*Starts.* 1 and 2 are the same for every case and kind: unity and twice it. They are not taken from any value of this
project (the spike's (1.0, 1.5) are not registered, §9.1). By C5 they can change only availability.

*Floor* (`s09_design/floor_probe.log`, non-registered):
- A1, a rate specification with its bracket found by expanding down: 8 evaluations, final |g| = 6.7e-12 against ytol
  1e-9.
- D1T, a temperature specification with its bracket found by expanding up: 9 evaluations, final |g| ≤ 4.7e-16 against
  ytol 1e-10.

### 5.5 The accuracy rerun (rule 2d; `floor_rerun`)

The selected rung is repeated from a fresh build with `tolerance = relative_tolerance = 1e-9`. At L2(c) its ytol is also
×10, which equals rule 2d's threshold. Everything else is unchanged. It must pass rules 2 and 2c, and it may move no
registered quantity by more than 0.1 tolerance. Measured on the probes: ≤ 4.9e-4 tolerance.

### 5.6 Units, duties and specification values

- BioSTEAM's flows are kmol/h and its enthalpies kJ/h. 1 mol/s = 3.6 kmol/h and 1 W = 3.6 kJ/h exactly (claim C8).
- **Stage duty** (positive into the stage, ADR 0001 D4.1) = (Σ outlet H − Σ inlet H)/3.6, over the stage's own streams in
  the tool's own enthalpy. `StageEquilibrium.Q` returns only a specified value, so this is the duty of every stage,
  and it is recorded with its definition. For a duty-specified stage the record carries both the stored and the
  computed duty.
- **Specification conversions** (Q-X6; exact, recorded):
  - a partial condenser's RR → `('Reflux', RR)`;
  - a total condenser's RR → `bottom_side_draws={0: 1/(1+RR)}` with `('Reflux', inf)`;
  - BR → `('Boilup', BR)`;
  - B → `('Flow', B/F)`, with F the sum of the registered inlet flows;
  - Q → `('Duty', 3.6 Q)`.
- **Registered quantities** are read per S03 §4 in our stage numbering: `T[j]` = stage j − 1's T; `L[j]` and `V[j]` =
  the liquid and vapour leaving stage j − 1's equilibrium partition; for a total condenser `reflux` = stage 0's liquid
  less the side draw, and `top[c]` = the side draw's flows.

### 5.7 One process per case; determinism

- Each case runs in its own Python process, with the tool's global thermo set once for that case (SYN-001, or PC-LB's
  variant), so that no state carries between cases.
- Within a case, every run is a fresh build.
- The spike found repeat runs bit-identical (`run2.log` and `run3.log` identical). A17 makes that executable: the whole
  qualification is run twice, and the records are compared.

## 6. Harness checks that replace the tool's convergence report

### 6.1 Why the tool's report is not used

- `_run` catches every exception its iteration raises, keeps the best point, and returns without raising
  (`stage.py:2674–2755`).
- With `early_termination=False`, the residual it stores is the constant 1e6 (`:2779–2784`).
- So "no exception" is not convergence, and the tool offers no usable residual.

The probes show all three silent failure modes: a wrong state from R1, a non-equilibrium state from R3, and a converged
state of an overwritten specification. Each check below catches a measured case.

### 6.2 Rule 2 for BioSTEAM (converged): all of

| Id | Check, computed from the tool's own record | Threshold | Catches (measured) |
| --- | --- | --- | --- |
| B1 | neither pass raised | — | R3's negative-temperature extrapolation |
| B2 | neither pass's iteration counter `iter` reached `maxiter` | — | a stopped iteration |
| B3 | per stage and component: \|Σ in − Σ out\| | 3.1e-8 mol/s | R1 on S1 (0.315 mol/s) and A1 (0.22) |
| B4 | per two-phase stage and component: \|y_c − K_c x_c\|, with K_c = `chemicals[c].Psat(T)/P` at the stage's T and P from the tool's objects (a total condenser stage, with no vapour: \|Σ_c K_c x_c − 1\|) | 1e-8 | R3 on D1 (0.25), whose balances and duties pass |
| B5 | S03 rule 2: overall component closure, and overall energy closure in the tool's datum | 3.1e-8 mol/s; 1e-3 W | — |

- The adiabatic-stage duty check (S03 rule 2c, 1e-3 W) is the energy-balance convergence check for those stages. It stays
  in rule 2c, as S03 has it. It catches R1 on S1 (1160 W).
- A stage with an empty phase is recorded under `one_phase_stages`, and B4 skips it. Every twin stage is two-phase, with
  L, V > 1e-3 mol/s, which is ≥ 3000 tolerances. Such a record therefore cannot `AGREE`, and a wrong one costs at most a
  false `DISAGREE`.
- *Threshold of B4* (claim C6). At an equilibrium stage Σ K x = 1, so the largest K_c x_c is at least 1/3, and its
  temperature derivative is at least L_min/(3RT²). A residual of 1e-8 therefore bounds a temperature-only error by
  1.575e-6 K, which is 0.00387 tolerance at the hottest registered stage (397.37 K). This bounds one error mode. The full
  accuracy is rule 2d's job.

### 6.3 Rule 2c additions for BioSTEAM (semantics); S03's rule 2c applies unchanged

- **Specification read-back.** After pass 2, each specified stage's `specified_variable` and stored value equal the
  registered ones after §5.6's conversion, exactly in binary64. At L2(c) the adjusted one equals the final x. Failure:
  `semantics: specification_readback(<stage>, <stored>)`.
- **Total-condenser vapour.** Stage 0's vapour product carries ≤ 3.1e-8 mol/s. Failure:
  `semantics: total_condenser_vapour(<value>)`. This is S03's fixed-zero-liquid-distillate check, mirrored.
- **Property readback.** §4.3's checks. Failure: `semantics: property_mapping(<item>)`.

S03's checks, unchanged: stage count and map, inlet stages, pressures within 1e-3 Pa, intermediate duties within
1e-3 W (from §5.6's computed duty), and a specification computed by S03 §5.1 row 9 within 1e-4 relative.

### 6.4 Rule 2d for BioSTEAM (accuracy)

- S03 §17.4's specification residual per kind, unchanged: 1e-8 relative for a ratio, rate or duty; 1e-8 absolute on a
  purity; 1e-9 absolute on a recovery; 1e-9 relative on a temperature.
- The accuracy rerun (§5.5) must pass rules 2 and 2c and move no registered quantity by more than 0.1 tolerance.
- **Path dependence** (S03 §18.4's form): at the attempt's level, two rungs whose runs pass rules 2–2c and the
  specification residual differ on a registered quantity by more than 0.1 tolerance →
  `NOT_COMPARABLE(reference_accuracy: path_dependence(<ratio>))`. The tool script computes the ratio with the tool's own
  values in the tolerance. The classifier recomputes it with the twin's.

Rule 2d can only exclude, never pass (S03 §7.1).

### 6.5 Rules 0, 1, 3, 4 and the order

S03 §7.1's order applies: 0, 1, 2, 2c, 2d, 3, 4. Rule 2b is IDAES only.
- Rule 1's fingerprint is `docs/reference-environments.md` §9's.
- Rule 3 reads S03's committed `ours-<case>.json` and `s03_reference.json`.
- Rule 4 uses S03 §6's tolerance, evaluated unrounded from the twin's 25-digit values, with no per-case or per-tool
  factor.

### 6.6 Floors and margins (non-registered probes, `s09_design/floor_probe.log`; passing rungs)

| Check | Threshold | Floor at the registered 1e-10 | Floor at the rerun's 1e-9 | Margin (registered / rerun) |
| --- | --- | --- | --- | --- |
| B3 stage component balance | 3.1e-8 mol/s | 4.4e-11 | 4.2e-10 | 700× / 74× |
| B4 equilibrium | 1e-8 | 2.5e-11 | 1.4e-10 | 400× / 71× |
| adiabatic duty (2c) | 1e-3 W | 1.1e-6 W | 6.6e-6 W | 890× / 150× |
| overall energy (B5) | 1e-3 W | 1.4e-11 W | 8.1e-12 W | > 10⁷ |
| rerun movement (2d) | 0.1 tolerance | 4.9e-4 | — | 200× |
| path spread (2d) | 0.1 tolerance | 8.6e-5 | 9.6e-4 | 1160× / 100× |
| outer termination (C4) | ytol | 6.7e-12 (rate), 4.7e-16 (temperature) | — | ≥ 150× |

- *Below the smallest error worth catching.* Every threshold is a tenth of S03's allowance or less, except B4, which is
  bounded by claim C6.
- *Where it would be thin, it says so.* The qualification reports per selected record its largest ratio of residual
  to threshold. A ratio above 0.1 is listed in `comparison.json` as "thin margin", reported and not classified.

## 7. Positive controls for BioSTEAM

| Id | Definition | Our side | Expected | Discrimination |
| --- | --- | --- | --- | --- |
| **PC-LB** | RC1's inputs, with BioSTEAM's `Hvap_i = L_i + P_r v_i` = 25010, 30010, 35010 J/mol in place of L_i (`s09_cases.json → controls.PC-LB`), so `h^V − h^L` is larger by `P_r v_i` = 10 J/mol | RC1's record | `DISAGREE` | 243.292 tolerances (`Q_reboiler`), 22/29 quantities over one tolerance. Marginal on temperatures (`T[4]`–`T[7]`, 0.585–0.782 tolerance), so duties and flows carry it |
| PC-P | S03's PC-P inputs (RC1 at 1.5e5 Pa) | S03's `ours-PC-P.json` | `DISAGREE` | S03's 176.357 is for K without the Poynting factor alone. BioSTEAM also lacks `v_i (P − P_r)` in `h^L` (§4.1), so its tool model is not S03's |
| (PC-L, BioSTEAM), (PC-LI, BioSTEAM) | — | — | `not_applicable` | — |

**PC-LB's tool model is PC-LI's** (claims C3 and C4). At P_r both have `K = Psat/P` and `h^V − h^L = L_i + P_r v_i` at
every T, and their liquid enthalpies differ by the same 185 J/mol for every component. So the tool-model twin is
`s03_reference.json → controls.PC-LI.tool_model`, and the reported tool-model distance (S03 §7.3) for PC-LB is computed
against it. *It is the natural mistake.* Entering DWSIM's mapped latent heat (S03 §5.1 row 1) as BioSTEAM's `Hvap` is
the error a harness author working on both tools would make. Its size is fixed by SYN-001's constants. It is inherited
from PC-L and PC-LI, both registered before any BioSTEAM run, and is not chosen by where BioSTEAM converges.

**PC-P's tool-model distance** is reported as `not_applicable(tool_model_differs)`. Its classification needs only our
side, and that is unchanged (§15 Q-S09-4).

**The control rule is S03 §17.3**, with §19.4's reading.
- BioSTEAM's controls are PC-LB and PC-P.
- BioSTEAM's pairs count if and only if at least one of them classifies `DISAGREE`.
- A control classified `AGREE` stops the comparison: this document or the harness is wrong.
- A control that is `NOT_COMPARABLE` propagates nothing by itself.

## 8. X31 and D19 with three tools (pre-registered)

### 8.1 The three-tool table

Each counted case (RC1–RC4) has three pairs:
- IDAES and DWSIM, read from S03's committed `comparison.json` at its pinned hash, never re-classified;
- BioSTEAM, from S09's comparison.

Each pair's class is S03 §17.5's: comparable, absent, unusable, access or ours. For each case, the first matching row
decides. Rows 1–4 are S03 §17.5's; rows 5–7 count AGREEs.

| # | Condition | Case outcome |
| --- | --- | --- |
| 1 | any pair is **ours** | not met: a column finding |
| 2 | any pair is a genuine `DISAGREE` | not met: a disagreement finding, until the design lane resolves it |
| 3 | any pair is **access** | blocked |
| 4 | any pair is **unusable** | not met: an available reference could not be shown to see a known difference |
| 5 | two or more pairs `AGREE`, the rest absent | two (or three) references |
| 6 | exactly one pair `AGREE`, the rest absent | one reference, with each absent tool and its reason quoted |
| 7 | every pair absent | no reference: not met |

**Reduction (claim C9).** On S03's two tools alone, this table gives S03's committed row for RC1–RC4 (5, 5, 6, 7) and
for RC5–RC7, and S03's clause "not met". The generalization changes nothing S03 decided.

### 8.2 The clause

The X31 reference clause, three-tool form, is:
- **met with two references** if every counted case is row 5;
- **met where available** if every counted case is row 5 or row 6, reported with the count of row 5 cases (target 4);
- **not met** if any case is row 1, 2, 4 or 7;
- **blocked** otherwise, when some case is row 3.

RC5–RC7 get the same per-case outcome, reported per inverse kind, outside the count.

### 8.3 Pre-registered outcomes (`s09_cases.json → x31_three_tool.pre_registered`, claim C10)

From S03's committed classes, which are RC1 and RC2 `AGREE`/`AGREE`, RC3 IDAES `AGREE` with DWSIM absent, and RC4
absent in both:

| Case | BioSTEAM `AGREE` | BioSTEAM absent | BioSTEAM `DISAGREE` / unusable / access / ours |
| --- | --- | --- | --- |
| RC1, RC2 | row 5, three references | row 5, two references | row 2 / 4 / 3 / 1 |
| RC3 | row 5, two references (BioSTEAM, IDAES) | row 6, one (IDAES) | row 2 / 4 / 3 / 1 |
| RC4 | row 6, one reference (BioSTEAM) | row 7, not met | row 2 / 4 / 3 / 1 |
| **Clause** | **met where available, 3 of 4** if every counted BioSTEAM pair `AGREE`s | **not met** whenever RC4 is absent | **not met** (rows 1, 2, 4) or **blocked** (row 3) |
| RC7 (temperature) | row 5, two references | row 6, one (IDAES) | as above |
| RC5, RC6 | row 5, three references | row 5, two references | as above |

- **"Met with two references" is unreachable.** RC4 can have at most one reference, BioSTEAM.
- **The best reachable outcome is "met where available, 3 of 4".**
- A genuine BioSTEAM `DISAGREE` on any case makes that case row 2, whatever IDAES and DWSIM say.
- If BioSTEAM's controls both fail to `DISAGREE`, every available BioSTEAM pair is unusable. Every counted case is then
  row 4, and the clause is not met until the harness is corrected. That is S03's rule, kept, and it is the signal that
  BioSTEAM's harness cannot see a known difference.

### 8.4 D19 (three-tool statement)

The `verdict` agent states, per registered state, how many independent implementations agree with our column: three,
two, one or none. It names each tool and its level (an L2(c) `AGREE` verifies our column against BioSTEAM's MESH
equations at the state where the harness's outer loop meets the specification). It carries the disclosure of §2.1 and
§9. It is numerical verification, not validation.

### 8.5 Relation to S03's verdict and to the ledger

- S03's verdict (`docs/reviews/S03-verdicts.md`) is S03's record and stands. Its X31 outcome ("not met, 2 of 4") is the
  two-tool outcome.
- S09's verdict records the three-tool outcome under this section's rule.
- The requirements ledger rows X31 and D19 (`docs/requirements.yaml`) cite S09's verdict as the later evidence, filled
  by the build lane from that document. Status moves only as the verdict and the release gate allow.
- Whether a release accepts "met where available" is outside S09.

## 9. Blindness and the spike (the ruling)

### 9.1 Exposure, stated

- **The spike** (2026-10-25, design-time, scripts and logs in `docs/derivations/scripts/s09_spike/`) chose its solver
  settings from the tool's own residuals (`rc3_sweep.py`). By its own account it then compared RC1, RC3 and RC4
  informally with this project's committed S03 results (`compare_ours.py`, which read `ours-*.json`). This document
  does not repeat those numbers. They are in the brief §4, which the qualification agent must not read (§9.2).
- `rc4_sweep.py` and `rc4_respec.py` ran RC4 at the **twin's reflux ratio**, 1.23419018 (S03 §3.1), as their docstrings
  say. The re-specification workaround was found at that value.
- `rc4_blind.py`'s secant starts (1.0, 1.5) bracket that value. They were chosen by an author who knew it.
- **The specifier** read the brief, including §4's summary of that comparison, and S03's twin sanity values, as every
  S03 author did. The specifier ran no S03 case and made no comparison. The measurements here (`s09_design/`) are on
  non-registered columns and read only the tool's own residuals.

### 9.2 Ruling (R-747)

1. **The spike's settings are not registered as such.**
   - The ladder (§5.3) is the tool's documented default chain, one algorithm per rung, all run.
   - The settings (§5.1) are justified from the tool's source.
   - The re-specification (§5.2) is justified from the tool's source and a non-registered probe.
   - The outer loop's starts (§5.4) are generic.
   - That the spike's working setting (phenomena, fixed-point) is one of the rungs follows from the tool's
     documentation, not from the spike.
2. **The qualification is run by a fresh build-lane agent** (WO-S09-2). Its brief contains no tool value for an S03
   case, no value of ours and no twin value. It is told not to open `docs/derivations/scripts/s09_spike/`,
   `docs/briefs/S09-third-reference-tool.md` or anything under `benchmarks/s03/references/results/` and
   `benchmarks/s09/`. It reads this document, `s09_cases.json`, `s03_cases.json` and the tool's documentation and
   source.
3. **The harness is written from this document**, not adapted from the spike's scripts. Those scripts embed
   exploratory choices, the twin's reflux ratio and a reader of our results.
4. **Executable (A03).**
   - Scanned set: the S09 tool scripts and their in-repo imports, transitively.
   - Forbidden strings: S03's seven, plus `s09_spike`, `compare_ours` and `1.2341901`.
   - Only `t06_fixtures.py` is exempt, pinned by SHA-256, and only for `twin` and `comparison`.
   - Input files: `s03_cases.json` and `s09_cases.json` only.
   - Scanned at HEAD and at the qualification commit.
5. **Disclosed.** The verdict quotes §9.1 under D19's independence disclosure.

### 9.3 Why this suffices

- The selection is mechanical: every rung runs, the first passing rung is selected, and two passing rungs that differ by
  more than 0.1 tolerance make the case `NOT_COMPARABLE` (§6.4). So no choice among rungs can steer the answer.
- At L2(c) the answer is fixed by the registered specification (C4, C5), so the loop's starts cannot steer it.
- What an exposed author could still influence is availability, through the harness's mechanics. Point 2 removes the
  exposed author from the run, and point 3 removes the spike's code from it.
- Blindness stays procedural, as in S03 §2.1: the agent knows this project. It is enforced by what the scripts may read,
  not by an independent author.

**Rejected.**
- *Register the spike's settings and let any agent run the qualification.* The settings are defensible, but the
  exposure is real: the twin's reflux ratio was used, and the starts bracket it. It costs one fresh agent to remove it.
- *Discard the spike's facts.* The tool defects it found (the initializer overwrite, inside-out's silent failure, the
  `IdealThermo` defect) are facts about the tool, not about agreement. Each has been re-established here from the tool's
  source and from non-registered probes, without the S03 cases.

## 10. Evidence layout and the gate

```
spikes/references/biosteam-requirements.{in,lock}   hash-locked closure (WO-S09-1)
spikes/references/s09_biosteam_syn001.py            §4.2's definition and §4.3's readback; imports t06_fixtures
spikes/references/s09_qualify_biosteam.py           tool script (BioSTEAM env): levels, rungs, outer loop, records
spikes/references/s09_qualify.sh                    runs every case (one process each), twice, and compares (A17)
benchmarks/s09/references/qualification/biosteam.json    levels, attempts, inspections, rungs, repeat_run
benchmarks/s09/references/results/biosteam-<case>.json   one record per pair (20)
benchmarks/s09/references/comparison.json            BioSTEAM classifications, controls, three-tool X31, responses
benchmarks/s09/references/SHA256SUMS
scripts/s09_reference_comparison.py                  classifier (may import S03's classifier; never changes it)
tests/test_s09_references.py                         the gate test
docs/S09_BUILD_DECISIONS.md                          build-lane decisions
```

**A tool record** carries:
- S03 §8's fields: case, tool, fingerprint, level and attempts, settings as registered, `stage_map`, `feed_stages`, the
  Q-X4–Q-X6 realizations, per stage T, P, L, V, x, y and duty, products' and inlets' enthalpies, the registered
  quantities by name (binary64 `repr`), and the rule values as the script computed them;
- per rung: both passes' `iter`, exceptions, the re-specification route, the read-back, every per-stage B3/B4 value and
  each check's largest value;
- at L2(c): every outer evaluation;
- §4.3's readback;
- the accuracy rerun's quantities;
- the per-level path-dependence ratio.

**The classifier recomputes every rule value from the raw fields** and does not trust the script's summary (S03 §8).
**The gate never runs a tool.** `tests/test_s09_references.py` recomputes every BioSTEAM classification from the
committed records, S03's `ours-*.json` and `s03_reference.json`, and the three-tool table from S03's pinned
`comparison.json`.

## 11. Assertions

`cases9` = `s09_cases.json`, `cases3` = `s03_cases.json`, `ref` = `s03_reference.json`, `cmp3` = S03's `comparison.json`,
`cmp9` = S09's.

| Id | Assertion | Expected | Tolerance and why |
| --- | --- | --- | --- |
| A01 | `s09_reference.py --check` passes | 167 claims; `cases9` byte-identical; S03 pins hold | exact |
| A02 | S03 is untouched: `cases3`, `ref`, `cmp3`, S03's `SHA256SUMS` and every file under `benchmarks/s03/references/` are byte-identical to `main` at `390e0af5`; `s03_reference.py --check` and S03's tests (`tests/test_s03_references.py`, `tests/test_s03_ours.py`) pass unchanged | equal; pass | exact |
| A03 | Blindness (§9.2 point 4): scanned set, forbidden strings and exemption, input files, no path under `s09_spike/`, `benchmarks/s03/references/results/` or `benchmarks/s09/`; checked at HEAD and at the qualification commit (`git show`; without history the test refuses explicitly, R-555's pattern) | pass | exact |
| A04 | Environment: every record's fingerprint equals `docs/reference-environments.md` §9's; two consecutive builds give identical fingerprints (recorded there); the lock pins every distribution by hash | equal | exact |
| A05 | Property readback (§4.3) in every record within its thresholds; and by mutation: a record whose readback `Psat` is moved by 1e-12 relative → rule 2c `property_mapping`, by 1e-15 → not fired; `h^V − h^L` moved by 1e-9 relative → rule 2c | as stated | thresholds §4.3; mutations at ≥ 100× and ≤ 0.1× of them |
| A06 | Ladder conformance: settings carry `tool_settings.BioSTEAM`; at every attempted level all four rungs are recorded (run, or the structural reason none was made); the selected rung is the first passing one in §5.3's order; a not-available record shows every rung at every expressible level; Q-X10 matches | set and order equality | exact |
| A07 | Solve path: every run shows passes 1 and 2, the attribute-setter route and the exact read-back after pass 2 | present | exact |
| A08 | L2(c) conformance: L2(c) attempted only after an L1 inspection recorded the specification inexpressible; the adjusted specification is the end's (`Reflux` stage 0 / `Boilup` stage N−1); evaluations start at x = 1, 2 and expand per §5.4; the solver call's arguments are §5.4's; every evaluation passed the inner checks; the final evaluation is at the returned x with \|g\| ≤ ytol(kind) | as stated | exact; ytol per claim C7 |
| A09 | Rule 2 fires (synthetic copies of a committed available record, or of a synthetic record if none is available): one stage's component flow +6.2e-8 mol/s → B3, +1.55e-8 → not; one stage's y_c +2e-8 → B4, +5e-9 → not; a pass with `iter == maxiter` → B2; an exception on pass 1 → B1; unaltered → rule 4 | the labels | mutations at 2× and 0.5× of each threshold |
| A10 | Rule 2c fires: stored B ≠ 1/RR by one ulp → `specification_readback`; total-condenser vapour 6.2e-8 → fired, 1.55e-8 → not; and S03 A12's four on BioSTEAM's RC1 record (`L[1]` × (1 + 2e-4) → 2c; × (1 + 2e-8) → 2d; a pressure + 0.01 Pa → 2c; a rerun quantity moved 0.2 tolerance → 2d); and S03 §17.9's per-kind synthetic records at 2× / 0.5× of rules 2c and 2d | the labels | as S03 A12 |
| A11 | Rule 2d path dependence fires: a copy with a second passing rung equal to the selected one except one quantity moved 0.2 tolerance → `path_dependence`; 0.05 → not | the labels | 2× and 0.5× of 0.1 |
| A12 | Controls: no control `AGREE`; §17.3(b) for BioSTEAM by mutation (both controls replaced by `NOT_COMPARABLE` copies → every BioSTEAM pair `NOT_COMPARABLE(control_not_comparable: …)`; one replaced while the other is `DISAGREE` → no pair changes; synthetic controls if none is `DISAGREE`); (PC-L, BioSTEAM) and (PC-LI, BioSTEAM) `not_applicable` with no record; PC-LB's tool-model distance computed against `ref.controls.PC-LI.tool_model`; PC-P's reported `not_applicable(tool_model_differs)` | as stated | exact |
| A13 | `cmp9` recomputed from the committed records, S03's `ours-*.json`, `cases3`, `cases9` and `ref` is byte-identical, and so is `SHA256SUMS`; recomputed with a live solve of our side, every BioSTEAM pair's classification, category, rule, label, `within_tolerance` and `quantities_outside`, the controls block and every X31 class, row and outcome equal `cmp9`'s | equal | exact (S03 §19.1's rule: floats that depend on our values are not compared against the live solve) |
| A14 | Tolerances: S03 §6's formula unrounded, no per-case or per-tool factor (synthetic pairs at 0.999 and 1.001 tolerance for each kind) | `AGREE` / `DISAGREE` | exact |
| A15 | Three-tool X31: `cmp9` holds, for RC1–RC4 and per inverse kind, the three classes (IDAES and DWSIM from `cmp3`), the row, the outcome and the clause; they equal `cases9 → x31_three_tool.pre_registered` at BioSTEAM's committed classes; with BioSTEAM omitted they equal `cmp3`'s rows and clause | equal | exact |
| A16 | The qualification commit is an ancestor of `cmp9`'s commit (`git merge-base --is-ancestor`; without history the test refuses explicitly) | pass | exact |
| A17 | Repeat run: `qualification/biosteam.json → repeat_run` shows the second full run reproducing every record byte for byte, wall-clock fields excepted | equal | exact (one machine; the tool is deterministic, §5.7) |
| A18 | `cmp9` holds each pair's level, rung and outer-evaluation count, each record's largest residual-to-threshold ratio and the "thin margin" list (§6.6), the perturbation response table with a BioSTEAM column (S03 §7.4), and every `NOT_COMPARABLE` and `DISAGREE` with its reason | present, complete | exact |
| A19 | `docs/reviews/S09-verdicts.md` exists, is the `verdict` agent's, and records §8's items and §9.1's disclosure | present | — |
| A20 | S01's, S02's, S03's and S06's suites pass unchanged on `wp/S09`; `s02_reference.py`, `s03_reference.py` and `s06_reference.py --check` pass | as registered | as registered |

## 12. Work orders

Each is about 150k context. At most two agents run at a time. Only WO-S09-2 needs `.venv-biosteam`.

**WO-S09-1 — environment** (build lane, `sonnet-implementer`, worktree; small).
- Write `spikes/references/biosteam-requirements.in` (`biosteam==2.54.0`) and its lock, compiled with
  `uv pip compile --generate-hashes --python-version 3.13 --python-platform x86_64-manylinux_2_28`.
- Record whether the same `.in` also resolves for `aarch64-manylinux_2_28`. This is a statement of installability, not
  a run.
- Add `biosteam` to `scripts/build-reference-envs.sh`: `.venv-biosteam/`, `--require-hashes`, a fingerprint (pip freeze
  SHA-256, Python version, the versions of §2.1).
- biosteam and thermosteam are sdists that build pure-Python wheels. If pip cannot hash-check their build backend under
  build isolation, pin `setuptools` and `wheel` in the lock and build with `--no-build-isolation`. Record the route.
- Add `docs/reference-environments.md` §9: status, host, reproduction, the fingerprint from two consecutive builds, the
  licence statement of §2.1, and the aarch64 statement. The qualification runs on the x86-64 workstation only, as for
  IDAES and DWSIM. CI on both architectures re-classifies committed records without BioSTEAM installed.
- Test: A04's file part. Log choices in `docs/S09_BUILD_DECISIONS.md`.

**WO-S09-2 — blind qualification** (build lane, `opus-engineer`, **fresh agent**, worktree).
- *Brief rules (§9.2).*
  - No tool value for an S03 case, no value of ours, no twin value.
  - Do not open `docs/derivations/scripts/s09_spike/`, `docs/briefs/S09-third-reference-tool.md`,
    `benchmarks/s03/references/results/` or `benchmarks/s09/` (before your own run).
  - Read this document, `s09_cases.json`, `s03_cases.json`, `docs/derivations/scripts/s09_design/` and the tool.
- `s09_biosteam_syn001.py`: §4.2 and §4.3.
- `s09_qualify_biosteam.py`: §2.3's order, §2.4's inspection, §5's path, ladder and loop, §6's rule values computed
  from the tool's own record, and §10's record fields.
- `s09_qualify.sh`: one process per case, the whole run twice, and the comparison (A17).
- Run all 20 pairs. Write `qualification/biosteam.json` and the 20 records. Commit them before WO-S09-3 (A16).
- Tests that need no tool: A03 (self-scan), A06–A08 (on the committed records).
- *Expected outcomes:* §2.5's realizations, to be confirmed or refuted. No convergence outcome is registered (Q-S09-1).
- A measurement that contradicts this document (a floor above §6.6's thresholds, a hook that behaves otherwise, a
  realization that cannot be built) **stops the work order before the recorded run**, and is reported to the design
  lane. The harness is not bent (rule 6).

**WO-S09-3 — classifier, gate test, evidence** (build lane, `opus-engineer`).
- `scripts/s09_reference_comparison.py`. It may import S03's classifier functions (tolerance, rules 3 and 4, response
  table) but never changes `scripts/s03_reference_comparison.py` or anything it writes (A02).
- `cmp9` and `SHA256SUMS`.
- `tests/test_s09_references.py`: A01–A03, A05–A16, A18, A20.
- `evidence/S09/<commit>/manifest.json` per §13.
- After WO-S09-4: the ledger rows X31 and D19 cite S09's verdict (§8.5).

**WO-S09-4 — verdict** (design lane, `verdict` agent).
- `docs/reviews/S09-verdicts.md` (A19): per-pair verdicts, the controls, the three-tool X31 clause (§8), D19 (§8.4), and
  §9.1's disclosure.

**Review.** The package's single `reviewer` pass covers WO-S09-1 to WO-S09-3 before the merge. It checks the harness
against §5 and §6, the read-back, and the L2(c) loop.

**Rules for every work order** (S03 §12, unchanged).
1. Nothing scientific is chosen on the build lane.
2. A failed run is a result.
3. A tolerance, setting, mapping, level or case changes only by an amendment of this document.
4. Every attempt is recorded.
5. Open build choices are isolated commits, logged in `docs/S09_BUILD_DECISIONS.md`.
6. A measurement that contradicts this document goes to the design lane.

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A18 and A20, each citing its id, and A19's document.
- `s09_reference.py --check` (167 claims) and `s03_reference.py --check` pass at the manifest commit.
- `ruff check` and `ruff format --check` are clean. `scripts/gate.sh` passes before the merge, and CI is green on both
  architectures.
- The manifest lists:
  - BioSTEAM's fingerprint;
  - the qualification commit and the comparison commit;
  - the SHA-256 of every record and of `cmp9`;
  - each pair's level, rung and classification;
  - each control's classification;
  - the three-tool table and the clause.
- `tested` records that the comparison was run and reproduces. It does not require any pair to `AGREE`.
- §14 is listed verbatim as limitations. `reviewed` is set only by the `reviewer`.
- Human numerical and process-modeling sign-off is Frank's.

## 14. What this does not establish

- **Not empirical validation.** SYN-001 is synthetic. An `AGREE` verifies that an independently written implementation
  of the same equations gives the same root at a registered state (S03 §14).
- **Only at `P_r`, only the registered states.** BioSTEAM's model away from `P_r` lacks both the Poynting factor and the
  liquid `v (P − P_r)` term. PC-P can show their combined effect, not either one. **Our Poynting terms stay without an
  independent check.**
- **An L2(c) `AGREE`** verifies our column against BioSTEAM's MESH equations at the state where the harness's outer loop
  meets the specification. The specification equation in that loop is S02's or S06's, written by the harness, not a
  BioSTEAM feature.
- **A `NOT_COMPARABLE`** is neither a failure nor a pass of our column. A BioSTEAM absence is a fact about this tool,
  these settings and this harness, not about the case.
- **The ladder and the loop are not claims about BioSTEAM's solvers.** The probes' rung outcomes are facts about five
  non-registered columns.
- **Path independence** is checked among four rungs at one level. It is no uniqueness claim.
- **The design probes (`s09_design/`) and the spike (`s09_spike/`) are not evidence** for any assertion. The thresholds
  they support are re-checked on every registered record (rule 2, §6.6's margin report).
- **The three-tool clause is S09's.** S03's verdict and its two-tool clause stand as S03's record. Whether a release
  accepts "met where available" is outside S09.
- **Independence is partial.** BioSTEAM shares numpy and scipy (other versions) as its numerical substrate. CoolProp,
  `thermo` and `chemicals` are in its closure and unused by the definition. Blindness is procedural (§9).
- **One platform.** The qualification runs on x86-64. aarch64 is a statement of installability.
- **No sensitivity capability, no phase-transition robustness, supported nonideal scope none** (S03 §9, §10.1, §14).

## 15. Open questions (each with a default)

1. **Q-S09-1** *Needs a fact* (WO-S09-2 settles it). Does BioSTEAM qualify each case at §2.5's expected level, and does
   the loop find a bracket for each L2(c) case? **Default: no expectation is registered.** A failure is
   `NOT_COMPARABLE(capability: <reason>)`, final for S09, and reported with its reason.
2. **Q-S09-2** *Needs Frank's preference* (scope, and an action only Frank can take). In plain words: if BioSTEAM cannot
   model the refluxed absorber (RC4), RC4 stays without any independent check, and X31's reference clause stays "not
   met". The only other candidate that models RC4 natively is ChemSep-LITE. It is Windows-only, needs 32-bit Wine
   installed with sudo, and its licence requires a visible acknowledgement. Should a ChemSep package be queued in that
   case? **Default: yes, queued but not started** until Frank installs 32-bit Wine and accepts the acknowledgement
   clause. If BioSTEAM qualifies RC4, nothing is queued.
3. **Q-S09-3** *Needs a fact* (WO-S09-1 settles it). Does the hash-locked build of two sdists reproduce byte for byte?
   **Default: yes**, with `--no-build-isolation` and a pinned build backend if needed. A failure is recorded, and the
   design lane decides whether a recorded wheel cache is acceptable.
4. **Q-S09-4** *Needs a fact* (WO-S09-3 settles it). Is PC-P BioSTEAM's only `DISAGREE` control? **Default: no**, PC-LB
   `DISAGREE`s. If PC-LB is not `DISAGREE` and PC-P is, the design lane adds a BioSTEAM-specific PC-P tool model (no
   Poynting factor and no liquid `v (P − P_r)`) to the generator by amendment before the verdict, so that the reported
   distance can show the `DISAGREE` comes from the expected effect.
5. **Q-S09-5** *Needs a fact* (WO-S09-2 settles it). Do the registered cases' residuals sit as far below the thresholds
   as the probes' (§6.6)? **Default: yes.** A selected record above 0.1 of a threshold is reported as "thin margin". A
   floor above a threshold stops WO-S09-2 before the recorded run (rule 6). The threshold is not relaxed.

## 16. Findings for other documents (not changed here)

- **F-1 (S03 §18.10 Q-A2-4, an expectation).** Q-A2-4 expected a third tool to be "a new package with its own ADR". S09
  finds none needed (§0). If the reviewer or Frank prefers one, it would be an ADR recording R-740 against ADR 0014 D7,
  with no change to any number here.
- **F-2 (R-628, "No other tool").** That was S03's scope and stays true for S03's records. R-740 records the new decision
  for S09, as the register requires.
- **F-3 (`docs/reference-environments.md`).** The title names T06's two tools. WO-S09-1 adds §9 and may retitle it. That
  is documentation, not a scientific change.
- **F-4 (S03 verdict F-1, the wording of §17.8 condition 2).** S03's erratum §19.2 has already corrected it. Nothing is
  open.

## 17. Decisions

Register R-740 to R-747.
- R-740: BioSTEAM 2.54.0 is the third column reference. S09 extends S03 without re-judging it. No ADR.
- R-741: BioSTEAM's levels: L1, and L2(c) under C1–C6. L2(a) is inapplicable, L2(b) and L3 are not admissible.
- R-742: BioSTEAM's SYN-001 definition: pure-component user methods, the tool's default datum, no `T_ref` subclass, and
  the per-run readback.
- R-743: The solve path (two passes, attribute-setter re-specification), the four-rung ladder (the tool's default chain,
  all rungs run), the common settings and the outer loop.
- R-744: BioSTEAM's rule 2 (B1–B5), the rule 2c additions and rule 2d's path dependence and rerun.
- R-745: PC-LB is BioSTEAM's control, with PC-LI's tool model. PC-P runs, and its tool-model distance is not applicable.
- R-746: The three-tool X31 table and clause, pre-registered. S03's verdict stands as its record, and the ledger cites
  S09's.
- R-747: Blindness: the spike's settings are not registered as such, a fresh agent qualifies, A03 gains three forbidden
  strings, and the exposure is disclosed.
