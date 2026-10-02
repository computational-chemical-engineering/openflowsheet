# Brief — verdict: V13 (e), compatible warm starts (T08.A71 on B40–B51)

**To:** `verdict` (design lane). **From:** build lane. **Branch:** `wp/T08` at HEAD.
**Deliverable:** `docs/reviews/T08-verdict-V13e.md`: each of B40–B50 MET / NOT MET / INSUFFICIENT EVIDENCE / BLOCKED
with reasoning, then B51 = V13 (e) overall (T08.A71), and what the verdict does not establish. Do not commit; write
no code. Budget: the user is near a weekly usage limit — judge from the tests and their numbers; run the W4 test file
once, not the whole suite.

## Criterion (registered)

`docs/derivations/T08-release-spec.md` §4.3 clause (e) and T08.A71:
> FAIL unless a test shows a solve opening from a compatible warm start, the trace recording its source, the opening
> checks applied, and an incompatible one rejected to the next source, on B40–B51.

`docs/derivations/T08-build-first-spec.md` Part B (§B1–§B5; §B5 lists what judges A71 and the registered states),
assertion rows T08.B40–B50 as replaced by **§Am1.C** (B41, B42, B46 amended), ADR 0024.

## Evidence

- Code: W4 `bb4fc1a`…`ff79cbe`, review fix S4 `16dc9e8`, amended tests `843d145`. Tests:
  `tests/test_t08_w4_warm_starts.py` (run it: `PATH=.venv/bin:$PATH python -m pytest -q tests/test_t08_w4_warm_starts.py`).
- Reported numbers (engineer, W4): target (recycle 0.95) certifies cold — cold 5 steps / 14 residual / 201 property
  calls; warm 3 / 8 / 112; warm and cold final states agree to 8.0e-15 relative; B47 replay MATCH of the B41, B43, B44
  bundles in a fresh project with 0 store lookups during rerun; B48 selection skips a FAILED-verdict and an
  out-of-lineage run; B49 no `warm_start` member under any other policy; B50 descriptions digest `6d13e13d…` and
  schemas unchanged since `c7bbc98` (with Amendment 1's T10 oracle via `t07_reference_t08.json`, G16-b 40/40).
- Design-lane review of the warm-start code: `docs/reviews/T08-review.md` (§3 item 6; finding S4, fixed).
- CI green on `wp/T08` (run on the verdict commit `2fa4232` and later); the A33 recovery-edge test is red on five
  rows unrelated to warm starts (E9, the warm-start rejection edge, has its evidence).

## Out of scope

V13 (a)–(d), V14, the other gates; any redesign. If a clause rests on a test that does not show what its row claims,
say so — do not re-read the criterion.
