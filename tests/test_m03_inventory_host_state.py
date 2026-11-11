"""R-1020 (`docs/reviews/HOSTMOVE-ruling.md` §6, WO-H3, HM-22 to HM-24): the m03 inventory's
`pynumero_asl_lookup_without_pyomo_config_dir` is host state. `scripts/m03_ipopt_inventory.py
--check` sets it aside, as it sets aside `host.libc`, and prints it when it differs; the route's own
lookup (`workload.<order>.pynumero_asl`) and the host's machine stay compared.

Each case changes one member of a copy of the committed inventory; the committed file is only read.
"""

from __future__ import annotations

import copy
import sys
from typing import Any

from conftest import REPO_ROOT, load_json

# Loaded as `tests/test_m03_nlp_greybox.py` loads it.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m03_ipopt_inventory as inventory  # noqa: E402

COMMITTED = REPO_ROOT / "benchmarks" / "m03" / "ipopt-inventory-x86_64.json"
MEMBER = "pynumero_asl_lookup_without_pyomo_config_dir"


def _pair() -> tuple[dict[str, Any], dict[str, Any]]:
    committed = load_json(COMMITTED)
    return committed, copy.deepcopy(committed)


def _equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return bool(inventory._comparable(a) == inventory._comparable(b))


def test_hm22_the_lookup_without_pyomo_config_dir_is_host_state() -> None:
    committed, now = _pair()
    assert committed[MEMBER] == "~/.pyomo/lib/libpynumero_ASL.so"
    now[MEMBER] = "(none)"
    assert _equal(committed, now)
    assert inventory.host_state_drift(committed, now) == [
        f"host state (not compared): {MEMBER} '~/.pyomo/lib/libpynumero_ASL.so' -> '(none)'"
    ]
    assert inventory.host_state_drift(committed, copy.deepcopy(committed)) == []


def test_hm23_the_routes_own_lookup_is_compared() -> None:
    committed, now = _pair()
    order = next(iter(now["workload"]))
    assert now["workload"][order]["pynumero_asl"] == "$ENV/share/pyomo/lib/libpynumero_ASL.so"
    now["workload"][order]["pynumero_asl"] = "~/.pyomo/lib/libpynumero_ASL.so"
    assert not _equal(committed, now)
    assert inventory.host_state_drift(committed, now) == []


def test_hm24_the_host_machine_is_compared_and_libc_is_not() -> None:
    committed, now = _pair()
    now["host"]["machine"] = "aarch64"
    assert not _equal(committed, now)

    committed, now = _pair()
    now["host"]["libc"] = "glibc 0.0"
    assert _equal(committed, now)
