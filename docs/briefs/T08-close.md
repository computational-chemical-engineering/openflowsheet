# Brief — T08 close-out at `C` = `67c66d9`: ledger, records, manifest, ADR statuses, small fixes

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-02. **Branch:** `wp/T08`.
**Inputs:** `docs/reviews/T08-verdicts.md` at `C` = `67c66d98587f23bd7dfe8da28a8facccc92da21e` (`f22f3cf`: nine PASS,
V14 FAIL accepted by Frank in ADR 0021 D3; findings G4–G8 and two G3 residuals); `docs/t08-rc-record.md` (`51cd5ff`);
release spec §8.1 (what an RC needs, item 5 the `tested` manifest) and §9; `scripts/t07_evidence_manifest.py` (the
pattern for a manifest generator and its test); `docs/T08_DECISIONS.md`.

## Items (one commit each, `T08 close: …`)

1. **Ledger and CHANGELOG.** `docs/requirements.yaml`: V13 → PASS, V19 → PASS (as the verdict says); regenerate the
   CHANGELOG gate table (`v0_1_gate.py --markdown`), keeping its test green.
2. **G6 — where the small RC records live.** §8.1 item 4 puts them under `benchmarks/t08/rc/`, which the D2.4 tree check
   covers, so committing them after `C` would make every tag candidate differ from `C`. DECISION (session): commit
   them under `evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/rc/` (outside the D2.4 trees; next to the
   manifest, where the evidence convention already puts per-commit records); copy every small JSON/text record the RC
   record cites (not the large ensemble result files if > 1 MB — keep those hash-referenced under `artifacts/`) and
   make `docs/t08-rc-record.md`'s hashes resolve to them (a test). Write the one-paragraph release-spec amendment
   (**Amendment R7 1**, "transcribed by the build lane from verdict finding G6") moving §8.1 item 4's location.
3. **G4 — V19 (i) and ADR 0022.** Amendment **R7 2**: §4.9 (i) reads "Frank's selection recorded in ADR 0022" (the
   verdict's reading) instead of "ADR 0022 accepted". Mark **ADR 0022 Accepted** (its own condition, V19 PASS at `C`,
   now holds), pointing at the dossier's "Frank's statements, 2026-10-02".
4. **G5 — dossier tables.** Bring `docs/v02-real-chemistry-dossier.md`'s tables in line with Frank's statements: the
   property-database row (cross-check only), rows for `chemicals`/`thermo` and CoolProp/Cantera as M01's sources (status
   `needs_fact` for M01, licence MIT for both libraries' code; data provenance per value is M01's), status cells
   `needs_frank` → the statement's outcome, and the "items 6 and 7" vs "7 and 11" inconsistency (use the table's truth).
   Keep `test_t08_w3_v19_records.py` and the A64 checks green.
5. **G7** — `scripts/t08_b50_surface_fixture.py` must import `process_runtime` inside the `c7bbc98` worktree (that
   commit predates the rename); re-run it and confirm it reports "equal". **G8** — ADR 0021 revision 2's path
   `src/process_runtime/__init__.py` → a dated note that the path is `src/openflowsheet/__init__.py` since R-149.
6. **G3 residuals.** `scripts/v0_1_gate.py`: (a) with `--rc C`, require §8.1 item 5 — `evidence/T08/<C>/manifest.json`
   exists with `status: tested` — or print NO; (b) "PASS: Failed to upload"-type cells: a Result cell whose status word
   is PASS/success but which also contains `Failed`/`FAILED`/`failure` as a word is classified failed. Tests.
7. **The manifest.** `scripts/t08_evidence_manifest.py` (pattern of `t07_evidence_manifest.py` and its test) writing
   `evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`: package T08, `requirements: [D04, A10, D17,
   D20]` per spec §15 W5.3, one check per T08.Axx (and the build-first T08.Bxx) with its actual status and the command
   or record that measured it, the §A4.6 attestation for PTC-R1 (with the disclosures the V14 (b) verdict listed: the
   reviewer's LOW-root probe, the aborted first local run, post-C_case `src/` changes found inert), limitations = the
   envelope's E-rows and every FAIL clause (V14 (b)), and **`status: tested`** only if every check the manifest lists
   passes or is an accepted FAIL — otherwise report what blocks and do not write `tested`. Never `reviewed`.
   CI evidence: the RC CI run 37008077757 and the push CI at `C`.
8. Mark ADR 0021 (with revisions 1–2), 0023, 0024 and 0025 **Accepted** with T08's tested evidence (the convention of
   ADR 0019/0020 "Accepted with T07's tested evidence"), noting Frank's decisions in each; only if item 7 wrote
   `tested`.
9. Run `.venv/bin/python scripts/v0_1_gate.py --rc 67c66d98587f23bd7dfe8da28a8facccc92da21e` and report its output.

## Rules

Nothing under the D2.4 trees changes except what an item names (items 5–7 touch `scripts/`; if `scripts/` is in D2.4's
tree list, stop and tell the session before committing — a change there after `C` would need a new C). No `src/`,
schema, `requirements.lock` or MCP change. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
and `Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the user
is near a weekly usage limit — targeted tests, then `rm -rf .ruff_cache && PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`
once (threads 1); read its final `check.sh: PASSED/FAILED` line before reporting.

## Report

Commits; the manifest's check counts and status; the gate script's output; `check.sh`'s final line; questions.
