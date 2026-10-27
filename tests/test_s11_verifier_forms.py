"""S11 WO-A3: the verifier's own provider table by basis and the declared-phase mixture form.

`docs/derivations/S11-design.md` §4.6 (ADR 0050 D5; register R-804), assertions S11.A16–A19, on
S11.A12's routing flowsheets (`tests/test_s11_routing.py`). The CoolProp cases need the optional
`coolprop` extra and are skipped with a reason without it.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import pytest
from m02_wo8_support import solve
from test_s11_routing import CASE_PARAMS, case_revision

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import (
    IAPWS95_BASIS,
    WILSON_BASIS,
    component_basis,
    parse_revision,
)
from openflowsheet.thermo import PropertyProvider, PropertyRequest
from openflowsheet.verify import certificate
from openflowsheet.verify.certificate import (
    FRESH_PROVIDERS,
    CheckPolicy,
    SolutionCertificate,
    fresh_provider,
    verify_revision,
)
from openflowsheet.verify.checks import VerifierError
from openflowsheet.verify.table import revision_checks

CONTEXT = EvaluationContext(model_version="s11-a3", constants_sha256="0" * 64)


class Recording:
    """A provider that records every property id it is asked for, and forwards everything."""

    def __init__(self, provider: PropertyProvider) -> None:
        self._provider = provider
        self.asked: list[str] = []

    def evaluate_phase(self, request: PropertyRequest, context: Any) -> Any:
        self.asked += list(request.properties)
        return self._provider.evaluate_phase(request, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)


def _certify(case: str, *, declared: bool = True) -> SolutionCertificate:
    document = case_revision(case, declared=declared)
    solved = solve(document)
    assert solved.run.outcome == "CONVERGED", solved.run.message
    return verify_revision(
        solved.binding, document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    )


def _by_id(certificate_: SolutionCertificate) -> Mapping[str, Any]:
    return {check.id: check for check in certificate_.checks}


# -- S11.A16: declared phases verify -----------------------------------------------------------


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_a16_the_routing_flowsheets_verify_with_declared_phases(case: str) -> None:
    issued = _certify(case)
    checks = _by_id(issued)
    assert not [c.id for c in checks.values() if c.result == "unsupported"]
    assert not [c.id for c in checks.values() if c.result == "fail"]
    energy = checks["energy_balance.SP"]
    assert energy.result == "pass" and abs(energy.value) <= energy.tolerance
    for stream in ("S1", "S2", "S3"):
        admissible = checks[f"phase_admissibility.stream.{stream}"]
        assert admissible.result == "pass", admissible
        assert "shares the property provider" in admissible.independence_qualification


# -- S11.A17: without declared phases the energy checks are blocked ----------------------------
#
# The routing ports take `liquid` or `vapor` only, so the binder refuses a routing flowsheet with
# a `vapor_liquid` stream (`port_phase_unsupported`): no bound revision reaches the unlifted path.
# It is exercised on the table itself, with the splitter's products undeclared, at the state the
# declared flowsheet solved to (docs/S11A_DECISIONS.md).


def _undeclared_checks(case: str, provider: Any = None) -> Mapping[str, Any]:
    solved = solve(case_revision(case))
    assert solved.run.outcome == "CONVERGED" and solved.run.state is not None
    undeclared = case_revision(case, declared=False)
    view = parse_revision(undeclared)
    basis = component_basis(undeclared)
    checks = revision_checks(
        view,
        (),
        solved.run.state,
        provider=fresh_provider(basis) if provider is None else provider,
        context=CONTEXT,
        tolerances=CheckPolicy().tolerances,
    )
    return {check.id: check for check in checks}


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_a17_without_declared_phases_the_energy_checks_are_blocked(case: str) -> None:
    checks = _undeclared_checks(case)
    energy = [c for c in checks.values() if c.category == "energy_balance"]
    assert {c.id for c in energy} == {"energy_balance.SP", "energy_balance.envelope"}
    for check in energy:
        assert check.result == "unsupported", check
        assert check.reason is not None and "unlifted(S2)" in check.reason
    admissibility = sorted(i for i in checks if i.startswith("phase_admissibility.stream."))
    assert admissibility == ["phase_admissibility.stream.S1"]
    assert not [c.id for c in checks.values() if c.result == "fail"]


# -- S11.A18: no lnK and no h_<c> from a non-SYN-001 provider ---------------------------------


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_a18_the_verifier_asks_no_lnk_and_no_component_enthalpy(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[Recording] = []
    original = certificate.fresh_provider

    def recorded(basis: Any) -> Any:
        provider = Recording(original(basis))
        made.append(provider)
        return provider

    monkeypatch.setattr(certificate, "fresh_provider", recorded)
    _certify(case)
    made.append(Recording(original(component_basis(case_revision(case)))))
    _undeclared_checks(case, made[-1])
    assert len(made) == 2 and all(p.describe().provider_id != "syn001" for p in made)
    asked = {name for provider in made for name in provider.asked}
    assert "h" in asked
    assert not [name for name in asked if name == "lnK" or name.startswith("h_")], asked


# -- S11.A19: the verifier's own table checks the basis ---------------------------------------


def test_a19_a_basis_whose_components_disagree_is_a_mismatch() -> None:
    assert FRESH_PROVIDERS == (
        "syn001",
        "pr-c1-v1",
        "iapws95-v1",
        "wilson-ig-v1",
        "coolprop-heos-v1",
    )
    with pytest.raises(VerifierError, match=r"^basis_mismatch\(iapws95-v1 \['D2O'\]"):
        fresh_provider(dataclasses.replace(IAPWS95_BASIS, components=("D2O",)))
    reversed_ = dataclasses.replace(WILSON_BASIS, components=WILSON_BASIS.components[::-1])
    with pytest.raises(VerifierError, match=r"^basis_mismatch\(wilson-ig-v1 "):
        fresh_provider(reversed_)
    for basis in (IAPWS95_BASIS, WILSON_BASIS):
        assert fresh_provider(basis).describe().provider_id == basis.provider_id


def test_a19_a_coolprop_basis_names_its_one_fluid() -> None:
    co2 = component_basis(case_revision("coolprop"))
    assert fresh_provider(co2).describe().components == ("CO2",)
    two = dataclasses.replace(co2, components=("CO2", "N2"))
    with pytest.raises(VerifierError, match=r"^basis_mismatch\(coolprop-heos-v1"):
        fresh_provider(two)


def test_a19_an_unreadable_coolprop_revision_is_refused_typed() -> None:
    document = case_revision("iapws95")
    solved = solve(document)
    broken = {
        **document,
        "component_set": {
            "record_source": "benchmarks/s07/components.yaml",
            "components": ["CO2", "N2"],
        },
    }
    with pytest.raises(VerifierError, match=r"^revision_unreadable\(components_unsupported\)$"):
        verify_revision(solved.binding, broken, solved.run)
