"""M01.A01, A02, A34 and the registered states' transcription (M01 spec §9, WO-4).

`docs/derivations/scripts/m01_reference.py --check` re-derives
`benchmarks/m01/reference_values.yaml` and `reactor-overlay.json` at 50 digits, re-checks its 82
claims, and requires the committed bytes to equal the regenerated ones (M01.A34; ~20 s, so it runs
on every gate).
`benchmarks/m01/external-crosscheck.json` is the record of the retrieval-equality check, run in its
own environment; its form is checked here (M01.A02), its `--check` is the evidence manifest's.

The transcription tests read the registered states the other M01 test modules do not: the flash
phases' properties at the TWO_PHASE states, the pure-component states, and PR's NH3 saturation.
`test_the_registered_state_ids_are_the_ones_the_tests_read` fails when the YAML gains or loses a
state, so no registered state goes untested by omission.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider, h_ig

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "m01_reference.py"
REFERENCE: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")
CLOSED = REFERENCE["closed_form"]
FLASH = CLOSED["flash_states"]
CONTEXT = EvaluationContext(model_version="m01-reference", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()


def _rel(value: float, expected: float) -> float:
    return abs(value - expected) / max(abs(expected), 1.0)


# -- A34, A02 ------------------------------------------------------------------------------------


def test_a34_the_generator_rederives_every_claim_and_the_committed_bytes() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert re.search(
        r"^82 claims hold; reference_values\.yaml matches; reactor-overlay\.json matches$",
        completed.stdout,
        re.MULTILINE,
    ), output
    claims = REFERENCE["generator_claims"]
    assert len(claims) == 82 and all(claim["holds"] is True for claim in claims)
    assert len({claim["id"] for claim in claims}) == 82


def test_a02_the_external_crosscheck_records_retrieval_equality() -> None:
    record = load_json(REPO_ROOT / "benchmarks" / "m01" / "external-crosscheck.json")
    assert record["retrieval_all_equal"] is True
    retrieval = record["retrieval"]
    assert list(retrieval) == list(COMPONENTS)
    for component, entry in retrieval.items():
        assert entry["equal"] and all(value is True for value in entry["equal"].values()), component
        assert entry["nasa7_low_range_equal"] is True, component
        assert entry["identifiers_equal"] is True, component


def test_a01_the_reference_was_generated_from_the_committed_records() -> None:
    records = (REPO_ROOT / "benchmarks" / "m01" / "components.yaml").read_bytes()
    assert REFERENCE["components_yaml_sha256"] == hashlib.sha256(records).hexdigest()


# -- coverage of the registration ------------------------------------------------------------------


def test_the_registered_state_ids_are_the_ones_the_tests_read() -> None:
    """The M01 test modules read these ids; a state added to or dropped from the YAML fails here."""
    assert list(CLOSED["phase_states"]) == [
        "V1",
        "V2",
        "L1",
        "L2",
        "V3",
        "V4",
        "V5",
        "U1",
        "U2",
        "U3",
        "U4",
        "U5",
        "U6",
    ]
    assert list(CLOSED["derivatives"]) == ["V1", "V2", "L1"]
    assert list(FLASH) == [f"F{k}" for k in range(1, 15)]
    assert list(CLOSED["boundary"]) == ["standin", "projection", "pressure_convention"]
    assert sorted(CLOSED["pure_component_states"]) == sorted(PURE)
    assert list(CLOSED["nh3_saturation_pr"]) == SATURATION


# -- the flash phases' properties at the TWO_PHASE states ------------------------------------------

TWO_PHASE = [fid for fid, state in FLASH.items() if state["phase_signature"] == "TWO_PHASE"]


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_the_two_phase_states_vapour_and_liquid_properties(fid: str) -> None:
    expected = FLASH[fid]
    state = StreamState(
        n=tuple(expected["n_mol_s"]), temperature=expected["T_K"], pressure=expected["P_Pa"]
    )
    result = PROVIDER.flash(FlashRequest(state=state), CONTEXT)
    assert result.vapor is not None and result.liquid is not None
    for phase, stream, block in (
        ("VAPOR", result.vapor, expected["vapour"]),
        ("LIQUID", result.liquid, expected["liquid"]),
    ):
        names = tuple(name for name in block if name in ("Z", *(f"lnphi_{c}" for c in COMPONENTS)))
        evaluated = PROVIDER.evaluate_phase(
            PropertyRequest(state=stream, phase=phase, properties=("h", *names)),  # type: ignore[arg-type]
            CONTEXT,
        )
        assert evaluated.status == "ok", evaluated.message
        assert _rel(evaluated.values["h"], block["h_J_mol"]) <= 1e-12, (phase, "h")
        for name in names:
            assert _rel(evaluated.values[name], block[name]) <= 1e-12, (phase, name)


# -- pure components -------------------------------------------------------------------------------

PURE = [
    "H2-VAPOR-268.15-1e7",
    "H2-VAPOR-673.15-1e7",
    "N2-VAPOR-268.15-1e7",
    "N2-VAPOR-673.15-1e7",
    "NH3-VAPOR-673.15-1e7",
    "NH3-LIQUID-268.15-1e7",
    "NH3-LIQUID-250-2.5e7",
    "Ar-VAPOR-268.15-1e7",
    "Ar-VAPOR-673.15-1e7",
    "CH4-VAPOR-268.15-1e7",
    "CH4-VAPOR-673.15-1e7",
]


@pytest.mark.parametrize("sid", PURE)
def test_pure_component_states(sid: str) -> None:
    expected = CLOSED["pure_component_states"][sid]
    component = sid.split("-")[0]
    index = COMPONENTS.index(component)
    n = tuple(1.0 if i == index else 0.0 for i in range(5))
    state = StreamState(n=n, temperature=expected["T_K"], pressure=expected["P_Pa"])
    result = PROVIDER.evaluate_phase(
        PropertyRequest(
            state=state, phase=expected["phase"], properties=("Z", "h", f"lnphi_{component}")
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    assert _rel(result.values["Z"], expected["Z"]) <= 1e-12
    assert _rel(result.values[f"lnphi_{component}"], expected["lnphi"]) <= 1e-12
    departure = result.values["h"] - h_ig(expected["T_K"], index)
    assert _rel(departure, expected["h_departure_J_mol"]) <= 1e-11


# -- PR's NH3 saturation: the provider's two pure phases are in equilibrium there ------------------

SATURATION = ["240", "260", "268.15", "280", "300", "320", "350", "380", "400"]


@pytest.mark.parametrize("temperature", SATURATION)
def test_nh3_saturation_states(temperature: str) -> None:
    expected = CLOSED["nh3_saturation_pr"][temperature]
    state = StreamState(
        n=(0.0, 0.0, 1.0, 0.0, 0.0), temperature=float(temperature), pressure=expected["P_sat_Pa"]
    )
    phases = {
        phase: PROVIDER.evaluate_phase(
            PropertyRequest(state=state, phase=phase, properties=("v", "h", "lnphi_NH3")),  # type: ignore[arg-type]
            CONTEXT,
        )
        for phase in ("LIQUID", "VAPOR")
    }
    liquid, vapour = phases["LIQUID"].values, phases["VAPOR"].values
    assert abs(liquid["lnphi_NH3"] - vapour["lnphi_NH3"]) <= 1e-12
    assert abs(liquid["v"] / expected["v_L_m3_mol"] - 1.0) <= 1e-12
    assert abs(vapour["v"] / expected["v_V_m3_mol"] - 1.0) <= 1e-12
    assert _rel(vapour["h"] - liquid["h"], expected["h_vap_J_mol"]) <= 1e-11
