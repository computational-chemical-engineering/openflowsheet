# ADR 0055: A standing release procedure from 0.4.0. One normative text and one generic gate, verdicts carried by evidence fingerprint, acceptances standing by scope fingerprint, one CI run per commit

**Status:** Proposed, 2026-10-31.
**Author:** design lane (`specifier`), from the orchestrator's brief on Frank's request of 2026-10-31 ("Is it possible to
reduce the checking a bit, but still retain quality?").
**Normative text:** this ADR until WO-R1 delivers `docs/derivations/release-procedure.md` (the *standing procedure*, RP).
After that, RP is the normative text and this ADR is its policy.
**Builds on:** ADR 0021 D5; ADR 0028 (alpha spec §4, §7, §8, Table T6); ADR 0042 D2; ADR 0053 D2–D7; R-151, R-337,
R-371, R-453, R-457, R-460, R-462, R-466, R-875, R-909, R-913, R-914.
**Supersedes, from 0.4.0 on:** each release writing its own release specification, policy ADR and
`scripts/v0_N_gate.py`; the sentence in ADR 0053 D2 "No acceptance from 0.2.0 is carried"; and the date rule (alpha
Table T6, ADR 0042 D2, ADR 0053 D2) as it applies to standing rows (D3.4). ADRs 0042 and 0053 remain the records of
0.2.0 and 0.3.0 and are not edited.
**Register:** R-915 … R-921.

## 1. Authority and scope

This ADR governs every release cut from 0.4.0 on, pre-releases included. The 0.1, 0.2 and 0.3 lines keep their
scripts, registries and tests, and their behaviour does not change by a byte (REL.A04). This ADR does not touch any
gate's criteria or tolerances, any 0.3.0 record, or `CLAUDE.md`. Where it finds that `CLAUDE.md` matters, it says so as
an open item for Frank (N-3).

## 2. What was measured or read, and how it shapes the ruling

- **F-A. Fewer suite runs are duplicated than the brief assumed.** `release.yml`'s `gate` job runs no test suite. It
  runs the line's gate script over committed records (`release.yml` l.85–97). RC step 1 runs no suite either. It cites
  CI's `check` job at C (`docs/v03-rc-record.md` rows "1", from the dispatch run 41108983463). So 0.3.0 ran the full
  suite at C three times: the local `scripts/gate.sh`, the CI push run, and the `rc_alpha` dispatch, whose `check` job
  has no `if` and so re-runs on every dispatch (`ci.yml` l.54).
- **F-B. The local full gate is not a duplicate of CI.** The workstation clone holds the archived pre-0.1.0 objects
  (`git cat-file -t 67c66d98…` gives `commit`). So the seven test modules that call `require_archived_history` run
  locally and skip on CI (`tests/conftest.py:43`; RELEASING "Notes").
- **F-C. A path diff alone cannot carry a verdict honestly.** Every claimed gate's evidence is computed by
  `src/openflowsheet/**`. R-453's standard for a carry scope is "the files that compute the carried result", and by it
  every honest product scope contains `src/`. S01–S12 changed `src/` between 0.2.0 and 0.3.0, so a path-diff carry
  would have carried none of the 17 gates. The orchestrator's "11 of 17 unchanged in substance" is a fact about
  *outcomes*. A path-diff rule can match it only if the scopes are narrowed by hand, and that is judgement. 0.3.0's V14
  row does exactly that: "no PTC, homotopy, globalization or continuation source changed since 0.2.0's candidate
  (checked)" (`docs/reviews/V03-verdicts.md` l.17).
- **F-D. Most of 0.3.0's design-lane passes went on bookkeeping that recurs.** Three of the 17 rows (V13, V17, W24)
  were `BLOCKED` only because ADR 0053 D2 re-asked acceptances that had not changed (V03-verdicts l.248–251). That cost
  a re-judgement pass. W21 (e) failed because the new spec re-transcribed the alpha's step 12 without 0.2.0's fix. This
  was F1 again, now R-909. Four amendments (R-902 … R-914) fixed transcription defects in a document written for one
  release.
- **F-E. Mechanical carries already exist and are trusted.** The journey carry: `git diff --name-only J C -- <carry
  paths>` must be empty (R-337, R-453, `v0_2_gate.journey_carry`). The W27 carry: members equal. The V17 carry: `LINKS`
  unchanged and the served digest equal (R-457, R-462). Each compares a registered, recomputable quantity and never asks
  for judgement.

Consequences for the four cuts. Cut 1 is adopted as proposed (D1). Cut 2 is **changed**. What carries is the
judgement, never the evidence. All evidence is re-run at C. The carry condition is equality of an *evidence
fingerprint*, which includes the outcomes, the audited non-product files the evidence read, and the criteria (D2). A
path diff alone is rejected (F-C). Cut 3 is adopted with a mechanical scope per row (D3). Cut 4 is adopted in a
narrower form than proposed, because F-A and F-B show which runs are true duplicates (D4).

## 3. Decision

### D1: One standing procedure (R-915)

1. **One normative text.** `docs/derivations/release-procedure.md` (RP) is written once by the design lane (WO-R1). It
   folds V03 spec §2–§7 and §10.1 into standing text, together with the alpha spec §8.2 steps as M07 §8 reads them. It
   writes every later amendment into the text of the step it governs: R-902 (version strings are build provenance),
   R-903 (W26 (a) as a function of whether W27 is claimed), R-906 (17b's one aarch64 skip), R-907 (the nlp selection),
   R-909 (step 12 keeps and audits G11's results in its own text), R-911 (the release evidence manifest is excluded from
   the envelope harvest), R-913 and R-914 (the acyclic order: manifest, then gate), R-875 and R-460 (after the tag).
   RP holds a coverage table with one row per register id and its RP section (REL.A18). RP changes only by an
   amendment section recorded in the register. It is never re-written for a release.
2. **One line file per minor line.** `release/lines/<major>.<minor>.json`, format `release-line-v1`, holds:
   - `gate_set`: every `GateSet` field of `scripts/v0_2_gate.py`, with `policy_adr` replaced by `acceptances`, the path
     of the standing table (D3);
   - `gates`: for each claimed gate g, four lists. `tests` T(g): pytest path globs, plus `tests/web/*.test.mjs` where
     node evidence applies. `rc` R(g): (RC step, check id) pairs. `criteria`: paths of the documents that define g's
     criteria. `documents`: paths whose content is g's evidence, such as a package verdict document;
   - `rc_items`: the release's package items, each with an id, its command (which exits 0 and writes a `t08-rc-v1`
     record), the assertion it carries, and the script that owns its code. That script is the package's own (for
     example `scripts/e01_evidence_manifest.py`), never a per-release RC script;
   - `changelog_what_it_is_not`, `evidence_package`, `inherits` (the previous line, for example `"0.3"`), and
     `changed` (the field names that differ from the inherited line).

   The generic gate refuses a line file with exit 2 when a field differs from the inherited line's and is not named in
   `changed` (REL.A01). A silent edit to the claim set or a clause grammar cannot pass.
3. **Generic scripts.** One generic script replaces each per-release script from 0.4 on:
   - `scripts/release_gate.py --line <major>.<minor> --rc C`: `v0_2_gate.py`'s engine, imported and not copied, plus
     D2's carry check and D3's standing acceptances;
   - `scripts/release_rc.py`: the standing RC steps, and a wrapper that runs each `rc_items` command into a record;
   - `scripts/release_evidence_manifest.py`: RP's standing assertion catalogue plus the line file's items;
   - `scripts/release_fingerprint.py` and `scripts/release_carry.py` (D2).

   `release.yml` resolves the gate this way: if `release/lines/<major>.<minor>.json` exists, it runs
   `scripts/release_gate.py --line <major>.<minor> --rc <rc>`. Otherwise it runs the legacy
   `scripts/v<major>_<minor>_gate.py`. If neither exists, it refuses with `no release gate for the <major>.<minor>
   line` (REL.A05). The YES line `vX.Y.Z tag may be proposed: YES` is unchanged.
4. **The per-release delta** is the line file (complete and self-contained, with `inherits` and `changed`) plus one
   block in `docs/RELEASING.md` of at most 40 lines: the version, C, what `changed` lists and why, new gates and items,
   and Frank's new answers. **No per-release specification and no per-release policy ADR.** A release needs an ADR only
   if it departs from RP or from this ADR. A new gate needs an RP amendment section that states its criteria (design
   lane) and a line-file entry. A claim-set change needs Frank's re-dated `Claim set` row (D3).
5. **Release package id.** The evidence package of release X.Y.Z is `REL` followed by the version's digits (0.4.0 →
   `REL040`): branch `wp/REL040`, manifest `evidence/REL040/<C>/manifest.json`, verdicts
   `docs/reviews/REL040-verdicts.md`, RC record `docs/REL040-rc-record.md`. These are line-file fields with these
   defaults.

### D2: A verdict carries by evidence fingerprint, and evidence is always re-run (R-916, R-917)

1. **What carries.** A claimed gate's verdict row (verdict, failing clauses, travelling limitations, basis) carries
   from the previous release's verdict document, judged or carried at C_prev, to the release candidate C. **No evidence
   is carried by D2.** Every test and RC step of every claimed gate runs at C. The existing evidence carries (journey
   R-337/R-453, V17 R-457/R-462, W27 M07 §9) are unchanged and remain the only evidence carries.
2. **The fingerprint** Φ(g, X) of gate g at candidate X is the canonical JSON of the members below, serialized as
   `json.dumps(·, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` in UTF-8. Lists are sorted. "blob" is the
   git object id of the file at X:
   - `criteria`: `[[path, blob]]` for `gates[g].criteria`;
   - `documents`: `[[path, blob]]` for `gates[g].documents`;
   - `tests`: `{"x86_64": [[nodeid, outcome]], "aarch64": [[nodeid, outcome]]}`, read from the junit files of the CI
     run of D4.1 at X, for every node whose file matches T(g). `outcome` is one of `passed`, `failed`, `error`,
     `xfailed`, `xpassed`, or `skipped:<message verbatim>`;
   - `rc`: `[[step, check_id, status]]` for R(g), read from the RC records at X;
   - `reads`: `[[path, blob]]` for every file that meets all of these: it is tracked at X (`git ls-files`), it lies
     outside `src/openflowsheet/`, `.git/` and any `__pycache__/`, and some process of g's audit run at X (D2.3) opened
     it for reading;
   - `git`: the sorted, de-duplicated non-benign git invocations of the audit run, each written `git <subcommand>
     [<first option>]`. The **benign** set is exactly `rev-parse`, `status`, `cat-file -e`, `cat-file -t` and
     `merge-base --is-ancestor`, which read no file content (REL.A14).

   Φ contains no commit id, date, run id, path outside the repository, or timing (REL.A11). `src/openflowsheet/` is
   left out of `reads` on purpose. Product code is covered by re-running every evidence node at X and comparing
   outcomes. Putting it in the scope carries nothing (F-C).
3. **The audit run.** At C, the CI dispatch job `release-audit` (D4.2) runs `pytest <T(g)>` for each claimed g under
   `strace -f -e trace=open,openat,openat2,execve`, on both architectures, with every other setting as in `check`. The
   RC steps of R(g) run under the same `strace` wrapper in their own evidence run: the local steps through the runner
   script, the CI steps in `rc-steps`, `rc-coolprop` and the rest. `reads` and `git` are the union over these runs.
   The raw traces go under `evidence/**/artifacts/` (ignored). Their SHA-256 values and the junit files' SHA-256 values
   go into the fingerprint record, so `release_fingerprint.py --check` recomputes Φ from the recorded inputs.
4. **The carry condition.** g's row carries from C_prev to C if and only if all of these hold:
   - **K1.** Φ(g, C) and Φ(g, C_prev) are byte-equal;
   - **K2.** the `git` member is empty in both;
   - **K3.** the row at C_prev is `PASS` or `FAIL`, never `BLOCKED`, and a `FAIL` row carries only when every failing
     clause has a standing acceptance at C (D3);
   - **K4.** g is claimed in both line files, and `gates[g]` is equal in both;
   - **K5.** the row at C_prev has a committed Φ record (it was judged or carried under this ADR).

   Otherwise the `verdict` agent judges g at C. A carried row keeps its cells. Its Basis begins `carried from <C_prev>
   (judged <date>), R-916; Φ <first 16 hex of SHA-256(Φ)>`.
5. **Unsupported is a result, never a match.** If a junit file is missing for an architecture, `strace` is
   unavailable, or an audit run fails or times out, Φ(g, X) is recorded as `{"unsupported": "<reason>"}`. Two
   unsupported records are never equal (REL.A13). The gate is judged. Silence never reads as a carry.
6. **Who writes what.** `release_carry.py --line <l> --rc C` writes `release/fingerprints/<version>/<g>.json` (Φ and
   its provenance: commit C, `tree_clean` true, the step-1 run id, the trace and junit hashes). It also writes the
   carried rows and a carry report naming each gate that did not carry, with its first failing condition. The
   `verdict` agent writes only the rows that did not carry, into the same document. These files are committed after C,
   outside the D2.4 paths, as RC records are. **The gate verifies every carried row (new decision item 13).** Both Φ
   records exist at the candidate. They are byte-equal. K2–K5 hold. The carried cells equal C_prev's row. Any failure
   gives NO with the reason (REL.A15). The release manifest does not judge item 13 (R-914).
7. **First application.** Φ is recorded for every claimed gate first at 0.4.0's C. Carry first applies at the next
   release after 0.4.0 (K5). Frank may prefer a bootstrap at 0.3.0's candidate (N-1).

### D3: Acceptances stand until the accepted thing changes (R-918, R-919)

1. **One standing table.** `release/acceptances.md` replaces the per-release ADR's two tables. The engine reads it as
   it read ADR 0042's and 0053's (R-466 cell rule, exactly one table of each kind, read by column). Each table gains
   three columns: `Scope`, `Fingerprint` and `Accepted at` (the commit at which the fingerprint was taken).
2. **Scope kinds.** A scope is one or more terms joined by ` + `:
   - `paths:<glob>,<glob>…`: the SHA-256 of the sorted output of `git ls-tree -r <commit> -- <globs>`, which covers
     mode, type, blob and path, so additions and deletions count;
   - `extract:<name>`: the SHA-256 of the canonical JSON of a registered extractor's value at the commit. The
     extractors are exactly these:
     - `claim_set`: the line file's `claimed` and `not_claimed`;
     - `pyproject_extra:<extra>`: that extra's requirement list from `pyproject.toml`. It is unaffected by a version
       bump (REL.A10);
     - `links`: `scripts/m07a_rc.py` `LINKS`' registers;
     - `served_digest`: step 8's served digest, from the RC record;
   - `gate_row:<g>`: Φ(g) at the commit.

   The row's fingerprint is the SHA-256 of the terms' hashes, joined in the order written.
3. **The standing rule.** A row *stands* at C if and only if:
   - (a) its answer starts `accepted, YYYY-MM-DD` (unchanged form);
   - (b) its scope recomputed at C equals `Fingerprint`;
   - (c) for a failure-clause row, the row of its gate at C, carried or judged, fails on a set of clauses that is a
     subset of the clauses with standing rows.

   A row that fails (b) is **lapsed**. It counts as absent, and the report names the differing paths or extractors. A
   clause that fails at C with no standing row gives NO (`not accepted`). **A new failure therefore always needs
   Frank's dated sign-off.** A changed claim set lapses `Claim set`, so a new claim always needs it too. A row for a
   clause that no longer fails is reported `not used` and is inert.
4. **Dates.** A standing row's date may precede the current verdict's `Judged` date. Its fingerprint does the work the
   date did, and more precisely: it binds the answer to the thing answered. A new or replaced row carries the
   fingerprint at C and must be dated:
   - for a failure clause, on or after the verdict's `Judged` date (unchanged; R-371's bounds apply to re-judgements);
   - for a decision item, on or after the date of the committed carry report that showed the lapse at C.

   A decision item asked before the verdict therefore removes the `BLOCKED` row and the re-judgement pass that 0.3.0
   paid for (F-D).
5. **Visibility at the tag.** The gate's report lists every standing row used, as `standing acceptance <item>:
   accepted <date> at <commit>, scope unchanged`. RP has `CHANGELOG.md`'s "What it is not" list every accepted failure
   clause in force. Frank sees both when he dispatches.
6. **Seeded table (WO-R1, at C₀.₃ = `a3e508e3`).** The six cells of ADR 0053 are copied verbatim, `Accepted at`
   `a3e508e3…`, with fingerprints computed there:

   | Item | Kind | Scope |
   | --- | --- | --- |
   | Claim set | decision | `extract:claim_set` |
   | V17 carry | decision | `extract:links + extract:served_digest` |
   | M02 N1 | decision | `paths:src/openflowsheet/adapters/external/**` |
   | M03 N1 | decision | `extract:pyproject_extra:nlp + paths:docs/m03-ipopt-audit.md,benchmarks/m03/ipopt-inventory-*.json,scripts/build-m03-ipopt-env.sh` |
   | X31 (c) | failure | `paths:docs/reviews/S09-verdicts.md,benchmarks/s03/**,benchmarks/s09/**`. Its evidence is a document fact (references available), not re-run, so R-453's determining files are documents and reference data |
   | V14 (b) | failure | `gate_row:V14`, once PTC-R1 is a standing RC item (N-2, default). Otherwise `paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md`. Its evidence is then not re-run, and R-453 puts `src/` in its scope |

   At 0.4.0, `gate_row:V14` has no Φ at C₀.₃ (K5), and the path fallback lapses on any `src/` change. **V14 (b) is
   therefore asked once more at 0.4.0, and stands from then on while V14's row carries.** The coolprop and lca licences
   are seeded only if WO-R1 finds Frank's recorded answer in the register (N-7). Otherwise they remain MR-12 audit
   checks (17c), which are mechanical and need no row.

### D4: One CI run per commit (R-920)

1. For a commit X, "CI green at X on both architectures" is evidenced by one completed `ci.yml` run with `head_sha` X
   whose `check` job concluded `success` on `ubuntu-latest` and `ubuntu-24.04-arm`. For a pushed commit that run is the
   push run. No step re-runs CI at the same SHA to obtain it.
2. A new dispatch input `release_rc` runs the RC jobs only: `rc-steps`, `rc-coolprop`, `dist`, `clean-install`,
   `bundle-set`, `bundle-replay`, `release-audit` (D2.3), and `ptc-r1` under N-2. `check` gains `if: ${{ !(github.event_name
   == 'workflow_dispatch' && inputs.release_rc) }}`, so the dispatch never re-runs the suite. `rc` and `rc_alpha` stay
   as they are, for the legacy lines.
3. **RC step 1 is the push run at C.** Its record holds the run id, both legs' conclusions, the SHA-256 of each job log
   and each junit file. Step 1 is `fail`, not skipped, if no such run exists or it is not green on both legs (REL.A17).
4. CI's `check` writes junit for pytest (`--junitxml`) and for node (`--test-reporter=junit`) on both legs, and uploads
   them as `junit-<arch>`. D2 reads them, and so may any step that reads node outcomes.
5. **17b is CI's `rc-coolprop` at C on both legs.** Its criterion is classed by architecture (x86-64, aarch64; R-906),
   not by machine, so the local cross-check (`v03_rc.py step17b`) adds no clause. It is dropped.
6. **Local runs at C** cover only what CI cannot run: the reactor, nlp and lca environments (steps 12, 14, 15, 17d),
   G10/G11/G12, and the journey. The local `scripts/gate.sh` before a merge into `main` is **kept** as `CLAUDE.md`
   requires. It runs in the background, in parallel with CI, and it is the only run of the archived-history tests
   (F-B). Records-only commits after C get their CI push run automatically, and nothing re-runs locally except that
   merge gate (N-3).
7. `release.yml` is unchanged apart from D1.3's resolution. Its `gate` job runs no suite (F-A). The dry run stays.

### D5: Lanes and Frank's attention per release (R-921)

- **Build lane:** the line-file fields `version`/`covers`, `envelope_id`, `packages`, `required_adrs`,
  `evidence_package` and the document paths. Also the RC job, the records, `release_carry.py`, the manifest,
  `CHANGELOG.md` and the RELEASING block.
- **Design lane, at most three passes per release:**
  - (1) a `specifier` pass, only if the claim set, a gate's criteria (an RP amendment), an `rc_items` entry or the
    "What it is not" phrases change;
  - (2) one `verdict` pass over the rows that did not carry. If every row carries and no row lapsed, the verdict
    document is generated with `**By:** carry (R-916)`, and no pass is needed;
  - (3) one `reviewer` pass, only if the release changes release machinery (`scripts/release_*.py`, RP). An
    independent review of numerics stays with the packages that change numerics, as today.
- **Frank:** one batched message in plain words, only for lapsed rows, new failing clauses, a changed claim set, or
  money. The tag, the dispatch and the PyPI approval stay his (ADR 0021 D5).

### D6: Kept unchanged

- CI on x86-64 and aarch64, and the full suite, before every merge into `main`.
- Every bit-identity and regression gate. Every test and RC step runs at C. D2 carries judgements, never runs.
- G11's keep-and-audit in step 12's own text (R-909, now in RP).
- The independent review when numerics change.
- Frank's dated sign-off on any new failure or new claim (D3.3).
- The tag and dispatch are Frank's.
- The dry run.
- R-151's tree record, R-460/R-875 after the tag, R-914's acyclic order.
- CLAUDE.md's scientific conduct: no relaxed checks, no narrowed denominators, and an unsupported result never counts
  as a match.

## 4. Alternatives rejected

- **A path-diff carry over scopes drawn by hand** (cut 2 as proposed). The scope is judgement exercised once and then
  trusted. It rots as tests start reading new fixtures, and it is the narrowing that 0.3.0's V14 row did by hand (F-C).
- **A path-diff carry whose scopes include the product (`src/`).** It is honest, but it carries nothing in any release
  that changes `src/` (F-C).
- **A fingerprint of outcomes only.** If a reference file or regression fixture is re-taken, the tests are unchanged and
  still pass, and the old verdict would carry over changed evidence. `reads` exists to catch that.
- **Carrying the evidence of unchanged gates, not just the judgement.** It skips defect-catching runs to save compute
  that is free.
- **Templated per-release specifications.** R-909 shows that re-transcription is where gaps come back in (F-D).
- **Acceptances that stand until withdrawn.** They would admit a changed failure without Frank's dated sign-off.
- **Acceptances keyed by date** (the status quo). They re-ask with no new information, and three `BLOCKED` rows and a
  re-judgement pass at 0.3.0 came from that alone (F-D).
- **Dropping the local full gate in favour of CI** (cut 4 read literally). It loses the archived-history tests (F-B) and
  contradicts `CLAUDE.md`. The choice is Frank's (N-3).
- **A new registry entry per line in a per-line script.** That is the per-release script this ADR removes.
  `release.yml` resolves by line, so a line file is the smallest unit that changes.

## 5. Affected requirements

- RELEASING: the per-release block and the gate resolution.
- `release.yml` (D1.3) and `ci.yml` (D4.2, D4.4, D2.3).
- Plan §1.3: the per-release lane split (D5).
- ADR 0042 D2 and 0053 D2: the acceptance and date rule from 0.4.0 on (D3.4). The ADRs are not edited.
- R-238: Frank's per-release answers become standing answers, which the gate checks by fingerprint.
- Unchanged: R-371 for judged rows, R-466 (the cell rule, now over more columns), R-909, R-913 and R-914 (now in RP),
  R-460 and R-875.

## 6. Migration: what 0.4.0's cut does differently, and the work orders

These must be done before K3 of 0.4.0. Each WO has its acceptance tests. Then the design lane makes one `reviewer`
pass over WO-R2 to WO-R6.

| WO | Lane | Deliverable | Acceptance |
| --- | --- | --- | --- |
| WO-R1 | design (`specifier`) | RP; `release/lines/0.3.json` (a transcription, used only for inheritance) and `release/lines/0.4.json` with `gates[*]` (T, R, criteria, documents) seeded from 0.3.0's Basis column; `release/acceptances.md` seeded as D3.6 | REL.A02, A18, A19; design review of `gates[*]` against V03-verdicts' Basis column |
| WO-R2 | build (Opus) | `scripts/release_gate.py` (line-file loader, `inherits`/`changed`, item 13 hook); the `release.yml` resolution | REL.A01–A05 |
| WO-R3 | build (Opus) | standing acceptances in `release_gate.py`: scope terms, extractors, lapse, dates, report lines | REL.A06–A10 |
| WO-R4 | build (Opus) | `ci.yml`: junit on both legs, `release_rc`, `check`'s `if`, `release-audit`, `ptc-r1` under `release_rc` (N-2) | REL.A17; one `release_rc` dispatch at a branch head that shows `check` skipped, the RC jobs run, and `junit-x86_64`/`junit-aarch64` present (N-4's measurement) |
| WO-R5 | build (Opus) | `scripts/release_fingerprint.py` (Φ, `--check`), `scripts/release_carry.py`, gate item 13 | REL.A11–A16, A21 |
| WO-R6 | build (Opus) | `scripts/release_rc.py` (standing steps 1–16, `rc_items` wrapper, `strace` wrapping), `scripts/release_evidence_manifest.py` | REL.A20; on 0.3.0's committed records, each standing assertion's status equals S13's manifest |

**0.4.0's cut, compared with 0.3.0's.**
1. No V04 spec, no policy ADR, no `scripts/v0_4_gate.py`. WO-R1's line file plus a RELEASING block take their place.
2. K3 and C as RP states them (unchanged in substance).
3. CI: the push run at C is step 1. One `release_rc` dispatch runs the RC jobs, the audit and PTC-R1, with no second
   `check`.
4. Local steps run under `strace`. Φ is recorded for all claimed gates. Nothing carries yet (K5).
5. Before the verdict, `release_carry.py` reports the lapsed rows. Frank is asked once, in plain words, for V14 (b)
   (D3.6), for anything else that lapsed, and for any claim-set change. Decision items answered then do not block.
6. One `verdict` pass over all claimed gates.
7. The manifest, then the gate (R-914), then the dry run, then Frank's dispatch.

**After the tag** as R-875 states, with the line file of the next line inheriting `0.4`.

## 7. Estimate (labelled an estimate; measured at 0.4.0 and at 0.5.0)

| | 0.3.0 (measured) | 0.4.0 (first standing release) | 0.5.0 on (carry active) |
| --- | --- | --- | --- |
| Design-lane passes | ~10 (verdict ×3, specifier ×3, reviews) | 1 verdict; 1 specifier only if the claim set or criteria change; the one-time migration (WO-R1 + 1 review) is off the critical path | 1 verdict over the rows that did not carry (0 if all carry); specifier 0 unless something new |
| Engineer passes | 8 | ~4 | ~3 |
| Frank's questions | 6 cells + re-asks | V14 (b) + anything lapsed or new | only lapsed or new rows |
| K3 → tag wall time | ≈ 2 days | ≈ 1 day (local RC compute dominates) | ≈ 0.5–1 day |

The share of gates that carry is not known in advance. "11 of 17" is an outcome-level figure (F-C). Φ also compares
`reads` and `git`, so the measured share at 0.5.0 may be lower (N-5).

## 8. What this ADR does not establish

- That any given gate will carry. Carry is measured per release and never promised.
- That a carried verdict was reviewed again. It is the original judgement, shown to rest on evidence that Φ shows to be
  the same. It is not new review, validation or optimality evidence.
- That the audit sees every dependency. It does not see reads made through git object storage; such gates have a
  non-empty `git` member and do not carry. It does not see processes started outside the audited process tree, or
  reads that depend on the architecture beyond the two CI legs and the workstation.
- Any change to a gate's criteria or tolerances, to a 0.3.0 record, or to `CLAUDE.md`.
- That PTC-R1 reproduces `T08-verdict-V14b.md`'s outcome when it is re-run (N-2 measures it).
- That the line-file schema suits a future line with new gate families. A new family needs an RP amendment.

## 9. Open items (work proceeds on the default)

- **N-1, Frank (preference): start carrying verdicts at 0.4.0 or at 0.5.0?** Default: 0.5.0. 0.4.0 judges every gate
  once and records the fingerprints. Alternative: one extra CI run and audit at 0.3.0's released candidate, so that
  carrying can start at 0.4.0. That costs about half a day of engineer work, no money. Its fingerprint is taken at
  `a3e508e3` plus a `ci.yml` change. Any test that reads `ci.yml` (for example V03.A15) is fingerprinted at the new
  bytes, and so does not carry.
- **N-2, needs a fact: PTC-R1's CI wall time at C, and whether it reproduces V14 (b)'s registered outcome.** It is
  measured by WO-R4's dispatch with `ptc_r1`. Default: PTC-R1 joins the standing RC job if it finishes within its
  360-minute timeout on both legs, and V14 (b)'s scope becomes `gate_row:V14`. Otherwise the scope is D3.6's path
  fallback, and V14 (b) is asked at every release that changes `src/`.
- **N-3, Frank (preference, and only Frank can change `CLAUDE.md`): keep the local full test run before the release
  branch merges?** Default: keep it, as `CLAUDE.md` says. It runs in the background beside CI, and it is the only run
  of the archived-history tests. Alternative: CI alone at the release merge, plus a local run of just the seven
  archived-history modules. That needs Frank to amend `CLAUDE.md`'s gate rule.
- **N-4, needs a fact: `strace` overhead and availability on both CI runner classes.** It is measured by WO-R4's
  dispatch. Default: if a gate's audit exceeds the job timeout, its Φ is `unsupported`, and the gate is judged, not
  carried.
- **N-5, needs a fact: how many test selections run non-benign git.** It is measured by the first audit at 0.4.0's C.
  Default: those gates are judged. The benign set is widened only by an amendment.
- **N-6, Frank (preference): is the list of standing acceptances in the gate report and the release notes enough for
  him at dispatch?** Default: yes, and no question is asked. Alternative: a one-line confirmation request per release
  that names the rows used.
- **N-7, needs a fact: is there a recorded Frank acceptance for the coolprop and lca licences?** WO-R1 searches the
  register. Default: none is seeded.

## 10. Acceptance evidence: numbered assertions

Every expectation below is exact. Nothing asserted is a floating-point quantity: the outputs are bytes, counts, exit
codes and strings, so there is no roundoff floor and no tolerance. "Each flip" means a control that changes only that
input. An assertion holds only if the base passes and every control fails with its stated reason. So no assertion can
be met by a constant answer.

| Id | Assertion | Expected |
| --- | --- | --- |
| REL.A01 | line file 0.4 with one `gate_set` field changed and not in `changed`; control with it listed | exit 2, `line 0.4: field <f> differs from 0.3 and is not in changed`; control accepted |
| REL.A02 | `release/lines/0.3.json` `gate_set` against `v0_3_gate.GATE_SETS[0]` | every field equal (`policy_adr` ↔ `acceptances` = ADR 0053's path) |
| REL.A03 | `release_gate.py --line 0.3 --rc a3e508e3` in dated mode (no `Scope` column) against `v0_3_gate.py --rc a3e508e3`, at the same checkout; V03.A06/A07's fixtures through both | stdout byte-identical; the same outcomes, fixture by fixture |
| REL.A04 | the tests of `v0_2_gate.py`/`v0_3_gate.py` (M07.A30–A32, M07a, V03.A01–A08) | pass with node ids unchanged |
| REL.A05 | `release.yml`'s gate step, read as text and run in a shell harness on three versions: one with a line file, one legacy (`0.3.0`), and one with neither | the generic command; the legacy script; refusal `no release gate for the <M>.<m> line` |
| REL.A06 | a standing row whose scope is unchanged, dated before `Judged` | stands; YES fixture |
| REL.A07 | one file in its `paths` scope changed | `lapsed (<path>)`, NO; re-dated on or after the relevant date (D3.4) with the fingerprint at C → YES; dated one day earlier → NO |
| REL.A08 | a clause failing at C with no row; a row for the same letter of another gate | NO `not accepted` in both |
| REL.A09 | a claim-set change | `Claim set` lapsed, NO until re-dated |
| REL.A10 | `extract:pyproject_extra:nlp` across a commit that changes only `version`; across one that adds a package to `nlp` | equal; different |
| REL.A11 | Φ computed twice from the same recorded inputs; key scan | byte-identical; no member holding a commit id, date, run id or timing; `--check` exit 0, and exit 1 after one recorded input is altered |
| REL.A12 | the carry base fixture, and eleven single flips: a criteria blob; a documents blob; one node's outcome on one leg; one node added; one RC check status; one read blob; one read path added; a non-benign git call; the prior row `BLOCKED`; `gates[g]` changed; no prior Φ | base carried; each flip `not carried` with its K-reason |
| REL.A13 | both Φ `unsupported` with the same reason | not carried |
| REL.A14 | the benign set | exactly the five forms of D2.2; `git show`, `git diff`, `git cat-file -p`, `git ls-files` are non-benign |
| REL.A15 | gate item 13: carried cells altered; Φ files unequal; a row marked carried without Φ files | NO with the reason, in each case |
| REL.A16 | a toy selection under the audit wrapper reads one tracked fixture, one `src/openflowsheet` file and one untracked file | `reads` holds exactly the fixture |
| REL.A17 | `ci.yml` text: `check`'s `if`, the `junit-<arch>` uploads, the `release_rc` job list; step 1 record fixtures: a green push run, a missing run, a red aarch64 leg | as D4.2–D4.4; `pass`, `fail`, `fail` |
| REL.A18 | RP's coverage table | rows for R-460, R-875, R-902, R-903, R-906, R-907, R-909, R-911, R-913, R-914, each naming an RP section that exists |
| REL.A19 | `release/acceptances.md` | the six rows of D3.6; answer cells verbatim from ADR 0053; `Accepted at` `a3e508e3…`; fingerprints recomputed there equal the recorded ones |
| REL.A20 | `release_evidence_manifest.py` over 0.3.0's committed records | each standing assertion has S13's status |
| REL.A21 | a verdict document produced with every row carried | header names C once and has one `Judged` line, with `**By:** carry (R-916)`; every Basis begins `carried from` |

**Proposed → Accepted** when REL.A01–A21 hold in a `tested` manifest of the migration package, the `reviewer` pass on
WO-R2 to WO-R6 is recorded, and Frank's answers to N-1, N-3 and N-6 are recorded, or their defaults stand.

## Frank's answer (2026-10-31, verbatim) and its effect

Asked in plain words whether to build parts 1–3 (one procedure with a per-line file, D1; standing acceptances, D3; one CI
run per commit, D4) now and the evidence-fingerprint carry (D2) later, Frank answered: **"1–3 now, 4 later
(Recommended)"**. So D2 (R-916, R-917) and WO-R5 are deferred: 0.4.0 judges every claimed gate, and the carry is taken up
only if 0.4.0's verdict pass is still costly; this needs a new decision recorded the same way. The `strace` parts of WO-R4
and WO-R6 and REL.A11–A16, A21 go with D2. N-1, N-4 and N-5 lapse with D2. N-3 and N-6 stand on their defaults (keep the
local merge gate; the listed acceptances suffice at dispatch). N-7, a fact: Frank accepted the coolprop and lca licence
decisions (R-624, R-900) on 2026-10-30, recorded verbatim in `docs/derivations/V03-release-spec.md` §11 (N-11); WO-R1
seeds that row.
