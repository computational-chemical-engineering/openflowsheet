# S10-C brief: the package's single `reviewer` pass (WO-1 to WO-4)

Branch `wp/S10C`, worktree `.claude/worktrees/s10c`, head `bd4f4fc7` (main with S09 merged in). Range
`ffcb387f..HEAD`, excluding the merge of main.

## 1. What it was built against

`docs/derivations/S10C-design.md` (architect, `b348e9b4`) and ADR 0049 (Proposed; amends ADR 0011 D1 and ADR 0012
D1–D2 for the γ–φ provider type only; replaces S11 in the column with an identity allow-list), R-760…R-769;
`docs/derivations/S10C-spec.md` (WO-S, normative where it differs from the note: F-1 derivative stencils, F-2 column
tolerances + A42), R-770…R-776; `benchmarks/s10c/reference_values.yaml` (50-digit, 118 claims). Build log
`docs/S10C_DECISIONS.md` (inventory table; W1-*, W2-*, W3-*, W4-* decisions; findings F-W3-1, F-W3-2, F-W4-1, F-W4-2).

## 2. Work orders and results

| WO | Content | Key numbers |
| --- | --- | --- |
| WO-1 | `equilibrium_form.py`, `gamma_phi.py` (`ln_k`, mixture enthalpy, `band_point`/Tsolve, `incipient_liquid`), dispatch in `saturation_band`/`tp_state`, `scripts/s10c_identity.py` (G1) | 139 tests; W1-3 reordered Tsolve's Newton/adjacent-double rule (the note's order could never fire): max evaluations 1205 → 234, same roots |
| WO-2 | band-first PH path in `ph_kernel.py`; `region._admissible` Wilson branch | G4 17 targets worst \|ΔT\| 5.1e-13 K; G5 13 E-2 states all `ok` on the band route, worst 5.7e-14 K; M3 detected (old route 13/13 `ph_not_converged`) |
| WO-3 | `gamma_phi_blocks.py` (K over stage liquid flows, T, P; mixture H); `declared_rows` dispatch; `validate` (admission, provider T/P domain, refused kinds, `energy_precheck`); S03 A04 amended | G6 FD 3.8e-8 vs 1e-6, closed forms 3.1e-15; M1 caught (0.499), M5 caught; G8 all pass |
| WO-4 | §4.9: `_k_values(liquid=)`, profile at z, sweeps relaxed ω = 1/2 (SYN-001 takes neither) | C-MW/C-EW CONVERGED Stage A, worst 5.7e-5 / 2.1e-8 of tolerance, Newton 9/4 iterations, order 2.19/2.03; A42 1.7e-7 τ; M2, M4 detected; A35 under M1: HOMOTOPY_STALLED; G9 C-MW 0.58 s; SYN-001 S02/S08 +6.6 % median / +8.6 % mean wall vs `ffcb387f` (limit +10 %) |

Throughout: G1 `S10C-IDENTITY PASS n=858 changed=[]` (52 column/cascade configurations, 803 `ph_state` calls); G2
frozen paths untouched; battery 2612 passed; ruff/format/mypy clean. Not yet: WO-5 (registrations, manifest,
harvest), the full gate, CI.

## 3. Rulings wanted, batched

1. Build decisions W1-1…W1-7, W2-1…W2-7, W3-1…W3-4, W4-1…W4-8; especially **W1-3** (Tsolve step order, a premise gap
   in the note).
2. **F-W3-1:** the note's claim that the dormant probe "moves nothing whatever the block returns" over-claims — the
   equilibrium row's ∂/∂l_i = −K_i·V reads the probe's K; in a two-phase solve an exactly zero liquid (a Stage-B start)
   would have its Newton step set by the probe, no converged value changes. Erratum text?
3. **F-W3-2:** spec text puts the vapour H block at (v_j, T_j); the YAML evaluates at the listed n; the build followed
   the YAML. Erratum?
4. **F-W4-2:** each equilibrium-form check costs a `describe()` call (~45 µs, ~9 % of SYN-001 solve time; 692 of 1751
   calls from `_k_values`); SYN-001 suites +6.6 % median against a +10 % limit. Acceptable, or must the form be
   resolved once per solve before merge?
5. **F-W4-1:** an absent component's flows end at 1.3e-18 mol/s rather than exactly 0.0; A41 checks them against the
   stage tolerance (OQ-2). Acceptable?

## 4. General review

- Residual and Jacobian: does the K-block's Jacobian describe the same function as the residual at every state,
  including dormant liquids and the total condenser reading v_2?
- The PH band-first route's correctness argument (T1–T5 in the spec): does the implementation realise the theorem's
  preconditions, and is any route chosen that the theorem does not cover?
- Is SYN-001 truly untouched (G1's coverage: what could change that G1 does not see)? Is the identity allow-list
  airtight (every other provider still gets S11's code)?
- Do the tests verify what they claim (expectations from the YAML or closed forms, never the code)? Do the mutations
  hit the intended paths?
- The ω = 1/2 relaxation: does it change any SYN-001 path (it must not), and is its stop rule sound?

## 5. Not worth your time

Formatting; re-deriving the 50-digit references; the design's measurement scripts.

## 6. Deliverable

`docs/reviews/S10C-review.md`, findings by severity, a ruling on each §3 item with exact text where anything changes;
errata as a dated amendment in `docs/derivations/S10C-spec.md` (or the design note) with register entries after R-776.
A docs-only commit on wp/S10C (include this brief). Do not push; do not set `reviewed`. Report in at most 25 lines.
