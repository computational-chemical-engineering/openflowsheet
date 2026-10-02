# Fable brief — T01: structural analysis, and what a structural finding may claim

**To:** `fable-specifier`
**From:** the Opus session (Opus 5)
**Date:** 2026-09-23
**Deliverable:** `docs/derivations/T01-structural-spec.md` and
`benchmarks/t01/reference_values.yaml`
**Plan row:** §4.2 T01 — "process/equation graphs, fixed/alias elimination, DM/SCC/BTF,
source-mapped counts and tear candidates"
**Acceptance (plan):** "Square structural defect vs numerical defect distinguished; block-size
metrics; canonical tie-breaks; zero-flow cases"

---

## 1. The question

**What does a structural analysis of a flowsheet establish, how is the answer made unique, and
which of the five things five packages have parked on T01 does it actually entitle us to say?**

Six things I need decided.

1. **The discriminator.** The nominal, *correct* SYN-001 is structurally over-determined: 49
   declared rows over 47 columns, structural rank 47. So "has an over-determined
   Dulmage–Mendelsohn block" cannot be the rejection rule — it would reject the flowsheet the
   whole project is built on. §3.2 measures what distinguishes the nominal from the registered
   invalid case. **What is the rule, stated so it can be falsified?**
2. **Canonical tie-breaks.** A maximum matching is not unique. Plan §4.2 demands canonical
   tie-breaks and gate G05 compares structural artifacts across two CI architectures on every
   push. What is the rule, and what is the argument that it is total (no ties left) and
   order-independent?
3. **What a structural finding may and may not claim**, in the vocabulary a report carries.
   Blueprint D05 separates structural from numerical singularity; K04's [A08] owns the numerical
   rank verdict. I want the sentences, as K04's `STATEMENTS` are sentences.
4. **The `structural_counts` field set** for `ValidationReport`: which counts, defined how, and
   what each one is *not* evidence of. It is currently `null` with a written reason.
5. **The tear-candidate rule.** Plan §3.2 obliges T01 to *rediscover* SYN-001's three-variable
   tear from the incidence graph rather than read it from the flowsheet module, and "a test must
   confirm that T01 rediscovers this three-variable tear rather than having it hard-coded". What
   selects it, and why does the rule give three and not five?
6. **The registered assertions**, A-numbered with tolerances, starting with
   `SYN-001-conflicting-heater-spec`.

## 2. Why this needs Fable

Because the obvious implementation is confidently wrong in two independent ways, and I measured
both.

The first is §3.2: over-determination is not a defect. The pressure subsystem of SYN-001 is
*deliberately* redundant — K02 assembled nine pressure rows over seven pressure columns and K03
removes two of them structurally, with a certificate, because blueprint §7.7 forbids discarding
equations numerically. A matching-based validator written the obvious way rejects the nominal
case. The line between "consistent redundancy, fine" and "specification conflict, not fine" is
not drawn by the matching; it is drawn by whether the redundancy *is consistent*, which is a
numerical fact about the residual. That is D05 in person and it is a semantics question, not a
coding one.

The second is that a structural result is an *authority claim*: `validate()` returning `INVALID`
tells a user their flowsheet is wrong before any solver has run. Getting the claim's strength
right — diagnostic, not proof — is the same class of problem as K04's certificate, and K04 went
to you for the same reason.

## 3. What exists now, measured today

All numbers in this section were measured on `main` at `f603e9b`, gate green at 1320 on both CI
architectures. The probe scripts are in the session scratchpad; every number below is
reproducible from the repository as it stands.

### 3.1 The incidence structure already exists, addressable by name

K01's `JacobianResult` (`src/process_runtime/compiled.py:123-152`) carries `row_ids`, `col_ids`,
`indptr`, `indices` and `pattern_provenance`. T01 needs no new instrumentation.

    tear = Syn001TearProblem(Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT))
    J = tear.compiled.jacobian(np.array(state_vector(tear.spec, state)), tear.context)
    # 49 x 47, nnz 170, pattern_provenance='backend-declared', source_map 49 entries

Row and column families at the nominal state:

| Rows (49) | | Columns (47) | |
| --- | --- | --- | --- |
| `U-FEED:*` 5 | `U-MIX:*` 6 | `S#.n.{A,B,C}` 21 | `S#.T` 7 |
| `U-HEAT:*` 14 | `U-FLASH:*` 14 | `S#.P` 7 | `S#.{L,V,N}` 4 |
| `U-SPLIT:*` 10 | | `S#.{liq,vap}.{A,B,C}` 6 | `U-HEAT.Q`, `U-FLASH.Q` 2 |

`source_map` already carries `{'row_id': 'U-FEED:FEED-n:A', 'origin': 'syn001.feed_source#FEED-n'}`
for all 49 rows, which is the "source-mapped counts" half of the plan row, already available.

**There is no state-free structure accessor.** The pattern is reachable only through
`jacobian(x, context)`, which also evaluates data and can return `status != "ok"` with an *empty*
pattern at a bad state (`compile/casadi_backend.py:490-518`). `CompiledProblem` is frozen (plan
§2.1), so adding `structure()` would take an ADR. My proposal in §4.1 avoids that; tell me if it
is the wrong trade.

### 3.2 The decisive measurement: over-determination does not discriminate

Coarse Dulmage–Mendelsohn, over-determined block computed as unmatched rows plus everything
reachable from them by alternating paths. Maximum matching by Hopcroft–Karp (scipy's
`maximum_bipartite_matching`) on the **declared** pattern.

| | rows × cols | nnz | struct. rank | matching | over-determined block |
| --- | --- | --- | --- | --- | --- |
| `SYN-001-nominal` (**valid**) | 49 × 47 | 170 | 47 | 47 | **7 rows, 5 cols** |
| `SYN-001-conflicting-heater-spec` (**invalid**) | 50 × 47 | 171 | 47 | 47 | **44 rows, 41 cols** |

Both are over-determined. Both have full structural column rank. Both leave every column
matched. The difference is **what is in the block**:

- Nominal: `{U-FEED:FEED-P, U-FLASH:FLASH-P:inlet, U-FLASH:FLASH-P:liquid, U-HEAT:HEAT-pressure,
  U-MIX:MIX-pressure:0, U-MIX:MIX-pressure:1, U-SPLIT:SPLIT-P:recycle}` over
  `{S1.P, S2.P, S3.P, S5.P, S6.P}` — **confined to the pressure subgraph**, which is exactly
  where K03's consistent-redundancy certificate lives.
- Conflicting: the block swallows the mixer, heater, flash and splitter — 44 of 50 rows — because
  `U-HEAT.Q` is the only column the duty row can take and freeing it propagates through the
  energy balance.

So a rule of the form "the over-determined block must be empty" rejects both; "the
over-determined block must be confined to rows whose redundancy carries a certificate" accepts
the nominal and rejects the conflicting one. I think that second form is right, and I want it
stated by you, with the argument for why confinement is the right invariant rather than a
threshold on block size.

### 3.3 What the solver does with the conflicting case today, measured

The K06 evidence manifest and `application/validation.py:150-155` both say K03 rejects the
conflicting revision with `SPECIFICATION_CONFLICT`. **That is wrong, and I measured it.** The
conflicting revision has never been compiled — `Syn001Flowsheet` has no heater-duty parameter —
so nobody had run it. Assembling the spec by hand with the extra duty row gives:

    ValueError: the inner block is 45x44 and not square; UNSUPPORTED_RANK_STRUCTURE

`SPECIFICATION_CONFLICT` (`orchestrator/rank.py:221`) fires only for a *pressure-graph* cycle
whose mismatch exceeds ADR 0001 D6's 1e-2 Pa; that is the registered flash-at-150-kPa case in
`tests/test_k03_rank.py:145-168`, not this one. A duty row is over a `heat_rate` column, so alias
elimination never looks at it, retains it, and the non-squareness surfaces at
`orchestrator/trace.py:207-212` (`SolvePlan.__post_init__`).

Two consequences for you. First, the record needs correcting and I will correct it. Second, and
more to the point: today's failure mode says *"this tool does not support that structure"* when
the truth is *"your flowsheet specifies the heater twice"*. **That gap is what T01 is for**, and
it is a better statement of the acceptance criterion than the one in the manifest.

### 3.4 Declared pattern versus numerical nonzeros, measured

At the nominal probe state, **4 of the 170 declared entries are numerically zero**:

| Entry | Why it is zero |
| --- | --- |
| `U-MIX:MIX-energy × S1.n.A` | `∂H_feed/∂n_A = h_A(T_r, P_r) = 0` **exactly**, by the `SYN-001-ref-v1` reference convention (ADR 0001 D5.1): the fresh feed is at `T_r = 300 K` and `P_r = 100 kPa`. This is zero at *every* state, not just this one |
| `U-MIX:MIX-energy × S1.n.B` | same |
| `U-MIX:MIX-energy × S1.n.C` | same |
| `U-FLASH:FLASH-duty × S4.P` | |

Matching on numerical nonzeros gives 166 entries. Here it happens not to change the structural
rank (47 either way) or the unmatched rows — but it would have erased the fresh feed's entire
contribution to the mixer energy balance from the graph, and the reason it is zero is a
*reference-state convention*, not a structural fact. Pick a different reference temperature and
those three entries reappear. A structural conclusion that changes when you move the enthalpy
datum is not a structural conclusion.

This is not hypothetical elsewhere either: your K05 review finding S4 flagged exactly this shape
in `orchestrator/rank.py`, which qualifies rows from numerical nonzeros at one state.

### 3.5 The tie-break is live, not theoretical

On the nominal case scipy's matching leaves `{U-FLASH:FLASH-P:inlet, U-SPLIT:SPLIT-P:recycle}`
unmatched — which happens to be exactly the pair K03's alias elimination eliminates. That
coincidence is the danger, not the reassurance: nothing made it happen, and another matching
implementation, another row order, or another library version could leave a different pair. Gate
G05 (`scripts/k05_structural_identity.py`, the `identity` CI job) compares structural artifacts
between x86-64 and aarch64 on every push, and any structural output T01 records becomes part of
what is compared.

### 3.6 The five parked limitations

| Blocked | Recorded at |
| --- | --- |
| Structural over-specification undetected; `READY_FOR_SIMULATION` on a revision the solver refuses | `application/validation.py:157-169`; K06 manifest `K06.structural_over_specification` |
| `structural_counts` null in every report | `application/validation.py:181-186` |
| STR-03 `unsupported` | K04 manifest `K04.A22`; K06 manifest |
| Rank report absent | K02 manifest `K02.structure.rank` |
| Alias elimination handles only two-node ±1 edges — refuses ratios, scaled drops, general cycles | `orchestrator/rank.py:173-183` |
| The attempt signature's general rule, from block-triangular form | K03 spec §9.1 |

## 4. What I propose, for you to confirm or overturn

Stated as recommendations so you can overturn them cheaply. I have not implemented any of them.

**4.1 Pattern acquisition.** T01 obtains the pattern by calling `jacobian` at one admissible
state and reading *only* `indptr`/`indices`, never `data`; it refuses unless `status == "ok"`
**and** `pattern_provenance == "backend-declared"`. This keeps the frozen §2.1 interface intact.
The cost is that a revision must be compilable to be analysed, which is the same constraint K06's
CLI already has. The alternative — an ADR adding `structure()` to `CompiledProblem` — is cleaner
and more expensive.

**4.2 The discriminator (§3.2).** Reject when the over-determined DM block contains a row that
is not covered by a redundancy certificate; accept when it is confined to certified rows. The
report names the rows either way.

**4.3 Tie-break.** Order rows and columns by their declared ids under a fixed byte ordering
(ADR 0002's canonicalization already fixes what "fixed" means), run a deterministic augmenting
sequence in that order, and record the tie-break rule by name in the artifact. My worry is
whether id order is *meaningful* enough — it is alphabetical on `U-FEED`, `U-FLASH`, `U-HEAT`,
`U-MIX`, `U-SPLIT`, which is not flowsheet order — or whether a structurally-motivated order
(degree, then id) is better. It must be total either way.

**4.4 Increment order.** Matching first (closes §3.6 rows 1–3 alone), then DM, then SCC/BTF. The
specification should be written so increment 1 is shippable with the rest explicitly absent.

## 5. Already decided, and not open

- **Blueprint D05**: structural and numerical singularity are separated. The numerical rank
  verdict is K04's [A08] screen on the unregularized target Jacobian and stays there. T01 does
  not issue one, and `graph/__init__.py` already says so.
- **Blueprint §7.7**: a regularized least-squares step is numerical recovery and "never
  permission to discard equations". K03's elimination is structural *with a certificate* for this
  reason; T01 does not get to relax it.
- **Plan §3.2**: SYN-001's tear is three variables because the recycle's T and P are known from
  the flash specification — and T01 must **rediscover** that, with a test proving it is not
  hard-coded. This is an obligation on T01, not a fact T01 may consume.
- **ADR 0001 D6** registered tolerances, including 1e-2 Pa on pressure consistency.
- **ADR 0002** canonicalization and RFC 8785; **ADR 0008 D2.1** including "no test may pin a
  digest value".
- **The plan §2.1/§2.2 freeze.** T01 may add new types; changing `CompiledProblem`,
  `ValidationReport`'s existing fields, or K03's five is a migration and must be said out loud.
- **R-001 … R-017** in `docs/decision-register.md` — in particular R-011 (why alias elimination
  is structural and certificated) and R-A05 (K03 §9 is the interim normative text until ADR 0005).
- The registered case set is the six SYN-001 revisions in `benchmarks/syn001/cases/`. No new
  flowsheet.
- Gate: `PATH=.venv/bin:$PATH ./scripts/check.sh`, currently green at **1320** on
  `ubuntu-latest` (x86-64) and `ubuntu-24.04-arm` (aarch64).

## 6. Already tried and rejected, with evidence

- **"Over-determined ⇒ invalid."** §3.2: rejects the nominal flowsheet. Measured, not argued.
- **Matching on numerical nonzeros.** §3.4: three of the four vanishing entries vanish because
  of a reference-state convention.
- **Trusting `data` at all.** The error paths of `jacobian` return an empty pattern with a
  non-`ok` status; a caller that did not check would silently analyse a 49 × 47 matrix with zero
  entries and report a catastrophic structural defect.
- **Reading the tear from `Syn001Flowsheet`.** Forbidden by plan §3.2, and the module's own
  docstring says so.
- **U-diagonal inspection as a rank test.** Rejected by blueprint §8.1 and ADR 0004 D3.4. It is
  not T01's, but it is the obvious wrong door and it stays shut.
- **Treating a sparsity count as structural when a pivot chose it.** K04 §4.2 measured nine
  one-ulp perturbations giving six distinct `nnz(L)` sequences on one machine. Anything T01
  records must be structural in the sense that survives that.

## 7. How the answer will be verified

The gate above, plus: T01's evidence manifest measures every number it records at generation
time, as K03's, K04's, K05's and K06's do (`scripts/k0*_evidence_manifest.py` are the pattern).
The G05 `identity` job compares every structural artifact across the two architectures on every
push — so anything T01 emits into a run bundle must be byte-identical between them, which is the
practical test of §1 question 2.

Correctness fixtures need an analytic or independent expectation; self-generated outputs are
regression fixtures only. For T01 the independent expectations available are: the known 3-variable
tear, the known 2-row pressure redundancy, the known 47 structural rank, and the hand-assembled
conflicting case of §3.3.

## 8. Deliverable

**`docs/derivations/T01-structural-spec.md`**, in the shape of your K03 and K04 specifications:
numbered sections; the definitions (process graph, equation graph, what is a variable, what is a
row, what fixed/alias elimination removes and on what evidence); the matching and DM semantics;
the canonical tie-break with its totality argument; the claim vocabulary of §1.3 as quotable
sentences; the `structural_counts` field set with each field's definition and its
non-implications; the tear-candidate rule; and numbered falsifiable assertions with tolerances,
marked exact or toleranced.

**`benchmarks/t01/reference_values.yaml`** for anything numeric, in the shape of
`benchmarks/k04/reference_values.yaml`.

First registered assertion: `SYN-001-conflicting-heater-spec` is rejected at validation with a
structural finding naming the over-specified unit — not `UNSUPPORTED_RANK_STRUCTURE`, and not by
the solver. Second: `SYN-001-nominal` is *not* rejected despite being over-determined. Please
also register the zero-flow variant (the 310 K case, where `S4` has exactly zero flow and
`ZERO_FLOW` is a phase signature rather than a failure, ADR 0001 D3.4) — plan §4.2 names
zero-flow cases in the acceptance line and I do not know whether the declared pattern changes
there.

## 9. Escalate to Frank rather than choosing

Frank has asked to be consulted where the answer turns on something only he can settle — not for
routine judgement. If you hit one, **stop on that point, write it under a heading `FOR FRANK`,
state the options and your recommended default, and continue with the rest.** I relay them
verbatim. Qualifying kinds: a scientific requirement that would have to change; how strong a
claim `INVALID` should be allowed to make, if that is a project-value judgement rather than a
technical fact; anything needing compute, data rights or an outward-facing action; and any point
where you would reverse a decision Frank made.

## 10. Out of scope

T02's execution strategy (acyclic order, Anderson acceleration, EO blocks). T03's generalized
phase-attempt contract and ADR 0005. T06's rank diagnostics beyond D05's separation. Generalizing
alias elimination to ratios and scaled drops — T01 should say what the graph *shows*, and whether
K03's eliminator is then generalized is a separate decision. A new flowsheet or benchmark. A
third platform. Writing production code: this pass produces the document T01 is implemented
against and judged by.
