# DOC brief 2: cost/LCA pages, harvest, and merge-readiness (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/doc`, branch `wp/DOC` (head `d0584872`; your predecessor's
handoff is at the end of `docs/DOC_DECISIONS.md`; the first brief `docs/briefs/DOC-site.md` and its rules apply unchanged).

1. **Merge `main`** (now has E01 at `05363060`: cost estimation and LCA, ADR 0052, `docs/derivations/E01-design.md`, the `lca`
   extra in `pyproject.toml`). Resolve conflicts by keeping both sides' additions; never drop main's content.
2. **Cost and LCA in the site** (the D2 gap): a user-guide page "Cost estimation and LCA" (what is estimated, the correlation
   set and its provenance — IDAES SSLW transcribed, checked against Seider et al. 3rd ed., cited by page; cost indices; the
   accuracy class and uncertainty; LCA as unit scores × inventory, IPCC AR6 GWP-100 shipped, ecoinvent/EF never shipped,
   restricted data labelled; the `lca` extra; using cost/impact as an optimisation objective), the install page's `lca`
   extra, the API pages for the public assessment entry points (NumPy docstrings where you add them), and one example
   notebook (e.g. capital and operating cost plus GWP of the Rankine cycle) executed by `tests/test_doc_examples.py` with its
   bold numbers asserted. Note: a separate branch (`wp/E01b`) is about to change pump/motor costs (× 0.788) and some vessel
   costs; **do not state cost numbers that E01b will move** — assert numbers from parts E01b does not change (e.g. GWP,
   exchanger/compressor items), or state the cost example's numbers as computed at build and assert only structure for
   them; say which you chose (DECISION line).
3. **T08 harvest** of the S14 manifest (the full gate failed on `tests/test_m07a_harvest.py` HARVEST_SIZE and the A21
   "unmapped" limitations): regenerate the S14 manifest at your final commit, then harvest it as the other packages do
   (append to `benchmarks/t08/support_envelope.yaml`, re-emit `docs/support-matrix.md`, re-pin `HARVEST_SIZE` in
   `tests/test_m07a_harvest.py`; see commit `b4e161e5` on `wp/E01b` for the pattern; `t08_support_matrix.py --check` 0).
4. Leave for later (the release batch, not you): the Wilson "source checkout" lines (Wilson ships in the wheel on `wp/V03`)
   and the turbine/compressor `semantic_role` in the examples (ADR 0054 on `wp/V03` adds `compressor`/`turbine`).
   Record both as open in `docs/DOC_DECISIONS.md`.

Checks: `mkdocs build --strict` clean, `scripts/doc_pages.py --check`, the doc tests, the tests you touch,
`tests/test_m07a_harvest.py` and the envelope/matrix tests, `scripts/s11_identity.py` PASS. Not the full gate. Same rules as
brief 1 (private temp dirs under `/home/frankp/.cache/`, named-path staging, no push, no subagents, no personal identifiers
to external services, ~150k context cap with a handoff). Report in at most 15 lines.
