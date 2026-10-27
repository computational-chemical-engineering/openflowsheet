# S11 brief: the binding package — library-only property models and the columns into flowsheets (design lane, `architect`)

Branch `wp/S11`, worktree `.claude/worktrees/s11`, from `main` `8c34ecb0`. The facts you need are in the recon digest
`docs/briefs/S11-binding-recon.md` (read-only survey, 2026-10-26, with `file:line` anchors and excerpts): read it first, in
full; it replaces reading the repository wide. Open further files only for what the digest does not settle.

## 1. The question

Design the package that makes these usable in flowsheets (process revisions the compiler, solver and verifier take), with
the ADR it needs, and work orders that two engineers can build **in parallel on disjoint files**, so that the whole package
is tested once at the end:

- **Property bases:** `iapws95-v1` (S05, pure water), `coolprop-heos-v1` (S07, CoolProp pure fluids, one fluid per
  instance), `wilson-ig-v1` (S10/S10-C, Wilson γ–φ with an ideal-gas vapour).
- **Unit models:** the S02/S06 column (and S01's cascade, if it costs little more) into `MODEL_BUILDERS`, with their
  support-envelope L-rows (R-535), and S06 §14's flowsheet binding of `F`, `F_c`, `ν*`, `π*` (S06-spec §15 Q7).
- **The admission-time checks already deferred here:** R-781 / S10-C review F2 (the column theorem's premises P1–P3 checked
  when a Wilson column is admitted), R-569 (axis row and L-rows come with the selection), S05 F-3 (W27 method string →
  `iapws95-v1`), and the rest of the digest's §6 list. Each item of §6 must end either done by S11 or explicitly left, with
  its reason.

What must come back: what a revision writes to select each basis (today selection is by `component_set.record_source`, and
two of the three new bases have no records file); `SELECTABLE_BASES`' new shape; which unit models each basis admits and how
(today `MODEL_BUILDERS` is per-basis: 13 syn001 + 9 c1 builders, `MODEL_BASES` maps each to one provider — do the new bases
reuse the c1 builders generically, or get their own?); what each basis must still provide that it does not (digest §3 gaps:
Wilson has no `s`, `v`, `Psat`; say which gaps block which units and whether S11 closes or refuses them); the two dispatch
tables (`basis_provider`, `fresh_provider`); W27 v2 rows and `PROVIDER_LINES`; support matrix, envelope, `LIBRARY_ONLY_PROVIDERS`
and the harvest; numbered falsifiable assertions; the identity gate.

## 2. Why it needs the architect

It changes a frozen interface (`SELECTABLE_BASES`' shape; S07-spec §12.4 says it needs its own ADR, which will be ADR 0050)
and possibly the frozen `process-revision` schema (`schemas/process-revision.schema.json:33-41`). It decides how unit models
attach to property providers for every future basis. A wrong shape here is expensive to undo.

## 3. Already decided, not open

- **Frank, 2026-10-26: "I want the binding package."** This supersedes the "library only for now" defaults: S05 Q-8
  (Frank 2026-10-23), S10 Q-F2 / R-709, S10-C Q1 ("Wilson not in flowsheets") and S10-C Q3 ("no cascade or other units") as
  far as S11's scope reaches. Record each supersession in the register.
- Frank's standing directive: as few limitations as possible; robustness first. Unimplemented capability returns an
  explicit unsupported result (never a placeholder success).
- **Frank, 2026-10-26: batch, then test once.** Design the work orders for two engineers in parallel (disjoint files), no
  intermediate full gates; per-commit only the touched tests and bit-identity scripts; one `reviewer` pass, one full gate,
  one CI at the end.
- Existing registered results do not move: every revision that solves today solves bit-identically (identity gate as in
  `scripts/s08_identity.py` / `scripts/s10c_identity.py`, whose registered lines are
  `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL` and `S10C-IDENTITY PASS n=858 changed=[]`).
- Never edit an earlier harvest envelope entry (HG(b), R-617); HARVEST_SIZE is pinned in `tests/test_m07a_harvest.py`.
- ADR numbering: next ADR is 0050. Register: R-795 and R-796 are taken by an unmerged branch (`wp/R796`); start S11's
  entries at **R-800**.

## 4. Genuinely open (decide each, with a default where it turns on Frank's preference)

1. Basis-selection key for record-less bases (schema change or not; how CoolProp's fluid is named in a revision).
2. Generic unit models over any provider with the needed property ids, versus per-basis builders.
3. Which units each new basis admits on day one; what refuses, with which typed outcome.
4. Wilson's missing `s`/`v`/saturation: close in S11, or admit only the units that need just `h` and `lnphi`.
5. Whether `pr-lib-v1` (S04/L01, vapour only, no flash; R-615) joins S11. Default: your call on cost; Frank wants few
   limitations.
6. Column/cascade binding: what a column unit looks like in a revision (its spec, its streams, its specs `F`, `F_c`, `ν*`,
   `π*`), and the verifier's certificate path for it.
7. W27 v2: new provider-method rows and lines, or explicitly not registered (W27 v1 files are frozen).

## 5. Out of scope

NRTL/UNIQUAC/LLE (no code exists; S10-spec says an interface ADR first); Helmholtz mixtures; S07b cryogenic liquids; the
methanol+ethanol refit (S10 S-4); any change to a registered numerical result; GUI/web.

## 6. Deliverable

A design note `docs/derivations/S11-design.md` (decision, rejected alternatives, the open items above decided, the ADR
summary, records that move, numbered assertions, the identity gate, work orders split into **track A and track B** on
disjoint files plus a short integration WO, risks with defaults); ADR `docs/adr/0050-…md` (Proposed); register entries from
R-800; a docs-only commit on `wp/S11` including this brief and the recon digest. Do not push. Report in at most 20 lines.
