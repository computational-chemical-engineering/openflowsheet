"""Shared support for T06's ensemble (W6): the 22 eligible cases as the registry registers them.
Not collected as tests; imported by the W6 tests and by `scripts/t06_ensemble.py`.

Each case is an `benchmarks.t06.ensemble.EnsembleCase`: its registry row's id, fixture, path and
policy (constructed where `test_t06_w4_registry.CONSTRUCTED` constructs it), a factory for a fresh
copy of its revision (W5's `_document`: a case file, or T05b's builder), and its registered root
at the registration's own precision. The revision-path roots are W5's reading
(`test_t06_w5_corpus.expected_root`); the three SYN-001 legacy fixtures' registrations are read
here, from the 20-digit strings: NET-01 and THM-03 are P01 variants (every stream coordinate and
both duties), NET-05 is T02's A02 sweep at 360 K (the heater and flash duties, the heater
outlet's temperature and its phase split).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from typing import Any

from conftest import REPO_ROOT, load_yaml
from test_t06_w4_registry import CASES, CONSTRUCTED, REGISTRY
from test_t06_w5_corpus import _document, expected_root

from benchmarks.t06.ensemble import EnsembleCase, allowance

__all__ = ["HOLDOUT_FILE", "RUNS_DIR", "STARTS_FILE", "ensemble_cases", "registered_root"]

#: Spec §6.5: the published starts.
STARTS_FILE = REPO_ROOT / "benchmarks" / "t06" / "ensemble" / "starts-nominal-v1.json"
#: Spec §7.6 (A5): the holdout's starts, the nominal law at start indices 20…39.
HOLDOUT_FILE = STARTS_FILE.parent / "starts-nominal-holdout1.json"
#: Spec §6.6 (A5): the committed run files, reports and comparisons, with `SHA256SUMS`.
RUNS_DIR = STARTS_FILE.parent / "runs"

Root = dict[str, tuple[Decimal, float]]


def _p01_variant(case_id: str) -> Root:
    """A P01 variant's registered state: S1…S7's flows, `T`, `P`, and the two duties."""
    reference = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    (variant,) = (v for v in reference["variants"] if v["case_id"] == case_id)
    feed = reference["fresh_feed"]
    liquid = [
        Decimal(a) + Decimal(b)
        for a, b in zip(variant["recycle_mol_per_s"], variant["purge_mol_per_s"], strict=True)
    ]
    flash, heater = Decimal(variant["T_flash_K"]), Decimal(variant["T_heater_K"])
    streams: dict[str, tuple[list[Decimal], Decimal]] = {
        "S1": ([Decimal(x) for x in feed["F_mol_per_s"]], Decimal(feed["T_K"])),
        "S2": ([Decimal(x) for x in variant["mixed_feed_mol_per_s"]], Decimal(variant["T_mix_K"])),
        "S3": ([Decimal(x) for x in variant["mixed_feed_mol_per_s"]], heater),
        "S4": ([Decimal(x) for x in variant["vapor_product_mol_per_s"]], flash),
        "S5": (liquid, flash),
        "S6": ([Decimal(x) for x in variant["recycle_mol_per_s"]], flash),
        "S7": ([Decimal(x) for x in variant["purge_mol_per_s"]], flash),
    }
    root: Root = {}
    for stream, (flows, temperature) in streams.items():
        for component, flow in zip("ABC", flows, strict=True):
            root[f"{stream}.n.{component}"] = (flow, allowance(f"{stream}.n.{component}"))
        root[f"{stream}.T"] = (temperature, allowance("S.T"))
        root[f"{stream}.P"] = (Decimal(variant["P_Pa"]), allowance("S.P"))
    root["U-HEAT.Q"] = (Decimal(variant["Q_heater_W"]), allowance("U.Q"))
    root["U-FLASH.Q"] = (Decimal(variant["Q_flash_W"]), allowance("U.Q"))
    return root


def _a02_sweep(point: str) -> Root:
    """T02's A02 sweep point: the duties, the heater outlet temperature and its phase split."""
    reference = load_yaml(REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml")
    entry = reference["syn001"]["a02_sweep"][point]
    temperature = Decimal(point.removeprefix("T_heater=").removesuffix("K"))
    root: Root = {
        "U-HEAT.Q": (Decimal(entry["Q_heater_W"]), allowance("U.Q")),
        "U-FLASH.Q": (Decimal(entry["Q_flash_W"]), allowance("U.Q")),
        "S3.T": (temperature, allowance("S.T")),
    }
    for phase, key in (("vap", "S3_vapor_mol_per_s"), ("liq", "S3_liquid_mol_per_s")):
        for component, value in zip("ABC", entry[key], strict=True):
            root[f"S3.{phase}.{component}"] = (Decimal(value), allowance("S.n"))
    return root


def registered_root(expected: Mapping[str, Any]) -> Root:
    key = expected["reference_key"]
    if key.startswith("variants[case_id="):
        return _p01_variant(key.removeprefix("variants[case_id=").removesuffix("]"))
    if key.startswith("syn001.a02_sweep["):
        return _a02_sweep(key.removeprefix('syn001.a02_sweep["').removesuffix('"]'))
    return dict(expected_root(expected))


@cache
def ensemble_cases() -> tuple[EnsembleCase, ...]:
    """The 22 eligible cases, in the registry's `ensemble.cases` order."""
    rows = {case["id"]: case for case in CASES if case["eligible"]}
    order = REGISTRY["ensemble"]["cases"]
    assert sorted(order) == sorted(rows), (order, sorted(rows))
    out = []
    for case_id in order:
        row = rows[case_id]

        def document(row: Mapping[str, Any] = row) -> dict[str, Any]:
            return _document(row["fixture"], row.get("revision"))

        out.append(
            EnsembleCase(
                case=case_id,
                fixture=row["fixture"],
                path=row["path"],
                policy=CONSTRUCTED[row["policy"]],
                document=document,
                root=registered_root(row["expected"]),
            )
        )
    return tuple(out)
