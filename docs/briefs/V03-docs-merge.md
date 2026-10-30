# V03 brief 4: take in the docs site and close its two open items (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03` (head `aa83d975`). `main` is now
`8f402cfa` (the docs site merged: `mkdocs.yml`, `docs-site/**`, `examples/*.ipynb`, `scripts/doc_pages.py`,
`tests/test_doc_pages.py`, `tests/test_doc_examples.py`, manifest `evidence/S14/…`, `docs/DOC_DECISIONS.md`).

1. **Merge `main`.** Register (`docs/decision-register.md`): per-entry merge with
   `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/regmerge3.py`
   (main's order, then ours-only; nothing dropped). Envelope/harvest: keep both blocks (main's first), recount
   `HARVEST_SIZE` as merge base + each side's increments, re-emit with `scripts/t08_support_matrix.py --emit`, `--check` 0.
   Never drop main's content.
2. **O1** (`docs/DOC_DECISIONS.md` O1): Wilson records now ship in the wheel (WO-2). Remove the "source checkout" lines in
   `docs-site/guide/property-bases.md`, `examples/README.md`, `docs-site/examples/index.md`,
   `docs-site/getting-started/install.md`; say the data ships with the package where a sentence is needed.
3. **O2** (O2): `semantic_role` of `thermal.turbine` / `thermal.compressor` in the examples becomes `turbine` / `compressor`
   (ADR 0054). Change the two notebooks, the tutorial and `examples/rankine-cycle.changeset.json` together. **Check whether
   the cost example (`rankine-cost-and-gwp`) maps cost correlations from `semantic_role`.** If any printed or asserted number
   moves (old: impact 0.024320 kg CO2-eq/s, and its capital figures), that is expected only if the role selects the
   correlation — state old and new numbers in the log and the notebook text, and confirm the new one comes from the
   turbine/compressor correlation of E01 §10.10; if a number moves for any other reason, stop and report.
4. Mark O1/O2 closed in `docs/DOC_DECISIONS.md` (one line each, with the commit).

Checks: `tests/test_doc_examples.py`, `tests/test_doc_pages.py`, `scripts/doc_pages.py --check`, `mkdocs build --strict`
(with the venv in `requirements-docs.txt`; if mkdocs is missing from `/home/frankp/Codes/OpenFlowsheet/.venv`, install
from `requirements-docs.txt` with `--require-hashes`), `scripts/t08_support_matrix.py --check`, `scripts/s11_identity.py`
(PASS), and the tests the merge touches. Not the full gate (the orchestrator runs it).

Rules as brief 2 (`docs/briefs/V03-WO3-WO4.md`): DECISION lines in `docs/V03_DECISIONS.md`; pytest with
`TMPDIR=/home/frankp/.cache/v03-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/v03-tmp/pt"` (TMPDIR only for
`s11_identity.py`; never share a `--basetemp` across its shards); `PYTHONPATH=$PWD/src:$PWD`; named-path staging; commit
messages name V03; do not push; no subagents; no personal identifiers to external services; never touch
`~/.config/procsim/v17-token`; ~150k context cap with a handoff at the end of `docs/V03_DECISIONS.md`. Report in at most
15 lines: head sha, HARVEST_SIZE, the S11 line, any moved number.
