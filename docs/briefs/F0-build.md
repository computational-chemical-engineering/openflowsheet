# Build brief: F0, the corpus identity gate (0.4)

Status: brief, 2026-11-05. Roadmap 0.4 (ADR 0057, R-928); build lane, no design pass. Spec: `docs/roadmap/target-architecture.md`
§3 F0 (lines 712–736), review finding S1 (byte-level freeze, §2.4.4 item at line ~473), assumption A1 (line ~1080).
Branch `wp/F0`, worktree `.claude/worktrees/f0`. Decisions log: `docs/F0_DECISIONS.md` (create; append-only).

## What to build

`scripts/corpus_identity.py --check` prints **one summary line** (PASS/FAIL with per-measure counts) and writes a full
log file; exit code 0 only on PASS. It checks the registered corpus:

| Measure | What is compared |
| --- | --- |
| M1 | `content_hash` of each repository revision |
| M2 | `model_version` and `constants_sha256` of each compiled problem |
| M3 | `r0_sha256` of each registered run |
| M4 | `state_sha256`, bitwise, on the reference platform |
| M5 | Certificate verdicts and check results |
| M6 | Cache-key digests of a recorded request sample |
| M7 | Replay verdicts of the 0.3.0 bundles |
| M8 | Schema round-trips |
| M9 | SHA-256 of each identity-bearing legacy module (§2.4.4), listed by path |

- **The corpus** is enumerated from existing registries (assumption A1, not yet verified): benchmark references, the W27
  snapshot, the release gate's bit-identity steps. Many `scripts/*_identity.py` already exist (t02–t07, s08, s08b,
  s10c, s11, k05_structural_identity, m02_g2_corpus). **Where an existing step measures something, F0 wraps it; do not
  duplicate it.** Write the corpus as a committed, registered list (with expected values) so a later change shows up as
  a diff. If A1 turns out false for a measure (nothing enumerable), record it in the decisions log and report it.
- **M9:** an "identity-bearing legacy module" is one whose bytes enter an `implementation_sha256` (§2.4.4). Enumerate
  them by finding what feeds `implementation_sha256`, not by hand.
- **`.gitattributes`:** mark `*.py` and every data file whose bytes enter an identity as `text eol=lf`. The index has no
  CRLF files today (checked 2026-11-05); prove `git add --renormalize .` changes nothing.
- A pytest wrapper so the gate and CI run F0; keep it fast enough for `scripts/gate.sh` or mark it as the existing slow
  identity tests are marked (follow the established pattern).

## Exit (all required)

1. The gate passes on the branch head (= main + F0).
2. A one-ulp change to one registered parameter makes M2 (through `constants_sha256`), M3 and M4 fail.
3. A test-only mutation that flips one check result makes M5 fail.
4. A one-byte change to a frozen module makes M9 fail and names the file.
Mutations are tests (temporary copies or monkeypatching), never edits to committed fixtures.

## Rules

- **F0 is inert:** it must not change any number, hash, fixture or released file. If wrapping a step seems to need a
  change to an identity, stop and report.
- No relaxed checks, no removed cases. A measure that cannot be implemented now is reported as not implemented, never as
  passing.
- Run the tests you touch; run `scripts/gate.sh` once at the end (in the worktree:
  `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`; start it with
  `run_in_background` and wait for its notification; read the log only on failure, by `grep`/`tail`).
- Write `evidence/F0/<commit>/manifest.json` following the newest manifests under `evidence/` (look at
  `evidence/S13/` for the current form); `status: tested` only if every exit item passed; never `reviewed`.
- Commit on `wp/F0` only, staging named paths, messages starting `F0:`. Do not push, do not merge into `main`.
- Context cap about 150k tokens: if you approach it, commit what is complete, write `docs/F0_HANDOFF.md` (≤ 40 lines:
  done, next, open), and stop.
- Never read, stat or touch `~/.config/procsim/`. Do not start subagents.

## Report (≤ 30 lines)

Commits, the summary line, the four exit results, the corpus size per measure, any measure not implemented and why,
whether A1 held, and build choices logged in `docs/F0_DECISIONS.md`.
