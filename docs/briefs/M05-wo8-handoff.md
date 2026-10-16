# M05 WO-8 handoff (2026-10-16, wp/M05)

Done (commits on wp/M05 after 4c83d15):
- §19.2 fd_check float rules + `decision_stable_with_an_fd_check` GENERATED record (t08 --check 0, v2 unchanged).
- §19.1 `C1Parent(coupling_sink=)`; `tests/support/m05_replay.py` (G10 shape rule, integrity, content) + tests.
- `C1Parent(truth_class=)` (S46); `scripts/m05_wo8_runs.py` (cases TR-E2, TR-E2-FD, LOOP-R; `--replay`).
- Records committed: `benchmarks/m05/records/trust-region-study-{tr-e2-fd,loop-r}.*`.
- Build log S45-S52 with the measured numbers (docs/design/M05-build-decisions.md, "WO-8").

Gate results: G5 FAIL (TR-E2 TRF_MAX_ITERATIONS, theta 4.01e-4; F-15 reproduced), G6 FAIL (TRF_MAX_ITERATIONS;
fd_check passes), G9 FAIL (|T*-653.15| 1.067e-6 K > 1e-6), G10 PASS (3 replays, 0 differences),
G7 partial (request identity holds; store bijection not evaluated), G8 NOT RUN (S52).

Open, for the design lane (one ruling round):
1. F-15/G5/G6: TRF's theta sawtooth on C1 (S-log "Measured"). No limit raised.
2. G9's 1e-6 K vs Ipopt's interior distance (5.3e-8 scaled).
3. S51: store-hit budget charge vs `cold_used = trf_cold + parent_executions`; TR-E2 record parked in
   evidence/M05/wo8/artifacts/ (ignored) until ruled; then rerun `scripts/m05_wo8_runs.py TR-E2` (remove the old
   files first: the script refuses to overwrite) and commit.
4. S50: the FD check's requests are in no run and no budget.
5. S47, S49: assumption-block mapping; G9 "constant basis" read as R-277's affine basis.

Next executable action: LOOP-S work order (S52): SurrogateTruth (§6.4), surrogate link basis (§6.6, J1-J3
1e-14 check), stage-A runner + P2 reference (§7.3), M04 it1-prefix manifest on m04-synthetic-smooth-v1; then
`LOOP-S` case in the script and G8. Run: /tmp-free command
`PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1 PYTHONPATH=src:.reference-downloads/m03-ipopt/nlp-test-tools
.venv-nlp/bin/python scripts/m05_wo8_runs.py <CASE> [--replay]` (3-4 s each).
