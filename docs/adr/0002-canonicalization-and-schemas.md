# ADR 0002 — Canonicalization and schema encoding: vector identity, structural identity, canonical JSON, the physical-model hash, and the migration rule

**Status:** Proposed by Fable 5.1 on 2026-09-18 (brief `docs/briefs/ADR-0002-canonicalization.md`); ratifies decision register R-006 (Frank Peters, 2026-09-18) and closes the anonymity hole R-006 names. In force once the Opus session applies "Consequences" C1–C10 on `wp/K02` and `PATH=.venv/bin:$PATH ./scripts/check.sh` passes with the assertions listed under "Acceptance evidence". Registered as R-A02.  
**Amended 2026-09-27 (Amendment 1)** — which integers are canonical: the D3.3 refusal of every integer beyond 2^53 contradicted D3.3's own spelling of integral binary64 values above 2^53, so the writer's output was refused on reading. Design lane (`specifier`), on the T07 build lane's W7c finding. The one changed passage, in D3.3, is struck and marked **Amended (Amendment 1)**; the section "Amendment 1" at the end has the decision, the evidence and assertions J10–J17.  
**Date:** 2026-09-18  
**Author:** Fable 5.1 (Fable owns every ADR and every change to the P01 interface freeze, plan §1.3)  
**Affected requirements:** D20 (deterministic structural artifacts separated from adaptive numerical decisions — the structural identity of D2 is the first such artifact), D10 (exact property cache keys on exact canonical numerical inputs — D1 fixes what "exact canonical" means for a vector of doubles), D02 (the compiled-problem boundary carries the identities defined here), gate R0 Structural (same canonical model ⇒ identical structural artifacts), blueprint §3.2 ("a structural fingerprint" at the minimum interface), §4.1 (ProcessRevision "semantic content hash"), §4.4 (serialization and identity, verbatim requirement at line 152), §6.4, §8.3.  
**Affected packages:** K02 (applies this ADR: the migration in "Consequences"), K03 (contexts and caches key on the identities defined here), K04/K05 (replay bundles store the digests and record the encoding identifiers, D6), K06 (`ProcessRevision.content_hash`, D4), T01 (structure document v2 when manifests feed the compiler, D2.7), T08 (release-time refresh of the identifier table), and every package that writes a document under `schemas/`. ADR 0007 inherits D1–D6 as constraints.  
**Blueprint authority:** §4.4 line 152 is the requirement being satisfied, verbatim: *"Provide readable YAML and normative JSON Schema, with canonical JSON for hashes. Define numeric representation, stable ID ordering, unit normalization, and handling of signed zero. Reject nonfinite numbers in semantic inputs; missing values have explicit states. Presentation metadata, timestamps, and layout are outside the physical-model hash."* Also §4.4 line 154 ("Separate schema, structure, numerical model, solve-policy, and full run fingerprints"), §3.2 line 105 ("a structural fingerprint"), §6.4 line 230 (the exact property key; quantization forbidden), §8.3 (hashes exclude timestamps, job IDs, telemetry).

## Context

Three identities exist in the repository today and none has a normative text.

1. **Vector identity.** `state_sha256` and `constants_sha256` are computed by `src/process_runtime/canonical.py` as SHA-256 over the big-endian IEEE-754 binary64 bytes of an ordered vector of doubles, signed zero normalized, under `ENCODING_ID = "ieee754-be-v1"`. Frank ratified that encoding on 2026-09-18 (register R-006) on the Fable review of K01, replacing the P02 §10.4 `%.17g` text form. ADR 0008 D2 fixes what `state_sha256` *covers* (exactly the dense `x`, in `variable_ids` order, nothing else) and D4.1 what `constants_sha256` covers (the complete pinned-input vector, in `parameter_ids` order). Neither ADR fixes the encoding; R-006 says ADR 0002 must.

2. **Structural identity — the hole.** The digest is of the *anonymous ordered vector of values*. The names in `parameter_ids` choose which values participate and in what sequence, but no name is hashed. The pair (`model_version`, `constants_sha256`) is what the whole `CompiledProblem` boundary uses to identify a problem (`docs/interfaces-frozen.md` §1; `EvaluationContext`; `check_pairing`), and it identifies one only if `model_version` pins `parameter_ids`. Today `model_version` is a free string supplied by whoever builds a `ProblemSpec` (`benchmarks/k01/syn001.py:315`: `f"SYN-001-{form}-1"`); nothing checks that two problems sharing it share a structure. Two problems with the same label, different `parameter_ids` and coincidentally equal value vectors are indistinguishable — and "coincidentally equal" is not rare when two parameters are swapped, which is exactly the permutation error a fingerprint should catch. The blueprint already asks for the missing object: §3.2 puts "a structural fingerprint" at the minimum interface and §4.4 separates the *structure* fingerprint from the *numerical model* one. K01's `CompiledProblemMetadata` has no such field; `model_version` was standing in for it without the property that makes a fingerprint one.

3. **Document identity.** `ProcessRevision.content_hash` is declared in the P01 schema as "absent until ADR 0002 fixes the encoding". Evidence manifests are written with `json.dumps(indent=2)`; the round-trip tests use `json.dumps(sort_keys=True, allow_nan=False)`; directory hashes are `sha256` over `path\0sha256\n` per file "sorted by path". Those are conventions in code. A rule defined as "what Python emits" is the `%.17g` mistake again: `json.dumps` spells `1e16` as `1e+16`, `1e-7` as `1e-07`, `1.0` as `1.0` and `1` as `1`, sorts keys by code point rather than by the order any other canonicalization standard uses, and `sorted(Path)` orders `a/b` before `a-c` where a byte sort orders them the other way (measured, D5.2).

This ADR fixes all three, states what each identity does *not* cover, rules on whether encoding identifiers travel in documents (brief §4.4), and generalizes the migration rule ADR 0008 exercised once.

**What did not change and is not reopened.** ADR 0008 D1–D3 (no time at the boundary; `state_sha256` coverage; accumulation declarations) are inherited verbatim. ADR 0001 D1.5 (nonfinite rejected in semantic inputs; signed zero normalized to +0.0) is inherited verbatim. Blueprint §6.4's prohibition on quantizing state coordinates on the exact path is normative and settled; it is quoted only so that nobody rediscovers it. The backend (ADR 0003) and distribution policy (ADR 0006) are untouched.

## Decision

### D1. Vector identity: R-006 is ratified (the encoding of `state_sha256` and `constants_sha256`)

1. **The encoding, exactly.** For an ordered vector `(v_1, …, v_n)` of IEEE-754 binary64 values: for each `v_i` in order, if `v_i == 0.0` replace it by `+0.0`; write the eight bytes of its binary64 representation in big-endian byte order (sign bit first); concatenate the `8n` bytes; the digest is SHA-256 of that byte string, rendered as 64 lowercase hexadecimal characters. Nothing else is hashed: no length prefix, no separator, no name, no encoding tag. The empty vector hashes to the SHA-256 of the empty string. `ENCODING_ID = "ieee754-be-v1"` names this encoding and does not change.
2. **Why bytes, not text (R-006's reasons, ratified).** (i) A text encoding puts a formatter inside replay identity; `%g` is C's, its trailing-zero stripping, exponent width and nan/inf spellings are not fixed across languages, and a replay bundle whose identity depends on one C library's printing of a double is portable only by luck. The byte form *is* the value. (ii) It is 30–38× faster measured (48.3 ms vs 1.6 ms at n = 1e5), recorded as the weaker argument because the release horizon's flowsheets are tens to low hundreds of variables. R-006 met the standard for reversing a fixed convention; this ADR finds nothing that would reverse it back. The P02 §10.4 text form is retained as `LEGACY_ENCODING_ID = "p02-10.4"` for the evidence about `spikes/p02/results/` and for nothing else (brief §5).
3. **Properties the encoding has, all pinned by tests already in the gate.** Injective over finite doubles; every coordinate participates at full precision, so a hash invariant under a one-ulp change of any coordinate is a quantized hash and is forbidden (ADR 0008 D2.6, blueprint §6.4); order participates; length participates; signed zero does not; keys outside the ordering never reach the hash; the dense (array) and mapping forms agree. Tests: ADR 0008 H1–H6 run against this encoding (`tests/test_adr_0008_transient_readiness.py`) and `tests/test_canonical.py`.
4. **One primitive, two uses.** `state_sha256(x, variable_ids)` and `constants_sha256(values, parameter_ids)` are the *same* operation over different named vectors (`hash_named_doubles`). They must not become two implementations; drift between them would be drift between what identifies a state and what identifies the problem it is a state of. Pinned by `test_constants_sha256_is_the_same_primitive_over_a_different_named_vector`.
5. **Coverage, restated from the ADRs that own it, with the name kept.** `state_sha256` covers exactly the dense `x` as passed, in `variable_ids` order, and nothing else (ADR 0008 D2). `constants_sha256` covers the complete pinned-input vector of the compiled-problem *instance* — physical constants, model parameters and specification values, including the current value of a time-varying specification — in `parameter_ids` order (ADR 0008 D4.1). ADR 0008 Q3 asked whether `constants_sha256` should be renamed now that it covers specification values; **it is not renamed**: the frozen result types echo it and a rename is a migration for a cosmetic gain. The widened coverage is recorded here.
6. **Non-finite values.** The encoding does not reject them: a trial state containing NaN or ±∞ is a legitimate input to `residual`, is reported `invalid_trial_state` by the evaluator, and still needs a `state_sha256` to be echoed. NaN payloads are *not* normalized (the text form collided them; the byte form distinguishes them). This is recorded and not load-bearing: a state containing a NaN is never reported `ok`, so its identity is never compared against anything. No test pins payload distinction and none may claim it as a rule. Semantic *inputs* (documents) are a different matter: D3.4 rejects non-finite numbers there, as ADR 0001 D1.5 requires.
7. **What the vector digest does not cover — stated as R-006 demanded.** No name is hashed. `constants_sha256` identifies a pinned-input vector only together with a `model_version` that pins `parameter_ids`; `state_sha256` likewise with `variable_ids`. D2 is the mechanism that makes `model_version` do that.
8. **Registered sanity vectors (assertion E1).** Computed from the specification in D1.1 with `struct.pack(">d")` and `hashlib.sha256`, independently of `process_runtime.canonical`; the test recomputes them the same way and compares both to this table and to the production functions.

   | Vector | Bytes (hex) | SHA-256 |
   | --- | --- | --- |
   | `()` | (none) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
   | `(1.0)` | `3ff0000000000000` | `54ade53a579f5389ecae3af42df9e96aa30fcf3fc02a7475afc18c3e4835f6f7` |
   | `(0.0)` and `(-0.0)` | `0000000000000000` | `af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc` |
   | `(1.0, 2.0)` | `3ff0000000000000 4000000000000000` | `f814737da80b11b6d6e54c254b9d7e711669462c0e53585f776afea6ea073afc` |
   | `(2.0, 1.0)` | `4000000000000000 3ff0000000000000` | `c842ab7cdc458e6cbffc7badbfd5a964b97139955d0c48ea5797061380dad0cf` |
   | `(5e-324)` | `0000000000000001` | `cd2662154e6d76b2b2b92e70c0cac3ccf534f9b74eb5b89819ec509083d00a50` |
   | `(0.1 + 0.2, 0.3)` | `3fd3333333333334 3fd3333333333333` | `d6999972a2f4872fde4c6bbdd100f2df5d970e6c317d3b843c244d06f7d7b2ca` |
   | `(360.0, 100000.0)` | `4076800000000000 40f86a0000000000` | `e0383cfde9a3a6a74e5385c0b68353ecb7f87bb19d8f3dd786cf78bb39799a40` |

   Why these: the empty vector pins the "no prefix, no length" rule; `(1.0)` pins byte order (the sign-and-exponent byte comes first); the two zeros pin normalization *at* the value where it acts; the two-element pair and its transpose pin order; the smallest subnormal pins that one ulp from zero registers; `0.1 + 0.2` next to `0.3` pins that a value whose 15-digit decimal form is `0.3` does not collide with `0.3`; `(360.0, 100000.0)` is the value vector of the anonymity example in D2.6 and is registered *because* two differently named problems share it.

### D2. Structural identity: `model_version` pins the name-level structure (closes the anonymity hole)

1. **The structure document.** For a compiled problem, the *structure document* is the JSON object with exactly these five members and no others:

   | Member | Value |
   | --- | --- |
   | `structure_schema` | the string `"compiled-problem-structure-v1"` |
   | `variable_ids` | `CompiledProblemMetadata.variable_ids`, in order |
   | `equation_ids` | `CompiledProblemMetadata.equation_ids`, in order |
   | `parameter_ids` | `CompiledProblemMetadata.parameter_ids`, in order |
   | `row_accumulation` | `CompiledProblemMetadata.row_accumulation`, as an object keyed by equation id |

   Scales, capabilities, backend and backend version are **not** members: scales are numerical policy (K03), capabilities and backend are properties of the compilation, and blueprint §4.4 keeps the structure fingerprint separate from those tiers. Two problems compiled by different backends from the same structure share a structure digest and are told apart by the `backend`/`backend_version` fields, as they should be: they describe the same function.
2. **The structure digest.** `structure_sha256` is the SHA-256, lowercase hex, of the canonical JSON bytes (D3) of the structure document. The document contains no numbers, so only D3's key ordering, string escaping and whitespace rules act on it.
3. **`model_version` is `<label>@<structure_sha256>`.** Normatively: `model_version` matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}@[0-9a-f]{64}$`, and the 64 hex characters after `@` equal the structure digest of the problem the field belongs to. The label is the human-readable name of the *function family* (for SYN-001: `SYN-001-L-1`, `SYN-001-I-1`, unchanged from K01). The label is not inside the digest: the digest is a pure name-level structural fingerprint, and two labels over the same structure share a suffix, which is informative rather than harmful. Consumers compare `model_version` as a whole string, exactly as they do today.
4. **Why the digest lives inside `model_version` rather than in a new field.** Every consumer that identifies a problem by (`model_version`, `constants_sha256`) — the context check in the backend, `check_pairing`, K03's caches, K04/K05's replay bundles — now keys on structure without any of them being told to, and ADR 0008 D2.4's pairing identity (`model_version`, `constants_sha256`, `state_sha256`, `phase_signature`; "no other field participates") is untouched in field set and strengthened in meaning. A separate `structure_sha256` field would either have to be added to the two frozen result types and to the pairing rule — reopening ADR 0008 D2.4, which the brief forbids — or would depend on a prose obligation that `model_version` pins it, which is the hole restated. The alternatives are in "Alternatives considered".
5. **The compiler assigns it.** A `ProblemSpec` supplies the *label*; `compile_problem` computes the structure digest from the spec and assigns `model_version`. A spec is not trusted to supply the digest. Whether `ProblemSpec.model_version` is renamed to `label` is Opus's choice (C3); its semantics are fixed here.
6. **The hole, made visible and closed (assertion S2).** Two specs, both labelled `HOLE`, with `parameter_ids = ("t_spec", "p_spec")`, `parameters = {t_spec: 360.0, p_spec: 100000.0}` and `parameter_ids = ("p_spec", "t_spec")`, `parameters = {p_spec: 360.0, t_spec: 100000.0}`. Their ordered value vectors are byte-identical, so their `constants_sha256` are **equal** (`e0383cfd…9a40`, D1.8) — the test asserts the equality, because that equality *is* the hole and must stay visible. Under D2.3 their `model_version` strings differ, so the pair (`model_version`, `constants_sha256`) differs. The same test permutes `variable_ids` and changes one `row_accumulation` kind, each of which must also change `model_version`.
7. **What the name-level digest does not cover, and who covers it.** Two problems with the same label and identical ids whose equation *expressions* differ (a sign flip in one row, a dropped term) share a structure digest. The label is the only thing separating them, and the obligation is on whatever assigns the label: **the label must change whenever the equation set changes**. For K01's hand-written `benchmarks/k01/syn001.py` this is a code-review obligation and is recorded as such. It becomes executable when a compiled problem is first assembled from `ModelManifest` and `ProcessRevision` documents rather than from Python: that package (T01 on the current plan; K06 if the revision compiler lands there first) introduces `"compiled-problem-structure-v2"` by migration (D7), adding a `sources` member that lists the content hashes (D4) of the contributing manifests and of the revision, so that expression identity is pinned by content and not by a label. Until then the label carries it and this ADR says so rather than pretending otherwise. The Jacobian sparsity pattern is likewise not in v1: it is a property of the compiled function, obtained from the backend, and blueprint §4.4's "compatible structural pattern" test for sparsity reuse is ADR 0007's to define over the pattern K01 already reports with `pattern_provenance`.
8. **Registered values (assertions S1, S6).** The small structure document

   ```
   {"equation_ids":["bal_A","eq_A","tspec"],"parameter_ids":["feed_A","t_spec"],"row_accumulation":{"bal_A":"holdup_balance","eq_A":"algebraic","tspec":"algebraic"},"structure_schema":"compiled-problem-structure-v1","variable_ids":["T","l_A","v_A"]}
   ```

   is 246 bytes and has `structure_sha256 = 690d754282fe59dc63ee7bd85a80329dd95623c4c264683ca42edb09d2335aa4`. With `parameter_ids` permuted to `["t_spec","feed_A"]` the digest is `edbbcf2d23abc0ee4d6a4ef7dc4e36ab95bbd9be7a22b1f83d195c5ff1582200`; with `bal_A` reclassified `algebraic` it is `50e8d3b8e1adddaf88480ffdb596dbe7d58cc65dda9009059c94221d12ab00c2`. The K01 SYN-001 lifted-form structure document, assembled from the five fields of `tests/fixtures/schemas/compiled_problem_metadata/valid/syn001_lifted.json` at commit `51f033b`, is 760 bytes, begins `{"equation_ids":["bal_A","bal_B","bal_C","Vdef","Ldef",`, and has digest `8e5930fc737e8e0b033a2fe35d06971c6cf911df2db5d9731e050cf1cb6fb98a`, so the regenerated fixture's `model_version` is exactly

   ```
   SYN-001-L-1@8e5930fc737e8e0b033a2fe35d06971c6cf911df2db5d9731e050cf1cb6fb98a
   ```

   Provenance of every digest in this section: a scratch implementation of D3 written for this ADR, independent of `process_runtime`, applied to the documents as written. The inlined form has no fixture and no registered digest; S6 checks it for self-consistency only (the compiled metadata's `model_version` suffix equals a recomputation from that metadata's own fields), which is a consistency check and is labelled as such.
9. **Cross-field rule.** `process_runtime.serialize.check_metadata_document` recomputes the structure digest from the document's own `variable_ids`, `equation_ids`, `parameter_ids` and `row_accumulation`, parses the label and digest out of `model_version`, and rejects a mismatch (assertion S4). `EvaluationResult` and `JacobianResult` documents carry no id lists from which to recompute, so for them the schema pattern of D2.3 is the whole check. The K05 second-platform gate (R0) compares `model_version` strings byte-for-byte across platforms; a difference there is a structural nondeterminism, never a tolerance question.

### D3. Canonical JSON for documents: RFC 8785 (JCS)

1. **Scope.** Canonical JSON is the byte form over which a *document* digest is computed: `structure_sha256` (D2), `ProcessRevision.content_hash` (D4), and every later document digest (ADR 0007's manifests and certificates). It is not a storage format: files under `schemas/`, `tests/fixtures/`, `evidence/` and user data may be YAML or JSON in any readable layout; the digest is of the canonical form of the *parsed* document. A numeric *vector* is never hashed through canonical JSON — its identity is D1's, and a document that needs to refer to a vector carries the vector's D1 digest or a hashed binary artifact (D5), never a re-spelling of the floats. `DOCUMENT_ENCODING_ID = "jcs-rfc8785-v1"` names this form.
2. **The rule is RFC 8785, the JSON Canonicalization Scheme, adopted whole.** Stated here so that this ADR is self-contained; where this text and the RFC differ, the RFC's normative text wins and the difference is a defect in this ADR to be amended. The output is UTF-8 with no byte-order mark and no whitespace outside strings. Objects are `{`, members as `"key":value` joined by `,`, `}`; arrays `[`, elements joined by `,`, `]`; literals `null`, `true`, `false`. **Members are sorted by the UTF-16 code units of the key** (RFC 8785 §3.2.3), which is lexicographic order of the key's UTF-16BE encoding. This differs from code-point order only when a key contains a character outside the Basic Multilingual Plane; because it differs, `json.dumps(sort_keys=True)` is *not* an implementation of this rule and the in-repo serializer sorts with the key `key.encode("utf-16-be")` (assertion J3 registers a document on which the two orders disagree). Arrays are never reordered: array order is semantic wherever a schema does not say otherwise, and no schema today says otherwise (`component_set.components` order *is* the component order, ADR 0001 D2.1). Duplicate keys do not exist in the canonical form and a document containing them is rejected on reading (D3.6).
3. **Numbers.** Every JSON number is an IEEE-754 binary64 value. Its canonical spelling is the ECMA-262 `Number::toString` of that value (RFC 8785 §3.2.2.3), which is: for zero of either sign, `0`; otherwise let `s`, `k`, `n` be integers with `k ≥ 1`, `10^(k−1) ≤ s < 10^k`, such that the double nearest to `s·10^(n−k)` is the value, `k` as small as possible, and among candidates of minimal `k` the one whose `s·10^(n−k)` is closest to the exact value (an even `s` on a tie); write `D` for the `k` decimal digits of `s`; then (a) if `k ≤ n ≤ 21`: `D` followed by `n−k` zeros; (b) if `0 < n ≤ 21`: the first `n` digits of `D`, `.`, the remaining digits; (c) if `−6 < n ≤ 0`: `0.`, `−n` zeros, `D`; (d) otherwise, if `k = 1`: `D`, `e`, `+` or `-`, the decimal digits of `|n−1|`; (e) otherwise: the first digit of `D`, `.`, the remaining digits, `e`, sign, `|n−1|`; a negative value takes a leading `-`. Consequences worth stating: `1.0`, `1` and `1e0` all canonicalize to `1`; `-0.0` to `0` (this is the canonical-form half of ADR 0001 D1.5); `1e21` to `1e+21` but `1e20` to `100000000000000000000`; `1e-7` to `1e-7` but `1e-6` to `0.000001`; an integral double above 2^53 is spelled with its *shortest round-trip digits padded with zeros*, not with its exact decimal expansion (2^68 is `295147905179352830000`). ~~An integer whose magnitude exceeds 2^53 is not canonicalizable and is refused with an explicit error, never rounded.~~ **Amended (Amendment 1, 2026-09-27):** an integer `n` is canonicalizable exactly when its decimal digits are the canonical spelling of the binary64 nearest to `n` (always, for `|n| ≤ 2^53`; for `2^53 < |n| < 10^21`, for exactly one integer per binary64, the one this rule spells; never, for `|n| ≥ 10^21`); it is then written as those digits. Any other integer is refused with an explicit error, never rounded. `process_runtime.canonical.integer_binary64` is the one implementation. The digit string `D` is what Python's `repr(float)` produces (shortest round-trip, closest on ties); only the layout differs, and the layout is the five cases above. Assertion J1 registers the vectors; open question Q1 records what is and is not established about the digit selection.
4. **Non-finite numbers.** NaN and ±∞ have no canonical spelling. A canonicalizer asked to serialize one raises; a reader that decodes one from a semantic document rejects the document (ADR 0001 D1.5; `process_runtime.units.check_quantity` already does this for `Quantity`). There is no path on which a non-finite value reaches a document digest.
5. **Strings.** UTF-8 of the code points, escaping exactly: `"` as `\"`, `\` as `\\`, U+0008 `\b`, U+000C `\f`, U+000A `\n`, U+000D `\r`, U+0009 `\t`, every other control character U+0000–U+001F as `\u` followed by four lowercase hex digits; nothing else is escaped — not `/`, not U+007F, not U+2028/U+2029, not any non-ASCII character. No Unicode normalization is applied to keys or values: `e` + U+0301 and U+00E9 are different strings and both are retained (assertion J8). Whether two ids that differ only in normalization form should be *admitted* by validation is a confusables question for the schema layer and is not decided here.
6. **The JSON data model, and what YAML may contribute to it.** A semantic document is a tree of `null`, booleans, numbers, strings, arrays and objects with string keys. A YAML source is loaded with `yaml.safe_load` and its result must lie in that model: a node that decodes to a date, a timestamp, a set, binary data, or a non-string key is rejected before canonicalization (a timestamp is written as a quoted string, as every P01 fixture already does). YAML `1` and `1.0` decode to different Python types and canonicalize to the same bytes by D3.3, which is the reason the number rule is value-based rather than type-based. A JSON or YAML source with a duplicated key is rejected (`json.loads` silently keeps the last value; the reader uses `object_pairs_hook` to refuse). A boolean is never a number: `true` and `1` are different values.
7. **Sizes.** Canonical form has no length limit of its own; blueprint §4.4 says large arrays and binaries are stored as hashed artifacts (D5), and a document that would embed a numeric array of more than a few hundred elements is mis-designed rather than canonicalized slowly.
8. **Implementation.** One function, `process_runtime.canonical.canonical_json(document) -> bytes`, written in the repository (about a hundred lines: a recursive serializer, the number layout of D3.3 over `repr`, the escaping of D3.5, the sort key of D3.2), with no new dependency. `json.dumps` with any options is not an acceptable implementation (D3.2, D3.3). The registered vectors of J1–J8 pin it; if an independent implementation of RFC 8785 is later present in the pinned environment, cross-checking against it is welcome evidence and not a requirement.

### D4. The physical-model hash: what a `ProcessRevision.content_hash` covers and what it excludes

1. **Definition.** `content_hash` is the SHA-256, lowercase hex, of the canonical JSON (D3) of the revision document *after removing* the members in D4.2. It is the "semantic content hash" of blueprint §4.1's ProcessRevision row and the **structure-and-specification tier** of §4.4's five fingerprints.
2. **Excluded members — a closed list.** At the top level: `content_hash`, `revision_id`, `parent_revision`. At any depth: `provenance` (and everything inside it — actor, operation, timestamp, source references, artifact hashes), `title`, `description`, `notes`, `meaning`, `display_unit`, `uncertainty_ref`, `initialization_hint`, and `record_source`. Everything not on this list participates, including `schema_version`, `component_set.components` in order, every instance with its `id`, `model` (id, version, artifact_ref), `semantic_role`, `parameters` and `policy`, every connection with its endpoints, kind, state definition, component mapping and phase capability, and every specification with its value or bounds, unit, dimension, kind, role, `bounds` and `nominal`. Reasons for the borderline members: `initialization_hint` is a labelled guess and never a constraint (ADR 0001 D3.1), so it is initialization policy, not model; `record_source` is a file location, and moving a file is not a change to the process; `nominal` is a registered physical value that the blueprint places at the minimum interface, so a changed nominal is a changed revision — a session wanting to experiment with scales does so in a `SolvePolicy`, not by editing nominals.
3. **Unit normalization.** A `Quantity` participates through `value`, `unit`, `dimension`, `kind`, `role`, `bounds` and `nominal`. Its `value` is already in the registered unprefixed SI unit of its `kind` (ADR 0001 D1.1) — validation rejects any other `unit` — and any conversion from a display or mass basis happened at validation time and is recorded in provenance (ADR 0001 D1.4), which is outside the hash. So "unit normalization before hashing" is the identity on a valid document, and a document with a non-SI `unit` is not canonicalizable because it is not valid. Signed zero: canonical form spells `-0.0` as `0` (D3.3), and a *stored* semantic document is additionally required to be in canonical value form, so `check_quantity`'s rejection of a stored `-0.0` stands; both rules hold and neither contradicts ADR 0001 D1.5.
4. **What `content_hash` does not cover.** The contents of the referenced `ComponentRecord`s (their molecular weights and parameters), the `ModelManifest`s of the instantiated models, and the property provider's implementation and data. Blueprint §4.4 says units, model parameters, reference states and source-data versions "affect numerical identity"; that is the *numerical model* fingerprint, which combines this content hash with the D4 content hashes of the records and manifests and the provider hashes of ADR 0001 D5.2, and is ADR 0007's to define. Two revisions that reference different record files with the same component ids share a `content_hash` and differ at the numerical-model tier; a reader that treats `content_hash` as a numerical identity has misread this ADR.
5. **Semantic equivalence is not byte identity.** Permuting the `instances` array changes `content_hash` (blueprint §4.4: "Cross-component permutations may change byte identity while still passing a semantic equivalence test"). This ADR defines the byte identity only; the equivalence test is a validation capability for a later package and is not established here.
6. **Obligation and timing.** A revision document *may* carry `content_hash` from the moment C4 lands, and if it carries one it must verify (assertion R2); K06, which first writes revisions, computes it on every commit and makes it required for revisions it writes (open question Q3). The fabricated-hash fixture from P01 stays as it is; a second fixture with a well-formed but wrong digest is added (C6).
7. **Registered vector (assertion R1).** The revision-shaped document (schema-valid) with `schema_version: 1`, `revision_id: "r1"`, `parent_revision: null`, `content_hash: null`, `title: "t"`, `component_set: {record_source: "x.yaml", components: ["A", "B"]}`, one instance `feed` (`model: {id: "m", version: "1", artifact_ref: null}`, `semantic_role: "feed"`, one parameter `F` — a `molar_flow` Quantity of value `1.5`, unit `mol/s`, dimension `[0,0,-1,0,1,0,0]`, meaning `"feed"`, role `fixed`, display unit `kmol/h` — `policy: {fidelity: "boundary", validity: "d"}`), empty `connections` and `specifications`, and `provenance: {actor: "a", operation: "create", timestamp: "2026-09-18T00:00:00Z"}` has the 362-byte hashed form

   ```
   {"component_set":{"components":["A","B"]},"connections":[],"instances":[{"id":"feed","model":{"artifact_ref":null,"id":"m","version":"1"},"parameters":{"F":{"dimension":[0,0,-1,0,1,0,0],"kind":"molar_flow","role":"fixed","unit":"mol/s","value":1.5}},"policy":{"fidelity":"boundary","validity":"d"},"semantic_role":"feed"}],"schema_version":1,"specifications":[]}
   ```

   and `content_hash = 21f5ca935d7b43ec2676bb6a7081d0fec6ad221346955c02768d3de893a6d58e`. Changing `F.value` by one ulp (to `math.nextafter(1.5, 2.0)`) gives `8eb480e7b1f1ee1e255d84c0a6743c70c9b0c3f3638dcee07c3351d17aef0615`; changing the timestamp to `2030-01-01T00:00:00Z`, the title to `"other"` and the display unit to `mol/s` all at once leaves it at `21f5ca93…d58e`. The document is registered *because* it has one excluded member of every kind that exists at that depth and one included value that a one-ulp change must move.

### D5. Artifact and directory identity

1. **File.** The identity of an artifact — a lock file, a reference-values YAML, a results JSON, a wheel — is the SHA-256 of its bytes as stored. Not its canonical form: an artifact is evidence about what was on disk, and reformatting it is a change to the evidence. `case_hash`, `environment_lock_hash` and every `artifacts[].sha256` in an evidence manifest are of this kind.
2. **Directory.** The identity of a directory of artifacts is the SHA-256 of the concatenation, over the regular files under it, of `<relative POSIX path as UTF-8> 0x00 <64 lowercase hex SHA-256 of the file> 0x0A`, **with the files ordered by the UTF-8 bytes of their relative POSIX path**. `DIRECTORY_HASH_ID = "dirhash-v1"`. This is the method `scripts/k01_evidence_manifest.py:directory_hash` already uses, with the ordering pinned: that function sorts `Path` objects, which Python orders component-wise, so that `a/b` precedes `a-c` while a byte sort places `a-c` first (measured on Python 3.13; `-` is 0x2D and `/` is 0x2F). The two orders agree whenever no entry name is a proper prefix of another entry name followed by a lower-sorting byte, which is the case for `tests/fixtures/schemas/jacobian_result` — its recorded K01 value `6fe5054eb4d15359f30f1c760e59efeaa5b4db71a48517d859d529bae52da4de` is reproduced under both orders (measured) — so no recorded manifest changes. The sort key changes (C8); symbolic links and empty directories are not walked and a directory containing a symbolic link is refused rather than silently partially hashed.
3. **Not a canonical form.** Evidence manifests are artifacts (D5.1). They are not canonicalized, their `indent=2` layout is fine, and nothing hashes them as documents.

### D6. Where the encoding identifiers live (brief §4.4): pinned globally, recorded in manifests, not a per-document field

1. **No `hash_encoding` field is added to any document schema.** The three identifiers — `ENCODING_ID = "ieee754-be-v1"` (D1), `DOCUMENT_ENCODING_ID = "jcs-rfc8785-v1"` (D3), `DIRECTORY_HASH_ID = "dirhash-v1"` (D5) — and `"compiled-problem-structure-v1"` (D2) are constants of `process_runtime.canonical` and are pinned by this ADR for the repository as a whole. A document carrying a different identifier could not be *read* by this repository in any case; the only correct response is refusal, and refusal does not need a per-document field to be correct — it needs the identifier recorded once wherever a set of documents is handed to a reader that might not share it.
2. **Where they are recorded.** Every evidence manifest from K02 onward records all three under `checks` or `inputs` (the K01 manifest already records `ENCODING_ID` in prose; C9 makes it a field). The replay bundle manifest and `RunManifest` (K04/K05, ADR 0007) record all three once per bundle; a reader that meets an unknown identifier reports `unsupported` with the identifier named and does not attempt a comparison — that obligation is placed on ADR 0007 here so that it cannot be omitted there. `docs/interfaces-frozen.md` §2 gains the identifier table (C1).
3. **Changing an identifier is a migration** (D7): a new `-v2` value, an ADR, and a migration report listing every stored digest that the change invalidates. The window in which this is cheap closes at K04/K05, as R-006 records.

### D7. The migration rule (generalizing ADR 0008 C3–C5)

1. **What counts as a schema change.** Any edit that changes the set of documents a schema under `schemas/` accepts (a field added, removed, renamed, re-typed, a pattern narrowed or widened, an enum value added or removed, a `required` list changed); any change to the *meaning* of an accepted document even when the JSON Schema text does not change (D2.3 is one: the `model_version` string existed before and means more now); any change to a canonical form or identity rule that changes the digest of an unchanged document (an encoding identifier, the structure-document schema, the exclusion list of D4.2); and any change to a frozen Protocol signature or result-type field set. **Not** a schema change: `description`, `$comment`, examples, the order of keys in a schema file, adding an *invalid* fixture, adding a cross-field check that only rejects documents no valid producer emits.
2. **What a migration must produce.** (a) A Fable-authored ADR — or a numbered amendment to an existing one, recorded in the decision register — stating reason, affected requirements, migration impact and acceptance evidence (CLAUDE.md "Authority"). (b) The transformation, old document → new document, as a function in `process_runtime.ir` (the module that "owns … schema migrations" by its own docstring), executable and tested on every instance it is applied to; a migration that is only a description is not a migration. (c) A **migration report** in the ADR listing every instance migrated (path or id), what changed in it, and for every instance that carries a digest, the digest before and after; an unchanged digest is stated as unchanged. (d) Every fixture, tracked document and evidence reference regenerated or updated in the *same* change, so that the gate never sees a mixed state. (e) An update to `docs/interfaces-frozen.md` §2 naming the ADR and the report.
3. **Originals are retained.** Repository-owned instances (fixtures, benchmark files) are migrated in place; git history is the retained original and the report cites the pre-migration commit. Instances the repository does not own — a user's revision, a stored run, a replay bundle — are never modified: a migration creates a new instance (a new revision with `parent_revision` set and provenance `operation: "migrate"`), the original stays readable at its own schema version, and the report says which. This is blueprint §4.4's "new revisions with a migration report and retained originals".
4. **Timing.** Before a schema's first non-repository instance exists, a migration is a regeneration and is cheap; the `evidence/` manifests of earlier packages are immutable history (ADR 0008 C9) and are not regenerated. After K04/K05 store digests in bundles, every rule in D1–D6 that changes a digest costs a per-bundle migration, which is why this ADR is being written now.
5. **The reader's obligation.** A reader handed a document at a schema version it does not implement reports `unsupported` naming the version; it never reads a newer document as an older one by ignoring fields it does not know. The three K01 schemas set `additionalProperties: false`, which is the executable half of this rule; the evidence-manifest schema does the same.

## Alternatives considered

- **Hash the names into the vector digest** (`constants_sha256` over names and values). Rejected. `state_sha256` cannot do it — ADR 0008 D2 says "nothing else participates" and is not reopened — so the two hashes would stop being one primitive (D1.4); it mixes the structure tier into the numerical-model tier that blueprint §4.4 separates; and it still leaves `model_version` a free string, so two problems with different *equations* over the same names would remain confusable. The name-level fingerprint belongs with the structure, and D2 puts it there.
- **A new `structure_sha256` field on `CompiledProblemMetadata` with `model_version` left as a label.** Rejected for now. The pairing identity of ADR 0008 D2.4 does not include it, so a cache or bundle keyed on the pairing fields would still collide unless the result types were widened (out of scope) or a prose rule made `model_version` pin it (the hole restated). Folding the digest into `model_version` gives every existing consumer the property without a new obligation. The blueprint's "structural fingerprint" is satisfied by the suffix; ADR 0007 may add a field if a bundle needs the digest without the label, and that is additive.
- **State the obligation normatively and test it at compile time only** (a registry of label → structure inside one process). Rejected: it catches a collision only when both problems are compiled in the same process, which is exactly not the replay scenario.
- **Hash the equation expressions** (backend `Function.serialize()`, or the Python source of the row builders). Rejected: backend serialization is version-specific and not portable across backends, source text is not what a manifest-driven compiler will have, and D2.7's `sources` member (content hashes of the manifests and the revision) is the portable version of the same idea.
- **Python `json.dumps(sort_keys=True, separators=(",", ":"), allow_nan=False)` as the canonical form.** Rejected: its float layout (`1e+16`, `1e-07`, `1.0`) is Python's `repr`, its key order is code-point order, and both are "what one library prints" — the objection R-006 sustained against `%.17g`. It is also very close to JCS, which is why the in-repo serializer is small.
- **Canonical CBOR (RFC 8949 §4.2) or another binary form for documents.** Rejected: blueprint line 152 says "canonical JSON for hashes", which is binding, and the readability of the canonical bytes is worth having when a digest disagreement is being debugged.
- **`%.17g` or `repr` text as the vector encoding.** Rejected by R-006 and not re-proposed; the portability argument stands and the digest changed once at the cheapest moment.
- **Hexadecimal floats in documents.** Rejected: not readable, not what the blueprint asked for, and unnecessary once vectors are hashed as bytes and documents through JCS.
- **A per-document `hash_encoding` field (brief §4.4).** Rejected, D6: it would cost a migration of three frozen schemas and give a reader nothing it can act on beyond refusal, which the bundle-level record already enables.
- **NFC-normalizing keys and ids before hashing.** Rejected: canonicalization must not make two byte-different documents equal; admitting or refusing confusable ids is a validation question.
- **Sorting arrays of ID-keyed objects in canonical form** (the "stable ID ordering" of line 152 read as a reordering rule). Rejected: `component_set.components` order is the component order and `variable_ids` order is the `x` layout; a canonical form that reorders arrays would silently change meaning. "Stable ID ordering" is satisfied by explicit ids, preserved array order, and key-sorted objects.

## Consequences — the migration, applied by the Opus session on `wp/K02`

No scientific choice is left open below. This ADR changes **no `state_sha256` and no `constants_sha256` value**: `ENCODING_ID` stays `ieee754-be-v1`, and every digest recorded in `evidence/K01/*/manifest.json` and in the K01 fixtures is unchanged. It changes one string field's format and adds document-level canonicalization.

### C1. `docs/interfaces-frozen.md`

In §1, "Binding semantics attached to the signatures", **append** to the second bullet (the one ending "Encoding of the hash is ADR 0002's."):

> `model_version` is `<label>@<structure_sha256>`, where the digest is over the name-level structure document (`variable_ids`, `equation_ids`, `parameter_ids`, `row_accumulation`) in canonical JSON (ADR 0002 D2); two problems sharing a `model_version` share that structure, and the label is the name of the function family.

In §2, **append** after the sentence about the ADR 0008 `ModelManifest` migration:

> `compiled-problem-metadata`, `evaluation-result` and `jacobian-result` were migrated by ADR 0002 (the `model_version` format, D2.3); the migration report is ADR 0002 "Consequences" C2–C7 and the only instances, the K01 fixtures, were regenerated in the same change. Canonical JSON is RFC 8785 (ADR 0002 D3); `ProcessRevision.content_hash` is defined by ADR 0002 D4. Encoding identifiers pinned for the repository: `ieee754-be-v1` (vectors), `jcs-rfc8785-v1` (documents), `dirhash-v1` (directories), `compiled-problem-structure-v1` (the structure document).

In §3, **replace** "and ADR 0008 D1–D3 (…) are part of this freeze." with "…, ADR 0008 D1–D3 (…) and ADR 0002 D1–D6 (vector identity, structural identity and the `model_version` format, canonical JSON, the physical-model hash, artifact identity, encoding identifiers) are part of this freeze."

### C2. The three K01 schemas

In `schemas/compiled-problem-metadata.schema.json`, `schemas/evaluation-result.schema.json` and `schemas/jacobian-result.schema.json`, replace the `model_version` property with

```json
"model_version": {
  "type": "string",
  "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}@[0-9a-f]{64}$",
  "description": "`<label>@<structure_sha256>` (ADR 0002 D2.3). The label names the function family; the digest is over the name-level structure document — variable_ids, equation_ids, parameter_ids, row_accumulation — in canonical JSON, so two problems sharing this string share that structure. Identifies equation structure only, never pinned-input values (ADR 0008 D4.1): two instances differing solely in specification values share it and are told apart by constants_sha256."
}
```

Append to each schema's top-level `description`: ` ADR 0002 D2 fixed the model_version format; check_metadata_document recomputes the structure digest from the document's own id lists.`

### C3. `src/process_runtime/canonical.py` and the compiler

Add to `canonical.py`: `DOCUMENT_ENCODING_ID = "jcs-rfc8785-v1"`, `DIRECTORY_HASH_ID = "dirhash-v1"`, `STRUCTURE_SCHEMA = "compiled-problem-structure-v1"`; `canonical_json(document) -> bytes` (D3, including the refusals of D3.3–D3.6); `structure_document(variable_ids, equation_ids, parameter_ids, row_accumulation) -> dict`; `structure_sha256(...) -> str`; `model_version(label, structure_digest) -> str` and `split_model_version(value) -> tuple[str, str]`, the latter raising on a string that does not match D2.3. Replace the module docstring's final section ("What the digest does not cover … ADR 0002 must state it") with a reference to D1.7 and D2.

In `compile/casadi_backend.py`, `model_version=spec.model_version` becomes the compiler's own assignment from the spec's label and the structure digest of the spec's ids and accumulation map. In `compile/spec.py`, the field carrying the label is documented as the label (renaming it to `label` is permitted; if it is not renamed, `validate()` refuses a value containing `@`). `benchmarks/k01/syn001.py` supplies `SYN-001-L-1` / `SYN-001-I-1` as labels; `MODEL_VERSION` there, if still referenced, becomes the full string obtained from the compiled metadata rather than a literal.

### C4. `process_runtime.serialize`

`check_metadata_document` additionally: parses `model_version` with `split_model_version`, recomputes `structure_sha256` from the document's `variable_ids`, `equation_ids`, `parameter_ids` and `row_accumulation`, and raises `DocumentError` on mismatch. A new `check_revision_document(document)` (or the equivalent in `process_runtime.ir`) computes D4's `content_hash` and, when the document carries a non-null `content_hash`, raises on mismatch. A document reader `load_document(path)` in `process_runtime.ir` implements D3.6 (safe YAML, JSON-model check, duplicate-key refusal) and is what the fixture tests load through.

### C5. Fixture regeneration (the migration report for D2.3)

| Instance | Change | Digests |
| --- | --- | --- |
| `tests/fixtures/schemas/compiled_problem_metadata/valid/syn001_lifted.json` | `model_version`: `SYN-001-L-1` → `SYN-001-L-1@8e5930fc737e8e0b033a2fe35d06971c6cf911df2db5d9731e050cf1cb6fb98a` | `constants_sha256` unchanged (`d4ddcbf8…f009`) |
| `tests/fixtures/schemas/evaluation_result/valid/{syn001_s1,syn001_s5,syn001_out_of_domain}.json` | `model_version` as above | `state_sha256`, `constants_sha256` unchanged |
| `tests/fixtures/schemas/jacobian_result/valid/{syn001_s1,syn001_s5,syn001_out_of_domain}.json` | `model_version` as above | unchanged |
| every invalid fixture under the three directories | `model_version` as above, so that each remains wrong in exactly one way | — |

The pre-migration originals are at commit `51f033b`. The evaluation and Jacobian fixtures are regenerated from real output exactly as K01 generated them; the metadata fixture's new `model_version` must equal the registered string in D2.8 (assertion S6), which is the check that the compiler's assignment and this ADR's independent computation agree.

### C6. New invalid fixtures

- `tests/fixtures/schemas/compiled_problem_metadata/invalid/structure_digest_mismatch.json` — a copy of the valid fixture whose `model_version` suffix is the *permuted-parameters* digest `edbbcf2d…2200` from D2.8 while the id lists are the lifted form's. `_why_invalid`: "the structure digest in model_version is not the digest of this document's own id lists (ADR 0002 D2.9)". Rejected by `check_metadata_document`, not by the schema.
- `tests/fixtures/schemas/compiled_problem_metadata/invalid/label_malformed.json` — `model_version` equal to `SYN-001-L-1` (the pre-ADR form). `_why_invalid`: "model_version carries no structure digest (ADR 0002 D2.3)". Rejected by the schema pattern.
- `tests/fixtures/schemas/process_revision/invalid/content-hash-mismatch.yaml` — a schema-valid revision whose `content_hash` is 64 hex characters that are not its D4 digest. `expect_error: content_hash`. Rejected by `check_revision_document`.
- `tests/fixtures/documents/invalid/duplicate-key.json` — raw text with a repeated key; the reader refuses it (D3.6).

### C7. New test module `tests/test_adr_0002_canonicalization.py`

Numbered assertions as listed under "Acceptance evidence" (E1, S1–S6, J1–J8, R1–R2, F1–F2), one test function per assertion, named `test_e1_…`, `test_s2_…`, so a manifest can cite them. The expected values are the tables in this ADR, transcribed into `tests/fixtures/canonical/adr-0002-vectors.json` by `scripts/adr_0002_vectors.py`, which computes the E and S digests from `struct`/`hashlib` and its **own** serializer written separately from `process_runtime.canonical` (the judge precedent: a harness must not certify its own hash), refuses to emit if any value disagrees with the literals in this ADR, and has a `--check` mode that re-derives the file and compares byte-for-byte. The test compares production output to the fixture.

### C8. `scripts/k01_evidence_manifest.py` (and the shared helper if one is extracted)

`directory_hash` sorts by `str(path.relative_to(root)).encode("utf-8")` (D5.2). The recorded K01 manifest is not regenerated; assertion F2 below shows its value is reproduced by the pinned order.

### C9. Evidence manifests from K02 onward

Record `"hash_encodings": {"vector": "ieee754-be-v1", "document": "jcs-rfc8785-v1", "directory": "dirhash-v1", "structure": "compiled-problem-structure-v1"}` under `inputs`; `schemas/evidence-manifest.schema.json` gains that optional object (this is a schema change under D7.1 and this ADR is its report: no existing manifest carries the field, none is regenerated).

### C10. Documentation and register

`schemas/README.md`: a section "Migrated by **ADR 0002**" with the `model_version` format and the canonical-JSON pointer. `tests/README.md`: one row for the new module. `docs/decision-register.md`: R-006's "Normative text" row becomes `docs/adr/0002-canonicalization-and-schemas.md` D1, and R-A02 in the "Already registered as ADRs" table is filled in (the entry text is in the author's report to the Opus session). `docs/progress.md`: ADR 0002 in the accepted-ADR table once the gate passes. `src/process_runtime/canonical.py`'s module docstring and `schemas/process-revision.schema.json`'s `content_hash` description drop the "until ADR 0002" wording.

## Acceptance evidence

`PATH=.venv/bin:$PATH ./scripts/check.sh` green (ruff, ruff format, mypy strict, pytest) with the assertions below present and passing. Baseline before this ADR: 645 tests, measured 2026-09-18 on `wp/K02` at `51f033b`. Every expected value is a digest or an exact byte string; tolerance is **exact** in every case — a hash has no roundoff floor, and the smallest error worth catching (one bit anywhere) changes every digit. No assertion is satisfiable by an accidental zero: every registered document has at least one non-trivial member of each kind it exercises, and every equality is paired with an inequality on a neighbouring input.

**E — the vector encoding (D1).**

- **E1** The eight rows of D1.8, each recomputed from `struct.pack(">d")` and `hashlib.sha256` inside the test, equal the table and equal `encode_doubles`/`hash_named_doubles` on the same input. The two-zeros row asserts equality of the `0.0` and `-0.0` digests *and* inequality of `(1.0)` against `(-1.0)`.
- The existing pins are cited, not duplicated: ADR 0008 H1–H6 (both hashers), `test_canonical.py` (dense/mapping agreement, length refusal, keys outside the ordering, round-trip, eight big-endian bytes, legacy agreement with the judge and the spike, production ≠ legacy, `ENCODING_ID` values, order and length participation, one primitive).

**S — structural identity (D2).**

- **S1** `canonical_json(structure_document(...))` for the small document of D2.8 equals the 246 registered bytes and hashes to `690d7542…5aa4`; the permuted-parameters and reclassified-row variants hash to `edbbcf2d…2200` and `50e8d3b8…00c2`, and all three digests are pairwise distinct.
- **S2** (the hole) The two `HOLE` specs of D2.6, compiled: `constants_sha256` equal to each other and to `e0383cfd…9a40`; `model_version` strings differ; the (`model_version`, `constants_sha256`) pairs differ. A third spec with `variable_ids` permuted and a fourth with one `row_accumulation` kind changed each produce a `model_version` different from the first.
- **S3** Two specs identical except for labels `A` and `B`: different `model_version`, identical suffix after `@`, identical `constants_sha256`.
- **S4** `check_metadata_document` accepts the regenerated valid fixture and rejects `structure_digest_mismatch.json` and `label_malformed.json` (the latter via the schema) with messages naming ADR 0002 D2.
- **S5** (determinism, R0 in one process) Compiling the same spec twice yields byte-identical `model_version` and `constants_sha256`; `split_model_version` round-trips `model_version(label, digest)`; a label containing `@` or longer than 64 characters is refused.
- **S6** The regenerated `syn001_lifted.json` carries exactly `SYN-001-L-1@8e5930fc737e8e0b033a2fe35d06971c6cf911df2db5d9731e050cf1cb6fb98a`, and the canonical bytes of its structure document are 760 long and begin with the 55 bytes quoted in D2.8. For the inlined form, the compiled metadata's suffix equals `structure_sha256` recomputed from that metadata's own fields (self-consistency; no registered value).

**J — canonical JSON (D3).**

- **J1** (numbers) For each row, `canonical_json(struct.unpack(">d", bytes.fromhex(hex))[0])` equals the string. Provenance: the ECMA-262 algorithm of D3.3 applied by the scratch implementation; rows marked † also appear in RFC 8785 §3.2.2.3 and must equal the RFC's text.

  | IEEE-754 hex | Canonical | Why registered |
  | --- | --- | --- |
  | `0000000000000000` † | `0` | zero |
  | `8000000000000000` † | `0` | negative zero normalizes (ADR 0001 D1.5) |
  | `0000000000000001` † | `5e-324` | smallest subnormal; case (d) |
  | `7fefffffffffffff` † | `1.7976931348623157e+308` | largest finite; case (e), 17 digits |
  | `ffefffffffffffff` | `-1.7976931348623157e+308` | sign |
  | `3ff0000000000000` | `1` | `1.0` is not `1.0`; case (a) with k = n = 1 |
  | `c000000000000000` | `-2` | negative integer |
  | `3fb999999999999a` | `0.1` | case (b), shortest digits not `0.1000000000000000055…` |
  | `3fd3333333333334` | `0.30000000000000004` | `0.1 + 0.2`; 17 digits needed |
  | `3fe0000000000000` | `0.5` | exact binary fraction |
  | `4076800000000000` | `360` | the SYN-001 `t_spec` value |
  | `40f86a0000000000` | `100000` | the SYN-001 `p_spec` value |
  | `4020a1013e8990be` | `8.31446261815324` | R, 15 digits suffice |
  | `4341c37937e08000` | `10000000000000000` | 1e16: case (a), k = 1, n = 17 — `repr` gives `1e+16` |
  | `4340000000000000` † | `9007199254740992` | 2^53 |
  | `4415af1d78b58c40` | `100000000000000000000` | 1e20, n = 21, last integer-form exponent |
  | `444b1ae4d6e2ef4f` † | `999999999999999900000` | just below the 1e21 boundary, zero-padded shortest digits |
  | `444b1ae4d6e2ef50` † | `1e+21` | the boundary; case (d) |
  | `4430000000000000` † | `295147905179352830000` | 2^68: shortest digits padded, not `295147905179352825856` |
  | `44b52d02c7e14af7` † | `1.0000000000000001e+23` | case (e) |
  | `3ee4f8b588e368f1` | `0.00001` | case (c), n = −4 |
  | `3eb0c6f7a0b5ed8d` † | `0.000001` | case (c), n = −5 — `repr` gives `1e-06` |
  | `3eb0c6f7a0b5ed8c` † | `9.999999999999997e-7` | one ulp below; case (e), no leading zero in the exponent |
  | `3e7ad7f29abcaf48` | `1e-7` | first exponent-form small value; `repr` gives `1e-07` |
  | `3e8421f5f40d8376` | `1.5e-7` | case (e) small |
  | `41b3de4355555554` † | `333333333.33333325` | 17 digits, case (b) |

- **J2** `canonical_json(-0.0) == b"0"`; `canonical_json` of NaN, `+inf`, `-inf` raises; `canonical_json(2**53 + 1)` raises; `canonical_json([1, 1.0, 2**53, -(2**53), 2.0**60]) == b"[1,1,9007199254740992,-9007199254740992,1152921504606847000]"`.
- **J3** (key order) The object with keys `z`, U+00E9, U+1F600, U+FF5E (values 1–4) canonicalizes to the bytes `7b227a223a312c22c3a9223a322c22f09f9880223a332c22efbd9e223a347d` — order `z`, `é`, U+1F600, U+FF5E — and `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` of the same object places U+FF5E before U+1F600, i.e. differs. Both facts are asserted.
- **J4** (escaping) The string of code points U+0000 U+0008 U+000A U+001F U+0022 U+005C U+002F U+00E9 U+007F U+2028 canonicalizes to the bytes `225c75303030305c625c6e5c75303031665c225c5c2fc3a97fe280a822`.
- **J5** `canonical_json(True) == b"true"`, `canonical_json(None) == b"null"`, and `canonical_json(True) != canonical_json(1)`.
- **J6** The reader refuses `duplicate-key.json`, refuses a YAML document with an unquoted timestamp, a set, binary, or a non-string key, and accepts the same documents with those nodes written as strings.
- **J7** The document `{"b": [1.0, -0.0, 1e21, "x"], "a": {"n": None, "t": True}}` canonicalizes to `{"a":{"n":null,"t":true},"b":[1,0,1e+21,"x"]}` (hex `7b2261223a7b226e223a6e756c6c2c2274223a747275657d2c2262223a5b312c302c31652b32312c2278225d7d`) with SHA-256 `f4cd59c01a56b22e33d6f0b802a5271bc5cc9f80c53a5051d317257e6c7fb10f`; and the same document round-trips through `json.loads(canonical_json(doc))` with `-0.0` decoded as `0.0`.
- **J8** (no normalization) The object with keys `e` + U+0301 and U+00E9 canonicalizes to `7b2265cc81223a312c22c3a9223a327d`, two members, decomposed form first.

**R — the physical-model hash (D4).**

- **R1** The document of D4.7 has hashed form equal to the 362 registered bytes and `content_hash = 21f5ca93…d58e`; the one-ulp variant gives `8eb480e7…0615`; the presentation-changed variant (timestamp, title, display unit) gives `21f5ca93…d58e` again; and each excluded member of D4.2 that exists in the document, changed on its own, leaves the digest unchanged, while each of `value`, `unit`, `role`, `components` order, `instances[0].id` and `schema_version`, changed on its own, changes it.
- **R2** `content-hash-mismatch.yaml` is rejected naming `content_hash`; the P01 fabricated-hash fixture is still rejected by the pattern; a revision with `content_hash: null` is accepted.

**F — artifact identity (D5).**

- **F1** `directory_hash` on a temporary tree with files `a/b`, `a-c`, `a.c`, `a/c`, `ab` orders them `a-c`, `a.c`, `a/b`, `a/c`, `ab`, and its digest equals a recomputation from that order with `hashlib` inside the test; the `Path`-sorted order of the same names differs (asserted, so the reason for the rule stays visible).
- **F2** On `tests/fixtures/schemas/jacobian_result` — whose *file names* C5 does not change, only their contents — the byte-order digest of D5.2 equals the `Path`-order digest of the pre-ADR code, both computed inside the test. This is the executable form of the statement that pinning the order left the K01-recorded value untouched; the reproduction of that recorded value itself (`6fe5054eb4d15359f30f1c760e59efeaa5b4db71a48517d859d529bae52da4de` under both orders) was measured on 2026-09-18 at `51f033b`, before C5 regenerated the files, and is recorded here as a measurement, not as an ongoing assertion.

Review: Opus reviews this ADR for coverage, packaging and documentation (plan §1.3) and may not alter D1–D7. Numerical sign-off on the identity rules and process-modeling sign-off on the D4.2 exclusion list are human decisions recorded separately and not claimable by an agent.

## What this ADR does not establish

- **No replay identity, no run fingerprint, no certificate hash.** `RunManifest`, the replay bundle manifest, the numerical-model tier (component records, manifests, provider hashes combined with `content_hash`), the solve-policy tier and the full-run tier are ADR 0007's. This ADR gives them the vector, structure, document and artifact identities to build on and the obligation to record the identifiers (D6.2) and to refuse unknown ones.
- **No expression identity for hand-written problems.** D2.7 says exactly how far the structure digest reaches and that the label carries the rest until `compiled-problem-structure-v2`.
- **No semantic-equivalence test** for permuted revisions (D4.5), no confusable-identifier policy (D3.5), no reordering rule for any array.
- **No cross-platform evidence for R0.** S5 is one process on one host; K05 owns the second platform. This ADR makes a structural nondeterminism *visible* as a `model_version` mismatch; it does not show there is none.
- **No claim that Python's `repr` digit selection equals ECMA-262's for every double.** The rule is ECMA-262's; the registered vectors pin the layout and the digits on 26 values; Q1 names the measurement.
- **No validation of anything physical**, no change to any requirement status in `docs/requirements.yaml`, no relaxation of any gate, no change to the backend or distribution policy, no change to any `state_sha256` or `constants_sha256` value, and no cryptographic claim beyond SHA-256 collision resistance — nothing is signed.
- **Nothing about the P02 artifacts.** `spikes/p02/results/` and `benchmarks/p02/judge.py` are judged by the P02 specification and its `p02-10.4` encoding; D2.3's format applies to `process_runtime` documents only.
- **No YAML canonical form.** YAML is an input syntax; canonical form is defined on the parsed JSON data model (D3.6).

## Open questions with recommended defaults

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Does Python's `repr(float)` select the same shortest digit string as ECMA-262 `Number::toString` for every finite double (both are "shortest round-trip, closest on ties"; the tie-to-even clause is the only place they could differ)? | needs a fact — run the RFC 8785 reference implementation's published 100-million-value test file, or a 1e7 random sample against an independent JCS implementation, through `canonical_json`; zero disagreements settles it | Accept on the J1 vectors plus a randomized round-trip property test (`float(canonical) == x` for 1e6 random bit patterns, which is necessary but not sufficient). A disagreement found later is a bug in the implementation against the rule, not a change to the rule. |
| Q2 | Should the SYN-001 labels stay `SYN-001-L-1` / `SYN-001-I-1`, or carry the K01 commit or the derivation version? | needs the user's preference | Keep them. The suffix now carries structure; the label's job is to be readable. Change only when the equation set changes (D2.7). |
| Q3 | When does `ProcessRevision.content_hash` become required (non-null)? | needs the user's preference | Required for every revision K06 writes; optional-but-verified for hand-written fixtures until then. Reversible by one `required` entry and one fixture pass. |
| Q4 | What does `compiled-problem-structure-v2` contain when manifests feed the compiler — the manifests' and revision's content hashes only, or also the declared Jacobian pattern? | needs the user's preference, informed by ADR 0007's sparsity-reuse rule | Content hashes only, as D2.7 says; the pattern stays a reported property with `pattern_provenance` and ADR 0007 decides how sparsity reuse compares it. |
| Q5 | Should `process_runtime.ir.load_document` be the *only* reader of semantic documents in the repository, with the `conftest` loaders routed through it? | needs the user's preference | Yes: one reader, so that D3.6's refusals cannot be bypassed by a test helper. Reversible by re-pointing two functions. |

## Changing this ADR

D1–D6 are part of the P01 interface freeze from the moment C1 lands. Changing the vector encoding or `ENCODING_ID`, the members or version of the structure document, the `model_version` grammar, the canonical JSON rule or `DOCUMENT_ENCODING_ID`, the exclusion list of D4.2, the directory-hash rule, or the decision of D6 that identifiers do not travel in documents requires a new Fable-authored ADR stating reason, affected requirements, migration impact and acceptance evidence, and — because every one of those changes alters stored digests — a migration report under D7 listing them. D7 itself is procedural and may be amended by a numbered addition to this ADR recorded in the decision register. A package that cannot discharge an obligation placed here reports it in `docs/progress.md` as a blocker, never by omission; if a measurement contradicts a registered value in this ADR, the ADR is amended and says so, and no harness is bent to fit it.

## Amendment 1 (2026-09-27) — an integer is canonical exactly when its digits are a binary64's canonical spelling

**Authority and scope.** Design lane (`specifier`), on the T07 build lane's W7c finding (`docs/T07_DECISIONS.md`, "FINDING (build lane / ADR 0002 owner)"; `docs/t07-measurements.md`, "Finding (ADR 0002 round trip)"). It amends one sentence of D3.3 and nothing else in D1–D7. It is made under D3.2's own clause: where this ADR and RFC 8785 differ, the difference is a defect in this ADR to be amended. "Changing this ADR" asks for a new ADR and a migration report *because* such changes alter stored digests. This one alters none (A1.6), and A1.6 is its D7 migration report: no instance migrated, no digest changed. `DOCUMENT_ENCODING_ID` stays `jcs-rfc8785-v1`: every byte string the writer produced before is produced unchanged, and every newly admitted input is written as RFC 8785 bytes.

Machine-readable reference: `docs/derivations/scripts/adr0002_a1_reference.json` (sha256 `c76bf9512be632bc33fae9d6d4b2e64c089d2fc29aab4a0ef049ff1dade8da95`, 10 805 bytes), emitted byte-reproducibly by `docs/derivations/scripts/adr0002_a1_reference.py` (`--check`: claims C1–C10). The generator decides each registered integer by exact integer arithmetic on D3.3's definition (its own round-half-even rounding and its own digit selection). It imports nothing from `process_runtime` and uses neither `float()` nor `repr` for an emitted value. CPython's `float()` enters only as a cross-check (C8, C9).

### A1.1 The defect, measured at `afcc327`

D3.3 spells an integral binary64 above 2^53 with its shortest digits padded with zeros. The same D3.3 refused every integer above 2^53, and every parser in use reads those digits as an `int`. So the writer's own output was refused on reading.

| Witness | Measured |
| --- | --- |
| This ADR's own J1 and J2 vectors | `canonical_json([1, 1.0, 2**53, -(2**53), 2.0**60])` is `[1,1,9007199254740992,-9007199254740992,1152921504606847000]`. `first_noncanonical(json.loads(<that>))` is `/4`. J1's `1e16`, `1e20` and `2.0**68` fail the same round trip. |
| T07 W7c, V17 T08 | The certificate's `regularity.inverse_one_norm_estimate`, 5.92612204108959e17, is written `592612204108959000`. `get_artifact` serves the file as text lines on every transport, and the V17 exporter needed a private number reader (`export._number`). |
| `commit_change` (found for this amendment) | Setting a revision's `settings.x` to the float `5.92612204108959e17`, or to the float `2.0**54`, makes `LocalApplication.commit_change` **raise** an untyped `CanonicalizationError` (`local.py:410` → `:1293` → `revisions.py:74`). The commit validates the canonical document read back (`json.loads(canonical_json(built))`, `local.py:1287`). That is an escape from ADR 0020 D6 (Q29: every entry refuses typed), on an input that is canonical. |
| Sample | Of the 98 221 integral doubles kept by J12's sampling law (100 000 draws), all 98 221 fail the round trip. |
| Parsers | `json.loads`, `pydantic_core.from_json` (the MCP SDK's stdio transport parses each message with `JSONRPCMessage.model_validate_json`) and `yaml.safe_load` each return an exact `int` for every integer text tried: `9007199254740993`, `9007199254740994`, `592612204108959000`, 2^55, 10^20 and 10^400 (all three); 2^63 and `100000000000000000001` (`pydantic_core`). Each refuses a text of more than 4300 digits (next row). |
| Beyond 4300 digits (found for this amendment) | `first_noncanonical({"x": 10**5000})` and `canonical_json(10**5000)` raise an untyped `ValueError`. The refusal message formats the integer, and CPython refuses to convert an `int` of more than 4300 digits to `str`. `json.loads` of a 4301-digit integer text raises a plain `ValueError`, which is not a `JSONDecodeError`, so the `except json.JSONDecodeError` at `bindings/http.py:261` does not catch it. That was measured at the parser; the binding's resulting response was not measured. |

### A1.2 Decision

D3.3's sentence *"An integer whose magnitude exceeds 2^53 is not canonicalizable and is refused with an explicit error, never rounded"* is replaced by the following.

> **An integer `n` is canonicalizable exactly when its decimal digits are the canonical spelling (D3.3) of the binary64 nearest to `n`** (round half to even). It is then written as those digits, and those digits are that binary64's canonical bytes. Any other integer is refused with an explicit error, never rounded.

It follows (proofs in A1.3):

| Range | Which integers are canonical |
| --- | --- |
| `\|n\| ≤ 2^53` | Every one, as before. |
| `2^53 < \|n\| < 10^21` | Exactly one integer per binary64: the one D3.3 spells. Admitted: 2^53+2, 2^54, 36028797018963970, 592612204108959000, 1152921504606847000, 18446744073709552000, 10^20. Refused: 2^53+1, 2^55 (= 36028797018963968), 2^60, 2^64−1, 2^64 and 2^68, although 2^55, 2^60, 2^64 and 2^68 are exact binary64 values. **The criterion is the spelling, not exactness.** |
| `\|n\| ≥ 10^21` | None: layouts (d)/(e) spell every binary64 there with an exponent. |

**The judgment is on the integer's own digits, so it does not depend on where the `int` came from.** An in-process `int`, `json.loads`, the MCP SDK's parser and YAML all give the same verdict. No reader changes, and no reader gains a number hook.

**One implementation.** `process_runtime.canonical.integer_binary64(n: int) -> float | None`:
- It returns `float(n)` when `|n| ≤ 2^53`.
- It returns `None` when `|n| ≥ 10^21`, without converting (`float(10**400)` raises `OverflowError`).
- Otherwise it returns `float(n)` if `_canonical_number(float(n)) == str(n)`, else `None`.
- A `bool` is not an integer here, and passing one raises `TypeError`.

Every consumer uses it:
- `_canonical_number`'s integer branch, and through it `canonical_json` and `first_noncanonical`;
- `units.read_number`'s integer branch, which returns the binary64, or the infinity of the integer's sign when the result is `None` (T06 A100 (a) unchanged).

**The refusal message** contains `is not the canonical spelling of a binary64` and `ADR 0002 D3.3` in every case. It **never formats an integer of 10^21 or more**: such an integer is named as "an integer of magnitude 10^21 or more", and the message adds that every binary64 there is spelled with an exponent. That closes A1.1's `ValueError` escape.

### A1.3 Why this reading, and the proofs

1. **The ADR contradicted itself, and the RFC.** D3.3's first sentence says every JSON number is a binary64. The text `1152921504606847000`, which is J2's output, is a JSON number whose binary64 is 2^60, and its canonical spelling is itself. An RFC 8785 implementation reads it and writes it back unchanged. The refusal sentence refused it. That is a defect under D3.2.
2. **"Never rounded" is kept exactly.**
   - An admitted integer is written as its own digits.
   - The refused integers are exactly those whose canonical bytes would differ from their digits. JCS would silently rewrite `9007199254740993` as `9007199254740992`; this ADR refuses it instead, as it always did.
   - Nothing is lost for any reader. A Python reader of the bytes gets the `int` `n`, and `float(n)` is the binary64 bit for bit. A JCS reader gets the binary64. Both write the same bytes back.
3. **Closure (the property the defect broke).** Take a finite binary64 `f` with canonical spelling `S`. Then `json.loads(S)` is canonical and re-canonicalizes to `S`, in each case:
   - If `S` contains `.` or `e`, `json.loads` gives a float equal to `f`, because `S` is a round-trip spelling.
   - If `S` is digits and `|f| ≤ 2^53`, `json.loads` gives the `int` `f`, which is admitted and spelled `S`.
   - If `S` is digits and `2^53 < |f| < 10^21`, `json.loads` gives the `int` `m = s·10^(n−k)`. By D3.3's definition of `s, k, n`, `m` rounds to `f`, and its digits are `S`, so it is admitted by the new rule.

   Hence `canonical_json(json.loads(canonical_json(d))) == canonical_json(d)` for every admitted document `d`, arrays and objects following by induction. J12 samples this.
4. **Nothing changes at or below 2^53.**
   - For `0 < |n| ≤ 2^53`, `n` is a binary64, and every integer of that magnitude is a binary64 of its own. So no other integer rounds to `n`.
   - A non-integer decimal that rounds to `n` has more significant digits than `n`: its integer part is within one of `n`.
   - So the shortest spelling is `n`'s own digits with trailing zeros removed, and layout (a) restores them (`n` has at most 16 digits).

   J11 samples this.
5. **Exactly one integer per binary64 in the band.**
   - For an integral `f` with `2^53 < |f| < 10^21`, the reals that round to `f` form an interval at least 2 wide, so it contains integers.
   - A non-integer candidate needs more significant digits than some integer in that interval, so D3.3's shortest candidates are integers.
   - D3.3 selects one `s·10^(n−k)`, and that integer is admitted. Every other integer that rounds to `f` is not its spelling, and is refused.
   - In `[2^53, 2^54)` the ulp is 2, and the admitted integers are exactly the even ones (generator claim C7a, exhaustive on `[2^53, 2^53 + 4096]`).

### A1.4 Alternatives rejected

- **(a) Readers parse an integer beyond 2^53 as a binary64 when that value is exact.** Measured, this refutes itself. 592612204108959000 is not exact: its binary64 is 592612204108958976 (reference rows I08, I10). J2's 1152921504606847000 is not exact either (I11, I12). So the exactness test refuses the writer's own output, which is the defect itself.
- **(a′) Readers parse such an integer as a binary64 when it is the canonical spelling** (the W7c exporter's `_number`). This gives the same verdicts at a JSON reader, but:
  1. The same logical document gets different verdicts in-process (an `int` is refused) and over HTTP (the text is admitted). That breaks T07 §11.6, "transports add nothing".
  2. The MCP SDK has parsed the arguments before the binding sees any text, so a second, tree-shaped entry point would be needed.
  3. There are 15 `json.loads` sites in `src/process_runtime` outside `canonical.py`, including the round trips at `local.py:1287` and `revision_run.py:479`. Each would have to be converted, and the next one written would silently bring the defect back.
  4. `revision_run.py:479` feeds R0, where `execution_plan_r0` keeps a float as its `repr` and an integer as itself. Converting it changes R0's projection rule for such values.
- **(b) The writer re-spells** such a value, for example as `5.92612204108959e+17`. That is not RFC 8785: layout (a) is mandatory for `n ≤ 21`, and an independent JCS implementation would disagree byte for byte.
- **(b′) The writer refuses integral binary64 values above 2^53.** That refuses legitimate values. The measured certificate's condition estimate could not be written, so a verified run could not write its certificate.
- **(c) The verdict depends on where the `int` came from** ("from a canonical reader"). That needs a provenance tag through three parsers, and makes the verdict history-based, where D3.6 makes it value-based.

### A1.5 What Q29's entry refusal keeps refusing

It keeps refusing everything it refused before, except the integers of A1.2's middle row that are canonical spellings. In particular:
- The in-process `int` 2^53+1 is refused.
- **The JSON text `9007199254740993` is refused identically.** Every parser gives the `int` 9007199254740993, whose nearest binary64, 2^53, is spelled `9007199254740992`.
- 2^64−1, a seed or hash shape, is refused.
- 10^400 is refused, typed, with no `OverflowError`. 10^5000 is refused typed too, which is new: it used to raise a `ValueError`.
- NaN, ±∞, lone surrogates, non-string or repeated keys, and nodes outside the data model are unchanged.
- T07 G10's vectors, T06 A100's four integers, and A100 (b) keep their results.

### A1.6 What moves: the migration report

- **No byte of any previously admitted document changes.** The float branch and the `|n| ≤ 2^53` branch are untouched (J11). So every stored document digest is unchanged: `content_sha256`, the R0 digests, the manifests' self-hashes, the V17 fixture digests and every identity key (J16 (a)).
- **The admitted set only grows.** No document goes from admitted to refused (generator claim C5).
- **No stored document changes its verdict.**
  - At `afcc327`, the 346 git-tracked `.json`, `.jsonl`, `.yaml` and `.yml` files contain no integer beyond 2^53 and no integral float in `(2^53, 10^21)` (measured; J16 (c) re-runs this once at the amendment's commit).
  - No registered run holds such a value in a field R0 projects, or in a committed revision. By code reading (not measured), such a run would have raised `CanonicalizationError` in `r0_sha256`, and such a commit raises (A1.1).
  - The V17 T08 certificate holds one. Its bytes do not change; only `get_artifact`'s reading of them does.
- **Behaviour that changes, as intended:**
  - `get_artifact` serves such a file as JSON.
  - `commit_change` with such a float commits.
  - A revision run with such a value in a field R0 projects no longer raises. Its R0 carries the written `int`, as `revision_run.py:479` intends.
  - `read_number` reads an admitted integer as its binary64, where it read ±∞ before. No corpus document holds one.
- **One test expectation moves.** `tests/test_adr_0002_canonicalization.py::test_j7_an_integer_beyond_2_to_the_53_is_refused_not_rounded` asserts that `canonical_json(2**53 + 2)` raises. That value is registered nowhere in this ADR: J2 registers `2**53 + 1`, which stays refused. It is exactly the over-broad rule this amendment corrects (reference row I04). The test is renamed `test_j7_an_integer_is_refused_unless_it_spells_its_binary64`. It asserts that `2**53 + 1` raises and that `canonical_json(2**53 + 2) == b"9007199254740994"`.

### A1.7 Code changes (build lane; items 1–4, 6 and 7 in one commit, item 5 optionally in its own; `canonical.py` is identity-bearing, so the commit goes to the `reviewer`)

1. **`src/process_runtime/canonical.py`:**
   - add `integer_binary64` as A1.2 specifies;
   - route `_canonical_number`'s integer branch through it, with the message A1.2 specifies;
   - keep `_MAX_EXACT_INTEGER` private;
   - update the `first_noncanonical` docstring's list ("an integer that is not the canonical spelling of a binary64", replacing "an integer beyond 2⁵³");
   - update the module comment at `_MAX_EXACT_INTEGER`.
2. **`src/process_runtime/units/__init__.py`:** `read_number` imports `integer_binary64` instead of `_MAX_EXACT_INTEGER`. For an integer, it returns the reading if that is not `None`, else the infinity of the integer's sign. Update the docstring.
3. **Refusal messages:** `application/local.py:635` and `:1213`, and `application/operations.py:657`. In each, "an integer beyond 2^53" becomes "an integer beyond 2^53 that is not a binary64's canonical spelling". No test pins these strings (measured); none is in R0 or in a reviewed tool description.
4. **Comments and docstrings only:** `application/validation.py:175`, `application/operations.py:11` and `models/revision_flowsheet.py:461`.
5. **`bindings/http.py:261`:** a `ValueError` from `json.loads` that is not a `JSONDecodeError` is refused typed as `invalid_request` ("the request body is not JSON this server parses"), 422, never `internal_error`.
6. **`benchmarks/t07/v17/export.py`:** delete `_number` and `_MAX_EXACT_INTEGER`. `read_document` becomes `json.loads(data, object_pairs_hook=_unique)`.
7. **Tests:** J10–J17 go in a new module, `tests/test_adr_0002_a1_integers.py`, one function per assertion (`test_j10_…`), plus the renamed J7 test. No reader is changed, and none may gain a `parse_int` hook (J17).

### A1.8 Acceptance evidence — assertions J10–J17

Every tolerance is **exact**. Each expectation is a verdict, a byte string, or a binary64 compared bit for bit (`struct.pack(">d", x)`). Nothing is computed in floating point that could round, so there is no roundoff floor to stay above. The smallest error worth catching, one wrong verdict or one wrong bit, fails the comparison. "The reference" is `adr0002_a1_reference.json`, and the rows' `why` fields say why each integer is registered. The pairs I06/I07, I10/I08, I11/I12, I14/I15 and I17/I18 share a binary64 and have opposite verdicts, so a rule keyed on magnitude or on exactness fails them.

The registered states, transcribed from the reference. The reference, not this table, is what a test reads.

| Id | n | Before | After | Nearest binary64 (bits) | Its spelling | Why |
| --- | --- | --- | --- | --- | --- | --- |
| I01 | `9007199254740992` | admitted | **admitted** | `4340000000000000` | `9007199254740992` | old boundary; A100 (b) |
| I02 | `9007199254740993` | refused | **refused** | `4340000000000000` | `9007199254740992` | J2, A100 (a), G10 |
| I03 | `-9007199254740993` | refused | **refused** | `c340000000000000` | `-9007199254740992` | sign of I02 |
| I04 | `9007199254740994` | refused | **admitted** | `4340000000000001` | `9007199254740994` | exact and self-spelled (old test_j7) |
| I05 | `18014398509481984` | refused | **admitted** | `4350000000000000` | `18014398509481984` | power of two, asymmetric interval |
| I06 | `36028797018963968` | refused | **refused** | `4360000000000000` | `36028797018963970` | exact, spelled by I07 |
| I07 | `36028797018963970` | refused | **admitted** | `4360000000000000` | `36028797018963970` | spelling of I06, inexact |
| I08 | `592612204108959000` | refused | **admitted** | `43a072c351d6f39a` | `592612204108959000` | the W7c witness |
| I09 | `-592612204108959000` | refused | **admitted** | `c3a072c351d6f39a` | `-592612204108959000` | sign of I08 |
| I10 | `592612204108958976` | refused | **refused** | `43a072c351d6f39a` | `592612204108959000` | exact value of I08 |
| I11 | `1152921504606846976` | refused | **refused** | `43b0000000000000` | `1152921504606847000` | exact, spelled by I12 |
| I12 | `1152921504606847000` | refused | **admitted** | `43b0000000000000` | `1152921504606847000` | J2 read back |
| I13 | `18446744073709551615` | refused | **refused** | `43f0000000000000` | `18446744073709552000` | u64 seed shape |
| I14 | `18446744073709551616` | refused | **refused** | `43f0000000000000` | `18446744073709552000` | exact, spelled by I15 |
| I15 | `18446744073709552000` | refused | **admitted** | `43f0000000000000` | `18446744073709552000` | spelling of I14 |
| I16 | `100000000000000000000` | refused | **admitted** | `4415af1d78b58c40` | `100000000000000000000` | largest 10^k without exponent |
| I17 | `295147905179352825856` | refused | **refused** | `4430000000000000` | `295147905179352830000` | exact, spelled by I18 (D3.3) |
| I18 | `295147905179352830000` | refused | **admitted** | `4430000000000000` | `295147905179352830000` | D3.3 spelling of 2^68 |
| I19 | `999999999999999999999` | refused | **refused** | `444b1ae4d6e2ef50` | `1e+21` | rounds to 1e21 |
| I20 | `1000000000000000000000` | refused | **refused** | `444b1ae4d6e2ef50` | `1e+21` | exponent-form guard |
| I21 | `10^400` | refused | **refused** | — | — | beyond binary64; A100 (a) |
| I22 | `-10^400` | refused | **refused** | — | — | sign of I21 |

- **J10 — the rule, on the 22 registered integers.**
  - (a) For each row with `verdict` admitted:
    - `canonical_json(n) == row.n.encode()`;
    - `integer_binary64(n)` is a float whose bits are `row.binary64`;
    - `units.read_number(n)` is that float, bit for bit;
    - where `|n| > 2^53`, `canonical_json(integer_binary64(n)) == row.n.encode()`: the `int` and its binary64 are one JSON number.
  - (b) For each refused row:
    - `canonical_json(n)` raises `CanonicalizationError`, and its message contains `is not the canonical spelling of a binary64`;
    - `integer_binary64(n) is None`;
    - `read_number(n)` is `math.inf` if `n > 0`, else `-math.inf`.
  - (c) `first_noncanonical({"v": [0, n]})` is `None` for an admitted row and `"/v/1"` for a refused one, with no other exception on any row.
- **J11 — unchanged at and below 2^53.** `canonical_json(n) == str(n).encode()` and `integer_binary64(n) == float(n)`, for `n` in `{0, ±1, ±(2^53−1), ±2^53}` and for the 100 000 draws of the reference's `samples.j11`. (Prototype: 0.18 s.)
- **J12 — closure.** The documents are:
  - `{"v": [f]}` for every `f` kept by `samples.j12` (98 221 of 100 000 draws, measured);
  - each of J1's registered values, and J2's list;
  - the witness `{"regularity": {"inverse_one_norm_estimate": 5.92612204108959e17}, "verification_status": "VERIFIED"}`.

  For each, with `b = canonical_json(d)` and `r = json.loads(b)`:
  - `first_noncanonical(r) is None`;
  - `canonical_json(r) == b`;
  - every numeric leaf of `r` satisfies `float(leaf)` equal bit for bit to the original, with `-0.0` taken as `+0.0` (ADR 0001 D1.5; J7 decodes it so).

  At `afcc327`, all 98 221 draws fail, and so do J1's `1e16`, `1e20` and `2.0**68`, J2's list and the witness (measured). With a prototype of A1.2, none fails (1.4 s).
- **J13 — every parser in use gives the same verdict.** For each reference row's text `t = row.n`, each of `json.loads(t)`, `pydantic_core.from_json(t)`, `yaml.safe_load(t)` and `canonical.load_document("[" + t + "]")[0]` is an `int` equal to `n`, and `first_noncanonical` of each gives J10's verdict. This pins the premise that no reader needs a number hook. A future parser that returns a float for a large integer text would silently admit a refused text's nearest binary64, and it fails here.
- **J14 — the entry points are typed, and the transports agree.** Use the harnesses of `tests/test_t07_transactions.py`, `tests/test_t07_w6a_http.py` and `tests/test_t07_w6b_mcp.py`.
  - (a) `commit_change` of `settings.x` gives `committed` for each of:
    - the float `5.92612204108959e17`;
    - the float `2.0**54`;
    - the `int` `592612204108959000`;
    - the `int` `2**53 + 2`.

    The stored document's canonical bytes hold `592612204108959000`, `18014398509481984` and `9007199254740994`, and its `content_sha256` recomputes from the stored document. At `afcc327`, the two floats raise (A1.1).
  - (b) For `2**55`, `2**64 − 1`, `2**53 + 1` and `10**5000`, the result is `rejected` with `document_not_canonical` at pointer `/edits/0/value`, and no exception. At `afcc327`, `10**5000` raises `ValueError`.
  - (c) Over HTTP and over MCP, an edit value given as the JSON text `36028797018963970` is accepted. `36028797018963968` is refused `document_not_canonical` at the in-process pointer. The in-process, HTTP and MCP results agree, as the §11.6 comparison already requires.
  - (d) An HTTP body holding a 4301-digit integer is refused with a 422 `invalid_request`, never `internal_error`.
- **J15 — `get_artifact` serves a canonical file as JSON.**
  - An artifact file whose bytes are `canonical_json` of J12's witness is returned by `get_artifact` as a mapping, not as lines, on all four transports. Its `/regularity/inverse_one_norm_estimate` is, after `float()`, 5.92612204108959e17 bit for bit.
  - Re-run G16-b, the ten V17 reference solutions over four transports: 40/40 clean, with the T08 certificate served as JSON. This closes the W7c finding.
  - A changed reference outcome is reported, never absorbed.
- **J16 — nothing registered moves** (compared with `afcc327`).
  - (a) R4-G1's identity protocol:
    - K05 `9a7b4e6d…`, T02 floats `9a8a5baf…` and syn001.py `67e47281…`;
    - keys t02–t06 as W0.1, and `t07` as at `afcc327`;
    - the 50 corpus `validate()` reports, byte-identical once `timestamp` is removed;
    - G1, G10, G11, G13 and G14 pass;
    - the full suite passes, with a count of at least `afcc327`'s plus the new tests.
  - (b) Without `_number`, the V17 exporter writes the W7c fixture set's export byte-identical to `afcc327`'s.
  - (c) Run once at the amendment's commit, and recorded in the manifest, not kept as a standing test: every git-tracked `.json`, `.jsonl`, `.yaml` and `.yml` file parses, and none holds an integer beyond 2^53 or an integral float in `(2^53, 10^21)` (at `afcc327`: 346 files, 0 and 0).
- **J17 — one rule.** No file under `src/process_runtime/` other than `canonical.py`, and none under `benchmarks/t07/`, contains `_MAX_EXACT_INTEGER`, `2**53`, `2 ** 53`, `1 << 53` or `parse_int=` (docstrings write 2⁵³). This is a text scan. It fails if a second copy of the rule, or a reader-side number hook, is added.

### A1.9 What this amendment does not establish

- **Not general I-JSON conformance.** A number text with a fraction or an exponent is still read by the parser as its nearest binary64, silently, even when that loses digits: `9007199254740993.0` reads as 2^53 and is admitted. That is unchanged and was not examined here. Noncharacters remain T07 R4-O1's question.
- **Not Q1.** Q1 asks whether `repr`'s digit selection equals ECMA-262's for every double. The reference's oracle checks it only for the 22 registered integers and the ≈ 24 000 integers of claim C7's windows, and only in this band.
- **Not that every consumer of a parsed number is right.** A Python reader of canonical JSON now receives the `int` `592612204108959000` for the binary64 5.92612204108959e17, and in Python `592612204108959000 == 5.92612204108959e17` is **False**, because int/float comparison is exact. Anything that compares a parsed number with a computed float must compare `float(x)`, or use `units.read_number` (A1-Q2).
- **Not a validation of anything physical**, and no change to any requirement's status. The G16-b re-run is evidence that the fix works, not an empirical validation.

### A1.10 Open questions, with defaults

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| A1-Q1 | Should readers hand back a float rather than an `int` for such a value, for consumers' convenience? | needs the user's preference | **No.** The parsed document is the file's document, and a conversion would be a second rule (A1.4 (a′)). Reversible by one reader function, if ever wanted. |
| A1-Q2 | Does any code under `src/` compare a number parsed from canonical JSON with a computed float using `==`? | needs a fact: an audit of comparisons downstream of `json.loads`, in the `reviewer`'s pass over this commit | **None is known.** J14 and J15 exercise the two paths that read such values. A hit is fixed with `float()` at the comparison, never with a reader hook. |
| A1-Q3 | Should a lossy float text (`9007199254740993.0`, `0.1000000000000000000001`) be refused? | needs the user's preference | **No, unchanged.** Refusing it needs a text-level reader hook in every parser, which is out of proportion to any case seen. |

### A1.11 Register text (the build lane adds it to R-A02 at T07 W8)

*Amendment 1 (2026-09-27): an integer is canonical exactly when its digits are the canonical spelling of its nearest binary64.* That is every integer up to 2^53, exactly one per binary64 in `(2^53, 10^21)`, and none from 10^21. The verdict is on the digits, so an in-process `int` and every parser agree, and no reader has a number hook. `canonical.integer_binary64` is the one implementation. **Rejected:** exactness as the criterion, which refuses the writer's own `592612204108959000`; a reader-side hook, which splits in-process from HTTP and needs a second entry point for MCP; the writer re-spelling, which is not RFC 8785; and provenance-dependent verdicts. No stored byte or digest moves. Evidence: J10–J17, `adr0002_a1_reference.json`.
