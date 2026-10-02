# Fable review brief — P02, completed implementation

Repository `/home/frankp/Codes/Process Simulator`, branch `wp/P02`, commits `73ee3d5..7e9d7a4`.

## What you are reviewing

The completed P02 implementation against **your own specification**, `docs/derivations/P02-composition-spec.md`. You wrote that document and amended it three times during the work; this is the last read before P02 is merged and P03 inherits the measurements. Assume it passes its tests — 383 in the repository suite, `scripts/check.sh` green — and look for what plausible-and-passing hides.

## The diff, in the order worth reading

1. `benchmarks/p02/expected.py` — the judge's independent transcription of your §2.3–§2.6 closed forms into double precision, plus the orderings, scales and the two patterns (60 and 43 entries).
2. `benchmarks/p02/judge.py` — every assertion A00–A24 for any backend, from exported artifacts, in the repository environment.
3. `benchmarks/p02/linear_solve.py` — §9, the common SuperLU factorization with the explicit configuration, run on each backend's exported matrices.
4. `spikes/p02/casadi/harness.py` and `spikes/p02/pyomo/harness.py` — the two routes. The Pyomo one was written by an Opus agent against §10.3 and integrated here.
5. `spikes/p02/common/` — the shared state loader, counters, canonical CSC, envelope and measurement helpers.
6. `tests/test_p02_composition.py` — including three tests that attack the judge itself.
7. `src/process_runtime/compiled.py` — the `CompiledProblem` protocol, introduced per `docs/interfaces-frozen.md` §1 (your Q6 default).
8. `evidence/P02/a1c2de3fd449ccaa750ae4f9734f085a3c4a2c0a/manifest.json`.

## What was run, and what it produced

`PATH=.venv/bin:$PATH ./scripts/check.sh` → 383 passed, ruff and ruff format clean, mypy strict clean on 19 files. `./spikes/p02/casadi/run.sh` and `./spikes/p02/pyomo/run.sh` → exit 0. `p02_reference.py --check` → exit 0, and `--emit` reproduces the reference YAML byte-identically.

Verdicts: **both routes PASS-composition**, 70 assertions pass, 0 fail, 3 not applicable.

Worst deviation as a fraction of each assertion's own tolerance:

| Assertion | CasADi | Pyomo |
| --- | --- | --- |
| A00 judge self-test vs the 40-digit reference | 1.3e-02 over 786 values | same |
| A02 / A06 block Jacobians | 0.0 / 0.0 | 0.0 / 0.0 |
| A03 against the independent P01 reference | 1.7e-03 | 1.7e-03 |
| A04 / A07 fourth-order finite differences | 6.3e-03 / 3.6e-04 | 6.3e-03 / 3.6e-04 |
| A10 assembled entries (360 each) | 0.0 (L), 2.6e-06 (I) | 2.0e-06 |
| A12 residuals | 7.0e-05 | 1.5e-04 |
| A14 Schur elimination | 1.3e-05 | 1.3e-05 |
| A15 directional derivative | 5.7e-04 | 5.7e-04 |
| A16 forward/reverse identity | 1.7e-04 | not applicable (declared absent) |
| A21 cross-backend | 1.9e-04 | |
| A23.1 / A23.2 / A23.3 SuperLU | 3.8e-17 / 7.4e-17 / 4.6e-15 | identical |

A08 exact at every state, 60 entries lifted and 43 inlined; A09 one canonical structure across seven states; A11 the 10 and 15 vanishing entries stored and exactly `0.0`; A18 one value call per residual and one Jacobian call per Jacobian on both routes, zero value calls during Jacobian assembly; A22 `absent` on both, with the supplementary H5 record returning all eight entries exactly when the block ships symbolic derivative code.

## Where I am least sure

1. **A10 is exactly 0.0 on the CasADi lifted form, over all 360 entries.** I mutation-tested the judge (a 1e-9 relative perturbation fails A10 and A14; a structural zero returned as 1e-13 fails A11), so the check bites. But exact agreement across 360 entries deserves your eye: is it what you would expect from two double evaluations of the same closed forms, or does it suggest the judge and the harness share an arithmetic path they should not?
2. **The Pyomo row-sign adapter.** You approved it and amended §4.3. I want your view on whether the *judge* should additionally assert the native orientation numerically, rather than trusting `raw_structure.json`'s self-report of what it negated.
3. **A15's expected value comes from `expected.py`, not from the backend's own Jacobian.** That is the specification's wording as I read it, and it makes the check stronger, but it means A15 does not compare the backend's residual against the backend's Jacobian. A16 does that for CasADi; for Pyomo nothing does, because jvp and vjp are absent. Is that a gap worth an assertion in a later package?
4. **The counters.** They count invocations of our own Python methods. If a backend evaluated a callback through a path that does not enter our Python code, the counters would not see it. I believe that is impossible for an opaque callback, but you should say so or not.
5. **`repeat_microseconds` uses `perf_counter_ns` on a machine whose load I did not control.** Medians of 200 calls after 20 warm-ups, minima reported alongside. Enough for P03's cost comparison, or does P03 need something better?

## Not worth your time

Formatting, naming, import order, the JSON layout of the artifacts, and the draft schemas under `spikes/p02/schemas-draft/` (they are drafts by your Q5 default, and K01 promotes them). The `.venv-*` environments and `docs/backend-environments.md` are inventory for P03, not part of this implementation.

## Deliverable

A verdict plus findings, most severe first, each with file and line, the concrete failure scenario, and a severity of must fix, should fix or note. Say plainly if it is sound, and say which parts you did not examine. Do not rewrite the implementation; name the minimal correction and I will make it.
