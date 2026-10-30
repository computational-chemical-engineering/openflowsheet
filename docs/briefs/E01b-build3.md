# E01b brief 3: finish A49, C5′, C6′, the S12b manifest and QA1b.patch (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/e01b`, branch `wp/E01b` (head `013f8969`). Start from the
handoff at the end of `docs/E01B_DECISIONS.md` (section "E01b, build 2"); the work order is `docs/derivations/E01-design.md`
§10.10.7 (what moves, by how much: any other moved number → stop), and the build-2 brief `docs/briefs/E01b-build2.md` (its
rules apply unchanged). Done: C3′ `cf3adaa1`, C4′ part 1 `c2695ec0`.

**Orchestrator ruling on build 2's question:** removing `CE_RATIO` from `cost_hand.py` and retiring the A44 "CE 394
conversion" check is the registered M4′ move of R-896 (pump/motor at CE 500), not a loosened check. In C6′ the two package
tests follow R-896: `test_a44_the_ce394_ratio_and_the_pump_forms` asserts the CE 500 basis (ratio 1.0 and the forms), and the
motor floor in `test_e01_a_contributor_c1.py` takes the × 0.788 value. Log it as a DECISION line citing this brief.

Remaining, in order: A49 (`seider3.yaml` + `tests/test_e01_b_seider3.py`; factor tables typed from
`/home/frankp/.cache/seider3/ch22_534_595.md` — numbers with page/table only, never text), C5′ (A15 in
`/home/frankp/.cache/idaes-2.13/venv`), C6′ (fixtures, pins, tripwire at 5, A44/A50/A51), then the E01 suite and the
acceptance commands once, `scripts/s11_identity.py`, the S12b manifest (extend `scripts/e01_evidence_manifest.py`), and C7 as
`docs/briefs/QA1b.patch` (not committed; flags: three compressors p. 569 Eqs. 22.36–22.38, turbine p. 593 Table 22.32,
`weight_limit` "2" p. 575 Eq. 22.57).

Report in at most 20 lines: commits, tests with counts, moved numbers vs §10.10.7, A48 count, the C7 flags with pages. Context
cap ~150k: commit, extend the handoff, end. Do not start subagents; no personal identifiers to external services; do not push.
