"""M02 WO-5, opt-in (`pytest -m pymrm`; deselected in the default gate): the built reactor
environment verifies against its pins, its handshake measures a fingerprint, and the child
reproduces the probe's design-grid nominal outlet bitwise at the record's exact tube inputs
(M01.A47 (a), when the environment block equals the record's). The full adapter halves of
M01.A41-A48 are `benchmarks/m02/g10_adapter_halves.py`'s, recorded in
`benchmarks/m02/g10-adapter-halves.json`.

The environment is the one `env build --variant pymrm-6089593-g2-nz800-s123-v1` made: its manifest
names the variant that built it, so it verifies against v1. The child is not part of it, so v2
(the child of R-251, the same `env_id`) executes in it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import OutOfProcessBackend
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.adapters.pymrm import env
from openflowsheet.models.c1.boundary import PERMEATE_OUTLET_PRESSURE, TubeInlet

pytestmark = pytest.mark.pymrm

#: The variant that built the environment, and the current one, which executes in it.
BUILT_BY = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v1")
VARIANT = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
PROBE: dict[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m01" / "reactor-probe.json")


def test_the_environment_verifies_against_its_pins() -> None:
    assert env.environment_root(BUILT_BY) == env.environment_root(VARIANT)
    assert env.verify(BUILT_BY, overlay=REPO_ROOT / env.OVERLAY) == []


def test_a47a_the_nominal_outlet_is_the_probes_bitwise(tmp_path: Path) -> None:
    pinned = PROBE["pinned"]
    backend = OutOfProcessBackend(VARIANT)
    environment = backend.environment(tmp_path / "handshake")
    assert environment.failure is None and environment.fingerprint is not None
    fingerprint = environment.fingerprint
    block = {name: fingerprint["packages"][name] for name in PROBE["environment"]["packages"]}
    if (fingerprint["python"], fingerprint["platform"], block) != (
        PROBE["environment"]["python"],
        PROBE["environment"]["platform"],
        PROBE["environment"]["packages"],
    ):
        pytest.skip("another environment block: M01.A47 (b) decides (G10's record)")
    flow, temperature = pinned["F_ret_in_mol_s"], pinned["T_in_K"]
    tube = TubeInlet(
        flow=flow,
        composition=tuple(pinned["y_in"]),
        temperature=temperature,
        outlet_pressure=pinned["P_in_Pa"],
        coolant_flow=VARIANT.sweep_ratio * flow,
        coolant_composition=(0.0, 1.0, 0.0, 0.0, 0.0),
        coolant_temperature=temperature,
        coolant_outlet_pressure=PERMEATE_OUTLET_PRESSURE,
    )
    execution = backend.evaluate(tube, tmp_path / "nominal", LaunchProgress(), None)
    assert execution.status == "completed" and execution.tube_outlet is not None
    outlet = execution.tube_outlet
    assert [value.hex() for value in outlet["flows"]] == [
        float(value).hex() for value in pinned["outlet_n_mol_s"]
    ]
    assert float(outlet["temperature"]).hex() == float(pinned["T_out_K"]).hex()
