"""Identity-key resolution (ADR 0061 D9): lookup keys, queries, identity classes, resolution.

Every stored record carries lookup keys `<scheme>:<value>`: `sha256`, `inchikey`, `inchi`, `cas`,
`id`, `name` (its name and each synonym, NFC, casefolded, whitespace collapsed) and `formula`
(Hill order). Formula, CAS and InChIKey strings are stored as given; only these keys are
normalised. A query `<scheme>:<value>` searches that scheme; a bare query tries `inchikey` (if it
has the InChIKey pattern), `cas` (if it has the CAS pattern), `id`, `name`, `formula`, and the
first scheme with a match wins.

`resolve` returns one record SHA, or `component_ambiguous(<key>)` with the ambiguity class
(`identity`: the matches form more than one identity class; `source`: one class, several
records) and the candidates. No origin or source is ranked: the caller chooses by SHA.
`search` lists the same matches without refusing. Both read through a `KeyIndex`, which the
store stack (`records.stack`) is.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any, Final, NamedTuple, Protocol

from openflowsheet.canonical import canonical_json
from openflowsheet.records.validate import CAS, INCHIKEY, formula_counts
from openflowsheet.registry.tokens import Coded

#: D9: the lookup-key schemes.
SCHEMES: Final = ("sha256", "inchikey", "inchi", "cas", "id", "name", "formula")
#: D9: the schemes a bare query tries, in order (the first two only when the pattern matches).
BARE_ORDER: Final = ("inchikey", "cas", "id", "name", "formula")
#: D9: the identifiers whose sharing joins two matched records into one identity class.
CLASS_SCHEMES: Final = ("cas", "inchikey")


class KeyIndex(Protocol):
    """What resolution reads: the SHAs holding a lookup key, and a stored record by SHA."""

    def shas_for(
        self, scheme: str, value: str, *, record_type: str | None = None
    ) -> frozenset[str]:
        """The SHAs of the records (of `record_type`, when given) holding key `scheme:value`."""
        ...

    def record(self, sha: str) -> Mapping[str, Any]:
        """The identity projection stored under `sha`."""
        ...


class Matches(NamedTuple):
    """A query's matches: the scheme that matched (`None` when nothing did) and the SHAs, sorted."""

    scheme: str | None
    shas: tuple[str, ...]


class Ambiguous(NamedTuple):
    """D9's refusal: `component_ambiguous(<key>)` and its `detail` (`ambiguity`, `candidates`)."""

    refusal: Coded
    detail: Mapping[str, Any]


def name_key(text: str) -> str:
    """D9's `name:` value: NFC, casefolded, whitespace collapsed (NFC again after the casefold,
    which may leave a string that is not NFC)."""
    folded = unicodedata.normalize("NFC", text).casefold()
    return unicodedata.normalize("NFC", " ".join(folded.split()))


def formula_key(formula: str) -> str:
    """D9's `formula:` value: the formula in Hill order (C, then H, then the other symbols
    alphabetically; without carbon all alphabetically; a count of 1 not written). A formula that
    does not read as element symbols with counts (`formula_counts` gives `None`) is its own key,
    NFC and without whitespace."""
    counts = formula_counts(formula)
    if counts is None:
        return "".join(unicodedata.normalize("NFC", formula).split())
    first = ("C", "H") if "C" in counts else ()
    order = [s for s in first if s in counts] + sorted(s for s in counts if s not in first)
    return "".join(s if counts[s] == 1 else f"{s}{counts[s]}" for s in order)


def lookup_keys(sha: str, record: Mapping[str, Any]) -> frozenset[tuple[str, str]]:
    """D9's lookup keys of the normalised record stored under `sha`, as (scheme, value) pairs.
    A record without identifiers (a parameter set, a synthetic component) has `sha256`, `id` and
    `name` keys only."""
    keys = {("sha256", sha), ("id", str(record["id"])), ("name", name_key(str(record["name"])))}
    keys.update(("name", name_key(synonym)) for synonym in record.get("synonyms", ()))
    identifiers: Mapping[str, str] = record.get("identifiers", {})
    keys.update((s, identifiers[s]) for s in ("inchikey", "inchi", "cas") if s in identifiers)
    if "formula" in identifiers:
        keys.add(("formula", formula_key(identifiers["formula"])))
    return frozenset(keys)


def query_keys(query: str) -> tuple[tuple[str, str], ...]:
    """The (scheme, value) pairs a query tries, in order: one for `<scheme>:<value>` (a prefix
    that is not a scheme makes the query bare), D9's bare order otherwise, each value spelled as
    its scheme's lookup key."""
    prefix, colon, rest = query.partition(":")
    if colon and prefix in SCHEMES:
        return ((prefix, _key_value(prefix, rest)),)
    tried = [s for s in BARE_ORDER if s not in CLASS_SCHEMES or _patterned(s, query)]
    return tuple((s, _key_value(s, query)) for s in tried)


def _key_value(scheme: str, value: str) -> str:
    """`value` spelled as a `scheme` lookup key (`name`, `formula` normalised; others as given)."""
    if scheme == "name":
        return name_key(value)
    if scheme == "formula":
        return formula_key(value)
    return value


def _patterned(scheme: str, value: str) -> bool:
    """Whether a bare query has `scheme`'s pattern (D3's InChIKey, the CAS digits pattern)."""
    return (INCHIKEY if scheme == "inchikey" else CAS).fullmatch(value) is not None


def search(index: KeyIndex, query: str, *, record_type: str | None = None) -> Matches:
    """D9's matches of `query` among the records of `record_type` (every type when `None`): the
    first tried scheme with a match, and its SHAs; `Matches(None, ())` when no scheme matches."""
    for scheme, value in query_keys(query):
        shas = index.shas_for(scheme, value, record_type=record_type)
        if shas:
            return Matches(scheme, tuple(sorted(shas)))
    return Matches(None, ())


def resolve(
    index: KeyIndex, query: str, *, record_type: str = "component"
) -> str | Ambiguous | None:
    """D9's resolution of `query` among the records of `record_type`: the one matching record's
    SHA; `Ambiguous` when several match (`identity` when they form more than one identity class,
    `source` when one); `None` when nothing matches (the caller's `not_found` or
    `data_unavailable`)."""
    matches = search(index, query, record_type=record_type)
    if len(matches.shas) <= 1:
        return matches.shas[0] if matches.shas else None
    records = {sha: index.record(sha) for sha in matches.shas}
    classes = identity_classes(records)
    detail = {
        "ambiguity": "identity" if len(classes) > 1 else "source",
        "candidates": candidates(classes, records),
    }
    return Ambiguous(Coded("component_ambiguous", {"key": query}), detail)


def identity_classes(records: Mapping[str, Mapping[str, Any]]) -> list[list[str]]:
    """D9's identity classes of the matched `records` (by SHA): the connected components under
    "shares an InChIKey or a CAS"; a record with neither is its own class. Each class is its
    SHAs sorted, and the classes are in the order of their first SHA."""
    parent = {sha: sha for sha in records}
    owner: dict[tuple[str, str], str] = {}
    for sha in sorted(records):
        for key in _class_keys(records[sha]):
            if key in owner:
                parent[_root(parent, sha)] = _root(parent, owner[key])
            else:
                owner[key] = sha
    classes: dict[str, list[str]] = {}
    for sha in sorted(records):
        classes.setdefault(_root(parent, sha), []).append(sha)
    return sorted(classes.values())


def _class_keys(record: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The record's (scheme, value) pairs of the class schemes, CAS and InChIKey."""
    identifiers: Mapping[str, str] = record.get("identifiers", {})
    return [(s, identifiers[s]) for s in CLASS_SCHEMES if s in identifiers]


def _root(parent: dict[str, str], sha: str) -> str:
    """The representative of `sha`'s set in the union-find forest `parent` (path halving, the
    forest's own working state)."""
    while parent[sha] != sha:
        parent[sha] = parent[parent[sha]]
        sha = parent[sha]
    return sha


def candidates(
    classes: Iterable[list[str]], records: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """D9's `detail.candidates`: per class `{class, records: [{sha, source_ids, name}]}`, where
    `class` is the sorted `<scheme>:<value>` CAS and InChIKey keys its records carry (empty for a
    record with neither); the records sorted by SHA, the classes by their canonical-JSON bytes."""
    found = []
    for shas in classes:
        keys = sorted({f"{s}:{v}" for sha in shas for s, v in _class_keys(records[sha])})
        members = [
            {
                "sha": sha,
                "source_ids": sorted(records[sha]["sources"]),
                "name": records[sha]["name"],
            }
            for sha in sorted(shas)
        ]
        found.append({"class": keys, "records": members})
    return sorted(found, key=canonical_json)
