"""M06 gate G1 (static half): the web shell can reach only its own files and `OPERATIONS` routes.

Design note §8 Layer A 3 and §2 (1, 5). A scan of `apps/web/`: no second network or markup sink
anywhere (`XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `innerHTML`, `outerHTML`,
`insertAdjacentHTML`, `document.write`, `eval(`, `new Function`, `import(`); `fetch(` exactly once,
in `js/api.js`; no absolute URL except the SVG namespace name in `js/h.js` and `favicon.svg`; the
pure modules (`js/model/`) touch no `document`, `window`, `fetch` or storage; `index.html` has no
inline script, style or handler; every relative module import resolves; the operation names the
sources call are `ROUTES` keys from the design's list of 17, and `routes.js` is what
`scripts/m06_web_routes.py` generates; the JS `FORBIDDEN_RANGES` block is Python's; and no
`OPERATIONS` path is under `/ui`. The browser half (a request recorder) is WO-11's smoke test.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.projection import FORBIDDEN_RANGES

WEB = REPO_ROOT / "apps" / "web"
JS = WEB / "js"
#: §6: the operations the shell calls, exactly.
UI_OPERATIONS = frozenset(
    {
        "get_project",
        "list_models",
        "list_revisions",
        "get_revision",
        "diff_revisions",
        "inspect_structure",
        "validate",
        "list_jobs",
        "get_job",
        "list_job_events",
        "wait_job",
        "get_job_result",
        "submit_job",
        "cancel_job",
        "get_artifact",
        "artifact_bytes",
        "list_audit",
    }
)
FORBIDDEN_TOKENS = (
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "sendBeacon",
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function",
    "import(",
)
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
#: Where the SVG namespace name may appear (an identifier, never fetched).
SVG_NAMESPACE_FILES = {"js/h.js", "favicon.svg"}
PURE_FORBIDDEN = ("document", "window", "fetch", "localStorage", "sessionStorage")


def _files(*suffixes: str) -> dict[str, str]:
    return {
        path.relative_to(WEB).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(WEB.rglob("*"))
        if path.is_file() and (not suffixes or path.suffix in suffixes)
    }


def test_the_shell_has_files_and_only_js_modules() -> None:
    files = _files()
    assert {"index.html", "favicon.svg", "css/tokens.css", "css/app.css", "js/h.js"} <= set(files)
    assert {Path(name).suffix for name in files} <= {".html", ".svg", ".css", ".js"}


@pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
def test_no_second_network_or_markup_sink(token: str) -> None:
    found = [name for name, text in _files().items() if token in text]
    assert found == []


def test_fetch_appears_exactly_once_in_api_js() -> None:
    found = {name: text.count("fetch(") for name, text in _files().items() if "fetch(" in text}
    assert found == {"js/api.js": 1}


def test_no_absolute_url_but_the_svg_namespace_name() -> None:
    for name, text in _files().items():
        urls = re.findall(r"https?://[^\s\"'`)<>]*", text)
        allowed = [SVG_NAMESPACE] * len(urls) if name in SVG_NAMESPACE_FILES else []
        assert urls == allowed, (name, urls)


def test_the_pure_modules_touch_no_browser_global() -> None:
    for name, text in _files(".js").items():
        if name.startswith("js/model/"):
            for word in PURE_FORBIDDEN:
                assert re.search(rf"\b{word}\b", text) is None, (name, word)


def test_index_html_has_no_inline_script_style_or_handler() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I)
    assert scripts, "index.html loads js/main.js"
    for attributes, body in scripts:
        assert body.strip() == "" and 'type="module"' in attributes and "src=" in attributes
    assert re.search(r"<style\b", html, re.I) is None
    assert re.search(r"\sstyle\s*=", html, re.I) is None
    assert re.search(r"\son[a-z]+\s*=", html, re.I) is None


def test_every_relative_module_import_resolves() -> None:
    for name, text in _files(".js").items():
        for target in re.findall(r"""\bfrom\s+["']([^"']+)["']""", text):
            assert target.startswith("./") or target.startswith("../"), (name, target)
            assert target.endswith(".js"), (name, target)
            assert (WEB / name).parent.joinpath(target).resolve().is_file(), (name, target)


# ======================================================================= operations and routes


def _routes() -> dict[str, dict[str, object]]:
    text = (JS / "routes.js").read_text(encoding="utf-8")
    body = text.split("export const ROUTES = freeze(", 1)[1].rsplit(");", 1)[0]
    table = json.loads(body)
    assert isinstance(table, dict)
    return table


def _called() -> set[str]:
    """Every operation name the sources call: `call("…"`, `readWhole("…"`, and `.raw(` (the
    raw export, `artifact_bytes`)."""
    names: set[str] = set()
    for _, text in _files(".js").items():
        names.update(re.findall(r"""\b(?:call|readWhole)\(\s*["']([a-z_]+)["']""", text))
        if re.search(r"\.raw\(", text):
            names.add("artifact_bytes")
    return names


def test_the_route_table_is_generated_from_the_http_rows() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "m06_web_routes.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    routes = _routes()
    assert set(routes) == {name for name, op in OPERATIONS.items() if "http" in op.transports}
    for name, entry in routes.items():
        assert (entry["verb"], entry["path"]) == OPERATIONS[name].http
        assert entry["right"] == OPERATIONS[name].right


def test_every_called_operation_is_a_listed_route() -> None:
    called = _called()
    assert called <= UI_OPERATIONS, called - UI_OPERATIONS
    assert called <= set(_routes()), called - set(_routes())


def test_the_ui_calls_exactly_the_seventeen_operations() -> None:
    assert _called() == UI_OPERATIONS
    assert set(_routes()) >= UI_OPERATIONS


def test_no_operation_path_is_under_the_shell_mount() -> None:
    paths = [op.http[1] for op in OPERATIONS.values() if op.http is not None]
    assert paths and [path for path in paths if path == "/ui" or path.startswith("/ui/")] == []


def test_the_js_forbidden_ranges_are_the_projection_s() -> None:
    text = (JS / "text.js").read_text(encoding="utf-8")
    block = text.split("// BEGIN FORBIDDEN_RANGES", 1)[1].split("// END FORBIDDEN_RANGES", 1)[0]
    pairs = re.findall(r"\[\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*\]", block)
    assert tuple((int(low, 16), int(high, 16)) for low, high in pairs) == FORBIDDEN_RANGES
