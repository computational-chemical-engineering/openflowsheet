# LINE06 D1: X06 architect pass (ADR 0078)

Design lane, `architect`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first). Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06` (from main `aa5822ac`). Write no
production code. Budget about 200k context; if you near it, commit the ADR with what is designed and list what
remains.

## The question

Design package X06 as **ADR 0078** (`docs/adr/0078-X06-application-capabilities.md`, status Proposed): what OpenFlowsheet
needs so that agents and users can (1) reach the application over **MCP over streamable HTTP** (today MCP is stdio
only), (2) keep **branches**: named mutable references over the immutable revision DAG, in the project store
(today the store has one ref, `head`), (3) **resume** a long job instead of re-running it, (4) use **further solve
policies** beyond the offered ones, and (5) **administer policy in band** through audited operations (today only the
operator CLI changes policy). The scope and order are the user's (Decision Desk card `ofs-line06-x06-scope`, choice A,
signed 2026-11-26): "ADR 0056 row 8 in full and in its order: MCP over HTTP, branches (what-if revisions in the store),
job resume, further solve policies, policy administration. The ADR may propose deferring a part, with a reason, for
the user's acceptance."

## Facts established

- 0.6 is F2 (ADR 0062, `ProcessRevision` v2 and the material model), F8 WO1 to WO3 and WO5 (ADR 0067, manifest, bundle v2,
  replay, platform records) and X06 (R-1070, ADR 0057 Amendment 3). F2 is being built now on `wp/F2`. F4 to F6 are 0.7,
  F7 (problem layer v2: dynamics, progress, checkpoints) is 0.8.
- X06 must change no stored record, no run identity and no released number (R-1065: X06 "does not change records";
  F0, `scripts/corpus_identity.py --check`, passes at main with M1 50/50 … M9 42/42 and must stay so). Outward
  interfaces may be redesigned through the ADR, with no shims left at the end (the user, 2026-11-14; ADR 0076).
- R-110 (`docs/decision-register.md`, `## R-110`): the five are excluded since v0.1 and "each reported explicitly
  unsupported"; its "Rejected" paragraph sketches the additive routes considered then ("resume as a J3 branch, branches
  as an optional ChangeSet member, the others as new operations"). The note's rule C7 (`docs/roadmap/target-architecture.md`
  §2.6, line ~763) says branches live "in the project store, never in documents"; reconcile the two explicitly.
- **Job resume vs F7.** The note's dependency table (`target-architecture.md` line ~1053) reads "X06 | — | resume of long
  jobs through F7", and rule C6 (line ~762) owns "per-kind checkpoints for resume (X06)" by F7, which is now 0.8.
  Decide what resume X06 can deliver in 0.6 on today's job machinery (ADR 0020: a process per job, cooperative then
  forced cancellation, D3 "no resume"; `src/openflowsheet/application/jobs/`) without fixing a structure F7 owns, or
  propose deferring it with the reason. This is the one place a deferral is expected to be argued.
- Rule C1: a capability is a set of OPERATIONS rows (method, right, schemas, transports); none exists on one transport
  only. Current bindings: `src/openflowsheet/application/bindings/{mcp,http,web}.py`, `application/serving.py`,
  `application/operations.py`, `application/contract.py`; the contract is ADR 0019 (frozen four plus `JobControl`,
  `Inspection`; authority from the credential only; (principal, operation, key) idempotency) as reshaped by ADR 0076.
  Policy types: `application/policy_types.py`, `application/authz.py`. The V17 login token is never copied (R-116).
- The HTTP transport must state its security model (binding address, authentication from the credential, no
  unauthenticated remote write), since it is the first remote surface.

## Authority (read by section, `grep -n '^#'`)

ADR 0056 row 8 and its entry conditions; ADR 0057 D5 and the note §2.6 (C1 to C8); ADR 0019; ADR 0020; ADR 0076;
R-110; the template of a W1 ADR for form: `docs/adr/0062-F2-material-model.md` (Context, Decisions D-n, Alternatives
rejected, Migration proof, Exit tests E-X06-n, New catalogue codes, Work orders table with Content and files /
Acceptance / Identity / Lane, Risks with defaults).

## Deliverable

`docs/adr/0078-X06-application-capabilities.md`, Proposed. Work orders sized for one engineer each (about 150k
context), lanes Opus or Sonnet, each with an acceptance check that a test decides; numbered exit tests; the order of
the five parts; for each part that changes an interface, the migration of today's callers. Add the register entry
`R-1071` (decision-register.md, form of R-1070) and a pointer in `docs/progress.md` is NOT yours: the orchestrator does
them. Commit only the ADR on wp/X06, message `X06: ADR 0078 Proposed (LINE06 D1)`, trailers
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_015Acof1nLKMy3Lsg6MpcJUZ`. Do not push.

## Stops (report rather than choose)

A part that cannot be built without changing records or identity; a part that needs F4 to F7; a security question the
user must answer (for example a default that opens a remote write path).

## Report (at most 30 lines)

The five parts with one line each (in 0.6 / deferral proposed, why); the number of work orders and their lanes; the
exit tests by count; open questions for the user, each with a default; the commit sha.
