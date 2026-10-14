# V02 alpha gate (M07a) build-lane decisions log

Open choices the build lane made while executing `docs/derivations/V02-alpha-release-spec.md` §15, for the design-lane
read of WO-5 and WO-8 (spec §15, "Design-lane steps"). Each names the commit that carries it and the alternative.

## WO-5 (step 8, the surface chain; commit `b44f684`)

B-WO5-1 **D_2, c_2's registered digest.** §15 makes WO-5 depend on "link c_2 registered" at M02's merge; no register
entry or committed constant pins it (R-234 says "M02's digest is registered at the merge commit"; the M02 manifest at
`ba90619` records `383b4e2c…` as evidence, "not a pin"). Chosen: `scripts/m07a_rc.py` `LINKS[1].digest` =
`383b4e2c004810663a3e3f80c591730bc95894e35736619eacac0f51e51b5403`, measured on this branch's merge of `main`
(`46176a7`, `harness.tool_descriptions_sha256()`), equal to the manifest's `served_sha256`; the test holds it equal to
that manifest value and the manifest's `without_m02_sha256` equal to D_1. Alternative: a register entry (design lane)
naming D_2, which the constant would then cite. Needs: the design lane to register it (or name another value).

B-WO5-2 **Where step 8 lives.** A new `scripts/m07a_rc.py` with one subcommand, `surface` (record
`rc-alpha-surface.json`, step `surface-alpha`, `t08-rc-v1` format via `t08_rc.finish`). CI's `rc_alpha` runs every
other step through `t08_rc.py` unchanged. Alternative: an `m07a_rc.py` that re-exports all of `t08_rc`'s subcommands.

B-WO5-3 **G16-b loop restated.** `t08_rc.step_surface`'s G16-b loop is copied into `m07a_rc.g16b` (check id
`a37.g16b_clean`), because factoring it out would edit the 0.1 step, which §15 forbids. Alternative: refactor
`t08_rc.py` (rejected by the spec's "unchanged").

B-WO5-4 **Item 3 by substitution.** `v17-c2`'s two texts are substituted into the stripped, dumped tool list rather than
re-served through `mcp.description`; equivalent because each served description is its file byte for byte (asserted by
`served_texts_are_the_files` and by `test_m02s_surface_move_decomposes_onto_the_base`).

B-WO5-5 **R-133's file hashes.** Item 4's "whose files equal R-133's" has no registered number. Chosen: the two
reviewed hashes in `REVIEW.json` at `PUBLIC_ROOT` (v0.1.0), restated in `R133_FILE_SHA256` and tested against
`git show PUBLIC_ROOT:…/REVIEW.json`.

B-WO5-6 **Control readings.** (i) the added member also fails item 1 (the served digest is not D_2); "fails at link
m" is read as the first failing row being link m's. (ii) "one member too many" is `get_project`'s `head` removed after
`without_m02`. (iii) one byte of `list_jobs.md`, judged on `description_problems` (texts passed in, not written to
disk). (iv) s_1 replaced by the identity.

B-WO5-7 **CI gating.** `rc_alpha` joins `rc` in the `if` of `dist`, `bundle-set`, `rc-steps`, `rc-ensemble`
(`clean-install` and `bundle-replay` follow by `needs`); in `rc-steps` the 0.1 surface step is now `if: always() &&
inputs.rc` and the alpha's `if: always() && inputs.rc_alpha`. The `rc` path's behaviour is unchanged.

## WO-8 (the harvest of T08's manifest; commit `e808406`)

The E/S/P/B classification is a design-lane read (spec §15, as T08.A21's was). The draft, item by item, in
`benchmarks/t08/support_envelope.yaml` (T08 manifest `67c66d98…`):

B-WO8-1 **Restated rows.** `limitations[12..57]` are T08's restatements "Lxx: …" of envelope rows; each is E to its own
row (46 items). Alternative: P (they duplicate the envelope).

B-WO8-2 **V14 (b).** `limitations[2]`, `checks[42]` (T08.A70) and `checks[67]` (T08.B23) are E to L01 (precedent:
T04 `limitations[11]`). Alternative: also carry B8 (PTC-R1 qualification) as a second pointer.

B-WO8-3 **E with a judgement.** `[5]` (A45 under policy v2, pivot paths not compared) E L07; `[11]` (bitwise,
portability) E L07, L15; `[7]` (V19 feasibility) E L42, since the shipped `pr-c1-v1` row now carries the user-facing
remainder (vapour-only light gases, no mixture VLE validation, k_ij = 0). Alternative for `[7]`: S to M01's
`check:M01.A38`–`A40` (K_NH₃ pinned by R-152, property values chosen by M01).

B-WO8-4 **P.** `[0]` evidence class (precedent T07, M06 P; T06 chose E L18), `[1]` verdicts outside the schema,
`[3]` test provenance, `[4]` §A4.6 attestation, `[6]` B50 amended by Frank, `[8]` library-only (no envelope row or
backlog id names it), `[9]` A34's scope at T08's RC (MR-11 widens A34 for the alpha but not to replays), `[10]` RC
record storage. Questions: should `[8]` become an envelope row, and `[9]` a backlog id?

B-WO8-5 **The v0.1 size quote.** `test_a21_every_item_is_classified_once_and_resolves` filtered manifests by first
letter P/K/T, which now admits T08; it is scoped to exclude `evidence/T08/`, matching its comment ("18 manifests of
P00–T07"). Alternative: move the quote to `t08_reference.py`'s `HARVEST_PACKAGES`.

B-WO8-6 **Size and the matrix now.** `HARVEST_SIZE = (23, 316, 29)` is the tree's size today; WO-10 re-reads it at
`C_α` and M07a's manifest quotes it. `docs/support-matrix.md` is re-emitted now because T08.A23 requires it to match
the harvest; WO-10 re-emits it again after the `C_α` pin of `envelope_id` and `release` (not done here).
