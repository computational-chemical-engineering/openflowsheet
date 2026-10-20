# M07 review — the journey (WO-1, WO-2, WO-2b, WO-4)

**Reviewer:** design lane (`reviewer`), one pass, as spec §13 requires. **Date:** 2026-10-17.

**Reviewed:** `wp/M07` @ `e443b4a`, which holds the code at `d8ae8c1` and the journey record at
J = `1623633db5afd6a55e2807f848ad4cf6a84e71b3`.

**Read against:** `docs/derivations/M07-spec.md` §4, §5, §6, §11, §13 and §18 (Amendment 1, R-420…R-427), and ADR 0041.

**Rulings:** spec §19 (Amendment 2, R-452…R-455).

**Not run:** I re-ran no build, test or replay. The gate counts, the replay result and the run times are the session's
reports. The numbers below I read or recomputed from the committed files.

## Verdict: fix first

The rules, the budget re-derivation, the experiment attribution, the R3 input conditions, the T* re-solve and the
replay design are sound, and the record's labels follow the spec as written. Two things stop the record from being W25
evidence:
- the headline decision is labelled `INTERIOR`, because of Ipopt's barrier offset (MF1);
- the carry rule leaves out the files that compute R3 (MF2).

Both fixes change the registration, so the journey is re-taken once at J′ (spec A2.6). That costs about an hour of
compute and no new measurement design. The should-fix items fold into the same re-take.

## Must fix

**MF1 — The refined decision at the lower bound is reported as `INTERIOR`, and without the bound phrase.**
`docs/derivations/scripts/m07_reference.py:44` and `:284-292`; `scripts/m07_journey.py:238-247` (reads
`decision.bound_tol_scaled`).
- *What the record shows:* T* = 653.15 + 3.516e-5 K, which is 1.758e-6 scaled, so the 10⁻⁶ test gives `INTERIOR`. The
  report's first line reads "`refined`, bound activity INTERIOR", and the bound phrase appears for R1 only.
- *Why the label is wrong:* the parent's J falls monotonically away from 653.15 K, J(T*) − J(653.15) = −8.17e-9 against
  ε = 3.71e-6, and M05's P5 poll clipped its minus point to the bound. This is exactly the offset M05's review measured
  (REAL 1.76e-6) and ruled the 10⁻⁶ distance cannot classify (R-430).
- *Consequence:* W25 (c) passes on the letter while the report omits the one limit statement that applies to its
  headline decision.
- *Fix (R-452, generator delta G5):* the tolerance becomes δ_T, giving new fixtures and b-08 at the REAL offset. The
  script follows the registration unchanged.

**MF2 — `carry.journey_files` omits M05's REAL configuration and the journey's own script.** The registered list is in
the generator at `m07_reference.py:103-110`; the carry is applied at `scripts/m07_journey.py:744-769`.
- *What is missing:* the REAL start, σ, `trf_config_v1` and basis policy live in `scripts/m05_wo9_real.py` and
  `scripts/m05_wo8_runs.py`, which import from `tests/support/`.
- *Failure scenario:* one of those files changes after M05's run commit while `src/**` stays byte-equal. R3 then
  carries a record that the code at J would not produce. RC step 15 would likewise carry the journey across a change to
  `scripts/m07_journey.py` or to the registration.
- *Today's record is unaffected:* none of these files changed in `cdacc32..1623633`, and R3 was re-run anyway.
- *Fix (R-453, G6):* split the set into `carry.r3_files` and `carry.journey_files`, and add GC-CARRY-1 to keep the
  import closure complete.

## Should fix

**SF1 — Nothing replays the journey-produced M05 re-run record** (`scripts/m07_journey.py:2133-2157`).
- *The gap:* `replay` reads T*, e* and the statuses from `<J>/m05/…json`. Only J* is re-derived, through the T*
  re-solve, and M05's G10 covers only M05's committed records.
- *Failure scenario:* a damaged or hand-edited re-run record whose e* or status differs, but whose sha256 is the one
  the journey recorded, would pass `replay`. Today the sha256 is the only protection.
- *Fix (R-455):* replay the re-run with M05's REAL replay, adding a `stem` keyword on `m05_wo9_real.compare`.

**SF2 — A re-run record loses its provenance** (`scripts/m07_journey.py:899-906`).
- *The gap:* after a re-run the record says only `carried_from: "rerun"`. The offered M05 record (path and sha256), its
  anchor `cdacc32` and the reason it was not carried appear only in the build log.
- *Fix (R-454):* add `m05_record.offered`.

**SF3 — Default-gate test gap: R3's numbers against the M05 record** (`tests/test_m07_journey_record.py`, A21).
- *What is checked now:* statuses, T and `cold_used`. J*, e*, `half_width`, `check_id`, the coupling digest and
  `store_hits` are tied to the M05 record only by the opt-in replay. `check` is record-only.
- *Fix:* assert that `m07._r3_document(path, m05, chosen, carried_from, wall)` equals the record's R3 member, excluding
  `t_star_resolve` and `candidate.constraints`. It is cheap, pure-file and default-gate.

## Rulings on the open questions

**1. The label disagreement (J29 c)** is ruled in A2.1, R-452.
- Reporting both labels as the rules give them was a faithful reading of §4.4.6.
- The tolerance itself was wrong for an interior-point TRF result.
- Neither label is derived from the other. Each decision is labelled at δ_T, which is the resolution the journey already
  uses for `FE_UNCHANGED`.
- M05's G9 two-clause criterion was rejected: it reads M05's poll structure, and a label that gates nothing needs only
  one constant.

**2. The re-run's refusal code and condition 5 (J22)** are ruled in A2.3, R-454.
- `R3:carry_identity_differs` is ratified.
- Condition 5 for a re-run record is judged on the committed record; A21 and `replay` already do this.
- `offered` is added.

**3. The reactor check (J25)** needs no M07 spec change (A2.5).
- The journey's filter (`scripts/m07_journey.py:647`) is what R-259 prescribes.
- `env.verify` itself contradicts R-259 (`src/openflowsheet/adapters/pymrm/env.py:347`). That is an M02 follow-up, and
  the filter goes once it is fixed.
- The `PYTHONPATH` leak is confined to the verify probe; the experiment child runs `-I` (`launcher.py:223`). It causes a
  false refusal, never a wrong number.

**4. What `replay` takes from the record (J27)** meets "every number" in §6.4 (A2.4, R-455).
- Walls and coupling digests are not functions of the stored inputs.
- The experiment split is taken only after the served total matches, and A25 pins the split by kind.
- R3's carry label is not a number.
- The list is now normative, and SF1 closes the one real gap.

**5. Per-commit gating (J24, J30)** is noted and accepted. WO-4b gated every commit.

## What the tests do not verify

- **A23's bound-activity test** compares the script with the reference generator, but both read the same constant. It
  passes whatever the tolerance is. The semantics are pinned only by A07's fixtures, and b-08 (G5) adds the case that
  mattered.
- **The R3 path of `replay` and the T* re-solve replay run only opt-in.** The default-gate dry run has R3
  `UNSUPPORTED`. SF3 covers the pure-file part.
- **The grid extras' store hits are not in `experiments`.** A1.4 counts the loop solve's coupling record only, so R1
  reports `store_hit` 0 at every point even though each point's `C1Parent.solve` was served from the store. An uncounted
  cold would still be caught by A25's archive count; I checked that the archive holds 58 executions, which is
  18 + 36 + 4. Note only.
- **`parent_checks.R3.run_sha256` names M05's targeted check**, while R3's constraint values come from the journey's
  re-solve. The two are tied by bitwise equality of the objective only, as R-426 allows. The re-solve's own coupling
  digest is not recorded. Note only.
- **Grid points' `coupling_sha256` cannot be checked afterwards.** It names artefacts under the ignored `--artifacts`
  directory, so a third party cannot verify it. It is provenance only.

## Checked and sound

- **The rule functions against §4.4.1–4.4.7, A1.1 and A1.8:** precedence, inclusive boundaries, tie-breaking, and a null
  noise floor never read as 0.
- **The budget stop and `check`'s re-derivation (A1.2), and the attribution and `extrapolated` counting (A1.4, A1.5).**
- **Conditions 1–5, including condition 4's revision identity, and the carry mechanics** (`git diff anchor HEAD` with
  `status`).
- **The record's numbers, recomputed by hand:**
  - P01 is `FE_CHANGED`: Δj = 3.17e-3 against ε = 4.6e-6.
  - P13 is `FE_UNCHANGED`: |Δt| = 3.5e-5 K.
  - TC-1 holds.
  - The journey wall is the sum of the rung walls plus the re-solve's.
  - The reactor cold count is 88 = 36 + 48 + 4.
- **The R3 re-run at J equals M05's committed REAL record bit for bit**, except walls, coupling digests and
  `provenance`. That makes it cross-commit evidence of determinism; it belongs in the build log with its command.
- **The replay design:** a record-only backend for every unit, comparison of the whole record by JSON text, and refusal
  on a thread mismatch or a missing archive.

## Not examined

- `render` and `check_report` prose beyond the headline lines.
- R2's reader beyond its outcome.
- M05's internals (reviewed in M05 §21).
- Packaging and CI.
- WO-3 and WO-5…WO-8.
- The 0.2.0a1 alpha.
