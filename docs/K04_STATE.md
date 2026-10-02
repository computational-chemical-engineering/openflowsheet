# K04 — campaign state

**Rewritten in place, never appended.** A position, not a diary.

| | |
| --- | --- |
| Objective | The verifier: independent checks, the [A08] regularity screen, the certificate, structured failures (plan §4.2 row K04) |
| Branch | `wp/K03` (K03 and K04 share it; the branch outlived its name) |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 1249 tests** on both architectures |
| Lead | **Fable / Opus.** Fable specified (`docs/derivations/K04-certificate-spec.md`, ADR 0007); Opus implemented |
| Manifest | `evidence/K04/bf3d9eef3698e364ceb9d1aaafb80e6ed16b5e29/manifest.json` — `status: tested`, 7 pass / 0 fail / 1 unsupported / 1 not applicable, both reviews `pending` |
| Requirements | D14, D05, A08, A09 — all four `implemented` in the ledger |

## Where we are now

**The verifier works and rejects the case it exists for.** All five registered variants
certify `VERIFIED` with no limitations at all. The trivial root is rejected `FAILED` with
`false_success_detected`.

That rejection is the package in one measurement. At the once-through variant with S3's lifted
split forced all-liquid and both duties closed:

| Passing | Failing |
| --- | --- |
| all 49 assembled rows (worst 8.8e-10) | energy.heater **−8237.850393069453 W** |
| every material balance | energy.flash **+8237.850393069451 W** |
| both alias certificates | admissibility Σx·K − 1 = **0.07031421908077462** |
| the overall energy **envelope** | independent split **0.30410617028015113 mol/s** |
| the regularity screen | |

Fable's closed forms are 8237.8503930694530451, 0.0703142190807741552 and
0.30410617028018327955. The envelope's *pass* is asserted as a registered blind spot, so a
later session cannot simplify the energy check to it without failing a test.

## What the verifier does not share with the solver

| Check | Independent of |
| --- | --- |
| material balances | the compiled problem, the provider and the unit models — plain sums over stream flows; the envelope row is not a compiled row at all |
| energy balances | the lifted split: every enthalpy from a **fresh flash** of the stream's own (n, T, P) |
| admissibility and split | the lifted split, recomputed and compared |
| regularity | the solver's factorizations — K03 never factorizes the 47×47 matrix, so nothing could belong to it |

## Next action

**K05** — the immutable `RunManifest`, events, artifacts, replay, and the two-platform
structural hashes. ADR 0007 D4 already fixes what replay must *report*; K05 builds it.

## Open items

| # | Item | State |
| --- | --- | --- |
| 1 | STR-03, structural over-specification | `unsupported` — no validator before K06. G04's bad-spec clause is served by the 150 kPa `SPECIFICATION_CONFLICT` instead |
| 2 | ADR 0001 D6 does not carry the lifted equilibrium row kind | §5.2 registers τ = 9.3e-8 (mol/s)² by derivation; a one-line D6 amendment when ADR 0001 is next touched |
| 3 | Factorization reuse for the screen | Not implemented and not needed; the refusal path for a mismatched identity exists and is tested before anyone needs it |
| 4 | F1, F2, F3 | **All closed by Frank, 2026-09-22**, recommended default in every case |
