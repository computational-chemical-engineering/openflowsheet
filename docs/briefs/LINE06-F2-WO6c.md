# LINE06 F2-WO6c: apply the F2-R1 D12 amendments (Opus)

Rules: `docs/LINE06_RULES.md`. Worktree `.claude/worktrees/f2` (wp/F2). Log dir `~/.cache/line06/f2-wo6c/`.
Starts after F2-WO6b has committed.

## Task

Apply the design-lane ruling F2-R1 (commit `2781db50`, `docs/F2_DECISIONS.md` section "Design-lane rulings R1
(D12)", from line 458; the work order itself is under "**Fix work order F2-WO6c**", about line 540). Read that
section in full: it is the specification. In short: in `revision_v2/lower.py` a stated `parameter_sets` must equal
the record file's legacy parameter-set records (else refused F4), `thermal_coordinate` must be `T` (else refused F6),
module docstring = the D12 text; `raise_v1.py` states the file's parameter sets; the tests listed in item 3.

## Facts

- WO6a-2 (`6f81897e`) and WO6a-3 (`90f46174`) are kept; this WO only adds the two amendments.
- Five `s10` corpus cases (GP-*) run Wilson with the file's lambdas, but the raised v2 documents currently state
  `parameter_sets: []`.
- WO6b's binder lowers without `validate`, so an `h_mass` document would otherwise run in T.
- E-F2-3 library half is 59/59 at `7ce12c23`; it must stay 59/59.

## Not in scope

Open item (1) (`validate` and `h_mass`) goes to the F2 reviewer; item (3) (F4 superset rule) keeps its default. Do
not edit ADR 0062: the orchestrator applies the D12 text.

## Acceptance

`tests/test_f2_lowering.py` and WO6b's E-F2-3 run half pass; the surface suites pass; F0
(`scripts/corpus_identity.py --check`) PASS; ruff, ruff format, mypy clean. A pinned v2 `content_hash` of a raised
`s10` document may move (unreleased test data): re-pin and log it as a DECISION. Any served digest or F0 move is a
STOP: commit nothing further and report.

Do not spawn sub-agents yourself. Make sure no background job of yours runs before you report. Commit named paths,
do not push, log DECISIONs in `docs/F2_DECISIONS.md`. Report in 200-300 words with real numbers.
