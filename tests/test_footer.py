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


def credit_line(markup):
    return re.search(r'text-anchor="middle" class="caption dim">([^<]*)</text>',
                     markup).group(1)


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


def test_the_credit_is_set_at_the_caption_step(markup):
    assert f"font-size:{c.CAPTION.size}px" in markup
    assert credit_line(markup)


def test_the_credit_stays_inside_the_content_column(markup):
    """It is centred, so it has to be measured outward from the middle, with
    the same pessimistic sans advance the project blurbs wrap by."""
    half = len(credit_line(markup)) * c.CAPTION.size * 0.62 / 2
    assert c.W // 2 - half >= c.TEXT_X
    assert c.W // 2 + half <= c.CONTENT_R


def test_it_credits_the_generator_and_dates_the_run(markup):
    text = c.visible(markup)
    assert "self" in text or "scheduled job" in text
    assert "2026-10-12" in text


def test_desc_repeats_what_is_drawn(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    assert "exit" in desc and "2026-10-12" in desc


def test_nothing_hand_written_reaches_the_footer(markup):
    """`cfg` is unused and underscored; only the run stamp varies."""
    assert footer.render({"identity": {"name": "x"}}, STAMPED, c.LIGHT) == markup


@pytest.mark.parametrize("data", [{}, {"stats": {}}, {"stats": None}])
def test_a_missing_timestamp_does_not_print_none(data):
    out = footer.render({}, data, c.LIGHT)
    assert "None" not in c.visible(out)
    assert "unknown" in c.visible(out)
    assert dim(out) % c.ROW == 0


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
    assert credit_line(dark) == credit_line(markup)
    assert dark != markup
