"""R-1064: the documented `grant ... > token.txt`, then `serve-mcp --token-file token.txt`, works.

Before R-1064, `project grant` printed five labelled lines on stdout and `serve-mcp` read the
whole file as the token, so the Coding Agents page's recipe wrote a file the server refused
("the token matches no current grant"). The token now goes alone to stdout and the capability,
principal and rights to stderr. These tests run the page's own commands, so a later change to
either the page or the CLI that breaks the recipe fails here.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.cli import main
from openflowsheet.application.serving import ServeRefusedError, token_capability

AGENTS_PAGE = REPO_ROOT / "docs-site" / "agents.md"
TOKEN = re.compile(r"prt_[A-Za-z0-9_-]{43}")


def _page_command(prefix: str) -> list[str]:
    """The one command line of the Coding Agents page that starts with `prefix`."""
    lines = [
        line.strip()
        for line in AGENTS_PAGE.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(prefix)
    ]
    assert len(lines) == 1, lines
    return shlex.split(lines[0])


def test_the_page_redirects_grant_into_the_file_serve_mcp_reads() -> None:
    grant = _page_command("openflowsheet project grant")
    assert grant[-2:] == [">", "token.txt"], grant
    serve = _page_command("claude mcp add openflowsheet")
    assert serve[serve.index("--token-file") + 1].endswith("/token.txt"), serve


def test_the_page_recipe_writes_a_token_file_serve_mcp_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["project", "init", "plant"]) == 0
    grant = _page_command("openflowsheet project grant")
    assert grant[0] == "openflowsheet" and grant[-2] == ">"
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        assert main(grant[1:-2]) == 0
    Path(grant[-1]).write_text(stdout.getvalue(), encoding="utf-8")

    written = Path("token.txt").read_text(encoding="utf-8")
    assert TOKEN.fullmatch(written.strip()), written
    assert written.count("\n") == 1
    assert "capability " in stderr.getvalue() and "rights     " in stderr.getvalue()
    assert not TOKEN.search(stderr.getvalue()), "the token is printed once, on stdout"

    capability = token_capability("plant", "token.txt")
    assert capability.capability_id in stderr.getvalue()


def test_a_file_with_the_old_five_line_output_is_still_refused(tmp_path: Path) -> None:
    """`serve-mcp` reads the token file as before: it does not learn to parse `grant`'s labels."""
    project = tmp_path / "plant"
    assert main(["project", "init", str(project)]) == 0
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        assert main(["project", "grant", "--project", str(project), "--principal", "agent"]) == 0
    token = stdout.getvalue().strip()
    assert TOKEN.fullmatch(token), token
    current = tmp_path / "current.txt"
    current.write_text(token + "\n", encoding="utf-8")
    token_capability(project, current)  # the same token alone is accepted: the control
    old = tmp_path / "old.txt"
    old.write_text(
        f"capability cap\nprincipal  agent\nrights     read\ntoken      {token}\n(note)\n",
        encoding="utf-8",
    )
    with pytest.raises(ServeRefusedError):
        token_capability(project, old)
