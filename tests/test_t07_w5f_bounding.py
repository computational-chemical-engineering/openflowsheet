"""T07 W5f: every bounded string is at most its limit, marker and collision suffix included
(design note §10.4 as amended by ruling round 4; gate R4-G5).

- `bound_text(s, limit)` over 10 000 seeded random strings — astral, C0/C1 controls, bidi and
  zero-width characters, lone surrogates, plain text — at each limit {0, 1, 10, 11, 12, 128, 256,
  2048}: at most `limit` code points; unchanged but translated when it fits; otherwise the
  longest prefix whose `…[+N chars]` marker still fits, `N` the code points cut, or a plain cut
  when no marker fits (`limit < 11`).
- `bound_document`: keys that collide once bounded get `~n`, and the suffixed key is itself at
  most `KEY_LIMIT`, the bounded key cut without a marker to make room.

G13's re-run with "≤ limit" meaning the total is `test_t07_w5a_operations.assert_within_bounds`.
The expectations are written out from §10.4, independently of the implementation.
"""

from __future__ import annotations

import random

from openflowsheet.application.projection import (
    KEY_LIMIT,
    TEXT_LIMIT,
    bound_document,
    bound_text,
    is_forbidden,
)

REPLACEMENT = "\ufffd"
LIMITS = (0, 1, 10, 11, 12, 128, 256, 2048)
STRINGS = 10_000
SEED = 20260927
#: Where the random code points come from, each drawn with equal weight.
POOLS: tuple[tuple[int, int], ...] = (
    (0x20, 0x7E),  # printable ASCII
    (0x00, 0x1F),  # C0, `\n` and `\t` among them
    (0x7F, 0x9F),  # DEL and C1
    (0x200B, 0x200D),  # zero-width
    (0x202A, 0x202E),  # bidi embeddings and overrides
    (0x2066, 0x2069),  # bidi isolates
    (0xFEFF, 0xFEFF),  # byte-order mark
    (0xD800, 0xDFFF),  # lone surrogates
    (0x00A0, 0xFFFD),  # the rest of the BMP (a surrogate drawn here is one too)
    (0x10000, 0x10FFFF),  # astral
)


def _random_strings() -> list[str]:
    rng = random.Random(SEED)
    strings = []
    for _ in range(STRINGS):
        # Lengths around every limit: short, near the small limits, near 256 and near 2048.
        length = rng.choice(
            (rng.randint(0, 16), rng.randint(0, 300), rng.randint(1990, 2110), rng.randint(0, 40))
        )
        strings.append(
            "".join(chr(rng.randint(*rng.choice(POOLS))) for _ in range(length)),
        )
    return strings


def _translated(text: str) -> str:
    return "".join(REPLACEMENT if is_forbidden(c) else c for c in text)


def _marker(cut: int) -> str:
    return f"…[+{cut} chars]"


def assert_bounded_exactly(out: str, text: str, limit: int) -> None:
    """§10.4 as amended, stated from the note."""
    assert len(out) <= limit
    if len(text) <= limit:
        assert out == _translated(text)
        return
    # The longest prefix whose marker fits beside it.
    keep = next((k for k in range(limit, -1, -1) if k + len(_marker(len(text) - k)) <= limit), None)
    if keep is None:
        assert out == _translated(text[:limit]), "no marker fits: a plain cut"
        return
    assert out == _translated(text[:keep]) + _marker(len(text) - keep)
    # A prefix one code point longer would not fit with its own marker.
    assert keep + 1 + len(_marker(len(text) - keep - 1)) > limit


def test_r4_g5_bound_text_over_random_strings() -> None:
    strings = _random_strings()
    assert len(strings) == STRINGS
    kinds = {"cut": 0, "plain": 0, "whole": 0}
    for text in strings:
        for limit in LIMITS:
            out = bound_text(text, limit)
            assert_bounded_exactly(out, text, limit)
            out.encode("utf-8")  # never a surrogate
            if len(text) <= limit:
                kinds["whole"] += 1
            elif out.endswith(" chars]"):
                kinds["cut"] += 1
            else:
                kinds["plain"] += 1
    # Every branch is exercised many times over.
    assert min(kinds.values()) > 1000, kinds


def test_r4_g5_two_long_keys_bound_to_two_distinct_keys_within_the_limit() -> None:
    common = "k" * 250
    first, second = common + "A" * 50, common + "B" * 50
    assert (len(first), len(second)) == (300, 300)
    bounded = bound_document({second: 2, first: 1})
    assert len(bounded) == 2
    assert all(len(key) <= KEY_LIMIT for key in bounded)
    # Both bound to this; the first in canonical order keeps it.
    plain = bound_text(first, KEY_LIMIT)
    assert len(plain) == KEY_LIMIT
    assert bounded == {plain: 1, plain[: KEY_LIMIT - 2] + "~2": 2}


def test_the_suffix_search_runs_over_the_cut_candidates() -> None:
    """Many collisions: every suffix fits, `~10` cuts one code point more than `~9`, and a key
    already named like a candidate pushes the search on."""
    common = chr(0x1F600) * 300
    document: dict[str, object] = {common + chr(0x41 + i): i for i in range(12)}
    plain = bound_text(common + "A", KEY_LIMIT)
    # `~2`'s candidate, present as a key of its own. It sorts first (its U+2026 is below the
    # long keys' UTF-16 surrogates at the same index), so it keeps its name and `~2` is taken.
    taken = plain[: KEY_LIMIT - 2] + "~2"
    assert taken.encode("utf-16-be") < (common + "A").encode("utf-16-be")
    document[taken] = "taken"
    bounded = bound_document(document)
    assert len(bounded) == len(document)
    assert all(len(key) <= KEY_LIMIT for key in bounded)
    assert bounded[taken] == "taken"
    renamed = sorted(
        (key for key in bounded if key not in (plain, taken)), key=lambda k: int(k.rsplit("~")[1])
    )
    for key in renamed:
        suffix = "~" + key.rsplit("~")[1]
        assert key == plain[: KEY_LIMIT - len(suffix)] + suffix
    assert [key.rsplit("~")[1] for key in renamed] == [str(n) for n in range(3, 14)]


def test_short_keys_keep_their_suffix_uncut() -> None:
    """In canonical order: the second control-character key takes `~2` before the key literally
    named so is reached, which then collides in turn."""
    shown = "a" + REPLACEMENT
    bounded = bound_document({shown + "~2": 3, "a\x01": 2, "a\x00": 1})
    assert bounded == {shown: 1, shown + "~2": 2, shown + "~2~2": 3}
    assert TEXT_LIMIT > KEY_LIMIT
