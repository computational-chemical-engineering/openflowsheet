# S09 brief: a third column reference tool, BioSTEAM (design lane, `specifier`)

Branch `wp/S09`, worktree `.claude/worktrees/s09`, from `main` `390e0af5`. Queue entry: `docs/CLOUD_WORK.md` l.54 (Frank,
2026-10-24, Q-A2-4 "Plan a 3rd tool"). Tool choice: Frank, 2026-10-25, Q-S09-1 "BioSTEAM first".

## 1. The question

Write S09's specification: how BioSTEAM becomes a third blind reference for S03's column cases, at what pre-registered
levels, with which registered solver settings, harness checks and classifier rules, so that the build lane has nothing to
choose and S03's coverage gaps (RC4 none; RC3 and RC7 IDAES only; X31 not met, 2 of 4 cases with two references) are
re-judged.

## 2. Why the specifier

Benchmark registration and reference-comparison rules are design-lane (CLAUDE.md). The blind-qualification discipline of
S03 (pre-registered levels, closed ladders, `NOT_COMPARABLE` never reformulated, controls that must disagree) must carry
over to a new tool with different failure modes.

## 3. The S03 framework S09 extends

`docs/derivations/S03-spec.md` is the pattern and stays the authority for the cases, quantities, tolerances and verdict
mechanics: §2 the qualification rule (§2.2 levels L1–L3 and "never admissible": user-written thermodynamics, phase
equilibrium, balance or enthalpy equations; a property method other than T06's SYN-001 definitions; any value from this
project's results; a change to a registered input), §3 the cases (`s03_cases.json`, twin `s03_reference.json`), §4
quantities, §5 matched semantics, §6 tolerances, §7 verdict mechanics (the table at l.325–331: rules 0, 1, 2, 2c, 2d, 3),
§17 and §18 (amendments: the IDAES path ladder), §19 errata. Records: `benchmarks/s03/references/`
(`comparison.json`, `qualification/`, `results/`); harnesses `spikes/references/s03_qualify_{idaes,dwsim}.py`; classifier
`scripts/s03_reference_comparison.py`; verdict `docs/reviews/S03-verdicts.md`; review `docs/reviews/S03-review.md`.
Register R-628…R-644. Reference environments: `docs/reference-environments.md`, built by
`scripts/build-reference-envs.sh` (IDAES and DWSIM).

## 4. Facts from a feasibility spike (2026-10-25, scratch, not evidence)

Scripts, logs and JSON: `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/s09-spike/`
(`check_pure.py`, `run_columns.py`, `rc3_sweep.py`, `rc3_algos.py`, `rc4_respec.py`, `rc4_blind.py`, `syn001_thermo.py`,
`freeze.txt`). Survey of other tools: `.../scratchpad/s09-tool-survey.md`.

- **Install.** Python 3.13.5, `pip install biosteam`: biosteam 2.54.0, thermosteam 0.54.2, thermo 0.6.1, chemicals 1.5.2,
  flexsolve 0.5.10, numba 0.68.0, numpy 2.5.4, scipy 1.18.1 (full freeze in `freeze.txt`). 33 s. biosteam/thermosteam
  are sdists building pure-Python wheels; every compiled dependency has cp313 manylinux aarch64 wheels. Licence:
  University of Illinois/NCSA in both LICENSE.txt files (METADATA says "MIT", inconsistent; MIT applied to 0.1–0.9 only).
- **Property method.** `Chemical.blank` (no database) with `Psat.add_method(closed form)`, `Hvap.add_method(L_i)`,
  `Cn.l`/`Cn.g.add_method(100)`, `V.l = 1e-4`, `phase_ref='l'`, `Tb`; T_ref is a read-only class attribute (298.15 K),
  set to 300 K by a two-line subclass; `IdealThermo` with an explicit `IdealMixture` (without it, `IdealThermo(chems)`
  raises AttributeError — a tool bug). At P = P_r, Psat, h^L, h^V match SYN-001's closed forms with relative error 0.0 at
  310/347/385/430 K; flash K ≤ 2.5e-16; no pressure dependence; nothing from a database leaks. Away from P_r the tool
  lacks SYN-001's Poynting and v(P − P_r) terms; S03 runs every case at P_r. **Whether supplying these closed forms
  through the tool's hooks counts as "a property method other than T06's SYN-001 definitions" or as user-written
  thermodynamics under §2.2 is for you to rule** (T06's mapping into IDAES and DWSIM is the precedent).
- **Columns.** `MultiStageEquilibrium` (stage 0 = top), native per-stage specs Duty, Reflux (L/V), Boilup (V/L),
  Temperature, Flow (liquid leaving / total feed); each spec replaces that stage's energy balance.
  - Solver settings: the default algorithm chain fails RC3 (Psat at T = −6e-6 K); `inside out` returns a wrong profile
    with **no error** (an adiabatic stage's energy gap reached 1448 W). Working: `phenomena`, fixed-point,
    `early_termination=False`, tolerance 1e-10; repeat runs bit-identical. `_run` catches solver exceptions and returns
    the best point without raising; the tool's reported residual is a meaningless 1e6 with `early_termination=False`.
  - RC1: Reflux 2, Boilup 1.5, 37 iterations. RC3 stripper: native (Duty on the last stage, others adiabatic), 24
    iterations; component balance 2e-16, worst adiabatic residual 2e-7 W.
  - RC4 refluxed absorber: **not native** — no distillate-rate spec; `Flow` on stage 0 sets the reflux, not D. Tool bug:
    with exactly one spec, the initializer (`biosteam/units/stage.py` ~3285–3298) overwrites a Reflux/Boilup spec
    (Reflux 1.234 became L/V 73). A workaround — re-impose `stages[0].B`, re-solve, wrapped in an outer secant on reflux
    to D = 0.5 — converges in 7 outer iterations from starts 1.0 and 1.5. Neither is among S03's L1–L3.
  - RC7: **not expressible** — a Temperature spec on stage 6 makes stage 6 carry the duty and leaves the reboiler
    adiabatic; no cross-stage specification.
  - Independence: no IDAES, Pyomo, DWSIM or IPOPT code in the stack (one commented-out `cyipopt` import).
- **Blindness exposure (state it in the spec).** After its runs, the spike compared RC1, RC3 and RC4 informally with
  `benchmarks/s03/references/results/ours-*.json` (max |ΔT| 2.2e-9, 2.2e-7, 9.2e-11 K). The solver settings above were
  chosen from the tool's own residuals before that comparison, by the spike's account. Rule whether the spike's settings
  may be registered, or whether S09's ladder must be registered from the tool's documentation and residual checks alone
  and the qualification re-run by a fresh agent that has not seen the comparison.

## 5. Already decided, not open

- BioSTEAM first (Frank). ChemSep-LITE (Windows-only, Wine with 32-bit support not installed, licence requires a visible
  acknowledgement) is not in S09; mention it only as the fallback if BioSTEAM cannot express RC4 at any admissible level.
- S03's cases, quantities, tolerances and verdict rules are not re-opened; S09 adds a tool, it does not re-judge IDAES or
  DWSIM.
- A case a tool cannot express is `NOT_COMPARABLE(capability: <what>)`, never a substituted model.

## 6. Open (rule)

1. The levels for BioSTEAM (L1 native unit + native specs; an L2 analogue; whether "native column + a harness secant on
   a native spec to meet a registered specification" can be an admissible level, and under what accuracy and disclosure
   rules — RC4 turns on this).
2. The property-method question in §4.
3. The registered solver ladder (algorithm, tolerances, iteration caps, `early_termination`), and the harness's own
   checks replacing the tool's untrustworthy convergence report (S03 rules 2, 2c, 2d as BioSTEAM-specific checks).
4. The blindness ruling in §4, and the work orders: environment acquisition (a pinned BioSTEAM environment added to
   `scripts/build-reference-envs.sh` and `docs/reference-environments.md`, with an aarch64 statement), blind
   qualification, classifier extension, comparison, the re-judged X31/D19 coverage, verdict.
5. Positive controls that must DISAGREE (as S03's PC-L and PC-LI).

## 7. Deliverable

- `docs/derivations/S09-spec.md` with numbered falsifiable assertions and work orders (each ~150k context), register
  entries after the last R-number on `main` at your start (check: S08's branch holds R-728…R-732 unmerged, so start at
  **R-740** and note the gap), an ADR only if a frozen interface or an accepted ADR changes.
- Copy the spike's scripts, logs, JSON and `freeze.txt` (not `venv/` or `__pycache__/`) into
  `docs/derivations/scripts/s09_spike/` as design-time evidence (the scratchpad is not durable), lint- and format-clean
  with semantics-preserving edits only (as S08's `s08_design/` probes were), labelled "not evidence".
- A docs-only commit on `wp/S09` (include this brief and the `docs/FRANK_QUESTIONS.md` line already staged in the
  worktree). Do not push. Report in at most 25 lines.

## 8. Out of scope

S08 (one-phase sections, running on `wp/S08`), S10-C, any change to IDAES/DWSIM harnesses or records, ChemSep.
