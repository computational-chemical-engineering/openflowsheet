# Review of the roadmap: target architecture and foundation rulings (roadmap stage 4)

Status: design-lane review (`reviewer`), 2026-11-02. Brief: `docs/roadmap/brief-reviewer-roadmap.md`. Under review:
`docs/roadmap/target-architecture.md` ("the note") and `docs/roadmap/foundation-rulings.md` ("the rulings"). Measured
against R-923 to R-927, ADR 0056 with Amendments 1–2, blueprint D01–D20 and the scientific-conduct rules in `CLAUDE.md`.
Nothing has been implemented, so this review judges a design and checks no test numbers.

## 1. Verdict

**Finalise after the listed fixes.** The main lines are sound, and I would not reopen any of them:
- the two-level material model, with `nTP-v1` kept as one registered definition;
- an enthalpy-type thermal coordinate, which is what makes regime discovery (FB-04 (2)) well posed;
- state points on a phase-set lattice that reduces exactly to ADR 0005 when there are two candidates;
- property methods built by composition, with one convention per flowsheet;
- frozen legacy families beside a generic `std.*` family;
- one problem stack, with an owned integrator and logic-based outer approximation (LOA) for MINLP.

The rulings are mostly correct, and five of the six departures improve on the note. Two things block finalisation:
- **The v2 revision grammar has no place for non-material connections or package-owned content.** Controllers, heat
  and work connections, utilities and reaction sets are missing. TX, X12, X14, X25 and X26 would therefore break v2
  after it is frozen. This is the first failure mode R-927 names (M1).
- **The F4 and F6 exit criteria contradict Q1 and Q2.** As written, they cannot be met (M2).

The should-fix items close real gaps but leave the structure as it is:
- reactivating a stream whose `ĥ` is only a label;
- the outputs of inactive phases, and the indicator for phase appearance;
- phase families for equation-of-state (EOS) methods;
- whether variable ids are injective;
- scaling under the elemental reference;
- one worked example in Q3 that is wrong;
- a byte-level legacy freeze that does not depend on line endings.

None of these needs rework.

## 2. Findings, by severity

### Must fix

**M1. ProcessRevision v2 has no energy or signal connections, no controllers and no home for package content.**
*Where:* note §2.1.1 (definitions are material only), §2.4.1 (`UnitDeclaration` ports "with the state definitions and
substreams it accepts"), F2 scope, §8 `ProcessRevision` row. The rulings say nothing on it.

*What:*
- The v1 schema already has port kinds `material | energy | signal`, but it forces `state_definition: const "nTP-v1"`
  and `component_mapping` on every connection (`schemas/process-revision.schema.json:116-122`).
- The note never says what an energy or signal connection carries in v2: its quantity and kind, its sign convention, or
  whether it has a definition at all.
- Nothing in either document covers controllers (PID loops, transmitters), heat and work connections (X14 heat
  integration, compressor–turbine shafts), costed utilities (X12) or shared reaction sets. Reaction sets are needed by
  X13 and X20, and Q2.A2 speaks of "registered reactions" that have no home. A grep of both documents finds only X25's
  "segment controller".
- Today reactions live in unit parameters, and v1 has no top-level section for them.

*Why it matters:* the note freezes v2 at the end of W1 (§5), and TX (0.7) cannot be a usable dynamic simulator without
control loops. Each of these capabilities would then need a v3, which is exactly what the roadmap exists to prevent.

*Fix:*
- (a) F2 registers energy and signal connection definitions alongside material ones:
  - each carries a quantity kind, an SI value and a sign convention;
  - signals are typed by quantity kind.
- (b) F1 adds an extension kind `revision_section`: namespaced, with one schema per extension, inside `content_hash`.
  Later packages then add sections (reaction sets, utilities, controller tuning, cost parameters) without a new schema
  version.
- (c) W1 decides how controllers are represented: as units with signal ports, or as expression documents. That decision
  fixes the grammar.

**M2. The F4 and F6 exit criteria contradict Q1 and Q2, and the rulings' §12 does not list them.**
*Where:* note §2.3 migration proof and F4 exit ("re-composition identity … bitwise … the `describe()` values and
outputs"); §2.4 migration proof and F6 exit ("equivalence of `std.*` and the legacy units … every certificate quantity
within the K04 numerical policy"); rulings Q2.R3, Q1.R1 and Q1.R3.

*What:*
- (i) Q2.R3 records the convention shifts in the composed method's `describe()` and adds `Σ n_c Δ_{m,c}` to `Ḣ`. A
  shifted method therefore cannot reproduce the legacy `describe()` or `h` bitwise.
- (ii) Bitwise identity also needs the same arithmetic in the same order. Composed methods are new code (their identity
  hashes "differ by design"), and F4's batching exit (≤ 0.1× cost per point) pushes them towards vectorised kernels.
  NumPy reductions sum pairwise, whereas the legacy loops sum sequentially, so the last bits differ.
- (iii) `std.*` units on `(n, ĥ, P)` with `ELEMENTAL-ref-v1` differ from legacy units on `(n, T, P)` with native
  conventions in their variable sets, scales, enthalpy values and residual norms. "Every certificate quantity" is
  therefore undefined.

*Why it matters:* an exit criterion that cannot be met either blocks the package forever or gets quietly relaxed, and
`CLAUDE.md` forbids relaxing a check.

*Fix:*
- State re-composition identity on the native, pre-shift layer; Q2.A1 already presupposes that this layer exists.
- Require it bitwise only for composed methods that delegate to the legacy kernels. For the others, require R2
  agreement within K04, with a registered difference.
- Define `std`↔legacy equivalence on a common physical projection: `n`, `T`, `P`, per-phase amounts and `β`, duties and
  work, and enthalpies compared after the convention shift is removed.
- A two-step proof is cleaner, if it is wanted:
  - first, `std.*` on a native-convention definition with coordinate `T` against legacy, which can be tight;
  - then that same definition against the `ĥ` definition.

### Should fix

**S1. The legacy freeze must be byte-level, and self-hashes must not depend on line endings.**
*Where:* note §1 item 11, F1 scope ("every existing provider … registered"), §2.3.5 (legacy-provider adapters), §2.4.4
("bug fixes … remain allowed").

*What:*
- `implementation_sha256` is the SHA-256 of the provider module's bytes (`thermo/wilson_ig.py:443`, which uses
  `Path(__file__).read_bytes()`; the same pattern is behind `pr_c1.py:721`, `syn001.py:84` and `coolprop_heos.py:923`).
- Any byte edit therefore moves the provider's identity, and with it cache keys (M6) and bundle identity and replay
  (M7). This includes a descriptor, an adapter method, a widened type annotation, a docstring and a bug fix.
- The repository has no `.gitattributes`. Windows CI checkouts default to `autocrlf=true`, so they hash CRLF bytes and
  produce a different self-hash. F1's exit "the snapshot hash is identical across runs and platforms (R0)" would then
  fail on the Windows leg of X07a.

*Fix:*
- Legacy modules are byte-frozen. Registration, adapters and type widening live in new modules.
- F0 adds a per-file SHA list of the legacy modules, so a violation is reported by name and not by a downstream digest.
- A legacy bug fix is a registered change to numerics, with new references; it is not "allowed" under F0 PASS.
- Before F1 records any self-hash, either hash LF-normalised source or add `.gitattributes` with `eol=lf` for `src/`.

**S2. The boundaries between state definitions are not defined.**
*Where:* note §2.1.1, §2.3.7 and §2.4.4; the 0.5 line acceptance ("a v2 revision … solves on the legacy route"); rulings
Q1.R3 and Q1.R5.

*What:*
- Neither document says whether one v2 flowsheet may mix `nTP-v1` connections (legacy units) with `(n, ĥ, P)`
  connections, or how a stream crosses from one to the other. Converting `T` to `ĥ` needs a method.
- Neither says how ports with different definitions meet at one unit: different substreams, grids (Q6.R4) or conserved
  bases (Q3).
- Neither says how a specification or a decision targets a stream's `T`, which is no longer a variable (Q1.R3).
  Students specify stream temperatures constantly, OPT decides on them, and specifications today target variable ids.
- The method-boundary admission rule in §2.3.7 is also incomplete. It needs Q3.R5 (basis compatibility), Q2.R2 (anchors)
  and Q8's lost solid candidate, and §12 lists none of them.

*Why it matters:* otherwise an `ĥ` flowsheet can contain nothing that `std.*` has not reimplemented (columns, the coupled
reactor), or converters appear ad hoc later.

*Fix:* F2 defines three things:
- (a) either a definition-boundary rule analogous to the method boundary (converted with the downstream unit's method,
  and reported), or the rule "one thermal coordinate per flowsheet, with legacy units only on `nTP-v1` flowsheets";
- (b) port compatibility: a superset definition admits a subset with the missing parts filled dormant (Q8.R6), and
  regridding is an explicit unit;
- (c) specifications on derived quantities: `T`, `β` or `s` of a stream as a specification or decision target, which
  adds a state point and a row.

**S3. Reactivating a stream whose `ĥ` is a label.**
*Where:* rulings Q1.R4 and argument 4 ("The label value is harmless … one Newton step removes it").

*What:*
- The argument covers only the rows of the producing unit. A restart by adjacency (ADR 0005 D4) starts from the previous
  attempt's state, so the consumers of a reactivated stream evaluate their PH state points at `(n, ĥ_label, P)` before
  that Newton step.
- Under `ELEMENTAL-ref-v1`, `ĥ` carries a formation enthalpy that depends on composition. Argument 4 itself says "a
  composition-free `ĥ` carries no information".
- Example 1: a dormant feed has `ĥ_label = +0.0` J/kg. Reactivated as liquid water (`ĥ ≈ −1.59e7` J/kg), the PH
  evaluation at 0 J/kg lies thousands of kelvin away, outside the domain of IAPWS-95 or of any correlation.
- Example 2: a flash's dormant vapour outlet takes the feed's liquid `ĥ`, which is off by the latent heat plus the
  difference in formation enthalpy.
- A `T` label, as used today, always lies in a plausible range.

*Fix:*
- When a stream reactivates, its `ĥ` is re-seeded from a physical evaluation: the producer's `T` at the new composition,
  set by the initializer before any consumer evaluates.
- Add an assertion Q1.A9: dormant → flowing across an attempt boundary, in three cases (a splitter fraction 0 → 0.3, a
  feed 0 → 1 mol/s, a flash vapour appearing), with no domain failure and the same converged state as a cold start.

**S4. The outputs of inactive phases and the phase-appearance indicator.**
*Where:* note §2.2.1, §2.2.7 and the last bullet of the F5 exit; rulings Q5.R3.

*What:*
- (i) Every candidate phase has per-phase symbols, and inactive amounts are exactly `+0.0`. Neither document gives a
  value rule for the compositions and intensive properties of inactive phases in the procedural block. `NaN · 0` is NaN
  in `Σ n_p h_p`, and derivatives with respect to an undefined value are undefined. The lifted formulation is covered by
  ADR 0005 D5; the procedural one is not.
- (ii) "The minimal `tm` of each inactive candidate … continuous across phase boundaries" holds only while the trial's
  non-trivial stationary point exists. On the stable side that point merges into the trivial solution, which Q5.R3
  excludes as a witness. The indicator is then undefined over part of the stable region, and it jumps when a trial
  changes basin.

*Fix:*
- The intensive properties of an inactive phase are the incipient composition from the trial that tracks it. Record it;
  it also seeds the phase's appearance. Where no such trial exists, use a declared label with zero derivatives.
- Define the appearance indicator by continuing the tracked stationary point (for VLE, the negative-flash phase fraction
  will do), and state its domain.
- Restate F5's bracketing exit on that definition.

**S5. EOS methods do not fit the family structure.**
*Where:* rulings Q4.R1, Q4.R2, Q4.R6 and O-3.

*What:*
- The families `{VAPOR, LIQUID, SOLID}` treat vapour and liquid as different models that are interchangeable only within
  a family. Under one fluid model (PR, SRK, CPA, SAFT, IAPWS-95), every fluid phase is the same model.
- In EOS VLLE, the identification rule may put two phases in the vapour family, or flip the light liquid between families
  near a critical endpoint. EOS VLLE includes water–hydrocarbon systems in the X21 assays and CO2–alkane L1L2V, a core
  case for a real simulator.
- The result is non-adjacent restarts and churn in R0 labels. `VAPOR.2` is also not in any candidate set.
- O-3 covers only single-phase flips.

*Fix:*
- For single-fluid-model methods, use one interchangeable `FLUID` family, ordered canonically by Q4.R3's key, with
  vapour or liquid as a reported attribute.
- Keep the legacy two-candidate rendering through a mapping.
- Settle this in ADR-F5, before labels become R0 identity.

**S6. Variable ids are not shown to be injective.**
*Where:* note §2.1.6; rulings Q4.R1 and Q4.A5.

*What:*
- Q4 makes phase-id rendering injective. Full variable ids, however, join user ids with `.`, which is inside the id
  alphabet. For example, substream `solid.n` with component `x` and substream `solid` with component `n.x` both render
  as `<S>@solid.n.n.x`.
- Ids are opaque (R-019), but a collision still merges two variables in the layout and in `model_version`.

*Fix:*
- F2 requires the whole id grammar to be injective, with a separator outside the alphabet at every user-id boundary.
- A [gen] property test covers every constructor: substream, attribute index, template prefix, state point and phase.

**S7. Scaling under `ELEMENTAL-ref-v1`.**
*Where:* rulings Q1 argument 5 and the Q2 argument, which compute floors only; ADR 0001 D6 (energy tolerance `1e-5 W +
1e-8 ×` an energy scale); blueprint D06.

*What:*
- Formation enthalpies make `|ĥ|` and `|Ḣ|` one to three decades larger than sensible magnitudes. For liquid water `ĥ ≈
  −1.59e7` J/kg, against `ĉ_p ≈ 4.2e3` J/(kg K).
- Any scale or step limit taken from a magnitude is distorted by that offset:
  - an energy-check scale taken from `max|Ḣ|` loosens energy closure by the same ratio;
  - a variable scale or relative step bound taken from `|ĥ|` admits steps of about 380 K, since 10 % of `|ĥ|` for water
    is 1.6e6 J/kg.
- The rejection of option (c) rests on representation error. Determination is not improved: a trace stream's `ĥ` is
  fixed by `ṁĥ − Ḣ` only to `τ/ṁ`, as `T` is today.

*Fix:*
- ADR-F2 and ADR-F4 register the scale of `ĥ` and the energy-check scale from a scale that does not depend on the
  convention, such as `ṁ ĉ_p ΔT_ref` or the duties, and never from `|ĥ|` or `|Ḣ|`.
- Add an assertion: shifting one component's `Δf h°` by 1e6 J/mol leaves the scales, the step bounds and the verdicts
  unchanged.
- The verifier's intensive recheck (an independent PH evaluation, Q1.A7) is what guards trace streams.

**S8. The foundations are frozen before the packages that could falsify them are designed.**
*Where:* note §5, rule 3 and lines 0.9–1.0; R2.

*What:*
- Some packages are the most likely to falsify F2–F5. Their tests would be the conserved basis, attributes, amount bases,
  `aq` anchors, the TPD for charged species and N-phase EOS behaviour:
  - X18 (electrolytes), X19 (solids), X20 (polymers), X21 (assays), X22 (rate-based columns);
  - X13 (reactors), and TX's holdups and controllers.
- They are first designed three to five lines after v2 is frozen, and the F2 probes are synthetic.
- Rule 3 is therefore broken exactly where it matters most.

*Fix:*
- Add to W1 a state-structure sketch of one to two pages for each of X13, X18–X22, PrISMa, TX and X24. Each says what
  the package carries on connections, which phase candidates and methods it needs, and what it refuses.
- Check each sketch against ADR-F2 to ADR-F7 before the freeze.
- This is documents only, at about the cost of one specifier pass.

**S9. The Q3 worked example is wrong, and group molar masses are undefined.**
*Where:* rulings, Q3 "Argument and limiting cases" and Q3.A2.

*What:*
- Take the species `{Na⁺, Cl⁻, NaCl(s), H2O}` with groups (NaCl, H2O). Then rank A = 2 and `zᵀ` is not in the row space
  of A, so `dim(ker A ∩ ker zᵀ) = 4 − 2 − 1 = 1`.
- The intersection is `span{Na⁺ + Cl⁻ − NaCl(s)}`, which is the dissolution reaction, not `{0}`. Condition (ii) holds
  only if R contains the dissolution reaction, so "ker A ∩ ker zᵀ = {0} = span R (complete dissociation)" is false.
- The [gen] expectation in Q3.A2 does not state R for this system.
- The MEA case has the right dimensions (9 − 3 − 1 = 5 = rank R).
- Separately, Q1.R1's `ṁ = Σ M_c n_c` needs a molar mass `M_g` for each group, and Q3 never defines one. A valid `M_g`
  exists if and only if every fast reaction conserves mass (M ⊥ span R).

*Fix:*
- Correct the example: R contains the dissolution reaction once `SOLID.NaCl` is a candidate.
- State R explicitly in each case of Q3.A2.
- Define `M_g` and add the check to Q7.A3.

**S10. The inequalities in Q6.R5 fail in floating point.**
*Where:* Q6.R5 and Q6.A5.

*What:*
- A monodisperse stream satisfies `λ0 λ2 = λ1²` exactly, and degree of polymerisation 1 gives `λ0 = λ1`. The computed
  product fails the strict test about half the time through rounding alone, so legitimate feeds would be rejected as
  invalid trial states.
- Living polymerisation runs at a polydispersity index of `1 + 1/DP`, right at that boundary.

*Fix:*
- Register the inequalities with a roundoff allowance, for example `λ0 λ2 ≥ λ1² (1 − 8ε)`.
- Add the boundary case to Q6.A5: a monodisperse feed is admitted.

**S11. ST's artifact is built before F2's grammar exists.**
*Where:* note §2.6, constraints on the 0.4 packages.

*What:* ST is built in 0.4, while ADR-F2 (phase ids, substreams, convention) is written in W1 P2.

*Fix:*
- ST keys phases by the structured triple of Q4.R1 and substreams by id, never by rendered strings.
- It records the enthalpy-convention id with each `h` and `s`.
- Its artifact schema is extended only additively.

### Notes

- **N1. The index check is structural only (D05).** "A matching on ∂g/∂z" (note §2.5.3) admits systems that are
  structurally index 1 but numerically near index 2. One example is a fixed-volume vessel filled with PR liquid: `P` is
  present in the expression graph, but `∂V/∂P ≈ 0`. Add a rank and conditioning check at consistent initialisation, with
  a typed limitation. F7's index-2 probe passes only when incompressibility is structural.
- **N2. The F0 sensitivity exit is overstated.** A one-ulp parameter change moves M2–M4: `constants_sha256` is an R0 field
  (ADR 0007, line 34). It does not move M5's verdicts and check results. Restate the exit, and test M5 with a structural
  perturbation.
- **N3. Legacy fingerprints.** In §2.1.7, "the definition SHA joins the numerical-model fingerprint" must apply to v2
  only. Otherwise M2 and M3 move for every legacy run.
- **N4. Gaps in the dependency table.**
  - X21's acceptance case (an assay preheat train) needs F5 and F6, and X09's PR liquid regime, but X21 lists only F4.
  - X09 widens the reactor box and adds the PR liquid regime. On legacy `c1.*` that conflicts with the freeze; on
    `std.*` it needs F6. Say which.
  - Neither gap changes the order of the release lines.
- **N5. PrISMa's adsorbed phase has no home.** It fits neither Q4's families nor Q8's criterion: a sorbent in a `solid`
  substream cannot be in equilibrium across substreams (Q8.R3). Decide in ADR-F5. One option: for equilibrium, an
  adsorbed phase `SOLID.<isotherm model>` with the sorbent as a `mixed` component confined to it; for kinetics, the
  loading in a solid substream with linear-driving-force rows.
- **N6. Q2.R2 and R-924.** Q2.R2 refuses a liquid-only method for a component anchored as ideal gas. R-924 asks for
  containment by declaration where it is possible. An anchor bridge through the record's `Δvap h°(T°)`, with the boundary
  defect reported, would contain it.
- **N7. Q4.R3 ordering.** The thresholded lexicographic comparison is not transitive for three or more liquids that lie
  within about `τ_comp` on the first key. Sort with exact comparison and attach the near-threshold flags afterwards.
- **N8. Q5.R4 `near_critical`.** The test `λ_min(B) < τ_spin` also fires on the spinodal far from any critical point. The
  classification stays conservative, but the name misleads; add a distance-to-critical criterion or rename it.
- **N9. F6 scaling gate.** 10–100 stages with 10 components is about 3e3 variables, two decades below R1's 1e4–1e5. Add one
  point at rate-based size.
- **N10. Conserved holdups.** In §2.5.2, the conserved holdups are the carried amounts: groups (Q3) and partition classes
  (Q6), not only component amounts.
- **N11. Agent contract.**
  - `check_admission(unit, method, definition)` cannot pre-check refusals that depend on the flowsheet: anchors (Q2.R2),
    basis compatibility (Q3.R5), solid roles (Q8.R2) and grids (Q6.R4). Either widen it to check a draft revision, or
    state that these refusals come from validation.
  - C2 descriptors should carry each unit's parameter and port schemas, so that agents can author documents without
    reading code.
  - C1 should state that ids containing `/ @ # [ ]` never appear unencoded in URL paths or filenames. The CLI
    documentation must give quoting rules: `#` and `[ ]` matter in POSIX shells, `@` and `#` in PowerShell.
  - C3's failure-kind taxonomy needs a class for codes that are not failures: `relabel`, `extrapolated`, limitations.
- **N12. F3 store on Windows.** `os.replace` onto a file that a reader holds open fails. In a content-addressed store,
  "the target exists, so done" is correct; say so. Also consider the 260-character path limit.

### Unnecessary complexity

- **U1. v2 definitions with `thermal_coordinate: T` (Q1.R5).**
  - They add a second coordinate path to every `std.*` unit, and a refusal path for degenerate states.
  - They provide nothing that `ĥ` lacks: every state they can hold, `ĥ` can hold too. R-924 is therefore not engaged by
    dropping them.
  - Keep `nTP-v1` for v1 and legacy only, or make the thermo face the only place where the coordinate is visible.
- **U2. The lifted formulation in F5.** Defer it until a benchmark needs it, and keep the slot.
- **U3. One job operation per run kind.** Seven kinds on four transports is 28 rows. A single typed `submit_run(kind,
  documents)` with per-kind schemas is more uniform for agents.
- **U4. The opt-in v1 → `std.*` mapping tool.** Defer it until someone asks; the equivalence tests exist without it.

## 3. Judgements on the architect's least-certain choices

**(a) The `ĥ` coordinate, made mass-specific by the specifier: endorse.**
- Q1's argument is correct. S is concave in H, so `T(ĥ)` is continuous and non-decreasing, and the state is single
  valued. At degenerate states `T` fixes only an interval of `ĥ`, which is exactly the FB-04 case.
- The note's claim that "h is strictly increasing in T" is false, and the ruling corrects it.
- Mass is the only normalisation defined on `kg` and `segment_mol` bases.
- The costs to fix are S3 (reactivation), S7 (scaling) and S2(c) (specifications on `T`). U1 removes the duplicate
  coordinate.
- This is the right foundation for a simulator with solids, polymers and assays.

**(b) Two unit code paths for a long time: endorse the freeze, with conditions.**
- The freeze is the only route to a bitwise proof, and rewriting legacy units in place would move every `model_version`.
- Condition 1: the freeze is byte-level (S1).
- Condition 2: equivalence is defined (M2).
- Condition 3: there is a retirement rule. Once a family has `std.*` parity with equivalence evidence, it is closed to
  new v2 work, and v1 revisions keep running it unchanged. Maintenance is then bounded to legacy-only bug compatibility.
- Without the retirement rule the cost is open-ended (question 1).

**(c) Owning the BDF step loop, and LOA for MINLP: endorse both, with qualifications.**

*The step loop:*
- The note's reason for rejecting IDAS ("hides step decisions") is true of CasADi's integrator wrapper, not of IDAS: its
  one-step mode exposes every step, with its order and size.
- The sound reasons are others: `forced_replay` must impose recorded decisions (D20); phase-set events map onto
  attempt-sized integration segments (ADR 0005); co-simulation needs communication points.
- Condition 1: follow the published DASSL/IDA BDF with a fixed leading coefficient, orders 1–5, the local error test and
  the convergence-rate test. Do not invent one.
- Condition 2: the corrector is modified Newton with Jacobian reuse, not the globalised steady-state Newton.
- Condition 3: register an IDAS cross-check gate (trajectories and event times within registered tolerances on a fixed
  set) as part of TX's acceptance.

*LOA:*
- The argument against big-M and hull relaxations follows from this architecture's zero-flow semantics and is correct.
  Dormant streams of undefined composition would sit in every relaxation.
- Condition 1: put the master problem in reduced space, with cuts from the reduced gradients of the parametric twin, so
  the MILP does not carry every flowsheet variable of every alternative.
- Condition 2: initialise with a set covering of the disjuncts.
- Condition 3: register one superstructure small enough to enumerate. On it, the LOA result must match full
  enumeration. That is the optimality evidence beyond "local per NLP".

**Freezing the v2 grammar before F3–F6 are built: do not freeze all of it at the end of W1.**
- Freeze at the end of W1 the parts built in 0.5: materials, records, the data lock, and connections including energy
  and signal (M1). Add the `revision_section` mechanism.
- Freeze the slots that F4–F6 fill (`property_methods`, phase assertions, templates) at the end of 0.6, after the line
  acceptance has exercised them. Until then, documents that use those slots are marked preview and fall outside the
  frozen-schema promise.
- The alternative is to freeze everything at W1 and accept that a v3 may follow, which costs one more permanent reader
  (ADR 0002 D7). See question 2.

## 4. Questions for Frank

1. **Retire the legacy families for new work once `std.*` reaches parity?**
   - Default: yes. v1 revisions run legacy code unchanged forever. A new v2 revision uses a family's `std.*` units once
     that family has parity and equivalence evidence.
   - Alternative: keep both paths open indefinitely. That is more freedom for users, and double maintenance with no end
     date.
2. **When is `ProcessRevision` v2 frozen?**
   - Default: the core is frozen at the end of W1, and the F4–F6 slots stay preview until the end of 0.6.
   - Alternative: everything is frozen at the end of W1, accepting that a v3 may follow.
3. **FB-04 (1) on the legacy turbine in 0.4?** F5 and `std.turbine` supersede it in 0.6, so it is a second design of the
   same physics.
   - Default: keep it only if a course needs a two-phase turbine outlet before 0.6; otherwise drop it and let F5 deliver.
   - Alternative: keep it as planned.
4. **Spend one more design-lane pass on the state-structure sketches of S8?** This is a cost question against the agent
   budget.
   - Default: yes. R-927 puts design quality first, and these sketches are the cheapest falsification available.

I agree with the defaults already listed for Frank's preferences: O1 (dynamics before the design toolkit), O-6 (water as
the first ordering key) and O-7 (mass-specific `ĥ`). They need no new question.

## 5. What this review did not establish

- **Nothing was built or run.** I checked numerically only the closed-form examples in the rulings, and all of them
  reproduced:
  - the ideal-K values `tm*_V = −0.16` and `tm*_L = −0.025`;
  - the freezing root 267.955 774 920 K and the slope 1.0066e-2 K⁻¹;
  - the floors in Q1 and the arithmetic in the rejection of option (c);
  - Q7.A4's dimension vectors, against the order in ADR 0001 D1.2.
- **SYN-001's K-values.** I confirmed that they do not depend on composition (`thermo/syn001.py:109`), so Q5.A1's
  closed form applies.
- **ADRs not read in full:** ADR 0005, 0008, 0012 and 0013. I relied on the documents' citations of them.
- **Assumptions not verified:** the note's A4 (ADR 0008 A1.2 on U–H relations and a constant mass matrix) remains
  unverified, and so do A1, A2, A5, A6 and the platform facts in R5.
- **Code checked:** only the revision schema (port kinds, `state_definition`, the id pattern, the `decision` role, which
  already exists, so OPT needs no v1 change), the self-hash pattern of the providers, the HTTP routes (only revision and
  job ids appear in paths today), and that the repository has no `.gitattributes`.
- **Not checked:** the inventory's other anchors.
- **Not assessed:** the feasibility of the batching ratio (≤ 0.1×) and the scaling slope (≤ 1.3), which are measured
  gates; R-706 rights questions; correlation choices; release mechanics; MSG's placement.
