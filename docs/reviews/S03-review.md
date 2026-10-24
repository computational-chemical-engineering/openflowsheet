# S03: independent review (design lane, `reviewer`), 2026-10-25

**Scope.** Branch `wp/S03`, range `main...wp/S03`, head `3724c0a5`. Brief: `docs/briefs/S03-review.md`. Spec:
`docs/derivations/S03-spec.md` §0–§18.

**Read.**
- The production diff: `cascade.py` (`property_method_refusal`, S11 in `validate`) and `column.py` (S11 in `validate`).
- `solve_column` and `solve_cascade` up to their `validate` call.
- The classifier, `scripts/s03_reference_comparison.py`, in full.
- These tests: `tests/test_s03_s11_refusal.py`, and A03, A08–A12 and the A12 synthetic test in `tests/test_s03_references.py`.
- These build decisions: B2b-1 to B2b-6 and B4-2 to B4-11 in `docs/S03_BUILD_DECISIONS.md`.
- The verdict's §7 and §8.

**Ran.**
- `pytest tests/test_s03_s11_refusal.py tests/test_s03_references.py tests/test_s03_ours.py` gives 305 passed in 196 s on x86-64, which is locally bit-identical.
- Two scratch probes (not committed), each built on the classifier's own functions:
  - (a) Our values were moved by at most 2.3e-16 relative, 1e-14 and 1e-13, and the full document was compared at A10's
    1e-12 rule, with every failure collected.
  - (b) Every non-selected IDAES position at the selected level was recomputed through rules 2–2d, with its distance to
    the selected answer.

## Verdict

**Sound, with one must-fix and two should-fix items.** The must-fix is the A10 test, together with its spec text.

- **S11.** It is placed correctly and guarantees zero evaluations.
- **The classifier.**
  - It implements §7.1, §17.3 (with §18.3), §17.5 and §18.4 faithfully.
  - It recomputes every rule value from raw fields, in a fixed 50-digit decimal context.
  - The only floating-point operations are single, correctly rounded ones, so the committed-input document is
    byte-identical across architectures. This is confirmed by CI, which fails only the live-solve part.
- **The tests** pin what they claim, apart from the items below.

Counts: must-fix 1, should-fix 2, notes 5.

## Findings

**F1 — must fix. A10's live-solve test is ill-posed, and CI's failure understates the problem.**
`tests/test_s03_references.py:537-563`; spec §8's last bullet and §11 A10.
- *Mechanism.* `assert_same` applies 1e-12 relative to every float, including two kinds of value:
  - `ratio = |ours − tool| / tol`. On RC2's family, DWSIM and ours differ by about 1e-14 mol/s.
  - `Δy = y_pert − y_base`, the response table.

  Both are differences of nearly equal numbers, with condition numbers above 1e12 with respect to our values.
- *Probe (a).* At ≤ 2.3e-16 relative, about one unit in the last place:
  - 932 floats fail;
  - three rule 4 `reason` strings change (they print the worst ratio with `.4g`);
  - at 1e-13 relative, `worst_quantity` changes too.

  No classification changes.
- *Why CI showed only the response table.* `assert_same` stops at its first failure, and in the sorted document
  `perturbation_response` comes before `rows`. CI therefore never compared the rows. A fix limited to the response table
  would fail next on `rows[*].ratio`.
- *Correction.* Apply §19.1, which is the engineer's proposal made precise:
  - (i) byte identity of the document recomputed from the committed files (the existing test);
  - (ii) on the live solve, exact equality of `classification`, `category`, `rule`, `label`, `within_tolerance`,
    `quantities_outside`, the `controls` block, `comparison_stopped`, and `x31`'s classes, rows, outcomes and clause;
  - our values stay pinned at 1e-12 relative by A07.

  In code: replace `assert_same` with a projection onto those keys, compared with `==`.

**F2 — should fix. Rule 2c checks IDAES's `stage_map` only for distinct units.**
`scripts/s03_reference_comparison.py:519-524` (and `:286-289`, where the intermediate duties are selected by `kind == "tray"`).
- *What is missing.* §7.1 rule 2c and §5.1 row 3 require the map to agree with the case. That means stage 1 is the
  condenser unit exactly when there is a condenser, stage N is the reboiler exactly when there is a reboiler, and the rest
  are trays in order.
- *Scenario.* A harness that orders the trays wrongly, or labels a tray `condenser`, passes 2c. In the second case that
  tray's duty also escapes the intermediate-duty check.
- *Consequence.* The values would then `DISAGREE`, by about 1e6 tolerances for an off-by-one (E1). That is a false
  finding for the design lane, not a false `AGREE`. Every current record conforms.
- *Minimal fix.* Assert the `kind` sequence per case, and tray order by unit index.

**F3 — should fix. `path_positions` silently skips a position without raw fields.**
`scripts/s03_reference_comparison.py:593-601`.
- *Scenario.* A position whose summary says "Optimal Solution Found" but which has no `full.raw` drops out of §18.4's
  path-dependence comparison without notice.
- *Minimal fix.* Raise, or let rule 2d fire with `path_dependence(not recomputable)`.
- Probe (b) found raw fields on every position of all 16 available IDAES records, so nothing changes today.

**N1 — note: the brief's §5 first question. P1 changes the termination, not the root.** Probe (b) measured the distance
from P0's own final iterate to the selected P1 answer, in tolerances:

| Case | P0's termination | Distance to P1 |
| --- | --- | --- |
| RC5 | acceptable | 0.0278 |
| RC3 | acceptable | 0.0216 |
| RC3-z | acceptable | 3.0e-3 |
| RC3-Q | acceptable | 8.9e-4 |
| RC2-RR | acceptable | 1.7e-4 |
| RC6 | "Optimal" (it failed only its rerun) | 1.8e-6 |

- Where all three positions end "Optimal", they agree to ≤ 1.2e-5.
- PC-LI's P1, which was not selected, hit 500 iterations and stopped about 1e5 tolerances away. P1 does not always help,
  but it was never selected where it did not.
- For every skipped IDAES position, the classifier's recomputation reproduces the script's failed rule.

**N2 — note: the brief's §5 second question. DWSIM's RC1-family `AGREE`s are meaningful at the registered resolution.**
- DWSIM's distance to the twin is 0.0326 (RC1), 0.0380 (RC1-RR) and 0.0180 (RC1-z), all on `top[B]`. Ours is ≤ 1.7e-6.
  The `AGREE` therefore measures DWSIM's own Wang–Henke error, about 25 times inside a tolerance.
- PC-L's tool-model distance, 0.0326, is the same number on the same configuration.
- The 0.071–0.093 reruns describe the 1e-7 rung, not the selected 1e-8 rung. The margin to rule 2d is a fact about DWSIM's
  floor, and verdict §8 item 4 already carries it.

**N3 — note: A08's ladder conformance trusts each skipped attempt's `passes` flag.**
`tests/test_s03_references.py:428-493`. Probe (b) confirms the flags for IDAES. DWSIM's skipped attempts are not
recomputed. Folding probe (b) into A08 would make "checked, not assumed" (§17.8) literal for IDAES. Optional.

**N4 — note: A03 is a static tripwire.**
- *What it catches.* Accidental imports, path strings and data-file names at HEAD and at the qualification commits.
  B4-10's mechanics are sound for that purpose.
- *What it cannot show.* Which code ran. The records carry no hash of the tool script or its imports, so the link from a
  record to its script is the commit alone, and blindness stays procedural (verdict §8 item 8).
- *For S09.* Record the SHA-256 of the running script and of its in-repository imports in every record, and check it
  against the qualification commit.
- The helper scripts `s03_dwsim_topup_merge.py` and `s03_idaes_p0_reproduction.py` contain none of the seven strings.

**N5 — note: S11 is sound.**
- *Placement.*
  - S11 precedes R1 in both `validate` functions (`cascade.py:495-497`, `column.py:630-632`).
  - `solve_column` and `solve_cascade` call `validate` before any provider use.
  - `column_warnings` reads only the specification.
- *The tests.*
  - The counting wrapper exposes only `describe`, `evaluate_phase` and `flash`, so any other provider call would raise.
  - Disabling S11 fails 13 of the 15 tests.
- *Not guarded.* The lower-level public functions (`compile_column`, `solve_target`, `declared_rows`, `profile_initial`).
  That is within §9's scope, and nothing outside `models/syn001` calls them.
- *Cosmetic.* `compute(ours=live)` still lists the committed `ours-*.json` hashes under `inputs_sha256`.

## Rulings (normative text in spec §19, register R-644)

1. **A10.** The exact replacement text is spec §19.1, for both §8's last bullet and §11's A10 row. The test changes as F1
   says.
2. **E501 in the tool scripts: option (a).** At HEAD the scripts are byte-identical to `2eb71ac0` (IDAES) and `5474531f`
   (DWSIM), and that identity is worth more than line length (§19.5). The text for `pyproject.toml` comes in two parts:
   - In the existing comment, replace "No other check is relaxed anywhere." with "Apart from the S03 tool scripts' E501
     waiver below, no other check is relaxed anywhere."
   - Add these lines under `[tool.ruff.lint.per-file-ignores]`:
     ```
     # The S03 tool scripts are the provenance of the committed tool records. They stay byte-identical to
     # their qualification commits (2eb71ac0, 5474531f), which A03 scans, so long lines are waived, not
     # rewrapped (S03 §19.5, R-644). An edit to either script means a new qualification run.
     "spikes/references/s03_qualify_idaes.py" = ["E501"]
     "spikes/references/s03_qualify_dwsim.py" = ["E501"]
     ```
3. **B2b-1 stands.** "Ipopt rejects" means the solver (§19.3). The options are recorded per position, the options file
   validates the value, and P0 reproduced 20 of 20, so P0 was not contaminated.
4. **The classifier choices.**
   - **B4-4 stands** and becomes normative (§19.4). Rules 0, 1 and 3 keep their labels, so §17.5's precedence holds. It
     changes nothing on these records.
   - **B4-9 stands** (§19.2).
   - **B4-10 stands** as a tripwire, with N4's limit.
5. **§17.8 condition 2.** The erratum is spec §19.2. It also corrects §18.5's "`tool_settings.DWSIM` is unchanged": that
   holds since `5474531f`, while since `95870140` the setting changed by the addition `column_method_order_amendment_1`.
   I verified this at all four qualification commits.
6. **General review.** See the verdict above and F2, F3 and N1–N5.

## Not examined

- The tool scripts' internals beyond A03's scan and the recorded options.
- DWSIM's attempt records, which have no raw fields to recompute.
- `scripts/s03_evidence_manifest.py`.
- `scripts/s03_references_ours.py`, apart from A07's tolerance.
- The generator, `s03_reference.py`, and the tolerances' derivation (excluded by the brief).
- A13 and A14 in detail.
- The harvest items (M07a, T08 A21).
