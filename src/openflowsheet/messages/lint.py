"""The catalogue lint, MSG-G4 (design note §4.2.7, I8).

Schema validity and unique keys are the loader's (`catalogue.py`); this module checks what the
schema cannot: references resolve, every templated name is declared, every complete entry's
examples render in every variant they reach, the summary length, the jargon lint and the
infeasibility lint (blueprint §7.7: no text says or implies that no solution exists).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator, Mapping
from typing import Any, Final

from openflowsheet.messages import template
from openflowsheet.messages.catalogue import (
    CATALOGUE,
    CONTEXT_PARAMS,
    DERIVING,
    Catalogue,
    Entry,
)
from openflowsheet.messages.render import (
    Explanation,
    RenderContext,
    RenderError,
    _matches,
    _Scope,
    render_code,
    render_template,
)

SUMMARY_LIMIT: Final[int] = 200
SURFACES: Final[tuple[str | None, ...]] = (None, "python", "cli", "http", "mcp")
_JARGON_WORDS: Final = re.compile(
    r"\b(closure|regime|initiali[sz]er|traversal|revision_eo|kernel|tear|residual|jacobian"
    r"|homotopy|ptc|taxonomy)\b",
    re.IGNORECASE,
)
_JARGON_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("the word None", re.compile(r"\bNone\b")),
    ("a snake_case token", re.compile(r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b")),
    ("a document id", re.compile(r"\b[A-Z]\d{2}\b")),
    ("a class name", re.compile(r"\b[A-Z][a-z]+(?:Error|Result|Failure)\b")),
)
_QUOTED: Final = re.compile(r"(?<!\w)'[^']*'(?!\w)|\"[^\"]*\"")
INFEASIBILITY: Final[tuple[str, ...]] = (
    "infeasib",
    "no solution exists",
    "has no solution",
    "cannot be solved",
    "impossible",
)


def jargon(text: str) -> list[str]:
    """The jargon found in a template's literal text (placeholders and quoted segments removed)."""
    literal = _QUOTED.sub(" ", template.literal(template.parse(text)))
    found = [f"the word {m.group(0)!r}" for m in _JARGON_WORDS.finditer(literal)]
    for label, pattern in _JARGON_PATTERNS:
        found.extend(f"{label} {m.group(0)!r}" for m in pattern.finditer(literal))
    return found


def _texts(entry: Entry) -> Iterator[tuple[str, str]]:
    yield "title", entry.title
    for name, index, text in entry.templates():
        yield (name if index is None else f"variants[{index}].{name}"), text
    gap = entry.gap or {}
    if gap.get("capability"):
        yield "gap.capability", str(gap["capability"])
    for name, declared in entry.params.items():
        yield f"params.{name}.label", declared.label


def _allowed_names(entry: Entry) -> set[str]:
    names = set(entry.params) | set(CONTEXT_PARAMS)
    for name, declared in entry.params.items():
        if declared.type in DERIVING:
            names.add(f"{name}_path")
            if declared.type in ("unit", "element"):
                names.add(f"{name}_model")
    return names


def _check_templates(entry: Entry, catalogue: Catalogue) -> list[str]:
    problems: list[str] = []
    allowed = _allowed_names(entry)
    for name, index, text in entry.templates():
        where = name if index is None else f"variants[{index}].{name}"
        problems += _check_template(entry, allowed, where, text)
    for name in entry.args:
        if name not in entry.params:
            problems.append(f"args: {name!r} is not a declared param")
    for name, declared in entry.params.items():
        if declared.vocabulary is not None and declared.vocabulary not in catalogue.vocabularies():
            problems.append(f"params.{name}: no vocabulary {declared.vocabulary!r}")
    if entry.detail_pattern is not None:
        try:
            re.compile(entry.detail_pattern)
        except re.error as error:
            problems.append(f"detail_pattern: {error}")
    return problems


def _check_template(entry: Entry, allowed: set[str], where: str, text: str) -> list[str]:
    """The template `text` at `where` parses, every name it renders is in `allowed`, and `!title`
    is applied only to a `code` param of `entry`."""
    problems: list[str] = []
    try:
        nodes = template.parse(text)
    except template.TemplateError as error:
        problems.append(f"{where}: {error}")
        return problems
    for param in template.params(nodes):
        if param.name not in allowed:
            problems.append(f"{where}: undeclared param {param.name!r}")
        elif param.conversion == "title":
            declared = entry.params.get(param.name)
            if declared is None or declared.type != "code":
                problems.append(f"{where}: !title on {param.name!r}, which is not a code")
    return problems


def _check_references(
    entry: Entry, catalogue: Catalogue, released: Collection[str] | None
) -> list[str]:
    problems = [
        f"see_also: {code!r} does not resolve" for code in entry.see_also if code not in catalogue
    ]
    replaced_by = entry.document.get("replaced_by")
    if replaced_by is not None and replaced_by not in catalogue:
        problems.append(f"replaced_by: {replaced_by!r} does not resolve")
    limitation = (entry.gap or {}).get("limitation")
    if limitation is not None:
        target = catalogue.entry(str(limitation))
        if target is None or target.family != "limitation":
            problems.append(f"gap.limitation: {limitation!r} is not a limitation entry")
    for index, variant in enumerate(entry.variants):
        for code in variant["when"].get("outer", ()):
            if code not in catalogue:
                problems.append(f"variants[{index}].when.outer: {code!r} does not resolve")
    if released is not None and entry.document.get("deprecated") and entry.code not in released:
        problems.append("deprecated: only a released code may be deprecated")
    return problems


def _example_params(example: Mapping[str, Any]) -> dict[str, Any]:
    return dict(example.get("params") or {})


def _check_examples(entry: Entry, catalogue: Catalogue) -> list[str]:
    problems: list[str] = []
    for number, example in enumerate(entry.examples):
        params = _example_params(example)
        chain = list(example.get("chain") or [entry.code])
        if chain[-1] != entry.code:
            problems.append(f"examples[{number}]: its chain must end with {entry.code!r}")
            continue
        for surface in SURFACES:
            context = RenderContext(surface=surface)  # type: ignore[arg-type]
            try:
                explanation = render_code(
                    entry.code,
                    params,
                    chain=chain,
                    context=context,
                    catalogue=catalogue,
                    strict=True,
                )
            except RenderError as error:
                problems.append(f"examples[{number}] (surface {surface}): {error}")
                continue
            problems += _check_lengths(explanation, surface, number)
            scope = _Scope(entry, {**context.params(), **params}, context, catalogue)
            outer = chain[: chain.index(entry.code)]
            problems += _check_reached_variants(entry, scope, outer, surface, number)
    return problems


def _check_lengths(explanation: Explanation, surface: str | None, number: int) -> list[str]:
    """Example `number` on `surface`: the rendered summary and cause are at most `SUMMARY_LIMIT`
    characters."""
    problems: list[str] = []
    for member in ("summary", "cause"):
        text = explanation.get(member)
        if text is not None and len(text) > SUMMARY_LIMIT:
            problems.append(
                f"examples[{number}] (surface {surface}): {member} has {len(text)} > "
                f"{SUMMARY_LIMIT} characters"
            )
    return problems


def _check_reached_variants(
    entry: Entry, scope: _Scope, outer: list[str], surface: str | None, number: int
) -> list[str]:
    """Example `number` on `surface`: every template of every variant whose `when` it reaches
    (with `outer`, the chain's codes before the entry's) renders in `scope`."""
    problems: list[str] = []
    for index, variant in enumerate(entry.variants):
        if not _matches(variant["when"], scope.params, surface, outer):
            continue
        for name in ("summary", "context", "where", "why", "action"):
            if name not in variant:
                continue
            try:
                render_template(str(variant[name]), scope)
            except RenderError as error:
                problems.append(
                    f"examples[{number}] (surface {surface}) variants[{index}].{name}: {error}"
                )
    return problems


def lint_entry(
    entry: Entry, catalogue: Catalogue = CATALOGUE, released: Collection[str] | None = None
) -> list[str]:
    """Every MSG-G4 violation of one entry, as `"<code>: <problem>"`.

    A complete entry is also checked by `_check_examples` (only when nothing else failed so far)
    and by `_check_jargon`.
    """
    problems = _check_templates(entry, catalogue) + _check_references(entry, catalogue, released)
    if entry.complete:
        if not problems:
            problems += _check_examples(entry, catalogue)
        problems += _check_jargon(entry)
    for where, text in _texts(entry):
        lowered = text.lower()
        problems += [
            f"{where}: says or implies that no solution exists ({phrase!r})"
            for phrase in INFEASIBILITY
            if phrase in lowered
        ]
    return [f"{entry.code}: {problem}" for problem in problems]


def _check_jargon(entry: Entry) -> list[str]:
    """The summary and context templates of `entry`, top level then each variant's, use no
    jargon. A template that does not parse is skipped: `_check_templates` reports it."""
    problems: list[str] = []
    for name, index, text in entry.templates():
        if name not in ("summary", "context"):
            continue
        where = name if index is None else f"variants[{index}].{name}"
        try:
            problems += [f"{where}: jargon: {found}" for found in jargon(text)]
        except template.TemplateError:
            pass  # reported by _check_templates
    return problems


def lint(catalogue: Catalogue = CATALOGUE, released: Collection[str] | None = None) -> list[str]:
    """MSG-G4 over the whole catalogue: an empty list is a pass."""
    return [
        problem
        for entry in catalogue.entries()
        for problem in lint_entry(entry, catalogue, released)
    ]


def review_count(catalogue: Catalogue = CATALOGUE) -> int:
    """The number of entries whose kind awaits design-lane review (printed, never failed on)."""
    return sum(1 for entry in catalogue.entries() if entry.review)
