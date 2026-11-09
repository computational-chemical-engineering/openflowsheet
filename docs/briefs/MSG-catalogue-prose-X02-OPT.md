# Specifier brief: MSG catalogue prose for X02's and OPT's new codes, and OPT D-93 (corpus case C12)

Status: brief, 2026-11-09. Design-lane wording ruling, batched for two packages now on main. **Do not spawn sub-agents
yourself.**

## The questions

1. Are the catalogue entries the build lane wrote for X02's and OPT's new user-visible codes correct, plain and
   consistent with the MSG house style? Rewrite any that are not.
   - X02 (D-39, `docs/X02_DECISIONS.md`): complete entries for `warm_start_source_missing` and
     `warm_start_unit_unknown`; `coupling_warm_start` allow-listed in `scan-allow.yaml` as a trace label.
   - OPT (D-92, `docs/OPT_DECISIONS.md`): complete entries `nlp_solver_unavailable` and `request_invalid`; stubs
     `DECISION_NOT_CONTINUOUS`, `DECISION_UNIT_NOT_INTERNAL`, `REVISION_MISMATCH`, `REVISION_UNBOUND`,
     `TOO_MANY_STARTS`, `OPTIMIZATION_ROUTE_UNAVAILABLE`, `REGIME_MARGIN_UNDEFINED`; labels `k03_kind_bound`,
     `no_declared_bound`, `phase_row_not_closure_test` allow-listed; L-OPT-2 reworded to pass G4.
   All are flagged `review: true`. For each: keep / rewrite (give the exact new text) / complete the stub (give the full
   entry). Check every allow-list reason really is never rendered to a user.
2. OPT D-93: MSG corpus case C12 ("validating a revision for the task optimization") registered `task_unsupported`;
   ADR 0071 lifted that refusal, and the build lane re-pointed C12 to `nlp_solver_unavailable` (what the default
   environment now emits). Is that the mistake C12 should register, or should C12 be replaced by a case that still
   exercises an unsupported task? Rule, with the exact case text if it changes.

## Where to read

`src/openflowsheet/messages/catalogue/*.yaml` (entries; the MSG style is set by ADR 0058 and
`docs/design/MSG-*.md` — find the house-style section and the WO-2 stub form), `scripts/msg_catalogue.py` (G1–G4 checks,
including G4's wording lint), the emitting code for each code (grep the code name under `src/openflowsheet/`), OPT's
design §4.11 and X02's design `docs/design/X02-warm-starts.md`, the MSG corpus (grep `C12` under `tests/` and
`benchmarks/`).

## Deliverable

A ruling note `docs/reviews/MSG-catalogue-X02-OPT.md`: per code keep/rewrite/complete with the exact YAML to apply, the
`review` flag value after your ruling (you may clear `review: true` only for entries you have ruled final), the C12
ruling, and a numbered work order for the build lane (which files, which regeneration commands — catalogue digest,
`message_entry` fixtures, doc pages, CLI pins — and which tests to run). Do **not** edit the catalogue or tests
yourself. Commit the note on **main** (docs-only, named path, message `docs: MSG catalogue prose ruling for X02/OPT
codes; OPT D-93`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull --rebase` if the push is rejected). Report ≤ 15
lines, including whether anything needs Frank (default expectation: no).

TRS2 shared: `uptime` first; reading only, no test runs. Never read or touch `~/.config/procsim/`,
`/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`. Out of scope: any code other than these.
