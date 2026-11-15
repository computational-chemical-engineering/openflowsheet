# S19 G1 plan: the orchestrator and numerics brain functions (architect, 2026-11-15)

Base `wp/S19` at 082b808e; every number is `codehealth scan`, `arch` or `grep` at that commit, and every line number
is that commit's. Read first: `docs/S19_RULES.md`, `.codehealth/playbook.md`, `docs/briefs/S19-architecture.md` §5.
Where this note is more specific it rules for G1. It stands alone: an engineer needs no other brief for the design.

## 1. Problem and scope

Remove the eight G1 brain functions and bring every G1 file to health >= 7.0, with no change to any floating-point
result, trace event, message, exception or order of side effects.

| function | file:line | NLOC | cog | params | debt | file health now -> expected |
|---|---|---|---|---|---|---|
| `_solve_region` | orchestrator/region.py:630 | 564 | 145 | 21 | 206.4 | 1.1 -> >= 7.3 |
| `_build_screen` | orchestrator/region.py:384 | 100 | 65 | 10 | 61.0 | (moves to region_screen.py, >= 8.0) |
| `solve_newton` | numerics/newton.py:248 | 434 | 115 | 11 | 145.4 | 7.3 -> >= 7.8 |
| `solve_recycle` | numerics/anderson.py:175 | 295 | 126 | 9 | 143.5 | 7.5 -> >= 8.5 |
| `solve_ptc` | numerics/ptc.py:216 | 361 | 90 | 11 | 116.1 | 7.0 -> >= 8.0 |
| `check_agreement` | orchestrator/splits.py:554 | 139 | 95 | 9 | 104.9 | 6.3 -> >= 8.5 |
| `couple` | orchestrator/coupling.py:289 | 159 | 92 | 6 | 92.9 | 7.5 -> >= 8.5 |
| `build_execution_plan` | orchestrator/execution.py:597 | 183 | 82 | 7 | 85.3 | 5.2 -> >= 7.5 |
| (no brain function) | orchestrator/executor.py | 1057 file | | | 60.4 | 5.0 -> 7.0 |

Out of scope: any public signature; the test-pinned private signatures of §2; merging literal twins; ADR 0076 steps
(I-9, I-10 and I-14 touch no G1 body; I-19 gains the re-exports of §4); the other G1 debt, left for the ordinary
by-debt pass (`revision._start_from_pass` 32.0, `mass.resolve_mass` 28.0, `rank.eliminate_alias_rows` 25.9,
`region_problem._region_problem` 19.0, `attempts.solve_with_attempts` 18.6, `ptc._polish` 10.0).

## 2. Constraints and invariants

- Tool (cce-code-health d542005, profile python@0). Brain: cognitive > 40 and NLOC > 70. Debt = (cog-15) +
  0.1(NLOC-70) + 3(nesting-3) + 2(bumps-2) + (params-5), positive parts only; `self` is not a parameter; a closure
  counts in its parent. File health = 10 - penalty: per function complex (cog > 15) 0.5 cap 2.0, brain 1.0 cap
  3.0, long (NLOC > 70) 0.3 cap 1.5, deep nesting (> 3) 0.5 cap 2.0, bumpy 0.5 cap 1.5, many_args (> 5) 0.2 cap
  1.0; file: large (> 1000 NLOC) 1.0, duplication (> 10 % of lines in a repeated 8-line window, repo-wide) 1.0.
  Health >= 7.0 means penalty <= 3.0. Cognitive is complexipy's; the estimates here are +-30 %, the scan decides.
- Bitwise: F0, the MCP digest and every test. The arithmetic rule (architecture note §5) holds inside every new
  helper and method: same operations, same order, no hoisting, no `sum()` versus loop change.
- The literal gate compares the multiset of every string constant over the touched files, `''` and f-string
  parts included. Consequences, binding here: (1) two exits or two records with equal literals are never merged
  into one site, so a helper never returns "the reason" for the caller to issue one refusal where two stood;
  (2) no record-forwarding helper: each `trace.record(...)`, `run.record(...)`, `finish(...)`, `record(...)`,
  `end(...)`, `closed(...)` call keeps its argument text and only moves; (3) `StepResult(index, "solve_eo", ...)`
  x3 and the six start events of `_solve_region` stay twins (playbook 15; named in the commit).
- Test-pinned, not to change in W3: `solve_region` (public, 21 keywords); `_solve_region` is called by keyword
  from `solve_region` through region's global (tests wrap it and read `warm_start`, `state`); `_LiftedOps(**kw)`
  with its 19 keyword names (tests spy `__init__` and rebuild it); `_homotopy(**kw)` with `x0`; the calls of
  `_attempt_screen`, `_build_screen`, `region_ptc_problem`, `_region_problem`; `_swapped_row_test` and
  `check_opening` looked up in region's namespace; executor `_eo_recovery` (9 positional arguments,
  tests/test_t04_edge3.py:450, scripts/t04_evidence_manifest.py:1439), `_region` (`item0_opening_source`
  default), `_bracket`. No test references `_ptc_attempt`, `_external_opening`, `_boundary_unit` or a closure.
- Interleaving fact that decides §3: `problem.residual` (the region's screen) can raise `_KernelRefusedError` or
  a budget error out of a solver loop, and `solve_region` then returns with the trace as written so far. A record
  therefore stays at its place between two evaluations; a helper may not return records for a later write.

## 3. The decision: one recipe for the loop functions, `closures-to-class` (RC)

Five targets (`solve_newton`, `solve_ptc`, `solve_recycle`, `couple`, `_solve_region`) have one shape: a loop whose
closures (`evaluate`, `finish`, `record`, `end`, `entry`, `closed`) share and rebind the enclosing locals, and whose
phases each write events with the run's common fields, advance the counters and may end the call. Extract-phase to
module functions fails on them: each phase needs 8 to 14 inputs and a callback to the closing closure.

Rejected: (B) a frozen frame record plus explicit threading of iterate and counters through every phase
(`ptc._polish` does it with 9 parameters): each signature carries the counters in and out, a missed rebind is a
silent miscount, and `finish`'s refinement mode (it reads `refining`, `chord_linear`, `x` at close time) would
force every branch back into the caller. (C) Pure helpers only (the G2 ruling's form, caller writes every table):
applied where a block is pure (A1, C1, K1, E1), but the interleaving fact forbids it for the trial loops, and the
remainders stay at cognitive 60 to 90. (D) Forwarders that merge records: refused by the literal gate.

Chosen: the closures and the state they share move into one private dataclass per function; phases become its
methods. Rules (binding; the reviewer checks each):

- RC1. A non-frozen `@dataclass`, defined directly after the function it serves, methods in order of first call
  (playbook 5). No explicit `__init__`.
- RC2. Fields are (a) the frame: values fixed for the call, never assigned after construction (`grep
  "self\.<name> ="` over the class is empty for each); (b) the state: exactly the locals that survive an iteration
  or that a closing closure reads. What one phase hands the next inside an iteration is never a field: it is a
  parameter or a return value, a NamedTuple when three or more values made by one phase travel together.
- RC3. The first step on a function moves the closures and the state and nothing else. Allowed differences:
  `run.`/`self.` prefixes; `nonlocal` lines gone; closure `def` lines; initialisers that become constructor
  arguments or field defaults (same expressions, same order of evaluation); one declared rename when a closure's
  name relied on its scope. Two scratch checks, quoted in the commit: (i) the token stream of the base function
  equals that of the head function plus its methods after deleting those differences; (ii) below the constructor
  call no bare `Name` node of a state field remains (a stale local read passes (i), so (ii) is required).
- RC4. A phase method is a whole unit: its records, counter updates and exits move together (playbook 2). One
  that may end the call returns `Result | None` (None: the call goes on) or `T | Result` dispatched by
  `isinstance`; the loop keeps the `return`. No callback parameter, no kind flag, no list or dict of the caller
  to fill. A method that only computes says "pure" in its docstring.
- RC5. Site counts are equal over the function at base (its lines in §5) and over the function plus its class
  at head (`grep -c`, the `def` line included): newton `finish(` 19, `trace.record(` 8;
  ptc ` record(` 11, `trace.record(` 6; anderson `finish(` 8, `trace.record(` 5, `record_trial(` 3; coupling
  ` end(` 11, `entry(` 7; region `closed(` 6, `run.record(` 7 (after P1's rename the ptc name changes, not the
  count).
- RC6. No local alias of a state field across a call that may rebind it. Aliases of frame fields are fine (mypy
  narrowing of `self.recovery`).
- RC7. New methods and helpers stay under every threshold (cog 15, NLOC 70, nesting 3, params 5), except the
  closing method, which keeps the closure's parameter list (`finish` 9, `record` 9).

Step classes: P = pure extraction (S1 cadence, a review every 3 accepted steps). CF = a step that moves an exit, a
record, an evaluation or loop-carried state of a numerics or region brain function: a `reviewer` pass before the
next step on that function. Every G1 step is made by the Opus engineer.

## 4. Restructure RS: `split-region-2` (before any function step on region.py)

Needed: region.py is 1272 NLOC, the RC steps add about 135, and no function step can remove the large-file
penalty. Plan `.codehealth/restructure/split-region-2.toml`, statements moved verbatim:

| new module | statements (region.py lines) | reaches |
|---|---|---|
| `orchestrator/region_result.py` | `RegionAttempt`, `AttemptSystem`, `RegionResult`, `RecoveryStart` (248-334) | other packages only |
| `orchestrator/region_screen.py` | `_attempt_screen`, `_screen`, `_build_screen` (336-520) | region_phase, region_problem |
| `orchestrator/region_attempts.py` | `region_ptc_problem`, `_ptc_attempt` (1302-1420), `_homotopy`, `_boundary_unit` (1462-1620) | region_screen (`_attempt_screen` x2), region_result (`RecoveryStart`) |

Stay in region.py: `syn001_lifted_splits`, `solve_region`, `_solve_region`, `_swapped_row_test`,
`_external_opening` (its `check_opening` call is patched in region's namespace). region.py re-exports every moved
name (old paths stay until I-19). `new_public`: the four record types, `region_ptc_problem`.
Expected, to be re-derived by simulation at the plan's base; a mismatch stops the lane: `codehealth arch` 6
violations / 4 cycles / 14 cycle edges (unchanged); region.py about 790 NLOC, no size smell (the gain: size-smell
weight 1 -> 0); debt over the touched files unchanged at 350.5; region_attempts about 250 NLOC, health about 7.4
(duplicated signature lines, concentrated: a note, not a failure); region_screen 6.3 until S2.
Orchestrator commits before the plan commit, in this order: (1) config: the forbid rule
`verifier-not-through-the-solver` gains the three modules (ADR 0076 I-8); (2) retarget: every patch of
`region.<name>` in tests and scripts whose call site moves gets the new module as well. Known:
`solve_newton` (tests/test_t05b_release_opening.py:120, scripts/t05b_evidence_manifest.py:6850: the corrector's
call inside `_homotopy` moves, the Newton attempt's stays, so both modules), `_admissible`
(tests/test_t03_contract.py:1309-1311 gains region_screen). The inventory is by grep over the call sites of the
moved statements, not by `patch_noop.py` alone: region.py's private re-exports hide a dead patch from it (R-B1
note 2). Source-reading tests: `grep -rn "orchestrator/region.py\|\"region.py\"" tests scripts`, add the three
modules, with the falsifier of S19_RULES. After the step: `patch_noop.py` 0 flagged; a `--no-gain` follow-up for
section headers and docstrings that name region.py as a moved name's home (playbook restructure 1).
STOP if a closure reaches a name that stays, or if a test reads `__module__` of a moved class.
No second restructure is planned. Fallback if region.py measures over 1000 NLOC after R6: move `_swapped_row_test`
(24 NLOC, no retarget: the call stays in region) with a one-statement plan; then `_external_opening` (34 NLOC, with
a `check_opening` retarget).

## 5. The functions

### 5.1 `_solve_region` (region.py:630-1265), steps R1 to R7, all CF

Phases: A 654-675 guard, trace, identity, PTC mapping refusal (T04 §7.1-7.2); closure `new_context` 677-681;
B 683-706 contract setting (owners, v2, PH defect, dormancy); C 708-802 the start (supplied state 708-714,
recovery override 715-718, §6.2 projection 719-755, §7.8 (ii) fixed point 756-802); D 803-840 start records
(accepted 803-814, §6.5 band routes 815-840); E 842-884 ledger and closure `closed`; loop 886-1263: F1 887-897
§7.1 guard; F2 898-923 layout, square check; F3 924-966 external-opening checks; F4 967-970 pins, `opened_at`;
F5 971-1023 core, context, `AttemptContext`, `attempt_opened`, wall; F6 1024-1121 the three cores; F7 1122-1127
end state; F8 1129-1170 `_LiftedOps`, `decide`, three handlers; F9 1171-1186 swapped rows; F10 1187-1238 attempt,
checkpoint, provenance; F11 1239-1263 converged, terminal, restart.

Structure: a run class. Example signature (frame: the arguments and phase B's values; state: 15 fields):

```python
@dataclass
class _RegionSolve:
    """One `_solve_region` call after its contract setting: what every attempt reads, and what the attempts hand on."""
    compiled: CompiledProblem; spec: ProblemSpec; region: Region; splits: Sequence[LiftedSplit]   # frame
    provider: PropertyProvider; policy: SolvePolicy; run: Trace; identity: tuple[str, str]; scaling: Scaling
    structure: ...; active_splits: list[LiftedSplit]; v2: bool; ph_units: frozenset[str]; forms: ...; vapour: ...
    temperatures: ...; dormancy: ...; order: ...; recovery: RecoveryStart | None; compile_level: ...
    region_mass: RegionMass | None; initializer_source: str | None; warm_start: bool
    current: dict[str, float]; source: OpeningSource                                              # state
    regimes: dict[str, Regime] = field(default_factory=dict); projections: list[str] = field(default_factory=list)
    counters: Counters = field(default_factory=Counters); used: ...; attempts: ...; provenance: ...; contexts: ...
    checkpoint: Checkpoint | None = None; message: str = "initial"; trial: Candidate | None = None
    opened_at: ... = None; budget: str | None = None; homotopy: HomotopyRecord | None = None
    def closed(self, outcome: SolveOutcome, text: str = "", system: AttemptSystem | None = None) -> RegionResult: ...
    def attempt(self, attempt_index: int) -> RegionResult | None: ...
```

- R1 (RC): closure `closed`, the ledger 842-853 and `current`, `regimes`, `projections` become the class; it is
  built where 713-714 stood. `new_context` becomes module `_new_context(identity) -> EvaluationContext`, called at
  the same two places (683 and in the loop). Phase B's locals stay locals. Invariant: RC3 (i), (ii); the ledger
  initialisers now run before the start, and the commit states they are pure (`Counters()`, empty lists,
  constants, the `source` conditional); `'initial'` count stays 2. Debt 206 -> about 200 (enabling step).
- R2: C from 715 and D. `_open_start(self, context, reference, band_routes) -> RegionResult | None` (None: attempt
  0 may open); `_start_answer(self, context, split) -> tuple[Regime, Mapping[str, float] | None]` (pure; `None`:
  the PH-type split is not re-projected, §6.4); `_settle_start(self, context, reference) -> RegionResult | None`.
  The caller keeps `supplied_items` (712) and the `return`. Invariant: each projection record follows its own
  kernel call and precedes the next split's; `_branch_found` is still called twice; line 737's test is verbatim;
  the not-settled result carries `dict(current)` and the projections so far. Debt -> about 165.
- R3: F1 to F5. `_check_dormancy(self, attempt_index) -> None` (raises the defect; `if self.v2` stays in the
  caller); `_layout(self) -> _Layout` (pure; NamedTuple `opening, items, running, pinned, dropped, labels, free,
  rows, attempt_rows`); `_external_refusal(self, attempt_index, layout) -> RegionResult | None` (both checks and
  the warm start's accepted record); `_open(self, attempt_index, layout) -> _Opened` (NamedTuple `continuing,
  core, context, memo, x0, opening_hash, wall`). The caller keeps `used.append(layout.opening)` and the square
  check. Invariant: `used.append` now follows the pure layout, with no catch site in between (stated); two
  `"INITIALIZATION_FAILED"` literals remain; `opened_at` holds copies; `contexts.append` precedes the
  `attempt_opened` record. Debt -> about 125.
- R4: F6, F7. `_run_homotopy`, `_run_ptc`, `_run_newton(self, attempt_index, layout, opened)`;
  `_take_end_state(self, layout, last) -> dict[str, float]`. The three-way dispatch stays in the caller.
  Invariant: every keyword of `_homotopy`, `_ptc_attempt`, `_attempt_screen`, `_region_problem` and
  `solve_newton` is unchanged; `base=` and `current` pass the same dict object (no copy added or dropped);
  `self.homotopy` is set as before. Debt -> about 100.
- R5: F8, F9, F10. `_decision(self, attempt_index, layout, opened, last, ended) -> Decision`;
  `_append_attempt(self, layout, ran, decision, ended)`; `_checkpoint_and_provenance(self, attempt_index, layout,
  opened, ran, decision)`, with `ran` a NamedTuple `last, homotopy, ptc` made at the dispatch. Invariant: the
  `_LiftedOps` keywords are unchanged; the three handlers keep their order and the budget handler still sets
  `budget`; the swapped-row test runs only on `converged and v2`. Debt -> about 60.
- R6: the loop body and F11 become `attempt(self, attempt_index)`; `_solve_region` keeps the `for`, the `return`
  and the final `raise`. Invariant: on a restart `current` and `regimes` are new dicts from the conversion, and
  `message`, `source`, `trial` are rebound as before. Debt -> about 24.
- R7 (optional): `_resolved_mass(policy, recovery, mass_mapping, spec, region) -> RegionMass | MappingRefusal |
  None` and `_check_ph_columns(active_splits, ph_units, temperatures) -> None`. Invariant: the mapping refusal
  still precedes `Scaling.from_spec`. Debt -> about 17 (parameters 16).

Risks: fourteen values cross attempts (R1 makes them fields, nothing else may); `current` is rebound and also
mutated in place, and `ended`, `opened_at` and the result state are copies taken at fixed moments; five `closed`
exits plus two direct `RegionResult` returns; `_KernelRefusedError` leaves through `solve_region` with the supplied
state; `attempt_index` reaches records, checkpoint ids and provenance; `counters` is replaced by `last.counters`.
End state of region.py, checked by scan: NLOC <= 1000; at most 2 functions over 70 NLOC, 1 over cognitive 15, 3
over 5 parameters. The duplication smell stays (signature twin, six start events): penalty <= 2.7.

### 5.2 `_build_screen` (region_screen.py after RS), steps S1, S2 (CF)

Closures `screen`, `reported_signature`, `screened_regime`, `asked`, `tp_regime` over ten captured values.
- S1: lift the two closures that read only `provider` and `context`: `_tp_flash_regime(provider, context, split,
  state, *, leaving=False) -> PhaseSignature | Evaluation` and `_band_screened_regime(provider, context, split,
  state) -> Regime | Literal["tp"] | None`. Calls unchanged in order. Debt 61 -> about 40; no longer brain by NLOC.
- S2: frozen dataclass `_TrialScreen` with the ten parameters as fields; `__call__(self, state)` (the old `screen`,
  both handlers), `_reported_signature`, `_unit_report(self, split, state) -> PhaseSignature | Evaluation` (the
  per-split ladder, each `append; continue` rung becoming a `return`), `_asked` (owns the `memo` write).
  `_build_screen` keeps its signature and returns `_TrialScreen(...)`. Invariant: the seven rungs in order (dormant
  feed; leaving `ZERO_FLOW`; `TWO_PHASE`; admissible; PH band answer; PH full closure; TP flash), an `Evaluation`
  passes through from rungs 2 and 7, and `_items(dormancy, state)` is appended after the last split. Debt -> about
  5. STOP if a test reads `__name__` or `__closure__` of the screen.

### 5.3 `solve_newton` (newton.py:248-728), steps N1 to N4 (CF)

Phases: N0 275-296 set-up; closures `digest` 297, `evaluate` 300, `finish` 305-362; N1 364-378 first evaluation;
loop 380-726: N2 381-383 norms; N3 385-468 §5.2 test and ADR 0018 ladder; N4 470-478 budget; N5 480-494
stagnation; N6 496-540 Jacobian and its evidence records; N7 542-586 linear solve; N8 588-607 bound-aware step;
N9 609-700 line search; N10 702-714 observer close; N11 716-726 search failed.
Structure: `_NewtonRun`; frame `problem, policy, trace, signature, attempt, observer, compare_empty, opened,
tolerance, lower, column_tolerance`; state `x, values, accepted_any, running, merits, kept, refining,
chord_linear`. Example: `def finish(self, outcome, values, *, message="", budget=None, linear_reason=None,
iterations, accepted_any, blocked_by=(), linear=None) -> NewtonResult` (the closure's list, unchanged).
- N1 (RC): the three closures and the eight state locals. `evaluate` keeps returning `(evaluation, running)`
  and callers keep the tuple assignment (no simplification in this step). Debt 145 -> about 132.
- N2: N3 becomes `_closing_at_convergence(self, iteration, array) -> NewtonResult | None` and `_refinement(self,
  iteration) -> NewtonResult | None` (ADR 0018 D2 to D4; None: D3's one more iteration). Invariant: `chord_linear`
  is assigned only by the `_chord` unpacking inside the `try`, so a failed back-solve passes the earlier record;
  `refining` is cleared before each `finish` exactly where it was. Debt -> about 100.
- N3: N5 `_stagnation(self, iteration) -> NewtonResult | None`; N6 `_jacobian(self, iteration, infinity, merit)
  -> tuple[sp.csc_matrix, sp.csc_matrix] | NewtonResult` (unscaled, scaled); N7 `_linear_step(self, iteration,
  scaled, infinity, merit) -> npt.NDArray[np.float64] | NewtonResult`. Invariant: each `running.plus` precedes the
  call it counts; `scale_residual` stays between the evidence records and the factorization count. Debt -> 78.
- N4: N9 `_line_search(self, iteration, merit, step) -> bool | NewtonResult`, `step` a NamedTuple `direction,
  step_scaled, alpha_max, landing` made after N8; `_rejection(self, evaluation, alpha, merit) -> tuple[
  RejectionReason | None, tuple[float, ...] | None]` (pure, 640-650); `_reject`, `_accept` (record, observer,
  state); N10 `_closed_by_observer(self, iteration, accepted) -> NewtonResult | None`. N4, N8, N11 stay in the
  loop. Invariant: `alpha_max / (2.0**halving)`; the merit of an accepted trial is computed again after the
  classification, as now; `iteration + (1 if accepted else 0)`. May be delivered as two steps. Debt -> about 20.
Risks: `finish` turns any exit inside a refinement into `CONVERGED` at `x_k`; `x` is rebound on a revert; `kept`
exists only with a refinement; the result holds `x` by reference.

### 5.4 `solve_ptc` (ptc.py:216-607), steps P1 to P4 (CF)

Phases: P0 239-247; closures `digest`, `evaluate`, `met`, `record` 249-308; P1 310-320; loop 322-604: P2 323-326
norms; P3 328-351 stop and polish; P4 353-361 budget; P5 363-397 Jacobian, mass, record, rhs; P6 399-542 retry
loop (one trial 402-482, rejection 484-526, shrink and stall 527-542); P7 544-590 accept, SER, records; P8 592-604.
Structure: `_PtcRun`; frame `ptc, problem, settings, trace, signature, attempt, observer, compare_empty,
tolerance, lower, sigma`; state `x, values, running, tau, steps, rejections`. `_Closed = tuple[NewtonResult,
PtcRecord]`. Example: `def _trial(self, k, tau_try, frozen) -> _Accepted | _Rejected | _Closed`.
- P1 (RC): closures and state; the one rename `record` -> `close`. Debt 116 -> about 105.
- P2: P3 `_stop(self, k) -> _Closed | None`; P5 `_frozen(self, k, scaled_residual, infinity, merit) -> _Frozen |
  _Closed`, `_Frozen` a NamedTuple `jacobian, mass, rhs, infinity, merit` (§7.3: formed once per pseudo-step).
  Dispatch by `isinstance(out, _Frozen)`. Debt -> about 85.
- P3: P6 as `_accepted_trial(self, k, frozen) -> tuple[_Accepted, float, int] | _Closed` (owns `tau_try`,
  `retry`, the stall exit), `_trial` (one factorization, bound, evaluation, classification) and `_reject(self, k,
  retry, tau_try, rejected) -> None`. `_Accepted` replaces the 5-tuple; `_Rejected` is `reason, alpha, blocked,
  trial, evaluation, step_inf, message`. Invariant: `tau_end=tau_try` on the trial-error and stall exits; the
  factorization is counted before `solve_linear` also when it fails. Debt -> about 21.
- P4: P7 `_accept(self, k, accepted, tau_try, retry, phi) -> None` (SER lines verbatim), P8
  `_closed_by_observer(self, k) -> _Closed | None`. Debt -> about 9.
Risks: `tau` moves only on an accepted step that fails the stop test; `iterations` is `k` or `k + 1`;
`accepted_any = bool(steps)`; the polish returns its own counters.

### 5.5 `solve_recycle` (anderson.py:175-507), steps A1 (P), A2 to A4 (CF)

Phases: A0 198-222; closures 224-304; loop 308-507: Aa 309-318 status, norms, best; Ab 320-322 convergence; Ac
324-352 stagnation and restart; Ad 354-367 oscillation; Ae 369-375 observer, budget; Af 377-409 history and
filtered least squares; Ag 410-445 event and record; Ah 447-456 step length; Ai 458-489 halving loop; Aj 490-507.
- A1 (pure): `_mixing(history_x, history_f, f_hat, rules, n) -> _Mixing` for 380-406, `_Mixing` a NamedTuple
  `step_hat, depth, by_condition, by_coefficient, kappa, gamma_inf, dropped`. The appends and the plain-step
  fallback stay. Invariant: the generator `sum(...)` and `history_x[-1] + rules.beta * f_hat - correction` are
  verbatim. Debt 143 -> about 128.
- A2 (RC): `_RecycleRun`; frame `problem, rules, signature, observer, keep_trajectory, trace, attempt, n, scale,
  tolerance_hat, lower`; state: the eighteen set-up locals and `current`. `k` stays the loop's local. Example:
  `def finish(self, outcome, k, residual, message="") -> RecycleResult`. Debt -> about 110.
- A3: `_measure(self) -> npt.NDArray[np.float64]` (Aa after the status check: norm, trajectory, best; returns
  `f_hat`); `_stagnation(self, k) -> RecycleResult | None` (Ac); `_oscillation(self, k, f_hat) -> None` (Ad).
  Debt -> about 71.
- A4: `_accelerated_step(self, k, f_hat)` (Af's appends, `_mixing`, fallback, Ag); `_alpha_max(self, direction)
  -> float` (pure); `_landed_trial(self, direction, alpha, alpha_max)` (pure); `_search(self, k, direction,
  alpha_max) -> tuple[npt.NDArray[np.float64], Evaluation, float] | None`; `_accept(self, k, direction, alpha)`.
  The `BOUND_BLOCKED` and `LINE_SEARCH_FAILED` exits and `landings += 1` stay in the loop. Debt -> about 13.
Risks: `calls` and `running` both count an evaluation; a restart clears the history before the append;
`previous_f` is set every iteration; `invalid` counts non-ok trials only; every record is guarded by `trace`.
Twin, not merged: `_alpha_max` and newton's `_bound_aware_alpha` (playbook 15).

### 5.6 `couple` (coupling.py:289-467), steps C1 (P), C2 to C4

Phases: C0 307-335; closures `entry`, `end` 337-365; loop 368-467: Ca 369-370; Cb 371-420 trial loop (experiments
385-405, backtrack 415-420); Cc 422-429 converged, max_outer; Cd 430-452 reset or Broyden update; Ce 453-467 step.
- C1 (pure): `_experiments(units, inner, evaluate, w, block) -> _Experiments` for 385-405, a NamedTuple `answers,
  entries, r_hat, rho, refused, transient`. The caller writes the record and issues both exits. Debt 93 -> 76.
- C2 (RC): `_Outer`; frame `units, block, solve_inner, evaluate, scales, lower, upper, m2`; state `u, b_matrix,
  best, base, reset_last, k, accepted_count, record`; methods `entry`, `end`. Debt -> about 72.
- C3: `_trial(self) -> _Trial | CouplingRun` (Cb; `_Trial` is `inner, r_hat, rho, answers, item`). Debt -> 37.
- C4: `_update(self, point, inner) -> tuple[_Point, str] | CouplingRun` (Cd) and `_advance(self, step_from, kind,
  trial) -> CouplingRun | None` (Ce). Three `"broyden_singular"` sites remain. Debt -> about 3.
Invariant: `base.u + 0.5 * (u - base.u)` and the Broyden expression verbatim; `item` is mutated after `entry`
returned it; `k` is the same for every entry of one trial loop.

### 5.7 `check_agreement` (splits.py:554-732), step K1 (P), K2 optional

A rule table: restructured whole, one `_check_<subject>` per rule in rule order (S17 form b5451805). New, each
after the caller in call order: `_squared_rows(spec, row_units)`; `_check_registered(models, splits, owners,
squared)` (a, a') 612-618; `_check_keys(models, splits, owners)` (a'') 619-623; `_check_authored_rows(split, rule,
authored, row_units, row_kinds)` (b) 630-652, under the caller's `if split.unit not in owners:` with the (b')
comment; `_check_columns(split, columns)` (c) 653-664; `_check_definitions(split, declaration)` (d)
665-675; `_check_equilibrium_reads(split, rule, declaration)` (e) 676-703, both loops verbatim; `_zero_flow_form(split, forms,
owners, row_units) -> ZeroFlowForm` and `_check_zero_flow_label(split, form, columns, declaration)` (f) 704-727.
Invariant: 14 `raise ValueError` sites; per split the order b, c, d, e; then f over all splits, g, h.
`squared[split.unit]` is now read before the pure row sets: it cannot raise because (a) holds. Debt 104.9 -> 4.0.
K2: `_check_vapour_only_forms` (cog 25) by one extraction.

### 5.8 `build_execution_plan` (execution.py:597-802), steps E1 to E3; cadence 8 (not S1)

Phases: Ea 612-620; Eb 622-638 specification regions; Ec 640-644; closure `region_step` 646-672; loop 674-781
(owned node 675-680; single unit 681-689; loop lookup 691-696; `method: eo` 697-704; tear 706-726; inner system
727-743; converge step 744-781); Ed 783-802.
- E1 (pure): `_claimed_regions(specifications) -> dict[str, Region]`, `_check_specifications(specifications,
  capable) -> None` (capability before squareness, per region). Debt 85 -> about 70.
- E2 (parameter object, built in one phase where 640-644 stand): frozen `_PlanBasis(label, policy, declaration,
  report, scaling, capable, retained, loops)`; `_region_step(basis, region, index, suffix) -> PlanStep`. -> 64.
- E3: `_loop_step(basis, graph, node, index) -> PlanStep` (691-781), with `_loop_tear(basis, graph, node, loop)`
  and `_inner_system(basis, loop, tear_variables, tear_rows)` (pure). `index` is `len(steps)`, read once per
  step as now. Invariant: 6 `raise` sites over the function and its helpers, in the same order per node. Debt -> about 8.
- E4 (optional): `condensation_order` (cog 16) under 15.

### 5.9 executor.py, steps X1 to X6 (refactor, cadence 8)

Penalty now 5.0: large 1.0, duplication 1.0, complex 0.5, long 1.5 (six functions), many_args 1.0. Function-level
work can only clear complex and long: target exactly 7.0. One step per function, largest first:
`_solve_revision_region` (100 NLOC, cog 17), `_eo_recovery` (90), `_revision_continuation` (83), `_converge` (79),
`execute_plan` (77), `_region` (75): each to NLOC <= 70 and cognitive <= 15 by one whole phase its docstring
names (playbook 1, 2, 7). This note does not fix those helper names (the bodies were not read for it): the
engineer states the phase and signature in its X1 report before X2. STOP and report, do not fragment, when a
function has no named phase of 10 NLOC or more. Twins stay: `StepResult(index, "solve_eo", ...)` x3, the
`checkpoint=recovered.checkpoint ...` block x2. The structure it needs is out of W3's reach because
`_eo_recovery` is test-pinned: a frozen `_PlanRun(flowsheet, spec, policy, run)` built once in `execute_plan`,
e.g. `_solve_eo(ctx, index, region, spent, starts)`, then a split of the EO-recovery edge (question Q4).

## 6. Order: two lanes in parallel (disjoint files), runs of at most 3 steps plus follow-ups

Lane N, branch `wp/S19-g1n` (numerics): run 1: A1, N1, P1. Run 2: A2, N2, P2. Run 3: A3, N3, P3. Run 4: A4, N4,
P4. A review after each run; the first one also rules on the RC form (Q1). Each run has one step per solver, so
the CF rule holds.
Lane O, branch `wp/S19-g1o` (orchestrator): run 1: K1, C1, E1 (no RC step; the orchestrator prepares RS's config
and retarget commits meanwhile). Run 2: RS (plan, step, `--no-gain` follow-up; the reviewer reads the retarget and
the split). Run 3: R1, S1, C2 (not before lane N's first review). Run 4: R2, S2, E2. Run 5: R3, C3, E3. Run 6:
R4, X1, X2. Run 7: R5, X3, X4. Run 8: R6, X5, X6. Run 9: R7, C4, K2, E4 and review notes. One region step per run.
Lane O's reviews may be read together with lane N's of the same number. The K, C, E and X steps touch no region
file, so they may run as a third lane if the orchestrator wants lane O shorter.

## 7. Verification gates

1. Before the first step on each function, the gate's self-test must detect a mutation inside it: `gate.sh
   --self-test` on newton.py:611, anderson.py:489, ptc.py:326, coupling.py:419, region.py:737 (five runs, each
   "detected"). On a miss try one other literal of the function; two misses mean the suite does not see that
   loop: stop that function and report.
2. Every step: `gate.sh` PASS (suite by the test map, F0, literal multiset, public API, ratchets, debt drop over
   the touched files). R1, N1, P1, A2, C2 are enabling steps with a small drop (about 5 to 15).
3. RC steps: checks RC3 (i) and (ii) quoted; RC5's counts equal at every step of that file.
4. RS: `--restructure` PASS with arch 6 / 4 / 14; `patch_noop.py` 0 flagged; the falsifier line quoted.
5. Per function at its last step, from the scan: `brain` false; cognitive <= 30 (a value of 31 to 40 is reported
   as a miss of this plan, not hidden); function debt within 10 of §5's estimate, else explained in the report.
6. At the end of G1: 0 brain functions in orchestrator/ and numerics/; every file there >= 7.0, with region.py >=
   7.3, executor.py = 7.0 and the others as §1; region.py <= 1000 NLOC; F0 identical on the merged branch.

## 8. Risks and open questions (each with a default)

- Q1, design-lane ruling (judgment): the RC form writes trace records inside phase methods, where the G2 ruling
  kept every table write in the caller. Default: accepted for the five loop functions under RC1 to RC7; the
  reviewer of lane N run 1 confirms before any other RC step. If refused: revert N1 and P1, stop both lanes'
  RC steps, keep the pure steps (A1, C1, K1, E1, E3, S1).
- Q2, fact: region.py's NLOC after R6 (estimate 925 +- 40). Default: the fallback moves of §4.
- Q3, user or orchestrator preference: a commit that declares a literal drop (`''` x5) to replace region.py's six
  start events by one `_start_event(run, kind, message)`. It removes the duplication smell (+1.0 health, about
  -45 NLOC). Default: not in W3; listed for the I-19 sweep.
- Q4, design-lane ruling: executor.py reaches only 7.0 without the context record, which needs the two direct
  `_eo_recovery` calls (one test, one script) rewritten to the new signature. That is a call adaptation, not a
  retarget in the sense of S19_RULES. Default: X1 to X6 now; `_PlanRun` and the split as a W4 item.
- Q5, fact: complexipy's count of the remainders. Default: the optional steps (R7, K2, E4) are taken only when
  the scan shows a complex or long smell that the file's penalty budget needs.
- Q6, fact: whether any test reads `__module__` of a moved record class or the screen's function attributes.
  Default: grep at the RS and S2 bases; a hit stops that step.
- Risk: `finish` and `record` become methods with 9 parameters (many_args, 0.2 each). Accepted: shortening them
  changes call sites, which RC3 forbids.
- For W4 (extends R-B1 notes 2 to 4): region.py's re-exports of the RS names and of about 20 private names;
  the underscore names that now cross five region modules (`_attempt_screen`, `_homotopy`, `_ptc_attempt`, the
  kernel names) become public there, not here.
