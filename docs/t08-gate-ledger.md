# T08 Gate Ledger: V11–V20 Evidence Reconnaissance

> Recon digest (read-only, cheap model), factual input for the design lane. Build-lane corrections: the
> T06 reference comparisons were **16/16 AGREE** (DWSIM and IDAES; positive controls DISAGREE), not
> "IDAES mixed" (`docs/reviews/T06-verdicts.md`). The `LICENSE` file is Apache-2.0, confirmed by Frank
> 2026-09-23 (`120acb4`). No verdict here: gates are judged by `verdict`.
>
> **W1.1 (T08.A02).** The ledger of record is `docs/requirements.yaml`: V11–V20 `evidence` now lists the T08
> release spec §3.1 manifests of the gates each serves (`evidence/T08/<C>` joins V18–V20 at W5.3), and G00–G06
> carry `PASS` with their owner manifests, backfilled from `scripts/v0_0_gate.py` (spec Q8, FD2; six of seven
> met with limitations, which that script prints). `tests/test_t08_w1_ledger.py` holds both.

**Date:** 2026-09-29 | **Branch:** `wp/T08` (= main + one docs commit) | **Git tag:** v0.0.0 only

## Gates V11–V20: Evidence Status

### V11: Semantic diff, drafts, task validation, units/references, real migration when applicable

**Text:** `docs/implementation-plan.md:340`  
**Owner packages:** K06/T01  
**Required evidence:** Semantic diff, drafts, task validation, units/references, real migration when applicable

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| K06 | `evidence/K06/cda68cd446be27992051d43422336ad5f9430fe8/manifest.json` | reviewed | 6 pass, 1 unsupported, 1 n/a | K06.structural_over_specification (unsupported: needs T01 matching); K06.jobs_and_remote_bindings (n/a: T07) |
| T01 | `evidence/T01/00a71f4562b7bd80441df50cf64b53064d832b78/manifest.json` | tested | 26 pass | 26 checks all pass |

**Requirement status (`docs/requirements.yaml`, W1.1):** V11 verdict: null; evidence: K06, T01, T06, T07 (spec §3.1)

---

### V12: Required unit library with per-model definition of done

**Text:** `docs/implementation-plan.md:341`  
**Owner packages:** T05  
**Required evidence:** Required unit library with per-model definition of done

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T05 | `evidence/T05/91ac0103c1040175560d74d9afa2a091a8d25b2d/manifest.json` | tested | 31 pass | No unsupported or not_applicable checks |

**Requirement status (`docs/requirements.yaml`, W1.1):** V12 verdict: null; evidence: T05, T05b (spec §3.1)

---

### V13: DM/SCC/BTF, tear and EO, scaling and initialization

**Text:** `docs/implementation-plan.md:342`  
**Owner packages:** T01/T02  
**Required evidence:** DM/SCC/BTF, tear and EO, scaling and initialization

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T01 | `evidence/T01/00a71f4562b7bd80441df50cf64b53064d832b78/manifest.json` | tested | 26 pass | — |
| T02 | `evidence/T02/b68585f775cc2b009ae1b130eebb865150cf943c/manifest.json` | tested | 37 pass | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V13 verdict: null; evidence: K02, K03, T01, T02 (spec §3.1)

---

### V14: Homotopy, qualified PTC/SER and three bounded recovery edges

**Text:** `docs/implementation-plan.md:343`  
**Owner packages:** T04  
**Required evidence:** Homotopy, qualified PTC/SER and three bounded recovery edges

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T04 | `evidence/T04/53cd23b29d3701e3a464fa1edaa455a9a1d6fbf5/manifest.json` | tested | 34 pass | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V14 verdict: null; evidence: T02, T04 (spec §3.1)

**Known gap:** T04 F1 (PTC experimental, V14's PTC clause incomplete) — `docs/progress.md:137–141`, `docs/T04_STATE.md`

---

### V15: Frozen phases, EO cross-unit spec, multiple-root evidence

**Text:** `docs/implementation-plan.md:344`  
**Owner packages:** T02/T03  
**Required evidence:** Frozen phases, EO cross-unit spec, multiple-root evidence

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T02 | `evidence/T02/b68585f775cc2b009ae1b130eebb865150cf943c/manifest.json` | tested | 37 pass | — |
| T03 | `evidence/T03/6ac24be9da572a90b198ba91b81d603f082cfa74/manifest.json` | tested | 27 pass | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V15 verdict: null; evidence: T02, T03, T06 (spec §3.1)

---

### V16: 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20×20 ensemble

**Text:** `docs/implementation-plan.md:345`  
**Owner packages:** T06  
**Required evidence:** 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20×20 ensemble

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T06 | `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` | tested | 96 pass, 4 n/a | T06.A09, T06.A10, T06.A58, T06.A94 (not_applicable) |

**Requirement status (`docs/requirements.yaml`, W1.1):** V16 verdict: null; evidence: T06 (spec §3.1)

**Scoring:** T06 run 2 PASSED on x86-64 and aarch64 (S = 434/440 each; CI 36270294833). Holdout: 440 fresh starts S = 436 on every class. Eight reference comparisons: DWSIM and IDAES 16/16 AGREE (positive controls DISAGREE). See `docs/reviews/T06-verdicts.md`.

---

### V17: Local/HTTP/MCP, ten agent tasks, ≥80% success, zero unauthorized actions/false verification

**Text:** `docs/implementation-plan.md:346`  
**Owner packages:** T07  
**Required evidence:** Local/HTTP/MCP, ten agent tasks, ≥80% success, zero unauthorized actions/false verification

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T07 | `evidence/T07/5f3d3ea25e8349b83c8f8382df3c793532971ca4/manifest.json` | tested | 107 pass | All checks pass |

**Requirement status (`docs/requirements.yaml`, W1.1):** V17 verdict: null; evidence: T07 (spec §3.1)

**Note:** V17 MET on v17-c2 (25/30 agent tasks, pinned claude-sonnet-5; zero false verification, zero unauthorized effects; 43 VERIFIED certificates independently checked). Design/build review `docs/reviews/T07-review.md` and `T07-review-2.md` (round-6/7 fixes closed). MCP tool descriptions: Frank's human review recorded 2026-09-29 for 15 of the 17; `validate` and `commit_change` pending his re-review after the 2026-10-01 text fixes (description review N1, N2). Design-lane review of all 17 recorded 2026-10-01 (`docs/reviews/T08-description-review.md`). `review` status pending (Frank's sign-off).

---

### V18: Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested

**Text:** `docs/implementation-plan.md:347`  
**Owner packages:** T06/T08  
**Required evidence:** Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T06 | `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` | tested | 96 pass, 4 n/a | — |
| T08 | — | planned | no evidence | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V18 verdict: null; evidence: K04, P03, T06 (spec §3.1)

---

### V19: Real-chemistry dossier with usable data/kinetics/property/reference route

**Text:** `docs/implementation-plan.md:348`  
**Owner packages:** T08  
**Required evidence:** Real-chemistry dossier with usable data/kinetics/property/reference route

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T08 | — | planned | no evidence | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V19 verdict: null; evidence: none (no §3.1 manifest serves V19) (spec §3.1)

**Real-chemistry candidates identified:**
- **OpenIDAES-450** (CRAFTS; `study/openidaes450` branch): audited, commits available:
  - `bf0c574` OpenIDAES-450 note: T06 uses SYN-001; candidates flagged for T08
  - `100a8ab` OpenIDAES-450 note: position relative to T06, M06/W27 and future full cross-check
  - `6c5e84d` OpenIDAES-450: access, rights and first audit
  - Branch details in `docs/T06_DECISIONS.md` (lines 100–) and `docs/T06_STATE.md`
- **PyMRM**: Mentioned as v0.2 requirement (M01 pins reactor + property route); no v0.1 candidate selected
- **IDAES/DWSIM**: Reference implementations (T06 reference fixture data acquired, CI 36270294833)

**Constraints:** Plan §4.3 requires real-chemistry selection using scored dossier (validated reactor/kinetics, property coverage, data rights, independent simulator case, computational cost). Frank's input expected before gate verdict.

---

### V20: ≥95% nominal robustness, correct invalid-structure handling, no adversarial false verification

**Text:** `docs/implementation-plan.md:349`  
**Owner packages:** T06/T08  
**Required evidence:** ≥95% nominal robustness, correct invalid-structure handling, no adversarial false verification

| Package | Path | Status | Checks | Notes |
|---------|------|--------|--------|-------|
| T06 | `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` | tested | 96 pass, 4 n/a | — |
| T08 | — | planned | no evidence | — |

**Requirement status (`docs/requirements.yaml`, W1.1):** V20 verdict: null; evidence: K04, T06 (spec §3.1)

**Current robustness:** T06 point estimate S ≥ 418/440 (both architectures); Clopper–Pearson bound reported. Holdout: 436/440 on every class.

---

## Summary of Known Gaps and Limitations

### T04 F1 (V14 clause incomplete)
- **Location:** `docs/progress.md:137`, `docs/T04_STATE.md`
- **Status:** PTC is derived but not qualified; experimental. V14's PTC clause incomplete.
- **Impact:** V14 gate blocked unless PTC experimental status is acceptable.

### ADR 0006 D4/D5 (Distribution / LICENSE)
- **Location:** `docs/progress.md`, "Notes for Frank" section 2
- **Status:** Apache-2.0 LICENSE file confirmed present; copyright "E.A.J.F. Peters"; `NOTICE` recorded. Closed 2026-09-23. File exists at `/home/frankp/Codes/Process Simulator/LICENSE` (11358 bytes, 2026-09-23 12:22).
- **Remaining open:** Q2 — METIS disposition. Default: ship no wheel bytes. Alternative remedies: University of Minnesota approval or upstream CasADi report (Frank's decisions, not agent's).

### T06 Known Limitations
- **Location:** `docs/T06_STATE.md`, `docs/progress.md:145–156`
- **Four not_applicable checks:** T06.A09, T06.A10, T06.A58, T06.A94 (real property conformance deferred to M01)

### T07 Hand-ons
- **Location:** `docs/T07_STATE.md`, `docs/progress.md:120–121`
- **Status:** `review` pending (Frank's sign-off). MCP tool descriptions: Frank's human review recorded 2026-09-29 for 15 of the 17; `validate` and `commit_change` pending his re-review after the 2026-10-01 text fixes (description review N1, N2). Design-lane review of all 17 recorded 2026-10-01 (`docs/reviews/T08-description-review.md`).

### T05b/T05 Registered Limitations (V12 input)
- **Location:** `docs/progress.md:158–172`
- Near-pure PH feeds (vapour-fraction fallback, A29), dormant PH-type outlets on EO path (A28, UNVERIFIED), single flowing component in latent jump on EO path (A30)
- Q9: zero-duty flash fed exactly at dew point provably singular → UNVERIFIED (six sweep runs certified FAILED, never VERIFIED); K04 follow-up by default

### K04 F9 (Follow-up from T04/T05b)
- **Location:** `docs/progress.md:138`, `docs/T04_STATE.md`
- **Status:** Fresh-flash tolerances call 15 of 179 correct A02 roots FAILED; decide before T06 certifies EO solves in bulk. T05b ADR 0013 resolves (all 179 A02-family roots now VERIFIED).

---

## Project License and Release Status

**LICENSE file:** Exists at `/home/frankp/Codes/Process Simulator/LICENSE` (11358 bytes)
- **Status:** Confirmed Apache-2.0; copyright "E.A.J.F. Peters"; form: scholarly output
- **NOTICE file:** Present; recorded in `docs/decision-register.md` sign-off entry
- **Decision:** Recorded in progress.md note 2 (2026-09-23, Frank's confirmation)

**Release readiness:** v0.0 complete (gates G00–G06 green). v0.1 release gates V11–V20 in evidence phase. No package is `reviewed` — human numerical/process-modeling sign-off pending. Nothing is empirically validated. Tag: v0.0.0 only.

---

## Real-Chemistry Research Inputs (V19)

**OpenIDAES-450 Branch Analysis:**
- **Branch:** `origin/study/openidaes450`
- **Latest commits:**
  - `bf0c574` (2026-09-29): OpenIDAES-450 note; T06 uses SYN-001; candidates flagged for T08
  - `100a8ab`: Position relative to T06, M06/W27, future full cross-check
  - `6c5e84d`: Access, rights and first audit
  - `63364f8` (pre-branch): Merge wp/T05b
- **References:** Blueprint v3 (`design-history/blueprint-v3.md`), T06 decisions (`T06_DECISIONS.md:100–`)
- **Note:** CRAFTS paper (arxiv 2608.01369, August 2026, before v1 date); typed stages and deterministic engineering gates; coverage and scoring must be reported if adapted subsets used

**Other candidates:**
- PyMRM: Deferred to v0.2 (M01). Plan §4.3 allows mode-B artifact after selection; M01 pins reactor + one required nonideal property route.
- IDAES/DWSIM: Reference implementations acquired (T06). IDAES: one setting adjusted (constr_viol_tol 1e-10 → 1e-9 on REF-04/05/06); DWSIM: .NET 8 EOL 2026-11-10.

---

## Not Found

- No T08 evidence manifest yet (package status: planned)
- V11–V20 verdicts: null in `docs/requirements.yaml` until `docs/reviews/T08-verdicts.md` exists (T08.A02)
- No completed gate ledger document (expected output: `docs/t08-gate-ledger.md`)
- No explicit T05b evidence manifest in the evidence tree (merged with T05 `91ac010…`)

