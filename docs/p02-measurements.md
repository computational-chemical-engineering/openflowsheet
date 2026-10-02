# P02 matched measurements: CasADi and Pyomo/PyNumero

**Package:** P02. **Authority:** `docs/derivations/P02-composition-spec.md` §7 (measurement
protocol) and §11.4 (what P02 does not establish). **Requirements:** D02, D03, A05.
**Recorded by:** Opus 5, 2026-09-10, from `spikes/p02/results/<backend>/`.

These are the inputs P03 compares under its own decision rule. **P02 states no preference between
the two routes.** Both are PASS-composition.

> **Count corrected by P03, 2026-09-17.** This sentence previously gave "70 assertions pass, none
> fail, three are not applicable". That count predates the Fable review of the completed P02
> implementation, which found a coverage defect in the judge and added assertions. The authoritative
> count is the evidence manifest's: `evidence/P02/507dccf…/manifest.json` records **93 checks — 89
> pass, 0 fail, 4 not applicable**. Neither per-backend verdict changes.

## 1. Host and protocol

Debian 13, x86-64, Python 3.13.5, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`. NumPy 2.2.4 and
SciPy 1.15.3 in both environments, held at the repository's pinned versions so that a difference is
attributable to the backend and not to the array stack. Machine load was not controlled; the
headline is the median and the minimum is reported beside it, because the minimum is the floor a
quiet machine reaches. Five fresh processes for import, compile and memory; 200 timed calls after
20 warm-ups for evaluation.

## 2. One-off costs

| | CasADi 3.8.0 | Pyomo 6.10.1 + PyNumero |
| --- | --- | --- |
| Backend import, median / min | 12.6 / 12.4 ms | 432.1 / 417.4 ms |
| NumPy import, for scale | 36.1 ms | 36.6 ms |
| Compile the lifted form, median / min | 5.76 / 5.63 ms | 162.5 / 161.1 ms |
| Compile the inlined form | 2.29 / 2.24 ms | not applicable |
| First residual call | 0.110 ms | 0.150 ms |
| First Jacobian call | 0.223 ms | 1.015 ms |

The Pyomo compile figure includes writing the problem and loading the ASL library, which happens
inside `PyomoNLPWithGreyBoxBlocks` construction. That is why its import looks expensive and its
compile more so: the two are one cost split across two lines.

## 3. Steady-state evaluation, at two levels

Both routes are timed at the same two levels, because comparing a bare function call against
another route's full boundary would flatter one of them. **Backend** is the evaluation plus
construction of the input from the NumPy state vector, which is what `set_primals` plus evaluation
is on the Pyomo side. **Boundary** adds what the `CompiledProblem` boundary does with the result:
naming the entries and assembling the canonical CSC, and on the Pyomo route the name-keyed
permutation into specification order.

| Median / min, µs | CasADi backend | CasADi boundary | Pyomo backend | Pyomo boundary |
| --- | --- | --- | --- | --- |
| Residual | 74.6 / 59.2 | 119.4 / 117.0 | 67.0 / 54.9 | 66.8 / 64.3 |
| Jacobian | 178.5 / 175.8 | 238.8 / 235.2 | 742.8 / 714.2 | 827.8 / 807.7 |

The residual is equivalent at the **backend** level: the 7.6 µs between the medians is inside the
spread between each route's own median and minimum. At the **boundary** it is not — CasADi's
boundary adds 44.8 µs to its residual while Pyomo's adds essentially none, so the boundary residual
favours Pyomo by 1.8×. The Jacobian runs the other way, and further: CasADi is about four times
faster at the backend level and about three and a half times faster at the boundary, a gap larger
than any bookkeeping difference between the two harnesses. At 17 variables all of this is overhead,
not scaling.

> **Corrected by P03, 2026-09-17.** This paragraph previously read "The residual costs the same on
> both routes at both levels", which its own table contradicts at the boundary (119.4 µs against
> 66.8 µs). Found by the `fable-verdict` pass on the P03 brief, which had inherited the sentence.
> The P03 verdict is unaffected — per Newton iteration at the boundary CasADi is still 2.5× cheaper,
> 358.2 µs against 894.6 µs — and `docs/adr/0003-compiled-problem-backend.md` D2.1 carries the
> corrected reading.

## 4. Memory

| Stage, resident set | CasADi | Pyomo |
| --- | --- | --- |
| After NumPy import | 25.8 MiB | 25.6 MiB |
| After backend import | 35.1 MiB | 111.7 MiB |
| After compiling the lifted form | 48.2 MiB | 116.4 MiB |
| Peak allocation during compile | 0.09 MiB | 0.44 MiB |

Current resident set from `/proc/self/status`, not the peak. Peak resident set is inherited by a
spawned process from the process that spawned it, which made the first measurements on both routes
report one number at every stage.

## 5. Structure and callback behaviour

| | CasADi | Pyomo |
| --- | --- | --- |
| Assembled lifted system | 17 × 17, 60 nonzeros | 17 × 17, 60 nonzeros |
| Stored structure size | 792 bytes | 792 bytes |
| Inlined system | 11 × 11, 43 nonzeros | not available on this route |
| Value calls per residual, per block | 1 | 1 |
| Jacobian calls per Jacobian, per block | 1 | 1 |
| Value calls per Jacobian, per block | 1 | 0 |
| Callback probes during compile | none | one Jacobian call per block |
| Second order through opaque callbacks | absent, raises | absent, raises |
| Forward and reverse products | exact | absent |

Neither route falls back to finite differences or to a dense Jacobian. CasADi calls each block's
value method once per assembled Jacobian, because the Jacobian callback takes the block's nominal
output as an argument; PyNumero calls it not at all. The specification's threshold for suspecting
a difference fallback is `n_inputs + 1` value calls per Jacobian, which is three for block K and
six for block H, so both routes are far below it, and one call is not evidence of differencing.

## 6. Facts a comparison must not lose

- **CasADi installs from a wheel. PyNumero does not work without a build.** `pip install Pyomo`
  leaves the ASL interface unavailable; it needs `pyomo build-extensions`, which needs setuptools
  in the environment plus cmake and a C and C++ compiler, and which exits nonzero even on success
  here because APPSI fails for want of pybind11. Details and hashes: `docs/backend-environments.md`.
- **The CasADi wheel bundles 221 shared objects, 235 MB**, including adaptor shims for six
  commercial solvers with no vendor library present, and ships no LICENSE or NOTICE file against
  its declared LGPLv3-or-later. That is a distribution question, not a numerical one.
- **A CasADi callback must declare its Jacobian sparsity** through `has_jac_sparsity` and
  `get_jac_sparsity`, or the assembled pattern is over-approximated.
- **PyNumero writes a grey-box output constraint as `f(inputs) − output`**, so the harness applies
  a declared row-sign adapter to the six defining rows and records the native orientation.

## 7. What these numbers do not establish

The problem has 17 variables, so the timings measure boundary and assembly overhead, not how
either backend scales. Nothing here is a solver benchmark: no nonlinear solve was run. Nothing
here selects a backend; that is P03, under correctness, sparse composition, distributability and
installability first, and measured cost second.
