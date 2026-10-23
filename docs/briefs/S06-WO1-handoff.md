# S06 WO-1 — handoff (build lane `opus-engineer`, 2026-10-22)

Branch `wp/C11`, commits `7c5ea60` (code), `460eb03` (tests, decisions). WO-1 is complete; WO-2 is not started.

**Built.** `models/syn001/column.py`: `EndSpecification.component`/`.stage`; `INVERSE_KINDS`, `END_KINDS`,
`NOT_OFFERED` as S06 §1; S4 for direct kinds only; `_inverse_refusal` (I1–I6 after S10; the split test exact in
`Fraction`; the band `saturation_temperature`/`stage_band` from §4's closed form). Declared rows: inverse slot rows
`T_s − T*`, `n_c − ν*`, `u − π*` (S02 ids, parameter `<column>*`), and per purity end the column `u`
(`purity_flow_id`) and `…:spec:purity_definition` (`rows.scaled_definition_row`, `F` at
`purity_reference_parameter`). `slot_column` covers the inverse kinds; `inverse_parameter`, `specified_quantity`;
`column_solve.spec_values` gains `<end>_<kind>`.

**Tests.** `tests/test_s06_column_wo1.py`: 89 pass, 1 strict xfail (A01, A02, A03, A04, A12, A13 formation).
S01, S02, C8 and ADR 0008 suites green (494 passed with S06). ruff, format and mypy clean.

**Open.** Q-S06-WO1-1 (`docs/C11_DECISIONS.md`): the I3 probe meets S01's R5 first at M1's 340 K feed. The design
lane should register the probe's feed temperature.

**For WO-2 (`column_solve.py`), known gaps:**
- `_initial_state` / `bubble_point_endpoint` do not set `u⁰` (S06 §6). A purity set's state has no `u` yet, so
  `row_values` raises `KeyError`.
- `slots()` reads `CONTINUED_KIND[kind]`, which has no inverse kinds yet (S06 §12: `temperature → T`,
  `recovery → N`, `purity → U`). `slot_column` already returns the inverse slot's variable.
- §8 items 1–4, §7.3 `UnreachedSpecification`, §7.5 records, A05–A11, A13 (records), A14–A16, the
  `s06_reference.py --check` run and `evidence/S06/<commit>/manifest.json`.
- Reference SHA-256 pinned in the test: `a8ff5bb3…cce810`.
