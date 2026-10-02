# T06 reference comparisons — committed evidence (spec §9.6, work order W8)

Authority: `docs/derivations/T06-corpus-spec.md` §9 as amended (Amendments 1 and 2), rulings M6
(a)–(g) of `docs/briefs/T06-amendment-1.md` §4 and item 7 of `docs/briefs/T06-amendment-2.md` §3,
assertions A47–A54 and A83. Numerical verification of a second,
independent implementation of the same equations — not empirical validation.

| File | What |
| --- | --- |
| `results/dwsim-<fixture>.json`, `results/idaes-<fixture>.json` | The tool records: raw output, §9.3's settings as applied and read back, environment fingerprint, rule 2's self-check, the compared quantities. `idaes-PC-1.json` records the registered absence (§9.4, ruling M6 (b)) |
| `results/idaes-<fixture>.ipopt.log` | Ipopt's log of each final solve (line 1 carries the run's absolute paths) |
| `results/idaes-default-eps-<fixture>.json`, `.ipopt.log` | W8's IDAES records (REF-01 … REF-08, PC-2), run at IDAES's default SmoothVLE smoothing (`eps_1 = 0.01 K`, `eps_2 = 5e-4 K`), byte-identical to W8's; superseded by the re-run at the registered `eps_1 = eps_2 = 1e-8 K` and retained (spec §9.5 rule 2b, A83) |
| `results/ours-<fixture>.json` | This project's side: outcome, certificate verdict, certified state, compared quantities. PC-1's "ours" is REF-04's |
| `results/SHA256SUMS` | SHA-256 of every file above |
| `comparison.json` | The mechanical classification of every (fixture, tool) by §9.5's rules (1, 2, 2b, 3, 4), with the full table; under `superseded_default_eps`, the retained records' rule 2b classification (`NOT_COMPARABLE(semantics: smooth_vle_shift(…))`) beside the table they produced without it (`without_rule_2b`), counted nowhere; recomputed by the gate from the files above alone |

The verdict is not recorded here: it is the `verdict` agent's, on `comparison.json`.

**Provenance.** DWSIM records and `idaes-default-eps-*`: 2026-09-26, Debian 13 x86-64, harness
`spikes/references/` at `d4f1184` (IDAES `constr_viol_tol = 1e-9` for every final solve; no
adjustment). IDAES records `idaes-<fixture>.json`: 2026-09-26, the same host, harness at W8b's
`ddda70b` (in addition, SmoothVLE `eps_1 = eps_2 = 1e-8 K` on every state block, set before any
initializer; no adjustment), re-run blind — flags and self-checks (rules 2 and 2b) read first,
two runs identical in content without wall times. Environments rebuilt by
`scripts/build-reference-envs.sh` with the fingerprint of `docs/reference-environments.md` §3. The tool scripts read neither this project's results nor the
twin (A52, checked statically by the gate).

**Reproduce** (from the repository root; the first two steps need the reference environments and
are never part of `scripts/check.sh`):

```bash
scripts/build-reference-envs.sh
spikes/references/t06_qualify.sh all evidence/T06/artifacts/w8-run
cp evidence/T06/artifacts/w8-run/{dwsim,idaes}-*.json evidence/T06/artifacts/w8-run/idaes-*.ipopt.log \
   benchmarks/t06/references/results/        # the idaes-default-eps-* records are W8's, kept as committed
PYTHONPATH=src:. python scripts/t06_references_ours.py
PYTHONPATH=src:. python scripts/t06_reference_comparison.py --write   # --check, --markdown
(cd benchmarks/t06/references/results && sha256sum $(ls | grep -v SHA256SUMS | sort) > SHA256SUMS)
```

The gate test is `tests/test_t06_w8_references.py`; it runs no tool.
