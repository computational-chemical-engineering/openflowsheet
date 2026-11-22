# X07a-WO1: Windows and macOS CI legs and a platform layer (roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
base `main` c4a91a75. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the
cap, commit what is complete, write where you stopped in `docs/X07a_DECISIONS.md`, and end.

Authorization: Decision Desk card ofs-05-widen, option B (Frank, 2026-11-19): "open the 0.5 lanes X07a and X01 rest,
each as wp/<ID> with its own brief, beside S19 at one lane". You may push `wp/X07a` to `origin` to run CI (the repo is
public, CI minutes are free). Never push, merge into or rebase `main`; never tag.

## Scope (roadmap.md:50; ADR 0056 row 5, `docs/adr/0056*.md:31`)

"Windows and macOS supported: CI legs on `windows-latest` and `macos-latest` (arm64), process isolation and kill chain
per platform (Job Objects on Windows, process groups on POSIX), path and spawn handling, per-platform reference records
where floating point differs, the support envelope's machine axis, install docs." The `nlp` and reactor environments
on three OSes are **X07b**, not here: on the new legs they are declared platform limitations (R-924, risk R5 at
`docs/roadmap/target-architecture.md:1190`), refused with a typed result, never faked.

## Facts already established (recon, 2026-11-19)

- CI: `.github/workflows/ci.yml`, one job `check`, matrix `runner: [ubuntu-latest, ubuntu-24.04-arm]` (ci.yml:78-80),
  `fail-fast: false`, runs `./scripts/check.sh` (ci.yml:149). No Windows or macOS leg anywhere.
- No platform abstraction module exists. POSIX-only calls in `src/openflowsheet`:
  `application/store.py` fcntl.flock (25, 1126, 1137, 1151, 1188); `adapters/experiments/store.py` fcntl.flock (29,
  289); `application/jobs/executor.py` os.killpg(pid, SIGKILL) (100-107); `application/jobs/worker.py` os.setpgid(0, 0)
  (98, ADR 0033 D2); `adapters/external/launcher.py` win32 refusal (211), Popen (236), SIGTERM/SIGKILL (351-354);
  `application/jobs/interrupt.py` (signal); `adapters/pymrm/env.py`, `child.py` (subprocess, signal);
  `registry/__init__.py:611-634` `platform_unsupported(<id>, <platform>)` typed refusal, :711 platform.system();
  `studies/nlp/closure.py:228-229`; `run/manifest.py:202`.
- `.gitattributes` marks `*.py *.pyi *.json *.yaml *.yml *.csv *.toml *.lock *.md *.txt *.jsonl *.log` and SHA256SUMS
  `text eol=lf` (F0). F0 is to run on every leg once X07a exists (target-architecture.md:121, :876; M9 catches a CRLF
  checkout by file name).
- ADR 0061:232-241 (Windows PermissionError on replace, path length 168) is F3's store, which is not on `main`: take
  its rule into the platform layer's atomic replace only if it applies to an existing store on `main`.
- No acceptance table for X07a exists in the plan; the checks below are the acceptance for this work order.

## Read (narrowly)

ADR 0056 row 5; ADR 0033 D2 (process groups; grep it); `registry/__init__.py:600-720`; the call sites above;
`scripts/check.sh`; `ci.yml`; `.codehealth/playbook.md` (rules for new code) and `.codehealth/config.toml:228-265`
(`repo-layers` order). `docs/S19_RULES.md` on `wp/S19` only for the codehealth rules if you need them.

## Deliverables

1. **Platform layer**: one small module (proposed `src/openflowsheet/_platform.py`, or a package if it grows past one
   concern), standard library only (no new dependency unless recorded as a DECISION with the reason): file lock
   (fcntl.flock on POSIX, msvcrt.locking on Windows, same blocking/non-blocking contract as today), process-tree
   spawn and kill (POSIX: new process group, killpg; Windows: Job Object or CREATE_NEW_PROCESS_GROUP + a documented
   kill chain), atomic replace with the Windows PermissionError retry if needed. Add it to the `repo-layers` order next
   to `openflowsheet._files`; `codehealth arch --depth 4` must stay at 0 cycles and 0 violations.
2. **Call sites** moved onto the layer. On Linux and macOS the same syscalls with the same arguments run as before:
   behaviour on Linux is bitwise unchanged (no numerics touched).
3. **CI**: add `windows-latest` and `macos-latest` to the matrix (fail-fast false), the same `scripts/check.sh`
   (bash is on the Windows runners; make the script portable where needed). F0 (`scripts/corpus_identity.py --check`)
   runs on every leg.
4. **Typed platform limits**: what cannot run on a leg (nlp, reactor child, external-subprocess-v1 on win32 today) is
   refused through `registry.platform_unsupported` or an explicit skip naming the limitation. Each skip is a row in
   `docs/X07a_DECISIONS.md` (test or module, platform, reason, the package that lifts it: X07b, X15, ...). No blanket
   skip of a test module, no relaxed tolerance, no removed case (CLAUDE.md "Scientific conduct").
5. Install notes for Windows and macOS in the existing install docs (find them; one section each).
6. `docs/X07a_DECISIONS.md` (build-decisions log: `DECISION: <q> -> <choice>. Alternative: <x>. Reversible by: <how>.`)
   and `evidence/X07a/<commit>/manifest.json` (ADR 0059 layout; follow the latest manifest under `evidence/F1/`),
   status `implemented` until CI is green on all four legs, then `tested`. Never `reviewed`.

## Stop and report instead of choosing (design-lane questions)

- F0 measures differ on a new leg (M2 to M5, i.e. a floating-point difference): do not exclude the leg or the measure.
  Record the measured difference (which measure, which records, first differing value) in `docs/X07a_DECISIONS.md`,
  leave that F0 step failing, and report: per-platform reference records are a design-lane ruling (ADR 0067 D7, R9).
- A change on Linux to any identity-bearing byte (F0 M9 module list) or to a frozen interface (ADR 0076).

## Acceptance (report each with the command and its one-line result)

- Linux: the tests you touched pass locally (repo-root `/home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -m pytest`
  with `PYTHONPATH=<worktree>/src`, no `-n`); `scripts/corpus_identity.py --check` PASS; `codehealth arch --depth 4`
  (binary `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth --repo <worktree>`) 0 cycles, 0
  violations; `codehealth scan` health of every touched file not lower than at c4a91a75.
- CI on the pushed head: both ubuntu legs green (merge condition), windows-latest and macos-latest green with the
  typed limits of deliverable 4; or, if a leg is red at your budget cap, the failing job's first error and your
  diagnosis in the decisions log. Give the run id.
- Commits name the package (`X07a: ...`), named paths staged (never `git add -A`). Report in 200 to 300 words.
