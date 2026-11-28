# LINE06 F8-WO2: bundle writer v2 (ADR 0067 work order 2)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `ddac950f` (clean; WO1 and WO1b
done). Logs and scripts under `/home/eajfpeters/.cache/line06/f8-wo2/` only; wait on log lines, not `kill -0`. Tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`; F0 with
`--log /home/eajfpeters/.cache/line06/f8-wo2/f0-detail.log`. Log every choice as `DECISION F8-WO2-<n>` in
`docs/F8_DECISIONS.md`. An engineer works in `.claude/worktrees/f2`; do not touch it. Budget about 150k: at the cap,
commit what is complete, write where you stopped, and end.

## The task

ADR 0067 (`docs/adr/0067-F8-identity-replay-evidence.md`) work order 2 ("Work orders", row 2): `run/bundle_v2.py`,
the D3 layout (line ~67), D4's rights-aware embedding (line ~86), and a **test-only v2 bundle factory** (a corpus case
rerun and recorded as v2). Read D1 to D4 and D9, "Exit tests" E-F8-2 and E-F8-3, and the WO1/WO1b entries of
`docs/F8_DECISIONS.md` (what exists: `run/manifest_v2.py` `RunManifestV2`, `extensions_used_rows`,
`EnvironmentRegistry`; schemas `bundle-v2`, `records-index`, `run-evidence`; the D3 artifact kinds in
`jobs/model.py`). `run/bundle.py` stays untouched (D3).

## Facts established

- Building blocks exist: `records/lock.py` `build_lock` (l.72), `data_lock_sha256` (l.67); `records/rights.py`
  `effective` (l.166), `embeddable` (l.215), `record_sources` (l.75); `records/store.py` `RecordStore.object_bytes`,
  `record`; `registry/snapshot.py` `snapshot_document`, `registry_sha256`; `Registry.snapshot`,
  `Registry.extensions_used` (`registry/__init__.py` l.625, l.681).
- In 0.6 no production run writes a v2 bundle (v2-compiled runs come with F6/WO6, 0.7); the factory is the only
  writer, and it lives under `tests/` (test-only), not in `src/`. A lowered run stays a v1 run in every artifact (D1,
  ADR 0062 D8): nothing in the v1 path may change.
- D4: a record is embedded iff every source's effective assessment is `permitted`; rights enter no hash; no network
  access while writing.
- Choose the factory's corpus case(s) so E-F8-3 has at least one embedded and one referenced record (a source
  `unknown` or `refused`); if no corpus case has both, construct the second assessment in the test's own rights
  register (state how in a DECISION).

## Acceptance (judged on these alone)

1. **E-F8-2:** a factory bundle round-trips: the manifest validates against `run-manifest.schema.json`;
   `data-lock.json` and `registry-snapshot.json` hash to their manifest values (`data_lock_sha256`,
   `environment.registry.snapshot_sha256`); `verify_bundle`'s integrity check covers `artifacts/records/*` (a mutated
   record byte fails it).
2. **E-F8-3:** a record whose sources are all `permitted` is embedded (bytes equal to the store's canonical bytes);
   `unknown` or `refused` is referenced only; re-assessing a source afterwards changes no `data_lock_sha256`,
   `structural_sha256` or `r0_sha256`.
3. **E-F8-10:** F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42); `tests/test_f8_manifest_v2.py`,
   `tests/test_k05_replay.py`, the surface suites (`tests/test_t07_*`, `tests/test_t08_w2_*`,
   `tests/test_m07a_surface_chain.py`) pass except the three known `tests/test_v03_semantic_roles.py` reds (F2's,
   fixed on wp/F2). No served digest moves (a move is a STOP). ruff, ruff format --check, mypy src clean.

Tests in `tests/test_f8_bundle_v2.py`, each named after its exit. Commit named paths only, never `git add -A`; do
not push. Make sure no background job of yours runs before you report. Report in 200-300 words: commits, test counts
per file, the F0 line, which corpus case(s) the factory uses and how E-F8-3's referenced record arises, DECISIONs.
