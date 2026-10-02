# Brief — T08: run the release-candidate job at `C` and assemble the RC record

**To:** `opus-engineer` (build lane). **From:** the session. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §8.1 (what `C` is), §8.2 (the RC job's eleven steps) as
amended by R3, §9 (T08.A16, A19, A30, A34, A41–A50); `scripts/t08_rc.py`'s docstring maps each step to its subcommand
or CI job; ADR 0021 D2.4 (the tree check).

## Given

`C` = the commit the session names in its message to you (its tree must be clean). The session has pushed `C` and
dispatched CI with `rc=true` and `rc_distribution=true` at `C`; it gives you the run id. Do not push or dispatch.

## Do

1. **Local steps at `C` on `ref-x86-64`** (threads pinned to 1: `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`),
   writing records under `evidence/T08/<C>/artifacts/rc/` (git-ignored): `identity`, `ensemble` (the registered
   ensemble + T06 A34's same-class replay), `corpus`, `surface`, `certificates` over the local outputs, and the A30
   inventory (`scripts/p03_binary_inventory.py --a30`). Run the long ones in the background and wait for them.
2. **CI artifacts:** when the CI run completes (`gh run watch <id>`; poll sparingly), download every RC artifact
   (`gh run download <id>`) into `evidence/T08/<C>/artifacts/rc/ci/`.
3. **`scripts/v0_1_gate.py`** at `C`: record its output (it will still show "no verdict" — the verdicts come next).
4. **The RC record** `docs/t08-rc-record.md` (committed): `C`, the CI run id and every job's conclusion, and per step
   of §8.2 the measured result with the record file and its sha256 (records stay git-ignored; hashes are committed),
   each mapped to its T08 assertion with PASS / FAIL / not-measured as the record itself says — **report, do not
   judge gates** (the design lane's `verdict` does that). List every failure verbatim with its cause if evident.
   Commit only `docs/t08-rc-record.md` (and nothing under the D2.4 trees — a commit after `C` touching those means a
   new RC).

## Rules

No code, spec, ADR, schema or `requirements.lock` change. If a step fails because of a defect, do not fix it: record
it and report — fixing it means a new `C`. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
and `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the
user is near a weekly usage limit — wait on long runs without polling tightly.

## Report

`C`; the per-step table (assertion, result, record sha256); every failure; the gate script's output.
