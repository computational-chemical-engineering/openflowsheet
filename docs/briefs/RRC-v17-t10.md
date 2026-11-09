# Specifier brief: V17-T10's offered-policy set after RRC offers `RRC-revision-v1`

Status: brief, 2026-11-09. Small design-lane ruling; it blocks RRC's merge. **Do not spawn sub-agents yourself.**

## The question

CI on `wp/RRC` `fcba6656` (run 42547017088) fails `tests/test_t07_v17_reference.py::test_g16b_reference_run[V17-T10-*]`
on all transports and both architectures: `{'T10-C1': True, 'T10-C2': True, 'T10-C3': False}`. Main is green.
`T10-C3` (`benchmarks/t07/v17/scorer.py:1358`) is the answer member `offered_policy_ids`, scored as an `exact_set`
against the reference (`docs/derivations/scripts/t07_reference.py`: `OFFERED_POLICIES` line 104;
`OFFERED_POLICIES_T08 = ("T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1")` with `T08_CHANGED_PATHS`
~line 2594 including `constants.offered_policy_ids` and `tasks.V17-T10.answer.offered_policy_ids.expected`). The
reference run (`benchmarks/t07/v17/reference.py:754`) answers with every `project["solve_policies"]` id, and RRC's
ADR 0072 (Accepted 2026-11-08) R-995 makes `RRC-revision-v1` an offered policy ("offered by name, never a route's
default"), so the project now lists five. How should V17-T10's expected set follow RRC — a registered reference change
in T08's form (e.g. an RRC set and changed-paths record, the reference JSON regenerated with its sha pins), or another
rule? Precedent inside RRC: D-45 (`.claude/worktrees/rrc/docs/RRC_DECISIONS.md` ~line 339) excluded RRC's policy from
T08's B27 by B13's rule because B27 judges T08's own four; V17-T10 is different — it asks the agent what the project
offers, so an exclusion there would make the benchmark's expected answer false. Constraints: no relaxed check, no
narrowed denominator; recorded runs (`v17-c1`, `v17-c2`) and their pinned bytes (R-115) are history and stay valid for
the version they were scored at.

## Deliverable

A short ruling appended to RRC's review or a new note `docs/reviews/RRC-v17-t10.md`: the rule, the exact edits (files,
constants, which generator regenerates the reference JSON and which sha pins move), and the tests that must pass. Do
not edit code or tests; the build lane applies it on `wp/RRC`. Commit the note on **main** (docs-only, named path,
message `docs: V17-T10 offered policies after RRC (ruling)`, trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`). Report
≤ 12 lines, including whether this needs Frank (default expectation: no).

TRS2 shared: `uptime` first; reading only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.
