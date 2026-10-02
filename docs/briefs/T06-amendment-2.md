# Brief — T06 amendment round 2 (units ADR, F6, generator arithmetic, logged choices)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-26. **Branch:** `wp/T06` (HEAD `53101dc`).
**Deliverable:** the ADR(s) and dated spec amendments below; twin re-emitted if a registered value
changes (`--check`, new SHA); a ruling list in §3 of this file (ruling, build-lane change, acceptance
test). No code; do not commit. `docs/T06_DECISIONS.md` (last two entries) has every number cited here.

## 1. Frank's decision to specify

**Spec Q11 — "Yes, in T06":** specifications and instance parameters accept other common units by a
recorded conversion — at least pressure (kPa, bar, MPa, atm, psi?), power/duty (kW, MW), temperature
(degC is done; degF?), flow (mol/s multiples, kmol/h, kg/s done, kg/h), fractions (%), and whatever the
Quantity machinery already names. This widens ADR 0001 D1 (frozen) → write the ADR amending it (0016 is
the next free number): the unit table, exact conversion arithmetic (and its binary64 rounding — one
operation where possible, like `unit-conversion-v1`), where conversion happens (validation/binding;
the four readers R1–R4 already route through `unit-conversion-v1`), how it is recorded
(`input_mapping`, `DIM-01`), what stays refused, identity consequences (a converted revision's
certificate equals its SI twin's, as A55–A56), and the T05 tests that currently register refusals for
kPa/bar/% (`tests/test_t05_w11_cases.py`) — what happens to them. New assertions and known answers.

## 2. Open items (rule each)

1. **F6** (finding; build-lane diagnosis done): the SYN-001 TP flash misclassifies a saturated liquid —
   the classification computes `Σz·K = 1.0000000000000002` (two-phase) while Rachford–Rice's
   `f(0) = Σz(K−1)` rounds to `−6.9e-17` (C3) / `−8.7e-18` (NET-02), so `f(0)·f(1) > 0` and
   `_rachford_rice` returns not_converged at iteration 0 with a misleading message. Measured on 760
   two-phase feeds: re-flashing the liquid product → not_converged 6×, LIQUID 624×, TWO_PHASE with
   β≈1e-16 130×; the vapour product → not_converged 15×. Reached by the units, the region's kernel
   checks and the verifier's fresh flash (not the compiled blocks). The fix "classify by the same
   f(0)/f(1) signs" sits in `thermo/syn001.py`, whose bytes are in every SYN-001 `model_version`
   (R-009, ADR 0011 D3). Decide: (a) fix in the provider with an ADR re-registering SYN-001's identity
   (say what moves: `model_version`, structural hash?, every identity key), or (b) a unit-layer /
   verifier-layer wrapper that re-classifies a not_converged-at-iteration-0 flash by the RR signs
   (R-016 for the verifier's copy), or (c) other. Frank's steers: fewest limitations, robustness.
2. **§6.3 generator arithmetic:** `δ = 0.2(2u − 1)` — the literal binary64 `0.2*x` and `(2u−1)/5`
   differ by one ulp at some keys (the F4 engineer's WO8 used `(2u−1)/5`); the spec's §6.3 known
   answers are "the exact value rounded once". State the exact operation the generator must use,
   before the build lane writes it (W6/M7).
3. **W3 seed:** 20260925 does not always return the exact inverse 1-norm (the A42 fixture, n = 19:
   seeds 0–19 give 5.9948, 20260925 gives 4.0300, still a lower bound; rcond₁ 0.0409 → 0.0608); M5's
   "exact at all 258" was a property of those matrices. A32/A38 still hold. Amend the text if needed.
4. **Pre-existing R-015 gaps:** the K03 fixture `syn001_off_b_restart_trace.json` regenerates today with
   116 property calls vs 115 committed (the comparison forgives property counters); the K05
   run-manifest fixture carries wall-clock fields and never regenerates byte-identically. Rule:
   re-baseline / exclude fields / leave.
5. **Build-lane choices to ratify or change:** W1 — `declared_components` always recorded (even
   `(A,B,C)`); kg/s on a component outside the table → `unit_unsupported`; empty component list →
   `components_unsupported`; DIM-01 lists specification failures before parameter failures. W2 —
   reason spellings `pressure_shift_outside_domain` / `pressure_shift_not_generic` /
   `shifted_state_<status>`, `witness_stencil_<status>(<col>)`, `projection_unevaluable(…)`; rows still
   eliminated structurally when the shift fails (claims `unsupported`); with no eliminated row there is
   no alias check, so a certificate can stay `VERIFIED`. F4 — a reconstruction the kernel refuses is
   recorded `kernel_refused`; P5 with no provenance item treats the start as `traversal-G0-v1`.
6. **The P5 consequence** (from amendment 1): P5 does not fire for a `user_guess` start, so on the nine
   acyclic cases every failed ensemble start is rescued from the causal answer. Confirm the report
   wording you require (`p_c^first` shown and stated in words).

## 3. Rulings (the design lane fills this in)

Design lane (`specifier`), 2026-09-26. Normative text: ADR 0016, ADR 0017, `docs/derivations/T06-corpus-spec.md` "Amendment 2" and every **(A2)** passage, ADR 0014 "Amendment 2", register R-081…R-084 (annotations on R-015, R-067, R-069, R-072, R-077, R-079). Twin: `t06_reference.py --check` 340 of 340; `--emit` sha256 `3058c3603b74c1eaec9ae933f2e42fae24c39565aae4cdda7fdb1d763d07d8bd`, 87 797 bytes, two emissions byte-identical. Items 7 and 8 arrived during the round and are ruled here too.

> **FOR FRANK (the build lane takes it to him): ADR 0017 moves SYN-001's identity.** Fixing F6 in `thermo/syn001.py` changes its SHA-256, which is in every SYN-001 `model_version` (R-009): every SYN-001 label, `plan_id`, K05's structural hash `4ce030ca…` and the `t02`…`t05b` keys move — by the hash substitution only; every number, outcome, trace and certificate value is unchanged (measured: 3 375 of 3 378 tests pass with the fix and the old label, the three failures F6's own registrations). No frozen interface changes beyond ADR 0001 D1's approved widening (ADR 0016). Default until he answers: everything else proceeds; the scoring run waits (ADR 0017 D6); if he declines, F6 stays a registered limitation (D5).

| # | Ruling (one line) | Build-lane change | Acceptance test |
| --- | --- | --- | --- |
| §1 Q11 | **ADR 0016: `unit-conversion-v2` replaces v1** — specifications and instance parameters, the table of D3 (°C, °F; kPa, MPa, bar, atm, psi; kW, MW; kmol/s, mmol/s, mol/h, kmol/h; kg/s, g/s, kg/h; % on fractions), `SI = RN(a·D(v) + b)` on the decimal `v` denotes (reverses R-077's binary reading: 75.1 % must equal 0.751), component before unit, records `{source, input_id, …}` in canonical order, everything else refused | W12 (spec §17 (A2)) | A67–A74; amended A55–A58; `t02`…`t05b` unchanged |
| 1 F6 | **(a), ADR 0017: fix it in the provider** — on `f(0)·f(1) > 0` return the single phase the bracket's signs name; identity re-baselined by substitution with a two-step proof. (b) rejected (a second classifier in five call sites with its own rounding; every other consumer keeps the defect). **Pending Frank** | W13, after W15, on Frank's yes | A75–A79 |
| 2 generator | `u = k·2.0**-53`, `w = 2.0*u − 1.0`, **`δ = w / 5.0`** (one division = the exact `0.2(2u−1)` rounded once; the literal `0.2*w` is not the draw), then `x_init + S*δ` as two roundings, no FMA; KATs compared by `u_hex`/`delta_hex` | W6/M7 generator | A21 (amended), A80 |
| 3 W3 seed | Text amended: the seed makes the estimate deterministic, not exact (A42: 4.0300 vs 5.9948); the seed is not changed; the exact-norm status check extends to every corpus certificate | W6 (A32 over the corpus) | A32 (amended), A38 unchanged |
| 4a K03 fixture | **Re-baseline** `syn001_off_b_restart_trace.json` with its generator in its own commit (diff exactly `property_calls` 115 → 116; counters are measured non-reproducible and forgiven by design) | W15 | A81 (a) |
| 4b K05 run manifest | **Leave; define "regenerates identically"** for it as `differences()` empty under `VOLATILE_FIELDS` plus Q-S7's hash; rewrite only when a compared field changes | W15 (docstring) | A81 (b) |
| 5 W1 | Ratified: `declared_components` always recorded; empty list → `components_unsupported`; specifications before parameters (and, added, parameters by instance order then name in code-point order). **Changed:** a kg/s value on a component outside the set is the component's error, not the unit's (component judged before unit) | W12 | A72 (a), A74 |
| 5 W2 | Ratified: the five reason spellings (reasons are not R0); alias rows still eliminated structurally when the shift fails, certificates `unsupported`; no eliminated row → no alias certificate → may stay `VERIFIED` | none | A40–A42 as registered |
| 5 F4 | Ratified: `kernel_refused` (with unit and status as fields); P5 with no provenance item reads `traversal-G0-v1` | none | existing WO3/WO5 tests |
| 6 P5 report | Wording fixed **verbatim** (§7.4's statement plus the acyclic sentence), `s_c^first/20` per case, the acyclic set computed from the plans (the "nine" is a claim the count checks) | W6 report | A84, A66 |
| 7 IDAES | **A semantics mismatch, not a genuine `DISAGREE`**: SmoothVLE evaluates equilibrium at `T_eq` shifted by up to `(ε₁+ε₂)/2` (5.0e-3 K = ε₁/2 at REF-08's saturated recycle, 9.8e-6 K at REF-03). Registered tool input `eps_1 = eps_2 = 1e-8 K` on every state block (derived from `a_T`, uniform, blind); rule 2b self-check `≤ 1e-7 K` from the tool's own record; default-ε records retained as `NOT_COMPARABLE(semantics: smooth_vle_shift(…))`; every IDAES record re-run; a later `DISAGREE` goes to `verdict`; ε never changed on the build lane's initiative. W8's four choices ratified (REF-08 tear path under `SYN-001-K03`; PC-1 on `U-FLASH.Q`; unrounded tolerance formula; DWSIM `S6` from the splitter product) | W8b | A83, A49, A51 (amended) |
| 8 VER-02/03 | **Implement the refusal in `screen`** (`target_identity`, four ADR 0008 D2.4 fields; mismatch or missing → `INCONCLUSIVE(identity_mismatch)`, numbers still recorded); the certificate passes the residual's identity (equal by construction; no registered certificate moves). Not re-registered against `state_mismatch` (never sees a matrix). A20's exceptions are four; A56 under `T05b-v2` suffices; W4's choices (NET-05 `T04-W12`; REF our-side `T06-revision-v1` except REF-08; own registry sections) ratified | W14 | A82 (W5's xfail becomes a pass), A19, A20 |

**Build-lane checklist** (order: the first six do not wait for Frank):

1. Adopt the twin emission: registry `SYN-001-T06.reference_sha256` and `corpus.reference_sha256`, `TWIN_SHA256` in `tests/test_t06_w4_registry.py`, and `benchmarks/t06/references/comparison.json` (regenerate with `scripts/t06_reference_comparison.py`; its only change is the twin's input hash) → `3058c360…d07d8bd`. Measured with the new YAML: these three tests fail until then, every other T06/reference test passes (563).
2. W15: K03 fixture re-baseline commit (A81); K05 docstring.
3. W12: ADR 0016 (units v2, parameters, component-first, records, new code, T05 test re-point, A57(a), A58 → A67, `interfaces-frozen.md` §3 note); A67–A74.
4. W14: `screen`'s `target_identity` and the certificate path; A82; drop W5's strict xfail; inertness on every registered certificate.
5. W8b: IDAES `eps_1 = eps_2 = 1e-8 K`, rule 2b, retain the default-ε records, blind re-run of every IDAES record; A83.
6. W6: generator arithmetic (A21 on hex, A80); A32 over the corpus; the report (A84). Starts may be generated now (ADR 0017 D6).
7. **Take ADR 0017 to Frank.** On yes: W13 in one isolated commit after W15, with ADR 0017 D3's proof (A78 old hash → byte-identical; A79 new keys recorded); C3's restart registrations (A77). On no: record F6 as a limitation (ADR 0017 D5).
8. The scoring run (W6/WO9) after step 7.

**New ADR numbers:** 0016 (units), 0017 (F6). Next free: 0018.
