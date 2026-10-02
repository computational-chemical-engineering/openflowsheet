# Brief — T08 review 3: the lock-search confinement (R3-W3) and ADR 0025's comparator, replay and recording

**To:** `reviewer` (design lane). **From:** build lane. **Branch:** `wp/T08` at HEAD.
**Deliverable:** `docs/reviews/T08-review-3.md`, findings ranked M (must fix before the new RC) / S / N with file:line,
failure scenario and smallest fix. Write no production code; do not commit; never set `reviewed`.
**Budget.** Frank is near his weekly usage limit — one pass; concentrate on §2.

## 1. Built against

- Release spec Amendment R3 item 5 (T08.A19, L41) → `39d3694` (+ `8093d03`): `_checkout_lock` in
  `src/process_runtime/run/manifest.py`; tests `tests/test_t08_r3_a19_lock_lookup.py`; `t08_rc.py lock-check`.
- `docs/adr/0025-cross-platform-replay-comparison.md` (Proposed) **with "Frank's answer to Q4"** (old records compared
  under the policy they record; unknown ids refused) and ADR 0007 Amendment 1 → commits `d6721fc`…`7133bdc` (W1–W7),
  the merged `056f850` (W3b: recording v2 from one source; fixtures), `4395df4` (W8), and the re-registration commit(s)
  after them (Frank approved the substitution-only identity move, R-148). History: `docs/T08_DECISIONS.md`
  (2026-10-01/02 entries).

## 2. Look hardest here

1. **The v2 comparator** (`src/process_runtime/run/compare.py`): does every §5 row do what it says; can any real
   difference (state beyond its floor, a verdict, an exact field, a structural field) pass under v2; is v1's path truly
   bit-identical (the 2250-comparison corpus claim); is `variable_kinds` sourced from the compiled problem and a missing
   map a difference (never a default)?
2. **Replay under the recorded policy** (`run/replay.py`): the engineer's `_as_recorded` reads the fresh certificate's
   `numerical_policy_id` as the archive's when the fresh one names `CURRENT_POLICY_ID` — so a v1 bundle's rerun (which
   records v2) is not reported MISMATCH on that one field. Is that correct and narrowly scoped, or can it hide a real
   difference?
3. **Recording** (`run/session.py`, `revision_run.py`, `verify/certificate.py`): one source of the id; the schema
   `const`→`enum`; the identity re-registration is substitution-only (tests reproduce the old values with v1).
4. **The lock-search confinement** (`_checkout_lock`): can an installed package still pick up a foreign lock; can the
   checkout case miss its own lock; is replay identity unchanged for every committed bundle (the engineer measured 246
   committed lock hashes unchanged).
5. **A14's controls** in `scripts/t08_rc.py` (C1 heat duty ×10 tolerance → MISMATCH, C2 status → MISMATCH, C3 pivot
   ×0.6 → MATCH): do they test what they claim on both runners?

## 3. Not in scope

Style; the rest of T08; re-deriving ADR 0025's rules (judge the implementation against them).

## Addendum — three small rulings (give exact text)

1. Release spec §3.2 (`docs/derivations/T08-release-spec.md:69-70`), `benchmarks/t08/reference_values.yaml:113-118`
   and `docs/derivations/scripts/t08_reference.py:86-92` still name minus-`t07` `9a7b4e6d…` and structural `915c97e8…`
   as values the RC must reproduce; under R-148 (Frank) the RC expects `29246e05…` / `e62a59a6…` (whole `28dd8bf7…`,
   t07 `a96f17ed…`). Write the amendment text (and say what the generator should check).
2. ADR 0025 §11 says nothing registered moves; R-148 shows the K05 keys move (structural hash covers
   `numerical_policy_id`). Write the correction text.
3. G3 (`5aeac9d`): the gate script accepts a §8.2 step as passed only if a row says PASS or success and none says
   FAIL/FAILED/failure/not measured; lower-case prose does not count; step 11 not required. Confirm or correct.
