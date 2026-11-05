"""The message catalogue (MSG design note §3.2, §4.2, §4.11): load, validate, merge, register.

The core catalogue is package data, `catalogue/*.yaml`, each file one document of
`schemas/message-catalogue.schema.json`; `kinds.yaml` and `vocabulary.yaml` are that schema's two
table forms. `CATALOGUE` is the lazy process singleton: the core is read on first use, an extension
may `register()` its own namespaced document until the first lookup, and the first lookup freezes
the key set (§4.11). Codes are stable: a key is never removed or renamed, only deprecated.

Neither the format id nor the content digest enters any identity, hash or explanation (§3.2).
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from importlib import resources
from typing import Any, Final

from openflowsheet.messages import template

FORMAT_ID: Final[str] = "openflowsheet-messages-v1"
#: `site_url` in `mkdocs.yml`; `tests/test_msg_engine.py` holds the two equal.
DOCS_BASE: Final[str] = "https://computational-chemical-engineering.github.io/openflowsheet/"
#: §3.5: one generated docs page per family.
FAMILY_PAGES: Final[Mapping[str, str]] = {
    "api_error": "api-errors",
    "refusal": "refusals",
    "outcome": "outcomes",
    "check": "checks",
    "status": "statuses",
    "limitation": "limitations",
    "notice": "notices",
    "job": "jobs",
}
KINDS: Final[tuple[str, ...]] = ("input", "not_supported", "numerical", "bug", "notice")
#: §4.2.4: the param types that name an element and render single-quoted.
ELEMENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "unit",
        "stream",
        "port",
        "specification",
        "element",
        "revision",
        "job",
        "artifact",
        "bundle",
        "directory",
    }
)
#: §4.2.5: the context params every template may name, with their types.
CONTEXT_PARAMS: Final[Mapping[str, str]] = {
    "revision": "revision",
    "job": "job",
    "bundle": "bundle",
    "operation": "text",
}
#: §4.2.5: the element types a revision document derives `<x>_path` (and, for units,
#: `<x>_model`) for, and the document member each one indexes.
DERIVING: Final[Mapping[str, str]] = {
    "unit": "instances",
    "stream": "connections",
    "specification": "specifications",
    "element": "instances",
}
TABLE_FILES: Final[tuple[str, ...]] = ("kinds.yaml", "vocabulary.yaml")
TEMPLATE_FIELDS: Final[tuple[str, ...]] = ("summary", "context", "where", "why", "action")


class CatalogueError(ValueError):
    """A catalogue document that is invalid, clashes with a key, or comes too late (§4.11)."""


@dataclass(frozen=True)
class Kind:
    label: str
    default_action: str


@dataclass(frozen=True)
class Param:
    name: str
    type: str
    label: str
    optional: bool
    vocabulary: str | None
    unit: str | None
    quantity_kind: str | None


@dataclass(frozen=True)
class Entry:
    """One validated catalogue entry (§4.2.2), with its templates parsed on first use."""

    document: Mapping[str, Any]
    namespace: str | None = None

    @property
    def code(self) -> str:
        return str(self.document["code"])

    @property
    def family(self) -> str:
        return str(self.document["family"])

    @property
    def kind(self) -> str:
        return str(self.document["kind"])

    @property
    def complete(self) -> bool:
        return bool(self.document["complete"])

    @property
    def title(self) -> str:
        return str(self.document["title"])

    @property
    def args(self) -> tuple[str, ...]:
        return tuple(self.document.get("args", ()))

    @property
    def detail_pattern(self) -> str | None:
        pattern = self.document.get("detail_pattern")
        return None if pattern is None else str(pattern)

    @property
    def variants(self) -> Sequence[Mapping[str, Any]]:
        return tuple(self.document.get("variants", ()))

    @property
    def gap(self) -> Mapping[str, Any] | None:
        gap = self.document.get("gap")
        return None if gap is None else dict(gap)

    @property
    def see_also(self) -> tuple[str, ...]:
        return tuple(self.document.get("see_also", ()))

    @property
    def examples(self) -> Sequence[Mapping[str, Any]]:
        return tuple(self.document.get("examples", ()))

    @property
    def review(self) -> bool:
        return bool(self.document.get("review", False))

    @cached_property
    def params(self) -> Mapping[str, Param]:
        """The declared params, in declaration order."""
        return {
            name: Param(
                name=name,
                type=str(spec["type"]),
                label=str(spec.get("label", name.replace("_", " "))),
                optional=bool(spec.get("optional", False)),
                vocabulary=spec.get("vocabulary"),
                unit=spec.get("unit"),
                quantity_kind=spec.get("quantity_kind"),
            )
            for name, spec in dict(self.document.get("params", {})).items()
        }

    @property
    def docs(self) -> str:
        return f"{DOCS_BASE}messages/{FAMILY_PAGES[self.family]}/#{self.code}"

    def templates(self) -> Iterator[tuple[str, int | None, str]]:
        """Every template as `(field, variant index or None for the base, text)`."""
        for name in TEMPLATE_FIELDS:
            if name in self.document:
                yield name, None, str(self.document[name])
        for index, variant in enumerate(self.variants):
            for name in TEMPLATE_FIELDS:
                if name in variant:
                    yield name, index, str(variant[name])


def _yaml_load(text: str) -> Any:
    import yaml  # noqa: PLC0415 (PyYAML is a runtime dependency; loaded with the catalogue)

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load(text, Loader=loader)  # noqa: S506 (a safe loader)


@dataclass
class _Validators:
    schema: Mapping[str, Any]
    cache: dict[str, Any] = field(default_factory=dict)

    def validate(self, document: object, definition: str) -> None:
        validator = self.cache.get(definition)
        if validator is None:
            from jsonschema import Draft202012Validator  # noqa: PLC0415

            validator = Draft202012Validator(
                {"$defs": self.schema["$defs"], "$ref": f"#/$defs/{definition}"}
            )
            self.cache[definition] = validator
        errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
        if errors:
            first = errors[0]
            where = "/".join(str(part) for part in first.absolute_path)
            raise CatalogueError(f"{definition} invalid at /{where}: {first.message}")


def _schema() -> Mapping[str, Any]:
    import json  # noqa: PLC0415

    from openflowsheet.resources import packaged  # noqa: PLC0415

    text = packaged("schemas/message-catalogue.schema.json").read_text(encoding="utf-8")
    loaded: Mapping[str, Any] = json.loads(text)
    return loaded


class Catalogue:
    """The merged catalogue: the core documents plus registered extensions (§4.11)."""

    def __init__(
        self, core: Mapping[str, str] | None = None, *, validate_core: bool | None = None
    ) -> None:
        #: `{file name: YAML text}`; `None` reads the package's `catalogue/*.yaml`.
        self._core_texts = core
        #: Whether the core documents are schema-validated at load. `None`: when given texts, or
        #: under the test-suite audit. The package's own files are validated by the suite
        #: (`tests/test_msg_engine.py`), so a production load skips the schema pass (the cold-load
        #: budget, §7 Performance); an extension's document is always validated (`register`).
        self._validate_core = validate_core
        self._lock = threading.RLock()
        self._entries: dict[str, Entry] | None = None
        self._kinds: dict[str, Kind] = {}
        self._vocabulary: dict[str, dict[str, str]] = {}
        self._frozen = False
        self._validators: _Validators | None = None

    # -- loading ----------------------------------------------------------------------------

    def _validator(self) -> _Validators:
        if self._validators is None:
            self._validators = _Validators(_schema())
        return self._validators

    def _texts(self) -> dict[str, str]:
        if self._core_texts is not None:
            return dict(self._core_texts)
        directory = resources.files("openflowsheet.messages") / "catalogue"
        return {
            entry.name: entry.read_text(encoding="utf-8")
            for entry in sorted(directory.iterdir(), key=lambda e: e.name)
            if entry.name.endswith(".yaml") and entry.name != "scan-allow.yaml"
        }

    def _load(self) -> dict[str, Entry]:
        with self._lock:
            if self._entries is not None:
                return self._entries
            validate = self._validate_core
            if validate is None:
                from openflowsheet.messages import audit  # noqa: PLC0415

                validate = self._core_texts is not None or audit.auditor is not None

            def check(document: object, definition: str) -> None:
                if validate:
                    self._validator().validate(document, definition)

            entries: dict[str, Entry] = {}
            for name, text in self._texts().items():
                document = _yaml_load(text)
                if name == "kinds.yaml":
                    check(document, "kinds_document")
                    self._kinds = {
                        kind: Kind(str(value["label"]), str(value["default_action"]))
                        for kind, value in document["kinds"].items()
                    }
                elif name == "vocabulary.yaml":
                    check(document, "vocabulary_document")
                    self._vocabulary = {
                        table: {str(k): str(v) for k, v in values.items()}
                        for table, values in document["vocabulary"].items()
                    }
                else:
                    check(document, "catalogue_document")
                    if document["namespace"] is not None:
                        raise CatalogueError(f"{name}: a core document has no namespace")
                    self._merge(entries, document, None, name)
            if set(self._kinds) != set(KINDS):
                raise CatalogueError("kinds.yaml must define exactly the five kinds")
            self._entries = entries
            return entries

    @staticmethod
    def _merge(
        entries: dict[str, Entry], document: Mapping[str, Any], namespace: str | None, source: str
    ) -> None:
        for item in document["entries"]:
            code = str(item["code"])
            if code in entries:
                raise CatalogueError(f"{source}: duplicate code {code!r}")
            if namespace is None and "." in code:
                raise CatalogueError(f"{source}: a '.' is reserved for extension namespaces")
            entries[code] = Entry(item, namespace)

    def register(self, document: Mapping[str, Any], *, namespace: str) -> None:
        """§4.11: add an extension's entries under `namespace`, before the first lookup."""
        with self._lock:
            if self._frozen:
                raise RuntimeError("the message catalogue is frozen: register before first use")
            entries = self._load()
            self._validator().validate(document, "catalogue_document")
            if document.get("namespace") != namespace:
                raise CatalogueError(
                    f"document namespace {document.get('namespace')!r} is not {namespace!r}"
                )
            prefix = namespace + "."
            staged = dict(entries)
            for item in document["entries"]:
                code = str(item["code"])
                if not code.startswith(prefix):
                    raise CatalogueError(f"{code!r} is not in namespace {namespace!r}")
                if code in staged:
                    raise CatalogueError(f"{code!r} is already in the catalogue")
                staged[code] = Entry(item, namespace)
            self._entries = staged

    # -- lookup (freezes) -------------------------------------------------------------------

    def _frozen_entries(self) -> dict[str, Entry]:
        entries = self._load()
        self._frozen = True
        return entries

    def entry(self, code: str) -> Entry | None:
        return self._frozen_entries().get(code)

    def __contains__(self, code: object) -> bool:
        return code in self._frozen_entries()

    def keys(self) -> list[str]:
        return sorted(self._frozen_entries())

    def entries(self) -> list[Entry]:
        entries = self._frozen_entries()
        return [entries[code] for code in sorted(entries)]

    def kind(self, kind: str) -> Kind:
        self._frozen_entries()
        return self._kinds[kind]

    def phrase(self, vocabulary: str, value: str) -> str | None:
        self._frozen_entries()
        return self._vocabulary.get(vocabulary, {}).get(value)

    def vocabularies(self) -> Mapping[str, Mapping[str, str]]:
        self._frozen_entries()
        return self._vocabulary

    def sha256(self) -> str:
        """SHA-256 of ADR 0002 canonical JSON of the merged entries, sorted by code (§3.2)."""
        from openflowsheet.canonical import canonical_json  # noqa: PLC0415

        documents = [dict(entry.document) for entry in self.entries()]
        return hashlib.sha256(canonical_json(documents)).hexdigest()


CATALOGUE: Final[Catalogue] = Catalogue()


def register(document: Mapping[str, Any], *, namespace: str) -> None:
    """§4.11, the extension slot F1 inherits: `CATALOGUE.register(document, namespace=...)`."""
    CATALOGUE.register(document, namespace=namespace)


def parsed(text: str) -> tuple[template.Node, ...]:
    """A template's node tree (cached)."""
    return template.parse(text)
