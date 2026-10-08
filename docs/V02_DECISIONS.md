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
