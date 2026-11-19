"""An example OpenFlowsheet extension package (ADR 0060 D7): one message catalogue.

The distribution declares the entry point `demo = "openflowsheet_demo_plugin:package"` in the
group `openflowsheet.extensions`. The entry point's name, `demo`, is the extension's namespace:
every descriptor id and every message code starts with `demo.`. `package()` returns the extension
package document; like every entry-point callable it imports only the standard library, so
loading it runs no simulation code.
"""

from __future__ import annotations

from typing import Any

#: The entry point's name in `pyproject.toml`; it must equal the document's `namespace`.
NAMESPACE = "demo"


def package() -> dict[str, Any]:
    """The extension package document: one `message_entries` descriptor naming the catalogue
    `messages.yaml` in this package, read through `importlib.resources`."""
    return {
        "package_format": "openflowsheet-extension-package-v1",
        "namespace": NAMESPACE,
        "descriptors": [
            {
                "descriptor_format": "openflowsheet-extension-v1",
                "kind": "message_entries",
                "id": "demo.messages",
                "version": "0.1.0",
                "title": "Demo plugin messages",
                "status": "tested",
                "requires": [],
                "provides": [],
                "limitations": [],
                "platforms": ["any"],
                "pip_extra": None,
                "data_rights": None,
                "implementation": {
                    "modules": ["openflowsheet_demo_plugin/messages.yaml"],
                    "factory": None,
                },
                "payload": {
                    "catalogue": {"package": "openflowsheet_demo_plugin", "path": "messages.yaml"}
                },
            }
        ],
    }
