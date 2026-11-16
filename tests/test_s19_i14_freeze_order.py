"""ADR 0076 I-14 (ruling `docs/briefs/S19-A11-ruling.md` sections 3 and 4): when the process message
catalogue freezes, and what it holds then.

Every test runs in a fresh interpreter (`python -I`), with the fake-site directories and this
repository's `src` first on `sys.path`, so what a module imports at import decides the result.
B1 and B2 (ADR 0076 I-14 tests (a) and (b)): wherever an entry point imports the registry, the
first lookup builds the process registry first, so an installed extension's codes are present
(the extension's own lookup during the build raises, as F1-WO3 pins). B3: a load validates the
packaged core exactly when the audit switch is on at that moment.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from f1_harness import FakeSite, descriptor

import openflowsheet.registry as registry_module

SOURCE = REPO_ROOT / "src"
CATALOGUE_YAML = """\
catalogue: openflowsheet-messages-v1
namespace: {namespace}
entries:
  - code: {namespace}.slurry_refused
    family: refusal
    kind: input
    complete: false
    title: Slurry refused
    summary: A slurry was refused.
"""
#: A core code (refusals.yaml), present whatever is installed.
CORE_CODE = "model_unsupported"


@pytest.fixture
def site(tmp_path: Path) -> Iterator[FakeSite]:
    registry_module.default_registry()  # built before any fake site is on `sys.path`
    fake = FakeSite(tmp_path)
    try:
        yield fake
    finally:
        fake.close()


def _fresh(script: str, directories: list[Path] | None = None) -> dict[str, Any]:
    """Run `script` in `python -I` with `directories` and `src` first on `sys.path`; it prints
    JSON on its last line."""
    paths = [*(str(path) for path in directories or ()), str(SOURCE)]
    prologue = f"import sys\nsys.path[:0] = {paths!r}\n"
    done = subprocess.run(
        [sys.executable, "-I", "-c", prologue + textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    found: dict[str, Any] = json.loads(done.stdout.splitlines()[-1])
    return found


def _slurry_with_peek(site: FakeSite) -> None:
    """test_f1_discovery's fixture: an extension with a message catalogue whose `package()` looks
    a code up while the registry is being built (and records the `RuntimeError`)."""
    module = site.module_name("slurry")
    reference = {"catalogue": {"package": module, "path": "m.yaml"}}
    spelled = json.dumps(
        json.dumps(descriptor("message_entries", "slurry.messages", payload=reference))
    )
    body = textwrap.dedent(
        f"""\
        import json
        from pathlib import Path

        SEEN = []


        def package():
            from openflowsheet.messages.catalogue import CATALOGUE

            try:
                CATALOGUE.entry("model_unsupported")
            except RuntimeError as error:
                SEEN.append(str(error))
            return {{"package_format": "openflowsheet-extension-package-v1",
                    "namespace": "slurry",
                    "descriptors": [json.loads({spelled})]}}
        """
    )
    site.add(
        "slurry-dist",
        "slurry",
        body=body,
        files={"m.yaml": CATALOGUE_YAML.format(namespace="slurry")},
    )


@pytest.mark.parametrize(
    "module",
    [
        "openflowsheet.registry",
        "openflowsheet.application.errors",
        "openflowsheet.application.jobs.worker",
        "openflowsheet.application.cli",
        "openflowsheet.application.local",
        "openflowsheet.application.serving",
    ],
)
def test_b1_an_entry_point_module_builds_the_registry_before_the_freeze(
    site: FakeSite, module: str
) -> None:
    _slurry_with_peek(site)
    found = _fresh(
        f"""
        import importlib, json
        importlib.import_module("{module}")
        from openflowsheet.messages.catalogue import CATALOGUE

        core = CATALOGUE.entry("{CORE_CODE}") is not None
        entry = CATALOGUE.entry("slurry.slurry_refused")
        from openflowsheet.registry import default_registry

        print(json.dumps({{
            "core": core,
            "entry": entry is not None and entry.namespace,
            "closed": default_registry().closed,
            "seen": sys.modules["{site.module_name("slurry")}"].SEEN,
        }}))
        """,
        site.directories,
    )
    assert found == {
        "core": True,
        "entry": "slurry",
        "closed": True,
        "seen": ["catalogue lookup during registry build"],
    }


def test_b2_an_api_error_rendered_first_sees_the_extension_entries(site: FakeSite) -> None:
    """The text's last line carries `args[0]`, `"<code>: <message>"` (MSG section 4.5)."""
    _slurry_with_peek(site)
    found = _fresh(
        """
        import json
        from openflowsheet.application.errors import api_error

        text = str(api_error("not_found", "probe"))
        from openflowsheet.messages.catalogue import CATALOGUE

        entry = CATALOGUE.entry("slurry.slurry_refused")
        print(json.dumps({
            "last": text.splitlines()[-1],
            "entry": entry is not None and entry.namespace,
        }))
        """,
        site.directories,
    )
    assert found == {"last": "  Details: not_found: probe", "entry": "slurry"}


def test_b3_a_load_without_the_audit_does_not_validate_the_core() -> None:
    found = _fresh(
        """
        import json
        from openflowsheet.messages.catalogue import Catalogue

        Catalogue().keys()
        print(json.dumps({"jsonschema": "jsonschema" in sys.modules}))
        """
    )
    assert found == {"jsonschema": False}


def test_b3_a_load_with_the_audit_enabled_validates_the_core() -> None:
    found = _fresh(
        """
        import json
        from openflowsheet.messages import audit
        from openflowsheet.messages.catalogue import Catalogue

        audit.enable()
        Catalogue().keys()
        print(json.dumps({"jsonschema": "jsonschema" in sys.modules}))
        """
    )
    assert found == {"jsonschema": True}


def test_b3_the_audit_switch_is_read_at_each_load() -> None:
    found = _fresh(
        """
        import json
        from openflowsheet.messages import audit
        from openflowsheet.messages.catalogue import Catalogue

        saved = audit.enable()
        audit.auditor = None
        Catalogue().keys()
        off = "jsonschema" in sys.modules
        audit.auditor = saved
        Catalogue().keys()
        print(json.dumps({"off": off, "restored": "jsonschema" in sys.modules}))
        """
    )
    assert found == {"off": False, "restored": True}
