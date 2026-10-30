"""V03.A15: the RC's CoolProp test step (V03 spec §4 step 17b, S07 F-8, R-879), read from CI.

The `rc-coolprop` job installs `requirements.lock`, then `requirements-coolprop.lock` with the
`check` job's two lines (`--no-deps --require-hashes`; `OPENFLOWSHEET_REQUIRE_COOLPROP=1` on the
test step), and runs every S07 and S11 test module that imports CoolProp on both CI
architectures, failing on any skip. The workflow file is the record read; the controls are
constructed in memory from it.
"""

from __future__ import annotations

import copy
from typing import Any

import yaml
from conftest import REPO_ROOT

CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
JOB = "rc-coolprop"
LOCK = "python -m pip install -r requirements.lock"
COOLPROP_LOCK = "--no-deps --require-hashes -r requirements-coolprop.lock"


def _a15(workflow: dict[str, Any]) -> list[str]:
    """What V03.A15 finds wrong with the job (empty: it holds)."""
    job = workflow["jobs"].get(JOB)
    if job is None:
        return ["no rc-coolprop job"]
    wrong = []
    if "inputs.rc" not in str(job.get("if", "")):
        wrong.append("not an RC job")
    if job.get("strategy", {}).get("matrix", {}).get("runner") != [
        "ubuntu-latest",
        "ubuntu-24.04-arm",
    ]:
        wrong.append("not on both architectures")
    runs = [step.get("run", "") for step in job["steps"]]
    lock = next((i for i, run in enumerate(runs) if LOCK in run), None)
    extra = next((i for i, run in enumerate(runs) if COOLPROP_LOCK in run), None)
    tests = next((i for i, run in enumerate(runs) if "pytest" in run), None)
    if lock is None or extra is None or not lock < extra:
        wrong.append("the coolprop lock is not installed after the main lock")
    if tests is None or extra is None or not extra < tests:
        wrong.append("the tests do not run after the coolprop lock")
        return wrong
    env = {**job.get("env", {}), **job["steps"][tests].get("env", {})}
    if env.get("OPENFLOWSHEET_REQUIRE_COOLPROP") != "1":
        wrong.append("OPENFLOWSHEET_REQUIRE_COOLPROP is not 1 on the test step")
    run = runs[tests]
    if "tests/test_s07_*.py" not in run or "tests/test_s11_*.py" not in run:
        wrong.append("the S07 and S11 modules are not selected")
    if "[0-9]+ skipped" not in run:
        wrong.append("a skip does not fail the step")
    if not any("OFS_S07_BUILD_PYTHON" in r for r in runs[:tests]):
        wrong.append("S07.A29's build Python is not set")
    return wrong


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_a15_the_rc_installs_the_coolprop_lock_and_requires_coolprop() -> None:
    assert _a15(_workflow()) == []


def test_a15_controls_fail() -> None:
    """Constructed: the job without the flag, with the two installs swapped, and absent."""
    workflow = _workflow()
    steps = workflow["jobs"][JOB]["steps"]
    tests = next(i for i, step in enumerate(steps) if "pytest" in step.get("run", ""))

    no_flag = copy.deepcopy(workflow)
    no_flag["jobs"][JOB]["steps"][tests].pop("env")
    assert "OPENFLOWSHEET_REQUIRE_COOLPROP is not 1 on the test step" in _a15(no_flag)

    swapped = copy.deepcopy(workflow)
    jobs = swapped["jobs"][JOB]["steps"]
    lock = next(i for i, step in enumerate(jobs) if LOCK in step.get("run", ""))
    extra = next(i for i, step in enumerate(jobs) if COOLPROP_LOCK in step.get("run", ""))
    jobs[lock], jobs[extra] = jobs[extra], jobs[lock]
    assert "the coolprop lock is not installed after the main lock" in _a15(swapped)

    absent = copy.deepcopy(workflow)
    del absent["jobs"][JOB]
    assert _a15(absent) == ["no rc-coolprop job"]
