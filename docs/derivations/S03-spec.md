# S03 — two independent column references: qualification rule, cases, matched semantics, tolerances, verdict mechanics, supported scope and test specification

Design lane (`specifier`), 2026-10-24. Package S03 (plan v1.2 §4.5, `docs/implementation-plan.md:283`; D19 `:314`, column
part; X31 `:357`, with S02), brief `docs/briefs/S03-column-references.md`. Base: S02 (`docs/derivations/S02-spec.md` with
§17–§19) and S06 (`docs/derivations/S06-spec.md` with §17). Precedent: T06 §9 (`docs/derivations/T06-corpus-spec.md`) and
ADR 0014 D7. Reference generator `docs/derivations/scripts/s03_reference.py` (mpmath, 50 digits; it reuses the S02 and S06
generators, which import nothing from `src/`). `--check` re-derives **4009 claims** and byte-compares two files,
`s03_cases.json` (inputs only) and `s03_reference.json` (twin values), in about one minute on 15 worker processes.
Register R-628 to R-633.

## 0. Authority and scope

Normative for S03. It composes with S01, S02 (§17–§19), S06 (§17), T06 §9 and ADR 0014 D7, ADR 0001 (units, signs) and
ADR 0005 D4 (the phase contract), and reopens none of them. **It applies ADR 0014 D7's reference semantics to columns
unchanged**: every compared state with phase equilibrium at `P = P_r`, DWSIM's latent mapping, IDAES's registered settings
and SmoothVLE ε, the tolerance `a_k + 1e-6 |v|`, a mechanical classification before the `verdict` agent's verdict, positive
controls that must classify `DISAGREE`, and a gate that never runs a tool. What it adds — the expressibility levels (§2),
the column semantics self-checks and the accuracy rerun (§7 rules 2c, 2d), DWSIM's column-solver ladder (§5.2) — is
specification content of the kind T06 §9.3's rows are. **No ADR is needed** (R-633).

It changes no frozen interface (`docs/interfaces-frozen.md`). The one code change it specifies, refusal S11 (§9), returns
the existing `CascadeFailure` with the existing code `CAPABILITY_UNAVAILABLE` and reads two existing fields of
`PropertyCapabilities` (`provider_id`, `reference_convention`). No protocol, schema, quantity kind, row or registered root
changes.

Lane: design leads, build follows (plan §4.5, binding). Build-lane chunks run as subagents in worktrees, and the design lane
reviews them before the merge.

**What it establishes.** The two references and the pre-registered rule for "where available" (§2). Five reference cases,
ten perturbed cases, two positive controls and one generator sensitivity case, with twin values (§3). The registered
comparison quantities (§4). The matched semantics per tool (§5). The tolerances (§6). The verdict mechanics (§7). The evidence
layout and blindness (§8). The supported nonideal scope, which is none, with the refusal that makes it checkable (§9). The
decisions S02 deferred (§10). Assertions S03.A01–A17 (§11), work orders (§12) and the manifest check list (§13).

**What it does not establish** is §14. Read it before citing anything here.

## 1. The brief's questions, decided

| Question (brief §6) | Decision | Where |
| --- | --- | --- |
| 1. The references | IDAES 2.13.0 and DWSIM 9.0.5, the T06 environments. Whether each can express a case is settled by a blind qualification at three pre-registered levels; a case a tool cannot express is `NOT_COMPARABLE(capability)` for that tool, never a substituted model | §2 |
| 2. Cases | RC1–RC4 are S02's M1–M4 with every pressure at `P_r` (X31's four). RC5 is S06's J1 on RC1 (one inverse kind). Both tools, all quantities of §4. P1 is not compared | §3 |
| 3. Matched semantics | T06 §9.3's mapping verbatim, plus the column rows of §5.1 | §5 |
| 4. Tolerances and verdicts | T06 §9.4's formula; T06 §9.5's rule order, plus a semantics self-check (2c) and an accuracy check (2d) | §6, §7 |
| 5. Perturbation studies | Ten registered perturbed cases (each end specification +2 %, and a feed-composition shift), solved by all three implementations and classified like the base cases. Each perturbation moves the twin by ≥ 8382 tolerances. The finite-difference response is reported. No sensitivity capability is claimed | §3.2, §7.4 |
| 6. Supported nonideal scope | **None.** The column's K is composition-independent by construction. Any provider other than SYN-001 is refused before evaluation (S11) | §9 |
| 7. Deferred items | R-533/R-554: the contract learns no block rule; the limitation is registered. R-534: the references attach to RC1–RC4, and M1–M4 keep generator-only matching. R-508: S01's cascade is exercised inside RC3 and RC4 | §10 |
| 8. Evidence and verdict | Manifest check list §13. The `verdict` agent writes `docs/reviews/S03-verdicts.md` | §12, §13 |

## 2. The two references and the qualification rule

### 2.1 The references

**IDAES** (idaes-pse 2.13.0, extensions 3.4.2; Ipopt with MUMPS) and **DWSIM** (9.0.5 through pythonnet 3.1.0), as built by
`scripts/build-reference-envs.sh` and fingerprinted in `docs/reference-environments.md` §3. Their licences are recorded in
§4 of that document. No other tool is used (brief §7). Neither tool shares code, data files or a property package with this
project. They share SYN-001's constants, entered as user input by T06's definitions, and the column semantics of §5, which
are matched by construction.

**Disclosure (D19).** *A comparison verifies a second, independent implementation of the same equations. It is numerical
verification, not empirical validation.* The twin (`s03_reference.json`) is the third corner. It shares SYN-001's closed forms
and S02/S06's definitions with the implementation, so it is not independent. Blindness (§2.3) is procedural: the person who
writes the tool scripts knows this project. It is enforced by what the scripts may read (A03), not by an independent author.

### 2.2 What "expressible" means: three levels

The **matched model** of a case is S02 §2's rows (with S06 §2's inverse row for RC5) on SYN-001 after T06 §9.3's mapping, at
the case's registered inputs (§3). A tool expresses a case if it builds that model from its own unit models and property
package at one of these levels:

| Level | What is allowed | Tools |
| --- | --- | --- |
| L1 | The tool's native column unit and its native specification options | IDAES (its column models, e.g. `TrayColumn`); DWSIM (its rigorous `DistillationColumn`, `ReboiledAbsorber`, `RefluxedAbsorber` or `AbsorptionColumn`) |
| L2 | The native column unit, plus either (a) a tool variable fixed at a value S02's semantics implies exactly (a liquid-distillate flow of 0, a tray duty of 0, a pressure drop of 0), or (b) a specification equation on the tool's own variables, written verbatim from S02 §2.1 or S06 §2, in place of a native specification. Form (b) is for an equation-oriented tool only | IDAES (a), (b); DWSIM (a) |
| L3 | A composition of the tool's own stage-level unit models — IDAES `Tray`, `Condenser`, `Reboiler`, `Flash` — joined by the tool's own connections (`Arc`), with L2's realizations. IDAES builds its `TrayColumn` this way, so every equation is still IDAES's | IDAES only |

**Never admissible, at any level:**
- user-written thermodynamics, phase equilibrium, balance or enthalpy equations;
- a property method other than T06's SYN-001 definitions;
- any value taken from this project's results, the twin, `s03_reference.json` or a comparison output;
- a change to a registered input (pressure, stage count, feed stage, inlet state, specification value).

A case that needs one of these is `NOT_COMPARABLE(capability: <what>)` for that tool. **A different model is never
substituted.**

*Why no DWSIM L3.* A cascade of DWSIM vessels joined by recycles is the harness author's column, converged by tear iteration.
Its accuracy depends on tear settings that would have to be registered case by case (T06 §5.2 measured DWSIM's `Recycle`
defaults leaving 0.0306 mol/s of balance error).

### 2.3 The pre-registered "where available" rule

1. **Order.** For each (case, tool), try the levels L1, L2, L3 in turn. At each level, first record a **structural inspection**
   of the built model: the answers to §2.4's questions, read from the model object before it is solved. Then run it under
   §5's registered settings. The case's level is the first one whose model is structurally expressible **and** whose run
   passes rules 2–2d of §7. Every attempt, failed or not, is recorded with its reason in
   `benchmarks/s03/references/qualification/<tool>.json`.
2. **Blind.** The tool scripts read `docs/derivations/scripts/s03_cases.json` and T06's SYN-001 tool definitions, and nothing
   else of this project. They read no result of ours, no twin value and no comparison output. Because the selection is blind,
   choosing a level or a DWSIM solver setting by convergence cannot steer toward agreement. A03 checks this.
3. **Committed before comparison.** The qualification records and tool results are committed before the classifier first runs.
   The manifest lists both commits, and the qualification commit must be an ancestor of the comparison commit. After that,
   no tool input, level, setting or mapping changes except by an amendment of this document (§12, rule 6).
4. **Available.** A tool is *available* for a case if and only if step 1 found a level. A tool that is not available for a case
   gives the record `NOT_COMPARABLE(capability: <reason>)`, with every attempt.
5. **X31's clause** "two independent references where available" counts RC1–RC4 only. It is met in count if every RC1–RC4
   case has a comparable classification (`AGREE` or `DISAGREE`) from every available tool, and at least one tool is available
   for every case. The count of cases with two comparable references is reported (target: 4). Whether the column is verified
   is the `verdict` agent's call (§7.5).

### 2.4 Structural questions (answered per tool and case, before the run)

| Id | Question | Record field |
| --- | --- | --- |
| Q-X1 | Does every stage, the condenser and the reboiler use T06's SYN-001 property definitions (IDAES's `GenericParameterBlock` from T06's script; DWSIM's T06 user compounds and its Raoult's Law package)? | `property_package` |
| Q-X2 | Does the model have N stages, counted as §5.1 row 3 counts them, and what is the map from our stage j to the tool's stage? | `stage_map` |
| Q-X3 | Does each inlet enter whole at its mapped stage? | `feed_stages` |
| Q-X4 | Is the condenser of §5.1 rows 5–6 (partial: vapour distillate, all liquid refluxed; total: saturated liquid at its bubble point) or absent with a top inlet on stage 1? | `condenser_realization` |
| Q-X5 | Is the reboiler a kettle (§5.1 row 7), or absent with a bottom inlet on stage N? | `reboiler_realization` |
| Q-X6 | How is each registered specification realized: native option, fixed variable or equation? Give the tool's definition in its own variables | `specifications` |
| Q-X7 | Is every stage pressure fixed at the registered value, with no pressure-drop relation? | `pressures` |
| Q-X8 | Are the intermediate stages adiabatic equilibrium stages (efficiency 1), with no hydraulics, entrainment, side draws or pump-arounds? | `intermediate_stages` |
| Q-X9 | Where does the initial point come from (§5.1 row 12)? | `initialization` |

## 3. Registered cases (inputs in `s03_cases.json`, twin values in `s03_reference.json`)

**Common to every RC and perturbed case.** Provider SYN-001; components A, B, C. The feed is as in S02 §9: `z = (0.3, 0.4,
0.3)` mol/s, F = 1. **Every stage pressure — condenser and reboiler included — and every inlet pressure is `P_r = 1e5 Pa`
exactly.** Intermediate stages are adiabatic. N, the feed stage, and each inlet's T and declared phase are those of the base
S02 case.

*Why `P_r`.* Neither tool's K has SYN-001's Poynting factor (`docs/reference-environments.md` §5.0). At `P = P_r` that factor is
exactly 1 and SYN-001's liquid-enthalpy term `v_i (P − P_r)` is exactly 0. The generator claims that the tools' model gives
SYN-001's rows exactly at every RC and perturbed root (15 claims). S02's M1–M4 run at a 1.00–1.06 bar profile, where the two
models differ by up to 176 tolerances (PC-P, §3.3). Comparing there with a declared difference is the alternative ADR 0014 D7
rejected as tuning by another name. Our solver takes a uniform pressure: S02 §5 S9 refuses only a pressure that decreases
down the column.

### 3.1 The reference cases

| Case | Configuration | Why it is in the list | Sanity values at the twin root (`ref.twin.<case>`) |
| --- | --- | --- | --- |
| RC1 | M1 at `P_r`: N = 7, partial condenser, kettle reboiler, liquid feed at stage 4 (340 K); RR* = 2, BR* = 1.5 | the nominal two-ratio column; S02's partial condenser (vapour distillate, all liquid refluxed), which no tool offers natively under that name | `T_1 = 332.48397297…`, `T_7 = 372.16157594…` K; `D = 0.35277028…` mol/s; `Q_1 = −20031.9749…`, `Q_7 = 30993.9377…` W; σ_min 0.0476505; 29 quantities |
| RC2 | M2 at `P_r`: N = 7, total condenser, kettle reboiler, same feed; RR* = 1.5, B* = 0.55 | the total condenser at its bubble point (bubble row and split), and a rate specification | `T_c = 329.80259061…`, `T_7 = 375.67495336…` K; `BR = 1.84698541…`; `Q_c = −31369.5973…`, `Q_7 = 32872.8363…` W; σ_min 0.0181329; 28 quantities |
| RC3 | M3 at `P_r`: N = 5, no condenser, kettle reboiler, liquid `top` inlet (300 K) on stage 1; Q_r* = 30 kW | a stripper: a `none` end whose stage 1 is an S01 stage, and a duty-specified reboiler | `T_1 = 362.19836934…`, `T_5 = 396.72011587…` K; `B = 0.19876902…` mol/s; `BR = 4.33310878…`; σ_min 0.0304219; 21 quantities (the specified duty is not compared) |
| RC4 | M4 at `P_r`: N = 5, partial condenser, no reboiler, vapour `bottom` inlet (385 K) on stage 5; D* = 0.5 | a refluxed absorber: a `none` reboiler and a distillate rate | `T_1 = 347.13470145…`, `T_5 = 370.90994102…` K; `RR = 1.23419018…`; `Q_1 = −18856.4152…` W; σ_min 0.0529821; 22 quantities |
| RC5 | RC1's column; condenser purity of A in the vapour distillate 0.85, BR* = 1.5 (S06's J1 at `P_r`) | S06's inverse slot against a second implementation, with a ratio partner. One inverse kind exercises S06's slot mechanics; recovery and temperature are not compared (§14, Q-S03-5) | `T_1 = 330.53412968…`, `T_7 = 371.65135241…` K; `D = 0.33702663…`; `RR = 2.24545407…`; `Q_1 = −21227.6941…`, `Q_7 = 31686.3669…` W; σ_min 0.0316093; 29 quantities |

RC1–RC4 are X31's "four matched column cases" for the reference clause. RC5 is reported beside them and is not counted.

Every case is checked in the generator:
- the twin root is reached by S02 §18.2's endpoint and the straight path in 16 equal steps (S06's solve);
- every stage is two-phase with `L, V > 1e-3` mol/s and lies in the domain;
- the root is regular (σ_min > 1e-4) and closes component and energy balances;
- S02's division-free rows vanish below 1e-38;
- RC5's purity row holds below 1e-30;
- each inlet is an admissible single phase with a margin of at least 0.02;
- every pressure is exactly the registered one;
- within each family of §4, the quantities differ pairwise by more than the sum of their tolerances, so a permuted stage or
  component index changes the classification.

### 3.2 The perturbation study (ten perturbed cases)

Each perturbed case is its base case with one input changed. All three implementations solve it, and it is classified like a
base case (§7). Its discrimination is `max_q |y_pert − y_base| / tol(y_pert)` at the twin (`ref.perturbations`). It is the
amount by which a tool, or our side, that ignored the perturbation would miss.

| Case | Change from the base | Twin discrimination: max ratio (quantity), quantities over 1 tolerance |
| --- | --- | --- |
| RC1-RR | RR* 2 → 2.04 | 8382.63 (`L[1]`), 29/29 |
| RC1-BR | BR* 1.5 → 1.53 | 10312.5 (`Q_reboiler`), 29/29 |
| RC1-z | feed (0.3, 0.4, 0.3) → (0.28, 0.4, 0.32) mol/s | 38123.4 (`top[B]`), 29/29 |
| RC2-RR | RR* 1.5 → 1.53 | 13520.3 (`reflux`), 27/28 |
| RC2-B | B* 0.55 → 0.561 | 22006.6 (`top[B]`), 28/28 |
| RC2-z | feed as RC1-z | 37346.1 (`top[B]`), 25/28 |
| RC3-Q | Q_r* 30000 → 30600 W | 32861.2 (`L[5]`), 21/21 |
| RC3-z | feed as RC1-z | 33895.7 (`top[A]`), 21/21 |
| RC4-D | D* 0.5 → 0.51 | 16354.2 (`L[2]`), 22/22 |
| RC4-z | feed as RC1-z | 28496.3 (`top[A]`), 20/22 |

**What "perturbation study" means here** (brief §6.5, decided).
- It is not a sensitivity capability: the column has none (S02 §14).
- It is a set of registered neighbouring states on which the three implementations are compared, so agreement is not confined
  to one state per topology (rule 3 of this repository).
- From the base and perturbed records it reports the finite-difference response `Δy = y_pert − y_base` per quantity for ours,
  each tool and the twin (§7.4).
- A response that agrees to within `tol(y_pert) + tol(y_base)` follows from two `AGREE` classifications. It is reported, not
  classified a second time.
- The generator claims every perturbation is resolvable: ≥ 100 tolerances on some quantity (measured: ≥ 8382).

### 3.3 Positive controls and the stage sensitivity

| Id | Tools | Definition | Our side | Expected | Twin discrimination (`ref.controls`, `ref.sensitivity`) |
| --- | --- | --- | --- | --- | --- |
| PC-P | IDAES, DWSIM | RC1's column, specifications and feed with **every pressure 1.5e5 Pa** (T06 PC-2's pressure) | the SYN-001 root at 1.5e5 Pa: a new our-side state, judged by rule 3 like the others | `DISAGREE` | tool model (K without the Poynting factor) against SYN-001: max 176.357 (`T[1]`: 346.35876623… against 346.42161247… K), 28/29 over 1 tolerance; least `bottom[C]` 0.53 and `top[C]` 1.04 |
| PC-L | DWSIM | RC1 with DWSIM's `ΔH_vap,i = L_i` (unmapped: 25000, 30000, 35000 J/mol), so `h^V − h^L` is smaller by `P_r v_i` = 10 J/mol | RC1's record | `DISAGREE` | max 243.292 (`Q_reboiler`: 30993.9377… against 30983.9642… W), 22/29 over 1 tolerance. **Marginal on temperatures**: `T[4]`–`T[7]` move 0.59–0.78 tolerance, so the duties and flows carry PC-L |
| (PC-L, IDAES) | — | IDAES's SYN-001 mapping has no vaporization-enthalpy input (T06 §9.4) | — | `not_applicable`, a registered absence outside every count | — |
| E1 | none (generator only) | RC1 with the feed one stage up (stage 3) | — | — | 1.0687e6 (`L[3]`), 29/29: a stage-numbering error in a harness cannot hide inside the tolerance |

Each tool-model root is found by Newton from the SYN-001 root in the tool's own model: K without the Poynting factor for
PC-P, `h^V` less `P_r v_i` for PC-L. It is regular (σ_min 0.0473614 and 0.0476583). The PC records also report the tool's
distance to the tool-model twin, divided by the tolerance (§7.3). That line shows whether a `DISAGREE` came from the effect the
control exists to show.

## 4. Registered quantities

For each case the comparison reads exactly the quantities `s03_cases.json` lists under `quantities` (names and kinds), in
SI units and in our stage numbering:

- `T[j]`, j = 1..N: stage temperature. `T[1]` of a total condenser is `T_c`.
- `L[j]`, `V[j]` for every equilibrium stage j: total liquid and vapour leaving the stage. For a partial condenser `V[1]` is
  the distillate and `L[1]` the reflux. For a kettle reboiler `L[N]` is the bottoms and `V[N]` the boil-up.
- `reflux` (total condenser only): `φ V_2`.
- `top[c]`, `bottom[c]`: component flows of the products (S02 §1.7). `top` is `v_1` for a partial or absent condenser and
  `d` for a total one; `bottom` is `l_N`.
- `Q_condenser`, `Q_reboiler` (W, positive into the stage), except a duty that is the registered specification.

Stream enthalpies are **not** compared: each tool's datum differs by per-component constants (T06 §9.3). These constants
cancel in every balance, so they do not cancel in a stream's enthalpy.

## 5. Matched semantics

### 5.1 Decisions (T06 §9.3's form)

| # | Question | Decision | Reason |
| --- | --- | --- | --- |
| 1 | SYN-001 inside the column | **T06 §9.3 verbatim, with its A1 and A2.** DWSIM: `ΔH_vap,i = ΔH_f,ig,i = L_i + P_r v_i` = 25010, 30010, 35010 J/mol; placeholders `T_c` 1000 K, `P_c` 1e7 Pa, ω 0, NBP = `T_b,i`; liquid-density pressure correction off. IDAES: `h_form,liq = 0`, `h_form,ig = L_i`, placeholders `T_c` 1000 K, `P_c` 1e7 Pa. **The tool scripts import T06's SYN-001 definitions** from `spikes/references/` rather than re-entering them | it is the mapping T06 qualified (16 of 16 pairs `AGREE`, `docs/reviews/T06-verdicts.md`). One definition cannot drift |
| 2 | Pressure | Every stage, the condenser, the reboiler and every inlet at `P_r` exactly, for RC, the perturbed cases and PC-L. Every pressure is 1.5e5 Pa for PC-P | §3. Generator-claimed identity of the rows at `P_r` |
| 3 | Stage numbering | Ours (S02 §1.1): j = 1..N top to bottom, counting the condenser (stage 1) and the reboiler (stage N) when present. Each record carries `stage_map` (our j → the tool's stage or unit). Expected maps: IDAES tray k = j − [condenser ≠ none] for intermediate stages, with the condenser and reboiler as units; DWSIM, the j-th stage from the top, with its index base recorded | the stage temperatures and flows are compared per stage; E1 shows an off-by-one costs 1.07e6 tolerances |
| 4 | Inlets | Single phase as declared, at their own (T, P), each entering its stage whole; a tool must not split a feed between stages. Every liquid inlet is subcooled and every vapour inlet superheated with a margin of at least 0.02 (generator claim), so a tool's feed flash returns the declared phase | S01 §3, S02 §1.4 |
| 5 | Partial condenser (S02 §1.2) | An equilibrium stage with duty, fed by `v_2`. Its vapour `v_1` is the distillate and all its liquid `l_1` returns to stage 2. A tool's liquid-distillate stream, if it has one, is fixed at exactly 0 (L2 a) | S02's semantics; a tool's "partial condenser" usually also offers a liquid distillate |
| 6 | Total condenser | `v_2` is condensed completely to saturated liquid at its bubble point at the condenser pressure. Reflux and distillate share composition and T. No subcooling | S02 §1.2, §2.2 |
| 7 | Reboiler | Kettle: an equilibrium stage with duty, with liquid bottoms `l_N` and vapour boil-up `v_N` | S02 §1.3 |
| 8 | `none` ends | RC3's liquid `top` inlet enters stage 1, with no condenser. RC4's vapour `bottom` inlet enters stage N, with no reboiler | S02 §1.2–1.3 |
| 9 | Specifications (molar) | RR = `L_1/V_1` (partial), `Σr/D` (total); BR = `V_N/L_N`; D = `V_1` (partial) or `D` (total); B = `L_N`; Q_r = the reboiler duty; purity = the mole fraction of A in the vapour distillate. A tool option with another definition (for example a reflux ratio over a liquid distillate) is not this specification. A specification in mass units is converted with T06's molar masses and recorded | S02 §2.1, S06 §1 |
| 10 | Intermediate stages | Adiabatic (Q = 0 exactly), equilibrium (efficiency 1), no pressure drop, no hydraulics, entrainment or weeping, no side draws, no pump-arounds | S02 §1.4–1.5, §14 |
| 11 | Signs | `Q > 0` into the stage (ADR 0001 D4.1). A tool's reported duty is converted, and the conversion is recorded | — |
| 12 | Initialization | The tool's own initializer or estimator. If it needs a temperature profile: linear from 320 K (stage 1) to 400 K (stage N), from SYN-001's `T_b` alone. No value from our side or the twin | T06 A1's rule: the tools' starts stay independent of ours |
| 13 | IDAES settings | T06 §9.3: `linear_solver = mumps`, `tol = 1e-10`, `constr_viol_tol = 1e-9`, `max_iter = 500` for the final solve; initializers with MUMPS and IDAES's other defaults; SmoothVLE `eps_1 = eps_2 = 1e-8 K` on every state block; converged iff Ipopt ends "Optimal Solution Found" | T06 §9.3, A1, A2 |
| 14 | DWSIM settings | Flash loops (PT and PH, external and internal) `1e-10`, 1000 iterations. The column solver and tolerance follow §5.2 | T06 §9.3 |
| 15 | Accuracy rerun (rule 2d; `floor_rerun` in `s03_cases.json`) | IDAES: `tol = 1e-9`, `constr_viol_tol = 1e-8`. DWSIM: the selected column tolerance × 10. Everything else unchanged | §6 |

Every setting is machine-readable in `s03_cases.json` → `tool_settings`.

### 5.2 DWSIM's column solver (pre-registered ladder; selected blind in qualification)

- **Tolerances**, tightest first: `1e-10, 1e-9, 1e-8, 1e-7, 1e-6`. These apply to the column's convergence tolerances (external
  and internal loops), with at most 1000 iterations.
- **Methods**, at each tolerance in this order:
  1. simultaneous correction (Napthali–Sandholm);
  2. inside-out (Russell);
  3. bubble point (Wang–Henke) for RC1, RC2, RC5, their perturbations and PC-P and PC-L, or sum rates (Burningham–Otto) for
     RC3 and RC4 and their perturbations.
- **Selection.** The first (tolerance, method) pair under which every DWSIM case converges and passes rules 2–2d becomes the one
  uniform setting. If no single pair converges every case, each case takes the first pair that works for it, and the record
  says so.
- **Why the ladder is not tuning.** The methods solve the same MESH equations, and the selection is blind (§2.3). Rule 2d
  checks the accuracy of whatever is selected.

## 6. Tolerances

For a quantity of kind k with twin value v (the 25-digit string in `ref.twin`, `ref.controls`, evaluated unrounded):

**`|ours − tool| ≤ a_k + 1e-6 |v|`**, where a_k is T02 §6.4's allowance: flow 3.1e-7 mol/s, T 1e-5 K, duty 1e-2 W. This is
T06 §9.4's formula, unchanged.

*Above the floors.*
- **Our side.** It must sit within 0.1 tolerance of the twin (rule 3). S02 measured our deviation from its generator at
  ≤ 8.5e-3 of S02's state tolerance (S02 §18.5). That is ≤ 8.5e-3 of this tolerance for flows, 2.5e-3 for T and 3e-3 for
  duties.
- **IDAES.** `constr_viol_tol = 1e-9` in model units, against 3.1e-7 mol/s (310×) and 1e-2 W (10⁷×).
- **DWSIM.** Its floor is measured per record by rule 2d, which requires the change between the registered and the looser
  setting to stay ≤ 0.1 tolerance.
- **Relative term.** `1e-6` is at least 10⁴ times ten ulps at every registered magnitude.

*Below the smallest error worth catching* (generator claims):
- PC-L: 243× (10 J/mol in a 25–35 kJ/mol latent heat);
- PC-P: 176× (a 2e-4 relative K error at 1.5 bar);
- E1: 1.07e6× (a feed one stage off);
- every perturbation: ≥ 8382× (a 2 % specification change);
- S02's own probes, for scale: swapping RR and BR, or flipping a slot sign, is O(1 K) = O(3000) tolerances.

*Where it is marginal, it says so.* PC-L moves the stripping-section temperatures by less than one tolerance (§3.3), and the
duties carry it. PC-P moves `bottom[C]` by 0.53 tolerance, and 28 other quantities carry it.

*Rule 2 thresholds* (each one tenth of an allowance or below, so a reference inside them cannot move a comparison):
- tool-internal component closure: 3.1e-8 mol/s per component;
- tool-internal energy closure: 1e-3 W;
- stage pressures: within 1e-3 Pa (ΔT ≈ (RT²/L)(ΔP/P) ≤ 4e-7 K, about 1e-3 tolerance);
- intermediate duties: |Q| ≤ 1e-3 W;
- a fixed-zero liquid distillate: ≤ 3.1e-8 mol/s.

*Specification residual thresholds.* The specification computed from the tool's own record (§5.1 row 9) is compared with the
registered value at two levels:
- more than **1e-4** relative is a definition mismatch (rule 2c), because a wrong definition errs by O(1–10 %);
- more than **1e-8** relative is an accuracy failure (rule 2d).

*Derivation of 1e-8.* The largest response to a relative specification change is RC3-Q's: 32861 tolerances per 2 %, or
1.64e6 tolerances per unit relative change. So 1e-8 relative moves a quantity by ≤ 0.016 tolerance, six times under the 0.1
budget. Purity uses 1e-8 absolute on the mole fraction.

## 7. Verdict mechanics

### 7.1 Mechanical classification, per (case, tool), in this order

Rules 0–2d read **only the tool's record** (and `s03_cases.json`). Rule 3 reads ours and the twin. Rule 4 reads ours and the
tool.

| Rule | Condition | Classification |
| --- | --- | --- |
| 0 | the tool is not available for the case (§2.3 step 4) | `NOT_COMPARABLE(capability: <reason>)` |
| 1 | the environment fingerprint differs from `docs/reference-environments.md` §3, or the tool did not run | `NOT_COMPARABLE(access: <what>)` |
| 2 | not converged: for IDAES, Ipopt's final solve did not end "Optimal Solution Found"; for DWSIM, the column or any object reported an error or hit its iteration limit. Or the tool's own overall component balance (inlets = products) misses by more than 3.1e-8 mol/s on any component. Or its own energy balance (Σ inlet enthalpies + duties = Σ product enthalpies, in its own datum) misses by more than 1e-3 W | `NOT_COMPARABLE(reference_accuracy: <value>)` |
| 2b | (IDAES only) T06 rule 2b unchanged: SmoothVLE shift > 1e-7 K on any state block, or a block without `eps_1 = eps_2 = 1e-8 K` | `NOT_COMPARABLE(semantics: smooth_vle_shift(<K>))` |
| 2c | semantics self-check fails: the stage count or `stage_map` disagrees with the case, an inlet enters another stage, a stage pressure is more than 1e-3 Pa from the registered value, an intermediate duty has \|Q\| > 1e-3 W, a fixed-zero liquid distillate carries more than 3.1e-8 mol/s, or a specification computed by §5.1 row 9 from the tool's own flows (or T) differs from the registered value by more than 1e-4 relative | `NOT_COMPARABLE(semantics: <check>(<value>))` |
| 2d | accuracy check fails: a specification residual > 1e-8 relative (purity 1e-8 absolute), or the accuracy rerun (§5.1 row 15) did not converge, or it moves any registered quantity by more than 0.1 tolerance | `NOT_COMPARABLE(reference_accuracy: <check>(<value>))` |
| 3 | ours is not accepted: its outcome is not `CONVERGED`, it fails S02 §8 or S06 §8, or a registered quantity is more than 0.1 tolerance from the twin | `NOT_COMPARABLE(ours_not_verified)`, and a column finding (§7.5) |
| 4 | every registered quantity within §6 | `AGREE`; otherwise `DISAGREE`, with the full table (quantity, ours, tool, twin, tolerance, ratio) |

*Why rule 2d may only produce `NOT_COMPARABLE`, never a pass.* A solver that stops on some criterion other than its tolerance
can show no change on the rerun and still be inaccurate. That error then appears as a `DISAGREE`, which goes to the `verdict`
agent. An inaccurate reference can therefore cost a false `DISAGREE`, never a false `AGREE`.

### 7.2 Positive controls

- PC-P (both tools) and PC-L (DWSIM) **must classify `DISAGREE`**.
- If rules 1–2d classify a control `NOT_COMPARABLE`, that tool's RC1 pair and its three RC1 perturbation pairs are
  classified `NOT_COMPARABLE(control_not_comparable: <control>)` as well: the tool's semantics are unproven on that
  configuration (T06 §9.5's rule, "the same fixture").
- An `AGREE` on a control means the harness cannot see the effect it exists to see. Then this document is wrong and the
  comparison stops.
- (PC-L, IDAES) is `not_applicable`.

### 7.3 Reported, not classified

- For each control: the tool's maximum distance to the tool-model twin, divided by the tolerance. It is expected to be ≤ 1
  if the tool computed its own model correctly.
- For every pair: the expressibility level and the DWSIM ladder rung.
- Iteration counts, property-call counts and times are not compared (plan §6.2).

### 7.4 The perturbation response table

For each perturbed case and quantity, report `Δy = y_pert − y_base` for ours, IDAES, DWSIM and the twin, with the bound
`tol(y_pert) + tol(y_base)`. Where both points are `AGREE`, the bound holds by construction. The table is evidence of matching
local responses at registered states and nothing more (§14).

### 7.5 The recorded verdict, and what a DISAGREE does

The `verdict` agent issues the recorded verdicts in `docs/reviews/S03-verdicts.md`, from the committed classification and this
document. It may not change a tolerance, setting, mapping, level or case. It records:
- per pair, the verdict with its reasons;
- X31's reference clause, counted by §2.3 step 5;
- D19's column part: matched-model inputs (§5), the independence disclosure (§2.1) and the verdicts;
- the perturbation response table (§7.4).

*A genuine `DISAGREE`* is one that survives rules 0–3. It is a finding for the design lane, which is told what the build lane
saw: either our column (an S02 or S06 defect) or the tool's model. No input changes on the build lane's initiative. A
justified explanation is not numerical agreement (blueprint §13.3).

*A rule 3 classification* means our solver failed a registered admissible state, or failed to land within 0.1 tolerance of
the twin. That is an S02 or S06 finding, never a reason to drop the case.

## 8. Evidence layout, blindness and the gate

```
spikes/references/s03_qualify_idaes.py    tool script (IDAES env); imports T06's SYN-001 IDAES definitions
spikes/references/s03_qualify_dwsim.py    tool script (DWSIM env); imports T06's SYN-001 DWSIM definitions
spikes/references/s03_qualify.sh          runs both blind (T06's t06_qualify.sh pattern)
benchmarks/s03/references/qualification/<tool>.json   levels, attempts, structural inspections, ladder selection
benchmarks/s03/references/results/<tool>-<case>.json  one tool record per (case, tool), controls included
benchmarks/s03/references/results/ours-<case>.json    our side: only the fields the comparison reads
benchmarks/s03/references/comparison.json             classifications, tables, response table, X31 count
benchmarks/s03/references/SHA256SUMS
tests/test_s03_references.py                          the gate test (A01–A03, A08–A14)
```

A **tool record** carries:
- case id, tool, environment fingerprint, level and its attempts;
- the settings used, as registered, and the DWSIM rung;
- `stage_map`, `feed_stages`, the realizations of Q-X4 to Q-X6;
- convergence status and termination message;
- per stage: T, P, L, V, x, y and duty;
- products' component flows and enthalpies, inlets' enthalpies;
- the registered quantities by name (binary64 `repr`);
- the rule 2, 2b, 2c and 2d values as the tool script computed them from its own record;
- the accuracy rerun's registered quantities.

The classifier recomputes the rule values from the record's raw fields. It does not trust the script's own summary.

**Blindness, executable (A03).**
- The two tool scripts, and any module they import from this repository other than T06's SYN-001 definitions, contain none of
  these strings (case-sensitive): `s03_reference`, `s02_reference`, `s06_reference`, `openflowsheet`, `ours-`,
  `comparison`, `twin`.
- They open no path under `benchmarks/s03/references/results/ours-*`.
- Their only input file from this project is `s03_cases.json`.

**The gate never runs a tool.**
- `tests/test_s03_references.py` recomputes every classification from the committed tool records, `s03_reference.json` and a
  live solve of our side, and checks the result equals `comparison.json`.
- Classifications are compared exactly; ratios and values to 1e-12 relative (T06 A50's rule, ADR 0014 Amendment 5).

## 9. Supported nonideal scope: none

**Statement.** The column (S01's cascade, S02's column and S06's specifications) supports exactly one property method:
SYN-001 (`provider_id = "syn001"`, `reference_convention = "SYN-001-ref-v1"`). It is an ideal solution with
composition-independent `K(T, P)`, including the Poynting factor, and ideal-solution enthalpies. **The supported nonideal scope
is empty**: no activity-coefficient liquid, no equation-of-state fugacities in either phase, no real chemistry.

**Reasons.**
1. No liquid-capable mixture method exists in this project. PR routes are vapour-only (ADR 0026, ADR 0043 Proposed).
   `iapws95-v1` (S05) and `coolprop-heos-v1` (S07) are pure-fluid and library-only.
2. The column evaluates K **by construction** as a function of (T, P) alone. `LnKBlock` has inputs `("T", "P")` and asks the
   provider for `lnK` at a fixed probe composition (`models/syn001/blocks.py:50–100`).
3. So a liquid-capable provider with composition-dependent K would be evaluated at the probe composition and give a wrong
   answer **silently**. Declared capabilities (phases, properties) cannot catch this, because such a provider would declare
   exactly what SYN-001 declares.
4. Today `validate` and `solve_column` accept any `PropertyProvider` (`models/syn001/column.py:614`), so that path exists.

**S11 (new refusal; build lane WO-S03-1).**
- *Rule.* Before R1 and before any provider evaluation, `validate` reads `provider.describe()` (metadata, not an
  evaluation). Unless `provider_id == PROVIDER_ID` and `reference_convention == REFERENCE_CONVENTION` (the constants in
  `openflowsheet.models.syn001`), it returns `CascadeFailure("CAPABILITY_UNAVAILABLE",
  "unsupported(column_property_method:<provider_id>)", <message naming the supported scope>)`.
- *Where it applies.* The same check guards S01's cascade validation, if that is a separate entry point. `solve_column`
  returns the failure unchanged.
- *What passes.* A wrapper that delegates `describe()` to a SYN-001 provider (the property cache) passes.
- *Why identity, not capability.* Reason 3 above.

**Evidence:** A04 and A05 (§11).

## 10. The decisions S02 deferred

### 10.1 R-533 / R-554 — the block rule and P1's outcome

**Decision.** S03 does not teach the phase contract the block rule, and specifies no model-side signature screen.
R-533 is closed as a **registered limitation**:
- *the column has no phase-transition robustness*;
- a run whose regular signature would be a block other than all-two-phase (S02 §4.3) may end in a typed S01 §4.5 outcome;
- P1 does end that way (`HOMOTOPY_STALLED`; attempt 1 `(2P, L, 2P, 2P, 2P)` breaks the rule);
- that outcome is S02 A12's typed branch, never a success.

**Reasons.**
1. The contract is ADR 0005 D4's single decision function (T05b's owner). A column rule inside it is the model-specific screen
   R-533 and S02 §18.3 declined. A screen around `solve_region` would be a second decision function.
2. No registered column case needs a block signature. RC1–RC5, M1–M4 and S06's J1–J8 are all two-phase at the root. P1 is a
   liquid heater dressed as a stripper.
3. The failure is honest: typed, with every attempted signature in the records (S02 A12).

**Reopening** needs a registered use case whose regular signature is not all-two-phase, and an ADR against ADR 0005 D4. Whether
to schedule that is Frank's call (Q-S03-4).

### 10.2 R-534 — S02's cases and the independent reference

**Decision.** The independent references attach to RC1–RC4, S02's configurations at `P_r`, not to M1–M4 themselves:
- M1–M4 run at a pressure profile both tools cannot express (§3);
- M1–M4 stay matched against the S02 generator only, so S02 §14's "no independent column reference" stays true for them as
  written;
- RC1–RC4 carry both the twin (our side, rule 3) and the tools.

S02 is not amended.

### 10.3 R-508 — S01's cascade

S01 receives no separate tool comparison. Its cascade appears inside RC3 (no condenser, a liquid `top` inlet on an S01 stage)
and RC4 (no reboiler, a vapour `bottom` inlet), and every equilibrium stage of every RC case is an S01 stage.

## 11. Assertions

`ref` = `s03_reference.json`, `cases` = `s03_cases.json`. Tolerances are as stated, with the reason after each table row where it
is not exact.

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A01 | `s03_reference.py --check` passes: every claim holds and both files are byte-identical | 4009 claims; `ref.cases_sha256` = SHA-256 of `cases` | exact |
| A02 | The registered inputs our side and the tools use are `cases`'s, and the classifier's quantity list per case is `cases.cases.<case>.quantities` | equal | exact |
| A03 | Blindness (§8): forbidden strings absent from the tool scripts and their in-repo imports other than T06's SYN-001 definitions; `s03_cases.json` is their only project input file | pass | exact |
| A04 | S11: M1's `ColumnSpec` with each non-SYN-001 provider in `thermo/` that implements `describe()` (`pr_c1`, `pr_lib`, `iapws95`, each built as its own tests build it; one that cannot be built without external data is listed with the reason) and with two spies — (i) `provider_id = "s03-spy"`, `reference_convention = "SYN-001-ref-v1"`, phases LIQUID and VAPOR, properties including `lnK` and `h`; (ii) `provider_id = "syn001"`, `reference_convention = "spy-ref"`. Each spy counts its `evaluate_phase` and `flash` calls | `validate` and `solve_column` return `CAPABILITY_UNAVAILABLE` `unsupported(column_property_method:<provider_id>)`; spy call counts 0 | exact |
| A05 | Not vacuous: the SYN-001 provider, bare and wrapped in the property cache, passes S11. M1's `validate` returns `None`, and S02 A06 still holds | `None` | exact |
| A06 | Our side on RC1–RC5, the ten perturbed cases and PC-P (inputs from `cases`): `CONVERGED`, S02 §8 and S06 §8 accepted, every stage two-phase (RC2: total condenser plus two-phase ×6), every registered quantity within 0.1 × its §6 tolerance of `ref` (`ref.controls.PC-P.ours` for PC-P) | as stated | 0.1 × §6. *Floor:* S02's measured deviations are ≤ 8.5e-3 of this. *Catch:* rule 3 |
| A07 | `ours-<case>.json` reproduces from a live solve | non-floats exact; floats 1e-12 relative | T06 A50's rule (cross-architecture last bits) |
| A08 | Every tool record carries §8's fields and `s03_cases.json`'s settings; every (case, tool) pair registered in §3 and §7.2 has a record (a `NOT_COMPARABLE(capability)` record included) | set equality | exact |
| A09 | The qualification records' commit is an ancestor of `comparison.json`'s commit (manifest fields; checked with `git merge-base --is-ancestor`; without history the test refuses explicitly, per R-555's pattern) | pass | exact |
| A10 | The gate test's recomputed classification of every pair equals `comparison.json` | equal | classifications exact; values and ratios 1e-12 relative |
| A11 | PC-P is `DISAGREE` in each tool where RC1 is available; (PC-L, DWSIM) is `DISAGREE`; (PC-L, IDAES) is `not_applicable`. Rule 2 on a control propagates as §7.2 says | as stated | exact |
| A12 | Rules 2c and 2d actually fire. On each available tool's committed RC1 record, the classifier is run on copies each altered in exactly one raw field: `L[1]` × (1 + 2e-4), which breaks RR's definition, so rule 2c; `L[1]` × (1 + 2e-8), so rule 2d's residual; a stage pressure + 0.01 Pa, so 2c; an accuracy-rerun quantity moved by 0.2 tolerance, so 2d. The unaltered record classifies by rule 4 | the four expected labels; unaltered: rule 4 | exact |
| A13 | `comparison.json` holds the X31 count (§2.3 step 5), the perturbation response table (§7.4), each control's tool-model distance (§7.3) and every `NOT_COMPARABLE`/`DISAGREE` with its reason. No registered pair is missing | present, complete | exact |
| A14 | The classifier's tolerances are §6's formula evaluated unrounded from `ref`'s 25-digit values, with no per-case or per-tool factor (a test feeds a synthetic pair at 0.999 and 1.001 tolerances for each kind) | `AGREE` / `DISAGREE` | exact |
| A15 | S01's, S02's and S06's suites pass unchanged on `wp/S03` | as registered | as registered |
| A16 | `s02_reference.py --check` and `s06_reference.py --check` still pass, since S03's generator imports them | pass | exact |
| A17 | `docs/reviews/S03-verdicts.md` exists, is written by the `verdict` agent, and records §7.5's items | present | — |

## 12. Work orders

Each is about 150k context. Run at most two agents at a time. WO-S03-2 and WO-S03-3 need the rebuilt `.venv-idaes` and
`.venv-dwsim`.

**WO-S03-1 — S11 and our side** (`opus-engineer`, worktree; build lane).
- S11 in `models/syn001/column.py` `validate` (and S01's cascade validation if separate); tests A04, A05, A15.
- An our-side runner that maps `s03_cases.json` to `ColumnSpec` (uniform pressures, inlets, end specifications). It solves
  RC1–RC5, the ten perturbed cases and PC-P with `solve_column` and the SYN-001 provider, and writes `ours-<case>.json`.
- Tests A06, A07, A02 (our half), A16.
- It may read `s03_reference.json`, because these are our tests. It imports no tool code.

**WO-S03-2 — IDAES qualification and runs** (`opus-engineer`, worktree; build lane).
- `s03_qualify_idaes.py`, run in `.venv-idaes` by `s03_qualify.sh`. For each case and control: levels per §2.3, structural
  inspection (§2.4), registered settings (§5.1 rows 13 and 15), the run and the accuracy rerun, and the rule 2–2d values from
  the tool's own record.
- Writes `qualification/idaes.json` and `results/idaes-*.json`, and commits them before WO-S03-4.
- Expected realizations, to be confirmed or refuted by inspection:
  - a partial condenser at L2 (the native condenser with its liquid distillate fixed at 0 and RR as `reflux = RR*·V_1`), or
    at L3 (a `Flash` as the condenser) if L2 fails (§2.3 step 1);
  - total condenser at the bubble point, natively;
  - RC3 and RC4 at L3;
  - RC5's purity as an L2(b) equation.

**WO-S03-3 — DWSIM qualification and runs** (`opus-engineer`, worktree; build lane).
- The same as WO-S03-2 for DWSIM (`s03_qualify_dwsim.py`), including §5.2's blind ladder selection, recorded.
- Expected realizations, to be confirmed or refuted: S02's partial condenser as DWSIM's full-reflux condenser or as a partial
  condenser with its liquid distillate fixed at 0 (L2 a); RC3 as `ReboiledAbsorber`; RC4 as `RefluxedAbsorber`; purity as a
  native product-composition specification.
- DWSIM runs on the pinned .NET 8 runtime, whose support ends on 2026-11-10 (Q-S03-6).

**WO-S03-4 — classifier, gate test, evidence** (`opus-engineer`; build lane).
- The classifier (§7), `comparison.json`, `SHA256SUMS`.
- `tests/test_s03_references.py`: A01, A02, A03, A08–A14.
- `evidence/S03/<commit>/manifest.json` per §13.

**WO-S03-5 — verdict** (`verdict` agent, design lane). `docs/reviews/S03-verdicts.md` (A17).

**Review.** The package's single `reviewer` pass covers WO-S03-1 to WO-S03-4 before the merge. S11 touches validation, and
the classifier decides reference verdicts.

**Rules for every work order.**
1. Nothing scientific is chosen on the build lane. A case a tool cannot express is recorded, not reformulated.
2. A failed run is a result.
3. A tolerance, setting, mapping or case changes only by an amendment of this document.
4. A level or rung is changed only during blind qualification, and every attempt is recorded.
5. Any open choice the build lane must make (a file name, a helper's location) is an isolated commit, logged in
   `docs/S03_BUILD_DECISIONS.md`.
6. A measurement that contradicts this document (for example a floor above §6's assumptions) is reported to the design lane,
   which amends the document. The harness is never bent to fit.

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A16, each citing its id, and A17's document.
- `s03_reference.py --check` passes at the manifest commit (4009 claims; both JSON files byte-identical). The S02 and S06
  generators' `--check` pass too (A16).
- `ruff check` and `ruff format --check` are clean. `scripts/gate.sh` passes before the merge, and CI is green on both
  architectures.
- The manifest lists:
  - each tool's environment fingerprint;
  - the qualification commit and the comparison commit;
  - the SHA-256 of every committed record and of `comparison.json`;
  - the DWSIM rung selected;
  - each pair's level and classification;
  - the X31 count;
  - each control's classification.
- `tested` records that the comparison was run and reproduces. It does not require every pair to be `AGREE`: the
  classification is the measured result, and the verdict is A17's. Every `NOT_COMPARABLE` and `DISAGREE` is listed with its
  reason.
- §14 is listed verbatim as limitations. `reviewed` is set only by the `reviewer`. The X31 verdict and D19's evidence fields
  in `docs/requirements.yaml` are filled from A17's document, not by the build lane.

## 14. What this does not establish

- **Not empirical validation.** SYN-001 is synthetic. An `AGREE` verifies that two independently written implementations of the
  same equations (§5's matched model) give the same root at a registered state. It says nothing about real chemistry, plant
  data or the property model.
- **Only at `P_r`.** At every RC state SYN-001's Poynting factor is 1 and its `v_i (P − P_r)` term is 0. **Our Poynting terms are
  not independently verified.** S02's generator covers them for M1–M4, and the generator is not independent. M1–M4 at their
  own pressure profile have no independent reference (S02 §14 stands for them).
- **Only the registered states.** Five configurations, ten neighbouring states and PC-P. Nothing for another N, feed stage,
  specification pair or state. No uniqueness claim. A tool converging from its own initializer says nothing about our solver's
  robustness.
- **No sensitivity capability.** The perturbation study gives finite-difference responses of three implementations at
  registered states. No derivative of our solution is verified, and S02 §14's "no sensitivity results" stands for the column
  as a capability.
- **Inverse specifications: purity only** (RC5). Recovery and stage temperature (S06) have no independent reference.
- **No phase-transition robustness** (§10.1). No partial dormancy, no subcooled condenser, no total reboiler, no side draws,
  pump-arounds, hydraulics, efficiencies or rate-based models (deferred by the plan).
- **Supported nonideal scope: none** (§9).
- **Refusals are not compared with the tools.** S1–S10 and S11 are our contract (S02 A02–A03, A04 here). The tools' error
  behaviour is not comparable.
- **IDAES at ε = 1e-8 K.** Agreement verifies SmoothVLE's sharp limit only to within that ε (T06 A2).
- **A `NOT_COMPARABLE`** is neither a failure nor a pass of our column. **An L3 `AGREE`** verifies our column against IDAES's
  tray equations as the harness connected them.
- **Blindness is procedural** (§2.1).

## 15. Open questions (each with a default)

1. **Q-S03-1** *Needs a fact* (WO-S03-2 and WO-S03-3 settle it). Can each tool express each RC case at some level?
   **Default:** yes for RC1, RC2 and RC5 in both tools, and RC3 and RC4 at IDAES L3 and DWSIM L1. A case a tool cannot
   express is `NOT_COMPARABLE(capability)`, reported. It is not a reason to change the case.
2. **Q-S03-2** *Needs a fact.* Does some rung of §5.2's ladder pass rule 2d for every DWSIM case? **Default:** yes, at
   `1e-10` or `1e-9`. If no rung passes for a case, the record is `NOT_COMPARABLE(reference_accuracy)` and goes to the design
   lane. §6 is not relaxed.
3. **Q-S03-3** *Needs a fact* (WO-S03-1). Does our side solve every RC case, perturbed case and PC-P within 0.1 tolerance of
   the twin? **Default:** yes. A failure is an S02 or S06 finding, not a relaxed tolerance or a dropped case.
4. **Q-S03-4** *Needs Frank's preference (scope and priority).* In plain words: today, a column whose physically right answer
   has a dry or flooded section (some stages all-liquid or all-vapour) ends in a typed failure, because the phase-switching
   logic cannot find that answer. Should a later package teach it to? **Default: no.** It stays a registered limitation, since
   no registered use case needs it and it would change the shared phase-switching logic (ADR 0005 D4).
5. **Q-S03-5** *Needs Frank's preference (scope).* In plain words: S03 checks one of S06's three new column specifications
   (product purity) against the other simulators, and not component recovery or stage temperature. Should it check all three?
   **Default: purity only.** One case exercises the shared mechanism. Adding RC6 (recovery) and RC7 (temperature) later costs
   two generator cases and two runs per tool, with no change to the rules.
6. **Q-S03-6** *Needs a fact.* Does DWSIM 9.0.5 still run on the pinned .NET 8 runtime after its end of support on
   2026-11-10? **Default:** yes, because the runtime is pinned and runs offline. The DWSIM runs should be done early. A runtime
   failure is rule 1 (`NOT_COMPARABLE(access)`), reported.
7. **Q-S03-7** *Needs a fact.* Does IDAES accept a partial condenser with its liquid distillate fixed at exactly 0 (L2)?
   **Default:** try it first. If it fails to initialize or fails rules 2–2d, fall back to L3 (a `Flash` as the condenser),
   with both attempts recorded (§2.3 step 1).

## 16. Decisions

Register R-628 to R-633.
- R-628: the references and the qualification rule.
- R-629: the cases at `P_r`, the perturbation study and the controls.
- R-630: the tolerances and verdict mechanics.
- R-631: the supported nonideal scope and S11.
- R-632: the block rule closed as a limitation.
- R-633: R-534 and R-508 resolved, and no ADR needed.
