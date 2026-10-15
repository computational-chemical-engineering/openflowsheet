# M06 WO-17 build-lane decisions log (preparation, branch wp/M06-wo17)

Scope: the parts of WO-17 (W27 canaries + 45-run campaign, at M07) that need neither the v0.2 candidate nor any
spend. Nothing here launches a session, a canary or a model call.

S1 State of the three preparatory items named in `docs/V02_STATE.md`'s M06 row, measured on main `67cfcff`:
  (a) "v0.2 binder reading in `snapshot.READINGS`" — already on main: W27-R63 item 1 (`bases-v1`) is
      `snapshot._routes_bases_v1`, chosen by `snapshot.reading_for` from the binder's `SELECTABLE_BASES` and
      `MODEL_BASES` (M06 WO-16h + M02 join J1/J2), never by `__version__`. `build_snapshot()` on main reads
      `bases-v1`: routes syn001 (13 ids) and pr-c1-v1 (8 `c1.*` ids), list_models `90d9da8e…`. The alpha cut
      (`e0e198e`, 0.2.0a1) changed only the version pin in `test_snapshot_of_this_build_is_todays_registry`.
      No module is named `READINGS`; the row's wording predates Amendment 2. Nothing to do.
  (b) "M01/M02 model-id rows" — already on main: registration Amendment 2 §21.1 (C1 rows) and Amendment 3 §22.1
      (`c1.reactor_surrogate`, WO-16i `b3216dc`) in `registration.json#/units/model_functions`, read by
      `coverage.py` and by `scorer.agent_connections`. Nothing to do. M04's own live re-pin (J3'–J6') is on
      `wp/M04`, not main.
  (c) "U14 rewrite for campaign records" — R-194: "U14 is then rewritten with the campaign, not relaxed." The
      claim text depends on the campaign, so it is M07's. Prepared here: B1–B3.

B1 R58's `confirmation/` is written by the harness. §7 keeps the scripted reference builds at
  `benchmarks/m06/openidaes450/confirmation/<case_id>.{py,json}` (P5 reads them there), while W27-R58 lists
  `confirmation/` inside `runs/<campaign>/` ("§7, or a record that C was empty"); nothing wrote it. Choice:
  `harness.campaign()` calls `record_confirmation` once, after the preflight passes and before the first run:
  byte copies of each sampled CANDIDATE's two files plus `confirmation.json` {candidates, files: name→SHA-256,
  record}; for an empty C the record says "C is empty: §7 has nothing to confirm" (P5's words). Alternative: a
  reference by hash only, no copies. Neither classification nor identity moves. Reversible: revert the commit.
B2 `harness.campaign_record(campaign_dir)`: W27-R58 as a mechanical verdict over a finished campaign — coverage
  with its snapshot hash, sample = re-draw, confirmation = sampled C with matching copies, exactly the sample's
  three canaries each passing `canary_verdict`, one run dir per run-order entry with R58's six files, `run.json`
  passing A23 with `tree_clean` true ("a dirty-tree run is not evidence") and campaign/order/case/coverage/
  snapshot equal to this campaign's, `campaign.json` equal to `scorer.aggregate` recomputed with its recorded
  surface, and no other entry. Choices where R58 is silent: canaries need not be from a clean tree (P8 judges the
  tree before the first run); the commit is not required equal across runs. Reversible: revert the commit.
B3 U14's test gains `U14_CAMPAIGNS = ()`: paths under `runs/<campaign>/` of a named campaign are exempt from the
  "no run or campaign record" clause only if the whole directory is tracked and `campaign_record` passes. With the
  tuple empty the accepted set is exactly today's (claim unchanged, R-194 not reversed). M07's rewrite = name the
  campaign there + restate the envelope's U14 outcome + a register entry amending R-194. The named-campaign
  branch is first exercised at M07 (no tracked campaign exists to test it on). Reversible: revert the commit.
