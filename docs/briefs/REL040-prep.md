# Engineer brief: 0.4.0 release prep — x05 gate entry, RP.L11 (ADR 0074 O-3), S-6 rehearsal

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** No tag, no release, no publish.

## Where

New branch `wp/REL040p` from `origin/main`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p`.
Worktrees have no `.venv`: `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; confirm
`openflowsheet.__file__` is the worktree's copy. Serial tests, `OMP_NUM_THREADS=1`. Another engineer works on `wp/X04`
in parallel — never touch its worktree.

## Authority

ADR 0055 (Accepted 2026-11-08; WO-R5 deferred by Frank), the normative `docs/derivations/release-procedure.md` (RP),
`docs/RP_DECISIONS.md`, `docs/reviews/RP-review.md` (S-6, ruling 8), ADR 0074 (Accepted; its schema change is already
applied — `work_package` admits `REL…` ids; **no further schema ADR is needed**), `release/lines/0.4.json`.

## Do (one commit per item, messages naming REL040)

1. **x05 gate entry.** RP §6.1 step 4 (`release-procedure.md` ~:422) names checks `a44.*` and `x05.*` for the clean
   install; `release/lines/0.4.json` lacks `x05`. Add the entry in the line file's own form (the logged intent:
   `[4, "x05.*"]` and `tests/test_x05_*.py` in the 0.4 gate) — find the exact member by how `a44.*` is listed. Run the
   release-gate/line tests (`tests/test_rel_*.py tests/test_release_workflows.py`) and the RP loader checks.
2. **RP.L11 (ADR 0074 O-3, its default).** Paste the rule verbatim from ADR 0074 O-3 (~:259–262) into RP's loader
   checks (~:145–186) as RP.L11, dated and citing ADR 0074 O-3: "for `role` `gate`, `gate_set.evidence_package` equals
   ADR 0074 D2's id of `<line>.0`". Implement it in `scripts/release_gate.py` with its own encoder of D2 (do not import
   the schema's regex), and a test with the control ADR 0074 names (`0.4.json` with `REL050` is refused; `REL040`
   passes). Register entry in `docs/decision-register.md` only if RP amendments get one by precedent (check how RP §17.2
   / R-970 was done); otherwise log in `docs/RP_DECISIONS.md`.
3. **S-6 rehearsal.** One background run of `scripts/release_rc.py local` with every step of the 0.4 line, at the
   branch head (a `main` commit plus items 1–2), as a rehearsal — records go under the work directory in the
   scratchpad, **never** into `docs/` or `evidence/`, and are not a candidate C. First read RP §5–§6 and
   `release_rc.py`: list which inputs each step needs (`--ci-run`, `--nlp-prefix`, `--journey`, `--w27-artifacts`).
   - If a step needs a GitHub `release_rc` workflow dispatch, read `.github/workflows/*.yml` first: dispatch only if
     it creates no tag, release, package upload or anything outside this repo's Actions artifacts; otherwise skip that
     step and record why.
   - Inputs that need the nlp environment or W27 archive: use what exists on this workstation; if an input is absent,
     run the remaining steps and record the missing input. Never copy the V17 login token (R-116).
   - Load: `uptime` first; the machine is shared (≤ ~36 busy cores; another engineer runs tests). If the run would
     exceed that, run the steps sequentially.
   - Outcome: a table step → ran / failed (first error line) / skipped (reason). A runner bug you can fix within the
     brief's scope (a script error, not a numerics change): fix it as its own commit with a test, log it in
     `docs/RP_DECISIONS.md`, re-run that step. Anything that would change a number, a gate threshold or an identity:
     stop and report.
4. Append the rehearsal result to `docs/RP_DECISIONS.md` (S-6 section: commit, steps ran/failed/skipped, fixes).
5. Tests: `tests/test_rel_*.py tests/test_release_workflows.py tests/test_evidence_manifests.py`; F0
   `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`. Push `wp/REL040p`. No manifest, no
   merge (the orchestrator decides the evidence form).

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. Cap ~150k context: commit, write where you
stopped in `docs/RP_DECISIONS.md`, end. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 20 lines)

Commits per item; RP.L11 test result; the S-6 step table; fixes made; test counts; F0 line; anything stopped on.
