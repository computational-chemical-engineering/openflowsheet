# Brief — G1: the cross-architecture replay comparison (an ADR, decided on its own grounds)

**To:** `specifier` (design lane). **From:** build lane, 2026-10-01. **Branch:** `wp/T08` at HEAD.
**Frank approved this pass (2026-10-01, "Go ahead now")**, knowing it is costly for his weekly usage — be decisive.

## The question

What must a replay of a committed bundle on a *different* machine class (`compatible_reproduction`, ADR 0007) compare,
and how, so that T08.A45 ("every bundle MATCHes … in `compatible_reproduction` on aarch64") tests reproducibility
without comparing floating-point noise or values derived from it? Deliver an ADR (**0025**, the next free number) with
a **new policy id** (do not edit `K04-numerical-policy-v1` in place; registered results compared under it keep it), the
exact comparison table, the A45 row as it then reads, and a build-lane work order.

## The integrity constraint (read first)

The result that triggered this is known: at `C` = `814e151`, the aarch64 replay gave 31 MATCH / 21 MISMATCH under the
current comparator (`docs/t08-rc-record.md`, F2; `docs/reviews/T08-verdicts.md` finding G1). **Do not tune the policy to
make these 21 pass.** Decide each rule from ADR 0007's own principles (D1 classes, D2 floats within declared policy,
F1: bitwise agreement reported, never promised across hardware) and from the measured noise scales of the quantities,
and state per rule why it is right independent of this run. If a principled rule still leaves a mismatch, that
mismatch stands and A45 fails. Say explicitly which of the 21 your rules would and would not pass, and why — after
fixing the rules, not before.

## Facts (from the verdict, G1; verify against the code)

- The comparator: `src/process_runtime/run/compare.py` (reads `K04-numerical-policy-v1` from
  `benchmarks/k04/reference_values.yaml`; still labels its message "interim", line ≈ 365).
- It compares `certificate_id` for value; that id is a prefix of the float-state digest — comparing it is what ADR 0007
  D1 forbids. It became non-empty-compared after the D2 fix (revision certificates gained `plan_id`). It is the only
  difference in 12 of the 21 mismatches.
- Stricter than ADR 0007 D2.2 in three places: `u_diag_min_abs` gets no floor; certificate limitation values get a zero
  absolute floor; solution variables have no registered floor at all.
- The pivot diagnostic `u_diag_min_abs` differs 39 % (k05 high-recycle: 0.0448 vs 0.0732) and 8.5 % (NET03) — against
  D2.1's measured premise of 2.2e-14 relative.
- Round-off-scale heat duties differ in sign at ~1e-15 W (`U-FLASH.Q` 1.6e-16 vs −4.5e-15; `U-FL2.Q` −3.97e-11 vs
  1.11e-11) under a 0 absolute floor; certificate `limitations[].value` differ ~1e-7 relative; derived fields
  (`level_constants_sha256`, event messages that embed floats) differ as a consequence.
- Under ADR 0007 D2 as written, at least five bundles mismatch (pivot diagnostic; event messages that D1 classes as
  exact-match differ in three bundles).
- x86-64 fresh replay: 52/52 exact.

## Decide

1. D1 classes for every bundle field the comparator touches, including ids/hashes derived from floats
   (`certificate_id`, `level_constants_sha256`) and free-text event messages that embed floats.
2. Floors and relative tolerances for each float class, from a stated noise model (conditioning × ε, or measured
   scales on a registered set chosen *before* looking at which bundles fail — e.g. the x86 vs aarch64 differences of the
   T06/T07 committed runs, if such data exist; say which).
3. Whether pivot/rank diagnostics (`u_diag_min_abs`) are comparable across architectures at all (LU pivoting can
   legitimately differ); if not, what is compared instead (e.g. the regularity verdict).
4. The A45 row as amended; which tests the build lane writes (a mutation that would show the comparator still catches a
   real difference — e.g. a changed state beyond tolerance, a changed verdict, a changed exact field).
5. Whether ADR 0007 needs an amendment (D2.1's premise).

## Deliverable

`docs/adr/0025-<name>.md` (Proposed), the amendment text for the release spec (A45 row) and ADR 0007 if needed, register
entry text from **R-146**, and a short work order. Do not commit; no production code.

## Out of scope

Everything else in T08; same-class replay rules (unchanged); the K04 tolerance table for registered comparisons.
