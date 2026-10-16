"""Tests for the closing slice."""
import re

import pytest

from tools.profile.present import console as c
from tools.profile.present.panels import footer

CFG = {"identity": {"handle": "ozzycodes2"}}


def painted(markup):
    """The text the slice draws, with the inline stylesheet excluded.

    `console.visible` keeps the CSS, which sits between tags rather than inside
    one, so an equality check on the drawn text has to drop it first.
    """
    return c.visible(markup.split("</style>", 1)[-1])


@pytest.fixture(scope="module")
def out():
    return footer.render(CFG, {}, c.LIGHT)


def test_the_slice_is_a_whole_number_of_grid_rows(out):
    assert footer.HEIGHT % c.ROW == 0
    assert f'height="{footer.HEIGHT}"' in out


def test_it_closes_the_frame(out):
    """Last slice: the rails stop here and the corners round off."""
    assert f'M{c.FRAME_L} ' in out and f"a{c.R_CARD} {c.R_CARD}" in out


def test_the_session_ends_on_a_command_and_what_it_printed(out):
    """No spaces in the prompt's own string: `$` and `exit` are spaced with dx,
    not with a word, so the two tiers stay separate elements."""
    assert [ln for ln in painted(out).split("\n") if ln] == [
        "$exit", "connection to ozzycodes2 closed. //EOF"]


def test_both_lines_are_mono_at_the_size_every_quoted_command_uses(out):
    """The sign-off is shell output, so it is set like the `$ …` transcripts
    under the section headings rather than like the prose in the header."""
    sized = re.findall(r'font-family="([^"]*)" font-size="(\d+)"', out)
    assert sized == [(c.e(c.MONO_STACK), "12")] * 2


def test_the_prompt_steps_up_the_ink_tiers(out):
    """The prompt is chrome, the command is what was typed."""
    fills = re.findall(r'<tspan fill="([^"]*)"', out)
    assert fills == [c.LIGHT.faint, c.LIGHT.dim]


def test_the_closing_line_is_the_quietest_tier_in_the_window(out):
    """It is the shell answering, not the author: below the command it follows.
    """
    line = re.search(r'<text x="\d+" y="(\d+)" fill="([^"]*)"', out)
    assert line.group(1) == str(footer.CLOSE_Y)
    assert line.group(2) == c.LIGHT.faint


def test_the_closing_line_names_the_account_it_closes(out):
    """A hardcoded handle would be wrong for anyone who forked this."""
    other = footer.render({"identity": {"handle": "someone-else"}}, {}, c.LIGHT)
    assert "connection to someone-else closed." in painted(other)


@pytest.mark.parametrize("cfg", [{}, {"identity": None}, {"identity": {}}])
def test_an_unconfigured_handle_shortens_the_line_rather_than_breaking_it(cfg):
    """Rule 10: a missing cfg key drops the clause, it does not raise."""
    markup = footer.render(cfg, {}, c.LIGHT)
    assert "connection closed. //EOF" in painted(markup)
    assert "None" not in painted(markup)


def test_the_prompt_is_the_same_glyph_every_section_heading_quotes(out):
    """`$` is in the subset both vendored monospaces carry; `❯` is not, so the
    window no longer asks a fallback face for the one glyph that closes it."""
    assert "❯" not in out
    assert "▌" not in out


def test_nothing_is_drawn_under_the_sign_off(out):
    """A band mirroring the title bar reads as an empty row below the text: the
    preview sets a second line of metadata inside that band and this footer has
    none to put there."""
    assert c.LIGHT.surface not in out.split("</style>", 1)[-1]


def test_the_dark_closing_band_would_dissolve_into_githubs_own_page():
    """The other half of the reason, and the one a reader cannot see locally.
    GitHub's dark canvas is #0d1117; `surface` sits 1.01:1 from it, so a band of
    it at the foot is not a quiet strip but a hole — the window's bottom 44px
    disappear and the side edges appear to stop above their own corners. The
    canvas the rest of the window is painted in clears that by an order more."""
    page = "#0d1117"
    assert c.contrast(c.DARK.surface, page) < 1.02
    assert c.contrast(c.DARK.canvas, page) > 1.09


def test_the_sign_off_keeps_its_clearance_above_the_edge_the_frame_closes_on(out):
    """It is the last thing in the window, so it needs clearance beneath it as
    well as the gutter the frame already leaves outside itself."""
    assert f'y="{footer.PROMPT_Y}"' in out
    assert footer.CLOSE_Y - footer.PROMPT_Y == 22
    assert footer.HEIGHT - c.MARGIN - footer.CLOSE_Y >= c.MARGIN


def test_nothing_animates(out):
    """A rendered SVG is a still at frame zero; the footer has no live state."""
    assert "animation" not in out.split("</style>", 1)[-1]
    assert 'class="live"' not in out


def test_no_accent_is_spent_here(out):
    """The footer closes the frame rather than opening a section, so it draws no
    heading — and it reports no quantity, so it has nothing to mark."""
    assert c.LIGHT.accent not in out


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_both_themes_draw_the_same_sign_off(theme):
    markup = footer.render(CFG, {}, theme)
    assert painted(markup) == painted(footer.render(CFG, {}, c.LIGHT))
    assert f'fill="{theme.canvas}"' in markup
    assert f'stroke="{theme.hairline}"' in markup


def test_desc_spells_out_the_line_the_slice_draws(out):
    assert re.search(r'<desc id="d">Closing prompt: exit\. '
                     r'Connection to ozzycodes2 closed\. //EOF</desc>', out)
