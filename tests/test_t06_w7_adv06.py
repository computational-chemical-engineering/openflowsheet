"""T06 W7: ADV-06, the noisy callback — T6-A16, A17, A18 (spec §4.4, §13).

Spec `docs/derivations/T06-corpus-spec.md` as amended: C1 (`SYN-001-UL-C1`) bound with the
`NoisyProvider(level)` test double (`t06_adv06_support`) at the three registered levels, solved on
the revision path and certified (default check policy):

- **A16 (H)**, `η_h = 10 J/mol`, `η_K = 1e-3`: never `VERIFIED` or `RELAXED`; the outcome is typed,
  or the certificate `FAILED`/`UNVERIFIED`.
- **A17 (M)**, `η_h = 1e-5`, `η_K = 1e-11`: `CONVERGED`; `UNVERIFIED`; `limitations` exactly
  `[derivative_limitation]` (Amendment 1's M4 ruling: the shared-provider qualification lives in
  `independence_qualifications`, A33, not in `limitations`); every K04 §4.1–§4.7 check `pass`; the
  witness error inside §4.4's band.
- **A18 (L)**, `η_h = 1e-10`, `η_K = 1e-15`: `CONVERGED`; `VERIFIED`.

The revision path's registered policy is `T06-revision-v2` (§6.6 (A4)); each level also runs under
`T05b-v2`, the policy M4 measured under (`docs/t06-measurements-m45.md`), where the outcome is the
same. A32 over ADV-06 L's and M's certificates is `test_t06_w6_a32.py`'s. What the verifier's
fresh flashes see is recorded as §4.4 asks: nothing noisy — they call a clean provider.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT, load_yaml
from t06_adv06_support import CASE, KEY_PREFIX, LEVELS, NoisyProvider, adv06, bind_noisy, xi
from test_t06_w4_registry import BY_ID

import openflowsheet.application.revision_binding as revision_binding
import openflowsheet.thermo.syn001 as syn001
from benchmarks.t06.generator import uniform
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import PropertyProvider, PropertyRequest, StreamState

BANDS: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")[
    "closed_form"
]["adv06_noise_bands"]
#: The registered revision-path policy first (§6.6 (A1)), then M4's.
POLICIES = ("T06-revision-v2", "T05b-v2")
#: K04 §4.1–§4.7's check categories (`alias_certificates` included: absent on the revision path,
#: never excused if present); §4.8 is `derivative_witness`.
CHECKS_4_1_TO_4_7 = frozenset(
    {
        "residual",
        "alias_certificates",
        "material_balance",
        "energy_balance",
        "specification",
        "bounds_and_domain",
        "phase_admissibility",
        "independent_split",
    }
)
CONTEXT = EvaluationContext(model_version="t06-adv06", constants_sha256="0" * 64)


def _certificate(level: str, policy: str) -> dict[str, Any]:
    run = adv06(level, policy)
    assert run.run.outcome == "CONVERGED", (level, policy, run.run.message)
    assert run.certificate is not None
    document: dict[str, Any] = run.certificate.as_document()
    return document


# -- the double and its registration ----------------------------------------------------------


def test_adv06_is_registered_on_c1_with_the_double() -> None:
    case = BY_ID["ADV-06"]
    assert case["revision"] == CASE
    assert case["path"] == "revision_eo"
    assert case["provider"].startswith("NoisyProvider(level)")
    assert sorted(case["expected"]["levels"]) == sorted(LEVELS)
    assert case["assertion"] == "T6-A16, T6-A17, T6-A18"


def test_the_levels_are_the_registered_bands() -> None:
    """§4.4's amplitudes are `ref.closed_form.adv06_noise_bands`' (the strings are exact decimal
    renderings of the binary64 values)."""
    assert {
        level: (float(band["eta_h_J_per_mol"]), float(band["eta_lnK"]))
        for level, band in BANDS.items()
    } == dict(LEVELS)


def test_the_noise_is_a_deterministic_function_of_the_exact_request() -> None:
    """§4.4: `h_<c>` moves by `η_h ξ`, `lnK_<c>` by `η_K ξ`, `ξ = 2u − 1` of the request's key;
    derivatives, status and phase signature are the clean provider's; the answer does not depend
    on call order or history; a one-ulp change of the state draws a different noise."""
    clean = syn001.Syn001Provider()
    double = NoisyProvider("M")
    assert isinstance(double, PropertyProvider)
    assert double.describe() == clean.describe()
    state = StreamState(n=(0.3, 0.5, 0.2), temperature=350.0, pressure=1e5)
    for phase in ("LIQUID", "VAPOR"):
        request = PropertyRequest(state, phase, ("h", "lnK"), ("T", "P"))
        expected = clean.evaluate_phase(request, CONTEXT)
        first = double.evaluate_phase(request, CONTEXT)
        assert double.evaluate_phase(request, CONTEXT) == first
        assert NoisyProvider("M").evaluate_phase(request, CONTEXT) == first
        assert first.derivatives == expected.derivatives
        assert (first.status, first.phase_signature) == (expected.status, expected.phase_signature)
        assert (
            sorted(first.values)
            == sorted(expected.values)
            == sorted(f"{p}_{c}" for p in ("h", "lnK") for c in "ABC")
        )
        exact = "3fd33333333333333fe00000000000003fc999999999999a4075e0000000000040f86a0000000000"
        for name, value in first.values.items():
            key = f"{KEY_PREFIX}|M|{phase}|{name}|{exact}"
            eta = 1e-5 if name.startswith("h_") else 1e-11
            assert xi(key) == 2.0 * uniform(key) - 1.0
            assert -1.0 <= xi(key) < 1.0
            assert value == expected.values[name] + eta * xi(key)
            assert value != expected.values[name]
    # One ulp of temperature is another request, so another draw.
    moved = StreamState(n=state.n, temperature=math.nextafter(350.0, 400.0), pressure=1e5)
    noise = []
    for at in (state, moved):
        request = PropertyRequest(at, "LIQUID", ("h",))
        clean_h = clean.evaluate_phase(request, CONTEXT).values["h_A"]
        noise.append(double.evaluate_phase(request, CONTEXT).values["h_A"] - clean_h)
    assert noise[0] != noise[1]


def test_a_failed_evaluation_passes_through_unchanged() -> None:
    state = StreamState(n=(0.3, 0.5, 0.2), temperature=500.0, pressure=1e5)
    request = PropertyRequest(state, "LIQUID", ("h",))
    result = NoisyProvider("H").evaluate_phase(request, CONTEXT)
    assert result == syn001.Syn001Provider().evaluate_phase(request, CONTEXT)
    assert result.status == "out_of_domain"


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_the_double_is_bound_under_every_compiled_evaluation(level: str) -> None:
    """The M4 hook reaches the binding (the guard against `bind_revision_flowsheet`'s
    function-local import moving: were it hoisted, the patch would not reach the binding and this
    fails instead of silently testing the clean provider); the patch does not outlive the bind;
    the solve's and the verifier's compiled evaluations go through the double, and the verifier's
    fresh flashes do not (§4.4: recorded)."""
    run = adv06(level, POLICIES[0])
    assert run.binding.flowsheet.provider._provider is run.double
    assert syn001.Syn001Provider().__class__ is syn001.Syn001Provider
    assert not isinstance(syn001.Syn001Provider(), NoisyProvider)
    assert run.solve_calls["evaluate_phase"] > 0
    assert run.double.max_noise["h"] > 0.0 and run.double.max_noise["lnK"] > 0.0
    eta_h, eta_k = LEVELS[level]
    assert run.double.max_noise["h"] <= eta_h and run.double.max_noise["lnK"] <= eta_k
    if run.verify_calls is not None:
        assert run.verify_calls["evaluate_phase"] > 0
        assert run.verify_calls["flash"] == 0


def test_the_hook_refuses_a_binding_it_did_not_reach(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates the refactor the guard exists for — the provider class no longer read from the
    module attribute at bind time — and checks `bind_noisy` fails rather than binding clean."""
    real = syn001.Syn001Provider
    original = revision_binding.bind_revision_flowsheet

    def hoisted(document: Any) -> Any:
        with pytest.MonkeyPatch.context() as inner:
            inner.setattr(syn001, "Syn001Provider", real)
            return original(document)

    monkeypatch.setattr("t06_adv06_support.bind_revision_flowsheet", hoisted)
    with pytest.raises(AssertionError, match="NoisyProvider is not the binding's provider"):
        bind_noisy(yaml.safe_load((REPO_ROOT / CASE).read_text("utf-8")), NoisyProvider("L"))
    assert syn001.Syn001Provider is real


# -- A16, A17, A18 --------------------------------------------------------------------------


@pytest.mark.parametrize("policy", POLICIES)
def test_a16_h_is_never_verified_or_relaxed(policy: str) -> None:
    """A16: at H no `VERIFIED` or `RELAXED`; the outcome is typed, or the certificate `FAILED` or
    `UNVERIFIED`."""
    run = adv06("H", policy)
    if run.run.outcome != "CONVERGED":
        assert run.certificate is None
        assert run.run.message, "a typed failure carries its message"
        return
    assert run.certificate is not None
    assert run.certificate.verification_status in ("FAILED", "UNVERIFIED")


@pytest.mark.parametrize("policy", POLICIES)
def test_a16_h_fails_in_the_initializer_as_m4_measured(policy: str) -> None:
    """Regression pin (not validation): M4's measured H outcome — 10 J/mol of rough enthalpy
    noise breaks the valve's PH kernel in the traversal, before any Newton step."""
    run = adv06("H", policy)
    assert run.run.outcome == "INITIALIZATION_FAILED"
    assert run.run.message.splitlines()[0] == "initializer_failed(U-VLV): ph_ill_conditioned"
    assert "initializer_rejected" in [event.kind for event in run.run.trace.events]


@pytest.mark.parametrize("policy", POLICIES)
def test_a17_m_converges_unverified_on_the_witness_alone(policy: str) -> None:
    """A17: `CONVERGED`, `UNVERIFIED`, `limitations` exactly `[derivative_limitation]`, every
    §4.1–§4.7 check `pass`; the witness fails inside §4.4's band (above K04's tolerance, at most
    `witness_error_scaled_max`); the shared-provider qualification is in
    `independence_qualifications` on exactly A33's checks."""
    certificate = _certificate("M", policy)
    assert certificate["verification_status"] == "UNVERIFIED"
    assert certificate["false_success_detected"] is False
    assert [limitation["kind"] for limitation in certificate["limitations"]] == [
        "derivative_limitation"
    ]
    checks = certificate["checks"]
    categories = {check["category"] for check in checks}
    assert categories - CHECKS_4_1_TO_4_7 == {"derivative_witness"}
    assert [
        c["id"] for c in checks if c["category"] in CHECKS_4_1_TO_4_7 and c["result"] != "pass"
    ] == []
    failing = [c for c in checks if c["result"] != "pass"]
    assert [(c["category"], c["result"]) for c in failing] == [("derivative_witness", "fail")]
    witness = failing[0]["value"]
    assert witness > failing[0]["tolerance"]
    assert witness <= float(BANDS["M"]["witness_error_scaled_max"])
    assert certificate["derivative_provenance"]["witness_max_diff"] == witness
    # A33 (A4): the prefixed checks judged `pass` or `fail` — those that consulted the provider.
    qualified = {entry["check_id"] for entry in certificate["independence_qualifications"]}
    assert qualified == {
        c["id"]
        for c in checks
        if c["id"].startswith(("energy_balance.", "phase_admissibility.", "independent_split."))
        and c["result"] in ("pass", "fail")
    }
    assert qualified


@pytest.mark.parametrize("policy", POLICIES)
def test_a18_l_converges_verified(policy: str) -> None:
    """A18: `CONVERGED`, `VERIFIED`; the witness error at most §4.4's L bound (`≤ 6e-10`)."""
    certificate = _certificate("L", policy)
    assert certificate["verification_status"] == "VERIFIED"
    assert certificate["limitations"] == []
    assert [c["id"] for c in certificate["checks"] if c["result"] != "pass"] == []
    witness = certificate["derivative_provenance"]["witness_max_diff"]
    assert 0.0 < witness <= float(BANDS["L"]["witness_error_scaled_max"])
