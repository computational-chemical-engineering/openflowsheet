"""M03 WO-6: the [A10] audit of the optional NLP path's Ipopt distribution (specification §9).

Two kinds of test, both in the default gate and neither needing the audited environment:

- **G6, the default install is unchanged:** importing `openflowsheet` and every module the default
  gate imports loads neither Pyomo nor cyipopt, and `pyproject.toml` names them only in an `nlp`
  extra. The adapter module of WO-8 (`openflowsheet.study.nlp.greybox`) is the one module allowed
  to import them, and is the one module not walked here; its tests are marked `nlp` and deselected.
- **A41's committed half:** the audit document and its inventory exist, record every gate item,
  and the inventory was taken from exactly the committed locks. That the inventory reproduces is
  `scripts/m03_ipopt_inventory.py --check`, run in the audited environment.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib

from conftest import REPO_ROOT

NLP_LIBRARIES = ("pyomo", "cyipopt", "ipopt_wrapper")
NLP_ADAPTER_MODULES = ("openflowsheet.study.nlp.greybox",)
AUDIT = REPO_ROOT / "docs" / "m03-ipopt-audit.md"
INVENTORY = REPO_ROOT / "benchmarks" / "m03" / "ipopt-inventory-x86_64.json"
LOCKS = {
    "conda": REPO_ROOT / "benchmarks" / "m03" / "nlp-conda-explicit.txt",
    "pip": REPO_ROOT / "benchmarks" / "m03" / "nlp-pip.lock",
    "build": REPO_ROOT / "benchmarks" / "m03" / "nlp-build-conda-explicit.txt",
}


def test_the_default_modules_import_no_nlp_library() -> None:
    """G6: every `openflowsheet` module but the NLP adapter imports, in a fresh interpreter,
    without loading Pyomo or cyipopt."""
    probe = (
        "import importlib, json, pkgutil, sys\n"
        "import openflowsheet\n"
        f"skip = {NLP_ADAPTER_MODULES!r}\n"
        "walked = []\n"
        "for module in pkgutil.walk_packages(openflowsheet.__path__, 'openflowsheet.'):\n"
        "    if module.name.startswith(skip):\n"
        "        continue\n"
        "    importlib.import_module(module.name)\n"
        "    walked.append(module.name)\n"
        f"loaded = sorted(m for m in sys.modules if m.split('.')[0] in {NLP_LIBRARIES!r})\n"
        "print(json.dumps({'walked': len(walked), 'loaded': loaded}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, cwd=REPO_ROOT
    )
    outcome = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcome["walked"] > 50
    assert outcome["loaded"] == []


def test_pyomo_and_cyipopt_are_named_only_in_an_nlp_extra() -> None:
    """G6: the default requirements and every other extra name neither library."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    groups = {"dependencies": project["dependencies"]} | {
        f"extra {name}": texts for name, texts in project["optional-dependencies"].items()
    }
    naming = {
        group: [text for text in texts if re.match(r"\s*(pyomo|cyipopt)\b", text, re.I)]
        for group, texts in groups.items()
    }
    assert {group for group, texts in naming.items() if texts} <= {"extra nlp"}


def test_the_audit_records_every_gate_item_and_a_verdict() -> None:
    """A41: G1-G8 each with an outcome, and the verdict PASS or FAIL."""
    text = AUDIT.read_text(encoding="utf-8")
    for item in range(1, 9):
        assert re.search(rf"^\| G{item} \|.*\*\*(PASS|FAIL|BLOCKED)\*\*", text, re.M), f"G{item}"
    assert re.search(r"^\*\*Verdict: (PASS|FAIL)\*\*", text, re.M)


def test_the_inventory_was_taken_from_the_committed_locks() -> None:
    """A41/G7: the committed inventory names the hashes of exactly the committed lock files, and
    records G1-G6 as measured."""
    record = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert record["format"] == "m03-ipopt-inventory-v1"
    assert record["locks"] == {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in LOCKS.items()
    }
    assert set(record["gates"]) == {"G1", "G2", "G3", "G4", "G5", "G6"}
    assert all(isinstance(gate["pass"], bool) for gate in record["gates"].values())
