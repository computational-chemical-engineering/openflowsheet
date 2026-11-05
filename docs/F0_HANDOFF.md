# F0 handoff (2026-11-05, first engineer stopped at the context cap)

Branch `wp/F0`, worktree `.claude/worktrees/f0`. Brief `docs/briefs/F0-build.md`; choices `docs/F0_DECISIONS.md`.

## Done
- `.gitattributes` (eol=lf; renormalize is a no-op) — commit 87936afa.
- `scripts/corpus_identity.py` `--check`/`--record`; registry `benchmarks/f0/corpus.json` (ref-x86-64);
  `tests/test_f0_corpus_identity.py` — commit 5fa16527. Summary today:
  `F0 FAIL: M1 50/50, M2 52/52, M3 52/52, M4 52/52, M5 52/52, M6 52/52, M7 NOT IMPLEMENTED, M8 NOT IMPLEMENTED, M9 8/8`.
- Exit 2 (one ulp in SYN-001's split fraction and its pinning spec → M2 constants_sha256, M3, M4 FAIL), exit 3 (one
  flipped check result → M5 FAIL), exit 4 (one byte in a frozen module → M9 FAIL naming the file): tests pass.
- Test file: 6 passed, 1 xfailed (strict: `test_the_gate_passes`), ~25 s.

## Next
1. M7 (D3): get the caller's ruling on how the 0.3.0 bundles enter the repo; implement `m7()`; remove M7 from
   `NOT_IMPLEMENTED`; re-record only the new measure (`--record` rewrites all; check the diff touches only M7).
2. M8 (D4): subprocess-wrap the six round-trip tests; register node ids; same.
3. Drop the strict xfail on `test_the_gate_passes`; `scripts/gate.sh` once; evidence `evidence/F0/<commit>/manifest.json`
   (form: `evidence/S13/`), `status: tested` only when exit 1 passes.

## Open (for the design lane, batched)
- D9: are `artifact_hash` self-hashed unit-model modules part of M9's frozen set?
