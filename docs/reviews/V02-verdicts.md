# V02 — verdicts on V11–V20 and W21–W27 for `0.2.0`

**Release candidate:** `ce993651ce37c1343e771b276160bd6623e43500`   **Judged:** 2026-10-20   **By:** design lane (`verdict`)
**Re-judged:** 2026-10-20 (V13, V17, W21, W24)

*First issued 2026-10-19. W21 judged again on 2026-10-20 in a new judgement (§19.2 item 2), which moves the date above; see "W21 re-judged (2026-10-20)". V13, V17, W21 and W24 then re-judged on 2026-10-20 on Frank's ADR 0042 answers; see "Re-judgement". Every other row stands as judged on 2026-10-19.*

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | T08 §4.1 with MR-10; at C′: K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and M07a.A42 green in step 1 (CI 39291243747, both architectures) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (alpha spec §5.1); at C′: T05, T05b and build-first B10–B19 nodes green in step 1 on both architectures; coupled cases SYN-001, T05 C1–C3, PTC-R1 |
| V13 | PASS | — | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3, T08.A71 and MR-7; at C′: T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51 (step 1), digest and schemas by the chain (step 8, three hosts, link c_3 included), under Frank's `V17 carry` (ADR 0042, accepted 2026-10-20); re-judged 2026-10-20 |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43 | T08 §4.4; T08-verdict-V14b.md (PTC-R1: the saddle clause fails on both registered platforms), unchanged at C′ (no PTC family or SER settings preregistered since); Frank's D3 acceptance in ADR 0042 pending; homotopy and edges: T04, T02 and T08.A33 nodes green in step 1 |
| V15 | PASS | — | L02, L14, L19, L20, L33 | T08 §4.5; at C′: T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both architectures; all five step-12 certificates carry uniqueness and dynamic stability NOT_ASSESSED (checked here) |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands (8 of 8 by both tools, 16/16 AGREE); T08.A48 passes 12/12 at C′ on ref-x86-64, ci-x86-64 and ci-aarch64 (step 7, 165 nodes) |
| V17 | PASS | — | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6; Frank's `V17 carry` of v17-c2's agent evidence across R-192, R-234 and R-295 (ADR 0042, accepted 2026-10-20; re-judged 2026-10-20); M07a.A37 at C′ on three hosts: served digest 455d01eb… strips by c_3 (R-295) to 383b4e2c…, by c_2 to 6c4375b4…, by c_1 to 171dd768…, and gives 6d13e13d… with v17-c2's texts; G16-b 40 of 40 |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12 as M07 §24.1 restates them; at C′: T08.A30 PASS on three hosts (182 modules walked, 179 imported, the three registered nlp-extra modules refused as registered); MR-12 for the nlp extra by S9.4 (audit, step 14's inventory check, R-450); T08.A34 0 violations on every audited set; T08.A31–A33 nodes green |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); the dossier and benchmarks/t08/v19 byte-identical to the alpha candidate's (git diff cc73219 C′ empty, checked here); the A60–A64 record tests green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; at C′: T08.A46 S = 434 of 440 on ref-x86-64 and ci-aarch64 (gate 418), no crash, no other-root, same-class replay 28/28; T08.A47 12/12 on three hosts; T08.A10 node green |
| W21 | PASS | — | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | alpha spec §6.1 and §19.6 (R-375); step 12 at C′: G10v3, G11v3 and G12 met, reproduce and live rerun as at the alpha; judged again 2026-10-20: G11 re-run at C′ with outcomes equal to step 12's record, its 210 experiment results (105 boundary points per run, 2 runs) kept under rc/step12/experiments/ and audited for blueprint §9.1's six items against the schema, 0 problems (audit re-run here, denominator checked against step 12's original record); the notes' section carries the four reactor statements; M02 N1 accepted by Frank (ADR 0042, 2026-10-20), "not a sandbox" in the support matrix and the notes at C′; re-judged 2026-10-20 |
| W22 | PASS | — | L42, L47 | alpha spec §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green on both architectures; step 11: crosscheck byte-equal on recomputation, IDAES re-run numbers identical; step 12: G12 VERIFIED on the route |
| W23 | PASS | — | L49 | M07 §7.3 and M04 §15: A01–A30, A34, A35 green in the default gate, A31–A32 recorded for the real variant (NOT_PROMOTABLE); step 13 at C′: m04_reference --check 11943 claims, schema fixtures exit 0, 485 M04 and manifest tests passed with none skipped |
| W24 | PASS | — | L19, L44, L46, L48, L49 | M07 §7.3; step 14 at C′ in the audited nlp environment: nlp tier 186 passed, inventory check exit 0 for both workloads, M03 and M05 tiers 640 passed, M05's REAL record replays with 0 differences, m03_reference --check exit 0; M03 N1 (the nlp extra's licences) accepted by Frank (ADR 0042, 2026-10-20); re-judged 2026-10-20 |
| W25 | PASS | — | L44, L45, L46, L48, L49 | M07 §5 on the journey record of K = 2c508b5 (A3.4): step 15 at C′ carried, check ACCEPT, replay bitwise; J.1 at C′; decision refined at 653.1500351610193 K at the lower bound, TC-1 holds; check and carry re-run here |
| W26 | PASS | — | L-WEB-1, L-WEB-2, L-WEB-3, L-WEB-4 | M07 §7.3; step 16 at C′: M06 tests with the browser required 661 passed, node 92 of 92, W27 dry run A23 PASS; step 1's CI x86-64 check ran with OPENFLOWSHEET_REQUIRE_BROWSER=1 and skipped no browser node |
| W27 | PASS | — | L40 | M07 §7.3, §9 and §22; W27-verdict-83f825d.md: the seven clauses judged at C_W 83f825d met, the aggregate re-judged met on 4812910a…9e28; the carry to C′ is step 17: record tree 95f9fcf2… equals the judged record, coverage at C′ exit 0, carry members equal (3c0e08c7…), campaign.json recomputed with an empty diff |

## Re-judgement

**2026-10-20, at the same candidate C′ = `ce99365…`, under alpha spec §19.2 (R-371) as ADR 0042 and the `v0.2-gate-v1`
entry carry it.** Four rows change, in place: V13, V17, W21 and W24 go from `BLOCKED` to `PASS`. No other row changes.
`Judged` stays 2026-10-20, the date of W21's new judgement. From "Read this first" onward, this document is kept as
recorded. For the four rows, this section replaces the verdict lines of their sections, the "Verdict: W21 `BLOCKED`"
line of "W21 re-judged (2026-10-20)", and the statement that all five ADR 0042 cells read `pending`. For every clause
not named below, the earlier text and evidence stand. This is still an agent verdict, numerical and procedural only. It
sets no `reviewed`, claims no scientific review or human sign-off, and moves no tolerance, band or classification rule.

**Nothing at C′ has moved.** The candidate and its step records are those judged on 2026-10-19 and in W21's new
judgement. The only new input is ADR 0042's five cells. `git diff` of the working tree against `HEAD` shows only those
five cells changed in ADR 0042 (read here, uncommitted at the time of reading). The other uncommitted files are
`docs/requirements.yaml`, M07's manifest draft and this document, and none of them is a D2.4 path.

### The answers read (ADR 0042, l.28–37 of the working tree)

| Item read | Cell | Table T7, with J = R = 2026-10-20 | Counts | What it does here |
| --- | --- | --- | --- | --- |
| decisions, `V17 carry` | `accepted, 2026-10-20` — Frank, verbatim: "Accept all five (Recommended)" (the default in this row) | J ≤ 2026-10-20 ≤ R: V13 and V17, listed, wait on it | yes | unblocks clause (e) of V13 and clause (a) of V17 |
| decisions, `M02 N1` | as above | J ≤ 2026-10-20 ≤ R: W21, listed, waits on it | yes | unblocks clause (c) of W21 |
| decisions, `M03 N1` | as above | J ≤ 2026-10-20 ≤ R: W24, listed, waits on it | yes | unblocks clause (a) of W24 |
| decisions, `Claim set` | as above | ≥ J; no listed gate waits on it | yes | confirms the claim set judged here, `v0.2-gate-v1` (all seventeen rows) |
| D3, clause `V14 (b)` | as above | ≥ J; V14 is not listed (Table T8 cannot list it) | yes | changes no verdict word. V14 stays `FAIL`, and the FAIL becomes releasable (D2.3), with PTC experimental. It is not a re-judgement |

**What these answers are.** Each cell takes its row's default. None chooses an alternative or declines. So §7.3 item
11's refusal does not apply. The `V17 carry` row names R-192, R-234 and R-295. Those are the registers of every link
in `scripts/m07a_rc.py` `LINKS` at C′ (c_1, c_2 and c_3, re-read here with `git show ce99365:scripts/m07a_rc.py`). The
build lane recorded the cells in ADR 0042. They record Frank's single verbatim answer, "Accept all five
(Recommended)", which `docs/V02_DECISIONS.md` l.1193 logs (commit `30a6334`, 2026-10-20 00:57 +0200), given after the
five items were put to him in plain words. This verdict did not witness that exchange. It reads the record as the
authority's decision, as the alpha's re-judgement read ADR 0028. Evidence class: decisions.

**Same-day sequencing (a limitation, not a failure).** Table T7's rule is day-granular, and every cell's date equals J
and R. By the timestamps, the answer was logged at 00:57 +0200. G11's kept results existed from 2026-10-19 23:24, and
the text of W21's new judgement was last written at 01:29. So Frank may have answered before he read W21's new text.
The registered rule is met as written. M02 N1's subject is clause (c), the out-of-process policy and its "not a
sandbox" label, and it does not depend on the (e) evidence that the new judgement added. The answer therefore waives
nothing that the new judgement found.

### V13 — BLOCKED → PASS (clause (e) judged again)

- **(e) compatible warm starts: met.** The B40–B49 nodes are green in step 1. B50's counterpart (MR-7) has its content
  by M07a.A51 (step 1), and its digest and schemas by the chain, M07a.A37, 8/8 on three hosts with link c_3, as judged
  on 2026-10-19 (V13 table). The carry that MR-7 names is now ADR 0042's `V17 carry`, accepted 2026-10-20. Its row
  names "V17, and T08.B50's surface", all three links and §5.3's chain.
- (a)–(d): met, unchanged.
- **Against the alpha (PASS).** Same word. The carry is now dated for 0.2.0 and spans c_3 (R-295) as well.
- **Does not establish:** that agents behave correctly on the v0.2 surface, because Frank's carry accepts that
  evidence and does not measure it. Nor warm starts beyond exact id-set compatibility (L-WS-1, L-WS-2).

### V17 — BLOCKED → PASS (clause (a) judged again)

- **(a) a surface to which Frank has carried `v17-c2`'s evidence, with M07a.A37's chain holding: met.** The carry is
  ADR 0042's `V17 carry`, accepted 2026-10-20, across R-192, R-234 and R-295. The chain is as read on 2026-10-19:
  `455d01eb…` → `383b4e2c…` (strip c_3) → `6c4375b4…` (strip c_2) → `171dd768…` (strip c_1), and `6d13e13d…` with
  `v17-c2`'s texts. The 17 tools and description files are as registered. The step-8 records were not re-read in this
  re-judgement, because C′ and its records are unchanged since then.
- (b) G16-b 40 of 40: met, unchanged.
- **Evidence classes.** The chain is identity verification against registered digests, tested on three hosts. The
  agent evidence is `v17-c2`'s, measured on the R-137 surface, and it reaches 0.2.0 only by Frank's decision. No
  agent ran on the 0.2.0 surface (L12).

### W21 — BLOCKED → PASS (clause (c) judged again)

- **(c) out-of-process execution policy: met.**
  - G3–G5 nodes in step 1: unchanged.
  - At C′, the support matrix row "External model execution" (l.23) states `external-subprocess-v1`, "not a sandbox",
    and "Linux is registered; macOS best effort; Windows is refused before spawn". L45 (l.136) states it again.
  - The `## v0.2.0` notes carry "not a sandbox" under "What it is not" (`CHANGELOG.md` l.194).
  - All of the above re-read here from `ce99365`.
  - M02 N1 was accepted on 2026-10-20 with its default, "ship the reactor child process labelled 'not a sandbox'".
- (a), (b), (d), (e) and (f): met, as judged on 2026-10-19 and in W21's new judgement (2026-10-20).
- **Does not establish:** that the reactor is right (L46), or that the child process is isolated. It is not
  isolated, and that is what the label says (L45).

### W24 — BLOCKED → PASS (clause (a) judged again)

- **(a) M03's fixed-topology NLP with final parent checks: met.** Step 14 at C′, in the audited nlp environment: the
  nlp tier passed 186, and inventory `--check` exited 0 for both workloads. MR-12 for the nlp extra holds by S9.4
  (V18). M03 N1 was accepted on 2026-10-20 with its default, "accept the licences of the optional `nlp` extra".
- (b)–(g): met, unchanged.
- **Evidence classes.** The inventory is a tested record. The licence acceptance is a decision.
- **Does not establish:** global optimality; any optimization result on aarch64; the licences' fitness for a user's
  own use beyond Frank's acceptance for this release.

### After this re-judgement

Sixteen PASS. One FAIL, V14 on (b), which D3 accepts. None BLOCKED. D2.2 and D2.3 no longer refuse a row of this
document. Whether the gate may propose the tag depends on its other items (M07's manifest, and ADR 0041 and ADR 0042
`Accepted`), which this document does not decide. For the gate to read ADR 0042's cells as read here, they must be
committed unchanged. **What would reopen these four rows:** any of the five cells withdrawn or changed; a committed
ADR 0042 whose cells differ from those read here; any change to a D2.4 path, which makes a new candidate on which
every row is judged again. **Limitations that travel with them:** V13 and V17 rest on Frank's carry, with no agent
measured on the 0.2.0 surface (L12). W21 (c) rests on an accepted "not a sandbox" profile (L45). W24 (a) rests on the
nlp extra's licences being accepted by decision. V14 (b) is an accepted FAIL, with PTC experimental. All five answers
are dated the same day as `Judged` (the sequencing note above).

**F10 (notes; before the tag).** The `## v0.2.0` bullet reads only "not a sandbox" and does not name the reactor child
process. The support matrix and L45 do name it, so (c) is met. A reader of the notes alone has to infer what the bullet
refers to, and "the reactor child process is not a sandbox" would remove the inference. This finding is a
recommendation and does not change the verdict.

## Read this first

*Since the 2026-10-20 re-judgement (above): sixteen PASS, one FAIL (V14 on clause (b), accepted in ADR 0042 D3), none BLOCKED. Before it, after W21's new judgement: twelve PASS, one FAIL, four BLOCKED (V13, V17, W21, W24). The paragraphs below are the 2026-10-19 text, kept.*

**The seventeen.** Twelve PASS (V11, V12, V15, V16, V18, V19, V20, W22, W23, W25, W26, W27). Two FAIL: V14 on clause
(b), as at v0.1 and the alpha, and **W21 on clause (e)**, which is new. Three BLOCKED (V13, V17, W24), each on one
answer only Frank can give. No YES is possible from this document: D2.2 refuses a `BLOCKED` claimed gate, and D2.3
refuses W21's `FAIL`, whose clause is not in ADR 0042's D3 table and should not be put there (see W21).

**W21 differs from what the registered waits predicted.** `rejudge_waits` lists W21 as waiting on M02 N1, and its
out-of-process clause (c) does wait on it. But clause (e) is not met at C′ for a reason inside the lanes' authority.
The alpha accepted W21 (e) on an inference about G11's experiment results (alpha verdict, W21 (e) and rejected
alternative 7) *because* R-375 (alpha spec §19.6 A6) deferred the per-result audit to 0.2.0's RC: "At 0.2.0, step 12
keeps G11's results under `rc/step12/experiments/` … An audit then checks blueprint §9.1's six items in each result
against `experiment.schema.json`." At C′ neither happened (checked: no `experiments/` under
`evidence/M07/ce99365…/rc/step12/`, no audit row in the RC record, and `benchmarks/m02/g11_coverage_v3.py` l.499 runs
each point in a `tempfile.TemporaryDirectory`, so the results are gone). Evidence the lanes were to produce and did not
is `FAIL`, never `BLOCKED` (T08 §3.3). The repair costs about fifty minutes of local compute and no money (see "What
would change").

**Against the alpha's verdicts** (`docs/reviews/V02-alpha-verdicts.md`, `C_α²` = `cc73219`, re-judged 2026-10-17):
- V13 and V17: PASS → BLOCKED. The alpha's carry was ADR 0028's answer, dated for `0.2.0a1`. ADR 0042 asks again for
  0.2.0 (D2: "an acceptance dated before the evidence is a waiver"), and the surface gained link c_3 (R-295).
- W21: PASS → FAIL on (e), for the reason above; (c) is pending again for the same reason as V13 and V17.
- V14 stays FAIL; the other eight V rows and W22 keep the alpha's verdicts, each re-judged on C′'s own records.
- W23–W27 were not claimed by the alpha.

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review and not a
process-model sign-off. It sets no `reviewed`, claims no human sign-off, and moves no tolerance, band or classification
rule. Human sign-off is Frank's and is recorded separately.

**Criteria, read before the evidence:** M07 spec §5 (W25 (a)–(h)), §7.1–§7.3, §8, §9, and Amendments 3–7 (§20 A3.4,
§22, §23.2, §24); the alpha spec §4–§6, §8.2 and §19 (Amendment 3, incl. §19.2 and §19.6), with T08 §3.3 and §4;
M04 spec §15 (W23); the W27 registration's W27-R57; ADR 0042 as it stands (all five cells `pending`); the register
entries R-375, R-450, R-478…R-484.

**Precondition.** M07's own manifest is written after this document (M07 spec §8 [A6]), as M07a's was for the alpha.
The step records are the evidence; M01–M06's manifests are evidence about their own commits and count only through the
RC job (alpha spec §4 rule 3).

## Frank's answers each row waits on (ADR 0042, `docs/adr/0042-v0.2.0-release-policy.md`)

All five cells read `pending`. Under ADR 0042 D2 and Tables T6/T7 (alpha spec §7.2, §19.2), an answer counts only if it
starts `accepted, YYYY-MM-DD` with a date **on or after 2026-10-20**, this document's `Judged` date (2026-10-19 until W21's new judgement); an answer a
re-judgement reads must also be dated on or before that re-judgement's date. Frank's informal answers of 2026-10-16
and 2026-10-18 predate this verdict and do not count until recorded with such a date.

| Row (verdict, clause) | ADR 0042 table and item | What a counting answer looks like | What it does |
| --- | --- | --- | --- |
| V13 BLOCKED, clause (e) | decisions, `V17 carry` | `accepted, <date>`, 2026-10-20 ≤ date ≤ the re-judgement's date | unblocks (e); expected met, since M07a.A37 and A51 hold at C′ |
| V17 BLOCKED, clause (a) | decisions, `V17 carry` (the same answer) | as above | unblocks (a), as above |
| W24 BLOCKED, clause (a) | decisions, `M03 N1` | as above | unblocks (a), whose evidence (step 14) is otherwise met |
| W21 BLOCKED, clause (c) (since 2026-10-20; (e) met) | decisions, `M02 N1` | `accepted, <date>`, 2026-10-20 ≤ date ≤ the re-judgement's date | unblocks (c); with (a), (b), (d), (e) and (f) met, W21 is then expected PASS |
| V14 FAIL, clause (b) | D3, row `V14 (b)` | `accepted, <date>`, date ≥ 2026-10-20 | changes no verdict word; makes the FAIL releasable (D2.3) |
| no row (gate item 11) | decisions, `Claim set` | `accepted, <date>`, date ≥ 2026-10-20 | confirms the claim set judged here (all seventeen) |

**Sequencing.** §19.2 item 2: a re-judgement may list only gates `BLOCKED` on a registered answer. W21 is `FAIL` on
evidence the lanes owe, so its change after the G11 audit is a **new judgement**, with a new `Judged` date, and every
answer must then be dated on or after it. The cheapest order is: the audit first, then the re-issued verdict, then
Frank's answers recorded with dates on or after the new `Judged`.

Choosing an alternative or declining is not an acceptance (alpha spec §7.3 item 11): a new V17 campaign, a declined
M02 N1 or M03 N1, or a different claim set each needs a spec amendment, not a D3 row.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/v02-rc-record.md` (records commit `2fd23a6`) | build lane: local `ref-x86-64`, detached worktree at C′ clean at start, after the venv, after the W27 hard links and at end; `tools/run_local.sh`, 50 commands, every exit 0; threads pinned. CI dispatch 39291243747 and push 39276061202, 39291243653, 39311681016 | none: the record reports and judges nothing. Checked here with `gh run view`: 39291243747 is `workflow_dispatch`, head `ce99365…`, `success`; 39311681016 is `push`, head `2fd23a6`, `success` | record |
| The 92 records it hashes (`rc/records.json`) | as above; 87 committed as is, 5 gzip-compressed | **recomputed here: 92 of 92 sha256 and byte counts equal** (gzip ones decompressed). Every one of the RC record's 89 distinct record hashes is in `records.json`; the two other 64-hex tokens are the campaign digest and the D78 extract, named values | provenance |
| M07a.A43 on those records | the records themselves | checked here: 36 provenance-bearing records carry `commit` = `ce99365…`, `tree_clean` true, lock `ead4edf1…`; none deviates | provenance |
| Step 1: x86-64 9911 passed, 106 skipped; aarch64 9882 passed, 105 skipped; 192 deselected each | CI 39291243747 | summary lines and `check.sh: PASSED` grepped here from the hash-pinned job logs, both naming `ce99365…` | tested (CI) |
| Step 1's skip set (R-376) | `evidence/M07/ce99365…/step1-skips/ci-x86-64.txt` (`b8d28407…`), `ci-aarch64.txt` (`338d361d…`) | classified here (skip audit below); totals 106 and 105 | record |
| Steps 2–10 (`t08-rc-v1`, A30 summaries) | as in the RC record | registered values: R-149's identity digests; D_0…D_3 and R-137's digest; S_min 418; A34's rule; S9.1–S9.4 | ci, tested, record |
| Steps 11–17 records `stepNN/rc-stepNN.json` | local; step 12 in the reactor environment from C′'s lock (`032a050c…`), one thread, possibly shared host; step 14 in m05's audited nlp environment under `env -i` | per step as cited below; every check `pass`, commit C′, tree clean (read here) | numerical verification against registered records; regression of the group's model (12, 15) |
| Step 12's five kept certificates | committed under `rc/step12/certificates/` | read here: all five carry `uniqueness` and `dynamic_stability` `NOT_ASSESSED` and regularity `NO_RANK_LOSS_DETECTED`; step 10 audits them (0 violations) | provenance |
| G11's experiment results at C′ | written by `g11_coverage_v3.py` into temporary stores, deleted at exit | **none kept**; `step12/g11-coverage-v3.runs.json` holds per-point summaries (status, stage, defects), not result records with provenance members (read here) | **absent** (R-375) |
| Journey record `benchmarks/m07/journey/2c508b5…/` | build lane at K, clean tree, m05 nlp environment, `OMP_NUM_THREADS=1` (J54) | **re-run here:** `m07_journey.py check` → `check: ACCEPT`; `v0_2_gate.py --rc ce99365 --carry-journey 2c508b5` → carried, exit 0. Numbers equal J′'s (`974c395`), the reviewed record, except walls, digests and commit (J54) | numerical verification of a workflow; record |
| W27 campaign `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/` | Claude Code sessions at C_W; judged in `docs/reviews/W27-verdict-83f825d.md` | **checked here:** `git rev-parse ce99365:<dir>` = `95f9fcf2…895a` = the tree at `89cd931` named in §22.1 | record; agent evidence (one model, k = 1) |
| M01–M06 manifests | build lane at their own commits | checked here: M01 `3c80392`, M02 `ba90619`, M03 `a35885b`, M04 `8df0ea7`, M05 `56fb2fa`, M06 `4719a1a` all `tested`, each an ancestor of C′ | evidence about other commits (rule 3) |
| Required ADRs | `docs/adr/` at `2fd23a6` | read here: 0022, 0026, 0027, 0030–0039 Accepted; 0041 and 0042 Proposed (their conditions follow this verdict and Frank's answers) | decisions |
| Frank's statements (R-145, R-450) and ADR 0042's cells | recorded by the lanes | none: the authority's decisions | decisions |

**What pins nothing.** Step 12's G11 and G12 wall times and step 14's durations were measured under whatever load the
host carried; they gate nothing. The journey's walls are within-platform records. Regenerated self-consistency (e.g.
`campaign.json` recomputing to the same bytes) shows determinism of the aggregate, not correctness of the scoring maps.

---

## V11 — PASS

(a) semantic diff, (b) immutable drafts, (c) task-specific validation, (d) units and component/reference checks: met by
the T07, K06, T01 and T06 nodes in step 1 on both architectures. (e) a real migration fixture: met by T08.A35 and
MR-10's counterpart M07a.A42 (`tests/test_m07a_v011_bundle.py`, the v0.1.1 bundle) in step 1. T08.A10 green.
**Does not establish:** migration of arbitrary old documents; structural checks are generic (L38).

## V12 — PASS

Every model of §14.3's list keeps its contract, limiting/failure, balance and derivative nodes, green in step 1 on both
architectures, and appears in a registered coupled case. The C1 and surrogate models are W21–W23's evidence, not V12's.
**Does not establish:** the listed model limitations.

## V13 — BLOCKED on V13 (e)

| Clause | Judgement | Evidence at C′ |
| --- | --- | --- |
| (a) DM/SCC/BTF | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes; E1/E2 library-level (L43) |
| (c) scales before iteration | met | K03 and T02 nodes |
| (d) model initialization | met | as at v0.1 and the alpha (K03 §10.1; L10) |
| (e) compatible warm starts | **blocked** | B40–B49 nodes green in step 1. B50's counterpart (MR-7): content by M07a.A51 (`tests/test_t08_b50_surface_content.py`, not in either skip file); digest and schemas by the chain, M07a.A37, 8/8 on three hosts with link c_3 (R-295). `t07_reference.json` and `t07_reference_c2.json` unchanged since `c7bbc98` (checked). **Missing:** the carry under which MR-7 places the digest and schemas, ADR 0042's `V17 carry` row ("V17, and T08.B50's surface"), `pending` |

**Does not establish:** that the v0.2 surface is acceptable for agents (Frank's carry decides that); warm starts beyond
exact id-set compatibility (L-WS-1, L-WS-2).

## V14 — FAIL on V14 (b)

- (a) typed homotopy: met (T04 A02–A12 in step 1).
- **(b) one PTC family qualified by §7.5: not met.** `T08-verdict-V14b.md`: the saddle clause fails on PTC-R1 on both
  registered platforms. `git diff cc73219 ce99365` touches no PTC, homotopy or globalization file, and no register
  entry since preregisters a family or SER settings (checked). The PTC-R1 diagnostic nodes skip on CI x86-64 (no
  committed results for that CPU); they bear on (b2), and (b1) fails regardless.
- (c) three bounded recovery edges: met (T02, T04, T08.A33).

ADR 0028's acceptance (for `0.2.0a1`) is not read (ADR 0042 D2). **Does not establish:** that PTC can never qualify
(L01).

## V15 — PASS

(a) frozen phase attempts with restart (T03 A00–A26), (b) cross-unit promotion without nested SM (T02), (c) multiple
roots with honest branch reporting (T03, T06 ADV-05, THM-09): met in step 1 on both architectures. The five step-12
certificates carry both claims `NOT_ASSESSED`. **Does not establish:** root completeness, uniqueness or stability (L19).

## V16 — PASS

T06 verdict 1 stands; T08.A48 12/12 on three hosts at C′. The tool side is not re-run (T08 §4.6). **Does not
establish:** IDAES agreement beyond the near-sharp ε (L16); the tools beyond their pins (L17).

## V17 — BLOCKED on V17 (a)

- **(a) blocked.** The chain holds on three hosts at C′: the served digest `455d01eb…` (equal to the W27 campaign's
  `surface.tool_descriptions_sha256`, §22.1) strips to `383b4e2c…` (D_2), `6c4375b4…` (D_1), `171dd768…` (D_0), and to
  `6d13e13d…` with `v17-c2`'s texts; the 17 tools and description files as registered. ADR 0042's `V17 carry` default
  names R-192, R-234 and R-295, every link of `scripts/m07a_rc.py` `LINKS` (the gate raises no links problem).
  **Missing:** Frank's answer, `pending`.
- (b) G16-b 40 of 40 over Python, CLI, HTTP and MCP: met on three hosts.

**Does not establish:** agent behaviour on the v0.2 surface; no V17 agent was run (L12).

## V18 — PASS

- **(a) met.** T08.A30 `PASS` on ref-x86-64 (266 objects, closure 150), ci-x86-64 (266, 150), ci-aarch64 (232, 147);
  no undispositioned object in a required closure; METIS not reached. S9.2: `nlp_extra_modules` exactly {greybox:
  cyipopt, projection: pyomo, trf: pyomo} on all three; S9.3: 182 walked, 179 imported, solve exit 0 (CI.1: `a30.log`
  ends `a30 exit status 0`). MR-12 for the one new extra, `nlp`: S9.4 (`mr12_extras_v02` pass; audit
  `docs/m03-ipopt-audit.md` and inventory present; step 14's `a60.w24.nlp_tier_and_inventory` pass at C′; R-450 in the
  register). The object counts differ from the alpha's because the workload is scoped (RC O2); A30's verdict reads the
  closure.
- (b), (c) met: T08.A34 0 violations over 77 locally (72 plus step 12's five), 72 per CI host, 1 per clean install, 49
  in the bundle set; T06 A33 0 in step 6.
- (d) met: T08.A33 in step 1.

**Does not establish:** the `nlp` extra's closure beyond the audit (linux x86-64 only; M07 §24.10); the certificates
step 5's replays re-emit; certificate locality (L19).

## V19 — PASS

(i) ADR 0022 Accepted with revision 1; (ii)–(iii) the dossier unchanged since the alpha (git diff empty); (iv) T08.A61–A63
record tests green, `benchmarks/t08/v19/` unchanged; (v) T08.A64 green. **Does not establish:** any comparison with data.

## V20 — PASS

(a)–(c): T08.A47 12/12 on three hosts; nothing verified outside S3 (worst ratio 0.0968); T08.A10 green. (d): T08.A46
S = 434 of 440 on ref-x86-64 (F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3) and ci-aarch64 (4, 2) against 418; no F-CRASH or
F-OTHER-ROOT; replay 28/28; class counts equal the alpha's (O4). **Does not establish:** robustness beyond the nominal
profile (L09); out-of-sample performance (L32).

### Skip audit (step 1, R-376)

| Reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| archived pre-0.1.0 history (R-150): `conftest.py` (33), `test_t07_evidence_manifest` (28), `test_t08_evidence_manifest` (5) | 66 | 66 | No (v0.1 history; as at the alpha) |
| W27 pinned archive absent (`test_m06_w27_coverage` 2, `_harness` 8, `_scorer` 16) | 26 | 26 | Covered: step 16 ran `tests/test_m06_*.py` at C′ with the archive present, 172 W27 nodes passed, none skipped (JUnit read here) |
| the ledger module, S-ABSENT (`test_m07_ledger`) | 4 | 4 | No: required by M07 §23.2 at C |
| PTC-R1 diagnostics, no ci-x86-64 results (`test_t08_ptc_r1_diagnostic`) | 6 | 0 | No: V14 (b) fails regardless |
| M04 platform-bound: `test_m04_prewarm` (A40, 2 cores), `test_m04_quadratic` (vacuous control on 4 CPUs), `test_m04_schemas` (floats on x86-64 only) | 1 | 2 | Covered: step 13 ran every `test_m04_*` node locally, 485 passed, none skipped (the three A40 nodes pass) |
| platform-bound fixtures: `test_k05_schemas`, `test_t06_w28_records` | 2 | 2 | No (alpha finding B1 on the K05 node stands) |
| aarch64 only: `test_k01_backend_dependency`, `test_t06_w13_f6` (2), `test_m06_browser_smoke` | 0 | 4 | No; the browser node runs on x86-64 (W26 (b)) |
| `test_t08_w1_ledger` ("not in A02") | 1 | 1 | No |

No clause judged here rests on a node skipped at every place it could run.

---

## W21 — FAIL on W21 (e)

*The 2026-10-19 judgement, kept. Superseded by "W21 re-judged (2026-10-20)" after the findings: W21 is BLOCKED on W21 (c).*

Judged by the alpha spec §6.1 as ADR 0028 D7 reads it (M07 §7.3: unchanged), with §19.6 A6 (R-375) for 0.2.0's RC.
Every number is the group's model at the pin, a regression. Step-12 values were re-read from C′'s records; RC O5 states
they equal `cc73219`'s exactly, G12 differing only in paths, hashes and wall time.

| Clause | Judgement | Evidence at C′ |
| --- | --- | --- |
| (a) port mapping | met | M01 and M02 G4, G8, G9 nodes in step 1 on both architectures; G10 (h) 1.43 × 10⁻⁸ against 10⁻⁶ |
| (b) accuracy contract | met | G10 (b) 1.56 × 10⁻⁸ (10⁻⁶), (e) 3.84 × 10⁻⁸ (10⁻⁷), (f) 5.06 × 10⁻⁵ (10⁻³); G12 floor ratios 65.3 (ξ) and 13.3 (T) against ≥ 10 |
| (c) out-of-process execution policy | **waits on M02 N1** | G3–G5 nodes in step 1; `docs/support-matrix.md` at C′ states `external-subprocess-v1`, "not a sandbox", "Linux is registered; macOS best effort; Windows is refused before spawn" (checked). Missing: Frank's M02 N1 acceptance in ADR 0042, `pending` |
| (d) timeout | met | G3 (b) in step 1; the registered v3 variant's 450 s governs (R-378); G12 CONVERGED in 4 outer iterations; G11v3 met (S12.4) |
| (e) provenance | **not met** | G6 nodes in step 1; G12's results sit in its coupling record, schema-checked by `reproduce` (`MATCH`); reactor commit `6089593…` = ADR 0022's pin. **G11's results (121 points × 2 runs) were not kept and not audited.** R-375 registers that 0.2.0's RC keeps them under `rc/step12/experiments/` and audits blueprint §9.1's six items in each. The alpha's inference (single writer path) was accepted for the alpha only, on that deferral |
| (f) parent-model validation | met (verdict half) | (f1) G10 (g) bitwise; (f2) T08.A61 in step 1; (f3) the grid study, G10 (b), G10 (i); (f4) stated here: the group's published comparison (Gargiulo et al. 2025 §3.1) is the group's evidence; this project compared no reactor result with data; the numbers are a regression of the group's model; discretization bias 1.0–1.4 % in NH₃ (L46). **The notes' half is not yet readable:** `## v0.2.0` at C′ carries §10's eleven phrases but not these four statements (the alpha's skeleton did). It is read in the merged section at W21's next judgement |

**Why FAIL and not BLOCKED.** (e)'s missing input is evidence the lanes were to produce (T08 §3.3). (c) alone would
make W21 `BLOCKED`; (e) makes it `FAIL` whatever Frank answers. **Do not route W21 (e) to ADR 0042's D3 table:** an
acceptance of a missing provenance audit that costs an hour of free compute is the "PASS with waiver" ADR 0021
rejects.

**The smallest measurement that settles (e).** At C′, re-run step 12's G11 with the command of
`tools/run_local.summary.txt` line 17 through a wrapper that keeps each point's store (as `tools/g12keep.py.txt` keeps
G12's); commit the result and attempt records under `evidence/M07/ce99365…/rc/step12/experiments/` (gzip over 1 MB,
listed in `records.json`); audit every result and its attempts against `experiment.schema.json` for the six items
(boundary mapping; variant id, SHA-256 and reactor commit; num_z and the estimate; stage and certificate; element
defects; wall time), and add the audit's row to the RC record. The re-run must also satisfy S12.2–S12.4, and both G11
records stay. No D2.4 path changes, so no re-cut.

**W21 does not establish:** that the reactor is right (L46); any aarch64 run or cross-machine reproduction (L44, L15);
a sandbox (L45); sensitivities or optimization through the reactor; coupled-loop convergence beyond one loop, two edges
and G11's corners and centre (L48); timings under other load.

## W22 — PASS

(a) numerical verification: M01.A05–A22 against closed forms, M01.A34 (`--check`) in step 1. (b) conformance: M01.A37 in
step 1; step 11's IDAES re-run numbers equal `benchmarks/m01/idaes-conformance.json`'s (only
`inputs.reference_values_yaml_sha256` differs), re-run file `7e1d41dd…` as at the alpha. (c) empirical validation of
pure-component behaviour against reference equations of state: step 11's `external_crosscheck.py --check` recomputes
the record byte-equal, so the alpha's ratios stand (0.012675 against 0.02; 0.040096 and 0.042371 against 0.05). These
are R-160's validation bands, not tolerances. (d) sufficiency: G7, G8 in step 1; G12 binds every evaluation to
`pr-c1-v1` and ends `VERIFIED`. **Does not establish:** mixture VLE; k_ij effects beyond R-157; the near-critical region;
liquid-density fitness (L47); anything outside M01's domain.

## W23 — PASS

| Clause (M04 §15 row) | Judgement | Evidence at C′ |
| --- | --- | --- |
| (a) conservation | met | A13, A26 in the default gate (step 1, both architectures; step 13 locally) |
| (b) domain | met | A03, A14, A15 in the default gate; A31 recorded |
| (c) derivative | met | A12, A17 in the default gate; A31 recorded |
| (d) default UQ | met | A04–A08, A16–A24 in the default gate; A31, A32 recorded |
| (e) insufficient data | met | A07, A11, A20, A21 |
| (f) frozen splits and transforms | met | A01, A02, A23 in the default gate; A32 recorded |
| (g) promotion and rollback | met | A25–A30, A33 |

Step 13 re-checks M04's committed records at C′: `m04_reference.py --check` 11943 claims, schema fixtures exit 0,
485 passed. M04's manifest `8df0ea7` is `tested`, 60 pass. Met on numerical verification as M04 §15 states. The real
verdict `NOT_PROMOTABLE` (`band_not_finite`) is recorded; by M04 N6 it is not a W23 failure. **Does not establish:**
a promotable surrogate of the real reactor (L49); any coverage claim for the real surrogate.

## W24 — BLOCKED on W24 (a)

| Clause | Judgement | Evidence at C′ |
| --- | --- | --- |
| (a) M03's fixed-topology NLP with final parent checks | **blocked** | nlp tier (A35–A42) 186 passed, inventory `--check` exit 0 for both workloads, in the audited environment (step 14). **Missing:** Frank's M03 N1 acceptance in ADR 0042, `pending` |
| (b) TRF composition | met | M05 G2–G4, G13 in step 14's all-tier run (640 passed, 2 skipped: the two default-install answers, unobservable where Pyomo is installed) |
| (c) TR-E2 with assumptions stated | met | M05 G5 in step 14 |
| (d) FD truth accuracy and real-reactor accounting | met | G6, G7 in step 14; G11's REAL record replays at C′ with 0 differences (`m05_wo9_real.py --replay`) |
| (e) parent checks and the refinement loop incl. the N6 branch | met | G8, G9 in step 14 |
| (f) constraints kept as constraints, limits stated | met | G7, G11 and the record content |
| (g) costs reported | met | the truth-ledger identities (G7 accounting) |

M03 (`a35885b`, 52/52) and M05 (`56fb2fa`, 14/14) manifests `tested` at ancestors; ADRs 0031, 0032, 0038, 0039
Accepted (R-481, R-482). **Does not establish:** global optimality (no envelope row; the notes' registered phrase "no
global optimality"); any optimization result on aarch64; that the bound-active REAL decision says anything outside the
box.

## W25 — PASS

Judged on K's record (`2c508b5`), carried to C′ by identity (A3.4, RC.1); J′'s record is not W25 evidence (R-483).

| Clause | Judgement | Evidence |
| --- | --- | --- |
| (a) rungs | met | R0 `INDIFFERENT` (nine grid records, 18 in-process); R1 `DECIDED` 653.15 K; R2 `SURROGATE_NOT_PROMOTABLE`, M04's verdict and reason verbatim, 0 evaluations; R3 `DECISION_STABLE`, M05's study re-run at K (cold 48) |
| (b) before/after decisions | met | P01 `FE_CHANGED`, P13 `FE_UNCHANGED`; equality with the reference function by A22 and `check` |
| (c) constraints | met | bound phrase present for R1, R3 and the journey (`BOUND_LOWER` at 653.15 K, R-315); A23, A11 |
| (d) discrepancy | met | A20, A15 in the default gate; `check` |
| (e) uncertainty | met | A20, A21; R3's noise floor and indifference set in the record |
| (f) truth checks | met | TC-1 `TC1_HOLDS` (best grid T 653.15 K); the decision is a parent evaluation (A23, A26) |
| (g) compute cost | met | R0 0 cold (budget 0), R1 36 of 60, 1558 s of 5400; R2 0; R3 48 of 400, 1477 s of 14 400; none exhausted (A25, A13) |
| (h) honest limits, reproducibility | met | step 15 at C′: carried, `check: ACCEPT`, `replay: bitwise`; J.1 (A24 for K passes at C′, J′ skipped as R-483 registers); A10, A11 in step 1 |

**Does not establish:** empirical validation; global optimality; anything outside 653.15–693.15 K, including whether
the objective improves below the lower bound where the decision sits; reproduction on another architecture (R3, L44);
the thirteen items of the report's §11.

## W26 — PASS

(a) M06 G1–G15 at C′: step 16, 661 passed with the browser required, `node --test` 92 of 92, the W27 dry run A23 PASS;
M06 manifest `4719a1a` `tested`. (b) the browser test on CI x86-64: the `check (ubuntu-latest)` job exports
`OPENFLOWSHEET_REQUIRE_BROWSER=1` (log line 454) and the x86-64 skip file has no browser skip. **Does not establish:**
usability or accessibility beyond L-WEB-3; anything but the local single-user security model (L-WEB-2).

## W27 — PASS

| Clause | Judgement | Evidence |
| --- | --- | --- |
| (a)–(d), (g) | met at C_W | `docs/reviews/W27-verdict-83f825d.md`, as judged there (2026-10-18) |
| (e) `campaign.json` computed | met at C_W | re-judged met on `4812910a…9e28` (repair `89cd931`), the record cited by full digest (§22.1) |
| (f) the nine inaccessible assets disclosed | met | `access_report.json` (nine, each absent); `docs/m06-w27-coverage.md` at C′ lists all nine (checked). The release report's own text, filled from the record under W27-R57, is read when the notes are merged |
| (h) carry from C_W to C′ | met | step 17 (§22.2): 17a tree `95f9fcf2…895a` = the judged record; 17b coverage at C′ exit 0; 17c `at-c.json` = `at-cw.json` (`3c0e08c7…`); 17d `diff -r` empty, `campaign.json` `4812910a…9e28` |

**Does not establish:** a headline score or any comparison with CRAFTS or `v17-c2`; any build measured (0
candidates, the system and effects zeros vacuous); agent capability beyond 45 runs of one model at k = 1; portability.
The W27 verdict's L-W27-1…8 travel with this row; they are not envelope rows.

---

## Alternatives considered and rejected

1. **W21 `BLOCKED` on (c) only, with (e) met by the alpha's inference, as the registered waits suggested.** Rejected.
   The alpha's acceptance of the inference (its rejected alternative 7) rested on "R-375 records the audit for 0.2.0".
   Accepting it again at 0.2.0 would reverse R-375 without a new decision. M07 spec §1 puts re-deciding the alpha
   spec's amendments out of scope, and nothing in M07 reverses §19.6 A6.
2. **W21 `BLOCKED` on (e).** Rejected: the input is the lanes' to produce (T08 §3.3).
3. **W21 (e) met because field presence is structural.** Rejected for 0.2.0: structure shows the keys exist, not that
   each of the 242 results carries the pinned variant, reactor commit, estimate and timing values. That is what the
   registered audit checks.
4. **Audit the G11 results here.** Not possible: they were written to temporary directories and deleted; the runs file
   lacks the provenance members (checked). An audit of uncommitted scratch would not be committed evidence anyway.
5. **V18 (a) blocked or not met because ADR 0042's M03 N1 cell is pending.** Rejected: M07 §24.1 S9.4 registers MR-12's
   decision leg as R-450 in the register, and it holds. V18 is not in `rejudge_waits`. The ADR 0042 cell is W24 (a)'s
   registered wait. The double reading is finding F2.
6. **V13 and V17 `PASS` on ADR 0028's carry.** Rejected: ADR 0042 D2 (per release), and link c_3 is new.
7. **W25 on J′'s record, or W25 not met because J′'s replay diverges.** Rejected: A3.4 and R-483 scope W25 to K's record
   at trees its carry reaches.
8. **W27 not met because `## v0.2.0` does not yet cite `4812910a…9e28` or list the nine assets.** Rejected: (f) is met
   on the committed record; the notes are written after the verdict and their text is a condition on the merged
   section (finding F3).
9. **No verdict because M07's manifest does not exist yet.** Rejected: as at the alpha, the manifest follows the
   verdict; the RC records are the evidence.
10. **V14 `PASS` on route (a), or V14 in a re-judgement.** Rejected (R-118; §19.2: V14 cannot be listed).

## What would change these verdicts

- **The G11 audit of "W21" above, committed at C′ and passing** → W21 (e) met, in a **new judgement** with a new
  `Judged` date (§19.2 item 2); W21 then stands on (c). A result missing any of the six items → (e) stays not met, now
  on a record.
- **Frank records `V17 carry` and `M03 N1` as `accepted, <date ≥ Judged>`** → V13 (e), V17 (a) and W24 (a) are
  re-judged (a `**Re-judged:**` line, same `Judged`, if no new judgement intervenes). Expected met if their evidence
  still holds.
- **Frank records `M02 N1` accepted** → W21 (c) met at W21's next judgement, which also reads (f4)'s notes half in the
  merged `## v0.2.0`.
- **A declined `M03 N1`** → W24 (a) not met, and V18 (a)'s MR-12 decision leg (R-450) is contradicted: V18 then needs a
  new judgement (it cannot be re-judged under §19.2). A declined `M02 N1` or a new V17 campaign → a spec amendment.
- **Frank's D3 acceptance of V14 (b)** dated ≥ the `Judged` date in force → V14's FAIL becomes releasable; no word changes.
- **Any change to a D2.4 path** → a new candidate and a new RC job; every row re-judged.
- **A record whose bytes no longer match its digest, a skipped node a clause rests on, a W27 carry member differing
  at a later candidate (N7), or a new preregistered PTC family passing (b1)–(b4)** → reopens the clause concerned.

## What these verdicts do not establish

- **No empirical validation** of the reactor, the C1 loop or the journey's decision; W22 (c) is pure-component PR
  against reference equations of state inside R-160's bands, nothing more.
- **No optimality evidence**: the journey's and M05's decisions are bound-active at 653.15 K; nothing is claimed below it.
- **No portability** of W21, W24 and W25: one machine (`ref-x86-64`), one thread, R3, a possibly shared host. W27: one
  platform, one Claude Code version, one model.
- **No agent behaviour on the v0.2 surface** (V17, V13 (e)), and no agent capability claim from W27.
- **No scientific or process-model review**, and no human sign-off.
- **No releasability**: the tag needs the G11 audit and W21's new judgement, Frank's five answers dated as above, the
  ledger (5 passed, 0 skipped), M07's `tested` manifest, ADRs 0041 and 0042 Accepted, the merged notes, and Frank's
  dispatch.

## Limitations that must travel into the manifest and the release report

- The envelope ids in the table, per gate (reactor on x86-64 only, opt-in, R3: L44, L15; not a sandbox: L45; W21 (f4)'s
  four statements: L46; PR's liquid bias: L47; G11's corners and centre: L48; no promotable real surrogate: L49; the
  web shell: L-WEB-1…4; reference data and OpenIDAES-450 not distributed: L40).
- V14 (b) FAIL, PTC experimental (L01), D3 acceptance to be recorded.
- W21 FAIL on (e) until the G11 audit; until then G11's provenance at 0.2.0 is an inference (R-375 open).
- W24 and W25: no global optimality; the decision is bound-active at the lower bound (no envelope row; the notes'
  registered phrase).
- W27: L-W27-1…8 of `docs/reviews/W27-verdict-83f825d.md`; cite the campaign only by `4812910a…9e28`.
- J′'s replay is judged only where its carry holds (J55, R-483).
- M05 review N1, and M05 build log S75 and S77, are open for the next design touch; the OpenIDAES-450 split is queued
  for after 0.2.0. None is judged here.
- Step 12's and the journey's timings were measured on a possibly shared host and bound nothing.

## Findings

- **F1 (design lane; changes a verdict).** R-375 (alpha spec §19.6 A6) was not carried into M07 §8 or Amendment 7, so
  C′'s step 12 neither kept nor audited G11's results. Remedy: the measurement under W21, by the build lane against
  R-375's stated checks; then W21 is judged again in a new judgement.
- **F2 (one decision read two ways).** Frank's M03 N1 licence decision is read as R-450 (2026-10-16) for V18 (a) (S9.4)
  and as ADR 0042's cell (dated ≥ `Judged`) for W24 (a). Both readings follow registered text. The ADR 0042 answer
  should be recorded consistent with R-450; a decline would reopen V18.
- **F3 (notes).** `## v0.2.0` at C′ carries §10's eleven phrases but not W21 (f4)'s four statements, the gate table,
  the limitation list, the W27-R57 sentence with the nine assets, or the campaign digest. The alpha's skeleton at
  `C_α²` already carried (f4)'s. These must be in the merged section before W21's next judgement and before A52's
  counterpart is judged.
- **F4 (envelope).** No envelope row covers W24/W25's optimality limits or W27's L-W27 items; they travel in prose and
  the notes' phrases. A later envelope revision could add rows; not required by any registered rule read here.
- **F5 (procedure).** With this document present, `tests/test_m07_ledger.py`'s four tests stop skipping at this
  0.2.0 tree (M07 §23.2) and judge the ledger and M07's manifest, which do not exist yet. Measured on the commit that
  adds this document: `pytest tests/test_m07_ledger.py` 2 failed, 3 passed (`test_the_claimed_verdicts_are_the_documents`,
  `test_every_claimed_gate_cites_m07_at_c`). The module stays red until the build lane's ledger edit and M07's manifest
  are committed.
- **F6 (procedure; dry run).** `v0_2_gate.py --rc ce99365 --candidate <the commit adding this document> --json` parses
  this document (exit 1, not 2) and refuses for 20 reasons: the ledger ×8 (V13, V17, W21 differ; W23–W27 absent),
  D2.2 ×3 (V13, V17, W24), D2.3 ×2 (V14 (b), W21 (e)), M07's manifest, ADRs 0041 and 0042 not Accepted, and Frank's
  four pending answers. Every reason is one this document predicts.

## W21 re-judged (2026-10-20) — BLOCKED on W21 (c)

**A new judgement, not a re-judgement line.** On 2026-10-19 W21 was `FAIL` on evidence the lanes owed. §19.2 item 2
lets a `**Re-judged:**` line list only gates `BLOCKED` on a registered answer, so W21 is judged again here and the
`Judged` date moves to 2026-10-20 (the Sequencing paragraph above). Only W21 (e) and the notes' half of (f4) are judged
again. (a), (b), (d), (f1)–(f3) and the verdict's half of (f4) stand on the evidence in the W21 table above. (c) waits
on M02 N1 as before. The other sixteen rows keep their verdicts and their evidence. The new date moves only the floor
for Frank's answers (now 2026-10-20, in the table of answers above).

| Clause | Judgement | Evidence |
| --- | --- | --- |
| (e) provenance | **met** | G11's 210 experiment results and 210 attempts, kept at C′ and audited for the six items against `experiment.schema.json`: 0 problems. Re-run here, with the denominator checked independently (below). Unchanged: G6 nodes in step 1, G10 (g), G12's `reproduce` `MATCH`, reactor commit `6089593…` = ADR 0022's pin |
| (f) parent-model validation | **met** | (f4)'s notes half: `## v0.2.0` carries the four statements (below). With (f1)–(f3) and the verdict's half (2026-10-19), (f) is met |
| (c) out-of-process execution policy | **waits on M02 N1** | unchanged: Frank's M02 N1 acceptance in ADR 0042 reads `pending` |

**Verdict: W21 `BLOCKED` on W21 (c).** Every other clause is met. D2.3 no longer refuses W21. D2.2 refuses it until
Frank's M02 N1 answer is recorded `accepted, <date>` with 2026-10-20 ≤ date. W21 can then be listed on a
`**Re-judged:**` line, because it is now `BLOCKED` on a registered answer.

### (e): the criterion, the production, and what was checked here

**Criterion, as registered.** Alpha spec §6.1, W21 (e), bullet 2: "Every experiment result record that step 12 writes
carries blueprint §9.1's six items, in the fields of `experiment.schema.json`." §19.6 A6 (R-375): "step 12 keeps G11's
results under `rc/step12/experiments/` … An audit then checks blueprint §9.1's six items in each result against
`experiment.schema.json`."

**Production (build lane, `2d71de1`; build log J78–J80).** G11 was re-run at C′ through `tools/g11keep.py.txt`, exit 0,
1847 s. The run records its own provenance block: commit `ce993651…`, `tree_clean` true, `ref-x86-64`, x86_64, Python
3.13.5, one thread, lock `ead4edf1…`. The wrapper (read here) loads `benchmarks/m02/g11_coverage_v3.py` unchanged. It
replaces only the module's `tempfile` and `ProcessPoolExecutor` names, so each point's store survives. Records: one
collected record per run, with each request, result and attempt embedded, plus the re-run's G11 record and runs file.
The RC record has the row (`docs/v02-rc-record.md` l.126).

**Checked here, independently of the build lane's summary:**

1. **Bytes.** The sha256 of the decompressed run records (`250739ee…`, `11fd4fe9…`), the re-run's
   `g11-coverage-v3.json` (`9ac1b0df…`) and its `.runs.json` (`8c85a787…`) equal the RC record row's.
2. **Same computation as step 12.** The re-run's runs file was compared with step 12's original G11 runs file, committed
   at C′'s records commit `2fd23a6` before the re-run. Over all 242 point-runs, `stage`, `accepted`, `child_accepted`,
   `tube_outlet` and `path` are exactly equal (JSON equality, 0 differences). The kept records are therefore step 12's
   G11 outcomes, not a different run. Both G11 records stay (`rc/step12/g11-coverage-v3.json` and
   `rc/step12/experiments/g11-coverage-v3.json`). S12.2–S12.4 are reported holding by the build lane (J79,
   `tools/s12_check.py.txt` and `m02_evidence_manifest.py:g11`). They were not re-run here: this verdict relies on the
   equality above, which pins the per-point outcomes those checks read.
3. **The denominator is 210, not 242.** Each run has 121 points. 105 go through the boundary (`ExperimentRunner`, one
   experiment each). 16 are evaluated by `backend.evaluate` directly (`g11_coverage_v3.py` l.499–570) and write no
   experiment record: B2's eight zero-inert corners (G11v3-8), the six ΔP-ramp points, `centre-x0.25` and
   `centre-x4`. The (label, path) multiset of the collected records equals step 12's original runs file exactly: 210
   boundary and 32 direct. The split is fixed by the frozen script and by the record written before the re-run, not by
   the collector. The criterion covers experiment result records step 12 *writes*. The 32 direct evaluations write
   none, so they are outside (e). They remain G11 coverage evidence, and no §9.1 provenance is claimed for them.
   **Correction to the 2026-10-19 text:** the W21 table's "121 points × 2 runs" and rejected alternative 3's "242
   results" counted points, not experiment results. The registered denominator is the 210 experiment results.
4. **The audit, re-run here.** `PYTHONPATH=src .venv/bin/python scripts/m07_g11_experiments_audit.py --variant-file
   <benchmarks/m02/variant-v3-provisional.json at C′> --runs rc/step12/experiments/g11-coverage-v3.runs.json run1.json
   run2.json`. The variant file is byte-equal at C′ and at `6d60af6`. Exit 0: "2 runs, 210 boundary points, 210 results,
   210 attempts, 0 without a result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): 420
   findings: PASS". The audit compares the records with independent expectations: the frozen schema, the pinned variant
   (id, SHA-256, reactor block with commit), and the runs file's inlets and `n_tubes`. It does not compare them only
   with themselves.
5. **Does the audit discriminate?** Four mutated copies of run 1 were audited here:
   - the reactor commit changed in one result: `version` 2 problems, exit 1;
   - `wall_s` removed from one attempt: `schema` 1, exit 1;
   - one boundary point's experiments emptied: `structural`, exit 1;
   - one boundary point relabelled `direct` with its experiment removed: **exit 0, PASS on 209**.

   The audit takes the boundary/direct split from the collected record's own `path` labels and does not check it
   against the runs file. Check 3 closes that gap for this record. The audit's own gap is finding F8.
6. **Tests.** `tests/test_m07_rc_records.py` and `tests/test_m07_g11_experiments_audit.py`: 22 passed here.

**Evidence class.** Implemented and tested by the build lane, and checked here. This is numerical and procedural
verification that the records carry the registered provenance fields with the pinned values. It is not empirical
validation, and it is not evidence that the reactor is right. Every number is still the group's model at the pin, a
regression.

### J78: the `job_id` pattern (ruling)

- **It does not affect W21 (e).** The registered criterion is the six items "in the fields of
  `experiment.schema.json`", and R-375's audit checks "the six items in each result against" the schema.
  `produced_by.job_id` and an attempt's `job_id` name the requesting job. That is not one of the six items (boundary
  mapping; version; discretization settings; convergence evidence; conserved fluxes; cost). Apart from that field, every
  request, result and attempt validates against the schema's definitions (audit `schema` 0). Failing (e) on `job_id`
  would add a criterion that is not registered.
- **It is a defect, not an acceptable state, and not a schema amendment.** All 420 values are `m02-g11v3-<label>`, and
  the frozen schema's pattern `^job-[0-9]{6,}$` (or null) refuses them. The schema's pattern is right for product jobs:
  `src/openflowsheet/application/store.py` l.643 issues `job-NNNNNN`. The cause has two parts. G11's harness passes its
  own label as `job_id` to `ExperimentRunner`. The runner writes `job_id` into results and attempts without checking it
  (`src/openflowsheet/adapters/experiments/runner.py` l.193–503).
- **Remedy at the next M02 touch, not for 0.2.0** (it changes no verdict): G11 passes `job_id=None` or a conforming
  id; the runner refuses a non-conforming `job_id` before it writes; the audit's `CONTEXT_FIELDS` returns to `()`.
  Finding F7; the limitation below travels.

### (f4)'s notes half

The section read is `## v0.2.0 — unreleased` in `CHANGELOG.md` at `6d60af6`, unchanged since `61f3b6b`, the "What it is
not" bullet at l.199–201. After whitespace normalization, each of the four phrases the alpha's re-judgement used
(alpha verdict l.99–104) appears exactly once in the section:

- `no reactor result has been compared with experimental data`;
- `the group's published comparison is the group's evidence`;
- `the group's model at the pin, a regression`;
- `discretization bias is 1.0–1.4 % in NH₃`.

`awaits Frank's statement` is absent. The notes half is **met**. This reads the section before its final edit, as the
alpha's §19.5 reading did. A52's counterpart checks the four statements again at the tag candidate. If any of them is
removed or altered there, that check fails and this half reopens. F3's other items (the gate table, the limitation
list, the W27-R57 sentence with the nine assets, the campaign digest) are not W21's, and they remain open.

### Alternatives considered and rejected (this judgement)

1. **(e) not met because the 32 direct evaluations have no experiment records (denominator 242).** Rejected. The
   criterion covers experiment result records that step 12 writes. The frozen script writes none for direct points, and
   the split equals step 12's original record. Making them write records would be a new requirement, which needs a spec
   amendment, not a verdict.
2. **(e) not met because `job_id` fails the schema (whole-record validity).** Rejected: the field is not one of the six
   items. See J78 above, findings F7 and the limitation.
3. **(e) met on the build lane's audit summary alone.** Rejected as a basis. The audit accepts a relabelled point
   (check 5). "Met" rests on the audit together with the independent denominator check 3.
4. **A `**Re-judged:**` line keeping `Judged` 2026-10-19.** Rejected: §19.2 item 2. W21 was `FAIL`, not `BLOCKED` on
   an answer.
5. **W21 `PASS`.** Rejected: (c) waits on Frank's M02 N1 answer, `pending`.
6. **Re-running S12.2–S12.4 here before judging.** Not needed for (e). R-375 does not register them. The equality in
   check 2 carries step 12's outcomes, and the build lane's re-check is on record.

### What would change this judgement

- **Frank records `M02 N1` as `accepted, <date>`, 2026-10-20 ≤ date** → W21 (c) met on a `**Re-judged:**` line → W21
  `PASS`. A declined M02 N1 needs a spec amendment.
- **A kept record whose bytes no longer match the RC row, or a boundary point of step 12's record without its experiment
  in the kept records** → (e) reopens.
- **Any of the four statements removed or altered at the tag candidate** → (f4)'s notes half reopens (A52's
  counterpart).
- **Any change to a D2.4 path** → a new candidate; every row is judged again.

### What this judgement does not establish

That the reactor is right (L46). §9.1 provenance for G11's 32 direct evaluations, which have no experiment records.
Whole-record schema conformance of G11's kept records (`job_id`, F7). Any platform other than `ref-x86-64`, or any
cross-machine reproduction (L44, L15). Anything about G12 beyond the 2026-10-19 reading. No scientific or process-model
review, and no human sign-off.

### Limitations that must travel (added to the list above)

- G11's 420 kept records (210 results, 210 attempts) carry a `job_id` that `experiment.schema.json` refuses. A
  consumer that validates whole records against the schema will reject them (F7). The six items are unaffected.
- G11's 32 direct evaluations per two runs are coverage evidence without experiment records. W21 (e) covers the 210
  boundary results.
- R-375 is closed at C′ by the audit, and G11's provenance at 0.2.0 is no longer an inference. The 2026-10-19 bullet
  "W21 FAIL on (e) until the G11 audit" is superseded.

### Superseded in the 2026-10-19 text (kept above, read as follows)

- "Read this first" counts and "Against the alpha's verdicts" for W21: W21 is `PASS → BLOCKED` on (c), as V13 and V17.
- "What would change these verdicts", first bullet: done. "No releasability": the G11 audit and W21's new judgement are
  done. The rest of that list stands, with Frank's answers now dated on or after 2026-10-20.
- F1: remedied by `2d71de1`. F3: the four statements are now present, and the rest stays open. F6: a dry run on the
  commit that carries this text should refuse W21 under D2.2 (four `BLOCKED`), not D2.3. It has not been run here,
  because the document is uncommitted.

### Findings (this judgement)

- **F7 (J78; next M02 touch).** G11's `job_id` values fail the frozen schema's pattern, and `ExperimentRunner` writes
  an unchecked `job_id`. Fix the harness and add a write-time check; not a schema amendment.
- **F8 (audit; next touch of `scripts/m07_g11_experiments_audit.py`).** The audit takes each point's boundary/direct
  path from the collected record, so a relabelled point passes. It should check each point's `path` against the runs
  file and fail on a mismatch.
- **F9 (this document).** The 2026-10-19 text counted G11's points (242 point-runs) as results. The registered
  denominator is 210 experiment results. Corrected above; no verdict depended on the miscount.
