# T05 review — six unit models on the PH closure, the revision-built flowsheet, the verifier table and the coupled cases, against `docs/derivations/T05-unit-models-spec.md`, ADR 0011 and `docs/design/T05-generalization.md`

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-25. Plan §1.3: the design lane
reviews every build-lane package that touches residuals, derivatives, phase logic, scaling,
certificates or replay identity. T05 touches all six.
**Brief:** `docs/briefs/T05-implementation-review.md`.
**Reviewed at:** `wp/T05` = `e867597`. Its `src/`, `tests/`, `scripts/` and `benchmarks/` are identical
to `6bb7620`, the brief's head. The build-lane range is `279b2eb..HEAD`: 31 source, script and
benchmark files. The documents in that range belong to the design lane; they were read but not reviewed.
**Run here:**
- The full test suite: **2417 passed** in 92 s. I ran pytest only, not ruff, format or mypy.
- `git diff 279b2eb..HEAD` over `thermo/`, `graph/`, `compile/` and `tests/fixtures/` is empty.
- The only edit to an existing test file (`tests/test_schemas_p01.py`) is additive, as spec §21
  sanctions.

**Environment:** x86-64 Linux 6.12.86, the repository's `.venv`. No CI artefact was examined.
**Measured:** every finding marked *measured* comes from a probe run against this tree in this
session. The probes are built from the tests' own helpers: `tests/t05_w12_support.py` `mini_revision`,
`unit_instance`, `Feed`, `Outlet`, `connection_pin`, `duty_pin`, `bind`, `solve_from`, and
policy `T05-W13`. Each probe (P1–P6) is described where it is used so that it can be re-run. Nothing
is marked measured that was only read.
**Amendments made in this commit:** none. The spec, the design note and the register are left to the
`specifier`, who is ruling concurrently on `docs/briefs/T05-rulings.md`. This review does not re-rule
those six questions; §7 lists the amendments it recommends.

---

## 1. Verdict

**The package is implemented as specified and designed. On SYN-001 it is inert by construction as
well as by evidence.**

- **The executor.** The dispatch is a type test that returns the legacy expressions verbatim
  (`executor._splits`, `_mass_mapping`). The general `_solve_eo` branch is a separate function
  entered before any legacy statement. `_reject_initializer` records the same fields in the same
  order as the pre-T05 `_missing_guess`. The guards in `solve_tear`, `run_session` and `verify` are
  first statements.
- **The traversal.** It is design note §1.5 line by line: the ready rule, the deadlock rule, the
  label from the first computed inlet, and `computed_torn`. `initial_state`'s owned-variable rules
  are §2.2's: exactly one of `duty` and `transferred_duty`, and `None` is a defect.
- **The revision encoding.** It applies no defaults. Pins are consumed through a recording reader,
  where membership does not count as a read. `configuration_sha256` covers everything that selects
  expressions — components, stream order, unit and model ids, port→stream lists, inlet phase, key,
  energy mode, declared side phases and exchanger mode — and no pinned value. A grep of the six
  models found no row structure that depends on a parameter value, so there is no label hole in
  either direction.
- **The split registry.** `plan_revision` enforces all of §3.3 (a)–(e), which is more than the
  design requires.
- **The verifier table** (`verify/table.py`) is R-016-clean by reading. Its only `models` imports are
  pure id helpers (`extent_id`, `work_id`, `total_flow_id`, `vapor_flow_id`, …). Every formula of
  spec §12.2 (errata applied) is present, in note §4.3's category-major order. The one-sided checks
  pass iff `value ≤ τ`, are near-threshold iff `τ/10 < value ≤ 10τ`, and become `not_applicable` at
  a dormant inlet. Declared-phase ports per model are exactly §4.3's list. The pump's work relation
  evaluates fresh liquid enthalpies at `(n_in, T_in, P_out)`, not the unit's isothermal block.
- **The models.** Each model's rows vanish at its own causal answers far from the registered cases
  (*measured*, P5: 161 random acyclic mini-flowsheets, worst `2.2e-6 τ`). The typed-failure order
  is the spec's for all six models. The trial-state harness fails on any unregistered nonzero
  Jacobian entry. The injection, coupled and unit tests read their expected values from
  `ref`, not from the implementation.

**No must-fix.** Nothing found produces a false `CONVERGED`, a false `VERIFIED` or a silently
wrong number. What remains is two refusals that are wrong in kind, one unregistered EO limitation,
and three verification gaps. None is on a registered path.

1. **A revision that declares a non-lifted stream `vapor_liquid` binds, then crashes with a bare
   `KeyError`** (S1). The binding module promises "every refusal is an `Unbound` … never an
   exception", and CLAUDE.md requires explicit unsupported results. *Measured* (P1).
2. **The conversion reactor refuses `X = 1` as `reactant_exhausted(<key>)` for about 6 % of feeds**
   whenever `|ν_k|` is not a power of two (S2). RX-8 hides this because `ν_A = −2`. *Measured* (P2).
3. **A PH-type outlet with one flowing component** — the kernel's saturation route, PHF-6 — **is
   solved causally but not on the EO path.** The run ends `ACTIVE_SET_CYCLING` or `BOUND_BLOCKED`,
   even from the exact root. The spec does not register this limitation (S3). *Measured* (P3, P4).
4. **R-016 for the table** (S4) and **twelve of the revision builder's refusal codes** (S5) are
   correct by reading but pinned by no test.

I recommend landing S1, S4 and S5 before merge; they are small and cannot move a registered number.
S2 and S3 each need a design-lane ruling first (§7).

---

## 2. Must-fix

None.

---

## 3. Should-fix

### S1 — A `vapor_liquid` connection whose producer does not lift the stream binds, then raises an untyped `KeyError`

**Where.** `src/process_runtime/application/revision_binding.py:515-528` (the port check, which has
no such refusal); the crash is at `orchestrator/revision.py:179` → `graph/trace.py:382`. Design note
§1.3 R4 guards only one direction of R-039's assembly rule: a producer's lifted outlet cannot be
declared single-phase by its consumer. The converse is unguarded. A consumer with
`inlet_phase = None` (valve, PH flash, reactor, separator, heater, tp_flash) reads
`<S>.vap.*`/`<S>.liq.*` columns, and nothing allocates them unless the producer is an `outlet`-style
`SPLIT_RULES` model.

**Measured (P1).** `mini_revision` with feed → U-VLV (C1's instance), feed → U-PHF, and feed → U-SEP
(C2's instance), each with `S1` at capability `vapor_liquid`, `(1,1,1)`, 360 K, `1.8e5 Pa`:

```
valve  bind: RevisionBinding   plan_revision: KeyError 'S1.liq.B'
phf    bind: RevisionBinding   plan_revision: KeyError 'S1.vap.C'
sep    bind: RevisionBinding   plan_revision: KeyError 'S1.vap.C'
```

`compile_problem(binding.spec)` instead raises `ValueError: block 'H_S1_vapor' is fed unknown
variables [...]`. A two-phase feed is an ordinary thing for a user to write. It fails with no typed
code.

**Minimal correction.** In `bind_revision_flowsheet`, after the port check: a `vapor_liquid`
material connection whose producer (`from.instance`, `from.port`) is not the `outlet` port of a model
with an `outlet`-style `SPLIT_RULES` entry → `Unbound("unsupported",
"port_phase_unsupported(<producer>.<port>)")`. Reuse the existing code, or a new one recorded in
`T05_DECISIONS.md`. An alternative is a check that `spec.block_inputs` stays inside
`spec.variable_ids` before the binding is returned; it is more general but reports less about the
cause.

**Falsifiable test.** P1's three revisions each return exactly that `Unbound`. The C1–C3X case files
and the SYN-001-shaped revision still bind with unchanged labels.

### S2 — `X = 1` is refused as the key reactant's exhaustion unless `|ν_k|` is a power of two

**Where.** `src/process_runtime/models/syn001/conversion_reactor.py:660-666`. The extent is
`ξ = X n_k/(−ν_k)` and the key's outlet is `n_k + ν_k ξ`, then `flow < 0.0` → `reactant_exhausted`.
At `X = 1` the key's outlet is exactly `0.0` only when `n_k/|ν_k|·|ν_k|` round-trips, which holds for
every `n_k` only when `|ν_k|` is a power of two. Otherwise it is `−2.2e-16` for a fixed fraction of
feeds.

**Measured (P2).**
- Through the model: `ν = (−3, 1, 2)`, key A, `X = 1`, feed `(1.7383439417747188, 0.5, 0.5)`,
  VAPOR, 420 K, `P_r` → `out_of_domain`, `reactant_exhausted(A)`. The same input with `n_A = 1.75` → `ok`.
- In doubles, over 10⁵ uniform `n_k ∈ [0.01, 5]`, the fraction with `n_k + ν_k(n_k/|ν_k|) < 0` is:

| `|ν_k|` | 2 | 3 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- |
| fraction | 0 | 6.63 % | 5.89 % | 6.62 % | 4.19 % |

In a flowsheet the refusal becomes `INITIALIZATION_FAILED` at the traversal. The contract admits
`X ∈ [0, 1]` closed, and RX-8 registers `X = 1` as supported. Spec §14's exact-zero claim for RX-8
("by generator claims on the reactor's double arithmetic") is true only for the registered `ν`.

**Needs a decision** (spec §6.3 prescribes "the rows' arithmetic"). I would go this way:
- the evaluator writes the key's outlet as `n_k − X·n_k`. This is exactly `0.0` at `X = 1` and
  `≥ 0` for every `X ≤ 1`, because rounding is monotone;
- the exhaustion test applies to the non-key components only;
- still no clipping.

The EO row `n_in + ν ξ − n_out` is unchanged, and it is left with at most one ulp at the causal
answer, far inside `τ`. A non-key reactant exhausted *exactly* (RX-6) is a boundary coincidence of
the data, and a one-ulp refusal there is defensible. Leave that as written.

**Falsifiable test.** The P2 feed at `X = 1` returns `ok` with `n_out,A == 0.0`, and so does a sweep
of `n_k` for `ν_k ∈ {−3, −5, −7}`. RX-1…8 and A06 are unchanged.

### S3 — A single flowing component on the saturation route is solved causally, never on the EO path; the limitation is unregistered

**Where.**
- Spec §4.4 step 2 returns `TWO_PHASE` at `T_sat`, with the split by the lever rule
  (`ph_kernel.py:352-419`).
- On the EO path the attempt's regime comes from the provider's TP flash. Its liquid test comes
  first (SYN-001 §5.1), so `K_k = 1` classifies `LIQUID` and the attempt pins the wrong branch.
- Separately, `initial_state` re-splits a heater-style lifted outlet with `tp_state`
  (`orchestrator/revision.py:145-157`). This follows design note §2.2 step 5. On this route it
  yields `V = 0`, contradicting the comment's "with the kernel the unit used". The start therefore
  misses the energy row by `β n Δh`.

**Measured.**
- **P3 (valve).** Feed `(0, 2, 0)`, 370 K, `1.8e5 Pa`, LIQUID → U-VLV → `1e5 Pa` → sink.
  - Causal: `ok`, `TWO_PHASE`, route `saturation`, `T = 360 K`, `β = 0.0336`.
  - `x⁰`: `S2.V = 0.0`, `S2.L = 2.0`.
  - `execute_plan`: `ACTIVE_SET_CYCLING`, `active_set_cycling(U-VLV:LIQUID; phase_wall(patience,
    U-VLV:VAPOR->LIQUID))`.
  - Re-seeded with the kernel's own lever-rule split through `solve_from(..., user_guess)`: still
    `ACTIVE_SET_CYCLING`, after 2 iterations. So the start is not the whole cause.
- **P4 (PH flash).** PHF-6's inputs (`(0, 2, 0)`, 300 K, `P_r`, LIQUID, `Q_spec = 42 000 W`) as feed
  → U-PHF → two sinks.
  - Causal: `ok`, 1.0/1.0 mol/s at 360 K.
  - EO: `BOUND_BLOCKED` after 1 iteration, at `S2.T = 378.75 K`, `S3.N = 0`.
  - Controls: with 1e-6 mol/s of A added, and at PHF-1's composition, the same flowsheet
    `CONVERGED`.

Every outcome is typed and none reaches a certificate, so this is not a false success. But the spec
registers the route as a supported unit result and says nothing about its EO face. §4.7 registers
T05's one EO singularity (dormant outlets, Q-R4) and §18 lists what is not established. This is a
second one, and a pure-component stream flashing across a valve is not an exotic flowsheet.

**Needs a decision.** I would register it as a limitation in §4.7 and §18: "a PH-type outlet with
exactly one flowing component at `T_sat` is not solved on the EO path; typed failure, never
`VERIFIED`". Pin that with P3/P4 as tests asserting a typed outcome. Then either:
- make `initial_state` take the unit's closure split for heater-style outlets (from
  `evaluate_with_closure`/`evaluate_with_split` rather than a re-flash), amending note §2.2 step 5;
  or
- correct the comment.

A real remedy touches ADR 0005's classification (a `TWO_PHASE` fingerprint at `K_k = 1`), so it is
the design lane's, beside Q-R4's `ZERO_FLOW` remedy. Interaction: Q-R1, where near-pure feeds
converge on the EO path (P4's control) and the conditioning question is causal-only.

**Falsifiable test.** P3 and P4 as mini-revisions assert the registered typed outcome. If
`initial_state` is changed: for every PH-type heater-style unit, its split columns in `x⁰` equal the
unit's closure split.

### S4 — R-016 for the verifier table is true by reading and pinned by nothing

**Where.** `src/process_runtime/verify/table.py:32-70`. The table's independence from row builders,
evaluators, the kernel and `admission.py` is the whole reason it exists (spec §12.1, note §4.1). The
brief lists it as the build lane's first uncertainty. The imports are id helpers today. But
`table.py` already imports the reactor, pump and flash modules for those helpers, so a later edit
that calls, say, `ph_kernel.port_enthalpy` or `admission.admitted_enthalpy` would pass every test.
The cross-validation compares legacy with general, not general with the solver.

**Minimal correction.** An AST test over `verify/table.py`:
- every `from process_runtime.models…` import names only id helpers from an explicit allow-list
  (`duty_id`, `flow_id`, `pressure_id`, `temperature_id`, `extent_id`, `total_flow_id`,
  `work_id`, `vapor_flow_id`, `liquid_flow_id`, `vapor_total_id`, `liquid_total_id`, and the
  revision view types);
- no module in `models.rows`, `models.syn001.{ph_kernel, admission, blocks}` or
  `compile` is imported at all.

The spec's A00 applies the same rule to the twin.

**Falsifiable test.** Adding `from process_runtime.models.syn001.ph_kernel import port_enthalpy` to
`table.py` fails it.

### S5 — Twelve refusal codes of R1–R5 and the port check have no test

**Where.** Design note §7 W1.b requires "one test per refusal of R1–R6 (kind and code)". These codes
occur in `src/` and nowhere in `tests/`:
- `revision_flowsheet.py:175` `instances_missing`; `:190` `phase_capability_unsupported`;
  `:196` `endpoint_missing`; `:201` `port_direction_conflict`; `:228`
  `specification_value_unreadable`; `:239/:252` `specification_target_unknown`; `:249-279`
  `specification_unsupported`; `:334/:344` `parameter_unreadable`;
- `revision_binding.py:116/:528` `port_unwired` (itself a logged interpretation); `:521`
  `port_unsupported`; `:523` `port_direction_unsupported`; `:525` `port_multiplicity_unsupported`.

I read each path and found no defect, but nothing would notice a change of kind or code.

**Minimal correction.** Extend `test_t05_w1b_revision.py`'s refusal parametrization with one
minimal revision per code.

**Falsifiable test.** The same parametrization, asserting `(kind, code)` exactly.

---

## 4. Notes (no change required, or a wording amendment recommended in §7)

- **N1 — The same construction is written three times, and the declared-phase helper twice.**
  - `component_separator.lifted_inlet_enthalpy` (`:202`) repeats `tp_state.stream_enthalpy_terms`
    (`:453`) line for line. Both repeat K02's frozen `TPFlash._inlet_enthalpy` (`flash.py:456`); only
    K02's copy is justified.
  - `admission.admitted_enthalpy` (`:42`, used by the separator and exchanger) and
    `ph_kernel.port_enthalpy` (`:449`, used by the PH flash, valve, reactor and pump) are two helpers
    for spec §5.2 (3). They share codes but not messages.

  Consolidate: route the separator through `stream_enthalpy_terms` and keep one declared-phase
  helper. Its inertness test is identical block ids and inputs at the separator's trial states.
- **N2 — The saturation route skips its own acceptance** (`ph_kernel.py:337-349`, `:413-419`). The
  `ln K` bisection's `converged` flag is dropped. §4.4 step 5's `τ_E` test is applied to the bracket
  route only, not to the lever-rule `residual`. Both are harmless on SYN-001: about 44 bisection
  steps on a 160 K interval, and an enthalpy exactly linear in `β`. Either check them, or say in §4.4
  that the route is exact by construction.
- **N3 — Two defect guards have no failing control:** a second traversal that tears differently
  (`orchestrator/revision.py:105-109`), and `duty`/`transferred_duty` both or neither (`:126-130`).
  Both are low risk; a test-double unit would pin each.
- **N4 — C3X's R0 entry does not carry A20's discriminant.** The `t05` key has
  `outcome: INITIALIZATION_FAILED` and the event kinds, but `r0_projection` drops messages, so the
  typed code `temperature_cross(cold_end)` is not in R0. The CI pair would not see a platform
  difference in *which* check refused; only the local gate pins it
  (`tests/test_t05_c3x_initializer.py:42`). This follows the design ("no message enters"), and codes
  carry no float (R-029). It interacts with Q-R5; the specifier may want the first line of a typed
  message admitted.
- **N5 — The verifier and the builder share `parse_revision`.** Design note §4.1 accepts this ("the
  declaration's inputs"). A routing defect in the parser — a pin sent to the wrong column, a unit
  misread — would therefore be common-mode between solve and check. W11's kind and SI-unit check
  narrows it. The pinned id lists and the twin-state tests would catch a mis-routed pin in the
  registered cases. Recorded, not a change.
- **N6 — Non-finite pinned inputs reach the kernel** (logged interpretation U1 (2)). *Measured*
  (P6): `PHFlash(duty = nan)` → `not_converged`, `ph_ill_conditioned`; `±inf` →
  `ph_outside_domain(above|below)`; `pressure_drop = nan` → `pressure_outside_domain(outlet)`. All
  typed, but `ph_ill_conditioned` misnames a NaN. The revision path's `check_quantity` is the
  primary guard. A construction refusal would name it honestly; that needs a code the spec does not
  have, so it is the specifier's if wanted.

---

## 5. Rulings

### 5.1 Brief §3 ("least sure")

1. **R-016 independence of `verify/table.py`.** Sound by reading:
   - no row builder, evaluator, kernel, `admission` or cache is reached;
   - energies are `checks.enthalpy_flow` fresh flashes;
   - phase properties come from fresh `evaluate_phase` calls on a fresh `Syn001Provider()`.

   The formulas and order match spec §12.2 and note §4.3 item for item. The one-sided semantics and
   the per-model declared-phase ports are §4.3's. Unpinned: S4. The splitter's missing energy check
   is Q-R3's; I have not re-ruled it.
2. **The executor dispatch.** No SYN-001 path changed. `_reject_initializer` is inert. Fix
   `3e8476d`'s prefix rule is right: a refused pass tears a prefix of pass 1, and both C3X tests
   pin unit, code and message. `initial_state`'s `duty`/`transferred_duty`/`W`/`xi` filling is §2.2.
   The split filling is §2.2 step 5 — except on the saturation route (S3).
3. **Residual/Jacobian ↔ evaluator.** They agree, *measured* (P5) at the models' own causal answers
   over random inputs:

   | Model | Samples | Worst `|row|/τ` |
   | --- | --- | --- |
   | Valve | 40 | 3.4e-7 |
   | PH flash | 40 | 2.6e-7 |
   | Reactor, T mode | 27 | 2.1e-7 |
   | Reactor, duty mode | 27 | 2.2e-6 |
   | Pump | 27 | 9.5e-9 |

   - **Pump.** The isothermal block is fed `(n_in, T_in, P_out)`. `work_row` pairs terms per
     component, so the `T_in` partial cancels exactly, which is the registered cancelling partial.
   - **Exchanger.** `energy_row(sink=)` is `−Q + Ḣ_hi − Ḣ_ho`, and K02's `sink=None` path is
     unchanged term for term.
   - **Separator.** The lifted-inlet enthalpy is the TPFlash construction (N1).
   - **Declared inlets.** The evaluator applies R-007 and then writes exactly the block the rows
     write, which discharges spec F7.

   Exceptions: S2 and S3.
4. **The revision encoding.** R1–R6 as §1.3, with no defaults (the optional K02 `pressure_drop`
   must be `0.0`). The unit check covers parameters and specifications. `configuration_sha256`
   coverage is as §1 states. Gaps: S1 (the converse of R4) and S5 (untested codes).
5. **Tests that verify nothing.** I found none that compares a function with itself or reads its
   expectation from the implementation:
   - the unit, trial-state, injection and coupled tests read `ref`;
   - the table's id lists are written out per case;
   - A12's "fails exactly one check" is real, because `assess` collects (5)–(8).

   The gaps are the unpinned claims S4, S5 and N3.

### 5.2 The engineers' interpretations (`docs/T05_DECISIONS.md`, 2026-09-25)

None of them is wrong in a way this review found. The specifier is ratifying them as a block
(rulings brief §3). Two remarks feed that ruling:
- U1 (2)'s unrefused non-finite `Q_spec` is N6.
- W1.d's "one running accumulator for the material envelope" and "mixer inlet always
  `.<port>.<S>`" are consistent with §4.3 and the pinned ids.

---

## 6. FOR FRANK

Nothing here needs Frank's decision to proceed. One scope preference is his to overrule:
- **S3: a pure-component stream flashing to two phases on the EO path** (a valve or PH flash with
  one flowing component). The default recommended here is to register it as a v0.1 limitation, with
  a typed failure that is never `VERIFIED`. Putting it in T05's scope needs a phase-classification
  change under ADR 0005 — design-lane work, and larger than the rest of this review.

---

## 7. What the fixes must not do; amendments recommended to the `specifier`

**The fixes.**
- **S1 must move no label.** The new refusal sits in the binding, before construction. Every case
  file and the SYN-001-shaped revision must bind to the same `configuration_sha256` and label, and
  protocol P must hold.
- **S2 must not clip, and must not touch the rows.** Only the evaluator's arithmetic for the key's
  outlet changes. RX-1…8, A06 and A14 stay as registered: RX-8 is exact either way at `ν_A = −2`.
  RX-6's non-key exact exhaustion keeps the `< 0.0` test.
- **S3 must not change the saturation route's causal result** (PHF-6 exact, A14). It must not
  introduce a regime or a fingerprint value without an ADR. If `initial_state` changes, the
  SYN-001-shaped start must stay bitwise equal to the legacy start (W1.c's test) and C1–C3's
  trajectories must stay unchanged; none of them has a single-component outlet.
- **S4 must not be discharged by copying the id helpers into `table.py`.** Shared ids are
  sanctioned (note §4.1); shared functions are not.

**Amendments recommended (design lane; not made here).**
1. **§6.3 and §14 (S2).** The key's outlet is `n_k − X n_k`. Exhaustion is tested on the non-key
   components. The exact-zero claim at `X = 1` holds for every `ν_k`.
2. **§4.4 step 2, §4.7 and §18 (S3).** The EO face of the saturation route, and its registered typed
   outcome. Note §2.2 step 5: the start split of a heater-style PH-type outlet is the unit's closure
   split.
3. **Note §1.3 R4 (S1).** A `vapor_liquid` connection must be produced by the `outlet` port of an
   `outlet`-style lifting model; otherwise `unsupported`, with its code.
4. **§4.4 (N2).** Either apply step 5's `τ_E` to the lever-rule residual and require the `ln K`
   bisection to converge, or state that the saturation route is exact by construction.
5. **Q-R5 (N4).** Consider admitting a typed failure's first message line (a registered code, no
   float) into the `t05` R0 projection, so the CI pair compares A20's discriminant.

**Not examined:**
- the manifest documents' contents beyond their tests (A01–A03);
- K02's `lift_two_phase_stream` and the provider;
- `scripts/t05_floors.py`;
- the numbers in `docs/t05-measurements.md`, beyond the gate count;
- the case YAMLs line by line; they were checked through W11's binding tests and the probes;
- the CI run;
- the separator and exchanger in P5's sweep (their rows are linear in the evaluator's arithmetic);
- inputs at the domain's edges.
