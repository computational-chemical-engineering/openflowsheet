# T08 review 3 — the lock-search confinement (R3-W3) and ADR 0025's comparator, replay and recording

**Reviewer:** design lane (`reviewer`), 2026-10-02. **Branch:** `wp/T08` at `8ff4c97`. **Brief:**
`docs/briefs/T08-review-3.md` (with its addendum). **Built against:** ADR 0025 (Proposed) with "Frank's answer to
Q4" (R-147); R-148; release spec Amendment R3 5 and R4; `docs/T08_DECISIONS.md`, 2026-10-01/02 entries.

**What I ran** (ref-x86-64, `.venv`):

- `pytest tests/test_t08_adr0025.py tests/test_t08_r3_a19_lock_lookup.py tests/test_k05_replay.py
  tests/test_t08_w4_v0_1_gate.py`: 117 passed.
- The R-148 substitution proofs (`test_t07_identity.py`, `test_t08_w1_identity_substitution.py`,
  `-k "minus_t07 or r148 or registered_one"`): 6 passed.
- `scripts/t08_numerical_policy.py --check`: exit 0.
- Five probes, scripts in the session scratchpad:
  1. **v1 frozen.** A differential fuzz of `differences(..., policy_id=v1)` against `814e151`'s own
     `compare.py`, loaded as a module. The inputs were the 52 RC bundles' documents under random mutations: floats
     moved, nulled or retyped, strings edited, keys added or dropped, lists resized, and two path labels. Result:
     **5000/5000 identical**, exceptions included.
  2. **v1 records replay under v1.** `reproduce_bundle(rerun=True)` with this build, which records v2, on all 52
     `814e151` RC bundles (v1 records): **52/52 `MATCH`**, `compatible_reproduction`, `bitwise_floats` true.
  3. **The v2 path end to end.** The same 52 bundles re-sealed to name v2, then reproduced: **52/52 `MATCH`**,
     bitwise. The kinds came from `declared_kinds(route.binding.spec)`.
  4. **Kind coverage.** Over the 44 solution states of the set, every variable has a declared kind: 1627/1627
     (molar_flow 1069, temperature 243, pressure 243, heat_rate 72).
  5. **v2 edge cases and the gate's result-cell classifier.** Both are quoted below.

**Not examined:** aarch64 behaviour, since I had no runner; §7's counterfactual rests on A12(b)'s transcribed F2
pairs. Also not examined: A2's K04 A32 parameterization, the W1 generator's internals beyond `--check`, W8's envelope
text, `docs/interfaces-frozen.md`, the full suite, and the CI workflow.

## Verdict

**The code is sound. One must-fix, and it is documentation.**

- **The v2 comparator.** It implements §5's fifteen rows as written. I found no path by which a real difference
  passes: not a state beyond its floor, a verdict, an R0 leaf, a key set or a list length. Every edge case I found
  errs toward a false `MISMATCH`.
- **The v1 path** is bit-identical to `814e151`. I measured this independently of the engineer's corpus.
- **`_as_recorded`** is correct and narrowly scoped (§B.2).
- **The lock confinement** is sound.
- **Recording** has one source.
- **R-148** is substitution-only, and its proofs pass.
- **The must-fix (M1).** The release spec still tells the RC to reproduce identity values that R-148 retired, and the
  RC script checks the new ones. Fix that text before `C` is cut. Ruling 1 gives the text.

## A. Findings

### Must fix (before the new RC)

- **M1. The release spec and the RC script disagree on what T08.A42 must reproduce.**
  - **Where the v1 values remain.** `docs/derivations/T08-release-spec.md:69-70` (§3.2) and `:76`, and its
    generator's `benchmarks/t08/reference_values.yaml:113-118` and `docs/derivations/scripts/t08_reference.py:86-92`.
    All of them still register minus-`t07` `9a7b4e6d…` and structural `915c97e8…` as values "the release candidate
    must reproduce".
  - **Where the v2 values are.** `scripts/t08_rc.py:76,79` checks `29246e05…` and `a96f17ed…` (R-148).
  - **Failure scenario.** At the next `C`, the RC job reports A42 PASS. The verdict lane, reading §3.2 (the
    execution authority), finds that `9a7b4e6d…` was not reproduced. It must then either FAIL A42 or overrule the
    spec on the register's say-so.
  - **A second problem.** `e62a59a6…` is not in the source that §3.2 names for the structural hash, the T07 evidence
    manifest. The generator's `digest in text` check therefore cannot register it as written.
  - **Smallest fix:** Ruling 1 (Amendment R5 1), then regenerate the reference values.

### Should fix

- **S1. The v0.1 gate reads some failed RC rows as passed.** `scripts/v0_1_gate.py:105-106, 279-285`.
  - **The current rule.** A cell passes if it contains `PASS` or `success` anywhere and none of
    `FAIL|FAILED|failure|not measured`.
  - **Probes**, all of which return `passed`:
    - `success / cancelled (…)`
    - `success / startup_failure`: `\bfailure` does not match after `_`.
    - `success / skipped`
    - `Not measured (job success; …)`: capital N.
    - `PASS (3/4): FAILS on aarch64`
    - `PASS: Failed to upload`
  - **Why it matters.** Step 1's two-runner form, `success / success`, makes `success / cancelled` the natural
    transcription of a cancelled aarch64 job.
  - **Severity.** This guards the tag proposal, not the RC itself, so it is S. Ruling 3 gives the corrected rule.

- **S2. Two texts still say v1 records are refused, and §11 says nothing registered moves.** Both statements are
  false since R-147 and R-148.
  - **The ADR.** ADR 0025 §11 (`:327-329`) and the §15 R-146 text (`:362, :379`) carry this. R-146 is to be
    *entered* at W9 from this text.
  - **The release spec.** Amendment R4 1 (`T08-release-spec.md:825`) says a bundle naming another id "is refused at
    replay (… D1.3)".
  - **Failure scenario.** The register entry and the spec describe a mechanism the code does not have. A v1 bundle
    in the RC set is compared under v1 and can `MATCH`. It fails A45 only because of the RC script's separate
    `a45.every_bundle_records_the_current_policy` check, which is correct (`t08_rc.py:836-845`).
  - **Smallest fix:** Ruling 2's text.

### Notes

- **N1. Kind-less variables, and two rows anchored to `<root>`.** Both are strict-direction only.
  - **Variables with no declared kind.** `compare.py:574` compares such a variable relative-only, with a visible
    label ("no declared kind…"). It is not reported as a difference. Coverage is complete today (probe 4), so this
    is latent. If a future route's state outgrows its spec, the symptom would be near-zero `MISMATCH`es on aarch64,
    filed under numerics. Smallest fix: report "`<id>`: no declared kind" as its own difference, in the spirit of
    D5's "never falls back to a default".
  - **Rows 11 and 12 under a path label.** Both rows key on `path == ""` and `\A<root>` (`:611`, `:475`). A caller
    that passes a path label silently loses the kind floors and the "kinds not supplied" difference. Today the only
    caller with a label is A44's v1 comparison.
- **N2. A digest-form certificate id accepts an empty target.** In `_certificate_id` (`compare.py:531-534`),
  emitted `target_state_sha256 = ""` with `certificate_id = "cert-"` passes against a digest-form committed id
  (probe). This is not reachable without a broken writer, and a non-converged rerun differs in status anyway.
  Smallest fix: require the emitted target to match `_HEX64` before forming `expected`.
- **N3. A literal `<f>` in a message crashes the comparison.** `_text` (`compare.py:549`): emitted `"<f>"` against
  committed `"1.0"` gives equal templates and token counts 0 and 1, so `zip(strict=True)` raises `ValueError`
  instead of reporting a difference. This is contrived. Smallest fix: compare the token counts first.
- **N4. Rows 3 and 4 check only the emitted side's kind.** An archived `u_diag_min_abs` of NaN, or a malformed
  archived digest, passes. The rerun's kind is the claim that matters, so this is acceptable. Row 4 has the same
  shape as v1.
- **N5. `exact_fields` is carried in v2's data and enforced by neither comparator** (`numerical_policy_v2.yaml`
  `exact_fields`; there is no §5 row for it). `alpha`, `scales`, `bounds` and `tolerance` are compared at 1e-9
  relative, not exactly. This is pre-existing in v1, and §5 has no such row, so the implementation matches the ADR.
  **Needs a decision (design lane):** v2 is about to be registered at the next `C`, after which any change needs a
  v3. **I would annotate the key as inert in v2** (a comment in the generator's output) rather than add an
  exactness row that has not been measured across platforms.
- **N6. A14: C3 and C2 need small strengthenings.**
  - **C3** passes on `MATCH` alone (`t08_rc.py:750`). A regression that stopped reading `solve-events.json` would
    still pass it. Smallest fix: also require `report.bitwise_floats is False`, which proves the mutated value was
    read and forgiven.
  - **C2's preconditions** are `assert`s (`:705-706`), which `python -O` strips. Smallest fix: raise instead.
  - **Otherwise both controls test what they claim** on either runner. C1 bounds the heat-rate floor from above
    (10× its v2 tolerance → `MISMATCH`, named). C2 is a non-forgiven verdict flip. C3 is D4's blind spot. Integrity
    is asserted first.
- **N7. Two stale texts.**
  - `application/types.py:1281`: "The comparison policy is always `run.compare.POLICY_ID`". It is now the policy
    the record names.
  - `tests/test_t08_adr0025.py:564-565`: "this build's recording switch is held". The switch is merged, so the
    reseal is now a no-op.
- **N8. A layering note.** `verify/certificate.py` now imports `run.compare`, which loads two policy YAMLs at
  import. ADR 0025 D1.2 prescribed this single source, so it is acceptable. A two-line `policy_ids` module would
  avoid K04 importing K05's comparator if this ever matters.

## B. What I checked and found sound

1. **The v2 comparator** (`compare.py:423-754`). Each row was checked against §5:
   - Rows 1–2: unchanged.
   - Row 3: number, finite, ≥ 0, min ≤ max on the same `linear` object, ratio ≤ 1, null against null; `bool` is
     refused.
   - Row 4: names plus the suffix; null-matching on `level_constants_sha256`.
   - Row 5: classed by the committed id's form. The plan form is exact.
   - Rows 6–7: unchanged.
   - Row 8: exact template, tokens relative with floor 0, `message`/`cause` at any depth, strings on both sides only.
   - Row 9: `near_threshold` value floored at the committed `threshold`; `check` and `kind` exact.
   - Row 10: unchanged.
   - Row 11: kinds required. A missing map is exactly one difference. Absent variables are differences.
   - Row 12: 3.1e-8 on the four flow keys. The phase labels are exact.
   - Rows 13–15: v1's floors without `u_diag_*`.

   The labels carry the policy id, the floor and its source. `V2_*` constants are all read from the policy file. On a
   same-class rerun the path is MATCH and bitwise on all 52 (probe 3).

   **No false MATCH.** Every new forgiveness is one of the classes §5 names. State, verdicts, R0 leaves, key sets and
   list lengths remain exact or floored at registered thresholds.
2. **`replay._as_recorded`.** It fires only when all of the following hold:
   - the archive's policy is a known, non-current one;
   - both documents are objects;
   - the archived document's root `numerical_policy_id` equals the manifest's;
   - the fresh document has the field.

   It then replaces **that one root field** in a shallow copy. If the fresh document names anything but
   `CURRENT_POLICY_ID`, that is a difference (tested: `K04-numerical-policy-v3` → `MISMATCH` naming the field).

   Only the certificate carries the field among artifacts (checked on the RC set). The manifest is not compared.
   Nothing else is altered, so nothing else can be hidden. **The reading is correct**: the field names a comparison
   policy, not a result of the solve.

   Two side effects, both accepted:
   - `bitwise_floats` is true for a v1 record whose rerun differs only in that field, since it is not a float.
   - The R-148 counterfactual must patch `_as_recorded` out, because a v1-recording build would otherwise flag its
     own id.

   Also checked: the unknown-id refusal precedes mode and rerun in both `replay` and `reproduce_bundle`, and v1 is
   never handed kinds (`replay.py:234`).
3. **Recording.** There is one source, `run.compare.CURRENT_POLICY_ID`. The literal in `compare.py` is asserted
   against the policy file's `id`. `session._numerical_policy_id` feeds both manifest writers
   (`session.py:87`, `revision_run.py:585`), and the certificate default is the same constant. No other constructor
   passes an id. Both schemas use `enum [v1, v2]`, and the packaged copies agree.

   **R-148 is substitution-only.** With the id undone at its two sources, plus `_as_recorded` (`056f850`'s whole
   source diff), the minus-`t07` document, the structural hash, the `t07` key and the fixtures reproduce byte for byte.
4. **`_checkout_lock`** (`manifest.py:189`).
   - **An installed package** can resolve a lock only if `here.parents[2]` is named `src`, `parents[1]` is
     `process_runtime`, and `parents[3]` holds a `pyproject.toml` with `name = "process-runtime"`. That is a
     process-runtime checkout. `site-packages` layouts, including a `.venv` inside the checkout, give `None`.
     The cwd fallback is gone.
   - **The checkout** resolves its own lock through `.resolve()` of the module path, so a symlinked working path is
     fine. It is the same file the old parent walk found first: there is no `requirements.lock` under `src/`.
   - **Committed bundles' identity** is therefore unchanged, consistent with the 246 hashes the engineer measured.
5. **The A14 controls** re-seal with the project's writer and check integrity first. C1 moves the state digest, the
   certificate target and the digest-form id together. The checks run on both replay runners inside
   `bundles-replay`. See N6 for the two strengthenings.

## C. Rulings (addendum)

### Ruling 1 — the identity values the RC must reproduce (release spec Amendment R5 1)

Append to `docs/derivations/T08-release-spec.md`:

> ## Amendment R5 (2026-10-02) — identity values and A45's refusal text after R-147 and R-148
>
> ### R5 1 — §3.2's identity values
>
> *Decision.* ADR 0025 D1.2 makes every run manifest and certificate name `T08-numerical-policy-v2`, and
> `RunManifest.structural_sha256` covers that field. The K05 identity values therefore move by that substitution
> only (Frank, 2026-10-02, R-148). In §3.2, the rows "K05 identity document minus `t07`" and "Structural hash" are
> replaced, and one row is added:
>
> | Value | SHA-256 | Registered in |
> | --- | --- | --- |
> | K05 identity document minus `t07` (R-148) | `29246e053ad126034c1aeef0f396ffe1d9f4dffcf5128f226720280bd1b656e5` | `tests/test_t07_identity.py` (`K05_MINUS_T07_SHA256_V2`) |
> | Structural hash (R-148) | `e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238` | `tests/test_t07_identity.py` (`STRUCTURAL_SHA256_V2`) |
> | `t07` key (§6.2's D1–D3, then R-148) | `a96f17eda025168ea184584bd8f0fd2bed6d940ecf8356a6b7ee6f9663348e4b` | `tests/test_t08_w1_identity_substitution.py` (`T07_KEY_SHA256_V2`) |
>
> The values T07 registered stay the registered values *with v1 recorded*: minus `t07` `9a7b4e6d…`, structural
> `915c97e8…`, `t07` key `422aa7a5…` and whole document `7f32b143…`. `tests/t08_v2_substitution.py::record_v1`
> reproduces them byte for byte, and those tests are part of these rows' evidence.
>
> The sentence under §3.2's table becomes: "The complete identity document to reproduce is the committed
> `evidence/T07/5f3d3ea…/artifacts/k05-identity.json`, except the keys re-registered under §6.2 (including R-148).
> At `C` the whole document is `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5`; with v1 recorded
> it is `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5`."
>
> §6.2 gains a final paragraph: "ADR 0025 D1.2's recording switch is a second substitution of this kind (R-148). The
> substituted field is `numerical_policy_id`, v2 for v1, at its two sources, together with the hashes that cover it.
> The proof is `tests/t08_v2_substitution.py`." T08.A42 and §8.2 step 2 keep the words "except §6.2's
> substitutions", which now include R-148.
>
> *Rejected.* Keeping the v1 values as what `C` must reproduce: A42 would fail at every `C` that records v2.
> Deleting them: that loses the substitution's anchor.

**What the generator must check** (`docs/derivations/scripts/t08_reference.py`, `REGISTERED_DIGESTS` → the
`registered_digests` block of `benchmarks/t08/reference_values.yaml`):

- **(a)** Each new value is found in its new `registered_in` source. This is the existing `digest in text` check. The
  structural row's source must move, because `e62a59a6…` is not in the T07 evidence manifest.
- **(b)** The minus-`t07` and `t07`-key values equal `scripts/t08_rc.py`'s `K05_MINUS_T07_SHA256` and
  `T07_KEY_SHA256`, read from the script, so the spec and the RC check cannot drift again.
- **(c)** Each moved entry carries `registered_v1: {sha256, registered_in}`, and the generator finds each value in its
  source:
  - `9a7b4e6d…` in `tests/test_t07_identity.py`
  - `915c97e8…` in `evidence/T07/5f3d3ea…/manifest.json`
  - `422aa7a5…` in `tests/test_t08_w1_identity_substitution.py`
- **(d)** Both values of each pair appear in `docs/decision-register.md` under `## R-148`.

### Ruling 2 — ADR 0025 §11 (and the texts that still say "refused")

Append to `docs/adr/0025-cross-platform-replay-comparison.md`, after "Frank's answer to Q4":

> ## Correction (2026-10-02, T08 review 3) — §11 and §15 after R-147 and R-148
>
> 1. **§11's "Not expected to change" is wrong for T08.A42.** The identity document carries no `numerical_policy_id`
>    key, but it does carry K05's `structural_sha256`. `RunManifest.structural_document` covers
>    `numerical_policy_id` directly, and also through `artifact_r0_sha256`, the certificate's R0 projection. D1.2
>    therefore moves the following values:
>    - **K05 identity document:** whole `7f32b143…` → `28dd8bf7…`; minus `t07` `9a7b4e6d…` → `29246e05…`; `t07` key
>      `422aa7a5…` → `a96f17ed…`.
>    - **K05's `structural_sha256`:** `915c97e8…` → `e62a59a6…`.
>    - **The CLI's `solve`/`inspect` structural hash of SYN-001-nominal:** `af86adb8…` → `f9536122…`.
>    - **The K05 schema fixtures:** the certificate hash, `manifest_sha256` and the structural hash.
>
>    The move is a substitution only. With v1 recorded again at the id's sources, every old value is reproduced byte
>    for byte (`tests/t08_v2_substitution.py`). Frank approved it on 2026-10-02 (R-148; release spec Amendment R5).
>
>    Unchanged, as §11 said: T02's floats (`9a8a5baf…`), the keys `t02`…`t06`, `check_policy_sha256`, A49's served
>    digest and B50's digests. The check §11 cited tested whether the document has the key, not what its hashes
>    cover.
> 2. **§11's "Records made under v1 … are refused at replay (`NOT_RUN`)"** is replaced by Frank's answer to Q4.
>    Such records are re-run and compared under `K04-numerical-policy-v1`, whose path is frozen bit for bit, and
>    their recorded verdicts stand. Only a record naming a policy this build does not know is refused.
> 3. **§11's cost** becomes one identity re-registration (R-148), one new `C` and one RC job.
> 4. **§15's R-146 is entered at W9 as amended by R-147.** Its title ends "…; records are compared under the policy
>    they name, and an unknown policy is refused at replay". Its sentence "Records made under v1 are refused at
>    replay" becomes "Records made under v1 are compared under v1 (R-147)". Its rejected alternative "Re-judging the
>    `814e151` bundles under v2" and its watch item "A v1 record compared under v2" stand.

And, as R5 2 of the same release-spec amendment:

> ### R5 2 — A45's refusal text
>
> In R4 1, "a bundle recording another id is refused at replay (`inspected_archived_results` / `NOT_RUN`, ADR 0025
> D1.3), and that counts as a failure" becomes: "a bundle recording another id fails the row
> (`a45.every_bundle_records_the_current_policy`). A `K04-numerical-policy-v1` bundle is compared under v1 (R-147)
> and an unknown id is refused (`inspected_archived_results` / `NOT_RUN`); neither satisfies the row." §9's A45 row
> is unchanged.

### Ruling 3 — G3's status vocabulary: confirmed in structure, corrected in classification

**Confirmed:**

- the table is read by column;
- a step passes only with at least one passed row and no failed or unstated row;
- a bare `—` is a supporting row;
- lower-case prose (`pass`, `failed`, "none failed") is not read;
- **step 11 is not required**: it is the gate script itself, run before the verdicts, so requiring it would be
  circular.

**Corrected:** the classification of one Result cell. Replace the docstring rule at `v0_1_gate.py:28-34` and
`_rc_outcome` with:

> A row's Result cell is read by its **status head**: the text before its first `(`, `:`, `;` or `.`, with `*`,
> `` ` `` and `"` removed, split on `/` and white space. The **status words** are the record's `PASS`, `FAIL` and
> `FAILED`, and CI's conclusions `success`, `failure`, `cancelled`, `skipped`, `timed_out`, `startup_failure`,
> `action_required`, `neutral` and `stale`. `not measured` is a status word in any letter case.
>
> A row **failed** if either:
> - its head holds a status word other than `PASS` or `success`; or
> - the whole cell contains `FAIL`, `FAILED` or `failure` (case-sensitive, and `failure` also inside a longer
>   identifier such as `startup_failure`), or `not measured` in any case.
>
> A row **passed** if it did not fail, its head holds at least one status word, and every status word in its head is
> `PASS` or `success`. Where the head is followed by a count `(k/n`, k must equal n, else the row is not stated as
> passed. A bare `—` is a supporting row. Anything else is not stated as passed.

**Checked against the `814e151` record's table, the rule gives:**

- **Every row that passes today still passes:**
  - `success / success (…)`
  - `PASS (4/4; … NOT_RUN)`: the body is not read for status words.
  - `PASS (12/12: …; none failed/missing/skipped)`
  - `"A30 PASS" (exit 0)`
  - `PASS: 72 certificates audited`
  - the future A45 row `PASS (…): … C1 MISMATCH, C2 MISMATCH, C3 MATCH`
- **The three rows the engineer reported as unstated stay unstated.**
- **`**FAIL** (3/4)` fails.**
- **The probes of S1 now fail or are unstated:** `success / cancelled`, `success / startup_failure`,
  `Not measured (job success…)`, `PASS (3/4): …`.

Add one test per new word, and one for the count rule.

## D. Counts

M 1 · S 2 · N 8. **A new RC may be cut once M1 (Ruling 1's R5 1 and the regenerated reference values) has landed.**
S1 must land before the gate is relied on for a tag proposal. S2 should land with M1, since it is the same amendment
and the ADR correction. The Ns can follow.
