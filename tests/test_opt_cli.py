"""OPT WO-6 (design §4.11, §4.12): the CLI's `optimize` and `validate --task optimization
--request`, default environment.

G11's CLI half: on an unaudited platform (the monkeypatched platform, so that the check holds in
the audited environment too) `validate` exits `unsupported` with `nlp_solver_unavailable`,
`optimize` writes an `UNSUPPORTED` report, and neither imports Pyomo or cyipopt (a subprocess, so
that no other test's imports count). The solved `optimize` is `test_opt_job_nlp.py`'s.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_opt_request import FIXTURES, REPO, S11, _available

from openflowsheet.application.cli import API_EXIT_CODES, main
from openflowsheet.studies.nlp import closure

REVISION = S11 / "thermal" / "TH-R1.json"
REQUEST = FIXTURES / "valid" / "th_r1_minimal.json"


def test_validate_takes_the_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(closure, "audited_solver", _available)
    arguments = ["validate", str(REVISION), "--task", "optimization"]
    assert main([*arguments, "--request", str(REQUEST), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "READY_FOR_OPTIMIZATION"
    assert main(arguments) == API_EXIT_CODES["invalid_request"]
    refused = json.loads(capsys.readouterr().out)
    assert (refused["code"], refused["detail"]["pointer"]) == ("invalid_request", "/optimization")
    # MSG §3.7: the refusal carries its explanation (the code's own, `invalid_request`).
    assert refused["detail"]["explanation"]["chain"][0] == "invalid_request"


def test_optimize_refuses_a_request_with_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request = json.loads(REQUEST.read_bytes())
    request["objective"] = {"kind": "no-such-kind"}
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    out = tmp_path / "record"
    code = main(["optimize", str(REVISION), "--request", str(path), "--out", str(out)])
    assert code == API_EXIT_CODES["invalid_request"]
    refused = json.loads(capsys.readouterr().out)
    assert refused["code"] == "invalid_request"
    assert refused["detail"]["pointer"].startswith("/request/objective")
    assert refused["detail"]["explanation"]["chain"] == ["invalid_request", "request_invalid"]
    assert not out.exists()


_CLI = """
import json, sys
sys.path.insert(0, sys.argv[1])
from openflowsheet.studies.nlp import closure
closure.running_platform = lambda: "linux-aarch64"
from openflowsheet.application.cli import main
revision, request, out = sys.argv[2:5]
validated = main(["validate", revision, "--task", "optimization", "--request", request])
optimized = main(["optimize", revision, "--request", request, "--out", out, "--json"])
print(json.dumps({"validate": validated, "optimize": optimized,
                  "loaded": sorted(m for m in ("pyomo", "cyipopt") if m in sys.modules)}))
"""


def test_g11_the_cli_without_a_solver_imports_neither_pyomo_nor_cyipopt(tmp_path: Path) -> None:
    out = tmp_path / "record"
    result = subprocess.run(
        [sys.executable, "-c", _CLI, str(REPO / "src"), str(REVISION), str(REQUEST), str(out)],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.strip().splitlines()
    found = json.loads(lines[-1])
    assert found == {"validate": API_EXIT_CODES["unsupported"], "optimize": 1, "loaded": []}
    refused = json.loads(lines[0])
    assert (refused["code"], refused["message"]) == ("unsupported", "nlp_solver_unavailable")
    report = json.loads((out / "optimization-report.json").read_bytes())
    assert report["status"] == "UNSUPPORTED"
    assert "NLP_SOLVER_UNAVAILABLE" in json.dumps(report["reasons"])
