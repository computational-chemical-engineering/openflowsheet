"""V02 alpha Amendment 2, R-347: the records of `scripts/t08_rc.py`'s `install-check`, `lock-check`
and `certificates` subcommands, and `scripts/t08_dist.py`'s, name a registered machine class
(spec `docs/derivations/V02-alpha-release-spec.md` §18.3).

The member is computed at write time by `t08_rc.machine_class()`, which wraps T06 §7.5 (A5)'s
`benchmarks.t06.ensemble.machine_class()`; it is never a literal. `install-check` writes it in
`provenance` beside `architecture` and `github_actions`, and must agree with both. `lock-check`'s
end-to-end test (`tests/test_t08_r3_a19_lock_lookup.py`) asserts the member on both states.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

from benchmarks.t06 import ensemble

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_rc  # noqa: E402

CLASSES = ensemble.registered()["machine_classes"]


def _registered_and_agreeing(document: dict[str, Any]) -> None:
    """The member is the function's value; on a registered host (the gate's hosts: `ref-x86-64`
    and the CI classes) it is a registry key that agrees with the record's own members. On any
    other host it is `unregistered(<machine>)`, which the M07a generator fails (A43)."""
    provenance = document["provenance"]
    label = provenance["machine_class"]
    assert label == t08_rc.machine_class()
    if label not in CLASSES:
        assert label == f"unregistered({platform.machine()})"
        return
    assert provenance["architecture"] == CLASSES[label]["architecture"]
    assert provenance["github_actions"] == CLASSES[label]["github_actions"]


def test_the_wrapper_is_t06s_function() -> None:
    assert t08_rc.machine_class() == ensemble.machine_class()


def test_the_certificates_record_carries_the_machine_class(tmp_path: Path) -> None:
    inputs = tmp_path / "certificates" / "nominal"
    inputs.mkdir(parents=True)
    shutil.copy(t08_rc.NOMINAL_CERTIFICATE, inputs / "solution-certificate.json")
    out = tmp_path / "certificates.json"
    assert t08_rc.main(["certificates", "--out", str(out), str(tmp_path / "certificates")]) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["step"] == "certificates"
    _registered_and_agreeing(document)


def test_the_install_check_record_carries_the_machine_class(tmp_path: Path) -> None:
    """Run as CI runs it: another interpreter, from outside the checkout, the package imported
    from a directory outside the tree. Its checks may fail here (this is not a clean
    environment); the record is written either way, and its provenance is what is asserted."""
    site = tmp_path / "site"
    shutil.copytree(
        REPO_ROOT / "src" / "openflowsheet",
        site / "openflowsheet",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment.update({name: "1" for name in t08_rc.THREAD_VARIABLES})
    environment["PYTHONPATH"] = str(site)
    out = tmp_path / "install.json"
    ran = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "t08_rc.py"),
            "install-check",
            "--out",
            str(out),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.is_file(), ran.stdout[-2000:] + ran.stderr[-2000:]
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["step"] == "install-check"
    _registered_and_agreeing(document)
    assert document["machine"] == document["provenance"]["architecture"]
