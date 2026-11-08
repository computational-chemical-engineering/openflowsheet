# Specifier brief: X05 — an installed package replays its own bundles (0.4)

Status: brief, 2026-11-07. Roadmap (ADR 0057) 0.4 package X05; ADR 0056 row 6 (R-925, Frank 2026-11-01: R-140 lifted
as policy, "the behaviour below stays until that package lands"). Design pass per roadmap: none (no architect); this
specifier pass writes the ADR and the test specification because X05 changes what `lock_sha256` attests (replay
identity, ADR 0007 D4/D6) — R-140's watch item forbids building it without an ADR 0007 amendment.

## The question

What must an installed package record and check so that its own bundles can replay with an honest mode — never a false
`exact_replay` — and what are the falsifiable assertions that prove it?

## Current state (recon, 2026-11-07; paths under `src/openflowsheet/`)

- `run/manifest.py:91-96` frozen `Environment`: `architecture, os_name, os_release, python_version, lock_sha256, blas,
  threads, superlu_options_ref`; `:169 environment(lock_path=None)`: `lock_sha256 = file_sha256(resolved)` (whole-file
  bytes) if a file, else `""`. `:185-217` `_repository_lock` → `_checkout_lock(__file__)`: only inside a source checkout
  (`parents[1] == root/src/openflowsheet`, `pyproject.toml` name `openflowsheet`) → `root/requirements.lock`.
  `manifest_sha256` includes the environment; `structural_sha256` excludes it.
- `run/replay.py:73 decide_mode(recorded, current)`, before anything runs: (1) either `lock_sha256` empty →
  `inspected_archived_results`; (2) lock hashes differ → inspected; (3) arch/OS not in `REGISTERED_PLATFORMS`
  {x86_64, aarch64}×Linux → inspected; (4) `identity()` differs → `compatible_reproduction`; (5) BLAS version differs →
  compatible; (6) thread pins differ → compatible; (7) threads unset either side → compatible; (8) `exact_replay`.
  `replay()` (`:172`) returns `NOT_RUN` in inspected mode. `application/revision_run.py:1019` uses the live
  `environment()`.
- Schema `schemas/run-manifest.schema.json:66-98`: `environment` closed (`additionalProperties: false`),
  `lock_sha256` pattern `^([0-9a-f]{64})?$`.
- Packaging: setuptools; `requirements.lock` (47 lines, `name==version`, no hashes; sha `ead4edf1…b9c4`) is **not** in
  the wheel; `pyproject.toml` pins five direct dependencies, transitive ones float. `requirements-coolprop.lock` is
  hash-pinned. Clean-install CI (`ci.yml:592`) installs `-c requirements.lock` then the wheel `--no-deps`.
- Pinning tests: `tests/test_t08_r3_a19_lock_lookup.py` (`:101` three states end to end: installed → `""` and
  inspected/`NOT_RUN`), `tests/test_k05_replay.py:152-161, :539-547`, `scripts/t08_rc.py:461-535 lock-check` (T08.A19,
  states a/b/c, "never MATCH"), envelope `benchmarks/t08/support_envelope.yaml:835-841` L41.
- F0: M7 judges replay verdict + integrity of the 52 v0.3.0 bundles (`tests/fixtures/f0/v0.3.0-bundles`, recorded
  `lock_sha256 ead4edf1…`), mode only on the reference platform; `run/manifest.py` and `run/replay.py` are outside M9.
- ADR 0067 (F8, frozen core R-941) `:33`, `:104` step 4: "Environment: ADR 0007 D4's mode from lock, platform and
  threads, unchanged"; its data lock (`data_lock_sha256`, ADR 0061 D10) is a different lock.

## Already decided, not open

- R-140's rejected alternative stays rejected: shipping the lock and recording its hash unchecked (false exact path).
- T08 §6.3 B12 is the starting design: the wheel carries the lock; `environment()` records its hash only after checking
  every locked distribution's installed version against it, else `""`; an ADR 0007 D4/D6 amendment.
- The v2 core is frozen (R-941): stay inside ADR 0067's step 4 or say exactly which sentence needs an amendment.
- No relaxed checks; a bundle recorded in a checkout must keep its present replay outcome (F0 M7 must stay PASS).

## Genuinely open (decide each, with the rejected alternative)

1. The check: which distributions (all lock lines, or the transitive closure of `openflowsheet`'s requirements),
   compared how (`importlib.metadata` version equality; normalised names; extras such as coolprop); what a missing or
   extra distribution means; cost at each `environment()` call (cache per process?).
2. What `lock_sha256` attests after X05, and whether a checkout and an installed wheel with the same verified lock
   should compare equal (same hash) — i.e. can a bundle made in CI's checkout replay `exact_replay` from the wheel.
3. "With the environment match stated" (ADR 0056): is a new field needed (e.g. the lock's source: checkout / wheel /
   none, or the failing distribution) — the environment object is closed, so a schema change is ADR 0019 Amendment 14 —
   or does the existing `reason` of the replay outcome carry it?
4. The packaged lock's identity: the same bytes as `requirements.lock` (so `ead4edf1…` stays), where it lives in the
   wheel, and the wheel-content test that pins it.
5. T08.A19's "never MATCH" states and L41: which assertions are retired, which restated, and the envelope change.

## Verification the build will be judged by

Numbered falsifiable assertions (X05.A01…), each with its test and a control: installed + matching versions →
recorded hash = the checkout's; one distribution off by a version → `""` (or the stated reason) and inspected/`NOT_RUN`;
the stray-lock defect stays fixed; checkout behaviour unchanged; F0 M7 PASS; clean-install CI job exercising the wheel
path on both architectures.

## Deliverable

`docs/adr/0069-X05-replay-from-the-wheel.md` (Proposed; amends ADR 0007 D4/D6; ADR 0019 Am. 14 only if a schema
changes; next free numbers verified), with the test specification and work orders for one build engineer, and register
lines drafted (not numbered — `wp/MSG` and `wp/RP` hold R-942…R-949 unmerged). Commit on main (docs-only, named
paths; any Python under `docs/derivations/scripts/` must pass `ruff check` and `ruff format --check` first). Report
≤ 30 lines.

## Out of scope

F8's data locks; the release procedure; MSG/ST/RP; the coolprop extra beyond stating how its lock interacts.
