# ADR 0008 Amendment 2 — transient-readiness re-check at the 0.2.0 cut (design lane, `architect`)

**Requested by Frank, 2026-10-18.** Run at the 0.2.0 cut commit K (after M07 merges into main). No spend, no dynamic code.

## The question
Do the v0.2 additions keep a later transient capability *additive* (ADR 0008 "Additive or refactor"), or did any of
them reintroduce a lock-in point? Per finding: where, the cost of fixing it now vs at the transient package, and a
recommended action (none / test / text / code change with its own ADR).

## Why
R-001 and ADR 0008 Amendment 1 (2026-09-26, ~37 000 lines) were checked before v0.2. Since then v0.2 added external
model execution and records (ADR 0033), external models in a flowsheet solve (ADR 0034), model replacement and
promotion (ADR 0035), surrogate units (ADR 0036/0037), the C1 reactor boundary and PR route (ADR 0026/0027), M03
sensitivities and the NLP adapter (ADR 0031/0032), the trust-region adapter (ADR 0038–0040), the web shell (ADR 0030),
job kinds such as `surrogate_study`.

## Check against
ADR 0008 D1–D4 (P-1 no time at the evaluation boundary; P-2 `state_sha256` = exactly `x`; P-3 per-row `accumulation`
declarations, no central mass-matrix recipe), Amendment 1 (U1/U2 energy holdup is `U`; J1–J3, J5 job outputs; X1–X10,
U–H constraints on the transient ADR) and Frank's answers (Q1, Q-A1…Q-A5). `tests/test_adr_0008_transient_readiness.py`
(44 passed on main `4edcb5a`, 2026-10-18) — does it reach the new model kinds (external, surrogate, stand-in)?
Known point to judge: an external reactor is a steady input→output map with no exposed holdup; say what its dynamic
variant would require and whether anything should be recorded now.

## Deliverable
ADR 0008 "Amendment 2" (dated section), a register update to R-001, and work orders for any test or text change
(build lane, one branch). ≤ 200-word report.
