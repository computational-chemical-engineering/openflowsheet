# M07 WO-4 handoff (2026-10-17, context cap reached)

Branch `wp/M07` (worktree `.claude/worktrees/m07`), tip `8f85aa2`. Build log J21–J25 has the choices.

## Done
- Main (M05 `defa458`) merged (`8ef35e6`); gate 9406 passed / 31 skipped.
- `bf05034` R3 reads M05's `provenance` (run commit, wall); grid extras pass `services=C1_PARENT_SERVICES`.
- `9949eb3` carry by identity of `carry.journey_files`; otherwise M05's REAL study is re-run at J (`m05_rerun`).
- `f5de819` T* re-solve (`apply_t_star_resolve`, `m05_t_star_resolver`), `t_star_resolve`, `omp_num_threads`.
- `8f85aa2` reactor-availability check applies R-259 (J25).
- Premises l.831–842 checked on the REAL record: AQ2 and AQ3 hold, conditions 1–5 pass; carry fails (src differs
  since cdacc322), so R3 re-runs at J.

## Running (started 2026-10-17, detached; do not touch that worktree until it ends)
- The real journey at J = `8f85aa2f021e10391fd77a2a7569d10c2193bbb6`, in the clean detached worktree
  `.claude/worktrees/m07-journey-run` (M05's re-run refuses a dirty tree). Script and log:
  `.claude/worktrees/m07-journey-artifacts/run.sh`, `run.log` (last line `EXIT <code>`; 0 expected, 3 if a rung is
  UNSUPPORTED). Store and bundles: `m07-journey-artifacts/art/` (keep: replay needs `art/store`).
- Output: `m07-journey-run/benchmarks/m07/journey/8f85aa2…/` {journey.json, journey.md, m05/trust-region-study-real.*}.
- Env: `.claude/worktrees/m05/.venv-nlp` python, `OMP_NUM_THREADS=1`, `PYTHONPATH=src` only (J25: the nlp-test-tools
  path breaks the reactor env check).

## Next (in order)
1. When `run.log` ends: `check` the output dir; copy it into `wp/M07` at the same path.
2. Implement `replay` (A24): archive `art/store` as `<dir>/journey.experiments.json` with
   `m05_wo9_real.store_archive` (and make `run` write it); replay restores it, runner with
   `m05_wo9_real.RecordOnlyBackend(OutOfProcessBackend(variant), found)`, re-evaluates the record's evaluated R0/R1 points
   (no budget), R2, R3 from the committed M05 record (sha256 must match) + T* re-solve; compare every member bitwise
   except measured walls (`wall_s`) and the coupling digest; `experiments` must map cold→store_hit (replay cold 0).
   Refuse exit 2 `omp_num_threads differs` on a thread mismatch. Replace `test_replay_refuses_until_wo4`.
3. Tests: default gate from the committed record — `check` accepts; A22/A23 labels equal the reference generator's
   functions (`docs/derivations/scripts/m07_reference.py`); A20 nine R1 entries with J, e, quantities; A25 store-archive
   attempts = Σ R1 cold + t_star_resolve.cold; A26 every decision names a run sha256; A21 R3 re-run record tracked with
   the recorded sha256. Opt-in `@pytest.mark.pymrm`: replay bitwise.
4. Commit record + report + archive; J-entries; `docs/progress.md`; push `wp/M07`. Remove the run worktree after.
