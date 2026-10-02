# Brief — ADR 0002: canonicalization and schema encoding

**To:** `fable-specifier`. **From:** the Opus 5 session, 2026-09-18. **Branch:** `wp/K02`.
**Authority:** plan §4.1 "Phase-0 ADRs" (0002 canonicalization and schemas); blueprint §4.3 line 152.

## 1. The question

**What is the canonical form of this project's data, and what exactly does an identity hash cover?**
Decision-shaped, in four parts:

1. **Ratify or replace the identity-hash encoding** that is already implemented and in use.
2. **State what the digest does not cover**, which is currently a latent hole (§4 below).
3. **Fix the canonical form of a serialized document** — number representation, key ordering, unit
   normalization, signed zero, what is excluded from a physical-model hash.
4. **State the migration rule**: what counts as a schema change and what a migration must produce.

## 2. Why this needs Fable

Every ADR is Fable's (plan §1.3). Beyond that: this is the document replay identity rests on, and
requirement D20 ("Separate deterministic structural artifacts from adaptive numerical decisions and
timing") and gate **R0 Structural** ("Same canonical model and structural policy yield identical
structural artifacts on supported platforms") both depend on it being right. The hole in §4 is the
kind that is invisible until two problems collide.

**The cheap moment is now.** Nothing is released. Changing the encoding today regenerates fixtures;
after K04/K05 store digests in replay bundles it is a migration.

## 3. What is already decided, and not open to you

- **Blueprint §4.3 line 152 is the requirement being satisfied**, verbatim: *"Provide readable YAML
  and normative JSON Schema, with canonical JSON for hashes. Define numeric representation, stable
  ID ordering, unit normalization, and handling of signed zero. Reject nonfinite numbers in semantic
  inputs; missing values have explicit states. Presentation metadata, timestamps, and layout are
  outside the physical-model hash."*
- **ADR 0001 D1.5**: nonfinite numbers are rejected in every semantic input; signed zero is
  normalized to +0.0 in canonical form.
- **ADR 0008 D2**: `state_sha256` covers exactly the dense `x`, in `variable_ids` order, after
  signed-zero normalization, **and nothing else**. D2.6 forbids quantizing state coordinates on the
  exact path — a hash invariant under a one-ulp change is a quantized hash.
- **ADR 0008 D4.1**: `constants_sha256` covers the complete pinned-input vector — physical
  constants, model parameters *and* specification values — in `parameter_ids` order.
- **Decision register R-006, ratified by Frank on 2026-09-18**: the identity encoding is **SHA-256
  over big-endian IEEE-754 binary64 bytes**, signed zero normalized, `ENCODING_ID =
  "ieee754-be-v1"`. Implemented in `src/process_runtime/canonical.py`. The rejected alternative was
  the P02 specification §10.4 text form (`%.17g`, comma-joined), on the grounds that `%g` is C's and
  its stripping, exponent width and nan/inf spellings are not fixed across languages, so a text
  digest makes replay identity depend on how one C library prints a double. Measured 30–38× faster
  as well, recorded as the weaker argument. **You may state that R-006 was wrong and say why — but
  it is a ratification question, not an open design question, and reversing it needs the same
  standard of evidence R-006 met.**
- **The schemas K01 promoted** (`compiled-problem-metadata`, `evaluation-result`,
  `jacobian-result`) and their cross-field rules in `process_runtime.serialize`. The plan's rule
  stands: a schema is added when its object is used, not in advance.
- **JSON Schema draft 2020-12 under `schemas/`, with round-trip fixtures** under
  `tests/fixtures/schemas/` (`docs/interfaces-frozen.md` line 49).

## 4. What is genuinely open — and the hole that prompted this

**4.1 The anonymity hole.** The digest is of the **anonymous ordered vector of values**. The names in
`order` choose which values participate and in what sequence, but **no name is hashed**. So:

> `constants_sha256` identifies a pinned-input vector only in combination with a `model_version`
> that pins `parameter_ids`, and `state_sha256` likewise with `variable_ids`.

**Nothing currently enforces that.** Two problems with the same `model_version`, different
`parameter_ids`, and coincidentally equal value vectors would be indistinguishable by
`(model_version, constants_sha256)` — the pair the whole boundary uses for identity. Found by the
Fable review of K01. **What must `model_version` be required to pin, and who enforces it?** Options
include hashing the names into the digest, requiring a structure digest in metadata, or stating the
obligation normatively and testing it at compile time. I have no preference; I have not implemented
any of them.

**4.2 Canonical document form.** Number representation in serialized JSON/YAML, key ordering, how a
`Quantity` is normalized before hashing, and — blueprint's words — what is *outside* the
physical-model hash (presentation metadata, timestamps, layout). Today the evidence manifests use
`json.dumps(..., indent=2, sort_keys=True, allow_nan=False)` and the directory-hash method
`sha256` over `path\0sha256\n` per file sorted by path. Those are conventions in code, not policy.

**4.3 The migration rule.** `docs/interfaces-frozen.md` says a schema changes only with a real
migration and migration report, and ADR 0008 is the one worked example (its C3–C5). Generalize it.

**4.4 Whether `ENCODING_ID` should travel in documents.** It is currently recorded only in evidence
manifests, not in any metadata document or schema. K01's promotion window is closed, so adding a
`hash_encoding` field to `CompiledProblemMetadata` later is itself a migration. Decide now: require
it, or state that the encoding is pinned globally by this ADR and a document needs no field.

## 5. Already tried and rejected, with the evidence

- **`%.17g` text** — implemented, used for all of P02 and the first half of K01, then replaced.
  See R-006. Do not re-propose it without addressing the portability argument.
- **Refactoring the two legacy implementations** (`spikes/p02/common/export.py`,
  `benchmarks/p02/judge.py`) to share one function — rejected, because the judge's was written
  separately so that a harness cannot certify its own hash, and collapsing them destroys the
  property that makes them evidence. They are retained and still tested for agreement.
- **Quantizing state coordinates for cache keys** — forbidden by ADR 0008 D2.6 and blueprint §6.4,
  which is normative and settled. Do not reopen; it is quoted here only so you do not rediscover it.

## 6. How the answer will be verified

`PATH=.venv/bin:$PATH ./scripts/check.sh`, green at **645 tests**. ADR 0008 D2's rules H1–H6 are
already pinned against both the production and the legacy implementations. Any rule you add should
name the test that discharges it, in the style ADR 0008 D4 uses.

## 7. Deliverable

`docs/adr/0002-canonicalization-and-schemas.md`, in the house form of ADR 0001 and ADR 0008: status,
context, numbered normative decisions, consequences, what this does not establish, open questions
with recommended defaults, and a "changing this ADR" clause.

It must at minimum: ratify or replace R-006 with reasons; close the §4.1 anonymity hole with a named
mechanism and the test that discharges it; fix canonical document form per blueprint line 152; state
the migration rule; and rule on §4.4.

In your report to me, give the decision-register entry for R-A02 in the form
`docs/decision-register.md` already uses, and name any obligation you place on a later package.

## 8. Out of scope

Do not write production code or edit any file other than the ADR. Do not reopen the backend
selection (ADR 0003), the distribution policy (ADR 0006) or ADR 0008's D1–D3. Do not design schemas
for objects that do not exist yet. Do not set `reviewed` in any manifest.
