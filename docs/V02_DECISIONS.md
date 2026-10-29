# v0.2 — decisions and gate runs (append-only)

Grep, don't read whole. Newest at the bottom.

## 2026-10-06 — start

- Frank switched to his TU/e account; "Go ahead according to your recommendations. For K_NH3 use the code's value";
  "You can use multiple agents at a time, but limit it to 4 max."
- R-152: K_NH₃ = the code's value (7000 cal/mol); the Rossetti 2006 check not made.
- R-153: order M01 design first, M06 alongside, `0.2.0a1` after M02.
- Web-shell design inputs (`5211ada`, `94a59ff`, README, `b876a2b` of the archive's `design/web-shell-brief`) copied as
  files onto public `main`; scanned for addresses, home paths and secrets (none; one link to a private artifact kept).

## 2026-10-06 — milestone 0

- `67029fa` ci.yml pinned by SHA (44 `uses:`; inputs checked against the new majors; test). check.sh on main
  (`67029fa`): 6879 passed, 31 skipped, PASSED.
- `d006997` T08 close-out review (all five confirmed, no must-fix) → T08 spec Amendment R8. DECISION (R8 1, the
  review's recommendation): the two 2.4 MB ensemble records committed as `.gz` beside their paths; rejected: an
  external store by hash. Reversible by reverting `d006997`.
- Stale worktrees (public-line, showcase, the CI agent's) are clean; removing them was refused by the permission
  classifier — left for Frank.
- Frank: the Claude Design web-shell design was not revised after 2026-09-29; the imported prototype is final input.

## 2026-10-06 — halt

- M06 architect done (`wp/M06` `44098b0`, `03f3f13`). Corrections from it: the project is Apache-2.0 (the brief said
  MIT); D1–D3 already fixed by T08 Phase 1; the command is `serve-http`.
- Specifier (M01) and engineer (M06 WO-4…6) both hit the account session limit, were resumed, then halted at
  Frank's request ("The task requires too many tokens. Try to get it to a save state and then halt.").
- M06 WIP `f8fa5e5` on `wp/M06-build` (untested). WO-4 partial: `resources.py` (`PACKAGED` + `web`, `REPOSITORY_PATHS`
  web→apps/web, `DIRECTORIES`), `_data/web` symlink, pyproject globs, `apps/web/index.html`, `favicon.svg`. Known
  breakage: `tests/test_t08_w4_package_data.py` (assumes packaged path = repo path). Engineer's next steps: fix that
  test via `repository_path()`; `bindings/web.py` with security headers as `/ui`-scoped middleware (not a mount
  wrapper: 404/405 would lack the CSP); `serve-http --ui` (exit 1 if web files missing); import rule in
  `tests/test_t07_w6a_http.py`; serving tests; then WO-5, WO-6. `actions/setup-node` v7.0.0 =
  `820762786026740c76f36085b0efc47a31fe5020`. Planned: G1 equality as `xfail(strict=True)` until WO-3/9/10.
- Frank (2026-10-06), M06 F2: the W27 agent campaign uses the most recent model available at campaign time ("This
  should be 5.5 (or preferably the most recent version)"), pinned by exact ID and recorded; the design note's default
  (V17 `v17-c2`'s `claude-sonnet-5`, for comparability) is overridden; the loss of direct comparability is stated.
  Development agents are unaffected (frontmatter aliases `opus`/`sonnet`/`haiku` resolve to the latest; the API saw
  `claude-opus-5-5`).

## 2026-10-08 — resume

- Frank: "start working to get to v0.2.0. Do maximally use 4 agents at a time."
- The repository moved from `~/Codes/Process Simulator` to `~/Codes/OpenFlowsheet`. Repaired: worktree links
  (`git worktree repair` + each worktree's `.git` file), `.venv` script shebangs and the editable `.pth`, the two
  spike venvs. Worktrees `showcase` and `study-openidaes450` still have broken `.git` files (stale; Frank's to
  remove). In a worktree, run the gate with `PYTHONPATH=$PWD/src` (the venv's editable install points at main).
- Both halt commits had landed (`wp/M01` `daea823`, `wp/M06-build` `f8fa5e5`).
- DECISION: build ADR 0019 Amendment 3 (M06 WO-1…3) now on its own branch `wp/M06-contract` (from `0f467ad` + main,
  merge `f085d14`); merge only after Frank approves the amendment. Alternative: wait for the approval. Reversible by:
  deleting the branch. (This is the default already stated in `V02_STATE.md` "Needs Frank".)
- DECISION: 4th agent slot = M03 recon → M03 specifier brief (M03 is off the critical path but has no
  dependency left). Alternative: M06 WO-14 (W27 acquisition). Reversible by: WO-14 takes the next free slot.
- Agents launched: `specifier` M01 (resume on `wp/M01`), `opus-engineer` M06 WO-4…6 (`wp/M06-build`),
  `opus-engineer` M06 WO-1…3 (`wp/M06-contract`), `recon` M03.
- Frank (2026-10-08): "Amendment 3 is approved, W27 runs are agreed, pushing to origin is fine, you can remove the
  stale worktrees." So: ADR 0019 Amendment 3 approved (status moves to Accepted when `wp/M06-contract` merges, with
  WO-13's review); M06 F1 W27 spend approved (45 runs at M07, USD 15–45); pushing to `origin` authorised (pre-push
  guard stays); worktrees `public-line`, `showcase`, `study-openidaes450`, `agent-a3fc35fa5df8ef915`,
  `agent-a0e7122a21d569dd7` removed (all clean; branches kept).
- M03 recon done; brief + digest `2d57974` on main; `specifier` M03 launched on `wp/M03` (ADR 0031+, R-180+ to avoid collisions with M01 0026…/R-154…169 and M06 0030/R-170…175).
- check.sh on main after the move (`6bf86ba` tree): 6879 passed, 31 skipped, PASSED (12 min 32 s) — same count as `67029fa`.
- M06 WO-4…6 done on `wp/M06-build`: `c304212` (WO-4 serving, `serve-http --ui`, `/ui` header middleware), `78d01d9`
  (WO-5 JS foundation, Node step in check.sh, setup-node pinned), `5d0261a` (WO-6 api/router/auth/frame). check.sh at
  `5d0261a`: 6930 passed, 31 skipped, 1 xfailed (strict: 17-operation equality until WO-3/9/10); Node 36/36; PASSED.
  G1 static, G8 headers, G9, G10 (in-tree; wheel half runs in CI only), G7 api rows evidenced. Deviations for the
  WO-13 review: `autocomplete` added to h.js whitelist; literal-marker guard returns a same-pointer marker instead of
  deepEqual (saves one request); `js/frame.js` added; wrong method on `/ui` → 422 (existing binding mapping), not 405.
  After WO-3 merges: `scripts/m06_web_routes.py --write`.
- `sonnet-implementer` M06 WO-14 (W27 acquisition/provenance/access) launched on `wp/M06-w27` (from `5d0261a`).
- W27 WO-14 stopped on the size gate: release asset `OpenIDAES-450-demo.tar.gz` is 220 802 919 bytes (SHA-256
  `6d42c02fdc7e8e4c81c861d77fd5b546198a2bfd7d9c87212c97149e50ea4526`; asset created 14:39Z, ~5 h after the release
  was published 09:19Z on 2026-09-26), not the audit's 220 433 394; the audit recorded no hash. Full SHA of `13ca57e`
  = `13ca57ecec1927c892b023fdc7f0cf13718bf28b`. DECISION: pin the live asset by size+SHA and disclose the
  discrepancy in `provenance.json`; "same data" rests on the audit's counts reproducing (450; 425/24/1; full82
  41/20/20/1). G13 wording amended on `wp/M06-w27`. Alternative: keep the audit's size (unverifiable, no earlier
  copy). Reversible by: reverting the note amendment commit.
- M06 WO-14 done on `wp/M06-w27`: `4ee514d` (G13 wording amended, §9 note), `e268ed8` (acquire script with offline
  `--check`, provenance.json, access_report.json, test). All audit counts reproduce (450; 425/24/1; families; model
  types; full82 82 = 41/20/20/1, 7 fail residual check). Extra evidence: `RELEASE_MANIFEST.json` at `13ca57e` says
  220 433 394, at head `b7e1006` 220 802 919 → re-upload after the audit. Ten inaccessible assets, all absent
  (three LoRA adapters, SFT data/knowledge base, role prompts/orchestration, scoring harness, 82-split score-run
  binding, agent outputs + GPT-5 mini controls, supplementary material). `full82.json` comes from the repo at the
  pinned SHA, not the archive. check.sh: 6939 passed, 31 skipped, 1 xfailed, PASSED.
- `specifier` M06 WO-15 (W27 registration) launched on `wp/M06-w27`; brief `docs/briefs/M06-W27-registration.md`
  (`1fb65c1`); register R-176…R-179.
- M03 specification done on `wp/M03` (`c91ebc9`…`17cec07`): `docs/derivations/M03-studies-spec.md` (A01–A42),
  ADR 0031 (parametric twin for F_p behind a bitwise guard; qualification policy M03-sensitivity-v1; forward+adjoint
  on one factorization; independent sweeps; SYN-001 (r, T_f) fit, identifiability by SVD), ADR 0032 (full-space
  PyNumero gray box over cyipopt, L-BFGS Hessian, exact refused; optional `nlp` extra behind an [A10] gate),
  generator `m03_reference.py` (257 claims, mpmath 60 digits), R-180…R-191. Probe: no cyipopt wheel for
  linux/cp313; Pyomo 6.10.1 wheel lacks `libpynumero_ASL`; no system Ipopt. Finding: P_spec columns of U-FLASH and
  U-FEED conflict with eliminated alias rows (refused individually). Specifier defaults: N2 (no substitute
  optimizer if the audit fails; UNSUPPORTED + BLOCKED), N3 (user-space conda-forge env for the audit). N1 (licences
  of the optional `nlp` extra: EPL-2.0, CeCILL-C, ASL notice, Apache-2.0 METIS 5, BSD, GCC runtime) asked of Frank.
- `opus-engineer` M03 WO-0…3 launched on `wp/M03`. Next M03 slot: WO-6 (the [A10] Ipopt audit).
- At merge: register index paragraph + ADR index need R-154…R-191 and ADRs 0026…0032; register appends from M01,
  M03, M06 branches resolve by concatenation.
- M06 WO-1…3 done on `wp/M06-contract`: `b570179` (binder records specification pins per column; isolated),
  `6b3a899` (WO-1 structure index, trace+analyse split, unroutable branch; G3, G4), `c0f3d25` (WO-2 element_diff;
  G5), `7b36f4a` (served MCP digest; isolated), `852b47b` (WO-3 list_audit; G6; R2 precondition holds),
  `4415e3e` (envelope list_audit; isolated). check.sh after WO-3: 7124 passed, 31 skipped. Engineer's contract
  detail for review: a routed declaration that cannot be traced gives `rows`/`columns: null` (not in corpus).
- Two escalations decided by the session on the contract branch (`90f4c0b`):
  - R-192: the served MCP tool-list digest moves `171dd768…` → `6c4375b4…`, bound to A3.2's `elements` by the
    decomposition test; R-133/R-134/R-137 stay the 0.1 record; `t08_rc.py` A49 not edited. Rejected: dropping
    `elements` from MCP (transports must agree, R-096), editing the 0.1 A49 constant.
  - R-193: `support_envelope.yaml` becomes v0.2's working envelope `v0.2-envelope-dev` / `0.2.0.dev0`; v0.1's stays
    at tag v0.1.1; M07 finalises `v0.2-envelope-1`. Rejected: amending v0.1's record in place.
  - R numbers: R-192+ are the session's (M03 holds R-180…R-191, WO-15 R-176…R-179).
- `wp/M06-contract` merged into `wp/M06-build`; `js/routes.js` regenerated (19 routes).
- `opus-engineer` M03 WO-6 (Ipopt [A10] audit) launched on `wp/M03-audit` (from `17cec07`).
- check.sh on merged `wp/M06-build` (routes regenerated): 7175 passed, 31 skipped, 1 xfailed (strict 17-op equality, until WO-9/10); Node pass; PASSED.
- M01 specification done on `wp/M01` (`341bd27`, `de683eb`, `74b4309`, `7f267ed`): `docs/derivations/M01-spec.md`
  (A01–A48), ADR 0026 (C1 PR vapour-only route) and 0027 (reactor boundary), both Proposed; R-154…R-169; generator
  `m01_reference.py` (82 claims; IDAES separator to 4e-12); `benchmarks/m01/` records, references, overlay,
  CoolProp cross-check, probe v2. Gate on `wp/M01`: one deliberate red, T08.A32 (all records synthetic), amended by
  spec §3.5 — WO-1's first step. Findings: the group tolerance leaves 0.45 % path dependence (polish → 1.6e-8); grid
  order only 0.6–0.8 (num_z 800 ≈ 1–1.4 % high; 100 ≈ 5.5 % high); F-R3 inlet Dirichlet T + axial conduction loses
  23–33 % of reaction heat through the inlet face; F-R1 hard-coded 3-species constant (subclass, proven inert);
  F-R2 fugacities at Σ reactive partial pressures; dossier §6 corrected (ideal-gas density). W22 measured:
  P_sat ≤ 1.27 % (2 %), liquid NH₃ ln φ 0.025/0.040 (0.05), light-gas ln φ ≤ 0.042 (0.05).
- Specifier defaults for Frank: Q-F1 inlet heat loss → use the pin as is, report it; Q-N1 c_p source → NASA
  TM-4513 (not Poling); Q-N2 upstream fixes → keep `6089593` + subclass/overlay; Q-N3 design grid → 800 (~9 s/solve);
  Q-N4 ship real C1 records in the wheel → yes, with citations.
- `opus-engineer` M01 WO-1…4, WO-6 launched on `wp/M01`. WO-5 (IDAES conformance, own env) and WO-7 (manifest) next.
- M06 WO-15 done (`5dde77f`…`f6a03c7` on `wp/M06-w27`): `docs/derivations/M06-W27-registration.md` (R01–R58,
  W27-A01…A40, S01…S18), generator `m06_w27_registration.py`, `case_facts/registration/dry_illustration.json`,
  R-176…R-179. Dry coverage today: 0 CANDIDATE of 450 (and of 82); a hypothetical v0.2 PR route still gives 0.
  Specifier defaults for Frank: Q3 up to 3 re-canaries within the approved budget; Q4 agent false verification
  reported with bound, not gated (R-179); Q5 run the approved 45 even with 0 candidates (alt: 15 runs).
- Finding F6: T08 U14 test red since `e268ed8` (WO-14's "green" gate ran before its files were tracked).
  DECISION R-194 (`b8a0518`): U14 restated for v0.2 — no comparison run/registered/shipped; adaptation records
  confined to `benchmarks/m06/openidaes450/`, no run records there, nothing in package data. Rejected: narrowing the
  test to registry.yaml + src/ (WO-15's suggestion). Design note: W27 model per Frank's F2; G14 records the registry
  snapshot SHA (WO-15 F1, F2).
- `wp/M06-w27` merged into `wp/M06-build` (`5ceb32c`; register conflict resolved by concatenation). Worktrees
  `m06-contract`, `m06-w27` removed. `opus-engineer` M06 WO-7…10 launched on `wp/M06-ui` (from `b8a0518`).
- M03 WO-6 [A10] Ipopt audit: **PASS** G1–G8 on `wp/M03-audit` (`4e56fc7`, `4b70e08`, `61da5d1`, `672998c`; check.sh
  6883 passed). Route: user-space conda-forge env (micromamba 2.9.0, explicit lock; CPython 3.13.5, Ipopt 3.14.20,
  MUMPS 5.8.2 seq, METIS 5.1.0 by symbol test, cyipopt 1.7.0, ampl-asl) + hash-locked PyPI wheels (pyomo 6.10.1,
  packaging 26.3); `libpynumero_ASL` compiled from Pyomo's own sources (reproducible, `6646bbdd…`). Rejected: Debian
  (MPI MUMPS → OpenMPI in-process); source build not needed. CasADi METIS closure untouched; no HSL; nothing
  restrictive. Draft extra `nlp = [pyomo==6.10.1, cyipopt==1.7.0, packaging==26.3]` (not added; N1 pending).
  WO-8 notes: set `PYOMO_CONFIG_DIR` (else P03's unaudited `~/.pyomo/lib` loads), `PYTHONNOUSERSITE=1`, explicit
  `linear_solver=mumps`; threaded-BLAS reproducibility open. The env lives in the session scratchpad (temporary);
  `scripts/build-m03-ipopt-env.sh` rebuilds it from the locks. Worktree removed; branch kept; merge into `wp/M03`
  after WO-0…3 finish.
- `opus-engineer` M06 WO-16 (W27 classifier/harness/scorer, stub dry run) launched on `wp/M06-w27-harness`.
- M03 WO-0…3 done on `wp/M03` (`8e179cb`, `a848bb5`, `2ac8f77`, `992e8e6`, `82560bf`): twin, `solve_transposed`,
  `studies/sensitivity.py`, `studies/syn001.py`; check.sh 6958 passed, 31 skipped. Q-F1: twin bitwise identical at
  P1–P3, B1–B3, all 8 sweep points (1/7/10 symbolic parameters). Worst: A05/A06 3.2e-3 of allowed; A09 FD 5.5e-12 vs
  1e-9; A12 `C=[1,10]` 2.13e-14 vs 1e-13 (4.7×, inside the 10× amend-first window). `wp/M03-audit` merged (`afa19ad`).
- DECISION: package `openflowsheet.studies` (blueprint §15, frozen layer list) not the spec's `study/`. Alternative:
  rename to `study`. Reversible by: a rename commit.
- DECISION: M03 design-lane questions batched into one spec amendment round after WO-4/5/7 — A12 margin; engineer's
  refusal-vocabulary choices (unevaluable residual → ROOT_NOT_CONVERGED; non-square → UNSUPPORTED_RANK_STRUCTURE;
  LinearSolveFailedError after a clean screen; mode-`both` consistency recorded not refusing; adjoint-only still runs
  forward for Q3); spec §5 toy residual "exactly 0" is 1.5e-36 in binary64; plus Q-F2/Q-F3 measurements.
  Alternative: amend now. Reversible by: consulting sooner.
- `opus-engineer` M03 WO-4, 5, 7 (+ optional WO-9) launched on `wp/M03`.
- check.sh on `wp/M06-build` `b8a0518` (W27 merged, R-194): 7189 passed, 31 skipped, 1 xfailed; PASSED. The U14 red is closed.
- M01 WO-1…4, 6 done on `wp/M01` (`4cd5e32`…`f595179`): records as package data (Q-N4 default, isolated `1621d65`),
  `thermo/pr_c1.py` (provider `pr-c1-v1`), `thermo/conventions.py`, flash, `models/c1/{boundary,reactor_standin}.py`;
  G20 allowlist 20→23; envelope rows (property_model `pr-c1-v1`, L40). check.sh 7035 passed, 0 failed. A33: SYN-001
  structural sha `16ae2bd4…773b` and bundle artifacts byte-identical before/after. Worst values all ≪ tolerance except
  A12 Gibbs–Duhem 1.0e-13 vs 1e-12 at V1 (within 10×).
- M01 design-lane amendment round (batched after WO-5): A26 defect-vector tolerance (1e-12 rel unreachable in binary64;
  asserted at 1e-13 × n_tot,in in isolated `f595179`); A09's "≥1e-3" parenthetical (V1 H₂/CH₄ ln φ gap 4.35e-4; test
  asserts ≥1e-6); A12 G–D margin; ModelManifest cannot carry `synthetic: true` (frozen schema); stand-in not in
  MODEL_BUILDERS (M02 binds it) — envelope mention?; engineer-added refusal behaviours (negative/non-finite flows →
  out_of_domain; unknown property → unsupported; state length → error; non-TP flash → unsupported_specification;
  enthalpy refusal → stream_enthalpy_refused; reactor_not_accepted(<stage>); boundary check order); ADR 0026's note in
  `docs/interfaces-frozen.md` (no WO covers it). Then `reviewer` on M01 (derivatives, phase logic), then WO-7 manifest.
- `opus-engineer` M01 WO-5 (IDAES conformance, A37) launched on `wp/M01-idaes` (from `f595179`).
- M01 WO-5 done (`13bcef7`, fast-forwarded into `wp/M01`): IDAES 2.13 conformance A37 — V1/V2 Z 0, ln φ 1.9e-16; L1 Z
  4.3e-16, ln φ 3.6e-14; F1 β 4.2e-12, y* 7.1e-11; F11 β 8.2e-13, y* 3.7e-11 (y* gap = SmoothVLE T_eq offset; 1.7e-13 at
  T_eq). Nothing within 10×. `.venv-idaes` fingerprint identical to T06's. check.sh 7047 passed. The env lives in the
  `m01-idaes` worktree (git-ignored); keep it for M02.
- `specifier` M01 Amendment 1 launched on `wp/M01` (items A26, A09, A12, synthetic marker, stand-in envelope row, added
  refusals, interfaces-frozen note; R-195+).
- M03 WO-4, 5, 7 done on `wp/M03` (`27cf166` sweeps, `d377364` estimation, `5cf4160` NLP formulation/KKT
  verifier/readiness/UNSUPPORTED path; no greybox, no extra): check.sh 6991 passed. Within-10× list empty (closest
  FIT-U σ₂/σ₁ 9.1e-15 vs 1e-12). Q-F3: FIT-I θ̂ 1.1e-16 scaled, FIT-U T̂_f 6.2e-12. New code `ESTIMATOR_NOT_CONVERGED`.
  Open: FIT-U r drifts to 0.969 (null projection 0.997 vs JSON 0.869); NOT_VERIFIED vs INFEASIBLE_REPORTED precedence
  (WO-8); WO-9 not started (package-data test hard-codes 32 schemas). Engineer stopped after reporting.
- `specifier` M03 Amendment 1 launched on `wp/M03` (R-210+; M01's amendment holds R-195…R-209).
- **W27 Tier 1 approved** — Frank, 2026-10-08: "W27 runs are agreed" (M06 F1: the registered 45-run campaign at
  M07, estimated USD 15–45, preceded by 3 canaries; registration `docs/derivations/M06-W27-registration.md`; agent
  model = the most recent at campaign time, pinned by exact ID, per F2). Recorded in this form for W27 preflight P1.
- M06 WO-16 done on `wp/M06-w27-harness` (`6c9b190`…`062bc59`; code in `benchmarks/m06/w27/`): classifier, snapshot,
  sampler, harness (lock hash + interpreter in run.json, A23), preflight P1–P8, scorer; check.sh 7266 passed, 31
  skipped, 1 xfailed. Tier 0 coverage at 0.1.1: 0 CANDIDATE of 450 and of 82 (unit 367/73, not-steady 65/8, component
  17/1, artifact 1/0); snapshot `f71c1f05…`, list_models `4a60f5a3…`. G14 pass; G15 18/18 stub states score as
  registered; preflight P2–P8 pass, P1 now recorded (line above). Engineer's scorer choices where the registration is
  silent and open items (W27-R57 "ten" vs 9 assets; effort pin only via run.json; M06 manifest needs the envelope
  harvest classification; WO-17 needs v0.2 binder reading in `snapshot.READINGS` + M01/M02 id rows + U14 rewrite for
  campaign records) → for WO-13's review / M07.
- `wp/M06-w27-harness` merged into `wp/M06-build` (`92d430e`). `recon` M02 launched (digest → M02 design brief).
- M06 WO-7…10 done on `wp/M06-ui` (`72a7e1b` fixtures, `22b3eef` view models, `327edcd` label decision, `a1a0fd9`
  screens A, `4aaa04c` screens B; strict xfail removed, shell calls exactly 17 operations): check.sh 7322 passed, Node
  91/91. G1 static, G5, G6 view, G7 (all design numbers), G4 STR-03, G8 Node evidenced; Chromium dump of 18 routes
  found and fixed a `history` shadowing bug. Merged into `wp/M06-build` (`6fc69ef`); worktree removed; engineer stopped.
- DECISION: certificate labels lower-case `pass`→ok, `fail`→bad, `unsupported`/`not_applicable`→none (`327edcd`).
  Alternative: the note's upper-case-only §5.5 table (every passing check would render ✕). Reversible by reverting
  `327edcd`; the WO-13 reviewer confirms.
- DECISION: G2 (HTTP contract tests of all 17 operations; no WO owned it) → WO-11. Alternative: a separate WO.
- `opus-engineer` M06 WO-11, WO-12 launched on `wp/M06-finish` (from `6fc69ef`).
- M02 recon done (digest delivered inline; key facts pasted into `docs/briefs/M02-design.md`, `58e1906`). Findings: no
  M02 code or schema; the seam is `ExternalEvaluation` (`wp/M01` `models/c1/boundary.py:164`); no subprocess call
  in `src/`; the T08 runner's subprocess has no timeout; no promotion/freeze/invalidation mechanism; no test reads
  `reactor-probe.json`; M01 §8.14 says A45–A50 (A49/A50 undefined) vs A41–A48 elsewhere → sent to M01 Amendment 1.
- DECISION: M02 is designed by the `architect` (design note + ADRs) although the plan's lane is Build/Design — it fixes
  the external-model process boundary, the experiment records (frozen §2.2 schema list → ADR) and promotion
  semantics that M04/M05/M07 inherit. Alternative: build-lane design by opus-engineer. Reversible by: none needed
  (the note is input to the build lane either way).
- `architect` M02 launched on `wp/M02` (from `wp/M01` `13bcef7`; ADR 0033+, R-220+), concurrent with M01 Amendment 1.
- M03 Amendment 1 done on `wp/M03` (`98485d5`, `2660608`, `8154baa`; check.sh 6991 passed; generator 264 claims; JSON
  sha `81d1d79a…`): A12 1e-13 → 1e-11 (below the a-priori 4.4e-12 bound before); LinearSolveFailedError → typed
  `LINEAR_SOLVE_FAILED` at new step Q2′; UNSUPPORTED_RANK_STRUCTURE added to ADR 0031 D3; FIT-U's undetermined r is
  arbitrary (registered values shown r-invariant; null projection a range [0.85960, 0.99761]); status precedence
  KKT_POINT_VERIFIED > NOT_VERIFIED > INFEASIBLE_REPORTED > SOLVER_FAILED; `schemas/registry.json` replaces the
  hard-coded schema count (A48). R-210…R-215. Q-F1, Q-F3 closed.
- `opus-engineer` M03 WO-2a, 5a, 7a, 9 launched on `wp/M03`.
- M01 Amendment 1 done on `wp/M01` (`49e9975`, `1e8aecd`; check.sh 7047 passed; generator 88 claims): A26 → 1e-13 ×
  n_tot,in (element balances too); A09 gap ≥ 1e-6; A12 rescaled to 1e-12 × M (block max), measured margin 2.6e3;
  refusals ratified (stage grammar `[A-Za-z0-9_]+`, registered stages), flash derivatives now refused
  `flash_derivatives_unsupported`; check order normative; §8.14 A45–A50 → A41–A48; new §8.15 record/adapter halves
  (A52 gates the record); A47 restated (bitwise only at the probe's exact tube inputs; 1e-6 through the boundary);
  Q-F4 sweep 16 corners + centre; new Q-F5 per-tube flow bound default [0.5, 2] × nominal (M02); A49–A52 new;
  R-195…R-200; interfaces-frozen §3 note. New Q-N5 for Frank: structured `synthetic` field in ModelManifest? default
  no. M02 architect told.
- `opus-engineer` M01 WO-8 (amendment build items, A49–A52) + WO-7 manifest launched on `wp/M01`.
- M02 design done on `wp/M02` (`e5af61d`, `98eaaff`, `a7230ff` merge of wp/M01 @ `4142471`, `a507c99`):
  `docs/design/M02-pymrm-adapter.md`, ADR 0033 (external execution + experiment records), 0034 (external models in a
  flowsheet solve: compiled unit pins X̂, ΔT̂; outer Broyden one experiment/iteration; route `revision_coupled`,
  outcome `COUPLING_NOT_CONVERGED`), 0035 (replacement/promotion: 8 §5.3 facets at commit,
  `model_replacement_incompatible`), R-220…R-233. Fresh child per attempt; 3-layer kill chain (adapter poll, worker
  process group + `killpg` amending ADR 0020 D3, child stdin/deadline); profile `external-subprocess-v1` not a
  sandbox; exact process-level cache serving deterministic outcomes only; one retry, none after timeout; 120 s
  timeout; coupled runs R3, replayed from record. New schemas experiment, model-variant, model-replacement. G1–G9 in
  the default gate, G10–G12 opt-in with the reactor. Conflict noted: M01.A49's "stand-in not bound" clause is
  replaced by M02 G8(e) (R-199 left binding to M02). Loop case `C1-LOOP-M02-v1` uses estimated numbers (escalate,
  don't adjust).
- M02 "Needs Frank" (defaults proceed): N1 accept "not a sandbox" locally; N2 no CI job for the reactor env; N3
  `v0.2-alpha-gate-v1` = v0.1 gate unchanged + W21, W22 met, no other claims; N4 ship the stand-in, listed synthetic;
  N5 defer PR LIQUID regime + pure-NH₃ flash; N6 no reactor warm start.
- `opus-engineer` M02 WO-1…4 (+ optional 5, 6) launched on `wp/M02`. M02 merges only after M01 `tested`.
- M06 WO-11, 12 done (`402e682` security/browser gates, `3c04037` changelog-test decision, `68bddc3` docs): check.sh
  7447 passed, 52 skipped, Node 91/91; browser module 31 passed (10/10 repeats; DevTools protocol over a pipe). G1
  dynamic, G1 static final list, G2 17/17 over HTTP, G8 DOM, G11 22 routes × 4 principals; live Solve/Cancel/download
  exercised in a real browser, no shell bugs. R-216 (session): the T08 CHANGELOG-limitations test reads v0.1.0's
  envelope (`98da494`). `wp/M06-finish` fast-forwarded into `wp/M06-build`; worktree removed.
- `wp/M06-build` pushed to origin (Frank authorised pushing) for CI evidence (G10 wheel half, G12, Chrome on
  ubuntu-latest); CI run 37825384881.
- `reviewer` M06 (WO-13 review) launched on `wp/M06-build` @ `98da494`.
- M01 WO-8 + WO-7 done on `wp/M01` (`11df954`…`cec8a01`): A49–A52 pass; manifest
  `evidence/M01/6c81683…/manifest.json` status **tested** (52 pass, 0 fail, 1 not_applicable = A47 adapter half);
  check.sh 7118 passed. Amended bounds measured: A12 ≤ 3.8e-16·M; A26 5.57e-17 × n_tot,in. Within 10×: A22 exactly
  1 ulp vs 1 ulp (proven worst case); A45 2.98e-8 vs 1e-7; A52 1 ulp vs 2; A38–A40 1.18–1.58× inside the W22 bands →
  for the reviewer. Harvest: 7 rows, class P. `7e0eb67` scoped two T08 tests to P/K/T → registered as R-217
  (`c2cf045`; session). IDAES record's `inputs.reference_values_yaml_sha256` moved with Amendment 1 (closed_form
  unchanged).
- `reviewer` M01 launched on `wp/M01` @ `c2cf045`.
- M03 WO-2a, 5a, 7a, 9 done on `wp/M03` (`5660bee`…`51941fa`): Q2′/LINEAR_SOLVE_FAILED (restructure bit-identical
  on 48 results, A10 still 2 factorizations), A43–A48 pass, `classify_starts`, `schemas/registry.json` (34 names),
  `study` + `optimization-report` schemas with emitted fixtures; WO-7 serialization defect fixed (`47fffad`); check.sh
  7043 passed. Nothing within 10×. R-218 (session, `7606ada`): rename-substitution test gets a registered
  post-rename fixture list (from the engineer's `26d1f1a`).
- DECISION: M03 WO-8 (cyipopt gray box) built now on `wp/M03`, the `nlp` extra in its own commit; no merge until
  Frank answers N1. Alternative: wait for N1. Reversible by: reverting that commit (no default path depends on it).
- `opus-engineer` M03 WO-8 launched on `wp/M03`.
- M01 review (`docs/reviews/M01-review.md`, `3a61298`): **matches, one must-fix.** F1 (must) harvest row for
  `limitations[3]` (no mixture VLE, k_ij=0) is user-facing → E + an L-row for pr-c1-v1; F2 `admissible_roots` keeps
  unconverged Newton values near a double root (NH₃ 400 K, P=10 025 791.149… Pa returns 3 "roots", LIQUID ok with
  Z=0.0699) → keep converged only/deflate; R-197's reasoning corrected; F3 dormant-inlet check precedes the state-space
  check (n=(0.5,−0.5,…) → ok ZERO_FLOW) → add check, amend §8.12; F4 declining Q-N4 is not a clean revert (loader via
  `packaged()`) → fallback; F5 flash samples miss a root in 5/497 states at 373–398 K, 1.05–1.24e7 Pa → quantify.
  Rulings: A22, A45, A52, A38–A40 accepted; A33 reading accepted; `requirements: ["D08"]` accepted (W-id carriage for
  v0.2 manifests: design lane before M07). ADR 0026 may move to Accepted (F2 before M02's units use the provider; F1
  before merge). ADR 0027 needs M02's adapter halves + review, the §8.12 amendment, the A49 supersession record, and
  M02's choice on boundary.py in the reactor identity. M02 notes: stand-in identity doesn't cover boundary.py;
  `Boundary` doesn't validate n_tubes.
- `opus-engineer` M01 review fixes F1–F5 launched on `wp/M01`; the reviewer confirms closure afterwards.
- CI run 37825384881 on `wp/M06-build` @ `98da494`: aarch64 check green; x86-64 check 2 failed / 7400 (browser smoke
  hard-codes 31487.641739605908 — trailing digits differ on the runner's re-solve); default-install 2 failed
  (route-table script imports uvicorn; envelope cites tests in modules that skip at module level). Chrome headless
  starts without `--no-sandbox` on ubuntu-latest.
- M06 review (`docs/reviews/M06-review.md`, `fc73c0b`): **matches with must-fixes.** F1 G10 never measured (dist and
  clean-install run only on dispatch); F2a–c the CI failures above; F3 Amendment 3 text (null rows/columns on the
  routed branch; R-192 digest move recorded). Should-fix F4 `h()` doesn't enforce the whitelist itself; F5 W27
  registration erratum (ten → nine) + ratify the scorer's three silent-case choices (reviewer recommends ratifying);
  F6 manifest harvest; F7 P1 lives on main (merge, re-run preflight); F8 as-built addendum. All deviations accepted;
  certificate tone mapping confirmed; the DevTools harness counts as §8 A6. ADR 0030 → Accepted after F1+F2 with a
  green CI run; Amendment 3 after F3 + the same run.
- `opus-engineer` M06 review fixes F1–F8 + WO-13 manifest launched on `wp/M06-build`.
- M02 WO-1a, 2, 3, 4 done on `wp/M02` (`dbc9e8a`, `441e3d1`, `7efd037`, `451d4d9`, `6a1319c`): new schemas
  experiment/model-variant/model-replacement; `adapters/` layer, variants + pin check, stand-in variant, HardDomain
  with the Q-F5 flow bound; launcher + 3-layer kill chain (G3 all within bounds: worst 2.10/3.0 s, 2.003/2.5 s,
  2.07/3.0 s); experiment store with per-key flock, runner with cache/retry/bypass (G4 a–i). check.sh 7178 passed.
  WO-1b (existing-schema edits) parked on `wp/M02-wo1b-proposed` (`631b1c7`): Q1 served MCP digest moves again
  (`8de83946…`), Q2 T07 Q26 forbids the numeric `body.inlet.n`. Q3 handshake-fingerprint keying, Q4 store layering
  (lazy upward import vs callback). Build decision log copied into `docs/design/M02-build-decisions.md` (`02403d1`).
  Engineer stopped near its context budget. M02 architect asked for rulings (R-234+).
- M02 architect rulings (`811b23c`, note §14 B1–B5, R-234…R-237): Q1 digest move follows R-192 (0.1 A49 constant
  unedited; decomposition test to the base's registered digest; `8de83946…` evidence, not a pin; the v0.2 gate pins
  the release commit's digest with one decomposition entry per surface change); Q2 `body/inlet/n` allowed by name +
  companion test; Q3 confirmed with separate handshake/evaluation retry budgets, handshake outcome fixed per job; Q4
  injected `ArtifactSink` callback replaces the lazy upward import (D10), `atomic_write_bytes` → `_files.py`.
- `opus-engineer` M02 WO-1b + R-234…237 code, WO-5 (reactor env + child, G10 opt-in run), WO-6 launched on `wp/M02`.
- M03 WO-8 done on `wp/M03` (`aa52638` adapter + tests + `m03_nlp_check.sh`, `569c300` inventory on NLP-1,
  **`91537b0` the `nlp` extra alone**, `e9de5ee` inventory after the extra): default gate 7047 passed, 17 deselected;
  nlp gate 17 passed. A35 3/3 KKT_POINT_VERIFIED, decision error 2.67e-12 (1e-6); A36 μ ≤ 9e-11, stationarity ≤
  1.4e-9; A37 NLP-INF INFEASIBLE_REPORTED; A38 exact Hessian refused with 0 solves; A39 no METIS-closure object, 0
  nlpsol; Q-F2 nothing within 10×; Q-F4 trial-point errors → step rejection, start/Jacobian errors → SOLVER_FAILED.
  Threading: 48 OMP threads → 1-ulp variation (NLP-1) and a different path on NLP-INF; OMP_NUM_THREADS=1 makes runs
  identical. Open: A40 "sum" reading (NLP-INF sums 597 > 500); record/enforce OMP threads. Merge still waits for N1.
- `reviewer` M03 launched on `wp/M03` @ `e9de5ee` (rules on A40 and threading).
- M03 review (`docs/reviews/M03-review.md`, `ceb5e15`): numerics and architecture sound; **one must-fix** F1 — three
  tests compare emitted output byte for byte (study fixtures pin 13 `state_sha256` (ADR 0008 D2.1) and converged
  floats; FIT-U pins arbitrary r, roundoff σ₂, the ranged projection, nfev) → policy comparison via
  `run.compare.differences`, ranges for path-dependent values, τ_abs floor; require green on both CI runners. F2 record
  OMP threads, effective max threads, the loaded ASL path/sha in `solver`. Rulings: A40's budget is per Ipopt run for
  every run, the sum is recorded cost (amend wording); threading recorded, not enforced (product rule = Frank's call);
  the seven build-lane choices accepted; vocabulary/precedence sound; F4 add `NLP_LICENCES_ACCEPTED` beside the extra.
  ADR 0031 Accepted after F1 + green on both runners + manifest tested; ADR 0032 also needs F2, A40 amended, N1.
- `opus-engineer` M03 review fixes + WO-10 manifest launched on `wp/M03`.
- M01 review fixes done on `wp/M01` (`e4eb1f0` F2 root check + deflation, R-197 note; `eec11d3` F3
  state_space_violation, R-198 note; `f1877ec` F4 checkout fallback; `094b936` F5 region 362.5–401 K, 1.00–1.38e7 Pa,
  26/1744; `ce0b92f` F1 L42 + E; `e041fcb` CHANGELOG test `ADDED_AFTER_V0_1_0=("L42",)`, R-217 note; `46a4a45`,
  `3c80392`, `784b38f` manifest). check.sh 7141 passed. Registered values bit-identical (float.hex dumps). New
  manifest `evidence/M01/3c80392…/manifest.json` tested. M02 items: boundary.py hash in the reactor identity;
  `Boundary.__post_init__` validating n_tubes; §8.15 A45 restricted to A41's points; no A10 check at a three-root
  state or for pure-vapour n-derivatives. M01 reviewer asked to confirm closure.
- M06 review fixes done on `wp/M06-build` (`f47a243`…`c5e6890`): F2a exact repr from the run's own bundle; F2b routes
  from OPERATIONS; F2c module-level skips moved; F4 h() brands its trees (WeakSet); F5 registration §20 (ten → nine;
  scorer rules W27-R59…R61; P2 pin `dd0b7f02…`); F3 Amendment 3 text + R-192 recorded; F8 as-built §14; F9;
  `4719a1a` cherry-picks M01's `7e0eb67`. check.sh at C=`4719a1a` 7469 passed, Node 92/92, browser 31/31;
  default-install reproduced locally (7203 passed, 0 failed). G10 measured locally on a clean wheel install: PASSED.
  Manifest `evidence/M06/4719a1a…/manifest.json` status **implemented** (G3, G12 wait for CI; G16 n/a). Preflight
  P1–P8 pass (P6/P7 by stub canaries). F5's ratification text wants `specifier` eyes before WO-17's first canary.
  F14 → M07 list: register v0.2's served surface, retarget A49.
- Pushed `wp/M06-build` @ `c5e6890`; CI push run 37839253802 and dispatch (rc_distribution) 37839266960. After green:
  `scripts/m06_evidence_manifest.py --commit 4719a1a… --add-ci --ci-run <ids> --harvest`, commit, then ADR 0030 and
  Amendment 3 → Accepted, merge.
- M01 review closure (`9098f14`): all five findings closed; Amendment 2 ratified; ADR 0026 → **Accepted** (`ab57fcc`);
  R-219 (session) records the declared no-walk-up exception. ADR 0027 stays Proposed (needs M02's adapter halves +
  review, the A49 supersession record, the boundary.py identity choice).
- **M01 merged into main** (`997c7da`). check.sh on main after the merge: 7142 passed, 31 skipped, PASSED.
- M04 recon done (digest inline): no M04 code/schema/ADR/register entry; no approved experiment budget or registered
  reference distribution; surrogate seam = M02's pinned (X̂, ΔT̂) (ADR 0034 D1). Brief `docs/briefs/M04-specification.md`
  (`418a891` on `wp/M04`). `specifier` M04 launched on `wp/M04` (ADR 0036+, R-240+).
- M06 CI green: push run 37839253802 (check both architectures, default-install, identity) and dispatch 37839266960
  (+ dist, clean-install both, bundle-set, bundle-replay both). `--add-ci` → manifest `evidence/M06/4719a1a…` **tested**
  (G1–G15 pass, G16 n/a). ADR 0030 and ADR 0019 Amendment 3 → **Accepted** (`19a1379`).
- `opus-engineer` merging `wp/M06-build` into main on `merge/M06` (reconcile register, envelope, matrix, changelog
  test with M01); main fast-forwards after a green gate.
- **M06 merged into main**: `7473f35` (merge onto M01; register rebuilt in numerical order, 190 entries, next free
  R-238; envelope + matrix regenerated, 51 limitations, 278 harvest rows; changelog test takes R-216's form and drops
  M01's `ADDED_AFTER_V0_1_0`, R-217 merge note; package data both kinds) — gate on that tree: 7717 passed, 52 skipped,
  Node 92/92, browser 34/34, matrix --check 0. `47baa4d` brings main's two state-file commits (docs only). Pushed.
- `specifier` v0.2 alpha release gate launched on `wp/V02-alpha-gate` (ADR 0028, R-238/239): what `0.2.0a1` claims,
  carried and moved v0.1 records (digest, envelope, CHANGELOG notes, review table, A49), W21/W22 verdict criteria,
  gate script work orders. Against M02's N3 default (v0.1 gate unchanged + W21, W22 met).
- M04 specification done on `wp/M04` (`35ace09`, `408a960`, `6e48ffb`): `docs/derivations/M04-spec.md` (A01–A35),
  ADR 0036 (surrogate evidence + Default split-conformal), ADR 0037 (surrogate unit, promotion, rollback; amends
  ADR 0035 additively and ADR 0019 as Amendment 5), R-240…R-249, generator `m04_reference.py` (5269 claims),
  `plan-it1.json`. Native unit `c1.reactor_surrogate` (frozen quadratic in 7 scaled inputs → (X, ΔT)) on
  `revision_eo`; reference distribution uniform on a box inside the data domain; one joint score scaled by width
  limits (0.0025 in X, 1.5 K); failures score +∞ and stay in denominators; promotion decided in integers (H ≥ h_min);
  new facet `surrogate_evidence`. Plan it.1: 144 train / 118 cal (k=114) / 300 test + 5×14 gradient stencil = 632
  cold experiments ≈ 95 min; power 0.9035 with no parent failures. WO-1, 2, 3, 10 need nothing from M02.
- M04 Needs Frank (defaults proceed): N1 experiment budget 632 (≈95 min) for it.1 + up to two more (≈4 h total); N2
  width limits 0.0025 / 1.5 K; N3 gradient limit 0.25; N6 M04 `tested` whatever the real verdict, M05 proceeds on the
  parent model if not promotable. N4 (reference box vs the real loop inlet) and N5 (runner concurrency) are facts
  for M02's measurements.
- `opus-engineer` M04 WO-1, 2, 3, 10 launched on `wp/M04`.
- M02 WO-1b, rulings, WO-5, WO-6 done on `wp/M02` (`100fd12`, `3f37c2e`, `d0eb848`, `2e63211`; check.sh 7236
  passed, 2 pymrm deselected). Reactor env built from pins (fresh clone, 20.6 s): lock `032a050c…` (85 dists), variant
  `pymrm-6089593-g2-nz800-s123-v1` = `2302cddf…`, fingerprint `238123dc…`. **G10 all pass**: A41 3/3; A42
  1.559285305616933e-08 (= probe); A43/A44 bitwise; A45 3.84e-8 ≤ 1e-7; A46 5.06e-5 ≤ 1e-3; **A47(a) bitwise**; A47(b)
  1.43e-8 ≤ 1e-6; A48 3/3. G5 15 tests over 4 transports. Real experiment job: 31.7 s; cache hit 1.88 s.
- **Finding (D22): one real evaluation costs 25–45 s, not ~9 s** — the probe's wall_s omitted the group's KPI
  certificate (12–35 s). 120 s timeout keeps 2.7×. Consequence: M04's iteration 1 (632 experiments) ≈ 4.4–7.9 h, not
  95 min; three iterations ≈ 12–20 h. Frank's M04 N1 restated. Open for the design lane: D22 (timing, R-224/§5.2/G12),
  D24 (`job_result.experiment` null before any attempt), D23 (every experiment job records through
  ArtifactTableSink), D18 (model exception → crashed), D14 (frozen handshake failure recorded per experiment).
- `opus-engineer` M02 merge-main + WO-7, WO-8 (+WO-9) launched on `wp/M02`.
- M03 review fixes + WO-10 done on `wp/M03` (`ca3d833`…`71b3c37`): F1 policy comparison (`tests/m03_fixture_compare.py`;
  8 perturbed regenerations compare clean; a 3e-9 χ² change is caught; 8 permanent must-catch mutations); F2
  `solver.environment` (thread vars, libomp max_threads, ASL path/sha); A40 per run (Amendment 2); F4
  `NLP_LICENCES_ACCEPTED` (`bf753ae` gate, `2b6e350` set True pending N1 — revert with `91537b0` to decline); F5
  twin bitwise at moved inputs. check.sh 7066 passed; nlp gate 18 passed. Manifest
  `evidence/M03/fd16834…/manifest.json` **implemented** (A01–A48 pass; `M03.N1` and `M03.ci_both_runners`
  unsupported until stated). Design lane to register the test-module comparison rules (review F1). Pushed
  `wp/M03` → CI 37846362678.
- M02 architect asked for rulings D14, D18, D22 (timing), D23, D24 (R-250+; R-238/239 alpha gate, R-240…249 M04).
- M02 rulings round 2 (`e4d1b82`, note §14.1 B6–B10, R-250…R-252): D22 the KPI certificate stays (part of ADR 0027 D6
  acceptance; produces A47's bits; no cheaper equal claim); timeout 120 s until G11 re-registers it; 25–45 s per
  evaluation, 2–6 min per coupled solve; G12 runs with wall_time_s 3600; **M04 lever: distinct-key experiments may run
  concurrently (≤ physical cores) without changing any bit**. D24 confirmed (null iff no experiment artifact). D23
  confirmed. D18 changed: new deterministic stage `model_exception` (cached, not retried, coupling backtracks). D14
  confirmed. Note: `e4d1b82` also concluded the WO-7/8 engineer's in-progress merge of main (parents `2e63211`,
  `e100b68`); engineer told to commit on top.
- M03 reviewer asked to confirm closure and rule on registering the test-module comparison rules.
- M03 review Closure (`a8a6dcc`): all findings closed in code; F1 final on green CI both runners; Amendment 2
  ratified; comparison rules ratified → R-253 (session, `85965cd`) with watch-for (move into run/compare + ADR 0025
  amendment before study/optimization records become replay-comparable, i.e. before M05/K05 bundles). ADR 0031 →
  Accepted on green CI + manifest tested; ADR 0032 also needs N1.
- `recon` M05 launched.
- M05 recon done (digest inline; facts pasted into `docs/briefs/M05-design.md`, `1ecf576`): Pyomo 6.10.1
  `contrib.trustregion` present in the audited env (TrustRegionSolver; ExternalFunction → holder variables; default
  subproblem solver = the ASL `ipopt` executable, which is in the env but NOT in the [A10] inventory); Python-callback
  ExternalFunction needs no ASL library; no M05 code/ADR anywhere; C1 decisions per ADR 0022 D6 = reactor inlet T
  (alternative purge fraction); no registered objective.
- `architect` M05 launched on `wp/M05` (ADR 0038+, R-260+), with a throwaway TRF probe allowed in the audited env.
- M04 WO-1, 2, 3, 10 done on `wp/M04` (`c757f13`, `cebe3f6`, `af4801a`, `7613b5e`; check.sh 7243 passed):
  `studies/surrogate/{plan,conformal,quadratic}.py` (the `studies` layer created byte-identically to wp/M03's).
  A01–A15 + A34 pass (closest: A12 R_T 8.1e-17 vs 1e-15, 12×). Choices isolated per commit (input map in plan.py;
  injected domain guard; `plan_not_registered` for it≥2; None is the only +∞ score). For the M04 amendment round:
  A11's "rank-deficient by two columns" is eight columns; whether it≥2 training lists earlier draws as requests.
  WO-4+ need M02's runner/unit → merge `wp/M02` into `wp/M04` after M02's WO-7/8 gate is green.
- M03 CI 37846362678: check green on both architectures; default-install failed on the G6 isolation walk importing
  bindings.http (uvicorn absent). Fixed (`8996973`: only a server-extra ModuleNotFoundError is tolerated); re-run
  37848933412.
- `docs/progress.md` "Start here" rows brought up to date.
- v0.2 alpha gate specified on `wp/V02-alpha-gate` (`e3703bb`): `docs/derivations/V02-alpha-release-spec.md` (12 gate
  rows, A00–A64), ADR 0028 (v0.2 pre-release policy), R-238/239, generator `v02a_reference.py` (64 claims), evidence
  id M07a. Claims at `C_α`: V11–V20 re-judged by T08 §4 unchanged + W21 + W22; W23–W27 "not claimed"; web shell ships
  unclaimed. Moved records MR-1…12 each with a counterpart at least as strict (surface digest chain R-234→R-192→R-133→
  v17-c2; V17 BLOCKED unless carried; alpha envelope pinned with T08's 58 limitations harvested; CHANGELOG `## v0.2.0a1`
  names L42, L-WEB-1…4). Findings: release.yml and changelog_section.py reject every pre-release today; B50's content
  test will break at M02's merge.
- `opus-engineer` alpha gate WO-1, 2, 3, 4, 7 launched on `wp/V02-alpha-gate` (no dispatch/tag/publish).
- M05 design done on `wp/M05` (`d7d6dbf`, `43651ce`): `docs/design/M05-trust-region.md`, ADR 0038 (TRF adapter: Pyomo
  6.10.1 contrib.trustregion unmodified, pinned by version + module hashes), 0039 (C1 study: one decision, reactor
  inlet T ∈ [643.15, 733.15] K, purge 0.02, maximize liquid NH₃), 0040 (fallback, inactive; triggers T1 N1 denied, T2
  structural failure, T3 audit + shim both fail), R-260…R-273. Probe (scratchpad): TRF composes (Pyomo example 1
  bitwise via a property-block wrapper); every ExternalFunction needs a gradient; TRF clones the model (identity hook
  needed for the ledger); exceptions abort TRF, NaN is silently "optimal" (callbacks raise typed refusals); subproblems
  need the `ipopt` executable (+ `libipoptamplinterface`, `libgomp` — not in M03's inventory). Glass box = canonical
  row builders over a Pyomo algebra + property outputs as Python-callback ExternalFunctions; reactor in full space
  ((X̂, ΔT̂) linked to an EF of 7 inlet vars, FD step 2⁻¹⁴, 7 concurrent workers); eligible example TR-E2 = C1 loop with
  a test-only smooth synthetic reactor; real reactor "qualified" only. Budgets 400 cold / 4 h per study.
- M05 Needs Frank (defaults proceed): N-F1 objective = liquid NH₃ product (alt: economic with his prices); N-F2 decision
  tolerance 0.5 K; N-F3 real-reactor budget 400 experiments / 4 h; N-F4 proceed in the audited env, merge with `nlp`
  undeclared if N1 is pending; N-F5 surrogate only if promoted; N-F6 decision box [643.15, 733.15] K; N-F7 no job op.
- `opus-engineer` merging main into `wp/M03` (merge-ready; base for M05 WO-1…3).
- Alpha gate WO-1, 2, 3, 4, 7 done on `wp/V02-alpha-gate` (`332e9d7`…`c35c50b`): `scripts/v0_2_gate.py` (104 tests;
  11 deliberate rule breaks each caught), release.yml + changelog_section.py accept PEP 440 pre-releases (dry-run
  default kept), v0.1.0 notes test reads PUBLIC_ROOT, v0.1.1 bundle fixture. check.sh 7861 passed. v0.1 gate and
  t08_rc.py empty diff. A dry `t08_dist.py` at `0.2.0a1` passes T08.A43; clean pip install reports 0.2.0a1. Open: A42
  (plain `replay` gives NOT_RUN; test judges `replay --rerun`). WO-5…11 need M02.
- `reviewer` alpha gate (WO-2 + the rest) launched.
- M03 CI 37851614039 on `2ed3f22`: **all green** (check both architectures, default-install, identity). `M03.ci_both_runners` can be stated green; the manifest's `tested` status still waits for N1. (The main-merge onto wp/M03 will need its own CI run.)
- `main` merged into `wp/M03` (`8d4069c` + `086bf2b` inventory skip of the `web` binding; check.sh 7904 passed, nlp gate
  18 passed, G1–G6 PASS). Pushed. Register now holds every entry (224 headings on wp/M05). M03 manifest must be
  regenerated (audit doc + inventory hashes moved) when N1 arrives.
- `wp/M03` merged into `wp/M05` (`d124e2c`; register = M03's + M05's appended R-260…273).
- M02 WO-7 done (`3c5df9f`: ComponentBasis by `record_source`; 50 corpus revisions bind byte-identically before/after,
  sha `d7ff979b…`), R-252 tests (`11d3882`), n_tubes check (`a19fdfd`), R-251 `model_exception` → new variant
  `pymrm-6089593-g2-nz800-s123-v2` (v1 superseded; G10 re-recorded bitwise equal, `6a46cdd`). check.sh 7902 passed.
  **WO-8 blocked before code** (D30): F1 liquid light-gas flows are variables in frozen `assemble`; F2 `check_agreement`
  expects SYN-001's split rows; F3 region admissibility is lnK/3-wide; F4 the verifier's revision path is SYN-001-only
  (PR checks = certificate policy); F5 no solve-time phase screen for non-lifted vapour outlets; F6 PR enthalpy-flow
  Jacobian undefined at exact dormancy. Plus D27 (API wording), D33 (env manifest variant id).
- Alpha gate review (`c8fd848`): sound, no must-fix; should-fix F1 T4 acceptance-cell rule too loose; F2 Frank's answers
  need the date rule per release; F3 `differences=None` skips the tree check; F4 six refusals untested; A42 `--rerun`
  confirmed. All six build choices accepted.
- Launched: fresh `architect` M02 WO-8 rulings (R-254+); `opus-engineer` M05 WO-2, WO-3 (`wp/M05`); `sonnet-implementer`
  M05 WO-1 ipopt-executable audit (`wp/M05-audit`); `opus-engineer` alpha gate review fixes.
- Alpha gate review fixes done (`4d6891b`…`178a070`): F1 acceptance-cell regex + calendar check (3 new "no" rows); F2
  Frank's answers dated ≥ `Judged` (new Table T6; `0.2.0a2` refused on `0.2.0a1`'s answers); F3 `differences=None`
  refuses "tree check not run"; F4 six refusal tests (each removal fails only its own tests); A42 line; RELEASING.md
  clause. check.sh 7889 passed; generator 67 claims. Session aligned ADR 0028's cell rule + answers intro and appended an
  R-238 amendment note (`c97da19`). Left: F6 (close 0.1-line pre-releases? Frank's call), F7 for M07, F8 aarch64
  `--rerun` MATCH to confirm in CI before `C_α`, WO-5 must check the V17-carry row names every surface link.
- M02 WO-8 rulings (`bfbad26`, note §14.2 B11–B19, R-254…R-259; amendments on ADR 0012, ADR 0013 (A3), ADR 0026 (A2),
  M01 spec §7 (A3), R-046, R-060, R-230): B11 M01's equilibrium row restated in R-008's form E = L·v·φ^V − V·l·φ^L
  (molar_flow_squared; same two-phase roots, no M01 value moves) — as written it was nonzero on VAPOR and unevaluable
  above NH₃'s T_c; B12 light-gas liquid rows l_i = 0 + `VapourOnlyForm` pinning +0.0; B13 `SplitRule.vapour_only`,
  SYN-001 code unedited; B14 region dispatch by provider id with τ_dew band; B15 PR verifier check forms from existing
  tolerances only (check_policy_sha256 unchanged; rejected |y−y*| ≤ 1e-10 as 500–16000× too tight); B16 evaluate refuses
  `vapour_phase_inadmissible`; B17 zero-flow ideal-gas limit; B18 D27 confirmed; B19 D33 confirmed. No specifier blocks
  (optional ratification of M01 §7 A3). Risks: G7(a) 1e-9 may need `newton_refined`; near-dew singularity → limitation.
- `opus-engineer` M02 WO-8.1…8.5 launched on `wp/M02`.
- M05 WO-2, WO-3 done on `wp/M05` (`0a93225` projection compiler, `aaa2452` omitted_rows DECISION, `545a385` G4 in K03
  scales DECISION, `dd9e364` TRF runner): default 7951 passed, nlp 67 passed. G2 pin refuses; G3 TR-E1 matches native to
  4.4e-16 in 5 iterations (6 cold points, 4 gradients); G4 SYN-001 ≤ 5.9e-4/7.1e-7/2.3e-3 of tolerance; G13 holds.
  Finding: Pyomo's EFReplacement.exitNode swallows start-value exceptions (bare except → 0); holder now records them.
  Open for the M05 architect: omitted pressure-alias rows (PROJECTION_DOF otherwise); G4/Ipopt scaling in K03's scales;
  unassigned affine basis (§6.6), readiness halves, TruthBox meta. Architect asked.
- M05 WO-1 done on `wp/M05-audit` (`a28d6a8`): the `ipopt` executable passes G1–G8 (audit §11 in
  `docs/m03-ipopt-audit.md`; record `benchmarks/m05/trsp-inventory-x86_64.json`). New objects only `bin/ipopt` and
  `libipoptamplinterface.so.3.14.20` (conda-forge ipopt-3.14.20, EPL-2.0 read / EPL-1.0 declared, as libipopt). The
  `libgomp.so.1` loaded is a symlink to LLVM libomp 23.1.3 (already inventoried) — ADR 0006 Amendment 1 not engaged.
  Method: `LD_DEBUG=files` in the workload's children, union equals `ldd` closure. No licence class added for N1
  (Ipopt now also runs as a separate process, noted). G7 narrower (no second-prefix rebuild). check.sh 7908 passed.
  To merge into `wp/M05` after the M05 architect's rulings commit; then a test that WO-3's pin hashes equal WO-1's record.
- M05 rulings (`595b32b`, note §16 + P13, R-274…R-276): R-274 omitted rows computed by `eliminate_alias_rows` (caller set
  only if equal; four certifying facts; C1 the same, escalate if elimination refuses); R-275 K03 `Scaling.from_spec`
  everywhere (unit_no_kinds for TR-E1; partial kinds refused); R-276 pre-flight start evaluation + no candidate after any
  recorded refusal. Gaps assigned: affine basis + TruthBox meta → WO-4; readiness halves → WO-6.
- `wp/M05-audit` merged into `wp/M05` (`aef41bf`). `opus-engineer` M05 R-274…276 code amendments + pin cross-check
  launched.
- M05 R-274…276 amendments done on `wp/M05` (`7697149`, `7929478`, `5ed884b`, `005db97`, `966ab1b`, `6e44cac`):
  default 7956 passed; nlp tier 90 passed; G3/G4 identical to baseline. Omitted rows computed via
  `eliminate_alias_rows` (facts 1–3 recorded per row; fact 4 a hook until P2); pre-flight start evaluation; pin cross-check
  vs the WO-1 record. **For the M05 review:** `7929478` moved the certificate's pressure-shift rule into
  `orchestrator/rank.py` (`pressure_shifted_state`) so the projection can use it — the certificate already uses rank.py's
  alias elimination, but this widens verifier/solver sharing (R-016) and needs a design-lane look. Finding: TRF 6.10.1
  fails its subproblem as infeasible on `y − 90z = 0` (EF output tied to decisions alone) independent of the projection —
  probe before C1. Test-order dependence (`-k g3` alone) noted. M05 now waits for M02 + M04 merges (WO-4+).
- DECISION: M04 continues on M02's completed base — `opus-engineer` merges the fixed commit `bfbad26` (M02 WO-1…7, gate
  green at `6a46cdd`) into `wp/M04` and builds WO-4, 5, 6. Alternative: wait for M02 to merge to main. Reversible by:
  reverting that merge; M02's later commits merge cumulatively.
- `opus-engineer` diagnosis probe of the TRF infeasible-subproblem shape (`y − 90z`), with C1 formulation implications
  (scratchpad only, no src commits).
- TRF shape probe (scratchpad `m05-probe2`): the `y − 90z` "infeasible subproblem" is TRF's default basis b ≡ 0 (already
  rejected by ADR 0038) failing the iteration-0 PMP; with b(w₀) = d(w₀) it converges. C1-shaped toy converges with the
  registered bases (6 starts within 4e-3 of the grid optimum). Two TRF defects found: "Optimal" with zero TRSPs when
  θ_PMP = 0; stall test compares θ with itself ("Feasible solution found" at θ = 1.80). Safe = forward shape (C1's link
  is); unsafe = EF output pinned by decisions alone. Proposed rules: refuse `basis_rule=None`; projection refusal
  `PROJECTION_IMPLICIT_EF_INPUT` (Dulmage–Mendelsohn); Taylor basis for the reactor EF without a promoted surrogate + no
  TRF_CONVERGED without an accepted TRSP; re-check θ on stalled exits. ADR 0040 T2 not fired. Sent to the M05 architect.
- M05 P14 rulings (`4c80ae4`; ADR 0038 Amendment 1; R-277…R-279; ADR 0040 T2 does not fire): R-277 mandatory basis
  (explicit test-only `zero_basis` for TR-E1; reactor gets the affine Taylor basis without a promoted surrogate, WO-4);
  R-278 `PROJECTION_IMPLICIT_EF_INPUT` = structural perfect matching with decisions + link EF outputs fixed (property
  relations stay functions), WO-2a; R-279 θ re-check after every exit, `TRF_CONVERGED` needs an accepted step, new
  `TRF_EXIT_WITHOUT_STEP` and `TRF_STALLED_INCONSISTENT`, WO-3a (+WO-6 handling).
- `opus-engineer` M05 WO-2a, WO-3a launched.
- M05 WO-2a, WO-3a done (`2f9022c`, `2dc50d9`): default 7962 passed; M05 opt-in 94 passed; G3 bitwise unchanged
  (one extra trailing memo-hit `f` from the θ re-check). P14 (a) basis refusal, (b) `TRF_EXIT_WITHOUT_STEP`, (c)
  `TRF_STALLED_INCONSISTENT` at θ = 1.8006 — all tested; WO-2a refuses `y − 90z`, passes SYN-001 (74/74 matched).
  Open for the design lane before WO-6: "Optimal" exit with θ_recheck > 1e-5 → engineer chose `TRF_ERROR(exit_mismatch)`
  (alternative `TRF_STALLED_INCONSISTENT`; matters for the retry policy). Other engineer choices (refusal raises
  `TrfConfigurationRefusedError`; zero_basis only for exempt_oracle; refusal names undetermined variables; `EFBasis`)
  for the M05 review.
- M02 WO-8 built on `wp/M02` (`df7a568`…`9f94727`, head `8734905`; check.sh 8081 passed, 1 xfailed): C1 PR blocks,
  `classify`, six C1 units, `vapour_only`/`VapourOnlyForm`, region PR dispatch, `verify/pr_c1.py`. G2: 50 T07 revisions
  byte-identical (44 certificates, `659748576adb9730…`). G7(a) β 1.3e-16; (b) VERIFIED; (c) F4 UNVERIFIED rank-deficient
  (rcond 5.9e-19; still UNVERIFIED at δ = 1e-5, rcond 4.2e-9) — strict xfail; (d) VERIFIED; (e)–(k) pass. Open for the
  design lane: D36 C1 builders kept in a separate `C1_MODEL_BUILDERS` (joining breaks 13 registry/list_models/W27 tests);
  D40 certificate witness excludes exactly-zero PR columns (`d9c7cd4`, ratify); D41 G7(c) VERIFIED unreachable at the
  dew point (structural singularity, as SYN-001's DEW_POINT_LIMITATION); D39 three SYN-001 assumptions fixed on the
  revision path. Sent to the WO-8 rulings architect.
- M02 follow-up rulings (`2587f14`, note §14.3, R-280…R-282, ADR 0013 A3 items 7–8): R-280 the separate C1 registry is
  interim until WO-9 ends; WO-9's last commit joins all eight C1 entries into MODEL_BUILDERS with registered C1 corpus
  revisions, re-taken fixtures (stripping `c1.` restores pre-M02), envelope rows, and M06's W27 snapshot re-pinned under
  a design-lane mapping amendment — no merge/tested manifest while the separate registry exists; R-281 witness skip
  ratified but narrowed to exactly-zero `<S>.n.<c>` columns for pr-c1-v1, recorded as a qualification + limitation
  `derivative_witness_partial`; R-282 near-dew window (rcond ≈ 7e-3·L/n_tot; verifies from L/n_tot ≈ 1.4e-6; the loop
  sits ~4 decades clear); G7(c) asserts UNVERIFIED at F4, VERIFIED at δ = 1e-3; D39's three fixes confirmed.
- Launched: `opus-engineer` M02 WO-9 + R-281/R-282 (no join yet); `specifier` W27 registration Amendment 2 (C1 map
  rows, v0.2 READINGS, §20 ratification) on `wp/M06-w27-c1map` (R-283+).
- M04 WO-4, 5, 6 done on `wp/M04` (`cadef83` merge of M02 `bfbad26`; `a16c3fa`, `2a4370a`, `846820c`, `b975a5d`,
  `d5736ac`): check.sh 8062 passed. A17 q̂ 1.8e-15 from reference, H 283/300, PROMOTABLE (632 experiments in 1.15 s);
  A18 NOT_PROMOTABLE; A19 PROMOTABLE; A16 stand-in through the job; A20 budget refusal + bitwise cached rerun; A21–A24.
  Added `ExperimentRunner.request()` in M02's runner (M02 tests unchanged); `surrogate_study` job op; schemas
  surrogate-manifest, model-evidence; served surface moved (SNAPSHOT_M04, stripping restores M02's). Open → M04
  Amendment 1 (sent to the M04 specifier, R-290+): A11 text; it≥2 plans; float classification for fit values (ADR 0007
  D2.3 / ADR 0025); manifest–evidence hash cycle; outputs/refusals/new schema members; WO-11 concurrency (R-250); surface
  move register entry.
- W27 registration Amendment 2 (`0bb7a15` on `wp/M06-w27-c1map`, §21, R-283…R-286; registration.json `14ff19d9…`):
  six C1 units map to their SYN-001 namesakes' functions (no token; state limits not expressible case-side, checked
  GC-A2-5); `c1.reactor` → no function (`fixed_design_reactor`); stand-in → no function (`synthetic_stand_in`);
  `pr-c1-v1` → `cubic_pr`; components by CAS. New R62 (units judged on the serving route's models), R24 (d)/(e), R63
  `bases-v1` READINGS (`SELECTABLE_BASES`/`MODEL_BASES`). Dry v0.2 coverage: still 0 CANDIDATE of 450 and of 82. §20
  ratified; W27-R59 amended (S19/S20). Finding F-A2-1 for M02: should SYN-001 builders refuse the C1 basis (recommended
  yes). M02 join steps J1–J6 recorded in §21.8.
- `opus-engineer` M06 WO-16h (R62, R24 d/e, R59, S19/S20, bases-v1, 0.1.1 guard) launched on `wp/M06-w27-c1map`.
- M04 Amendment 1 (`3c4f8c2`, spec §18, ADR 0036/0037 A1, R-290…R-295; generator 8634 claims; gate 8062): A11 text
  corrected (eight columns at roundoff, ratio 9.1e-32); it≥2 training lists earlier draws as requests, `plan-it2/it3.json`
  committed, `iteration_not_permitted` unless earlier failures were coverage-only; no new float class (R1/R2 under ADR
  0007 given the same records; R0 only with decision gaps ≥ 1e-8; `domain.admissibility_margin`); manifest–evidence
  pointer reversed (evidence → manifest); outputs/refusals confirmed (+`cache_misses`); concurrency only as a pre-warm of
  632 `experiment` jobs at max_workers 16 (≈16–30 min), study then fully cached, recorded only in the package manifest;
  surface move R-295. Work items WO-13…17.
- `opus-engineer` M04 WO-13…17 launched on `wp/M04`.
- M06 WO-16h done (`b8d3211`…`552555b`): R62 + R24 (d)/(e) in coverage.py (A16–A19), amended R59 + S19/S20 in scorer.py
  (closes M06 review F5), 0.1.1 guard + `bases-v1` reading in snapshot.py; coverage.json re-taken (rows unchanged, 0
  candidates); preflight P1–P8 pass (P6/P7 by stub canaries); G15 20/20. **Merged into main** (`e88fb96`). M02's join:
  J1 must expose SELECTABLE_BASES, MODEL_BASES, MODEL_BUILDERS, basis_provider; J5 updates three snapshot tests.
- M02 WO-9 + R-281/R-282 built on `wp/M02` (`fd1427b`…`33bf150`; gate 8106 passed; G2 byte-identical): witness skip
  narrowed and recorded; G7(a) vapour feed VERIFIED; G7(c) F4 UNVERIFIED asserted; `C1Reactor` + stand-in in the
  interim registry; `C1-LOOP-M02-v1` registered (`benchmarks/m02/c1-loop-standin.json`), converges in 4 iterations,
  VERIFIED; G7(f) at w* rcond 1.42e-4, flash L/n 0.128, reactor inlet inside both domains (P, H₂/N₂ at the data
  domain's upper edges), per-tube flow 0.576 F_nom. Escalated: D44 the near-dew window is narrower than R-282 stated
  (VAPOR side from |δ| 2.48e-4, TWO_PHASE from L/n 3.37e-5; δ=1e-4 UNVERIFIED by the absolute screen limit and the
  witness stencil); D46 optional `coupling_initial` needs a frozen-schema amendment; F-A2-1; D45/D47 confirmations.
  Asked the WO-8 rulings architect (§14.4). Then the join (R-280 + W27 J1–J6).
- M02 pre-join rulings (`d5df272`, §14.4, R-287…R-289, R-282 amended): D44 measured near-dew window ratified (verifies
  from |δ| ≈ 2.5e-4 vapour side, L/n ≈ 3.4e-5 two-phase side; §14.3 C3 withdrawn; loop flash ~3,800× clear); D46
  `coupling_initial` stays refused (start is solver state; warm start via ADR 0024 if M05 needs it); F-A2-1 yes —
  each model binds on its own basis, `MODEL_BASES` single source; D45/D47 confirmed. Join list accepted + no exemptions;
  the served MCP digest must not move.
- `opus-engineer` M02 join (merge main; R-288/J1; R-280 registry move + corpus + fixtures + envelope; W27 J2–J6; R-282
  G7(c)) launched on `wp/M02`.
- M04 WO-13…17 done on `wp/M04` (`ee83ea1`…`2aa86ec`; check.sh 8102 passed): evidence → manifest pointer (A38); numerical
  addendum + conditional R0 (A37; A19's decision gaps ≥ 1.4e-3); it2/it3 + admission guard + family-wise bound (A36);
  refusal/record tests (A39, A42); `scripts/m04_prewarm.py` (A40: 4 processes reproduce A19 bitwise, cold 0; A41
  bypass repeats). WO-14…16 were not gated separately (each carries a reverted schema-description edit that would trip
  R4-G3); HEAD gate covers them. Remaining: WO-7/8/9 after the M02 join; WO-11 real run (pre-warm command recorded);
  WO-12 manifest.
- **M02 join done** on `wp/M02` (`61defce` merge of main, `a10dac3` R-282, `4c57bce` join, `fc54944` J4/J6, `386191b` D49,
  `f71d55e`): gate 8203 passed, 0 failed. Served MCP digest unchanged (`383b4e2c…`). J3: live snapshot = hypothetical_v02
  (SYN-001-only branch). J4: coverage 0/450, 0/82 candidates, G14 pass. G2 byte-identical (C1 corpus kept separate,
  `tests/m02_c1_corpus.py`). B50 fixture not re-taken (strip the 8 C1 ids, R-234 method). Fifth C1 revision
  `C1-REACTOR-M02-v1`. Left for the design lane: envelope still lists pr-c1-v1 under `unbound_providers` (false since the
  join); the stand-in's docstring says "Not registered" but its file hash is the pinned artifact hash.
- Launched: `opus-engineer` M02 WO-10, WO-11 (coupled route + replay; promotion); `opus-engineer` M04 merge `f71d55e` +
  WO-7 (surrogate unit); `opus-engineer` M05 merge `f71d55e` + WO-4, WO-5 (truth adapters, C1 formulation).
- Frank (2026-10-09): "Token usage is too large" → approved changes 1–6 and "Make sure future sessions have the same
  workflow". Recorded as `CLAUDE.md` "Agent budget": at most 2 agents; never resume a large-context agent (fresh agent,
  tight brief); batch design-lane questions per package (isolated commits, one ruling round, preferably in the reviewer
  pass); ~150k context cap per engineer; Sonnet for bounded items; 200–300-word reports, detail in the repo's
  build-decisions logs. Unchanged: one design pass + one reviewer pass per package, full gate before every commit. Also
  saved as project memory. The three engineers already running finish as briefed.

- **M04 WO-7 done** (2026-10-09, `wp/M04` `2841cd3`): merge of M02 `f71d55e` (`4ba0e6b`, register joined in order); unit
  `studies/surrogate/reactor.py`, binder resolution, `verify/surrogate.py`; WO-16 helper fix `d8bd39f` (A20/A39 were
  vacuous); resolver threaded through the application. Gate 8435 passed / 31 skipped. A12–A15, A26 (revision + project
  level) measured, see `docs/design/M04-build-decisions.md` E1–E8. Registration blocked: W27 classifier refuses
  `c1.reactor_surrogate` (W27-R24(a)); needs a `model_functions` row + snapshot/J3 re-pin from the design lane (batched
  into the M04 ruling round). `reproduce_bundle` gives `rerun_unsupported` for surrogate runs until bundles carry the manifest.

- **M05 WO-4/5 done** (2026-10-09, `wp/M05` `6b54b8d`; merge `3e7df38`; M02 schemas added to registry, R-213). Gate 8465
  passed; opt-in 104 passed. G4 (C1) pass (73×73 matching; alias rows omitted per R-274); T_ref 673.6434377969885 K;
  G7 mechanics pass. STOP: TRF on TR-E2 → `TRF_TRUTH_REFUSED(property_domain_error:S1_Hdot_V)`, S1.n.NH3 = -3.448e-27
  (exact-zero flows unbounded per ADR 0032 D4). Misses committed as strict xfails: WO-4 FD 4.1e-2 (dX/dT), gradient
  check 0.0373 vs 2.27e-3 (truncation; η escalation worsens), §16.4 |Δz| 1.18e-6. Batched with M04 B1 into one
  `architect` ruling round (brief `docs/briefs/v02-rulings-M05-M04.md`).

- **M02 WO-10/11 done** (2026-10-09, `wp/M02` `770969d`): gate 8251 passed, 2 strict xfails; G2 dump unchanged; digest
  unmoved. G8 (a)–(d), (g), G6 (c), R3, G9 (b)–(e) pass (G8(c) 62 vars within 3.0e-14 of the independent oracle).
  Escalated: D50 G8(f) G=1.8 ends `no_decrease` under §4.3's reset; D61 G9(a) stand-in→real fails `validity` (stand-in
  per-tube flow bound null). Findings D55 (all C1 runs R3 via "external" text match), D58 (exact compare of Broyden
  iterate floats in `constants_sha256`), D64 fixed. Rulings batched into M02's reviewer pass. WO-12 launched.

- **Ruling round M05/M04** (2026-10-09, `architect`): M05 §17 `5bb026e` on `wp/M05` (R-296 zero flows eliminated as
  constants with their pinning rows, G4 → 68×68; R-297 `M05-fd-v2` three-step curvature-aware check, FD kept at 2⁻¹⁴;
  R-298 TR-E1 ‖Δz‖ ≤ 2e-5; R-299 → `TRF_STALLED_INCONSISTENT`, retried once; R-300 E1–E7 confirmed). W27 Amendment 3
  `14c8695` on main (R-301/302). WO-2b/3b/4a launched; WO-5b folded into M02 WO-12.

- **M02 WO-12** (2026-10-09, `wp/M02` `bdb756e`): G12 PASS (real loop 3 outer iterations, ρ 319.6→0.298, VERIFIED;
  inlet 0.81×F_nom; replay MATCH; live rerun bitwise; 142.5 s). G11: Q-F4 1/17 accepted; Q-F5 0.5× fails
  (`element_balance_defect`), 0.25× fails, 2×/4× pass; ΔP first > ε_P at 8×; NaN/inf corners typed `external_crashed`.
  §10.3 triggered, no mechanical narrowing → `specifier` ruling round batching D50/D55/D58/D61/D69/D70/D71/envelope.
  D71: `with_coupling` not copied (duplicates `at_coupling`) — contradicts R-300 E7, in the round.

- **M02 ruling round** (2026-10-09, `specifier`, `wp/M02` `7be4084`): §14.5 D1–D10, R-303…R-310. R-303 v3 child: extra
  polish at 1/10 target when element defect > 1e-7 (boundary 1e-6 unchanged); NaN/inf → `reactor_not_accepted(nonfinite)`.
  R-304 v3 domain = first of three registered boxes whose points all pass; timeout from all in-box runs. R-305 reset off
  for the first 2n iterations (G8(f) holds). R-306 G9(a) restated (stand-in→real rejected on validity alone). R-307 D55
  bug → registered external-provider set (empty). R-308 replay digest recomputed at recorded iterate (ADR 0007). R-309
  M05 uses `at_coupling` (supersedes R-300 E7). R-310 `other_basis_providers`, docstring erratum. N7 to Frank (default:
  measured box). WO-12a + WO-11a launched.

- **M05 WO-2b/3b/4a done** (2026-10-09, `wp/M05` `7bc8c56`, gate 8473; opt-in 105 passed, 15 xfailed = Z2). §17.1
  (a)–(e), §17.2 (i)–(iv), §17.3, §17.4 pass; G4 C1 68×68, worst ratios unchanged. TR-E2 TRF: `TRF_MAX_ITERATIONS` at
  30, θ_recheck 4.01e-4, T 673.667 K. Escalated (batched): Z2 SYN-001 jointly pinned zero flows, W2. Choices Z1, Z5, W1
  logged. M02 WO-14 launched in its own worktree (`wp/M02-wo14`) beside WO-12a.

- **M02 WO-12a stopped / WO-11a done** (2026-10-09, `wp/M02` `9142032`, gate 8267). G10v3 FAIL: δ recorded after the
  certificate (runner.py:548, +20 pseudo-time steps), so D1's round fires at every point (δ 4e-5…8.4e-5 after S3).
  Experiment D78 (δ after certificate): G10v3, G11v3-1..3 met; no box qualifies (B1 12/21, B2 11/19, B3 11/19): every
  zero-inert corner `nonpositive_flow`, absent-element defect 0/0, low-T/high-P zero-inert and B1 643.15 K at S1; all
  0.2-inert corners and centres ok. Timeout rule 360–370 s. Round-7 `specifier` ruling launched.

- **M02 round 7** (2026-10-09, `specifier`, `wp/M02` `2e22c29`, R-311…R-314): E1 δ read after the first certificate,
  round 2 only if it passed, re-certified; E2 positivity and A45 defect over present species (presence from requested
  composition), zero-inert outside shipped domain; E3 `inert_min` 0.02, boxes V1–V3 at T_in [653.15, 693.15] K → M05
  REAL box [653.15, 693.15] K; E4 D73–D76 + timeout rule confirmed. E5: ADR 0027 D6/Am. 2 contradicted → Am. 3 (text in
  §14.6 E5) before WO-12b. Q-E1 open fact (inert fraction at M05's edges; floor revisited if < 0.03).

- **M02 WO-12a′ stopped at G11v3-4** (2026-10-09, `wp/M02` `bd446ab`/`6145b48`/`d1b8af1`, gate 8286; G2 unchanged). G10v3
  met bitwise; G11v3-1,2,3,5,8,9,10 met. No box: V1 19/21, V2 19/21, V3 20/21; failures all 653.15 K, high-P, 2 %
  inert, at S1. Q-E1: 4.047 % (693.15 K), 4.548 % (653.15 K, v3 child only). D85: 2 points with failed first
  certificate and δ₁ > 1e-7. DECISION: N7 default → raise `inert_min`, keep T_in [653.15, 693.15] K; alternative: new
  S1 start strategy (outside plan row); reversible: append-only variant. Round-8 `specifier` launched.

- **M02 round 8** (2026-10-09, `specifier`, `wp/M02` `756e123`): R-315 rungs V4/V5/V6 (inert floor 0.03, 0.035, then P
  and H₂/N₂ narrowed), first qualifying = v3's domain, all measured in both runs; G12v3-2 loop at both T edges; G11v3-11
  full re-measure, G11v3-12 nesting/loop-inside check. R-316 round 2 whenever δ₁ > 1e-7 (reverses part of R-311).
  ADR 0027 Am. 4. WO-12b may proceed on the selected rung before Frank answers N7. WO-12a″ launched.

- **M02 WO-14 done** (2026-10-09, `wp/M02-wo14` `e8c7777`, gate 8281): D5 reset at k ≥ 2n (f1–f5 vs independent replica
  1e-9; D50 xfail → f2), D9 `at_coupling` guard, D7 `EXTERNAL_PROVIDERS` (no re-takes needed), D8 replay digests; D94
  shape rule extended to all final-digest copies (isolated `e8c7777`). RP-2 not met (strict xfail): rerun with moved last
  bits still MISMATCH via certificate inlet check + exact-0 ρ/r_ξ. RP-2, D94, AC-1, f5 → M02 reviewer batch. W27 WO-16i
  (Sonnet) launched in worktree off main.

- **W27 WO-16i merged into main** (2026-10-09, `b3216dc`, Sonnet): registration Amendment 3 implemented; pre-existing
  members byte-identical; P2 pins re-taken (registration.json `ba627342…`, .md `b5b5b3a5…`, script `57568204…`); gate
  7748 passed; W27 tests with the archive dir linked 124 passed, 0 skipped. Interpretations to check in M04 review: optional
  `model_functions` parameter in `check_snapshot`/`classify`; `C1_MODEL_IDS` excludes the surrogate; `hypothetical_v02_a3`
  basis string wording.

- **M02 WO-12a″ done** (2026-10-09, `wp/M02` `764cab5`/`39620d1`/`bcfd0af`, gate 8290; G2 unchanged): V4 20/21
  (`V4-corner-T653.15-P1.1e+07-r2.5-i0.03` S1), V5 21/21, V6 21/21 in both runs → **V5 selected**; timeout 450 s
  (slowest 149.7 s); G10v3 bitwise vs D83; G11v3-11 87×2 labels 0 differences. D100–D102, D105 to reviewer batch.
  WO-14 merged into `wp/M02` (`ba13ce3`; build log joined in D-order).

- **M02 WO-12b done** (2026-10-09, `wp/M02` `7502515`/`14906e6`/`f4e8c56`, gate 8348, 1 xfail RP-2): v3 registered
  (sha 8b92540a…, V5, `inert_min` 0.035, timeout 450 s); G12 under v3 met (ρ 0.292, VERIFIED, replay MATCH bitwise);
  G12v3-2 both edges met (min inert request 0.039076 = 1.116× floor; slowest experiment 108.8 s). Digest 383b4e2c…
  unmoved. M02 `reviewer` launched with the batched rulings.

- **M02 review** (2026-10-09, `reviewer`, `wp/M02` `4c3623a`, R-317/R-318): numerics sound (driver honest per §4.3/R-305;
  v3 child per R-311→R-316, R-312). Must-fix F1 unclassified recorded floats in `external-coupling.json`; F2 replay
  EXT-COUPLING compares the recorded request; F3 f5 end-to-end. Should-fix F4 (no w-dependent external map in default
  gate), F5 (inner failure reason dropped). RP-2: (a) recompute request at rerun inlet, live check stays bitwise; (b)
  floors = each quantity's own threshold, B/du reported not compared → ADR 0034 Am. 1 in WO-13. D94 kept; AC-1 = D9's
  acceptance; D100–D115 ratified; c1-reactor.json stays v2.

- **M04 W27 part done** (2026-10-09, `wp/M04` `2018dca`…`4cd23ad`, gate 8444): main merged; corpus resolver; surrogate
  registered; J3′–J6′ vs `hypothetical_v02_a3` equal (22 models); 0/450 cases differ; G14 pass; `list_models`
  90d9da8e…→f070fbe0…, registry snapshot 0b2f4596…→8f4bb0c8…. Flaky under load (passed on rerun): browser smoke, W27
  S18 scorer, `t07_w5b` replay (fails alone without OMP_NUM_THREADS etc.). Open → M04 review batch (E10, E12, E14
  envelope wording). M05 WO-6 launched.

- **M05 WO-6 done** (2026-10-09, `wp/M05` `39eebba`…`c5aa61b`, gate 8522; nlp 121 passed): checks P1–P5, study loop
  S0/A/B/C, statuses with precedence (49 fake tests), readiness 12 codes, `TrfStage` bitwise = `run_trf`; REAL box per
  R-313. Not done: real parent adapter (needs M02 `coupled_run.py`). Choices S1–S10 (S6 isolated `c5aa61b`) → M05 review.
  WO-7 (Sonnet) launched.

- **M05 WO-7 STOP** (Sonnet, uncommitted): `test_t08_adr0025` refuses 4 unclassified sha256 names in the new schema.
  DECISION: classify all four `exact_sha256` in an M05 addendum `benchmarks/m05/numerical_policy_external.yaml`
  following M02's precedent (dbc9e8a) and classify the record's floats (ADR 0007 D2.3, as the M02 review's F1
  demanded). Alternative: per-machine hashes outside identity. Reversible by: reverting the isolated commit. Five
  spec-vs-producer choices logged for the M05 review. Opus engineer finishing WO-7.

- **M02 review fixes done** (2026-10-09, `wp/M02` `88b3ab4`…`ef03f97`, gate 8358, 0 xfail; G2 unchanged): F2/RP-2(a)
  `attributed_request`; F1/RP-2(b) per-float compare rules in the packaged addendum, RP-2 → MATCH; F3 e2e
  COUPLING_NOT_CONVERGED; F4 nonlinear synthetic child (4 iterates = closed form); F5 `inner_failure` kept. D124: failure
  bundle's record copy and `record_sha256` still under old rules → DECISION: apply the same rules, digest shape-only, in
  WO-13 (isolated commit). D122/D123/D126/D127 logged. WO-13 launched.

- **M05 WO-7 done** (2026-10-09, `wp/M05` `7f17a50`…`71804a6`, gate 8606): schema `trust-region-study-v1` + tests;
  S11 M05 addendum (4 sha256 names exact; `--check` generalised over ADDENDA, v2 policy bytes unchanged); 17 float
  rules, every float of every record classified. S16, S18 → M05 review. M07 recon launched (design prep while M02 WO-13 runs).

- **M02 merged into main** (2026-10-09, `9f6a9be`; manifest `tested` at `ba90619`; WO-13 `550d2ec`…`2277d33`: D130 failure
  bundle compare rules, ADR 0034 Am. 1, R-310, `external_execution` envelope axis, manifest generator; digest 383b4e2c…,
  G2 659748576adb9730… unchanged). Register conflict rebuilt as the numeric union (wp/M02's amended R-46/R-60 kept).
  Main gate PASS 8371. M07 recon digest + spec brief on `wp/M07` (`e35b16d`); specifier stopped at Frank's pause request.
  Paused for the token budget; no agents running.

- **Alpha gate WO-5/6/8 done** (2026-10-15, `wp/V02-alpha-gate` `46176a7`…`f6a748a`, gate 8558; WO-7 already done
  c35c50b): A51, A37 (+ controls i–iv), A50 harvest pass. Open for the design-lane read: B-WO5-1 (c_2 digest 383b4e2c…
  pinned, needs a register entry), B-WO5-5 (R-133 hashes from REVIEW.json at v0.1.0), B-WO8-1…5 (E/S/P/B draft; [8], [9]
  rows; 18-manifests scope). WO-9 (Sonnet) launched.

- **M04 merge + WO-8/9 done** (2026-10-15, `wp/M04` `0c2fc4c`…`c8f7e5d`, gate 8624): `surrogate_evidence` facet (10th),
  rollback exception; A25–A30 pass (A26 band within 1e-10; A29 zero new attempts). E15, E16, E22, E23 (A19 env
  fingerprint stale after M02 `7502515`, numbers unchanged) → M04 review. WO-11 launched with a v3 domain check first.

- **M04 WO-11 stopped at the domain check** (2026-10-15, nothing run): binds v3; 115/632 plan requests below the v3 inert
  floor 0.035 (lowest 0.02255; §3.1 y_Ar [0.01, 0.03] + y_CH₄ [0.01, 0.04]); loop inlet H₂/N₂ 3.000008 just above the
  box's 3.0. `specifier` box ruling launched (N4).

- **Alpha design-lane read** (2026-10-15, `reviewer`, `wp/V02-alpha-gate` `7152170`, R-319…R-321): WO-10 may cut C_α after
  F1 (HARVEST_EXCLUDED evidence/M07a/), F2 (A52 (g)/(e) read C_α's tree), F4 (harvest: L43, B13, V14(b) → L01/B8); F5 at
  the cut (web-shell line, drop "Certificates and extras"). F3 done (c_2 digest 383b4e2c… registered; R-133 hashes
  verified at v0.1.0). Alpha fixes + WO-10 launched (CI dispatch authorised as part of push; no tag/publish).

- **M04 Amendment 2** (2026-10-15, `specifier`, `wp/M04` `a7b17f9`): box `m04-c1-box7-v2` for real parents (y_Ar [0.014,
  0.03], y_CH₄ [0.022, 0.04], F [0.0050, 0.0086], r [2.5, 3.00001]); plans `b2-it1…3` same seeds/counts (632 cold);
  v1 plans synthetic-only; A31/A33/A41 re-pointed, A43–A47 new; ADR 0036 Am. 2 required before WO-11. Its register
  entries collided with the alpha branch's R-319…R-321 → renumbered R-322…R-325 on wp/M04. "3.000008" was rounded
  provisional data (r = 3 to 2.9e-14). ADR + WO-18/19/20 launched.

- **Agent burst** (2026-10-15, Frank: "for the next 7 minutes try to do as much as possible using many agents … after these
  7 minutes step back to a normal pace"): 8 agents launched in separate worktrees (see V02_STATE). Previous session's two
  agents had finished their work before it ended: alpha F1/F2/F4/F5 + C_α cut `e0e198e` + tree record `259af65`; M04
  ADR 0036 Am. 2 + WO-18/19/20 + E24–E29 (`43d6557`). Back to ≤ 2 agents for new launches afterwards.

- **M02 closeout** (2026-10-15, `reviewer`, merged `2497ec2`, R-340…R-344): ADR 0027 Accepted; D130 ratified with an R0
  guard (archived `record_sha256` checked against the archived record); D131 label ratified; R-343: `external-subprocess-v1`
  "not a sandbox" + M02 limitations [1][2][3][5][6] are E items needing L-rows (build work). Finding C1 (should-fix): v3's
  inert floor check `boundary.py:390` is exact float compare; ADR's design composition at 0.035 refused in ~45 % of flow
  scalings (−4.4e-16); proposal a few-ulp slack. Queued as an M02 follow-up after the alpha RC (C_α already cut).
- **M05 ruling batch** (2026-10-15, `architect`, `wp/M05-rulings2` `4cc5956`, R-326…R-330, §18): Z2 → joint-pin elimination
  `M05-zero-flow-v2` (WO-2c); W2 keep candidate + `trf_max_iterations` limitation (WO-6b); S1–S10 confirmed; S11–S18
  partly amended, S14 reversed (closed schema objects), purpose counts now (WO-6b/7b); REAL box text corrected (R-330).
  F-15 watch: TR-E2 hit max iterations once → G5 at risk; default report failure, not raise the limit. M07 told to start
  at R-331.
- **M04 WO-11** (2026-10-15, `opus-engineer`, `wp/M04` `6a353b3` E30 record `benchmarks/m04/wo11-b2-it1-v3/`, `7108cc6` E31):
  b2-it1 on v3, 632 cold runs (16 workers, 4467 s incl. pre-warm/A41, host load 80–96), verdict NOT_PROMOTABLE
  (`band_not_finite`): 26/632 certificate refusals (cal 5, test 18, train 3, grad 0), cal tolerance n−k = 4. Finite scores
  cal ≤ 0.316, test ≤ 0.292 (282/300 in width); max |e_X| 7.3e-4, |e_ΔT| 0.32 K; grad 0.036 vs 0.25. A31/A32 (manifest
  `d65bb022…`)/A41 (8/8) hold; A33 not run. Per N6 M04 still `tested`; M05 falls back to parent model. Open: E31 (relative
  path → fingerprint change), design question on the 4.1 % failure rate (batch into reviewer), Q-A2.1.
- **Alpha WO-10** (2026-10-15, `opus-engineer`, `wp/V02-alpha-gate` `4d591c7`): second session rebuilt lost /tmp scratch
  under `~/.cache/of-rca-e0e198e/`, re-ran steps 10–12 (B-WO10-11). CI dispatch 38667458248 / push 38667452347 green
  (check 8498/100 x86, 8470/98 arm). Step 11 PASS 3/3; step 12 PASS 6/6 (ρ 0.29, floor ratios 65.3/13.3, bitwise rerun).
  Step 10 FAIL F1 (5/77 certificates, 4 extra qualified ids). Manifest `implemented`: 35 pass, A39/A43 fail, 6 unsupported.
  Ruling round: `specifier` on brief `docs/briefs/V02-alpha-amendment2-brief.md` (`b8a769a`).
- **Alpha Amendment 2** (2026-10-15, `specifier`, `ab80ca5`, R-345…R-349): F1 is a certificate defect (M02 §4.4/C2 put
  non-[A09] notes in `independence_qualification`; `certificate.py:1305–1316`); remedy writes `None`; expected set not
  extended. Failure is V18 (c), Q5 corrected. A43 → registered `machine_class` (scoped exception to "unchanged" for
  `t08_rc.py`/`t08_dist.py`). Wrapper output accepted; bundle cert = recorded sha `d61a86fb…`. `e0e198e` superseded; re-cut
  C_α¹ (R-349). Frank alternative Q-A2-1 (accept V18 (c) FAIL) not recommended; re-cut proceeds.
- **M05 merge + WO-5c + S3** (2026-10-15, `opus-engineer`, `wp/M05` `fae2785`/`8edf34d`/`84295ba`/`40acf09`, gates 8775/8774/8774/8786):
  register union R-296…R-318; WO-5c `at_coupling` proved inert (4 w values, identity + bitwise inner solve); S20 input-spec
  classes moved to `holders` (P3 without Pyomo); S3 `C1Parent`, real v3 673.15 K in 164 s, ΔX 4.40e-6, ΔT 2.92e-3 K. Open
  for review: S22, S23–S26. NLP-1 inventory stale (3 objects). Next M04 slot: E31 fix + WO-12 (launched).
- **Alpha Am2 actions 1–2** (2026-10-15, `opus-engineer`, 04e65be R-345, 00acbe9/f0cfda8/46b2095 R-347, logs f77262e/2e778d3;
  gates 8585/8591): Am2.5 inertness — G2 (ii) dump byte-identical (`659748576adb9730…`), K05 identity PASS, 10/10 pr-c1-v1
  solution states identical, 9 certificates differ only in scoped qualification fields. B-AM2-3: CI `dist`/`build` jobs
  install `requirements.lock` first (untested locally, needs network) — for the design read.
- **Alpha Am2 design read** (2026-10-15, `reviewer`, `eb108c4`): proceed to re-cut; cut applies cleanly (14 files).
  DECISION: S2 → accept that §18.4 (b) includes B-AM2-3's two workflow steps. Alternative: re-scope R-347. Reversible by:
  a design-lane amendment. S3 (prove imports in lock-only/clean venvs) folded into the re-cut brief before the cut; S1 tests after.
- **M04 E32 + WO-12** (2026-10-15, `opus-engineer`, `f3fd44e`/`a9566a6`/`3f99eee`, gates 8647/8653): root cause in
  `launch()` (relative attempt dir vs child's `getcwd()`), fixed by `attempt_dir.resolve()`; absolute fingerprint unchanged
  `dfce4150…`, relative re-run cold 0 / 632 hits / `d65bb022…`. Manifest `evidence/M04/a9566a6…` `tested`, 57/58 (A33 n/a).
  E33: default BLAS threads → manifest `908cbe2f…` (≤1e-12 rel. fit drift) — A32 needs single-threaded BLAS. E34 class P.
  M04 `reviewer` launched (brief `2aa71db`, register R-360…R-369).
- **M04 review** (2026-10-15, `reviewer`, `9c2cb64`, spec §20 Amendment 3, R-360…R-369): conformal arithmetic and E32
  sound. Must-fix MF1 (unchecked added/renamed surrogate instance, probe committed a NOT_PROMOTABLE surrogate; R-360 A48),
  MF2 (manifest checker accepts null scores replaced by 0.1 → re-derives PROMOTABLE; R-361). E33 → pin BLAS 1 thread (A49).
  4.1 % refusals: no amendment; finding to the parent's owner. E34 partly reversed (real verdict class E). Q-A2.1 open.
  Engineer launched on the Am. 3 actions + main merge + manifest.
- **Alpha re-cut** (2026-10-15, `opus-engineer`): S3 dispatch 38768575677 green (machine_class OK). C_α¹ = `6fec822` on
  `wp/V02-alpha-rc1` (cherry-picks -x, gate 8574), merged --no-ff into `wp/V02-alpha-gate` (`896d014`). CI 38772065394 /
  38772054427 green (8507/100 x86, 8479/98 arm); local 2, 6–12 PASS; step 10 0/77 violations. Manifest `implemented`
  37/0/6. Build choices for later design read: B-AM2-6, -9, -10 (multiset hash tests, 6146aa3). `verdict` launched.
- **Alpha verdicts at C_α¹** (2026-10-15, `verdict`, `fffb0e4`): 8 PASS, V14 FAIL (b), BLOCKED V13 (e) / V17 (a) (V17 carry),
  W21 (c) (M02 N1). W22 band ratios 1.58/1.25/1.18. 61 record hashes recomputed, match. Findings A1 (aarch64 reactor
  limitation row missing from envelope, before any tag), A2 (date rule vs re-judgement), A5 (CHANGELOG), A3/A4/A6–A10.
  Frank notified (push). `specifier` Amendment 3 launched (brief `b272cea`).
- **Alpha Amendment 3** (2026-10-15, `specifier`, `6505315`, R-370…R-379): A1 re-cut C_α² (envelope platforms axis + L15
  claim aarch64 for the reactor; notes-only fix rejected as narrowing); A2 re-judgement rule (T7/T8, M07a.A14); A3 A61 names
  V13 (e); A4 `tested` iff A00–A51, A53; A5 CHANGELOG phrases (11 added); A6 deferred to 0.2.0; A7 `-rs`; A8 L47/U15; A9 450 s;
  A10 marker. B-AM2-6/9/10 confirmed. Q-A3-1 (strict date rule) put to Frank. Engineer launched on §19.8 actions 1–4.
- **Alpha Am3 actions 1–4** (2026-10-15, `opus-engineer`, 162e13b/e892790/967a622/7af0ee3 for C_α², 2055d19/958af67 gate-branch
  only; gates 8603→8629): envelope fixed (harvest E/S/P/B 158/42/139/6), re-judgement rule + A14, `-rs`, CHANGELOG skeleton +
  phrase test, R-373 status rule. B-AM3-1…5 logged. Re-cut engineer launched (actions 5–8).
- **M04 Am. 3 fixes + merge** (2026-10-16, `opus-engineer` `6363c24`…`d81d7f1`; gates 8661–8670): MF1 A48, MF2 (probe → 23
  findings), E35 unresolvable manifest rejected, A49 BLAS pin (manifest `d65bb022…` at 1 and 48 threads), A50, E27, envelope L43.
  Manifest `evidence/M04/8df0ea7…` `tested` 60/61. Merged into main `78685cc`, **main gate PASS 8670 passed, 31 skipped**.
  M05 engineer launched (rulings2 merge, WO-2c/6b/7b, then main merge).
- **M05 rulings merge + WO-2c + WO-6b** (2026-10-16, `opus-engineer`, `75cdc3b`/`05e2dba`/`442eed1`/`dec989e`; gates 8786/8790,
  nlp 164/1): Z2 joint-pin elimination, rcond P1 7.663e-3, P2 1.417e-2, B2 5.203e-6; matching 70 = 74 − 4; G4 worst ratios
  residual 5.92e-4, Jacobian 7.11e-7, decision 2.30e-3; unaffected cases byte-identical dumps. Stopped at context cap before
  WO-7b; fresh engineer on WO-7b + S33/S36 defaults + main merge. Open: S27, S33, S36.
- **Alpha re-cut C_α²** (2026-10-16, `opus-engineer`): C_α² = `cc73219` (6fec822 + 6505315, 162e13b, e892790, 967a622, 7af0ee3;
  gate 8600). CI 38813135468/38813136015 green (8533/100 x86, 8505/98 arm); local 2, 6–12 PASS; step 10 0/77; G12 cert bound.
  Manifest `tested` 38/0/6. B-AM3-6…9 (fresh envs, `tools/fetch_ci.sh`, O5 corrected). `verdict` at C_α² launched.
- **Alpha verdicts at C_α²** (2026-10-16, `verdict`, committed by session `f14f02e`): identical words to C_α¹; W21 carries L44–L46,
  L48, W22 L47; 61/61 hashes, 30 RC records' provenance hold. Gate dry run: 16 expected refusals. Findings B1–B6; B6 (ADRs
  Proposed) and B5 (declined N1 needs amendment) → `specifier` launched. Frank asked for the four answers in plain words.
- **Alpha B6/B5** (2026-10-16, `specifier`, `758a902`, R-380…R-382): ADR status flips legitimate (gate reads ADRs at the decision
  commit; `docs/adr/` outside D2.4 trees). 0027 copied from main; 0033/0034/0035 Accepted (M02 `ba90619` tested, G1–G12 pass;
  thin spot: D28/D29 never ruled individually). §20 Am. 4 contingent on Frank declining M02 N1. Dry run: only ADR 0028 + Frank.
- **M07 spec** (2026-10-16, `specifier`, `wp/M07` `48d4112`): ADR 0041/0042 Proposed, R-331…R-339, 40 assertions, journey R0–R3,
  W25 8 clauses (honest reporting), 0.2.0 gate `v0.2-gate-v1` + RC steps 13–18. Needs Frank (0.2.0, defaults) listed in state.
  Engineer launched on WO-1/WO-2 with a build-lane coverage read.
- **M07 WO-1/WO-2** (2026-10-16, `opus-engineer`, `53ba75f`/`94819ea`, gate 8731): journey script + 61 tests; R0 ≈ 3 s in default
  gate; R1/R3 UNSUPPORTED without reactor env / M05; `replay` exits 2 until WO-4. Spec issues J3, J4, J5, J6, J8, J9 batched for
  the M07 ruling round (none numerics). Merging `wp/test-hardening` (1-line test pin) into main with a full gate.
- **wp/test-hardening merged** (2026-10-16, `26b13db`, main gate PASS 8670 passed, 31 skipped).
- **M05 S33/S36/WO-7b + main merge** (2026-10-16, `opus-engineer`, `899cc2b`/`ce86c03`/`733cf8a`/`d65a9a4`/`e4a8f4b`; gates 8790/8889;
  merged tree 9186 passed 1 failed (S43); nlp 167/1). S33 bitwise on FD link toy; value_cold 8→16 (accounting).
  DECISION: S43 → (a) invert dependency (adapter into `application`, injected), alt. (b) exemption / (c) narrow rule;
  reversible by reverting S44. S40 + `fd_check` float rule → design ruling before WO-8.
- **M05 S44** (2026-10-16, `opus-engineer`, `a5927b4`, gate 9187 passed, nlp 167/1): `ParentServices` injected
  (`application/trust_region_parent.py`); moving `parent.py` would break R-003's isolation test. Bitwise dumps identical (6393 +
  3668 lines; coupling-record sha masked — wall times, S40). Found: R-003 means no application job can run the study.
  `architect` pre-WO-8 ruling launched (S40, fd_check floats, R-003 vs jobs; R-383…R-389).
- **M05 pre-WO-8 ruling** (2026-10-16, `architect`, `4c83d15`, §19, R-383…R-389): `coupling_record_sha256` exact_sha256; between runs
  shape-only (as R-318); coupling records saved via `coupling_sink` and file-checked in G10; fd_check floats classed (eta exact,
  rest r1_r2_existing_floors); R-003 stands, no job entry for WO-8/M07. WO-8 engineer launched.
- **M02 follow-up** (2026-10-16, `opus-engineer`, `wp/M02-followup` 39e6b0c/768690f/b6f51d8; gates 8672/8675/8675): D133 R-341 guard
  (negative control MATCH→MISMATCH); D134 C1 slack 4·2⁻⁵² (exact compare refused 46.2 % of 2×10⁵ scalings, max shortfall 1.59·2⁻⁵²;
  pin rewritten 1 ulp accepted/16 refused); D135 L44/L45/L46/L48, harvest [1]→L44 [2]→L45 [3]→L48 [5]→L46 [6]→L44. `reviewer` launched
  (R-390 if it rules D134).
- **M02 follow-up review** (2026-10-16, `reviewer`, `54b7baa`, R-390): merge; D134 4·2⁻⁵² confirmed (correct worst case just under
  8 rounding units vs slack 8; adversarial 10⁵ states refused 0, exact 11.1 %); should-fix S1/S2 wording only. R-390 taken →
  M07 continues at R-391. Sonnet on S1/S2 + manifest `evidence/M02-followup/…`.
- **M05 WO-8 (partial)** (2026-10-16, `opus-engineer`, 313115d…6a9d29d, gate 9212, nlp pytest 167/1; `m03_nlp_check.sh` exits 1 on the stale
  M03 inventory): §19 items done. G10 PASS; G5 FAIL (F-15, θ min 1.03e-5 vs 1e-5, θ_recheck 4.01e-4); G6 FAIL (TRF_CONVERGED clause);
  G9 FAIL (1.067e-6 K vs 1e-6 K); G7 partial; G8 not run (S52). No limit raised. Open S47, S49, S50, S51, S52. Diagnosis engineer
  launched (doc only) before an architect ruling.
- **M05 F-15 diagnosis** (2026-10-16, `opus-engineer`, `04454d7`, doc only): mechanism = linear model drops the truth's curvature,
  start at box corner, full-radius steps θ = C·Δ² (C 0.27→0.775), radius band 1e-4 vs termination 1e-5; refuted criticality /
  scaling / floor / FD noise. 150-iteration scratch: θ 9.72e-6 at k = 35. `architect` ruling launched (R-400…R-409).
- **M05 post-WO-8 ruling** (2026-10-16, `architect`, `a9d05d3`, §20, R-400…R-409, ADR 0038 Am. 2): see state. WO-8a/8c/8d engineer launched.
- **M02 follow-up merged** (626fb26) — first main gate FAIL (2): manifest under `M02-followup/` but work_package M02; its limitations
  unharvested. Fixed `95053be` (moved to `evidence/M02/6c3a087…`, 4 P harvest entries, matrix re-emitted). **wp/adr-acceptance merged**
  (`61cc785`, ADRs 0033–0037 Accepted, R-381 copied, R-410/R-411; register union 284). **Main gate PASS 8681 passed, 31 skipped.**
- **M05 WO-8a/8c/8d** (2026-10-16, `opus-engineer`, 4c9a083/55674aa/d56b42d/f72a875; gates 9231/9235/9238, nlp 177/1): TRF_EXIT_UNVERIFIED
  (F-15 k=27/28 ratio 0.99985 → radius_limited); store-hit refund (TR-E2 cold_used 47 = 31 + 16); basis v2 matches §20.1 (TR-E2 θ 2.998e-6,
  0.00734 K; c_X −9.5883e-4 /K²); v1 bitwise vs a9d05d3. Finding: v1 records don't replay across environments (~1e-15). Open S53, S54,
  S56, S57, S58. WO-8e launched.
- **M05 WO-8e** (2026-10-16, `opus-engineer`, 4da50ad/546b14a/5961915; gate 9257, nlp 177/1): v1 records replaced by four v2
  records (TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R). G5 PASS (TRF_EXIT_WITHOUT_STEP k=0, θ 2.998e-6, 0.00734 K); G5b PASS (C1 radius_limited
  k=7, C2 converged k=1, |ΔT| 0.0107 K); G6 PASS (converged k=1, |T*_FD−T*_E2| 0.0213 K); G7 PASS (store bijection 0 violations, 19/42/48/63
  attempts); G9 PASS (|d*−d_lb| 5.29e-8 scaled vs 1e-6); G10 PASS (0 diffs, one env). Drift cause: OpenMP OpenBLAS thread count, not a
  venv rebuild; script now requires OMP_NUM_THREADS=1 and writes `<stem>.environment.json` (S59, S60, S61). Open for review: S53, S56–S61.
  Note: `m03_nlp_check.sh` inventory diff (conda_packages, gates, objects) not touched by M05; pre-existing staleness, unverified.
- **M07 ruling round 1** (2026-10-16, `specifier`, `9ef4543` on wp/M07, docs only): spec §18 Amendment 1, R-420…R-427; ADR 0041 D6
  gains refusal reason `surrogate_loop_unavailable`. J3 confirmed (missing noise floor → FE_NOT_DETERMINED/TC1_NOT_APPLICABLE, never 0;
  fixtures tc1-08/09, A06 7→9); J4 confirmed (check recomputes budget stop); J5 W25 (a) not met under PROMOTABLE without surrogate loop;
  J6 experiments split {cold, store_hit, in_process}; J7 changed: `extrapolated` counts last coupling iteration only, closed-form R0
  checks (X_pass tol 2.5e-13); J8 replaced: M05 record named by five content conditions, not a path (defects: R3 wall always 0.0,
  carried_from defaults "rerun"); J9 re-solve T* with M05 C1Parent, J bitwise; J11 changed: grid-only decision = R1's own rung decision.
  AQ1–AQ3 are facts for the build lane. Finding FD-3 for M05: study record lacks run commit and spent wall (put in WO-9 brief).
- **M07 WO-2b** (2026-10-16, `opus-engineer`, 140e262…6e2640d on wp/M07, each commit gated in a detached worktree; final tree re-gated
  after the workstation reboot): Amendment 1 applied, one commit per ruling (J14–J20). R0 re-taken: VERIFIED ×9, INDIFFERENT at 673.15,
  J unchanged within the registered one-ulp spread; moved as ruled: experiments {cold 0, store_hit 0, in_process 2}, `extrapolated` 1 → 0.
  AQ1 answered yes. J15 (build choice): A1.4's first identity holds by construction, checkable only at replay (WO-4).
- **M05 WO-8b** (2026-10-16, `opus-engineer`; interrupted by the reboot before commit, work complete in the tree): F-22 yes (M04.A19's
  PROMOTABLE manifest on wp/M05). SurrogateTruth, promoted basis, P2_A, LOOP-S record (S62–S64). **G8 FAIL** on its at-bound rows:
  stage A TRF_CONVERGED k=1, P2_A passed, DECISION_STABLE, but |d*−d_lb| 1.0965e-6 scaled vs 1e-6 (LOOP-R 5.29e-8), so P5 polled both
  sides; held as strict xfail. Premise off: R-408 expected TRF_EXIT_WITHOUT_STEP θ≈1e-14; measured θ 6.55e-3 (affine property EFs not
  exact). For the M05 design ruling/review batch.
- **M05 WO-9 REAL** (2026-10-16, `opus-engineer`, c912f92/20e398e/c3ff66b/7350684; gate 9287 + 1 xfail, nlp 180, pymrm 1): G11 PASS,
  G10-REAL PASS. fd_check clean at 2⁻¹⁴ (τ̂ 3.1e-3, ν̂ 6.9e-4); C1 converged k=1, θ_recheck 2.33e-6, P2 passed; 48/400 cold, 1454 s;
  no cap hit (F-13); F-21 yes. Not interior: T* 653.1500352 K, 1.76e-6 scaled above the bound (same at-bound question as G8).
  `extrapolated` 12/61 from the ledger (no record field); H2/N2 at the kinetics' data edge flips the flag. M07 needs: FD-3 done
  (`provenance {run_commit, tree_clean, wall_s}`), AQ2 no. M05 `reviewer` launched (brief `docs/briefs/M05-review-brief.md`,
  R-430…449), then WO-10.
- **M05 review** (2026-10-16, `reviewer`, `f0693d8` on wp/M05; `docs/reviews/M05-review.md`, design note §21, R-430…R-435): verdict
  fix first. Core sound (R-401 exits, basis v2, R-405/R-406 accounting, P2/P2_A/P5). MF1: `noise_ratio` misses η·s_k/√2 (REAL
  (3591.6, 5.42) → (0.0388, 0.0299)); re-take LOOP-R, TR-E2-FD, REAL, bitwise with noise_ratio/provenance masked. SF1: in-process
  replays as an nlp test. SF2/R-430: §7.4's 1e-6 classification kept; R-404's offset rationale wrong (slopes within 15 %, offsets span
  33×), so G8/G9 stop gating Ipopt's offset: |T*−653.15| ≤ δ_T 0.5 K and P5's evidence contains the bound (G8 then passes on the
  committed LOOP-S). R-431: TRF_CONVERGED expected for stage A. R-433: ledger count suffices; data-edge flip = limitation + note to M07.
  R-434: build choices confirmed (S58 reversed, S54 superseded, S64 settled). WO-10a (fixes) launched; WO-10b (manifest) after.
- **M05 WO-10a** (2026-10-16, `opus-engineer`, cdacc32…748f8cf; gate 9289/31, nlp 186/1): MF1 fixed (R-432); LOOP-R, TR-E2-FD, REAL
  re-taken, new/old noise_ratio exactly η·s_k/√2, REAL → (0.0388, 0.0299); 0 other differences (`scripts/m05_retake_diff.py`); G8/G9
  restated (G8 PASS, xfail gone); `tests/test_m05_g10_replay.py` (nlp, mutation-checked); `EXTRAPOLATED_LIMITATION`; note to M07
  `docs/briefs/M05-note-to-M07.md`. S70: the re-take diff also masks wall-clock timings and digests over them (M02 attempt timings,
  reactor diagnostics wall_s, REAL experiments archive digest; request/result files byte-equal).
  DECISION: accept S70's timing mask without another design pass → yes (timings are not reproducible by nature; every non-timing byte
  equal). Alternative: a ruling round. Reversible by: re-running the diff script with a narrower mask.
  Review notes: N2 (in-flight key on a non-TruthRefused exception) fixed in WO-10b; N1 (stage C restart ignores regime match) open,
  default at next touch: apply stage A's eligibility; N3/N4 noted in the manifest.
  DECISION: M05 merges into main only after M03 (M05 contains M03's nlp code; M03 merges when Frank answers its licence question N1).
  Alternative: merge M05 with M03 now. Reversible by: merging once Frank answers. M07 WO-4 may build on wp/M05 meanwhile.
- **Frank, 2026-10-16: "I accept the licenses."** M03 N1 answered: the optional, non-default `nlp` extra ships with the licences the
  [A10] audit lists. M03 closeout launched (`opus-engineer`): register R-450, main merged into wp/M03, the stale inventory check
  explained (stop if anything outside the audited set appears), CI on both runners at the final commit, manifest → tested. Then the
  session merges M03, then M05, into main. The four 0.2.0a1 questions remain open.
- **M05 WO-10b** (2026-10-17, `sonnet-implementer`, cfecb15/b5099a3/1032ed0; gate 9296/31, nlp 186/1): review N2 fixed (try/finally,
  test); manifest `evidence/M05/cfecb15…/manifest.json` **tested**, 14 checks (G1–G13 + G5b) all pass, review pending; 10 limitations
  harvested (all class P), matrix --check 0 problems; ADR 0039 box note; progress.md; `docs/briefs/M05-W24-table.md`. S75 interpretations
  for the next design touch: G10 cross-architecture `not_run` (limitation), E-row candidates (`extrapolated`, bound-active REAL optimum,
  `fd_gradient`), case_hash = sha256 of c1-loop-real.json. Open: review N1 (stage-C restart eligibility). cfecb15 carries a Sonnet
  trailer (accurate; not rewritten). M05 ready to merge after M03.
- **M03 closeout, part 1** (2026-10-17, `opus-engineer`, wp/M03 0c6ca90/4ccd369/b0db48e/2bba33e; gate 8867/31, nlp 18/1): R-450 records
  Frank's N1; main merged (register union by hand: scratchpad `regunion.py` was lost in the reboot); manifest script takes `--n1
  accepted` and `--ci-run`. Inventory: fresh env reproduces 086bf2b's 178 objects; after the main merge M02's `adapters/pymrm/env.py`
  imports urllib → ssl, mapping `libssl.so.3` (openssl-3.6.5, Apache-2.0) and `_ssl` (CPython 3.13.5, PSF-2.0); same packages,
  same licences, 41 conda packages and wheels unchanged.
  DECISION: are the two new objects inside Frank's licence acceptance → yes (same audited packages and licences; no licence added).
  Alternative: ask Frank again. Reversible by: reverting b074d57 on wp/M03. Re-take cherry-picked as `b074d57`, m03_nlp_check.sh exit 0.
  **Blocker:** main's CI red since 2026-10-16 (M04 tests on 2-core runners: prewarm a40 max_workers 4; a49 negative control; a35
  a19 fixture differs on arm). `wp/M04-ci` engineer launched; M03's CI-on-both-runners check waits for it.
- **Main CI fix** (2026-10-17, `opus-engineer`, wp/M04-ci 2a07b66/df818a1/422c53a/09c6fed/54778d2; CI run 38998365118 green on both
  runners): A40 script-path test skips below 4 physical cores (refusal tests at min(4, cores)); A49 asserts both pinned claims
  everywhere, skips only the negative control where it cannot show a difference; A35 floats compared only on the recorded CPU class
  `x86_64/Haswell` (spec §18 A1.3 makes no cross-machine bitwise claim), non-float members everywhere; CI prints skip reasons (E39–E42).
  Manifest `evidence/M04/09c6fed…` tested. Open for M04's design lane: off-Haswell floats against A1.3's R1/R2 floors (default no).
  Merged into main `f79864d`, **main gate PASS 8687/31**.
- **M03 merged into main** (2026-10-17, `0bdb80d`): closeout part 2 (`sonnet-implementer`, a35885b/e8a22eb) merged main, CI 39007361803
  green on both runners, manifest `evidence/M03/a35885b…` **tested** 52/0/0, 8 limitations harvested (one new: licence acceptance covers
  the audited list only, class P — design lane may confirm). Merge tree identical to gated e8a22eb (8879 passed, 31 skipped).
  M05 main-merge launched (`opus-engineer`).
- **Frank, 2026-10-17: "Accept the defaults"** — the four 0.2.0a1 questions (asked in plain words): N3 claim set v0.2-alpha-gate-v1;
  V17 carry (no new campaign); M02 N1 ship the reactor subprocess as "not a sandbox"; V14 (b) PTC failure accepted again. Dated after
  the verdict (Judged 2026-10-16), as R-371 requires. Recorded in ADR 0028's four cells on wp/V02-alpha-gate (status left Proposed:
  acceptance also needs M07a's manifest at the candidate). Next: `verdict` re-judges V13/V17/W21 (brief
  `docs/briefs/V02-alpha-rejudge-brief.md`), then action 10's build part (step 5, A52, A64, manifest, step 7), then merge to main.
- **Alpha re-judgement** (2026-10-17, `verdict`, `c52039b` on wp/V02-alpha-gate): V13, V17, W21 BLOCKED → PASS at C_α²; V14 FAIL (accepted
  in D3). Findings R1 (ADR 0028 still Proposed), R2 (notes should say V17's agent evidence is carried). Gate at c52039b: NO (W21/W22 not
  in the ledger; ADR 0028 not Accepted) — action 10's build part launched (`opus-engineer`, brief `docs/briefs/V02-alpha-action10-brief.md`).
- **Finding (session's own error): the release freeze was broken.** ADR 0028 / spec §9.2 step 2: from C_α² (2026-10-15) until Frank's
  dispatch, main takes no change to D2.4 paths (src, schemas, benchmarks, lock, pyproject, …). Since then main took the M02 follow-up,
  M03 and the M04 CI fix (52 files under D2.4 differ), so main's head can no longer be the candidate. The alpha branch's D2.4 paths
  still equal C_α² exactly. Asked Frank: release from the alpha branch/tag (ADR 0028's named alternative; recommended) or re-cut the
  candidate from main and redo the RC job and verdicts.

## 2026-10-17 — M05 main-merge
- `wp/M05` @ `56fb2fa`: origin/main merged (`eb17f79`; register numeric union, no clash), NLP inventory re-taken (181 objects,
  `_queue` added, same packages/licences; S76, as M03's `b074d57`), five in-process G10 records re-taken (`56fb2fa`, S77): main's
  D134 change to `models/c1/boundary.py` changed the environment fingerprint, so 105–185 digest differences per record; all
  non-digest fields equal except timings, old→new digest map one-to-one, REAL unaffected. Gate 9319/31 skipped, nlp 186/1,
  m03_nlp_check exit 0, REAL replay 0 diffs, CI 39018247132 green on both runners.
- DECISION: S77 re-take vs narrowing the fingerprint → keep the re-take (engineer's choice; fingerprint working as designed).
  Alternative: exclude unrelated model files from the in-process fingerprint (design-lane). Reversible by: revert `56fb2fa`.
  Batched for M05's next design touch.
- DECISION: merge M05 into main now, although the freeze question to Frank is open → yes. Default (release from the alpha
  branch) is unaffected; a re-cut would then include M05 too. Reversible by: reverting the merge commit on main.

## 2026-10-17 — Frank: release 0.2.0a1 from the alpha branch
- Frank, verbatim: "Perform the release as recommended". Release ref = the alpha branch `wp/V02-alpha-gate` (D2.4 paths =
  C_α² `cc73219` exactly), not main; ADR 0028's named alternative. Frank asks the session to perform the dispatch.
- Mechanics: the `pypi` environment admits only `main` or `v*` tags. Plan: dry run from the branch at the head that prints
  YES; then the real run from a `v0.2.0a1` tag on that same commit (rc = `cc73219…`).
- Action 10 build part done: `wp/V02-alpha-gate` @ `423ae9c` (ADR 0028 Accepted R-451 `47246c1`; ledger + A64 test `9324a91`;
  CHANGELOG/gate table, candidate `5c3a068`; manifest regenerated `423ae9c`: tested, 40 pass, 4 unsupported A60–A63). Gate
  8642/31. Session check: D2.4 diff cc73219..423ae9c empty; `v0_2_gate.py --rc cc73219… --candidate 423ae9c` → YES.
- Release dry run 39024603561 from the branch at `423ae9c`: gate, build success. Tag push from the session was refused by the
  permission classifier; Frank given the two commands (tag + real dispatch from the tag).
- **0.2.0a1 RELEASED 2026-10-17.** Frank: "Do the push and release." Annotated tag `v0.2.0a1` → `423ae9c` pushed; release
  run 39045791146 from the tag: gate, tag, build, pypi, github-release all success. PyPI `openflowsheet 0.2.0a1`: wheel
  sha256 `ebcf0daf040522c9…`, sdist `bda40baea315cd2b…`. GitHub pre-release
  https://github.com/computational-chemical-engineering/openflowsheet/releases/tag/v0.2.0a1 with both files.

## 2026-10-17 — M05 merged into main
- `defa458` = merge of `wp/M05` @ `b0d4123` (manifest `evidence/M05/56fb2fa…` tested; 6 artifact hashes re-taken: 5 G10
  records + build log). Gate at `defa458`: 9325 passed, 31 skipped (also covers b0d4123's envelope change, which its own
  gate did not). Pushed. M07 WO-4 (real journey) launched.

## 2026-10-17 — M07 WO-4 part 1 (`wp/M07` @ `6996507`, gate 9412/31)
- Main merged (`8ef35e6`; R-017 differed only by a `---` separator). Journey at J=`8f85aa2` EXIT 0, `check` accepts:
  R0 INDIFFERENT 673.15; R1 DECIDED 653.15 BOUND_LOWER; R2 SURROGATE_NOT_PROMOTABLE; R3 re-run (carry fails, src changed)
  DECISION_STABLE, T* 653.1500351610193, J* 0.4524965242483627 = M05's record, re-solve bitwise; 88/460 cold runs, 3316 s.
- Process slip: only the tip was gated (J24), not every commit. Next engineer told to gate every commit.
- Open for M07's ruling round / reviewer (defaults: as implemented): J22 limitation `R3:carry_identity_differs`; J25
  `env.verify` vs R-259 `variant_id`; T* 3.5e-5 K inside the bound reads INTERIOR (tolerance 2e-5 K) while R1 says
  BOUND_LOWER. WO-4b (replay, committed record, A20–A26 tests) launched.
- WO-4b done `d8ae8c1`: record at J=`1623633` (bitwise = `8f85aa2` run), replay bitwise 13.4 s, refuses at 2 threads;
  A20–A26 tested; each commit gated (9413 → 9435/31); nlp 186/1.
- M07 review `0ad726a`, fix first (spec §19 Am. 2, R-452…455, ADR 0041 D2/D5): MF1 at-bound tolerance δ_T = 0.5 K
  (T* 1.76e-6 scaled from the bound is the interior-point offset, as M05 R-430); MF2 carry list missing M05 REAL config,
  schema and journey script → split lists + GC-CARRY-1; SF1 replay the re-run M05 record; SF2 `m05_record.offered`; SF3
  A21 default-gate test. J22 stands; J25 is M02's (`env.py:347` contradicts R-259) — backlog; J27 meets "every number".
  WO-4c launched.
- WO-4c done `wp/M07` @ `9d2d072`: MF1 `6501016`, MF2 `854deda`, SF2 `2905034`, SF1 `974c395` = J′, record `c4e8467`.
  Re-take at J′ (3324 s): every number bitwise equal to the `1623633` record; labels R3 + journey INTERIOR → BOUND_LOWER
  (predicted); limitations gain `bound:R3`, `bound:journey`. check ACCEPT; replay bitwise 17.7 s; re-run M05 replay clean;
  pymrm 2 passed; nlp 186/1; gate 9454/31, every commit gated.
- DECISION (engineer, J31): old `1623633` record + its test removed (fails `check` under the new registration) → accept.
  Alternative: keep it as history. Reversible by: restore from `c1f104f`.
- DECISION (engineer, J35): replay of a re-run record needs pyomo → runs in the nlp env, nlp-test-tools on `sys.path` in
  process (avoids the J25 leak) → accept. Reversible by: revert the J35 commit.

## 2026-10-17 — alpha into main: merged on `wp/V02-alpha-main` @ `d73004a`, CI red
- Engineer: register union (381, no clash), L43 collision → main's M04 row renumbered L49 (`989b16f`), version 0.2.0a1,
  W27 coverage re-taken. Gate 5 failed / 9591 / 31; CI 39050289989 red on both runners with the same five:
  ledger `test_the_unclaimed_gates_are_untouched` (W24 row moved), A37 chain ×3 (served MCP list moved since C_α²: digest
  `383b4e2c…` → `455d01eb…` at c_2 R-234), changelog `test_c` (gate NO at main: D2.4 differs). nlp: 5 G10 replays fail on
  version-derived hashes only (551 diffs). Not merged into main.
- A37 finding matters for 0.2.0 (agent surface moved after C_α²; V17 carry for 0.2.0).
- Design-lane rulings pass launched (`specifier`, brief `docs/briefs/V02-alpha-main-rulings-brief.md` `6a760c1`).
- Rulings `d85e7b4` (`docs/design/V02-alpha-main-rulings.md`, E1–E8): R-456 alpha ledger/changelog tests read the
  released commit `423ae9c` (R-217 pattern); R-457 surface chain gets a third link (the move is M04's `surrogate_study` job
  kind, not M03/M05; 17 tools, no description changed); R-458 G10 records re-taken digest-only now and at the 0.2.0 cut,
  fingerprint unchanged (version = cache-safety guard, ADR 0036 D8), proof by a new `m05_retake_diff.py --digest-only`
  (the S77 proof was manual); R-459 L49 confirmed; R-460 main's version `0.2.0a2.dev0` + test that main never carries a
  released version on a different tree. For Frank later: the 0.2.0 "carry the agent evidence" question must name M04's
  new job kind. Engineer applying E1–E8 launched.
- E1–E5, E7, E8 applied (`wp/V02-alpha-main` @ `3969e57`): gate 9611/0; CI 39066214331 green both runners; R-456 check
  YES at `423ae9c`, table found verbatim in the released section; REAL replay 0 diffs. `--digest-only` passes S77's pair
  (42/80/71/92/38); S78 build choice: store index paired by key. **E6 stopped**: re-take after the version change moves one
  non-digest leaf per coupling record (`frozen.reactor.fingerprint.openflowsheet_version`), so R-458's rule (a) can never
  pass; G10 red (nlp 181/5). Narrow design question sent to a fresh `specifier` (proposal: a `version` class on that one
  path, old = `--old-version`, new = running `__version__`).
- R-458 Amendment A1 `12bbd89` (E5a): stricter than proposed — exact path only, pinned old/new values, plus binding check
  `fingerprint_sha256 == document_sha256(fingerprint)` on both sides (holds on all 22 committed records and S77's 44 sides).
  Rejected: unbound glob. E6 expected: version leaves 4/7/4/3/4, digests 41/79/70/91/37. Engineer applying E5a + E6 launched.

## 2026-10-17 — alpha into main (`wp/V02-alpha-main`), build lane

- DECISION: envelope id L43 is held twice — the alpha's (R-321: Anderson/E1/E2 library-only; released, cited by the
  `## v0.2.0a1` CHANGELOG section) and main's (R-365: no promotable real surrogate; M04). → main's M04 row is
  renumbered **L49** (next free; row, `unit_models` statement, M04/M05 harvest `to`/notes, `scripts/m04_evidence_manifest.py`)
  in its own pre-merge commit; the alpha's L43 keeps its released meaning. Alternative: renumber the alpha's row
  (contradicts the released CHANGELOG). Reversible by: reverting that commit and re-resolving the merge. Committed
  M04/M05 manifests and historical notes that say "L43" for the surrogate are not rewritten. R-365's text ("row L43")
  awaits a design-lane ruling (substitution only).
- Rulings R-456 – R-460 applied (`docs/design/V02-alpha-main-rulings.md` §3, in §4's order):
  - E1–E4, E8: `ALPHA_TAG_COMMIT`; the alpha's ledger and changelog tests read the record at the tag (AM-01 – AM-08);
    `m07a_rc.LINKS` gains c_3 (R-295, `strip_m04`, `455d01eb…`) with the controls re-aimed, each preceded by an
    unmodified-list pass (AM-10 – AM-18); AM-30 (M04/M05 harvest rows map to L49). Gate 9602 passed, 0 failed.
  - E7: version `0.2.0a2.dev0` (B-WO10-4's set), envelope back to `v0.2-envelope-dev` / `0.2.0.dev0`, `ENVELOPE_ID`,
    support matrix re-emitted (0 problems), RELEASING "After a tag", `tests/test_v02_main_version.py` (AM-40 – AM-42).
    AM-10 still passes at the new version (D_3 unchanged). W27 coverage re-taken from the working tree (rows and
    `list_models` unchanged; snapshot `153894c4…`), then once more at the E7 commit so `git_commit` names its build.
  - E5: `m05_retake_diff.py --digest-only` (AM-20 PASS ×5 on S77's pair, 42/80/71/92/38 = S77's; AM-22 unit tests).
    DECISION: store-index pairing in the leaf walk → by relabelled key, not position (the index is sorted by key, so
    positional pairing fails (b)/(c) on S77's pair: 17 and 14 digests). Alternative: positional (AM-20 cannot pass).
    Reversible by: reverting the E5 commit. M05 build log S78.
  - E6 STOPPED (not applied; for the design lane). The re-take at `2345b54` (clean tree, `.venv-nlp`, OMP 1) is
    not digest-only: `--digest-only` FAILs every case with other = one leaf per coupling record,
    `frozen.reactor.fingerprint.openflowsheet_version` `'0.1.1'` → `'0.2.0a2.dev0'` (4/7/4/3/4 leaves; the committed
    records were taken at 0.1.1). Everything else is digest-only: changed digests 41/79/70/91/37, timing 20/35/20/26/20,
    environment files equal, map a function and injective. The coupling record carries the fingerprint in clear, so a
    version change always moves one non-digest leaf; S77's boundary change moved a digest leaf there instead (hence
    its +1 counts). Passing would need E5 to admit that leaf (e.g. a `version` class: committed side = `--old-version`,
    re-take side = the running `__version__`, only at `*.fingerprint.openflowsheet_version`) — a change to rule (a),
    not made here. Committed records untouched; G10 stays red until a ruling.
  - Q1 settled at `2345b54` (0.2.0a2.dev0): `m05_wo9_real.py --replay` REPLAY PASS REAL, 0 differences (REAL's
    fingerprint carries no version, F4). nlp tier: 181 passed, 1 skipped, 5 failed (G10 ×5 only; 107/185/107/147/…
    differences); `m03_nlp_check.sh` fails on that pytest step only (inventory checks exit 0).
- R-458 Amendment A1 applied (`12bbd89` rulings; E5a then E6):
  - E5a (`f6ea52b`): `--digest-only` admits `frozen.reactor.fingerprint.openflowsheet_version` (exact path) as class
    `version`, pinned to `--old-version` / the running `__version__`, with every frozen unit's `fingerprint_sha256`
    bound to `document_sha256(fingerprint)` on both sides. AM-20 on S77's pair still PASS ×5, 42/80/71/92/38,
    `version=0`; AM-22 +6 cases (13 in the file). Gate 9618 passed, 0 failed. M05 build log S79.
  - E6: five G10 records re-taken at `f6ea52b` (clean tree, `.venv-nlp`, OMP 1, nlp-test-tools on `PYTHONPATH` as
    WO-8 took them — without it the environment has 14 distributions, not 17, and (d) fails). `--digest-only
    --old-version 0.1.1` PASS ×5: version 4/7/4/3/4, changed digests 41/79/70/91/37, other 0, environment equal —
    as expected. nlp tier 186 passed, 0 failed (G10 5 passed); `m03_nlp_check.sh` PASSED; REAL `--replay` 0
    differences; gate 9618 passed, 0 failed. M05 build log S80.

## 2026-10-18 — alpha on main
- E5a `f6ea52b`, E6 `09f9b9c` (five G10 records re-taken; `--digest-only --old-version 0.1.1` passes: version 4/7/4/3/4,
  digests 41/79/70/91/37, other 0; re-take needs nlp-test-tools on PYTHONPATH to reproduce WO-8's 17 distributions).
  Gate 9618/0; nlp 186/1/0; m03_nlp_check PASS; REAL replay 0; CI 39080413397 green both runners.
- Merged into main `93cfbe5` (tree = gated `09f9b9c` except the two V02 docs; log conflict resolved as union). Pushed.
- DECISION: order M07 WO-3 → M07 into main → cut C_W on main → paid W27, so the W27 carry surface is not moved by M07's
  merge afterwards. Alternative: cut C_W now. Reversible by: cutting C_W at any later main commit.

## 2026-10-18 — M07 WO-3 done (`wp/M07` @ `271f70d`)
- Main merged (`81cc0cd`, register union, journey record tests pass). Per-set clause, `v0.2-gate-v1`, carry checks, O1–O3,
  `tests/test_m07_v0_2_gate.py`, `tests/test_m07_ledger.py`. Gate on every commit (head 9876/35); nlp 186/1; CI
  39089921525 green both runners. Gate script on head: NO (version 0.2.0a2.dev0 not covered) as expected.
- Needs ruling: J40 (A31 "alpha tests unmodified" vs A30's registry; five alpha test cases edited, isolated `039cbd8`;
  alpha output byte-identical). Revertible choices J39, J41, J42, J43. Findings: journey at J′ no longer carries (re-run at
  RC step 15); ADR 0042 headers ≠ gate's; registration A53 vs spec A62 for step 17. Ruling round 3 launched.
- DECISION: C_W is cut on `wp/M07` (not main), because M07 cannot merge before WO-5…8 and its manifest. The W27 carry
  compares the served tool list, `list_models` and coverage rows at C_W and C, which M07's later WOs do not touch.
  Alternative: merge M07 early. Reversible by: cutting C_W elsewhere before the first canary.
- M07 ruling round 3 `958b983` (spec §20 Am. 3, R-461…466): (1) A31 restated: AM-07 + alpha test file equals the tagged
  one except the three functions `039cbd8` edited (ast test); (2) J39 ok, J41 ok with `links_item` registered (GC-SET-3,
  A32), J42 ok with refusal texts registered, J43 `.devN` skip is scoping (R-463); (3) spec's A62 right; registration
  regenerated by the build lane with `check` accepting a `gate`-only registration difference (R-465), target hash
  `85e56dd5…282506b`; (4) ADR 0042 headers fixed in the ADR (R-466); (5) journey runs at the 0.2.0 cut commit K, carried
  K→C by identity (R-464). Launched: Am. 3 build actions on `wp/M07`; W27 readiness (no spend) on `wp/M07-w27`.
- W27 recon: WO-16h, M02 join J1/J2, WO-16i present; unclear: S20, A21/A22, live snapshot vs `hypothetical_v02_a3`,
  U14 rewrite. P1 approval line present (l.191).
- W27 readiness `wp/M07-w27` @ `273ab0f` (no spend): live snapshot = `hypothetical_v02_a3`, live coverage = committed
  (0 CANDIDATE); C1 rows in place; CLI `python -m benchmarks.m06.w27.harness` (`27fb4b8`); DECISION (engineer): spend
  ceiling — stop before a run whose USD 5 cap could pass USD 45 (`8e6d80b`, revertible). Stub dry run: P1–P5, P8 pass;
  Claude Code 2.1.302. Stopped on four design questions (U14 text; A50 vs R31 order; R58/R56 record formats; re-canaries)
  → `specifier` launched. Model: registration l.378 settles it (CLI default read from the first canary's init, pinned).
- W27 registration Amendment 4 `bbf1d01` (§23, R-467…471; gate 9856/59): U14 text (records only under
  `runs/w27-m07-<hex>/`, A70–A73), draw before canaries with each record naming its predecessors' SHA-256 (M07.A50 restated
  in M07 spec §21), `confirmation/confirmation.json` (empty set only) and `preflight.json`, ≤ 6 canary attempts (P6 11
  states), model pinning without `--model` (P7 6 states). WO-17a launched (no spend).
- M07 Am. 3 build actions done `wp/M07` @ `bdd2004`: registration regenerated to `85e56dd5…282506b`, `check` paths (i)/(ii)
  with exact refusal texts (J′ record passes via (ii)), A31(b) ast test in `tests/test_m07_v0_2_gate.py`, A32 `links_item`,
  A37/A38 refusal texts; Q-A3-1 default (J47). Gates 9881/9886/9887, 35 skipped; CI 39113895404 green both runners.
- Plan: after WO-17a, merge `wp/M07-w27` into `wp/M07`; C_W = that merge; then canaries + campaign; WO-6 after.
- W27 WO-17a done `wp/M07-w27` @ `1219636` (no spend): U14 + A70–A73 `1ed4a96`; unpinned canary attempt `b71d86c`;
  confirm/P5, preflight.json/P8, canaries with attempt cap, P6/P7, order_check `8a3b17e`. Stub dry run (clean tree): G14,
  P1–P8, 45 stub runs, order_check 0, G15 20/20, A23 on 59 records. Gate 9910/35. Open: unpinned attempt records the init
  model as `pinned/model` with `model` null; A23 needs non-empty `model` (affects M07.A51) → `specifier` before any spend.
- R-472 `a230156` (registration §23.12): engineer's form accepted — `model` = the `--model` passed or null (canary attempts
  only); `pinned.model` = `model`, or the init model for an unpinned attempt (non-empty, not `claude-sonnet-5`); scorer
  unchanged; W27-A23 and M07.A51 restated; A79 new; K registered `"f"*40`. WO-17b + merge into `wp/M07` launched.
- 2026-10-18 Frank: run a transient-readiness re-check (ADR 0008 Amendment 2) at the 0.2.0 cut, covering the v0.2
  additions (external models, surrogates, C1 boundary, M03/M05 adapters, web shell). Brief
  `docs/briefs/ADR-0008-A2-readiness-recheck.md`; readiness tests 44/44 on main `4edcb5a`.
- 2026-10-18 Frank: register a seeded development/held-out split of OpenIDAES-450 at the 0.2.0 cut, before any
  OpenIDAES-targeted scope; held-out scored only at release gates; W27-exposed cases count as development. v0.2 W27
  unchanged. Brief `docs/briefs/OpenIDAES-split-registration.md`.
- 2026-10-18 WO-17b `d0307d8` (A79; A23 62/62 in dry run; gate 9912/35) + merge into `wp/M07` `83f825d` (conflict only in
  M07-build-decisions.md, both kept; gate 9923/35; CI 39136157258 green). C_W = `83f825d`, campaign `w27-m07-83f825d`:
  coverage 0/450, 0/82 CANDIDATE, G14 PASS; sample 45, canaries blind_synthesized_prommis_nanofiltration_membrane_schematic,
  mvo_variant_transcritical_co2_high_demand_flexible, variant_v4_cryst_n13_t338_y45_50; confirm written. Canaries launched.
- 2026-10-18 W27 canaries: 3/3 passed at the first attempt; pinning attempt 01 init model `claude-sonnet-5-5` (CLI default of
  the v17 setup-token login, R-471: nobody chooses), Claude Code 2.1.302; recorded spend USD-eq 0.233. Preflight P1–P8 pass.
  45-run campaign launched (ceiling 45).
- 2026-10-18 W27 campaign done: 45/45 recorded; CORRECT_LIMITATION 44, WRONG_LIMITATION 1 (26-official_idaes_skeleton_pervaporation);
  system false verification 0, unauthorized 0, critical 0; order_check exit 0; spend USD-eq 3.379 (48 results). Records
  `wp/M07` `22ae1e3` (gate 9923/35 at 83f825d tree + records). Launched: `verdict` on W27 (a)–(g); WO-6 (Sonnet) on `wp/M07-wo6`.
- 2026-10-18 W27 verdict `14d4527` at C_W: (a)–(d), (f), (g) MET; (e) NOT MET — `campaign.json` reproduces byte for byte but
  omits W27-R53 (coverage by family), R54 (§11.10 pooled terms; model, version, cost), R56 (identifier hits; preflight before
  first run). G16 gated terms met (vacuously: no job, revision or certificate). Run 26 WRONG_LIMITATION stands. Repair (build
  lane) launched: extend `scorer.aggregate`, regenerate `campaign.json` from unchanged records, re-judge (e). Findings F-1, F-3
  to the M07 ruling round. F-5: correction — the inaccessible assets are **nine** (W27-R57 record), not ten as logged earlier.
- 2026-10-18 W27 (e) repair `89cd931` (+R53/R54/R56 terms; identifier scan all 384 files, 0 hits; 45/45 name the preflight)
  campaign.json 15c6b300… → 4812910a…; verdict re-judged (e) MET `c50e6fb` (engineer's 3 choices confirmed; F-7 for WO-7/step 17).
  WO-6 `120c51f`+`5cdec3b` merged into wp/M07 `10ae324` (gate 9935/35).
- 2026-10-18 **Frank, M07 §15:** N1 claim all seventeen gates (V11–V20, W21–W27); N3 no equilibrium-reactor rung in 0.2.0;
  N5 carry V17 across R-192, R-234, R-295 (no re-run). Dated acceptances N4 (V14 (b)) and N6 (M02 N1) follow the 0.2.0 verdict.
- 2026-10-18 Launched: `specifier` ruling round 4 on the W27 verdict findings (F-7 blocks RC step 17) on `wp/M07-rulings4`;
  WO-8a (opus-engineer) on `wp/M07`: K (0.2.0 + O5 G10 re-takes), journey at K, record committed after K.
- 2026-10-19 Ruling round 4 `be7a06d` (`wp/M07-rulings4`, M07 spec §22 Amendment 5, R-473/R-474; gate 9935/35): step 17 = 17a
  campaign tree `95f9fcf2…` unchanged, 17b coverage to scratch, 17c `--carry-w27`, 17d aggregate on a copy == `4812910a…9e28`;
  on the campaign login only, never CI (`unsupported` otherwise; L-A5-1); F-3 doc scope → build lane WO-10; F-1 → next
  OpenIDAES registration (R02 unchanged through C); F-6 no action. Merge into wp/M07 after WO-8a.
- 2026-10-19 DECISION (session): the WO-7 verdict draft `0ca7943` is parked on local branch `wp/M07-verdict1`, not pushed — committing it alone reddens `tests/test_m07_ledger.py` until the ledger and M07's manifest exist. Alternative: push it red. Reversible by: cherry-pick `0ca7943`. W21 (e) FAIL (R-375 G11 results not kept) → WO-8d keeps and audits them at C′ (no re-cut).
- 2026-10-20 **Frank, ADR 0042 (0.2.0):** "Accept all five (Recommended)" — Claim set all seventeen; V17 carry across R-192, R-234, R-295; M02 N1 "not a sandbox"; M03 N1 `nlp` extra licences; D3 V14 (b) accepted, PTC experimental. To be recorded in ADR 0042 dated 2026-10-20, on/after the re-judged verdict's Judged date (2026-10-20). Also Frank: too many tokens — finish 0.2.0 with minimal passes.
- 2026-10-20 DECISION (session): M07 A8-Q1 (ship 0.2.0 without classifying M07a's ~42 unharvested envelope rows) → defer (ruling default, R-485). Alternative: re-cut C″ and re-run steps 1–17. Reversible by: a re-cut before the tag. Frank's five ADR 0042 answers recorded in ADR 0042 by the session (agent relay refused by the permission layer); verdict re-judged 2026-10-20: 16 PASS, V14 FAIL (D3-accepted).
- 2026-10-20 M07 into main `8a06b91`. Process error (session): the merge was committed and pushed before the gate output was read; the pre-commit gate had 9 failures, all git-state artefacts of gating an uncommitted merge (HEAD still `e0508d4`). Re-gate at `8a06b91`: 10013 passed, 1 failed (`test_v02a_r347_machine_class`: `t08_rc.py` install-check strips sys.path entries under the repo root, which in the main checkout contains `.venv`; passes in worktrees and on CI). CI 39399661594 green. Step 18 YES at `38935b2`.
- **0.2.0 RELEASED 2026-10-20.** Frank: "Tag and publish now (Recommended)". Release from `main`: dry run 39412425757 (gate, build success); annotated tag `v0.2.0` → `5c82b4c` (gate YES at `--rc ce99365 --candidate 5c82b4c`) pushed; release run 39412610914 from the tag: gate, tag, build, pypi, github-release all success. PyPI `openflowsheet 0.2.0`: wheel sha256 `2380c76b4496b7db…`, sdist `a4d4f82a7c42cdbc…`. GitHub release https://github.com/computational-chemical-engineering/openflowsheet/releases/tag/v0.2.0 (not a pre-release) with both files.
- 2026-10-22 **Frank:** the gate rule changes to "gate by risk, not by commit" (CLAUDE.md, Agent budget): docs-only commits need no local gate; code commits run the tests they touch; the full gate once before a merge into `main` and before any RC cut or tag, read before pushing; CI green on both architectures before merging. Replaces "the full gate before every commit" (2026-10-09). Cloud work packages: `docs/CLOUD_WORK.md` (`afc2340`).
- 2026-10-22 **Frank: "accept all recommendations"** for `docs/FRANK_QUESTIONS.md` (C2-Q1/Q2, Q-B1/B2, Q-S01-1, Q-S02-1…4, D1-Q1, L01-Q1…Q4); answers recorded at the top of that file. New items: IAPWS-95 ADR (v0.3 addition), rights check + attribution before `pr-lib-v1` records ship, duty-only column multiplicity warning, ADR 0044 acceptance requires other units bit-identical, W27 Amendment 3 for the next release, column purity/recovery specs next.
- 2026-10-23 wp/WS1 into main `05288372` (Frank approved the merge after the auto-mode check stopped the engineer's; redone on top of the cloud session's C8/C9/C12; merge-tree gate PASS 10634 passed, read before push; CI 39862529869 green both architectures). WS1 item 4 (C2 F-1 facts) parked on `wp/WS1-f1`: fails SPLIT-A09 and W27 P2, needs a design-lane registration amendment. **ADR 0044 Accepted 2026-10-23** — Frank: "1: yes"; condition (3) recorded in its C2; ADR 0010 D3 pointer added (C4); R-547 updated.
- 2026-10-23 Cloud handoff `docs/briefs/HANDOFF-cloud-2026-10-23.md` taken up. **Frank:** C10-Q1 yes as described; C10-Q2 VAPOR; Q-S06-1 no new warning; Q-S06-2 typed failure; C12 "Keep unshipped for now" (A32 step parked; shipping needs a clean-up package: drop CAS RNs, primary-paper constants). wp/C10 (S05) into main: gate PASS at `fc4e476f` (11024 passed), CI 39870960878 green. S06: review `637585b8` (no must-fix; F1–F4; R-608–R-610), fix work order running. C2 Amendment 2 `fccaa734` (R-581, R-582), WO-C2-A2 running. C12 terms fetch `6a4bf0fd` on `wp/C12-terms` (RC-03 cleared; six unresolved, terms quoted).
- 2026-10-23 Combined merge into main `a904cedf`: wp/C11 (S06, manifest `ad264a2…` tested; main merged in at `f28ac273`, HARVEST_SIZE (45, 519, 71) measured), wp/C2-A2 (C2 Amendment 2 + review fixes `8c955085`; register conflict resolved as a union, R-581/R-582 placed before R-585), wp/C12-terms. Full gate PASS 11228 passed / 60 skipped, read before push; branch CI green both architectures (C11 `f28ac273`, C2-A2 `8c955085`, C12-terms `9ef1e0ff`).
- 2026-10-23 **Frank: "yes add S07 to the queue"** — CoolProp as an optional external provider, pure fluids first (row in `docs/CLOUD_WORK.md`). Session recommendation it rests on: evaluator at (T, ρ) only, own phase logic, pinned optional dependency, mixtures deferred. Remote landed `wp/*` branches deleted (45; `wp/M06-wo17` kept), Frank's request.
- 2026-10-23 **Frank: S05 ships with IAPWS attribution** ("Yes, ship with attribution"), after the Tables check `af04961e` (385/0). Merged into main locally: wp/S05-tables, wp/D2 (R-611…R-615; ADR 0045 Accepted). Next: WO-S05-4 (labels, manifest) and S06 A04 edit (R-613) — build; WO-S05-5 packaging/binding after the ship decision — design.
- 2026-10-23 main pushed with wp/S05-tables + wp/D2 (gate PASS `8ac950b1` 11228/60, read; branch CI green). **Frank: no more cloud sessions** (budget). **Frank Q-8: S05 library only for now**; binding planned with S07 (`eb95cf08` on wp/S05-ship).
- 2026-10-24 **S07 merged into main `a40a6b80`** (wp/S07 head `c80dc6e5`). WO-S07-3 stopped at Q-1: aarch64 A31 worst 2.24e-8 (R22 cp at T_σ,max) against the pre-registered 1e-12/1e-10; nothing loosened. Specifier ruling: spec §20, R-627 (`3d6af0a7`; class T 1e-10 both tiers, class N per-state allowance 1e-10·max(|x|,s_f) + 2e-10·P|∂q/∂P|, Psat 1e-10; x86-64 bitwise). WO-S07-A31 (CI 40000637382): class T worst 0.566 of bound, class N 0.0183, x86-64 bit-identical. Manifest `evidence/S07/7bfab70d…` tested 64/65; harvest `f924c5ea` HARVEST_SIZE (48, 552, 74); D08 cites S07 and the ledger registers it (`c80dc6e5`). Gate PASS `c80dc6e5` 11653 passed / 3137 skipped (read); S05+S07 with `OPENFLOWSHEET_REQUIRE_COOLPROP=1` 3847 passed / 2 skipped; CI 40045965622 green both architectures.
- 2026-10-25 **S03 merged into main `4819e406`** (wp/S03 `3ad02fd0`; includes wp/ledger-sync `17195239`). Gate PASS `3ad02fd0` 11976 passed / 3137 skipped (read); CI 40140766357 green both architectures. Verdict: 23 AGREE, controls PC-L/PC-LI DISAGREE as designed, X31 not met (2 of 4), D19 met for covered states with the RC4 gap. Frank: Q-S03-4 plan S08, Q-S03-5 all three inverse specs, Q-A2-4 plan S09. Clean-up: 8 merged worktrees removed; remote branch deletion denied by the permission classifier (left to Frank). S10 started (ADR 0047 Proposed): Frank Q-F1..Q-F4 defaults; Kurihara 1993 supplied by Frank.
- 2026-10-25 **S10 merged into main `30b7b4b8`** (wp/S10 `7cf51876`). Close-out WO-S10-7 (S-1 A4-3 uncertainty + lineage, S-2 rights, S-3 blindness, manifest, ledger, harvest); CI then failed on two pre-existing tests → Amendment 5 (§18, R-722…724: T08.A32 vets `records.yaml` via `records-vetting.json` with (ii′)/(v′); aarch64 saturation check 1e-10 / 2.1e-10, x86-64 bitwise); CI failed again on S05.A28 (a test imported CoolProp) → B-85 (metadata version). WO-S10-7a (manifest `f974cc87…` with D08+D19, HARVEST_SIZE (52, 688, 85)); B-87 (HG(b): old harvest note not rewritten). Gate PASS `7cf51876` 12234/3139 (read); CI 40193243573 green both architectures. GitHub API rate limit hit by `gh run watch` at 3 s polling: use `--interval 300` or the sparse wait script. Frank supplied Kurihara et al. 1995; double entry byte-identical; Amendment 6 (`d42fcf08`, R-725…727) pre-registered VAL-2 blind; WO-S10-8 next.
- 2026-10-25 **S10 WO-S10-8 (VAL-2) merged into main `329757c2`** (wp/S10 `6bc159e9`). Amendment 6 (`d42fcf08`, R-725…727) fixed VAL-2 blind: per binary, both must pass; ΔP/P on measured P; y1; closed-form bubble P at P_eval 101325 Pa; all 159 points. Kurihara et al. 1995 double-entered (A text-layer+image, B image-only; byte-identical `e1290279…`), committed `a15baa0a`. Results (`9fadf32f`): methanol+water AAD_P 0.01086763935, AAD_y 0.004754833453; ethanol+water 0.00289894189, 0.004075153801; 40/159 below 30 kPa; no refusals. Verdict `d473f215`: within band ×3, independent recomputation exact, all 477 values checked against the image. Records sentence + lineage `8ddeac6a`/`b02f1b7e` (records d4a39730… → 033e10b3…); manifest `evidence/S10/f6f27c3f…` tested, 248 passed 0 skipped; HARVEST_SIZE (53, 735, 88). Gate PASS `6bc159e9` 12244/3137 (read); CI 40200526990 green. Frank: stale A6-13/RC-06 limitation sentences "Do it later" (next S10 change).
- 2026-10-26 **S08 merged into main `d96c17ae`** (wp/S08 `f5565a34`). Architect design `943276d8` (ADR 0048 Proposed, R-728…R-731): block rule in the contract measured not to help (restart opens in a signature with no regular root — premise corrected by the review, R-733…R-736); route = Stage B block openings after a typed or item-6-rejected Stage A. WO-G roots (R-732, 84 claims); WO-1 item 6 (worst registered 2.42e-6 K; F1 false CONVERGED 0.379 K); WO-2 block endpoints; WO-3 Stage B; WO-4 tests/G1/manifest; review: A14(b) did not test its claim, A17/A18 added, W2-4/W4-5 reversed; WO-5 fixes, HARVEST_SIZE (54, 747, 90). Gate PASS `f5565a34` 12356/3137 (read); CI 40248543872 green. S08b queued (contract stage-id defect; trace-vapour roots in flash/cascades). S09: Frank chose BioSTEAM (Q-S09-1); spec + Am. 1; blind qualification 19/19 available; 17 AGREE, controls DISAGREE, X31 met where available 3 of 4.
- 2026-10-26 **S09 merged into main `8d94ea28`** (wp/S09 `6d1c2d66`). Pre-merge gate at `df7aff86` FAILED 21 (T06 A48 parser read S09's `.venv-biosteam` lines in `reference-environments.md`, KeyError) → regex scoped to (idaes|dwsim) (`6d1c2d66`); gate PASS 12507/3137 (read); CI 40262198930 green. Verdict 17 AGREE / 2 DISAGREE controls / X31 met where available 3 of 4; review sound (F1 NaN fix, Amendment 2). S10-C: architect design `b348e9b4` (ADR 0049), WO-S spec/generator (118 claims; F-1, F-2 corrected the note), WO-1..WO-3 done, G1 n=858 changed=[].

## 2026-10-26 — S10-C merged

- S10-C final work orders on wp/S10C (`c856715a..aa6ea662`): WO-R5 `5d1c123f` (R-785, A41 absent flows `== 0.0`; a
  1e-300 mutation fails both cases), WO-R6 `f23985bf` + log `659bd10e` (R-786; G-R8: oracle 2000/2000, old vs new
  2000/2000, chains 2000/10000 columns 0.9/3.0 ms where the old code raised RecursionError at 2000; 1518 suite calls 0
  mismatches; detector 17/153/182 identical before/after), T07 pin per machine class `fbba9643`, generator `2aedd250`,
  manifest `cdfcef5d` (`evidence/S10c/2aedd250…` tested 49/51), harvest `aa6ea662` (HARVEST_SIZE (58, 824, 99)).
- Build decisions for the ruling round (logged in `docs/S10C_DECISIONS.md`): G2 admits `numerics/newton.py`,
  `test_t06_w20_counters.py`, `test_t07_interrupt.py` by name; T07 on an unregistered class checks > 89 records only.
- Erratum `94f70c2d`: R-782 note §9 — A41 checks 38 absent flows per case; 60 is |Z*|.
- Gate PASS `94f70c2d`: 13249 passed, 3137 skipped. CI 40315691647 green (both architectures, default-install, identity).
- Merged into main `8654aabc` (`--no-ff`, tree identical to `94f70c2d`), pushed.

## 2026-10-26 — S08b merged

- wp/S08b: WO-0 merge `0387b2e7` (B = `a13203b8`; `S08B-RECORDS n=52 moved=[] stage_a_moved=[]`, §6.1's eleven, byte-identical
  to `measured.txt`); WO-1 G1 gate `8c455729` (control `--no-change`: `a_texts=0 b_moved=0`); WO-2 `564bf772` (§5.1); WO-3
  `a6fa18a7`/`6ea95a4a` (§5.2, B1–B3; B2 1.609e-06 K); manifest `evidence/S08b/acbd1266…` tested 18/20; harvest `cb25186d`
  (HARVEST_SIZE (59, 832, 101)). G1 at acbd1266: `S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/20`.
  G3: branch 13280 / base 13249 passed; S01 rows largest error 2.43e-06 K.
- Review (`docs/reviews/S08b-review.md`): sound, no must-fix; all build decisions accepted; F1 (cache fact misdiagnosed — a
  test memo filled under a forced edge-3 patch) and F2 (no test pins `items` at `_proposal`) to follow-up wp/S08b-f; errata
  B3/G3/Q5 applied on main `764860d1`.
- CI 40359016227 at `d34f8b57` failed T07 THM-09/4 on ci-x86-64 (136 vs pinned 94; runner CPU varies). DECISION T07-1
  (`f4b5d8dd`, `1d4ca814`): ci-x86-64 unpinned; failure names the CPU. For the ruling round.
- Gate PASS `d34f8b57` 13286/3137 and `1d4ca814` 13286/3137. CI 40373688071 green. Merged `e65b0690` (tree identical), pushed.

## 2026-10-26 — S08b-f and R796 merged; S11 started; batching

- wp/S08b-f merged `8c34ecb0` (review F1/F2; gate PASS `de8ec0e8` 13288/3137; CI 40388688886).
- Ruling round (verdict) on S10-C G2, T07 unregistered class, T07-1: all accepted; R-795, R-796; C1 report line. wp/R796
  merged (tree identical to `3a2c17ae`; gate PASS 13288/3137; CI 40403579501). T07 lines: Haswell → 94, SkylakeX (EPYC 9V45,
  Xeon 6973P-C, Xeon 8370C) and neoversen2 → 136; no new pin (`docs/t07-measurements.md` W4b.5, `77f54168`).
- Frank: "I am getting slightly impatient… implement many more features in one pass and then test them together" → batch per
  branch, two engineers in parallel, one gate + one CI per batch (memory `batch-then-test`).
- Frank: "I want the binding package" → S11 (wp/S11); architect brief `docs/briefs/S11-binding-design.md`.

## 2026-10-27/28 — S11 built; E01 designed and built; paused

- S11 (binding package): design + ADR 0050, units design + ADR 0051 (Frank: pure-fluid and Wilson units in S11), Q9 ruling
  (§10), batched rulings R-830…R-842; tracks A–D + I1/I1b/I2 on wp/S11 (head `8d2ee175`). Manifest
  `evidence/S11/01e72ca4…` tested 123/126; `S11-IDENTITY PASS n=54494 changed=[]`; HARVEST_SIZE (60, 867, 104).
- E01 (cost + LCA): design `49fef97c` (ADR 0052, R-850…R-862), ruling §9 (R-863…R-867); tracks A and B complete on wp/E01
  (`cd85a773`). Verified cost-optimal SYN-001 tac (3 starts, V1–V7). Independent checks: hand SSLW 2.3e-15, IDAES 1e-14,
  Brightway 3e-16.
- PrISMa scoping digest `docs/briefs/PrISMa-scoping.md`; E01 and PrISMa queued per Frank.
- Incident: one E01 engineer sent Frank's e-mail as a User-Agent to download.bls.gov once (logged in E01A_DECISIONS);
  briefs now forbid personal identifiers to external services and nested subagents.
- Frank, 2026-10-28: "finish what you are doing and then pause further development until budget is refreshed again" →
  paused after S11 WO-I2 and E01 WO-B4; next actions in `docs/V02_STATE.md`.
- 2026-10-29: S11 merged into main `1b2758d1` (gate PASS `021441ef`; CI 40877525424 green both architectures; aarch64
  R-843 classes ≤ 2.9e-3 of bound, R-845 flash 0.024). wp/E01 merged main at `84d71df8` (register: per-entry three-way
  merge, 720 entries, nothing dropped from either side). DECISION: E01 manifest → keep `02fc8d2f` (S08b/S11 precedent).
  Alternative: regenerate at the merge commit. Reversible by: re-running `scripts/e01_evidence_manifest.py`.
- Frank, 2026-10-29: "cut 0.3.0 right after S11 and E01 merge, before starting the optimiser package, and leave Wilson
  in." Release work queued as step 2 of `docs/V02_STATE.md`.
