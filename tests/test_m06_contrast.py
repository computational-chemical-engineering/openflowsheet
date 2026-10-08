"""M06 gate G9: the shell's colours are legible in both themes (design note §5.5).

`apps/web/css/tokens.css` holds the README token table (`docs/design/web-shell/README.md`) for
light and dark — the dark values twice, under `prefers-color-scheme` and under
`html[data-theme="dark"]`, which must agree. Contrast is WCAG 2.x's: relative luminance of the
sRGB values, (L1 + 0.05) / (L2 + 0.05). Every text token on every background token is at least
4.5:1 in both themes except `ink-3` on `select` in light, measured 4.39:1, which the selected-row
rule (`--ink-3: var(--ink-2)` on a selected row) never lets render; every pill's word on its fill
is at least 4.5:1. `app.css` sets text colours only from the text tokens (or a pill's fg) and
backgrounds only from the background tokens (or a pill's bg), so the pairs checked here are a
superset of the pairs the stylesheet can produce.
"""

from __future__ import annotations

import re

import pytest
from conftest import REPO_ROOT

TOKENS = REPO_ROOT / "apps" / "web" / "css" / "tokens.css"
APP = REPO_ROOT / "apps" / "web" / "css" / "app.css"
README = REPO_ROOT / "docs" / "design" / "web-shell" / "README.md"

TEXT = ("ink", "ink-2", "ink-3", "link", "ok", "info", "warn", "bad", "gap", "edu")
BACKGROUNDS = ("bg", "surface", "sunken", "select")
TONES = ("ok", "info", "warn", "bad", "none")
#: The one pair below 4.5:1, and the theme it is in (§5.5).
EXCEPTION = ("ink-3", "select", "light")

_DECLARATION = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6});")


def _block(text: str, opener: str) -> dict[str, str]:
    start = text.index(opener) + len(opener)
    end = text.index("}", start)
    return dict(_DECLARATION.findall(text[start:end]))


def _themes() -> dict[str, dict[str, str]]:
    text = TOKENS.read_text(encoding="utf-8")
    light = _block(text, ":root {")
    media = _block(text, ':root:not([data-theme="light"]) {')
    forced = _block(text, ':root[data-theme="dark"] {')
    assert media == forced, "the two dark blocks differ"
    return {"light": light, "dark": forced}


def _luminance(colour: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_the_tokens_are_the_readme_table() -> None:
    themes = _themes()
    readme = README.read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([a-z0-9-]+) \| `(#[0-9a-f]{6})` \| `(#[0-9a-f]{6})` \|$", readme, re.M)
    assert len(rows) == 16
    for name, light, dark in rows:
        assert (themes["light"][name], themes["dark"][name]) == (light, dark), name
    pills = {
        theme: dict(
            (tone, (fg, bg, border))
            for tone, fg, bg, border in re.findall(
                r"(ok|info|warn|bad|none) `(#[0-9a-f]{6})/(#[0-9a-f]{6})/(#[0-9a-f]{6})`",
                readme.split("Dark:")[index],
            )
        )
        for index, theme in enumerate(("light", "dark"))
    }
    for theme, tones in pills.items():
        assert sorted(tones) == sorted(TONES), theme
        for tone, colours in tones.items():
            found = tuple(themes[theme][f"pill-{tone}-{part}"] for part in ("fg", "bg", "border"))
            assert found == colours, (theme, tone)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_text_token_on_every_background_is_legible(theme: str) -> None:
    tokens = _themes()[theme]
    low = {
        (fg, bg): round(contrast(tokens[fg], tokens[bg]), 2)
        for fg in TEXT
        for bg in BACKGROUNDS
        if contrast(tokens[fg], tokens[bg]) < 4.5
    }
    expected = {EXCEPTION[:2]: 4.39} if theme == EXCEPTION[2] else {}
    assert low == expected


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_pill_word_is_legible_on_its_fill(theme: str) -> None:
    tokens = _themes()[theme]
    ratios = {
        tone: contrast(tokens[f"pill-{tone}-fg"], tokens[f"pill-{tone}-bg"]) for tone in TONES
    }
    assert min(ratios.values()) >= 4.5, ratios


def test_a_selected_row_never_shows_ink_3_on_select() -> None:
    css = TOKENS.read_text(encoding="utf-8")
    selected = r'\.selected,\s*\[aria-selected="true"\]\s*'
    rule = re.search(selected + r"\{\s*--ink-3:\s*var\(--ink-2\);", css)
    assert rule is not None
    assert contrast(_themes()["light"]["ink-2"], _themes()["light"]["select"]) >= 4.5


def test_app_css_draws_text_and_fills_only_from_checked_tokens() -> None:
    css = APP.read_text(encoding="utf-8")
    text_ok = {*TEXT, *(f"pill-{tone}-fg" for tone in TONES)}
    fill_ok = {*BACKGROUNDS, *(f"pill-{tone}-bg" for tone in TONES)}
    colours = re.findall(r"(?<![-a-z])color:\s*([^;]+);", css)
    fills = re.findall(r"background(?:-color)?:\s*([^;]+);", css)
    assert colours and fills
    for value in colours:
        assert re.fullmatch(r"var\(--([a-z0-9-]+)\)", value.strip()), value
        assert value.strip()[6:-1] in text_ok, value
    for value in fills:
        assert re.fullmatch(r"var\(--([a-z0-9-]+)\)", value.strip()), value
        assert value.strip()[6:-1] in fill_ok, value
    # No colour literal anywhere in a declaration: every colour is a token.
    assert re.findall(r":[^;{}]*#[0-9a-fA-F]{3,8}\b[^;{}]*;", css) == []
