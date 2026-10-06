# Brief — M06 design note: the diagnostic web shell and the external agent benchmark

**To:** `architect` (design lane, software design). **From:** the session (build lane), 2026-10-06.
**Plan row (v1.2 §4.4, binding):** *M06 — T08: diagnostic web shell; bounded topology/SFILES work only if an actual
comparison needs it; external agent benchmark adaptation. Acceptance: all actions use public application contract;
equation/trace/scenario views; benchmark coverage and artifact-access report.* Lane: **Build** lead / Design second.
Gates: **W26** (diagnostic web shell through shared contract) and **W27** (external agent benchmark adaptation
attempted; inaccessible assets disclosed). Blueprint §14.4: "Diagnostic web shell supports inspection, traces,
revision comparison, and agent history through public contracts" and "External benchmark adaptation attempted with
exact provenance and coverage; inaccessible artifacts are reported and do not block core scientific acceptance."

## 1. The question

Design M06 so the build lane can implement it in ordered work orders: the web shell's architecture (technology,
packaging, serving, auth, state, testing), its mapping of every screen to public contract operations, the minimal
ADR 0019 amendment it needs (which of the five contract asks, which record defects), and the W27 adaptation plan —
each with acceptance tests a verdict can later judge W26/W27 by.

## 2. Why the architect

It adds the project's first browser-facing component and its first non-Python asset pipeline to a codebase whose
contracts are frozen (ADR 0019/0020) and whose replay identity must not move; it decides whether and how the frozen
application contract widens; and it must be testable in a repository with no Node tooling, under a strict gate
(ruff, mypy strict, ~6900 pytest tests). Wrong choices here are expensive to reverse (dependency, licence,
packaging, contract).

## 3. Current state — read these

- **Recon digest:** `docs/briefs/M06-recon-digest.md` — contract protocols and the `OPERATIONS` table, the HTTP
  (Starlette + uvicorn) and MCP bindings, bearer-token auth and six rights, record schemas, packaging, CI, the
  authority excerpts. Recon-grade: verify against code before relying on a claim.
- **Design inputs:** `docs/design/web-shell-design-brief.md` (nine screens, design system), `docs/design/web-shell/README.md`
  (tokens), `docs/design/web-shell/gap-triage.md` (G1–G11 triage: five contract asks, defects D1–D3, design questions
  Q1–Q5 with defaults), and the Claude Design prototype `docs/design/web-shell/Workbench.dc.html` + `support.js`
  (visual reference only, not product code; it runs on Claude Design's runtime).
- **W27 input:** the OpenIDAES-450 / CRAFTS audit, readable with
  `git show study/openidaes450:docs/openidaes450-audit.md` (7 KB; rights: MIT repository, data-use permission from the
  first author to Frank on 2026-09-26 including subsets and publishing comparisons; attribution requested). It notes:
  "M06 / W27 already covers OpenIDAES-450 as an *agent* benchmark. All 450 requests can be attempted there; the measured
  claim is a correct build or a typed limitation, zero false verification, with coverage reported." Blueprint line
  ~481: adapted subsets report coverage and never inherit the original headline score. The support matrix row U14
  (`docs/support-matrix.md`) says nothing is registered for it in v0.1.
- **Agent evaluation precedent:** T07's V17 campaigns (`docs/reviews/T07-verdicts.md`; agents through MCP, pinned
  model, 30 tasks, zero false verification and zero unauthorized effects judged) — the pattern an agent benchmark run
  should follow.

## 4. Constraints and invariants

- **Every action goes through the public application contract** (the same operations Python/CLI/HTTP/MCP expose).
  No private backdoor reads of the store, no second implementation of any operation in the browser.
- Replay identity, R0 and `structural_sha256` must not move. Defects D2/D3 touch hashed replay artifacts: any fix is
  design-reviewed and proved not to move registered identities (or the move is named and goes to Frank).
- ADR 0019/0020 change only by amendment (additive preferred).
- Dependencies: every new runtime or bundled asset has a recorded licence (ADR 0006; the project is MIT; casadi LGPL).
  No CDN loads at runtime for the shipped product (offline/local use; reproducibility); vendored or generated assets
  ship as package data in the wheel. The repository has no Node/npm tooling today — adding a JS build step is a
  decision you must justify against no-build alternatives.
- The gate (`./scripts/check.sh`) must stay green; UI tests must run in CI without a GUI.
- Security: the shell is local-first; bearer token auth exists; say what is exposed by default (bind address, CORS).
- Design system from the brief: light and dark, accessible, status never by colour alone, tabular numbers, SI units.

## 5. Decided — do not reopen

- M06 is off the v0.2 critical path; it runs alongside M01 (R-153). It must not wait on M01's chemistry.
- The prototype's nine screens are the scope wish list; W26's minimum is inspection, traces, revision comparison and
  agent history (blueprint §14.4) plus equation/trace/scenario views (plan row).
- SFILES/topology work only if an actual comparison needs it (plan row) — default: none.
- The OpenIDAES-450 data may be used, subsetted and published with attribution (Frank's correspondence, audit).

## 6. Open — decide these

1. Front-end technology and build (no-build vanilla JS/ES modules, a small vendored library, or a JS toolchain), and
   how assets are versioned, licensed and shipped.
2. Serving: an `openflowsheet serve`-style command on the existing Starlette app, static mount, auth flow for a
   browser (token entry, storage), defaults.
3. The screen → operation map, including which views need contract widening (the five asks) — decide each ask:
   adopt (with the exact ADR 0019 amendment text and schema change), defer, or reject. Agent history needs a source
   (ask 4) — decide.
4. Defects D1–D3: confirm or correct the triage, decide the fix and its identity impact.
5. Design questions Q1–Q5 (gap triage): confirm defaults or decide otherwise.
6. "Equation view" (Q2): what a row view carries without symbolic text.
7. Testing: how the UI is verified (contract-level tests of every call the UI makes; a headless browser test or
   not — weigh the dependency), and what W26's evidence is.
8. W27: what is attempted (which subset of OpenIDAES-450, by what agent harness, at what cost), how coverage and
   inaccessible artifacts are reported, what is claimed. Bound the cost — a full 450-case agent campaign may be too
   expensive; propose a sized plan with the cost estimate and a cheaper alternative, and mark the spend as Frank's
   decision.

## 7. Already tried / known

- The prototype was built from an excerpt of the records; most of its "gaps" were brief artefacts or are closed on
  `main` since T07 (gap triage). Three defects remain (D1–D3; the recon confirmed D1–D3 still present).
- T07's V17: the first agent campaign failed (19/30) on three system defects, fixed; the second met (25/30). Agent
  campaigns cost real money and need pre-registration.

## 8. Verification

`./scripts/check.sh` green, identities unchanged; the evidence manifest `evidence/M06/<commit>/manifest.json` must
reach `status: tested` with one check per acceptance row you define; a `reviewer` pass follows the implementation.

## 9. Deliverable

On a branch `wp/M06` from `main` (do not push; do not touch `main`): a design note `docs/design/M06-web-shell.md`
with: architecture; screen → operation table; the ADR 0019 amendment text (proposed) and schema deltas; decisions on
asks, defects and Q1–Q5; the testing strategy; the W27 plan with cost; **ordered work orders** for the build lane
(each with files, acceptance tests, and which can be given to a bounded implementer); verification gates; what M06
does not establish. Use ADR numbers from **0026 upward but coordinate**: M01's specifier is writing concurrently and
takes 0026 first — use **0030** and up for any new ADR of yours, and register entries from **R-170** up, to avoid
collisions (the session renumbers at merge if needed). Questions for Frank only for value judgements (cost, scope),
each with your default. Commits name M06 and end with:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GsDmvQLNcSrnTKTqHXyPD2
```
Stage named paths only. No production code.

## 10. Out of scope

M01–M05 science; a flowsheet drawing canvas or editor (blueprint: minimal canvas follows headless workflows);
SSP/FMI/DEXPI/CAPE-OPEN; hosting the shell publicly; changing the solver or the verifier beyond D2/D3.
