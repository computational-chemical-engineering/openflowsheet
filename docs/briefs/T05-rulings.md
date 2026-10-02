# Brief — T05 ruling round (one batch, build lane → design lane)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-25. **Package:** T05, branch `wp/T05`.
**Deliverable:** rulings written as amendments to the documents they touch — the spec
`docs/derivations/T05-unit-models-spec.md`, the design note `docs/design/T05-generalization.md`, and
(if a new decision a later session could undo) a register entry in `docs/decision-register.md` —
plus a short ruling list at the end of this file (§4), each item: ruling, what the build lane must
change (if anything), and the acceptance test. Do not edit code. Do not commit; the build lane
commits.

## 1. Where T05 stands (all measured; `docs/t05-measurements.md`)

All six models and the kernel are implemented and match every registered unit case (56 + 11
construction), trial-state rows/Jacobians at the twin's 53-bit floors, A06 ≤ 6e-8 τ, A15 at all
seven structures. W1 (the generalization) is in, SYN-001 bit-identical after every chunk (identity
document `b364bb3d…`, structural `4ce030ca…`, policy `21c44e10…`). C1, C2, C3 converge from
`traversal-G0-v1` within §11.5 (worst: C3 3.6e-8 K, 3.3e-7 W) and are `VERIFIED` (160/116/139
checks, none near threshold, bounds 8.1e-14 / 3.9e-15 / 3.2e-9); C3X fails typed at U-HX
`temperature_cross(cold_end)` and its twin state is `FAILED` on exactly `cold_end = +10 K`; A22's
four injections reproduce (≥ 4.7e3 τ); A27 as designed. Gate 2417 green.

## 2. The questions

### Q-R1 — The PH kernel's `ph_ill_conditioned` guard (spec §4.4 step 5) misses a mid-jump target

Measured (engineer, W2): PHF-6's inputs `(0, 2, 0)` with `1e-12` mol/s of C added and PHF-6's duty
(the target exactly mid-jump of B's latent heat) → kernel returns `ok`, `|f| = 5e-8 W`: the
provider's Rachford–Rice is ill-conditioned there and returns its first bisection midpoint β = 1/2,
which meets the target by coincidence. A target at 30 % of the jump → `ph_ill_conditioned`,
`|f| = 30 W`; a `1e-9` impurity → `ph_ill_conditioned`, `|f| = 7e-3 W`. The returned state is
consistent with the provider's own flash at `T*`, but that flash is poorly determined. §4.4's text
("this step makes that visible instead of silent") claims more than step 5 delivers.
**Question:** amend §4.4's claim (a limitation, stated), or add a conditioning criterion (which,
with what threshold, and what code)? The current implementation is §4.4 as written.

### Q-R2 — Component sums in the general verifier: Python `sum()` or left to right?

Note §4.3 says every sum accumulates left to right. The legacy K04 builders use Python's `sum()`,
which on CPython ≥ 3.12 is Neumaier-compensated. At W1.d's non-root x⁰, `sum(S3.liq.*)` =
3.7937936767848512 vs left-to-right 3.7937936767848517, so `total.S3.L` is `0.0` legacy and
`−4.44e-16` general, and the required bitwise cross-validation fails. The engineer's DECISION
(`15aed94`, isolated): sums over **one stream's components** use `sum()`; every other sum stays left
to right (the legacy writes those with explicit `+`). **Question:** ratify (amend note §4.3), or
rule otherwise. Note: `sum()`'s result depends on the CPython version (≥ 3.12); the CI pair runs the
same pinned interpreter.

### Q-R3 — The K02 splitter has no energy check in the general table

Legacy K04 has `energy_balance.splitter`; spec §12.2 (and note §4.3) give the K02 splitter only
`material_balance.U.<c>` and `specification.U.ratio.<c>`. At x⁰ the legacy check is 2458.79 W (not
vacuous: it catches a recycle/purge temperature copy that the material checks cannot). So in C3 the
general certificate is weaker than K04's on the splitter. **Question:** add
`energy_balance.U-SPLIT` = `Ḣ(in) − Ḣ(rec) − Ḣ(pur)` (heat_rate, [A09]) to §12.2 and the note's order
(and pair it with the legacy in W1.d's cross-validation), or state why not.

### Q-R4 — W0.8 (spec Q4): a dormant PH-type outlet does not fail on the rank path

Measured (W13a): a VLV-Z flowsheet (feed `(0,0,0)`, 330 K → valve to `9e4 Pa` → sink) and a PHF-Z0
flowsheet both return `CONVERGED` at iteration 0 with no Jacobian formed — `traversal-G0-v1`'s start
is the exact root. K04's regularity screen on the target Jacobian at that root: `RANK_DEFICIENT`,
rank 15 of 18, so `grade` gives at best `UNVERIFIED` — "never `VERIFIED`" holds. Two further facts:
(a) the rank loss is **3**, from the three equilibrium rows (`…-equilibrium:{A,B,C}`) whose gradients
vanish identically at zero flow in the `TWO_PHASE` form the attempt ran — not the single loss §4.7
registers for the temperature column (A15's registered column structure itself holds); (b) the
zero-flow lifted outlet is fingerprinted `TWO_PHASE` in the attempt signature and `branch_found`,
not `ZERO_FLOW`. **Questions:** what does Q4 register (suggested: "`CONVERGED` at x⁰; certificate
`UNVERIFIED` (`RANK_DEFICIENT`); never `VERIFIED`")? Should §4.7 state the rank-3 structure? Is (b) a
defect for T05 (ADR 0005's regime lattice has `ZERO_FLOW`) or a registered limitation deferred with
§4.7's remedy? No registered coupled case contains a dormant PH-type outlet.

### Q-R5 — Digests and decimal strings inside the `t05` identity key

Note §6 builds `t05` from existing projections: `execution_plan_r0` (which writes the plan's declared
`column_scales`, `row_scales`, `bounds` as decimal strings — as `t02` does) and T03's fingerprint
projection (which keeps `constants_sha256`, `variable_ids_sha256` and `delta_scaled_inf "0.0001"` —
as `t03` does). Spec A24 says "no new R0 field"; the engineer's brief said "no float or digest".
**Question:** confirm the note's projections as they are (the build lane's reading), or require a
filter.

### Q-R6 — Informational, ratify or amend: C3's solution-error bound margin

C3's recorded bound `3.18e-9` is 3.1× under §11.5's `1e-8` because the Newton stops at tolerance
(worst residual `U-PHF:PHF-duty` at 1.9e-2 τ), not at roundoff. It passes; say whether §11.5's
argument needs a note.

## 3. Engineer interpretations already logged (ratify as a block, or name any to change)

`docs/T05_DECISIONS.md` lists every local interpretation the engineers made where the spec or note
left a choice (typed-code borrowings, dormant exchanger side handling, refusal codes of the revision
builder, unit checks on specifications, A03's unit/flowsheet split, W12's injection extras). Read
that file's entries of 2026-09-25 and either ratify them as a block or name the ones to change.

## 4. Rulings (the design lane fills this in)

**Ruled by** the design lane (`specifier`), 2026-09-25. Q-R7 and Q-R8 were added mid-round from the review (`docs/reviews/T05-review.md` S2 and S3). The review's other §7 amendments are ruled here too: S1 at the end of this section, N2 in Q-R1, N4 in Q-R5, and N6 in the §3 block.

- **Where the amendments are.** In place in the spec `docs/derivations/T05-unit-models-spec.md` (header, §3.5, §4.4, §4.7, §5.1, §6.3, §6.4, §11.5, §12.2, §12.5, §14, §15, §16.1, §18, §19, §20) and in the design note `docs/design/T05-generalization.md` (header, §1.3 R4, §2.2 step 5, §4.3, §6, §7 W1.d). Every amendment is dated 2026-09-25, marked "ruling round" and carries its reason.
- **Register entries.** R-048 to R-051.
- **What does not change.** No number in `benchmarks/t05/reference_values.yaml`; the generator is not re-run. No ruling needed one to change.
- **Measured by the design lane this round** (scratch probes; each is re-measured by an acceptance test named below):
  - the near-pure kernel grid (Q-R1);
  - C3's splitter energy balance (Q-R3);
  - the exact against the estimated `‖Ĵ⁻¹‖₁` on C1–C3 (Q-R6).

### Q-R1 — The PH kernel's `ph_ill_conditioned` guard

**Ruling: amend the claim and state the limitation; add no conditioning criterion.** Register R-049. Spec §4.4 step 5, the new paragraph "What `ok` guarantees", §5.1, §18, §19 Q11; review N2 is folded in.

- **What step 5 is.** An acceptance test on the answer, not a conditioning detector. `ok` means that the provider's own split at `T*` carries `H*` to within `τ_E`.
- **Measured.** I ran `(ε, 2, 0)` and `(0, 2, ε)` at `P_r`, with targets `12 000 + φ · 60 000 W`:
  - At `ε ≤ 1e-9` only `φ = 0.5` is `ok`. Its `β = 1/2` exactly, and it lies within `7e-10 mol/s` of the lever rule.
  - Every other `φ` is `ph_ill_conditioned`, with `|f| ≥ 2.6e-2 W`.
  - At `ε = 1e-6` all targets are `ok`.
- **Why the `ok` answer is right, not lucky.** Near purity, `Ḣ` is affine in the vapour flow (§4.2). So meeting `τ_E` fixes `V` to `τ_E/min Δh_i ≈ 4e-8 mol/s`, which is the energy tolerance's own resolution.
- **Why no criterion.** A criterion that refuses whenever adjacent doubles of `T` differ in `Ḣ` by more than `τ_E` would refuse correct answers, on a threshold that no case calibrates.
- **N2, folded in.** The saturation route now passes through step 5 as well. Its `T_sat` bisection has its own budget, of step 4's size, and exhausting it is `ph_not_converged`.

**Build-lane changes.**

- [ ] `ph_kernel.py`, saturation route:
  - do not drop the `T_sat` bisection's `converged` flag: `not_converged` → `ph_not_converged`, with a budget of `max_evaluations`, counted separately from `f`'s;
  - apply the `|residual| ≤ τ_E` acceptance to the lever-rule answer: `ph_ill_conditioned` otherwise.
  - Acceptance: PHF-6 unchanged (A07, A14), and PHF-6's inputs with `max_evaluations = 5` give `not_converged`, `ph_not_converged`.
  - *Amended 2026-09-25 (design lane, on the build lane's measurement):* the budget-5 half is unmeetable — PHF-6's `T_sat = 360 K` is the domain midpoint and `ln K_B(360 K, P_r) == 0.0`, so the bisection closes at its first step (budgets ≥ 3 → `ok`, 1–2 → `ph_not_converged`); it is replaced by `test_an_exhausted_t_sat_bisection_is_not_converged` (pure B at 1.5e5 Pa: budgets 5 and 52 → `ph_not_converged` with no `f` evaluation, 53 → `ok`), and PHF-6's measured budget pattern is pinned as a positive test, not a strict `xfail`.
- [ ] A29 (new, spec §15). The 20-call grid plus the `ε = 1e-6` control, with the measured pattern pinned as a regression value.
- [ ] Manifests of `syn001.ph_flash`, `syn001.valve` and `syn001.conversion_reactor`: `validity.limitations` states the near-pure limitation and §4.7 (a), (b), as in spec §5.1. Acceptance: A01 passes, and A23 is unchanged (only T05 manifests move).

### Q-R2 — Component sums: Python `sum()` or left to right?

**Ruling: ratified.** Design note §4.3 is amended; register R-048.

- A Σ over the components of one stream (its flows, lifted flows, flow × property products, fractions, fraction × `K`) uses builtin `sum` in component order, the primitive of K04's legacy builders. Every other sum accumulates left to right with the operators as written.
- `pyproject.toml` requires Python ≥ 3.13, so `sum` is Neumaier-compensated on every supported interpreter.
- A future CPython change would move legacy and general together. That exposure is K04's already, not new.

**Build-lane changes.** None: `15aed94` stands. Optionally, point `_component_sum`'s docstring at R-048 instead of "reported to the design lane".

### Q-R3 — The K02 splitter's energy check

**Ruling: add `energy_balance.U-SPLIT` = `Ḣ(inlet) − Ḣ(recycle) − Ḣ(purge)`** (heat_rate, [A09]), in the legacy's operation order. Spec §12.2 and its amendment paragraph; design note §4.3 splitter row; §7 W1.d pair list; spec §20 F11.

- It restores parity with K04, and it is the only independent check of the splitter's temperature copies.
- Measured values:
  - `2 458.79 W` at the shaped `x⁰` (W1.d);
  - `−1.8e-12 W` at C3's solved state (this round), so C3 stays far from threshold.

**Build-lane changes.**

- [ ] `verify/table.py`: `_splitter_energy`, the `energy` rule of `syn001.stream_splitter`.
- [ ] W1.d cross-validation:
  - add the pair `energy_balance.splitter` ↔ `energy_balance.U-SPLIT` (bitwise, at the root and at `x⁰`);
  - add assertion (d), **coverage**: every legacy id is generic (the same id in both) or the legacy side of a listed pair. An unpaired legacy id fails the test and is reported, not paired silently.
- [ ] Acceptance:
  - the pinned id lists gain the id (shaped 146 → 147; C3 139 → 140);
  - A21: C3 is `VERIFIED` and the new check is not near threshold;
  - A20: C3X's second branch still fails exactly `{bounds_and_domain.U-HX.cold_end}`;
  - A22 is unchanged;
  - protocol P (i)–(viii) is unchanged;
  - the identity document minus `t05` = `b364bb3d…`.

### Q-R4 — W0.8: a dormant PH-type outlet on the EO path

**Ruling.** Spec §4.7 (a) is rewritten, §18 and §19 Q4 are resolved, A28 is added, and R-050 is registered.

1. **What Q4 registers.** From the traversal start the solve is `CONVERGED` at iteration 0, and the certificate is `UNVERIFIED`, with a `rank_limitation` (`RANK_DEFICIENT`) and no failing check. It is never `VERIFIED`.
   - "No failing check" is argued (every check at the dormant root is an exact zero or not applicable), not yet measured, because W0.8 did not call the verifier table. If A28 measures `FAILED`, the spec is amended, not the test.
   - The rank-path failure the spec expected applies only to a start that is not the root. Its outcome is not registered.
2. **The rank-3 structure: yes, §4.7 states it.** Each equilibrium row `v_i L − K_i l_i V` is bilinear in lifted flows that are all exactly zero, so there is one zero row per component. The dormant `T` columns lie inside that null space. A15's column structure still holds.
3. **(b) is not a defect, and the brief's premise is wrong.**
   - ADR 0005 D2's lattice is `LIQUID — TWO_PHASE — VAPOR`, with no `ZERO_FLOW`. Dormancy is not a phase selection (K03 §9.1).
   - `TWO_PHASE` is `branch_found`'s `else` arm (T03 §8.2 as amended). It names the form that ran, not a phase found.
   - The certificate's `phase_branch` already records `ZERO_FLOW`.
   - Changing either needs an ADR, deferred with the `ZERO_FLOW`-regime remedy.

**Build-lane changes.**

- [ ] A28 (new, spec §15), built on W0.8's two mini-flowsheets, through `verify_revision`. Items 1–5:
  1. outcome and iterations;
  2. exact root values;
  3. exactly the three equilibrium rows all-zero, and rank 15 of 18;
  4. `UNVERIFIED` with `rank_limitation`, and no failing check;
  5. `branch_found` `TWO_PHASE`, and `phase_branch` `ZERO_FLOW`.
- [ ] If item 4 measures otherwise, stop and report it to the design lane.

### Q-R5 — Digests and decimal strings inside the `t05` identity key

**Ruling: confirm the projections as they are; no filter.** Design note §6 is amended and spec A24 reworded.

- R0 excludes computed floats and digests of computed states. It includes declared constants as shortest decimal strings (the plan's scales and bounds, `delta_scaled_inf`) and digests of declared inputs (`constants_sha256`, `variable_ids_sha256`), exactly as `t02` and `t03` already do (ADR 0009 D1, T03 A23).
- The note's "no … float or digest" was loose, and is replaced by that rule.
- **Review N4, adopted.** Each case gains its run's typed message, first line only. For C3X that is `initializer_failed(U-HX): temperature_cross(cold_end)`, A20's discriminant. It contains no float (R-029), and T03's `_messages` is the precedent.

**Build-lane changes.**

- [ ] `scripts/t05_identity.py`: per case, `"message": run.message.splitlines()[0] if run.message else ""`.
- [ ] Correct the docstring: "no message, computed float or digest" → "no free-text message, computed float or digest of a computed state".
- [ ] Acceptance:
  - the document minus `t05` = `b364bb3d…`;
  - C3X's entry carries the code above, and C1–C3's carry `""`;
  - the whole document is equal on the CI pair;
  - the new whole-document hash is recorded (measured, not registered).

### Q-R6 — C3's solution-error bound margin

**Ruling: ratified, with a note in spec §11.5, and one tightening of how A21 is judged.**

- **Where the margin comes from.** C3's bound is `‖Ĵ⁻¹‖₁ ≈ 16.6` × `‖F̂‖∞ = 1.91e-10` (the worst row at `1.9e-2 τ`), against `2.6e-15` at the twin's state. It depends on where Newton stopped; "overshoots by decades" is an expectation, not a guarantee.
- **Why the requirement is kept.** It is what makes A17–A19's allowance comparison diagnostic. It is an evidence condition, not a certificate check (K04 §7.4).
- **The tightening.** K04's `onenormest` is a lower estimate, and at C3 it is 6 % low: exact `17.76`, exact bound `3.40e-9`, a margin of 2.9×. A21 therefore judges `≤ 1e-8` on the exact norm. The certificate keeps K04's estimate. Spec F10 records this as a K04 observation.

**Build-lane changes.**

- [ ] The W0.6 test (`test_a21_w0_6_the_solution_error_bound`) also computes the exact `‖Ĵ⁻¹‖₁` from the dense inverse of `target_jacobian(...)` at the final state (`n ≤ 64`), and asserts `exact × ‖F̂‖∞ ≤ 1e-8`.
- [ ] Record both factors in `docs/t05-measurements.md`.
- [ ] Acceptance: C1 `8.08e-14`, C2 `3.88e-15`, C3 `3.40e-9` (measured this round), each `≤ 1e-8`.

### Q-R7 — Reactor arithmetic at `X = 1` (review S2)

**Ruling: the key's outlet is `n_in,k − X·n_in,k`; every other component is `n_in,i + ν_i ξ`; `ξ` is unchanged; no clipping.** Spec §6.3 and §14 amended, A10 reworded, register R-051.

- **The exhaustion test stays over every component, in component order.** Monotone rounding makes the key's outlet `≥ 0` for `X ≤ 1`, so only a non-key can trigger it, and no special case is needed. RX-6's exact non-key exhaustion keeps its `< 0` test: a one-ulp refusal there is a boundary coincidence, and it is typed.
- **Only the causal evaluator changes.** The rows (`RX-mole`) keep `n_in + ν ξ − n_out`. They describe the same function, and at the causal answer the key's row is a few ulps, far inside `τ`, which is what "same function at the same state" requires.
- **No registered number moves.** For `|ν_k| ∈ {1, 2}` the two forms are bitwise identical, and every registered case has `|ν_k| ∈ {1, 2}`. RX-F1 still exhausts A: `1 − 2·0.6 = −0.2`.

**Build-lane changes.**

- [ ] `conversion_reactor.py` (review S2 `:660-666`): the key's outlet as ruled.
- [ ] Acceptance:
  - the review's P2 input (`ν = (−3, 1, 2)`, key A, `X = 1`, `(1.7383439417747188, 0.5, 0.5)`, VAPOR, 420 K, `P_r`, `T_spec = 420 K`) → `ok` with `n_out,A == 0.0`;
  - a deterministic sweep of 1 000 `n_A ∈ [0.01, 5]` for `ν ∈ {(−3,1,2), (−5,2,3), (−7,3,4)}`, key A, same conditions:
    - at `X = 1`, all `ok` with `n_out,A == 0.0`;
    - at `X ∈ {0.25, 0.5, 0.75}`, no `reactant_exhausted(A)`;
    - `RX-mole:A` at each answer within `1e-12 ×` its term scale;
  - RX-1…8, Z, F1 (still `reactant_exhausted(A)`), F5 and S1–S5 are bitwise unchanged;
  - A06, A10 and A14 are unchanged.

### Q-R8 — One flowing component on the saturation route, on the EO path (review S3)

**Ruling: registered as a v0.1 limitation — a typed failure, never `VERIFIED`. It belongs with Q-R4, as spec §4.7 (b).** Also: §4.4 step 2 pointer, §5.1, §18, §19 Q12 (Frank's scope preference; default: the limitation), A30, R-050.

- **The EO rows are regular there.** The region path cannot reach the state, because ADR 0005's screen takes its regimes from the provider's TP flash, which never reports `TWO_PHASE` for one flowing component.
- **K04's independent split shares that blind spot.** So even a correct root would be `FAILED`.
- **The remedy is an ADR 0005 change,** beside Q-R4's `ZERO_FLOW` regime.
- **`initial_state` is not changed.** Re-seeding with the exact split still fails (review P3), and on every other route the closure split *is* the re-flash. Only the comment is corrected; design note §2.2 step 5 states the exception.

**Build-lane changes.**

- [ ] A30 (new):
  - P3 and P4 causal answers: `β = 0.0336` by closed form; PHF-6's registered values;
  - EO never `VERIFIED` (typed non-`CONVERGED`, or a non-`VERIFIED` certificate), with the measured `ACTIVE_SET_CYCLING` and `BOUND_BLOCKED` pinned as regression values;
  - the control, P4 + `1e-6 mol/s` of A, ends `CONVERGED`.
- [ ] Correct the comment at `orchestrator/revision.py:145-157`; no logic change. Acceptance: C1–C3 trajectories and W1.c's bitwise start are unchanged.
- [ ] The manifests' limitations, as Q-R1's item.

### §3 — The engineers' interpretations (`docs/T05_DECISIONS.md`, 2026-09-25)

**Ratified as a block**, with these named.

- **U1 (2): an unrefused non-finite `Q_spec` (review N6) — changed.**
  - The rule: a non-finite numeric constructor input is refused at construction. Where no registered code applies it is `ValueError`, as the reactor's and the exchanger's values already are; where one applies, the registered code (spec §3.5, §5.1).
  - Today a NaN duty comes back as `ph_ill_conditioned`, a typed answer with the wrong name.
  - [ ] Build lane: a table test over the six constructors × every numeric input × `{nan, inf, −inf}`. Each is refused at construction, with `ValueError` or its registered code. Known gaps are the PH flash's `duty` and `pressure_drop`; check the reactor's `pressure_drop` (`nan < 0` is false). Registered cases unchanged.
- **U1 (2): provider refusals surfaced with the provider's own status — ratified.** Spec §3.5 now states the exception, which §3.3 implied.
- **U3 (5): RX-F1's `extent` is `None` — ratified.** Spec §6.4 and A10 state that `ref`'s `0.6` is the twin's diagnostic, not an output.
- **W9/W10: A03's configuration change is judged at flowsheet level — ratified.** The A03 wording is amended to say where `model_version` moves.
- **W12: A22's extra failing checks are consequences — ratified.** Spec §12.5 and A22 now say "contains", not "equals"; A20 alone asserts an exact set.
- **W1.d `sum()`:** see Q-R2. **W13b's R0 projections:** see Q-R5.
- **Everything else is ratified as logged:**
  - U2 (1)–(7);
  - U1 (1), (3), (4), (6);
  - U3 (1)–(4), (6), (7);
  - W1.a/W1.b (1)–(6);
  - W1.c;
  - W11;
  - W1.d's other interpretations;
  - W12's other interpretations.

### Review S1 (§7 amendment 3) — a `vapor_liquid` connection from a non-lifting producer

**Ruling: design note §1.3 R4 is amended.**

- A `vapor_liquid` connection is admitted only from the `outlet` port of an `outlet`-style `SPLIT_RULES` model.
- Otherwise it is refused at binding: `Unbound("unsupported", "port_phase_unsupported(<producer unit>.<port>)")`, the existing code and format.

**Build-lane changes.**

- [ ] The review's minimal correction in `bind_revision_flowsheet`.
- [ ] Acceptance:
  - the review's P1 revisions each return exactly that `Unbound`;
  - C1–C3X and the SYN-001-shaped revision bind with unchanged `configuration_sha256` and label;
  - protocol P is unchanged.

S4, S5, N1 and N3 are build-lane work as the review states; nothing in them needs a ruling.

### For Frank

Nothing blocks. Two scope preferences are recorded with their defaults in force: spec §19 Q11 and §19 Q12.

- **§19 Q11, a PH kernel that resolves near-pure feeds.** Default: the limitation. It will matter for real high-purity streams from T08 on.
- **§19 Q12, EO solves of a single flowing component in the jump.** Default: the limitation. The remedy is an ADR 0005 change.

Q4's `ZERO_FLOW`-regime remedy stays deferred, as before.
