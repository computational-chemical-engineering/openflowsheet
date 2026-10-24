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

## WO-S03-3b (DWSIM top-up: RC3, RC4 families, RC6, RC7)

Engineer: build lane, worktree `.claude/worktrees/s03`, branch `wp/S03`. Authority: spec §17.2, §17.4,
§17.6, §17.8, §17.10. Only `s03_cases.json` is read by the tool script.

**B3b-1 Ladder and order (spec-mandated, §17.2).** `ladder()` reads
`column_method_order_amendment_1` (Napthali-Sandholm, Wang-Henke); the Russell and Burningham-Otto
names and `SUM_RATES_BASES` are gone. Positions within a level: tolerance tightest first, then method.
L2(a) positions exist only under a method whose L1 realization was structurally inexpressible. Every
position is recorded in `attempts`: a run, or `structurally_expressible: false`,
`failed_rule: "structural"` with the Q-X6 reason (§17.8 ladder conformance).

**B3b-2 Realization per (level, method).** `realization(case, level, method)` with `end_option()`; the
structural answer can now differ by method. Napthali-Sandholm's condenser `Stream_Ratio` on a
`Full_Reflux` condenser is L(0)/LSS(0), not L_1/V_1, so it is structurally inexpressible (F2; §17.2's
own example), and no run is made. Every failing end's reason is recorded, not only the first.
`levels.<L>.by_method.<method>` holds `realization` and `structural_inspection` for the new entries
(the standing entries keep their method-independent layout). Alternative: one realization per level
and runs under NS that fail (WO-S03-3's behaviour). Reversible by: reverting the commit.

**B3b-3 New specification kinds (§17.4).** Recovery → DWSIM `Component_Recovery` at the reboiler,
value = 100 × r* (DWSIM's percent; recorded in `settings.recovery_percent_conversion`). Its definition
in both methods is `Lj(ns)·xc(ns)(c) / Σ_j zc(j)(c)·F(j)` (NewtonRaphson.vb l. 472-479, BubblePoint.vb
l. 284-290), i.e. l_N's flow of c over the inlets' flow of c: §17.4's. Temperature → DWSIM
`Temperature` only when the named stage is the end stage; DWSIM reads Tj(0) or Tj(ns) only
(NewtonRaphson.vb l. 492-494, 919; BubblePoint.vb l. 291-293, 659-661). Rule 2c stays 1e-4 relative;
rule 2d per kind from `RULE2D_SPEC` (ratio/rate/duty 1e-8 rel, purity 1e-8 abs, recovery 1e-9 abs,
temperature 1e-9 rel); each spec record now carries `rule2d_basis` and `rule2d_threshold`.

**B3b-4 Q-A1-1 measured by the tool script.** `ColumnSpec` has a `StageNumber` property. When a case
has a temperature specification, the script scans the IL of every method in the loaded DWSIM
assemblies for calls to its accessors and records the callers in `settings.stage_number_readers`.
Runner: `s03_qualify.sh` passes arguments after LOG_DIR to the tool script (`--only ...`).

**B3b-5 Top-up output and merge.** The tool script runs the eight cases into
`evidence/S03/artifacts/s03-qualification-topup/out` (git-ignored), so it cannot rewrite a standing
record. `spikes/references/s03_dwsim_topup_merge.py` then checks the eleven standing results files
byte-equal to `95870140` (`git show`; refuses without history), copies the eight records, and writes
`qualification/dwsim.json`: the top-up run's top-level fields; `qualification_runs` with the earlier
run's versions, fingerprint and settings; standing entries verbatim plus `from_commit`, `run` and
`ladder: column_method_order`; top-up entries plus `run` and `ladder:
column_method_order_amendment_1`; the selection recomputed over all 19 cases as a (tolerance, method)
pair, since `rung_index` counts different ladders in the two runs. Alternative: a merge mode inside
the tool script (rejected: the tool script may read no project file but `s03_cases.json`). Reversible
by: deleting the script and rewriting the file.

### WO-S03-3b outcome (records: commit 5474531f)

Run 2026-10-24, 1116 s, DWSIM 9.0.5 on .NET 8.0.31, fingerprint matches `docs/reference-environments.md`
§3. Command: `spikes/references/s03_qualify.sh dwsim evidence/S03/artifacts/s03-qualification-topup/out
evidence/S03/artifacts/s03-qualification-topup --only RC3 RC3-Q RC3-z RC4 RC4-D RC4-z RC6 RC7`, then
`.venv-dwsim/bin/python spikes/references/s03_dwsim_topup_merge.py
evidence/S03/artifacts/s03-qualification-topup/out`. The eleven standing results files are byte-equal to
`95870140`; their qualification entries are verbatim (checked key by key).

| Case(s) | DWSIM | Level, rung | Attempts (every position of §17.2's order) |
| --- | --- | --- | --- |
| RC3, RC3-Q, RC3-z | not available | — | NS: 1000 iterations at every tolerance. WH: DWSIM's own mass-balance error at 1e-10..1e-8; converged at 1e-7 and 1e-6 but rule 2 component balance 1.1e-7..4.0e-7 mol/s (> 3.1e-8) |
| RC4, RC4-D, RC4-z | not available | — | L1 structural under both methods (no native V_1). L2(a): NS "Error evaluating error functions", WH "A convergence error was found while trying to solve the column", every tolerance |
| RC6 | available | L1, (1e-10, NS) | spec residual max 1.5e-16 (recovery absolute, threshold 1e-9; RR relative); rule 2 balance 1.7e-16 mol/s, 1.5e-11 W; rerun at 1e-9 moves 6.6e-9 tol. NS also passes at 1e-9..1e-6; WH fails (2 at 1e-10 and 1e-6, 2d rerun 0.206 and 0.537 tol at 1e-9 and 1e-8, 2d spec residual 2.2e-8 at 1e-7) |
| RC7 | not available | — | structural at every position: NS's partial-condenser RR (F2) and, under both methods, the reboiler Temperature specification is Tj(ns) = T_7, not T_6; no L2(a) |

- **Q-A1-1 answered: no.** DWSIM 9.0.5's column temperature specification is T of the condenser stage or
  the reboiler stage only (source lines in B3b-3). `ColumnSpec.StageNumber` exists, but the tool's IL
  scan (24156 methods in 20 DWSIM assemblies, `settings.stage_number_readers`) finds only
  `Column.GetSolverInputData`, `GetSolverInputData_New` and `Column.get_Specs` touching it, which use it
  as the -1 sentinel of the default distillate-rate specification and in a log line. RC7 is
  `NOT_COMPARABLE(capability: interior-stage temperature specification)` for DWSIM, as §17.12 defaulted.
- **Q-A1-2 answered: no.** Wang-Henke qualifies no case of the RC3 or RC4 families.
- **Q-A1-3 (DWSIM part): yes for RC6.** Recovery residual 1.5e-16 against 1e-9; no DWSIM temperature case
  was runnable.
- Selection over all 19 cases: no uniform (tolerance, method) pair; 10/19 available.
- Disclosure: before the run, the harness was exercised once on RC7 alone into the scratchpad (structural
  positions and the IL scan only; RC7 has no runnable position, so no solver ran). One mistyped runner
  call (`... RC3` without `--only`) was rejected by argparse before DWSIM started. No other run was made.

## WO-S03-1b (our side for RC6 and RC7, spec §17.10)

- RC6 and RC7 are appended after RC5 in `OURS_CASES` (the order of `s03_cases.json`). `column_spec` needed no
  change: the registered `recovery` (component C, 0.99) and `temperature` (stage 6, 368) entries go
  through the existing S06 inverse-specification path in `ColumnSpec`.
- Regenerated all 18 `ours-*.json`. In each of the 16 old records only `cases_sha256` changed, to
  `a0ac8496…3f24fb2` (key-by-key comparison against the prior files; `git diff --numstat` is 1/1 per file).
- Agreement with `s03_reference.json` (A06, tolerance fractions): RC6 worst 2.0e-2 (`bottom[A]`), RC7 worst
  1.1e-6 (`top[B]`), both under 0.1 (Q-S03-3). A06 is parametrized over `OURS_CASES`, so it took both cases
  with no code change; only the docstring and a measurement comment were updated.
- `tests/test_s03_ours.py` + `tests/test_s03_s11_refusal.py`: 95 passed (A02 case-set, A06, A07, A16 included).

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

## WO-S03-2b (IDAES re-run under the path ladder, spec §18; build lane `opus-engineer`, 2026-10-24; branch `wp/S03`)

Script `spikes/references/s03_qualify_idaes.py` (ladder `44efbcaf`, B2b-1 `4163aa5e`, pilot disclosures in the records
commit), run once by `spikes/references/s03_qualify.sh idaes`. P0 check: `spikes/references/s03_idaes_p0_reproduction.py`
(reads IDAES records only: `git show 6d9486a0:…` and the new ones). S1–S6 are B2-4's code, unchanged.

- DECISION B2b-1: `bound_mult_init_method` → passed through Ipopt's options file (Pyomo's `OF_` prefix). Measured (step 3,
  `warm_start_options_check`): the ipopt executable's AMPL keyword interface refuses it ("Unknown keyword"). Ipopt 3.13.2
  accepts it through its options file and validates its value: an invalid value raises `OPTION_INVALID`. `mu_init`,
  `bound_push` and `bound_frac` pass on the command line as before. §18.1's contingency ("if Ipopt rejects …") is
  therefore not applied, because Ipopt does not reject the option, only one of its two input routes does. Alternative:
  apply the contingency (P1 and P2 without it). Reversible by reverting `4163aa5e` and re-running. **Question for the
  design lane** (batched for the `reviewer` pass): does §18.1's "Ipopt rejects" mean the solver or the command-line route?
- DECISION B2b-2: path-dependence ratio (§18.4) → `|q_b − q_a| / tol(kind, q_a)`, where `a` is the earlier position in
  P0, P1, P2 order. Every pair of converged positions is compared, as the rerun's movement uses the base value (B2-6). Each
  level records every pair, the maximum, its quantity and its pair. Alternative: the larger of both values. The difference
  is the 1e-6 relative term, and the classifier recomputes the ratio with the twin's value anyway.
- DECISION B2b-3: rerun and judgement order → every position whose final solve ends "Optimal Solution Found" gets its
  `floor_rerun` (§18.1 order step 2), before rules 2–2d are judged. The failed-rule order is unchanged (2, 2b, 2c, 2d
  specification, 2d rerun). Under B2-6 the rerun ran only after 2–2c passed. No 6d9486a0 attempt converged and then failed
  rules 2–2c, so P0's records are unaffected; the P0 check confirms this.
- DECISION B2b-4: record layout → every position's full record (B2-8's contents) sits under
  `levels.<L>.positions.<P>.{summary, full}` in `results/idaes-<case>.json`. The selected attempt is held once, at the
  record's top level (`solve`, `raw_output`, `rule_values`, `registered_quantities`, `accuracy_rerun`) as before, plus
  `position` and `path_dependence`. `levels` replaces `levels_before`. `qualification/idaes.json` holds the summaries,
  `supersedes`, `pilot_runs`, `warm_start_options_check`, `settings.path_ladder_used` and `p0_reproduction`.
- DECISION B2b-5: a P2 intermediate solve that raises (no iterate to load) ends the position as a recorded failure.
  Alternative: none within §18.1, because the next step starts from the previous step's iterate.
- Pilot runs (all in `pilot_runs`, scratch output only):
  1. The unchanged WO-S03-2 harness on all cases reproduced 20/20 attempts of `6d9486a0` exactly, raw output included,
     before any ladder change. The old harness ignores `tool_variant`, so its "PC-LI" run solved RC1's model.
  2. The option check.
  3. The ladder harness on RC2: P0, P1 and P2 all pass at L2, P0 reproduces, and the path dependence is 2.8e-6.
- DECISION B2b-6: the P0 check at levels the new run did not reach. RC6 and RC2-RR pass at L2 (P1), so §18.1's search
  stops there, and their old L3 attempts have no new P0 counterpart. `s03_idaes_p0_reproduction.py --run-unreached` runs
  those two P0 attempts with the tool script's own `position_attempt`, for the check only. They are not qualification
  attempts, are written to no tool record and cannot change a selection. Alternative: report 18/18 and leave the two
  unchecked. Reversible by dropping the flag; the records do not depend on it.

### WO-S03-2b outcome (one run, 199 s, fingerprint matches; `cases_sha256` `c901d6c9…`)

- **Q-A2-2.** All four warm-start options are accepted, `bound_mult_init_method` through the options file (B2b-1). The
  contingency is not applied.
- **Q-A2-3.** P0 reproduces `6d9486a0` exactly: 20/20 attempts. 18 come from the records, and 2 were run for the check
  (B2b-6). The comparison covers termination, iterations, every rule value, the raw output, the quantities and the rerun.

| Case | IDAES | Level, position | Positions (final solve; rerun movement) | Path dependence |
| --- | --- | --- | --- | --- |
| RC1, RC1-RR, RC1-z, RC7 | available | L3, P0 | all three pass | ≤ 1.2e-5 |
| RC1-BR | available | L3, P0 | P1 converged, but its rerun did not converge (2d); P0 and P2 pass | 1.0e-7 |
| RC2, RC2-B, RC2-z | available | L2, P0 | all three pass | ≤ 2.8e-6 |
| RC2-RR | available | L2, P1 | P0 "acceptable" (8 iterations); P1 and P2 pass | 4.6e-9 |
| RC3, RC3-Q, RC3-z | available | L3, P1 | P0 "acceptable" (6–13 iterations); P1 and P2 pass | ≤ 6.7e-8 |
| RC5 | available | L3, P1 | P0 "acceptable" (14); P1 and P2 pass | 7.8e-5 |
| RC6 | available | L2, P1 | P0 converged, rerun moved 0.34 (2d); P1 and P2 pass with rerun 0 | 1.8e-6 |
| RC4, RC4-D, RC4-z | not available | — | L3: every position hits 500 iterations (RC4's P2 step 1 ends locally infeasible) | — |
| PC-P | not available | — | L3: every position hits 500 iterations | — |
| PC-LI | available | L3, P0 | P1 hits 500 iterations; P0 and P2 pass (rerun 1.9e-5) | 3.6e-8 |
| PC-L | not_applicable | — | — | — |

The path-dependence check excludes no level: the largest ratio is 7.8e-5 tolerance (RC5, P1 against P2), and the threshold
is 0.1. 15 of the 19 IDAES cases are available. Every standing P0 selection stays where it was. The cases that move are
RC3, RC3-Q, RC3-z and RC5 (L3, P1), and RC2-RR and RC6 (L2, P1). PC-P stays not available, and PC-LI runs. The
classification of the controls belongs to WO-S03-4; this script computes no twin distance.

## WO-S03-1c: our side after Amendment 2 (§18.8)

- DECISION: PC-LI → alias of RC1, `OURS_ALIASES = {"PC-L": "RC1", "PC-LI": "RC1"}`; no `ours-PC-LI.json` (§18.3, A02). Alternative: a copy of RC1's record. Reversible by: moving PC-LI to `OURS_CASES`.
- Docstrings of `scripts/s03_references_ours.py` and A02's test updated for the alias; A02's alias assertion extended.
- The 18 `ours-*.json` regenerated. `git diff` shows 1 line added and 1 removed in each file, only `cases_sha256`, now `c901d6c90f4b700b92ff98e2a01ae7e8f1d5557b80dd647e3b14e089d3703f39`.
- `tests/test_s03_ours.py` and `tests/test_s03_s11_refusal.py`: 95 passed (A02 alias test and A07 on the 18 records included).

## Session (orchestrator) decisions after WO-S03-2b

- DECISION: §18.1's "Ipopt rejects" an option → read as the solver rejecting it, not one invocation route. Ipopt 3.13.2
  accepts `bound_mult_init_method=mu-based` through its options file and rejects an invalid value there; only the
  executable's command-line parser lacks the keyword. So B2b-1 (`4163aa5e`) stands and §18.1's contingency is not
  applied. Alternative: read it as the command-line route, revert `4163aa5e` and re-run WO-S03-2b with the
  contingency. Reversible by: that revert and re-run. Put to the package's `reviewer` pass for confirmation.

## WO-S03-4 (classifier, comparison, gate test, evidence; build lane `opus-engineer`, 2026-10-24; branch `wp/S03`)

Authority: spec §6–§8, §11–§13 as amended by §17 and §18. Started after WO-S03-1c and WO-S03-2b (§18.8).

- DECISION B4-1: files → `scripts/s03_reference_comparison.py` (T06's `scripts/t06_reference_comparison.py`
  pattern: `compute()`, `--write`, `--check`, `--markdown`); `benchmarks/s03/references/SHA256SUMS` lists every
  `qualification/*.json`, `results/*.json` and `comparison.json`, paths relative to `benchmarks/s03/references/`.
  Alternative: a module under `benchmarks/s03/`. Reversible by: moving the file and its imports.
- DECISION B4-2: what "recomputes the rule values from the record's raw fields" (§8) reads → the tool's registered
  quantities and every rule 2–2d value come from `raw_output` (DWSIM: `profile`, `streams`, `energy_streams_kW` with
  the recorded sign conversion; IDAES: `stages`, `products`, `inlets`, `variables`, `smooth_vle_parameters`), the
  structural fields (`stage_map`, `feed_stages`), `settings_used.max_iterations`, `accuracy_rerun` and, for §18.4,
  each converged position's `levels.<L>.positions.<P>.full.raw`. `registered_quantities` and `rule_values` (the
  script's summaries) are not read by `classify`; the gate test checks that the script's `registered_quantities`
  equal the recomputed ones (a harness-defect check). DWSIM inlets are the streams tagged `IN*`, products the rest.
  DWSIM's iteration limit: the column's internal and external iteration counts must be below the recorded maximum.
  IDAES pressures: every stage's `P_Pa`, each product's, and every `*.pressure` variable, attributed to its stage by
  the `stage_map` unit prefix. Alternative: trust `rule_values`. Reversible by: reading `rule_values` in `classify`.
- DECISION B4-3: the tolerance in rule 2d's rerun movement, in §18.4's path dependence and in rule 3 → §6's formula on
  the twin's 25-digit value (§18.4 says so for the path; the scripts used the tool's value, B3-3, B2b-2). No pair's
  outcome differs: the largest rerun movements are 0.0931 (DWSIM RC1-z) and 0.00694 (IDAES RC1), as the scripts had.
- DECISION B4-4: §17.3(b)'s "every pair of that tool" → the tool's non-control pairs that reached rule 2 or beyond
  (rules 2–2d and 4). Rule 0 (absent), rule 1 (access) and rule 3 (ours) keep their labels, so §17.5's precedence
  (ours, access before unusable) sees them; the controls keep their own classification (§17.3(c)). Moot on these
  records: both tools have a `DISAGREE` control. Alternative: relabel every pair. Reversible by: `apply_controls`.
- DECISION B4-5: §7.3's control distance to the tool-model twin → divided by §6's tolerance of the tool-model value
  (`ref.controls.<PC>.tool_model`). Alternative: the twin's tolerance (differs by 1e-6 relative of the difference).
  Reported, not classified.
- DECISION B4-6: §17.3(a)'s "the comparison stops" → `comparison.json` is still written, with
  `comparison_stopped: true` and the clause "stopped"; a pair outside §17.5's classes makes the clause
  "undetermined". Neither occurs on these records.
- DECISION B4-7: §7.4's response table → a tool's Δy is given wherever both its records are available, with a
  `both_agree` flag per tool; ours where both of our records are `CONVERGED`; the bound `tol(y_pert) + tol(y_base)` on
  the twin's values.
- DECISION B4-8: A10 → two tests: the document from the committed files equals `comparison.json` (and `SHA256SUMS`)
  byte for byte; the document from a live solve of our side (`s03_references_ours.solve`, aliases applied) equals it
  with every non-float exact and every float to 1e-12 relative (§8, T06 A50's rule). Measured locally: bit-identical.
  A near-zero `|ours − tool|` makes its ratio sensitive to last-bit changes of ours across architectures; if CI's
  second architecture differs there, that is reported, not loosened.
- DECISION B4-9: §17.8 rule 2 ("every `tool_settings` key of that earlier file is present, and equal") and A08's
  settings check → read as "additions only", recursively: every earlier JSON value is present and identical, and a
  mapping may gain keys (§17's preamble; Amendment 1 added `column_method_order_amendment_1` inside
  `tool_settings.DWSIM`, so the literal top-level reading would fail the eleven records §17.8 says stand "by
  construction"). Alternative: top-level equality. Reversible by: `contained()` in the test.
- DECISION B4-10: A03's mechanics → an in-repository import resolves to `spikes/references/<name>.py` (the scripts'
  directory; a module of that name under `src/`, `scripts/`, `tests/`, `benchmarks/` or `docs/` fails the test);
  "`s03_cases.json` is the only input file" is checked statically: the data-file names a scanned module spells
  (string and f-string literals, docstrings excluded) must be `s03_cases.json`, the outputs `idaes.json`,
  `dwsim.json`, `idaes-{}.json`, `dwsim-{}.json`, or DWSIM's own `DWSIM.UI.Desktop.runtimeconfig.json`. Scan points:
  HEAD's working tree and `QUALIFICATION_COMMITS` (95870140, 5474531f, 2eb71ac0); at each, the producing tool
  script must be present.
