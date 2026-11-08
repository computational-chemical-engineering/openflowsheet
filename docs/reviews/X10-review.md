# X10 inventory: review (design lane, single pass)

Date 2026-11-07. Branch `wp/X10`, head `c45e8e08`, inventory/manifest commit `18d34648`. Brief
`docs/briefs/X10-reviewer.md`. Read: `scripts/x10_inventory.py`, `docs/X10_DECISIONS.md`,
`tests/test_x10_inventory.py`, `benchmarks/x10/inventory.json` (programmatically), the harvest diff,
`revision_binding.py:1716-2000`, `revision_run.py:503-590`, `verify/checks.py:850-1010`,
`policies.py:128-145`, `admission.py:222-233`. Run: two single-thread probes of
`C1-SURROGATE-M04-v1` (scripts in the session scratchpad; numbers below). Not run: `--check`, the
test, the CoolProp-present environment, the full gate.

## Verdict

**Sound as a measurement; merge after M-1.** Every admitted pair is probed by a solve (54 admitted:
41 + 1 + 2 off CoolProp, 10 on it), every refusal is the binder's own and state-independent, and the
hashed record is reproducible. One harvest class is wrong (item 1), and the brief's premise for item 1
is false: it is neither a policy difference nor a probe error.

## Must fix

- **M-1 (item 1): `limitations[4]` is user-facing — class E, not P, with its text corrected.**
  See the ruling on item 1. Add a support-matrix row ("a `pr-c1-v1` revision whose component flows are
  small against the column scale (e.g. M04's per-tube `c1-surrogate.json`) solves CONVERGED but
  certifies UNVERIFIED: the derivative witness's step is set by the column scale, not by the state"),
  point the harvest entry's `to:` at it, and drop "not diagnosed" from the limitation. File the
  follow-up named below.

## Should fix

- **S-1 `render()` (x10_inventory.py:696-700):** the table never names R134a. Say in it that the
  CoolProp column is probed on R134a: admission holds for all 123 fluids by construction, a V cell is
  R134a's solve only.
- **S-2 `tests/test_x10_inventory.py`:** the only live check is self-referential (re-measure ==
  recorded). Add the independent oracle I checked by hand: for all 150 pairs, `refused_admission` iff
  `not registry_admits` (`MODEL_BASES`), and `refused_basis` only in `coolprop_extra_absent`. It holds
  today (0 exceptions) and catches a binder that refuses for a reason other than R-288 admission.
- **S-3 `classify()` (:497-512):** a bound pair whose `select_route` returns `no_route` falls through
  to `solve_failed` with detail `None`. No pair reaches it today; give it its own class (or
  `refused_other` with the reason) before X10 gaps re-records.
- **S-4 matrix:** mark the 9 constructed-probe cells (e.g. `V*`). A V from a constructed state is
  weaker than one from a registered revision, and X10 gaps reads this matrix.

## Rulings

1. **`c1.reactor_surrogate`: a real user-path result — class E plus a design-lane follow-up; the probe
   is right.** The comparison in the brief is between two different flowsheets.
   `test_m04_wo7_surrogate_unit.py:605-620` solves the M02 stand-in **loop** with its reactor swapped
   for the surrogate (`LOOP_PATH`, :66), not `benchmarks/m04/c1-surrogate.json`. Nothing in the
   repository solved `c1-surrogate.json` before X10; its tests only bind it (:333-345;
   `test_t07_w5c_signatures.py:349`). The policy is the same: `resolve_policy("default",
   "revision_eo")` is `T06-revision-v2` (`policies.py:129,144`), which is M02's `POLICY`
   (`m02_wo8_support.py:32`). `solve_route` runs the same `plan_revision` → `execute_plan` →
   `verify_revision` chain as the test (`revision_run.py:550-583`), and `CheckPolicy()` is what
   admission builds for a job without tolerances (`admission.py:230`). The M04 test's own path applied
   to `c1-surrogate.json` gives CONVERGED / **UNVERIFIED**, `on_pattern` = 0.1089 against 1e-7.
   - **Diagnosis.** The worst entries are `S1.n.NH3` and `S1.n.N2` on row `R:C1RX-temperature`. The
     step is h = 1e-5 × column scale = 3e-5 mol/s, while the per-tube flows are 1.4e-4 to 4.9e-3
     (h/x = 14 % for NH3, 21 % for Ar). The difference J − FD falls by 4.00× per halving of h (scaled
     0.109, 0.0272, 0.0068, 0.0017, 4.3e-4). That is pure O(h²) truncation, so the AD Jacobian and the
     residual describe the same function, and the Jacobian is not defective. The loop passes because
     its flows are plant-scale.
   - **Follow-up (design lane: scaling and certificate policy).** Decide how the witness step should
     relate to the state (for example a step relative to max(|x|, floor)), or whether such revisions
     stay UNVERIFIED by declaration. Do not decide it inside X10. It affects any small-flow `pr-c1-v1`
     revision, not only the synthetic surrogate.
2. **D-2: the constructed states are inside the declared domains, and no refusal or failure comes from
   a probe state.**
   - **Refusals.** All 96 refusals are `model_unsupported(<model under test>)` or
     `basis_unavailable(coolprop-heos-v1)`. Admission reads only the model id and the provider id
     (`revision_binding.py:1990-1997`), before any state is used.
   - **Failures.** The only failure is GP-M2's registered INITIALIZATION_FAILED (S11.A81).
   - **States checked.** R134a: T_sat(10/8/5/2 bar) = 312.5 / 304.5 / 288.9 / 263.1 K, and the
     subcooled feeds are consistent with S1 `liquid`. 440 K at 30 bar is above T_c (374.2 K) but below
     p_c, so it is gas, and S3 is `vapor`. A dry R134a expansion keeps S4 `vapor`. Steam at 400 K and
     1 bar is superheated. The Wilson turbine runs 395 K → 1.25 bar inside the 300–400 K records. The
     two corrections each move the state away from a declared limit; neither is tuning.
   - **Wording in D-2.**
     - It says "eight constructed probes", but `CONSTRUCTED` has 9 pairs (pump and turbine on CoolProp
       share one flowsheet), so the text should say 8 flowsheets / 9 pairs.
     - "Corrected once each" is inaccurate for the Wilson turbine, which by its own account was
       corrected twice.
     - TH-R1's 25 → 5 kW duty change has no stated reason.
3. **D-1: accepted for admission, which is proved by the code: `MODEL_BASES` and `provider_for`'s
   CoolProp test key on the provider id.** Solve outcomes do not transfer across fluids (S-1).
   Per-fluid provider construction is S07/S11's coverage (`test_s11_bases.py:74`), not X10's.
   - **D-4: accepted.** `bound_not_solved` claims nothing about solvability.
   - **D-5: accepted.** At 38 s, a subset saves little. Two costs follow:
     - Any new corpus or benchmark revision can change a pair's smallest native probe, so its author
       must `--record` in both environments.
     - `--record` keeps the other environment's section unchanged, so only CI (which has the extra)
       catches a stale CoolProp-present section.
   - **Harvest: P is right for `limitations[0-3,5]`; `limitations[4]` is E (M-1).**
4. **Reproducibility: yes.**
   - **Wall time.** Wall times go to stderr only (:577-583).
   - **Paths.** Revision names are relative to the repository, and the record has no `/home`,
     `.venv` or site-packages text.
   - **Environment-dependent text.** It appears only under the per-environment CoolProp keys.
   - **Floats.** None in the record: `checks_not_passed` holds ids and results, not values. Equality
     across architectures therefore depends only on outcomes, and the one non-VERIFIED margin is
     0.109 against 1e-7.
   - **Latent.** `_first_line(error)` would bring text that depends on the Python version, but 0 errors
     are recorded.

## Notes

- A pair's class is its last attempt's, not its best. With `MAX_TRIES` > 1, a CONVERGED/UNVERIFIED
  native followed by a failed one would read `solve_failed`. No pair has more than one native attempt
  today.
- 21 of the 76 off-CoolProp admission refusals have a same-function namesake on that basis (the hint
  says so). X10 gaps should separate refused ids from missing capability.
- D-2's discarded Wilson attempt is a user-facing edge: a stream at the records' 400 K upper bound
  cannot be VERIFIED, because the stencil leaves the records (ADR 0014 D5 `unsupported`). This is
  known behaviour, not new.

## Not established

- The CoolProp-present section, which I did not re-run.
- aarch64 equality, which needs CI on both architectures before the merge.
- The full gate.
- The harvest sha256 values and the `HARVEST_SIZE` arithmetic, beyond the +1 manifest / +6 items
  consistency.
- Whether a state-relative witness step is the right repair (design lane).

This review sets no `reviewed` status.
