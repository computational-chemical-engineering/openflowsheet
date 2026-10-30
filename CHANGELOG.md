# Changelog

## v0.3.0 — unreleased

*Draft (V03 WO-4); nothing below is released. The release candidate C, its gate table and the
verdicts are added to this section at C (V03 spec §4, ADR 0053). 0.3.0 claims V11–V20, W21–W26
and X31; W27 is not claimed.*

### S01 — the countercurrent equilibrium-stage subsystem

- Equilibrium stages with explicit degrees of freedom and energy and phase coupling, an
  initializer and Newton continuation, on SYN-001. Manifest
  `evidence/S01/465240a4…/manifest.json`.

### S02 — the MESH column

- Stage indexing, feed, condenser, reboiler, pressure and specification conventions; four matched
  cases and the invalid-specification and invalid-phase refusals. Manifest
  `evidence/S02/1810dde8…/manifest.json`.

### S03 — independent column references

- Column answers compared with an independently written implementation across the available suite,
  with perturbation studies and the supported nonideal scope. Manifest
  `evidence/S03/930aad1b…/manifest.json`.

### S04 — the Peng–Robinson component library `pr-lib-v1` (library-only)

- A vapour-phase Peng–Robinson library provider; a revision cannot select it, and its records do
  not ship. Manifest `evidence/S04/5c29fbf6…/manifest.json`.

### S05 — IAPWS-95 water `iapws95-v1`

- The IAPWS-95 formulation as a provider with its own reference convention `IAPWS95-ref-v1`; the
  coefficients ship with IAPWS's attribution in NOTICE. Manifest
  `evidence/S05/01cdeed4…/manifest.json`.

### S06 — column specifications by purity, recovery and stage temperature

- Purity, recovery and stage-temperature specifications for the column, with their rows, degrees of
  freedom and typed refusals. Manifest `evidence/S06/ad264a23…/manifest.json`.

### S07 — CoolProp pure fluids `coolprop-heos-v1` (optional extra `coolprop`)

- CoolProp 8.0.0's Helmholtz equations of state for 123 fluids in two tiers, reference convention
  `COOLPROP-DEF-ref-v1`, compared across architectures within registered bounds (ADR 0046).
  Manifest `evidence/S07/7bfab70d…/manifest.json`.

### S08 and S08b — one-phase column sections and the phase contract

- Block openings for column sections in one phase (ADR 0048), and signature items by declaration
  with saturation consistency for S01 cascades. Manifests `evidence/S08/6d7d1a6d…/manifest.json`
  and `evidence/S08b/acbd1266…/manifest.json`.

### S09 — BioSTEAM as a third column reference

- A blind third reference for the column cases: 19 of 19 qualified, X31 met where available for 3
  of 4 cases. Manifest `evidence/S09/4d4df087…/manifest.json`.

### S10 and S10-C — the Wilson liquid-mixture method on real records

- `wilson-ig-v1`: Wilson activity coefficients with an ideal-gas vapour for methanol, ethanol and
  water, Wilson parameters fitted to published equilibrium data (Kurihara et al. 1993), with the VAL-1–3
  validation bands (ADR 0047); S10-C adds the
  γ–φ PH flash and the column on Wilson (ADR 0049). Wilson's records and the Kurihara 1993 points
  ship as package data (V03 spec §9.1). Manifests `evidence/S10/f6f27c3f…/manifest.json` and
  `evidence/S10c/2aedd250…/manifest.json`.

### S11 — the binding package

- Water (IAPWS-95), CoolProp's pure fluids and Wilson selectable in flowsheets; the seven
  `thermal.*` units; the column as a flowsheet unit (ADRs 0050, 0051). `semantic_role` gains
  `compressor`, `turbine` and `other` (ADR 0054). Manifest `evidence/S11/01e72ca4…/manifest.json`.

### S12 (E01) — cost estimation and LCA

- Cost and life-cycle impact as differentiable post-solve functionals of a
  verified state, with an accuracy class (ADR 0052); the LCA table builder needs the optional
  extra `lca`. Manifest `evidence/S12/02fc8d2f…/manifest.json`.

### What it is not

- numerical verification, not empirical validation
- no global optimality
- Linux only
- not a sandbox
- the stand-in reactor is synthetic
- no reactor result has been compared with experimental data by this project: the group's published
  comparison is the group's evidence, and every real-reactor number is the group's model at the pin,
  a regression, whose discretization bias is 1.0–1.4 % in NH₃ (M02 design note §13)
- the optimization routes need the optional nlp extra
- the CoolProp provider needs the optional coolprop extra
- cost and LCA results are assessment estimates with an accuracy class
- cost and LCA are Python-only
- no ecoinvent data
- Wilson is vapour-liquid only; no liquid-liquid split
- no automatic liquid/vapour regime switching for pure fluids
- X31: one independent reference for the refluxed absorber
- no rate-based column models
- no W27 claim in 0.3.0
- no CFD or Peclet refinement
- no external benchmark score

## v0.2.0a1 — release candidate `C_α` = `cc73219a77f6a54579c8acb151ed6fae228c8a4c` (`0.2.0a1`); a pre-release; tag and publication by Frank

*ADR 0021 D4, reused by ADR 0028. The gate table below is what
`scripts/v0_2_gate.py --rc C_α --markdown` prints at the tag candidate, after the design lane's
verdicts on `C_α` (`docs/reviews/V02-alpha-verdicts.md`: judged 2026-10-16, V13, V17 and W21
re-judged 2026-10-17 on Frank's answers in ADR 0028). Nothing in this section is released until
the tag; the tag and every publication are Frank's (ADR 0021 D5).*

**What it does.** Everything v0.1.0 does (the application contract, the thirteen unit models, the
planner, the verifier, the certificate or the typed failure, the replay bundle) and, added since
v0.1.1: an adapter that runs the pinned PyMRM reactor as a unit model, with its coupled route and
its experiment artifacts (M02); the Peng–Robinson property route of the ammonia loop (M01); and a
diagnostic web shell served by `serve-http --ui`, which edits nothing (Solve and Cancel are its
only effects; M06). The supported envelope is `docs/support-matrix.md`: **unlisted is
unsupported**.

**Gates (V11–V20, W21, W22), as `scripts/v0_2_gate.py` prints them.** A FAIL is printed FAIL.

| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |
| --- | --- | --- | --- |
| V11 | PASS | Semantic diff, drafts, task validation, units/references, real migration when applicable | limitations: L38 |
| V12 | PASS | Required unit library with per-model definition of done | limitations: L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 |
| V13 | PASS | DM/SCC/BTF, tear and EO, scaling and initialization | limitations: L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 |
| V14 | FAIL | Homotopy, qualified PTC/SER and three bounded recovery edges | failing: V14 (b); V14 (b) FAIL, accepted by Frank 2026-10-17 (ADR 0028 D3); limitations: L01, L08, L20, L21, L43 |
| V15 | PASS | Frozen phases, EO cross-unit spec, multiple-root evidence | limitations: L02, L14, L19, L20, L33 |
| V16 | PASS | 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20x20 ensemble | limitations: L16, L17, L18, L32 |
| V17 | PASS | Local/HTTP/MCP, ten agent tasks, >=80% success, zero unauthorized actions/false verification | limitations: L11, L12, L13 |
| V18 | PASS | Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested | limitations: L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 |
| V19 | PASS | Real-chemistry dossier with usable data/kinetics/property/reference route | — |
| V20 | PASS | >=95% nominal robustness, correct invalid-structure handling, no adversarial false verification | limitations: L04, L07, L09, L31, L32, L38 |
| W21 | PASS | PyMRM boundary/accuracy/execution and provenance | limitations: L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 |
| W22 | PASS | One validated needed nonideal property route | limitations: L42, L47 |
| W23 | not claimed | Surrogate conservation/domain/derivative/default UQ and promotion | — |
| W24 | not claimed | Fixed-topology optimization, eligible trust-region example and parent-model checks | — |
| W25 | not claimed | End-to-end real reactor refinement with honest evidence limits | — |
| W26 | not claimed | Diagnostic web shell through shared contract | — |
| W27 | not claimed | External agent benchmark adaptation attempted; inaccessible assets disclosed | — |

**What it is not.**

- **Not 0.2.0.** A pre-release: W23–W27 are not claimed, and the web shell is included and not
  claimed.
- **Not empirically validated.** SYN-001 is synthetic, and every result is numerical verification
  against the same equations. Also, no reactor result has been compared with experimental data by
  this project: the group's published comparison is the group's evidence, and every real-reactor
  number is the group's model at the pin, a regression, whose discretization bias is 1.0–1.4 % in
  NH₃ (M02 design note §13).
- **Not a guarantee.** A human sign-off records that someone with the relevant expertise examined
  the evidence and raised no objection, not that the content is correct (R-017).
- **Not general beyond the support matrix.** What `docs/support-matrix.md` does not list is
  unsupported, and each unsupported capability ends typed.
- **Not a certificate of solution accuracy.** `VERIFIED` certifies residual accuracy at the
  registered tolerances; the solution-error bound is recorded and disclosed, never promised
  (ADR 0007 F3).
- **PTC is experimental.** No PTC family is qualified: V14 (b) is judged FAIL at `C_α`.
- **The agent evidence is narrow.** One pinned model and configuration, MCP only. V17's agent
  evidence is carried from `v17-c2`'s surface, not re-measured on v0.2's: Frank accepted the carry
  (ADR 0028, 2026-10-17), and the release candidate's job checks the recorded decomposition chain
  from that surface to this one (M07a.A37).
- **The reactor is opt-in and measured on one machine.** Real-reactor runs are opt-in (they need
  the separately built, pinned reactor environment) and of reproducibility class R3 (ADR 0034 D6).
  The reactor has been run on Linux x86-64 on one machine (`ref-x86-64`): it is not measured on
  aarch64, and no CI job runs the reactor. What CI runs in its place is a stand-in, and the reactor
  stand-in is synthetic; it certifies nothing about the reactor. There is no warm start of the
  reactor (L44).
- **The reactor execution profile is not a sandbox.** The group's pinned code runs with the user's
  privileges, unconfined (L45). The profile is registered on Linux; macOS is best effort, and
  Windows is refused before spawn (ADR 0033 D2).
- **The property route is narrow.** Validation covers pure-component behaviour within R-160's bands
  against the reference equations of state; `k_ij = 0`; there is no mixture VLE validation. Of
  `pr-c1-v1`'s liquid side: the LIQUID regime and pure-NH₃ flashes are deferred and refused typed
  (U15), and against the reference equations of state its saturated-liquid volume is 11–30 % high
  and its enthalpy of vaporization 2–5 % high (L47); no v0.2 loop decision uses either.
- **Rights.** The group's 4TU dataset may be used and referenced (Frank, 2026-10-02; the real
  chemistry dossier §8, row 8); no result of this release is compared with it.

**Known limitations, by support-matrix id** (the text of each is in `docs/support-matrix.md`):
`L01`, `L02`, `L03`, `L04`, `L05`, `L06`, `L07`, `L08`, `L09`, `L10`, `L11`, `L12`, `L13`, `L14`, `L15`, `L16`, `L17`, `L-CSTR-1`, `L-CSTR-2`, `L-CSTR-3`, `L-WS-1`, `L-WS-2`, `L18`, `L19`, `L20`, `L21`, `L22`, `L36`, `L37`, `L38`, `L39`, `L23`, `L24`, `L25`, `L26`, `L27`, `L28`, `L29`, `L30`, `L31`, `L32`, `L33`, `L34`, `L35`, `L40`, `L41`, `L42`, `L43`, `L-WEB-1`, `L-WEB-2`, `L-WEB-3`, `L-WEB-4`, `L44`, `L45`, `L46`, `L47`, `L48`.

**Reproducibility.** In the words of ADR 0007 F1: "the project reports bitwise agreement and
never promises it, on any platform including a single machine; R0 bit-identity of structure plus
D2 agreement for floats is the promise."

**Review status of every package** (each manifest's `status` at `C_α`, the manifest at the latest
committer time where there are several; human `review` fields as recorded; M07a, whose manifest is
the record of this gate and is written after `C_α`, has no row, R-320):

| Package | Status | Human review (numerical / process model) |
| --- | --- | --- |
| K01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K04 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K05 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K06 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| M01 | `tested` | pending / pending |
| M02 | `tested` | pending / pending |
| M06 | `tested` | pending / pending |
| P00 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| T01 | `tested` | pending / pending |
| T02 | `tested` | pending / pending |
| T03 | `tested` | pending / pending |
| T04 | `tested` | pending / pending |
| T05 | `tested` | pending / pending |
| T05b | `tested` | pending / pending |
| T06 | `tested` | pending / pending |
| T07 | `tested` | pending / pending |
| T08 | `tested` | pending / pending |

## v0.2.0 — unreleased

*In development on `main`; nothing below is released. The gate table is added to this section
at the release candidate (M07).*

### M01 — the Peng–Robinson route of the ammonia loop (W22)

- **C1 property route.** Peng–Robinson with the light gases vapour-only, its root and phase
  rules, an equilibrium-vapour flash, and the formation datum `PR-C1-ref-v1` (ADR 0026); the
  parameters are cited and registered. The reactor boundary of the loop is ADR 0027.

### M02 — the PyMRM reactor adapter (W21)

- **External reactor as a unit model.** The pinned PyMRM reactor runs in an out-of-process child,
  one per attempt, under a three-layer kill chain, with process-level experiment identity and an
  exact cache of deterministic outcomes (ADR 0033); it runs inside a flowsheet solve (ADR 0034),
  with model replacement and promotion as a checked commit (ADR 0035). Experiment records and
  the coupled route are replay artifacts. A synthetic stand-in reactor ships for the default gate
  and is listed as synthetic.

### M03 — sensitivities, studies and the NLP bridge (W24, part)

- **Parametric sensitivities and studies.** Parameters are pinned inputs; their derivative comes
  from a bit-identical parametric twin and is issued only at a qualified regular root; sweeps and
  the estimation example are studies over those parameters (ADR 0031).
- **General NLP bridge.** A PyNumero gray box over the parametric twin solved by an audited
  cyipopt, judged only on the re-solved, certified simulation (ADR 0032). It needs the optional
  `nlp` extra and its licences (accepted by Frank 2026-10-16).

### M04 — surrogate evidence (W23)

- **Surrogates as evidence.** A registered uniform reference box, a plan registered before the
  parent runs, joint split-conformal intervals, and promotion decided by an integer coverage test
  (ADR 0036). The surrogate is a native unit pinned by its manifest's hash, promoted and rolled
  back through the checked commit (ADR 0037); the `surrogate_study` job kind joins the contract.

### M05 — the trust-region study of the C1 loop (W24)

- **Trust-region adapter.** Pyomo's trust-region filter over a projection of the canonical
  problem, with the audited Ipopt executable for its subproblems (ADR 0038); a conditional
  scipy-only fallback is ADR 0040. The C1 study optimizes the reactor inlet temperature for
  liquid NH₃ product; candidates are judged by parent checks and every true-model call is
  accounted (ADR 0039).

### M06 — the diagnostic web shell (W26)

- **`serve-http --ui`.** A browser view of one project at `/ui/`, on the same origin as the
  unchanged HTTP API: revisions with a flowsheet drawing, validation and degrees of freedom, the
  equation view (structure), runs with attempts, trace and plan (live while a job runs),
  certificates, failure bundles, streams and units, bundle files with download, revision and run
  comparison, and the agent history. Solve and Cancel are its only actions; it edits nothing.
  `docs/web-shell.md` says what each screen shows and does not claim; ADR 0030 (proposed) and
  `docs/design/M06-web-shell.md` are the design.
- **Contract only.** Hand-written ES modules and CSS shipped as package data: no build step, no
  framework, nothing third-party. One `fetch` call site, URLs from a route table generated from
  `OPERATIONS`, exactly 17 operations called; records read whole through the raw export and
  checked against their registered SHA-256. The bearer token stays in session storage and the
  `Authorization` header; every `/ui` response carries a strict Content-Security-Policy.
- **Contract amendments (ADR 0019 Amendment 3, proposed).** `inspect_structure` gains a row and
  column index and, for an unroutable revision, the validation's own analysis; `diff_revisions`
  gains element-level detail; a new operation, `list_audit`, reads the project's audit history
  (own rows with `read`, other principals' with `policy`).
- **Tests.** Static scans of the shell's sources; Node's built-in runner on the view models and
  screens against fixtures captured from real responses (`check.sh` needs Node ≥ 22 unless
  `OPENFLOWSHEET_SKIP_WEB_TESTS=1`); every used operation over HTTP; a headless-Chromium test of
  every screen with a request recorder, Solve, a live and a cancelled job, and the downloads
  (skipped without a browser, required on CI's x86-64 leg).

### M07 — the reference journey and the release gate (W25)

- **Reference journey.** One decision (the reactor inlet temperature) taken through four rungs of
  fidelity, with decisions compared by the parent's objective against its noise floor; W25 is
  judged on reporting what happened, not on whether the decision changed (ADR 0041).
- **The 0.2.0 gate.** `scripts/v0_2_gate.py` gains `v0.2-gate-v1`, which claims all seventeen
  gates V11–V20 and W21–W27, each judged at its own candidate, with per-release acceptance of
  failures (ADR 0042, proposed).

### What it is not

- not a sandbox
- Linux only
- reactor results reproduce from records (R3)
- T_in 653.15-693.15 K, P 9-11 MPa, H2/N2 2.5-3.5, inerts 0.035-0.2, per-tube flow 0.5-2 x nominal
- no empirical validation of the C1 loop
- no reactor result has been compared with experimental data by this project: the group's
  published comparison is the group's evidence, and every real-reactor number is the group's model
  at the pin, a regression, whose discretization bias is 1.0–1.4 % in NH₃ (M02 design note §13)
- no global optimality
- the optimization routes need the optional nlp extra
- the stand-in reactor is synthetic
- no external benchmark score
- no CFD or Peclet refinement
- no equilibrium-stage subsystem

## v0.1.1 — the single public repository; release by workflow; no change to the simulator

*The code and data of the simulator are v0.1.0's: under the ADR 0021 D2.4 paths (`src/`,
`schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`,
`LICENSE`, `NOTICE`) this release differs from the release candidate `C` = `67c66d9` only in the
version, as v0.1.0 did, and `scripts/v0_1_gate.py --rc 67c66d9…` proposes it under the v0.1 gates.
0.1.1 is the first release published through the release workflow.*

- **One repository.** `computational-chemical-engineering/openflowsheet` is now the working
  repository — branches, pull requests, CI, tags and releases (R-150). Its history starts at
  v0.1.0; the development history before it is archived, read-only, in `openflowsheet-dev`, and the
  commit ids cited under `evidence/` refer to that archive (`docs/HISTORY.md`).
- **Release workflow.** `.github/workflows/release.yml`, dispatched by hand and a dry run by
  default: the release gate, the tag, the sdist and the wheel (built twice and inspected), the
  PyPI upload by trusted publishing behind an approval, and the GitHub release with this section as
  its notes (`docs/RELEASING.md`). The two-repository snapshot release that preceded it is removed.
- **The gate without `C`.** Where `C` is not in the repository, `scripts/v0_1_gate.py` compares
  the candidate with `C`'s recorded file hashes, `release/rc-trees/<C>.json`, by the same rule
  (R-151); it prints the version it judges (`vX.Y.Z tag may be proposed`) and covers the 0.1 line.
- **Pre-push guard.** `scripts/install-hooks.sh` installs a hook that refuses to push to the public
  repository any commit that does not descend from v0.1.0.
- **T08 manifest generator.** §A4.6's ancestry rule is judged on the development history only; a
  release commit without that history (the public v0.1.0) is listed as unrelated, not counted
  against it.
- **Tests without the archived history.** Tests that read pre-0.1.0 commits skip explicitly where
  those commits are absent, with the reason "pre-0.1.0 development history is archived in
  openflowsheet-dev (R-150)", and run unchanged where they are present.

## v0.1.0 — release candidate `C` = `67c66d9` (`0.1.0rc1`), version-only change to `0.1.0`; tag and publication by Frank

*ADR 0021 D4. The gate table below is what `scripts/v0_1_gate.py --markdown` prints for the release
candidate `C` = `67c66d98587f23bd7dfe8da28a8facccc92da21e` after the design lane's verdicts
(`docs/reviews/T08-verdicts.md`); T08's evidence is `evidence/T08/67c66d9…/manifest.json` (`tested`). The tag
commit differs from `C` only in the version (ADR 0021 D2.4); the tag and every publication are Frank's (ADR 0021 D5).*

**What it does.** A process simulator for ideal three-component processes that an agent or a
person drives through one application contract — Python, CLI, HTTP and MCP over stdio, twenty
operations — in which every solve ends in a certificate or a typed failure and writes a replay
bundle. A flowsheet is a content-addressed revision of thirteen unit models (mixer, splitter, TP
and PH flashes, heater, exchanger, pump, valve, component separator, conversion reactor, kinetic
CSTR, feed and sink). Validation reports structure (DM/BTF), units and components before a solve.
The planner tears recycles with safeguarded Anderson acceleration or merges them into
equation-oriented regions, promotes cross-unit specifications into EO, and runs bounded phase
attempts and the bounded recovery edges of `docs/recovery-edges.yaml`. A verifier that shares no
factorization with the solver issues a `SolutionCertificate` (residuals, balances, regularity,
alias certificates) or a failure bundle. Compatible warm starts and pseudo-transient continuation
are offered by explicit policy only (`T08-warm-v1`, `T08-ptc-v1`). The supported envelope is
`docs/support-matrix.md`: **unlisted is unsupported**.

**Name.** The project is **OpenFlowsheet**: distribution, import package and console script are
`openflowsheet` (they were the provisional `process-runtime` and `process_runtime`; there is no
alias), and the environment variables are `OPENFLOWSHEET_*` (R-149). Install the server extra with
`pip install 'openflowsheet[server]'`; solve with
`openflowsheet solve SYN-001-nominal --out ./bundle`.
The schema `$id`s keep their v0.1 URLs. The rename moved the SYN-001 provider's self-hash and so the
registered identity values that cover it, by substitution only (R-149).

**Gates (V11–V20), as `scripts/v0_1_gate.py` prints them.** A FAIL is printed FAIL; a released
FAIL is only a clause ADR 0021 D3 lists with Frank's acceptance.

| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |
| --- | --- | --- | --- |
| V11 | PASS | Semantic diff, drafts, task validation, units/references, real migration when applicable | limitations: L38 |
| V12 | PASS | Required unit library with per-model definition of done | limitations: L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 |
| V13 | PASS | DM/SCC/BTF, tear and EO, scaling and initialization | limitations: L10, L22, L23, L24, L36, L38, L-WS-1, L-WS-2 |
| V14 | FAIL | Homotopy, qualified PTC/SER and three bounded recovery edges | failing: V14 (b); V14 (b) FAIL, accepted by Frank 2026-09-29 (ADR 0021 D3); limitations: L01, L08, L20, L21 |
| V15 | PASS | Frozen phases, EO cross-unit spec, multiple-root evidence | limitations: L02, L14, L19, L20, L33 |
| V16 | PASS | 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20x20 ensemble | limitations: L16, L17, L18, L32 |
| V17 | PASS | Local/HTTP/MCP, ten agent tasks, >=80% success, zero unauthorized actions/false verification | limitations: L11, L12, L13 |
| V18 | PASS | Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested | limitations: L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 |
| V19 | PASS | Real-chemistry dossier with usable data/kinetics/property/reference route | — |
| V20 | PASS | >=95% nominal robustness, correct invalid-structure handling, no adversarial false verification | limitations: L04, L07, L09, L31, L32, L38 |

**What it is not.**

- **Not empirically validated.** SYN-001 is synthetic — three pseudo-components with invented
  constants and ideal VLE — and every result is numerical verification against the same
  equations (L18).
- **Not a guarantee.** A human sign-off records that someone with the relevant expertise
  examined the evidence and raised no objection, not that the content is correct (R-017).
- **Not general beyond the support matrix.** What `docs/support-matrix.md` does not list is
  unsupported, and each unsupported capability ends typed (U01–U14).
- **Not a certificate of solution accuracy.** `VERIFIED` certifies residual accuracy at the
  registered tolerances; the solution-error bound is recorded and disclosed, never promised
  (ADR 0007 F3; L05).
- **PTC is experimental.** No PTC family is qualified: V14 (b) is FAIL (on PTC-R1, PTC ends at
  the saddle from 149 of 441 starts) and carried by Frank's acceptance (ADR 0021 D3, L01).
- **The agent evidence is narrow.** One pinned model and configuration, MCP only, not out of
  sample (L12).

**Known limitations, by support-matrix id** (the text of each is in `docs/support-matrix.md`):
`L01`, `L02`, `L03`, `L04`, `L05`, `L06`, `L07`, `L08`, `L09`, `L10`, `L11`, `L12`, `L13`, `L14`, `L15`, `L16`, `L17`, `L-CSTR-1`, `L-CSTR-2`, `L-CSTR-3`, `L-WS-1`, `L-WS-2`, `L18`, `L19`, `L20`, `L21`, `L22`, `L36`, `L37`, `L38`, `L39`, `L23`, `L24`, `L25`, `L26`, `L27`, `L28`, `L29`, `L30`, `L31`, `L32`, `L33`, `L34`, `L35`, `L40`, `L41`.

**Reproducibility.** In the words of ADR 0007 F1: "the project reports bitwise agreement and
never promises it, on any platform including a single machine; R0 bit-identity of structure plus
D2 agreement for floats is the promise." The registered platforms are Linux x86-64 and aarch64
with Python 3.13 and the one lock (`requirements.lock`, `ead4edf1…`); floats are compared under
`K04-numerical-policy-v1`.

**Review status of every package** (each manifest's `status`; human `review` fields as
recorded):

| Package | Status | Human review (numerical / process model) |
| --- | --- | --- |
| P00 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K04 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K05 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K06 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| T01 | `tested` | pending / pending |
| T02 | `tested` | pending / pending |
| T03 | `tested` | pending / pending |
| T04 | `tested` | pending / pending |
| T05 | `tested` | pending / pending |
| T05b | `tested` | pending / pending |
| T06 | `tested` | pending / pending |
| T07 | `tested` | pending / pending |
| T08 | `tested` | pending / pending |

`reviewed` on P00–K06 is Frank's sign-off of 2026-09-23 in R-017's qualified form: it records
examination without objection, not a guarantee of correctness. T01–T08 are `tested`: their
design-lane reviews are recorded under `docs/reviews/`, and their human `review` fields are
`pending`. T08's manifest is at the release candidate `C` = `67c66d9`
(`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`): 85 checks, 83 pass and
2 FAIL (T08.A70 and B23, V14 (b), accepted by Frank in ADR 0021 D3).

**Licensing.** Apache-2.0 (`LICENSE`, `NOTICE`). The sdist and the wheel carry the project's own
code, its package data and its licence files only (ADR 0006 mode A); CasADi (LGPL-3.0-or-later),
numpy and scipy are fetched by the installer from PyPI.

## v0.0.0 — 2026-09-23

The first vertical slice: an ideal three-component flash–recycle process, solved, independently
verified, replayable, and inspectable from the command line.

**What it does.** Compiles a declared flowsheet to a sparse residual and exact Jacobian
(CasADi 3.8.0); solves a three-variable tear with a damped Newton and bounded phase attempts;
verifies the answer with a verifier that shares no factorization, cache or intermediate with
the solver; issues a `SolutionCertificate` or a `FailureBundle`; writes a replay bundle that a
third party can re-run or, failing that, inspect.

    python -m process_runtime.application.cli solve SYN-001-nominal --out ./bundle
    python -m process_runtime.application.cli inspect ./bundle
    python -m process_runtime.application.cli replay ./bundle

**Acceptance.** All seven gates of plan §5.1 are met — `PYTHONPATH=. python
scripts/v0_0_gate.py` reads them from the committed evidence rather than re-deriving them. Six
of the seven are **met with limitations**, and the limitations are on the report rather than in
a footnote. 1320 tests, green on x86-64 and aarch64.

**What it is not.**

- **Not empirically validated.** SYN-001 is synthetic: three pseudo-components with invented
  constants. Nothing here has been compared against experiment or an independent simulator.
- **Not a guarantee.** The human sign-off on every evidence manifest records that someone with
  the relevant expertise examined it and raised no objection — register R-017, and the field
  says so itself. Defects are expected to surface in verification and validation studies.
- **Not general.** The check set, the balances and the tear are written for the SYN-001
  topology. A general structural decomposition is T01 and does not exist, which is what most of
  the recorded limitations are waiting on.
- **Not a certificate of solution accuracy.** `VERIFIED` certifies the residuals at the
  registered tolerances; the first-order solution-error bound is recorded and disclosed, never
  promised.

**Known limitations, by gate.** K01's second-order derivatives through an opaque callback
(`unsupported`, reported rather than fabricated); K02's rank report; K03's initializer chain,
of which only the registered local initializer is wired; K04 and K06's structural
over-specification, which needs T01's matching; K05's clean-container replay.

**Reproducibility.** Structural artifacts are bit-identical across x86-64 and aarch64 —
measured, in CI, every push. Floating-point agreement is *reported* and never promised: two
`ubuntu-latest` runners were measured disagreeing on a converged state's last bits, and the
project's promise is R0 structural identity plus agreement within the declared numerical
policy. A changed dependency cannot produce an exact replay, because the mode is decided from
the environment before anything runs.

**Licensing.** Apache-2.0. No third-party binaries are redistributed; CasADi is fetched from
PyPI by the installer.
