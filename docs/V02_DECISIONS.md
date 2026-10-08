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
