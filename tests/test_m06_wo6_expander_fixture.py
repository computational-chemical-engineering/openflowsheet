"""M06 WO-6: the expander fixture is the server's projection of its document, as committed.

`tests/web/api.test.mjs` reassembles a document with `api.readWhole` from the views in
`tests/web/fixtures/expander.json`; this holds those views to `projection.project` and
`bound_document` of today (`scripts/m06_web_expander_fixture.py --check`), so the Node test
cannot drift from the server it stands in for.
"""

from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT


def test_the_expander_fixture_is_the_server_s_projection() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "m06_web_expander_fixture.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
