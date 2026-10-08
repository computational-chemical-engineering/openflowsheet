"""A headless Chromium driven over the DevTools protocol on a pipe, for the M06 browser tests.

Not collected. Design note `docs/design/M06-web-shell.md` §8 A6 names the browser and its flags
(`--headless=new --disable-gpu --user-data-dir=<tmp>`); the page is read once the shell says it
is ready (`<html data-ofs-ready="1">`), not after a fixed virtual-time budget — `--dump-dom
--virtual-time-budget=20000` was measured at ~24 s a route on the reference host (8.5 min for
§6's routes), and a fixed budget is a race where a readiness wait is not. What is read is the
same: the serialized DOM (`DOM.getOuterHTML` of the document element, as `--dump-dom` prints it).

The protocol travels on descriptors 3 (commands in) and 4 (replies and events out), as
`--remote-debugging-pipe` defines: JSON messages, each terminated by a NUL byte. Only the
standard library is used. Each `Page` is a fresh browser context (its own storage, as a fresh
`--user-data-dir` would be) with one tab, attached in flat mode; the page's console errors,
uncaught exceptions and JavaScript dialogs are collected as they arrive, so a test can assert
that none happened (a CSP violation is reported as a console error).
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

#: §8 A6: the browser binary — `OPENFLOWSHEET_BROWSER`, else the first of these on `PATH`.
BROWSER_VARIABLE: Final[str] = "OPENFLOWSHEET_BROWSER"
REQUIRE_VARIABLE: Final[str] = "OPENFLOWSHEET_REQUIRE_BROWSER"
CANDIDATES: Final[tuple[str, ...]] = ("chromium", "chromium-browser", "google-chrome")
#: How long one protocol command, or one wait on the page, may take.
PATIENCE_S: Final[float] = 60.0
POLL_S: Final[float] = 0.05


def find_browser() -> str | None:
    """§8 A6's binary, or `None` when there is none."""
    named = os.environ.get(BROWSER_VARIABLE)
    if named:
        return shutil.which(named) or (named if Path(named).is_file() else None)
    for candidate in CANDIDATES:
        found = shutil.which(candidate)
        if found is not None:
            return found
    return None


class BrowserError(RuntimeError):
    """A protocol error, a page that did not get ready, or a browser that went away."""


def _high(fd: int) -> int:
    """`fd` moved above the standard ones and 3/4 (close-on-exec), so the spawn's `dup2`s onto
    3 and 4 cannot clobber each other."""
    moved = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
    os.close(fd)
    return moved


class Browser:
    """One headless Chromium process; `page()` opens a fresh context with one tab."""

    def __init__(self, binary: str, profile: Path, download_dir: Path) -> None:
        self.download_dir = download_dir
        to_browser_r, to_browser_w = (_high(fd) for fd in os.pipe())
        from_browser_r, from_browser_w = (_high(fd) for fd in os.pipe())
        argv = [
            binary,
            "--headless=new",
            "--disable-gpu",
            f"--user-data-dir={profile}",
            "--remote-debugging-pipe",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1280,2000",
            "about:blank",
        ]
        actions = [
            (os.POSIX_SPAWN_DUP2, to_browser_r, 3),
            (os.POSIX_SPAWN_DUP2, from_browser_w, 4),
            (os.POSIX_SPAWN_OPEN, 1, os.devnull, os.O_WRONLY, 0),
            (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0),
        ]
        self.pid = os.posix_spawn(binary, argv, dict(os.environ), file_actions=actions)
        os.close(to_browser_r)
        os.close(from_browser_w)
        self._out = to_browser_w
        self._in = from_browser_r
        self._lock = threading.Lock()
        self._next = 0
        self._replies: dict[int, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._ready = threading.Condition()
        self._closed = False
        self._reader = threading.Thread(target=self._read, name="cdp-reader", daemon=True)
        self._reader.start()

    # -- the pipe -----------------------------------------------------------------------------

    def _read(self) -> None:
        buffer = b""
        while True:
            try:
                chunk = os.read(self._in, 1 << 16)
            except OSError:
                chunk = b""
            if not chunk:
                with self._ready:
                    self._closed = True
                    self._ready.notify_all()
                return
            buffer += chunk
            *messages, buffer = buffer.split(b"\0")
            with self._ready:
                for raw in messages:
                    message = json.loads(raw)
                    if "id" in message:
                        self._replies[message["id"]] = message
                    else:
                        self._events.append(message)
                self._ready.notify_all()

    def send(
        self, method: str, params: dict[str, Any] | None = None, session: str | None = None
    ) -> Any:
        """One command; its `result`, or `BrowserError` with the protocol's error."""
        with self._lock:
            self._next += 1
            ident = self._next
            message: dict[str, Any] = {"id": ident, "method": method, "params": params or {}}
            if session is not None:
                message["sessionId"] = session
            data = json.dumps(message).encode() + b"\0"
            while data:
                data = data[os.write(self._out, data) :]
        deadline = time.monotonic() + PATIENCE_S
        with self._ready:
            while ident not in self._replies:
                if self._closed:
                    raise BrowserError(f"{method}: the browser went away")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BrowserError(f"{method}: no reply in {PATIENCE_S} s")
                self._ready.wait(remaining)
            reply = self._replies.pop(ident)
        if "error" in reply:
            raise BrowserError(f"{method}: {reply['error']}")
        return reply.get("result", {})

    def events(self, session: str | None = None) -> list[dict[str, Any]]:
        """The events received so far (of one session, or the browser's own)."""
        with self._ready:
            return [event for event in self._events if event.get("sessionId") == session]

    def wait_event(self, accept: Callable[[dict[str, Any]], bool], what: str) -> dict[str, Any]:
        deadline = time.monotonic() + PATIENCE_S
        with self._ready:
            while True:
                for event in self._events:
                    if accept(event):
                        return event
                remaining = deadline - time.monotonic()
                if self._closed or remaining <= 0:
                    raise BrowserError(f"no {what} in {PATIENCE_S} s")
                self._ready.wait(remaining)

    # -- pages --------------------------------------------------------------------------------

    def page(self) -> Page:
        context = self.send("Target.createBrowserContext")["browserContextId"]
        target = self.send(
            "Target.createTarget", {"url": "about:blank", "browserContextId": context}
        )["targetId"]
        session = self.send("Target.attachToTarget", {"targetId": target, "flatten": True})[
            "sessionId"
        ]
        # A download is saved under its `guid` (`Browser.downloadWillBegin`), in this context.
        self.send(
            "Browser.setDownloadBehavior",
            {
                "behavior": "allowAndName",
                "browserContextId": context,
                "downloadPath": str(self.download_dir),
                "eventsEnabled": True,
            },
        )
        page = Page(self, context, target, session)
        for domain in ("Page", "Runtime", "Log", "DOM"):
            page.send(f"{domain}.enable")
        return page

    def close(self) -> None:
        try:
            self.send("Browser.close")
        except BrowserError:
            pass
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            if pid != 0:
                break
            time.sleep(POLL_S)
        else:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        os.close(self._out)
        self._reader.join(timeout=10)
        os.close(self._in)


class Page:
    """One tab in its own browser context."""

    def __init__(self, browser: Browser, context: str, target: str, session: str) -> None:
        self.browser = browser
        self.context = context
        self.target = target
        self.session = session

    def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return self.browser.send(method, params, self.session)

    def evaluate(self, expression: str) -> Any:
        """`expression`'s value (by value); an exception it throws is a `BrowserError`."""
        result = self.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise BrowserError(f"{expression}: {result['exceptionDetails']}")
        return result["result"].get("value")

    def navigate(self, url: str) -> None:
        reply = self.send("Page.navigate", {"url": url})
        if reply.get("errorText"):
            raise BrowserError(f"{url}: {reply['errorText']}")

    def wait_for(self, expression: str, what: str, patience_s: float = PATIENCE_S) -> Any:
        """Poll `expression` until it is truthy; its value."""
        deadline = time.monotonic() + patience_s
        while True:
            value = self.evaluate(expression)
            if value:
                return value
            if time.monotonic() > deadline:
                raise BrowserError(f"timed out waiting for {what} ({expression})")
            time.sleep(POLL_S)

    def wait_ready(self, patience_s: float = PATIENCE_S) -> None:
        """§8 A6: until `<html data-ofs-ready="1">`."""
        self.wait_for(
            "document.documentElement?.getAttribute('data-ofs-ready') === '1'",
            "data-ofs-ready=1",
            patience_s,
        )

    def dom(self) -> str:
        """The serialized document, as `--dump-dom` prints it."""
        root = self.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
        html: str = self.send("DOM.getOuterHTML", {"nodeId": root})["outerHTML"]
        return html

    def click(self, selector: str) -> None:
        """A real mouse click on the first element matching the CSS `selector`."""
        self.click_element(f"document.querySelector({json.dumps(selector)})", selector)

    def click_element(self, element: str, what: str) -> None:
        """A real mouse click (pressed and released) at the centre of the element the
        expression `element` yields, scrolled into view — a trusted event with user activation,
        as a person's click is."""
        box = self.evaluate(
            f"(() => {{ const e = {element};"
            " if (!e) return null; e.scrollIntoView({block: 'center'});"
            " const r = e.getBoundingClientRect();"
            " return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()"
        )
        if box is None:
            raise BrowserError(f"no element {what}")
        for kind in ("mousePressed", "mouseReleased"):
            self.send(
                "Input.dispatchMouseEvent",
                {"type": kind, "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1},
            )

    def problems(self) -> list[str]:
        """Every console error, uncaught exception and JavaScript dialog of this page so far."""
        found: list[str] = []
        for event in self.browser.events(self.session):
            method, params = event["method"], event.get("params", {})
            if method == "Runtime.exceptionThrown":
                found.append(f"exception: {params['exceptionDetails']}")
            elif method == "Page.javascriptDialogOpening":
                found.append(f"dialog: {params.get('type')} {params.get('message')!r}")
            elif (
                method == "Log.entryAdded"
                and params["entry"]["level"] == "error"
                # A refused contract call is logged as a failed resource load; the recorder
                # holds every status, and the tests assert those exactly.
                and params["entry"].get("source") != "network"
            ):
                entry = params["entry"]
                found.append(
                    f"log {entry.get('source')}: {entry.get('text')} {entry.get('url', '')}"
                )
            elif method == "Runtime.consoleAPICalled" and params.get("type") in {"error", "assert"}:
                found.append(f"console.{params['type']}: {params.get('args')}")
        return found

    def close(self) -> None:
        self.browser.send("Target.disposeBrowserContext", {"browserContextId": self.context})
