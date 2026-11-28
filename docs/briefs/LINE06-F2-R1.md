# LINE06-F2-R1: two design-lane rulings on ADR 0062 D12 (lowering), from F2-WO6a (architect)

Standing rules: `docs/LINE06_RULES.md` (binding). **Do not spawn sub-agents yourself.** Read in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2` (branch wp/F2, head `f9a415f1`); another engineer may be
working there on F2-WO6b at the same time: do not edit code or tests, and commit only `docs/F2_DECISIONS.md` (append a
section "Design-lane rulings R1 (D12)"; `git pull` is not needed, it is a local branch; if the commit conflicts with
the engineer's, commit again on top). Logs under `/home/eajfpeters/.cache/line06/f2r1/`. Write no production code.

D12 (`docs/adr/0062-F2-material-model.md` line ~268) and D13 (~287: "D12's dispatch and lowering criterion" is
frozen core) are at stake; ADR 0062 is still Proposed (its acceptance card comes before F2's merge), so a ruling that
changes D12's text is an edit to the Proposed ADR, made with its reason.

## Question 1 (WO6a-2): what does D12's "one file whose component list equals `component_set` in order" mean?

Facts (`docs/F2_DECISIONS.md` ~line 408): read literally it refuses the corpus revision `SYN-001-T06-STA04`
(components C, A, B: a permutation the v1 binder accepts, T06 §8.6), so E-F2-3's "every corpus v1 revision raises
and lowers" is 58/59 (measured at `fa81bdcf`); it also refuses every CoolProp revision (one fluid of the S07 file's
123). The engineer's reading (commit `6f81897e`, revert restores the literal one): every record is a legacy component
record of one file, under its id there; the lowered `components` are the set's ids in its order. With it, 59/59.
Rule: the exact criterion (text for D12), whether a lowered run of such a revision is byte-identical to the v1 run of
the lowered document (it must be: D8), and the test that proves it.

## Question 2 (WO6a-3): fields D12 neither maps nor lists

Facts (`docs/F2_DECISIONS.md` ~line 415, commit `90f46174`): refused now, not dropped: `semantic_role` with D11's four
new roles (F6), instance `template` and `references` (F6), `phase_assertion` (F5), a non-empty `parameter_sets` (F4).
`materials` dropped whatever it holds (as D12 says). Rule per field: refuse (with which foundation in
`construct_unavailable`), or drop when empty/absent; give the D12 text.

Also confirm or change WO6a-4 (`definition_sha256` classified exact in a new addendum
`benchmarks/f2/numerical_policy_external.yaml`, F3's pattern) in one line.

## Output

The rulings committed in `docs/F2_DECISIONS.md`, with the exact D12 text to apply (the orchestrator applies it to the
ADR). Report in at most 250 words: per question the ruling, the commits to keep or revert, the tests, and whether the
user's ADR 0062 acceptance card needs to mention it.
