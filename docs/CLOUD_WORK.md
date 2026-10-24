# Work packages after 0.2.0, sorted by where they can run

**2026-10-23 (Frank): no more cloud sessions** — that budget is nearly gone. Every package below, cloud or local,
now runs in workstation sessions; the cloud/local split is kept only as a record of what needs local assets.

0.2.0 is released (tag `v0.2.0`, 2026-10-20). This file sorts the open work by **where it can run**: in a cloud
session (a fresh clone, no local assets) or only on Frank's workstation. It does not re-plan anything. Package
order and scope are still those of `docs/implementation-plan.md` §4.5 and the decision register. Starting v0.3 (S01)
is Frank's call.

## What a cloud session has, and what it lacks

- **Has:** the repository, including every committed record, `coverage.json`, the registrations, the ADRs and
  `.claude/agents/`; the project environment from `requirements.lock`; GitHub CI on both architectures.
- **Lacks:** the OpenIDAES-450 archive (`evidence/M06/W27/artifacts`, ignored, local), the V17 login token (never
  copied, R-116), the nlp environment (`.venv-nlp` with Ipopt, `.reference-downloads/m03-ipopt`), the pinned reactor
  environment (PyMRM), and `~/.claude` (the global routing policy and session memory).
- **Gate:** `scripts/gate.sh` runs without the archive. The archive-dependent W27 tests skip (about 60), and a run
  without the symlink has passed. Run the browser test with `REQUIRE_BROWSER=1` only where a browser exists. Rely on
  CI for both architectures.

## Cloud packages (in suggested order)

| ID | Lane / agent | Work | Exit | Notes |
| --- | --- | --- | --- | --- |
| C1 | design / `architect` | Transient-readiness re-check, ADR 0008 Amendment 2 | Amendment committed; `tests/test_adr_0008_transient_readiness.py` still passes | Brief `docs/briefs/ADR-0008-A2-readiness-recheck.md` (Frank, 2026-10-18) |
| C2 | design / `specifier` | OpenIDAES-450 development/held-out split registration; takes up R-474 (F-1, W27-R02 consulting `topology.json#/units`) | Registration + generator `--check`; seeded split reproducible from committed `coverage.json` | Brief `docs/briefs/OpenIDAES-split-registration.md`; Frank's rules are in it |
| C3 | build / `sonnet-implementer` | Housekeeping, each with a test. (a) Verdict F8: `scripts/m07_g11_experiments_audit.py` accepts a point relabelled `direct`. (b) `scripts/t08_rc.py` install-check strips `sys.path` under the repo root, which fails `tests/test_v02a_r347_machine_class.py` when `.venv` is inside the checkout. (c) Reused IDs W27-A20…A22 (M07 spec §22.3). (d) Milestone 0 F3 / the schema `$id` move. (e) Refresh `docs/progress.md` | Full gate; CI green | (b) may need a one-line ruling if the check's scope is registered (read R-347 first) |
| C4 | build / `opus-engineer` | Classify M07a's ~42 unharvested envelope rows (A8-Q1, deferred at 0.2.0; M07 spec §25) | Envelope mapping complete; harvest tests per R-485 | Committed manifests only |
| C5 | design / `specifier`, then build | **v0.3 S01**: countercurrent equilibrium-stage subsystem (derivation, DOF, energy/phase coupling, initializer, Newton continuation), then its implementation and tests | Plan §4.5 S01 exit | Frank starts it. Pure-Python numerics on the existing property providers |
| C6 | as C5 | **v0.3 S02**: MESH column conventions, four matched cases, invalid-spec/phase tests | Plan §4.5 S02 exit | After S01 |

**Next cloud queue (Frank's answers, 2026-10-22; C1–C6, C7, D1 and S04 are done and on `main`):**

| ID | Lane / agent | Work | Exit |
| --- | --- | --- | --- |
| C8 | build / `sonnet-implementer` | A "multiple steady states possible" warning on every duty-only column specification (Q-S02-4) | Tests and the full gate |
| C9 | design / `specifier` | W27 Amendment 3 for the NEXT release's registration: allow more than one route per method; fix the `Co`/`CO` case clash (L01-Q1). v0.2's W27 stays unchanged | Registration, generator `--check` |
| C10 | design / `specifier`, then build | **IAPWS-95** as a planned v0.3 addition: an ADR (use case, affected requirements, acceptance), a derivation and test spec against the published IAPWS tables, then the implementation (L01-Q3) | Plan-level manifest `tested` |
| C11 | design, then build | Column specifications by purity, recovery and stage temperature: the next column package (Q-S02-2) | Plan-level manifest `tested` |
| C12 | build, then design | Rights check of each source for the nine `pr-lib-v1` records, an attribution file, then the design lane amends T08.A32 (L01-Q4). Release only after that | Rights rows vetted; A32 amended |
| S07 | design / `specifier`, then build / `opus-engineer` | **CoolProp as an optional external property provider, pure fluids first** (Frank, 2026-10-23). ADR + spec first: CoolProp called only as a Helmholtz evaluator at (T, ρ) with its analytic pure-fluid derivatives, the project's own phase logic, retry rules and exact-input caches kept; one pinned CoolProp version as an optional dependency (not in the default wheel), so its data is not redistributed by us; bit-identity on both CI architectures; cross-check against S05 (water) and the S04 records. Mixtures out of scope until measured (composition derivatives would need declared, audited finite differences). Then the implementation and tests | Plan-level manifest `tested` |

## Local-only packages (Frank's workstation)

| ID | Work | Why local |
| --- | --- | --- |
| L1 | Verdict F7: G11's `job_id` pattern (`m02-g11v3-<label>`) fixed in G11's script and the runner, then re-verified | Code edit can be cloud; the re-run needs the reactor environment |
| L2 | M05 review N1, S75, S77; any M03/M05 re-take | nlp environment (Ipopt) |
| L3 | M04's off-Haswell question; J25 `env.verify` vs R-259 | machine-specific measurement |
| L4 | **v0.3 S03**: two independent column references, perturbation studies | external reference environments (likely) |
| L5 | Any release candidate (RC steps 12, 14, 17), the journey at a cut, W27/V17 campaigns | reactor/nlp environments, the archive, the login token (R-473) |
| S08 | **One-phase column sections** (Frank, 2026-10-24, Q-S03-4 "Yes, plan a package"; provisional id from S03 spec §17.7): teach the phase logic to converge columns whose right answer has an all-liquid or all-vapour section, instead of the typed failure S03 registers as a limitation. Design lane first | after S03 merges |
| S09 | **Third column reference tool** (Frank, 2026-10-24, Q-A2-4 "Plan a 3rd tool"): a reference tool beyond IDAES and DWSIM (candidates COCO/ChemSep; licences to check) for S03's column cases with fewer than two references — RC4 refluxed absorber (none), RC3 stripper and RC7 interior-stage temperature (IDAES only). Design lane first | after S03 merges |

## How to run a cloud session cheaply

Read `CLAUDE.md`, then `docs/V02_STATE.md` (position) and this file. Run **one agent at a time**. Each package gets a
brief file under `docs/briefs/` (question, facts with `file:line`, exit test). Cap agent context at about 120k, and
keep reports to 150 words or fewer. Gate by risk, as `CLAUDE.md` says: docs need no local gate, and code runs the
tests it touches. Run the full `scripts/gate.sh` once before merging into `main`, in the background, and read only its
summary line. Push the branch `wp/<ID>` and let CI judge both architectures. Merge to `main` only with a `tested`
manifest where the package has one. C-items and design-lane ruling rounds (D1, …) have none: they merge on the read full gate and
CI green on both architectures, recorded in the merge commit message. A C-item that is or becomes a plan package takes
that id and its manifest (C5 = S01, C6 = S02); L01 is renumbered S04 for its manifest (D1, R-565).
