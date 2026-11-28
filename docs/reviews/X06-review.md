# X06 review (design lane, single `reviewer` pass, with the X06 ruling batch)

Reviewed: `wp/X06` at `020b7b72` (merge base `aa5822ac`; 117 files, +11260/-380) against ADR 0078 (D1 to D6,
E-X06-1 to 24, the R1 section), `docs/X06_DECISIONS.md` (WO1-* to WO5-*, R1) and the evidence manifest at
`a657d29d`. Brief: `docs/briefs/X06-reviewer.md`. Date 2026-11-27.

## Verdict

**Not ready to merge; sound in its core, one fix round.** The guard (D1), the branch model and its races (D2), the
`user.` bundle check (R1-1) and the delegation rule (D5.3) are correct as built, and no registered policy's behaviour
or released number moved. Two must-fix findings stand: a public serving path that bypasses D5's remote refusal, and a
support envelope that still declares MCP over HTTP unsupported. Both known reds are ruled below (Q26: admit by full
path; descriptions: eight approved as they stand, three with edits). The fix round is one Opus work order.

Run by this review, in the worktree (logs `~/.cache/line06/x06rev/`): `tests/test_x06_*.py`, `test_t07_q26.py`,
`test_t08_w2_description_reviews.py`, `test_t07_authz.py`: 147 passed, 2 failed (exactly the two known reds). Bundle
gate: 63 bundles, 60 ok, digest `b42b1ec439d1683c` (unchanged). F0 and the full surface battery not re-run (the build
lane's numbers stand).

## Findings

### Must fix

**M1. `bindings.http.serve` and `bindings.web.serve` serve the in-band writes beyond loopback without the D5.3 refusal.**
`src/openflowsheet/application/bindings/http.py:456` and `bindings/web.py:152` are public functions that serve
`create_app(owner)` (all nine X06 operations over REST, the four `Administration` ones included) on any host with
`allow_remote=True`, and never set `owner.serving_remote`; only `serving.serve_http` sets it
(`serving.py:166`). Scenario: a Python caller runs `http.serve(owner, host="0.0.0.0", allow_remote=True)` on a project
whose operator switched administration on; `grant_capability` over plain HTTP succeeds, which ADR 0078's title and D5.3
forbid ("never on a no-TLS remote server", Q3 "no override in 0.6"). E-X06-19 does not see it: its tests mark the owner
by hand or go through `serve_http`. The CLI no longer calls either function (WO1-1). Fix: delete both (no shims; the
interface is not frozen), retarget `tests/test_t07_w6a_http.py:717-724` to `serving.serve_http` (the same `ValueError`
for a non-loopback host without `allow_remote`), and fix the docstrings that still name them (`http.run`,
`bindings/web.py` module text). This is also ruling 6's first half.

**M2. The support envelope and the generated support matrix still say MCP over HTTP is unsupported, backed by a vacuous
test.** `benchmarks/t08/support_envelope.yaml:490-499` (U08: capability "Resume, MCP over HTTP, ...", outcome "no HTTP
route serves MCP"), the interfaces row at `:294` ("HTTP (`/v1`) and MCP over stdio") and `docs/support-matrix.md:21`
contradict the shipped `/mcp` and the user guide (`docs-site/guide/interfaces.md:13, 27`). The evidence test
`tests/test_t08_w2_unsupported.py:183` (`test_u08_mcp_is_not_served_over_http`) checks only `OPERATIONS` rows, not the
served application, so it passes while `/mcp` is served. WO2-9 left this for WO5; WO5 did not take it. Fix: U08's
capability "Resume, the benchmark-registered solve policies that are not offered" (plus ruling 4's text); its outcome
loses "no HTTP route serves MCP"; remove the test (its premise is what D1 reverses, WO2-9's precedent) and say so in
the module docstring; the interfaces row reads "... HTTP (`/v1`), and MCP over stdio and over streamable HTTP at `/mcp`
of `serve-http` (ADR 0078 D1) ..." with `tests/test_x06_mcp_http.py::test_e_x06_2_tools_list_over_http_is_stdios_and_the_registered_digest`
as evidence; regenerate `docs/support-matrix.md` (`scripts/t08_support_matrix.py`).

### Should fix

**S1. The in-band writes judge the caller and the switch on a policy read before the write transaction.**
`administration_service.py:101, 118` (grant: `caller`, `delegation_refusal`), `:163, 174` (revoke: `caller` captured
outside, used inside `remove`), `:251` (switch) all read `policy.current()` before `store.writing()` (`:287`);
`change_policy` re-reads the file under `BEGIN IMMEDIATE`, but `apply` never re-resolves the caller from it. Scenario:
the operator runs `project revoke --capability cap-admin` (or `project administration off`) while an in-band grant by
`cap-admin` is between its check and its write; the revoke commits first, the grant then lands, and the minted
capability survives the revocation of its maker (or the switch-off). Not an escalation beyond the caller's own rights,
but it breaks "a revocation takes effect" for a call that commits after it. Fix: in each `apply` closure (or once in
`_write`, given the policy `change_policy` read), re-resolve the caller in that policy by `(capability_id,
token_sha256)` (LOCAL_OWNER unchanged; absent: `_RefusedError("unauthenticated", ...)`), refuse
`administration_disabled` if the switch is off there, and re-run `delegation_refusal` / `revoke_refusal` against the
re-resolved caller. Test: a hook between check and write (monkeypatch `authz.read_policy` to revoke the caller, or to
switch off, first) gives the refusal and leaves the file and ledger unchanged.

**S2. E-X06-18's leak test grants only over REST.** `tests/test_x06_administration.py:459-510` makes the grant through
`POST /v1/policy/grants`; MCP over HTTP and stdio are used only for `get_project`, so a token logged by the MCP
binding's result path (`TextContent` plus `structuredContent`) would pass. Fix: inside the same `caplog` (DEBUG) and
`capfd` capture, grant once per carrier (REST, MCP over HTTP via `mcp_call`, MCP stdio via the in-memory session with
arguments, in-process), and assert each token and `prt_` absent from the store, WAL, policy file, logs and output.

**S3. E-X06-13's `optimize` half has no test.** The manifest records it "NOT RUN", but nothing exists that could run
(`grep nlp tests/test_x06_solve_policies.py`: none). Fix: write it (an `optimize` record whose solve body names
`user.copy` reproduces in a fresh project with the same verdict as under `T06-revision-v2`), guarded by
`pytest.importorskip` of the `nlp` extra, and run it wherever the extra is installed. Until it has run, the manifest
says "not run" and the merge card states it.

### Notes

- N1. `revision_service.py:95, 163`: after `ASSIGNED_ID_ATTEMPTS` (8) re-assignments an auto id ends `rejected
  revision_id_taken`, an id the caller never named. Reachable only with nine or more concurrent commits on distinct
  refs. Leave; if it is ever seen, answer it as the retryable `conflict` family instead.
- N2. A delegated grant may name any existing principal (D5.3 excludes only `local-owner`), so its acts are audited
  under that principal and share its ledger scope; the capability id tells them apart and the granter already holds
  `policy`. Keep for 0.6; revisit if a principal ever carries authority of its own.
- N3. `service_core.py:77-81`: `acting_as` copies `serving_remote` by value, so views share it only because
  `serve_http` sets it before serving. Fine today; a later toggle would not reach live views.
- N4. `solve_policy_registry.load` (`:70`) reads and hashes every registered policy file on each `user.` admission and
  each runner `resolve`: linear in the registrations. Fine at expected sizes.
- N5. `scripts/t07_schema_fixtures.py:182` `_pin_threads` still writes `os.environ` for the process; WO5-1 scoped its
  three callers. Code-health: let the generator restore the environment itself, so a fourth caller cannot leak.
- Checked and sound: the guard order and its 401/403/405/413 documents; caller isolation under 50 concurrent calls;
  revocation on the next HTTP request (real server); bearer only from the header; `branch` omitted when absent or
  `head` (E-X06-7 golden list of 303 real requests); the ref check before the id check in the commit loop, so a head
  conflict stays a conflict; `list_branches` bounds (`branches/` to `branches0`); write-once registration by hash; the
  `user.` branch of `_cross_check_solve_path` (15 forgeries, none raises; `fullmatch`; one candidate);
  `delegation_refusal` (rights, both limits, expiry; fixed-width timestamps make the string comparison exact); token
  kept out of the ledger (`token: null` stored), audit and policy file.

## Rulings on the batch

1. **R-088 Q26 (WO4 STOP): admit by full path. Keep the members; change the test.** These are scalars, which Q26 does
   not forbid but inventories: three budget ceilings of a grant (the kind of `budgets/wall_time_s`, already admitted,
   and bounded by the caller's own, D5.3) and a declaration only the gauge display units read (ADR 0075 D6; no run,
   certificate or replay reads it). None is a matrix, a map or a state. In `tests/test_t07_q26.py`, beside
   `SOLVE_POLICY_SCALARS`:
   ```python
   #: X06 (ADR 0078 D5.2; X06 review ruling 1): the in-band administration requests' numeric scalars, by full
   #: path: a grant's budget ceilings and a display-only ambient declaration.
   ADMINISTRATION_SCALARS = frozenset(
       {
           ("grant_capability", "limits/default_wall_time_s"),
           ("grant_capability", "limits/max_wall_time_s"),
           ("grant_capability", "limits/max_active_jobs"),
           ("set_ambient_pressure", "value"),
       }
   )
   ```
   and in `test_t07_q26_no_external_state`, after `scalars = {...}` is built and before `names`:
   ```python
   operations = {operation for operation, _ in ADMINISTRATION_SCALARS}
   assert {s for s in scalars if s[0] in operations} == ADMINISTRATION_SCALARS
   scalars -= ADMINISTRATION_SCALARS
   ```
   Docstring paragraph, after the X06 one: "**X06 administration (ADR 0078 D5.2; X06 review ruling 1).**
   `grant_capability`'s `limits/default_wall_time_s`, `limits/max_wall_time_s` and `limits/max_active_jobs` are a
   grant's budget ceilings, the kind of `budgets/wall_time_s`, bounded by the caller's own (D5.3);
   `set_ambient_pressure`'s `value` is a declaration only the gauge display units read (ADR 0075 D6), never a run, a
   certificate or a replay. None is a matrix, a map or a state. They are pinned by full path
   (`ADMINISTRATION_SCALARS`) and kept out of the name inventory." A clarification within D5.2 as Accepted (it names
   these members): no ADR decision changes, no user card; the orchestrator may add one register row in R-1075's form.
2. **Description texts (design lane; the human review stays the user's).** Approved as they stand, at these SHA-256:
   `create_branch` `c5a5108a…99a6`, `delete_branch` `0220874b…ba3c`, `list_branches` `73b23d6b…083f`,
   `get_solve_policy` `d471d354…b185a`, `get_policy` `e323b09a…dca74`, `grant_capability` `c85ad53d…8e87f`,
   `revoke_capability` `a2b60341…0194`, `set_ambient_pressure` `e48673d1…96573` (full hashes: `REVIEW.json` at
   `020b7b72`). Approved with edits (exact replacements; everything else byte for byte, the generated target table
   untouched):
   - `commit_change` (1497 characters, SHA-256 `b5b0dea1bdb46f635d77ba9b6c5009bc73f8b1a94a828168b1e89344f68fd359`):
     `Effect: a new revision and a moved head, only on status "committed". Right needed: draft. A "branch" commit moves
     only that branch.` becomes `Effect: a new revision and a moved head, or only the "branch" moved, on status
     "committed" only. Right needed: draft.`; and `It never solves; a commit` becomes `It never solves or verifies; a
     commit`.
   - `preview_change` (1352, `8c5fe94f0e21a858719211a373c10d64f3618d31c2ff908c4859f44b5bf9adf8`): `commit with
     commit_change, which checks the head again.` becomes `commit with commit_change, which checks the head or branch
     tip again.`
   - `register_solve_policy` (1429, `a246826c9c6df511e33f7679b459b52ab825f916dbedb3a4cbd7f2abda61ce7c`): `the schema;
     the id` becomes `the schema; that the document reads back unchanged; the id`, and `; every member as the solver
     reads it, and every open value (initializer_chain entries, linear_solver, the kinds of residual_tolerances and
     scales, recycle) against the solver's registries; else` becomes `; every open value against the solver's
     registries (initializer_chain entries; the kinds of residual_tolerances and scales; recycle.policy_id),
     linear_solver equal to the registered one, and no recycle.tear_streams; else`. Reason: WO3-1's strict readings
     (exact `linear_solver`, `tear_streams` refused) are what a caller trips on; the text now says them.
   The fix round applies the three edits, checks the three hashes above, and records the design-lane review of all
   eleven as `reviewed` at their final hashes citing this file.
3. **WO3b-1 (40th scalar `policy/admissibility_epsilon`): keep.** A strictly positive constant read by the search's
   admissibility test, the class of the other 39; the verifier reads no solve policy (E-X06-14). The R1 count was
   short by one; "40" in the R1 section and R-1075 is right.
4. **WO4b-1 (U08 test removed): change.** The removed test still pinned a true limitation: ADR 0078 "does not
   establish" in-band `install`, `publish`, executor settings or project creation, and the switch stays operator-only.
   Removing it outright is a relaxed check. Restore it re-scoped as
   `test_u08_no_operation_installs_publishes_or_sets_executor_or_switch`: the names `install`, `publish`,
   `set_policy`, `register_policy`, `policy` are not in `OPERATIONS`, and no request schema reachable from
   `OPERATIONS` has a member named `executor`, `administration` or `in_band` at any depth. U08's capability gains "in-band
   install, publish, executor settings, the administration switch and project creation" with that test as evidence.
5. **WO4b-2 (E-X06-16 on operator-written policies): keep.** With no committed `project-policy.json`, files written by
   the operator commands are the honest population, and the test exercises the omission rule both ways. Optional, not
   required: commit one policy file written at `aa5822ac` and round-trip it.
6. **WO1-1: remove the two unused serve functions** (M1). **Stateless `tools/call` without `initialize`: keep.** There
   is no session to require it, the bearer is still required, and nothing `initialize` negotiates changes a tool's
   meaning; the Q9 test pins the answer.
7. **WO2-4: keep.** E-X06-8 as Accepted requires a branch commit and a head commit from one snapshot both to succeed;
   the loop re-assigns only an id the caller did not name, only while its ref is unmoved, and re-validates. It changes
   nothing where no branch exists. No user card. **WO2-7: change.** One fact was dropped ("or verifies"); ruling 2's
   edit restores it within 1500 characters.
8. **WO5-1: keep** (test isolation only; no generated fixture moved). Root cause as N5.
9. **`render_error` on a message without its code prefix: code-health, not X06.** Every X06 refusal message leads
   with its code (checked: branch, solve-policy, administration and origin refusals), so no X06 path renders the "no
   message code" text. File it for the next code-health batch.

## Fix-round work order (one Opus engineer, `wp/X06`)

1. M1: delete `bindings.http.serve` and `bindings.web.serve`; retarget `tests/test_t07_w6a_http.py:717-724` to
   `serving.serve_http`; fix the docstrings that name them. Check: `grep -n "^def serve(" src/openflowsheet/application/bindings/*.py` empty.
2. M2 and ruling 4: the U08 and interfaces rows of `benchmarks/t08/support_envelope.yaml`, the U08 tests and
   docstring in `tests/test_t08_w2_unsupported.py`, regenerate `docs/support-matrix.md`.
3. Ruling 1: `ADMINISTRATION_SCALARS`, the two assertions and the docstring paragraph in `tests/test_t07_q26.py`;
   `test_t07_q26.py` 6 passed.
4. Ruling 2: apply the three text edits; verify the three hashes; update `REVIEW.json` (hashes, characters, design-lane
   `reviewed` for all eleven citing `docs/reviews/X06-review.md`, human `pending`); re-pin `X06_SERVED_SHA256`,
   `X06_FILE_SHA256`, c_12's `D_12` and any R4-G3 row the texts reach; `without_x06` must still give F3's `f7ec3c94…`.
   `test_every_description_is_reviewed_by_both_lanes` then fails only on the eleven human items.
5. S1: re-resolve the caller and the switch inside the write transaction; the hook test.
6. S2: the per-carrier grant in E-X06-18.
7. S3: the `optimize` half of E-X06-13, `importorskip`-guarded; run it where the `nlp` extra exists or leave it "not
   run" in the manifest.
8. Close: surface suites, `tests/test_x06_*.py`, MSG and doc-page tests, ruff, format, mypy; bundle gate (63, 60,
   `b42b1ec439d1683c`); F0 PASS; a new evidence manifest at the fix commit; one `X06_DECISIONS.md` section listing
   each item with its commit.

## What waits for the user

- The human review of the eleven description texts (`REVIEW.json`, the user's lane); the gate stays red until then.
- The X06 merge card, which also moves ADR 0019 Amendment 18 from Proposed. No ruling here changes an Accepted ADR
  decision, so no other card is needed. If S3 cannot run on any available host, the card states E-X06-13's `optimize`
  half as not run.

## Not examined

The conformance scenario's six-client steps (`tests/test_t07_conformance.py`) beyond the decisions file; the E-X06-8
race tests and E-X06-14 beyond their names and the code they exercise; `policy_validation`'s registries (WO3-1) beyond
the decisions file; the schema-fixture generator and `scripts/m07a_rc.py`; the user guide, CHANGELOG and ADR 0019
Amendment 18 prose; the web shell. F0 was not re-run.
