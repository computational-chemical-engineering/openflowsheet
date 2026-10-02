# Brief — T08: implement ADR 0025 (W1–W8)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-02. **Branch:** `wp/T08`.
**Binding:** `docs/adr/0025-cross-platform-replay-comparison.md` (Proposed) — §4 D1–D7, §5 the comparison table, §8
the policy file, §9 assertions A1–A15, §10 the work order W1–W8 — **with "Frank's answer to Q4" at the end, which
replaces D1.3's refusal**: a record under another *known* policy is replayed and compared under the policy it records
(v1's path bit-identical); only an *unknown* policy id is refused. ADR 0007 Amendment 1; release spec Amendment R4 (A45).

## Items: W1–W8 of ADR 0025 §10, one commit each (`T08 A25-Wn:`), with the Q4 change applied to W4 and A-tests.

## Stop conditions (report, don't choose)

- **Agent surface (T08.A49/B50; V17's carry, R-133/R-134):** W3 changes `numerical_policy_id` from `const` to `enum`
  in the frozen `run-manifest` and `solution-certificate` schemas. Before committing W3, establish whether either
  schema is reachable from any MCP tool's served `inputSchema`/`outputSchema` (the descriptions digest `171dd768…` and
  the request/response schemas pinned by A49/B50). If the served MCP surface would change, **stop and report** — that
  goes to Frank.
- **Identity:** the K05 identity document and every registered key must stay byte-equal (`measure_identity`: whole
  `7f32b143…`, `t07` `422aa7a5…`, minus-`t07` `9a7b4e6d…`, structural `915c97e8…`, T02 floats `9a8a5baf…`). If
  recording v2 in new run manifests/certificates moves a registered identity or a registered fixture beyond the one
  `numerical_policy_id` field (W5's rule), **stop and report**.
- Never edit fixtures recorded at another tag or by an agent run (`tests/fixtures/t08/v0.0.0-*`,
  `benchmarks/t07/v17/runs/**`), committed RC/W5 results, or `requirements.lock`.

## Rules

Spec/ADR text is done — do not edit it (except `docs/interfaces-frozen.md`'s note, W3, and the envelope rows, W8).
Work in this checkout; nobody else edits it. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
and `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the user
is near a weekly usage limit — targeted tests, then `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` once (threads 1).
W2–W4 get a design-lane review afterwards.

## Report

Commits; the surface check's result; identity and fixture moves (each justified); A1–A15 results; `check.sh` counts;
questions.
