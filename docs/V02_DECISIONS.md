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
