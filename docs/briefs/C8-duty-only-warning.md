# C8 — "multiple steady states possible" warning on duty-only column specifications (build lane, `sonnet-implementer`)

Branch `wp/C8` from `main` `f880582`. Source: `docs/CLOUD_WORK.md` C8; Frank's answer Q-S02-4
(`docs/FRANK_QUESTIONS.md:13`): no selection rule; both states registered and disclosed; **add a "multiple steady states
possible" warning to every duty-only column specification.**

## Facts with anchors
- The multiplicity: S02 spec §18.1 item 3 and §18.4 (`docs/derivations/S02-spec.md:475-477`, `:556-557`, `:571`),
  R-549; assertion A21 (`:591`); the second root `variants.M2.duty+duty.second_root` in
  `docs/derivations/scripts/s02_reference.json`.
- Duty-only detection already exists: `src/openflowsheet/models/syn001/column.py:529`
  (`all(_specification(spec, end).kind == "duty" for end in spec.ends())`, the R7 branch of §5 validation).
- Results: `ColumnSolution` (`src/openflowsheet/models/syn001/column_solve.py:774-792`, frozen dataclass); failures are
  `CascadeFailure` (S01's `cascade.py`). Existing warnings pattern elsewhere: `warnings: tuple[str, ...]` in
  `src/openflowsheet/studies/trust_region/trf.py:165`.

## Do
1. One function deciding the warning from the spec alone (duty-only ⇔ every end specification of kind `duty`),
   returning a typed, stable string in the repo's `code(detail)` grammar, e.g.
   `multiple_steady_states_possible(duty_only)` (DECISION line for the exact text).
2. Carry it on every answer for such a spec: `ColumnSolution` gains `warnings: tuple[str, ...] = ()` (defaulted, so no
   existing construction breaks and no `state_sha256` or record identity moves); if a `CascadeFailure` is returned for
   a duty-only spec, carry it too if `CascadeFailure` can take it additively — otherwise log a DECISION why not.
3. Tests (`tests/test_c8_duty_only_warning.py`): every duty-only registered case/variant (V-M1 duty+duty, V-M2
   duty+duty, M3 if duty-only — read the spec sets) carries exactly the warning; every non-duty-only set carries none;
   a negative control (a mixed spec) has none; the warning appears on V-M2 duty+duty's `R2` answer.
4. A one-line note in S02 spec §14 ("What this does not establish") is the design lane's — do not edit the spec; add the
   docs line to `docs/C8_DECISIONS.md` instead for the next design touch.

## Exit test
The new tests pass; `tests/test_s02_*.py tests/test_s01_*.py` pass unchanged; ruff/format/mypy clean.

## Out of scope
A selection rule between steady states; any numerics; S02's manifest (C8 carries none, R-565).

## Agent rules
Context cap ~80k; report ≤ 120 words. Choices: `DECISION:` lines in `docs/C8_DECISIONS.md`.
