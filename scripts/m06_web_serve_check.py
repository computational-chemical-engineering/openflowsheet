"""M06 gate G10: a running `openflowsheet serve-http --ui` serves the diagnostic web shell.

Usage: `python scripts/m06_web_serve_check.py WORKDIR`, with the interpreter of the installation
under test (CI's clean-install job: the RC wheel in a fresh environment, from outside the
checkout; the serving tests: the checkout's). It creates a project in `WORKDIR` with
`openflowsheet project init`, starts `openflowsheet serve-http --ui` on a free loopback port —
the console script beside the interpreter, else `python -m openflowsheet.application.cli` — and
asks for each file of `EXPECTED` over plain `urllib`: status 200, its content type, and the
shell's Content-Security-Policy; and for `/v1/project` without a token: 401 (the API is there and
needs the token). Prints one line per check and `m06_web_serve_check: PASSED|FAILED`; exits 0
only when every check passed. Standard library only: the clean environment has no test
dependencies.
"""

from __future__ import annotations

import json
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

#: Each path the check asks for, and the content type it must arrive with.
EXPECTED: Final[dict[str, str]] = {
    "/ui/": "text/html; charset=utf-8",
    "/ui/favicon.svg": "image/svg+xml",
    "/ui/js/main.js": "text/javascript; charset=utf-8",
    "/ui/js/routes.js": "text/javascript; charset=utf-8",
    "/ui/css/tokens.css": "text/css; charset=utf-8",
}
CSP_PREFIX: Final[str] = "default-src 'none'; script-src 'self';"
START_SECONDS: Final[float] = 60.0


def _command() -> list[str]:
    script = Path(sys.executable).with_name("openflowsheet")
    if script.is_file():
        return [str(script)]
    return [sys.executable, "-m", "openflowsheet.application.cli"]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _get(url: str) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 (loopback)
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    work = Path(argv[0])
    project = work / "m06-serve-check"
    command = _command()
    subprocess.run([*command, "project", "init", str(project)], check=True, timeout=120)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    log = (work / "m06-serve-check.log").open("wb")
    server = subprocess.Popen(
        [*command, "serve-http", "--ui", "--project", str(project), "--port", str(port)],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    results: list[tuple[str, bool, str]] = []
    try:
        deadline = time.monotonic() + START_SECONDS
        while True:
            try:
                _get(f"{base}/ui/")
                break
            except OSError:
                if server.poll() is not None or time.monotonic() > deadline:
                    results.append(("server started", False, f"exit {server.poll()}"))
                    break
                time.sleep(0.25)
        if not results:
            for path, media_type in EXPECTED.items():
                status, headers, _ = _get(base + path)
                found = (status, headers.get("content-type"))
                csp = headers.get("content-security-policy", "")
                ok = found == (200, media_type) and csp.startswith(CSP_PREFIX)
                results.append((f"GET {path}", ok, f"{found} csp={csp[:40]!r}"))
            status, headers, body = _get(f"{base}/v1/project")
            code = json.loads(body).get("code") if body else None
            ok = (status, code) == (401, "unauthenticated")
            results.append(("GET /v1/project without a token", ok, f"{status} {code}"))
    finally:
        server.send_signal(signal.SIGINT)
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    passed = bool(results) and all(ok for _, ok, _ in results)
    if not passed:
        print((work / "m06-serve-check.log").read_text(encoding="utf-8", errors="replace"))
    print(f"m06_web_serve_check: {'PASSED' if passed else 'FAILED'} ({' '.join(command)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
