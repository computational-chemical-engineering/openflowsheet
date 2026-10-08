"""M01.A37: IDAES 2.13 conformance of pr-c1-v1 (M01 spec §9.8, WO-5).

`benchmarks/m01/idaes-conformance.json` is the record `benchmarks/m01/idaes_conformance.py` writes
in the IDAES environment (`scripts/build-reference-envs.sh idaes`); no IDAES is needed here. These
tests check that the record was made from the committed records, at the registered states, in the
hashed environment, and compare its numbers with the provider's at A37's tolerances: at V1, V2 and
L1, |Δ ln φ| ≤ 1e-9 and Z relative ≤ 1e-9; at F1 and F11, |Δβ| ≤ 1e-8 and y* relative ≤ 1e-8.
The record's enthalpies and the flash phases' Z and ln φ are recorded, not asserted (A37 names
none of them).

Measured at WO-5 (pr-c1-v1 against the committed record): Z rel ≤ 4.3e-16 and |Δ ln φ| ≤ 3.6e-14
(L1; ≤ 1.9e-16 at V1, V2); |Δβ| 4.2e-12 (F1), 8.2e-13 (F11); y* rel 7.1e-11 (F1), 3.7e-11 (F11).
The y* gap is IDAES's SmoothVLE, which evaluates the equilibrium at T_eq = T − 2.0e-9 K (F1;
−1.0e-9 K at F11, the record's `T_equilibrium_minus_T_K`): the provider's y* at T_eq agrees with
IDAES's to 1.7e-13 (F1) and 8.8e-14 (F11).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml, sha256_of

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider, load_records

M01 = REPO_ROOT / "benchmarks" / "m01"
RECORD: Mapping[str, Any] = load_json(M01 / "idaes-conformance.json")
CLOSED: Mapping[str, Any] = load_yaml(M01 / "reference_values.yaml")["closed_form"]
CONTEXT = EvaluationContext(model_version="m01-idaes-conformance", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
#: M01.A37's tolerances (spec §9.8).
LNPHI_ABS = 1e-9
Z_REL = 1e-9
BETA_ABS = 1e-8
Y_STAR_REL = 1e-8
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _rel(value: float, expected: float) -> float:
    return abs(value - expected) / abs(expected)


def test_the_record_is_a37s_and_its_environment_is_hashed() -> None:
    assert RECORD["record"] == "m01-idaes-conformance"
    assert RECORD["assertion"] == "M01.A37"
    assert RECORD["status"] == "measured" and RECORD["judged"] is False
    env = RECORD["environment"]
    assert env["lock_sha256"] == sha256_of(REPO_ROOT / "spikes/references/idaes-requirements.lock")
    for key in ("pip_freeze_sha256", "idaes_data_bin_tree_sha256", "ipopt_sha256"):
        assert SHA256.match(env[key]), key
    assert SHA256.match(env["cubic_roots_sha256"])
    assert set(env["idaes_extension_sha256"]) == {
        "idaes-lib-ubuntu2204-x86_64.tar.gz",
        "idaes-solvers-ubuntu2204-x86_64.tar.gz",
    }
    assert all(SHA256.match(value) for value in env["idaes_extension_sha256"].values())
    assert env["packages"]["idaes-pse"] == "2.13.0"
    assert env["ipopt_version"].startswith("3.13.2")
    # The same Peng-Robinson constants as the spec's (§4.1).
    pr = env["idaes_pr_constants"]
    assert (pr["omegaA"], pr["coeff_b"], pr["u"], pr["w"]) == (0.45724, 0.0778, 2, -1)


def test_the_record_was_made_from_the_committed_records() -> None:
    inputs = RECORD["inputs"]
    assert inputs["components_yaml_sha256"] == sha256_of(M01 / "components.yaml")
    assert inputs["components_yaml_sha256"] == load_records().sha256
    echoed = inputs["records"]
    assert list(echoed) == list(COMPONENTS)
    for component in load_records().components:
        row = echoed[component.id]
        expected = {
            "molar_mass": component.molar_mass,
            "critical_temperature": component.critical_temperature,
            "critical_pressure": component.critical_pressure,
            "acentric_factor": component.acentric_factor,
            "standard_formation_enthalpy": component.formation_enthalpy,
            **{f"ideal_gas_cp_b{k}": b for k, b in enumerate(component.cp_coefficients)},
            "ideal_gas_cp_lower_temperature": component.cp_temperature_range[0],
            "ideal_gas_cp_upper_temperature": component.cp_temperature_range[1],
        }
        assert row == expected, component.id


@pytest.mark.parametrize(
    ("group", "sid"),
    [("phase_states", "V1"), ("phase_states", "V2"), ("phase_states", "L1")]
    + [("flash_states", "F1"), ("flash_states", "F11")],
)
def test_the_records_states_are_the_registered_states(group: str, sid: str) -> None:
    spec, registered = RECORD[group][sid]["spec"], CLOSED[group][sid]
    for key in ("T_K", "P_Pa"):
        assert float(spec[key]).hex() == float(registered[key]).hex(), key
    assert [float(v).hex() for v in spec["n_mol_s"]] == [
        float(v).hex() for v in registered["n_mol_s"]
    ]
    if group == "phase_states":
        assert spec["phase"] == registered["phase"]


@pytest.mark.parametrize("sid", ["V1", "V2", "L1"])
def test_a37_phase_states_agree_with_idaes(sid: str) -> None:
    entry = RECORD["phase_states"][sid]
    spec, idaes = entry["spec"], entry["values"]
    assert entry["degrees_of_freedom"] == 0 and entry["max_constraint_residual"] <= 1e-15
    names = tuple(name for name in idaes if name.startswith("lnphi_"))
    assert names == (
        ("lnphi_NH3",) if spec["phase"] == "LIQUID" else tuple(f"lnphi_{c}" for c in COMPONENTS)
    )
    state = StreamState(n=tuple(spec["n_mol_s"]), temperature=spec["T_K"], pressure=spec["P_Pa"])
    ours = PROVIDER.evaluate_phase(
        PropertyRequest(state=state, phase=spec["phase"], properties=("Z", *names)), CONTEXT
    )
    assert ours.status == "ok", ours.message
    assert _rel(ours.values["Z"], idaes["Z"]) <= Z_REL
    for name in names:
        assert abs(ours.values[name] - idaes[name]) <= LNPHI_ABS, name


@pytest.mark.parametrize("sid", ["F1", "F11"])
def test_a37_flash_states_agree_with_idaes(sid: str) -> None:
    entry = RECORD["flash_states"][sid]
    spec = entry["spec"]
    assert entry["degrees_of_freedom"] == 0 and entry["initialization"] == "ok"
    assert (entry["solver_status"], entry["termination_condition"]) == ("ok", "optimal")
    assert math.isclose(entry["liquid"]["x_NH3"], 1.0, rel_tol=0.0, abs_tol=1e-12)
    state = StreamState(n=tuple(spec["n_mol_s"]), temperature=spec["T_K"], pressure=spec["P_Pa"])
    ours = PROVIDER.flash(FlashRequest(state=state), CONTEXT)
    assert ours.status == "ok" and ours.phase_signature == "TWO_PHASE", ours.message
    assert ours.vapor_fraction is not None
    assert abs(ours.vapor_fraction - entry["vapor_fraction"]) <= BETA_ABS
    assert _rel(ours.k_values["NH3"], entry["y_star"]) <= Y_STAR_REL
