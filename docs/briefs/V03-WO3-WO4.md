# V03 brief 2: work orders WO-3 and WO-4 (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03` (head `c82c2fd3`). Specification
`docs/derivations/V03-release-spec.md` with Amendment 1 (ADR 0053, ADR 0054); its §10 table names WO-3 and WO-4, §10.3 and
§10.4 the amendments, §10.1 the stops. WO-1/WO-2 are done (`docs/V03_DECISIONS.md`, incl. merge notes for E01's files).
Frank's answers: N-1 no W27, N-7 keep the token, N-8 correct U02, N-9 keep `other` (end of §11).

1. **Merge `main`** first (E01 merged at `05363060`; expect additive conflicts in NOTICE, `tests/test_t08_w2_inventory.py`,
   `src/openflowsheet/resources.py`, `pyproject.toml` — the notes are in `docs/V03_DECISIONS.md`; per-entry merge for
   `docs/decision-register.md`: keep every entry of both sides, main's order then ours-only; nothing dropped).
2. **WO-3**: §10.3's roles first (ADR 0054: enum + Table R, the nine cases regenerated through their generators, the five
   test builders, A28–A31; prove A31: binder outcomes equal for every committed document), then MR-12 v03 and the RC CoolProp
   step (F-8). **The A48 tripwire at 0 is not yours**: it arrives with `wp/E01b` (cost-range flags, about to merge into main);
   leave that item and say so.
3. **WO-4** (one engineer, you): ADR checks and flips per §6 (S07 F-1 line transcribed verbatim into ADR 0001 and
   `docs/interfaces-frozen.md`; mark only what §6 allows — never mark a package `reviewed`), the `## v0.3.0` CHANGELOG draft
   ("What it is not"), the envelope U02 text (N-8), L40 and L-S11-3 and the attribution page (§10.4), RELEASING "Per release"
   for 0.3.0 and the W27 sentence (F-4).
4. If `main` by then contains `docs-site/` (the docs branch may merge first), also fix the site's Wilson "source checkout"
   lines and the examples' turbine/compressor `semantic_role` (now `turbine`/`compressor`); otherwise note it as open.

## Rules
DECISION lines in `docs/V03_DECISIONS.md`, one isolated commit each; stop (commit, write the question, end) on anything §10.1
lists or that changes numerics or a frozen interface beyond ADR 0054. Tests you touch + `scripts/s11_identity.py` (expect
PASS; the nine regenerated documents change their own hashes — S11 identity hashes documents, so read §9.4/A31 on how that is
handled and report the line exactly). Not the full gate. Pytest: `TMPDIR=/home/frankp/.cache/v03-tmp
PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/v03-tmp/pt"`, `PYTHONPATH=$PWD/src:$PWD`,
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`. Never `/tmp` directly. Named-path staging; commit messages name V03; do
not push; no subagents; no personal identifiers to external services; never touch `~/.config/procsim/v17-token`. Context cap
~150k: commit, ≤40-line handoff at the end of `docs/V03_DECISIONS.md`, end. Report in at most 20 lines.
