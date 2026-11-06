# RP build decisions (ADR 0055 WO-R2, WO-R3)

Build lane, branch `wp/RP`. Brief: `docs/briefs/REL-build-WO-R2-R3.md`. Normative text: RP
(`docs/derivations/release-procedure.md`). Each choice below is isolated in `scripts/release_gate.py` and named
where it lives. Questions for the design lane are batched for the one `reviewer` pass over WO-R2…R6 (ADR 0055 §6).

## Choices (build lane, 2026-11-06)

- **B-1 Mode.** Dated mode iff neither acceptances table has a `Scope` column (REL.A03's wording); then
  `release_gate` calls the engine's `main`/`build` unchanged. Standing mode otherwise (`standing_acceptances`).
- **B-2 Where things are read.** The line file, its chain and the schema are read in the candidate's tree (as the
  engine reads every input, and RP §8.2 E1). RP.L05/RP.L08 are checked in `C`'s tree by git (RP §3.4). A line with
  `gates` or `rc_items` whose `C` is not a commit of the repository is refused, exit 2.
- **B-3 Scope of the checks.** RP.L01/L02 on every file of the chain; RP.L03/L04 on every link of the chain;
  RP.L06–L10 on the judged line; RP.L10 for either role (0.3's acceptances are ADR 0053, which passes).
- **B-4 New versus standing row.** A row is *new* (RP §8.4) iff its `Accepted at` is `C` ("carries the fingerprint
  and commit at the C it answers"). A new failure-clause row keeps the engine's `Judged` and Table T7 bounds (its
  own date is passed to `judge_gate`); a standing one has none (`datetime.date.max`, D3.4). A new decision row is
  dated on or after the lapse report's first-line date, which must name this `C`.
- **B-5 Table T7's upper bound** (an answer a re-judged gate waits on counts only up to the re-judgement) is kept
  for decision items in standing mode, as the engine's item 11 has it.
- **B-6 Report naming.** In standing mode `GateSet.adr` is the acceptances path (`StandingGateSet`), so reports say
  `release/acceptances.md` where the engine says `ADR 0053`. The engine's section suffixes (D2, D2.3, D3, D4) are
  its own text and stay.
- **B-7 Composition.** The engine's `build` takes no policy argument and is not edited, so standing mode composes
  its parts (`verdict_document`, `judge_gate`, `rc_record_problems`, `manifest_problems`, `envelope_problems`,
  `adr_problems`, `links_problems`) in `build`'s order and keys (`_build_standing`). Dated mode and the
  not-covered report call `engine.build` itself.
- **B-8 Report lines** (RP §8.5): `standing acceptance <item>: accepted <date> at <commit>, scope unchanged` for
  each row used; `acceptance <item>: lapsed (<terms>)`, `… unsupported (<reason>)`, `acceptance <clause>: not
  used`. They precede the YES/NO line, and are the JSON key `acceptances`.
- **B-9 Naming a lapse.** The differing terms are found by re-evaluating the scope at `Accepted at`: a `paths:`
  term by the paths whose records differ, an `extract:` term by itself; if `Accepted at` does not reproduce the
  recorded fingerprint, the report says only that. E1/E4 at a commit other than `C` read the newest line file of
  the chain present there, else the chain's root from the candidate (RP §8.2's seed rule, generalised). Only the
  wording depends on this; standing or lapsed is decided at `C` alone.
- **B-10 `--lapses`** prints the report to stdout (the build lane commits it as
  `evidence/<pkg>/<C>/acceptance-lapses.txt`); a row line is `<item>: stands | lapsed (…) | unsupported (…)`; the
  date is UTC; exit 0. It is refused (exit 2) on a dated line.
- **B-11 Malformed standing table** (Scope not one backtick span, an unknown term or extractor, a Fingerprint or
  Accepted-at of the wrong shape, not exactly one table of each kind, a missing column): exit 2, as a malformed
  verdict document is.
- **B-12 Extractors.** E3 is the engine's `link_registers` (an empty `LINKS` is unsupported). E4 needs exactly one
  item-1 chain entry per step-8 record; listed files not ending `.json` are not read.
- **B-13 Item 13** does not exist while D2 is deferred (RP.S06): the hook is the term `gate_row:<g>`, always
  `unsupported (gate_row needs the evidence fingerprint, ADR 0055 D2, deferred)`.
- **B-14 `release.yml`.** The role is read with `python -c json`; a malformed line file fails the step (bash `-e`).
  Refusal `no release gate for the <M>.<m> line`; the other refusals name the command run.
- **B-15 Engine-only commands** (`--write-tree-record`, `--carry-journey`, `--carry-w27`) run the engine with the
  line's gate set after the loader, without RP.L05/L08 (they judge nothing). Every line admits post-releases.

## Questions for the design lane (defaults applied)

- **Q-B1 (B-4).** RP does not say how the gate tells a new row from a standing one. Default: `Accepted at` = `C`.
- **Q-B2 (B-5).** RP §8.4 states only the lower bound for a decision item. Default: the engine's T7 upper bound too.
- **Q-B3 (B-6).** Standing-mode reasons read e.g. `FAIL clause not accepted in release/acceptances.md D3`, `(…
  release/acceptances.md D4)`. A wording ruling would need either this text or an engine edit (frozen).
- **Q-B4.** A row is checked only at `C` (RP §8.3 (b)); its fingerprint is never verified at `Accepted at`, so a
  hand-edited row with an old `Accepted at` and `C`'s fingerprint escapes §8.4's date bound. Default: as RP says.
- **Q-B5 (B-2).** A `C` known only from `release/rc-trees/` cannot pass RP.L05/L08. Default: refused, exit 2.

## Measured (2026-11-06, at `76d6ef68` + this branch)

- The seven seeded fingerprints and all eleven term hashes of `release/acceptances.md` recompute at `a3e508e3`
  exactly. At HEAD: V14 (b) is lapsed only by `src/openflowsheet/__init__.py`; V17 carry is unsupported (no
  REL040 records yet); the other five stand.
- `release_gate.py --line 0.4 --rc HEAD`: exit 2, `RP.L08: WHEEL-DATA script scripts/wheel_data_check.py: not at
  C`, alone (RP §3.4 predicts it until WO-R6).
- REL.A03 at the checkout (`--rc a3e508e3`, text and `--json`): stdout byte-identical. HEAD is `0.4.0.dev0`, so
  both print the not-covered report; `--candidate a3e508e3` cannot be compared because that tree has no line file.
  The fixture comparison (V03.A06–A08's 17 states and the W27 malformed case) carries the substance.
