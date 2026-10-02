"""Registered evaluation states, read as harness *input* only (specification §5).

Only `parameters`, `x_L`, `x_I` and the perturbed Newton state are read here. The expected
residuals and Jacobian entries in the same file are the judge's business; a harness that read
them could not be wrong.

S1–S6 are in the reference document. Three further states are defined by specification §5 prose
and are derived here so that both harnesses see identical inputs:

* `S1p` — the §9 Newton-step state, `linear_solve.S1_perturbed_newton_step.x_pert`, with S1's
  parameters (T ≠ T_spec there, so the T and P columns participate in the solve).
* `S7a` — S4's state and parameters with T = 450 K: out of the closed domain in temperature.
* `S7b` — S4's state and parameters with P = 40 000 Pa: out of the closed domain in pressure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

import yaml

REFERENCE_PATH: Final = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "p02" / "reference_values.yaml"
)

#: Variables of the I-form (specification §2.6), a subset of the L-form variables.
I_FORM_VARIABLES: Final = (
    "v_A",
    "v_B",
    "v_C",
    "l_A",
    "l_B",
    "l_C",
    "V",
    "L",
    "T",
    "P",
    "Q",
)

#: States evaluated by both harnesses, in order.
EVALUATION_ORDER: Final = ("S1", "S2", "S3", "S4", "S5", "S6", "S1p", "S7a", "S7b")

#: The two out-of-domain probes and the values that put them outside the closed domain (A17).
DOMAIN_PROBES: Final = {"S7a": ("T", 450.0), "S7b": ("P", 40000.0)}


@dataclass(frozen=True)
class StateInput:
    """The inputs of one registered state."""

    state_id: str
    feed: tuple[float, float, float]
    h_feed: float
    t_spec: float
    p_spec: float
    x_l: dict[str, float]
    x_i: dict[str, float]
    oracle_phase_state: str | None
    expect_domain_error: bool = False


def _floats(mapping: dict[str, Any] | None) -> dict[str, float]:
    return {key: float(value) for key, value in (mapping or {}).items()}


def load_directions(path: Path | None = None) -> dict[str, tuple[float, ...]]:
    """Read the registered directions `u_L`, `v_L` (and any others) from the reference document.

    Directions are harness *input*, like the state vectors: they say where to differentiate, not
    what the answer is.
    """
    with (path or REFERENCE_PATH).open(encoding="utf-8") as handle:
        document: dict[str, Any] = yaml.safe_load(handle)
    return {
        key: tuple(float(value) for value in values)
        for key, values in document.get("directions", {}).items()
        if isinstance(values, list)
    }


def load_states(path: Path | None = None) -> dict[str, StateInput]:
    """Read S1–S6 from the reference document and derive S1p, S7a and S7b."""
    with (path or REFERENCE_PATH).open(encoding="utf-8") as handle:
        document: dict[str, Any] = yaml.safe_load(handle)

    states: dict[str, StateInput] = {}
    for entry in document["states"]:
        parameters = entry["parameters"]
        feed = [float(value) for value in parameters["f_mol_per_s"]]
        states[entry["state_id"]] = StateInput(
            state_id=entry["state_id"],
            feed=(feed[0], feed[1], feed[2]),
            h_feed=float(parameters["H_feed_W"]),
            t_spec=float(parameters["T_spec_K"]),
            p_spec=float(parameters["P_spec_Pa"]),
            x_l=_floats(entry.get("x_L")),
            x_i=_floats(entry.get("x_I")),
            oracle_phase_state=entry.get("oracle_phase_state"),
        )

    perturbed = _floats(document["linear_solve"]["S1_perturbed_newton_step"]["x_pert"])
    states["S1p"] = replace(
        states["S1"],
        state_id="S1p",
        x_l=perturbed,
        x_i={name: perturbed[name] for name in I_FORM_VARIABLES},
        oracle_phase_state=None,
    )

    for probe_id, (variable, value) in DOMAIN_PROBES.items():
        base = states["S4"]
        x_l = dict(base.x_l)
        x_l[variable] = value
        states[probe_id] = replace(
            base,
            state_id=probe_id,
            x_l=x_l,
            x_i={name: x_l[name] for name in I_FORM_VARIABLES},
            oracle_phase_state=None,
            expect_domain_error=True,
        )

    return states
