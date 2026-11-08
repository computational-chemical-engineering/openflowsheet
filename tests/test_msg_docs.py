"""MSG WO-8: the message docs pages (design note `docs/design/MSG-messages.md` §3.5, §4.12; MSG-G5).

`scripts/doc_pages.py` writes one page per family, `docs-site/messages/<family>.md`, one section per
code opened by `<a id="<code>"></a>`. `tests/test_doc_pages.py` holds every generated page equal to
the code (`--check`); this file holds:

- each page's anchors are exactly its family's catalogue keys;
- every `docs` URL an explanation can carry resolves to a generated anchor: each entry's, each
  rendered example's, and every one in the committed fixtures that record explanations
  (`docs_url_problems` is the check the corpus reuses);
- the hand-written pages: `messages/index.md` in the nav with the eight family pages, and every code
  `guide/limitations.md` names linked to its section.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from conftest import REPO_ROOT

from openflowsheet.messages.catalogue import CATALOGUE, DOCS_BASE, FAMILY_PAGES
from openflowsheet.messages.render import entry_document
from openflowsheet.messages.text import STUB_NOTE

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import doc_pages  # noqa: E402

MESSAGES = REPO_ROOT / "docs-site" / "messages"
ANCHOR = re.compile(r'^<a id="([^"]+)"></a>$', re.MULTILINE)
#: The committed fixtures that record explanations as documents.
RECORDED = (
    REPO_ROOT / "tests" / "web" / "fixtures" / "w26" / "exchanges.json",
    *sorted((REPO_ROOT / "tests" / "fixtures" / "schemas" / "application_results").rglob("*.json")),
)


def _anchors(page: str) -> list[str]:
    return ANCHOR.findall((MESSAGES / f"{page}.md").read_text(encoding="utf-8"))


def docs_url_problems(urls: Iterable[str]) -> list[str]:
    """Each URL that is not `DOCS_BASE` + `messages/<family page>/#<code>` with that anchor on
    the generated page."""
    anchors = {page: set(_anchors(page)) for page in FAMILY_PAGES.values()}
    problems = []
    for url in urls:
        parts = urlsplit(url)
        match = re.fullmatch(
            r"messages/([a-z-]+)/", parts.path.removeprefix(urlsplit(DOCS_BASE).path)
        )
        if (
            not url.startswith(DOCS_BASE)
            or match is None
            or match.group(1) not in anchors
            or parts.fragment not in anchors[match.group(1)]
        ):
            problems.append(url)
    return problems


def _docs_urls(node: Any) -> Iterator[str]:
    """Every string under `node` that is a link into this site's message pages."""
    if isinstance(node, str):
        if node.startswith(DOCS_BASE + "messages/"):
            yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _docs_urls(value)
    elif isinstance(node, list):
        for value in node:
            yield from _docs_urls(value)


def test_each_page_anchors_exactly_its_familys_codes_in_key_order() -> None:
    for family, page in FAMILY_PAGES.items():
        codes = [entry.code for entry in CATALOGUE.entries() if entry.family == family]
        assert _anchors(page) == codes, page


def test_every_entrys_docs_url_resolves_to_its_section() -> None:
    urls = [entry.docs for entry in CATALOGUE.entries()]
    assert len(urls) == len(CATALOGUE.keys())
    assert docs_url_problems(urls) == []


def test_every_rendered_examples_docs_url_resolves() -> None:
    urls = [
        example["docs"]
        for code in CATALOGUE.keys()
        for example in (entry_document(code) or {"examples": []})["examples"]
    ]
    assert urls
    assert docs_url_problems(urls) == []


def test_every_recorded_explanations_docs_url_resolves() -> None:
    urls = [
        url for path in RECORDED for url in _docs_urls(json.loads(path.read_text(encoding="utf-8")))
    ]
    assert len(urls) >= 3
    assert docs_url_problems(urls) == []


def test_a_wrong_url_is_reported() -> None:
    good = CATALOGUE.entries()[0].docs
    bad = [
        good.replace("#", "#x"),
        good.replace("messages/", "message/"),
        good.replace(DOCS_BASE, "https://example.org/"),
        DOCS_BASE + "messages/nowhere/#not_found",
    ]
    assert docs_url_problems([good, *bad]) == bad


def test_a_section_shows_the_entry_and_a_stub_says_so() -> None:
    page = (MESSAGES / "refusals.md").read_text(encoding="utf-8")
    section = page.split('<a id="isentropic_state_two_phase"></a>')[1].split("<a id=")[0]
    assert "## `isentropic_state_two_phase`: " in section
    assert "**Kind:** Not supported in this version" in section
    assert "&lt;s_star&gt;" in section  # a display template, escaped for Markdown
    assert "[`L-TH-4`](limitations.md#L-TH-4)" in section  # the gap's limitation
    assert "support-matrix.md" in section
    assert "[`phase_regime_mismatch`](#phase_regime_mismatch)" in section  # see also
    assert "```text\nThe solve stopped before its first iteration" in section  # the example
    stub = next(entry for entry in CATALOGUE.entries() if not entry.complete)
    text = (MESSAGES / f"{FAMILY_PAGES[stub.family]}.md").read_text(encoding="utf-8")
    assert f"*{STUB_NOTE}*" in text.split(f'<a id="{stub.code}"></a>')[1].split("<a id=")[0]


def test_the_nav_has_the_messages_section() -> None:
    config = yaml.load((REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"), Loader=yaml.Loader)
    (section,) = [item["Messages"] for item in config["nav"] if "Messages" in item]
    pages = [next(iter(item.values())) for item in section]
    assert pages == [
        "messages/index.md",
        *(f"messages/{page}.md" for page in FAMILY_PAGES.values()),
    ]
    assert config["site_url"] == DOCS_BASE
    assert (MESSAGES / "index.md").is_file()
    assert set(doc_pages.message_pages()) == {
        MESSAGES / f"{page}.md" for page in FAMILY_PAGES.values()
    }


def test_the_limitations_guide_links_every_code_it_names() -> None:
    text = (REPO_ROOT / "docs-site" / "guide" / "limitations.md").read_text(encoding="utf-8")
    linked = 0
    for match in re.finditer(r"(\[)?`([^`\n]+)`(\]\(([^)]+)\))?", text):
        head = match.group(2).split("(")[0]
        entry = CATALOGUE.entry(head)
        if entry is None:
            continue
        assert match.group(4) == f"../messages/{FAMILY_PAGES[entry.family]}.md#{head}", match[0]
        linked += 1
    assert linked >= 8


def test_the_page_paths_are_what_the_docs_urls_name() -> None:
    for page in FAMILY_PAGES.values():
        assert Path(MESSAGES / f"{page}.md").is_file(), page
