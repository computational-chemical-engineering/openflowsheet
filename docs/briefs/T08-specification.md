# Brief — T08 specification: v0.1 release evidence, supported envelope, v0.2 real-chemistry selection

**To:** `specifier` (design lane). **From:** build lane, 2026-09-29. **Branch:** `wp/T08` (from `main` at
`16c4fbd`; T07 merged).

**Deliverable:** the T08 specification `docs/derivations/T08-release-spec.md`. It must contain:
- (a) the judging criteria for each release gate V11–V20 (what counts as MET for v0.1, and what the evidence must contain);
- (b) the **supported envelope** of v0.1 as a registrable statement (what is supported, what is explicitly unsupported and how it fails, and the registered limitations);
- (c) the **V19 real-chemistry dossier** criteria and the candidate assessment (see §5 item 3);
- (d) the definition of a reproducible release candidate;
- (e) numbered falsifiable assertions;
- (f) any ADR needed (0021 is the next free number) and register entries;
- (g) a build-lane **work order in phases**.

Write no production code. Do not commit.

## 1. The package (plan v1.2 §4.3, row T08 — binding)

> T08 | T06, T07: v0.1 release evidence, supported envelope and v0.2 real-chemistry selection. | Gate
> V11–V20; selected chemistry/data/kinetics/property/reference dossier; reproducible release candidate. |
> MOD/SYS | Design / Build

The gates (plan §4.3 table, `docs/implementation-plan.md:340–349`; minimum evidence in `docs/requirements.yaml`):

| Gate | Required evidence | Owner packages |
| --- | --- | --- |
| V11 | Semantic diff, drafts, task validation, units/references, real migration when applicable | K06/T01 |
| V12 | Required unit library with per-model definition of done | T05 |
| V13 | DM/SCC/BTF, tear and EO, scaling and initialization | T01/T02 |
| V14 | Homotopy, qualified PTC/SER and three bounded recovery edges | T04 |
| V15 | Frozen phases, EO cross-unit spec, multiple-root evidence | T02/T03 |
| V16 | 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20×20 ensemble | T06 |
| V17 | Local/HTTP/MCP, ten agent tasks, ≥80% success, zero unauthorized actions/false verification | T07 |
| V18 | Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested | T06/T08 |
| V19 | Real-chemistry dossier with a usable data/kinetics/property/reference route | T08 |
| V20 | ≥95% nominal robustness, correct invalid-structure handling, no adversarial false verification | T06/T08 |

Plan §4.4 (v0.2) begins with M01: "pin the selected PyMRM reactor and one required nonideal property
route". So the V19 selection has to feed M01.

## 2. What exists

The factual ledger is `docs/t08-gate-ledger.md`, a recon digest with build-lane corrections at its top. Read it first. In short:
- **Manifests.** Every owner package has a tested manifest: K06, T01–T07, T05b. V17 is already MET, by the `verdict` of T07 (`docs/reviews/T07-verdicts.md`).
- **V16/V20.** T06 run 2 PASSED S = 434/440 on both architectures. The holdout gave 436/440. The references were 16/16 AGREE (`docs/reviews/T06-verdicts.md`).
- **V14 is the hard one.** T04 F1 left PTC **experimental**; V14's PTC clause is incomplete (`docs/T04_STATE.md`, `docs/progress.md`). Frank's F1 default is in force.
- **V18.** ADR 0006: D4/D5 require a notice bundle before any mode-B artifact, with the METIS remedy open (Q2 answered by Frank 2026-09-22: default confirmed, and neither R4 nor R5 pursued). `LICENSE` is Apache-2.0, confirmed by Frank 2026-09-23.
- **Registered limitations and hand-ons:**
  - `docs/T05b_STATE.md`: zero-duty flash at its dew point is UNVERIFIED.
  - `docs/T06_STATE.md`: 4 not_applicable checks (A09, A10, A58, A94) deferred to M01; stress profiles not run.
  - `docs/T07_STATE.md`:
    - R-088 Q24/Q25 (K04 amendment);
    - S-R5, S-G, R4-O1, R4-O2;
    - F6 (fallback not built);
    - V17's scope (one pinned model, MCP only, T09 0/6, INJ-4 never exposed, run records lacking the lock hash);
    - the A89 aarch64 flake;
    - an unmapped rank error class.
- **Human review.** No package is `reviewed`; the numerical/process-model sign-off is Frank's. He has reviewed the 17 MCP tool descriptions (2026-09-29).
- **V19 candidate material.** OpenIDAES-450 / CRAFTS was audited on branch `origin/study/openidaes450` in `docs/openidaes450-audit.md`: access, rights, a first audit, and candidates flagged for T08. Read it with `git show origin/study/openidaes450:docs/openidaes450-audit.md`. Blueprint §11.4 says CRAFTS must have its executable artifacts, splits and licensing checked before it becomes a gate. PyMRM is named by plan M01.

## 3. Constraints

- Every registered result and identity key stays as registered (`t02`…`t07`; K05 minus-`t07` `9a7b4e6d…`).
- CLAUDE.md "Scientific conduct": no relaxed checks and no narrowed denominators. A gate that is not met is reported NOT MET; it is not reworded. Numerical verification, empirical validation and optimality evidence are kept distinct.
- Frank's standing directives:
  - fewest limitations;
  - robustness with recorded fallbacks;
  - "a fallback may change the method, never the problem".
- No outward action. Tagging, publishing and data acquisition that costs money or needs rights are Frank's.

## 4. Already decided — do not reopen

T07's rulings and ADRs 0019/0020; ADR 0006's distribution modes; Frank's F1 default (PTC experimental), which stays in force **until** Frank decides whether v0.1 may ship with it.

## 5. Genuinely open — decide or frame these

1. **Per gate, the judging criteria for v0.1.** Which existing evidence the `verdict` agent should judge, and what is missing. For V14, say precisely what "qualified PTC/SER" requires and what it would cost, versus releasing v0.1 with V14 NOT MET or with a registered, scoped qualification. That scoping is a decision for Frank; frame it as a question with a recommended default.
2. **The supported envelope:**
   - components and property model (SYN-001 only?);
   - unit models;
   - topologies (recycle, tear/EO);
   - specifications and units;
   - interfaces (Python/CLI/HTTP/MCP);
   - what fails typed.

   Every registered limitation must be listed with its evidence.
3. **V19.**
   - The dossier's required contents: chemistry, component set, property route (nonideal), kinetics, data rights, a reference route (independent tool or data), and the PyMRM reactor for M01.
   - The selection criteria.
   - An assessment of the candidates you can identify from the OpenIDAES-450 audit and the plan. The **choice is Frank's**: give a ranked recommendation with its reasons and costs.
   - Say what can be verified offline now, and what needs acquisition or rights (Frank).
4. **The reproducible release candidate:** what it is (tag, lock, notice bundle per ADR 0006 mode A, replay of registered bundles on a clean environment, CI on both architectures), and what T08 may do versus what needs Frank.
5. **V18/V20's T08 halves.** What T06 left for T08.
6. **Hand-ons.** Which of T07's hand-ons (listed above) block a gate, and which become v0.2 backlog.

## 6. How it will be verified

`verdict` judges each gate against your criteria. The build lane produces any missing evidence. Then come CI on both architectures, `reviewer` on anything built, and `evidence/T08/<commit>/manifest.json`.

## 7. Out of scope

M01–M07 implementation (v0.2), the web shell (M06; its design sits on `design/web-shell-brief`), and publishing.
