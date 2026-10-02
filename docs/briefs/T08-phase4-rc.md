# Brief — T08 Phase 4: the release candidate machinery (no tag)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §8 (8.1 definition, 8.2 the RC job, 8.3 what T08 may do
vs Frank), §9 rows **T08.A34, A40–A50** (read them all), §15 Phase 4 (W4.1–W4.5), and its amendments (R2: §8.1
item 2 — the description review, now recorded); ADR 0021 D1–D5 with its proposed revision 1 and the D3 row (V14 (b)
carried as FAIL, Frank 2026-09-29); ADR 0006 (mode A: sdist/wheel of the project only, `LICENSE`, `NOTICE`, the
CasADi LGPL statement; Amendment 1).

## Items (one commit each; messages `T08 W4.n:`)

| Item | What | Assertions |
| --- | --- | --- |
| W4.1 | Version `0.1.0rc1` (wherever the version is declared — find every place, keep them consistent); `CHANGELOG.md` draft per ADR 0021 D4 (the gate table as `v0_1_gate.py` prints it, FAILs included — V14 (b) FAIL; "what it is not"; known limitations by support-matrix id; the reproducibility promise in ADR 0007 F1's words; review status of every package) | — |
| W4.2 | Package the runtime data the installed package needs (spec Q1: schemas resolved from the source tree today — make them package data and resolve them via `importlib.resources`; an installed wheel must find them); sdist and wheel built twice, contents limited per A43, `Requires-Dist` pins equal `pyproject.toml`'s, unpacked contents identical file by file | T08.A43 |
| W4.3 | CI: clean-install job and bundle-set replay job on both architectures (`workflow_dispatch`-only or on push — follow §8.2/A44/A45) | T08.A44, A45 |
| W4.4 | The RC job (§8.2) — check, identity, ensemble (local `ref-x86-64` and CI `ci-aarch64`), corpus, references, agent surface, inventories, certificate audit — as a script plus a `workflow_dispatch`-only CI job; do not dispatch | T08.A34, A41, A42, A46–A49 |
| W4.5 | `scripts/v0_1_gate.py`: reads the verdicts and evidence and prints the V11–V20 table; exit ≠ 0 on any unlisted FAIL or BLOCKED (ADR 0021 D2/D3: V14 (b) is a listed FAIL with Frank's acceptance) | T08.A50 |

**Not in scope:** tagging, publishing, pushing to PyPI, running the RC job at `C` (the session does that), Phase 5.

## Rules

- `requirements.lock` must not change (R-121); a moved schema byte or identity key: stop and report. Moving the schemas
  into package data must leave every schema byte, every schema `$id` and every identity value unchanged — prove it
  (sha256 of every schema before/after; `measure_identity`: whole K05 `7f32b143…`, `t07` `422aa7a5…`).
- No change to MCP tools/descriptions, specs, ADRs or registered results. If §8/§9 is under-determined, stop and report
  with file:line.
- Work in this checkout; nobody else edits it. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  and `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only; no build
  artifacts committed (`dist/` ignored). Budget: the user is near a weekly usage limit — targeted tests while
  developing; full `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` once at the end.

## Report

Commits; where the version lives; the package-data change and its byte-identity proof; sdist/wheel contents and the
two-build comparison; the CI jobs added (names, triggers, dispatch inputs); what `v0_1_gate.py` prints today; `check.sh`
counts; questions.
