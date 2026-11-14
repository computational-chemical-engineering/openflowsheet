# S17 review 4 (reviewer, 2026-11-13): coupled_run.py steps 577fd426..93218f5c (7 steps)
Verdict: 7 accepted (4 accept, 3 accept-with-note), 0 rejects. No behaviour difference found.
Follow-up commit (--no-gain, accepted-neutral), after WO4:
- 839117ac `_request_at` (614) -> `_rerun_request` (in-process branch runs the experiment in scratch); type the run
  parameter `ExperimentOutcome` (import under TYPE_CHECKING; module has `from __future__ import annotations`).
- a3f998be `fresh: Any` (644) -> `fresh_result: Mapping[str, Any] | None` (runner.py:105); docstring: envelope belongs
  to the run, not the result.
- 4a8a1129 helper `_solve_inner` (1106) named apart from closure `solve_inner` (1057).
- solve_coupled chain reset (`last.clear(); last.update(...)`): one-line comment.
Playbook: 12 types no weaker than before (Any where mypy inferred is a regression; TYPE_CHECKING import);
13 parameter named for what it holds, no reuse of a caller's local name for another object; rule 10 extended (a store
moved later: commit names every statement it now follows and the catch sites in between); recipe note: closure ->
thin adapter owning nonlocal/side-table writes, pure work to a module helper named apart; when-not: closure reading and
writing one side table in <= 8 lines, extracting the read alone (483fd1a3, 5.0 points).
