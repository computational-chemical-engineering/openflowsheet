"""E01 WO-B1 (design §4.8.2, §4.8.5; ADR 0052 D8): write the shipped LCA tables.

- `gwp100-ipcc-ar6-v1.json` (`direct-factor-table-v1`): the IPCC AR6 WG1 GWP-100 values of
  Table 7.15 (Forster et al. 2021, ch. 7, p. 1017), verified by WO-B1 against the chapter PDF
  (sha256 below);
  `co2_non_fossil_air` 0.0 is the biogenic cut-off convention, stated, not a table value.
- `test-background-v1.json` (`unit-score-table-v1`): the synthetic background of §4.8.5, with a
  Brightway-importable description (`brightway`) and its hand-derived unit scores
  `q = (16.965625, 5.8625, 27.9578125)/31` (the nearest doubles; A24 recomputes them with
  Brightway, `benchmarks/e01/lca_hand/` in mpmath).

Each file's `sha256` is `tables.table_sha256` of its content. Usage:
    python scripts/e01_lca_data.py            # write both files
    python scripts/e01_lca_data.py --check    # exit 1 when a file differs from what this writes
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openflowsheet.assessment.lca.tables import table_sha256  # noqa: E402
from openflowsheet.canonical import document_sha256  # noqa: E402

OUT = ROOT / "src" / "openflowsheet" / "_data" / "assessment" / "lca"

#: The chapter PDF the values were read from (WO-B1, retrieved 2026-10-27).
IPCC_PDF = {
    "url": "https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_Chapter07.pdf",
    "sha256": "470d2662fdd212421617a32c684e8106a4221a7235bdfff40a278eff02febfa9",
    "retrieved": "2026-10-27",
}
IPCC_CITATION = (
    "Forster, P., T. Storelvmo, K. Armour, W. Collins, J.-L. Dufresne, D. Frame, D.J. Lunt, "
    "T. Mauritsen, M.D. Palmer, M. Watanabe, M. Wild, and H. Zhang, 2021: The Earth's Energy "
    "Budget, Climate Feedbacks, and Climate Sensitivity. In Climate Change 2021: The Physical "
    "Science Basis. Contribution of Working Group I to the Sixth Assessment Report of the "
    "Intergovernmental Panel on Climate Change. Cambridge University Press, pp. 923-1054, "
    "doi:10.1017/9781009157896.009. Table 7.15, p. 1017."
)


def _sealed(document: dict[str, Any]) -> dict[str, Any]:
    document = {key: value for key, value in document.items() if key != "sha256"}
    document["sha256"] = table_sha256(document)
    return document


def gwp100() -> dict[str, Any]:
    flows = [
        ("co2_fossil_air", "Carbon dioxide, fossil", 1.0),
        ("co2_non_fossil_air", "Carbon dioxide, non-fossil", 0.0),
        ("ch4_fossil_air", "Methane, fossil", 29.8),
        ("ch4_non_fossil_air", "Methane, non-fossil", 27.0),
        ("n2o_air", "Dinitrogen monoxide", 273.0),
    ]
    return _sealed(
        {
            "format": "direct-factor-table-v1",
            "table_id": "gwp100-ipcc-ar6-v1",
            "categories": [
                {
                    "category_id": "climate_change_gwp100_ar6",
                    "method": ["IPCC AR6", "climate change", "GWP-100"],
                    "unit": "kg CO2-eq",
                }
            ],
            "flows": [
                {"flow_id": f, "name": name, "compartment": ["air"], "unit": "kg"}
                for f, name, _ in flows
            ],
            "factors": [[value for _, _, value in flows]],
            "source": {
                "citation": IPCC_CITATION,
                "table": "Table 7.15, column GWP-100 (central values; the ± ranges are not used)",
                "document": IPCC_PDF,
                "read": {
                    "co2_fossil_air": "CO2 1.000",
                    "ch4_fossil_air": "CH4-fossil 29.8 ± 11",
                    "ch4_non_fossil_air": "CH4-non fossil 27.0 ± 11",
                    "n2o_air": "N2O 273 ± 130",
                },
                "conventions": {
                    "co2_non_fossil_air": "0.0: biogenic CO2 under the cut-off convention "
                    "(uptake and release both outside the factor); a stated convention, not a "
                    "Table 7.15 value",
                },
            },
            "rights": {
                "class": "open",
                "licence": "five numerical values from IPCC AR6 WG1 (© 2021 IPCC), reproduced "
                "as facts with their citation",
                "redistribution": "allowed",
                "notice": "Values from IPCC AR6 WG1 Chapter 7, Table 7.15. " + IPCC_CITATION,
            },
        }
    )


BIOSPHERE = "test-biosphere-v1"
BACKGROUND = "test-background-v1"
#: §4.8.5: activity -> (unit, si_per_unit, technosphere inputs, biosphere emissions, kg).
ACTIVITIES: dict[str, tuple[str, float, dict[str, float], dict[str, float]]] = {
    "tb.electricity": ("kWh", 3.6e6, {"tb.heat": 0.25}, {"co2_fossil_air": 0.5}),
    "tb.heat": (
        "MJ",
        1e6,
        {"tb.electricity": 0.125},
        {"co2_fossil_air": 0.0625, "ch4_fossil_air": 0.001953125},
    ),
    "tb.chemical_x": (
        "kg",
        1.0,
        {"tb.electricity": 0.5, "tb.heat": 2.0},
        {"co2_fossil_air": 0.25},
    ),
}
BW_UNITS = {"kWh": "kilowatt hour", "MJ": "megajoule", "kg": "kilogram"}
CATEGORY_METHOD = ["openflowsheet", "test", "climate_change_test"]
#: The hand solution of A s = e_k (§4.8.5), as exact rationals.
HAND_Q = {
    "tb.electricity": Fraction("16.965625") / 31,
    "tb.heat": Fraction("5.8625") / 31,
    "tb.chemical_x": Fraction("27.9578125") / 31,
}


def brightway_description() -> dict[str, Any]:
    """The background as Brightway `Database.write` and `Method.write` data (plain JSON)."""
    activities = {}
    for activity, (unit, _, inputs, emissions) in ACTIVITIES.items():
        exchanges: list[dict[str, Any]] = [
            {"input": [BACKGROUND, activity], "amount": 1.0, "type": "production"}
        ]
        exchanges += [
            {"input": [BACKGROUND, k], "amount": v, "type": "technosphere"}
            for k, v in inputs.items()
        ]
        exchanges += [
            {"input": [BIOSPHERE, e], "amount": v, "type": "biosphere"}
            for e, v in emissions.items()
        ]
        activities[activity] = {
            "name": activity,
            "unit": BW_UNITS[unit],
            "location": "GLO",
            "type": "process",
            "exchanges": exchanges,
        }
    return {
        "biosphere_database": BIOSPHERE,
        "biosphere": {
            "co2_fossil_air": {
                "name": "Carbon dioxide, fossil",
                "categories": ["air"],
                "unit": "kilogram",
                "type": "emission",
            },
            "ch4_fossil_air": {
                "name": "Methane, fossil",
                "categories": ["air"],
                "unit": "kilogram",
                "type": "emission",
            },
        },
        "technosphere_database": BACKGROUND,
        "activities": activities,
        "methods": [
            {
                "category_id": "climate_change_test",
                "method": CATEGORY_METHOD,
                "unit": "kg CO2-eq",
                "cfs": [
                    [[BIOSPHERE, "co2_fossil_air"], 1.0],
                    [[BIOSPHERE, "ch4_fossil_air"], 29.8],
                ],
            }
        ],
    }


def test_background() -> dict[str, Any]:
    description = brightway_description()
    return _sealed(
        {
            "format": "unit-score-table-v1",
            "table_id": BACKGROUND,
            "producer": {
                "engine": "hand",
                "derivation": "E01 design §4.8.5: q_k = c·B·A⁻¹e_k solved exactly; the nearest "
                "doubles of 16.965625/31, 5.8625/31, 27.9578125/31",
                "created": "2026-10-27",
            },
            "background": [
                {
                    "database": BACKGROUND,
                    "declared_version": "1",
                    "system_model": "synthetic (no allocation; three activities)",
                    "metadata_sha256": document_sha256(description),
                }
            ],
            "categories": [
                {
                    "category_id": "climate_change_test",
                    "method": CATEGORY_METHOD,
                    "unit": "kg CO2-eq",
                }
            ],
            "activities": [
                {
                    "activity_id": activity,
                    "key": [BACKGROUND, activity],
                    "name": activity,
                    "location": "GLO",
                    "unit": unit,
                    "si_per_unit": si,
                }
                for activity, (unit, si, _, _) in ACTIVITIES.items()
            ],
            "scores": [[float(HAND_Q[activity]) for activity in ACTIVITIES]],
            "rights": {
                "class": "open",
                "licence": "Apache-2.0 (synthetic data authored in this repository)",
                "redistribution": "allowed",
                "notice": "Synthetic test background; not the inventory of any real process.",
            },
            "brightway": description,
        }
    )


def files() -> dict[Path, str]:
    return {
        OUT / f"{doc['table_id']}.json": json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
        for doc in (gwp100(), test_background())
    }


def main() -> int:
    wanted = files()
    if sys.argv[1:] == ["--check"]:
        stale = [
            p.name for p, text in wanted.items() if not p.is_file() or p.read_text("utf-8") != text
        ]
        print("e01_lca_data: " + ("stale " + ", ".join(stale) if stale else "current"))
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for path, text in wanted.items():
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
