# S09 feasibility spike (2026-10-25): design-time record, NOT evidence

Copied from the session scratchpad so that it is durable (`docs/derivations/S09-spec.md` §9.1). These files are the
record of what the spike ran and saw. They are **not evidence** for any S09 assertion, they are not a qualification,
and no S09 record, classifier or test may read or import them (S09.A03 forbids the string `s09_spike`).

- Scripts were made lint- and format-clean with semantics-preserving edits only (formatting; renamed locals; the
  safe ruff fixes; `% (...)` to the equivalent format calls; one lambda to a `def`; `# noqa: E402` where an import
  follows `warnings.filterwarnings` on purpose). Their ASTs, normalised for exactly those edits, equal the originals.
  The logs and JSON are the originals, produced by the unedited scripts.
- `compare_ours.py` read this project's S03 results. It is kept because it documents the spike's blindness exposure.
  Its output was not saved. `rc4_sweep.py` and `rc4_respec.py` used RC4's twin reflux ratio, as their docstrings say.
- `rc3_algos.log` and `run1.log` came from an earlier state of `run_columns.build` (before the sweep's settings were
  written into it); re-running those scripts today would not reproduce them.
- `syn001_thermo.py` overrides thermosteam's read-only `Chemical.T_ref` with a subclass. S09 does not register that
  (§4.2): the registered definition keeps the tool's default datum.
- The environment is in `freeze.txt` (Python 3.13.5); `install.log` is the pip log.
