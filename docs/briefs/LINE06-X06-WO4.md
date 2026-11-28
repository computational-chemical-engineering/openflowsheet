# LINE06 X06-WO4: in-band policy administration (ADR 0078 D5)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the surface-suite rule: `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_m07a_surface_chain.py`).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06` (head `4ca7ce3c`: WO1 to WO3b
done, ADR 0078 Accepted with ruling round R1 appended). Another engineer works on F2 in `.claude/worktrees/f2`; leave
it alone. Budget about 150k context: at the cap, commit what is complete, write where you stopped in
`docs/X06_DECISIONS.md`, and end.

## The task

Build X06-WO4 as ADR 0078 states it (`docs/adr/0078-X06-application-capabilities.md`, **Accepted**; do not edit it):
D5 (lines ~204-241: the per-project operator switch `administration: {in_band: true}`, absent = off and omitted by
`as_document`; the four operations `get_policy`, `grant_capability`, `revoke_capability`, `set_ambient_pressure` on
all four transports with right `policy`; the refusals in D5.3 in that order; the delegation rule
`authz.delegation_refusal`; the token shown once and never stored, ledgered as `token: null`; `change_policy` with an
actor and one audit row per write; `AdministrationService` directly below `branch_service`) and work-order row 4
(line ~391): `authz.py`, `policy_types.py`, `schemas/project-policy.schema.json`, `administration_service.py`,
`service_core.py` (`serving_remote`), `serving.py`/`cli.py` (`project administration on|off`, the flag),
`contract.py` (`Administration`), `operations.py`, `local.py`, descriptions, `$defs`; layers; catalogue; the
served-digest re-pin; the new operations as conformance steps on all six clients (ADR D6). ADR Q2 and Q3 (lines
~402 on) fix the defaults: off by default, writes refused on a non-loopback server.

## Facts established

- WO1 to WO3b logs: `docs/X06_DECISIONS.md` (WO3b-1 is open for the reviewer). Current pin:
  `X06_SERVED_SHA256 = 4a80f77f…` (`tests/test_t08_w2_surface_digest.py:174`), decomposing onto F3's `f7ec3c94…`;
  chain link c_12 (R-1073) in `scripts/m07a_rc.py`. Re-pin it the way WO3 did (WO3-8).
- At `4ca7ce3c`: surface suites 2619 passed, 28 skipped, 3 xfailed (MSG `test_g6_pending_holds`, pre-existing),
  1 failed (the description-review gate, below); `tests/test_t07_q26.py` 6 passed; bundle gate 63 bundles, 60 ok,
  digest `b42b1ec439d1683c` (script: `docs/X06_DECISIONS.md` ~line 262-273).
- F0 on wp/X06 must stay: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42. E-X06-16: every existing
  policy file keeps its bytes and `policy_sha256`.
- `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes` is red by design until
  the reviews are recorded (seven texts so far; yours add to them). Do not mark any review; list your new or changed
  description files in the report.
- R-088 Q26 (`tests/test_t07_q26.py`): numeric maps and scalars in a request are admitted only by full path with a
  design-lane ruling (precedents R-1058, R-1075). If your new requests make it report findings (for example
  `set_ambient_pressure`'s `value`, `grant_capability`'s `limits`), do **not** pin or allow them yourself: list each
  finding exactly as the test prints it as a STOP item in your report and in `docs/X06_DECISIONS.md`, and finish the
  rest. The design lane rules on them in X06's reviewer pass.

## Acceptance (report each)

1. E-X06-16 to E-X06-21 and E-X06-22 (ADR "Exit tests", ~lines 355-375): test names and counts, 0 failed.
2. The surface suites, `tests/test_x06_*.py`, MSG and doc-page tests: counts; 0 failed except the description-review
   gate (name the texts it lists) and any Q26 finding reported as a STOP. Run after your last commit.
3. ruff check, ruff format --check, `mypy src` clean.
4. The bundle gate: 63, 60 ok, `b42b1ec439d1683c`.
5. F0 PASS with the counts above, at your last commit.

## Stops (report rather than choose)

A change to a record, run identity, the store schema, a request hash or an existing policy file's bytes; a token or
`prt_` string reaching the store, audit, ledger, policy file or a log; the ADR contradicting the code; a test that
passes only by relaxing a check; a Q26 finding (above).

## How

Commit named paths on wp/X06, messages `X06-WO4: ...`; DECISIONs in `docs/X06_DECISIONS.md`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Report (200-300 words)

Per acceptance item: pass/fail and the number; DECISIONs (one line each); commits; the description files touched;
STOP items; anything for WO5.
