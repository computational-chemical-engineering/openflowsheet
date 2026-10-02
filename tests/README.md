# `tests/`

Risk-based test suite for OpenFlowsheet (blueprint §13.1, §15). Tests are the acceptance
evidence referenced by `docs/requirements.yaml` and by each `evidence/<package>/<commit>/manifest.json`;
their node IDs are recorded in the ledger as packages are implemented.

Present now (introduced by **P00**, repository bootstrap):

| File | Checks |
| --- | --- |
| `test_document_hashes.py` | The SHA-256 of `docs/blueprint-v3.1.md` equals the baseline hash in the plan header |
| `test_package_imports.py` | All nine subpackages import and `__version__` is present |
| `test_requirements_ledger.py` | `docs/requirements.yaml` validates, hashes agree, references resolve, no placeholders |
| `test_evidence_manifests.py` | Every committed evidence manifest validates and names a real commit |

Added by **P01**:

| File | Checks |
| --- | --- |
| `test_syn001_oracle.py` | Thermodynamic identities, K-values, flash classification and zero-flow behavior, recycle invariance, energy closure, the mixer domain margin, argument validation, and that the oracle does not import `openflowsheet` |
| `test_syn001_reference_values.py` | The oracle against Fable's independent 20-digit reference values: K grid, every registered variant's numbers and phase states, and reference-file integrity |
| `test_schemas_p01.py` | The six P01 schemas, their round-trip fixtures and deliberate rejections, the ADR 0001 D1 unit rules, and cross-document consistency between the registry, the case revisions, the component records and the declared model manifests |

Added by **ADR 0008**:

| File | Checks |
| --- | --- |
| `test_adr_0008_transient_readiness.py` | Pins the evaluation-boundary field sets and method arities (no time coordinate), the coverage properties of the state hash (every coordinate at full precision, order, signed zero, nothing else), and the registered accumulation classification and balance-row statements of the six SYN-001 manifests |

Amendment 1 adds U1, U1b, U2, U2b: every physical holdup in the unit library is internal energy or component amounts, never an enthalpy, and only the PTC path imports the residence-time pseudo-holdup mapping directly.

`tests/fixtures/schemas/` holds the round-trip fixtures. An invalid fixture is a document with
`expect_error` and `document` keys: it must be rejected, and the rejection message must contain
the reason it declares, so a fixture cannot pass by failing for an unrelated reason. The
ProcessRevision and ComponentRecord fixtures are the real SYN-001 documents rather than copies,
so the schema and the files the rest of the package uses cannot drift apart.

What arrives later: backend
composition and chain-rule fixtures (P02); conformance, solve-trace, certificate, failure, and
replay tests (K01–K06); structural, globalization, phase, homotopy/PTC, and adversarial
verifier tests (T01–T06); agent-task and transport tests (T07).

Self-generated outputs are regression fixtures, not validation: a correctness fixture needs an
analytic or independent expectation (`CLAUDE.md`, "Scientific conduct"). Coverage is a
diagnostic, never a claim of mathematical correctness.
