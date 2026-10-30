# V03 brief: work orders WO-1 and WO-2 (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03` (head `0608cd8d`). The specification is
`docs/derivations/V03-release-spec.md` (ADR 0053, Proposed); its §10 table names WO-1 and WO-2 and the assertions each must
make pass; §10.1 lists the stops — on any stop, commit what is complete, write the question in `docs/V03_DECISIONS.md` and
end. Frank's answers N-1 (W27 not claimed), N-7 (keep the token), N-8 (correct U02) are recorded at the end of §11.

- **WO-1:** `scripts/v0_3_gate.py` on `v0_2_gate.py`'s engine (registry, line name and spec texts made parameters; v0.2's
  output must stay **byte-identical** — prove it by diffing `scripts/v0_2_gate.py` output before/after on the same inputs,
  and keep its existing tests green), `benchmarks/v03/registration.json`, tests in the pattern of
  `tests/test_m07_v0_2_gate.py`, A10's pairs (R-563 as ruled in the spec §5.3).
- **WO-2:** the Wilson ship set as package data (Frank: fitted parameters **and** the transcribed Kurihara 1993 points, plus
  the three CIAAW atomic weights); remove the R-811 wheel refusal row as the spec says; NOTICE blocks;
  `docs/attributions/wilson-ig-v1.md`; the rights-check table (already updated by the spec author — check it agrees).

Not yours: WO-3 onward (E01 is not merged into this branch yet; do not merge `main` or `wp/E01`).

## Rules
- Each choice the spec leaves open: a `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.` line in
  `docs/V03_DECISIONS.md`, one isolated commit. Stop rather than choose on anything changing numerics or a frozen interface.
- Per commit: run the tests you touch plus `scripts/s11_identity.py` once at the end (expect `S11-IDENTITY PASS`). Not the
  full gate (the orchestrator runs it once per batch). Pytest with a private temp dir:
  `TMPDIR=/home/frankp/.cache/v03-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/v03-tmp/pt"`, `PYTHONPATH=$PWD/src:$PWD`,
  interpreter `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`. Never use `/tmp` directly.
- Stage named paths; never `git add -A`. Commit messages name V03. Do not push.
- Do not start subagents. Do not send names, e-mail addresses or other personal identifiers to any external service.
- Never read, stat or copy `~/.config/procsim/v17-token`.
- Context cap ~150k: if reached, commit, write a ≤40-line handoff at the end of `docs/V03_DECISIONS.md`, and end.
- Report in at most 20 lines: commits, tests run with counts, the byte-identity proof, any stop.
