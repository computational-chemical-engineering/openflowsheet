"""T08.B50 (build-first spec Amendment 4, R-144): `c7bbc98`'s served `list_models` and
`get_project` content, regenerated from that commit's own code.

B50 compares the content those two operations serve today with what they served at `c7bbc98`
(the commit V17's `v17-c2` campaign ran on). This script checks `c7bbc98` out into a temporary
detached worktree, runs that tree's `process_runtime` (its `src/` first on `PYTHONPATH`; the import
is checked to come from the worktree) on a fresh project created exactly as the B50 test creates
today's, and writes both responses to `tests/fixtures/t08/b50-c7bbc98-surface.json`. The worktree is
removed afterwards. `tests/test_t08_b50_surface_content.py` checks the fixture against `v17-c2`'s
own transcripts (served at `c7bbc98`, recorded verbatim), so it is not only self-generated.

Usage:
    .venv/bin/python scripts/t08_b50_surface_fixture.py [--write]

Without `--write` it compares the regenerated content with the committed fixture and exits 1 on
any difference.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
COMMIT: Final = "c7bbc9833beab5f743b064b5d428da4fe13fd9be"
FIXTURE: Final = ROOT / "tests" / "fixtures" / "t08" / "b50-c7bbc98-surface.json"
#: The project both builds serve: created fresh, owner-local, under this id.
PROJECT_ID: Final = "t08-b50"

#: Run inside the checked-out tree's interpreter environment; prints the two responses. `c7bbc98`
#: predates the rename (R-149), so its package is `process_runtime`, not `openflowsheet`
#: (T08 verdicts finding G7: the scripted rename had changed these imports too).
SERVE: Final = """
import json, sys
from pathlib import Path
import process_runtime
from process_runtime.application.local import LocalApplication
from process_runtime.application.operations import dispatch

source = Path(process_runtime.__file__).resolve()
if not source.is_relative_to(Path(sys.argv[1]).resolve()):
    raise SystemExit(f"process_runtime imported from {source}, not from {sys.argv[1]}")
project = Path(sys.argv[2])
LocalApplication.create(project, project_id=sys.argv[3]).close()
with LocalApplication.open(project) as application:
    served = {name: dispatch(application, name, {}) for name in ("get_project", "list_models")}
print(json.dumps(served, sort_keys=True))
"""


def served_at(commit: str) -> dict[str, Any]:
    """`get_project` and `list_models` as `commit`'s code serves them on a fresh project."""
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "tree"
        subprocess.run(
            ["git", "worktree", "add", "--detach", "--quiet", str(tree), commit],
            cwd=ROOT,
            check=True,
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", SERVE, str(tree), str(Path(scratch) / "p"), PROJECT_ID],
                cwd=scratch,
                env={"PYTHONPATH": str(tree / "src"), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, check=True
            )
        if completed.returncode != 0:
            raise SystemExit(f"serving at {commit} failed:\n{completed.stderr[-3000:]}")
        served: dict[str, Any] = json.loads(completed.stdout)
        return served


def document() -> dict[str, Any]:
    return {
        "commit": COMMIT,
        "project_id": PROJECT_ID,
        "generator": "scripts/t08_b50_surface_fixture.py",
        **served_at(COMMIT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    text = json.dumps(document(), indent=1, sort_keys=True) + "\n"
    if arguments.write:
        FIXTURE.write_text(text, encoding="utf-8")
        print(f"wrote {FIXTURE.relative_to(ROOT)}")
        return 0
    same = FIXTURE.is_file() and FIXTURE.read_text(encoding="utf-8") == text
    print(f"{FIXTURE.relative_to(ROOT)}: {'equal' if same else 'DIFFERS'}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
