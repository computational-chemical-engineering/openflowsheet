"""Bounded text and bounded projections: what every response may carry (§10.4, §11.4).

**Bounding (§10.4).** Every string in every response is project data an agent will read, and some
of it was written by whoever could commit a revision or hand over a bundle. `bound_text` replaces
the code points that hide or reorder text — C0 and C1 controls except `\\n` and `\\t`, the
zero-width characters, the byte-order mark and the bidirectional embeddings, overrides and
isolates — with U+FFFD, then cuts the string so that it fits its limit with a marker saying how
much it cut.
`bound_document` applies it to every string value (2048 code points) and every object key (256),
deterministically renaming keys that collide once bounded. It does not look for text that reads
like an instruction: that is not falsifiable, and it is not claimed. Authority comes from the
credential only (§10.1); this is the mitigation beside it.

Lone surrogates (U+D800–U+DFFF) are replaced too. §10.4 does not list them, but a parsed JSON
string can hold one (`"\\ud800"`), and no transport can encode it in UTF-8.

**Projection (§11.4).** A document is viewed at an RFC 6901 pointer. Objects below the requested
depth are replaced by `{"$elided": {"pointer": p, "members": n}}` (an array by `{..., "items": n}`),
nested arrays keep their first 20 items and one elision marker, an array target is paged by an
offset cursor, and a view whose bounded canonical size exceeds 65 536 bytes is re-rendered one
level shallower until it fits or its depth is 1, and is then marked `truncated`. Each step is a
pure function of its inputs, so a view is reproducible.

Depth counts container levels below the target: the target itself is level 0 and is always shown
(`depth >= 1`); a non-empty object or array at level `depth` is elided. An elision marker's `n` is
the size of the node at its pointer — members of an object, items of an array — so an agent reads
the rest with that pointer.
"""

from __future__ import annotations

import base64
import binascii
import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

from openflowsheet.application.contract import ApplicationError, Projection, api_error
from openflowsheet.canonical import canonical_json

#: §10.4: the bounds of a string value and of an object key, in code points.
TEXT_LIMIT: Final[int] = 2048
KEY_LIMIT: Final[int] = 256
#: §11.4: depth (default 4, at most 12); an array target's page (default 50, at most 200); the
#: items a nested array keeps; the canonical size a view must fit.
DEFAULT_DEPTH: Final[int] = 4
MAX_DEPTH: Final[int] = 12
DEFAULT_PAGE: Final[int] = 50
MAX_PAGE: Final[int] = 200
NESTED_ARRAY_ITEMS: Final[int] = 20
SIZE_CAP: Final[int] = 65_536
ELIDED: Final[str] = "$elided"
REPLACEMENT: Final[str] = "�"

#: §10.4's forbidden code points, each replaced by U+FFFD: C0 except `\n` and `\t`, DEL and C1
#: (`Cc`), U+200B–U+200D, U+2060, U+FEFF, U+202A–U+202E, U+2066–U+2069; and lone surrogates.
FORBIDDEN_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x00, 0x08),
    (0x0B, 0x1F),
    (0x7F, 0x9F),
    (0x200B, 0x200D),
    (0x2060, 0x2060),
    (0xFEFF, 0xFEFF),
    (0x202A, 0x202E),
    (0x2066, 0x2069),
    (0xD800, 0xDFFF),
)
_REPLACE: Final[Mapping[int, str]] = {
    code: REPLACEMENT for low, high in FORBIDDEN_RANGES for code in range(low, high + 1)
}


# =================================================================================== bounding


def is_forbidden(character: str) -> bool:
    """Whether `bound_text` replaces this code point."""
    return ord(character) in _REPLACE


def bound_text(text: str, limit: int) -> str:
    """§10.4: forbidden code points replaced by U+FFFD; a string longer than `limit` code points
    cut and `…[+N chars]` appended, `N` the code points cut. The result is at most `limit` code
    points *with* the marker, so a bounded string meets a schema's `maxLength` of the same limit
    (an `ApiError` message is ≤ 2048): the most code points are kept that leave room for the
    marker of what they cut. A limit too small for any marker is a plain cut. Replacement is one
    code point for one, so it commutes with the cut."""
    if limit < 0:
        raise ValueError("a text limit is >= 0")
    if len(text) <= limit:
        return text.translate(_REPLACE)
    # The marker is `…[+` `N` ` chars]`: 10 code points and N's digits. Fewer digits keep more.
    for digits in range(1, len(str(len(text))) + 1):
        keep = limit - 10 - digits
        if keep < 0:
            break
        if len(str(len(text) - keep)) <= digits:
            return f"{text[:keep].translate(_REPLACE)}…[+{len(text) - keep} chars]"
    return text[:limit].translate(_REPLACE)


def bound_document(document: Any) -> Any:
    """§10.4 over a whole document: every string value to `TEXT_LIMIT`, every key to
    `KEY_LIMIT`; numbers, booleans and null unchanged. Keys are visited in canonical order
    (ADR 0002: UTF-16 code units), and a bounded key already taken gets `~2`, `~3`, … — the first
    free one — so the renaming is deterministic. The suffix counts inside `KEY_LIMIT` too (ruling
    round 4): a key that would not fit with it is first cut, without a marker, to make room."""
    if isinstance(document, str):
        return bound_text(document, TEXT_LIMIT)
    if isinstance(document, Mapping):
        bounded: dict[str, Any] = {}
        for key in sorted(document, key=lambda k: str(k).encode("utf-16-be", "surrogatepass")):
            name = bound_text(str(key), KEY_LIMIT)
            if name in bounded:
                name = next(
                    candidate
                    for n in itertools.count(2)
                    if (candidate := _suffixed(name, n)) not in bounded
                )
            bounded[name] = bound_document(document[key])
        return bounded
    if isinstance(document, list | tuple):
        return [bound_document(item) for item in document]
    return document


def _suffixed(name: str, n: int) -> str:
    """The collision candidate `name~n`, at most `KEY_LIMIT` code points in total (§10.4 as
    amended by ruling round 4): `name` is cut, without a marker, to leave room for `~n`."""
    suffix = f"~{n}"
    return name[: KEY_LIMIT - len(suffix)] + suffix


# ============================================================================ RFC 6901 pointers


def escape_token(token: str) -> str:
    """RFC 6901 §3: `~` is written `~0` and `/` is written `~1`."""
    return token.replace("~", "~0").replace("/", "~1")


def pointer_tokens(pointer: str) -> tuple[str, ...]:
    """The reference tokens of `pointer`; `ValueError` if it is not RFC 6901 syntax."""
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ValueError("a JSON pointer is empty or starts with '/'")
    tokens = pointer[1:].split("/")
    for token in tokens:
        if "~" in token.replace("~0", "").replace("~1", ""):
            raise ValueError("'~' in a JSON pointer is followed by '0' or '1'")
    return tuple(token.replace("~1", "/").replace("~0", "~") for token in tokens)


def resolve(document: Any, tokens: Sequence[str]) -> Any:
    """The node at `tokens`; `LookupError` when there is none. An array index is `0` or a
    decimal with no leading zero (RFC 6901 §4); `-` names no existing item."""
    node = document
    for token in tokens:
        if isinstance(node, Mapping):
            if token not in node:
                raise LookupError(token)
            node = node[token]
        elif isinstance(node, list | tuple):
            if not token.isdecimal() or not token.isascii() or (token != "0" and token[0] == "0"):
                raise LookupError(token)
            index = int(token)
            if index >= len(node):
                raise LookupError(token)
            node = node[index]
        else:
            raise LookupError(token)
    return node


# ================================================================================= projection


def encode_offset(offset: int) -> str:
    """§11.4: an array page's cursor, `base64url(canonical_json({"offset": k}))`, unpadded."""
    encoded = base64.urlsafe_b64encode(canonical_json({"offset": offset}))
    return encoded.decode("ascii").rstrip("=")


def decode_offset(cursor: str) -> int | None:
    """The offset of a cursor `encode_offset` issued, or `None` for anything else."""
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError, binascii.Error):
        return None
    offset = decoded.get("offset") if isinstance(decoded, dict) else None
    if (
        not isinstance(decoded, dict)
        or set(decoded) != {"offset"}
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
    ):
        return None
    return offset


def _refused(pointer: str, message: str) -> ApplicationError:
    return api_error("invalid_request", message, pointer=pointer)


def check_view_arguments(pointer: object, depth: object, cursor: object, limit: object) -> None:
    """The argument rules of every projecting method, each refused `invalid_request` with the
    request member it names."""
    if not isinstance(pointer, str):
        raise _refused("/pointer", "pointer is an RFC 6901 JSON pointer string")
    try:
        pointer_tokens(pointer)
    except ValueError as error:
        raise _refused("/pointer", str(error)) from None
    if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= MAX_DEPTH:
        raise _refused("/depth", f"depth is an integer from 1 to {MAX_DEPTH}")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
        raise _refused("/limit", f"limit is an integer from 1 to {MAX_PAGE}")
    if cursor is not None and (not isinstance(cursor, str) or decode_offset(cursor) is None):
        raise _refused("/cursor", "cursor is not one this view issued")


def _elided(pointer: str, node: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    count = "members" if isinstance(node, Mapping) else "items"
    return {ELIDED: {"pointer": pointer, count: len(node)}}


def _render(node: Any, pointer: str, level: int, depth: int) -> Any:
    """`node`, at `level` below the target, with §11.4's depth and nested-array rules."""
    if isinstance(node, Mapping):
        if node and level >= depth:
            return _elided(pointer, node)
        return {
            key: _render(value, f"{pointer}/{escape_token(key)}", level + 1, depth)
            for key, value in node.items()
        }
    if isinstance(node, list | tuple):
        if node and level >= depth:
            return _elided(pointer, node)
        items = [
            _render(item, f"{pointer}/{index}", level + 1, depth)
            for index, item in enumerate(node[:NESTED_ARRAY_ITEMS])
        ]
        if len(node) > NESTED_ARRAY_ITEMS:
            items.append(_elided(pointer, node))
        return items
    return node


def project(
    document: Any,
    *,
    subject_id: str,
    sha256: str,
    pointer: str = "",
    depth: int = DEFAULT_DEPTH,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE,
) -> Projection:
    """§11.4's view of `document` at `pointer`. Raises `ApplicationError`: `invalid_request` for
    an argument outside its rule (`detail.pointer` names the request member), `not_found` for a
    pointer with no target (`detail.pointer` is that pointer)."""
    check_view_arguments(pointer, depth, cursor, limit)
    try:
        target = resolve(document, pointer_tokens(pointer))
    except LookupError:
        raise api_error(
            "not_found", "nothing in the document at this pointer", pointer=pointer
        ) from None
    next_cursor: str | None = None
    render: Callable[[int], Any]
    if isinstance(target, list | tuple):
        offset = 0 if cursor is None else decode_offset(cursor)
        assert offset is not None  # checked above
        page = target[offset : offset + limit]
        if offset + limit < len(target):
            next_cursor = encode_offset(offset + limit)

        def render(at: int) -> Any:
            return [
                _render(item, f"{pointer}/{offset + index}", 1, at)
                for index, item in enumerate(page)
            ]

    else:
        if cursor is not None:
            raise _refused("/cursor", "a cursor pages an array, and this target is not one")

        def render(at: int) -> Any:
            return _render(target, pointer, 0, at)

    def view(at: int, truncated: bool) -> Projection:
        return Projection(
            subject_id=subject_id,
            pointer=pointer,
            sha256=sha256,
            value=render(at),
            truncated=truncated,
            next_cursor=next_cursor,
        )

    at = depth
    shown = view(at, False)
    while bounded_size(shown.as_document()) > SIZE_CAP:
        if at == 1:
            return replace(shown, truncated=True)
        at -= 1
        shown = view(at, True)
    return shown


def bounded_size(document: Any) -> int:
    """The canonical size, in bytes, of `document` as a response carries it (bounded)."""
    return len(canonical_json(bound_document(document)))
