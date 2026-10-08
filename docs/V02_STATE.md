# v0.2 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`. History:
`docs/V02_DECISIONS.md` (append-only).

| | |
| --- | --- |
| Objective | Plan v1.2 §4.4: M01–M07, the scientific reactor replacement; release gate W21–W27; release `0.2.0` |
| Chemistry | C1, the ammonia synthesis loop (ADR 0022, R-120); `docs/v02-real-chemistry-dossier.md`; reactor `ammonia_synthesis_reactor` `main` @ `6089593` (MIT) |
| Order | R-153: M01 design first; M06 built alongside; M03 when the critical path allows; pre-release `0.2.0a1` after M02 `tested`; `0.2.0` after M07 |
| Concurrency | At most 4 agents at a time (Frank, 2026-10-06) |
| Repository | Public `origin` only (R-150); pre-push guard installed; pushing to `origin` authorised (Frank, 2026-10-08) |

## Packages

| ID | Lead | Depends | Gate | Status |
| --- | --- | --- | --- | --- |
| M01 | Design | T08 | W22, W21 (part) | **tested, reviewed by the design lane (closure `9098f14`), merged into main `997c7da`**; ADR 0026 Accepted; ADR 0027 Proposed until M02's adapter halves |
| M02 | Build | M01 | W21 | WO-1…7 done (`6a46cdd`; G10 bitwise, re-recorded on variant v2); WO-8 rulings R-254…259 (`bfbad26`); WO-8 running; then WO-9…13 |
| M03 | Design | T08 | W24 (part) | complete; main merged in (`086bf2b`); CI green on both runners (`2ed3f22`); manifest → `tested` and merge when Frank answers N1 |
| M04 | Design | M02 | W23 | spec done; WO-1, 2, 3, 10 done (`7613b5e`, gate green); WO-4…9 after `wp/M02` (WO-7/8) is merged into `wp/M04`; WO-11 real run needs M02 WO-5 env (built) + Frank's N1 budget |
| M05 | Design | M03, M04 | W24 | design done; WO-2, 3 done (`dd9e364`; G2, G3, G4 (SYN-001/TR-E1), G13); WO-1 audit PASS (`wp/M05-audit` `a28d6a8`, to merge); rulings on omitted rows/scales asked; WO-4+ need M02 + M04 merged |
| M06 | Build | T08 | W26, W27 | **tested, reviewed by the design lane, merged into main `7473f35`**; ADR 0030 + ADR 0019 Amendment 3 Accepted; WO-17 (3 canaries + 45-run campaign) at M07 — needs v0.2 binder reading in `snapshot.READINGS`, M01/M02 id rows, U14 rewrite for campaign records, `specifier` read of registration §20 |
| M07 | Design | M05, M06 | W25, W21–W27 | not started |

## Milestone 0 (housekeeping)

- [x] Web-shell design inputs ported from `design/web-shell-brief` (pre-0.1.0 base, cannot be pushed) onto `main`
- [x] Frank's K_NH₃ decision (R-152), the order (R-153), the dossier statement
- [x] `ci.yml` actions pinned by SHA (`67029fa`; 44 lines; inputs checked against the new majors; test added)
- [x] T08 close-out review (`docs/reviews/T08-closeout-review.md`): all five confirmed, no must-fix; F1/F2/N1/N2/N5 applied as T08 spec Amendment R8
- [ ] **F3 hand-on:** T08's own manifest (58 limitations, 16 without L/U id; A70, B23) is an input to v0.2's support-envelope harvest
- [ ] Schema `$id` move (deferred to v0.2 by ADR; R-149) — with M01's or M06's first schema change

## Open inputs (M01, dossier `needs_fact`)

PR parameter set (T_c, P_c, ω, c_p, ΔH_f per value from open, cited sources: `chemicals`/`thermo`, cross-checked
with CoolProp or Cantera; group database a cross-check only); a cited k_ij source; high-pressure NH₃–H₂–N₂ VLE data;
the loop's pressure-drop convention (ADR 0022 D2); whether the reactor keeps its own fugacity correlations or takes
PR's. K_NH₃ settled (R-152: the code's 7000 cal/mol).

## Needs Frank

- **M03 N1:** accept the licences of an optional, non-default `nlp` extra; the [A10] audit (PASS, `docs/m03-ipopt-audit.md`
  on `wp/M03-audit`) found exactly: EPL-2.0 (Ipopt, cyipopt), CeCILL-C (MUMPS, Scotch), public domain (PORD, SQLite),
  Apache-2.0 (METIS 5, OpenSSL), Apache-2.0 WITH LLVM-exception (libomp), BSD-3 (OpenBLAS, SPRAL, hwloc, libuuid,
  Pyomo), ASL BSD-3 + f2c notice, MIT (libxml2, libffi), **LGPL-2.1-only** (libiconv), **GPL-3.0 WITH GCC RLE from
  conda-forge** (libstdc++, libgcc_s, libgfortran, libquadmath), PSF-2.0, bzip2, 0BSD, BSD-2, Zlib. Default: accept;
  without it W24's M03 optimizer part stays BLOCKED.

- **M01 (defaults set, work proceeds):** Q-F1 the reactor's inlet heat loss (23–33 % of reaction heat through the
  inlet face) — intended, or Danckwerts? default: as pinned, reported; Q-N1 c_p source — default NASA TM-4513, not
  Poling; Q-N2 fix F-R1/F-R2 upstream at a new pin? default: keep `6089593` + subclass/overlay; Q-N3 design grid —
  default num_z = 800 (~9 s/solve); Q-N4 ship the real C1 records in the wheel — default yes, with citations; Q-N5
  a structured `synthetic` field in ModelManifest — default no schema change in v0.2.

- **W27 (defaults set):** Q3 up to 3 re-canaries within the approved budget; Q4 agent false verification reported
  with its bound, not gated; Q5 run the approved 45 even if 0 cases are candidates (alternative: 15 runs).

- **M02 (defaults set):** N1 accept "not a sandbox" (`external-subprocess-v1`) for local v0.2 use; N2 no CI job for
  the reactor environment; N3 `v0.2-alpha-gate-v1` = v0.1 gate unchanged + W21, W22 met, no other claims (for
  `0.2.0a1`); N4 ship the synthetic stand-in, listed synthetic; N5 defer the PR LIQUID regime and pure-NH₃ flash;
  N6 no reactor warm start.

- **M03 threading (new):** make single-threaded BLAS/OpenMP (`OMP_NUM_THREADS=1`) a product rule for NLP runs?
  Default: recommended and recorded in every report, not enforced (it is reproducible and faster: 1.7 s vs 3.2–3.9 s).

- **M04 (defaults set):** N1 experiment budget — 632 cold reactor runs for iteration 1 and up to two more. **Corrected
  2026-10-08:** a real evaluation takes 25–45 s (not 9 s), so iteration 1 ≈ 4.4–7.9 h and three iterations ≈ 12–20 h of
  local compute; N2 width limits 0.0025 in conversion, 1.5 K; N3 gradient limit 0.25; N6 M04 counts as `tested`
  whatever the real verdict, and M05 uses the parent model if the surrogate is not promotable.

- **`0.2.0a1` (alpha gate, ADR 0028; defaults set):** N3 claim set = V11–V20 re-judged + W21 + W22, W23–W27 not
  claimed; carry the V14(b) FAIL acceptance into this release (dated after the alpha verdict); **carry V17 across the
  surface changes R-192/R-234** as R-133 did (alternative: a new agent campaign, ≈USD 10); accept M02 N1 "not a sandbox"
  for a published release; W21(f) read as adapter-reproduces-standalone + group tests + error travels + published
  validation cited (the stronger reading would BLOCK W21 on the 4TU data statement); publish via release.yml with your
  approval, marked pre-release. Preferences on defaults: cut `C_α` before M03 merges; freeze distribution paths from
  `C_α` to dispatch.

- **M05 (defaults set):** N-F1 objective = maximize liquid NH₃ product, reactor inlet T the only decision (alt: an
  economic objective with your prices, making purge a second decision); N-F2 decision tolerance 0.5 K; N-F3 real-reactor
  budget 400 experiments / 4 h; N-F6 decision box [643.15, 733.15] K.

Otherwise nothing open. Answered 2026-10-08: Amendment 3 approved; W27 spend (45 runs, USD 15–45) approved; pushing to
`origin` authorised. Earlier: F2 agent model = most recent, pinned by ID; F3 fonts system; F4 scenario = run comparison;
F5 education mode deferred.

## Next action

Resumed 2026-10-08 (Frank: "start working to get to v0.2.0", at most 4 agents).

| Agent | Package / WO | Branch (worktree under `.claude/worktrees/`) |
| --- | --- | --- |
| `opus-engineer` | M02 WO-8.1…8.5 (PR units, verifier forms) | `wp/M02` (`m02`) |
| `architect` | M05 rulings (omitted rows, G4 scales) | `wp/M05` (`m05`) |

Done today: M06 WO-1…6, WO-14…16 (all merged into `wp/M06-build`; R-192…R-194; W27 Tier 1 approval recorded), the M01 and M03 specifications, M03 WO-0…3 and WO-6 (Ipopt audit PASS, merged into `wp/M03`).
Next free slot: `reviewer` M01 after Amendment 1, then M01 WO-7 manifest → merge → M02 design; then M03 spec amendment round (batched);
M03 WO-8 after N1; M06 WO-11…13. In worktrees run the gate with `PYTHONPATH=$PWD/src PATH=<main>/.venv/bin:$PATH ./scripts/check.sh`.
Push `main` at milestones (authorised).
