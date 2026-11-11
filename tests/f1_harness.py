"""F1-WO3's fake-distribution harness (ADR 0060 D7): installed distributions without pip.

A `FakeSite` is a directory put on `sys.path`; `add` writes one distribution into it: a
`<name>-<version>.dist-info` with `METADATA` and an `entry_points.txt` declaring
`[openflowsheet.extensions] <namespace> = <module>:package`, and a top-level package `<module>`
whose `package()` returns the extension package document (or runs `body` instead). Module names
are unique per site, so no test sees another's imports; `close` removes them from `sys.modules`.
`entry_points()` is `discovery.entry_points` over the site's directories alone, so the developer's
own environment never enters a test.
"""

from __future__ import annotations

import importlib
import json
import sys
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from openflowsheet.registry import discovery

PACKAGE_FORMAT = "openflowsheet-extension-package-v1"


def descriptor(kind: str, identifier: str, **fields: Any) -> dict[str, Any]:
    """A valid extension descriptor of `kind`, `fields` replacing the defaults."""
    document: dict[str, Any] = {
        "descriptor_format": "openflowsheet-extension-v1",
        "kind": kind,
        "id": identifier,
        "version": "1.0.0",
        "title": identifier,
        "status": "tested",
        "requires": [],
        "provides": [],
        "limitations": [],
        "platforms": ["any"],
        "pip_extra": None,
        "data_rights": None,
        "implementation": {"modules": [], "factory": None},
        "payload": {},
    }
    document.update(fields)
    return document


def package_document(namespace: str, descriptors: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "package_format": PACKAGE_FORMAT,
        "namespace": namespace,
        "descriptors": [dict(item) for item in descriptors],
    }


class FakeSite:
    """One or more `sys.path` directories holding fake distributions."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.directories: list[Path] = []
        self.modules: list[str] = []
        self._tag = uuid.uuid4().hex[:8]

    def directory(self, index: int = 0) -> Path:
        while len(self.directories) <= index:
            path = self.root / f"site{len(self.directories)}"
            path.mkdir(parents=True)
            self.directories.append(path)
            sys.path.insert(0, str(path))
        return self.directories[index]

    def module_name(self, namespace: str) -> str:
        """The top-level package `add` writes for `namespace` (unique to this site)."""
        return f"{namespace}_ext_{self._tag}"

    def add(
        self,
        distribution: str,
        namespace: str,
        descriptors: Iterable[Mapping[str, Any]] = (),
        *,
        version: str = "1.0.0",
        body: str | None = None,
        files: Mapping[str, str] | None = None,
        module: str | None = None,
        directory: int = 0,
        document_namespace: str | None = None,
    ) -> str:
        """Write a distribution; returns its top-level package name. `body` replaces the
        default `package()` source; `files` are written under the package directory;
        `document_namespace` overrides the document's namespace (default: `namespace`)."""
        root = self.directory(directory)
        module = module or self.module_name(namespace)
        info = root / f"{distribution.replace('-', '_')}-{version}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n", encoding="utf-8"
        )
        (info / "entry_points.txt").write_text(
            f"[{discovery.GROUP}]\n{namespace} = {module}:package\n", encoding="utf-8"
        )
        package = root / module
        if not package.exists():
            package.mkdir()
            document = package_document(document_namespace or namespace, descriptors)
            source = body or (
                "import json\n\n"
                f"DOCUMENT = json.loads({json.dumps(json.dumps(document))})\n\n\n"
                "def package():\n    return DOCUMENT\n"
            )
            (package / "__init__.py").write_text(source, encoding="utf-8")
            for name, text in (files or {}).items():
                target = package.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            self.modules.append(module)
        importlib.invalidate_caches()
        return module

    def entry_points(self) -> tuple[discovery.Discovered, ...]:
        return discovery.entry_points(path=[str(path) for path in self.directories])

    def close(self) -> None:
        for path in self.directories:
            if str(path) in sys.path:
                sys.path.remove(str(path))
        for name in list(sys.modules):
            if any(name == m or name.startswith(m + ".") for m in self.modules):
                del sys.modules[name]
