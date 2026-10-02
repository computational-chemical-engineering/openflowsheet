# PTC-R1 saddle diagnostic — ref-x86-64

**Diagnostic after C_res; not a result of the registered comparison; changes no verdict (R-118).**

Commit `4f0839f756f934c4774b4770f2e9e8b77010d28d` (tree clean: True); source `benchmarks/t08/ptc_r1/results-ref-x86-64.json` (sha256 `76a7455d39e059f4…`). Every re-run reproduced its committed record byte-for-byte (233 of 233).
Thresholds: `1/s₊ = 4.15865 s`, `2/s₊ = 8.31731 s`. Statistics are min / median / max.

| set | runs | crosses 1/s₊ | first k (count) | Δτ there [s] | crosses 2/s₊ | first k (count) | Δτ there [s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MID | 149 | 149 | 3 (149) | 4.78 / 8 / 8 | 149 | 4 (148), 5 (1) | 8.98 / 16 / 16 |
| control | 84 | 84 | 3 (57), 4 (8), 5 (1), 6 (2), 7 (4), 8 (3), 9 (2), 10 (2), 11 (1), 16 (1), 24 (1), 41 (1), 54 (1) | 4.2 / 8 / 8.19 | 84 | 4 (48), 5 (8), 6 (3), 7 (5), 8 (5), 9 (3), 10 (3), 11 (2), 12 (2), 17 (2), 25 (1), 42 (1), 55 (1) | 8.52 / 14.8 / 16.6 |

Distance to `MID` (dimensionless ∞-norm, §A1.5):

| set | at the start | before first Δτ > 2/s₊ step | after it | min over run | last accepted step (pre-polish) |
| --- | --- | --- | --- | --- | --- |
| MID | 0.51 / 3.71 / 6.51 | 0.00159 / 0.502 / 1.54 | 0.000306 / 0.174 / 0.771 | 3.21e-09 / 2.03e-07 / 5.33e-06 | 3.21e-09 / 2.03e-07 / 5.33e-06 |
| control | 0.11 / 0.91 / 5.71 | 0.0109 / 0.444 / 4.46 | 0.00425 / 0.441 / 4.45 | 0.00425 / 0.196 / 4.45 | 0.439 / 0.439 / 4.45 |

Median distance to `MID` by iterate (0 = the start, n = after pseudo-step n − 1):

| set | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MID | 3.71 | 2.69 | 1.93 | 1.08 | 0.502 | 0.174 | 0.0324 | 0.00144 | 4.73e-05 |
| control | 0.91 | 0.421 | 0.361 | 0.39 | 0.44 | 0.44 | 0.44 | 0.439 | 0.439 |

The iterate each run's first `Δτ > 2/s₊` step starts from, counted by its distance to `MID` (reporting bins, not a registered neighbourhood), and the runs whose distance to `MID` never increases from that iterate on:

- MID (149): ≤ 0.01: 4, ≤ 0.1: 32, ≤ 0.3: 56, ≤ 1.0: 117; non-increasing from there: 145.
- control (84): ≤ 0.01: 0, ≤ 0.1: 1, ≤ 0.3: 1, ≤ 1.0: 72; non-increasing from there: 38.

Other facts:

- MID: attempts per run [1]; largest Δτ 98.2 / 256 / 1.02e+03 s; rejected trials 0; polish {'accepted': 149}; runs whose `sign det(M̂/Δτ + Ĵ_σ)` changes 14 (first change at k: 1 (8), 2 (5), 3 (1)).
- control: attempts per run [1]; largest Δτ 21.1 / 174 / 474 s; rejected trials 0; polish {'accepted': 84}; runs whose `sign det(M̂/Δτ + Ĵ_σ)` changes 51 (first change at k: 1 (18), 2 (21), 3 (9), 5 (2), 6 (1)).

## Reading

Written by hand after the run, from the numbers above only.

The data **support the timing** the verdict hypothesised (§7), **rule out the polish and rejections as the
source**, and **leave open** whether crossing `2/s₊` is what sends a run to `MID`. Every `MID` run first takes
`Δτ > 2/s₊` at pseudo-step 4 (148 runs) or 5 (1), and from the iterate that step starts at, its distance to `MID`
never increases in 145 of 149 runs, down to 3.2e-9–5.3e-6 at the last accepted pseudo-step, before the polish;
no trial is rejected and the polish is accepted in every run, so the approach to the saddle is the SER-controlled
pseudo-steps' own. Whether `Δτ` passes `2/s₊` *before* the iterate enters the saddle's neighbourhood depends on a
radius no document registers: of those 149 starting iterates, 4 are within 0.01 of `MID`, 32 within 0.1, 117
within 1.0. Crossing `2/s₊` does not by itself distinguish the `MID` runs: all 84 controls cross it too, 48 at the
same pseudo-step 4 and from iterates at a similar median distance to `MID` (0.44 vs 0.50), and end at `LOW` or
`HIGH`. The `MID` runs' median distance to `MID` already falls from 3.71 to 1.08 over their first three
pseudo-steps, all taken at `Δτ < 1/s₊` (the controls': 0.91 to 0.39). The data are consistent with the saddle
being reached by large-`Δτ` pseudo-steps from iterates the early small-`Δτ` steps have already brought towards
it; they do not show which of the two selects `MID`. The determinant sign of the full scaled step matrix changes
in 14 `MID` runs and 51 controls, always at k ≤ 3 in the `MID` runs, and carries no further signal here.
