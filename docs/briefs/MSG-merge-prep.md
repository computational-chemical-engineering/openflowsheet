# Build brief: MSG — merge preparation after Frank's review (0.4)

Status: brief, 2026-11-08. Frank approved the `explain.md` description on the decision board (2026-11-08; record
`docs/FRANK_QUESTIONS.md` "Answers — Frank, 2026-11-08"). MSG merges first of MSG → X02 → OPT → RRC → ST
(`docs/roadmap/decisions.md` 2026-11-08). **Do not spawn sub-agents yourself.**

Branch `wp/MSG`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/msg`, head `35403f42`; manifest
`evidence/MSG/9c76b939…` (`implemented`); log `docs/MSG_DECISIONS.md` (or the package's decisions file); review
`docs/reviews/MSG-review.md`. Merge rule now (CLAUDE.md, Frank 2026-11-08): CI green on both architectures is the merge
condition — no local full gate.

## Do, in order (one commit each, messages `MSG: …`)

1. `git merge main` into `wp/MSG` (no squash). Main now has WIT (manifest X10a), S15a (ADR 0074, R-970), X10, X05 and
   docs. Resolve conflicts the way earlier merges did (`HARVEST_SIZE` in `tests/test_m07a_harvest.py` recomputed;
   `benchmarks/t08/support_envelope.yaml` entries combined; `scripts/t08_support_matrix.py --emit` then `--check`;
   register entries kept from both sides). Log each resolution.
2. **Human review:** in `src/openflowsheet/application/bindings/descriptions/REVIEW.json`, `explain`'s `human` review →
   `"status": "reviewed", "reviewed_by": "Frank Peters", "reviewed_at": "2026-11-08"`, exactly as the other human
   reviews on main are recorded. First confirm the file's sha256 still equals the recorded `explain` hash (the text
   Frank read was `wp/MSG:…/explain.md` at `35403f42`); if the text changed since, stop and report.
   `test_every_description_is_reviewed_by_both_lanes` must now pass on this branch.
3. **Register:** MSG's R-942/R-943 collide with RP's R-942…R-949 on main. Renumber MSG's two entries to **R-975** and
   **R-976** (block R-975…979 is MSG's) everywhere on the branch: `docs/decision-register.md`, ADR/decision/test text
   that cites them. `grep -rn "R-94[23]"` before and after; RP's own R-942/R-943 must stay untouched.
4. **Surface chain:** MSG merges first, so it keeps link c_4. After step 1, re-run the surface-digest and R4-G3 tests;
   if a digest moved because of what main brought, re-record it and log old → new.
5. Targeted tests (one run at a time, `OMP_NUM_THREADS=1`): the description/REVIEW tests, surface/R4-G3 tests, MSG's
   own tests (`tests/test_msg*` or as the handoff names them), catalogue checks, `tests/test_m07a_harvest.py
   tests/test_t08*.py tests/test_evidence_manifests.py`; `scripts/corpus_identity.py --check` PASS; `ruff check`,
   `ruff format --check`, `mypy` clean.
6. Push `wp/MSG`. Do not merge into main and do not write the manifest (the orchestrator waits for CI first).

## Rules

No relaxed checks, no edited gates; never set `reviewed` on the package manifest. Named paths only (never `git add -A`);
trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first, targeted tests only. Never read
or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; nothing in other
worktrees. Context cap ~150k: commit, write `docs/MSG_HANDOFF.md` (≤ 40 lines), stop.

## Report (≤ 20 lines)

Commits and head; conflicts resolved; REVIEW.json hash check; renumbering (files touched); digests old → new; test
counts; F0 line.
