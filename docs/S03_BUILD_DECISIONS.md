# S03 build decisions

Build-lane choices made while executing `docs/derivations/S03-spec.md` §12. Each is an isolated,
revertible commit. Scientific questions are not decided here; they are listed for the design lane.

## WO-S03-3 (DWSIM qualification and runs)

Engineer: build lane, worktree `.claude/worktrees/s03`, branch `wp/S03`.

**B3-1 Files.** `spikes/references/s03_qualify_dwsim.py` (tool script) and
`spikes/references/s03_qualify.sh idaes|dwsim [OUT] [LOG_DIR]` (shared runner; the idaes mode calls
`s03_qualify_idaes.py`, which WO-S03-2 writes). Records go to `benchmarks/s03/references/
qualification/dwsim.json` and `results/dwsim-<case>.json` (§8); the full run log goes to
`evidence/S03/artifacts/s03-qualification/dwsim-run.log` (git-ignored). Alternative: one script
per tool with no shared runner. Reversible by: deleting the runner.

**B3-2 Which modules are "T06's SYN-001 definitions" (A03).** The tool script imports
`t06_fixtures` (constants, flash settings, fingerprint, rule-2 balance), `dwsim_representability`
(the user-compound definition) and `t06_qualify_dwsim` (its `Sheet`, `make_compound` and
`stream_record`: the mapped SYN-001 package exactly as T06 qualified it), plus the loader
`dwsim_runtime`. `t06_fixtures.py` and `t06_qualify_dwsim.py` contain the A03 strings `twin` and
`comparison` in their docstrings, so the A03 test (WO-S03-4) must treat these three T06 modules as
the exempt set. `s03_qualify_dwsim.py`, `s03_qualify.sh`, `dwsim_runtime.py` and
`dwsim_representability.py` contain none of the A03 strings. The script asserts at start that the
imported T06 values equal `s03_cases.json` → `tool_settings.DWSIM` (latent heats, formation
enthalpies, placeholders, NBP, flash settings). Alternative: re-enter the mapping in the S03 script
(rejected: §5.1 row 1 says import). Reversible by: changing the import.

**B3-3 Rule 2d's tolerance inside the tool script.** The rerun movement is divided by
`a_k + 1e-6 |v|` with v = the tool's own value, because the script may read no other value. The
classifier recomputes it from the record's raw fields with the generator value (§8).

**B3-4 "The accuracy rerun converged"** is read as DWSIM's own status at the rerun (no solver error,
every object calculated), the convergence half of rule 2. Rule 2's balance thresholds are applied
to the registered run, not to the rerun; the rerun's balances are in the record.

**B3-5 Methods DWSIM does not know are run, not skipped.** Every ladder rung is attempted with the
name DWSIM's column dispatches on (`Column.SolvingMethodName`): "Napthali-Sandholm (Simultaneous
Correction)", "Russell (Inside-Out)", "Wang-Henke (Bubble Point)", "Burningham-Otto (Sum Rates)".
DWSIM's own error for an unknown name is the recorded result of that attempt.

**B3-6 Selection evaluated on the full matrix.** Every case is run at every rung of its ladder (and
at L2 where L1 found nothing), then §5.2's rule is applied: a rung passing for every case is the
uniform setting, otherwise each case takes its first passing rung at its first passing level.
Alternative: stop at the first uniform rung (same selection, fewer runs). Compute only.

**B3-7 Duty sign conversion.** `Q_condenser = -1000 E(Q-COND)`, `Q_reboiler = +1000 E(Q-REB)` (W,
positive into the stage) from DWSIM's energy streams in kW (condenser: heat removed, reported
positive; reboiler: heat supplied, reported positive). Recorded in every record as
`sign_conversion`; rule 2's energy balance would fail on a wrong sign.

**B3-8 DWSIM realizations tried per level** (structural, recorded with reasons). L1: partial
condenser → `Full_Reflux` (vapour distillate, all liquid refluxed); total → `Total_Condenser` with
0 K subcooling; no condenser → `DistillationColumn.ReboiledAbsorber = True`; no reboiler →
`RefluxedAbsorber = True` (DWSIM 9.0.5's `AddObject` has no case for the absorber object types, so
the flag on its own `DistillationColumn` is the native unit; `ColumnType` is left at DWSIM's value).
Specifications: RR → `Stream_Ratio`; BR → reboiler `Stream_Ratio`; B → reboiler
`Product_Molar_Flow_Rate` (mol/s); Q_r → `Heat_Duty` (kW); purity → `Component_Fraction`, unit
"M" (molar), compound A. D on a partial condenser has no L1 realization (DWSIM's condenser
`Product_Molar_Flow_Rate` is the liquid distillate). L2(a): only RC4's family (partial condenser,
D specified): `Partial_Condenser`, vapour product rate = D*, liquid distillate fixed at 0 by the
condenser specification. L3: not admissible for DWSIM (§2.2).

### WO-S03-3 outcome and questions for the design lane (records: commit 95870140)

Run 2026-10-24, 1404 s, DWSIM 9.0.5 on .NET 8.0.31, fingerprint = `docs/reference-environments.md` §3.

| Case(s) | DWSIM | Level, rung | Note |
| --- | --- | --- | --- |
| RC1, RC1-RR, RC1-z, PC-L | available | L1, (1e-8, Wang-Henke) | rerun moves 0.071, 0.079, 0.093, 0.071 tol |
| RC2, RC2-RR, RC2-B, RC2-z, RC5 | available | L1, (1e-10, Napthali-Sandholm) | rerun 0.000 (RC2 family), 0.017 (RC5) |
| RC1-BR | not available | — | only (1e-8, WH) passes 2-2c; its rerun moves 0.1006 tol (2d) |
| PC-P | not available | — | WH fails DWSIM's own mass-balance check at 1e-10..1e-8, rule 2 balance at 1e-7, 1e-6 |
| RC3, RC3-Q, RC3-z | not available | — | NS: 1000 iterations without convergence at every tolerance |
| RC4, RC4-D, RC4-z | not available | — | L1 not expressible; L2(a) under NS: "Error evaluating error functions" |

Measured facts that bear on the spec (no harness change made; §12 rule 6):
- **F1** DWSIM 9.0.5's `DistillationColumn` dispatches only "Wang-Henke (Bubble Point)", "Modified Wang-Henke" and
  "Napthali-Sandholm" (`RigorousColumn.vb` v9.0.5, ~l. 4807-4855). Russell inside-out does not exist; Burningham-Otto is
  used only by `AbsorptionColumn` (no condenser or reboiler). §5.2's ladder therefore has one method for RC3/RC4.
- **F2** Napthali-Sandholm defines the condenser `Stream_Ratio` as L(0)/LSS(0) and `Product_Molar_Flow_Rate` as LSS(0)
  (the liquid distillate, `NewtonRaphson.vb` l. 442-448), which a full-reflux condenser holds at 0: every RR- or
  D-specified partial-condenser case fails under NS. Wang-Henke's reflux ratio is L(0)/(LSS(0)+V(0)) = L_1/V_1.
- **F3** DWSIM's column checks its own relative component balance at 10 × the column tolerance and errors above it, so
  Wang-Henke passes only at 1e-8 here, and its 10× rerun moves quantities by 0.07-0.10 tolerance.
- **F4** By §7.2, PC-P not comparable for DWSIM makes DWSIM's RC1 and its three perturbation pairs
  `NOT_COMPARABLE(control_not_comparable: PC-P)` in the classifier (WO-S03-4), leaving DWSIM comparable on the RC2 family,
  RC5 and PC-L only.

Questions (defaults are what the records already do):
- **Q3-1** Amend §5.2 for F1 (e.g. a substitute method for RC3/RC4)? Default: no amendment; RC3/RC4 families are
  DWSIM-unavailable. Wang-Henke, outside their registered ladder, was not run into the records.
- **Q3-2** Q-S03-2 answered "no" for 8 cases. Default: records stand as `NOT_COMPARABLE`; §6 not relaxed.

## WO-S03-1 (build lane `opus-engineer`, 2026-10-24; branch `wp/S03-ours`)

- DECISION: where S11 lives → one helper `cascade.property_method_refusal(unit, provider)` in S01's `models/syn001/cascade.py`, called as the first statement of both `cascade.validate` (S01's separate entry point, §9 "Where it applies") and `column.validate`, ahead of R1 and of the misuse `ValueError` checks; the same cause `unsupported(column_property_method:<provider_id>)` from both. Alternative: two copies, or a column-only check with the cascade left open. Reversible by: deleting the two calls and the helper.
- DECISION: A04's provider set → `pr_c1`, `pr_lib`, `iapws95` and also `coolprop_heos` (S07; it is in `thermo/`, implements `describe()`, and builds without CoolProp because `describe()` is computed from constants), plus the two spies; none needed external data, so none is listed as unbuildable. Each real provider is wrapped in a counting delegate that forwards its own `describe()`, so its evaluation count is asserted 0 like the spies'. Alternative: the three providers §11 names only. Reversible by: dropping the `coolprop_heos` entry in `tests/test_s03_s11_refusal.py`.
- DECISION: S11 test file → `tests/test_s03_s11_refusal.py` (A04, A05, the cascade entry point, S11-before-R1), separate from WO-S03-4's gate test `tests/test_s03_references.py`. Alternative: fold into the gate test. Reversible by: moving the tests.
- DECISION: our-side runner → `scripts/s03_references_ours.py` (T06's `scripts/t06_references_ours.py` pattern: `solve(case)`, `write`, `--out`), unit id `S03`, `solve_column` at its default policy (`s01-default-v1`) with a bare `Syn001Provider`. Alternative: a module under `benchmarks/s03/`. Reversible by: moving the file and its import in `tests/test_s03_ours.py`.
- DECISION: `ours-<case>.json` fields → `case`, `side`, `cases_file`, `cases_sha256`, `unit_id`, `provider_id`, `policy_id`, `outcome`, `cause`, `signature` and `quantities` (the registered names of `cases.cases.<case>.quantities`, binary64 via `json.dumps`); no state and no `state_sha256` (§8 "only the fields the comparison reads"; last-bit floats are not a cross-architecture promise, A07). A refusal or non-`CONVERGED` answer is still written, without quantities. Alternative: the full state, as T06's records carry. Reversible by: adding fields to `solve` and regenerating.
- DECISION: PC-L → no `ours-PC-L.json`; `OURS_ALIASES = {"PC-L": "RC1"}` (§3.3 "Our side: RC1's record", as T06's PC-1 → REF-04). Alternative: a copy of RC1's record under PC-L's name. Reversible by: adding PC-L to `OURS_CASES`.
- DECISION: `reflux` (total condenser) → computed as `φ · V_2` from the state, §4's literal definition. Alternative: `Σ_c r_c` (equal at the root to roundoff). Reversible by: one line in `quantity`.
- DECISION: our-side test file → `tests/test_s03_ours.py` (A02 our half, A06, A07, A16); A06 compares in `Decimal` against `ref`'s 25-digit strings with the tolerance recomputed from §6's formula (and checked equal to `ref`'s tolerance string). A16 runs `s02_reference.py --check` and `s06_reference.py --check` concurrently as subprocesses (measured 202 s and 138 s), so the test costs ~3.5 min. Alternative: leave A16 to the gate script outside pytest. Reversible by: deleting the test.
- Measured (2026-10-24): all 16 our-side cases `CONVERGED`, every equilibrium stage `TWO_PHASE`, worst deviation from the twin 3.5e-3 of a §6 tolerance (RC3 `bottom[B]`; RC3-Q 2.3e-3, RC3-z 1.7e-3; every other case ≤ 2.4e-6). Q-S03-3 answered yes. Two runs write byte-identical records.

## WO-S03-2 (IDAES qualification and runs; build lane `opus-engineer`, 2026-10-24; branch `wp/S03-idaes`)

Script `spikes/references/s03_qualify_idaes.py` (commit `787cd4fd`), run by `spikes/references/s03_qualify.sh idaes`
(unchanged); Ipopt logs go to `evidence/S03/artifacts/s03-qualification/idaes-ipopt/` (git-ignored).

- DECISION B2-1: imports → `t06_fixtures`, `t06_qualify_idaes` (both exempt and pinned, §17.6) and `idaes_representability`
  (not exempt; contains none of the seven strings). The script asserts the imported settings equal
  `tool_settings.IDAES` (Ipopt options, ε, placeholders, h_form). Alternative: re-enter the mapping (rejected by §5.1 row 1).
- DECISION B2-2: the L1/L2 boundary → L1 fixes only IDAES's column specification variables (`Condenser.reflux_ratio`,
  `Reboiler.boilup_ratio`, `Reboiler.heat_duty`). Every other specification is an explicit `Constraint` written from S02 §2.1 /
  S06 §2 (L2(b)), including a bottoms rate `L_N − B*` and a stage temperature `T_s − T*`. This matches §17.1's expectations.
  Alternative: count fixing a port or state variable (bottoms flow, a tray temperature) as L1. Reversible by `L1_NATIVE`.
  Levels and comparisons are unaffected (the equations are identical); only the recorded level moves.
- DECISION B2-3: S02's partial condenser → not expressible at L1 or L2, by inspection, without a run (§2.3 step 1; DWSIM's
  precedent for an inexpressible structure). L3 realizes it as a `Flash` whose outlet pressure is fixed at the registered
  value (`deltaP` free), the analogue of `TrayColumn`'s fixed `condenser_pressure`. Its liquid outlet goes to stage 2 by an
  `Arc`, so no liquid distillate exists. This answers Q-S03-7 (below).
- DECISION B2-4: initialization (§5.1 row 12) → recorded in every record (`settings.initialization`):
  - profile-seeded guesses on tray inlets (320 → 400 K, 1 mol/s, the inlet composition);
  - IDAES's own `TrayColumn.initialize()` (L1/L2), or the unit initializers in its order (L3);
  - one full solve with IDAES's initializer solver;
  - **the initializers run at IDAES's default SmoothVLE ε; the registered ε = 1e-8 K is set on every block afterwards**, before
    the final solve and the rerun. Rule 2b checks every block (shift 5.0e-9 K on every passing record).

  Measured on pilot RC2 runs: at ε = 1e-8 K, `TrayColumn.initialize` fails in the condenser's inlet-state initialization (a
  saturated vapour: "bad status: error", then `InitializationError`). This happens with IDAES's default guesses (the feed tray's
  vapour is 1.8e-16 mol/s) and with profile-seeded guesses. T06's application note set ε before the initializers; this
  departs from that note, not from a registered setting. Alternatives tried on the pilot and rejected: an ε continuation
  (1e-4, 1e-6, 1e-8; RC2 ended "Solved To Acceptable Level"), and no full initializer solve. Disclosure: the policy was fixed
  on pilot runs of RC2 and RC3 by convergence alone, before the 18-case run. No comparison exists.
- DECISION B2-5: `OMP_NUM_THREADS = OPENBLAS_NUM_THREADS = MKL_NUM_THREADS = 1` (setdefault, recorded) → deterministic
  linear algebra. Measured: a threaded MUMPS run sat at 1100 % CPU for minutes on the shared host; single-threaded, an RC2 run
  takes 6 s.
- DECISION B2-6: rule 2d inside the script → as B3-3/B3-4. The tolerance uses the tool's own value. "The rerun converged"
  means "Optimal Solution Found". The rerun rebuilds, re-initializes and solves with `floor_rerun` (tol 1e-9, constr_viol_tol
  1e-8), everything else unchanged. The level search stops at the first level that passes, as DWSIM's did.
- DECISION B2-7: the sign → identity: IDAES's `heat_duty` is heat into the control volume (`sign_conversion` in every record).
  Rule 2's energy balance would catch a wrong sign.
- DECISION B2-8: record contents → §8's fields plus every Pyomo variable and every SmoothVLE ε (rule 2b is recomputed from
  these, as in T06), `cases_sha256`, and the failed levels' full records. 19 files, 1.47 MB.

### WO-S03-2 outcome (run 2026-10-24, 63 s, fingerprint = `docs/reference-environments.md` §3)

| Case(s) | IDAES | Note |
| --- | --- | --- |
| RC1, RC1-RR, RC1-BR, RC1-z, RC7 | available, L3 | Flash condenser; reruns move ≤ 0.0069 tolerance |
| RC2, RC2-B, RC2-z | available, L2 | TrayColumn with B as L2(b) for RC2 and RC2-B; RC2-z the same; reruns ≤ 1.8e-5 |
| RC2-RR | not available | L2: "Solved To Acceptable Level" after 8 iterations; L3: 500 iterations |
| RC3, RC3-Q, RC3-z | not available | L3: "Solved To Acceptable Level" after 6–13 iterations |
| RC4, RC4-D, RC4-z | not available | L3: 500 iterations (the initializer's full solve also fails) |
| RC5 | not available | L3: "Solved To Acceptable Level" after 14 iterations |
| RC6 | not available | L2 converged, but rule 2d's rerun moved 0.34 tolerance; L3: local infeasibility |
| PC-P | not available | L3: 500 iterations |
| PC-L | not_applicable | registered (§3.3) |

On every passing record, rules 2–2d are met:

| Check | Worst value |
| --- | --- |
| component balance | ≤ 1.7e-10 mol/s |
| energy balance | ≤ 1.7e-5 W |
| SmoothVLE shift | 5.0e-9 K |
| pressure deviation | 0 Pa |
| specification residual | ≤ 2.1e-15 |
| final constraint violation | ≤ 7e-10 |

**Finding for the design lane (rule 6; T06 §9.5's rule 2b note).** The failures are Ipopt terminations at the registered
ε = 1e-8 K. They are not model errors. The failing final solves stall at residuals of 1e-10 to 1e-5 on the SmoothVLE rows of
the trays' *inlet* state blocks (`_teq_constraint`, `eq_mole_frac_tbub` of `properties_in_vap`/`_liq`). IDAES's `Tray`
re-flashes every inlet, and a saturated inter-stage stream sits at the kink, where ε = 1e-8 K gives curvature ~1/ε. The
dual infeasibility reaches 1.8e14.

The outcome depends on the starting point:
- RC2 converged from one pilot start and ended "acceptable" from another;
- RC6's L2 converged, but its rerun moved 0.34 tolerance.

Consequence under §17.3(b): PC-P, IDAES's only control, is not available, so **every IDAES pair becomes
`NOT_COMPARABLE(control_not_comparable)`**. No harness change was made to rescue a case.

**Q-S03-7 answered (inspection, `qualification/idaes.json` → `q_s03_7_partial_condenser`).** No. IDAES's partial `Condenser`
has no liquid-distillate variable. Its distillate flow is the Expression `(1 − RR/(1+RR))·F_liq`, which is 0 only at
RR = ∞, and its `reflux_ratio` is reflux over the liquid distillate. It also refuses `atBubblePoint`. So L2(a) has no
realization, and every partial-condenser case goes to L3 (Flash): RC1, RC7 and the RC1 family pass there.
