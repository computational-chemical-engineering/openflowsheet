# S08b review (design lane, `reviewer`, 2026-10-26)

Range `a13203b8..d34f8b57` on `wp/S08b`, against `docs/derivations/S08b-design.md` (R-790 to R-794) and
`docs/S08b_BUILD_DECISIONS.md`. The production diff (4 files under `src/`), the S08b tests, the G1 gate and its recorder, the
S01 Amendment 2 text and the build decisions were read. Two scratch worktrees (base `a13203b8`, head `d34f8b57`, detached under
the session scratchpad, removed afterwards) were used for three probes, described under F1 and F2.

## Verdict

**Sound; merge once the gate and CI are green.** Nothing is must-fix. (a) replaces the `"."` heuristic with the declared-item
rule exactly as §5.1 specifies, and nothing else moves. (b) moves item 6's body verbatim, applies it at the right point, and
adds no rule to `_admissible` or to the flash units. One should-fix: the fact recorded for B1 is wrong. The solver is
deterministic. What varies is a pre-existing contaminated test memo, which also weakens B2 and S01's A18 in some shard orders.
One should-fix test gap and three notes follow.

## Findings, most severe first

### F1 — should fix: the B1 "cache warming" fact is a misdiagnosis; the cause is a contaminated S01 test memo (pre-existing)

*What was measured.* The build log (WO-3) and B1's docstring (`tests/test_s08b_saturation.py:63-65`) say that "a solve's last
bits depend on which caches earlier tests warmed". The solver does not do that. In one process, at base and at head,
`solve_cascade(C2)`, then C1/C3/C4/C5, then C2 and C3 again, gives repeats that are bit-identical (0 of 52 and 0 of 85 state
entries differ). After `test_s01_cascade_wo2.py` + `wo3.py`, the memo `solved("C2")` also equals a fresh solve bit for bit.
When `test_s01_cascade_wo3.py` runs **alone**, at base and at head alike, `solved("C2")` differs from a fresh solve in 36 of 52
entries.

*Cause.* `solved()` (`tests/test_s01_cascade_wo2.py:62-71`, "one solve per registered case per session (the solve is
deterministic, A20)") is first called for C2 by `test_a17_forced_edge_3_from_the_presolve_root`, through `compare_with_a06`
(`wo3.py:57`, called at `:199`). That call happens while `_forced_edge_3` has monkeypatched `eo_recovery_due` to `True`
(`wo3.py:125`). So whenever no earlier test in the process has filled the memo, it holds C2's **forced edge-3 recovery root**,
not A06's root. That root accounts for the 2.0096e-06 K against 7.36e-09 K.

*Consequences.*
- B1's spy form is a sound wiring test, but its stated reason is false.
- In such a shard, B2 (`_cascade_pairs` → `solved`) measures the edge-3 root of C2, not "C2 as registered". It still passes,
  at 2.0e-6 K ≤ 1e-5 K.
- S01's A18 tests (`wo3.py:245, 266`, "is the A06 root") then compare against the edge-3 root. They still pass (`SAME`), but
  against the wrong reference.

Nothing in S08b's production code is affected, and G1 family A builds its own solves.

*Minimal correction.*
- Now, which moves no decision: replace B1's docstring sentence with the exact text below, and append a dated correction to the
  WO-3 entry of the build log.

  > "The expected values are the pairs of the raising solve itself (a spy on `saturation_pairs`): the session memo
  > `solved("C2")` is not always A06's root — `test_s01_cascade_wo3.py::test_a17_…` fills it under a forced edge-3 recovery when
  > it runs first in a process (S08b review F1)."

- After S08b merges, as a separate commit on main: in `_forced_edge_3`, call `solved("C2")` before the two
  `monkeypatch.setattr` lines. Do not do this inside S08b. It changes `test_a17`'s recorded decisions in the shards where it
  applies, so it would trip G1 family B against `B`.

### F2 — should fix: no test pins the `items` argument at `_proposal`'s two `choose` calls

Every call site is right. `adjacent` is called only from `choose`, and `choose` only from `_proposal`
(`phase_contract.py:437, 450`), with `items = frozenset(declared)`. The recorder sees every in-process `decide` (it rebinds
`attempts.decide` and `region.decide`), and a different chosen candidate would show in the conversion's opening hash and trial
α. But A1–A4 call `adjacent` and `choose` directly, and A7 calls `_units_and_items_disjoint` directly.

*Measured.* I changed `_proposal`'s line to `items = frozenset()` in a scratch copy of the head and ran 50 modules: every
`test_t05b_*`, `test_t03_*`, `test_t04_*`, `test_k03_*` and `test_s08_*` module, plus `test_s08b_contract` and
`test_s02_column_wo3`. All 1 084 tests passed, so nothing catches an `items` argument dropped at either call.

*Minimal correction:* one `_proposal`-level test, through a stub `ops` with `declared_phases = {"U-PUMP.outlet": "LIQUID"}`
and two wall candidates. The first is not adjacent. The second is adjacent only if the pump entry counts as an item. Assert
that the second is the conversion's candidate. Also add one assertion that `_LiftedOps.__init__` raises on a clash, or accept
A7 as function-level (the design says no registered region reaches it).

### F3 — note: family B's blind spots (none bites this change)

- `decide` calls made in child processes (CLI, job or journey tests that spawn Python) are not recorded.
- The 3 137 locally skipped CoolProp tests are not witnessed. CoolProp is refused by columns and cascades (S11), so no stage
  id arises there.
- Base-only keys under a test id the branch also has are reported, not failed. R-794's "Watch for" names this, and the
  measured `b_only=0/20` is all `test_s08b_saturation.py`.

A later gate on this pattern should FAIL a base-only key whose test node exists in both trees.

### F4 — note: the manifest is `tested` with `S08b.gate` and `S08b.ci` `unsupported`

This conflicts with §8 WO-4's "`tested` only if every A/B item and G1–G3 pass", but it follows S08's precedent
(`evidence/S08/6d7d1a6…`). The orchestrator must read the gate line and CI 40359016227 before the merge is pushed.

### F5 — note: `phase_wall(stall, )` survives on the tear path in one synthetic test

The 3 unchanged tear-path decisions (`test_k03_attempts.py::test_the_attempt_budget_is_a_typed_outcome`) keep an empty list.
Their signatures differ only in unit id (`U-1` against `U-3`, both `LIQUID`), and `_changes` lists regime changes only. The
construction is not physical and this is pre-existing, not S08b's.

## Rulings on the build decisions

- **WO3-1 — accepted.** Every asserted value is unchanged. Only the lookup site of a stub moved, which the move of §5.2
  implies. Design-note erratum, to add after §7 B3:

  > "*Erratum (2026-10-26, design lane `reviewer`, S08b review):* 'S08's item-6 tests pass untouched' holds for every asserted
  > value; one stub target moves — `tests/test_s08_item6.py::test_a_band_answer_other_than_inside_is_a_failure` patches
  > `band_temperature` in `cascade_solve`, where §5.2's moved body resolves it (build decision WO3-1)."

- **WO4-1 — accepted** (`requirements: [D09]`; X31 in a limitation; S08's W5-7 precedent). Erratum, to add after §10 Q5:

  > "*Erratum (2026-10-26, reviewer):* the frozen manifest schema admits only `^[DA][0-9]{2}$`; the manifest carries
  > `requirements: [D09]` and names X31 in a limitation; `depends_on` is not a manifest field (build decision WO4-1)."

- **WO4-2 — accepted.** "No flash behaviour changed" means branch = base. The base scan is the right reference once S10-C has
  added its 46 kernel-agreeing splits. The near-trivial buckets are still held to `measured.txt`.
- **WO4-3 — accepted.** The probe sees only uncached solves, so both trees must share the dealing, for G1's reason. The same
  dealing reproduces `measured.txt`'s S01 rows, including the A17 memo effect of F1.

  One erratum covers both WO4-2 and WO4-3, to add after §9 G3:

  > "*Erratum (2026-10-26, reviewer):* `measured.txt` predates S10-C; on any later tree S10-C's tests add 46 kernel-agreeing
  > flash-type splits to the `[0.001, 2)` bucket. 'Flash-type rows identical to `measured.txt`' reads: identical to the same scan
  > of the merge base `B`, both trees dealt as G1 deals them (`s08b_identity.shards`); the three near-trivial buckets also equal
  > `measured.txt`'s (build decisions WO4-2, WO4-3)."

- **G1 decisions 1–5 — accepted.**
  1. Requiring shards to exit 0 is stricter than §9.
  2. A SHA-256 over the structural fields gives the same verdict as verbatim fields.
  3. `b_moved` counts decisions, as §9's line implies.
  4. The copied recorder is the only way the base tree imports nothing from the branch, and the plugin checks the tree.
  5. `collections.abc.Set` is the non-deprecated spelling.
- **Item 4 (B1 judged against the raising solve's own values) — sound as a wiring test.** It hides nothing in S08b's code.
  The fact it rests on is corrected by F1.

## Checked and found sound

- `_split`, `adjacent`, `_changes` and `choose` match §5.1. `items` is keyword-only and required. The tear path keeps no
  `declared_phases`.
- On the lifted path, a signature's items are always among `declared_phases` keys, both built from `_dormancy`
  (`region.py:1281-1291`), and `_units_and_items_disjoint` makes the rule unambiguous.
- `saturation_pairs` is the column body verbatim. The id helpers resolve to the same `cascade` module, and column item 6
  delegates, so B3 is an identity.
- The S01 clause runs only on `CONVERGED`, on the final signature's regimes, after the per-stage loop
  (`cascade_solve.py:526-534`, `:756-760`). Column acceptance does not call it, so a column reports item 6 once.
  `solve_cascade` has no production caller.
- No change to `_admissible`, `_branch_found`, `PHFlash`, `c1.tp_flash` or `tp_state`.
- Amendment 2 is verbatim, and the A5 and A6 edits keep every value.

## Not examined

Family A's text walker and the manifest generator beyond the gate checks; the T08 harvest; CoolProp and aarch64 behaviour
(CI); `docs/derivations/scripts/s08b_design/*` beyond `_is_item` handling.

No register change is needed. The errata above go into the design note as dated notes.
