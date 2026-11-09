# RRC ruling: V17-T10's offered-policy set after `RRC-revision-v1`

Design lane (`specifier`), 2026-11-09. Brief: `docs/briefs/RRC-v17-t10.md`. Read at `main` `7f5d089b` and `wp/RRC`
`fcba6656` (read only). Nothing was run except `sha256sum` of the three committed T07 reference documents and a
Python check of the registered set's order (§7).

## 1. Authority and scope

This note rules how T10-C3's expected set follows RRC. It covers `V17-T10`, the T07 reference generator and the
carried-surface reference the scorer reads. The build lane applies it on `wp/RRC` as written (§4). The design lane
does not edit code or tests.

It is consistent with:

- **T07 V17 spec Amendment T08-1** (`docs/derivations/T07-v17-tasks-spec.md` §"Amendment T08-1"). Its last sentence
  reads: "It is not a licence for later content changes: each needs its own amendment of this kind." This ruling is
  that amendment for RRC.
- **ADR 0072 R-995.** `RRC-revision-v1` is offered by name and is never a route's default. **ADR 0072 C1** measured
  the served tool-list digest `455d01eb…` and every offered `policy_sha256` as unchanged.
- **M07a's MR-7 clause** (`docs/derivations/V02-alpha-release-spec.md`). It admits a v0.2-and-later content
  addition named by a register entry under Frank's F5 (2026-09-29).
- **Release procedure §4.4.** The V17 carry holds iff step 8 passes with `LINKS` unchanged. The `V17 carry`
  acceptance's terms are the links and the served digest, and RRC moves neither.
- **R-115 and R-087.** Recorded runs keep the bytes they were scored against, and no criterion is applied after
  the outcome.

No frozen interface (`docs/interfaces-frozen.md`), schema or registered identity changes.

## 2. The rule

**R1. Each content change to `get_project.solve_policies` that T10-C3 registers gets its own carried-surface
reference document.** The document is generated in Amendment T08-1's form, and every earlier document stays frozen.
For RRC this means:

1. **A fourth document**, `docs/derivations/scripts/t07_reference_rrc.json`, written by
   `t07_reference.py --emit-rrc`. It is `t07_reference_c2.json`'s document with exactly the three paths T08-1
   changed, and no others:
   - `carry` (RRC's own);
   - `constants.offered_policy_ids`;
   - `tasks.V17-T10.answer.offered_policy_ids.expected`.

   The offered set becomes `["RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"]`, which
   is sorted and unique. Its `generator_claims` count GC-01…GC-18. Put another way, it is T08's document with the
   offered set grown by exactly `RRC-revision-v1` and its `carry` restated.
2. **T10-C3 stays an `exact_set`** for reference runs from RRC on, against those five ids. T10-C1, T10-C2 and
   item 7 are unchanged: `T06-revision-v1` is still not offered.
3. **The scorer's carried-surface entry moves to the new document.** `scorer.CARRIED_SURFACE_REFERENCE_PATH`
   changes, and with it `reference.run`, G16-b in `tests/test_t07_v17_reference.py`, and step 8 of the RC job
   (`m07a_rc.g16b`).
4. **Frozen, and not re-scored:**
   - `t07_reference.json` (`cba24a92…`, GC-16);
   - `t07_reference_c2.json` (`23b924b8…`, GC-17);
   - `t07_reference_t08.json` (`f946a88f268acc0b690e24f5fb1c358611b5333e169468bd2ae861f8a13148b9`, new
     GC-18.t08.reference_frozen).

   The records stay valid for the version they were scored at: `v17-c1`, `v17-c2`, T08.A49's G16-b and
   M07a.A37's G16-b.

**Why D-45 does not apply here.** D-45 excluded `RRC-revision-v1` from T08's B27 by B13's rule because B27
measures what *T08* delivered, which is its four policies. T10-C3 measures what *the served contract offers*, and
item 8 asks exactly that. Excluding the fifth policy there would make the expected answer false. The reference
solution would then have to filter its own live answer, or the scorer would have to narrow `exact_set`. B27 and
T10-C3 measure different quantities, so the two rulings agree.

## 3. Rejected alternatives

- **Editing `OFFERED_POLICIES_T08` in place.** This moves the bytes that T08-1's text, GC-17 and T08.A49/M07a.A37
  describe. It also leaves the four-set quoted in T08-1 contradicted by the file of that name, which amounts to
  amending a registered amendment in place.
- **Excluding `RRC-revision-v1` from T10-C3 (B13's rule, as D-45 did).** This makes the expectation false (§2).
- **Hiding `RRC-revision-v1` from `get_project` in the V17 fixtures.** This contradicts R-995. T08-1 also rejected
  a contract that hides what it serves.
- **An oracle read from the live `get_project`, or a "contains T08's four" test.** The first makes the expectation
  come from the thing tested. The second admits invented ids. T08-1 rejected both.
- **Deriving the set from register entries at score time.** This is a new mechanism with the same per-addition
  cost, and it moves the oracle out of a generator-checked document.

## 4. Exact edits (build lane, on `wp/RRC`)

None of these files differ between `main` and `wp/RRC` today: the generator, the three JSONs, `benchmarks/t07/v17/`,
`tests/test_t07_v17_reference.py` and the T07 spec.

**E0. Baseline first.** On the unedited branch, run `python docs/derivations/scripts/t07_reference.py --check`. It
must exit 0 and print `t07_reference_t08.json is byte-identical to --emit (sha256 f946a88f…)`. This is A1. If it
fails, stop and report: the T08 pin below would then be wrong.

**E1. `docs/derivations/scripts/t07_reference.py`.**

- **Module docstring.** Add `--emit-rrc docs/derivations/scripts/t07_reference_rrc.json` to the usage block and say
  "the four committed JSON files". Add a paragraph: "A fourth document (spec Amendment RRC-1, 2026-11-09; ADR 0072
  R-995). `t07_reference_rrc.json` is what reference runs of the carried surface are scored against from RRC on:
  `v17-c2`'s document with exactly the offered solve policies changed (GC-18.changes_exactly) and a `carry` member.
  `t07_reference_t08.json` is frozen (GC-18.t08.reference_frozen)."
- **New section `# 10. Amendment RRC-1`**, after section 9. It defines:
  - `RRC_JSON = HERE / "t07_reference_rrc.json"`
  - `T08_REFERENCE_SHA256 = "f946a88f268acc0b690e24f5fb1c358611b5333e169468bd2ae861f8a13148b9"`
  - `OFFERED_POLICIES_RRC = ("RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1")`
  - `RRC_CHANGED_PATHS = {"carry", "constants.offered_policy_ids",
    "tasks.V17-T10.answer.offered_policy_ids.expected"}`
  - `carry_rrc()`, returning exactly:
    ```python
    {
        "amendment": "T07-v17-tasks-spec.md Amendment RRC-1 (ADR 0072, R-995)",
        "rule": "F5 (Frank, 2026-09-29) as M07a's MR-7 applies it: a content-only addition to "
        "get_project.solve_policies that a register entry names (R-995) keeps V17's carry; the served "
        "tool-list digest and the surface chain are unchanged (ADR 0072 C1)",
        "base": carry()["base"],
        "supersedes": {
            "reference": "docs/derivations/scripts/t07_reference_t08.json",
            "reference_sha256": T08_REFERENCE_SHA256,
            "use": "reference runs of the carried surface from T08 up to RRC (T08.A49, M07a.A37); frozen, "
            "never re-scored against this document",
        },
        "use": "reference runs of the carried surface from RRC on (G16-b; RC step 8); no agent campaign is "
        "scored against this document",
        "change": "the offered solve policies (T10-C3 and constants.offered_policy_ids): RRC-revision-v1 added",
    }
    ```
  - `rrc_document(c2_doc, summary)`. This is `t08_document` with `OFFERED_POLICIES_RRC` and `carry_rrc()` in place
    of T08's, and `carry` sits in the same place, after `registration`. A copy of `t08_document` or a shared helper
    used by both is acceptable. GC-18.t08.reference_frozen is what proves the helper refactor inert.
  - `run_rrc_claims(result, r6, t08)` with the eight claims of GC-18 (§5, A2).
  - `build_rrc(result, r6, t08, rrc)`. It refuses to emit if any GC-18 claim fails, and it merges the claims of
    `result`, `r6`, `t08` and `rrc` into `generator_claims`.
- **`main`.**
  - Add `--emit-rrc PATH`, with help "write the carried-surface reference JSON after RRC (RRC-1)", and extend the
    `parser.error` text.
  - Under `--check`, after GC-17: compute `rrc = run_rrc_claims(result, r6, t08)`, report it as
    `_report(rrc[0], "claims of Amendment RRC-1 (GC-18)")`, return 1 on failure, and add
    `(RRC_JSON, dump(build_rrc(result, r6, t08, rrc)))` to the byte-identity loop.
  - `--emit-rrc` computes `r6`, `t08` and `rrc` as needed.
- **Unchanged:** sections 1–9, `OFFERED_POLICIES`, `OFFERED_POLICIES_T08`, GC-01…GC-17.

**E2. Emit only the new file.** Run `python docs/derivations/scripts/t07_reference.py --emit-rrc
docs/derivations/scripts/t07_reference_rrc.json`. Never re-emit the three frozen files.

**E3. `docs/derivations/T07-v17-tasks-spec.md`.** Append §6 of this note verbatim at the end of the file, after
Amendment T08-1. GC-18.spec.* reads it.

**E4. `benchmarks/t07/v17/scorer.py:138`.** Change it to `CARRIED_SURFACE_REFERENCE_PATH: Final =
REFERENCE_PATH.with_name("t07_reference_rrc.json")`. The comment above it reads: "Amendments T08-1 and RRC-1: the
reference runs of the carried surface (G16-b) are scored against `t07_reference_rrc.json` from RRC on
(`t07_reference_t08.json` from T08 to RRC, frozen), `v17-c2`'s document with only the offered set changed. A named
entry beside the campaigns', not one of them: no campaign is scored against it, and the default for an unnamed
campaign is unchanged." There is no logic change.

**E5. `tests/test_t07_v17_reference.py`.**

- In the module docstring, lines 6–7 read: "From T08 on they are scored against `t07_reference_t08.json` (V17 spec
  Amendment T08-1), and from RRC on against `t07_reference_rrc.json` (Amendment RRC-1; `reference.run`)."
- Add the test of A5, which follows G16-g's pattern and uses the module-scoped `runs`, so it adds no runs:
  ```python
  T08_REFERENCE = scorer.load_reference(scorer.REFERENCE_PATH.with_name("t07_reference_t08.json"))
  RRC_OFFERED = ["RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"]

  @pytest.mark.parametrize("transport", reference.TRANSPORTS)
  def test_rrc1_t10_answers_rrcs_five_and_fails_t08s_four(runs: dict[str, Any], transport: str) -> None:
      """Amendment RRC-1: the T10 reference run answers the five offered ids; they meet T10-C3 under
      `t07_reference_rrc.json` and fail it under `t07_reference_t08.json` (exact_set is exact)."""
      assert scorer.CARRIED_SURFACE_REFERENCE_PATH.name == "t07_reference_rrc.json"
      expected = reference.CARRIED_SURFACE_REFERENCE["tasks"]["V17-T10"]["answer"]["offered_policy_ids"]
      assert expected["expected"] == RRC_OFFERED
      record = _record(runs, "V17-T10", transport)
      answered = record.session.answer["offered_policy_ids"]
      assert len(answered) == 5 and sorted(answered) == RRC_OFFERED
      assert record.scores["completion"]["conditions"] == {"T10-C1": True, "T10-C2": True, "T10-C3": True}
      old = scorer.score(record.directory, T08_REFERENCE)["completion"]["conditions"]
      assert old == {"T10-C1": True, "T10-C2": True, "T10-C3": False}
  ```

**E6. `scripts/m07a_rc.py:18`.** This is a docstring only, and the module still runs step 8. Change "40 of 40 clean
against `t07_reference_t08.json` (unchanged from T08.A49; …" to "40 of 40 clean against the carried-surface
reference (`scorer.CARRIED_SURFACE_REFERENCE_PATH`: `t07_reference_t08.json` at the alpha, `t07_reference_rrc.json`
from RRC on, V17 spec Amendment RRC-1; …". Constants and checks are not touched.

**E7. Register entry `R-996`**, in `docs/decision-register.md` on `wp/RRC`. R-996 is the next free number after
RRC's R-990…R-995. If `main` holds R-996 at merge, take the next free number and say so in D-46. Follow the
neighbours' table form:

- **Title:** "V17-T10 after RRC: a fourth carried-surface reference, `t07_reference_rrc.json`; T08's is frozen
  (2026-11-09)".
- **Normative text:** T07 V17 spec Amendment RRC-1 (GC-18), and this note.
- **Affected packages:** RRC, and every later package that adds an id to `get_project.solve_policies`.
- **Decision:** R1 above.
- **Rejected:** §3, first two bullets.
- **Watch for:** `t07_reference_t08.json` edited; `RRC-revision-v1` dropped from T10-C3 by B13's rule.

**E8. `docs/RRC_DECISIONS.md` D-46.** Record the application: the four `--check` lines with their counts and the
four shas, the new document's sha256, the hand negative control (A7) and the test counts. Record the evidence
manifest's commands as actually run.

**What does not change:**

- the three frozen JSONs;
- `benchmarks/t07/v17/reference.py`, which follows `CARRIED_SURFACE_REFERENCE`;
- `scripts/release_rc.py`, `release-procedure.md` and `release/acceptances.md`;
- the T08 specifications and the V02-alpha specification (records);
- D-45/B27;
- the `project_summary` fixture, which RRC already moved.

## 5. Assertions (all exact; no tolerance applies, as every comparison is of bytes, ids or booleans)

| # | What | Expected |
|---|---|---|
| A1 | E0: `--check` on the unedited `wp/RRC` | exit 0; T08 line shows sha256 `f946a88f268acc0b690e24f5fb1c358611b5333e169468bd2ae861f8a13148b9` |
| A2 | `--check` after E1–E3 | exit 0; `claims of Amendment RRC-1 (GC-18): 8 of 8 pass`; four `byte-identical` lines with `cba24a92…`, `23b924b8…`, `f946a88f…` and the new sha |
| A3 | `git diff --exit-code main -- docs/derivations/scripts/t07_reference.json docs/derivations/scripts/t07_reference_c2.json docs/derivations/scripts/t07_reference_t08.json` | no difference |
| A4 | sanity values of `t07_reference_rrc.json` (by hand, in D-46) | `generator_claims.count` = 2863 (T08's 2855 + 8); families add `GC-18.t08`: 1, `GC-18.changes_exactly`: 1, `GC-18.offered`: 2, `GC-18.carry`: 1, `GC-18.spec`: 3; top-level key order equal to T08's document's |
| A5 | `pytest tests/test_t07_v17_reference.py` with the `server` extra | G16-b 40/40, including V17-T10 on all four transports; `test_rrc1_…` 4/4; G16-g and F6 (≤ 300 s) pass as before |
| A6 | `pytest tests/test_t07_w7b_scorer.py tests/test_t07_v17_c2.py tests/test_t08_b50_surface_content.py tests/test_m07a_surface_chain.py tests/test_t08_evidence_manifest.py` | all pass, unchanged |
| A7 | hand negative control (not committed): remove `RRC-revision-v1` from `OFFERED_POLICIES_RRC`, run `--check`, revert | exit 1; `claims of Amendment RRC-1 (GC-18): 7 of 8 pass`, the one `FAIL` being `GC-18.offered.adds_exactly_rrc_sorted_unique` (the spec still quotes T08's four-set, so GC-18.7 passes) |
| A8 | `ruff check`, `ruff format --check`, `mypy` on the edited Python files (the generator is linted in CI) | clean |
| A9 | CI on `wp/RRC` | green on both architectures (merge condition) |

**GC-18** (in `run_rrc_claims`; each a named claim, and `--check` fails if any fails):

1. `GC-18.t08.reference_frozen`: `sha256(dump(build_t08(result, r6, t08))) == T08_REFERENCE_SHA256`.
2. `GC-18.changes_exactly`: `set(sig_diff(_without(c2_doc, "generator_claims"), _without(body,
   "generator_claims"))) == RRC_CHANGED_PATHS`, with `body = rrc_document(c2_doc, None)`.
3. `GC-18.offered.adds_exactly_rrc_sorted_unique`: `set(OFFERED_POLICIES_RRC) - set(OFFERED_POLICIES_T08) ==
   {"RRC-revision-v1"}`, `set(OFFERED_POLICIES_T08) < set(OFFERED_POLICIES_RRC)`, and `list(OFFERED_POLICIES_RRC) ==
   sorted(set(OFFERED_POLICIES_RRC))`.
4. `GC-18.offered.item_7_still_unoffered`: `"T06-revision-v1" not in OFFERED_POLICIES_RRC`, and
   `'"T06-revision-v1"'` is in `body["tasks"]["V17-T10"]["body"]`.
5. `GC-18.carry.names_frozen_documents`: `body["carry"]["base"]["reference_sha256"] == C2_REFERENCE_SHA256`, and
   `body["carry"]["supersedes"]["reference_sha256"] == T08_REFERENCE_SHA256`.
6. `GC-18.spec.amendment_present`: `"## Amendment RRC-1"` is in the spec.
7. `GC-18.spec.quotes_offered_set`: `{"RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1",
   "T08-warm-v1"}` is in the spec, built as GC-17 builds its quote.
8. `GC-18.spec.quotes_t08_reference_sha`: `T08_REFERENCE_SHA256` is in the spec.

**Why these are enough.**

- **A5's second half** is the falsifier. It is the CI failure itself (`{'T10-C1': True, 'T10-C2': True, 'T10-C3':
  False}`, run 42547017088), now asserted as the expected outcome against the predecessor document. So if
  `exact_set` were scored as a superset, or the surface stopped serving the fifth id, the test would fail.
- **GC-18.1 and A3** together hold the three earlier documents. GC-18.2 together with GC-18.3 pins the one change.
- **A7** shows that GC-18.3 bites.

## 6. Text to append to the T07 V17 spec (E3, verbatim)

```markdown
## Amendment RRC-1 (the carried surface after RRC; ADR 0072, R-995) — 2026-11-09

**Author:** design lane (`specifier`), ruling `docs/reviews/RRC-v17-t10.md`. **Authority.** This amendment is part of this specification. It adds a registration for reference runs of the carried surface from RRC on. It changes no task, prompt, oracle or footer of `v17-c1` or `v17-c2`, it changes nothing in Amendment T08-1, and it re-scores no run.

**Why.** RRC offers one more solve policy, `RRC-revision-v1`, by name and never as a route's default (ADR 0072, R-995). It is a content-only addition to `get_project.solve_policies` named by a register entry, which M07a's MR-7 clause admits under Frank's F5 (2026-09-29); ADR 0072 C1 measured the served tool-list digest `455d01eb…` and the surface chain unchanged. Amendment T08-1 registered T10-C3's set as `{"T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"}` and requires an amendment of its kind for each later content change. G16-b's T10 reference solution answers from the live `get_project` and failed on all four transports and both architectures (CI run 42547017088, `wp/RRC` `fcba6656`: T10-C3 false, T10-C1 and T10-C2 true).

**Decision.**
1. **A fourth document.** `t07_reference.py --emit-rrc` writes `docs/derivations/scripts/t07_reference_rrc.json`. It is `t07_reference_c2.json`'s document with exactly these changes, and no others (GC-18.changes_exactly):
   - `constants.offered_policy_ids` and `tasks.V17-T10.answer.offered_policy_ids.expected` become `["RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"]`;
   - a member `carry`, where T08-1's stands, states the base (`v17-c2`, as T08-1's does), the document it supersedes (`t07_reference_t08.json`, sha256 `f946a88f268acc0b690e24f5fb1c358611b5333e169468bd2ae861f8a13148b9`), F5 as MR-7 applies it, and the document's use;
   - `generator_claims` counts GC-18 as well.
2. **T10-C3 for reference runs from RRC on** reads: `answer.offered_policy_ids` is an array whose elements, as a set, equal `{"RRC-revision-v1", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"}`. T10-C1, T10-C2 and item 7's `T06-revision-v1` (still not offered, GC-18.offered.item_7_still_unoffered) are unchanged.
3. **Who reads what.**
   - Runs recorded under `v17-c1` and `v17-c2` keep their documents (SC-13 unchanged). `t07_reference.json` stays at `cba24a92…` (GC-16), `t07_reference_c2.json` at `23b924b8…` (GC-17), and `t07_reference_t08.json` at `f946a88f…` (GC-18.t08.reference_frozen).
   - The reference runs of the carried surface — G16-b in `tests/test_t07_v17_reference.py` and in the RC job's step 8 — are scored against `t07_reference_rrc.json` from RRC on, and `scores.json`'s `inputs.reference_sha256` names it. G16-b as recorded for T08.A49 and M07a.A37 stays as recorded.
   - No agent campaign is scored against the new document; a new campaign would need its own amendment and Frank's approval (R-115).
4. **Nothing is re-scored** (R-087).

**GC-18** (in `run_rrc_claims`; `--check` fails if any fails): `t08.reference_frozen`; `changes_exactly` (the paths that differ from the c2 document, `generator_claims` aside, are exactly `carry`, `constants.offered_policy_ids` and `tasks.V17-T10.answer.offered_policy_ids.expected`); `offered.adds_exactly_rrc_sorted_unique`; `offered.item_7_still_unoffered`; `carry.names_frozen_documents`; `spec.amendment_present`, `spec.quotes_offered_set` and `spec.quotes_t08_reference_sha`.

**Rejected alternatives, and why.** Editing T08-1's set in place (it moves bytes T08-1, GC-17, T08.A49 and M07a.A37 describe); excluding `RRC-revision-v1` from T10-C3 by B13's rule (B27 measures what T08 delivered, T10-C3 what the contract offers: the expectation would be false); hiding it from `get_project` (contradicts R-995); an oracle from the live surface or a superset test (T08-1's reasons).

**Build-lane changes.** `scorer.CARRIED_SURFACE_REFERENCE_PATH` names `t07_reference_rrc.json`; `tests/test_t07_v17_reference.py` gains the RRC-1 test (T10 meets T10-C3 under this document and fails it under T08-1's).

**Watch for.** `t07_reference_t08.json` edited (GC-18 refuses); an offered id dropped from T10-C3 by a package's own exclusion rule; a later offered id without its own amendment.

**What this amendment does not establish.** It is no evidence of agent behaviour with `RRC-revision-v1` offered, since no session was run. It is not a re-judgement of `v17-c1`, `v17-c2`, or T08's or the alpha's G16-b. It is not a licence for later content changes: each needs its own amendment of this kind.
```

## 7. What this ruling does not establish

- It is **no agent evidence**. No agent session ran on the RRC surface. The V17 carry covers the surface and the
  scripted reference solutions, not how an agent uses a fifth policy whose name resembles item 7's
  `T06-revision-v1`.
- It does **not validate RRC's numerics**. G16-b proves the reference solutions score clean, nothing more.
- It does **not re-judge** `v17-c1`, `v17-c2`, T08.A49, M07a.A37 or D-45.
- The **checks I ran** were the shas of the three committed documents (`cba24a92…`, `23b924b8…`, `f946a88f…`) and
  the sorted, unique, one-addition property of the five-set. I did not run the generator. The T08 pin rests on the
  committed file, and A1 confirms that it regenerates.

## 8. Open questions (each with a default; none blocks)

- **Q1 (needs a fact): should `t07_reference.py --check` run in CI?** Today no test runs it.
  `tests/test_t08_reference_generators.py` covers three other generators, and preflight G16-f runs it only before a
  campaign. So a hand edit to a committed T07 JSON would surface only through the tests that read it. The fact that
  settles this is the `--check` wall time on the CI runner. **Default:** not added in RRC, following T08-1's
  precedent, with A1 and A2 run by hand and recorded in D-46. Propose a separate test item if the time is
  ≤ 60 s.
- **Q2 (design lane, at the next occurrence): a document per content change costs about 248 KB each.**
  **Default:** keep R1. If a third content change arrives, consider one generated document per surface with the
  earlier ones frozen. Do not decide that now.

**Needs Frank: no.** F5 is his standing ruling, MR-7 admits register-named additions (R-995), the `V17 carry`
acceptance's terms (links, served digest) do not move, no campaign is added, and no check is relaxed.
