# REL050 standing rules (every worker gets these; they decide nothing here)

- **Frank's words:** "Let's go for the smaller 0.5 release" (2026-11-20, R-1065). "Will you take care of the release?"
  (2026-11-21). Scope: X07a, F1, F3, X01's plugin docs. Nothing else is added to 0.5 without Frank.
- **Authority:** RP `docs/derivations/release-procedure.md` (read narrowly by section) and ADR 0055; `CLAUDE.md`
  (Scientific conduct; Branch and merge discipline; never set `reviewed` on your own package).
- **Stops (RP §12):** the engineer reports and does not choose. Nothing is edited, re-run or re-taken to pass; records
  are committed as they are. A failed gate stays failed.
- **Lanes (RP §13):** build lane: `covers`, `envelope_id`, `packages`, `required_adrs`, `evidence_package`, document
  paths, RC jobs and records, lapse report, manifest, CHANGELOG, RELEASING block. Design lane, at most three passes:
  `specifier` (claim set, gate criteria, `rc_items`, phrases), one `verdict` over all claimed gates, one `reviewer`
  only if release machinery changes.
- **Frank:** at most two batched plain-word messages (RP §8.5), through the Decision Desk via hub. The tag, the
  dispatch and the PyPI approval are his. Any merge into main needs his signed card, verified with
  `~/.claude/tools/decision_desk_verify.py`.
- **Freeze:** from K3 until the dispatch, main takes no D2.4 change (`src/`, `schemas/`, `benchmarks/`,
  `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`).
- **Host:** re-takes and steps 6, 11, 14, 15 run on a `ref-x86-64` host (`t08_rc.machine_class()`; SMM-TR09 joined
  by R-1020).
- **Git:** stage named paths; merge commits, never squash; pushes need
  `git -c credential.helper='!gh auth git-credential' push`. Never copy the V17 login token (R-116).
- **Runs:** long runs detached, one summary line, full log to a file, PID recorded; read logs by grep/tail only.
