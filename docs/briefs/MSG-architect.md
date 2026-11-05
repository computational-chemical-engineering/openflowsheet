# Architect brief: MSG, messages a student understands (0.4, wave 1)

Status: brief, 2026-11-05. Roadmap 0.4 package MSG (ADR 0056 Amendment 1; ADR 0057 rule C3; Frank put MSG first in 0.4,
ahead of X04). Carries FB-05, with FB-01 and FB-03 folded in (`docs/USER_FEEDBACK.md`). One architect pass, then the
build lane implements, then one reviewer pass.

## The question

Design the error, refusal, warning and notice model that every surface (Python API, CLI, HTTP, MCP, web shell) shares,
so that each message says what, where (user names), why and what to do, carries its kind (input / not supported in this
version (limitation id) / numerical / internal bug / `notice`), is layered (human first line → stable typed code →
details), shows the triggering numbers, has a docs page and `openflowsheet explain <code>`, and is tested against a
corpus of beginner mistakes in CI — **without changing a frozen interface, a typed code, or any replay identity**. Also
fix FB-01 and FB-03 inside that design. Deliver a design note with work orders an `opus-engineer` can execute.

## Why it needs the architect

It is a cross-cutting change to the error model of a frozen application contract (ADR 0019): fifteen closed `ApiError`
codes, free-text `code(detail)` refusals in many modules, ~21 solver taxonomy codes, a replay comparator that compares
message templates exactly (ADR 0025), and ~229 test assertions plus a CLI golden file that pin codes and output. The
catalogue it introduces is also the slot F1 extensions register into later (rule C3) and the "typed gap" the agentic
layer reads (R-931). A wrong shape here is paid for by every later package.

## Current state

The recon digest `docs/briefs/MSG-recon-digest.md` (263 lines, `file:line` anchors, excerpts; FB-01/03/05 copied
verbatim from the tutorial's FEEDBACK.md in §9, including FB-05's worked examples) is your map of the code. Read it
whole; read source only to confirm a point it makes. The essentials:

- **No catalogue, no registry, no `explain`, no per-code docs, no failure-kind enum.** The one closed enum is
  `ApiErrorCode` (15 codes, `src/openflowsheet/application/types.py:69-86`; HTTP map `:88-104`;
  `schemas/api-error.schema.json:16-32`). Other codes are free-text prefixes `code(detail)`, e.g.
  `phase_regime_mismatch(S4)` (`models/thermal/kernel.py:552`, list `:19-23`), `initializer_failed(T)`
  (`orchestrator/tear.py:681`); solver taxonomy codes in `verify/failure.py:28-75`.
- **FB-01:** `LocalApplication.create` on a non-empty directory raises a bare `StoreError` (`store.py:252-256`, a
  `RuntimeError`, no code). `LocalApplication.open()` exists (`local.py:214`). No `exist_ok` anywhere. Frank's choice:
  keep the refusal, name `open()` in the message, add `create(..., exist_ok=True)` (opens an existing project, refuses a
  non-empty directory that is not a project), make the README quickstart use it (`tests/test_readme_current.py` keeps
  the README current). Keep the word "directory".
- **FB-03:** `RunResult.error` (`types.py:1157`) is `job.error` (`local.py:1002-1017`); a non-converged solve ends the
  job `completed` with `error=None` (`jobs/runner.py:591-593`); the reason is only in `failure-bundle.json`
  (`revision_run.py:864`). `not_found: no such artifact` comes from `local.py:1481-1488` with no member list or outcome.
  Asks: the failure on `RunResult`; `not_found` names the member, the outcome and the bundle's members; an outcome check
  in the quickstart.
- **Surfaces:** all go through `operations.py:544` dispatch and `project_error` (`:526`). CLI `cli.py:52-55` (exit 2..16
  by code, 1 = call never made); `solve` prints the outcome only (`cli.py:103-121`); `inspect` prints the bundle taxonomy
  (`cli.py:165-171`). HTTP `bindings/http.py:123-131`. MCP `bindings/mcp.py:241-245` (`isError` with an `ApiError`).
- **Warnings and notices** (certificate statuses, limitations L-…, `extrapolated`, …): digest §5.

## Constraints and invariants

- **ADR 0019 D5 / R-095:** one `ApiError{code, message, detail, retryable}`, closed code enum, new codes only by ADR;
  domain outcomes are results, not errors. **R-159:** every refusal's `message` begins with its reason code; tests match
  the prefix. **R-109:** hints beside an unchanged code. **R-104 / ADR 0020 D8:** job events carry no solver messages;
  the `t07` identity key carries no message text. **R-022:** kinds conflict / incomplete / unsupported are distinct.
- **ADR 0025** (`docs/adr/0025-cross-platform-replay-comparison.md:173`, `:192`): the replay comparator treats
  `message`/`cause` as "template exact; tokens D2.1" and wants float-free messages at the producer. A message rewrite can
  therefore break replay of released 0.3.0 bundles. Decide where human text lives so that released bundles replay and
  revision hashes, run fingerprints, certificates and cache keys do not move (F0, the corpus identity gate, will check
  this; until it exists, bit-identity is proved by test).
- **ADR 0057 rule C3** (target-architecture §2.6, verbatim): "Every `ApiError` code and every typed refusal or limitation
  code has a catalogue entry: what, where (a template over element ids), why, what to do, and the kind: input, not
  supported, numerical, bug, or `notice` for codes that are not failures (`relabel`, `extrapolated`, `anchor_bridged`,
  limitations). Extensions register entries through F1. CI fails on an emitted code without an entry. `explain <code>`
  is an operation." And: "MSG's catalogue is keyed by code, uses parameterised templates and is extensible." Rule C1:
  one OPERATIONS row per capability on every transport, so `explain` is an operation, not a CLI-only command.
- **Units:** X04 (units at the boundary; conversion only in dispatch and projection, internal values SI; ADR 0001 D1.1,
  ADR 0016 D1.2) comes after MSG. MSG shows numbers with SI units now and must leave the slot X04 fills (display units),
  not implement conversion.
- **F1** (extension registry) is designed later in W1 (P1). MSG must not fix F1's structure; give it a catalogue it can
  register into.
- Additive only: existing request and response schemas unchanged, round-trip fixtures pass, new codes are additive.
  Python 3.11+, the repository's existing style; a docs site exists (`docs-site/`, MkDocs).

## Already decided, not open

- MSG before X04 (Frank). FB-01's shape is Frank's choice (above). FB-04 part 1 is dropped: the legacy turbine is not
  fixed; MSG's message must explain that limitation and the workaround (re-declare the outlet phase) until F5 and
  `std.turbine` solve it.
- Messages are for a student first: no internal class names in the first line; user element ids (stream `S4`, unit `T`).

## Genuinely open (decide these)

1. Where the human text lives: catalogue rendering at projection time from `(code, params)` vs. stored message text;
   what a producer must emit (structured params) and how legacy `code(detail)` strings map into it.
2. The catalogue's form (Python registry, data file, schema), its identity (versioned? hashed?), and how CI enforces "no
   emitted code without an entry" (static scan, runtime registry check, or both).
3. The failure-kind and layering fields: in `detail` (additive) or a new `ApiError` member (ADR) — and the same for
   refusals inside results, warnings and certificate notices.
4. FB-03: how a failed run's cause reaches `RunResult` while R-095 keeps outcomes as results (an outcome/cause member vs.
   `error`), and the improved `not_found`.
5. `explain <code>` as an operation on all transports, and per-code docs pages generated from the catalogue.
6. The beginner-mistake corpus: its form, where it lives, what a test asserts (first line, kind, code, named element,
   suggested action), and its size for 0.4.
7. Exit codes and CLI rendering (the golden file `tests/fixtures/t07/cli-existing-commands.json` pins stdout and exit).

## How the answer will be verified

The full gate (`scripts/gate.sh`); the CLI golden file; ~229 code/status/`isError` assertions (digest §6) stay green or
change only where the note says why; replay of the released 0.3.0 bundles and the G10 records bitwise; a test that
every emitted code has a catalogue entry; the beginner-mistake corpus in CI; the README quickstart test.

## Deliverable

1. `docs/design/MSG-messages.md`: the design (each open item decided, rejected alternatives with reasons), the catalogue
   schema and a worked entry for at least `phase_regime_mismatch`, `isentropic_state_two_phase`, `not_found` and FB-01's
   refusal, rendered on CLI, HTTP and MCP; the identity analysis (what may and may not move); **work orders** WO-1…n, each
   with files, acceptance tests and whether it touches identity; and a short list of build choices left to the engineer.
2. A Proposed ADR `docs/adr/0058-messages-and-code-catalogue.md` if any decision changes a frozen interface or adds an
   `ApiError` code or member; otherwise say in the note why none is needed.
3. Report ≤ 30 lines.

Do not commit; the orchestrator commits. Write no production code. Do not start subagents. Never read, stat or touch
anything under `~/.config/procsim/`. Do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`.
Do not edit `docs/roadmap/foundation-rulings.md` (a specifier is amending it concurrently).

## Out of scope

X04's unit conversion, ST's stream table, F1's registry design, translations into other languages, the web shell's
visual design, and rewriting every existing message (the note picks the 0.4 coverage; the catalogue grows after).
