"""Tests for the closing slice."""
import re

import pytest

from tools.profile.present import console as c
from tools.profile.present.panels import footer


def painted(markup):
    """The text the slice draws, with the inline stylesheet excluded.

    `console.visible` keeps the CSS, which sits between tags rather than inside
    one, so an equality check on the drawn text has to drop it first.
    """
    return c.visible(markup.split("</style>", 1)[-1])


@pytest.fixture(scope="module")
def out():
    return footer.render({}, {}, c.LIGHT)


def test_the_slice_is_a_whole_number_of_grid_rows(out):
    assert footer.HEIGHT % c.ROW == 0
    assert f'height="{footer.HEIGHT}"' in out


def test_it_closes_the_frame(out):
    """Last slice: the rails stop here and the corners round off."""
    assert f'M{c.FRAME_L} ' in out and f"a{c.R_CARD} {c.R_CARD}" in out


def test_the_prompt_is_the_only_text(out):
    """No spaces in the drawn string: the parts are spaced with dx, not words."""
    assert painted(out).strip() == "❯exit▌"


def test_the_prompt_is_mono_at_the_footer_size(out):
    assert f'font-family="{c.e(c.MONO_STACK)}" font-size="12"' in out


def test_the_three_parts_step_up_the_ink_tiers(out):
    """The glyph is chrome, the command is prose, the cursor is the live edge."""
    fills = re.findall(r'<tspan fill="([^"]*)"', out)
    assert fills == [c.LIGHT.faint, c.LIGHT.dim, c.LIGHT.ink]


def test_nothing_is_drawn_under_the_prompt(out):
    """A band mirroring the title bar reads as an empty row below `exit`: the
    preview sets a second line of metadata inside that band and this footer has
    no second line."""
    assert c.LIGHT.surface not in out.split("</style>", 1)[-1]
    assert footer.HEIGHT == 2 * c.ROW


def test_the_dark_closing_band_would_dissolve_into_githubs_own_page():
    """The other half of the reason, and the one a reader cannot see locally.
    GitHub's dark canvas is #0d1117; `surface` sits 1.01:1 from it, so a band of
    it at the foot is not a quiet strip but a hole — the window's bottom 44px
    disappear and the side edges appear to stop above their own corners. The
    canvas the rest of the window is painted in clears that by an order more."""
    page = "#0d1117"
    assert c.contrast(c.DARK.surface, page) < 1.02
    assert c.contrast(c.DARK.canvas, page) > 1.09


def test_the_prompt_sits_one_row_above_the_edge_the_frame_closes_on(out):
    """It is the last thing in the window, so it needs clearance beneath it as
    well as the gutter the frame already leaves outside itself."""
    assert f'y="{footer.PROMPT_Y}"' in out
    assert footer.HEIGHT - c.MARGIN - footer.PROMPT_Y >= c.MARGIN


def test_nothing_animates(out):
    """A rendered SVG is a still at frame zero; the footer has no live state."""
    assert "animation" not in out.split("</style>", 1)[-1]
    assert 'class="live"' not in out


def test_no_accent_is_spent_here(out):
    """The footer closes the frame rather than opening a section, so it draws no
    heading — and it reports no quantity, so it has nothing to mark."""
    assert c.LIGHT.accent not in out


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_both_themes_draw_the_same_prompt(theme):
    markup = footer.render({}, {}, theme)
    assert painted(markup) == painted(footer.render({}, {}, c.LIGHT))
    assert f'fill="{theme.canvas}"' in markup
    assert f'stroke="{theme.hairline}"' in markup


def test_desc_says_what_the_slice_is(out):
    assert re.search(r'<desc id="d">Closing prompt: exit\.</desc>', out)
