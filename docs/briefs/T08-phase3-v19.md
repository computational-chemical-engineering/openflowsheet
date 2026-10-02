# Brief — T08 Phase 3: V19 facts for the ammonia synthesis loop (C1)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §7 (the dossier: §7.1 required contents, §7.3 C1's
assessment, §7.5 what is offline vs Frank's), §9 rows **T08.A60–A64**, §12 Q6/Q7, §15 Phase 3 (W3.2–W3.4);
ADR 0022 (Proposed). **Frank chose C1, the ammonia loop (F3, 2026-09-29)**; he states the group repository is MIT.

## DECISION (session): W3.1 is not run

W3.1 (re-acquire OpenIDAES-450, 220 MB, and re-measure C2–C5) served the ranking; Frank chose C1, and no IDAES-450
case covers ammonia (§7.3). Alternative: run it for completeness. Reversible by running W3.1 later. Record this in
the dossier's provenance section.

## Items (one commit each; messages `T08 W3.n:`)

1. **W3.2 — T08.A61, Q6.** The group's reactor repository is local at `/home/frankp/Codes/ammonia_synthesis_reactor`
   (remote `gitlab.tue.nl:SMM/research_projects/eajfpeters/ammonia_synthesis_reactor`; do not push or pull; read and
   run only). In a **separate pinned venv outside this repository** (e.g. under the session scratchpad
   `/tmp/claude-1003/-home-frankp-Codes-Process-Simulator/c1654ca5-cf40-4fac-b53a-1914bdd081e5/scratchpad/`; record
   the exact package versions, `pymrm` 2.1.20, and the repo commit hash), run its own regression test(s) and record
   the result against the group's regression tolerance (quote it); time one 1D solve; test a no-membrane
   configuration. Commit a small record `benchmarks/t08/v19/c1-reactor.json` (versions, commit, tolerance, result,
   timing, no-membrane outcome) and a test that checks the record's form (it does not re-run the external model).
   Also find, from the repository's code, `documents/` and README, **which published rate law the kinetics class
   implements** (paper, equation, parameter source) and where the Rossetti et al. data come from; record what you
   find with file:page pointers — do not guess; "not determinable from the repository" is a valid answer.
2. **W3.3 — T08.A62, A63, Q7.** IDAES 2.13 in another separate venv (outside the repo): Peng–Robinson flash for the
   N₂/H₂/NH₃ (+ Ar/CH₄ inerts if the loop needs them, per §7.3) system at two states — a two-phase high-pressure
   separator state and a single-phase reactor-inlet state; record phase split and K-values (no comparison claimed).
   Build the loop skeleton (reactor with an equilibrium or stoichiometric form, cooler, flash, purge, recycle) headless
   and solve it once; the representability table (unit, method, reaction form: Y/N with reason). Commit the records
   under `benchmarks/t08/v19/` and the scripts that produced them (scripts may live under `benchmarks/t08/v19/` and
   must not be imported by the package or the default test run; a test only checks the records' form). If IDAES
   cannot be installed offline or a solver is missing, record exactly what failed and stop that item.
3. **W3.4 — T08.A60, A64.** Draft `docs/v02-real-chemistry-dossier.md` with §7.1's twelve items, each with status
   (`met` / `needs_fact` / `needs_frank`) and evidence pointers, and the rights table (A64: source, licence or
   permission, scope, mode for every code and data item; mark anything not established as `needs_frank`, never
   `unknown`). The design lane finalizes scores and ADR 0022.

## Rules

Nothing outside `benchmarks/t08/v19/`, `docs/v02-real-chemistry-dossier.md` and their tests changes in this
repository; no `requirements.lock`, `pyproject.toml`, schema, src, spec or ADR change; IDAES/pymrm never enter the
project's environment. No outward action (no pushes, no downloads that need credentials or payment; PyPI/conda
public installs are fine). Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the user
is near a weekly usage limit — keep investigations focused; full `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`
once at the end.

## Report

Commits; the regression result vs tolerance and timing; the no-membrane outcome; the rate-law and data provenance
found (with pointers); the PR flash results; the skeleton solve and representability table; the dossier's item
statuses; what remains for Frank.
