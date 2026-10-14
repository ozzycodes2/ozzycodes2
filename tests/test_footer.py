"""Tests for the closing slice."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import footer

# `.ink .dim .accent` for fill, the five type steps, `.ln .cursor .dot` for
# motion. Everything else went with the two retired palettes.
LIVE = {"ink", "dim", "accent", "display", "heading", "body", "caption", "mono",
        "ln", "cursor", "dot"}

STAMPED = {"stats": {"updated": "2026-10-12"}}


@pytest.fixture(scope="module")
def markup():
    return footer.render({}, STAMPED, c.LIGHT)


def dim(markup):
    return int(re.search(r'height="(\d+)"', markup).group(1))


def painted(markup):
    """The text the slice draws, with the inline stylesheet excluded.

    `console.visible` keeps the CSS, which sits between tags rather than inside
    one, so an equality check on the drawn text has to drop it first.
    """
    return c.visible(markup.split("</style>", 1)[-1])


def test_it_closes_the_frame(markup):
    """Only the footer draws a bottom edge, so the window reads as one object."""
    height = dim(markup)
    assert f"M{c.MARGIN} {height - c.MARGIN - c.R_CARD}V0" in markup
    assert f"H{c.FRAME_L + c.R_CARD}" in markup


def test_it_stays_short(markup):
    assert dim(markup) <= 160
    assert dim(markup) % c.ROW == 0


def test_the_prompt_blinks(markup):
    assert "❯" in markup
    assert 'class="ink cursor" dx="10">▌<' in markup  # the shared class, so reduced-motion wins
    assert "prefers-reduced-motion" in markup
    assert "█" not in markup


def test_the_prompt_is_mono_and_dim(markup):
    assert f'<text x="{c.TEXT_X}" y="48" class="mono dim">' in markup


def test_the_prompt_is_the_only_thing_drawn(markup):
    assert len(re.findall(r"<text", markup)) == 1
    assert painted(markup).strip() == "❯exit▌"


def test_no_date_reaches_the_slice(markup):
    """The stamp went with the credit: a date in the frame dated the whole
    README, and the one it printed was the previous run's, not this one's."""
    assert "2026-10-12" not in markup
    assert not re.search(r"\d{4}-\d{2}-\d{2}", painted(markup))


def test_desc_repeats_what_is_drawn(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    assert desc == "Closing prompt: exit."


@pytest.mark.parametrize("data", [{}, {"stats": {}}, {"stats": None}, STAMPED])
def test_neither_argument_reaches_the_footer(data):
    """Both `cfg` and `data` are unused and underscored — the slice is fixed."""
    assert footer.render({"identity": {"name": "x"}}, data, c.LIGHT) == \
        footer.render({}, {}, c.LIGHT)


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_every_fill_comes_off_the_theme(theme):
    out = footer.render({}, STAMPED, theme)
    assert f".ink{{fill:{theme.ink}}}.dim{{fill:{theme.dim}}}" in out
    assert f'fill="{theme.canvas}"' in out
    assert f'stroke="{theme.hairline}"' in out
    assert f'fill="{theme.accent}"' not in out   # accent is state, not chrome


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_it_names_only_classes_the_new_systems_keep(theme):
    out = footer.render({}, STAMPED, theme)
    used = {token for value in re.findall(r'class="([^"]*)"', out)
            for token in value.split()}
    assert used <= LIVE, used - LIVE
    for gone in ("glow", "soft", "grid"):
        assert f"url(#{gone})" not in out


def test_the_two_themes_differ_in_nothing_but_colour(markup):
    """readme.py pairs them in one <picture> under a single alt text."""
    dark = footer.render({}, STAMPED, c.DARK)
    assert dim(dark) == dim(markup)
    assert painted(dark) == painted(markup)
    assert dark != markup
