# Brief — T08 Phase 2a: the supported envelope, the harvest, the recovery-edge inventory, the ledger

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §5 (the supported envelope: §5.1 form, §5.2
supported axes, §5.3 unsupported and how each fails, §5.4 alias-pressure-shift limit, §5.5 registered limitations
with the build-first additions L-CSTR-1..3 and L-WS-1..2, §5.6 recovery-edge inventory, §5.7 the harvest), §9
(T08.A02, A20–A24, A33), §15 Phase 1 W1.1 and Phase 2 W2.1–W2.4. The build-first spec's B27 and §E.4 (13
models; offered policies `T06-revision-v2`, `T04-W12`, `T08-ptc-v1`, `T08-warm-v1`). Decisions so far:
`docs/T08_DECISIONS.md`. Frank's rulings: V14 (b) carried as FAIL (ADR 0021 D3 row, 2026-09-29) — the envelope
states PTC as experimental; F5 V17 carried.

## Items (one commit each; messages `T08 W2.n:` / `T08 W1.1:`)

| Item | What | Assertions |
| --- | --- | --- |
| W1.1 | The gate ledger `docs/t08-gate-ledger.md`: V11–V20 evidence lists as §4 names them, G00–G06 backfill (Q8) | T08.A02 |
| W2.1 | `support_envelope.yaml` (location per §5.1), `scripts/t08_support_matrix.py --check`, `docs/support-matrix.md`; every unsupported row names the test node that shows its typed outcome | T08.A20, A22, A23 |
| W2.2 | The harvest (§5.7): every `limitations[]` entry and non-`pass` check of every manifest under `evidence/`, keyed by path, index and text sha256, classified E/S/P/B exactly once, with `--check` failing on unmapped/dangling/changed items. **Draft classification only — the design-lane `reviewer` checks it later (R).** | T08.A21 |
| W2.3 | The alias-rule threshold test (§5.4) | T08.A24 |
| W2.4 | Recovery-edge inventory and bijection (§5.6) — **R** later | T08.A33 |

Out of this increment: W2.5 ([A10] refresh), W2.6 (v0.0.0 bundle probe), W1.6 (A89), Phases 3–5.

## Rules

- Where §5 is under-determined, stop and report the question with file:line — do not invent support claims. The
  envelope may only claim what a test shows; everything else is unsupported with a typed outcome or a registered
  limitation.
- No change to schemas, MCP tools/descriptions (T08.A49), specs, ADRs, YAMLs, generators, `requirements.lock`, or
  any registered result. Identity unchanged (`measure_identity` in `scripts/t07_evidence_manifest.py`: whole K05
  `7f32b143…`, `t07` `422aa7a5…` — the approved values since the STR-05 merge — minus-`t07` `9a7b4e6d…`,
  structural `915c97e8…`, T02 floats `9a8a5baf…`, keys `t02`…`t06`).
- Work in this checkout; nobody else edits it. Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. Never set
  `reviewed`. `.venv/bin/python`; quote the path. Budget: the user is near a weekly usage limit — targeted tests
  while developing, the full `PATH=.venv/bin:$PATH ./scripts/check.sh` once at the end.

## Report

Commits per item; each assertion with pass/fail and numbers (how many limitations harvested, the E/S/P/B counts,
edges inventoried); `check.sh` counts; questions you stopped on; what the reviewer should check in W2.2/W2.4.
