# E01b brief 2: build C3′–C6′ from Amendment 1 (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/e01b`, branch `wp/E01b` (head `1c149f3f`). Your work order
is **`docs/derivations/E01-design.md` §10.10.7** (Amendment 1 to ruling B, against the Seider **3rd edition**; R-895…R-899),
with the amended numbers in §10.10.5.1, ranges §10.10.5.3, what moves and by how much in §10.10.7 (any other moved number →
stop), and the acceptance commands. §10 (the 4th-ed. ruling) stands only where §10.10 does not replace it. Open questions:
work on the defaults (Q-B2, Q-B3, Q-B8, Q-B9, Q-B11, Q-B12).

Done before you (on the branch): C1 (`f72af0c1`), C2 loader (`acc75185`), C1 pins (`15307c6a`). Parked on local branch
`wip/E01b-held` (built on the 4th-ed. numbers): take from it only what §10.10.7 allows — `forms.py`/`contributor.py` from
`e37dacb1`, cherry-picks of `c73a0721` and `02477928` with the listed changes, test files from `f43f7dab` adapted; redo the
set JSON, the cost_hand constants, the fixtures and the pins; `seider3.yaml` replaces `seider4.yaml` (A49). Facts from the
previous engineer (end of `docs/E01B_DECISIONS.md`): the scratch IDAES 2.13.0 env is at `/home/frankp/.cache/idaes-2.13/venv`
(A15); `f43f7dab` left a line-length and a formatting fix pending in `tests/test_e01_a_cost.py`.

- Do **C3′–C6′**, test once after C6′, extend `scripts/e01_evidence_manifest.py` for package id **S12b** (A49–A51) and write
  `evidence/S12b/<commit>/manifest.json` (`tested`; G8/gate/CI and C7 items honestly open).
- **C7** (five new `verified: true` flags: three compressors, the turbine, `weight_limit` "2") is **not committed**: write it
  as `docs/briefs/QA1b.patch` applying cleanly on C6′, and list in your report each flag with its 3rd-ed. page.
- Do not merge `main` or `wp/E01` (the orchestrator does that).

## Rules
- DECISION lines in `docs/E01B_DECISIONS.md` (section "E01b, build 2"), one isolated commit each. Never widen a tolerance or
  edit an expectation to make a test pass; a number outside §10.10.7's list → stop, commit, write the question, end.
- Tests you touch, the acceptance commands, then `scripts/s11_identity.py` → `S11-IDENTITY PASS`. Not the full gate. Pytest:
  `TMPDIR=/home/frankp/.cache/e01b-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/e01b-tmp/pt"`,
  `PYTHONPATH=$PWD/src:$PWD`, `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`. Never `/tmp` directly. ruff check +
  format clean.
- The Seider texts under `/home/frankp/.cache/seider3/` and `seider4/` are licensed copies: never copy them into the
  repository; individual numbers with page/table citations only.
- Stage named paths; never `git add -A`. Commit messages name E01b. Do not push. Do not start subagents. Do not send names,
  e-mail addresses or other personal identifiers to any external service.
- Context cap ~150k: commit, write a ≤40-line handoff at the end of `docs/E01B_DECISIONS.md`, end.
- Report in at most 20 lines: commits, tests with counts, every moved number versus §10.10.7, A48 count, the C7 flags.
