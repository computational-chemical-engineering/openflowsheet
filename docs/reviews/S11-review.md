# S11 review: the binding package (design lane, `reviewer`)

Branch `wp/S11` at `8d2ee175`; branch-only diff read against the true merge base with main, `35ceeb8a`.
Read against `docs/derivations/S11-design.md` (§10 especially), `S11-units-design.md`, `docs/reviews/S11-rulings.md`
and the four decisions logs. Nothing was built or run. The numbers below are the brief's or the logs'.

## Verdict

**Mergeable after two must-fixes.** Both are small, and neither touches numerics on SYN-001 or C1:

- **M1:** the aarch64 byte check. CI must be green on both architectures before the merge, so R-843 below has to be
  implemented first.
- **M2:** L-TH-7's text. It says something the certificate contradicts. R-844 below rules O-C6-1.

What I found sound:

- **Q9 stage-split rule.** The rule as built matches §10.2 step for step.
- **`wilson-ig-v2` entropy.** I re-derived it, and its derivatives too.
- **Additive-vapour isentropic state.** Both the block and the verifier evaluate pure-component vapour at e_j, so
  composition stays fixed, the mixing term cancels, and no ds/dn singularity appears.
- **R-831's one-sided witness.** It runs only on the Wilson basis, and its central path is bit-identical to the old
  code. A shift of ±1.0·h gives the same floats.
- **The tests amended outside §8.3.** None of them is weakened. Each one restricts the base assertion to ids outside
  `thermal.` and pairs it with a literal pin of the thermal ids.

## Q9 (look-hardest 1): sound

- **One place does the merge, and the registry functions see registry splits only.** `region_splits` is the single
  place the merge is written. It passes `registry`, not the merged splits, to `zero_flow_forms`,
  `split_temperatures` and `vapour_only_forms`, so F4's `KeyError` cannot occur.
- **The identity argument holds as written.**
  - With `staged == {}`, every changed expression reduces to the old one: `owners.get(k, k)`, `{**m}` with the same
    key order, and `(u,)` in `build_region`.
  - The central stencil in `derivative_witness` is bitwise unchanged.
  - On a refused point, the new code evaluates fewer stencil points but returns the same reason string.
- **No stage split can be dropped or given the wrong owner:**
  - `solve_region` has one caller on the revision path, `executor._region`, and it passes `split_owners`.
  - `tear` and `cascade_solve` use their own registries.
  - The legacy route and `build_execution_plan` serve SYN-001 only.
  - Revision specification regions are refused (`executor.py:688`), so `plan_revision`'s whole region is the only
    `build_region` that can hold a column. It passes `staged_units`, and step 5's guard checks the result.
  - A staged unit missing from `instances` would raise `lifted_split_unregistered` at check (a′).
  - Two staged units supplying the same key would raise `lifted_split_key_collision` at (a″).
  - A stage key that equals an instance id is caught twice: at bind (I1, `revision_binding.py:2033`) and at (a″).
- **Every `split.unit` lookup in `region.py` is keyed by the split key, as §10.2's table requires.** I checked all
  ~60 sites. The only `at[...]` lookup indexed by unit is the one step 2 changed.

## Must fix before merge

### M1. aarch64: `s11_thermal_reference.py --check` is byte-exact only on x86-64. Rule: R-843 (text below)

- **File:** `docs/derivations/scripts/s11_thermal_reference.py:468-493`.
- **Failure:** CI 40610610012 on aarch64 fails `test_the_reference_regenerates_byte_for_byte`.
- **What the file holds.** CoolProp `PropsSI` answers: saturation T, h and s at 15 pressures; TP evaluations of h and
  s; PH and PS flashes giving (T, Q) and a regime label. It also holds the generator's arithmetic on those answers:
  W, Q, efficiency, COP, and TH-R1's 40-sweep recycle.
- **No near-critical state.** The nearest point to its critical temperature is CO2 at 6 MPa, with 1 − T/T_c ≈ 0.03.
  So R-627's class N does not arise, and one class suffices.
- **Cancellation is the hazard.** A54's pump work is (h_s − h_I)/η = (3509.8 − 3455.4)/0.75. It amplifies the
  relative noise by about 128, so a purely relative bound would fail by construction. An absolute floor at the
  fluid's energy scale absorbs that amplification without a second constant.
- **Unknown:** the CI log says only "differs", so the aarch64 magnitudes are not known to me. The ruling therefore
  prints them, and it stops at one decade inside the bound, as R-723 did.
- **Tests:** this is a harness change only. The kernel tests that read the YAML are untouched.

### M2. L-TH-7 says "v2 suffices", and the certificate says otherwise. Rule O-C6-1: R-844 (text below)

- **What happens now:**
  - L-TH-7 reads: "Dormant single-phase thermal outlets need T05b's v2 phase contract."
  - Under v2, A62 at Q = 0 converges, but it certifies UNVERIFIED with regularity `RANK_DEFICIENT`. This is measured
    (S11A log, item 8) and not pinned.
  - The cause: `verify.zero_flow.DORMANT_OUTLETS` has no `thermal.*` outlet. The verifier therefore judges the energy
    row, which reads no temperature at n = 0, so the outlet T column is structurally zero.
- **Is the verdict safe?** Yes. It is conservative: there is no false VERIFIED. That is why I accept the build
  default for S11.
- **What must change:**
  - The published limitation must not tell a user that v2 is enough.
  - The v2 certificate must be pinned, so that a later verifier change flips it on purpose rather than silently.

## Should fix

- **S1. No test ties the verifier's staged splits to the solver's.**
  - Anchors: `verify/certificate.py:870-880`, and `tests/test_s11_column_verifier.py:285`.
  - The gap:
    - §10.2 step 7 and §10.11 B4 rest on "the same pure function". The verifier builds `StagedSplits` from
      `column_structure(parse_revision(...))`, while the solver uses the copy that the binder's builder holds.
    - Those are two readers of one instance. If they ever diverge, the certificate's split keys and phase branch
      stop matching the solve's attempt signature, and no test notices.
  - Correction: add one assertion on M1 and on one Wilson case:
    `_staged_splits(parse_revision(doc))[U] == binding.flowsheet.<unit U>.staged_splits()` (frozen-dataclass `==`).
- **S2. The v2 A62 certificate is unpinned.** This is part of R-844; the test is named there.

## Notes (no change required for merge)

- **N1. A dormant column stage raises a bare exception.**
  - Where: `verify/zero_flow.py:117,121`.
  - At a dormant column stage, `zero_flow_form_unknown` is a bare `ValueError`. The caller,
    `revision_run.py:583`, catches nothing.
  - It is unreachable today, because the traversal's `solve_column` refuses a zero feed.
  - When the design lane reads the per-stage form (B4 escalation), make it a typed `VerifierError` or an
    `unsupported` check.
- **N2. Stage attribution depends on message text.**
  - Where: `verify/column.py:296-325`. `_stages_of` attributes acceptance items by regex over `column_solve`'s
    message text.
  - It fails closed (`acceptance_item_unattributed` raises), so it can never produce a false pass. But any rewording
    in `column_solve` breaks certificates.
  - A test that enumerates every item format `acceptance_failures` can emit would pin this coupling.
- **N3. `region_splits` is recomputed six times per region solve.**
  - `executor._splits`, `_split_owners`, `_closure_types`, `_zero_flow_forms`, `_split_temperatures` and
    `_vapour_only_forms` each call `_region_splits(flowsheet)`, which re-runs the registry functions every time.
  - This is cheap next to the solve. Computing it once per `_region` call would also make "one merge" literal at run
    time.
- **N4. The column's linear specification checks loosen at small product rates.**
  - The checks (B4, R-838) compare `n_c − π*·P` against τ_flow. The purity is therefore judged only to τ_flow/P,
    which is loose when the product rate is small.
  - This was accepted as built. If no L-COL row states it, add one sentence there.
- **N5. One-sided stencil re-evaluates F(x) per column.**
  - In `derivative_witness`, the one-sided stencil re-evaluates F₀ = F(x) for each column in Z: 63 extra residual
    calls on C-MW.
  - This is negligible, but F₀ could be hoisted out of the loop.
- **N6. The identity count fell by three, apparently with cause.**
  - §10.2 asked for `n ≥ 54497`; the measured value is `n = 54494`.
  - Family C counts only keys present at the base, so new tests add none. Excluding R-841's three amended tests
    removes three keys, which matches the drop.
  - Correction: the erratum E2 below, after the build lane confirms that the three missing keys are exactly R-841's.
- **N7. The R-561 reclassification is the right call.**
  - The commit is `de7e23c1`. It follows the specific registered rule over §4.11's general sentence, so the
    orchestrator default is correct.
  - Correction: the erratum E3 below.
- **Confirmations:**
  - `v2_binder()` and `restrict_to_v2_models` are test and benchmark scaffolding, not product code.
  - W27 v1 and v2 now refuse the unrestricted build, and that refusal is pinned (`test_s11_the_v2_snapshot_refuses_this_build`).
  - v3 reads the full build.
  - The Wilson pump's refusal is correct: v2 offers no v, so W = ∫v dP would be silently 0.
  - `derivative_singular`, which refuses a whole request, is the honest answer at x_c = 0.
  - The machines never ask for it, because they use the additive form.

## Register entries (exact text; R-843 and R-844)

```
## R-843 — S11's thermal reference check: bitwise on x86-64; elsewhere classed (R-723's pattern), floats within 1e-10·max(|x|, s_f) with a physical s_f

| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), S11 review |
| Normative text | `docs/reviews/S11-review.md` M1; amends `docs/derivations/scripts/s11_thermal_reference.py --check` |
| Evidence | CI 40610610012 at `8d2ee175`: x86-64 byte-identical; aarch64 "differs". Jet floor 1.05e-12 (R-627). No reference state within 1 % of T_c (CO2 at 6 MPa: 1 − T/T_c ≈ 0.03). Largest cancellation in the file: A54's pump work, κ = (h_s + h_I)/(h_s − h_I) ≈ 128 |
| Affected packages | S11 |

**Decision.**
- On x86-64, byte equality, unchanged.
- Elsewhere, `--check` parses both documents and compares them leaf by leaf:
  - **Exact:** the structure and key order, every string (names, labels, `regime`, the `coolprop` block), every
    integer, and every `null`. A `beta: null` that becomes a number, or the reverse, is a difference.
  - **Every other float:** |Δ| ≤ 1e-10·max(|x|, s_f). The floor s_f is set by the leaf's key:
    - R·T_c of the case's fluid, times the case's `n` for a rate, for keys beginning `h`, `Q` or `W`;
    - R for keys beginning `s`;
    - 1 for `beta`, `efficiency` and `COP`;
    - 0 for every other key (T, P, flows).
  - A float under a key outside this map is an error of the check, not a pass.
- `_coolprop()` sets `ENABLE_SUPERANCILLARIES` explicitly, as S10's `compute()` does (R-723). It takes the value
  under which the x86-64 byte check still passes, with no byte moved.
- `--check` prints one line per class on every architecture: the leaf path of the worst |Δ|/bound, and that ratio.

**Rejected alternatives, and why.**
- *Run the check on x86-64 only.* aarch64 would then never confirm provenance (R-723's reason).
- *1e-10·|x| without a floor.* It fails the cancelled differences (W, Q) by construction, since κ is up to 128.
- *A flat bound fitted to the aarch64 worst.* That is fitting to a measurement (R-627).
- *Tolerating a regime flip at the β = 0 or β = 1 grid points.* That flip is exactly what the check exists to show.

**Watch for.** Stop and escalate to the design lane with the printed line, and never widen the bound in the harness,
if either of these happens:
- an exact leaf differs. The likely case is a `regime`/`beta` flip at a β = 0 or β = 1 grid point, which is fixed by
  moving that nominal state off the boundary in the generator;
- the classed worst exceeds 1e-11 relative to its bound.
```

*Amended 2026-10-29 by R-845:* a `T` whose enclosing mapping has `regime` LIQUID or VAPOR (a single-phase
PH/PS flash answer) is its own class `flash`, |Δ| ≤ 1e-8·|x|. CoolProp's flash converges T only to about 1e-9·T
(measured 9.27e-10), and CI 40861460178 printed 2.403 at `TH-C1.pump_outlet.T`. The premise that A54's
cancellation is the hazard for derived temperatures is measured false: through 1/c_p it contributes 6.4e-4 of the
bound. Every other class, the watch and the x86-64 byte check are unchanged.

```
## R-844 — S11 O-C6-1: the verifier's dormant-outlet table gains no `thermal.*` outlet in S11; a converged dormant single-phase thermal outlet certifies UNVERIFIED/RANK_DEFICIENT under either contract, and L-TH-7 says so

| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), S11 review (rules S11A_DECISIONS item 8's OPEN; confirms the build default) |
| Normative text | `docs/reviews/S11-review.md` M2; erratum to S11 units design §4.9; envelope row L-TH-7 |
| Evidence | `tests/test_s11_thermal_solve.py::test_o_c6_1_*` (v1: A62 Q = 0 CONVERGED, UNVERIFIED, RANK_DEFICIENT; Q = 1 kW LINEAR_SOLVE_FAILED; the SYN-001 pump's dormant case VERIFIED, NO_RANK_LOSS_DETECTED); S11A log item 8 (A62 under `T06-revision-v2`: UNVERIFIED, RANK_DEFICIENT) |
| Affected packages | S11; a follow-on verifier package |

**Decision.**
- `verify.zero_flow.DORMANT_OUTLETS` is unchanged in S11.
- L-TH-7's text becomes: "Dormant single-phase thermal outlets need T05b's v2 phase contract to solve. Under v1 a
  converged start certifies RANK_DEFICIENT, and a solve that must move ends LINEAR_SOLVE_FAILED. Under either contract,
  a converged run with such an outlet certifies UNVERIFIED, with regularity RANK_DEFICIENT. The verifier's own
  dormant-outlet table (verify.zero_flow.DORMANT_OUTLETS, spec §7.6) has no thermal.* outlet, so it judges the outlet's
  energy row, which reads no temperature at zero flow."
- A new test pins A62 at Q = 0 under `T06-revision-v2`: CONVERGED, UNVERIFIED, RANK_DEFICIENT. It is added to
  L-TH-7's evidence beside the two `test_o_c6_1_*` tests.
- Follow-on (not S11):
  - add the nine single-phase rules of units design §4.9 to `DORMANT_OUTLETS`;
  - key each rule by a configuration the verifier reads from the revision: the heater's pinned column (as
    `exchanger_specification` does) and the outlet's declared phase;
  - make `tests/test_t05_table_independence.py` compare the two tables as data;
  - the v2 pin then flips to VERIFIED on purpose.

**Rejected alternatives, and why.**
- *Add the entries in S11.* The verifier's configuration reading is unspecified, and no table-comparison test exists.
  The risk is a reduction applied where the solver applies none (a T-mode heater), which would judge a label row the
  solve never imposed.
- *Keep L-TH-7 as written.* It tells a user that v2 suffices, and the certificate contradicts that.

**Watch for.** A dormant thermal outlet that certifies VERIFIED before the follow-on lands.
```

## Design-note errata (exact text)

- **E1.** In `S11-units-design.md` §4.9, append after the R-839 erratum:
  "*Erratum 2026-10-29 (R-844):* "as the SYN-001 pump's is" does not hold at the certificate. The SYN-001 pump's
  dormant outlet certifies VERIFIED under either contract, because the verifier reduces it by its own table. That
  table has no `thermal.*` outlet, so a converged dormant single-phase thermal outlet certifies UNVERIFIED,
  `RANK_DEFICIENT`, under v1 and v2 alike (L-TH-7). The verifier's thermal entries are a follow-on."
- **E2.** In `S11-design.md` §10.2, after the identity paragraph:
  "*Erratum 2026-10-29 (S11 review):* family C counts only keys present at the base, so new tests add none. The floor
  is n = 54494: 54497 less the three keys of R-841's tests, which `AMENDED_TESTS` excludes. Measured:
  `S11-IDENTITY PASS n=54494 changed=[]`."
  Write this only after the build lane confirms that the three keys are R-841's; otherwise stop and report the
  difference.
- **E3.** In `S11-design.md` §4.11, after "No earlier harvest entry is edited":
  "*Erratum 2026-10-29 (S11 review):* except S02's twelve U04 items, which R-561 (the specific registered rule) has
  the binding package reclassify (`de7e23c1`)."

## Not examined

- `column_unit.py`'s `contribute` and `_owned` internals beyond `evaluate`.
- The thermal blocks' declared derivatives, `machines.py`, and `gamma_phi_units.py` beyond its imports and §4.8. For
  these I relied on the FD-witness and A46 evidence.
- W27 v3 data, the T08 harvest and `test_t08_w2_inventory` data, the `_UNADMITTED` texts, T08.A32 clause (vi), and the
  30-model registry line by line.
- E01 (out of scope).
