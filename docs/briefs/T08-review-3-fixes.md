# Brief — T08: land review 3 (M1, S1, S2, N5, N6) and register R-146/R-147

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-02. **Branch:** `wp/T08`.
**Binding:** `docs/reviews/T08-review-3.md` — M1, S1, S2, the Notes (N5, N6), and **§C Rulings 1–3 with their exact
text**. You transcribe the rulings' text; you decide nothing they leave open (stop and report instead).

## Items (one commit each; messages `T08 R5-…:`)

1. **Ruling 1 (M1):** append release spec Amendment R5 1 with in-place markers at §3.2 (and §6.2: R-148 as the second
   substitution); update `docs/derivations/scripts/t08_reference.py` exactly as the ruling says the generator must
   check, regenerate `benchmarks/t08/reference_values.yaml` with `--emit`, and `--check` must pass byte-reproducibly.
2. **Ruling 2 (S2):** append ADR 0025's correction section (§11's moved/unchanged values, Q4 replacing "refused at
   replay", the cost line) and the spec's Amendment R5 2 for R4 1. Then enter **R-146** (ADR 0025, as amended by Frank's
   Q4) and **R-147** (Frank's Q4) in `docs/decision-register.md` in the format of R-144/R-145, using ADR 0025 §15's text
   as amended; update the index line (next free R-149; ADR 0026).
3. **Ruling 3 (S1):** correct `scripts/v0_1_gate.py`'s Result-cell classification to the closed vocabulary the ruling
   gives (pass: PASS/success; fail: FAIL/FAILED/failure and the CI conclusions cancelled, skipped, timed_out,
   startup_failure, action_required, neutral, stale; "not measured" in any case; `(k/n)` must have k = n), with the
   review's S1 probes as tests and the check that the `814e151` record classifies as the ruling states.
4. **N5:** mark `exact_fields` in the v2 policy as inert exactly as the review recommends (policy generator + file +
   a test that it is documented as not enforced), unless the review's text leaves the form open — then stop and report.
5. **N6:** strengthen A14's controls in `scripts/t08_rc.py`: C3 also requires `bitwise_floats is False`; C2's
   precondition `assert`s become raised errors. Tests.

## Rules

No `src/` behaviour change except what an item names (none of these should touch `src/`; if one does, stop and say
why). Identity unchanged at R-148's values (`measure_identity`: whole `28dd8bf7…`, t07 `a96f17ed…`, minus-t07
`29246e05…`, structural `e62a59a6…`, T02 floats `9a8a5baf…`). No schema, MCP or `requirements.lock` change. Work in
this checkout; nobody else edits it. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the user is
near a weekly usage limit — targeted tests, then `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` once (threads 1);
expected fully green.

## Report

Commits; generator `--check` result and new YAML sha256; G3 behaviour on the probes and on the 814e151 record;
`check.sh` counts; questions.
