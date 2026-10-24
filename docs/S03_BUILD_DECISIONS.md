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
