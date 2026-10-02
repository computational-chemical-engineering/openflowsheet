# Brief — T06 reference acquisition (DWSIM, IDAES): environments and representability

**To:** `opus-engineer` (build lane), worktree isolation
**From:** the session (build lane), 2026-09-24
**Why now:** plan §4.3 T06 row "Start reference acquisition after P03" and §6.4 "Acquire
DWSIM/IDAES examples early"; the v0.1 schedule review (`docs/v0.1-schedule-review.md` §3.2) found it
has not started. It is the longest external risk on the v0.1 critical path.

## The question

Can this machine run pinned, reproducible DWSIM and IDAES environments headless, and **which of the
plan's simple fixtures can each tool express with the same model equations as ours**? Deliver the
environments and a representability table — **not** comparisons, verdicts or tolerances (those are
the design lane's, T06: `verdict`/`specifier`).

## Rules that bind you (read `CLAUDE.md` first)

- Isolated environments only, git-ignored under `.venv-*/` or a directory under `.gitignore` —
  exactly like the P02 spikes (`scripts/build-backend-envs.sh`, `docs/backend-environments.md`).
  **Never touch `requirements.lock`** or the project `.venv`.
- Pin exact versions and record hashes of every downloaded artifact. Record the licence of every
  tool, solver binary and property database as stated by its source; "free to download" is not an
  open-source licence (blueprint D19). Bytes are not committed; hashes and URLs are.
- **Separate access/build problems from scientific ones** (plan §6.4). A tool that cannot be built
  or run here is `BLOCKED` with the exact error log kept — never skipped silently, never worked
  around by editing the tool.
- Do not compare numbers against this project, do not choose tolerances, do not tune either side.
  If you run a tool's own example to prove the environment works, record its output as an
  environment check only.
- Record whether a tool's property package or correlations are shared with ours (SYN-001 is
  synthetic: ideal VLE, Antoine-type `K(T,P)`, constant-cp enthalpy — see
  `docs/derivations/SYN-001.md`) and whether a user-defined synthetic compound set with our
  constants can be entered at all. That determines whether SYN-001 is comparable or only
  real-chemistry fixtures are.
- No pushes, no merges, no outward-facing actions beyond downloading public packages.

## What to produce (on branch `wp/T06-refs` in your worktree, committed, not pushed)

1. `scripts/build-reference-envs.sh` — reproducible build of both environments (IDAES via pip with
   its solver extensions; DWSIM via its Linux distribution and a headless automation route — its
   automation API through pythonnet or its CLI, whichever works; record what you tried).
2. `docs/reference-environments.md` — what the script produces: versions, hashes, licences,
   platform notes, what failed and the exact error, and how long a build takes.
3. A representability table in that document for plan §6.4's fixtures — mixer, splitter, heater,
   ideal flash, valve, liquid pump, conversion reactor, recycle — per tool: `expressible with the
   same equations` / `expressible with different equations (say which)` / `not expressible` /
   `BLOCKED (access)`, and for each whether a synthetic component set with user constants is
   possible. Evidence for each cell: the tool's documentation section or a minimal script you ran.
4. One smoke test per working tool (its own example flowsheet runs headless and returns), kept as a
   script under `spikes/references/` and **not** wired into `scripts/check.sh` (the gate must not
   depend on external tools).

## Verification

The gate `PATH=.venv/bin:$PATH ./scripts/check.sh` still passes (your files must not break ruff/mypy;
put scripts where the existing spikes live and follow their lint exclusions). The build script runs
twice with the same result.

## Report back

Worktree path, branch, commit; per tool: works / partially / BLOCKED with the reason; the
representability table; licences; anything that needs Frank (rights, data access, accounts). Stop
and report rather than guess if a step needs an account, a licence acceptance on someone's behalf,
or a paid component.

## Out of scope

Comparisons and verdicts; choosing the eight release comparisons; any change to `src/`, `tests/`
(beyond nothing), schemas, the spec or reference values.
