# Reviewer brief: X02 — declared warm starts (0.4), the single review pass

Status: brief, 2026-11-07. Design `docs/design/X02-warm-starts.md` (architect), ADR 0070 (Proposed, ADR 0019 Am. 15).
Branch `wp/X02`, worktree `.claude/worktrees/x02`, head `005d206f` (WO-1…WO-5; WO-6 close-out not yet done — no full
gate, no manifest). Build log `docs/X02_DECISIONS.md` (D-1…D-29), handoff `docs/X02_HANDOFF.md`, G5 records
`evidence/X02/69c4a24d…/`.

## The question

Does `wp/X02` implement the design correctly and safely for identity (cold runs unchanged, warm runs keyed, recorded and
replayable), and what are the rulings on the batched questions — so WO-6 can close the package and it can merge?

## What was measured (engineers' numbers; re-run what you doubt, within the machine-load rule below)

- WO-1 (Part C, shipped defect): failing-first `tests/test_x02_wo1_part_c.py` 3/5 failed before (bundle lacked
  `warm_start`; reproduce MISMATCH `iterations[0].inner.iterations: 4 against 3`), 5/5 after incl. a control.
- WO-2 contract: `tests/test_x02_wo2_contract.py` 16 passed, four transports; c_4 link digest `0af895a0…`; stripping
  X02's members gives M04's `455d01eb…`; six job-operation snapshots re-taken; Q26 pins.
- WO-3 G3 (stand-in loop): restart 1 outer iteration vs 2, w bitwise equal, 1 cache-hit experiment; user iterate
  VERIFIED ‖Δû‖∞ = 0; rejected opening / compatibility rejection records byte-equal to cold; replay MATCH (a)(b)(c);
  forged `declared` bundle not MATCH. G6 W14 corners: (0, −50) `COUPLING_NOT_CONVERGED`; (0.95, 250) VERIFIED.
- WO-4 G4 (synthetic warm child) a–f pass, outlets within 1e-11 of an independent closed form.
- G0 throughout: F0 PASS M1–M9; 163 recorded experiment keys recompute with 0 differences; batteries 4158/4620 passed
  with one failure each, fixed (D-14 recovery-edges E9 row; D-21 global-state allowlist 35 → 36) — not re-run in full.
- WO-5 G5 (real reactor env `pymrm-6089593-032a050c6cf3`): (a) cold new variant = v3 bitwise 8/8 inlets; (b) warm vs
  cold max rel 1.92e-7 (> 1e-7); (c) warm ~21 % slower overall (287 vs 133 s; 383 vs 420 s) — the note's §3.1 premise
  false; (e) Part A on v3: restart 1 call, 25 s vs cold 4 iterations, 175 s. (d) not run. Variant NOT registered.

## Rule on each (default in brackets)

1. **D-29 / the warm reactor variant:** orchestrator decision: do not register it (Frank's Q1 re-asked with default no).
   Rule: does `child_warm.py` (and the provisional variant file) stay in `src/` unregistered, or leave the package with
   the campaign script and records kept as evidence? [leave the package; WO-4's generic plumbing stays, tested by the
   synthetic child]. Does the design note need an amendment for §3.1 and G5?
2. **D-11:** the note's G3 (c) premise false (every grid point converges on the registered loop); the test uses a
   lowered H₂ make-up and first proves the failure. Acceptable? [yes]
3. **D-13:** a declared iterate can move one ulp through u = w₀/s; a job source round-trips exactly. Acceptable, or must
   a user iterate round-trip exactly? [acceptable, disclosed]
4. **Register numbers:** the c_4 link entry is provisional R-950 (main now holds R-942…R-949 from RP; `wp/MSG` holds
   its own R-942/R-943 and its own c_4, unmerged). Rule the renumbering at merge [whichever merges second renumbers its
   entries and becomes c_5 with the combined tree's digest].
5. **x₀ rejection-reason form:** bare check names (`integrity`, `route`, as ADR 0024) vs the note's
   `warm_start_rejected(...)` for the `coupling` sub-record. [keep both as built, if intended — confirm]
6. **D-14** (a T08 release-spec file, `docs/recovery-edges.yaml` E9, edited), **D-20** (`benchmarks/m02/g12_real_loop.py`
   edited for the `Experiments` protocol's `start`), **D-21**, and any other D-* you find questionable.
7. **ADR 0020 D7 reconciliation** (note D1): D7 requires a W14 path test from the first operation that accepts a state;
   is the registered full-path test sufficient?

## Least sure of

Identity: that no cold path changed (bundles, keys, snapshots beyond those re-taken), and that warm records replay; the
certificate disclosure (D6, D8); the batteries' fixes not re-run in full.

## Deliverable

`docs/reviews/X02-review.md`: verdict, must-fix (M*), should-fix (S*), one ruling per item above, design-note/ADR
amendment text where a ruling needs one, what the review did not establish. Commit on **main** (docs-only, named path,
message `docs: X02 review`, with the session's Co-Authored-By / Claude-Session lines from your prompt). Do not edit
`wp/X02`. Never set `reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2 (the user's): whole machine ≤ ~36 busy cores of 48; check `uptime` first; targeted tests only, one at a time; no
reactor campaign runs. Another engineer (X05) may be running a full gate.

## Out of scope

X05, MSG, ST; RRC; OPT; style.
