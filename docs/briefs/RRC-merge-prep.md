# Build brief: RRC — merge preparation after Frank's acceptance of ADR 0072 (0.4)

Status: brief, 2026-11-09. Start **after OPT is merged into main** (merge order MSG → X02 → OPT → **RRC** → ST).
**Do not spawn sub-agents yourself.** Stay under ~150k context: if you approach it, commit what is complete, write
where you stopped in `docs/RRC_HANDOFF.md`, push and end.

Frank (decision board, 2026-11-08; `docs/FRANK_QUESTIONS.md` "Answers — Frank, 2026-11-08"): **ADR 0072 accepted**;
FQ1 **yes** (the three additive schema widenings); FQ2, FQ3, FQ4 **default** (read each default in
`docs/FRANK_QUESTIONS.md` / ADR 0072 and apply it as written). The `reviewer` pass is done (`docs/reviews/RRC-review.md`)
and its fix round is in (WO-7). Frank's merge rule (2026-11-08, CLAUDE.md "Gate by risk") replaces the ADR's
"`scripts/gate.sh` on the merge candidate": CI green on both architectures is the merge condition, no local full gate.

Branch `wp/RRC`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rrc`, head `fe572ad5` (~184 commits
behind main). Read `docs/RRC_HANDOFF.md` ("Next") and `docs/RRC_DECISIONS.md` (D-1…D-38) first. Worktrees have no
`.venv`: run `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`, and confirm
`openflowsheet.__file__` is the worktree's copy before trusting any result.

## Do, in order (one commit each, messages `RRC: …`; log each in `docs/RRC_DECISIONS.md` as D-39, D-40, …)

1. `git merge main` (no squash, no rebase). Main now has WIT, MSG (c_4), X02 (c_5), OPT (c_6), X05a, X10b, S15a.
   Resolve as earlier merges did: `HARVEST_SIZE` recomputed, `support_envelope.yaml` combined,
   `t08_support_matrix.py --emit` then `--check`, generated files regenerated, register entries from both sides, CLI and
   binding parameters keep every side's. RRC and OPT both touch the revision-solve path (`revision_run.py`, recovery
   edges, `final_system`): keep both behaviours; if the two cannot both hold, stop and report.
2. **Surface chain:** does RRC add response-schema members (FQ1's widenings)? If it changes the frozen surface, RRC
   becomes link **c_7** after OPT's c_6 in the established form (strip RRC's members over main's chain, measure D_7,
   `m07a_rc.LINKS`, chain test, texts); stripping RRC must give main's D_6 exactly, never re-record D_4…D_6. If RRC's
   widenings are request-side only and the chain does not move, say so with the test that proves it. ST, which merges
   after RRC, will then take the next link.
3. **Global-state cache count** (`tests/test_t07_global_state.py`): main's after OPT, plus RRC's if it adds one.
4. **ADR 0072 → Accepted, 2026-11-08 (Frank)**: status line; register drafts R-RRC-1…6 → **R-990…R-995** in ADR order
   (RRC's block; ST holds R-1000…), entered in `docs/decision-register.md` in X02's R-951 form; replace every
   `R-RRC-n` (including `tests/test_t08_b50_surface_content.py` `V02_ADDITIONS["solve_policies"]`). Align D5's bullet
   "`opening_state_sha256` equal to the source root's" with design §5.8 (amended) — "over the free columns" — as the
   handoff asks (one sentence, cite S1). Apply FQ2–FQ4 defaults' text where the ADR leaves them open.
5. **MSG catalogue G2** (as X02 D-39 / OPT D-92): `msg_catalogue.py scan` on the merged tree; complete entries where
   the prose exists in the design note, else stubs in MSG WO-2's form, all `review: true`; labels allow-listed with
   reasons; `sync-limitations`; `msg_catalogue.py check` PASS; regenerate fixtures/doc pages it names.
6. **ADR 0025 D2.3**: any new sha256 name RRC records must be classified (exact/float) through RRC's `ADDENDA` entry in
   `scripts/t08_numerical_policy.py`, as ST did (ST review ruling 6).
7. **CI coverage of G7/G8** (handoff "For `tested`"): confirm which CI job runs G8 on N1 **and** C3 on both legs and
   G7 on aarch64. If CI does not run them, add them to the CI test selection as the design's §8 states them (no
   relaxed case), or stop and report if that needs a workflow decision.
8. Tests: `tests/test_rrc_*.py`, OPT's `final_system`/`test_opt*` (default env), `tests/test_t08_w2_recovery_edges.py`,
   surface chain / R4-G3 / global state / descriptions, `test_msg_*`, `test_m07a_harvest.py tests/test_t08*.py
   tests/test_evidence_manifests.py` (`OMP_NUM_THREADS=1`, serial — the venv has no xdist); `ruff check`,
   `ruff format --check`, mypy as `scripts/check.sh` runs it; F0 `scripts/corpus_identity.py --check` PASS.
   Update the handoff's gate section. Push `wp/RRC`. **No merge into main, no manifest** (the orchestrator re-takes it
   after CI).

Stop and report rather than choose on anything that would change numerics, a digest already on main, or a frozen
interface beyond FQ1's three widenings. Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. TRS2 shared: `uptime`
first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`.

## Report (≤ 20 lines)

Commits; conflicts and how resolved; chain link and digest (or why none); cache count; register numbers; catalogue
counts; G7/G8 CI coverage; test counts; F0 line; anything stopped on.
