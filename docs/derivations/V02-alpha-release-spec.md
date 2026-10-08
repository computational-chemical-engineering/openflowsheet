# V02 alpha — the release gate of the pre-release `0.2.0a1`: what it claims, the v0.2 counterparts of the moved v0.1 records, how W21 and W22 are judged, and the release candidate

**Package:** M07a, the alpha stage of M07's v0.2 gate (plan v1.2 §4.4 row M07, "real reference journey and v0.2
gate"; R-153, "a pre-release `0.2.0a1` once the reactor runs in the loop (M02 `tested`)"). Lanes Design / Build: the
design lane owns this specification, ADR 0028 and the verdicts; the build lane owns the gate script, the release
mechanics, the release-candidate (RC) job and the evidence manifest `evidence/M07a/<C_α>/manifest.json` (ADR 0028 D5).
**Author:** design lane (`specifier`), 2026-10-08, on `wp/V02-alpha-gate` from `main` @ `3eca9c8`.
**Status:** Proposed. Binding on the build lane and on the `verdict` agent once committed. It is written against the
default of N3, which Frank has not answered (§14 F-α0). A defect found in it is amended here, dated, and never worked
around downstream.
Amended 2026-10-09 by Amendment 1 (review), §17.
**Requirements served:** D17 (every release gate judged, none substituted) and D20 (a reproducible release candidate).
Gates V11–V20, W21 and W22. The evidence-manifest schema carries D/A ids only, so the gates travel in
`docs/requirements.yaml` and in the verdict document, as in T08.
**Decisions:** ADR 0028 (Proposed). Register R-238 (the claim set, the gate set, Frank's per-release answers, W21's
reading) and R-239 (the moved records and their counterparts).
**Reference generator:** `docs/derivations/scripts/v02a_reference.py` → `benchmarks/m07a/reference_values.yaml`.
`--check` re-derives every claim of §11 and requires the committed YAML byte for byte.

---

## 0. The answer, in one paragraph

`0.2.0a1` claims what v0.1 claimed and two things more. It claims V11–V20, with V14 (b) FAIL, **re-judged at its own
release candidate `C_α`** by T08's criteria, which are unchanged. It also claims **W21** (the PyMRM reactor adapter) and
**W22** (the Peng–Robinson route of the ammonia loop). It claims nothing of W23–W27. The web shell (M06) ships in the
alpha but is not claimed.

The gate is `scripts/v0_2_gate.py`, one script for the 0.2 line. Its only registered gate set is
`v0.2-alpha-gate-v1`, which covers `0.2.0aN` and no other version. It reuses three things from the v0.1 gate unchanged:
the decision of ADR 0021 D2, the tree check, and the RC-record grammar. `scripts/v0_1_gate.py` is not edited.

Twelve v0.1 records moved, or must move, during v0.2. Each has a v0.2 counterpart at least as strict, and none is
relaxed (§5.2).

Four answers only Frank can give are preconditions of a YES, and the gate checks that each is recorded:
- his answer to N3;
- his acceptance of V14 (b) FAIL **for this release**, because ADR 0021 D3 is per release;
- his carry of V17's agent evidence across the surface changes registered since R-133, because T08 §4.7 makes V17
  `BLOCKED` without it;
- his acceptance of M02's "not a sandbox" execution profile, which the alpha publishes.

---

## 1. Authority, scope, and what is out of scope

**Authority.**
- Blueprint v3.1 (SHA-256 `66f574b0…`, as in the plan header): §14.4, whose bullets 1 and 2 are W21 and W22, and §14.3
  (V11–V20).
- Plan v1.2: §5.1 (the gate ledger), §4.4 (M07's "v0.2 gate") and §6.5 (the RC job).
- ADR 0021: D1, D2, D4 and D5 are reused unchanged (its Consequences: "A later release reuses D1, D2 and D4 unchanged;
  D3 is per release").
- T08 release spec: §3.3 (rules of judgement), §4 (V11–V20), §8 (the RC and its job) and §9 (assertions), with its
  Amendments R3–R8.
- M01 spec: §8.14, §8.15, §9.8, §9.9, §10 and §11.
- M02 design note (`docs/design/M02-pymrm-adapter.md` on `wp/M02`): §10 (G1–G12) and §14 B1.
- Register: R-151, R-153, R-160, R-192, R-193, R-216 and R-217.

**Plan rows and blueprint bullets.** Where a plan row omits a clause of its blueprint bullet, the blueprint clause
counts (T08 §1). W21's row is "PyMRM boundary/accuracy/execution and provenance". It omits three clauses of blueprint
bullet 1: port mapping, timeout, and parent-model validation (FD-α1).

**Frozen interfaces.** Nothing here changes a frozen interface (`docs/interfaces-frozen.md`), a schema, an identity
key, a tolerance or a registered result.
- The new evidence package id `M07a` matches the manifest schema's pattern `^[PKTMSR][0-9]{2}[a-z]?$`.
- The ledger schema already admits W gates.
- T05b is the precedent for a letter-suffixed package with no row in the ledger's package table.

**In scope.**
- (a) What `0.2.0a1` claims and does not claim (§3).
- (b) The rules of judgement at `C_α` (§4).
- (c) V11–V20 at `C_α`: the rows carried unchanged, and the moved records with their counterparts (§5).
- (d) W21's and W22's clauses, evidence and verdict procedure (§6).
- (e) The gate script's version logic, inputs and decision (§7).
- (f) The RC and its job (§8).
- (g) The release mechanics and Frank's dispatch (§9).
- (h) Numbered assertions (§10) and the generator (§11).
- (i) Open questions, Frank's items and the build-lane work orders (§13–§15).

**Out of scope.**
- W23–W27 and the 0.2.0 gate (M07 registers `v0.2-gate-v1`).
- Any change to M01's or M02's assertions, tolerances or design.
- Any change to `scripts/v0_1_gate.py`, `scripts/t08_rc.py`'s registered constants, or a v0.1 release record.
- Tagging, publication, PyPI and billed agent campaigns. These are Frank's.

---

## 2. What this specification establishes

1. The claim set of `0.2.0a1`, `v0.2-alpha-gate-v1`: claimed V11–V20, W21, W22; not claimed W23–W27 (§3). Its
   alternatives are stated for N3.
2. That V11–V20 are judged **at `C_α`** under T08 §4 unchanged, with every moved record replaced by a counterpart at
   least as strict (§5).
3. W21's six clauses and W22's four, each with its evidence and verdict rule, and one reading decided by the design
   lane: "parent-model validation" (§6.1 (f); ADR 0028 D7).
4. `scripts/v0_2_gate.py`: its version coverage, inputs and decision, its outputs, and how R-151 applies (§7).
5. `C_α` and a 13-step RC job: T08 §8.2's steps 1–10 at `C_α` with step 8 replaced, two W steps, and the gate (§8).
6. The changes to `release.yml`, `changelog_section.py` and `RELEASING.md` that a PEP 440 pre-release needs, and the
   procedure up to Frank's dispatch (§9).
7. 43 numbered assertions (§10). Every float comparison among them reuses a tolerance already registered, with its
   argument, by M01, M02, K04/ADR 0007, T02 §6.4, T06 or ADR 0025. **This specification registers no tolerance.**

---

## 3. The claim set `v0.2-alpha-gate-v1` (N3's default)

### 3.1 Claimed

| Gate | Blueprint | Judged at `C_α` by | Owner packages |
| --- | --- | --- | --- |
| V11–V20 | §14.3 bullets 1–9; §13.4 | T08 release spec §4, unchanged, with §5's counterparts | as in the ledger |
| W21 | §14.4 bullet 1 | §6.1 | M01, M02 |
| W22 | §14.4 bullet 2 | §6.2 | M01 |

### 3.2 Not claimed

W23 (surrogates), W24 (optimization), W25 (the reactor-refinement journey), W26 (the web shell) and W27 (external
benchmark adaptation) are not claimed.

The gate prints each of them as `not claimed (v0.2-alpha-gate-v1)`, whatever the ledger holds, and none of them blocks
(M07a.A06).

The alpha ships whatever `C_α` contains: today M06's web shell, and M03's NLP adapter if M03 merges first (Q6). Shipped
but unclaimed code still enters the support envelope (T08.A20) and the release notes' limitations. It does not enter
the claims.

### 3.3 N3 and its alternatives (Frank's)

- **Default.** As §3.1–§3.2.
- **(i) Also claim W26.** M06 is `tested` and merged. A W26 verdict at `C_α` would need criteria, which M06's design
  note supplies, and no extra RC step beyond step 1, where its browser test runs on CI's x86-64 leg. Cost: one more
  verdict row. This spec would be amended to gate set `v0.2-alpha-gate-v2`.
- **(ii) Claim only W21 and W22, without re-judging V11–V20.** The notes would state that v0.1's gates were judged at
  `67c66d9` and not at `C_α`. *Not recommended.* The alpha's code differs from v0.1's: M01's provider, M02's adapter,
  M06's shell, and additive contract changes. A V gate that is not judged on that code is an unstated gap, and R-153's
  watch-for asks for a gate "of its own … not by relaxing the v0.1 one".
- **(iii) No pre-release before M05 or 0.2.0.** This is M02's stated alternative.

If Frank chooses anything but the default, this specification is amended before the RC, and the gate refuses until
it is (§7.3 item 11).

---

## 4. Rules of judgement

T08 §3.3 applies unchanged:
- The vocabulary is `PASS`, `FAIL` and `BLOCKED`. `BLOCKED` is used **only** when the missing input is outside both
  lanes' authority.
- Judgement is clause-wise. A `FAIL` names its clause.
- Every gate is judged at the RC commit.
- No new tolerance is introduced.
- Numerical verification, empirical validation and optimality are kept distinct.

Four additions:

1. **D3 is per release.** A V or W `FAIL` is releasable only if ADR 0028's D3 table lists its clause with Frank's
   acceptance **dated on or after the alpha verdict's `Judged` date**. ADR 0021's acceptance of V14 (b) (2026-09-29)
   covered V14 (b) as judged at `67c66d9` for v0.1. It is not read for `0.2.0a1`. An acceptance recorded before the
   evidence would be the "PASS with waiver" ADR 0021 rejects.
2. **Moved records have counterparts.** A v0.1 record that v0.2 moved on purpose (§5.2) stays as released, at the tags
   `v0.1.0` and `v0.1.1`. At `C_α` its counterpart is judged in its place, and the counterpart is at least as strict:
   every quantity the old record fixed is fixed by the new one, or is derived from it by a registered decomposition.
3. **Evidence about another commit reaches `C_α` only through the RC job.** This covers M01's and M02's manifests and
   T08's records alike (ADR 0021 D1).
4. **Unmeasured is stated, never omitted.** An aspect the RC does not measure is a limitation row of the alpha
   envelope and is named in the notes. The aarch64 reactor run is the known one (Q1). The RC record cannot carry it:
   T08 Ruling 3's grammar fails any row that reads "not measured" (FD-α8).

---

## 5. V11–V20 at `C_α`

### 5.1 Criteria carried unchanged

| Gate | Criterion | Evidence at `C_α` (RC step, §8.2) | Moved record (§5.2) |
| --- | --- | --- | --- |
| V11 | T08 §4.1 | step 1 (K06, T01, T06, T07 nodes; T08.A10; T08.A35) | MR-10 |
| V12 | T08 §4.2 | step 1 (T05, T05b, build-first B10–B19) | — |
| V13 | T08 §4.3 and T08.A71 | step 1 (T01, T02, K03, B40–B49) | MR-7 (B50) |
| V14 | T08 §4.4 and T08.A70 | step 1 (T04, T02, B20–B25 nodes; T08.A33) | MR-8 (D3 per release) |
| V15 | T08 §4.5 | step 1; the certificate schema's `NOT_ASSESSED` uniqueness claims | — |
| V16 | T08 §4.6 | step 7 (T08.A48) | — |
| V17 | T08 §4.7 | step 8 | MR-1, MR-2, MR-6 |
| V18 | T08 §4.8 | step 1 (T08.A31–A33); step 9 (T08.A30); step 10 (T08.A34) | MR-11, MR-12 |
| V19 | T08 §4.9 | the dossier, ADR 0022 and `benchmarks/t08/v19/` at `C_α` | — |
| V20 | T08 §4.10 | step 1 (T08.A10); step 6 (T08.A46); step 7 (T08.A47) | — |

**Unchanged assertions.** T08.A10–A19, A20–A24 (under R-193's working-envelope rule), A30–A35, A40–A48, A60–A65 and
A70–A71 are carried as T08 states them, each as amended there. T08.A32 is carried as M01 spec §3.5 amends it for real
component records. Each is re-run at `C_α` by the step named above. T08.A40 requires `requirements.lock` to hash to
`ead4edf1…`. It is unchanged on `main`, `wp/M02` and `wp/M03` today (generator claim L1). A lock edit before `C_α`
fails A40, and it is not a moved record.

**V12's denominator** is §14.3's unit list (T08 §4.2). The C1 models M02 adds (`c1.*`) are W21's and W22's evidence, not
V12's. They enter the envelope's `unit_models` axis (T08.A20) without changing V12's list.

### 5.2 The moved records and their counterparts

| MR | Record (v0.1) | Why it moved | Counterpart at `C_α` | Checked by |
| --- | --- | --- | --- | --- |
| MR-1 | T08.A49's descriptions digest `171dd768…` (R-133, R-137) | R-192 (ADR 0019 A3.2: `diff_revisions`'s `outputSchema` gains `elements`) → `6c4375b4…`; R-234 (M02's additive schema members) → M02's served digest | the **surface chain** of §5.3: the digest served at `C_α` decomposes, one registered link at a time, to `171dd768…` and then to `v17-c2`'s `6d13e13d…`; the 17 description texts are byte-identical to R-133's | M07a.A37 |
| MR-2 | T08 §4.7's carry of V17 from `c7bbc98` | the surface differs from R-133's, so V17 is `BLOCKED` pending Frank (T08 §4.7, F5) | Frank's `V17 carry` row in ADR 0028, naming every link of the chain | M07a.A05; the V17 verdict |
| MR-3 | the envelope `v0.1-envelope-1`, release `0.1.0` (as released at `v0.1.1`) | R-193: the file is v0.2's working envelope `v0.2-envelope-dev`, release `0.2.0.dev0` | at `C_α`, `envelope_id: v0.2-alpha-envelope-1` and `release: 0.2.0a1`, equal to the version being cut (R-193's watch-for); T08.A20–A24 at `C_α`; the harvest covers every manifest at `C_α`, **T08's included** (R8 4, milestone 0 F3) | M07a.A10, A50 |
| MR-4 | the v0.1.0 notes' limitation list, checked against v0.1's envelope as released (R-216; R-217's amendment and merge note) | v0.2's rows (L42, L-WEB-1…4, and later ones) are not v0.1.0's | the `## v0.2.0a1` section names exactly the alpha envelope's `limitations` ids, in order, L42 and L-WEB-1…4 among them | M07a.A52 |
| MR-5 | the v0.1.0 review table and the 18-manifest harvest size (R-217) | scoped to P, K and T | the `## v0.2.0a1` review table has one row per package with a manifest at the candidate, with that manifest's `status` (the manifest at the latest committer time when there are several); the harvest's size at `C_α` (manifests, limitations, non-pass checks) is quoted in M07a's manifest and held equal by a test | M07a.A50, A52 |
| MR-6 | T08.A49 (step 8: digest, schemas, G16-b) | MR-1; `scripts/t08_rc.py`'s A49 constant is a 0.1 record and is not edited (R-192, M02 B1) | M07a.A37 replaces step 8: the chain (which also carries A49's request/response-schema clause, as T08 read it, through the last link), and G16-b 40/40 against `t07_reference_t08.json`, unchanged. The 0.1 row `a49.descriptions_digest_r133` is not a row of the alpha's RC record. Its endpoint `171dd768…` is asserted inside the chain, so nothing it fixed is released. | M07a.A37 |
| MR-7 | T08.B50 (R-134, R-144): digest `171dd768…`, the schemas of `c7bbc98`, and the content differences exactly `syn001.kinetic_cstr`, `T08-ptc-v1`, `T08-warm-v1` | the digest and the schemas as MR-1; the content moves when M02 adds `c1.*` models to `list_models` (FD-α4) | digest and schemas by the chain, under the same carry (MR-2). Content: the differences from `c7bbc98`, excluding `server.package_version`, are exactly B50's named entries plus the v0.2 additions named by register entries (each `list_models` id and `solve_policies` id). Frank's F5 ruling of 2026-09-29 ("content-only additions keep V17's carry") covers them. An unnamed addition fails. | M07a.A51 |
| MR-8 | ADR 0021 D3's acceptance of V14 (b) (2026-09-29) | D3 is per release | ADR 0028's D3 table: V14 (b) with Frank's acceptance dated on or after the alpha's `Judged` date | M07a.A04 |
| MR-9 | the v0.1.0 notes' gate table, tested against the **live** ledger and `T08-verdicts.md` | the alpha writes V and W verdicts into the same ledger rows (FD-α5) | the test reads the ledger and `T08-verdicts.md` as v0.1.0 released them (`PUBLIC_ROOT`, R-216's pattern); `## v0.2.0a1`'s table is `v0_2_gate.py --markdown`'s | M07a.A53, A52 |
| MR-10 | V11 (e): T08.A35, a real **v0.0.0**-emitted bundle | v0.1.0 was released and schemas changed after it under ADRs (ADR 0019 Amendment 3; ADR 0033–0035), so by T08 §4.1's own reasoning the clause now also applies to a v0.1.x-emitted instance | T08.A35 unchanged, **and** M07a.A42: the `SYN-001-nominal` bundle written by the CLI at tag `v0.1.1` gets a typed report from `C_α`'s `replay`, `inspect` renders it, and no exception is unhandled | M07a.A42 |
| MR-11 | T08.A34 over "every certificate the RC job emits" (steps 4–7) | the RC job now also emits coupled-route certificates (step 12) | the same rule over steps 4–7 **and** 12 | M07a.A39 |
| MR-12 | T08.A30's scope: the default install and the `server` extra | M03 may declare an `nlp` extra (Q6) | the default install and `server` (unchanged); and every extra that `C_α` declares and `v0.1.1` did not, through its own [A10] audit and Frank's recorded licence decision (M03's: `docs/m03-ipopt-audit.md` and M03 N1). Otherwise V18 (a) is `FAIL`. | M07a.A38 |

**MR-3, after the tag.** The first commit on `main` after the tag that changes a D2.4 path returns the envelope to
R-193's working form (`v0.2-envelope-dev`, `0.2.0.dev0`). The tag `v0.2.0a1` keeps the pinned file. After `C_α`, M07a's
own manifest is excluded from the harvest (`HARVEST_EXCLUDED = ("evidence/M07a/",)`), exactly as T08's was: it is
written after `C_α`, and it is the next harvest's.

### 5.3 The surface chain (MR-1, MR-6)

**Notation.**
- `T(C)` is the MCP tool list served at `C`.
- `d(·)` is its digest, by `benchmarks/t07/v17/harness.py`'s `tool_descriptions_sha256` rule: SHA-256 of the canonical
  JSON of every tool's `model_dump(exclude_none=True)`, covering names, descriptions, `inputSchema` and `outputSchema`.

**The links.** The surface changes registered since R-133, in the order they were introduced, are links `c_1 … c_m`.
Today m = 2:

| Link | Register | What it adds | Digest after it |
| --- | --- | --- | --- |
| c_1 | R-192 | `elements`: required member of `diff_revisions`'s `outputSchema` (ADR 0019 A3.2) | `6c4375b478d71c12b1211c17fafe7e58e9dfc0a05e11def2106799a6917631c9` |
| c_2 | R-234 | M02's enum values, branches, members and `$defs` (M02 note §14 B1) | registered at M02's merge into `main` |

Each link k has a registered strip function `s_k` that removes exactly what `c_k` added, and a registered digest `D_k`
after it. `D_0` = `171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14` (R-133).

**The chain holds at `C_α` iff all five hold:**
1. `d(T(C_α)) = D_m`.
2. `d(s_k(s_{k+1}(… s_m(T(C_α))))) = D_{k−1}` for k = m … 1, each strip applied to the **previous strip's output**. Two
   separate strips of the served list do not satisfy this. Today's `_without_a3_2`, applied to `T(C)` directly, stops
   giving `D_0` once M02 is merged.
3. With every link stripped, serving `v17-c2`'s `validate.md` and `commit_change.md` in place of the served two gives
   `6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d` (R-137).
4. The MCP tools at `C_α` are exactly the 17 of `V17_C2_FILE_SHA256`. Each description file's SHA-256 equals that table's
   value, except `validate` and `commit_change`, whose files equal R-133's. T08.A18 is therefore not reopened.
5. **Negative controls** (test states):
   - (i) a member added to another tool's `outputSchema` → the chain fails at link m, naming it;
   - (ii) `s_m` made to strip one member too many → it fails at m;
   - (iii) one byte of a non-N1/N2 description changed → item 4 fails;
   - (iv) `elements` left in place → it fails at link 1.

**A new MCP-visible change before `C_α`** (a schema edit by M03 or M04) is a new link c_{m+1}. It needs a register
entry, a strip function, a registered digest, and Frank's carry extended to name it. Without all four the chain fails
and V17 is `BLOCKED`.

### 5.4 Clause labels for V12, V16 and V17

T08 §4 letters the clauses of V11, V13–V15 and V18–V20. For a FAIL or BLOCKED row at `C_α`, the alpha's verdict
document also uses the labels below. They are labels only; no criterion changes.

- **V12 (a)**: every model of §14.3's list has, at `C`, the definition of done of T08 §4.2's rule.
- **V16 (a)**: at least 30 distinct cases. **V16 (b)**: eight shared-model comparisons. **V16 (c)**: at least two by
  both tools where feasible. **V16 (d)**: the registered ensemble. T08 §4.6's rule is "T06 verdict 1 stands and
  T08.A48 passes".
- **V17 (a)**: the agent surface at `C` is one to which Frank has carried `v17-c2`'s evidence, and M07a.A37's chain
  holds. **V17 (b)**: G16-b's ten scripted reference solutions are clean on 40 of 40 runs over Python, CLI, HTTP and
  MCP at `C`.

---

## 6. W21 and W22

Both are judged by the `verdict` agent at `C_α`, from the inputs of §6.3. A clause is `met` only when every listed
item holds at `C_α`. The gate is `PASS` iff every clause is met.

### 6.1 W21 — "PyMRM adapter with port mapping, accuracy contract, out-of-process execution policy, timeout, provenance, and parent-model validation" (blueprint §14.4 bullet 1)

The ids are M01 spec §9 (`M01.Ann`) and M02 note §10 (`Gn`). "Step" refers to §8.2.

**W21 (a) — Port mapping.** The reactor's ports, degrees of freedom and unit mapping (M01 §8.2–8.3; ADR 0027) are
implemented and checked.
- M01.A25–A32 and A49–A51 at step 1. These run on the stand-in path.
- M01.A52's record half: mapping 1 ulp, against a bound of 2.
- G4 (e)–(g), G8 (a)–(e) and G9 (b) at step 1.
- G10 (h) at step 12: the full boundary at N_tubes = 1 is within 10⁻⁶ of the record.

**W21 (b) — Accuracy contract.** The real variant declares its precision floor, ε_eval = 10⁻⁶ relative, and the
design grid's discretization estimate (M02 D7). Every `ok` result carries both: G10 (i) at step 12.

The variant's own figures hold at step 12:

| Item | Bound | Recorded |
| --- | --- | --- |
| G10 (b), path independence | ≤ 10⁻⁶ | 1.56 × 10⁻⁸ |
| G10 (e), element defect | ≤ 10⁻⁷ | 2.98 × 10⁻⁸ (M01.A45 record half) |
| G10 (f), \|ΔP\|/P_in | ≤ 10⁻³ | 4.90–5.06 × 10⁻⁵ |
| G12, the real loop's floor ratios | ≥ 10 | — |

M01 §10's grid study (M01.A48's record half) holds.

**W21 (c) — Out-of-process execution policy.** The profile is `external-subprocess-v1` (ADR 0033 D1–D2).
- G3 (a)–(h) at step 1, on Linux.
- G4 (a)–(i) and G5 at step 1.
- The support matrix states the profile, "not a sandbox", Linux as the registered platform, and Windows refused.
- M02 N1 accepted by Frank in ADR 0028's decisions table. This is a precondition, not a default, because the alpha
  publishes the profile.

**W21 (d) — Timeout.**
- G3 (b) at step 1: `timed_out` is recorded within 3.5 s of spawn under `timeout_s = 1`, and there is no retry.
- The per-attempt timeout in force at `C_α` is the one M02 §5.2 registers.
- G11 (d)'s `startup_s` and `solve_s`, measured at step 12, are recorded beside it.

No new ratio is introduced. A timeout that the measured attempt exceeds makes G12 fail, and that fails W21.

**W21 (e) — Provenance.**
- G6 (a)–(c) at step 1.
- Every experiment result record that step 12 writes carries blueprint §9.1's six items, in the fields of
  `experiment.schema.json` (ADR 0033): the boundary mapping; the version (the variant id and SHA-256, and the reactor
  commit); the discretization settings (num_z and the estimate); the convergence evidence (stage and certificate); the
  conserved fluxes (element defects); and the cost (wall time).
- G10 (g) at step 12: M01.A47 (a) bitwise, or the finding naming both CPU models with (h) deciding (R-200).
- G12's `reproduce` returns `MATCH` from the record.
- The reactor commit in the real variant equals ADR 0022's pin, `6089593464fc9bc2c0a0cb58e30ad5433ece6332`.
- The reactor and its data are used by reference under the dossier's rights table (T08.A64; ADR 0006 mode A). The
  wheel carries the reactor environment's lock and no code of the group's.

**W21 (f) — Parent-model validation**, read as decided in ADR 0028 D7. The PyMRM reactor is the parent model of v0.2's
surrogates (blueprint §9.1–9.2). Its validation evidence is carried by the adapter and stated, not re-made. The clause
is met iff all four hold:
- **(f1)** The parent model run through the adapter reproduces the parent model run standalone: G10 (g) bitwise or,
  failing that, (h) within 10⁻⁶ (M01.A47), at step 12.
- **(f2)** The parent model's own regression reference at the pin is reproduced: T08.A61 (the group's suite at
  `6089593`: 69 passed, 0 failed, 3 skips counted *not reproduced*), at the pin the variant names.
- **(f3)** The parent model's numerical error is evidenced and carried with every result: M01 §10 (A48's record half,
  the discretization estimate DX-01, path independence) and G10 (i).
- **(f4)** Its empirical validation is cited, not re-judged. The verdict and the notes say four things:
  - the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's rate
    law; dossier H2, R-143) is the group's evidence;
  - this project has compared no reactor result with data;
  - the numbers are the group's model at the pin, a regression;
  - their discretization bias is 1.0–1.4 % in NH₃ (M02 §13).

*The stronger reading, rejected as the default (F-α4).* "Parent-model validation" would mean that this project
compares reactor results with experimental data. That is validation of the reactor's physics. Blueprint §9.1 keeps
high-fidelity model discrepancy as separate evidence, and M07's "truth checks" own it. The 4TU dataset's use also
awaits Frank's rights statement (T08 R3 8 (b)). Under that reading W21 (f) would be `BLOCKED` on the statement.

**W21 does not establish:**
- that the reactor is right: every real-reactor number is the group's model at the pin, a regression, with F-R2, F-R3
  and its discretization bias;
- bitwise reproduction across machines, or any run on aarch64, which is not measured (Q1);
- a sandbox, Windows support, or concurrency across hosts or on network filesystems;
- sensitivities through the reactor, or optimization;
- the convergence of coupled loops in general;
- that the stand-in certifies anything about the reactor (R-199).

### 6.2 W22 — "One additional validated nonideal property route sufficient for the selected chemistry" (blueprint §14.4 bullet 2; R-160; M01 spec §11)

**W22 (a) — Numerical verification.**
- M01.A05–A22 pass at step 1. Their expectations come from closed forms (`m01_reference.py`), independent of the
  implementation.
- M01.A34 (`m01_reference.py --check`) passes at step 1.

**W22 (b) — Conformance with an independent implementation of the same method.**
- M01.A37 at step 1: `pr-c1-v1` at `C_α` against the committed IDAES 2.13 record.
- Step 11: re-running `idaes_conformance.py` in the IDAES environment gives numbers identical to
  `benchmarks/m01/idaes-conformance.json`. Only `inputs.*_sha256` members may differ, and each that does is listed
  (M01's manifest records `inputs.reference_values_yaml_sha256` and gives the reason).

**W22 (c) — Empirical validation of the pure-component behaviour that drives the loop**, against the reference
equations of state. The bands are validation bands (R-160), the design lane's fitness statement. They are not
numerical tolerances.

| Assertion | Quantity | Measured | Band | Band ÷ measured |
| --- | --- | --- | --- | --- |
| M01.A38 | max \|P_sat,PR/P_sat,ref − 1\|, 240–320 K | 0.012675 | 0.02 | 1.58 |
| M01.A39 | max \|Δ ln φ^L\|, NH₃ at the separator states | 0.040096 | 0.05 | 1.25 |
| M01.A40 | max \|Δ ln φ^V\|, light gases and NH₃ vapour | 0.042371 | 0.05 | 1.18 |

The table is generator claims M1–M3. Step 11 re-derives these values at `C_α` with
`external_crosscheck.py --check` (exit 0).

The provider at `C_α` equals the closed form within A05–A22's tolerances, 10⁻⁹–10⁻¹⁴ (W22 (a); M01 §9.8), and the
closed form is what the bands compare. So the route validated is the provider that `C_α` ships.

The verdict quotes the three ratios. It does not turn them into a confidence statement.

**W22 (d) — Sufficient for the selected chemistry.** The C1 loop binds every property evaluation to `pr-c1-v1` and
solves to `VERIFIED`:
- G7 (a)–(e) and G8 (a)–(c) at step 1;
- G12 at step 12.

The gaps the route leaves are stated:
- the LIQUID regime and pure-NH₃ flashes are deferred and refused typed (M02 N5);
- dissolved light gases are not represented (R-143);
- k_ij = 0, with its effect stated (R-157);
- there is no mixture VLE validation (R-160);
- PR's saturated-liquid volume is 11–30 % high and its enthalpy of vaporization 2–5 % high (M01 §11). No loop decision
  in v0.2 uses either.

**W22 does not establish:**
- mixture VLE;
- the effect of k_ij beyond R-157's statement;
- the near-critical region;
- liquid-density fitness;
- any claim outside the five C1 components and the domain M01 registers.

### 6.3 The verdict procedure

**Who and when.** One `verdict` agent, after the RC record is complete (§8.3) and M07a's manifest is `tested`. It
judges V11–V20, W21 and W22 together, at `C_α`. It does not judge W23–W27.

**Its brief must paste:**
- the RC record's step table, with every record's path and SHA-256;
- the M01 manifest (`evidence/M01/3c80392…`) and the M02 manifest (at M02's `tested` commit), their checks and
  limitations;
- §5 and §6 of this specification;
- T08 §4;
- ADR 0028's tables as they stand.

**Output.** `docs/reviews/V02-alpha-verdicts.md`, in T08 Amendment R3 §R3.3's form, with three differences:
- The header line is `**Release candidate:** \`<C_α, 40 hex>\`   **Judged:** <YYYY-MM-DD>   **By:** design lane (\`verdict\`)`.
- There is exactly one table with a `Verdict` header: `Gate | Verdict | Failing clauses | Travelling limitations |
  Basis`, with twelve rows, `V11` … `V20`, `W21`, `W22`, in that order.
- Clauses are written `Gnn (x)` with §4's, §5.4's and §6's labels. Limitation ids come from the alpha envelope.

Below the table there is one section per gate. Each section judges every clause met, not met or blocked, gives its
evidence at `C_α`, and states what the verdict does not establish. For W21 and W22 that is at least the lists of
§6.1–§6.2.

**Rules.**
- A V or W verdict that differs from v0.1's at `67c66d9` says why in its section.
- The verdict never sets `reviewed`.
- It never moves a tolerance, a band or a classification rule.

---

## 7. The gate script `scripts/v0_2_gate.py`

### 7.1 The version line and the registered gate sets

`release.yml` resolves the gate script from the version's release segment: `scripts/v<major>_<minor>_gate.py`, so
`0.2.0a1` resolves to `scripts/v0_2_gate.py`. That script holds a registry of gate sets, each covering the versions its
pattern fullmatches.

The only entry is `v0.2-alpha-gate-v1`, with pattern `0\.2\.0a[1-9][0-9]*`. This is PEP 440's canonical alpha form, so
setuptools writes it unchanged into METADATA and the file names (Q2).

A version that no registered set covers is refused, with the reason "version V is not covered by a registered v0.2
gate set", and exit 1. This includes `0.2.0`, `0.2.0bN` and `0.2.0rcN`. M07 adds `v0.2-gate-v1` for them.
`scripts/v0_1_gate.py` keeps covering the 0.1 line and nothing else (R-151).

**Table T1 — the gate set's coverage**

| Version | Covered by v0.2-alpha-gate-v1 |
| --- | --- |
| `0.2.0a1` | yes |
| `0.2.0a2` | yes |
| `0.2.0a10` | yes |
| `0.2.0a0` | no |
| `0.2.0a01` | no |
| `0.2.0` | no |
| `0.2.0b1` | no |
| `0.2.0rc1` | no |
| `0.2.0a1.dev1` | no |
| `0.2.0a1.post1` | no |
| `0.2.0.dev0` | no |
| `0.2.0alpha1` | no |
| `0.2.0A1` | no |
| `0.2.0-a1` | no |
| `0.2.1a1` | no |
| `0.1.1` | no |
| `0.1.0rc1` | no |
| `1.2.0a1` | no |

### 7.2 Inputs

Every input is read **at the candidate commit**, with `git show <candidate>:<path>`, not from the working tree. This
departs from `v0_1_gate.py`, which reads the working tree. In `release.yml` the two coincide, but locally only the
commit is unambiguous.

1. **The ledger.** `docs/requirements.yaml`, `gates[V11…V20, W21…W27].verdict`.
2. **The verdict document.** `docs/reviews/V02-alpha-verdicts.md`, read by column under §6.3's form.
   - The header names `C` once, as `` **Release candidate:** `<40 hex>` ``, and that commit must equal `--rc`.
   - `**Judged:** YYYY-MM-DD` is read as the judged date.
   - These are malformed, exit 2:
     - a clause outside its column;
     - a gate out of order;
     - a W23–W27 row;
     - a second `Verdict` table;
     - a header naming another `C`;
     - no `Judged` date.
   - Clause grammar: `\b(?:V(?:1[1-9]|20)|W2[12]) \([a-z0-9]+\)`. Limitation ids: `\bL(?:\d{2}|-[A-Z]+-\d+)\b`, each of
     which must exist in the candidate's envelope.
3. **ADR 0028.** `docs/adr/0028-v0.2-pre-release-policy.md` has two tables, and only this ADR is read: ADR 0021 is not
   an input.
   - **The D3 table** has a header column `Frank's acceptance`, and each row's first cell is a clause. A row counts iff
     its acceptance cell passes the cell rule below **and** its date is on or after the judged date.
   - **The decisions table** has a header column `Frank's answer`, and its rows are `N3`, `V17 carry` and `M02 N1`.
     Each of the three must pass the cell rule **and** its date must be on or after the judged date, so an answer
     given for one release is not read for a later one. Table T6 fixes the date rule for both tables. *(amended
     2026-10-09, Amendment 1 (review) F2)*
   - **The cell rule.** Remove `*` and backticks from the cell and strip it. Lower-cased, it must match
     `^accepted[\s,;:]*(\d{4}-\d{2}-\d{2})(?![0-9])` at its start, so the date comes right after the word, and that
     date must be a calendar date. It is the acceptance date. Table T4 fixes the rule. *(amended 2026-10-09,
     Amendment 1 (review) F1)*
4. **The RC record.** `docs/v02-alpha-rc-record.md`, read by `v0_1_gate.py`'s RC-record grammar unchanged (T08 review
   3, Ruling 3).
   - It names `C` once, as `` `C` = `<40 hex>` ``.
   - It has one per-step table whose headers begin `Step | Assertion` and include a `Result…` column.
   - Steps 1–12 must each have a row that passed, and none that failed or is not stated as passed. Step 13 is the gate
     itself and is not required.
5. **The manifests.**
   - `evidence/M07a/<C>/manifest.json`: `work_package` `M07a`, `commit` `C`, `status` `tested` or `reviewed`.
   - For each of M01 and M02, at least one `evidence/<P>/<c>/manifest.json` with `status` `tested` or `reviewed` whose
     commit `c` is an ancestor of `C` or equal to it (`git merge-base --is-ancestor`).
6. **The envelope.** `benchmarks/t08/support_envelope.yaml` at the candidate: `envelope_id` = `v0.2-alpha-envelope-1`
   and `release` = the candidate's version.
7. **The required ADRs.** 0022, 0026, 0027, 0028, 0033, 0034 and 0035 (M02's three, by the numbers M02 merges with).
   The first line of each that starts `**Status:**`, with `*` removed and stripped, must start `Status: Accepted`.
   Table T5 fixes the rule. A missing file fails.
8. **`C`.** `--rc` resolves through git, or else through a unique prefix of a record in `release/rc-trees/` (R-151,
   unchanged). `C`'s version is read from git, or from the record's `version`.

**Table T4 — Frank's cell rule** *(three `no` rows added 2026-10-09, Amendment 1 (review) F1)*

| Cell (as written) | Counts as Frank's acceptance |
| --- | --- |
| `accepted, 2026-10-12 ("go")` | yes |
| `Accepted 2026-10-12` | yes |
| `**accepted**, 2026-10-12` | yes |
| `pending` | no |
| `accepted` | no |
| `alternative (i), 2026-10-12` | no |
| `not accepted, 2026-10-12` | no |
| `2026-10-12, accepted` | no |
| `accepted (i), 2026-10-12` | no |
| `accepted alternative (ii), 2026-10-12` | no |
| `accepted, 2026-10-123` | no |

**Table T5 — the ADR status rule**

| Status line (as written) | Accepted |
| --- | --- |
| `**Status:** **Accepted, 2026-10-02**, with its Proposed revision 1` | yes |
| `**Status:** **Accepted**, 2026-10-08 — on M01 tested` | yes |
| `**Status:** Accepted` | yes |
| `**Status:** Proposed, 2026-10-08; amended before acceptance by Amendment 1 (2026-10-08, below), and still Proposed.` | no |
| `**Status:** Proposed; Accepted when M02 is tested` | no |

**Table T6 — Frank's answers against the verdict's `Judged` date** *(added 2026-10-09, Amendment 1 (review) F2)*

A D3 row and each decisions row count iff the cell passes Table T4's rule and its acceptance date is on or after
`Judged`.

| Cell (as written) | Judged | Counts |
| --- | --- | --- |
| `accepted, 2026-10-12` | `2026-10-12` | yes |
| `accepted, 2026-10-13` | `2026-10-12` | yes |
| `accepted, 2026-10-11` | `2026-10-12` | no |
| `accepted, 2026-10-12` | `2026-11-02` | no |
| `accepted (i), 2026-10-12` | `2026-10-12` | no |

### 7.3 Decision

A tag `v<version>` may be **proposed** to Frank iff every item below holds. The tag itself is Frank's (ADR 0021 D5).

1. **Coverage (§7.1).** The candidate's version is covered by a registered gate set. Its claimed gates are the set's
   claimed gates, here V11–V20, W21 and W22.
2. **Same version.** `C`'s version equals the candidate's (ADR 0028 D4).
3. **D2.1.** Every claimed gate has a verdict in the ledger, and the same verdict in the verdict document.
4. **D2.2.** No claimed gate is `BLOCKED`.
5. **D2.3.** Every `FAIL` names its clauses, and each clause is accepted in ADR 0028's D3 table (§7.2 item 3).
6. **D2.4.** The candidate's files under `src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`,
   `MANIFEST.in`, `README.md`, `LICENSE` and `NOTICE` equal `C`'s. The rule and the code path are `v0_1_gate.py`'s,
   including the one-occurrence version allowance, which item 2 makes moot. If `C` is absent, the comparison is made
   against `release/rc-trees/<C>.json` (R-151). The path list equals `v0_1_gate.TREES` (generator claim L3).
7. **D1, as §8.1 item 4.** The RC record of `C` shows steps 1–12 passed.
8. **§8.1 item 5.** M07a's manifest at `C` is `tested` or `reviewed`.
9. **The packages.** M01 and M02 have `tested` or `reviewed` manifests at ancestors of `C`.
10. **The envelope.** It is pinned as item 6 of §7.2 requires.
11. **Frank's answers.** `N3`, `V17 carry` and `M02 N1` each pass the cell rule. An answer that does not, including a
    chosen alternative, refuses with "Frank's answer to <item> is not an acceptance of the default; amend the alpha
    specification for it". Each is also dated on or after the verdict's `Judged` date (Table T6); an answer dated
    before it refuses, naming the item and both dates. *(amended 2026-10-09, Amendment 1 (review) F2)*
12. **The ADRs.** Every required ADR is Accepted.

**Exit codes.** Exit 0 iff a tag may be proposed. Exit 1 if it may not. Exit 2 if the verdict document is malformed or
`C` cannot be found.

**What is not checked.** Unclaimed gates are printed and never checked. A `FAIL` is printed `FAIL`, accepted or not.

### 7.4 `C_α` and R-151

`C_α` is a commit of the public repository (R-150). The gate reads it from git, and so does the M01/M02 ancestry
check.

`C_α` must stay reachable. The RC branch is merged into `main` with a merge commit, never squashed, and the tag
protects it after the release.

The RC procedure writes `release/rc-trees/<C_α>.json` (R-151's `--write-tree-record`, through `v0_2_gate.py`, whose
record format and `trees` list are `v0_1_gate.py`'s). The record has two uses:
- it is durable evidence of `C_α`'s distribution sources;
- the tree check falls back to it when `C_α` is absent.

With `C_α` absent, the ancestry check of §7.2 item 5 cannot run. The gate refuses with the reason "C is not in the
repository: the M01/M02 ancestry check needs it". A vanished `C_α` is a procedural defect, not a path to a YES.

### 7.5 Output

**Text output.**
- The first line is `v0.2 gates (v0.2-alpha-gate-v1) at C = <C>; candidate <commit>`.
- Then 17 gate rows: V11–V20, W21 and W22 with their verdict and notes, and W23–W27 as
  `not claimed (v0.2-alpha-gate-v1)`.
- Then one line each for: the tree check, the RC record, the manifests, the envelope, the ADRs, and Frank's answers.
- The last line is exactly `v<version> tag may be proposed: YES`, or `… NO (k reasons)`. `release.yml` greps for the
  YES line.

**Other modes.**
- `--json` gives the same content as JSON.
- `--markdown` prints the table `| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |`
  with 17 rows. W23–W27 read `not claimed` in the verdict column.
- `--write-tree-record --rc C` writes R-151's record.

**A version with no covering gate set** prints no gate rows, only the reason and the NO line.

---

## 8. The release candidate `C_α`

### 8.1 Definition

`C_α` is a commit on the RC branch, cut from `main` after M02's merge, such that:

1. **Tree.** The version in `pyproject.toml`, `src/openflowsheet/__init__.py` and the version-carrying test fixtures is
   `0.2.0a1`. The envelope is pinned (MR-3). `requirements.lock` hashes to `ead4edf1…` (T08.A40).
2. **Precondition packages.** M01's and M02's manifests are `tested`. ADR 0027, 0033, 0034 and 0035 are Accepted, by
   M02's acceptance evidence. The surface chain's links are registered (§5.3). B50's counterpart (MR-7) is in the
   gate.
3. **This specification's work orders are done** (§15, WO-1 to WO-9), and `check.sh` is green at `C_α`.
4. **The RC job** (§8.2) has completed at `C_α`, and its records are committed (§8.3).
5. **The documents exist:**
   - `evidence/M07a/<C_α>/manifest.json` with `status: tested`;
   - `docs/reviews/V02-alpha-verdicts.md`;
   - the ledger;
   - the `## v0.2.0a1` section of `CHANGELOG.md`;
   - ADR 0028's tables.
6. **Nothing outward** has been done: no tag, no publication.

### 8.2 The RC job

| Step | What | Where | Assertion |
| --- | --- | --- | --- |
| 1 | `scripts/check.sh` (T08.A41 at `C_α`): includes M01's in-gate assertions, M02's G1–G9, M06's tests, the chain, B50's counterpart, M07a.A42 | CI `ubuntu-latest` and `ubuntu-24.04-arm` | M07a.A30 |
| 2 | Identity (T08.A42 at `C_α`): the R-149 values; unchanged under the trial version `0.1.0` | both architectures; CI `identity` | M07a.A31 |
| 3 | sdist and wheel twice (T08.A43 at `C_α`); `Version` `0.2.0a1` in METADATA and the file names | CI | M07a.A32 |
| 4 | Clean install and the lock lookup (T08.A44, A19 at `C_α`) | fresh runners of both architectures | M07a.A33 |
| 5 | The RC bundle set (T08.A45 at `C_α`) | CI x86-64 writes; fresh x86-64 and aarch64 replay | M07a.A34 |
| 6 | The registered ensemble and T06 A34's same-class replay (T08.A46 at `C_α`) | `ref-x86-64` locally; `ci-aarch64` by dispatch | M07a.A35 |
| 7 | Adversarial, invalid-structure and reference subsets (T08.A47, A48 at `C_α`) | three hosts | M07a.A36 |
| 8 | The surface chain (§5.3) and G16-b 40/40 (replaces T08.A49) | three hosts | M07a.A37 |
| 9 | The [A10] inventory (T08.A30 at `C_α`; MR-12) | both architectures | M07a.A38 |
| 10 | Certificates of steps 4–7 and 12 (T08.A34 at `C_α`; MR-11) | where they were emitted | M07a.A39 |
| 11 | W22's external records: `external_crosscheck.py --check`; the IDAES conformance re-run | `ref-x86-64`, in their pinned environments | M07a.A40 |
| 12 | W21's reactor evidence: M02 G10 (a)–(i), G11 (a)–(d), G12 at `C_α` | `ref-x86-64`, in the reactor environment built from `C_α`'s lock | M07a.A41 |
| 13 | `scripts/v0_2_gate.py --rc C_α` | local | M07a.A12 |

**How the steps run.**
- Steps 1–10 run `scripts/t08_rc.py`'s subcommands unchanged, except step 8. Their registered constants are still
  right at `C_α`: the lock, the K05 identity (M02 G2 keeps it), the trial version, the bundle sets and the ensemble.
- Step 8 is a new `surface` step that implements §5.3 (WO-5). `scripts/t08_rc.py`'s A49 constants are not edited
  (R-192).
- CI runs steps 1–10 through a new dispatch input that selects the alpha's step 8 (WO-5). The 0.1 `rc` input is left
  as it is.

### 8.3 Records

**Where they go.** As T08 §8.1 item 4, with R7 1 and R8 1:
- small text records under `evidence/M07a/<C_α>/rc/`;
- large records under `evidence/M07a/<C_α>/artifacts/`, by hash, with records over 1 MB committed gzip-compressed beside
  their paths;
- `rc/records.json` listing every cited record with its SHA-256, its size, and whether it is committed.

**What every record carries.** `commit` = `C_α`, `tree_clean: true`, the lock's SHA-256, and the machine class
(T08.A16 at `C_α`; M07a.A43).

**The RC record.** `docs/v02-alpha-rc-record.md` follows `docs/t08-rc-record.md`'s form:
- it names `C_α` once;
- it has one per-step table, `Step | Assertion | Where | Result (as the record says) | Record | sha256`, with at least
  one row per step 1–12;
- the `Result` cells use the status words of Ruling 3.

`release/rc-trees/<C_α>.json` is written at `C_α` (M07a.A44).

---

## 9. Release mechanics and Frank's dispatch

### 9.1 What changes, and what does not

**`release.yml`'s version step** accepts canonical PEP 440 final versions and pre-releases:
`^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)((a|b|rc)[1-9][0-9]*)?$` (Table T2).

**Unchanged in `release.yml`:**
- the gate-resolution line (major and minor from the release segment);
- the YES-line grep;
- the dry-run default;
- the `rc` input's default, `67c66d9`, which belongs to the 0.1 line. For the alpha, Frank passes `rc` = `C_α`. A
  forgotten `rc` fails closed, because `C`'s version `0.1.0rc1` is not the candidate's (§7.3 item 2).

**`github-release`** passes `--prerelease` iff the version has an `a`, `b` or `rc` segment.

**`scripts/changelog_section.py`** accepts tags `v` + the same form (Table T3). It keeps the heading rule ("`## <tag>`
followed by the end of the line or a space"), which already keeps `## v0.2.0a10` apart from `v0.2.0a1`.

**`docs/RELEASING.md`** gains a "Pre-releases" section: the alpha's preparation, its `rc` input, the freeze (Q7), and
the GitHub pre-release flag. Its sentence "a `0.2.x` release needs a `scripts/v0_2_gate.py` and its own release
candidate" stays true.

**Table T2 — `release.yml`'s version step**

| Version input | release.yml accepts it |
| --- | --- |
| `0.1.1` | yes |
| `0.2.0` | yes |
| `0.2.0a1` | yes |
| `0.2.0b2` | yes |
| `0.2.0rc1` | yes |
| `1.0.0` | yes |
| `10.20.30rc12` | yes |
| `v0.2.0a1` | no |
| `0.2.0a0` | no |
| `0.2.0rc0` | no |
| `0.2.0a01` | no |
| `0.2.0.dev0` | no |
| `0.2.0a1.post1` | no |
| `0.2.0-a1` | no |
| `0.2.0A1` | no |
| `0.2.0alpha1` | no |
| `0.2` | no |
| `01.2.0` | no |

**Table T3 — `changelog_section.py`**

| Tag | Heading line | Is the tag's section |
| --- | --- | --- |
| `v0.2.0a1` | `## v0.2.0a1` | yes |
| `v0.2.0a1` | `## v0.2.0a1 — release candidate C = 0123abc` | yes |
| `v0.2.0a1` | `## v0.2.0a10 — later` | no |
| `v0.2.0a1` | `## v0.2.0 — unreleased` | no |
| `v0.2.0` | `## v0.2.0a1 — release candidate C = 0123abc` | no |
| `v0.2.0` | `## v0.2.0 — unreleased` | yes |
| `v0.1.1` | `## v0.1.1 — the single public repository` | yes |

The tags `v0.2.0a0`, `v0.2.0.dev0` and `0.2.0a1` are refused as malformed (exit 2).

### 9.2 The procedure

1. **The build lane** completes WO-1 to WO-9 on `wp/M07a`, from `main` after M02's merge, and has them reviewed (§15).
2. **Cut `C_α`** (§8.1 items 1–3). From then until the dispatch, `main` takes no change to a D2.4 path (Q7's default).
   Work continues on branches.
3. **The RC job** runs at `C_α` (§8.2). Its records and the RC record are committed on `wp/M07a` after `C_α`, outside
   the D2.4 paths.
4. **The manifest** `evidence/M07a/<C_α>/manifest.json` is written with `status: tested` iff M07a.A00–A53 pass at
   `C_α`.
5. **The verdicts.** The `verdict` agent writes the verdict document (§6.3). The build lane writes the ledger
   (M07a.A64) and the `## v0.2.0a1` section (M07a.A52), then runs `v0_2_gate.py --markdown`.
6. **Frank's answers.** Frank records them in ADR 0028's two tables. Each of the four, V14 (b) and the three
   decisions, is dated on or after `Judged`. *(amended 2026-10-09, Amendment 1 (review) F2)* ADR 0028 is marked Accepted.
7. **The local gate.** `PYTHONPATH=src .venv/bin/python scripts/v0_2_gate.py --rc <C_α>` ends
   `v0.2.0a1 tag may be proposed: YES`. Then `wp/M07a` is merged into `main` with a merge commit. The candidate is
   `main`'s head, whose D2.4 paths equal `C_α`'s.
8. **Frank's release.** Frank opens Actions → **release** → Run workflow, from `main`, with `version` `0.2.0a1`, `rc`
   = `C_α`, and **dry_run ticked**. He inspects `release-record` and `dist`. He runs it again unticked, and approves
   `pypi`. The GitHub release is created marked pre-release.
9. **After the tag.** The freeze ends, and the envelope returns to its working form (MR-3).

### 9.3 What the lanes may do, and what is Frank's

**The lanes may:**
- set `0.2.0a1` at `C_α`;
- build sdists and wheels locally and in CI, without publishing them;
- dispatch CI, including the ensemble (existing practice);
- run the reactor and the IDAES and cross-check environments locally;
- commit and merge with `status: tested`;
- write the CHANGELOG section;
- push `main` (authorized 2026-10-08).

**Frank's:**
- N3, the V14 (b) acceptance, the V17 carry and M02 N1, recorded in ADR 0028;
- the dispatch;
- the `pypi` approval, every publication, and the tag;
- any new agent campaign;
- any human review sign-off, in R-017's form.

---

## 10. Assertion catalogue

Tolerances:
- **exact** means equality of strings, integers, hashes or sets. No roundoff enters, and the smallest error worth
  catching is one character, one count or one hash.
- **registered** means that a float comparison reuses the tolerance its source registered, cited there with its
  argument. This specification registers none.

| ID | Subject and state(s) | Expected | Tolerance and why | Judged by |
| --- | --- | --- | --- | --- |
| M07a.A00 | `v02a_reference.py --check` | every claim of §11 passes; the committed YAML equals the regenerated bytes; this table's ids equal the generator's catalogue, unique and sorted; the RC step table and Tables T1–T6 equal the generator's | exact | generator |
| M07a.A01 | Version coverage: the 18 versions of Table T1, each as the candidate's version with an otherwise passing fixture | each `yes` row proposable; each `no` row exit 1 with "not covered by a registered v0.2 gate set" and no gate rows | exact. The boundary rows `a0`, `a01` and `a10` catch an off-by-one pattern; the `.dev` and `.post` rows catch a prefix match | test |
| M07a.A02 | `C`'s version against the candidate's: (i) both `0.2.0a1`; (ii) `C` = the committed record of `67c66d9` (`0.1.0rc1`) with candidate `0.2.0a1`; (iii) `C` at `0.2.0a1`, candidate at `0.2.0a2` | (i) passes this item; (ii) and (iii) refused, naming both versions | exact. (ii) is the forgotten-`rc` dispatch; (iii) is D2.4's version allowance, which the alpha does not use | test |
| M07a.A03 | The verdict document's form, with each §7.2 item 2 departure on a passing fixture: reordered or missing column; gate out of order; bold gate id; a clause or L id in `Basis`; a second Verdict table; a `W23` row; a header naming another `C`; no `Judged` date; `**Judged:**` twice *(Amendment 1 (review) F4)*; an unknown L id | the passing fixture parses; every departure is exit 2, except the unknown L id, which is exit 1 (a gate problem, as in v0.1) | exact. One state per rule, so a dropped rule fails its own state | test |
| M07a.A04 | D2.1–D2.3 with ADR 0028's D3 table: (a) all PASS; (b) V14 FAIL `V14 (b)` accepted, dated on the judged date; (c) the same dated the day before; (d) the same accepted only in an ADR 0021-shaped table; (e) an unlisted FAIL; (f) a BLOCKED W21; (g) ledger PASS against document FAIL for W22; (h) each acceptance cell of Table T4; *(Amendment 1 (review) F4)* (i) an accepted row whose first cell is a clause followed by prose; (j) two D3 tables; (k) a clause listed twice; (l) an acceptance dated `2026-02-30` | (a) and (b) proposable, (b) printing V14 `FAIL` with its acceptance; (c)–(g) and (i)–(l) refused, each naming its rule; (h) as Table T4 | exact. (c) catches a waiver dated before the evidence; (d) catches a v0.1 acceptance leaking into the alpha | test |
| M07a.A05 | Frank's decisions table: each of `N3`, `V17 carry` and `M02 N1` in turn `pending`, an alternative, missing, or accepted the day before `Judged` *(Amendment 1 (review) F2)*, with the other two accepted; two decisions tables; each item's row doubled; each answer dated `2026-02-30` *(Amendment 1 (review) F4)* | refused, naming that item; proposable only with all three accepted | exact. Three states, one per item, so a reader that checks one row only fails two of them | test |
| M07a.A06 | W23–W27 with ledger verdicts null, PASS, FAIL and BLOCKED (four fixtures) | printed `not claimed (v0.2-alpha-gate-v1)` in text and markdown; never a reason; never read from the verdict document | exact. The FAIL and BLOCKED fixtures catch an unclaimed gate that blocks; the PASS fixture catches one that is claimed | test |
| M07a.A07 | The tree check: T08.A50's and R-151's states (version-only change, pin edit, an edit, an addition, a removal, a mode change, a doubled version string; git against record at a scratch commit; `C` absent with and without its record) | the same answers as `v0_1_gate.py` gives on the same states; `TREES` and `VERSION_FILES` equal `v0_1_gate`'s | exact | test |
| M07a.A08 | The RC record: steps 1–12 each passed; step 7 failed; step 12 missing; step 12 present only as a `—` supporting row; step 13 failed; another `C`; a "not measured" step-12 row | proposable in the first and fifth cases (13 is not required); every other case refused, naming the step | exact. The step-12 cases catch a reader still bounded at v0.1's step 10 | test |
| M07a.A09 | Manifests: (a) M07a `tested` at `C`; (b) M07a missing, at another commit, or `implemented`; (c) M02's only manifest at a commit not an ancestor of `C`; (d) M01 `implemented` only; (e) `C` absent with its record present | (a) passes this item; (b)–(d) refused, naming the package; (e) refused with §7.4's reason | exact | test |
| M07a.A10 | The envelope at the candidate: (a) `v0.2-alpha-envelope-1`, release `0.2.0a1`; (b) `v0.2-envelope-dev`, release `0.2.0.dev0`; (c) the right id with release `0.2.0a2` | (a) passes; (b) and (c) refused | exact. (b) is today's file, so a gate that does not read the envelope is caught | test |
| M07a.A11 | Required ADRs: Table T5's lines as each ADR's status; one file missing | as Table T5; missing refused | exact | test |
| M07a.A12 | Output and exit: on the fixtures above, the first line, the 17 gate rows in order, the last line format; `--markdown` 17 rows; `--json` keys; exit 0, 1 or 2 as §7.3 | as §7.5 | exact | test |
| M07a.A13 | `scripts/v0_1_gate.py` and `tests/test_t08_w4_v0_1_gate.py` | byte-identical to `main` @ `3eca9c8` (SHA-256 in the generator's YAML); the v0.1 gate's suite green | exact. Any edit to the v0.1 gate needs its own register entry | generator, test |
| M07a.A20 | `release.yml`'s version step on Table T2's inputs, run as the existing `test_the_version_step` runs it | as Table T2; refusals print "not of the form" | exact | test |
| M07a.A21 | The gate step with a stub `scripts/v0_2_gate.py`: (a) exit 0 with the exact YES line for `0.2.0a1`; (b) exit 0 with the line for another version; (c) exit 1 | (a) passes; (b) and (c) refused | exact | test |
| M07a.A22 | `changelog_section.py` on Table T3 | as Table T3; malformed tags exit 2 | exact. The `a10` row catches a prefix match | test |
| M07a.A23 | `github-release` for `0.2.0a1`, `0.2.0rc1` and `0.2.0` | `--prerelease` for the first two, absent for the third | exact | test |
| M07a.A24 | The dispatch defaults | `dry_run` true and `rc` `67c66d9…` (the existing test, unchanged) | exact | test |
| M07a.A30 | Step 1 | `check.sh` green at `C_α` on both CI architectures (run ids recorded) | exact | ci |
| M07a.A31 | Step 2 | T08.A42's three checks at `C_α` on both architectures, with the R-149 values | exact | ci |
| M07a.A32 | Step 3 | T08.A43's checks at `C_α`; `a43.version` gives `0.2.0a1` from all three sources | exact | ci |
| M07a.A33 | Step 4 | T08.A44 and T08.A19 at `C_α` on both architectures | exact; state within `K04-numerical-policy-v1` (registered, ADR 0007 D2) | ci |
| M07a.A34 | Step 5 | T08.A45 at `C_α`: `N_b` enumerated and recorded per set; every bundle `T08-numerical-policy-v2` and `MATCH` on both replay runners; ADR 0025 A14's controls | registered: `T08-numerical-policy-v2` (ADR 0025 §5) | ci |
| M07a.A35 | Step 6 | T08.A46 at `C_α`: S ≥ 418 of 440 on each class, 0 `F-CRASH`, 0 unexplained `F-OTHER-ROOT`, the same-class replay `MATCH`; CP bound reported | registered: T02 §6.4, the 60 s ceiling, T06 A34 | ci |
| M07a.A36 | Step 7 | T08.A47 and A48 at `C_α` on three hosts | registered (T06 §7–§9.4) | ci |
| M07a.A37 | Step 8: the chain of §5.3 at `C_α`, with its negative controls in the test, and G16-b | §5.3 items 1–5 hold; G16-b clean on 40 of 40 against `t07_reference_t08.json`; records attributable | exact | test, ci |
| M07a.A38 | Step 9 | T08.A30 at `C_α` on both architectures, with zero undispositioned objects in a required closure; MR-12's rule for every extra new since `v0.1.1` | exact | ci |
| M07a.A39 | Step 10 | T08.A34 over steps 4–7 and 12: [A08] regularity evidence and [A09] qualification present; 0 violations | exact | ci |
| M07a.A40 | Step 11 | `external_crosscheck.py --check` exit 0 in its pinned environment; the IDAES re-run's numbers identical to the committed record, with only `inputs.*_sha256` members differing, each listed | exact | record |
| M07a.A41 | Step 12 | M02 G10 (a)–(i), G11 (a)–(d) and G12 as M02 §10.2–§10.3 state them, at `C_α`, in the reactor environment from `C_α`'s lock, one thread; the environment block and the CPU model recorded | registered: M01.A41–A48's and M02 G10–G12's own (10⁻⁶ path independence and boundary, 10⁻⁷ element defect, 10⁻³ ΔP, floor ratio 10) | record |
| M07a.A42 | V11 (e)'s predecessor (MR-10): the `SYN-001-nominal` bundle written by the CLI at tag `v0.1.1` (a worktree at the tag, its own environment), committed as a fixture | `C_α`'s `replay --rerun` returns a typed report (`exact_replay` or `compatible_reproduction` `MATCH`, or `inspected_archived_results` with `NOT_RUN` and its reason, or a typed refusal naming the schema version); plain `replay`'s `compatible_reproduction` `NOT_RUN` with its reason is recorded, not judged *(Amendment 1 (review) A42)*; `inspect` renders it; no unhandled exception | exact (pattern), as T08.A35 | test |
| M07a.A43 | Every record of steps 1–12 | carries `commit` = `C_α` (40 hex), `tree_clean: true`, the lock's SHA-256 and its machine class | exact | test |
| M07a.A44 | `release/rc-trees/<C_α>.json` | equals `tree_record(C_α)` regenerated byte for byte; `trees` equal to `TREES` | exact | test |
| M07a.A50 | The envelope at `C_α` | `envelope_id` and `release` as MR-3; `t08_support_matrix.py --check` 0 problems (T08.A20–A24); the harvest classifies every limitation and non-pass check of every manifest at `C_α`, T08's 58 limitations and 2 non-pass checks included, with `HARVEST_EXCLUDED` empty; the size quoted in M07a's manifest equals the computed one | exact | test |
| M07a.A51 | B50's counterpart (MR-7): (a) the content at `C_α`; (b) one unregistered model added to `MODEL_BUILDERS`; (c) one registered addition removed | (a) the differences from `c7bbc98`'s fixture, excluding `server.package_version`, are exactly B50's three entries plus the register-named v0.2 additions, each once; (b) and (c) fail, naming the entry | exact | test |
| M07a.A52 | `CHANGELOG.md` `## v0.2.0a1`: (a) the heading is first, above `## v0.1.1`, and names `C_α`; (b) ADR 0021 D4's six headings in order; (c) the gate table equals `v0_2_gate.py --markdown` at the candidate; (d) "what it is not" contains each phrase of §10.1; (e) the limitation ids named are exactly the alpha envelope's, in order; (f) the reproducibility promise is ADR 0007 F1 verbatim; (g) the review table, as rows, equals MR-5's computed set | all seven hold | exact | test |
| M07a.A53 | The v0.1.0 section's gate-table test (MR-9) | builds the v0.1 report from the ledger and `T08-verdicts.md` at `PUBLIC_ROOT`; its table is in the `## v0.1.0` section; green with the live ledger's W21 and W22 set | exact | test |
| M07a.A60 | `docs/reviews/V02-alpha-verdicts.md` | §6.3's form; judged at `C_α`; each gate's section judges every clause and states what it does not establish | exact (presence and pattern) | verdict |
| M07a.A61 | V11–V20 | judged by T08 §4 at `C_α`, with §5.2's counterparts; V14 (b) expected `FAIL`; V17 `BLOCKED` unless Frank's carry is recorded | exact (criterion) | verdict |
| M07a.A62 | W21 | judged by §6.1, clauses (a)–(f) | exact (criterion) | verdict |
| M07a.A63 | W22 | judged by §6.2, clauses (a)–(d) | exact (criterion) | verdict |
| M07a.A64 | `docs/requirements.yaml` | for the 12 claimed gates the verdict equals the document's; each claimed gate's `evidence` includes `evidence/M07a/<C_α>/manifest.json`; W21's includes an M01 and an M02 manifest, W22's an M01 manifest; W23–W27 untouched | exact | test |

### 10.1 The phrases of "What it is not" (M07a.A52 (d))

ADR 0021 D4's phrases are carried:
- `Not empirically validated`
- `Not a guarantee`
- `R-017`
- `Not general beyond the support matrix`
- `Not a certificate of solution accuracy`
- `ADR 0007 F3`
- `PTC is experimental`
- `MCP only`

The alpha adds:
- `Not 0.2.0`
- `W23–W27 are not claimed`
- `the web shell is included and not claimed`
- `not a sandbox`
- `Linux`
- `x86-64`
- `R3`
- `synthetic`
- `pure-component`
- `k_ij = 0`
- `no reactor result has been compared with experimental data`

---

## 11. Reference generator and executable self-claims

`docs/derivations/scripts/v02a_reference.py` emits `benchmarks/m07a/reference_values.yaml`. It reads committed files
as data and imports nothing from `openflowsheet`, `benchmarks` or `scripts`. `--check` re-derives the following, and
refuses to pass when any of them stops being true:

- **L1. The lock.** `requirements.lock` hashes to `ead4edf1…`, and `scripts/t08_rc.py`'s `LOCK_SHA256` is that value.
- **L2. The surface digests.** Each occurs where it is registered:
  - `171dd768…` in `tests/test_t08_w2_surface_digest.py`, `scripts/t08_rc.py` and the register under `## R-134`;
  - `6c4375b4…` in `tests/test_t08_w2_surface_digest.py` and the register under `## R-192`;
  - `6d13e13d…` in `benchmarks/t08/reference_values.yaml`;
  - the three are distinct.
- **L3. The v0.1 gate's lists.** `v0_1_gate.py`'s `TREES` and `VERSION_FILES` (read by `ast`) equal the lists of
  §7.3 item 6. Its 0.1-line pattern is the one R-151 states.
- **L4. ADR 0021's acceptances.** The accepted FAIL clauses are exactly {`V14 (b)`}, dated 2026-09-29, which §4 item 1
  does not carry.
- **L5. The v0.1 gate is untouched.** `v0_1_gate.py` and its test are byte-identical to `3eca9c8`'s (M07a.A13).
- **L6. T08 §8.2's step table.** Steps 1–11 map to T08.A41, A42, A43, A44/A19, A45, A46, A47/A48, A49, A30, A34 and
  A50, as §8.2 reuses them.
- **M1–M3. W22's figures.** M01's manifest at `3c80392` is `tested`. Its A38, A39 and A40 pass with the measured
  values and bands of §6.2, whose quotients round to 1.58, 1.25 and 1.18. A05–A22 and A37 pass. It has 53 checks:
  52 pass and A47 `not_applicable`.
- **M4. T08's manifest.** `tested`, with 85 checks: 83 pass, and `T08.A70` and `T08.B23` fail. 58 limitations, which
  MR-3 hands to the alpha's harvest.
- **M5. M06's manifest.** `tested`.
- **S1. The ledger.** It holds V11–V20 and W21–W27. W21's owners are [M01, M02] and W22's [M01].
- **S2. The schemas.** The manifest schema's package pattern admits `M07a`. The ledger's gate pattern admits `V` and
  `W`.
- **T1–T6. The tables.** §7.1, §7.2 and §9.1's tables equal the generator's truth tables, and the stated rules
  reproduce every row.
- **C1. The catalogue.** §10's ids equal the generator's catalogue, unique and sorted.
- **C2. The RC step table.** §8.2 holds steps 1–13 in order, with the assertion ids of the catalogue.
- **C3. The moved records.** §5.2's MR ids are MR-1 … MR-12, contiguous.
- **R1. The register.** It holds `## R-238` and `## R-239`, and ADR 0028 holds its two tables with the rows §7.2 item
  3 names.

The YAML is emitted with sorted keys and is byte-reproducible.

---

## 12. What this specification does not establish

- **No verdict.** The `verdict` agent judges at `C_α`. "Expected" in §10 is a forecast.
- **No validation beyond W22's bands.** It establishes no validation of the reactor by this project (§6.1 (f)), and
  no mixture VLE.
- **Not that the RC job passes.** In particular, the ensemble at `C_α` (step 6) and the real loop (step 12) can fail.
  If they do, V20 or W21 is `FAIL` at `C_α`, and a remedy is a new registration, not a re-score.
- **Not W23–W27, not 0.2.0, not M07's journey.**
- **No new tolerance, band, identity value or registered result.**
- **Not that V17's agent behaviour is unchanged on the v0.2 surface.** The carry is Frank's decision on a decomposition,
  as R-133 was, not a measurement. W27's campaign at M07 is a different campaign and does not stand in for V17's.
- **Not a review.** It sets no `reviewed`.
- **Not M02's design.** It cites M02's gates as M02 registered them. If M02 amends them before `C_α`, §6.1 follows the
  amendment, and a criterion that M02 weakens is a finding for the design lane, not an automatic change here.

---

## 13. Open questions with recommended defaults

| # | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Does the reactor environment build and run on aarch64? | **needs a fact**: build it on `ubuntu-24.04-arm` once (M02 N2's alternative) | Not measured. W21's evidence is `ref-x86-64` only. The envelope and the notes say so, with "x86-64" in "what it is not". |
| Q2 | Do `t08_dist.py`, the clean install and setuptools keep `0.2.0a1` unchanged in METADATA, the dist-info name and the file names? | **needs a fact**: WO-3 runs `t08_dist.py` on a scratch tree at `0.2.0a1` | Yes (canonical PEP 440). Any `X.Y.Z` assumption found is fixed in WO-3 and reported. |
| Q3 | Does M02's merge leave the K05 identity unchanged (step 2)? | **needs a fact**: M02 G2 at the merge; step 2 at `C_α` | Yes. If not, stop. A substitution re-registration is Frank's (R-148, R-149). |
| Q4 | Does any package other than M06 and M02 change an MCP-visible schema before `C_α`? | **needs a fact**: the chain test | No. Otherwise §5.3's new-link rule applies. |
| Q5 | Do coupled-route certificates carry [A08] and [A09] evidence (MR-11)? | **needs a fact**: step 10 over step 12's certificates | Yes, by M02 §4.4. If not, V18 (b) is `FAIL` at `C_α`, escalated to the design lane, and the rule is not narrowed. |
| Q6 | Is M03 merged before `C_α`? | **needs the user's preference** (schedule; M03 also waits on its N1) | No: cut `C_α` right after M02's merge. If M03 merges first, MR-12 applies, and M03 N1 is a precondition of V18 (a). |
| Q7 | How is `main` kept equal to `C_α` on D2.4 paths until the dispatch? | **needs the user's preference** | Freeze D2.4 paths on `main` from `C_α` to the dispatch; work continues on branches. Alternative: Frank pushes `v0.2.0a1` on the candidate and dispatches from the tag (the `pypi` environment admits tags `v*`). |
| Q8 | The evidence package id | **needs the user's preference** (bookkeeping) | `M07a` (ADR 0028 D5). Alternative: `M02a`. It is reversible by renaming one directory before the RC. |

---

## 14. Needs Frank

Items F-α0 to F-α3 are **gate preconditions**: the gate checks that each is recorded in ADR 0028, dated on or after the
alpha verdict's `Judged` date *(amended 2026-10-09, Amendment 1 (review) F2)*. Items F-α4 and F-α5
proceed on their defaults until Frank answers.

- **F-α0 — N3: what `0.2.0a1` claims.** Default: `v0.2-alpha-gate-v1` (§3). Alternatives: (i) also W26; (ii) W21 and
  W22 only, without re-judging V11–V20 (not recommended); (iii) no pre-release before M05 or 0.2.0. Reversible by not
  dispatching.
- **F-α1 — V14 (b) FAIL carried into `0.2.0a1`.** ADR 0021 D3 is per release, so the 2026-09-29 acceptance was for
  v0.1. Default: accept, with PTC experimental and selectable by explicit policy only, as in v0.1. It must be dated on
  or after the alpha verdict.
- **F-α2 — V17 (and T08.B50's surface) carried across R-192 and R-234.** Neither change touches a description text.
  Both add schema members: `elements` in one output schema, and M02's additive members and branches. Default: carry,
  with the chain recorded, as R-133 did. Alternative: a new V17 campaign on the v0.2 surface, about USD 10 of
  subscription time and an hour (T08 F5's estimate).
- **F-α3 — M02 N1 for a published release.** `external-subprocess-v1` runs the group's pinned code with the user's
  privileges and no confinement, on Linux. Default: accept, stated as "not a sandbox" in the support matrix and the
  notes.
- **F-α4 — W21 (f)'s reading.** Default: the parent model's validation is cited, its regression suite reproduced, and
  its adapter conformance and numerical error carried (§6.1). Alternative: this project compares reactor results with
  experimental data inside W21, which would be `BLOCKED` on the 4TU data-use statement.
- **F-α5 — Publication.** Default: through `release.yml`, with Frank's `pypi` approval, and a GitHub release marked
  pre-release (`pip` installs it only with `--pre` or the exact version).

The alpha also ships with M02's other defaults: N2 (no CI reactor job, hence Q1), N4 (the stand-in shipped and listed
synthetic), N5 (the PR LIQUID regime deferred) and N6 (no reactor warm start). The notes state each.

---

## 15. Build-lane work orders

Branch `wp/M07a`, from `main` after M02's merge. WO-1 to WO-4 and WO-7 do not depend on M02 and may start now on
`wp/V02-alpha-gate`.

| WO | Owner | Content | Depends | Acceptance |
| --- | --- | --- | --- | --- |
| **WO-1** | bounded | Add `v02a_reference.py` to `tests/test_t08_reference_generators.py`'s parametrization | — | M07a.A00 in `check.sh` |
| **WO-2** | Opus | `scripts/v0_2_gate.py` (§7) and `tests/test_m07a_v0_2_gate.py`. `scripts/v0_1_gate.py` is **not edited**; the new script may import from it any function whose behaviour depends on no v0.1-only constant (`TREES`, `VERSION_FILES` and the RC-record status words are shared by ADR 0028 D2): `_tables`, `_cells`, `_bare`, `_rc_outcome`, `git`, `has_commit`, `tree`, `_contents`, `_sha256`, `version_at`, `tree_record`, `recorded_tree_differences`, `tree_differences`; and defines its own versions of the rest, parametrized by the gate set | — | M07a.A01–A13 |
| **WO-3** | Opus | `release.yml`'s version regex and `--prerelease`; `changelog_section.py`'s tag form; `tests/test_release_workflows.py` and `tests/test_changelog_section.py` extended; `docs/RELEASING.md` "Pre-releases"; Q2's scratch-tree run of `t08_dist.py` at `0.2.0a1`, reported | — | M07a.A20–A24; Q2 answered |
| **WO-4** | bounded | MR-9: `tests/test_t08_w4_changelog.py::test_the_gate_table_is_what_the_gate_script_prints` reads the ledger and `T08-verdicts.md` at `PUBLIC_ROOT` (`git show`), as R-216 did for the envelope | — | M07a.A53 |
| **WO-5** | Opus, **R** | The alpha's step 8 (§5.3): the composed chain as a test (with negative controls (i)–(iv)) and as an RC subcommand; a CI dispatch input (`rc_alpha`) running steps 1–10 with it. `scripts/t08_rc.py`'s registered constants and its 0.1 `surface` step are unchanged; new code imports its other steps | M02 merged (link c_2 registered) | M07a.A37; `tests/test_t08_w4_rc.py` green |
| **WO-6** | Opus | MR-7: B50's content counterpart in `tests/test_t08_b50_surface_content.py`. B50's named entries plus a register-sourced list of v0.2 additions, each cited by its R entry. This may land with M02's merge; the alpha requires it | M02 merged | M07a.A51 |
| **WO-7** | Opus | MR-10: the v0.1.1 bundle fixture (written by the CLI in a worktree at tag `v0.1.1`) and its test | — | M07a.A42 |
| **WO-8** | Opus, **R** | MR-3 and MR-5: the harvest of T08's manifest (its 58 limitations and 2 non-pass checks classified E/S/P/B, with pointers), `HARVEST_EXCLUDED` emptied, the size test; at `C_α` the envelope id and release pinned and the support matrix re-emitted | M02 merged (its rows) | M07a.A50 |
| **WO-9** | bounded, then design-lane read | The `## v0.2.0a1` section skeleton (D4 headings; "what it is not" with §10.1's phrases; the limitation list generated from the envelope) and `tests/test_m07a_changelog.py`; the gate table is pasted from `--markdown` after the verdicts | WO-2, WO-8 | M07a.A52 |
| **WO-10** | Opus (runs) | Cut `C_α`; run the RC job (§8.2) and write the RC record, the records, `records.json` and the tree record; the M07a manifest generator `scripts/m07a_evidence_manifest.py` (T08's pattern) and the manifest | all above | M07a.A30–A44; manifest `tested` iff A00–A53 pass |
| **WO-11** | bounded | Ledger (M07a.A64) after the verdicts; `docs/progress.md` and `docs/V02_STATE.md` | verdicts | M07a.A64 |

**Design-lane steps.**
- A `reviewer` pass on WO-2 and WO-5, before `C_α`.
- The `verdict` agent at `C_α` (§6.3).
- Reading WO-8's harvest rows for T08's manifest. The E/S/P/B classification is a design-lane read, as T08.A21's was.

---

## 16. Findings (recorded, not acted on here)

- **FD-α1.** Plan §5.1's W21 row ("PyMRM boundary/accuracy/execution and provenance") omits three clauses of blueprint
  §14.4 bullet 1: port mapping, timeout, and parent-model validation. The blueprint clause counts (§6.1). The plan text
  is not changed.
- **FD-α2.** M02 note §10.4 proposes "the v0.1 release gate unchanged … except its served-surface row". It does not
  account for T08 §4.7's rule that a changed surface makes V17 `BLOCKED` pending Frank. ADR 0028 makes the carry an
  explicit, gate-checked answer (F-α2). M02's proposal is superseded by ADR 0028, not amended.
- **FD-α3.** R-153 says pre-releases go through `release.yml`. Today the workflow and `changelog_section.py` refuse
  every PEP 440 pre-release (WO-3).
- **FD-α4.** `tests/test_t08_b50_surface_content.py` will fail when M02 adds `c1.*` models to `list_models` (WO-6).
- **FD-α5.** The ledger holds one verdict per gate and no commit. Two release lines judging the same gate at different
  RCs share the row. The v0.1.0 notes' gate-table test reads the live ledger (WO-4).
- **FD-α6.** `scripts/v0_1_gate.py` never checked that `T08-verdicts.md` names the same `C` as `--rc`. The alpha's gate
  does (§7.2 item 2). The v0.1 script is left as released.
- **FD-α7.** `HARVEST_EXCLUDED` still holds `evidence/T08/`. F3 (T08 Amendment R8 4) is discharged at the alpha
  (WO-8).
- **FD-α8.** The RC-record grammar fails any row that reads "not measured". An unmeasured platform is therefore stated
  in the envelope and the notes, never as an RC row (§4 item 4).

---

## 17. Amendment 1 (review), 2026-10-09

**Author:** design lane (`reviewer`), `docs/reviews/V02-alpha-gate-review.md` (verdict "sound, no must-fix"),
transcribed by the build lane. The rulings below are the reviewer's recommended rules and are binding. The body
markers *(amended 2026-10-09, Amendment 1 (review) F<n>)* point back here.

**F1 — Table T4's cell rule (review F1).** The rule "starts with `accepted` and contains a date" counted a chosen
alternative written after the word as an acceptance of the default (`accepted (i), 2026-10-12`), and its unbounded
date read `2026-10-123` as 2026-10-12. §7.2 item 3's cell rule is replaced: the bare, lower-cased cell must match
`^accepted[\s,;:]*(\d{4}-\d{2}-\d{2})(?![0-9])` at its start, and the captured date, a calendar date, is the
acceptance date. Table T4's three `yes` rows and five `no` rows keep their answers; three `no` rows are added:
`accepted (i), 2026-10-12`, `accepted alternative (ii), 2026-10-12` and `accepted, 2026-10-123`. The rule governs
both of ADR 0028's tables, so the D3 cell for V14 (b) is read by it too. Rejected: keeping the rule and telling Frank
in `RELEASING.md` to write exactly `accepted, <date>`, which relies on the writer.

**F2 — Frank's per-release answers are tied to the release (review F2, option (a)).** The gate set covers every
`0.2.0aN`, and the decisions table carried no date rule, so `0.2.0a2` would have been proposable on the three answers
given for `0.2.0a1`; D3's rows were protected only by the new verdict's `Judged` date. D3's date rule now applies to
the decisions table too: `N3`, `V17 carry` and `M02 N1` each count only if dated on or after the verdict's `Judged`
date (§7.2 item 3, §7.3 item 11, §9.2 step 6, §14). Table T6 fixes the rule for both tables, and the generator
re-derives it. Rejected: (b) reading each table only under a heading that names the version, which ties the gate to
prose headings; (c) narrowing `covers` to `0\.2\.0a1`, which changes Table T1 and only defers the question.

**F4 — each refusal has its own state (review F4; tests only, no rule changes).** The refusals the build lane added
(review §4, rulings 3 and 5) each get one state on the passing fixture: M07a.A03 `**Judged:**` twice; M07a.A04 (i)–(l);
and in M07a.A05 two decisions tables, a doubled row and a non-calendar date. Removing any one of these refusals fails
its own state and no other.

**A42 — which `replay` is judged (review §5).** M07a.A42's expected outcomes are those of `C_α`'s `replay --rerun`: only
a rerun can give `exact_replay` or `compatible_reproduction` `MATCH`. Plain `replay` never reruns (R-131), and its
`compatible_reproduction` `NOT_RUN` ("no rerun was supplied") is a typed report that is recorded, not judged, so it is
not read as a `FAIL` of V11 (e). The test already reads A42 this way; the row now says so.
