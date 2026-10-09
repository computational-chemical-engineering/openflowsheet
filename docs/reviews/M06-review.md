# M06 review — the diagnostic web shell (W26) and the W27 benchmark machinery, against `docs/design/M06-web-shell.md`, ADR 0030 and ADR 0019 Amendment 3

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-10-08. This is the review half of work order WO-13.
**Reviewed at:** `wp/M06-build` = `98da494`. The merge base on `main` is `eaedc1c`. The range is 43 commits and
182 files.
**Read against:** the design note §§2, 4–8, 9, 10, 11 (G1–G16) and 12; ADR 0030; ADR 0019 Amendment 3; register
entries R-170…R-179, R-192, R-193, R-194 and R-216; and the W27 registration (§§10–12, plus the claims template).
**Run here:** one probe, P1 (§2 F4). It is a Node script that imports `apps/web/js/h.js` and
`screens/common.js` from this tree. I also read the failed-job logs of the CI run below (`gh run view --log-failed`).
The test suite was not re-run. The numbers in the brief (gate 7447 passed / 52
skipped, Node 91/91, browser 31 passed ×10, and G2–G7, G11, G13–G15) are taken as reported. I spot-checked the
tests that produce them: G3, G4, G5, G6, G8, G11 and the expander.
**CI:** run `37825384881` on `98da494` **failed**.

| Job | Result |
| --- | --- |
| `check (ubuntu-24.04-arm)` | success |
| `check (ubuntu-latest)` | failure: 2 failed, 7400 passed, 97 skipped; Node 91/91 ran and passed |
| `default-install` | failure: 2 failed, 7152 passed, 283 skipped |

Every dispatch-only job was skipped, `dist` and `clean-install` among them (see F1). The failures are F2a–F2c.

---

## 1. Verdict

**Matches, with must-fixes.** The contract amendment is built as designed, and it is inert where the design says
it must be:
- the index sits beside the report, never inside it;
- the trace/analyse split keeps every argument;
- `elements` stays out of `TransactionResult.diff`;
- `list_audit` is `cancel_job`'s authorization rule exactly, and its join's precondition is tested first.

The shell keeps its central invariants by construction:
- one `fetch`;
- a generated route table;
- 17 operations, checked both statically and on a live request log;
- text-only rendering behind a strict CSP.

The tests mostly pin the design's numbers. They do not just check that the code ran. Two expander tests are worth
naming: the expander is tested against the server's own projections, not a hand-made mock, and the R3 attribution
is cross-checked against the legacy binder on 8 revisions.

Three must-fixes remain:
- G10 has no measurement;
- the CI gate is red: three small test-side defects that the reference host cannot show (F2);
- Amendment 3's normative text does not yet say what was built.

No product-code defect blocks.

---

## 2. Findings

Severity is **must-fix** (before `tested`/Accepted), **should-fix** (before the next consumer depends on it) or
**note**.

**F1 — must-fix (evidence). G10 has not been measured.**
- *Evidence:* the G10 step ("the installed wheel serves the web shell", `.github/workflows/ci.yml` ~l. 615) sits in
  the `dist`/`clean-install` chain. That chain runs only on `workflow_dispatch` with `rc_distribution` or `rc`
  (`ci.yml:513`). In run `37825384881` both jobs are `skipped`, and the brief lists no G10 number.
- *What the tests do show:* the packaging tests prove that the package-data globs cover `apps/web/` exactly
  (`tests/test_t08_w4_package_data.py::test_the_web_shell_holds_no_link_and_nothing_outside_the_packaged_globs`).
  `test_a_real_server_serves_the_shell` serves the checkout. Neither installs a wheel.
- *Fix:* dispatch `rc_distribution` on the tip, or run its local equivalent (build the wheel → clean venv with the
  server extra at the lock → `scripts/m06_web_serve_check.py` from outside the tree). Record the commands and
  output in the M06 manifest. Until then, M06 is not `tested` on G1–G15.

**F2 — must-fix (gate). G12 is red: CI run `37825384881` failed on two jobs.** Before the three failures, two
open questions this run did settle:
- Chrome starts on `ubuntu-latest` without `--no-sandbox`: 29 of the module's 31 browser tests passed there.
- The Node step ran on both legs: 91/91, not skipped.

The failures:

- **F2a — the smoke test pins 17 digits of a fresh solve.**
  - *Evidence:*
    `test_g11_every_screen_renders_and_reaches_only_the_contract[supervisor-c:/job/job-000001/streams]` and
    `[…/job/job-000001/row/U-HEAT%3AHEAT-duty]` fail with `AssertionError: 31487.641739605908`
    (`tests/test_m06_browser_smoke.py:395`). The marker list is at `:362` and `:364`.
  - *Cause:* the shell fixture re-solves NET-02 on the runner (`build_fixture_project`, `:264`). The short marker
    `>31487.6` passed and only the full-precision text was absent, so the element and its formatting are there
    and only the trailing digits of the value differ. The x86-64 runners are already recorded as disagreeing on
    converged floats (`ci.yml`, the comment above the `check` matrix). "10 of 10 green" was measured on the
    reference host only.
  - *Fix:* read the expected full value from the run the test just produced (job-000001's
    `solution-state.json` in the shell's store, `repr(value)`) and assert that text. Keep `>31487.6` as the G7
    marker. Do not loosen G7 itself: the Node tests assert `31487.641739605908` against committed fixture bytes,
    which is exact and correct.
- **F2b — the route-table check needs the server extra.**
  - *Evidence:* in `default-install`, `tests/test_m06_static_scan.py::test_the_route_table_is_generated_from_the_http_rows`
    fails with `ModuleNotFoundError: uvicorn`. `scripts/m06_web_routes.py:24` imports
    `bindings.http.HTTP_OPERATIONS`.
  - *Fix:* derive the rows from `operations.OPERATIONS` (an HTTP row is one whose transports include `http`;
    the binding adds nothing, per R-096), so the static scan holds without the extra.
  - *Alternative:* `importorskip("uvicorn")` in that test. This is weaker, because the default install would no
    longer check the table.
- **F2c — two envelope evidence references are not collected without the extra.**
  - *Evidence:* in `default-install`, `tests/test_t08_w2_support_envelope.py::test_a22_every_evidence_reference_resolves`
    reports `test node not collected` for
    `tests/test_m06_http_contract.py::test_g2_every_ui_operation_answers_schema_valid_over_http` (interfaces
    axis) and for L-WEB-2's `tests/test_m06_wo4_serving.py::test_a_shell_file_is_served_with_its_type_and_the_shell_headers`.
  - *Cause:* both modules skip at module level (`pytest.importorskip("starlette")`, `:43` and `:30`), so pytest
    collects nothing from them.
  - *Fix:* do one of the following:
    - move the skip into a fixture, so the nodes are collected and skipped;
    - or cite collectable evidence or the M06 manifest's check ids, as T07's rows do with `check:T07.G11`.

  The first is smaller, and it keeps A22 meaningful.

After the fixes, record the green run id and both legs' Node and browser lines in the manifest.

**F3 — must-fix (text, before Accepted). Amendment 3 does not yet describe what was built.** It moves to Accepted on
this review, so its normative text has to be right.
- **(a)** A3.1 makes `rows`/`columns` nullable only on the unroutable branch. On the routed branch, a declaration
  that cannot be traced now yields the UNSUPPORTED report with `rows`/`columns: null`
  (`revision_run.py:235` `traced_analysis`; `tests/test_m06_wo1_structure_index.py::test_an_untraceable_declaration_has_no_index`).
  That is the right behaviour, but a client of the contract must be told. Amend A3.1 to: "null on either branch
  when no declaration was traced".
- **(b)** Neither A3.2 nor its *Unchanged* bullet says that the served MCP tool-list digest moves (R-192:
  `171dd768…` → `6c4375b4…`). The design note §2 item 2 ("every registered digest stays bit-identical") is
  superseded on this point. Add one sentence citing R-192 and the decomposition test to A3.2, to the *Acceptance
  evidence*, to `docs/interfaces-frozen.md`'s A3.2 paragraph (whose neighbouring T08 paragraph still names
  `171dd768…` as the served list), and as an "as built" line at the design note's §2.
- **(c)** Update the status line (Proposed 2026-10-06 → approved by Frank 2026-10-08; Accepted on this review).

**F4 — should-fix (security hardening). `h` accepts any object with a string `t` as a tree, so the "only whitelisted
elements and attributes" invariant is held by the callers, not by `h.js`.**
- *Evidence:*
  - `apps/web/js/h.js:71` pushes any `{t: string}` child unchecked;
  - `create()` (`h.js:92–108`) sets every key of `tree.p` without the whitelist;
  - `screens/common.js:143` and `screens/equation.js:197` pass any `cell.t === "td"` object straight through.
- *Measured (P1):*
  - `h("td", null, JSON.parse('{"t":"img","p":{"src":"x","onerror":"alert(1)"},"c":[]}'))` is accepted;
  - `table(["a"], [[{t:"td", p:{onclick:"x", style:"color:red"}, c:["hi"]}]])` passes its `p` through.
- *Why this is not a must-fix:* I found no screen that passes a raw server object as a child. Every one I checked
  coerces with `text()`, `id()`, `String`, `JSON.stringify` or `jsonTree`. The CSP would block script execution
  even so.
- *Why it still matters:* a forged element could still navigate (`<meta http-equiv=refresh>`) or draw an outside
  link. ADR 0030 D1 says the builder *can only* create whitelisted nodes, and today one careless
  `h("td", null, value)` over a revision member makes that false.
- *Fix:*
  - brand trees in `h()` (a module-private `Symbol` key, or a `WeakSet` of created nodes);
  - refuse unbranded objects in `children()`, and re-check the tag in `create()`;
  - make `table`/`equation` test the brand, not `.t === "td"`;
  - add a Node test that a `JSON.parse`d `{t,p,c}` child throws.

**F5 — should-fix (design lane, before WO-17's canaries). The W27 registration needs an erratum and three
ratifications.**
- *Erratum:* `docs/derivations/M06-W27-registration.md:620` (W27-R57's claims template) says "the ten of
  `access_report.json`", but the report holds 9 `inaccessible_assets`. The 9 cover every item design note §9
  Tier 0 item 2 names: the fine-tuned models, prompts and workflow, the scoring harness, and the 82-split
  binding.
- *Ratifications:* `benchmarks/m06/w27/scorer.py:16–24` takes three choices where the registration is silent:
  1. the naming of *available* items for W27-R41;
  2. a quantity at more than one time point is unjudged;
  3. a reference component the agent's product stream does not carry counts as 0 mol/s.

  These are scoring semantics, which is the specifier's call (CLAUDE.md: the build lane does not resolve a
  scientific ambiguity by choosing). The scorer does report each one in the score, which is right.
- *My recommendation (needs a decision):* ratify all three.
  - Choice 2 is conservative.
  - Choice 3 is almost moot: when the W27-R44 component check passes, every chemical component is in the
    revision, and every `nTP-v1` connection carries all of them.
  - Choice 1 is mechanical.
- *Fix:* one registration amendment covering the erratum and the three rules. P2 then re-pins the registration's
  SHA-256 (`preflight.py:44–52`), as the module already provides.

**F6 — should-fix (process, WO-13). The M06 manifest has to be harvested.**
- *Evidence:* T08.A21's harvest reads every `evidence/**/manifest.json` except T08's
  (`scripts/t08_support_matrix.py:436–456`). Each `limitations[]` entry and each non-`pass` check must be
  classified in `support_envelope.yaml#harvest`, keyed by text SHA-256. That includes G16 (`planned`), and G10
  if it is still unmeasured.
- *Fix:*
  - write the manifest's limitations as exactly L-WEB-1…4, plus the restated U14 if it is listed;
  - add their `harvest:` entries in the same commit, and classify G16 as M07's;
  - run `scripts/t08_support_matrix.py --check`.
- *On merge:* `support_envelope.yaml` and `docs/support-matrix.md` will conflict with M01's model rows. Regenerate
  with `--emit` after resolving the YAML; do not hand-merge the Markdown.
- *Also:* the comment at `t08_support_matrix.py:211–212` ("pending the session's record of that move on the v0.1
  envelope") is stale since R-193.

**F7 — should-fix. G15's preflight is measured without P1.**
- *Evidence:* P1 reads `docs/V02_DECISIONS.md` for `- **W27 Tier 1 approved**` (`preflight.py:41–42`). That line
  is on `main` (l. 191) but not on the branch, so P2–P8 are what passed.
- *Fix:* re-run the dry-run preflight on the merge commit, or after merging `main` into the branch. Record P1–P8,
  and record that P6/P7 were met by stub canaries. The real campaign's P7 then refuses stub canaries by model id
  and Claude Code version, which is the right guard.

**F8 — should-fix (documentation). The design note needs an "as built" addendum.** The note is the normative text
for ADR 0030 and does not yet say:
- §5.1's whitelist gains `autocomplete`;
- §5.4's guard is a same-pointer check;
- §5.5 now lists the lower-case certificate results;
- §6's per-screen reads are wider (still the 17);
- §8 A6's harness is the DevTools protocol over a pipe;
- `js/frame.js` exists.

`apps/web/js/text.js:66–70` still says "pending design-lane confirmation". This review confirms the mapping (§3),
so that comment should say so.

**F9 — note. The G1 module test skips when run alone.** `tests/test_m06_browser_smoke.py:711` skips "needs the
module's other tests to have run", even under `OPENFLOWSHEET_REQUIRE_BROWSER=1`. In the gate it runs last and
passes. Under `-k` or a reordering plugin, the dynamic "exactly the 17" check would skip silently. Prefer `fail`
when `REQUIRE_BROWSER=1`.

**F10 — note. Long-poll cost on the server.**
- An aborted `wait_job` ends in the browser, but its server thread runs until `timeout_s` (20 s). Three things
  re-issue the call on a live run screen: navigation, the numbers toggle (`main.js:107–111` calls `navigate()`),
  and a re-render.
- One user toggling quickly can therefore hold several worker threads for up to 20 s each.
- This is acceptable for the local single-user model. If the HTTP binding ever serves more than one user, cap
  outstanding waits per principal there, not in the shell.
- "One outstanding call per view" is what §5.4 asked for, and `_not_overlapping` in the smoke test pins it.

**F11 — note. A boot token erases the remembered one.** `takeBootToken` calls `store.set(token, false)`
(`auth.js:60`), which removes a token remembered in `localStorage` (`auth.js:39`). That is harmless, but
surprising: opening a `?token=` link signs the browser out of "remember".

**F12 — note. `element_diff` edge cases.** These are consistent with the rule as written.
- A member absent from one revision and `[]` in the other gives `{id: null, change: "changed"}` while the coarse
  diff says `added`.
- Values compare by Python `==`, so `1`, `1.0` and `true` are equal. That is the same as the pre-existing
  `semantic_diff`, so the two diffs stay consistent. It does mean a content-hash change from `1` to `true` is
  invisible to both.

**F13 — note.** `fmt(-0, "full")` prints `0`, not Python's `-0.0`. §5.5's "identical to Python's `repr`" holds
except for the sign of zero and for integer-valued floats, which JSON cannot distinguish anyway.

**F14 — note. R-192 and A49.** I agree with not editing `scripts/t08_rc.py`'s `R133_DESCRIPTIONS_SHA256`: it is a
0.1 release record. But `t08_rc.py surface` is now known-red on any v0.2 tree. Put "register v0.2's served
surface and retarget A49" on M07's list in `docs/progress.md`, so that a red A49 at the v0.2 RC is not waved
through as expected.

---

## 3. Rulings on the recorded deviations

| Deviation | Ruling |
| --- | --- |
| `autocomplete` added to h.js's whitelist | **Accepted.** §7 itself requires `autocomplete=off`; the §5.1 list omitted it. It carries no risk. |
| The literal-marker guard returns a same-pointer marker instead of `deepEqual` | **Accepted.** The projection always shows its target (`projection.py`: "the target itself is level 0 and is always shown"), so a view of `at` that is a marker of `at` can only be literal content. The check is stronger than `deepEqual`, saves a request, and the expander fixture built from real projections exercises it. |
| `js/frame.js` added | **Accepted.** The header and error panel are pure views, testable in Node; nothing new reaches the network. |
| A wrong method on `/ui` gives 422, not 405 | **Accepted.** It is the binding's own `ApiError` mapping, and it carries the CSP (the middleware covers it). The design did not fix a code. Mention it in `docs/web-shell.md`. |
| Certificate labels: `pass`→ok, `fail`→bad, `unsupported`/`not_applicable`→none (`327edcd`) | **Confirmed.** Without it, §5.5's "every label not listed is bad" would paint every passing check red. `unsupported` → none matches §5.5's treatment of `NOT_RUN`, and the certificate-level pill (UNVERIFIED → warn) carries the judgement. Record it in §5.5 (F8). |
| Screens read beyond §6's table, within the 17 | **Accepted.** G1's invariant is the 17, and it is held statically and on the live log. The extra reads are necessary joins: a record's artifact id comes only from the bundle listing. List them in `docs/web-shell.md`. |
| Three bundle kinds have no published schema | **Accepted.** `NO_RECORD_SCHEMA` is a closed set and the test asserts equality with the observed kinds, so a fourth cannot slip in. |
| JSON trees open the top level only | **Accepted.** Adding `open` to the boolean attributes would be harmless if wanted later. |
| The browser harness drives Chrome over the DevTools protocol on a pipe instead of `--dump-dom` | **Accepted as §8 A6.** It is stronger: a readiness wait instead of a virtual-time race, real clicks, and console, CSP and dialog collection. It needs only the standard library, and it reads the same serialized DOM. R1's Playwright fallback is moot. |
| A routed declaration that cannot be traced gives `rows`/`columns: null` | **Accepted.** There is no declaration to index. Amend A3.1 (F3a). |
| The binder records specification pins per column (`b570179`) | **Accepted.** This is R3's sanctioned route: computed where the units are built and read only by `specification_rows`. G3 50/50 shows the reports did not move, and the independent cross-check against the legacy binder covers 8 revisions. |
| W27 code lives in `benchmarks/m06/w27/` | **Accepted.** Keeping code apart from the committed records is cleaner. R-194's U14 test pins paths named after the benchmark, and the harness's default runs root is under `openidaes450/runs/`, which U14 covers. |
| W27 scorer choices where the registration is silent | **Acceptable for the dry run. They must be ratified by registration amendment before the canaries (F5).** |
| The registration says "ten" inaccessible assets; nine are listed | **Erratum in the registration (F5). Nine is right.** |

---

## 4. The build lane's open questions

- **Is the protocol harness A6?** Yes (§3).
- **The G8 split, projected vs raw.**
  - The split is sound. G8's DOM criterion holds on the projected screens, because the server already replaces
    U+202E.
  - The shell's own `sanitize` is exercised where it matters: on the raw `revision.json` export
    (`test_g8_the_raw_revision_as_solved_renders_as_text`), with assertions on `<img`, `on*` attributes, the
    script count and console problems.
  - F4 is the remaining gap in that defence, and it lies in `h`, not in `sanitize`.
- **The CI browser wiring.** It is sound.
  - The `ubuntu-latest` match is correct for this matrix.
  - Chrome starts without `--no-sandbox`: 29 of the 31 browser tests passed on x86-64.
  - The two failures are the test's float pin (F2a), not the wiring.
  - The aarch64 leg skips the browser module, as designed.
- **R-192 and A49.** Correct, with F3b and F14.
- **Is G15's "preflight passes" met?** Not yet in full (F7). P1 needs the merge.
- **The envelope harvest for L-WEB-1…4.** See F6. Those rows are accurate as written.
- **Cancel and the long-poll.** One outstanding call per view is what §5.4 specified, and the smoke test pins it.
  The cancel POST is a second, independent request, and it works while the wait is outstanding
  (`test_cancel_stops_a_running_job`). See F10 for the server-side cost.

---

## 5. ADR 0030 and Amendment 3

- **ADR 0030** may move to Accepted once two things are recorded in the M06 manifest:
  - F1: G10 measured;
  - F2: F2a–F2c fixed and a green CI run on both legs and on `default-install`, with the Node step run and the
    browser module not skipped on x86-64.
- **ADR 0019 Amendment 3** may move to Accepted once F3's text corrections are committed, under the same F2
  condition. G3–G6 are met as reported.
- F4–F8 are not conditions of acceptance. F5 must close before WO-17's first canary.

---

## 6. Not examined

- The view code of most screens beyond spot checks (job, revision, history, compare and equation were read in
  part).
- The CSS, the token values and the contrast computation (G9 taken from its test).
- The W27 classifier maps, `facts.py`, `coverage.py`, `stubs.py`, `report.py` and the registration generator.
  Their content is the design lane's registration, which the `specifier` authored and reviewed.
- The acquisition script.
- The fixture generators.
- `docs/web-shell.md`, README and CHANGELOG.
- No test or gate was re-run; one Node probe (P1) was run.
