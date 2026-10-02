# Brief — T06 F4: recovery for a revision-built EO region that ends `BOUND_BLOCKED` or stalls

**To:** `architect` (design lane). **From:** build lane, 2026-09-25. **Branch:** `wp/T06`.
**Deliverable:** a design note `docs/design/T06-F4-recovery.md` — decision, seams with signatures,
the fallback order and its records, inertness proof plan, work orders with tests. No production code;
do not commit.

## 1. The question

Which recovery path should a revision-built EO region take when its Newton ends `BOUND_BLOCKED` (or
stalls) and T04's edge 3 (homotopy) has no continuation parameter and PTC's mass mapping is missing
for a T05 unit? Design it so that NET-02 is solved and `VERIFIED`, every switch is a recorded,
deterministic fallback, and no registered result moves.

## 2. Why the architect

It adds a recovery edge (or generalizes edge 3 / PTC) on the executor's region path — the phase
contract's and globalization's data flow (ADR 0005, ADR 0010, ADR 0012). It decides whether T06's 95%
nominal gate is reachable: NET-02 alone may use 20 of the gate's 22 allowed failures.

## 3. Evidence (from the T06 specification pass; `docs/derivations/T06-corpus-spec.md`, finding F4, R-074)

- NET-02 = heater + PH flash + recycle at r = 0.95 (revision-built). It ends `BOUND_BLOCKED` at
  iteration 1 under **both** contracts v1 and v2: the first Newton step truncates `S6.n.A` to 0; the
  next direction points out of the feasible set.
- Edge 3 reports `unsupported: no_continuation_parameter` — a revision flowsheet's region has no
  continuation parameter (T05b review S3 measured the same for every revision flowsheet).
- PTC refuses `PTC_MAPPING_INVALID(U-PHF…)` — T05 registered no PTC mass mapping for its units (T05
  spec §12.4; ADR 0010 D4).
- K03 §5.3's structural-zero release (T05b, R-064) acts only on components exactly on their bound at
  both the opening and the iterate; `S6.n.A` is truncated during the solve, not at the opening.
- Read: `docs/derivations/T06-corpus-spec.md` (F4, NET-02's registration, the ensemble's success rule),
  ADR 0010 (globalization: homotopy, edge 3, PTC, mass mapping), ADR 0005/0012 (phase contract),
  `docs/derivations/K03-solver-spec.md` §5.3, `docs/design/T05-generalization.md` §2 (the revision
  solve path), `src/process_runtime/orchestrator/{executor,region,homotopy,recovery,mass}.py`,
  `numerics/{newton,ptc}.py`.

## 4. Constraints

Frank's steers: fewest limitations; robustness first — "if a method cannot solve a hard case and the
solver then switches to another method this is also fine" (recorded, deterministic, never a relaxed
check). The certificate judges only the target declaration (R-035). SYN-001, T02–T05b registered
results and every identity key (`t02`…`t05b`, structural `4ce030ca…`) unchanged unless you say why.
No frozen interface change unless flagged prominently (the build lane takes it to Frank). R-016.

## 5. Options the build lane sees (you decide)

(a) A continuation parameter for revision flowsheets (e.g. a homotopy on specifications or feeds)
so edge 3 applies; (b) PTC mass mappings for the T05 units so PTC can run; (c) a bound-aware Newton
change (e.g. a projected / active-set step at a truncated component) in K03; (d) a new recovery edge
(e.g. a sequential-then-EO restart from a traversal of the truncated state). Say which, in what order,
and with what triggers.

## 6. Verification

NET-02 `CONVERGED` and `VERIFIED` within its allowances; the T06 ensemble's NET-02 starts; every
registered case unchanged (identity protocol as in T05b); gate green.
