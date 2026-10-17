# V02 alpha — verdicts on V11–V20, W21 and W22 for `0.2.0a1`

**Release candidate:** `cc73219a77f6a54579c8acb151ed6fae228c8a4c`   **Judged:** 2026-10-16   **By:** design lane (`verdict`)
**Re-judged:** 2026-10-17 (V13, V17, W21)

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | T08 §4.1 with MR-10; at C_α²: K06, T01, T06 and T07 nodes, T08.A35, T08.A10 and M07a.A42 green in step 1 (CI 38813135468, both architectures) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (spec §5.1); at C_α²: T05, T05b and build-first B10–B19 nodes green in step 1 on both architectures; coupled cases SYN-001, T05 C1–C3, PTC-R1 |
| V13 | PASS | — | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3, T08.A71 and MR-7; at C_α²: T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51, digest and schemas by the chain (step 8, three hosts), under Frank's V17 carry (ADR 0028, accepted 2026-10-17); re-judged 2026-10-17 |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43 | T08 §4.4; T08-verdict-V14b.md (PTC-R1: the saddle clause fails on both registered platforms), unchanged at C_α²; Frank's D3 acceptance for 0.2.0a1 pending; homotopy and edges: T04, T02 and T08.A33 nodes green in step 1 |
| V15 | PASS | — | L02, L14, L19, L20, L33 | T08 §4.5; at C_α²: T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both architectures; the certificate schema fixes both claims to NOT_ASSESSED, as all five step-12 certificates carry |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands (8 of 8 by both tools, 16/16 AGREE); T08.A48 passes at C_α² on ref-x86-64, ci-x86-64 and ci-aarch64 (step 7) |
| V17 | PASS | — | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6; Frank's V17 carry of v17-c2's agent evidence (ADR 0028, accepted 2026-10-17); M07a.A37 at C_α² on three hosts: served digest 383b4e2c… decomposes to 6c4375b4… and 171dd768…, and to 6d13e13d… with v17-c2's texts; G16-b 40 of 40 |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12; at C_α²: T08.A30 PASS on three hosts, no undispositioned object in a required closure, no new extra; T08.A31–A33 nodes green; T08.A34 0 violations on every audited set, step 12's five coupled-route certificates included |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); the dossier unchanged since C_α¹ with H1–H6 met; the benchmarks/t08/v19 records byte-identical to those at 67c66d9; the A60–A64 record tests green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; at C_α²: T08.A46 S = 434 of 440 on ref-x86-64 and on ci-aarch64, no crash, no other-root, same-class replay 28/28; T08.A47 12/12 on three hosts; T08.A10 node green |
| W21 | PASS | — | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | spec §6.1; step 1: M01 stand-in and M02 G3–G9 nodes green on both architectures; step 12 on ref-x86-64: G10v3 and G11v3 met, G12 CONVERGED and VERIFIED, reproduce MATCH, live rerun bitwise; M02 N1 accepted by Frank (ADR 0028, 2026-10-17); the four parent-model statements in the notes' section at C_α²; re-judged 2026-10-17 |
| W22 | PASS | — | L42, L47 | spec §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green; step 11: crosscheck byte-equal on recomputation, IDAES re-run numbers identical; step 12: G12 VERIFIED on the route |

## Re-judgement

**2026-10-17, at the same candidate `C_α²` = `cc73219…`, under spec §19.2 (R-371).** Three rows change, in place:
V13, V17 and W21 go from `BLOCKED` to `PASS`. No other row changes. `Judged` stays 2026-10-16. From "Read this first"
onward, this document is the first judgement, kept as recorded. For V13, V17 and W21, this section replaces those
sections' verdict lines and the statement that no YES is possible. For every clause not named below, the first
judgement's text and evidence stand. This is still an agent verdict, numerical and procedural only. It sets no
`reviewed`, claims no scientific review or human sign-off, and moves no tolerance, band or classification rule.

**Nothing at `C_α²` has moved.** `git diff --name-only cc73219 e4cad68` lists no D2.4 path (`src`, `schemas`,
`benchmarks`, the lock, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`). It also lists neither
`CHANGELOG.md` nor `docs/support-matrix.md` (checked here). The records judged on 2026-10-16 are the records judged now.
The only new input is ADR 0028's four cells.

### The answers read (ADR 0028, as committed in `e4cad68`)

| Item read | Cell | Table T7, with J = 2026-10-16 and R = 2026-10-17 | Counts | What it does here |
| --- | --- | --- | --- | --- |
| decisions, `V17 carry` | `accepted, 2026-10-17` — Frank, verbatim: "Accept the defaults" (the default in this row) | J ≤ 2026-10-17 ≤ R: V13 and V17, listed, wait on it | yes | unblocks clause (e) of V13 and clause (a) of V17 |
| decisions, `M02 N1` | as above | J ≤ 2026-10-17 ≤ R: W21, listed, waits on it | yes | unblocks clause (c) of W21 |
| decisions, `N3` | as above | ≥ J; no listed gate waits on it | yes | confirms the claim set this document judges, `v0.2-alpha-gate-v1` (the twelve rows) |
| D3, clause `V14 (b)` | as above | ≥ J; V14 is not listed (it cannot be, Table T8) | yes | changes no verdict word. V14 stays `FAIL`, and the FAIL becomes releasable (D2.3). It is not a re-judgement |

**What these answers are.** Each cell takes its row's default. None chooses an alternative or declines. So §7.3 item
11's refusal does not apply, and Amendment 4 (§20), which applies only if N1 is declined, is void. The four cells were
recorded by the build lane in commit `e4cad68` (2026-10-17). They record Frank's single verbatim answer, "Accept the
defaults", given after the four questions were put to him in plain words (re-judgement brief). This verdict did not
witness that exchange. It reads the record as the authority's decision, as it read R-145 and R-149. Evidence class:
decisions.

### V13 — BLOCKED → PASS (clause (e) judged again)

- **(e) compatible warm starts: met.**
  - T08.A71's four elements: the B40–B49 nodes are green in step 1 on both architectures, as judged on 2026-10-16.
  - B50's counterpart (MR-7), content: M07a.A51 `pass` at `C_α²`. Its 4 nodes cover the content check and the two
    negative controls (an unregistered model added, a registered addition removed).
  - B50's counterpart, digest and schemas "by the chain, under the same carry (MR-2)". M07a.A37 is `pass` at `C_α²`:
    8 test nodes, plus the three step-8 records (local `ref-x86-64`, `ci-x86-64`, `ci-aarch64`). Each record is
    `passed` with 7 of 7 checks, `commit` = `cc73219…` and a clean tree. Their sha256 (`9fd188b7…`, `8f9d9525…`,
    `59eb9ceb…`) equal the RC record's; recomputed here.
  - The carry MR-7 names: ADR 0028's `V17 carry`, accepted 2026-10-17. The row names "V17, and T08.B50's surface".
    It names both links, R-192 and R-234, and §5.3's chain, which is what MR-2's counterpart asks for.
- (a)–(d): met, unchanged (see the V13 section).
- **Against v0.1 (PASS).** Same word, different route. At `67c66d9`, T08.A49's digests met B50 directly (R-133,
  R-134). At `C_α²`, the digest and schemas are met through the registered chain under a new carry, and the content
  through A51.
- **Does not establish:** that agents behave correctly on the v0.2 surface. Frank's carry accepts that evidence; it
  does not measure it. Warm starts beyond exact id-set compatibility (L-WS-1, L-WS-2).

### V17 — BLOCKED → PASS (clause (a) judged again)

- **(a) a surface to which Frank has carried `v17-c2`'s evidence, with M07a.A37's chain holding: met.**
  - The carry is ADR 0028's `V17 carry`, accepted 2026-10-17.
  - The chain was re-read here from the local step-8 record, and each link equals its registered expectation:
    - `d(T(C_α²))` = `383b4e2c…` = D_2 (R-319);
    - stripping c_2 (R-234) gives `6c4375b4…` = D_1 (R-192);
    - stripping c_1 (R-192) gives `171dd768…` = D_0 (R-133);
    - serving `v17-c2`'s two texts gives `6d13e13d…` (R-137).
  - The 17 tools and their description files are as registered (0 problems). The CI records on both architectures
    carry the same 7 of 7.
- (b) G16-b 40 of 40 over four transports on three hosts: met, unchanged.
- **Evidence classes.** The chain is identity verification against registered digests, tested in CI. The agent
  evidence is `v17-c2`'s, measured on the R-137 surface, and it reaches `0.2.0a1` only by Frank's decision. No agent
  ran on the v0.2 surface.
- **Against v0.1 (PASS).** Same word. As at v0.1 (R-133), it rests on a recorded carry, now across R-192 and R-234.
- **Does not establish:** agent behaviour on the v0.2 surface; anything beyond L12's single pinned model and
  configuration over MCP.

### W21 — BLOCKED → PASS (clause (c), and (f4)'s notes half, judged again)

- **(c) out-of-process execution policy: met.**
  - G3 (a)–(h), G4 (a)–(i) and G5: nodes in step 1, unchanged.
  - The support matrix at `C_α²` states `external-subprocess-v1`, "not a sandbox", "Linux is registered; macOS best
    effort; Windows is refused before spawn". This is unchanged and was re-read here.
  - M02 N1: accepted 2026-10-17.
  - Frank's acceptance is of the default "accept, stated as 'not a sandbox' in the support matrix and the notes". Both
    places state it: the matrix row above, and in the notes the bullet "The reactor execution profile is not a
    sandbox" (`CHANGELOG.md` l.47 at `C_α²`), with L45.
- **(f4), the notes' half: met.**
  - The `## v0.2.0a1` section at `C_α²` holds all four statements in its "Not empirically validated" bullet (l.27–31):
    - `no reactor result has been compared with experimental data`;
    - `the group's published comparison is the group's evidence`;
    - `the group's model at the pin, a regression`;
    - `discretization bias is 1.0–1.4 % in NH₃`.
  - After whitespace normalization, each appears once. The forbidden `awaits Frank's statement` is absent (checked
    here).
  - With the verdict's half (2026-10-16), (f4) is met, and so (f) is met.
- **Which section is read.** §19.5 says the re-judgement reads "the merged section". This verdict reads it as the text
  that action 4 merged into the skeleton at `C_α²` (§19.5: "The build lane edits the skeleton in `C_α²`"). That is the
  only reading consistent with §19.8 action 10's order. The re-judgement comes before §9.2 step 5, and step 5's gate
  table must show the re-judged words (A52 (c)), so the post-step-5 section cannot exist yet. Step 5 completes the
  section with the gate table and `C_α` (§19.4). A52 (d) at the candidate checks the four statements again, and §9.2
  step 7 runs the gate only after that check passes. If step 5 removes or alters any of the four, A52 (d) fails there,
  and so does this half of (f4).
- (a), (b), (d), (e), (f1)–(f3) and the verdict's half of (f4): met, unchanged, on the same step-1 and step-12
  records.
- **Does not establish:** the W21 section's list, unchanged. In addition, Frank's acceptance of N1 is acceptance of a
  profile stated to be unconfined (L45). It is not a security review.

### What the re-judgement does not change, and findings

- **V14** stays `FAIL` on (b). Its row's Basis still reads "Frank's D3 acceptance for 0.2.0a1 pending", because that
  was true on 2026-10-16 and §19.2 forbids touching a row this re-judgement does not list. The D3 row now reads
  accepted, 2026-10-17. The gate reads that row, not the Basis cell.
- **Finding R1 (build lane; blocks the gate, not these verdicts).** ADR 0028's status line still reads "Proposed,
  2026-10-08". Its own acceptance condition holds: the answers are recorded and M07a's manifest at `C_α²` is
  `tested`. §9.2 step 6 says it "is marked Accepted", and the gate's required-ADR check (§7.2 item 7) reads that line.
- **Finding R2 (disclosure; not a failed clause).** Neither the envelope nor the notes say that V17's agent evidence
  was measured on an earlier surface (R-137's) and reaches `0.2.0a1` by Frank's carry. L12 and the notes say only that
  it is narrow. V17 (a)'s criterion as registered is the carry plus the chain, and both are met. §4 rule 4 is not
  breached: the surface difference is exactly what the RC measures (A37), and the carry is the registered substitute
  for a campaign. v0.1 left R-133's carry unstated in the same way. Recommendation: step 5's prose (`CHANGELOG.md` is
  not a D2.4 path) adds one sentence. The envelope cannot change without a re-cut (§19.10).
- **What would reopen these three words:**
  - a change to any D2.4 path, which means a new candidate and a new judgement;
  - step 5 altering the four (f4) statements or the sandbox bullet;
  - a replaced or withdrawn answer: an alternative is refused by §7.3 item 11; a declined N1 brings in §20; a new V17
    campaign replaces the carried evidence and needs its own verdict;
  - a hash mismatch in the step-8 records, or A37 or A51 failing on a re-run at `C_α²`.
- **Rejected:**
  - leaving W21 `BLOCKED` until after step 5. That is circular (step 5's table needs this verdict), and `BLOCKED` is
    reserved for inputs outside both lanes' authority, while the notes are the build lane's;
  - rewriting `Judged` (§19.2 item 1);
  - rewriting the first judgement's sections. Each of the three gets only a pointer line under its heading;
  - listing V14 (Table T8);
  - treating one blanket "Accept the defaults" as too thin. Each cell records "(the default in this row)", and
    Table T4 reads the cell.
- **Limitations that travel, in addition to those below:**
  - V17's agent evidence is carried, not measured on the v0.2 surface;
  - W21 (f4)'s notes half was read on `C_α²`'s text, and the final text is guarded by A52 (d) at the candidate;
  - Frank's four answers are one phrase, recorded by a lane.

## Read this first

**The twelve.** Eight PASS (V11, V12, V15, V16, V18, V19, V20, W22), one FAIL (V14 on clause (b), as
expected), three BLOCKED (V13, V17, W21), each on one answer that only Frank can give. No clause that the lanes were to
produce is missing or failing. No YES is possible from this document: D2.2 (spec §7.3 item 4) refuses a `BLOCKED`
claimed gate. V13, V17 and W21 are re-judged after Frank answers, under §19.2 (R-371).

**Against `C_α¹`'s verdicts** (`docs/reviews/V02-alpha-verdicts-6fec822.md`, superseded with its candidate by R-370):
every verdict word, failing clause and missing input is the same. The difference is in the travelling limitations: W21
now carries L44, L45, L46 and L48, and W22 carries L47, the rows R-370 and R-377 added to the envelope at `C_α²`. Each
gate was judged again on `C_α²`'s own records. The agreement is a result, not something carried over.

**Against v0.1's verdicts at `67c66d9`** (`docs/reviews/T08-verdicts.md`):
- **V13: PASS → BLOCKED on V13 (e).** At v0.1, T08.A49's digests, equal to R-133's, met B50's digest and schema
  clauses directly. The v0.2 surface moved by design (R-192, R-234). B50's counterpart is MR-7: "digest and schemas by
  the chain, *under the same carry (MR-2)*". ADR 0028's `V17 carry` row names "V17, and T08.B50's surface", and it
  reads `pending`. M07a.A61 now names V13 (e) as well (R-372).
- **V17: PASS → BLOCKED on V17 (a).** T08 §4.7: a surface that differs from R-133's carried surface makes V17
  `BLOCKED` until Frank decides again (MR-2).
- **W21 and W22** were not judged at v0.1.
- The other eight V rows keep v0.1's verdicts.

**What `C_α²` changes, and what it leaves alone.** `git diff --stat 6fec822 cc73219` lists 11 files (checked here):
`CHANGELOG.md`, `benchmarks/m07a/reference_values.yaml`, `benchmarks/t08/support_envelope.yaml`,
`docs/decision-register.md`, the spec, its generator, `docs/support-matrix.md`, `scripts/check.sh`,
`scripts/v0_2_gate.py`, and two M07a test files. Nothing under `src/`, `schemas/`, `pyproject.toml` or the lock moved.
So the numerical evidence of steps 2–12 is expected to repeat, and it does. RC record O6 lists the exceptions, and the
step-12 values quoted below were re-read here.

**The precondition (§6.3: M07a's manifest `tested`): met.** `evidence/M07a/cc73219…/manifest.json` is `tested`: 38
pass, 0 fail, 6 unsupported. All of A00–A14, A20–A24, A30–A44, A50, A51 and A53 pass. The six unsupported are A52
(§19.4) and A60–A64, the outputs of this verdict and of action 10. Under R-373 the status rule reads exactly A00–A51
and A53, so the precondition now holds by the rule itself. At `C_α¹` it held only in substance (finding A4 there).

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review and not a
process-model sign-off. It sets no `reviewed`. Human sign-off (R-017's form) is Frank's, and this document does not
claim it. It moves no tolerance, band or classification rule.

**Criteria, read before the evidence and not re-read after it:**
- V02 alpha release spec §4–§6, §8, §18 (Amendment 2) and §19 (Amendment 3, R-370…R-379), with their markers;
- T08 release spec §3.3 and §4 with its amendments;
- T08 build-first B40–B51 with Amendments 3 and 4 (V13 (e));
- ADR 0028 D1–D7 and its two tables as they stand (all four cells `pending`);
- ADR 0022's status and revision 1 (V19 (i));
- M02 design note §10 G3–G12 with §14.5–§14.7 (W21);
- M01 spec §9 and §11 (W22).

## Frank's answers each row waits on (ADR 0028, `docs/adr/0028-v0.2-pre-release-policy.md`)

All four cells read `pending` at the time of judging. Under §4 rule 1 and Tables T6 and T7, an answer counts only if
it is dated on or after this document's `Judged` date, **2026-10-16**. An answer that a re-judgement reads must also be
dated on or before that re-judgement's date (T7). No answer has been recorded yet, so none needs re-dating (Q-A3-1).

| Row (verdict, clause) | ADR 0028 table and item | What a counting answer looks like | What it does |
| --- | --- | --- | --- |
| V13 BLOCKED, clause (e) | decisions table, `V17 carry` | `accepted, <date>`, with 2026-10-16 ≤ date ≤ the re-judgement's date | unblocks (e). It is expected to be met if M07a.A37 and A51 still hold at `C_α²` |
| V17 BLOCKED, clause (a) | decisions table, `V17 carry` (the same answer) | as above | unblocks (a), as above |
| W21 BLOCKED, clause (c) | decisions table, `M02 N1` | `accepted, <date>`, with 2026-10-16 ≤ date ≤ the re-judgement's date | unblocks (c), whose other items are met; the re-judgement also reads the merged `## v0.2.0a1` section for (f4)'s notes half (§19.5) |
| V14 FAIL, clause (b) | D3 table, row `V14 (b)` | `accepted, <date>`, with date ≥ 2026-10-16. No upper bound, because a re-judgement cannot list V14 | changes no verdict word. It only makes the FAIL releasable (D2.3) |
| no row (gate item 11) | decisions table, `N3` | `accepted, <date>`, with date ≥ 2026-10-16 | confirms the claim set this document judges |

Choosing an alternative, or declining, is not an acceptance. That covers the new V17 campaign, an N3 alternative and a
declined M02 N1. §7.3 item 11 refuses such an answer with "amend the alpha specification for it". **A D3 row alone
cannot release it** (finding B5).

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/v02-alpha-rc-record.md` | build lane: local `ref-x86-64`, a detached worktree at `C_α²` (clean at start, after the venv and at end), one script (`tools/run_local.sh`, 24 commands, every exit 0), threads pinned. CI dispatch 38813135468 and push 38813136015: `success`, head `cc73219…` (checked here in `artifacts/ci-run-*.json`) | none: the record reports and judges nothing | record |
| The 61 records it hashes | as above | **recomputed here: 61 of 61 sha256 equal the record.** 59 are committed under `evidence/M07a/cc73219…/rc/`; the two ensemble run files are in the RC worktree's `artifacts/rc/` | provenance |
| M07a.A43 on those records | the records themselves | checked here: 29 `t08-rc-v1` records and `t08-a43-dist.json` carry `commit` = `cc73219…`, `tree_clean = true` and the lock `ead4edf1…`. None deviates | provenance |
| Step 1: `check (ubuntu-latest)` 8533 passed, 100 skipped; `check (ubuntu-24.04-arm)` 8505 passed, 98 skipped; 2 deselected each | CI 38813135468 on the public repository; the summary lines grepped here from the hash-pinned job logs | the tests' own expectations | tested (CI) |
| Step 1's skip set (R-376) | `step1-skips/ci-x86-64.txt` (62 lines, sha256 `f2c8d42f…`) and `ci-aarch64.txt` (64 lines, `91dbe21a…`) | checked here: each file equals the `SKIPPED` lines of the hash-pinned CI log for its architecture, line for line. Classified below (V-gate skip audit) | record (formerly inference) |
| Steps 2–10 records (`t08-rc-v1`) | as in the RC record | registered values: R-149's identity digests; D_0 `171dd768…`, D_1 `6c4375b4…`, D_2 `383b4e2c…` (R-319), `6d13e13d…` (R-137); `S_min` 418; A34's rule and T06 A33's set | ci, tested, record |
| Step 11 (`step11/rc-step11.json`) | local, pinned cross-check and IDAES environments (freezes hashed) | `external_crosscheck.py --check` recomputes the committed record and compares bytes ("external-crosscheck.json matches"). The IDAES re-run is compared with `benchmarks/m01/idaes-conformance.json`; only `inputs.reference_values_yaml_sha256` differs. The re-run file's sha256 is `7e1d41dd…`, the same as M01's own re-run and as at `C_α¹` | ci-equivalent re-run; validation inputs |
| Step 12 (`step12/rc-step12.json` and its eight records) | local `ref-x86-64`, with a reactor environment built from `C_α²`'s lock and verified (lock `032a050c…`, reactor commit `6089593…`), one thread, on a host that may have been shared | M01's bounds and the probe record (G10), the design lane's G11v3 and G12 criteria, and G12's own certificate | numerical verification against registered records; a regression of the group's model |
| Step 12's five kept certificates | committed under `rc/step12/certificates/` (B-AM2-9) | checked here: the bundle's sha256 `faa8e4da…` equals `g12-real-loop-v3.json`'s `certificate_sha256`; the live and replay copies are byte-identical to it; all five carry `VERIFIED`, `uniqueness` and `dynamic_stability` `NOT_ASSESSED` | provenance |
| Which variant step 12 runs | `tools/run_local.summary.txt` lines 16–19 | checked here: G10 and G11 run `benchmarks/m02/variant-v3-provisional.json`. M02's design runs G11v3 on a provisional document that is never registered (note l.1804). It differs from the registered `pymrm-6089593-g2-nz800-s123-v3` in 9 leaves only: six hard-domain bounds, `inert_min` (absent), `timeout_s` 600 against 450, and the id. Pin, grid, floor and estimate are equal. G12 and its edges run the registered v3. This was so at `C_α¹` too (finding B4) | like-with-like check |
| M01 (`3c80392`) and M02 (`ba90619`) manifests, `tested` | build lane at their own commits, both ancestors of `cc73219` (checked here) | as stated per check | evidence about other commits, counted only through the RC job (spec §4 rule 3) |
| The envelope at `C_α²` | `git show cc73219:benchmarks/t08/support_envelope.yaml` | checked here against §19.1 item 1's normative texts: the `platforms` statement, L15, L44–L48 and U15 match. The harvest classes M02 `limitations[1,2,3,6]` as E (to L44, L45, L48, L44) and `[0,4,5]` as P. U15 cites the pure-NH₃ refusal node `tests/test_m02_wo8_g7.py::test_g7e_a_pure_nh3_feed_is_refused_by_the_flash` (Q-A3-3). M07a.A50 passes | record |
| Frank's statements (R-145, R-149, ADR 0022, the dossier's 2026-10-02 statements) and ADR 0028's four cells (`pending`) | recorded by the lanes from Frank's answers | none: these are the authority's decisions | decisions |

**What pins nothing.** The RC record's local-host timings (G11v3, G12 wall times) were measured under whatever load the
host carried. They are recorded beside the timeout and gate nothing (W21 (d)).

---

## V11 — PASS

| Clause | Judgement | Evidence at C_α² |
| --- | --- | --- |
| (a) semantic diff | met | T07 `diff_revisions` / `semantic_diff` nodes in step 1, both architectures |
| (b) immutable drafts | met | K06 revision, draft/ready, conflict and idempotent-commit nodes in step 1 |
| (c) task-specific validation | met | T01 STR-01…06 and R-022's DRAFT/INVALID nodes in step 1 |
| (d) units and component/reference checks | met | T06 A43, A55–A57, A67–A74 and THM-05 nodes in step 1. T01 A09 supersedes K06's structural check |
| (e) a real migration fixture | met | T08.A35 (the v0.0.0 bundle) in step 1. MR-10's counterpart, M07a.A42: `C_α²`'s `replay` gives a typed report on the `SYN-001-nominal` bundle written at tag `v0.1.1`, and `inspect` renders it (step 1; manifest `pass`) |

T08.A10 (D1) is green in step 1. **Does not establish:** migration of arbitrary old documents (only the two real
bundles are migrated); structural checks are generic (L38).

## V12 — PASS

At `C_α²`, every model in §14.3's list has contract, limiting/failure, balance and derivative nodes that pass in step 1
on both architectures, and each appears in a registered coupled case (SYN-001, T05 C1–C3, PTC-R1). `src/` is
unchanged since `C_α¹`. The C1 models are W21's and W22's evidence, not V12's (spec §5.1). **Does not establish:** the
listed model limitations; any C1 model's definition of done under V12.

## V13 — BLOCKED on V13 (e)

*Re-judged on 2026-10-17 to PASS: see `## Re-judgement`. The text below is the first judgement (2026-10-16), kept as recorded.*

| Clause | Judgement | Evidence at C_α² |
| --- | --- | --- |
| (a) DM/SCC/BTF with block statistics | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes in step 1; E1/E2 at library level (L43) |
| (c) scales before iteration | met | K03 and T02 nodes in step 1 |
| (d) model initialization | met | as at v0.1: each §7.4 source has a passing node or a recorded absence (K03 §10.1; L10) |
| (e) compatible warm starts | **blocked** | B40–B49 nodes green in step 1 (T08.A71's four elements). B50's counterpart (MR-7): the content differences are exactly B50's three entries plus the register-named v0.2 additions, M07a.A51 `pass`. The digest and schemas come by the chain, M07a.A37, on three hosts (step 8, 7/7 each). G16-b 40/40. `docs/derivations/scripts/t07_reference.json` and `t07_reference_c2.json` are unchanged since `c7bbc98` (`git diff` empty, checked here). **Missing:** the carry under which MR-7 places the digest and schemas. That is ADR 0028's `V17 carry` row ("V17, and T08.B50's surface"), which reads `pending`. |

**Why it differs from v0.1 (PASS):** see "Read this first". The missing input is Frank's decision, so the clause is
`BLOCKED`, not `FAIL` (T08 §3.3). M07a.A61's expectation now names V13 (e) (R-372). One answer unblocks V13 and V17
together.

**Does not establish:** that the v0.2 surface is acceptable for agents (Frank's carry decides that); warm starts
beyond exact id-set compatibility (L-WS-1, L-WS-2).

## V14 — FAIL on V14 (b)

- **(a) typed homotopy: met.** T04 A02–A12 nodes in step 1.
- **(b) one PTC family qualified by §7.5: not met.** In `T08-verdict-V14b.md`, the saddle clause fails on PTC-R1 on
  both registered platforms, so (b1) fails. No commit after `67c66d9` preregisters a new family or new SER settings.
  `6fec822..cc73219` touches none of that, so the result holds at `C_α²`. The PTC-R1 git-order and diagnostic nodes skip
  in CI: the archived history, and no committed ci-x86-64 results (skip audit below). They bear on (b2), and (b1) fails
  regardless.
- **(c) three bounded recovery edges: met.** T02 and T04 nodes and T08.A33 in step 1. E1 and E2 are library-level
  (L43).

Same verdict as v0.1 and `C_α¹`. ADR 0021's acceptance (2026-09-29) is not read (§4 rule 1; ADR 0028 D2). The FAIL is
releasable only if ADR 0028's D3 row `V14 (b)` records Frank's acceptance dated on or after 2026-10-16. Today it reads
`pending`. **Does not establish:** that PTC can never qualify. PTC stays experimental (L01).

## V15 — PASS

- **(a) frozen phase attempts with restart: met.** T03 A00–A26 nodes in step 1.
- **(b) cross-unit promotion to EO without nested SM: met.** T02 nodes in step 1.
- **(c) multiple roots with honest branch reporting: met.** T03 fingerprint and provenance nodes; T06 ADV-05 and
  THM-09 nodes in step 1.

The certificate schema fixes `uniqueness` and `dynamic_stability` to `NOT_ASSESSED`, and all five step-12 certificates
at `C_α²` carry both (checked here). **Does not establish:** root completeness, uniqueness or stability (L19).

## V16 — PASS

T06 verdict 1 stands: 8 of 8 by both tools, 16/16 AGREE, the positive controls DISAGREE. T08.A48, which checks that our
side re-solved equals its committed records, passes 12/12 on ref-x86-64, ci-x86-64 and ci-aarch64 at `C_α²` (step 7,
165 nodes, none failed, missing or skipped). The tool side is not re-run (T08 §4.6). **Does not establish:** IDAES
agreement beyond the near-sharp ε (L16); the tools' environments beyond their pins (L17).

## V17 — BLOCKED on V17 (a)

*Re-judged on 2026-10-17 to PASS: see `## Re-judgement`. The text below is the first judgement (2026-10-16), kept as recorded.*

- **(a) a surface to which Frank has carried `v17-c2`'s evidence, with M07a.A37's chain holding: blocked.**
  - The chain holds on three hosts at `C_α²`. `d(T(C_α²))` = `383b4e2c…` = D_2 (R-319). Stripping c_2 gives
    `6c4375b4…` = D_1. Stripping c_1 from that gives `171dd768…` = D_0 (R-133). Serving `v17-c2`'s two texts gives
    `6d13e13d…` (R-137). The 17 tools and their description files are as registered.
  - **Missing:** Frank's `V17 carry` answer in ADR 0028, which reads `pending`.
- **(b) G16-b 40 of 40 over Python, CLI, HTTP and MCP: met** on three hosts.

**Why it differs from v0.1 (PASS):** T08 §4.7 as amended by R3 2. The surface at `C_α²` differs from R-133's, so V17 is
`BLOCKED` until Frank decides again (MR-2). **Does not establish:** agent behaviour on the v0.2 surface. No agent was
run (L12).

## V18 — PASS

- **(a) dependency and data provenance, binary inventory: met.**
  - T08.A30 `PASS` on ref-x86-64 (381 objects, closure 150), ci-x86-64 (381, 150) and ci-aarch64 (308, 147). No
    undispositioned finding in a required closure; METIS not reached.
  - T08.A31 and A32 nodes in step 1; A31's checks in step 3 (8/8).
  - MR-12: `pyproject.toml` is unchanged since `C_α¹`. It declares the extras `dev` and `server`, as `v0.1.1` does, so
    no new extra needs an audit.
  - RC record O2's `files_digest` and host differences are fields A30's verdict does not read.
- **(b) final target-Jacobian regularity, (c) qualified energy checks: met.**
  - K04 and T06 A32, A33, A37–A46 nodes in step 1.
  - T08.A34 (MR-11) finds 0 violations in every audited set: 77 locally (72, plus step 12's five bound by hash), 72 on
    each CI `rc-steps` host, 1 in each clean install, and 49 in the bundle set.
  - Step 6 holds the ensemble's certificates to T06 A33 (A33 0 on both hosts).
- **(d) no enabled recovery edge without a direct failure test: met.** T08.A33 in step 1.

Same as v0.1 and `C_α¹`. **Does not establish:** the certificates that step 5's replays re-emit (T08 B13); the
certificates' locality (L19); the provider shared with the energy checks (L06).

## V19 — PASS

- **(i) Frank's selection recorded in ADR 0022: met.** Accepted 2026-10-02, with revision 1 (R-145).
- **(ii) every §7.1 item: met.** The dossier has items 1–12. It is not among the 11 files changed since `C_α¹`, and no
  status moved away from `met`.
- **(iii) H1–H6 `met`: met.** As at `C_α¹`; the dossier is unchanged.
- **(iv) T08.A61–A63: met.** The record tests pass in step 1. `benchmarks/t08/v19/` is byte-identical between `67c66d9`
  and `cc73219` (`git diff` empty, checked here).
- **(v) no unknown in the rights table: met.** T08.A64 in step 1. The rows reading `needs_fact` for M01 state their
  source, licence, scope and mode, as v0.1 judged.

Same as v0.1. **Does not establish:** any comparison with data. The dossier is a feasibility record.

## V20 — PASS

- **(a) nominal fixtures, (b) invalid structure rejected naming the revision's objects, (c) no false `VERIFIED`: met.**
  - T08.A47 12/12 on three hosts (T06 A02–A08, A16, A19, A20, A47, A50; 165 nodes, none failed, missing or skipped).
  - Nothing verified outside S3 (worst success ratio 0.0968).
  - T08.A10 node in step 1.
- **(d) ≥ 95 % over the registered ensemble: met.**
  - T08.A46: N = 440 and S = 434 on ref-x86-64 (F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3) and on ci-aarch64 (4, 2),
    against S ≥ 418.
  - No F-CRASH or F-OTHER-ROOT. Same-class replay 28 of 28 `MATCH`.
  - The class counts equal `C_α¹`'s and `67c66d9`'s (O4).
  - The one-sided 95 % Clopper–Pearson lower bound, 0.973264, is reported and never gated. It assumes independent
    starts, which clustered starts are not.

Same as v0.1. **Does not establish:** robustness beyond the nominal profile (L09); out-of-sample performance for
`T06-revision-v2` (L32).

### V-gate skip audit (step 1, R-376)

Step 1's skip set is now a record. The table classifies each architecture's skips by reason, read from the two
`step1-skips` files. Each count sums to the pytest totals (100 and 98).

| Reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| archived pre-0.1.0 history (R-150): `conftest.py:43` (33), `test_t07_evidence_manifest` (28), `test_t08_evidence_manifest` (5) | 66 | 66 | No. The conftest guard is called only from `test_evidence_manifests`, `test_t06_w31_runs` (A98a, A99b), `test_t08_ptc_r1_case` (B20) and `test_t08_w4_v0_1_gate` (checked here). These check v0.1 history and provenance. B20's git order bears on V14 (b2) only |
| W27 pinned archive absent (`test_m06_w27_*`) | 23 | 23 | No: W27 is not claimed |
| A52's gate table pending (`test_m07a_changelog`) | 2 | 2 | No: A52 is `unsupported` by R-373 |
| PTC-R1 diagnostic results only for other CPUs (`test_t08_ptc_r1_diagnostic`) | 6 | 0 | No: V14 (b) fails regardless |
| platform-bound fixtures: `test_k05_schemas` (certificate floats recorded on Python 3.13.5; CI runs 3.13.16), `test_t06_w28_records` (refusal checked) | 2 | 2 | No (finding B1 on the K05 node) |
| aarch64 only: `test_k01_backend_dependency` (the x86-64 audit; aarch64 inventory is T08.A30 at step 9), `test_t06_w13_f6` (A75 states found on ref-x86-64; runs on x86-64), `test_m06_browser_smoke` (no browser) | 0 | 4 | No |
| `test_t08_w1_ledger` ("not in A02") | 1 | 1 | No |

This confirms `C_α¹`'s inference (its finding A7) by record: no V, W21 or W22 clause rests on a skipped node. The U15
nodes, the A14 nodes and the M01/M02 nodes cited below are not in either skip file, and step 1 has no failure.

---

## W21 — BLOCKED on W21 (c)

*Re-judged on 2026-10-17 to PASS: see `## Re-judgement`. The text below is the first judgement (2026-10-16), kept as recorded.*

Judged by spec §6.1, as ADR 0028 D7 reads it. Every number below is the group's model at the pin, run through the
adapter. It is numerical verification against registered records, not empirical validation. All step-12 figures were
re-read here from `C_α²`'s records.

**(a) Port mapping: met.**
- M01.A25–A32 and A49–A51 (stand-in path) and M02 G4 (e)–(g), G8 (a)–(e) and G9 (b) nodes in step 1 on both
  architectures.
- M01.A52's record half: mapping 1 ulp against 2 (node in step 1).
- G10 (h) at step 12: the full boundary at N_tubes = 1, max relative difference 1.43 × 10⁻⁸ against 10⁻⁶.

**(b) Accuracy contract: met.**
- The registered v3 variant declares `precision_floor_rel` 10⁻⁶ and the design grid's discretization estimate
  (num_z 800). G10 (i): every `ok` result's estimate equals the reference, 3 of 3.
- G10 runs the provisional document, whose grid, floor and estimate equal v3's (finding B4).
- G10 (b) 1.56 × 10⁻⁸ (bound 10⁻⁶).
- G10 (e) 3.84 × 10⁻⁸ (bound 10⁻⁷). This is the adapter's figure at `C_α²`, quoted under R-379; the bound is the
  criterion.
- G10 (f) 5.06 × 10⁻⁵ (bound 10⁻³).
- G12's floor ratios are 65.3 (ξ) and 13.3 (T), against ≥ 10. T's margin is 1.33×.
- M01.A48's record half (the grid study) in step 1.

**(c) Out-of-process execution policy: blocked.**
- G3 (a)–(h) in step 1 on Linux (both architectures); G4 (a)–(i) and G5 in step 1: met.
- The support matrix at `C_α²` (`docs/support-matrix.md`, external model execution row) states the profile
  `external-subprocess-v1`, "**not a sandbox**", "Linux is registered; macOS best effort; Windows is refused before
  spawn": met. The re-emitted matrix adds L44 and L45. Its `platforms` row now says the reactor is measured on x86-64
  only, which removes the contradiction `C_α¹`'s finding A1 named.
- **Missing:** M02 N1 accepted by Frank in ADR 0028's decisions table. §6.1 makes this a precondition of the clause,
  "not a default". The cell reads `pending`. The input is Frank's, so the clause is `BLOCKED`.

**(d) Timeout: met.**
- G3 (b) in step 1: `timed_out` within 3.5 s under `timeout_s = 1`, no retry.
- The per-attempt timeout in force at `C_α²` is the registered v3 variant's 450 s
  (`src/openflowsheet/adapters/variants/pymrm-6089593-g2-nz800-s123-v3.json`, checked here). It comes from §5.2's rule
  as amended by §14.5 D4 (D104, D111).
- G11 (d) at step 12: `startup_s` 1.87–1.94 s and `solve_s` 28.6–29.2 s over five repeats (start-up share 6.2 %).
- No step-12 attempt came near 450 s. The longest G11 timing in the runs file is 104.7 s, the longest point solve in
  the coverage record 101.5 s, and the slowest G12 call 47.8 s. G12 as a whole took 126.7 s over 4 experiments.
- Under this run's load, the G11v3-4 rule gives 320 s for V5 (270 s at `C_α¹`). This is not a bound (R-378). The
  registered 450 s governs (finding B3).

**(e) Provenance: met.**
- G6 (a)–(c) in step 1.
- Blueprint §9.1's six items in every experiment result record that step 12 writes:
  - G10 calls the backend directly and writes none.
  - G12's four results and their attempts sit in its coupling record. `reproduce` returned `MATCH` from that record.
    It cannot do so unless the record passes `coupling_record_problem`'s check against
    `experiment.schema.json#/$defs/coupling`. That check `$ref`s `result` and `attempt`, whose required members carry
    the six items.
  - G11's results, written by the same `ExperimentRunner` to scratch stores, were not audited one by one. Their
    presence rests on that single writer path, schema-checked by G5's node in step 1 and by G12's record in step 12.
    This is inference, stated as such. R-375 defers the per-result audit to 0.2.0's RC.
- G10 (g): M01.A47 (a) bitwise, environment block equal.
- G12's `reproduce`: `MATCH`, floats bitwise, 4 external results replayed from the record. Live rerun bitwise, 4 of 4.
- The reactor commit is `6089593464fc9bc2c0a0cb58e30ad5433ece6332`, ADR 0022's pin, in the v3 variant and in the
  built environment's manifest (checked here).
- Rights: T08.A64 in step 1. The wheel's package data holds the reactor lock and no other file of the group's. T08.A32's
  node in step 1 refuses any third-party data or non-package Python in the sdist or wheel. `src/`, `pyproject.toml` and
  `MANIFEST.in` are unchanged since `C_α¹`.

**(f) Parent-model validation, read as ADR 0028 D7: met (the verdict's half of (f4); the notes' half is read at the
re-judgement).**
- **(f1)** G10 (g): A47 (a) bitwise at step 12.
- **(f2)** T08.A61: the group's suite at `6089593`, 69 passed, 0 failed, 3 skips counted not reproduced. This is a
  record measured at T08 on one host and re-checked in step 1, at the pin the variant names.
- **(f3)** The grid study and DX-01 estimate (M01.A48's record half), path independence (G10 (b)) and the estimate
  carried in every `ok` result (G10 (i)).
- **(f4)** Stated here:
  1. the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's
     rate law; dossier H2, R-143) is the group's evidence;
  2. this project has compared no reactor result with data;
  3. the numbers are the group's model at the pin, a regression;
  4. their discretization bias is 1.0–1.4 % in NH₃ (M02 §13).

  At `C_α²`, the envelope carries all four as L46. The `## v0.2.0a1` skeleton in `CHANGELOG.md` holds each of §19.5's
  phrases for them (line-wrapped). It also holds the reactor bullet, the sandbox bullet, the property-route additions
  and the corrected rights text ("may be used and referenced"), and it does not contain "awaits Frank's statement"
  (checked here; A52 (d) in step 1). The section is final only after §9.2 step 5. The re-judgement reads the merged
  section (§19.5). If any of the four is missing there, (f4) is not met there.

The stronger reading of (f), that this project compares reactor results with data, is not the default (F-α4) and is not
applied. It is no longer blocked on rights (Frank, 2026-10-02; §6.1 marker).

**W21 does not establish:**
- that the reactor is right. Every real-reactor number is the group's model at the pin, a regression, with F-R2, F-R3
  and its discretization bias (L46);
- bitwise reproduction across machines, or any run on aarch64, which is not measured (Q1). The envelope now says so
  (L44, L15);
- a sandbox (L45), Windows support, or concurrency across hosts or on network filesystems;
- sensitivities through the reactor, or optimization;
- the convergence of coupled loops in general: one real loop, two edges, and G11's corners and centre (L48);
- that the stand-in certifies anything about the reactor (R-199);
- timings under any other load. Step 12 may have shared its host.

## W22 — PASS

**(a) Numerical verification: met.** M01.A05–A22 in step 1, against closed forms from `m01_reference.py`, independent
of the implementation (tolerances 10⁻⁹–10⁻¹⁴). M01.A34 (`--check`, 88 claims) in step 1.

**(b) Conformance with an independent implementation of the same method: met.**
- M01.A37 in step 1: `pr-c1-v1` against the committed IDAES 2.13 record.
- Step 11: the IDAES re-run's numbers equal `benchmarks/m01/idaes-conformance.json`'s. The one differing member is
  `inputs.reference_values_yaml_sha256`; it is listed, and M01's manifest gives the reason. The re-run file is
  byte-identical to M01's own re-run (`7e1d41dd…`).

**(c) Empirical validation of pure-component behaviour against the reference equations of state: met.** Step 11's
`external_crosscheck.py --check` recomputes the record at `C_α²` and finds it byte-equal ("matches"). Values from the
record:

| Assertion | Measured | Band | Band ÷ measured |
| --- | --- | --- | --- |
| M01.A38, max \|P_sat,PR/P_sat,ref − 1\| | 0.012675 (240 K) | 0.02 | 1.58 |
| M01.A39, max \|Δ ln φ^L\|, NH₃ | 0.040096 (250 K, 25 MPa) | 0.05 | 1.25 |
| M01.A40, max \|Δ ln φ^V\| | 0.042371 (CH₄, 268.15 K) | 0.05 | 1.18 |

These are validation bands (R-160), not numerical tolerances. The ratios are quoted, not turned into a confidence
statement. The reference is CoolProp 8.0.0's equations of state, which are themselves correlations of data, not raw
measurements.

**(d) Sufficient for the selected chemistry: met.** G7 (a)–(e) and G8 (a)–(c) in step 1. At step 12, the C1 loop
binds every property evaluation to `pr-c1-v1` and ends `VERIFIED`. The gaps the route leaves:
- the LIQUID regime and pure-NH₃ flashes are deferred and refused typed (M02 N5). This is now the envelope's U15, whose
  two nodes pass in step 1;
- dissolved light gases are not represented (R-143; L42);
- k_ij = 0: k_H2–NH3 = 0.1 would move y* by −3.1 % (R-157);
- there is no mixture VLE validation (R-160);
- PR's saturated-liquid volume is 11–30 % high and its enthalpy of vaporization 2–5 % high (M01 §11; now L47). No v0.2
  loop decision uses either.

**W22 does not establish:** mixture VLE; the effect of k_ij beyond R-157's statement; the near-critical region;
liquid-density fitness; any claim outside the five C1 components and M01's registered domain.

---

## Alternatives considered and rejected

1. **V17 PASS (carried), because the chain holds and the carry is the expected default.** Rejected. T08 §4.7, MR-2 and
   M07a.A61 make the carry Frank's recorded answer, and a default is not an answer. T6 and T7 require the answer to be
   dated on or after 2026-10-16.
2. **V13 PASS, treating the carry as V17's business only.** Rejected. MR-7 reads "under the same carry (MR-2)"; ADR
   0028's carry row names "T08.B50's surface"; T08.B51 makes B50 part of V13 (e); at `814e151`, B50 alone made V13
   FAIL. R-372 now writes V13 (e) into A61.
3. **W21 PASS, reading N1 as a gate precondition only (§7.3 item 11), not as part of clause (c).** Rejected. §6.1 lists
   it under (c) as "a precondition, not a default", and §6 meets a clause only when every listed item holds.
4. **W21 (f) not met, because the notes are only a skeleton.** Rejected. §9.2 step 5 writes the notes after this
   verdict, and §19.5 assigns the notes' half to the re-judgement. The skeleton at `C_α²` already carries the four
   statements.
5. **No PASS on W21-adjacent rows, or W21 FAIL, for the missing Q1 row.** This was `C_α¹`'s alternative 5. It no
   longer arises: L44 and the corrected L15 and `platforms` axis are in the envelope at `C_α²`.
6. **No verdict, because M07a's manifest has six `unsupported` assertions.** Rejected. R-373's status rule makes the
   manifest `tested` without them, and each is an output of this verdict or comes after it.
7. **W21 (e) not met for want of a record-by-record audit of G11's scratch results.** Rejected. Field presence is
   structural, and the single writer path is schema-checked at step 1 and, on the registered variant, at step 12.
   R-375 records the audit for 0.2.0. This is stated as inference.
8. **W21 (a), (b) or (f1) not met because G10 ran the provisional variant document, not the registered v3.**
   Rejected. M02's design registers that procedure (note l.1804). The documents differ only in the boundary block,
   `inert_min`, the timeout and the id, none of which G10's figures depend on. G12, which carries the floor ratios and
   `reproduce`, ran the registered v3 (finding B4).
9. **V18 not PASS because step 5's replays re-emit certificates that nobody audits (B13).** Rejected. This is v0.1's
   accepted scope, a recorded limitation. The 49 bundles were audited when written.
10. **V14 PASS on route (a) alone.** Rejected (R-118; T08 §4.4 "Why not re-read").
11. **Reading W22's band ratios, or the Clopper–Pearson bound, as confidence statements.** Rejected (spec §6.2; T08
    §4.10).
12. **Carrying `C_α¹`'s verdicts over because `src/` did not change.** Rejected. §4 rule 3 and R-370 item 3 admit only
    evidence about `C_α²`. Every row above rests on `C_α²`'s records.

## What would change these verdicts

- **Frank records `V17 carry` as `accepted, <date ≥ 2026-10-16>`.** V13 (e) and V17 (a) are re-judged at `C_α²`, with
  the same `Judged` date and a re-judgement line dated on or after the answer (§19.2). They are expected to be met if
  M07a.A37 and A51 still hold. If Frank chooses the new V17 campaign instead, that is a spec amendment (§7.3 item 11),
  and V17 and B50's surface half of V13 (e) move onto that campaign's evidence.
- **Frank records M02 N1 as accepted** (dated as above). W21 (c) is re-judged, and (f4)'s notes half is read in the
  merged section. If N1 is declined, W21 (c) is not met. Such an answer is also no acceptance under §7.3 item 11, so
  the route is a spec amendment, not D3 alone (finding B5).
- **Frank's D3 acceptance of V14 (b)**, dated on or after 2026-10-16. It changes no verdict word; it only makes the FAIL
  releasable.
- **Any change to a D2.4 path** (`src/`, `schemas/`, `benchmarks/`, the lock, `pyproject.toml` …) means a new candidate,
  and every row is re-judged on its RC job. This includes any later change to `benchmarks/m07a/reference_values.yaml`
  (§19.10).
- **A new preregistered PTC family or SER settings, committed before any result, that passes (b1)–(b4).** It reopens
  V14 (b).
- **A measured aarch64 reactor run (Q1).** It removes a W21 does-not-establish item and would retire part of L44. It
  changes no clause.
- **A record showing a skipped node that a clause rests on**, or a G11 result missing one of §9.1's six items. Either
  reopens the clause it bears on.

## What these verdicts do not establish

- **No empirical validation of the reactor, and none of v0.1's synthetic chemistry.** W22 (c) is empirical validation
  of pure-component PR behaviour against reference equations of state, inside R-160's bands, and nothing more.
- **No optimality evidence of any kind.**
- **Portability of W21.** It rests on one machine (ref-x86-64), one environment and one thread, on a possibly shared
  host. The V rows rest on both architectures.
- **Agent behaviour on the v0.2 surface** (V17, V13 (e)).
- **Scientific or process-model review** of anything. Human sign-off is recorded separately and is not claimed.
- **Releasability.** This document gives the verdict words. A tag needs §7.3's twelve items: Frank's four answers, the
  re-judgement, the ledger (A64), the merged notes (A52), the required ADRs Accepted (B6), and his dispatch.

## Limitations that must travel into the manifest and the release report

- The envelope ids in the table, per gate. At `C_α²` the envelope itself carries what `C_α¹`'s verdict had to carry
  outside it:
  - the reactor measured on x86-64 only, opt-in, R3, no CI job (L44, L15);
  - the profile is not a sandbox (L45);
  - W21 (f4)'s four statements (L46);
  - PR's liquid-volume and enthalpy-of-vaporization bias (L47);
  - G11's corners and centre and the inert floor (L48);
  - M02 N5's refusal (U15, an unsupported-capability row; the gate's column takes `L` ids only).
- V14 (b) FAIL, PTC experimental (L01), with ADR 0028's D3 acceptance still to be recorded.
- V13, V17 and W21 are BLOCKED on Frank's answers. No tag may be proposed on this document as it stands.
- W21 (e)'s G11 provenance is an inference (R-375). The G11 and G12 timings were measured on a possibly shared host
  and bound nothing.

## Findings

`C_α¹`'s findings, at `C_α²`:

| `C_α¹` finding | Ruling | At `C_α²` |
| --- | --- | --- |
| A1 (Q1 row; `platforms`/L15) | R-370 | **resolved**: L44, the corrected axis and L15 in the envelope and the support matrix; the harvest re-classed (checked here) |
| A2 (date rule with a re-judgement) | R-371 | **resolved** in `v0_2_gate.py` (Table T7, T8); M07a.A14 passes |
| A3 (A61 omits V13 (e)) | R-372 | **resolved** |
| A4 (`tested` vs A52) | R-373 | **resolved**: the manifest is `tested` by its rule |
| A5 (notes lack (f4) item 4; stale rights text) | R-374 | **resolved in the skeleton**; the re-judgement reads the merged section |
| A6 (G11 results not audited) | R-375 | **open by ruling**, for 0.2.0's RC; W21 (e) keeps the inference |
| A7 (skip set an inference) | R-376 | **resolved**: the skip files are records; audit above |
| A8 (N5 and PR liquid bias without rows) | R-377 | **resolved**: U15, L47 |
| A9 (G11v3-4 rule's 270 s) | R-378 | **confirmed**: 450 s governs; the rule gives 320 s at `C_α²` (B3) |
| A10 (G10 (e)'s quoted figure) | R-379 | **resolved**: this verdict quotes step 12's figure at `C_α²`, 3.84 × 10⁻⁸ |

New at `C_α²` (none changes a verdict):

- **B1.** `tests/test_k05_schemas.py`'s certificate-float fixture records Python 3.13.5. CI runs 3.13.16, so the node
  skips on both CI architectures. Step 1 is CI-only, so the node ran nowhere at `C_α²`. No clause rests on it, because
  V18's certificate evidence is T08.A34's audit. If a later RC wants this node exercised, it should run it on
  `ref-x86-64` or re-take the fixture.
- **B2.** `pytest -rs` names a skip by its location. For the 33 skips raised in `conftest.py:43` that location is the
  helper, not the test, so the record gives the archived commit but not the node. This verdict maps them statically to
  four files (audit above). A later RC wanting node-level skip records needs `-rA` or a JUnit file.
- **B3.** The G11v3-4 timeout rule moved from 270 s (`C_α¹`) to 320 s (`C_α²`) on the same host. This is the load
  dependence §14.5 D4 records. R-378 already makes the registered 450 s govern. Nothing to do.
- **B4.** Step 12's G10 and G11 run `benchmarks/m02/variant-v3-provisional.json`, by M02's design, and G12 runs the
  registered v3. The two documents agree in every leaf G10's figures depend on (9 differing leaves, listed above). This
  verdict names it so that a later reader does not take it for a mismatch.
- **B5 (correction to `C_α¹`'s "What would change").** That document said a declined M02 N1 would make W21 a FAIL
  "releasable only through ADR 0028's D3 table". §7.3 item 11 refuses any decisions answer that is not an acceptance.
  A declined N1 therefore needs a spec amendment, whatever D3 records.
- **B6 (procedural; outside the verdict).** A dry run of `v0_2_gate.py --rc cc73219…` was made against a commit object
  holding this document. It parses the document (exit 1, not 2) and refuses for 16 reasons:
  - D2.1 ×4: the ledger, which WO-11/A64 writes after these verdicts;
  - D2.2 ×3: V13, V17, W21;
  - D2.3 ×1: V14 (b);
  - Frank's three pending answers;
  - five ADRs not Accepted.

  Of those five ADRs, only 0028 waits on Frank. 0027, 0033, 0034 and 0035 are conditionally accepted ("Accepted when
  M01's/M02's evidence manifest is `tested` …"), and their status lines still read Proposed. Whether those conditions
  are met is for the lanes to record. `docs/adr/` is not a D2.4 path, so this needs no re-cut. Until it is done, §7.3
  item 12 refuses a YES even after Frank answers.
