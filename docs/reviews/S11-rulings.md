# S11 rulings: the batched ruling round on the build lane's escalations

Design lane (`specifier`), 2026-10-27. Brief: `docs/briefs/S11-ruling-round.md`. Everything was read at `wp/S11`
`645c1e22`: tracks A, B and C merged, D1 and D4 merged, D2/D3 running on `wp/S11-d` (whose `fc645bce` is item 11's
subject). Register: **R-830…R-842**.

## 0. Authority and scope

- This document is the normative text for the thirteen rulings below and for every assertion text it replaces.
  - The two design notes carry a dated erratum line at each changed assertion, pointing back here:
    `docs/derivations/S11-design.md` (ADR 0050) and `docs/derivations/S11-units-design.md` (ADR 0051).
- It amends three things:
  - T08.A32, as already amended by M01 §3.5, L01 §12.4 and S10 §18 A5-1. Item 1 adds clause (vi).
  - The certificate's derivative witness on the Wilson basis (item 2). R-281 stands unchanged for `pr-c1-v1`.
  - W27 registration version 3 (item 3): a new rule W27v3-R09, a restated W27v3-A08, and a new W27v3-A09.
- It changes none of the following: a schema, a `Protocol`, a quantity kind, a check category, a `KIND_TOLERANCE`
  entry, `DERIVATIVE_TOLERANCE` (1e-7), `FD_RELATIVE_STEP` (1e-5), or W27 versions 1 and 2.
- **Measured** numbers come from scratch probes run for this round on `645c1e22`. The probes ran central, one-sided
  and step-halving stencils around the committed cases. They are not fixtures. Each number that justifies a tolerance
  is measured again and asserted by the test that its work order names, so the claim can be executed there.
- Governing rules (brief §1):
  - no relaxed checks, no removed cases, no narrowed denominators;
  - a self-generated output is a regression fixture, not validation;
  - Frank: "as few limitations as possible".

## 1. The rulings at a glance

| # | Item | Ruling | Register | Carried by |
| --- | --- | --- | --- | --- |
| 1 | T08.A32 refuses `s05/` and `s07/components.yaml` | **change**: register a class of provider-identity record files, with its own predicate | R-830 | I1 |
| 2 | Wilson column certificates UNVERIFIED on the witness | **change**: a one-sided five-point stencil at absent-component zero columns on Wilson. R-281 is not extended | R-831 | I1 (first commit) |
| 3 | W27 v3 Q-1 (spelling rule vs CAS-less records) | **accept** the default, as W27v3-R09; A08 restated; A09 added | R-832 | I1b |
| 4 | Kernel fix C3-1 | **accept** | R-833 | I2 (negative control) |
| 5 | A46 at the top of the range (C1-4); scaled comparison (C1-3) | C1-3 **accept**; C1-4 **revert and restate** (a fixed 1e-5 at the two near-top states) | R-834 | I1b |
| 6 | A12 "exact `==`" | **restate**: ≤ 2 ulp, plus a registered non-exact state | R-835 | I1 |
| 7 | A68 "square"; A77(iii) | **restate** (the engineer's readings, plus one coverage assertion) | R-836 | I1b |
| 8 | §4.10 "all existing W27 tests pass unchanged" | **restate** | R-837 | none (done); I2 cites |
| 9 | Track B decisions | **accept** all; **change** one stale hint | R-838 | I1 |
| 10 | Track C decisions | **accept** Q-C2, O-C4-1, C4-2, C6-2, C6-3 and O-C3-1 (with limitation texts); **change** C3-2; O-C6-1 *needs a fact* | R-839 | I1b |
| 11 | Track D decisions | **accept** the v2 `provider_id`; **change** the `ph_kernel` labels | R-840 | D5 (merge), D6 |
| 12 | Track A decisions | **accept** four; **change** the routing models' hints on C1 | R-841 | I1b |
| 13 | Identity gate: `VOLATILE` revision ids | **accept**, plus a test that makes it executable | R-842 | I1 |

---

## 2. Items that block the final gate or the release

### Item 1 — T08.A32 and the two new record files (R-830): change

**Ruling.** The two files hold no property datum (`parameters: {}`): only identity (id, name, CAS RN, formula) and a
molar mass that S11.A05 already requires float-equal to the provider's constant. The provider's data is pinned
elsewhere: IAPWS-95's by S05, CoolProp's `FLUIDS` by S07 (A01, C19). Clauses (ii), (iv) and (v′) were written for files
that *are* a data source, and fail here for structural reasons only (no InChI, no cross-check JSON, no shared parameter
by construction). A blanket exemption would be a relaxation; the ruling registers a third class with its own predicate,
which fails on every defect the original clauses exist to catch. R-722's rejection of "vet by `--check` alone" does not
apply: these records are the source of no value, and the predicate compares them with constants the provider ships
and S05/S07 vetted independently.

**Replacement text.** A new clause, added to T08.A32 after (v′):

> **(vi) Provider-identity record files** (S11 rulings item 1, R-830). `PROVIDER_IDENTITY_RECORD_FILES` registers:
> - `benchmarks/s05/components.yaml`: provider `iapws95-v1`, ids `("H2O",)`;
> - `benchmarks/s07/components.yaml`: provider `coolprop-heos-v1`, ids = the `id` of each row of
>   `thermo._coolprop_heos_fluids.FLUIDS`, in table order (123; asserted).
>
> These files are not vetted files. A `synthetic: false` record in one of them is judged by (i-p), (ii-p), (iii),
> (iv-p) and (v-p), which replace (ii), (iv), (v) and (v′) for it:
> - **(i-p)** it carries one of its file's registered ids, each once, and the file's `reference_convention` is the
>   provider's (`IAPWS95-ref-v1`; `COOLPROP-DEF-ref-v1`);
> - **(ii-p)** `identifiers.cas` is non-empty and equals the provider's: `7732-18-5` for IAPWS-95, and the row's `cas`
>   for CoolProp. InChI and InChIKey are not required;
> - **(iii)** as written: rights, and a provenance on the molecular weight;
> - **(iv-p)** it holds no datum:
>   - `parameters == {}`;
>   - `molecular_weight.value` is float-`==` to the provider's constant (`iapws95.M`; the row's `M`);
>   - `name` equals the provider's (`water`; the row's `name`);
>   - for IAPWS-95, also `identifiers.formula == "H2O"` and `elemental_composition == {H: 2, O: 1}`;
> - **(v-p)** it takes no part in (v) or (v′), because it has no parameter to compare. Instead, for each id it shares
>   with another real record that carries a CAS RN, the CAS RNs are equal. A real record is `synthetic: false`, in a
>   vetted or provider-identity file, and a package-data link counts as its single copy. The set of ids so compared is
>   registered and asserted equal to {Ar, C2H6, C3H8, CH4, CO2, H2, H2O, N2, O2} (measured: 9 ids, all equal).
>
> The registered real (file, id) set of (i)'s final clause gains the 124 provider-identity pairs.

**Work order (I1).** Edit `tests/test_t08_w2_inventory.py` to carry the table, the predicate and the registered
CAS-compared set. Acceptance:
1. T08.A32 passes.
2. A new `test_a32_provider_identity_predicate_refuses_each_defect` mutates one record per case. Each mutation must
   make the predicate fail:
   - (a) a parameter added to the s05 H2O record;
   - (b) the s07 CO2 `M` moved by one ulp;
   - (c) the s07 CO2 CAS set to N2's: fails (ii-p) and (v-p);
   - (d) an s07 `name` changed;
   - (e) an id not in `FLUIDS`;
   - (f) the s05 record copied into an unregistered file: fails (i);
   - (g) the s05 `reference_convention` changed.

### Item 2 — the Wilson column certificates (R-831): change (R-281 is not extended)

**Ruling.** R-281 exempts `pr-c1-v1`'s zero stream flows because no derivative exists there (the forward point is
light gas in a pure-NH3 liquid), and its *Watch for* names exactly the widening asked for here. On Wilson the forward
points are admissible and the activity coefficients are analytic at x_c = 0 (infinite dilution), so the one-sided
derivative exists and equals the AD entry; only the backward point is refused (ADR 0001 D2). R-281 rejected a forward
stencil for two reasons, neither of which holds here: an unregistered tolerance (this rule keeps
`DERIVATIVE_TOLERANCE`, 160× above the stencil's measured floor), and testing a convention at dormant columns (the
positive-sibling condition excludes them). Every column stays differenced: no `derivative_witness_partial`, no
narrowed denominator.

**Normative rule.** It is the Wilson companion of ADR 0013 Amendment 3 item 7:

> **Derivative witness, one-sided columns (S11 rulings item 2, R-831).**
> - On a `wilson-ig-v1` or `wilson-ig-v2` basis, let **Z** be the columns of the target that meet all three
>   conditions:
>   - the column is named `<p>.<c>`, with `c` a declared component;
>   - its value at the witnessed state is exactly `0.0`;
>   - some `<p>.<c′>` (c′ ≠ c, a declared component) is `> 0.0`.
> - For each column j ∈ Z the witness uses the forward five-point stencil
>   D_j = (−25 F₀ + 48 F₁ − 36 F₂ + 16 F₃ − 3 F₄) / (12 h), with F_k = F(x + k h e_j) and
>   h = `FD_RELATIVE_STEP` × the column's scale (the registered step).
> - D_j is compared in the same scaled form, against `DERIVATIVE_TOLERANCE`, into the same two checks.
> - Every other column keeps the central stencil.
> - A refused stencil point makes both checks `unsupported` (`witness_stencil_<status>(<name>)`), as now.
> - Z is empty on every other basis.
> - No limitation is written, because every column is differenced.

**Measured** (scaled units; registered step 1e-5):

| Case | \|Z\| | one-sided worst (5-point) | central worst (other columns) | smallest nonzero scaled AD entry in Z |
| --- | --- | --- | --- | --- |
| C-MW | 63 | 6.09e-10 | 8.243e-8 | 7.1e-4 |
| C-EW | 63 | 6.22e-10 | 4.644e-8 | 4.6e-3 |
| C-MW-stripper | 34 | 3.27e-10 | 2.083e-9 | 2.3e-2 |

*Why five points.* On C-MW at the registered step:

| Forward stencil | Worst (scaled) | Verdict |
| --- | --- | --- |
| 3-point (2nd order) | 2.22e-6 | truncation; fails |
| 4-point | 3.11e-9 | truncation-dominated |
| 5-point | 6.1e-10 | roundoff |

- Below the registered step the 5-point value grows ∝ 1/h (6.2e-8 at 1e-7), so at 1e-5 it is roundoff-dominated.
- Of C-MW's 63 columns, 22 (the stages' `m` vectors) enter linearly, and the stencil is exact on them (0.0).
- No forward point is refused.
- Every column whose central stencil the provider refuses (41/41/21) is in Z.
- The other 18/18/9 exactly-zero columns have no positive sibling. They keep the central stencil, which the provider
  answers.

**Work order (I1, first commit).** Code goes in `verify/checks.py` (`derivative_witness` gains the one-sided set) and
`verify/certificate.py` (Z beside R-281's set). Acceptance:
1. `test_a35_the_wilson_column_rows_pass` is rewritten to the following, parametrized over C-MW, C-EW and the stripper
   (`benchmarks/s11/flowsheets/C-MW-stripper.json`):
   - each certificate is VERIFIED;
   - \|Z\| = 63, 63 and 34, each name `<p>.<absent component>`;
   - both witness values are ≤ 1e-7, and the one-sided part is ≤ `DERIVATIVE_TOLERANCE`/10 (value recorded).
2. Mutation: set to 0.0 the AD entry of largest scaled magnitude in a Z column (wrap the target's `jacobian`). Then
   `derivative_witness.on_pattern` FAILs.
3. Every test file that calls `verify_revision` passes unchanged (SYN-001 and C1 certificates do not move).

D6 records \|Z\| and the one-sided worst on each GP certificate. A value above `DERIVATIVE_TOLERANCE`/10 is a stop:
escalate, and never widen. A Wilson certificate whose witness stays `unsupported` because a whole phase is exactly zero
is also escalated, with its column list (OQ-5). D6's VERIFIED clauses (A69, A71) depend on this commit, so D6 rebases
onto it first.

### Item 3 — W27 v3 Q-1 (R-832): accept the default, as W27v3-R09

**Ruling.** W27v2-R08 exists so that an unaliased spelling cannot leave a registry chemical silently unavailable.
Its pass condition, `aliases[N] = X`, presupposes a CAS RN X. A record with no CAS RN matches no case component, since
W27-R15 identifies components by CAS RN. So no alias, and no amendment of the alias table, could ever close such a
refusal. The rule is undefined there, not violated, and skipping those records is not a relaxation. The consequence
is that the Wilson route serves no case, which is the effect §4.10 already states. It is a conservative under-count,
and the release's W27 record must state it. Giving the Wilson records CAS RNs is a question for R-706 and for Frank
(his 2026-10-23 direction on the CAS licence), not for this round.

**Replacement text** (`docs/derivations/W27-registration-v3.md`; the states block is regenerated, not hand-edited):

> **W27v3-R09 (W27v2-R08 under version 3).** A non-synthetic registry record with no CAS RN (`cas` absent, null or
> empty) takes no part in W27v2-R08: it can match no case component (W27-R15), so no alias can close a collision with
> it. Records with a CAS RN keep W27v2-R08 unchanged. Versions 1 and 2 are unchanged.
>
> **W27v3-A08 (restated).** Version 3, snapshot B, case H2O-iapws:
> - `UNIT_UNAVAILABLE`, judged on `iapws95-v1`;
> - reasons: `UNIT_UNAVAILABLE` `Heater` `no_model:heater units=fs.heater`;
> - Heater models: none.
>
> This is A04's outcome, now on B. Mutant `cas_less_refused` (W27v2-R08 applied to CAS-less records) must fail here.
>
> **W27v3-A09 (new).** Version 3, snapshot S1co with each route's `record_source` added, case `co`: refused
> `archive spellings of registry chemicals not aliased ['co->630-08-0']` (W27v2-A16's refusal, under version 3).
> Mutant `spelling_rule_off` (W27v2-R08 skipped for every record) must fail here.
>
> **Effects (§4.10, and the document's §7 and §9):** "the Wilson records carry no CAS RN (R-706), so W27v3-R09 skips
> them and the route serves no case".

The expected outcomes are written by hand from the rules. GC-V3-4 refuses to emit unless the generator's reference
reproduces them. If the reference gives A08 another outcome, stop and escalate; do not edit the expectation to match.

**Work order (I1b).** Change the generator, `registration_v3.json`, the v3 branch of
`benchmarks/m06/w27/coverage.py`, and the document (§9 Q-1 marked "ruled: R-832"). Acceptance:
1. `w27_registration_v3.py --check` is OK, with GC-V3-4's mutants extended by the two above.
2. GC-V3-5 holds.
3. S11.A30 holds (v1 and v2 byte-identical).
4. Snapshot S4 classifies under version 3 on all 225 development rows with no refusal; the counts are recorded.

### Item 4 — kernel fix C3-1 (R-833): accept

**Ruling.** §4.2 names S05's convergence rule, and R-600 defines `previous` as the last raw Newton correction, reset
to ∞ only after a non-positive slope. Resetting it after a bisection was a defect against the design, found by a
stencil and fixed in code new in S11 (`models/thermal/kernel.py` does not exist at the base), so no pre-S11 output can
move. Measured over 11 200 grid outcomes: 7 go from `not_converged` to converged (root residual ≤ 1e-12·T·dg/dT), 2
move within the floor (≤ 3.1e-15 relative), the rest are bit-identical.

**Work order (I2, manifest).** Record the negative control once: in a scratch tree of `36ea9175` with the one line
reverted, `test_solve_keeps_the_newton_correction_through_a_bisection` fails (`not_converged`).

---

## 3. Assertion clauses that cannot hold as written

### Item 5 — S11.A46 (R-834): C1-3 accept; C1-4 revert and restate

**Ruling on C1-3.** A relative comparison of an entry far below its output's scale is ill-posed. A central
quotient's rounding error is about ε_F·|F|/h whatever the entry is, so for the liquid's dh/dP the literal relative
error reached 2.9e-2 on a correct derivative. Judging each entry relative to max(|∂F/∂x|, |F/x|) is the scaled form
that the solver and the witness use. Entries with elasticity ≥ 1 keep the literal test. The small ones are also pinned
by closed-form identities to 1e-9, which is stronger than any FD clause could be for them. This is a restatement, not
a relaxation.

**Ruling on C1-4.** The engineer's criterion added the measured |D(h) − D(h/2)| to the tolerance, capped at 1e-4: a
tolerance that grows with the noise it is judged against, so it is reverted. Near the top the provider's Maxwell floor
bounds a central quotient's error at ~3.8e-6 at step 1e-6, and no admissible step does better (measured below). The
same floor holds 1e-4 below the top, where the plain 1e-6 passes only through the noise realization (F-3). Both
near-top states therefore get one fixed bound above the floor.

*Measured* at P = p_σ(647.0 K)(1 − 1e-6):
- the noise of H(P) is ε_H = 1.29e-11 relative (the residual of a quadratic fit through 21 points spaced 1e-9);
- the elasticity is (P/H)·∂H/∂P = −3.39, so the error bound is ε_H/(h·|el|) = 3.8e-6 at h = 1e-6;
- measured error: 1.30e-6 at step 1e-6; 4.4e-5 at 1e-8 (smaller steps raise it); a larger step leaves the range; a
  one-sided second-order stencil adds 2.6e-5 of truncation at 1e-5;
- 1e-4 below the top: 3.53e-7 at step 1e-6, under the same bound of 3.8e-6.

**Replacement text:**

> **S11.A46 (restated, R-834).**
> - Each block's Jacobian agrees with central differences at relative step 1e-6, at 20 states per block, within 1e-6.
>   Each entry is judged relative to max(|∂F_i/∂x_j|, |F_i/x_j|), which is the plain relative error when the elasticity
>   is ≥ 1.
> - Entries whose elasticity is < 1 are also pinned to 1e-9 relative by two identities:
>   dh/dP = v − T·(∂v/∂T)_P and ∂Hs/∂P_I = −n·T_s·(∂v/∂T)_{P,I}.
> - The saturated blocks also include three range-end states:
>   - P = p_σ(T_t)·(1 + 1e-6), at a central step of 5e-7, within 1e-6;
>   - P = p_σ(647.0 K)·(1 − 1e-6) and p_σ(647.0 K)·(1 − 1e-4), at step 1e-6, within **1e-5**. The upper stencil
>     point stays below p_σ(647.0 K), and this is asserted. At these two states the provider's Maxwell floor bounds the
>     quotient's error by 3.8e-6 (ε_H = 1.29e-11, |elasticity| = 3.39) at every admissible step.

**The tolerance argument.**
- 1e-5 is 2.6× above the bound and 7.7× above the measured value (1.30e-6 at 1e-6 below the top; 3.53e-7 at 1e-4
  below).
- A dropped or mis-signed term of dh_sat/dP changes the entry by order one, which is ≥ 1e3 above the tolerance.

**Work order (I1b).** Rewrite `test_a46_saturated_flow_block_at_the_top_of_the_range` to this clause, with the
adaptive floor removed. Record the worst value of each A46 test in `docs/S11C_DECISIONS.md`, on x86-64 and, from CI,
on aarch64. A failure on either architecture is escalated, not widened.

### Item 6 — S11.A12 (R-835): restate

**Ruling.** The splitter's rows are n₂ = r·n and n₃ = (1 − r)·n in binary64, and their sum equals n only when both
products are exact. Choosing feed flows so that they are exact makes `==` pass by the choice of state, which is the
accidental zero that the governing rules forbid. The meaningful claim is that the balance holds to the arithmetic of
those two rows. Per component, the error is within 2 ulp(n): two rounded products, the rounding of 1 − r, and the
test's own addition, each at most ½ ulp(n). The non-exact state is registered *because* the discrepancy is non-zero
there.

**Replacement text:**

> **S11.A12 (restated, R-835).**
> - The cases:
>   - IAPWS-95: H2O liquid at 300 K, 1 MPa, 1 mol/s;
>   - CoolProp: CO2 vapour at 300 K, 1 bar, 1 mol/s;
>   - Wilson: liquid at 330 K, 101 325 Pa, flows (0.25, 0.25, 0.5) mol/s, and as a fourth case (0.4, 0.4, 0.8) mol/s.
> - On each, `feed → splitter(0.3) → 2 sinks` binds and solves `CONVERGED`.
> - Per component, the products equal the splitter's binary64 rows exactly: `n₂ == 0.3*n` and `n₃ == (1 - 0.3)*n`.
> - Per component, |n₂ + n₃ − n| ≤ 2·ulp(n).
> - The discrepancy is exactly 0.0 for (0.25, 0.25, 0.5). It is exactly −ulp(n), non-zero, for each component of
>   (0.4, 0.4, 0.8).
> - The outlet T and P equal the feed's.

**Work order (I1).** In `tests/test_s11_routing.py`, `CASES` gains `wilson-ulp`, and the comment about choosing exact
flows is replaced by this clause. A16 is unchanged (its three cases).

### Item 7 — S11.A68 and S11.A77(iii) (R-836): restate

**Ruling on A68.** K02's flash and mixer author one pressure row per inlet that restates an upstream pressure, and
the plan eliminates it (`SP:SPLIT-P`). No K02 unit is square by count alone, on any basis:
- heater → flash has 33 rows and 32 variables;
- the mixer has 16 and 15;
- the same holds on SYN-001 and on Wilson.

What A68 needs is that the γ–φ face changes the blocks and nothing else. The engineer's reading tests exactly that,
and adds that every row vanishes at the unit's own evaluation (worst 2.9e-8 of its kind tolerance).

> **S11.A68 (restated, R-836).** On the verification and the real records, for each of the five units:
> - its contribution has the equation ids, origins, row kinds, variable ids and block ids of the SYN-001 construction
>   with the same components and wiring, with `GammaPhiLnKBlock` (fed by the liquid flows) and the mixture enthalpy
>   blocks in place of SYN-001's;
> - the assembled feed → unit → sink flowsheet has the SYN-001 flowsheet's equation and variable ids and the same
>   counts (33/32 for heater → flash; 16/15 for the mixer);
> - every row vanishes within its `KIND_TOLERANCE` at the unit's evaluated state;
> - a recording provider sees no `lnK` and no `h_<c>` request.

**Ruling on A77(iii).** The identity holds wherever both phases can be evaluated. v2 forwards v1's refusal of a
pressure outside the records' P box, and 10 of the 18 (component, T) pairs have their P_sat outside it. Those
refusals are asserted. That every component is still covered is made executable.

> **S11.A77(iii) (restated, R-836).**
> - For each pure component i and T ∈ {310, 350, 390} K with P_i^sat(T) inside the records' P domain:
>   s^V − s^L = (h^V − h^L)/T to 1e-12 relative. These are the 8 pairs: verification VA 350 K, VB 350 K, VC 390 K;
>   real CH3OH 310 K and 350 K, C2H5OH 350 K, H2O 350 K and 390 K.
> - Each of the other 10 pairs is refused `out_of_domain` by v2.
> - The judged pairs cover all six components (asserted).

**Work order (I1b).** Add the coverage assertion to `tests/test_s11_wilson_v2.py`. The A68 test stands.

### Item 8 — §4.10's "all existing W27 tests pass unchanged" (R-837): restate

**Ruling.** D9 says that versions 1 and 2 have no provider line for S11's bases. A W27 test that snapshots the
installed build under v1 or v2 must therefore read it restricted, or be refused, so the clause contradicted D9. The
engineer's `v2_binder()` keeps every such test's routes, bind calls and assertions, and no family-C key moves. A new
test pins the refusal of the unrestricted build, and v3's reading is pinned as `v2_binder`'s routes plus
`record_source`. The version-switch test now probes 4, because version 3 is accepted (W27v3-R01 itself).

> **WO A4's acceptance (restated, R-837).**
> - S11.A30–A33.
> - Every existing W27 test passes. Those that snapshot the installed build read it through `v2_binder()`: the
>   installed tables with `SELECTABLE_BASES` restricted to the bases `snapshot.PROVIDER_LINES` covers.
> - A test pins W27-R63's refusal of the unrestricted build under version 2.
> - `test_version_switch_refuses_other_versions` probes (0, 4, True).

**Work order:** none (done at A1 and A4). I2 cites R-837.

---

## 4. Build decisions for confirmation

### Item 9 — track B (R-838)

| Decision | Ruling | Reason |
| --- | --- | --- |
| B3c: no `s11-column-v1` | accept | Q8's premise was wrong. `T06-revision-v2` already carries phase contract v2 and solves the column. A fifth policy would move the served `solve_policies` and add no capability. |
| B3b: S2's "wrong kind" and "kind not offered" are unreachable from a document; `ModelSignature` has no optional field | accept, plus a hint fix | Under R-824 a name fixes its kind. `ModelSignature` is served and frozen. The refusal hints are therefore the discovery channel for the twelve names, and one hint is stale (F-2). |
| A91 is met by the reader | accept; A91 restated | The reader refuses a dotted id with exactly A91's code, before binding. §10.2 step 9 stays as the binder's own guard. |
| B4: specification checks in the linear form | accept | This is the row the solve satisfies, judged with registered kinds. The quotient form needs a dimensionless tolerance kind that the policy lacks, and adding one is a policy change. The splitter's ratio row is the precedent. |
| B4: stage items from the standalone declaration | accept | They are judged at the state, with each regime read from the state's totals, never from the solve's signature. |
| B4: a stage at V = L = 0 raises `zero_flow_form_unknown(syn001.column)` | accept | It is a named refusal, never a heater-style reduction, and the module already treats an unknown form this way. It is unreachable from a converged solve, because `validate` refuses a no-feed column (S10). |
| B4: the column's duties in the envelope | accept | Without them the envelope misses Q₁ + Q_N (M1: −11 077 W). |

> **S11.A91 (restated, R-838).** Column `C1` beside an instance `C1.stage.<j>`, for j an equilibrium stage, is refused
> as `id_unsupported(C1.stage.<j>)` by the revision reader's id rule (`revision_flowsheet.py:83`), before binding.
> §10.2 step 9's check stays as the binder's own guard, exercised by A89(3) with the key `U-BOT`.

**Work order (I1).** Acceptance:
- (a) Every A29 case, solved through the application under the policy id `T06-revision-v2`, reproduces A29 (max
  |Δ|/tol ≤ 1, ≤ 3 Newton iterations) and certifies as A35 says. The cases are M1–M4, J1–J8, C-MW, C-EW, the stripper
  and the recycle. This is the served path, since `S01_DEFAULT_V1` is not a served policy.
- (b) The column binding's refusal hints name end specifications by their R-824 parameter names:
  - S2-missing's hint lists `<end>_<kind>` for each kind offered at that end on the basis: the γ–φ subset on Wilson,
    `<end>_purity.<component>`, `<end>_recovery.<component>` and `<end>_temperature.<stage>`;
  - no hint in the B2/B3b refusal table contains `condenser.` or `reboiler.` (asserted over the table).

### Item 10 — track C (R-839)

| Decision | Ruling | Reason |
| --- | --- | --- |
| Q-C2: the turbine's `isentropic_phase` cannot be stated in a revision | accept for S11; typed refusal; L-TH-4 text; OQ-1 to Frank | A revision parameter is a numeric quantity (a schema rule). A flag encoded as a number would add a public name, which is Frank's call. The `pure-*/sat` variant exists and is tested by direct construction (C3-7). |
| O-C4-1: a revision mixer cannot take a liquid and a vapour inlet | accept; L-TH-8; OQ-2 | R4 (one declared phase per port) is the reader's rule, shared with the column (L-COL-1). |
| C3-2: β_s outside [0, 1] reuses `isentropic_state_two_phase` | **change** | That code is false for a single-phase state, and it points an agent the wrong way: it already declared `vapor_liquid`. |
| C4-2: the thermal builders skip `instance_contract` | accept | They use the binder's codes and its helpers. The only divergence is the converse of R4, which a saturated thermal outlet must not meet (R-815). |
| C6-2: `test_m02_wo8_registries` restricted to non-`thermal.` keys | accept; §8.3 erratum | The base's keys stay pinned, and a new test pins the 27 thermal keys and 9 rules literally. The B13 precedent applies. No family-C key is involved. |
| C6-3: A63's hint asserted on the valve's own answer | accept; A63 restated; OQ-3 | The plan keeps the first line of every unit's refusal. Changing that is a cross-cutting orchestrator change. |
| O-C6-1: under v1, A62 at 1 kW gives `LINEAR_SOLVE_FAILED` | *needs a fact* (I1b) | §4.9's "typed `RANK_DEFICIENT`" is a certificate regularity status, which can be checked only once I1b registers the thermal checks. |
| O-C3-1: four supercritical closures return `not_converged` at the label switch | accept; L-TH-5 text | The answer is typed, never a wrong value. Making supercritical closures label-free is a design change outside S11. |

**Replacement texts (units design):**

> **§4.4, turbine (restated).** The isentropic state's form follows the outlet's declaration: `vapor` gives
> `pure-single/single`, and `vapor_liquid` gives `pure-*/sat`. A revision cannot state another form, because its
> parameters are numeric quantities; a parameter named `isentropic_phase` is `parameter_unsupported(<U>.isentropic_phase)`.
> Direct construction can (C3-7). §7 Q23 is closed by this text.
>
> **§4.2, typed codes (addition).** `isentropic_state_single_phase` covers two cases, in both of which the isentropic
> state is single-phase: a saturated isentropic form with β_s outside [0, 1], and a root outside the saturation range
> whose label is not the declared phase. `isentropic_state_two_phase` keeps the case of a single-phase form whose s*
> lies past the saturated entropy.
>
> **L-TH-4 (appended).** In a revision, a turbine's isentropic state takes the outlet's declared form. A vapour outlet
> whose isentropic state is two-phase is refused `isentropic_state_two_phase(<U>)`.
>
> **L-TH-5 (appended).** A supercritical PH or PS closure whose root lies at the provider's label switch (T = T_c)
> returns `not_converged` (measured: 4 of 11 200 grid outcomes, at 22.85 MPa).
>
> **L-TH-8 (new).** A revision declares one phase per port (R4), so a `thermal.mixer` takes inlets of one declared
> phase. Mixing a liquid with a vapour is available by direct construction only, as L-COL-1 is for the column's side
> feeds.
>
> **S11.A63 (restated).** A valve is declared `liquid` and its closure is SATURATED:
> - the plan ends with the message `initializer_failed(<U>): phase_regime_mismatch(<S>)`, the first line that
>   `revision.InitialStateFailure` keeps;
> - the valve's own answer carries the hint ending `declare vapor_liquid` (asserted on the unit's evaluation);
> - with the declaration corrected, the flowsheet converges.
>
> **§4.9, the v1 sentence (restated).** Under v1, a dormant single-phase thermal outlet has a singular Jacobian.
> - A solve that must move from its start ends `LINEAR_SOLVE_FAILED`. Measured: A62's flowsheet under `T04-W12`, with
>   Q = 1 kW.
> - A converged start (Q = 0) certifies with regularity `RANK_DEFICIENT`, as the SYN-001 pump's does (L-TH-7). This
>   part is checked at I1b.

**Work order (I1b).** Acceptance:
- **Q-C2.** A revision turbine: steam at 1 MPa and 573.15 K, expanded to 0.1 MPa with η = 0.5, outlet declared
  `vapor`. Measured on `iapws95-v1`: x_s = 0.9613, and the actual outlet lies 2.61 kJ/mol above h^V_sat. It is refused
  `isentropic_state_two_phase(<U>)`. A parameter `isentropic_phase` is refused `parameter_unsupported`.
- **C3-2.** In `kernel.isentropic_temperature`, `blocks.isentropic_state` and `machines` (evaluate and manifest
  limitation text):
  - C3-7's turbine, declared `vapor_liquid` with β_s > 1, gives `isentropic_state_single_phase(U1)`;
  - A55's n-pentane compressor still gives `isentropic_state_two_phase(U1)`.
- **O-C6-1.** Run A62's flowsheet under `T04-W12`:
  - Q = 0 gives CONVERGED, and its certificate's regularity status is `RANK_DEFICIENT`;
  - Q = 1 kW gives `LINEAR_SOLVE_FAILED`;
  - record the SYN-001 pump's dormant case under `T04-W12` beside it;
  - if Q = 0 is not `RANK_DEFICIENT`, stop and escalate.
- **Envelope.** L-TH-4, L-TH-5 and L-TH-8 as above.
- **Records.** Add `test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet` to §8.3's record.

### Item 11 — track D (R-840)

- **`provider_id` of a v2 result is `wilson-ig-v2`: accept.**
  - A provider whose results name a provider other than its own `describe()` would be incoherent.
  - The label is not a value: A75 and A78 compare v1's answer with the label swapped back (`float.hex`).
  - The reference convention stays `WILSON-IG-ref-v1`.
  - It lands with track D's merge of `fc645bce`, and D5's A79 must hold on the values.
- **The `ph_kernel` failure labels: change.**
  - ADR 0001 D5.2 forbids labelling a Wilson state with SYN-001's convention.
  - A failure carries no value, but its label is a claim, and agents read it.
  - **D6:** `typed_failure`, `closure_failure` and `_state_failure` take the bound provider's convention and provider
    id. Acceptance:
    - a Wilson PH-flash typed failure and a Wilson valve typed failure each carry `WILSON-IG-ref-v1`;
    - `S10C-IDENTITY PASS changed=[]`;
    - `S11-IDENTITY changed=[]`. SYN-001's label is the same constant as before.

### Item 12 — track A (R-841)

| Decision | Ruling | Reason |
| --- | --- | --- |
| CoolProp records `elemental_verification: NOT_APPLICABLE` | accept | The schema's `if/then` refuses `PENDING` with a null formula; this is §4.1's stated fallback. T08.A32 (vi) does not read the field. |
| Routing-model hints on C1 name only SYN-001 and C1 | **change** | "binds on the syn001 basis only" became false the day the routing models went basis-generic, and the five K02/T05 units and the column will follow at I1b. A hint is the agent's guidance; truth outranks byte-identity of a hint. |
| Routing `evaluate()` reports the bound convention | accept | ADR 0001 D5.2. SYN-001 is unchanged. |
| A17 tested directly on `revision_checks` | accept; A17 restated | The binder refuses a `vapor_liquid` routing port, so the unlifted path is reachable only there. That refusal is itself asserted. |
| L01's measurement binding keeps only the bases W27 v2 has lines for | accept | W27v2-A23's output stays unchanged. L01 measures SYN-001, C1 and `pr-lib-v1` only, and says so. |

> **S11.A13 (restated, R-841).** Every refused pair gives `model_unsupported(<id>)`, with its reason.
> - On every basis, the hint names every basis the model binds on, using "bases" when there is more than one.
> - The syn001↔c1 hints are byte-identical to the base for every model whose `MODEL_BASES` S11 does not change.
> - The others move on purpose: their tests enter `AMENDED_TESTS`, citing R-841.
>
> **S11.A17 (restated, R-841).**
> - A routing port declared `vapor_liquid` is refused at bind, `port_phase_unsupported` (asserted).
> - The unlifted path is therefore exercised on `revision_checks` directly. A12's flowsheets, with the splitter
>   products declared `vapor_liquid` at the declared flowsheet's solved state, give energy checks blocked with
>   `temperature_degenerate_unlifted(<S>)`, and none of them passes.

**Work order (I1b), after the `MODEL_BASES` rows land.** Remove the `S11_BASES` filter from `_basis_refusal`, and
pluralize. Acceptance:
- G1 shows `changed=` exactly the keys of the syn001↔c1 refusal tests whose model gained an S11 basis (expected
  `tests/test_m02_join.py`'s routing-model tests);
- those tests are listed in `AMENDED_TESTS`, citing R-841;
- the other syn001↔c1 hints are byte-identical.

### Item 13 — identity gate: `VOLATILE` (R-842): accept

**Ruling.**
- The binder reads neither `revision_id` nor `parent_revision`.
- Digesting them would fail the gate on clock-named ids in three T07 tests, whose binder output does not change.
  Excluding those tests instead would drop 25 keys of coverage.
- The binding's `revision_sha256` is still checked, as equal to the hash of the document passed in.
- "The binder reads neither" is prose today. I1 makes it executable.

**Work order (I1).** Acceptance: `tests/test_s11_identity_gate.py::test_g1_the_binder_reads_no_revision_identifier`
binds three corpus documents: the SYN-001 nominal revision, a C1 revision and a column revision.
- With `revision_id` and `parent_revision` changed, each gives an equal family-C binding digest.
- With one stream's flow changed, each gives a different digest, so the test is not vacuous.

---

## 5. Work orders, by WO

| WO | Carries | Acceptance (all also: the touched tests; G1 where the trigger list says so) |
| --- | --- | --- |
| **I1** | Item 2 as its *first, isolated* commit; then items 1, 6, 9 and 13 | item 2's A35-Wilson, mutation and unchanged-certificate tests; T08.A32 plus its defect test; A12 restated; A29 under `T06-revision-v2`; the column hints; the `VOLATILE` test |
| **I1b** | Items 3, 5, 7, 10 and 12 | W27 v3 `--check` with the two new mutants, and S4 on the 225 rows; A46 restated; the A77(iii) coverage assertion; Q-C2, C3-2 and O-C6-1; L-TH-4, L-TH-5 and L-TH-8; the routing hints, with `AMENDED_TESTS` |
| **D5** | Item 11 (`provider_id`): no work. It lands with track D's merge of `fc645bce` | A79 holds |
| **D6** | Item 11 (`ph_kernel` labels); item 2 on the GP certificates | the Wilson failure labels with both identity lines; \|Z\| and the one-sided worst recorded per GP certificate; rebase onto I1's first commit before A69/A71 |
| **I2** | Item 4's negative control. ADR 0050 gains an amendment line citing R-830…R-842, and ADR 0013 Amendment 3 item 7 a cross-reference to R-831. The manifest records item 2's table, F-1's step series and item 5's values. The single `reviewer` pass covers these rulings | the full gate, as planned |

## 6. Findings

- **F-1 (witness margin on Wilson columns).**
  - At the registered step, C-MW's central witness is truncation-limited at 8.243e-8 against 1e-7, a margin of 1.21×.
    C-EW's is 4.644e-8.
  - The error is O(h²) and deterministic. On C-MW it measures 7.42e-7 at 3e-5, 8.24e-8 at 1e-5, 7.42e-9 at 3e-6 and
    8.25e-10 at 1e-6, so roundoff is below 1e-11 at the registered step. The pass therefore holds across architectures
    by about 1000× the roundoff.
  - The comment on `DERIVATIVE_TOLERANCE` ("350× above the worst floor") describes SYN-001, not Wilson columns.
  - The tolerance is not changed. Loosening it would be a relaxation, and tightening it fails C-MW.
  - On C-MW, a Jacobian error can mask itself against the truncation by up to about 1.8e-7, which is still ≥ 3900×
    below the smallest entry in Z (7.1e-4).
- **F-2 (a stale hint).** The column's `specification_missing` hint says "Pin exactly one of condenser.reflux_ratio,
  …" (`column_unit.py:471`). That is the dotted spelling R-824 refuses as `parameter_unsupported`. It is fixed at I1
  (item 9 (b)).
- **F-3 (A46 near the top).** The plain 1e-6 criterion at 1e-4 below the top passes at 3.53e-7, under its own floor
  bound of 3.8e-6, so the pass depends on the noise realization. Both near-top states move to the fixed 1e-5 bound
  (item 5).

## 7. Open questions, each with a recommended default

| Id | Question | Needs | Default |
| --- | --- | --- | --- |
| OQ-1 | A vapour-outlet turbine whose isentropic state is two-phase, in a revision | Frank's preference (scope) | **Not in S11**: typed refusal (L-TH-4). Follow-up: an isentropic form whose regime is found inside the block (the isentropic state is not a stream, so ADR 0051 D1 does not bind it). This needs no new parameter. Rejected for now: a numeric flag parameter (a public name, and a wart) |
| OQ-2 | Relax R4 (one declared phase per port) for multi-inlet ports: the thermal mixer here, the column's side feeds (L-COL-1) | Frank's preference (scope) | **Keep R4 in S11** (L-TH-8, L-COL-1) |
| OQ-3 | Carry a unit's refusal hint through the plan's message (today the first line only, for every unit) | Frank's preference | **Not in S11**: a cross-cutting orchestrator follow-up that would move existing failure messages |
| OQ-4 | O-C6-1: A62's Q = 0 certificate regularity under v1 | a fact (I1b) | Expected `RANK_DEFICIENT`. Otherwise stop and escalate |
| OQ-5 | Item 2's rule on D6's GP certificates: the one-sided floor; a whole phase exactly zero | a fact (D6) | The rule applies. Above `DERIVATIVE_TOLERANCE`/10, or `unsupported` on a dormant phase: escalate with the column list |
| OQ-6 | CAS RNs in the provider-identity files (S11 §7 Q5; Frank's 2026-10-23 CAS direction) | Frank's preference | **Keep** (Q5's default). If they go, (ii-p) becomes (ii′)-style registered names, (v-p) has nothing to compare, and W27 loses IAPWS-95 matching |
| OQ-7 | InChI/InChIKey for provider-identity records | Frank's preference | **Not required**. They can be added from CoolProp 8.0.0 in a scratch venv if Frank wants parity with (ii) |

## 8. What this document does not establish

- **Item 2** shows that the AD Jacobian agrees with the residual at the absent-component columns. It is no evidence
  about Wilson's physics, and none about D6's GP cases until they are measured there.
- **Item 1** decides neither whether the rights statements are correct nor whether these files ship. That is Frank's,
  as in L01-Q4, M01 Q-N4 and S10 Q-F3.
- **W27v3-R09** gives no coverage number. The Wilson route's coverage is not counted (an under-count).
- **Item 5's 1e-5 bound** covers two near-top states only. It claims nothing about the provider's accuracy near the
  critical point.
- **Item 6's bound** is the arithmetic of the splitter's rows at the traversal start. It is not a statement about
  conservation in a state that Newton moved.
- **O-C6-1** is not ruled; it waits for its fact.
- **This round reviews no code.** The package's single `reviewer` pass does.
- **The scratch probes behind the measured numbers are not committed.** Each work order's test measures its number
  again and asserts its margin.
