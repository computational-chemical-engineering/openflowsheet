# ADR 0077: S19 W5, identity re-registration by batch, with the identity pin

**Status:** **Accepted (Frank Peters, 2026-11-18, Decision Desk cards `ofs-s19-w5-fr1-providers` option A "All of
tier 3, pinned", `ofs-s19-w5-fr2-reregister` option B "Once per batch", `ofs-s19-w5-fr3-gend-clause` option A
"Approve E1 to E5"; all three sign-offs verified).** Proposed 2026-11-18 by the design lane (`specifier`) in
`docs/briefs/S19-W5-ruling.md` section 11 (merged on `wp/S19` at 2b5c1d13); filed from that draft unchanged except
for this status line. Normative text: the ruling (sections 4 to 9). **Amends:** ADR 0076, Affected requirements (F0 M9 and the built-in registry
identity "change once, in W5"; "Replay identity: unchanged"), Consequences, and Acceptance "End of W5"; S19
decision Q1 ("M1 to M8 unchanged"); the S19 end gate G-END ("F0 and MCP digest identical").

**Decision.**
- D1: the files of R are classified into the four tiers of the ruling's section 4, computed by
  `scripts/w5_identity.py sets`.
- D2: `thermo/syn001.py` is not edited in S19.
- D3: W5 re-registers, per batch and in one commit, exactly the values that are functions of the edited files'
  bytes (R1). The batches are N, P and L.
- D4: evidence is the exact moved-key check per step and the judged diff per batch; for tier 3 also the identity
  pin (R2).
- D5: no identity hole (R4). No provider or unit module is split in W5, except B7's data table through its
  generator.
- D6: B7 as in the ruling's section 8.
- D7: G-END's F0 clause as E1 to E5.
- D8: S10 A26's oracle is F0's registered M9 value instead of `main` (ruling R7, finding F-2).

**Alternatives rejected.**
- Re-registration per step: one identity change per step is not reviewable (Q1).
- Declared implementation versions instead of byte hashes: ADR 0060 D3 has the registry compute identities and
  never take them from an author; a declared version would let behaviour change unseen.
- Hashing a normalised AST or stripped source, so that comment edits do not move identities: refactoring changes
  the AST anyway, and it would change the identity formula of every provider for no gain in W5.
- Comparing artifacts after textual substitution of old by new identity strings: hashes computed over documents
  that contain identities (M3, M6, the bundle index) cannot be substituted. The pin moves the substitution to
  the source.
- Re-registering M7 as `MISMATCH`, or rewriting the v0.3.0 bundles: either would register a regression as
  expected, or end the 0.3.0 reproduction check.
- A production switch that overrides `implementation_sha256`: identity must not be overridable outside a test
  harness.

**Affected requirements.**
- F0 registry `benchmarks/f0/corpus.json`: M9 per batch; M2, M3 and M6 in batch P.
- E-F1-5's constant `tests/fixtures/registry/builtin-sha256.txt` and the built-in tables.
- The served `registry_sha256`.
- `model_version` of runs on four providers (batch P).
- Replay of earlier bundles on those providers, which becomes `MISMATCH` on `model_version`.
- G-END's F0 clause.
- Other packages' immutability assertions: S10 A26 (its oracle, D8); S11 A75 "v1 is not edited" (batch P); L01
  A22's pins of `pr_c1.py` and `models/c1/`, moved by L01's registered-move route (batches P and L).

**Migration impact.**
- Batches N and L: no user-visible change except `registry_sha256` in `list_capabilities` and in inspection
  responses.
- Batch P: 0.5.0 release notes list the moved provider fragments (old and new `[:12]`). v1 bundles from 0.4.x on
  those providers replay `MISMATCH` with the `model_version` difference listed. Nothing else in their reports
  changes.

**Acceptance evidence.**
- W5-T1 to W5-T7.
- W5-S1 to W5-S8 per step, and W5-K1 to W5-K8 per batch.
- B7-C1 to B7-C4.
- E1 to E5 at G-END.

---
