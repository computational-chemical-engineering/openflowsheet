# C3 — housekeeping (a)–(e) (build lane, `sonnet-implementer`; branch `wp/C3` from `main` `3c10e97`)

Source: `docs/CLOUD_WORK.md:25`. Each item gets a test (or, for docs-only items, a generator `--check` or an
existing test that covers it). Register numbering for this package: R-500…R-504 (only if a ruling is needed).

## (a) Verdict F8 — the G11 experiments audit accepts a point relabelled `direct`
- Finding: `docs/reviews/V02-verdicts.md:702-704` (F8); demonstration `:600-606` (one boundary point relabelled
  `direct` with its experiment removed → exit 0, PASS on 209).
- Code: `scripts/m07_g11_experiments_audit.py:307-360` (`audit`); with `runs` given it builds `by_label` (:337) but
  the `point["experiments"] is None` branch (:343-347) trusts `point["path"]`.
- Fix: when `runs` is given, compare each point's `path` with the runs file's point of the same label and record a
  `structural` problem on mismatch. Exit test: a new test in `tests/test_m07_g11_experiments_audit.py` that relabels
  one boundary point `direct` (experiment removed) and asserts a non-zero exit / a structural problem; the existing
  tests still pass. No committed record may change.

## (b) `scripts/t08_rc.py` install-check strips `.venv` when the venv is inside the checkout
- Code: `scripts/t08_rc.py:304-321` drops every `sys.path` entry under `ROOT`, including the running interpreter's
  own site-packages when `.venv` lives inside the checkout; then imports fail. Test:
  `tests/test_v02a_r347_machine_class.py:63-` (fails in a checkout with an inner `.venv`; passes in CI/worktrees).
- R-347 (`docs/decision-register.md:7902-7920`) registers the record's `machine_class` member only; it does not
  register which `sys.path` entries are stripped. The check that must keep its meaning is `a44.outside_the_tree`
  (:315-321): `openflowsheet` imported from outside the tree.
- Fix (DECISION already taken by the build lane, see `docs/C3_DECISIONS.md`): keep the running interpreter's own
  `sysconfig` `purelib`/`platlib` (and stdlib) paths even when under `ROOT`; strip every other entry under `ROOT`.
  `a44.outside_the_tree` is unchanged, so an editable install inside the tree still fails it. Same treatment for the
  second strip at :455-465 if it has the same defect. Exit test: `tests/test_v02a_r347_machine_class.py` passes with
  `.venv` inside the checkout (this cloud checkout has one: `/home/user/openflowsheet/.venv`), plus a unit test that
  the filter keeps the interpreter's site-packages and drops `ROOT/src`.

## (c) Reused assertion ids W27-A20…A22
- `docs/derivations/M06-W27-registration.md:712-714` defines W27-A20 (sample re-draw), A21 (cards), A22 (prompt).
  Amendment 3 (§22, `:1306`, `:1372-1374`, `:1393-1396`) defines W27-A20…A22 again for the surrogate states.
  Highest id in use: W27-A79. Tests: `tests/test_m06_w27_coverage.py:434-510` (Amendment 3) and `:843-` (sample).
- Fix: an erratum renaming Amendment 3's three ids to W27-A80…A82 in the registration prose (dated erratum note in
  §22) and in the test names/comments. **Constraint:** no hashed committed artifact may change
  (`registration.json`, `dry_illustration.json`, `coverage.json`, campaign records, preflight pins). If the ids occur
  inside such JSON (e.g. state labels `A20-e`), leave the JSON as is and state in the erratum that those labels are
  the Amendment 3 ids now named A80…A82. Exit test: `PYTHONPATH=src .venv/bin/python
  docs/derivations/scripts/m06_w27_registration.py --check` passes; the touched tests pass; a test asserting that each
  W27-A id is defined once in the registration's assertion tables.

## (d) Milestone 0: F3 and the schema `$id` move
- F3 is already closed: T08's manifest is in the harvest since the alpha (`tests/test_m07a_harvest.py:1-10`, :28,
  :85; `scripts/t08_support_matrix.py:478-482`). Tick the box in `docs/V02_STATE.md` "Milestone 0" with that pointer.
- The `$id` move (R-149, `docs/decision-register.md:3470`; R-185 `:4245`) changes every schema's identity — a frozen
  interface (CLAUDE.md: changes only by a design-lane ADR). Not done here; recorded as a v0.3 backlog item with its
  trigger (first v0.3 schema change). Exit: the V02_STATE line says so; no schema file changes.

## (e) Refresh `docs/progress.md`
- `docs/progress.md` "Start here" (:14-26) is dated 8 October 2026 and describes mid-v0.2. Rewrite "Start here" and
  "Last updated" to the current position: 0.2.0 released (tag `v0.2.0` → `5c82b4c`), M01–M07 merged, the cloud queue
  (C1, C2, C3, S01, L01, S02) and where its state lives (`docs/V02_STATE.md`, `docs/CLOUD_WORK.md`). Keep the
  Baseline table; the hashes are checked by `tests/test_document_hashes.py` — run it. Do not edit history sections.

## Out of scope
Any change to numerics, records, registered JSON, schemas, or the frozen interfaces. The F7 `job_id` fix (local L1).

## Agent rules
Context cap about 120k; at the cap commit, write a handoff of ≤ 30 lines to `docs/briefs/C3-handoff.md`, stop.
Report ≤ 150 words. Defensible choices: one `DECISION:` line each in `docs/C3_DECISIONS.md`.
