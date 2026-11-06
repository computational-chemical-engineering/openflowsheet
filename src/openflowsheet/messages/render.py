"""Resolution and rendering (MSG design note §4.4, §4.5): a code chain and params → an explanation.

The explanation is a plain document (`application-results.schema.json#/$defs/explanation`),
computed on read and stored nowhere (I2). Three entry points build the chain:

- `render_error(document)`: an `ApiError` document — its code, then the first candidate text of
  its `detail` (or its message) that parses to at least one code;
- `render_failure(outcome=…, message=…, diagnosis=…)`: a failure bundle's outcome, then its
  observation message, with the diagnostic sidecar's params when they agree with the chain;
- `render_code(code, params, chain=…)`: a code with given params (examples, `explain`).

`entry_document(code)` is the catalogue entry itself, as `explain` returns it (§3.5, §4.9), and
`suggestions(code)` the keys near an unknown code.

**Rendering is total (I9).** A defective entry, a template that fails or an unknown code falls back
to the next entry outward, and last to a minimal rendering (the code and the machine text). Under
the test-suite audit each fallback is recorded as a defect, which fails the session.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from openflowsheet.messages import audit, template
from openflowsheet.messages.catalogue import (
    CATALOGUE,
    CONTEXT_PARAMS,
    DERIVING,
    DOCS_BASE,
    ELEMENT_TYPES,
    FAMILY_PAGES,
    FORMAT_ID,
    TEMPLATE_FIELDS,
    Catalogue,
    Entry,
    parsed,
)
from openflowsheet.messages.diagnostic import Diagnostic, Quantity
from openflowsheet.messages.legacy import (
    Chain,
    Link,
    Segment,
    detail_params,
    parse_chain,
    resolve,
)

Surface = Literal["python", "cli", "http", "mcp"]
Explanation = dict[str, Any]

MAX_NUMBERS = 8
MAX_ELEMENTS = 16
#: §4.2.1: the binder's `Unbound.kind`s that make a `revision_unsupported` an input problem.
UNBOUND_INPUT_KINDS = frozenset({"conflict", "inadmissible", "incomplete"})


@dataclass(frozen=True)
class RenderContext:
    """What a rendering may know besides the chain (§4.2.5): the surface, the revision document,
    and the ids that are context params. `display_units` is X04's slot and always `None` here."""

    surface: Surface | None = None
    revision: Mapping[str, Any] | None = None
    revision_id: str | None = None
    job_id: str | None = None
    bundle_id: str | None = None
    operation: str | None = None
    display_units: Mapping[str, str] | None = None

    def params(self) -> dict[str, Any]:
        values = {
            "revision": self.revision_id,
            "job": self.job_id,
            "bundle": self.bundle_id,
            "operation": self.operation,
        }
        return {name: value for name, value in values.items() if value is not None}


class RenderError(Exception):
    """A template that cannot render with the params at hand (a defect under I9)."""


# -- numbers ------------------------------------------------------------------------------------


def format_number(value: float) -> str:
    """§4.5, normative: four significant digits for `1e-3 ≤ |v| < 1e9`, `.4g` otherwise."""
    if value == 0:
        return "0"
    magnitude = abs(value)
    if 1e-3 <= magnitude < 1e9:
        digits = 3 - math.floor(math.log10(magnitude))
        return f"{round(value, digits):.{max(digits, 0)}f}"
    return format(value, ".4g")


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _quantity(value: object) -> tuple[float, str, str | None] | None:
    if isinstance(value, Quantity):
        value = value.as_document()
    if isinstance(value, Mapping) and "value" in value and "unit" in value:
        number = _number(value["value"])
        if number is None:
            return None
        kind = value.get("kind")
        return number, str(value["unit"]), None if kind is None else str(kind)
    return None


def _pointer(path: Sequence[str | int]) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


# -- params -------------------------------------------------------------------------------------


def _present(value: object) -> bool:
    return value is not None


def _normalized(value: object) -> object:
    if isinstance(value, Quantity):
        return value.as_document()
    return value


@dataclass(frozen=True)
class _Typed:
    type: str
    value: Any
    vocabulary: str | None = None


class _Scope:
    """The params one entry renders with: the merged chain params, typed by the entry's
    declarations, plus the derived (§4.2.5) and context params."""

    def __init__(
        self, entry: Entry, params: Mapping[str, Any], context: RenderContext, catalogue: Catalogue
    ) -> None:
        self.entry = entry
        self.params = params
        self.context = context
        self.catalogue = catalogue
        self.derived: dict[str, _Typed] = {}
        self.types: dict[str, str] = {}
        for name, declared in entry.params.items():
            value = params.get(name)
            kind = declared.type
            if not _present(value):
                self.types[name] = kind
                continue
            located = _locate(kind, value, context.revision)
            if located is not None:
                kind, path, model = located
                self.derived[f"{name}_path"] = _Typed("pointer", path)
                if model is not None:
                    self.derived[f"{name}_model"] = _Typed("text", model)
            self.types[name] = kind

    def lookup(self, name: str) -> _Typed | None:
        """The typed value of `name`, `None` when absent; `RenderError` when undeclared."""
        declared = self.entry.params.get(name)
        if declared is not None:
            value = self.params.get(name)
            if not _present(value):
                return None
            return _Typed(self.types[name], value, declared.vocabulary)
        if name in self.derived:
            return self.derived[name]
        if name.endswith(("_path", "_model")):
            base = name.rsplit("_", 1)[0]
            if base in self.entry.params:
                return None
        if name in CONTEXT_PARAMS:
            value = self.params.get(name)
            return None if not _present(value) else _Typed(CONTEXT_PARAMS[name], value)
        raise RenderError(f"{self.entry.code}: undeclared param {name!r}")


def _locate(
    kind: str, value: object, revision: Mapping[str, Any] | None
) -> tuple[str, list[str | int], str | None] | None:
    """§4.2.5: `(type, path, model)` of an element param in the revision document, upgrading an
    `element` to a `unit` when the revision has a unit with that id; `None` if not found."""
    member = DERIVING.get(kind)
    if member is None or revision is None:
        return None
    items = revision.get(member)
    if not isinstance(items, Sequence):
        return None
    if kind == "specification" and isinstance(value, int) and not isinstance(value, bool):
        return ("specification", [member, value], None) if 0 <= value < len(items) else None
    for index, item in enumerate(items):
        if isinstance(item, Mapping) and item.get("id") == value:
            model = None
            if member == "instances":
                model_document = item.get("model")
                if isinstance(model_document, Mapping) and isinstance(
                    model_document.get("id"), str
                ):
                    model = model_document["id"]
            return ("unit" if kind == "element" else kind), [member, index], model
    return None


def _raw(value: object) -> str:
    if isinstance(value, float):
        return format_number(value)
    if isinstance(value, Mapping):
        quantity = _quantity(value)
        if quantity is not None:
            return f"{format_number(quantity[0])} {quantity[1]}"
    if isinstance(value, list | tuple):
        return ", ".join(_raw(item) for item in value)
    return str(value)


def _format(typed: _Typed, conversion: template.Conversion, catalogue: Catalogue) -> str:
    value = typed.value
    if typed.type == "pointer" and isinstance(value, list | tuple):
        return _pointer(value)
    if conversion == "raw":
        return _raw(value)
    if conversion == "title":
        entry = catalogue.entry(str(value)) if typed.type == "code" else None
        return entry.title if entry is not None else _raw(value)
    if typed.type in ELEMENT_TYPES:
        return f"'{_raw(value)}'"
    if typed.type == "quantity":
        quantity = _quantity(value)
        if quantity is not None:
            return f"{format_number(quantity[0])} {quantity[1]}"
        number = _number(value)
        return format_number(number) if number is not None else _raw(value)
    if typed.type == "number":
        number = _number(value)
        return format_number(number) if number is not None else _raw(value)
    if typed.type == "enum":
        phrase = (
            None if typed.vocabulary is None else catalogue.phrase(typed.vocabulary, str(value))
        )
        return phrase if phrase is not None else _raw(value)
    if typed.type == "list":
        items = value if isinstance(value, list | tuple) else [value]
        return ", ".join(_raw(item) for item in items)
    return _raw(value)


def _render(nodes: tuple[template.Node, ...], scope: _Scope) -> str:
    out: list[str] = []
    for node in nodes:
        if isinstance(node, template.Text):
            out.append(node.text)
        elif isinstance(node, template.Param):
            typed = scope.lookup(node.name)
            if typed is None:
                raise RenderError(f"{scope.entry.code}: missing param {node.name!r}")
            out.append(_format(typed, node.conversion, scope.catalogue))
        elif all(scope.lookup(name) is not None for name in node.direct_names):
            out.append(_render(node.nodes, scope))
    return "".join(out)


def render_template(text: str, scope: _Scope) -> str:
    try:
        nodes = template.parse(text)
    except template.TemplateError as error:
        raise RenderError(f"{scope.entry.code}: {error}") from error
    return _render(nodes, scope)


# -- variants -----------------------------------------------------------------------------------


def _matches(
    when: Mapping[str, Any], params: Mapping[str, Any], surface: str | None, outer: Sequence[str]
) -> bool:
    if any(not _present(params.get(name)) for name in when.get("has", ())):
        return False
    if any(params.get(name) != value for name, value in dict(when.get("equals", {})).items()):
        return False
    if any(params.get(name) == value for name, value in dict(when.get("not_equals", {})).items()):
        return False
    if "surface" in when and surface not in when["surface"]:
        return False
    return not ("outer" in when and not set(when["outer"]) & set(outer))


def _field(
    entry: Entry, name: str, scope: _Scope, outer: Sequence[str], *, strict: bool, machine: str
) -> str | None:
    """`name` of `entry`: the first matching variant that defines it, then the base (§4.2.2).
    An empty rendering counts as not supplied. A candidate that fails is a defect: `strict`
    raises it, the audit records it, and the next candidate is tried; `RenderError` when every
    candidate fails."""
    candidates = [
        str(variant[name])
        for variant in entry.variants
        if name in variant and _matches(variant["when"], scope.params, scope.context.surface, outer)
    ]
    if name in entry.document:
        candidates.append(str(entry.document[name]))
    if not candidates:
        return None
    error: RenderError | None = None
    for text in candidates:
        try:
            rendered = render_template(text, scope)
        except RenderError as failure:
            if strict:
                raise
            if audit.auditor is not None:
                audit.auditor.defect(f"{entry.code}.{name}: {failure}", machine)
            error = error or failure
            continue
        if rendered:
            return rendered
    if error is not None:
        raise error
    return None


def _kind(entry: Entry, scope: _Scope, outer: Sequence[str]) -> str:
    for variant in entry.variants:
        if "kind" in variant and _matches(
            variant["when"], scope.params, scope.context.surface, outer
        ):
            return str(variant["kind"])
    return entry.kind


# -- the explanation ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Request:
    links: list[Link]
    params: dict[str, Any]
    context: RenderContext
    machine: str
    family_hint: str
    hint: str | None = None
    kind_override: str | None = None
    extra_elements: tuple[str, ...] = ()


def _explain(request: _Request, catalogue: Catalogue, *, strict: bool) -> Explanation:
    codes = [link.code for link in request.links]
    resolved = [
        (position, entry)
        for position, link in enumerate(request.links)
        if (entry := catalogue.entry(link.code)) is not None
    ]
    for position, entry in reversed(resolved):
        try:
            return _from_entry(position, entry, request, codes, resolved, catalogue, strict=strict)
        except RenderError as error:
            if strict:
                raise
            if audit.auditor is not None:
                audit.auditor.defect(f"{entry.code}: {error}", request.machine)
    return _minimal(request, codes, catalogue)


def _from_entry(
    position: int,
    entry: Entry,
    request: _Request,
    codes: list[str],
    resolved: list[tuple[int, Entry]],
    catalogue: Catalogue,
    *,
    strict: bool,
) -> Explanation:
    scope = _Scope(entry, request.params, request.context, catalogue)
    outer = codes[:position]
    machine = request.machine

    def field(of: Entry, name: str, in_scope: _Scope, before: Sequence[str]) -> str | None:
        return _field(of, name, in_scope, before, strict=strict, machine=machine)

    summary = field(entry, "summary", scope, outer)
    if summary is None:
        raise RenderError(f"{entry.code}: no summary")
    kind = _kind(entry, scope, outer)
    if request.kind_override is not None:
        kind = request.kind_override
    why = action = where = None
    if entry.complete:
        why = field(entry, "why", scope, outer)
        action = field(entry, "action", scope, outer)
        where = field(entry, "where", scope, outer)
    if action is None:
        action = catalogue.kind(kind).default_action
    cause = None
    head = resolved[0]
    if head[0] == 0 and head[1].family == "outcome" and head[1].code != entry.code:
        outcome = head[1]
        outcome_scope = _Scope(outcome, request.params, request.context, catalogue)
        try:
            line = field(outcome, "context", outcome_scope, [])
            if line is None:
                line = field(outcome, "summary", outcome_scope, [])
        except RenderError as error:
            if strict:
                raise
            if audit.auditor is not None:
                audit.auditor.defect(f"{outcome.code}: {error}", request.machine)
            line = None
        if line is not None:
            summary, cause = line, summary
    return {
        "code": entry.code,
        "family": entry.family,
        "kind": kind,
        "complete": entry.complete,
        "summary": summary,
        "cause": cause,
        "where": where,
        "why": why,
        "action": action,
        "hint": request.hint,
        "elements": _elements(request, resolved),
        "numbers": _numbers(entry, request.params),
        "gap": entry.gap,
        "chain": codes,
        "docs": entry.docs,
    }


def _minimal(request: _Request, codes: list[str], catalogue: Catalogue) -> Explanation:
    """I9's last resort: the code and the machine message."""
    code = codes[0] if codes else "internal_error"
    entry = catalogue.entry(code)
    family = entry.family if entry is not None else request.family_hint
    kind = entry.kind if entry is not None else "bug"
    if request.kind_override is not None:
        kind = request.kind_override
    return {
        "code": code,
        "family": family,
        "kind": kind,
        "complete": False,
        "summary": request.machine or code,
        "cause": None,
        "where": None,
        "why": None,
        "action": catalogue.kind(kind).default_action,
        "hint": request.hint,
        "elements": [],
        "numbers": [],
        "gap": None,
        "chain": codes,
        "docs": f"{DOCS_BASE}messages/{FAMILY_PAGES[family]}/#{code}",
    }


def _elements(request: _Request, resolved: list[tuple[int, Entry]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []

    def add(kind: str, identifier: str, path: list[str | int] | None) -> None:
        if (kind, identifier) not in seen and len(out) < MAX_ELEMENTS:
            seen.add((kind, identifier))
            out.append({"type": kind, "id": identifier, "path": path})

    for _, entry in resolved:
        for name, value in request.params.items():
            declared = entry.params.get(name)
            if declared is None or declared.type not in ELEMENT_TYPES or not _present(value):
                continue
            located = _locate(declared.type, value, request.context.revision)
            if located is None:
                add(declared.type, _raw(value), None)
            else:
                add(located[0], _raw(value), located[1])
    for identifier in request.extra_elements:
        located = _locate("element", identifier, request.context.revision)
        if located is None:
            add("element", identifier, None)
        else:
            add(located[0], identifier, located[1])
    return out


def _numbers(entry: Entry, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, declared in entry.params.items():
        if len(out) == MAX_NUMBERS:
            break
        value = params.get(name)
        number: float | None
        unit: str
        kind: str | None
        if declared.type == "quantity":
            quantity = _quantity(value)
            if quantity is not None:
                number, unit, kind = quantity
                kind = kind if kind is not None else declared.quantity_kind
            else:
                number = _number(value)
                unit, kind = declared.unit or "", declared.quantity_kind
        elif declared.type == "number":
            number = _number(value)
            unit, kind = "", None
        else:
            continue
        if number is None:
            continue
        out.append(
            {"name": name, "label": declared.label, "value": number, "unit": unit, "kind": kind}
        )
    return out


def _merge(
    context: RenderContext, links: Sequence[Link], *layers: Mapping[str, Any]
) -> dict[str, Any]:
    """Context, then the chain's params outer → inner (inner wins), then each layer (§3.1's
    precedence: sidecar over `detail` members over legacy args over context)."""
    merged: dict[str, Any] = context.params()
    for link in links:
        merged.update({name: _normalized(value) for name, value in link.params.items()})
    for layer in layers:
        merged.update({name: _normalized(value) for name, value in layer.items()})
    return merged


# -- the entry points ---------------------------------------------------------------------------


def render_code(
    code: str,
    params: Mapping[str, Any] | None = None,
    *,
    chain: Sequence[str] | None = None,
    context: RenderContext | None = None,
    catalogue: Catalogue = CATALOGUE,
    strict: bool = False,
) -> Explanation:
    """`code` with the given params; `chain` (outer → inner, ending with `code`) when the code
    is explained inside other codes, as an entry's examples are."""
    context = context or RenderContext()
    links = [Link(item) for item in (chain or [code])]
    request = _Request(
        links=links,
        params=_merge(context, links, dict(params or {})),
        context=context,
        machine=code,
        family_hint="refusal",
    )
    return _explain(request, catalogue, strict=strict)


def _candidate_chain(
    detail: Mapping[str, Any], message: str, catalogue: Catalogue
) -> tuple[Chain, bool]:
    """§4.4: the first candidate text that yields a code; `True` when it was the binder's."""
    unbound = detail.get("unbound")
    if isinstance(unbound, Mapping) and isinstance(unbound.get("detail"), str):
        chain = parse_chain(unbound["detail"], catalogue)
        if chain.segments:
            return chain, True
    report = detail.get("report")
    if isinstance(report, Mapping) and isinstance(report.get("checks"), Sequence):
        for check in report["checks"]:
            if isinstance(check, Mapping) and check.get("result") == "FAIL" and check.get("id"):
                return Chain((Segment(str(check["id"])),)), False
    reason = detail.get("reason")
    if isinstance(reason, str):
        chain = parse_chain(reason, catalogue)
        if chain.segments:
            return chain, False
    return parse_chain(message, catalogue), False


def render_error(
    document: Mapping[str, Any],
    *,
    context: RenderContext | None = None,
    catalogue: Catalogue = CATALOGUE,
    strict: bool = False,
) -> Explanation:
    """An `ApiError` document (`code`, `message`, `detail`) → its explanation (§4.4)."""
    context = context or RenderContext()
    code = str(document["code"])
    message = str(document.get("message", ""))
    detail = document.get("detail") or {}
    if not isinstance(detail, Mapping):
        detail = {}
    if context.operation is None and isinstance(detail.get("operation"), str):
        context = replace(context, operation=detail["operation"])
    chain, from_binder = _candidate_chain(detail, message, catalogue)
    links = [Link(code), *resolve(chain, catalogue)]
    declared = {
        name
        for link in links
        if (entry := catalogue.entry(link.code)) is not None
        for name in entry.params
    }
    members = {name: value for name, value in detail.items() if name in declared}
    unbound = detail.get("unbound")
    hint = None
    extra: tuple[str, ...] = ()
    kind_override = None
    if isinstance(unbound, Mapping):
        hint = unbound.get("hint") if isinstance(unbound.get("hint"), str) else None
        implicated = unbound.get("implicated")
        if isinstance(implicated, Sequence) and not isinstance(implicated, str):
            extra = tuple(str(item) for item in implicated)
        if from_binder and unbound.get("kind") in UNBOUND_INPUT_KINDS:
            kind_override = "input"
    request = _Request(
        links=links,
        params=_merge(context, links, members),
        context=context,
        machine=f"{code}: {message}",
        family_hint="api_error",
        hint=hint,
        kind_override=kind_override,
        extra_elements=extra,
    )
    return _explain(request, catalogue, strict=strict)


def _consistent(diagnosis: Mapping[str, Any], links: Sequence[Link], catalogue: Catalogue) -> bool:
    """§4.4: the sidecar applies only to a code of the chain whose element params agree."""
    code = diagnosis.get("code")
    if code not in {link.code for link in links}:
        return False
    entry = catalogue.entry(str(code))
    params = diagnosis.get("params") or {}
    chained: dict[str, Any] = {}
    for link in links:
        chained.update(link.params)
    for name, value in params.items():
        declared = entry.params.get(name) if entry is not None else None
        if declared is None or declared.type not in ELEMENT_TYPES:
            continue
        if name in chained and chained[name] != value:
            return False
    return True


def _derived_elements(
    entry: Entry, params: Mapping[str, Any], revision: Mapping[str, Any] | None
) -> dict[str, Any]:
    """§4.2.5, for a run failure (review Q1): an entry's `outlet` stream param, when absent, is
    the one connection that leaves its `unit` param's `outlet` port in the revision. Absent when
    the revision has no such connection, or more than one."""
    declared, unit = entry.params.get("outlet"), params.get("unit")
    if (
        declared is None
        or declared.type != "stream"
        or _present(params.get("outlet"))
        or not isinstance(unit, str)
        or revision is None
    ):
        return {}
    connections = revision.get("connections")
    leaving = [
        item.get("id")
        for item in (connections if isinstance(connections, Sequence) else ())
        if isinstance(item, Mapping)
        and isinstance(item.get("from"), Mapping)
        and item["from"].get("instance") == unit
        and item["from"].get("port") == "outlet"
    ]
    return {"outlet": leaving[0]} if len(leaving) == 1 and isinstance(leaving[0], str) else {}


def render_failure(
    *,
    outcome: str,
    message: str | None,
    diagnosis: Diagnostic | Mapping[str, Any] | None = None,
    context: RenderContext | None = None,
    catalogue: Catalogue = CATALOGUE,
    strict: bool = False,
) -> Explanation:
    """A failure bundle's `outcome` and `observations.message`, with the sidecar → explanation."""
    explanation, _ = explain_failure(
        outcome=outcome,
        message=message,
        diagnosis=diagnosis,
        context=context,
        catalogue=catalogue,
        strict=strict,
    )
    return explanation


def explain_failure(
    *,
    outcome: str,
    message: str | None,
    diagnosis: Diagnostic | Mapping[str, Any] | None = None,
    context: RenderContext | None = None,
    catalogue: Catalogue = CATALOGUE,
    strict: bool = False,
) -> tuple[Explanation, dict[str, Any]]:
    """`render_failure`'s explanation and the merged params it was rendered from (context, the
    chain's params outer → inner, then the sidecar's; a quantity as `{value, unit, kind}`):
    `RunFailure.params` (§4.8)."""
    context = context or RenderContext()
    links = [Link(outcome)]
    if message:
        links.extend(resolve(parse_chain(message, catalogue), catalogue))
    explained = next(
        (entry for link in reversed(links) if (entry := catalogue.entry(link.code)) is not None),
        None,
    )
    layer: dict[str, Any] = {}
    if diagnosis is not None:
        document = diagnosis.as_document() if isinstance(diagnosis, Diagnostic) else diagnosis
        if _consistent(document, links, catalogue):
            layer = dict(document.get("params") or {})
            detail = layer.get("detail")
            if explained is not None and isinstance(detail, str):
                # Review Q1 (WO-5a): the sidecar's detail lines hold the numbers the bundle's
                # one-line message lacks; the explained entry's pattern reads them.
                layer = {**detail_params(explained, detail), **layer}
        elif strict or audit.auditor is not None:
            raise RenderError(f"diagnosis {document.get('code')!r} does not match the chain")
    params = _merge(context, links, layer)
    if explained is not None:
        params.update(_derived_elements(explained, params, context.revision))
    request = _Request(
        links=links,
        params=params,
        context=context,
        machine=message or outcome,
        family_hint="outcome",
    )
    return _explain(request, catalogue, strict=strict), dict(request.params)


# -- the catalogue entry (`explain`, §3.5, §4.9) ------------------------------------------------

#: §3.5: an unknown code's suggestions — at most this many keys within this edit distance.
MAX_SUGGESTIONS = 5
MAX_SUGGESTION_DISTANCE = 3


def _distance(a: str, b: str) -> int:
    """The Levenshtein distance between `a` and `b` (unit-cost insert, delete, substitute)."""
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, start=1):
        current = [i]
        for j, right in enumerate(b, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left != right))
            )
        previous = current
    return previous[-1]


def suggestions(code: str, catalogue: Catalogue = CATALOGUE) -> list[str]:
    """§3.5: up to `MAX_SUGGESTIONS` catalogue keys within Levenshtein distance
    `MAX_SUGGESTION_DISTANCE` of `code`, compared case-insensitively, sorted by (distance, key)."""
    folded = code.casefold()
    scored = sorted(
        (distance, key)
        for key in catalogue.keys()
        if (distance := _distance(folded, key.casefold())) <= MAX_SUGGESTION_DISTANCE
    )
    return [key for _, key in scored[:MAX_SUGGESTIONS]]


def _display(entry: Entry, name: str) -> str | None:
    text = entry.document.get(name)
    return None if text is None else template.display(parsed(str(text)))


def entry_document(code: str, catalogue: Catalogue = CATALOGUE) -> dict[str, Any] | None:
    """§4.9: the catalogue entry `code` as `application-results.schema.json#/$defs/message_entry`
    — its display templates (`{p}` → `<p>`, optional brackets removed), params, gap, see-also,
    examples rendered with their params (surface `None`), docs URL, deprecation and the
    catalogue's id and digest — or `None` when `code` is not a key. Reads no project state."""
    entry = catalogue.entry(code)
    if entry is None:
        return None
    return {
        "code": entry.code,
        "family": entry.family,
        "kind": entry.kind,
        "complete": entry.complete,
        "title": entry.title,
        **{name: _display(entry, name) for name in TEMPLATE_FIELDS},
        "params": [
            {"name": p.name, "type": p.type, "label": p.label, "optional": p.optional}
            for p in entry.params.values()
        ],
        "gap": entry.gap,
        "see_also": list(entry.see_also),
        "examples": [
            render_code(code, example["params"], chain=example.get("chain"), catalogue=catalogue)
            for example in entry.examples
        ],
        "docs": entry.docs,
        "deprecated": bool(entry.document.get("deprecated", False)),
        "replaced_by": entry.document.get("replaced_by"),
        "catalogue": {"id": FORMAT_ID, "sha256": catalogue.sha256()},
    }
