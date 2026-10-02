# ADR 0014 — T06: the corpus and NET-07, the sampling law and the gate, a deterministic regularity estimate, a verifier that never raises on a converged solve, validation's dimension and component checks, and the reference-comparison semantics

**Status:** Accepted 2026-09-27 — T06's manifest `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` is `tested` (100 checks: 96 pass, 4 not_applicable with reasons; A29/A30 judged on scoring run 2, run 1's FAIL carried), after the design-lane review `docs/reviews/T06-review.md` and verdicts `docs/reviews/T06-verdicts.md`. Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Amended:** 2026-09-26, Amendment 1 (section at the end; D1, D3, D6, D7, D8 amended; D9–D11 added). 2026-09-26, Amendment 2 (second section at the end; D2, D3, D4, D6, D7, D8 amended; D12 added). 2026-09-26, Amendment 4 (after scoring run 1; D3, D11 amended; D13 added; the spec's Amendment 3 needed no ADR text). 2026-09-27, Amendment 5 (the closing round; D3, D6, D7, D8, D13 amended; D14–D15 added). Still Proposed.
**Date:** 2026-09-25
**Author:** design lane (`specifier`); brief `docs/briefs/T06-specification.md` (`f463e7d`)
**Directive:** Frank, 2026-09-25: *"as little limitations as possible"*; *"robustness is the important thing — if a method cannot solve a hard case and the solver then switches to another method this is also fine"* (recorded, deterministic fallbacks; never a relaxed check).
**Normative text:** `docs/derivations/T06-corpus-spec.md` (the corpus §3–§5, the law §6, scoring §7, the verifier §8, references §9, identity §10); machine-readable expectations `benchmarks/t06/reference_values.yaml` from `docs/derivations/scripts/t06_reference.py` (295 claims).
**Amends:** K04 §4.2's alias-certificate construction and §7.2's estimator call (D4, D5); K06's validation stages (D6). **Reverses:** nothing registered.
**Affected requirements:** V16, V18, V20; D05, D11, D14, D19, D20; A04, A08, A09.
**Affected packages:** T06; K04 (`verify/regularity.py`, `verify/certificate.py`); K06 (`application/validation.py`, `application/binding.py`); K05 (identity document: a new key `t06`); T07 (inherits Q2, Q4, Q6 of the spec).

## Context

Plan row T06 asks for 30+ distinct cases, a registered 20 × 20 robustness ensemble with a 95 % nominal target, eight reference comparisons, and a stronger rank screen and verifier. Registering the corpus meant building its cases and solving each once from its registered initializer (spec §2; no perturbed start was solved). That pilot found: a kg/s feed validated `READY` and bound as mol/s (no `dimensions` check exists); a specification on an unknown component diagnosed for the wrong reason; the verifier raising `VerifierError` on a converged, correct state because its alias-certificate pressure shift left the provider's domain; a high-recycle revision-built loop ending `BOUND_BLOCKED` with no recovery edge available; and `onenormest`'s dependence on numpy's global random state (T05b's hand-on). Each decision below is one a later session could plausibly undo.

## Decision

### D1. The corpus and NET-07

The counted corpus is spec §3.2's 49 cases, one per distinct failure mechanism (plan §6.1), each with a fixture, a preregistered outcome kind and denominator membership; 28 are in the success denominator, 22 are ensemble-eligible. Plan IDs keep the plan's meaning; a fixture registered earlier under a plan ID of another mechanism keeps its name and supports the right corpus case (K03's seed "NUM-01" supports NUM-04). New flowsheets form a new family, `SYN-001-T06`. **NET-07 is `SYN-001-UL-C3`**: it meets both clauses of plan §6.1's definition and its tear map has measured composition–temperature coupling; its scalar reduction and `r`-independent `T_f` are covered by NET-02 (a fixed point that depends on `r`) and by NET-03/09/10/11 (no scalar reduction). **NET-02 is registered with its physical expectation although the software fails it today** (register R-074).

### D2. The nominal sampling law

Selected coordinates per solve path (spec §6.2): the three tear flows on the SYN-001 tear path; the freed guess `S3.T` for the A02 case; on the revision path every stream coordinate and unit-owned scalar that no fixed specification pins, **with every lifted-split coordinate recomputed from the perturbed streams by the initializer's own rule**. One special parameterization: a component absent from every feed and every reaction is held at `+0.0`. `δ = 0.2(2u − 1)` of the registered scale, `u` from **`sha256-counter-v1`** (SHA-256 of a key naming profile, case, start, joint attempt, coordinate and coordinate attempt; 53 bits). Box rejection per coordinate (cap 64), start-level rejection when the start assembly refuses (cap 64); an ungenerable start is a counted failure `F-GEN`. Starts are generated once, before any solve, on the reference machine class, committed, and scored as committed on every platform. Three stress profiles (`box`, `log`, `trivial-split`) are registered with their laws and reported, never gated. THM-04 is ineligible: its tear-path start space is `{0}` (`min_i K_i(420 K, P_r) = 1.65 > 1`).

### D3. Success, the gate and its uncertainty

A start succeeds iff it ends `CONVERGED` by any recorded path, its certificate is `VERIFIED` under the default check policy, the certified state is within T02 §6.4's allowances of the case's registered root, and it finishes within **60 s**. Failure classes are preregistered and exhaustive (spec §7.2); every `F-CRASH` is a defect, and every `VERIFIED` state outside the allowances is a potential false verification until the design lane shows it is a genuine second root. **The gate is the point estimate `S ≥ ⌈0.95 N⌉ = 418` of `N = 440`, on the reference machine class and on CI aarch64, with no `F-CRASH` and no unexplained `F-OTHER-ROOT`.** The one-sided 95 % Clopper–Pearson bound on `S/N` is reported as the start-sampling uncertainty for the 22 fixed cases; no statement about other process designs is made.

### D4. The regularity estimate is deterministic

`onenormest` runs with numpy's legacy global generator saved, seeded with `20260925` and restored around each of `verify/regularity.py`'s two calls. The recipe stays plan §6.3's; no schema, threshold, status, method string or check-policy byte changes.

### D5. The verifier's alias shift stays in the domain, and a converged solve never makes the verifier raise

K03 §7.2's shifted state keeps its distinct amounts `997·(j + 1)` Pa but moves a pressure column **down when the provider's domain predicate refuses the upward value**, and reports the alias certificate `unsupported` (`pressure_shift_outside_domain`, `pressure_shift_not_generic`) when neither direction is admissible or two distinct pressures coincide. Any evaluation failure at a state the verifier constructs — the shifted state, a witness stencil point, ADR 0013's projection — is the served check `unsupported` with its reason and the verdict `UNVERIFIED`; no `VerifierError` leaves `verify` or `verify_revision` for a `CONVERGED` solve carrying its full state.

### D6. Validation's `dimensions` stage and component references

`DIM-01` (`stage: dimensions`): every Quantity in a specification or instance parameter is in its kind's internal SI unit and has the kind its target path requires; `COMP-03` (`stage: component_reference_compatibility`): every component a specification or a component-keyed parameter names is in the revision's component set. Either failing makes the revision `INVALID`, naming the offending ids. The legacy binding refuses the same conditions (`conflict`). Units stay internal-SI (ADR 0001 D1); conversion at an API boundary is not decided here.

### D7. The reference comparisons

All eight plan §6.4 fixtures against **both** DWSIM 9.0.5 and IDAES 2.13.0. Semantics: every fixture with phase equilibrium at `P = P_r` (both tools lack the Poynting factor; SYN-001's factor is 1 there); DWSIM's `ΔH_vap,i := L_i + P_r v_i` and `ΔH_f,ig,i := ΔH_vap,i` (derived: DWSIM's latent then equals SYN-001's at every pressure and its liquid formation enthalpies are zero); IDAES's formation data as the probe's; IDAES mixer `none` + outlet `P = P_r`; solver settings registered as inputs (Ipopt with MUMPS, `tol = constr_viol_tol = 1e-10`; DWSIM flash loops `1e-10`, `Recycle` `1e-12` kg/s, `1e-8` K, `1e-6` Pa). Tolerance `a_k + 1e-6 |v|`, `a_k` T02 §6.4's allowances. A mechanical classification (access → tool accuracy → ours not verified → `AGREE`/`DISAGREE`) precedes the `verdict` agent's recorded verdict; two positive controls (DWSIM unmapped latent; IDAES at 1.5e5 Pa) must classify `DISAGREE`. Tools never run in the gate; their committed outputs are re-classified by it.

### D8. Identity and replay

A new key `t06` in K05's identity document carries the new cases' registered-initializer R0 records, the diagnosis fixtures' statuses and codes, and the ensemble's definition (never per-start outcomes). `t02`…`t05b` and `4ce030ca…` must not move. Ensemble replay is harness-level: a start is re-run from the committed starts file and its record compared with `run.compare.differences` under `K04-numerical-policy-v1`.

## Alternatives considered

- **D1: building a new NET-07** — discards the one thermally coupled recycle with a 40-digit reference and a measured tear-map Jacobian, for no coverage NET-02 and NET-03/09/10/11 do not add. **Counting SYN-001's r-variants or A02's targets separately** — forbidden by plan §3.2/§4.3 and would pad the count. **Dropping NET-02 or retuning it to a recycle ratio the solver handles** — choosing cases by the solver's outcome is selection toward the gate (R-074).
- **D2: perturbing only the traversal's torn-stream guesses** — degenerate for acyclic cases and nearly consistent starts elsewhere, so it tests little. **Perturbing lifted-split coordinates independently** — makes the start's phase assignment arbitrary; that is the `trivial-split` stress profile, not the nominal law. **numpy's PCG64** — adds a version dependence and sequential state; a counter-based hash is order-independent and reproducible from a key. **Regenerating starts on every platform** — the initializer's floats differ in the last bits across platforms, so "the same starts" would not be the same.
- **D3: gating on the lower confidence bound** — the blueprint's wording is the success fraction; a bound at 95 % would demand `S ≥ 426` of 440, 96.8 % observed (`ref.closed_form.gate`), a stricter gate than the blueprint registers (Q7 leaves it to Frank). **Treating 440 starts as independent designs** — plan §6.2 forbids it. **Excluding `F-GEN`** — silently shrinks the denominator.
- **D4: exact `‖Ĵ⁻¹‖₁` in the certificate** — departs from plan §6.3's recipe and moves every recorded `rcond₁`; the ensemble harness computes the exact norm beside the estimate instead (spec §8.3). **`t = 1`** — a weaker estimate, still an estimate. **Leaving the estimate random** — same-machine replay of `b` is then not exact.
- **D5: shifting by the rank among pressure columns** — changes every registered certificate's shifted state for no gain. **Letting `VerifierError` stand** — an untyped exception on a converged solve is a placeholder path, not a result (rule 5).
- **D6: converting units at binding** — makes the stored revision disagree with what was solved and belongs to an API boundary (T07). **Leaving the check to the schema test** — `validate()` is what a user calls, and it said `READY`.
- **D7: comparing at `P ≠ P_r` with a declared Poynting difference** — a known equation difference inside a numerical tolerance is tuning by another name; it is a positive control instead. **Using the tools' default settings** — DWSIM's `Recycle` default leaves 0.0306 mol/s of balance error on the recycle. **Using IDAES's default MA27** — not open source (HSL); MUMPS is registered and MA27 disclosed.
- **D8: per-start event sequences in R0** — adaptive floating-point decisions are outside the cross-platform promise (blueprint §8.3). **Generalizing K05's bundles now** — a T07/T08 scope decision (spec Q6).

## Consequences

C1. Four registered expectations fail today and are registered as such: STR-06 (F2), STA-03 (F1), NET-11's certificate (F3), NET-02 (F4). W1 and W2 fix the first three; NET-02 needs a design pass (spec Q1, phase R1).
C2. Validation reports gain two `PASS` entries on every registered revision (regenerated fixtures, R-015); no status changes.
C3. Recorded `rcond₁` and `b` values become fixed functions of the matrix (R1 fields); no R0 field moves.
C4. The gate may fail on the measured rate; that is reported, not engineered (CLAUDE.md "Scientific conduct").

## Acceptance evidence

Spec §13's assertions A01–A54 in `evidence/T06/<commit>/manifest.json`; in particular A37–A46 (the inertness of D4–D6: `t02`…`t05b` and `4ce030ca…` unchanged, every registered certificate bit-identical after D5, every registered revision's status unchanged after D6), A21–A36 (the law and the gate), A47–A54 (the references), and the `t06` key equal on x86-64 and aarch64.

---

## Amendment 1 — 2026-09-26

**Author:** design lane (`specifier`); brief `docs/briefs/T06-amendment-1.md` (`8e560e0`; its §4 is the ruling list). **Affected packages (A1):** P01 (`units`: the conversion), K06 (`application/binding.py`, `application/validation.py`), T05 (`models/revision_flowsheet.py`: the order mapping and the pins), K04 (`verify/certificate.py::_revision_values`), K02/K03 (`models/syn001/flowsheet.py`, `orchestrator/tear.py`: D10), T06, T07. **Normative text:** `docs/derivations/T06-corpus-spec.md` "Amendment 1" and every passage marked **(A1)**; machine-readable expectations re-emitted (313 claims; sha256 `a22bc72c277e712650a367aee6c369f1e4ad59e5b153c2e7f7a63bc384f90f75`). **Register:** R-076 … R-080; R-066, R-068, R-071, R-072, R-074 annotated. R-075 is ADR 0015's.

**Context.** Frank answered on 2026-09-26 (`docs/T06_DECISIONS.md`): Q3 *support* a permuted component order; Q4 *convert* non-SI units (kg/s → mol/s via the molar masses, °C → K, recorded; unknown units still refused); Q7 the gate on the *point estimate*; for F4 he approved ADR 0015's two additive enum widenings, counting restart-rescued starts as successes (reported per case), and the restart as T07's product default. Phase M (M1–M6) raised questions M1, M4 and M6. Measuring for this amendment found F7 (a permuted SYN-001 revision crashes the legacy tear path) and that the original D6 contradicted ADR 0001 D1.4.

### Amended decisions

- **D1 (amended).** STA-03 and STA-04 become `verified_at_reference` — at SYN-001-nominal's and C2's roots, bit for bit — so the success denominator is **30** (was 28). Neither is ensemble-eligible: eligibility clause (e) now excludes a case whose compiled problem and start restate another case's (NUM-04 → NET-01, STA-03 → NET-01, STA-04 → NET-08; generator-checked). The eligible set, `N = 440` and `S_min = 418` do not move.
- **D3 (amended).** The ensemble's revision path runs **`T06-revision-v1`** = `T05b-v2` with only `globalization.eo_recovery = homotopy_or_sequential_restart` (ADR 0015). A start that converges only through edge 3's restart is a success (Frank), reported per case as `s_c^first + s_c^rescued`, with the report stating that a restart discards the start. The gate stays the point estimate `S ≥ 418` of 440 on both machine classes (Q7, confirmed); the Clopper–Pearson bound is reported on `S` and, for information, on `S^first`. NET-02 is registered `VERIFIED` under `T06-revision-v1` and `BOUND_BLOCKED` under `T05b-v2`/`T05-W13` (the edge-off control); R-074 is closed by R-075.
- **D6 (amended; replaces "units stay internal-SI … conversion at an API boundary is not decided here").** Specification values in a unit other than their kind's SI unit are **converted** by **`unit-conversion-v1`**, which is exactly ADR 0001 D1.3–D1.4: `degC` → K on a temperature target (`value + 273.15`, one binary64 addition) and `kg/s` → mol/s on a one-component flow target (`value / M_c`, one binary64 division, `M_c` from an id-keyed table of SYN-001's molecular weights). The declared kind must be the target's, or `mass_flow` for the mass basis; anything else is refused with the revision binding's existing codes (`specification_kind_unsupported`, `specification_unit_unsupported`). One function in `process_runtime.units`; every reader of a specification value goes through it — the legacy binding, the revision layer's `_read` (and so `verify_revision`), `verify_bound`'s `_revision_values`, and `DIM-01`. Instance parameters (Quantities) are not converted. Conversions are recorded in the bindings' new `input_mapping` and in `DIM-01`'s `PASS` message and implicated ids; the certificate, which judges the SI declaration, does not carry them. `DIM-01` fails (`INVALID`) on a refused unit or kind, because such a unit violates ADR 0001 D1.1. `COMP-03` is unchanged.
- **D7 (amended; M6).** IDAES `constr_viol_tol = 1e-9` for every final solve (the registered `1e-10` sat at 3.4 ulps of a 2e5 Pa row; M6 measured the violation stuck at 1.02e-10–1.16e-10); `tol = 1e-10`, MUMPS everywhere including IDAES's initializers (whose other options are IDAES's defaults). IDAES has converged iff Ipopt ends "Optimal Solution Found". PC-1 is DWSIM's only ((PC-1, IDAES) is `not_applicable`); PC-2 runs in both tools, with feed (1, 1, 1) mol/s, 300 K, liquid, 1.5e5 Pa and our fixture `SYN-001-T06-PC2`. REF-08's tool-side recycle guess (0.2, 0.6, 0.8) mol/s, 360 K, `P_r` is a registered tool input. DWSIM's REF-07 extent is derived from its conversion of A, so B and C carry rule 2 (disclosed). The six IDAES records run at `1e-10` (REF-01, -02, -03, -07, -08, PC-2) are re-run blind before W8.
- **D8 (amended).** The `t06` key gains STA-03's conversion records and tear-path R0 record (asserted equal to SYN-001-nominal's), STA-04's declared order and R0 record (asserted equal to C2's), D10's typed outcomes, NET-02 under `T06-revision-v1`, and each path's policy id in the ensemble definition.

### Added decisions

- **D9. A permuted component order is mapped onto the provider's** (Q3). A declared `component_set.components` that is a permutation of the provider's `describe().components` is accepted; the binding's components are the provider's order; the declared list is kept in `input_mapping.declared_components`. Every component-keyed input is keyed by id, so nothing else changes. One function in the revision layer, called by `_read` and by the legacy binding (which fixes F7). `configuration_sha256`, the label, `constants_sha256`, `variable_ids` and the certificate are the unpermuted twin's (R-047's own rule: the declared order selects no expression or id after the mapping); `revision_sha256` differs. Any other list is refused `components_unsupported`. `thermo/syn001.py` is unchanged.
- **D10. The legacy tear path types a failed registered initializer** (M1). `Syn001Flowsheet.initial_recycle` raises `InitializerFailedError(SpecificationError)`; `solve_tear` returns `INITIALIZATION_FAILED` with message `initializer_failed(SYN-001-tear-init-v2): <status>: <first line>` and a trace of one `solve_closed` event, instead of letting the exception escape.
- **D11. The shared-provider qualification ([A09], D14) is `independence_qualifications`** (M4). It is already implemented: one entry per `energy_balance.*`, `phase_admissibility.*` and `independent_split.*` check, naming the provider's identity, plus a fourth statement (measured on six certificates). It is not a `limitations` entry, and ADV-06 M's limitation set is exactly `[derivative_limitation]`. No chunk implements D14; W7 has no dependency on it. K04 §8.2's text says otherwise; an erratum is recommended.

### Alternatives rejected (Amendment 1)

- **D6:** a decimal (exact-sum) conversion — a second arithmetic for a ≤ 1-ulp difference nothing needs; converting instance parameters — contradicts P01's `check_quantity` and ADR 0001 D1.1, and no v0.1 parameter has a convertible unit; converting `kPa`, `bar`, `kW`, `%` — widens ADR 0001 D1, which is frozen (spec Q11, Frank's, default not in v0.1); recording conversions in the certificate — the certificate's subject is the declaration (R-035), and the legacy `verify` never sees the revision; `DRAFT` for an unknown unit (R-022's "cannot read") — a unit outside ADR 0001's rules is a defect against a frozen rule, not a tool limit.
- **D9:** permuting at the provider boundary — every property call, derivative column and cache key touched, a mapping inside the residual path, and a column order that differs from the twin's, so agreement only within a tolerance; the declared order in `configuration_sha256` — two labels for one equation set; the mapping in the certificate — two certificates of one declaration and state differing by how a document was read.
- **D10:** leaving the raise (rule 5; the revision path already types the same condition); a domain check at validation (blueprint §4.3; T07's with Q2).
- **D11:** moving the qualification into `limitations` — moves every certificate's R0 projection (limitation kinds are R0).
- **D7:** `constr_viol_tol = 1e-9` only for REF-04/05/06 — a per-fixture setting reads as tuning; an IDAES analogue of PC-1 — a new control needing its own derivation, for a tool PC-2 already discriminates 4 581×; counting "Solved To Acceptable Level" — a silent relaxation of the registered `tol`.
- **D1:** making STA-03 and STA-04 eligible — their starts would re-sample NET-01's and NET-08's basins under other names (and change `N` after the gate arithmetic was registered).

### Consequences (Amendment 1)

- C1 (amended). The registered expectations that fail today are now STR-06 (F2), STA-03 (F1: it converts nothing), STA-04 (the refusal), NET-11's certificate (F3), NET-02 under `T06-revision-v1` (until ADR 0015's work orders land), the legacy permutation check (F7) and the typed initializer failure (D10). W1a, W1b, W2, W11 and ADR 0015's WO1–WO6 fix them.
- C5. `validate()`'s reports gain `DIM-01` and `COMP-03` `PASS` entries on every registered revision (unchanged from C2); for a converted revision `DIM-01`'s `PASS` names the conversions. No registered binding, label, key, trace or certificate moves: every registered revision is in SI and in the canonical order (the inertness proofs of W1a and W1b), and nothing registered reaches D10's raise.
- C6. Frozen interfaces: none change for D6, D9, D10 or D11 — D6 implements ADR 0001 D1.3–D1.4, which are in the freeze. ADR 0015's two enum widenings (F4) are Frank-approved and ADR 0015's own.
- C7. T07 inherits: storing an SI twin with `display_unit` at commit; presenting results in a declared order (spec Q13); converting `bounds` and `tolerance` when it first reads them; the widening question (Q11).

### Acceptance evidence (Amendment 1)

Spec §13's A55–A66 and the amended A01, A02, A17, A33, A49 and A51, in `evidence/T06/<commit>/manifest.json`. In particular: A55/A56 (STA-03 byte-identical to SYN-001-nominal on both paths, and `verify_bound`'s read), A57 (the refusals and `tests/test_t05_w11_cases.py` unchanged), A58 (the conversion's bit patterns), A59–A61 (STA-04 and the legacy permutation byte-identical to their twins), A62 (the typed initializer failure), A63–A66 (F4's registration and the rescued-start report). The twin's `--check` passes 313 claims, and two `--emit` runs are byte-identical.



---

## Amendment 2 — 2026-09-26

**Author:** design lane (`specifier`); brief `docs/briefs/T06-amendment-2.md` (its §3 is the ruling list), with items 7–8 sent during the round. **Normative text:** `docs/derivations/T06-corpus-spec.md` "Amendment 2" and every passage marked **(A2)**; ADR 0016 (units) and ADR 0017 (F6, **pending Frank**); machine-readable expectations re-emitted (340 claims; the sha256 in the specification's header). **Register:** R-081 … R-084; R-015, R-067, R-069, R-072, R-077, R-079 annotated.

**Context.** Frank decided Q11 (units, in T06). The build lane diagnosed F6, found the draw's `0.2·w` ambiguity, the seed's inexactness at a constructed fixture, two R-015 gaps, and — from W8 and W4/W5 — IDAES's SmoothVLE shifting saturated streams and VER-02/VER-03's refusal missing from K04.

### Amended decisions

- **D2 (amended).** The draw's binary64 arithmetic is fixed: `δ = (2u − 1)/5` in one division (the exact `0.2·(2u − 1)` rounded once), then `x_init + S·δ` in two separately rounded operations; the KATs carry `u_hex`, `delta_hex` and are compared as bits. The literal `0.2 * w` is not the registered draw (it differs at 35 % of keys).
- **D3 (amended).** The rescued-start report's wording is fixed verbatim, with `p_c^first` per case and the acyclic cases counted from their plans (spec §7.4 (A2)).
- **D4 (amended).** The seed makes the estimate deterministic, not exact (A42's fixture: 4.0300 against 5.9948); the exact-norm status check runs at every certificate the corpus issues as well as at every ensemble state. The seed does not change.
- **D6 (amended again).** Superseded in its unit part by **ADR 0016** (`unit-conversion-v2`: specifications and instance parameters; `RN(a·D(v) + b)`; the table; component before unit; records with `source` and `input_id`, ordered by the canonical revision). `DIM-01` and `COMP-03` otherwise stand.
- **D7 (amended).** IDAES's SmoothVLE is a known equation difference and is removed by a registered tool input, `eps_1 = eps_2 = 1e-8 K` on every state block of every IDAES fixture and control, with a tool-only self-check (rule 2b: shift ≤ `a_T/100`); W8's default-ε records are retained as `NOT_COMPARABLE(semantics: smooth_vle_shift(…))` and every IDAES record is re-run blind. W8's choices ratified: REF-08's our side on the tear path under `SYN-001-K03`; PC-1 on `U-FLASH.Q`; tolerances by the unrounded formula; DWSIM's REF-08 `S6` from the splitter product.
- **D8 (amended).** ADR 0017, if Frank approves it, moves every SYN-001 label and so `t02`…`t05b`, `4ce030ca…` and `t06`, by substitution only (ADR 0017 D3's proof); from its commit on, "must not move" refers to the re-baselined values. The `t06` key's conversion records carry ADR 0016's fields.

### Added decision

- **D12. The regularity screen refuses a matrix whose identity is not the target's** (VER-02, VER-03; K04 §7.5 and A24, never implemented). `screen` gains `target_identity` (ADR 0008 D2.4's four fields); on a missing or differing `jacobian_identity` its status is `INCONCLUSIVE(identity_mismatch)` with the matrix's numbers still recorded; the certificate path passes the residual's identity, equal by construction, so no registered certificate moves. Not re-registered against the `state_mismatch` guard, which never sees a matrix.

### Alternatives rejected (Amendment 2)

- **D2:** the literal `0.2 * w` (a second, unregistered draw); comparing the 17-digit decimal strings as binary64 (they do not determine the double at one KAT).
- **D4:** another seed chosen because it is exact at a known fixture (tuning a constant on an observation).
- **D7:** a genuine `DISAGREE` for the `verdict` agent (the mechanism is an equation the tool was configured to solve); `NOT_COMPARABLE(semantics)` without a re-run; `ε = 0` (non-smooth at a saturated stream); a per-fixture ε.
- **D12:** re-registering VER-02/VER-03 against `state_mismatch` (a raise on a state, not a regularity word on a matrix); leaving the strict xfail (a registered verifier test with no code path).

### Consequences (Amendment 2)

- C7. Frozen interfaces: ADR 0001 D1 widened by ADR 0016 (Frank's decision); nothing else frozen changes. ADR 0017 moves registered identity keys, not a frozen interface, and is Frank's to approve.
- C8. Build-lane chunks W12 (units), W13 (F6, after Frank's yes), W14 (the refusal), W15 (R-015), W8b (IDAES re-run) and W6's generator and report items (spec §17 (A2)).

### Acceptance evidence (Amendment 2)

Spec §13's A67–A84 and the amended A19, A20, A21, A32, A44, A49, A51, A55–A58 and A66, in `evidence/T06/<commit>/manifest.json`. The twin's `--check` passes 340 claims and two `--emit` runs are byte-identical.

---

## Amendment 4 — 2026-09-26 (after scoring run 1)

**Author:** design lane (`specifier`); brief `docs/briefs/T06-scoring-round.md` (its §3 is the ruling list). **Normative text:** `docs/derivations/T06-corpus-spec.md` "Amendment 4" and every passage marked **(A4)**; ADR 0018 (the solver's terminal refinement, **pending Frank's approval of one enum widening**); machine-readable expectations re-emitted (347 claims, `e97f61ce…`; additive). **Register:** R-085 … R-087; R-080 annotated.

**Context.** Scoring run 1 (`ref-x86-64`, `dfa7d09`, `T06-revision-v1`): S = 431 of 440, gate **FAIL** on four THM-09 `F-OTHER-ROOT`s — the registered root stopped inside a row-tolerance window 5.02 × S3's temperature allowance. The build lane also found the two-phase closure identically zero, three `F-BUDGET`s with an under-reporting counter, A33's wording broader than the certificate's rule, and a false branch label behind NET-11's "roots 2".

### Amended decisions

- **D3 (amended).** Run 1's FAIL stands. The revision path's policy for run 2 and after is `T06-revision-v2` (ADR 0018: `globalization.eo_core = "newton_refined"`); the tear path and NET-05 keep theirs. Nothing that scores a start changes: N, `S_min`, S1–S4 and T02 §6.4's allowances, the failure classes and §7.2's explanation route (a genuine second root only), the budgets and the ceiling. Run 1's four are diagnosed — the registered root inside the certificate's own `b`, not a false verification — and that diagnosis is a finding, not an explanation. A cost remedy for `F-BUDGET` is admitted only if result-inert, and the revision path's recorded `property_calls` equals its meter's. ADR 0013 D1's rescue of THM-09 start 1 is ruled sound (spec Amendment 4).
- **D11 (amended).** The qualified check ids are the prefixed checks whose result is `pass` or `fail`; the certificate's rule (qualify what consulted the provider) is right, A33's wording was not.

### Added decision

- **D13. The two-phase admissibility closure is the saturation closure** (spec §8.8). For a flowing, non-degenerate two-phase lifted split: `max(|T − T_b(l, P)|, |T − T_d(v, P)|)` from the verifier's own `band_ends`, against the policy's `τ_T`, reference 100 K, id and category unchanged, `unsupported(closure_<status>)` on a saturation failure, judged where ADR 0013 D1 judges `phase_admissibility`. It replaces K03 §8.2's `Σ(y − x)`, which is identically zero. It moves exactly four registered expectations — T05b B34 (a)'s tally, B16's and B26's lists at Newton's stop, one T04 schema fixture's tolerance and reference — and no identity key (measured).

### Alternatives rejected (Amendment 4)

- **D3:** widening S3 to the row window or to `b`; adding "the registered root within `b`" to §7.2's explanations; raising the property budget to the three starts' measured 10 093–12 524 calls. Each is a criterion chosen on run 1's outcomes. The same rule under every existing policy instead of a new policy value — a silent change of registered policies' meaning, and measured to move four registered tests. Re-forming the equilibrium row for small `V·L` — it moves every lifted split's rows and the check policy (ADR 0018's alternatives). An exact memo for `F-BUDGET` — measured to save nothing.
- **D11:** qualifying `not_applicable` checks, which would claim a provider dependence that did not happen.
- **D13:** the composition sums against a fixed ε (a mixture-dependent temperature accuracy); a tolerance scaled by `V·L` (a computed tolerance, and implied by the rows); deleting the check (it leaves ADR 0013 D3's unresolved splits unguarded).

### Consequences (Amendment 4)

- C9. Frozen interfaces: ADR 0018's enum widening only (Frank's to approve). D13 changes no schema, check id, category, kind or `check_policy_sha256`.
- C10. Build-lane chunks W17–W23 (spec §17 (A4)); run 2 (W23) after Frank's yes on ADR 0018.
- C11. Recommended errata (design lane, not written here): K03 §8.2's two-phase row and K04 §4.7's closure description (D13); K04 §8.2 (D11, as recommended at Amendment 1).

### Acceptance evidence (Amendment 4)

Spec §13's A86–A95 and the amended A33, in `evidence/T06/<commit>/manifest.json`. The twin's `--check` passes 347 claims and two `--emit` runs are byte-identical.

---

## Amendment 5 — 2026-09-27 (the closing round)

**Author:** design lane (`specifier`); brief `docs/briefs/T06-closing-round.md` (its §2 is the ruling list). **Sources:** the design-lane review `docs/reviews/T06-review.md` (`bc9ef84`), the verdicts `docs/reviews/T06-verdicts.md` (`167bfd4`), and Frank's answers of 2026-09-27 (`docs/T06_DECISIONS.md`, `66861d5`): **yes** to a fresh-draw holdout ensemble in T06, reported and not gated; `newton_refined` kept as T07's default. **Normative text:** `docs/derivations/T06-corpus-spec.md`, "Amendment 5" and every passage marked **(A5)**; ADR 0018 Amendment 1. The machine-readable expectations are **not** re-emitted: no registered value moves (347 claims, `e97f61ce…`, `--check` re-run). **Register:** R-088 … R-090 added; R-085, R-086 and R-087 annotated.

**Context.** Run 2 passed the gate on both machine classes (S = 434 of 440 each), and the verdicts found it legitimate, with qualifications. The review found T06 ready once ADR 0018's outcome claim is corrected (M1). Both left items that are registration text, not code:

- a self-contradictory sentence in §7.3;
- an "exact" that cross-machine floats cannot meet (A50);
- a floor that was a rounded measurement (A92);
- a certificate hash no test read;
- run evidence kept in a scratchpad, with a mislabelled machine class;
- an A90 that the run records cannot meet.

Frank asked for a holdout.

### Amended decisions

- **D3 (amended).** §7.3's last sentence now states R-087's rule: after an ensemble solve has been seen, nothing that *scores* a start changes; a solver or verifier remedy, named by a design-lane amendment, is re-scored by the full gate on both classes; every earlier run stays on record. **Added:**
  - the holdout ensemble `holdout1` (D14), reported and never gated;
  - run 2r, run 2's starts re-run once with the instrumented harness to meet A90. Its classes and `S` must equal run 2's per class, or the difference is a discrepancy for the design lane and the `verdict` agent. The gate verdict stays run 2's.
- **D6 (note, no rule change).** ADR 0016 V0's "the binary64 value as read" is read with ADR 0002 D3.3: a JSON integer ~~beyond 2⁵³~~ whose digits are not the canonical spelling of its nearest binary64 (*amended by ADR 0002 Amendment 1, 2026-09-27*; every integer up to 2⁵³ has a reading, exactly one per binary64 in (2⁵³, 10²¹) does, none from 10²¹ does, and spec A100's registered integers and results are unchanged) has no binary64 reading. Every number reader therefore refuses it with reason `value`, exactly as it refuses a non-finite float in the same field (codes `specification_value_unsupported(<id>)`, `parameter_quantity_invalid(<instance>.<name>)`; spec §8.5 (A5), A100). *Measured:* `10⁴⁰⁰` raised `OverflowError` and `2⁵³ + 1` raised `CanonicalizationError` on the bindings. The same escape from fields no reader reads is a K06 boundary gap, registered for T07 (spec Q29).
- **D7 (amended).** An our-side reference record carries only fields A50 compares. `certificate_sha256` is dropped: it was machine provenance, checked by no test, and stale since W19. A50 is non-floats exact and floats to 1e-12 relative, over every field. *Pre-A5:* "exact", which the build lane rightly relaxed.
- **D8 (amended).** No identity key moves. The holdout's definition is registry content, not R0.
- **D13 (amended).** A92's floor is `100 τ_T = NEAR_THRESHOLD_MARGIN² · τ_T` (1e-4 K), a decade beyond K04's near-threshold band. T05b B34 (a)'s closure values are recorded, not asserted, because they depend on the machine: 23.78 K on the reference machine, 16.16 K on both CI runners, for one state. *Pre-A5:* "≥ 9.5e-4 K", a measured minimum rounded up.

### Added decisions

- **D14. The holdout ensemble is the frozen generator at start indices 20…39** (Frank's yes; spec §7.6 (A5); R-089).
  - It uses the same law, cases, coordinates, caps and assembly, and the keys `T06-ens-v1|nominal|<fixture>|20…39|…`, none of which is a gate key.
  - It is generated by `generator.generate_start` on `ref-x86-64` and committed alone before any holdout solve.
  - It is run at the closing commit under run 2's policies on every class, and reported per §7.4 with no gate line.
  - An `F-CRASH` in it is a defect. An `F-OTHER-ROOT` in it goes to the design lane before the manifest cites V20's no-false-verification clause.
- **D15. Run records are evidence and are kept as evidence** (spec §6.6 (A5), §7.5 (A5); R-090).
  - A run document records the run id, the commit and a clean-tree flag, the lock hash, the registered `cache_condition`, and a machine class decided from the host by the harness (never the generator's literal).
  - Per attempt, it records whether ADR 0018's rule fired and how it ended, parsed from D5's message.
  - Run files, reports and comparisons are committed, unedited, under `benchmarks/t06/ensemble/runs/`, with `SHA256SUMS` and the registry's `ensemble.runs` table.
  - The judged run 1 and run 2 bytes are committed with the verdicts' §0 hashes.

### Alternatives rejected (Amendment 5)

- **D3:** keeping "nothing in §6 may be changed" and treating run 2 as illegitimate. That imposes a rule the plan does not have (plan §6.5 orders the re-run), and the verdict rejected it. Gating on the holdout: Frank's answer is "reported, not gated", and a gate added after two runs would be a criterion chosen on outcomes.
- **D7:** a machine-independent certificate digest (the R0 projection's hash) in place of the dropped hash. It would add an exact check of per-check results that `verification_status`, `limitations` and `non_passing_checks` already carry for the comparison's purpose, and the `t06` key (A45) already checks REF-01…07's certificate R0 across architectures.
- **D13:** a floor re-derived from each new minimum. It fails on some machine or is lowered again (review S3).
- **D14:** a new first key field for the holdout. It needs either an edit of the frozen generator, which breaks A25 by design, or a second implementation of its draw loop. Regenerating or extending the nominal file: its hash is what run 1 and run 2 scored.
- **D15:** run files as git-ignored artifacts (`evidence/**/artifacts/`, the evidence README's default for bulky outputs). The gate's evidence would then live on one disk and in CI artifacts that expire on 2026-12-25; the files are text, about 2.2 MB each and about 0.12 MB compressed. A machine class written by the generator: the generator is frozen with its file.

### Consequences (Amendment 5)

- C12. Build-lane chunks W24–W32 (spec §17 (A5)). The only `src/` changes are ADR 0018's docstring sentence (W24) and S5's number reading (W25). `generator.py` is not edited.
- C13. The campaign manifest records run 1, run 2, run 2r and `holdout1` as separate records (A95 (A5)).
- C14. T07 inherits spec Q24–Q29 (R-088).

### Acceptance evidence (Amendment 5)

Spec §13's A96–A100 and the amended A50, A88, A90, A92 and A95, in `evidence/T06/<commit>/manifest.json`. The twin's `--check` passes 347 claims unchanged.
