# Work packages after 0.2.0, sorted by where they can run

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

## Local-only packages (Frank's workstation)

| ID | Work | Why local |
| --- | --- | --- |
| L1 | Verdict F7: G11's `job_id` pattern (`m02-g11v3-<label>`) fixed in G11's script and the runner, then re-verified | Code edit can be cloud; the re-run needs the reactor environment |
| L2 | M05 review N1, S75, S77; any M03/M05 re-take | nlp environment (Ipopt) |
| L3 | M04's off-Haswell question; J25 `env.verify` vs R-259 | machine-specific measurement |
| L4 | **v0.3 S03**: two independent column references, perturbation studies | external reference environments (likely) |
| L5 | Any release candidate (RC steps 12, 14, 17), the journey at a cut, W27/V17 campaigns | reactor/nlp environments, the archive, the login token (R-473) |

## How to run a cloud session cheaply

Read `CLAUDE.md`, then `docs/V02_STATE.md` (position) and this file. Run **one agent at a time**. Each package gets a
brief file under `docs/briefs/` (question, facts with `file:line`, exit test). Cap agent context at about 120k, and
keep reports to 150 words or fewer. Gate by risk, as `CLAUDE.md` says: docs need no local gate, and code runs the
tests it touches. Run the full `scripts/gate.sh` once before merging into `main`, in the background, and read only its
summary line. Push the branch `wp/<ID>` and let CI judge both architectures. Merge to `main` only with a `tested`
manifest where the package has one.
