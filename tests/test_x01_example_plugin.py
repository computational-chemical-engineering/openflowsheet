"""X01 (ADR 0060 D7, D9): the example plugin `examples/plugins/demo/` and its guide page.

The example is installed into a temporary directory from its own `pyproject.toml`: a
`<name>-<version>.dist-info` with `METADATA` and the `entry_points.txt` its
`[project.entry-points]` table declares, and a copy of its `src/` packages. No installer runs and
nothing is fetched, so the test is offline; a wheel built from the same `pyproject.toml` installs
the same three things. The registry then finds the example through the real discovery,
`discovery.entry_points` over that directory (`importlib.metadata`).

- The example is registered whole and listed with its namespace, its distribution, its
  self-hash of `messages.yaml` (D3) and the D9 flags (`installed`, `unreviewed`, `core`); its
  message code reaches the catalogue.
- Refusals with the existing codes: a second distribution declaring `demo` quarantines both
  (`namespace_conflict`); an entry point whose name differs from the document's namespace is
  `extension_invalid` at `/namespace`.
- Every fenced block of `docs-site/guide/plugins.md` and of the example's README carries a
  marker: `file <path>` (the block is a verbatim part of that file), `cli` (each `$ openflowsheet`
  line runs with the example installed, in a fresh interpreter, and exits 0), `python` (the block
  runs likewise) or `illustrative`.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

import openflowsheet.registry as registry_module
from openflowsheet.application import capabilities
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import Catalogue
from openflowsheet.registry import Registry, discovery
from openflowsheet.registry.descriptor import PAYLOAD_DEFS

EXAMPLE = REPO_ROOT / "examples" / "plugins" / "demo"
GUIDE = REPO_ROOT / "docs-site" / "guide" / "plugins.md"
SOURCE = REPO_ROOT / "src"
MODULE = "openflowsheet_demo_plugin"


def _install(
    site: Path, *, name: str | None = None, entry_point: str | None = None
) -> dict[str, Any]:
    """Install the example into `site` from its own `pyproject.toml`; `name` replaces the
    distribution name and `entry_point` the entry point's name (the negative cases). Returns the
    `[project]` table."""
    project = tomllib.loads((EXAMPLE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    name = name or project["name"]
    points = project["entry-points"][discovery.GROUP]
    if entry_point is not None:
        (value,) = points.values()
        points = {entry_point: value}
    info = site / f"{name.replace('-', '_')}-{project['version']}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {project['version']}\n", encoding="utf-8"
    )
    lines = [f"[{discovery.GROUP}]", *(f"{key} = {value}" for key, value in points.items())]
    (info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for package in (EXAMPLE / "src").iterdir():
        if package.is_dir() and not (site / package.name).exists():
            shutil.copytree(package, site / package.name)
    importlib.invalidate_caches()
    return dict(project)


@pytest.fixture
def site(tmp_path: Path) -> Iterator[Path]:
    """A directory on `sys.path` to install into; the process registry is built before it is on
    the path, so it never holds the example."""
    registry_module.default_registry()
    directory = tmp_path / "site"
    directory.mkdir()
    sys.path.insert(0, str(directory))
    try:
        yield directory
    finally:
        sys.path.remove(str(directory))
        for loaded in list(sys.modules):
            if loaded == MODULE or loaded.startswith(MODULE + "."):
                del sys.modules[loaded]


def _build(*sites: Path, catalogue: Catalogue | None = None) -> Registry:
    return Registry.build(
        builtin_tables=discovery.builtin_tables(),
        entry_points=discovery.entry_points(path=[str(path) for path in sites]),
        catalogue_register=None if catalogue is None else catalogue.register,
    )


def test_the_example_is_discovered_and_listed_with_its_namespace_and_flags(site: Path) -> None:
    project = _install(site)
    catalogue = Catalogue()
    built = _build(site, catalogue=catalogue)
    assert built.quarantined == ()
    installed = [e for e in built.descriptors() if e.origin != "builtin"]
    assert [(e.kind, e.id, e.version) for e in installed] == [
        ("message_entries", "demo.messages", "0.1.0")
    ]
    page = capabilities.capability_page(built, id_prefix="demo.").as_document()
    assert page["next_cursor"] is None and len(page["items"]) == 1
    item = page["items"][0]
    assert {
        key: item[key]
        for key in (
            "entry_point",
            "distribution",
            "distribution_version",
            "origin",
            "status",
            "effective_status",
            "evidence_class",
            "stability",
        )
    } == {
        "entry_point": "demo",
        "distribution": project["name"],
        "distribution_version": project["version"],
        "origin": "installed",
        "status": "tested",
        "effective_status": "tested",
        "evidence_class": "unreviewed",
        "stability": "core",
    }
    # D3, independently: the hash of the LF-normalised `messages.yaml` under its module path.
    path = f"{MODULE}/messages.yaml"
    data = (EXAMPLE / "src" / MODULE / "messages.yaml").read_bytes().replace(b"\r\n", b"\n")
    pairs = [[path, hashlib.sha256(data).hexdigest()]]
    assert item["self_sha256"] == hashlib.sha256(canonical_json(pairs)).hexdigest()
    used = built.extensions_used([("message_entries", "demo.messages", None)])
    assert [notice.as_document() for notice in used.notices()] == [
        {"code": "extension_unreviewed", "params": {"id": "demo.messages", "origin": "installed"}}
    ]
    entry = catalogue.entry("demo.feed_too_wet")
    assert entry is not None and entry.namespace == "demo"


def test_a_second_distribution_declaring_demo_quarantines_both(site: Path, tmp_path: Path) -> None:
    project = _install(site)
    other = tmp_path / "other"
    other.mkdir()
    _install(other, name="other-demo-plugin")
    built = _build(site, other)
    conflict = {"code": "namespace_conflict", "params": {"namespace": "demo"}}
    assert sorted(
        (row.distribution, row.reason.as_document()) for row in built.quarantined
    ) == sorted([(project["name"], conflict), ("other-demo-plugin", conflict)])
    assert [e.id for e in built.descriptors() if e.origin != "builtin"] == []


def test_an_entry_point_not_named_after_the_documents_namespace_is_refused(site: Path) -> None:
    _install(site, entry_point="demo2")
    built = _build(site)
    assert [row.reason.as_document() for row in built.quarantined] == [
        {"code": "extension_invalid", "params": {"entry_point": "demo2", "pointer": "/namespace"}}
    ]


# ---------------------------------------------------------------------------------------------
# The guide's snippets

_FENCE = re.compile(r"^```[a-z]*\n(.*?)^```\n", re.MULTILINE | re.DOTALL)
_MARKER = re.compile(r"<!-- snippet: (file \S+|cli|python|illustrative) -->\n\Z")


def _snippets(page: Path) -> list[tuple[str, str]]:
    """Each fenced block of `page` with the marker on the line before it (`""` when none)."""
    text = page.read_text(encoding="utf-8")
    found = []
    for block in _FENCE.finditer(text):
        before = text[: block.start()]
        marker = _MARKER.search(before[before.rstrip("\n").rfind("\n") + 1 :])
        found.append((marker.group(1) if marker else "", block.group(1)))
    return found


def _fresh(site: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([str(site), str(SOURCE)])
    return subprocess.run(
        [sys.executable, *arguments],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=300,
    )


_CLI = "import sys; from openflowsheet.application.cli import main; sys.exit(main(sys.argv[1:]))"


@pytest.mark.parametrize("page", [GUIDE, EXAMPLE / "README.md"], ids=["guide", "readme"])
def test_every_snippet_is_checked_or_marked_illustrative(page: Path, site: Path) -> None:
    snippets = _snippets(page)
    assert snippets, page
    text = page.read_text(encoding="utf-8")
    assert len(re.findall(r"^\s*(```|~~~)", text, re.MULTILINE)) == 2 * len(snippets), page
    _install(site)
    for marker, block in snippets:
        assert marker, f"a block without a snippet marker in {page.name}:\n{block}"
        if marker.startswith("file "):
            source = (REPO_ROOT / marker.removeprefix("file ")).read_text(encoding="utf-8")
            assert block in source, f"not a verbatim part of {marker}:\n{block}"
        elif marker == "cli":
            commands = [line.removeprefix("$ ") for line in block.splitlines()]
            assert commands and all(c.startswith("openflowsheet ") for c in commands), block
            for command in commands:
                done = _fresh(site, "-c", _CLI, *shlex.split(command)[1:])
                assert done.returncode == 0, (command, done.stderr[-2000:])
                assert "demo." in done.stdout, (command, done.stdout[-2000:])
        elif marker == "python":
            done = _fresh(site, "-c", block)
            assert done.returncode == 0, done.stderr[-2000:]


def test_the_guides_listing_claim_is_what_the_cli_prints(site: Path) -> None:
    """The guide states the example's listed fields; the CLI prints them."""
    _install(site)
    done = _fresh(site, "-c", _CLI, "capabilities", "--prefix", "demo.")
    assert done.returncode == 0, done.stderr[-2000:]
    (item,) = json.loads(done.stdout)["items"]
    assert (item["id"], item["entry_point"], item["distribution"]) == (
        "demo.messages",
        "demo",
        "openflowsheet-demo-plugin",
    )
    assert (item["origin"], item["effective_status"], item["evidence_class"]) == (
        "installed",
        "tested",
        "unreviewed",
    )
    assert item["stability"] == "core"
    guide = GUIDE.read_text(encoding="utf-8")
    for field, value in (
        ("entry_point", "demo"),
        ("distribution", "openflowsheet-demo-plugin"),
        ("origin", "installed"),
        ("effective_status", "tested"),
        ("evidence_class", "unreviewed"),
        ("stability", "core"),
    ):
        assert f"`{field}` `{value}`" in guide.replace("\n", " "), (field, value)


def test_the_guide_names_every_kind_with_a_payload_schema() -> None:
    """A new schema kind in `PAYLOAD_DEFS` fails here until the guide's "Kinds" section names it."""
    text = GUIDE.read_text(encoding="utf-8")
    section = text.split("## Kinds in this release", 1)[1].split("(ADR 0061", 1)[0]
    assert set(re.findall(r"`([a-z_]+)`", section)) == set(PAYLOAD_DEFS)
