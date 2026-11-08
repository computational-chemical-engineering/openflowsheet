# Architect consult brief: OPT — three design premises failed in WO-4b/WO-5

Status: brief, 2026-11-07. Design `docs/design/OPT-revision-optimisation.md` and ADR 0071 (Proposed), both on main
(`e4316d9c`). Build on `wp/OPT` (worktree `.claude/worktrees/opt`, head `826cc4c4`): WO-1…WO-5 done; log
`docs/OPT_DECISIONS.md` D-1…D-38 (read D-12, D-37, D-38 and the C-MW measurements; the gate numbers are there).
This is a mid-build consult because measured facts contradict the note; it is not the review (the reviewer comes after
WO-7 and rules the other pending D-items: D-18, D-24, D-28, D-30, D-32).

## The question

Given the three measured premise failures below, what does the note prescribe instead — so WO-6/WO-7 and the review
have a design that holds — and which gates change?

## Measured facts

1. **D-37 — phase-boundary optima are not certifiable as designed (G10).** OPT-A3 (OPT-A1's heater, maximise T_out, Q
   box past the bubble point): Ipopt reaches the bubble point (|T − T_b| = 9.1e-10 K, Q = 14232.354594159335 vs mpmath
   Q* = 14232.35459443206). V1's cold re-solve (D6: production route, cold) is `CERTIFICATE_NOT_VERIFIED`: K04's
   regularity check on the full target system (equilibrium rows included) is `ILL_CONDITIONED` because the V = 0 branch
   and the two-phase branch meet at T_b; rcond ≈ 2.27e-6·ΔQ (ΔQ = 1 W → 2.27e-6 VERIFIED; 0.1 W VERIFIED; 0.01 W
   ILL_CONDITIONED; 0 → RANK_DEFICIENT; −1e-3 W (two-phase) ILL_CONDITIONED). A lifted split's phase row is "active"
   (|a/N0| ≤ 1e-6) only within ~1e-2 W of Q*, where the certificate already fails, so §4.7's V4 exemption and Q4 held
   mode are unreachable for lifted splits. Thermal port rows have no such bifurcation (not exercised active).
   Engineer's options: (a) at a candidate with an active split row, V1 judges regularity on the held-regime system
   (the converged attempt's Newton system, which is regular) — a K04/V1 policy change; (b) G10 expects `NOT_VERIFIED`
   with a typed boundary reason; (c) certify a point stepped back into the interior (moves T ≥ 3e-5 K; breaks G10's
   1e-6 K). Current: numerics unchanged, G10-as-designed `xfail(strict=True)`. Related: Frank's OPT Q7 ("include
   phase-boundary optima in 0.4? default yes").
2. **§4.2.3 zero-at-start flows.** "A flow exactly zero at the start → unbounded, reason
   `zero_at_start_pinned_by_regime`". On C-MW (297 columns, methanol–water column; feed carries exactly zero ethanol)
   those flows are free columns, not pinned by any regime; Ipopt drives them negative and the twin raises `DomainError`
   on ~99 % of residual calls; start 0 fails in restoration.
3. **TWO_PHASE stages and D-12.** §4.7 says TWO_PHASE is "held by V, L ≥ 0" with no row, but V4 and Q4′ still judge a
   margin for every split, and C-MW's 19 two-phase stages have `null` margins → V4 fails (19 inside τ_regime) and V5
   `REGIME_MARGIN_UNSUPPORTED` ×19. Start 1 passes V1, V2, V3, V6 — the null margins are its only failing cause. D-12
   (WO-2): on `pr-c1-v1` and composition-dependent K, the closure admits single-phase branches by `classify` / the
   incipient-phase ΣW, not `tp_margin`; the build refuses those splits (`REGIME_MARGIN_UNSUPPORTED`); alternative is
   `tp_margin` everywhere as §4.2.4 reads literally (revert `8f7f34b5`).
4. **Minor:** WO-5's phase rows add an inequality for every LIQUID-held split, so OPT-A1/A2/C0 are no longer
   byte-identical to their WO-4b reports (A1's Q bitwise equal; A2 r error 4.6e-11, Q 1.9e-10 rel; C0 Q 1.0e-11 rel —
   all inside their gate tolerances). Confirm the gates are tolerance gates, not byte gates, after WO-5.

## Constraints (unchanged)

ADR 0032 D1–D6 and R-188 (truth is the re-solved certified simulation, never Ipopt's status), R-189 (true domain
bounds, no penalties); no relaxed checks: a change to what K04/V1 accept must be a stated, justified policy with its own
test, not a loosened tolerance; F0 identity (M1–M9) and SYN-001 identity (G2) stay; certificates of ordinary `solve`
runs must not change. Distinguish numerical verification from optimality evidence.

## Deliverable

An amendment section in the design note (A-1…, with the replaced text quoted), the matching ADR 0071 edits (status
stays Proposed), the changed gates (G10 and any other), and any plain-words change to Frank's OPT Q7. Commit on
**main** (docs-only, named paths, message `docs: OPT design amendment (D-37, zero flows, two-phase margins)`, with the
session's Co-Authored-By / Claude-Session lines). Report ≤ 30 lines: each ruling in one line, gates changed, work
orders affected.

## Machine-load rule

TRS2: `uptime` first; at most single small probes with `OMP_NUM_THREADS=1`; no full gate (one is running).

## Out of scope

D-18, D-24, D-28, D-30, D-32 (the reviewer's); WO-6/WO-7 surface work; X12; X24; style.
