# LINE06 X06-WO1: MCP over streamable HTTP (ADR 0078 D1)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06` (head `dcbab9b7`, the ADR).
Another engineer works on F2 in `.claude/worktrees/f2`; leave it alone. Budget about 150k context: at the cap, commit
what is complete, write where you stopped in `docs/X06_DECISIONS.md`, and end.

## The task

Build X06-WO1 exactly as ADR 0078 states it (`docs/adr/0078-X06-application-capabilities.md` on wp/X06): D1 (lines
55-97: one server, `/mcp` on `serve-http`, the SDK's stateless JSON mode of the pinned `mcp==1.30.0`, the bearer
checked per request before the SDK sees it, the Origin rule, 413 on oversized bodies, the security model D1.6),
work-order row 1 (line ~383: `application/bindings/{mcp,mcp_http}.py`; the `serve-http` composition in
`application/serving.py` and `application/cli.py` with the warning text; `tests/test_x06_mcp_http.py`; the sixth
client in `tests/test_t07_conformance.py`; the import-graph allowlists in `tests/test_t07_w6a_http.py` and
`tests/test_t07_w6b_mcp.py`; the catalogue entry `origin_refused`). D6 (lines 237-247) for the surface rules: no
`ApiError` code is added; the served tool list is unchanged by WO1.

## Facts established

- ADR 0078 is Proposed (acceptance requested on card `ofs-x06-accept-adr0078`); build on its text as written. Card
  `ofs-x06-mcp-clients` (the ADR's Q4) is open; its default and this WO's scope is **a static bearer header only, no
  OAuth**. Q9 (the SDK's stateless answers to `GET`, batches, a wrong Accept) is measured here: the guard answers
  `GET`/`DELETE` itself; pin whatever 1.30.0 answers otherwise, provided nothing is executed.
- F0 on main: PASS, M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42. WO1 changes
  no identity; F0 must be unchanged. The store has its `refs` table at `application/store.py:90` (not WO1's concern).
- Never copy the V17 login token (R-116); never read `~/.config/procsim/`. Tests use their own tokens.
- Where the ADR is silent, take the reading that changes no existing byte and log a `DECISION` in a new
  `docs/X06_DECISIONS.md` (format of `docs/F3_DECISIONS.md`), isolated in its own commit.

## Acceptance (report each)

1. E-X06-1 to E-X06-5 (the ADR's "Exit tests"): each named test passes; give counts.
2. The existing MCP and HTTP suites stay green: `tests/test_t07_*.py` (including the conformance test with the sixth
   client) and every test whose name contains `mcp` or `http`; give the counts.
3. ruff check, ruff format --check and mypy on the touched files clean.
4. F0 (`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src python scripts/corpus_identity.py
   --check`): PASS with the counts above.
5. The Q9 measurements, one line each.

## How

Commit named paths on wp/X06 with messages `X06-WO1: ...`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. Bind test servers to loopback
only, on ephemeral ports. No push, no merge, no manifest (WO5).

## Stops (report rather than choose)

The SDK cannot run stateless without a new dependency or a version change; a security default would open a remote
write path; the ADR contradicts the code; a test passes only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and the number. The DECISIONs (one line each). Commits (short sha). Anything for WO2.
