# S09 brief: the package's single `reviewer` pass (WO-S09-1 to WO-S09-3)

Branch `wp/S09`, worktree `.claude/worktrees/s09`, head `293cb19b`. Range `390e0af5..HEAD`.

## 1. What it was built against

`docs/derivations/S09-spec.md` (R-740…R-747) with Amendment 1 (§18, R-748…R-750). S03's spec and records are the frame
and are unchanged. Build log: `docs/S09_BUILD_DECISIONS.md`. A verdict agent (WO-S09-4) runs concurrently and writes
`docs/reviews/S09-verdicts.md`; do not wait for it.

## 2. Work orders

| WO | Content | Commits |
| --- | --- | --- |
| WO-S09-1 | `.venv-biosteam` (hash-locked, 63 pins; numpoly compiles C, so `--no-build-isolation` with pinned setuptools/wheel/cython), `build-reference-envs.sh`, `reference-environments.md` §9 | `6f9e01c4` |
| WO-S09-2 | harness `s09_biosteam_syn001.py`, `s09_qualify_biosteam.py`, `s09_qualify.sh`; first agent stopped on a registered string (Amendment 1) | `080290c8`, `c2589694` |
| WO-S09-2b | §18.6 harness changes; records committed before any comparison (A16); two runs byte-identical (A17) | `fd38124d`, `95643b4c`, `ff7f021f` |
| WO-S09-3 | classifier `scripts/s09_reference_comparison.py`, `cmp9`, `SHA256SUMS`, `tests/test_s09_references.py`, manifest `evidence/S09/6ce5b624…` `implemented` 25/28 (A19 waits for the verdict) | `94a9d0c0`…`293cb19b` |

## 3. Results

19 pairs: 17 AGREE (worst RC6 bottom[A] 0.0202 tolerance; RC3 family 0.0017–0.0035; others ≤ 1.1e-5); PC-LB DISAGREE
243.3 tol, PC-P DISAGREE 175.9 tol; no NOT_COMPARABLE; levels L1/R1 ×10, L1/R2 ×3 (RC3 family), L2(c)/R2 ×3 (RC4
family), L2(c)/R1 ×3 (RC5–RC7); largest margin ratio 0.0117. Three-tool X31: met where available, 3 of 4 (RC4 one
reference). Tests: `test_s09_references.py` 125 passed; S03 reference files byte-identical to `390e0af5`.

## 4. Look hardest at

- **Blindness:** was it real? The first spike saw our results; the spec ruled the spike's settings not registered and a
  fresh agent ran the qualification. Check the harness and records for any trace of tuned settings or leaked values, and
  that A16's commit order holds.
- **The L2(c) loop** (outer loop on a native spec to meet a registered specification): the six conditions, the
  accuracy rerun as fixed by §18, and whether an AGREE through L2(c) is as strong as an L1 AGREE.
- **The harness's own convergence checks** replacing BioSTEAM's (the tool swallows solver exceptions and reports
  meaningless residuals): B2–B5, the per-stage equilibrium check (simultaneous correction returns balanced states with
  equilibrium residuals 0.25–0.36), and the read-back of the property mapping.
- **Build choices** in WO-S09-3: equilibrium K in B4 from SYN-001's closed form rather than the recorded K; B5 summing
  every stage's duty; rule 2c's check order; margin rows in the twin's tolerance; the WO-S09-2b margin-row change
  (per-specification measure over its own kind threshold).
- **Open items:** WO-S09-1's numpoly fingerprint (pip-freeze hash does not cover the compiled extension; §18.8
  recommends no change); A04 judged only on records' fingerprints.
- Does every test verify what it claims?

## 5. Not worth your time

Formatting; re-deriving S03's tolerances; the spike's history beyond the blindness question.

## 6. Deliverable

`docs/reviews/S09-review.md`, findings by severity with a ruling on each §4 item and exact text where anything changes;
spec errata as a dated amendment with register entries after R-750. A docs-only commit on wp/S09 (include this brief).
Do not push; do not set `reviewed`. Report in at most 25 lines.
