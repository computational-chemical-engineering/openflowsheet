# Brief — T08: PTC-R1 saddle diagnostic (not a result; changes no verdict)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`.

## Why

The verdict `docs/reviews/T08-verdict-V14b.md` found V14 (b) FAIL: under the registered PTC arm
(`T08-PTC-R1-ptc`), 149 of 441 PTC-R1 starts converge (VERIFIED) to the saddle MID. Its hypothesis (not
established): with T04 §7.7's SER settings (start Δτ = 1 s, growth ≤ 2× per step, 200 steps) the pseudo-time step
passes 2/s₊ ≈ 8.3 s by about step 4, after which steps contract toward the saddle (build-first spec §A3.6's named
risk; the step matrix is singular at Δτ = 1/s₊ ≈ 4.16 s). Frank (2026-09-29) asked for a diagnostic recording
step-size histories. It explains the mechanism for v0.2; it is **not** part of the registered comparison and
changes nothing registered.

## Deliverable

1. `benchmarks/t08/ptc_r1/diagnose.py`: re-runs **only the PTC arm** on the 149 starts whose class in
   `benchmarks/t08/ptc_r1/results-ref-x86-64.json` is `MID`, plus, as controls, the PTC runs that ended LOW/HIGH
   from the 84 starts in `S_ptc \ S_newton` (read both sets from that file). Per run and per pseudo-step it records:
   Δτ, accepted/rejected, the state mapped to `(x₁, x₂)` (§A1.5's map), the ∞-distance to each of LOW/MID/HIGH,
   and the sign of `det(M̂/Δτ + Ĵ_σ)` if cheap (else omit and say so). Obtain the per-step data from the trace/
   `RegionAttempt.ptc` records if they carry it; if not, capture it with a pass-through shim like `compare.py`'s
   Newton shim (no numerics change — assert that the final state and outcome equal the committed result record,
   byte-equal floats, for every re-run). It must not touch `case.json`, `revision.json`, the arms, `compare.py` or
   any committed result.
2. Output `benchmarks/t08/ptc_r1/diagnostic-ref-x86-64.json` and a short `diagnostic-ref-x86-64.md`: for the MID
   runs vs the controls, the step index and Δτ at which Δτ first exceeds 1/s₊ (4.16 s) and 2/s₊ (8.3 s), the
   distance-to-MID history summary, and a plain statement of whether the data support, contradict or leave open the
   hypothesis. Label it at the top: "Diagnostic after C_res; not a result of the registered comparison; changes no
   verdict (R-118)."
3. A test that the diagnostic's re-runs reproduce the committed outcomes for a handful of starts (fast), and that
   the script refuses to write over an existing diagnostic file.

## Rules

Local only (`ref-x86-64`, threads pinned to 1 like CI: `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`).
Commit script, test and outputs (messages `T08: PTC-R1 diagnostic …`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`); stage named paths only; `check.sh`
green at the end. Do not edit specs, ADRs, the verdict or any registered file. Do not interpret beyond the data;
if the shim would have to change numerics to get the data, stop and report. Budget: the user is near a weekly
usage limit — keep it small.

## Report

Commits, the table of first-crossing step/Δτ for MID vs controls, the one-paragraph reading, `check.sh` counts.
