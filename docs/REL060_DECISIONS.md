# REL060 build decisions (append-only)

Build-lane choices made while implementing the 0.6.0 release's work orders, each with the
alternative and how to reverse it. The design authority is `docs/briefs/REL060-line-0.6.md`.

## LINE06-R-WV: `scripts/wheel_data_check.py --f2` (RC item `WHEEL-F2`, D-5 WV-1 to WV-6)

- **DECISION R-WV-1: the input assertions are their own check, `f2.inputs`.** D-5 ("Inputs")
  says the script asserts each raised document has `schema_version` 2 and N differs from its
  source only at `/materials/thermal_coordinate`, but gives that assertion no check id among WV-1
  to WV-5. Choice: a sixth check `f2.inputs` (after `wheel.built`), which must pass like the others
  for exit 0; it also carries the five document digests WV-6 asks for. Strictest reading: a wrong
  input fails the item by name instead of only through whatever the probes then do. "Differs only
  at" is read as "differs exactly there": N equal to its source (control (e)) fails `f2.inputs` as
  well as `f2.refusal`. Alternative: fold the clause into `f2.probes` (WV-2). Reversible by moving
  the `inputs_findings` clause into the `f2.probes` condition in `run_f2_checks`.
- **DECISION R-WV-2: WV-4's registry is read with `git show C:benchmarks/f0/corpus.json`**, not
  from the working tree, so that "at C" holds even if the checkout carried an uncommitted edit (the
  item already refuses a checkout whose HEAD is not C). Alternative: read the working-tree file, as
  `run_checks` reads `benchmarks/v03/registration.json`. Reversible in `run_f2_checks`.
- **DECISION R-WV-3: the probes record the thread variables they ran with**, and `f2.probes`
  requires each of `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` to be `"1"` on both
  sides, so WV-2's "both with ... = 1" is checked, not only arranged. Alternative: set them and not
  check them. Reversible by dropping the `threads` clause of `f2_findings`.
- **DECISION R-WV-4: a document's run in WV-3 also requires exactly one `run_manifest` output and
  every `artifacts` value to be 64-hex**; N's admission is a pass only as `{"admitted": ...}`, any
  other exception than `ApplicationError` is recorded as an error and fails WV-5. These make the
  check stricter than D-5's words without adding a value D-5 does not name.

## LINE06-R-FIX

- **DECISION R-FIX-1 (F-1): WV-5 records `{"admitted": bool(report.admitted)}` and requires `{"admitted": True}` for the base's v2.**
  An `AdmissionReport` with `admitted: false` is not an admission. Alternative: keep the type name. Reversible by
  reverting `ddf883ed`.
- **DECISION R-FIX-2 (F-2): the `junit-cases` tests build step 1's record with `step1_checks`, and `legs.junit` records
  `compared_with_step1` (the legs whose step-1 hash was found and compared).** Alternative: leave the silent skip.
  Reversible by reverting `d8e9fcab`.
- **DECISION R-FIX-3 (F-3, orchestrator: pin): `--case <file>::<test>=<N>` pins the matched count on every leg**
  (N a positive decimal integer, else exit 2); `legs.cases` fails on a leg whose count differs and records the counts.
  `F2-THREE-OS` pins 56 and 1 (measured on all four legs of run 46041020889). Alternative: four-leg equality only.
  Reversible by dropping `=N` from `release/lines/0.6.json` (the parser keeps the old form).
- **DECISION R-FIX-4 (N-1): controls for a push run not `completed` (fails exactly `legs.push_run`) and control (d)
  asserts `== {"legs.cases"}`.** Tests only. F-3 and N-1 share one commit (one test file).
