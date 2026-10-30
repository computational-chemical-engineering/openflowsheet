"""DOC (manifest id S14): run the documentation package's checks and write its evidence manifest.

Every check is a command run here, at the current commit, with its real exit code and the SHA-256
of its output; a check passes only if its command exits 0. The manifest is written to
`evidence/S14/<commit>/manifest.json` with the commands' outputs under `artifacts/` (ignored).

    python scripts/s14_evidence_manifest.py --docs-python /home/frankp/.cache/doc-venv/bin/python

`--docs-python` is an interpreter with requirements.lock, requirements-coolprop.lock, the project
and requirements-docs.txt installed (the site job's environment); the other commands use the
interpreter running this script. Status `tested` iff every check passes; `review` stays `pending`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

TESTS = (
    "tests/test_doc_examples.py",
    "tests/test_doc_pages.py",
    "tests/test_release_workflows.py",
    "tests/test_t08_w2_inventory.py",
    "tests/test_s07_packaging.py",
    "tests/test_evidence_manifests.py",
    "tests/test_k06_application.py",
    # The assessment entry points whose docstrings DOC extends (brief 2).
    "tests/test_e01_a_report.py",
    "tests/test_e01_b_lca.py",
    "tests/test_e01_b_studies.py",
    "tests/test_e01_b_brightway.py",
)

LIMITATIONS = (
    "The cost and impact example states only figures no cost correlation reads (the impact, the "
    "steam bill and their sensitivities); its capital figures are printed, not stated, because "
    "wp/E01b moves them (DOC_DECISIONS D11).",
    "The assessment guide states the SSLW set's page-level check against Seider et al. 3rd ed. "
    "that wp/E01b lands; on main 05363060 the set cites chapter and equations only "
    "(DOC_DECISIONS D13; revert 5ce7ff92 if DOC merges first).",
    "The assessment is documented as a library layer: no transport offers it (ADR 0052 D10); the "
    "example assesses the bundle's state through openflowsheet.assessment (DOC_DECISIONS D12).",
    "The examples are demonstrations, regression-checked against their own stated numbers; they "
    "are not verification or validation evidence.",
    "The thermal machines carry semantic_role `pump` in the examples: the frozen schema has no "
    "turbine or compressor role (DOC_DECISIONS D3, question Q1).",
    "The Wilson records are documented as read from a source checkout (DOC_DECISIONS D7).",
    "The site has been built locally only; it is deployed by site.yml after the merge to main, "
    "once Pages is enabled.",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs-python", required=True, help="the docs environment's python")
    arguments = parser.parse_args(argv)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = ROOT / "evidence" / "S14" / commit
    artifacts_dir = out / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    docs_bin = Path(arguments.docs_python).parent
    junit = artifacts_dir / "s14-tests.junit.xml"
    junit_cp = artifacts_dir / "s14-examples-coolprop.junit.xml"
    site = artifacts_dir / "site"
    runs: list[tuple[str, str, list[str]]] = [
        (
            "S14.C1",
            "the generated pages (unit catalogue, operations table) equal the code's",
            [python, "scripts/doc_pages.py", "--check"],
        ),
        (
            "S14.C2",
            "the touched tests pass: the examples against their stated numbers, the "
            "quickstart and tutorial code, the generated pages, the workflow pins and guards, the "
            "sdist/wheel inventory, packaging, manifests, the application",
            [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}", *TESTS],
        ),
        (
            "S14.C3",
            "the example notebooks pass in the docs environment, with CoolProp installed "
            "(the refrigeration example runs rather than skips)",
            [
                arguments.docs_python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit_cp}",
                "tests/test_doc_examples.py",
            ],
        ),
        (
            "S14.C4",
            "mkdocs build --strict: no warning, no broken link, every notebook executes",
            [str(docs_bin / "mkdocs"), "build", "--strict", "--site-dir", str(site)],
        ),
        (
            "S14.C5",
            "S11's identity gate is unchanged by the docstring edits",
            [python, "scripts/s11_identity.py"],
        ),
        ("S14.C6", "ruff check over the repository", [python, "-m", "ruff", "check", "."]),
        (
            "S14.C7",
            "ruff format --check over the repository",
            [python, "-m", "ruff", "format", "--check", "."],
        ),
    ]
    environment = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    commands: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for check_id, description, command in runs:
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, check=False
        )
        log = artifacts_dir / f"{check_id}.log"
        log.write_bytes(completed.stdout + completed.stderr)
        last = (completed.stdout.decode(errors="replace").strip().splitlines() or [""])[-1]
        commands.append(
            {
                "cmd": " ".join(command).replace(str(ROOT) + "/", ""),
                "cwd": ".",
                "exit_code": completed.returncode,
                "stdout_sha256": sha256(completed.stdout),
            }
        )
        checks.append(
            {
                "id": check_id,
                "description": description,
                "result": "pass" if completed.returncode == 0 else "fail",
                "value": last[:300],
            }
        )
        artifacts.append(
            {
                "path": str(log.relative_to(ROOT)),
                "sha256": sha256(log.read_bytes()),
                "description": f"output of {check_id}",
            }
        )
    for path in (junit, junit_cp):
        if path.is_file():
            artifacts.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256(path.read_bytes()),
                    "description": "JUnit report",
                }
            )
    passed = all(check["result"] == "pass" for check in checks)
    manifest = {
        "work_package": "S14",
        "commit": commit,
        "requirements": [],
        "status": "tested" if passed else "implemented",
        "inputs": {
            "case_id": "DOC (S14): the user documentation site, docs/briefs/DOC-site.md",
            "case_hash": sha256((ROOT / "docs" / "briefs" / "DOC-site.md").read_bytes()),
            "environment_lock_hash": sha256((ROOT / "requirements.lock").read_bytes()),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": artifacts,
        "limitations": list(LIMITATIONS),
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(
        f"S14 {'PASS' if passed else 'FAIL'} {commit} "
        + " ".join(f"{c['id']}={c['result']}" for c in checks)
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
