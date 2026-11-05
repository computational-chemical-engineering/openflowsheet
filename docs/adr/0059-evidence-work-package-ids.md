# ADR 0059 — The evidence manifest's `work_package` admits the roadmap's package ids: an additive widening

**Status:** Proposed, 2026-11-05 (design lane, `reviewer`, F0 ruling round D16; brief `docs/briefs/F0-review.md`).
It becomes **Accepted** when the build lane has applied the pattern below in one isolated commit and recorded that
`tests/test_evidence_manifests.py` passes with every committed manifest unchanged and with F0's manifest
(`evidence/F0/<commit>/manifest.json`) added. The build lane marks it, as for ADRs 0050–0054.
**Author:** design lane (`reviewer`), review `docs/reviews/F0-review.md` (ruling 2).
**Change rule served:** plan §2.2 / `docs/interfaces-frozen.md` header: a widening of a frozen schema needs a
design-lane ADR. Precedent for an additive widening without a version move: ADR 0054 (and 0012, 0015, 0018, 0025).
**Register:** a new entry (next free R-number when committed) that **reverses the rejected alternative** of R-565 and
R-878 ("an ADR widening the pattern"), for the reasons under *What changed* below.

## Context (measured on `main` = `7783ec94`)

- `schemas/evidence-manifest.schema.json:21-24`: `"work_package": {"type": "string", "pattern":
  "^[PKTMSR][0-9]{2}[a-z]?$"}`. `tests/test_evidence_manifests.py:96` also requires the directory name
  `evidence/<work_package>/` to equal the field.
- ADR 0057 (Accepted by Frank, 2026-11-02) and `docs/roadmap/target-architecture.md` name the packages from 0.4 to 1.0:
  `F0`–`F8`; `X01`–`X26` with letter suffixes (`X07a`, `X07b`); and the named tracks `TX`, `MSG`, `ST`, `OPT`,
  `RRC`, `PrISMa` (roadmap dependency table, lines ~900–1000). None of them matches the pattern. `W1` is a design
  wave and `FB-04 (2)` is part of F5; neither carries a manifest.
- Precedent so far: each misfit got a fitting alias (R-565: `L01` → `S04`; `E01` → `S12`; R-878: `V03` → `S13`;
  ADR 0028: `M07a`). C-items carry no manifest (R-565).
- The schema's bytes enter no runtime identity: no module under `src/` reads it (it ships through the
  `_data/schemas` symlink), and no replay bundle, run manifest or release inventory hashes it.

## What changed since R-565 and R-878

Those rulings rejected a widening because the misfits were one-off labels, and an alias cost one line. The roadmap
now fixes more than forty package ids that do not fit, by Frank's acceptance. Aliasing each one would make every
evidence directory, check-id prefix and branch name of the next six releases differ from the id the authority
uses. That is a recurring cost and a standing source of mismatches. R-565's two objections still hold, and this ADR
respects them: the `L` and `C` letters stay out (no package/support-row ambiguity, and no one-digit C ids), and the two
other frozen schemas that share the old pattern are not touched.

## Decision

**D1.** `schemas/evidence-manifest.schema.json` `properties.work_package.pattern` becomes

```
^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa)$
```

It is additive: every string the old pattern accepts, the first alternative accepts unchanged. It accepts `F0`–`F9`,
`X01`–`X99` with an optional lower-case letter, and the six named tracks. It still refuses `L01`, `C9`, `E01`,
`V03`, `W1`, `FB-04`, an empty string, lower-case-first ids, and angle-bracket placeholders.

**D2.** No version move and no other schema changes. `package_id` in the ledger schema and the model-manifest
schema keep `^[PKTMSR][0-9]{2}$`. If a roadmap package later needs either one (for example, F6's `std.*` model
manifests), its own design pass decides that, citing this ADR.

**D3.** A named track that is not in D1 gets its id by amending D1 (one alternative per id). It does not get a
generic upper-case pattern: a closed list keeps a mistyped id (`FO`, `MGS`) from passing as a package.

## Rejected alternatives

- *An alias for F0 (an `S`/`T` id), as R-565 and R-878 did.* It works for F0, but every later roadmap package
  would need the same alias. See *What changed*.
- *A generic shape (`^[A-Z][A-Za-z0-9]{1,7}$`).* It is simpler, but it admits `L01`, `C9` and typos. That reopens
  R-565's ambiguity objection, and it gives up the only check that a manifest names a package family.
- *Widening the ledger and model-manifest patterns too.* No package needs them yet. Freezing more surface than the
  blocker requires is what R-565 warned against.

## Acceptance evidence (the build lane records it)

1. `tests/test_evidence_manifests.py` passes, every committed manifest unchanged and F0's added.
2. A unit check that the new pattern accepts every id matching the old one (an exhaustive enumeration is cheap:
   6 × 100 × 27) and accepts `F0`, `X07a`, `MSG`, `PrISMa`, while it refuses `L01`, `C9`, `E01`, `W1`, `FB-04`, `f0`, `F10`.
3. No other file changes in the commit.
