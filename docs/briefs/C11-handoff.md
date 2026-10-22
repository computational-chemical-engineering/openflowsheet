# C11 (S06) — design-step handoff (specifier, 2026-10-22)

Branch `wp/C11` (worktree `/home/user/ofs-c11`). Design step of S06 delivered; build step not started.

**Delivered.** `docs/derivations/S06-spec.md` (kinds, rows, DOF, band, refusals I1–I6, solve path, unreached report,
acceptance, cases, A01–A16, WO-1/WO-2, manifest list, non-claims); `docs/derivations/scripts/s06_reference.py` +
`s06_reference.json` (imports the S02 generator; four worker processes); `docs/C11_DECISIONS.md` (9 DECISION lines);
register R-601 to R-607; Frank questions Q-S06-1, Q-S06-2.

**Key facts measured.** J1–J8 and four matched M1 sets reach λ = 1 on the straight 16-step path from S02's endpoint.
U1 (ill-conditioned endpoint) and U2 (negative reflux `φ` on the path) have regular roots (M2's) but are not reached:
registered typed failures (A11, two branches). First candidates J2 (0.97, 0.55), J4 (0.85, 0.50) and matched
(recovery A, recovery C) were replaced; see spec §7.2.

**Next executable action.** Build lane, WO-1 (`opus-engineer`, `models/syn001/column.py`): spec §12. Then WO-2.
`s06_reference.py --check` takes about 2.5 minutes on four cores; run it in the background.

**Open.** Spec §15 (needs-a-fact items 1–4 are WO-2 measurements; 5–6 are Frank's, defaults set; 7 is a later package).
No ADR written (ADR 0046 free); §16 records the two formulations that would have needed one.
