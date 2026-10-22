# C7 — `main` returns to a `.dev0` version and the working envelope after 0.2.0 (build lane, `opus-engineer`)

Branch `wp/C7` from `wp/C4` `7cc7807` (contains S02; S02 and C4 merge first). Register numbering: **R-556…R-559** only if a ruling is needed
(questions go to `docs/C7_DECISIONS.md` as `QUESTION:`).

## The question
R-460 (`docs/decision-register.md:9409-9440`): "the first D2.4 change after a tag sets a `.dev0` after the tagged
version and returns the envelope [to its working form]", enforced by `tests/test_v02_main_version.py`. 0.2.0 was
tagged at `5c82b4c`; S01 (and later packages) changed D2.4 paths on `main`, yet `pyproject.toml:12` and
`src/openflowsheet/__init__.py:14` still say `0.2.0` and the envelope is pinned `v0.2-envelope-1`. The test does not
catch it because `RELEASED` (`tests/test_v02_main_version.py:25`) lists only `0.2.0a1`.

## Do
1. Add `"0.2.0": <the v0.2.0 tag's commit>` to `RELEASED` (read it with `git rev-list -n1 v0.2.0`; the tag may be
   absent in a fresh clone — fetch tags or use `5c82b4c…` from `docs/V02_STATE.md`, and state which). Show the test now
   fails on `main` (negative control).
2. Set the version to `0.3.0.dev0` in B-WO10-4's version-carrying set (find it: grep the register for B-WO10-4 /
   the alpha-main rulings `docs/design/V02-alpha-main-rulings.md` §3 E7, AM-40–AM-42). DECISION line: label
   `0.3.0.dev0` (v0.3 is in progress; sorts after 0.2.0). Alternative `0.2.1.dev0`. The label is Frank's to change.
3. Return the envelope to its working form per MR-3 / R-460 (`v0.2-envelope-dev`-style id and dev label — read what
   the rule and `ENVELOPE_ID` in `scripts/t08_support_matrix.py` require for the post-0.2.0 cycle; if the working id
   for the v0.3 cycle is not registered, choose by analogy with a DECISION line and a QUESTION).
4. The re-takes R-460 names ("re-take W27's coverage"; R-458 G10) — do them only if their committed records embed the
   version and a test fails without the re-take; each re-take is digest-only where possible, with its reason logged.
   Anything needing the archive or the reactor/nlp environments goes to `docs/C7_DECISIONS.md` as blocked.

## Exit test
`tests/test_v02_main_version.py` passes with `0.2.0` in `RELEASED`; the touched tests pass (version, envelope,
support matrix, W27 coverage, M07 ledger, server version); ruff/format/mypy clean.

## Out of scope
Any release, tag or publish; changing released records.
