# Design-lane ruling round: M05 (after WO-4/5) and M04 (W27 row)

One batched round (CLAUDE.md "Agent budget"). Decide each item; write rulings, not code. Each answer must say what
changes in the design text, which acceptance criteria change (with new numbers), and which work order implements it.

## Part A — M05 (`wp/M05` @ `6b54b8d`, worktree `.claude/worktrees/m05`)

Design note: `docs/design/M05-trust-region.md` (§6.1 projection l.199, §6.5 FD policy l.323–341, §16 rulings l.889,
work orders l.806, gates l.822–829). Build log: `docs/design/M05-build-decisions.md`. Write the rulings as **§17** of
the design note and new register entries (next free after R-295; check `docs/decision-register.md` on `wp/M05`).

**A1. Exact-zero flows at x₀ (STOP; blocks every C1 TRF run).** TRF on C1 TR-E2 ends before iteration 1 with
`TRF_TRUTH_REFUSED(property_domain_error:S1_Hdot_V)`; the PMP point has `S1.n.NH3 = -3.448e-27`. ADR 0032 D4 (M03):
"molar flows a lower bound of 0 except a flow that is exactly zero at the verified start (pinned there by its regime's
own rows; a bound would be degenerate and break LICQ), which V2 and V4 then police." In the M05 projection those flows
are *not* pinned by rows (the zero-ΔP alias rows were omitted per R-274), so Ipopt moves them by roundoff and
`pr-c1-v1` refuses n < 0. Exact-zero flows at x₀: `S1.n.NH3`, `S6.n.{H2,N2,Ar,CH4}`. Engineer proposes: bound them
≥ 0, or fix them at 0. Decide (bound / fix / restore a pinning row / other), whether it amends ADR 0032 D4 or is an
M05 projection rule, and the effect on LICQ and on G4's 73×73 matching.

**A2. FD policy `M05-fd-v1` (§6.5 and design-note table D8 at l.83: forward differences, h_j = η·max(|w_j|, f_j), η = 2⁻¹⁴, f_T = 1 K;
gradient check ‖G(η) − G(η/4)‖_∞ ≤ 1e-3·max(1, ‖G(η)‖_∞), η ← 4η at most twice, then `fd_unstable`).** Measured on the
synthetic truth (`tests/support/m05_synthetic.py`, §5.2, curvature on a 20 K half-width):
- WO-4 acceptance "analytic vs FD ≤ 1e-6 relative at η": worst 4.1e-2 on dX/dT (T step 0.041 K); others ≤ 1e-4.
- Gradient check: ‖ΔG‖ = 0.0373 vs allowance 2.27e-3; η = 2⁻¹² gives 0.149, 2⁻¹⁰ 0.598 → `fd_unstable`. The error is
  truncation, not noise, so the escalation direction (larger η) is wrong for it.
- G6 ("gradient check passes at η = 2⁻¹⁴") will therefore fail as registered.
Options seen: central differences (2× cost; D8 rejected them for cost), coordinate-range-scaled steps, smaller η,
escalating η in both directions, a curvature-aware check. Decide the policy, the check, and the new WO-4 / G6
criteria. Keep in mind the real reactor costs 25–45 s per cold evaluation and has its own noise floor (G11, WO-9).

**A3. §16.4 basis acceptance "TR-E1 with an affine basis converges to native within 1e-6".** Measured |Δz| =
1.18e-6 / 1.11e-6 / 5.7e-7 at TRF's step-size termination; objective agrees within 4e-11 relative. Decide: keep
(tighten TRF termination for this test), or restate the criterion.

**A4. (pending since WO-3a)** An Ipopt "Optimal" exit with θ_recheck > 1e-5: engineer chose `TRF_ERROR(exit_mismatch)`;
alternative `TRF_STALLED_INCONSISTENT`. Matters for the retry policy. Decide.

Engineer decisions to confirm or reverse (each an isolated commit on `wp/M05`): parent-truth meta carries a sixth key
`code`; (X, ΔT) read from the envelope (ξ/n_N₂, T_out − T_in) until M02 has a coupling-coordinate function; ledger
records explicit FD purposes on memo hits; non-parent holders refuse parent budgets (`ValueError`); `project()` gained an
additive `variable_bounds` argument (T_in/P_in hard-domain bounds); concurrency test uses no artifact sink because ids
depend on completion order. New accessor `application/revision_binding.py::with_coupling(binding, unit_id, X, dT)`
(proved inert vs M02's `at_coupling`) must also land on `wp/M02` — say whether that needs review.

## Part B — M04 (`wp/M04` @ `2841cd3`, worktree `.claude/worktrees/m04`)

**B1.** Registering `c1.reactor_surrogate` (`studies/surrogate/reactor.py`) in `MODEL_BUILDERS`/`MODEL_BASES` makes
the W27 classifier refuse: `RefusalError: unregistered model ids ['c1.reactor_surrogate']` (W27-R24(a)); 4 tests in
`test_m06_w27_coverage` fail; `list_models` would change to `f070fbe0…` with 22 models (route pr-c1-v1 has 9). W27
registration (on `main`): `docs/derivations/M06-W27-registration.md` §21 (Amendment 2; the C1 rows table at l.1020,
`c1.reactor` → `fixed_design_reactor` l.1040, GC-MODEL-1/2 l.1194) and
`docs/derivations/scripts/m06_w27_registration.py` (l.431 the C1 id list). Decide the surrogate's `model_functions`
row and none-reason (or function), whether the v0.2 snapshot / J3 must be re-pinned, and the new assertion rows. Write
it as a short Amendment 3 section in the registration (on `main`, a separate commit) and its register entries.
Also say whether the C1 corpus tests (which need a bound instance of every builder) get a resolver or an exclusion.

## Rules

- Do not reopen ADR 0038–0040 beyond these items. Do not edit production code or tests.
- Commit Part A on `wp/M05` (worktree m05), Part B on `main` (repo root; `git pull` not needed, nothing pushes there
  while you run). Stage named paths only. No gate run needed for doc-only commits.
- Report ≤ 300 words: per item the ruling in one line, the commit, and the work order that implements it.
