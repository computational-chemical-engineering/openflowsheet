"""YAML loading for the message catalogue and for extension catalogue documents (ADR 0076 I-14).

A leaf: it imports nothing from `openflowsheet`, and PyYAML only when called.
"""

from __future__ import annotations

from typing import Any


def yaml_load(text: str) -> Any:
    import yaml  # noqa: PLC0415 (PyYAML is a runtime dependency; loaded with the catalogue)

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load(text, Loader=loader)  # noqa: S506 (a safe loader)
