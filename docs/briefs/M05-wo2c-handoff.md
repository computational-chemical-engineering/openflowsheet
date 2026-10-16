# M05 handoff after WO-2c, WO-6b, S33, WO-7b and the M04 merge (2026-10-16)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05`, branch `wp/M05`. Stopped at the ~150k context cap.

## Done (commits on wp/M05)
- `75cdc3b` merge `origin/wp/M05-rulings2` (§18 rulings, R-326..R-330); register conflict resolved as a union
  (R-301..R-318 from HEAD, then R-326..R-330).
- `05e2dba` WO-2c, `M05-zero-flow-v2` (§18.1, R-326). SYN-001 P1/P2 (S3 vapor) and B2 (S4 vapor): one certified
  4 × 4 block each, rcond 7.663e-3 / 1.417e-2 / 5.203e-6; 15 strict xfails pass unmarked; G4 at P1/P2/B2 passes
  (worst residual 5.92e-4, Jacobian 7.11e-7, decision 2.30e-3, joint 0.0). Inertness: dumps byte-identical
  before/after for C1 TR-E2 S0 and perturbed, TR-E1, link toy, AT, SYN-001 P3/B1/B3. Build log S27–S31.
- `442eed1` WO-6b (§18.2 R-327, S15, S16 holder part, S18). Build log S32–S36; S33 and S36 OPEN (see the log).
- Gate: at the WO-2c tree, 8786 passed / 31 skipped (one mypy error, fixed before the commit); nlp tier 164 passed,
  1 skipped. The gate at the pushed head is in the caller's report.

## Done since (second engineer)
- `899cc2b` S33 (build log S37): the basis is formed inside the holders' run; per-run `basis_fd_point` = n_in; run
  document and TRF-phase ledger byte-identical on the FD link toy. Gate 8790 passed / 31 skipped.
- `ce86c03` S36 (S38): half-width `minimum: 0`. `733cf8a` WO-7b (S39–S42): closed schema, S12, S13, S15, S18, the
  G12 checker. Gate at 733cf8a: 8889 passed / 31 skipped.
- `d65a9a4` merge origin/main (32ceea5, contains M04 78685cc). Gate: 1 failed (S43, OPEN), 9186 passed, 31 skipped;
  nlp tier 167 passed, 1 skipped.

## Next actions, in order
1. **S43** (design lane): M04's no-`application`-imports rule for `studies` vs the trust-region parent adapter. Until
   it is ruled, the full gate on wp/M05 has that one failure.
2. Review batch: S27–S30, S32–S43 (S40 classifies `coupling_record_sha256` exact_sha256: replay identity).
3. WO-5c, then WO-8 (real runs). WO-8 gap (S-log WO-7b): `fd_check`'s floats have no float rule yet.

## Superseded next actions (kept for the record)
1. **WO-7b** (bounded): brief at `docs/briefs/M05-wo7b-brief.md` (closed schema S14, S12, S13, S15, S16 identity
   checker for G12, S18, mutation tests). The minimal schema declarations for WO-6b's fields are already in.
2. **Merge `origin/main` into wp/M05**: `78685cc` (M04) is now an ancestor of origin/main (`4662ff8`). Merge, gate
   (default gate with the W27 link, then `scripts/m03_nlp_check.sh --no-inventory .venv-nlp
   .reference-downloads/m03-ipopt -- tests/`), push.
3. WO-8 (the real runs) needs WO-2c, WO-6b, WO-7b and WO-5c. Before it, decide S33 (basis requests carry no run, so
   §8.3's per-run `basis_fd_point` = n_in cannot hold as built).

## Open questions for the review batch
- S33: attribute the affine basis's requests to the run (default) or read them by stage.
- S36: S15's "half-width > 0" vs an exact 0.0 for a zero-noise parent; default schema `minimum: 0`.
- S27–S30, S32, S34, S35: build choices (numerical incidence of `y`/`w` columns by their own partial; persistence
  coordinates; §17.1 (e)'s toy now `joint_not_square`; block numbering; PMP flag definition).

## Notes
- `scripts/m03_nlp_check.sh --no-inventory` needs the prefix and cache given explicitly before `--`.
- The Z6 inertness dump script used for WO-2c (e) was a scratch script; to redo it, dump per projection the source
  map (less `zero_blocks`), every active constraint's expression and value at x₀ in hex, variables with bounds and
  values, suffixes and the component list, at the parent commit and at the change, and `cmp` the files.
