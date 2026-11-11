"""R-1020 (`docs/reviews/HOSTMOVE-ruling.md` §7, WO-H5, HM-30 to HM-33): T06's reference machine
class `ref-x86-64` lists its CPU models (T06 amendment H-1). `machine_class()` tests membership,
`ensemble.same_class_host` decides "same reference host", and `scripts/t06_ensemble.py check`
compares a regeneration on `ref-x86-64` byte for byte with `host.cpu_model` set to the published
one.

The running host's CPU model is read only through `generator._cpu_model`, which the tests patch.
`check` is run on synthetic documents (`_generate` patched); no starts file is read or written.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from benchmarks.t06 import ensemble, generator
from openflowsheet.canonical import canonical_json

REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
TRS2_CPU = "AMD Ryzen Threadripper PRO 5965WX 24-Cores"
TR09_CPU = "AMD Ryzen Threadripper 2950X 16-Core Processor"
LISTED = (TRS2_CPU, TR09_CPU)
#: Made-up literals (§11.0): no committed value and not the running host's.
MADE_UP_CPU = "cpu-hm31"
MADE_UP_NUMPY = "0.0.0-hm32"
for _literal in (MADE_UP_CPU, MADE_UP_NUMPY):
    assert _literal not in LISTED and _literal != generator._cpu_model(), _literal
    assert _literal not in (REPO_ROOT / "benchmarks" / "registry.yaml").read_text("utf-8")


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t06_ensemble_script_hostmove", REPO_ROOT / "scripts" / "t06_ensemble.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


def _host(cpu: str, **changed: str) -> dict[str, str]:
    return {
        "machine_class": "ref-x86-64",
        "architecture": "x86_64",
        "cpu_model": cpu,
        "python": "3.13.5",
        "numpy": "2.2.4",
        "scipy": "1.15.3",
        **changed,
    }


def _document(cpu: str, u: float = 0.3) -> dict[str, Any]:
    """A synthetic starts document: a host block and one start's one accepted `u`."""
    return {
        "format": "t06-starts-hm33",
        "host": _host(cpu),
        "cases": [{"case": "HM-33", "starts": [{"start": 0, "draws": [{"u": u}]}]}],
    }


def _check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, published: Any, regenerated: Any
) -> int:
    path = tmp_path / "starts.json"
    path.write_bytes(canonical_json(published))
    monkeypatch.setattr(SCRIPT, "_generate", lambda holdout: json.loads(json.dumps(regenerated)))
    return int(SCRIPT.check(argparse.Namespace(file=str(path), holdout=False)))


def test_hm30_the_registry_lists_the_two_models_in_order() -> None:
    entry = REGISTRY["ensemble"]["machine_classes"]["ref-x86-64"]
    assert entry["cpu_models"] == [TRS2_CPU, TR09_CPU]
    assert "cpu_model" not in entry
    assert entry == {"github_actions": False, "architecture": "x86_64", "cpu_models": list(LISTED)}


@pytest.mark.parametrize(
    ("github", "machine", "cpu", "expected"),
    [
        (None, "x86_64", TRS2_CPU, "ref-x86-64"),
        (None, "x86_64", TR09_CPU, "ref-x86-64"),
        ("false", "x86_64", TR09_CPU, "ref-x86-64"),
        (None, "x86_64", MADE_UP_CPU, "unregistered(x86_64)"),
        ("true", "x86_64", TRS2_CPU, "ci-x86-64"),
        ("true", "x86_64", TR09_CPU, "ci-x86-64"),
        ("true", "x86_64", MADE_UP_CPU, "ci-x86-64"),
        ("true", "aarch64", MADE_UP_CPU, "ci-aarch64"),
        (None, "aarch64", TR09_CPU, "unregistered(aarch64)"),
    ],
)
def test_hm31_machine_class_tests_membership(
    monkeypatch: pytest.MonkeyPatch, github: str | None, machine: str, cpu: str, expected: str
) -> None:
    if github is None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    else:
        monkeypatch.setenv("GITHUB_ACTIONS", github)
    monkeypatch.setattr(ensemble.platform, "machine", lambda: machine)
    monkeypatch.setattr(generator, "_cpu_model", lambda: cpu)
    assert ensemble.machine_class() == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (_host(TRS2_CPU), _host(TRS2_CPU), True),
        (_host(TR09_CPU), _host(TR09_CPU), True),
        (_host(TR09_CPU), _host(TRS2_CPU), True),
        (_host(TRS2_CPU), _host(TR09_CPU), True),
        (_host(MADE_UP_CPU), _host(TRS2_CPU), False),
        (_host(TR09_CPU), _host(MADE_UP_CPU), False),
        (_host(MADE_UP_CPU), _host(MADE_UP_CPU), False),
        (_host(TR09_CPU, numpy=MADE_UP_NUMPY), _host(TRS2_CPU), False),
        (_host(TRS2_CPU, numpy=MADE_UP_NUMPY), _host(TRS2_CPU), False),
    ],
)
def test_hm32_same_class_host(a: dict[str, str], b: dict[str, str], expected: bool) -> None:
    assert ensemble.same_class_host(a, b) is expected


def test_hm33_one_ulp_in_a_start_on_ref_x86_64_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    published = _document(TRS2_CPU)
    regenerated = _document(TR09_CPU, u=math.nextafter(0.3, 1.0))
    assert _check(monkeypatch, tmp_path, published, regenerated) == 1
    out = capsys.readouterr().out
    assert "same host: a defect" in out
    assert "identical but for" not in out


def test_hm33_control_only_the_cpu_model_differs_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _check(monkeypatch, tmp_path, _document(TRS2_CPU), _document(TR09_CPU)) == 0
    assert f"identical but for host.cpu_model ({TR09_CPU})" in capsys.readouterr().out


def test_hm33_control_an_unlisted_model_is_reported_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    published = _document(TRS2_CPU)
    regenerated = _document(MADE_UP_CPU, u=math.nextafter(0.3, 1.0))
    assert _check(monkeypatch, tmp_path, published, regenerated) == 0
    assert "another host: reported" in capsys.readouterr().out
