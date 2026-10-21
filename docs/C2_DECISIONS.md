# C2 — build decisions (OpenIDAES-450 split registration)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: register-number ranges for the cloud queue (branches run unmerged in parallel) → C2 R-486…R-494, C1
  R-495…R-499, C3 R-500…R-504, S01 R-505…R-519, L01 R-520…R-529, S02 R-530…R-539. Alternative: renumber at merge.
  Reversible by: renumbering an unmerged branch's entries before its merge.
- DECISION: split ratio → per-stratum halves, odd strata alternating up/down by seeded stratum rank, no compensation
  across strata (D-1, SPLIT-R06). Alternative: global largest remainder or 60/40. Reversible by: a v2 registration
  before any held-out score is reported.
- DECISION: which R02 the strata use → W27-R02 as committed in `coverage.json` (D-2, R-487). Alternative: R02-F1
  classes. Reversible by: a v2 registration.
- DECISION: seed source → fixed text embedding brief commit `f39746770dd7…`, committed (`0211372`) before the draw
  (`c0649a7`) (D-3, R-489). Alternative: archive SHA-256, free string. Reversible by: a v2 registration.
- DECISION: dynamic cases → in the frame as own strata (D-4, R-493). Alternative: exclude. Reversible by: a v2
  registration.
- DECISION: incomplete case → excluded from both halves; a repaired one is an added case (development, as already
  named) (D-5, R-491). Alternative: assign now. Reversible by: an amendment.
- DECISION: exposed set → W27's 45 + 3 canaries + 17 cases named in committed non-data files at `f397467` (D-6,
  R-488; Frank asked, C2-Q2). Alternative: the 48 only. Reversible by: a v2 registration before any held-out score.
- DECISION: protection → recorded rule + held-out ids never in clear outside 12 all-case files and `heldout/` dirs +
  hash commitment + leak-guard test SPLIT-A09 (D-7, R-490). Alternative: ids in clear with a rule alone. Reversible
  by: adding ids to the record (one-way).
- DECISION: re-split policy → never redraw; generator refuses on input change; removed/changed/added cases by
  amendment, added by seeded per-case coin (D-8, R-491). Alternative: redraw on change. Reversible by: a new
  registration.
- DECISION: F-1 → R02-F1 with class-name fallback, awaiting `topology_units` in a new `case_facts-v2.json` from the
  workstation (D-9, R-492). Alternative: topology_kind-only rule, or a flag. Reversible by: an amendment after the
  development-only measurement (§11 Q-4).
- DECISION: contamination at the first draw (a held-out id used as an example in the pre-draw text) → recorded under
  SPLIT-R11 by hash, mention kept, headline 223 (D-10, R-490). Alternative: edit it out silently. Reversible by: none
  needed.
- DECISION: record location → `benchmarks/c2/openidaes450_split.json` (package-id convention) (D-11). Alternative:
  next to W27's data. Reversible by: moving it with the generator constant.
