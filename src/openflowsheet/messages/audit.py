"""The runtime audit, MSG-G3 (design note §3.2, §4.2.8).

Under pytest, `tests/conftest.py` calls `enable()`. Hooks at the emission points of machine text
(`api_error()`, `bundle_for()`, `Unbound`, `RunUnsupportedError`) call `observe(text, module)`;
the auditor parses the text (§4.3) and records every code it finds that has no catalogue entry,
with the first producer module seen. The renderer records here every defect it falls back from
(I9). `pytest_sessionfinish` fails the session when either set is non-empty.

In production `auditor` is `None` and a hook costs one `is None` check.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Auditor:
    #: `{code: first producer module}` for codes without an entry.
    misses: dict[str, str] = field(default_factory=dict)
    #: `{"<code>: <reason>": first context}` for rendering defects the renderer fell back from.
    defects: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, text: str, caller_module: str) -> None:
        if not caller_module.startswith("openflowsheet."):
            return
        from openflowsheet.messages.catalogue import CATALOGUE  # noqa: PLC0415
        from openflowsheet.messages.legacy import parse_chain, resolve  # noqa: PLC0415

        links = resolve(parse_chain(text, CATALOGUE), CATALOGUE)
        with self._lock:
            for link in links:
                if link.code not in CATALOGUE:
                    self.misses.setdefault(link.code, caller_module)

    def code(self, code: str, caller_module: str) -> None:
        """A code observed directly (not parsed from text)."""
        if not caller_module.startswith("openflowsheet."):
            return
        from openflowsheet.messages.catalogue import CATALOGUE  # noqa: PLC0415

        if code not in CATALOGUE:
            with self._lock:
                self.misses.setdefault(code, caller_module)

    def defect(self, key: str, where: str) -> None:
        with self._lock:
            self.defects.setdefault(key, where)


auditor: Auditor | None = None


def enable() -> Auditor:
    global auditor  # noqa: PLW0603
    if auditor is None:
        auditor = Auditor()
    return auditor


def disable() -> None:
    global auditor  # noqa: PLW0603
    auditor = None


def observe(text: str, caller_module: str) -> None:
    if auditor is not None:
        auditor.observe(text, caller_module)


def misses() -> dict[str, str]:
    return {} if auditor is None else dict(auditor.misses)
