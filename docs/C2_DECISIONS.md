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
- DECISION (build lane): evidence manifest for C1/C2/C3 → none; `schemas/evidence-manifest.schema.json`'s
  `work_package` pattern `^[PKTMSR][0-9]{2}[a-z]?$` admits no `C` id, and the schema is frozen. These packages merge
  on the full gate read and CI green on both architectures (the user's queue rule: "tested manifest where the package
  has one"). Alternative: an ADR widening the pattern. Reversible by: that ADR and retro-manifests.
- DECISION (build lane, CI): D-11 reversed → the record moves to `benchmarks/m06/openidaes450/split.json`. CI run
  39688818107 failed W27-A71 (`tests/test_t08_w2_unsupported.py:230`, R-194/R-467): a tracked path naming `openidaes`
  under `benchmarks/` must lie in the adaptation directory `benchmarks/m06/openidaes450/`. `split.json` is not a
  registered record name and not under `runs/`, so W27-A72 holds. The record's bytes and SHA-256 are unchanged (it
  does not name its own path). Alternative: amend U14 (a W27 registration change). Reversible by: moving it back with
  a U14 amendment.
