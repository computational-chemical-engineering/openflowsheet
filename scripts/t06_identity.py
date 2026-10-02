"""T06's part of the cross-platform identity (§10, A45), included by `k05_structural_identity.py`.

`docs/derivations/T06-corpus-spec.md` §10 (Amendments 1–3), ADR 0014 D8 (amended). Each case runs
under its **registered** policy (`benchmarks/registry.yaml`: the corpus row's `policy`, the
reference fixtures' `policy`, ADV-06 under the revision path's `T06-revision-v2`), so the key
records the registered results; NET-02's control under `T05b-v2` is its own entry:

- `cases` — every new flowsheet of §4.3 (THM-01, THM-02, THM-10, STA-02, NET-02, NET-03, NET-06,
  NET-09, NET-10, NET-11), `references` — REF-01…REF-07 (§9.2), and `adv06` — ADV-06 L, M, H
  (C1 bound with `NoisyProvider(level)`, §4.4): the full R0 record as `t05_identity.py` builds it
  — the execution plan's R0 projection, the outcome, `r0_projection` of the events, the
  structural report and, when converged, the certificate `verify_revision` issues, the root
  fingerprint through T03's projection, and the typed message's first line (`""` when none);
- `controls` — NET-02 under `T05b-v2` (`BOUND_BLOCKED`, the pre-ADR-0015 behaviour; it does not
  move), the same record;
- `validation` — STR-02 and STR-06: the validation report's status and each check's id and result;
- `sta03` — per unit variant (`-kgs`, `-degC`) and A69's two SYN-001-nominal spellings
  (`SPEC-feed-n-A` `3.6 kmol/h`, `SPEC-feed-T` `80.33 degF`): the validation status, `DIM-01`'s
  result and implicated ids, the legacy binding's conversion records (ADR 0016 D6's fields, every
  float as its binary64 `repr`) and the tear-path solve's R0 record under `SYN-001-K03`, which this
  script asserts equal to SYN-001-nominal's computed in the same run;
- `sta04` — `input_mapping.declared_components` and the revision-path R0 record under
  `T06-revision-v2`, asserted equal to C2's computed in the same run;
- `initializer_failures` — §8.7's three feeds (SYN-001-nominal's feed at 450.0 K, 279.0 K and
  400.0 K): the tear path's outcome and the message's first line (A62);
- `ensemble` — the definition, never an outcome: the 22 case ids with their fixture ids (the draw
  key's spelling, §6.3 (A3)), paths and selected coordinate ids; each path's policy id and its
  canonical hash (`run.manifest.policy_sha256`; A86 for `T06-revision-v2`); the profile, the key
  prefix, the RNG id, and the KATs' `k53` integers.

Floats-free: a plan's floats are declared scales and bounds kept as shortest decimal strings
(`execution_plan_r0`); a conversion record's floats are declared inputs and registered constants,
kept as `repr`; the fingerprint's `delta_scaled_inf` is a registered constant. Digests only of
declared inputs: `constants_sha256`, `variable_ids_sha256`, the model version's structure hash and
the policies' canonical hashes; the fingerprint's two state digests are dropped by T03's
projection. No per-start ensemble outcome and no measured float enters (blueprint §8.3). Every
case is built from uncached entry points, so two calls in one process are two solves.
"""

from __future__ import annotations

import copy
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from t03_identity import _fingerprint  # noqa: E402

#: §4.3's new flowsheets, in the corpus table's order.
NEW_CASES = (
    "THM-01",
    "THM-02",
    "THM-10",
    "STA-02",
    "NET-02",
    "NET-03",
    "NET-06",
    "NET-09",
    "NET-10",
    "NET-11",
)
#: §9.2's our-side revision fixtures (REF-08 is SYN-001-nominal, whose tear solve the rest of the
#: identity document already carries).
REFERENCES = ("REF-01", "REF-02", "REF-03", "REF-04", "REF-05", "REF-06", "REF-07")
#: ADV-06's levels (§4.4), and the registered revision-path policy it runs under.
ADV06_LEVELS = ("L", "M", "H")
ADV06_POLICY = "T06-revision-v2"
#: NET-02's registered control (ADR 0015; spec §3.2 NET-02 row): edge-off, `BOUND_BLOCKED`.
NET02_CONTROL = "T05b-v2"
#: STR-02, STR-06: validation only (never bound, compiled or solved).
VALIDATION_CASES = ("STR-02", "STR-06")
#: A69's two SYN-001-nominal spellings the `t06` key carries beside STA-03's variants (A2 (ii)).
A69_SPELLINGS = {
    "SYN-001-nominal:SPEC-feed-n-A=3.6kmol/h": ("SPEC-feed-n-A", 3.6, "kmol/h"),
    "SYN-001-nominal:SPEC-feed-T=80.33degF": ("SPEC-feed-T", 80.33, "degF"),
}
#: §8.7's three feed temperatures (K) of SYN-001-nominal (A62).
INITIALIZER_FEEDS = (450.0, 279.0, 400.0)
NOMINAL = ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"


def _first_line(message: str | None) -> str:
    return message.splitlines()[0] if message else ""


def _typed_prefix(message: str | None) -> str:
    """`initializer_failed(<id>): <status>: <unit>` — the typed part of a tear-path initializer
    failure (A62). The free text after it may quote a computed number (the 400 K case: "misplace the
    outlet temperature by 300 K"), which R-029 keeps out of an R0 record; A62's exact messages are
    asserted by `tests/test_t06_w11_initializer.py`, not here."""
    return ": ".join(_first_line(message).split(": ")[:3])


def _load(path: str | Path) -> dict[str, Any]:
    import yaml

    loaded: dict[str, Any] = yaml.safe_load((ROOT / path).read_text("utf-8"))
    return loaded


def _revision_record(binding: Any, document: Mapping[str, Any], policy: Any) -> dict[str, Any]:
    """`plan_revision` → `execute_plan` → `verify_revision` when `CONVERGED`: the R0 record."""
    from openflowsheet.orchestrator.execution import ExecutionPlan
    from openflowsheet.orchestrator.executor import execute_plan
    from openflowsheet.orchestrator.region import RegionResult
    from openflowsheet.orchestrator.revision import plan_revision
    from openflowsheet.run.identity import execution_plan_r0, r0_projection
    from openflowsheet.verify.certificate import verify_revision

    plan, report = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    converged = run.outcome == "CONVERGED"
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in run.trace.events],
        "structural-report.json": report.as_document(),
    }
    if converged:
        certificate = verify_revision(
            binding, dict(document), run, solve_plan=plan.steps[-1].solve_plan
        )
        artifacts["solution-certificate.json"] = certificate.as_document()
    detail = run.steps[-1].detail if run.steps else None
    fingerprint = (
        detail.root_fingerprint if converged and isinstance(detail, RegionResult) else None
    )
    return {
        "plan": execution_plan_r0(plan.as_document()),
        "outcome": run.outcome,
        **r0_projection(artifacts),
        "root_fingerprint": _fingerprint(fingerprint),
        "message": _first_line(run.message),
    }


def _revision_case(document: Mapping[str, Any], policy_id: str) -> dict[str, Any]:
    from test_t06_w4_registry import CONSTRUCTED

    from openflowsheet.application.revision_binding import (
        RevisionBinding,
        bind_revision_flowsheet,
    )

    binding = bind_revision_flowsheet(dict(document))
    assert isinstance(binding, RevisionBinding), binding
    return _revision_record(binding, document, CONSTRUCTED[policy_id])


def _corpus_row(case_id: str) -> dict[str, Any]:
    from test_t06_w4_registry import BY_ID

    row: dict[str, Any] = BY_ID[case_id]
    return row


def _cases() -> dict[str, Any]:
    out = {}
    for case_id in NEW_CASES:
        row = _corpus_row(case_id)
        assert row["path"] == "revision_eo", case_id
        out[case_id] = _revision_case(_load(row["revision"]), row["policy"])
    return out


def _controls() -> dict[str, Any]:
    row = _corpus_row("NET-02")
    (control,) = row["controls"]
    assert NET02_CONTROL in control["policies"]
    return {f"NET-02|{NET02_CONTROL}": _revision_case(_load(row["revision"]), NET02_CONTROL)}


def _references() -> dict[str, Any]:
    from test_t06_w4_registry import REGISTRY

    section = REGISTRY["reference_fixtures"]
    by_id = {fixture["id"]: fixture for fixture in section["fixtures"]}
    return {
        ref: _revision_case(_load(by_id[ref]["revision"]), section["policy"]) for ref in REFERENCES
    }


def _adv06() -> dict[str, Any]:
    from t06_adv06_support import CASE, NoisyProvider, bind_noisy
    from test_t06_w4_registry import CONSTRUCTED

    out = {}
    for level in ADV06_LEVELS:
        document = _load(CASE)
        binding = bind_noisy(document, NoisyProvider(level))
        out[level] = _revision_record(binding, document, CONSTRUCTED[ADV06_POLICY])
    return out


def _validation() -> dict[str, Any]:
    from openflowsheet.application.validation import validate

    out = {}
    for case_id in VALIDATION_CASES:
        report = validate(_load(_corpus_row(case_id)["revision"]))
        out[case_id] = {
            "status": report.status,
            "checks": [[check.id, check.result] for check in report.checks],
        }
    return out


def _conversion(record: Any) -> dict[str, Any]:
    """ADR 0016 D6's record, every float as its binary64 `repr` (declared inputs and registered
    constants, exact and platform-independent by §8.5)."""
    return {
        "source": record.source,
        "input_id": record.input_id,
        "value": repr(record.value),
        "unit": record.unit,
        "si_value": repr(record.si_value),
        "si_unit": record.si_unit,
        "rule": record.rule,
        "component": record.component,
        "molar_mass": None if record.molar_mass is None else repr(record.molar_mass),
    }


def _tear_record(flowsheet: Any) -> dict[str, Any]:
    """`solve_tear` under `SYN-001-K03` and `verify` when `CONVERGED`: the tear path's R0 record."""
    from test_t06_w4_registry import CONSTRUCTED

    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.run.identity import r0_projection
    from openflowsheet.verify.certificate import verify

    result, trace = solve_tear(flowsheet, policy=CONSTRUCTED["SYN-001-K03"])
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in trace.events],
    }
    if result.plan is not None:
        artifacts["solve-plan.json"] = result.plan.as_document()
    converged = result.outcome == "CONVERGED"
    if converged:
        artifacts["solution-certificate.json"] = verify(flowsheet, result).as_document()
    return {
        "outcome": result.outcome,
        **r0_projection(artifacts),
        "root_fingerprint": _fingerprint(result.root_fingerprint if converged else None),
        "message": _first_line(result.message),
    }


def _legacy_flowsheet(document: Mapping[str, Any]) -> tuple[Any, Any]:
    from openflowsheet.application.binding import Binding, bind_revision_or_reason

    binding = bind_revision_or_reason(dict(document))
    assert isinstance(binding, Binding), binding
    return binding, binding.flowsheet


def _sta03_entry(document: Mapping[str, Any], nominal: Mapping[str, Any]) -> dict[str, Any]:
    from openflowsheet.application.validation import validate

    report = validate(dict(document))
    (dim01,) = [check for check in report.checks if check.id == "DIM-01"]
    binding, flowsheet = _legacy_flowsheet(document)
    tear = _tear_record(flowsheet)
    if tear != nominal:
        raise AssertionError("a converted SYN-001 revision's tear record is not nominal's")
    return {
        "status": report.status,
        "dim01": {"result": dim01.result, "implicated": list(dim01.implicated_objects)},
        "conversions": [_conversion(record) for record in binding.input_mapping.conversions],
        "tear": tear,
    }


def _sta03() -> dict[str, Any]:
    nominal_document = _load(NOMINAL)
    nominal = _tear_record(_legacy_flowsheet(nominal_document)[1])
    out = {}
    for variant in _corpus_row("STA-03")["variants"]:
        out[variant["fixture"]] = _sta03_entry(_load(variant["revision"]), nominal)
    for key, (specification_id, value, unit) in A69_SPELLINGS.items():
        document = copy.deepcopy(nominal_document)
        (entry,) = (s for s in document["specifications"] if s["id"] == specification_id)
        entry.update(value=value, unit=unit)
        out[key] = _sta03_entry(document, nominal)
    return out


def _sta04() -> dict[str, Any]:
    from openflowsheet.application.revision_binding import (
        RevisionBinding,
        bind_revision_flowsheet,
    )

    row = _corpus_row("STA-04")
    document = _load(row["revision"])
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    record = _revision_case(document, row["policy"])
    twin = _revision_case(_load(_corpus_row("NET-08")["revision"]), row["policy"])
    if record != twin:
        raise AssertionError("STA-04's revision-path record is not C2's")
    return {
        "declared_components": list(binding.input_mapping.declared_components),
        "record": record,
    }


def _initializer_failures() -> dict[str, Any]:
    from test_t06_w4_registry import CONSTRUCTED

    from openflowsheet.orchestrator.tear import solve_tear

    out = {}
    for temperature in INITIALIZER_FEEDS:
        document = _load(NOMINAL)
        (entry,) = (s for s in document["specifications"] if s["id"] == "SPEC-feed-T")
        entry["value"] = temperature
        _, flowsheet = _legacy_flowsheet(document)
        result, _ = solve_tear(flowsheet, policy=CONSTRUCTED["SYN-001-K03"])
        out[repr(temperature)] = {
            "outcome": result.outcome,
            "message": _typed_prefix(result.message),
        }
    return out


def _ensemble() -> dict[str, Any]:
    from conftest import load_yaml
    from t06_ensemble_support import ensemble_cases

    from benchmarks.t06 import ensemble, generator
    from openflowsheet.run.manifest import policy_sha256

    cases = ensemble_cases()
    policies: dict[str, dict[str, str]] = {}
    for case in cases:
        entry = {"policy_id": case.policy.policy_id, "policy_sha256": policy_sha256(case.policy)}
        assert policies.setdefault(case.path, entry) == entry, case.case
    twin = load_yaml(ROOT / "benchmarks" / "t06" / "reference_values.yaml")
    kats = twin["closed_form"]["draw_known_answers"]
    return {
        "cases": [
            {
                "case": case.case,
                "fixture": case.fixture,
                "path": case.path,
                "coordinates": [c.id for c in ensemble.setup(case).coordinates],
            }
            for case in cases
        ],
        "policies": policies,
        "profile": generator.PROFILE,
        "key_prefix": generator.KEY_PREFIX,
        "rng": generator.RNG_ID,
        "kats_k53": [[kat["key"], generator.k53(kat["key"])] for kat in kats],
    }


def identity() -> dict[str, Any]:
    return {
        "cases": _cases(),
        "controls": _controls(),
        "references": _references(),
        "adv06": _adv06(),
        "validation": _validation(),
        "sta03": _sta03(),
        "sta04": _sta04(),
        "initializer_failures": _initializer_failures(),
        "ensemble": _ensemble(),
    }
