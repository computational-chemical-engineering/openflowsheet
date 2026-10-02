# T05 — decisions log

Append-only. Never read whole; grepped for a specific question. Each entry: the question, the
options, the choice, the reasoning, and the commit that carries it. Scientific choices are the
design lane's and live in the spec, ADR 0011 and the register; this log holds the build lane's.

## 2026-09-25

**Q: Route W0.2 (flowsheet / lifted-split / check-set generalization) to the architect?**
**Yes.** `execute_plan`, `Syn001TearProblem`, `solve_region`'s split list, `root_fingerprint`,
`verify` and `run_session` are all typed on `Syn001Flowsheet`, so the generalization changes the
executor's data flow — the user's stated trigger. Brief `docs/briefs/T05-W0.2-generalization.md`
(`c9cedf5`); note `docs/design/T05-generalization.md`.

**Q: Shape of spec F6's additive `UnitEvaluation` field.**
Options: (a) three named optional fields `work`, `extent`, `transferred_duty`; (b) one mapping of
owned-variable values. **Chose (a)**: typed, and the non-ok rule ("nothing a caller could mistake
for an answer") extends to each field. Inert for K02 (no unit sets them; nothing serializes
`UnitEvaluation` by its fields). Reversible by reverting `b8cd4fd`.

**Q: Where do the six T05 modules live?**
**`src/process_runtime/models/syn001/`**, beside K02's. The SYN-001 flowsheet label hashes only
the provider's two declared hashes (`flowsheet.py` `label`), so new modules there move no
`model_version`.

**Q: Parallelize the unit models with W0.2's design?**
**Yes**, in worktrees: the models are new files on K02's pattern and do not touch the orchestrator
or verifier. U1: W2–W5 (kernel, PH flash, valve, pump, and the trial-state harness); U2: W7–W8
(separator, exchanger). The reactor (W6) waits for U1's kernel.

**Recon note.** The W0.2 recon digest quoted `ENERGY_TOLERANCE = 1e-5` and `FLOW_TOLERANCE = 1e-9`;
the source is `1e-5 + 1e-8·1e5` (1.01e-3 W) and `1e-9 + 1e-8·3.0` (3.1e-8 mol/s). Two of its
anchors were also wrong, and it missed `attempts.py:83` `SIGNATURE_UNITS = ("U-FLASH",)`. The brief
went out corrected.

**U2 merged (`3efd9be`; gate 1973).** Separator and exchanger match every registered case (no
xfail). `energy_row` gained `sink=` (`1ef38fb`, inert: identity document byte-identical,
`b364bb3d…`). Local interpretations to put before the reviewer: (1) a dormant exchanger side still
has R-007 and the domain check on the flowing side, skips §10.2 (6)–(8), signature `ZERO_FLOW` only
if both sides are dormant; (2) §10.2 step (2) status `unsupported` (as step 5); (3) a provider
`out_of_domain` on a port becomes `state_outside_domain(<port>)`; (4) misuse (vector length, bad
literal, wiring) raises `ValueError` so every `SpecificationError` carries a registered code;
(5) the separator's `inlet_phase` has no default; (6) the exchanger's enthalpy inversion is a
bisection-safeguarded Newton; (7) manifest wording not in the spec is the engineer's — W9 checks
it against A01/A02. Consolidation candidate: `component_separator.lifted_inlet_enthalpy` repeats
`TPFlash._inlet_enthalpy`. U2's worktree had been created from `main`; the engineer reset it to
`b8cd4fd` before working — brief future worktree agents to check their base.

**U1 merged (`65c1d4c`; gate 2038; identity document byte-identical).** Kernel, PH flash, valve,
pump match every registered case (no xfail). Interpretations for the reviewer: (1) route and split
are returned by `evaluate_with_closure() -> (UnitEvaluation, PHState | None)`, `evaluate()` its first
element; (2) provider refusals in the kernel keep the provider's status, except an inner
`not_converged` → `ph_not_converged`; inlet off the domain → `state_outside_domain(<port>)`; pump
outlet off the domain → `outlet_outside_domain` (borrowed from §10.2(4)); pump `P_spec` off the
domain → `pressure_outside_domain(outlet_pressure)` (borrowed from the valve); a non-finite `Q_spec`
is not refused (no code); (3) plain bisection; (4) pump/valve `duty=None`, pump work in `work`;
(6) `tp_state.stream_enthalpy_terms` repeats `TPFlash._inlet_enthalpy`. **Design-lane question
(batched):** §4.4 step 5's `ph_ill_conditioned` guard misses a near-pure feed whose target is
exactly mid-jump (PHF-6's duty with 1e-12 C: `ok`, |f| = 5e-8 W, because the provider's RR returns
its first bisection midpoint β = 1/2); 30 % of the jump gives `ph_ill_conditioned` (|f| = 30 W).

**U3 merged (reactor; gate 2076; identity unchanged).** Interpretations for the reviewer:
(1) `MOLAR_MASSES = (0.1, 0.1, 0.1)` in the reactor module for the mass-conservation refusal (the
provider declares none and `thermo/syn001.py` is frozen), tested against
`benchmarks/syn001/components.yaml`; (2) negative `pressure_drop` → `negative_pressure_drop`;
(3) unknown `energy_specification` → `unknown_specification(<name>)`; non-finite value / wrong-length
ν → `ValueError`; (4) non-finite ν → `stoichiometry_not_mass_conserving`; (5) RX-F1's registered
extent 0.6 appears only in the free text (a failure carries no values), test asserts `extent is None`;
(6) `evaluate_with_split` → `(UnitEvaluation, TPState | None)`; (7) manifest dependencies name
`extent.xi`; `duty.Q` sensitivity `unavailable`, as the pump's `work.W`.

**W1.a/W1.b merged (`60841d7`; gate 2129; protocol P all eight items unchanged; Q-F holds — pass 2
bitwise equal to the legacy traversal).** Interpretations (engineer's, for the reviewer):
(1) "parameter-name change" tested as an instance rename; (2) the phase-capability label test uses a
derived once-through revision, since every such change on the shaped revision is refused by §1.3;
(3) swapping mixer inlets also reorders stream allocation (R1); (4) builders read pins through a
recording mapping, an unread pin → `specification_unconsumed(<spec id>)`; `pin_specifications`
helper; (5) `splits.check_agreement` implements §3.3 (a)–(e), each with a failing control;
(6) refusal codes the note left open: `id_unsupported`, `phase_capability_missing`,
`port_phase_unsupported`, `parameter_missing`, `parameter_unsupported`,
`parameter_value_unsupported`; nonzero K02 heater/flash `pressure_drop` refused; unread parameter
refused; unwired port `incomplete`; `SpecificationError` from `spec()`/`contribute` → `unsupported`.
**Follow-up for W11:** parameter values are read as the Quantity's `value` with no unit check — W11
adds `check_quantity`/SI-unit refusal at parse time so a kPa value cannot be read as Pa.

**W9/W10 merged (gate 2273 expected = 2129 + 144).** A01 over 43 configurations; A02 literal; A16
complete (22 codes from registered cases, 4 built: `state_outside_domain(inlet)` PHF-1 at 450 K,
`outlet_outside_domain` HX-3 at 1 MW, `ph_ill_conditioned` near-pure PHF-6, `ph_not_converged` via
a 10-evaluation budget); A06 worst 5.94e-8 τ (valve VLV-5); A15 at all 7 structures; A13/A14 already
covered by per-model tests. **DECISION (engineer's, accepted): A03's "configuration change changes
`model_version`"** holds at unit level for energy mode, exchanger duty-vs-temperature and
declared-vs-lifted inlet; for key component, declared phase and hot-vs-cold outlet spec no id moves,
so the unit-level test asserts rows differ with equal structure hash, and the flowsheet-level half
(label via `configuration_sha256`, R-047) was added to W11's scope. Reversible: delete
`LABEL_CONFIGURATIONS` and its test. Note: `tests/` is not under mypy; `tests/t05_trial_states.py`
has pre-existing mypy errors (loop variable reuse) — cosmetic.

**W1.c merged (gate 2285; protocol P all unchanged; identity `b364bb3d…`).** Shaped revision:
`initial_state` bitwise equal to the legacy start on all 47 variables; `CONVERGED` in 3 iterations;
worst deviation flows 2.2e-16 mol/s, duties 7.3e-12 W. Interpretations: `solve_and_bundle` refuses
through `run_session` (`syn001_only(run_session)`); the general `_solve_eo` branch is a separate
`_solve_revision_region` so the legacy body is untouched; `initializer_rejected` recording moved into
a shared `_reject_initializer` also used by `_missing_guess` (output identical by P vii/viii).
The CasADi `DomainError` traceback on stderr of `k05_structural_identity.py` is pre-existing
(registered failure cases), confirmed on the pre-W1.c tree.

**W11 merged (gate 2343).** Case files C1–C3X bind; rows at the twin's reference states ≤ 1.43e-8 τ
(one rounding unit; negative control — C3 with recycle/purge swapped — 1.28e7). A25 registry family
and cases; `typed_failure_or_failed_certificate` with `expected.accepted` = A20's two outcomes.
`tests/test_schemas_p01.py` gained C3X in the outside-denominator set and a closed-vocabulary test
(sanctioned by spec §21; additive). A03 flowsheet half: eight configuration changes move label and
`model_version`; six pinned-value changes move only `constants_sha256`. Interpretations: the unit
check (kind + SI unit + `check_quantity`) also covers specifications (`specification_{kind,unit}_unsupported`),
beyond the brief's parameters — kept, same fault class; "spec is square" read as T01
`STRUCTURALLY_CLOSED` (C2/C3 have one redundant pressure row around the recycle, as SYN-001's 49/47);
reactor/exchanger mode conflicts → `specification_missing|conflict(U.<field>)`; a second conversion
→ `parameter_unsupported(U-RX.conversion.B)`; case files follow §2.4 literally (no mixer
`pressure_drop`; `split_fraction` a plain parameter); Quantity bounds run before the constructor
(pump efficiency 1.5 → `parameter_quantity_invalid`).

**W1.d merged (gate 2353; protocol P all unchanged; identity `b364bb3d…`).** Shaped solve
`VERIFIED`, 146 pinned check ids; 42 legacy↔general pairs bitwise equal at the root and at x⁰
(15 nonzero there); trivial root → `FAILED`, `false_success_detected`, the legacy detection values to
the bit. **DECISION (engineer's, `15aed94`, isolated):** sums over one stream's components use
Python's `sum()` (Neumaier-compensated since 3.12, as the legacy builders), not left-to-right as
note §4.3 writes — left-to-right gives `total.S3.L` = −4.44e-16 vs legacy 0.0 at x⁰. Every other sum
stays left to right. Reverting the commit restores the failing pair. → design-lane batch.
**Gap → design-lane batch:** legacy `energy_balance.splitter` has no general counterpart (spec §12.2
and note §4.3 give the K02 splitter no energy check); at x⁰ it is 2458.79 W, so the general set is
weaker than K04's there. Other interpretations: one running accumulator for the material envelope;
envelope terms keyed by model-id sets in `table.py`; independent-split tolerance
`tolerances["molar_flow"]` (identical to `FLOW_TOLERANCE` under the registered policy); mixer inlet
always `.<port>.<S>`; a T05 model slots in as one `ModelChecks` entry.

**W13a merged (gate 2374).** C1/C2/C3 `CONVERGED` from `traversal-G0-v1` (0/2/3 iterations); worst
deviations C1 7.3e-12 W, C2 9.1e-13 W, C3 3.6e-8 K and 3.3e-7 W (`U-HX.Q`) — all inside §11.5.
A26 `branch_found` exact. W0.9: T01 certifies only loop-closing copy rows (C2 `U-SEP:SEP-P:top`,
C3 `U-SPLIT:SPLIT-P:recycle`); PHF-T, SEP-T, HX-pressure are matched rows; Q-B agreement exact.
**W0.8 → design-lane batch:** a dormant valve or PH-flash inlet does **not** fail typed on the rank
path as spec §4.7/Q4 expects — `CONVERGED` at iteration 0 (the traversal start is the exact root, no
Jacobian formed); K04's screen at the root: `RANK_DEFICIENT`, rank 15 of 18, so at best `UNVERIFIED`
("never VERIFIED" holds). Rank loss is 3 (the three equilibrium rows have zero gradient at zero
flow), not §4.7's one; and the zero-flow lifted outlet is fingerprinted `TWO_PHASE`, not `ZERO_FLOW`.
Recorded, not pinned.

**W12 merged (`6c181e2`; identity unchanged).** Six T05 table entries (no row builder, evaluator,
kernel or `admission.py` imported); `Unit` gains optional `provider`/`context` for the pump's work
relation; heater lifted-outlet rows factored into a helper shared with valve and reactor (W1.d
bitwise cross-validation still passes); pump component sum via `_component_sum` (question (a) stays
one place); exchanger spec id `specification.U-HX.<mode>` with §10.1's mode name. A22 all four
reproduce (≥ 4.7e3 τ); extra failing checks beyond §12.5's "what must fail" are consequences
(INJ-T1: `independent_split.U-VLV.S2.<c>`, envelope; INJ-T3: envelope A/B and residual rows; INJ-T4:
residual `PUMP-work`) — the compiled declaration carries the revision's ν and η, so its rows fail at
an injected state too; INJ-T3's duty set so the fresh-flash energy balance closes. A20 second branch
exact (+10.0 K sole failure); A27 rows as note §5 with 0 residual/Jacobian calls; C1–C3 twin states
`VERIFIED`, worst table check 1.01e-7 τ. Tests import helpers across test modules
(`test_t05_w11_cases`, `test_t04_ptc_region`).

**W13b merged (`5462865`; gate 2417).** A21: C1/C2/C3 `VERIFIED`, 160/116/139 checks, no
limitation, none near threshold; bounds 8.08e-14 / 3.88e-15 / 3.18e-9 (C3's 3.1× margin to 1e-8 is
a tolerance-stop, worst residual 1.9e-2 τ). W0.5 witness 2.36e-11 / 2.85e-11 vs 1e-7. W0.7: F9's
mechanism not active. A24: `t05` key; document minus `t05` = `b364bb3d…`; whole document
`8987721d…`. Interpretations: `t05` keeps the plan's declared scale/bound decimal strings (as
`t02`) and T03's fingerprint projection's `constants_sha256`/`variable_ids_sha256` (identities of
constants and ids, as `t03`) — the note mandated those projections; a one-line filter removes them
if the design lane wants.

**Fix pass A merged (gate 2498 + 1 xfail).** Items 1–7 of the ruling checklist (models side); all 61
registered unit cases repr-identical; identity minus `t05` unchanged. **DECISION: the ruled
acceptance "PHF-6's inputs with `max_evaluations=5` → `ph_not_converged`" is impossible** — PHF-6's
T_sat = 360 K is the exact midpoint of [280, 440] K and ln K_B(360, P_r) == 0.0, so the bisection
closes on its first step (budgets 3, 4, 5, 200 → `ok`; 1, 2 → `ph_not_converged`). Kept as
`xfail(strict=True)` with those numbers; the budget is tested instead on pure B at 1.5e5 Pa
(53 ln K evaluations: budgets 5 and 52 → `ph_not_converged`, 53 → `ok`). For the design lane to
ratify at its next touch (amend the ruling's acceptance to the added test). **DECISION:** a
non-finite `pressure_drop` (including −inf) is `ValueError` at construction per amended §5.1/§3.5,
not `negative_pressure_drop` (reactor likewise); reversible by reverting `6502481`'s two-line check.
A NaN/+inf key ν_k is refused `key_not_reactant` (§6.2's order tests ν_k < 0 first) — pinned as is.

**Q (fix pass B, A28): K04's screen and bound segfault on the dormant PH flash's target.**
*Measured:* `verify_revision` on A28's PH-flash mini-flowsheet killed the process (SIGSEGV) in
`regularity.solution_error_bound`'s `splu`, 4 of 5 pytest runs; the dumped 18 × 18 target
(structural rank 15, three empty equilibrium rows) segfaults SciPy 1.15.3's `splu` under ADR 0004's
options on the **first** call in a fresh process, pure SciPy (other option sets: `RuntimeError`,
or SuperLU's "failed to factorize … dpanel_bmod.c", or BLAS "DTRSV parameter 6 illegal"). The
valve's target (also rank 15) did not crash under ADR 0004's options in 2 000 calls. **Chose:**
ADR 0004 D3.3's structural refusal (T04 review S5), until now only in `solve_linear`, applied to
the screen's and the bound's `splu` through one helper (`regularity._factorize`): structural rank
< n → the `RuntimeError` both callers already read as "exactly singular" (screen → SVD escalation,
bound → `None`). Bit-inert on every structurally nonsingular matrix; protocol P unchanged;
A28 8/8 clean after. Alternative: run A28 in a subprocess (hides a production crash). Reversible
by reverting the commit "T05 review: K04's screen and bound refuse a structurally singular
matrix before SuperLU". For the design lane: D3.3's "the only known route to the crash" no longer
holds — K04's regularity screen is a second route, now closed the same way.

**Narrow design-lane review of the K04 guard (2026-09-25).** `79e8559` correct and inert for every
structurally nonsingular matrix; downstream K04 §7.3 behaviour as required (`RANK_DEFICIENT` via
SVD, bound `None`, `UNVERIFIED`). ADR 0004 D3.3 amended (dated note). Should-fix applied in
`59ed087`: one guarded `numerics.linear.factorize` (structural refusal + square check), the only
`splu` call (AST test with failing control); the Q-R1 acceptance replacement ratified and the strict
xfail turned into a positive test of PHF-6's measured budget pattern. Gate 2542, identity document
`622463f5…`, T02 floats `9a8a5baf…` unchanged. Notes left as is: `INCONCLUSIVE(svd_budget)` for
n > 2000 structurally singular targets (same verdict); the evidence does not say the structural
refusal triggered the escalation (schema does not require it).

## 2026-09-25 (after the merge) — Frank reverses the two registered limitations

**Frank's answers (verbatim intent):** "I want the software to have as little limitations as
possible. So, yes: the PH solver should be able handle near-pure feeds, and EO solves can handle a
single flowing component that is partly vaporised." → spec §19 **Q11 answered: yes** (reverses
R-049's "no conditioning criterion / registered limitation"), **Q12 answered: yes** (reverses R-050
for §4.7 (b)). Reversal takes a new decision recorded the same way (CLAUDE.md): the design lane
writes it (ADR 0012 + register), on branch **`wp/T05b`** (from `main` at the T05 merge).
**DECISION (build lane, under Frank's "as little limitations as possible"):** §4.7 (a) — a dormant
PH-type outlet on the EO path, `UNVERIFIED` — is in the same scope, since its remedy (a `ZERO_FLOW`
regime with a label row) is the same ADR 0005 lattice change. Alternative: leave it registered.
Reversible by: dropping it from `docs/briefs/T05b-limitations.md` §1. Other Frank-preference
defaults (Q2 exchanger phase change, Q3 general mixer, Q7 several reactions, Q8 formation data, Q9 UA
spec) are **not** taken on without his word; asked in the report.

**Frank's steer for T05b (2026-09-25, verbatim):** "The important thing for me is robustness, if a
method cannot solve a hard case and the solver then switches to another method this is also fine.."
Passed to the `specifier` mid-pass: design a primary method plus a typed, recorded, deterministic
fallback chain (each switch a trace event; never a relaxed check; certificate independent, R-016)
rather than a single method that refuses a hard case. Read as a priority on robustness, not as an
answer to Q2/Q3/Q7/Q8/Q9, which stay at their defaults.

**Frank's answers on T05b (2026-09-25, via the question tool):** (1) **approves** the frozen-schema
widening `solve-policy.phase_contract` const → enum [`T03-phase-contract-v1`,
`T05b-phase-contract-v2`] (ADR 0012; unblocks W5); (2) **include** dormant pump, exchanger and K02
mixer outlets in T05b, accepting that C1–C3's `t05` identity is re-registered with the reason
recorded (SYN-001 unaffected) — needs a design-lane amendment of the T05b spec; (3) schedule
**T04 F9 right after T05b**, before T06.
**T05b W0–W2 merged** (gate 2666; B02 bitwise on all 61 registered calls; identity unchanged).
Engineer's items for the design lane: W0.4 — T05's evidence manifest `91ac010` A28 value records
`branch_found` `TWO_PHASE` for V = L = 0 (the records §8/D6 name; a committed evidence record, not a
fixture); A16's constructed `ph_ill_conditioned` case rebuilt on the JUMP double (`09a7feb`,
reversible) since the band route now answers the near-pure case — confirm or amend §16. Also fixed
ruff errors in `t05b_reference.py` (`89450ff`; output unchanged, 454 claims, `35c4e6db…`).

**T05b W3–W5 merged (`f75721c`; gate 2713; protocol unchanged after every chunk).** B06, B14,
B15 (v1 half: DZ-1/DZ-2 `VERIFIED`, `branch_found` `ZERO_FLOW`), B18, B19 pass. **DECISION
(engineer's, `65f36b5`, isolated):** a policy naming `T05b-phase-contract-v2` is refused
`phase_contract_unimplemented(T05b-phase-contract-v2)` until W6 (else v1 rules under a v2 label);
W6 removes it. **Cost:** each R-007 refusal spends ≈104 extra `lnK` calls (OFF-B trace property
calls 521 → 729; the K03 fixture forgives property counters, not re-baselined) → W6 adds the
suggested 2–4-call pre-screen with a proof of identical decisions. **For the design lane (batch):**
(1) §9.2 qualification text for a degenerate stream outside any split — engineer wrote "in its
declared phase <PHASE>"; (2) a degenerate split with a flowing feed gets `.saturation` even at
V = L = 0 (spec silent); (3) INJ-B1 also fails the compiled `VLV-energy` row (2016 W; spec silent).
Notes: `verify/zero_flow.py` keeps its own zero-flow id table (R-016); the verifier's band test now
runs at every flowing stream (≈110 `lnK` calls/stream); B18 uses a stand-in `CONVERGED` claim for
SC-1 until W6's real v2 solve; `scripts/t05_evidence_manifest.py` `_a28` retirement is W8's.

**T05b W6 merged (gate 2762; protocol unchanged).** v2: SC-1, SC-2, SC-4, NP-1/2/3, NP-G
`CONVERGED` and `VERIFIED`; SC-3 two attempts (one adjacent restart `LIQUID → TWO_PHASE`), `VERIFIED`;
v1 regression values kept (SC-1/SC-3 `ACTIVE_SET_CYCLING`, SC-2 `BOUND_BLOCKED`). B07: C1–C3X under v2
equal to v1 (R0, messages, fingerprint) except `policy_id`/plan ids. R-007 pre-screen (`5c0105d`):
0 decision mismatches over 35 540 gate calls and a 126 420-call sweep; `lnK` calls 15 945 → 293 in
the gate; OFF-B property calls 523 (fixture's 521 not re-baselined; counters are forgiven).
**DECISION (engineer's):** a v2 solve that needs `ZERO_FLOW` raises
`phase_contract_unimplemented(T05b-phase-contract-v2, ZERO_FLOW): <unit>` until W7 (never v1's form
under a v2 label). **For the design lane (batch with the review):** (1) NP-G's recorded
solution-error bound 7.0e-8 > spec §13's 1e-8 (others ≤ 3.8e-10); (2) a products-style split's
opening sets only the vapour product's temperature, `PHF-T` closes the liquid's — confirm;
(3) B07's "except the policy literal" = except `policy_id` and plan ids; (4) B11's pre-change value
is W0.1's, not re-measured. No end-to-end case exercises a region-internal TP/band fallback (none
registered triggers one; kernel-level KS-1…KS-3 test the records).

**T05b W7 merged (gate 2808 + 1 xfail; protocol unchanged).** B15 v2, B17 (DZ-1/2/4/5 `VERIFIED`
at iteration 0), B18 INJ-B3 (`residual.U-VLV:zero-flow-label` 1.0 K), B28 DZ-2C
(`SPECIFICATION_CONFLICT`, `zero_flow_conflict(U-PHF:PHF-duty)`; negative control closes `CONVERGED`
without the test). **Stop-and-report → design lane:** B16 DZ-3 converges (v2, one attempt, S4.T within
8.1e-7 K) but its certificate is `FAILED` on fresh-flash checks — `independent_split.U-PHF.S1.total`
−9.1e-8 mol/s (2.9 τ), `energy_balance.U-PHF`/envelope −1.33e-3 W (1.3 τ_E) — because Newton stops
at its row tolerances (largest row 0.2 τ), not at roundoff as spec §13 assumed: T04 F9's mechanism.
`xfail(strict=True)` with these numbers. Engineer's reversible decisions: a dormant feed at the v2
start selects `ZERO_FLOW` for either closure type (nonzero supplied split overwritten, recorded
`projected(S, <branch>, ZERO_FLOW)`); a flowing feed with V = L = 0 leaves `ZERO_FLOW` by TP
projection (branch word `zero_flow`, v2 only); regime/dormancy disagreement at opening → RuntimeError
(unreachable); `ZeroFlowForm` built beside `LiftedSplit` so W1.a's pinned repr digest holds.

**Frank (2026-09-25, question tool): fold T04 F9 into T05b** (instead of "right after"), so DZ-3 and
NP-G are certified and T05b merges with no registered limitation left. Brief
`docs/briefs/T05b-F9.md` to a fresh `specifier` (T04 Q8's default — first-order propagation — named
as an option, with a solver-side polish and both).

**T05b W7b (worktree on `wp/T05b` `10c17c7`; commits `b23fdff`, `ad2f2ad`, `408daea`, `f6802ed`, `9c85948`; gate 2864 + 2 xfail; protocol unchanged after every chunk).** Dormant
non-lifted outlets: registry (`DORMANCY_RULES`), `check_agreement` (g), the verifier's own table
(`verify/zero_flow.py` `DORMANT_OUTLETS`), region signature items / screen / openings with the
outlet reset / closure agreement / swapped-row test. B23, B24, B25, B27, B28 (DZ-11), B29, B30 (a),
B20 (d) pass. **Stop-and-report → design lane:** B26 DZ-10 converges (item throughout, label moves,
S4.T within 8.1e-7 K) but its certificate is `FAILED` on the PH flash's fresh-flash checks with
DZ-3's exact numbers (energy −1.33e-3 W = 1.3 τ_E; independent split −9.09e-8 mol/s = 2.9 τ) —
T04 F9's mechanism, as B16; `xfail(strict=True)`. **Against the spec's letter (for the design
lane):** (1) W0.11 (b): at DZ-9 T01 and K03 remove `U-MIX:MIX-pressure:1` only when the feeds are
declared before the mixer; declared after, both remove the second feed's `FEED-P` — `dz9()`
declares the feeds first, as the twin does. (2) F8's premise: the table already reported all three
exchanger one-sided checks `not_applicable` (`ZERO_FLOW`) at any dormant inlet (T05 §4.3's rule),
so what changed is `heat_flow`, now judged at a dormant side. (3) B29 INJ-B4 names
`energy_balance.U-HX`; the table's ids are `energy_balance.U-HX.hot` / `.cold` — the test uses the
hot one. **DECISION (engineer's, `408daea`, no code):** the terminal checks' `not_applicable`
reason stays K04's existing `ZERO_FLOW` (spec §9.3/B25 write `zero_flow`, lower case, which no
check reason uses); alternative: a new lower-case reason; reversible by passing `reason=` in
`Unit.one_sided`'s dormant branch for `hot_end`/`cold_end`. **DECISION (`f6802ed`):** the outlet
reset of §7.8 (ii) is applied to a fixed point, each outlet at most once, because a reset outlet can
be another form's trigger (a pump after a pump); items are then read off the result. **DECISION
(`f6802ed`, `9c85948`):** an item is recognized by its key (`<U>.<port>`; unit ids have no `.`,
R1), and `phase_contract._proposal` reads the declared phases with
`getattr(ops, "declared_phases", {})` rather than adding a `PathOps` attribute, so the tear path
and the T03/T04 test stubs are untouched. **Recorded property:** Newton screens a trial only when
the frozen signature is non-empty (`newton.py:450`), so on a flowsheet with no lifted split an
attempt without items is unscreened; §7.8 (iv) 1's closure agreement is the path that catches a
trigger going dormant there (`inadmissible(<S>, dormant)`); no registered case reaches it.

**T05b W7b merged (`5782bd3`; gate 2864 + 2 xfail — B16 DZ-3 and B26 DZ-10, both T04 F9's
mechanism, folded into T05b's F9 pass; protocol unchanged).** B23, B24/B25 (v2 and v1 now
`VERIFIED`), B27, B28 DZ-11, B29, B30 (a), B20(d) pass; W0.10 no committed record has an active
form. **Spec items for the design lane (batch with the review):** W0.11 (b) T01/K03 remove
`U-MIX:MIX-pressure:1` at DZ-9 only when feeds are declared before the mixer (else `U-FEED-1:FEED-P`);
F8's premise false (`hot_end`/`cold_end` were already `not_applicable`; what changed is `heat_flow`
now judged); B29 names `energy_balance.U-HX`, table ids are `.hot`/`.cold`; **DECISION** terminal
checks' reason stays `ZERO_FLOW` (spec says `zero_flow`), reversible by `reason=`; **DECISION**
the outlet reset is a fixed point (a pump feeding a pump stays consistent); recorded property:
Newton does not screen trials with an empty signature — only the closure agreement catches a trigger
going dormant on a flowsheet without lifted splits (no registered case reaches it).

**T05b F9 W1–W6 and W0 (build lane; `ae6c27d`…`c9866d6`; spec `docs/derivations/K04-F9-spec.md`,
ADR 0013 Proposed).** Gate 2992 passed + 2 xfailed; K05 identity, structural, policy and T02
hashes unchanged after every chunk; W0 matches the prototype's numbers to the printed digit
(`docs/t05b-measurements.md`, "F9 W0"). **DECISION (`9912a67`):** D2 is applied only when the
provider's flash splits the stream (`phase_signature == "TWO_PHASE"`), then bubble test first,
dew second, each `≤ 1 + ε_adm` in `admissibility_checks`' arithmetic; alternative: evaluate the
two tests on every flowing stream before the flash (§5.2's literal order); the two differ only
where §5.2's own "bitwise unchanged where the provider reads single-phase" would be broken (a
stream within `ε_adm` of both boundaries — a pure component within ~4e-11 K of `T_sat`, which is
degenerate and never reaches `enthalpy_flow` in the table); reversible in `checks.enthalpy_flow`.
**DECISION (`ae6c27d`):** guard 4's "every flow" is §4.6's flow predicate
(`checks.is_flow_column`: `.n.`, `.V/.L/.N`, `.vap./.liq.`), not every `molar_flow`-kind column
(a reactor extent may be negative); the exact-zero rule uses the kind, as §5.1 says; and a row the
compiled problem cannot evaluate at `x̃` does not pass (`projection_rows_not_passed`). Reversible
in `verify/projection.py`. **Recorded:** X22's harness compares the legacy set "at one state" by
composing `run_checks` at `x_final` with its fresh-flash categories from `run_checks` at the
certificate's `x̃`, and also each engine at `x_final` and at `x̃` alone, every pair bitwise.
**Stop-and-report to the design lane (both `xfail(strict=True)`):** X26 at NP-GC, `b = 1.212e-7 >
1e-7` (S4/S5 6.7e-9 mol/s from ref, 46× inside 3.1e-7); X21 at NP-1, floor ratio 171130.3 vs
171213 (4.8e-4) from binary64 band ends of a 2.14e-11 K band — NP-1 is degenerate, so it decides
nothing. **Handed on:** the K05 `run_manifest/valid/syn001_nominal.json` fixture's
`solution-certificate.json` hash was already stale at the base (`f0206d1f…` against the emitted
`bf76b9c8…`; its test does not compare it) and now changes again with the new key; not regenerated
(the gate does not name it).

**T05b W8, less the evidence generator (build lane; `d0fe494`…; base `385fdc9`).** Gate 3000
passed + 2 xfailed (2992 + 8 new); protocol unchanged; K05 identity whole `1b4f44f5…` with the new
`t05b` key (`b1b4f6c8…`), minus `t05b` `622463f5…`, minus both `b364bb3d…`
(`docs/t05b-measurements.md`, "W8"). **DECISION (`d0fe494`):** §16 says the manifests "drop" the
retired statements, while T05 spec §5.1's T05b amendment keeps the dormant statement "for what T05b
does not cover"; both are met by dropping the T05-era texts and stating what remains — the kernel's
acceptance and band route (T05b §5.1–§5.3), the EO outcome per literal (v2 solves; the default v1
keeps T05's rules: B08–B10, B16, B26), the dormant-duty conflict not searched past (§7.8 (iv), §17),
and for the exchanger (whose manifest had no EO statement to drop) its EO conflict and unjudged
terminal differences (§9.3, §17). Alternative: delete with no replacement. Reversible in the five
manifests and A01. **DECISION (`3771502`):** retired A28–A30 are `not_applicable` with value
`status: retired by ADR 0012`, the replacements and the last measuring manifest named; the
measurement code is deleted, not kept dormant. **DECISION (`cd44057`):** the registered-start
cases of B22 (DZ-3, DZ-10, DZ-11, DZ-2C, DZ-12) project the planned region's trace and a certificate
on its final state, the plan R0 being the planned one. **Found and fixed (`1b683e6`):** T05's
generator still expected A16's pre-T05b label `PHF-6 near pure`. **Recorded, not changed:** T05's
generator run at T05b's head fails A23 on T05-scoped inertness claims later packages broke by
design (tests added outside T05's names, K02–T04 test files F9 edited, the fixture tree, xfail
marks outside `test_t05_`); T05's committed manifest is untouched.

**T05b review (`docs/reviews/T05b-review.md`): not ready — one must-fix.** M1: a restart that
changes a split's feed between zero and flowing (series PH flashes; a PH flash after a dormancy-form
outlet) raises an uncaught `RuntimeError` (`region.py:1457–1467`) — the W7 "unreachable" claim was
wrong. S1: v2 screen runs the full PH closure per flagged trial (NP-1 12 598 calls > 10 000 cap).
S2: near-pure feeds restarting into two phases end `BOUND_BLOCKED` (absent component's zero flow at
K03's bound; liquid product keeps the trial T). S3: three untested paths. **DECISION (build lane,
under Frank's "as little limitations as possible" / robustness):** S2 is fixed inside T05b, not
registered as a limitation. Alternative: typed limitation, K03 fix with T06. Reversible by: the
ruling in `docs/briefs/T05b-rulings.md` §4. M1, S1, S2 sent to the running ruling round (Q-S9…Q-S11).

**Review S3 closed (`911d251`, 13 tests, no defect).** Valve after a PH flash under v2: 0 → 30 kW and
30 kW → 0 both `CONVERGED` in 3 attempts, `VERIFIED` (records `fallback(U-VLV, tp)` on leaving;
none on entering); v1 regression values pinned (0 → 30 kW `LINEAR_SOLVE_FAILED`; 30 kW → 0
`CONVERGED` in the declared VAPOR form, certificate honestly `FAILED` on the label, 48.31 K).
PTC core with the label row: DZ-1/6/9 +5 K off their labels `CONVERGED` in 1 iteration, `VERIFIED`.
Edge 3 under v2: HOM-01…05 identical to v1; a revision flowsheet's region has no continuation
parameter (`unsupported(no_continuation_parameter)`), so edge 3 with a `ZERO_FLOW` signature is not
reachable by any registered case.

**W9 items 1–3 (ruling round, build lane).** **DECISION (W9.1, Q-S7):** the new gate test compares the
`run_manifest` fixture's `solution-certificate.json` hash exactly when the running platform
(`Environment.identity()`) is the fixture's, and skips with that reason elsewhere — ADR 0007
measured converged floats 1–3 ulp apart across x86-64/aarch64, and blueprint §8.3 promises no
cross-platform float bitwise equality. Alternative: compare everywhere (fails on aarch64 CI by
that measurement). Reversible by deleting the skip branch. **DECISION (W9.2, Q-S4 (6)):** the
empty-signature screen is an opt-in keyword `compare_empty` on `solve_newton`/`solve_ptc` that the
region sets to `bool(dormancy)` (v2 with a dormancy-form outlet — §7.8 (iii)'s scope), not a
universal change of the core's predicate: the universal form moved four K03 tear tests (84 trials),
which drive `solve_newton` with the default `signature=()` while the tear reports the flash's.
Alternative: `signature=None` for "not frozen" (changes the default and every trace record).
Reversible by reverting the W9.2 commit.
**DECISION (W9.3, Q-S9):** the non-settling opening's `ACTIVE_SET_CYCLING` is produced in
`phase_contract.py` (`OpeningNotSettledError` raised by the region, `opening_not_settled(...)` the
Decision), because T03 A02 pins that the cycling refusal has one producer and `region.py` names no
`ACTIVE_SET_CYCLING`. Alternative: produce it in `region.py` and relax A02 (rejected: a relaxed
check). The fixed point also runs at attempt 0 only when there is no recovery start (a recovery
opens at an already-settled attempt-0 opening). **Stop-and-report (W9.3):** B31 (b)'s `VERIFIED`
for CH-UP, CH-DZ12, CH-3 is unmet — each `Q = 0` downstream flash sits on its dew point, where
the declared lifted form K04 screens is rank deficient; strict xfail with the measured values
(`docs/t05b-measurements.md`); the design lane decides B31 (b)'s verdict clause.
**W9 items 4–6 (ruling round, build lane).** **DECISION (W9.4, Q-S11 (a)):** the liquid product's
temperature column comes from a new registry map `splits.split_temperatures` (unit → every
temperature column of its split's streams), passed to `solve_region` as `split_temperatures` beside
`zero_flow_forms`, because `LiftedSplit`'s `repr` digest is registered (T05 W1.a) and cannot gain a
field; a PH-type split without an entry under v2 is a `ValueError` defect. Alternative: parse the
liquid stream off `LiftedSplit.liquid_total` (rejected: id parsing). Reversible by reverting W9.4.
**DECISION (W9.5, Q-S11 (b)):** the release is in K03's Newton core only (`_bound_aware_step`);
T04's PTC core keeps `_bound_aware_alpha` unchanged, because K03 §5.3 as amended names the Newton
core and no case needs PTC; `Z*` is found by a maximum matching with the count re-checked (a set
failing it releases nothing). Alternative: PTC too (a T04 behaviour change, not ruled).
Reversible by reverting W9.5. SC-2 under `T05-W13` and T05 A30 P4 move `BOUND_BLOCKED` →
`ACTIVE_SET_CYCLING` (not `VERIFIED`; the move B33 (d) names), pins re-registered.
**DECISION (W9.6, Q-S10):** B32 (b)'s call counts are recorded in `docs/t05b-measurements.md`
and the test asserts only `CONVERGED` under the meter (counts below `max_property_calls`), not
the exact counts: property counts are not R0 (R-015) and bisection lengths may differ by platform.
Alternative: pin the counts (fails on a platform whose floats differ). The (s3) memo is per
attempt and keyed on `float.hex` of the closure's inputs; the homotopy corrector's screen has none
(it only costs a repeat). Reversible by reverting W9.6.
**W10 (Q-S9 addendum, Q-S12…Q-S14, build lane).** **DECISION (W10.4, Q-S14):** "the feed's `T`"
is the temperature of the stream `split.feed` names, `temperature_id(split.stream)` — a
products-style split's inlet; for an outlet-style PH-type split (valve, duty reactor) its own
outlet, so its leaving flash is unchanged and nothing is written. Alternative: the zero-flow
label's source (the inlet `T`) for both styles (moves the valve's and reactor's leaving, which
B36 (c) does not list). Reversible in `_contract_kernel`'s leaving branch. **DECISION (W10.4):**
the screen's leaving report at a trial (`_attempt_screen.tp_regime`) keeps the split's own `T`
(B36 rules the opening's answer only); at a candidate the `tp` sanctioned difference admits a
disagreement between the two. Alternative: the
feed's `T` there too. **STOP-AND-REPORT (W10.4):** B34 (a)'s regression counts move 80/12 →
82/10 (`(0, 0, 115 kW)`, both orders, `ACTIVE_SET_CYCLING` → `CONVERGED`); strict xfail with the
measured counts pinned beside it; the design lane rules. **DECISION (W10.3):** `opening=` is
normalized as the start is, and a length mismatch is a `ValueError`.

## 2026-09-25 — Frank: "The defaults are agreed. Please continue"

Frank agrees every default in force: T05b §18 Q9 (the exact dew-point zero-duty flash stays
`UNVERIFIED`; K04 follow-up later), K04-F9 §12 Q1 (F10's checks not added to SYN-001's legacy set),
T05 Q2/Q3/Q7/Q8/Q9 (no exchanger phase change, no general two-phase mixer, one reaction per reactor,
no synthetic formation data, no UA/approach spec), design Q-D and Q-G. Next package: **T06** on
`wp/T06` (from `main` at `63364f8`, with `wp/T06-refs` merged in: `65d4d18`).
