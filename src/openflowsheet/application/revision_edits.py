"""Revision edits and revision diffs: the pure algebra under K06's transactions.

Edits: `apply_edits` applies a change's `Edit`s in order to a copy of a revision document, and
`EditPathError` names the first one that cannot be applied (§5.2, `edit_path_invalid`);
`json_pointer` writes the paths. Diffs: `semantic_diff` compares two revision documents,
`element_diff` compares their elements by id (ADR 0019 Amendment 3), and `revision_diff` is the
two together. Nothing here reads or writes a store: `local` and `revision_continuation` import
from here, and `transactions` re-exports every public name for K06's callers.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

from openflowsheet.application.revisions import CONTENT_HASH_EXCLUDED
from openflowsheet.application.types import DiffElement, DiffMember, Edit, SemanticDiff


class EditPathError(ValueError):
    """§5.2 `edit_path_invalid`: edit `edit_index` cannot be applied at `pointer`."""

    def __init__(self, edit_index: int, pointer: str, reason: str) -> None:
        super().__init__(f"edit {edit_index} at {pointer or '/'}: {reason}")
        self.edit_index = edit_index
        self.pointer = pointer
        self.reason = reason


def json_pointer(path: Sequence[str | int]) -> str:
    """RFC 6901: `/`-joined, `~` as `~0` and `/` as `~1`."""
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


def apply_edits(base: Mapping[str, Any], edits: Sequence[Edit]) -> dict[str, Any]:
    """Apply `edits` in order to a copy of `base`; `EditPathError` names the first bad one.

    §5.2: strings index objects and integers index arrays. `set` on an object key creates or
    replaces it, creating missing *object* parents (K06); on an array index the index must
    exist. `append` needs an existing array at its path. `remove` on an object key removes it,
    and an absent key — or an absent parent — is a no-op (K06); on an array index the index must
    exist and later elements shift down. Anything else is refused, never guessed at.

    Applied to a copy: a failure part way through leaves the base untouched, which is what
    "grouped atomically" has to mean for a draft nobody wants half-edited.
    """
    document = copy.deepcopy(dict(base))
    for index, edit in enumerate(edits):
        _apply(document, edit, index)
    return document


def _apply(document: dict[str, Any], edit: Edit, index: int) -> None:
    """Apply edit number `index` to `document` in place: walk its path to the node it acts on
    (an object member by `_ensure_member`, an array element by `_check_array_index`),
    then edit that node (`_apply_at`). A `remove` whose parent is absent returns from the walk.
    """
    path = edit.path
    walk = path if edit.operation == "append" else path[:-1]
    node: Any = document
    for depth, key in enumerate(walk):
        here = json_pointer(path[: depth + 1])
        if isinstance(node, dict):
            following = path[depth + 1] if depth + 1 < len(path) else None
            if not _ensure_member(node, key, following, edit, index, here):
                return  # an absent parent holds no key to remove
        elif isinstance(node, list):
            _check_array_index(node, key, index, here)
        else:
            raise EditPathError(index, here, "the path runs through a scalar")
        node = node[key]
    _apply_at(node, edit, index)


def _ensure_member(
    node: dict[str, Any],
    key: str | int,
    following: str | int | None,
    edit: Edit,
    index: int,
    here: str,
) -> bool:
    """One step of edit `index`'s walk into the object `node`: True when member `key` exists,
    after creating it if needed; `following` is the path's next key (`None` at its end).

    An integer key is refused. An absent member is created as an empty object for a `set` whose
    next key is a string (K06) and refused for anything else, except that a `remove` returns
    False: an absent parent holds no key to remove.
    """
    if not isinstance(key, str):
        raise EditPathError(index, here, "an integer indexes an array; this is an object")
    if key not in node:
        if edit.operation == "remove":
            return False
        if edit.operation == "set" and isinstance(following, str):
            node[key] = {}
        else:
            raise EditPathError(index, here, "no such member")
    return True


def _check_array_index(node: list[Any], key: str | int, index: int, here: str) -> None:
    """One step of edit `index`'s walk into the array `node`: `key` must be an existing index."""
    if not isinstance(key, int):
        raise EditPathError(index, here, "a string indexes an object; this is an array")
    if key >= len(node):
        raise EditPathError(index, here, f"index {key} is past the array's {len(node)}")


def _apply_at(node: Any, edit: Edit, index: int) -> None:
    """Apply edit number `index` at `node`, the end of its walk: the array an `append` extends,
    or the object or array that holds the last key of a `set` or `remove`.
    """
    path = edit.path
    if edit.operation == "append":
        if not isinstance(node, list):
            raise EditPathError(index, json_pointer(path), "append needs an array here")
        node.append(copy.deepcopy(edit.value))
        return

    last = path[-1]
    here = json_pointer(path)
    if isinstance(node, dict):
        if not isinstance(last, str):
            raise EditPathError(index, here, "an integer indexes an array; this is an object")
        if edit.operation == "set":
            node[last] = copy.deepcopy(edit.value)
        else:
            node.pop(last, None)
    elif isinstance(node, list):
        if not isinstance(last, int):
            raise EditPathError(index, here, "a string indexes an object; this is an array")
        if last >= len(node):
            raise EditPathError(index, here, f"index {last} is past the array's {len(node)}")
        if edit.operation == "set":
            node[last] = copy.deepcopy(edit.value)
        else:
            del node[last]
    else:
        raise EditPathError(index, json_pointer(path[:-1]), "the path runs through a scalar")


def semantic_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> SemanticDiff:
    """Paths added, removed and changed in the revision's content.

    Descriptive fields are excluded on purpose: two revisions differing only in their title are
    the same process, and a diff that said otherwise would make every retitle look like an
    edit to the model.
    """
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []

    def walk(left: Any, right: Any, path: str) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            for key in sorted(set(left) | set(right)):
                if not path and key in CONTENT_HASH_EXCLUDED:
                    continue
                where = f"{path}.{key}" if path else key
                if key not in left:
                    added.append(where)
                elif key not in right:
                    removed.append(where)
                else:
                    walk(left[key], right[key], where)
        elif left != right:
            changed.append(path)

    walk(before, after, "")
    return SemanticDiff(tuple(added), tuple(removed), tuple(changed))


#: ADR 0019 Amendment 3 (A3.2): the members `element_diff` pairs, in its order.
ELEMENT_MEMBERS: Final[tuple[DiffMember, ...]] = ("instances", "connections", "specifications")


def _by_id(items: Any) -> dict[str, Any] | None:
    """`items` keyed by `id` when it is a list of objects each with a string `id`, unique; else
    `None` (the member cannot be paired)."""
    if not isinstance(items, list):
        return None
    keyed: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            return None
        if item["id"] in keyed:
            return None
        keyed[item["id"]] = item
    return keyed


def _item_paths(left: Any, right: Any) -> tuple[tuple[str, ...], ...]:
    """Every path `semantic_diff`'s walk reports inside one item — keys added, keys removed,
    values changed; objects recursed by key, every other value compared atomically — as key
    tuples from the item's root, in code-point order."""
    paths: list[tuple[str, ...]] = []

    def walk(old: Any, new: Any, path: tuple[str, ...]) -> None:
        if isinstance(old, Mapping) and isinstance(new, Mapping):
            for key in set(old) | set(new):
                if key not in old or key not in new:
                    paths.append((*path, key))
                else:
                    walk(old[key], new[key], (*path, key))
        elif old != new:
            paths.append(path)

    walk(left, right, ())
    return tuple(sorted(paths))


def element_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[DiffElement, ...]:
    """ADR 0019 Amendment 3 (A3.2; M06 design note §4.2): the items of `instances`,
    `connections` and `specifications` that differ, paired by `id`. `diff_revisions`'s only.

    Where every item of a member is an object with a string `id`, unique, in both revisions: an id
    only in `after` is `added`, only in `before` `removed`, in both with unequal items `changed`
    with its `paths`. Otherwise a member that differs is one entry with `id` `None`. Items that
    differ only in order give no entry (the coarse `changed` still names the member). Ordered by
    member, then by `id` in code-point order. No member is excluded inside an item:
    `CONTENT_HASH_EXCLUDED` is top-level only."""
    elements: list[DiffElement] = []
    for member in ELEMENT_MEMBERS:
        old, new = before.get(member), after.get(member)
        left, right = _by_id(old), _by_id(new)
        if left is None or right is None:
            if old != new:
                elements.append(DiffElement(member, None, "changed"))
            continue
        for item_id in sorted(set(left) | set(right)):
            if item_id not in left:
                elements.append(DiffElement(member, item_id, "added"))
            elif item_id not in right:
                elements.append(DiffElement(member, item_id, "removed"))
            elif left[item_id] != right[item_id]:
                paths = _item_paths(left[item_id], right[item_id])
                elements.append(DiffElement(member, item_id, "changed", paths))
    return tuple(elements)


def revision_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> SemanticDiff:
    """`diff_revisions`'s result: `semantic_diff`, unchanged, with its `elements`."""
    return replace(semantic_diff(before, after), elements=element_diff(before, after))
