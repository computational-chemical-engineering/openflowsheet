"""E01 WO-B4 (design §5.3, §4.8.4-§4.8.5; A25): Brightway's score of P4's foreground.

Runs in the audited `lca` environment (`scripts/build-lca-env.sh`; bw2calc and bw_processing
at the versions of `lca-pip.lock`). It uses neither `openflowsheet` nor bw2data: the synthetic
background `test-background-v1` is written here from the design note's description (§4.8.5) as
float64 bw_processing vectors, so Brightway's engine (bw2calc's `LCA`: technosphere solve,
inventory, characterisation) computes the score on matrices this script built itself. That keeps
the expectation independent of the adapter's own assembly (`brightway.py`, ESC-B1's float64
path), which A25 checks.

The foreground activity produces one unit and consumes P4's exchange amounts a_k per second
(`benchmarks/e01/lca_hand/lca_hand.yaml`, `p4.exchange_amounts_per_s`: the P1 fixture's net
electricity, boiler heat and raw material S1 in kWh, MJ and kg per second); P4 has no direct
emissions. The score is `impact.climate_change_test.rate` in kg CO2-eq per second.

Usage (lca env): `<venv-lca>/bin/python -I benchmarks/e01/brightway/foreground_p4.py` writes
`foreground_p4.yaml` beside it; `--print` writes to stdout.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
LCA_HAND = HERE.parent / "lca_hand" / "lca_hand.yaml"

#: §4.8.5, product/activity ids 1..3 (electricity kWh, heat MJ, chemical_x kg), 4 = foreground.
ACTIVITIES = {"tb.electricity": 1, "tb.heat": 2, "tb.chemical_x": 3}
FOREGROUND = 4
CO2, CH4 = 101, 102
#: (product row, activity column, amount): unit production and the inputs as negative entries.
TECHNOSPHERE = [
    (1, 1, 1.0), (2, 2, 1.0), (3, 3, 1.0),
    (2, 1, -0.25),  # electricity consumes 0.25 MJ heat
    (1, 2, -0.125),  # heat consumes 0.125 kWh electricity
    (1, 3, -0.5), (2, 3, -2.0),  # chemical_x consumes 0.5 kWh and 2 MJ
]  # fmt: skip
BIOSPHERE = [(CO2, 1, 0.5), (CO2, 2, 0.0625), (CH4, 2, 0.001953125), (CO2, 3, 0.25)]
CHARACTERISATION = [(CO2, 1.0), (CH4, 29.8)]  # climate_change_test


def _vector(dp: Any, matrix: str, rows: list[tuple[int, int, float]]) -> None:
    from bw_processing import INDICES_DTYPE

    dp.add_persistent_vector(
        matrix=matrix,
        name=f"e01-b4-{matrix}",
        indices_array=np.array([(r, c) for r, c, _ in rows], dtype=INDICES_DTYPE),
        data_array=np.array([a for _, _, a in rows], dtype=np.float64),
        flip_array=np.zeros(len(rows), dtype=bool),
    )


def score(amounts: dict[str, float]) -> float:
    import bw2calc as bc
    from bw_processing import create_datapackage

    inventory = create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    foreground = [(FOREGROUND, FOREGROUND, 1.0)] + [
        (ACTIVITIES[k], FOREGROUND, -a) for k, a in amounts.items()
    ]
    _vector(inventory, "technosphere_matrix", TECHNOSPHERE + foreground)
    _vector(inventory, "biosphere_matrix", BIOSPHERE)
    method = create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    _vector(method, "characterization_matrix", [(b, b, cf) for b, cf in CHARACTERISATION])
    lca = bc.LCA({FOREGROUND: 1.0}, data_objs=[inventory, method])
    lca.lci()
    lca.lcia()
    for name in ("technosphere_matrix", "biosphere_matrix", "characterization_matrix"):
        assert getattr(lca, name).dtype == np.float64, name
    return float(lca.score)


def build() -> dict[str, Any]:
    hand = yaml.safe_load(LCA_HAND.read_text(encoding="utf-8"))["p4"]
    amounts = {k: float(v["value"]) for k, v in hand["exchange_amounts_per_s"].items()}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rate = score(amounts)
        unit_scores = {k: score({k: 1.0}) for k in ACTIVITIES}
    return {
        "id": "e01-brightway-foreground-p4-v1",
        "script": "benchmarks/e01/brightway/foreground_p4.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "amounts_from": "benchmarks/e01/lca_hand/lca_hand.yaml p4.exchange_amounts_per_s",
        "amounts_sha256": hashlib.sha256(LCA_HAND.read_bytes()).hexdigest(),
        "environment": {
            "bw2calc": importlib.metadata.version("bw2calc"),
            "bw_processing": importlib.metadata.version("bw_processing"),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "exchange_amounts_per_s": amounts,
        "unit_scores": unit_scores,
        "impact.climate_change_test.rate": rate,
        "unit": "kg CO2-eq per s",
    }


def main() -> int:
    text = yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)
    if sys.argv[1:] == ["--print"]:
        sys.stdout.write(text)
    elif not sys.argv[1:]:
        (HERE / "foreground_p4.yaml").write_text(text, encoding="utf-8")
    else:
        raise SystemExit("usage: foreground_p4.py [--print]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
