# Brief — T08 W2: implement `syn001.kinetic_cstr`

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-build-first-spec.md` Part A — §A1 (the model: contract, rows,
derivatives, causal evaluator, zero flow, realization, verifier checks, definition of done), §A3 (the PTC
mapping entry), §A5 (expected values), §C.1 (assertions), §I W2. ADR 0023 (Proposed). Reference values:
`benchmarks/t08/build_first_reference.yaml` (generator `docs/derivations/scripts/t08_build_first_reference.py`).

## Scope (W2 only)

The model, its `list_models` signature and builder (it becomes the 13th of `MODEL_BUILDERS`), the T04 mass-
mapping entry for it (§A3), the verifier checks (§A1.6), and T05 §13.2's row (already added to `docs/derivations/T05-unit-models-spec.md`
in W1; implement what it states). Follow the pattern of the T05 unit models (the conversion reactor is the
nearest) — find them first.

## Gates

T08.B10–B19 and B26 (§C.1), plus `PATH=.venv/bin:$PATH ./scripts/check.sh` green (ruff, ruff format, mypy
strict, pytest). Tests go in `tests/` following the T05 model tests' pattern; expected values come from the
YAML, never from the implementation's own output (CLAUDE.md: self-generated outputs are regression fixtures,
not validation).

## Forbidden — stop and report instead

- **No PTC run on the PTC-R1 flowsheet, and no Newton run from any registered PTC-R1 start** (the 21 × 21
  grid of §A4.2). This is the preregistration's integrity (§A4.6): the case is registered in W3 (`C_case`)
  before any result exists. Single steps at the three **off-grid** states of B15 and evaluations at the roots
  (B11–B14) are allowed; B13–B15 on the bound revision belong to W3 — if B13–B15 need the W3 revision, leave
  them for W3 and say so.
- No new quantity kind, no schema change, no MCP tool/description change, no change to any existing model's
  rows, no change to `requirements.lock`, no edit to the spec, the ADRs or the YAML. If the design is wrong
  or under-determined, stop and report the question (file:line, what you expected, what you found).
- Identity (B26): K05 minus-`t07` `9a7b4e6d…`, T02 floats `9a8a5baf…`, structural `915c97e8…`, keys
  `t02`…`t06` byte-equal; `t07` unchanged in W2 (D2/D3 are a separate increment). Show this with the
  existing identity tests, not by assertion. If adding a model to `MODEL_BUILDERS` moves any key (e.g. a key
  that hashes the model list), stop and report before going further.

## Q-A4 (build-lane fact to establish first)

The CSTR's causal `evaluate` returns an isothermal **initializer**, not a steady state (§A1.4). Grep every
caller of `UnitModel.evaluate` and confirm none treats its output as a solved answer (e.g. a verifier, a
certificate or a sequential-modular solve that reports it). Report the list of callers with file:line and your
reading. If one does, stop and report before implementing.

## Working rules

- Work in this checkout on `wp/T08`; nobody else is editing it. Commit your work in coherent commits whose
  messages start `T08 W2:` and end with the two attribution lines:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only; never
  `git add -A`. Never set `reviewed` anywhere.
- The venv is `.venv` (`.venv/bin/python`); the path has a space in it — quote it.
- Budget: the user is near a weekly usage limit. Work efficiently: read the spec sections named above and the
  nearest existing model, not the whole repository; run targeted tests while developing and the full
  `check.sh` once at the end.

## Report

Commits (hashes), the Q-A4 caller list, each gate B10–B19/B26 with pass/fail and the measured numbers against
the YAML values, the `check.sh` result (test count), anything left for W3, and any question you stopped on.
