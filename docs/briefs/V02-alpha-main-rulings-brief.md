# Rulings brief: the released 0.2.0a1 alpha on main — design lane (`specifier`), one pass

## The question
Main must take the released alpha's work (M07 WO-3, the 0.2.0 gate, builds on it). After the merge, five alpha tests and
five M05 replay records fail on main. Decide, per item below, what each check must verify on main from now on, without
weakening anything the 0.2.0a1 release claimed, and write the rulings so a build-lane engineer can apply them.

## Where
Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-main`, branch `wp/V02-alpha-main` @ `d73004a`
(pushed): `989b16f` (pre-merge renumber), `06fb0f2` (merge of `wp/V02-alpha-gate` @ `423ae9c` into main @ `f2b9486`'s
ancestor), `d73004a` (W27 coverage re-take at the merge build). Released: tag `v0.2.0a1` → `423ae9c` (2026-10-17; PyPI,
GitHub pre-release). The alpha's candidate C_α² = `cc73219a77f6a54579c8acb151ed6fae228c8a4c`; spec
`docs/derivations/V02-alpha-release-spec.md` (§9.2 release procedure, §19); ADR 0028 (Accepted, R-451); verdicts
`docs/reviews/V02-alpha-verdicts.md`. M07 spec `docs/derivations/M07-spec.md` is on `wp/M07` (not merged): it defines the
0.2.0 gate (WO-3: per-set clause, `v0.2-gate-v1`, carry checks, tests "in the pattern of `tests/test_m07a_v0_2_gate.py`").

## Measured on `d73004a`
Gate: 5 failed, 9591 passed, 31 skipped; CI 39050289989 fails on both runners with the same five:
1. `test_the_unclaimed_gates_are_untouched` (`tests/test_m07a_ledger.py`): the ledger's W24 row differs from the pinned
   value — main's M03/M05 merges changed W24's evidence (`evidence/M03/fd16834…`, owner packages incl. M05).
2–4. `test_m07a_a37_the_chain_holds_on_the_served_list`, `…_control_ii_s_m_strips_one_member_too_many`,
   `…_control_iv_elements_left_in_place`: A37 (V17 carry chain from `v17-c2`'s agent surface to the served MCP list)
   breaks at `c_2 (R-234)`: expected digest `383b4e2c…`, found `455d01eb…` — main's served MCP tool list has moved (M03/
   M05 tools added after C_α²). **This matters for 0.2.0:** 0.2.0's defaults say "re-accept the agent-evidence carry for
   0.2.0" and "if the agent-facing surface changes after the paid W27 run, stop and ask".
5. `test_c_the_gate_table_is_what_the_gate_script_prints` (`tests/test_m07a_changelog.py`): runs `v0_2_gate.py --rc
   cc73219…`, which at main prints NO (D2.4 tree check: 137 paths differ from C_α² — expected on main).
6. nlp tier: the five M05 G10 in-process replays (`tests/test_m05_g10_replay.py`) fail with 551 differences, all
   version-derived hashes (main's version moves 0.1.1 → 0.2.0a1 with the merge), no numeric difference. Precedent S77
   (`56fb2fa`, M05 build log): records re-taken digest-only after a fingerprint change, proved by
   `scripts/m05_retake_diff.py` (all non-digest fields equal, one-to-one digest map). Every future main change to a
   fingerprinted file or the version (e.g. 0.2.0 itself) breaks them again.
7. Envelope id collision: both sides registered `L43`. The merge kept the alpha's L43 (R-321, cited by the released
   CHANGELOG) and renumbered main's M04 row (R-365, no promotable surrogate) to `L49` (`989b16f`); R-365's text still says
   L43.
8. Main's version after the merge: `0.2.0a1` (the alpha's); main had `0.1.1`. Main's head is no longer what was released
   as 0.2.0a1.

## Precedent
R-217 (2026-10-08): T08 tests pinned facts of the v0.1.0 release; v0.2 manifests broke them; they were scoped to the
v0.1 packages' records, the universal half (harvest completeness) stayed universal; rejected: rewriting a release record.

## Already decided, not open
0.2.0a1 is released from `423ae9c`; nothing in its record (CHANGELOG `## v0.2.0a1`, ledger at C_α², verdicts, M07a
manifest) is rewritten. No tolerance, band or classification moves. A failed check is never relaxed to pass; a check
whose subject is a past release keeps verifying that release's committed record.

## Open — rule on each
A. Items 1–5: what each test verifies on main (scope to the 0.2.0a1 record, as R-217; which parts become 0.2.0-gate
   obligations for M07 WO-3 instead). For 2–4 say explicitly what the 0.2.0 gate must do about the moved agent surface
   (and whether that is a Frank question: a new agent campaign costs ≈ USD 10; W27 is the approved paid run, 45 runs).
B. Item 6: re-take now (S77 procedure) vs change what the G10 in-process fingerprint covers (version, unrelated files);
   say which and, if re-take, when (now and again at the 0.2.0 RC?).
C. Item 7: confirm L49 and R-365's wording.
D. Item 8: main's version between releases (keep `0.2.0a1`; or a PEP 440 dev/next pre-release such as `0.2.0a2.dev0` /
   `0.2.0.dev0` — check what `release.yml`'s gate and T08 tests accept for a non-release head).

## Deliverable
Register entries (next free numbers above R-455 unused on main, `wp/M07`, `wp/V02-alpha-main`), one per ruling, with the
rejected alternative; a short `docs/design/V02-alpha-main-rulings.md` with, per item, the exact change for the engineer
(file, test, what it asserts afterwards). Commit, push `wp/V02-alpha-main`. No code changes. Report ≤ 300 words, with
anything that needs Frank in plain words.

## Out of scope
Building WO-3; the paid W27 run; M05/M07 internals beyond the G10 fingerprint question.
