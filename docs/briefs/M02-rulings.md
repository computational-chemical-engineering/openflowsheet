# Design-lane ruling round: M02 after WO-10, WO-11, WO-12 (one batch)

Branch `wp/M02` @ `bdb756e`, worktree `.claude/worktrees/m02`. Design note `docs/design/M02-pymrm-adapter.md` (§4.3
coupling driver, §6.2 replacement facets, §7.2 run class/replay, §10.2 G10–G12 l.784, §10.3 l.809, WO table l.700).
Build log `docs/design/M02-build-decisions.md` — each item's full facts are in the entry at the line given; read those
lines (sed -n), not the whole file. Reactor spec: `docs/derivations/M01-spec.md` (§8.15 Q-F4/Q-F5, A41–A48).
Records: `benchmarks/m02/g11-coverage.json`, `g12-real-loop.json`.

§10.3 as written: "A Q-F4 or Q-F5 point **inside** the hard domain that is not accepted: the variant's hard domain is
narrowed to exclude the failing region by a **new variant** (append-only) and a register entry; the failing point
becomes a registered refusal test. A narrowing that would exclude M01's nominal point stops the WO and goes to the
design lane. Q-F5's bound is widened (new variant) only if both 0.25× and 4× are accepted."

## Items

1. **D69 (l.82; STOP — §10.3 triggered; blocks WO-12 close and the M02 manifest).** G11 on the real reactor, two full
   runs identical at every point: Q-F4 accepts only the centre (1/17); all 16 corners fail — mostly stage S1 (low T),
   the certificate stage, or `element_balance_defect` (boundary limit 1e-6 although the child accepted its solution);
   the four 773.15 K zero-inert corners NaN/inf in the child's JSON output → typed `external_crashed` (transient,
   retried) although repeatable. Q-F5: 0.5× (on the variant's own lower flow bound) fails `element_balance_defect`;
   0.25× fails, 2× and 4× pass. ΔP ramp: first above ε_P at 8×; at 5 MPa 0.5× and 2× fail the defect limit while 1× and
   4× pass (not monotone). So no narrowed box follows mechanically; a box keeping the nominal point exists. Decide: the
   new variant's hard domain (or a different element-defect policy at the boundary — say which and why it is not a
   relaxed check), the refusal tests to register, whether NaN/inf output becomes `not_converged` (a child change → new
   variant), and the consequence for M05's decision box [643.15, 733.15] K (M05 N-F6) and M07 (plan risk K6).
   G12 for reference: real loop CONVERGED in 3 outer iterations, VERIFIED, reactor inlet 0.81 × F_nom, replay MATCH,
   live rerun bitwise.
2. **D70 (l.83).** §5.2 timeout re-registration deferred to the new variant (rule gives 200 s / 180 s, measured at
   host load 37–67). Confirm or rule.
3. **D50 (l.63).** G8 (f) G = diag(1.8, 0): pure Broyden needs a ρ rise at k = 2; §4.3's reset fires (step also
   clipped at X̂ = 0) → `no_decrease`. Restate the clause or adopt a non-monotone safeguard.
4. **D61 (l.74).** G9 (a) stand-in → real promotion `rejected`: only `validity` fails, on the real variant's per-tube
   flow bound (ADR 0034 D10) vs the stand-in's null bound. Options: flow bound judged as an operating-point check, not a
   domain dimension; a stand-in variant with a flow bound; restate G9 (a) as real → stand-in. (Interacts with item 1.)
5. **D55 (l.68).** Run-class rule matches "external" in `pr-c1-v1`'s provenance text, so every C1 run is R3,
   including stand-in coupled runs. Bug or intended?
6. **D58 (l.71).** Final `constants_sha256` hashes the Broyden iterate's floats, compared exactly; a cross-platform
   replay could MISMATCH on a last bit. Acceptable for v0.2, or change?
7. **D71 (l.84).** M05's ruling R-300 E7 said `with_coupling` (wp/M05 `1ed8c6c`) lands on wp/M02 byte-identically;
   the M02 engineer found it duplicates WO-10's `application/coupled_run.at_coupling` and did not copy it. Rule which
   one M05 uses (M05 §17.5, on `wp/M05`).
8. **Small:** the support envelope still lists `pr-c1-v1` under `unbound_providers` (false since the join); the
   stand-in's docstring says "Not registered" but its file hash is the pinned artifact hash.

Also flag anything that needs Frank (scope of the shipped reactor domain may be his call — if so, give a default).

## Deliverable
Rulings as a new section of the M02 design note + register entries (next free R-number after R-302; check
`docs/decision-register.md` on `wp/M02` and on `main`, both). Per item: the ruling, changed acceptance with numbers,
the work order implementing it (WO-12a, WO-14…, bounded vs Opus). Commit on `wp/M02` (named paths, doc only, no gate).
No production code or tests. Report ≤ 300 words.
