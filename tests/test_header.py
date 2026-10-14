"""Tests for the top slice."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import header

CFG = {"identity": {
    "name": "Osniel Quintana",
    "handle": "ozzycodes2",
    "role": "platform engineer",
    "tagline": ["first line", "second line", "third line"],
}}

# `.ink .dim .accent` for fill, the five type steps, `.ln .cursor .dot` for
# motion. Anything outside this set is a class one of the retired palettes
# used to define, and a panel that still names one renders unstyled rather
# than failing loudly.
LIVE = {"ink", "dim", "accent", "display", "heading", "body", "caption", "mono",
        "ln", "cursor", "dot"}


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def texts(svg):
    """(class list, content) of every text element, in draw order."""
    return re.findall(r'<text[^>]*class="([^"]*)"[^>]*>(.*?)</text>', svg, re.S)


def classes(svg):
    """Every class token the slice names anywhere."""
    return {token for value in re.findall(r'class="([^"]*)"', svg)
            for token in value.split()}


# --- frame -----------------------------------------------------------------

def test_header_is_the_slice_that_closes_the_top():
    """Only this panel draws the top edge; the rest continue the rails."""
    svg = header.render(CFG, {}, c.LIGHT)
    assert f"M{c.FRAME_L} {height_of(svg)}V{c.MARGIN + c.R_CARD}" in svg
    assert f"H{c.FRAME_R - c.R_CARD}" in svg


def test_header_draws_the_window_title_bar():
    svg = header.render(CFG, {}, c.LIGHT)
    assert re.search(rf'<text x="{c.W // 2}"[^>]*>ozzycodes2</text>', svg)
    assert svg.count("<circle") == 3       # three hairline rings, no traffic lights


def test_header_height_is_on_the_grid():
    assert height_of(header.render(CFG, {}, c.LIGHT)) % c.ROW == 0


def test_header_grows_with_the_tagline():
    short = dict(identity={**CFG["identity"], "tagline": ["one"]})
    long = dict(identity={**CFG["identity"], "tagline": ["one"] * 6})
    assert height_of(header.render(long, {}, c.LIGHT)) > \
        height_of(header.render(short, {}, c.LIGHT))


def test_header_sets_every_line_from_the_text_column():
    """The one exception is the window title, centred in its own chrome."""
    svg = header.render(CFG, {}, c.LIGHT)
    xs = {int(v) for v in re.findall(r'<text x="(\d+)"', svg)}
    assert xs == {c.TEXT_X, c.W // 2}
    assert max(xs) <= c.CONTENT_R


def test_header_renders_every_tagline_line():
    svg = header.render(CFG, {}, c.LIGHT)
    for line in CFG["identity"]["tagline"]:
        assert line in svg


# --- type ------------------------------------------------------------------

def test_the_name_is_one_text_at_the_shared_display_step():
    """It used to be a glow and a fill drawn over each other at 38px."""
    svg = header.render(CFG, {}, c.LIGHT)
    drawn = [(cls, body) for cls, body in texts(svg) if "Osniel Quintana" in body]
    assert drawn == [("display ink", "Osniel Quintana")]
    assert f"font-size:{c.DISPLAY.size}px" in svg


def test_the_handle_and_role_share_one_mono_line():
    svg = header.render(CFG, {}, c.LIGHT)
    cls, body = next((cls, body) for cls, body in texts(svg)
                     if "ozzycodes2" in body and "·" in body)
    assert cls == "mono"
    assert "platform engineer" in body


def test_the_tagline_is_set_at_the_body_step():
    svg = header.render(CFG, {}, c.LIGHT)
    for line in CFG["identity"]["tagline"]:
        assert f'class="body dim">{line}</text>' in svg


def test_the_prompt_is_dim_and_the_cursor_is_a_half_block():
    svg = header.render(CFG, {}, c.LIGHT)
    assert f'<text x="{c.TEXT_X}" y="96" class="mono dim"><tspan>❯</tspan>' in svg
    assert "▌" in svg and "█" not in svg


# --- motion ----------------------------------------------------------------

def test_header_blinks_a_cursor_via_the_shared_class():
    """Inline animation shorthand would escape the reduced-motion override."""
    svg = header.render(CFG, {}, c.LIGHT)
    assert 'class="ink cursor" dx="10">▌<' in svg
    assert "prefers-reduced-motion" in svg


def test_header_staggers_its_rows_so_they_arrive_one_after_another():
    svg = header.render(CFG, {}, c.LIGHT)
    delays = [float(d) for d in
              re.findall(r'class="ln" style="animation-delay:([\d.]+)s"', svg)]
    # prompt, name, handle/role, one per tagline line, then the live cursor.
    assert len(delays) == 3 + len(CFG["identity"]["tagline"]) + 1
    assert delays == sorted(delays)
    assert len(set(delays)) == len(delays)


# --- colour ----------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_header_takes_every_fill_from_the_theme(theme):
    svg = header.render(CFG, {}, theme)
    assert f".ink{{fill:{theme.ink}}}.dim{{fill:{theme.dim}}}" in svg
    assert f'fill="{theme.canvas}"' in svg
    assert f'fill="{theme.surface}"' in svg
    assert f'stroke="{theme.hairline}"' in svg
    assert f'fill="{theme.accent}"' not in svg   # accent is state, not chrome


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_header_names_only_classes_the_new_systems_keep(theme):
    svg = header.render(CFG, {}, theme)
    assert classes(svg) <= LIVE, classes(svg) - LIVE
    for gone in ("glow", "soft", "grid"):
        assert f"url(#{gone})" not in svg


def test_the_two_themes_differ_in_nothing_but_colour():
    """readme.py pairs them in one <picture> under a single alt text."""
    light, dark = (header.render(CFG, {}, theme) for theme in c.THEMES)
    assert height_of(light) == height_of(dark)
    assert desc_of(light) == desc_of(dark)
    assert light != dark


# --- accessibility and degrading -------------------------------------------

def test_header_description_carries_name_role_and_tagline():
    desc = desc_of(header.render(CFG, {}, c.LIGHT))
    assert "Osniel Quintana" in desc
    assert "platform engineer" in desc
    assert "third line" in desc


def test_header_escapes_markup_in_the_name():
    cfg = {"identity": {**CFG["identity"], "name": 'A <b>& "B"'}}
    svg = header.render(cfg, {}, c.LIGHT)
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_header_with_an_empty_tagline():
    cfg = {"identity": {**CFG["identity"], "tagline": []}}
    svg = header.render(cfg, {}, c.LIGHT)
    assert height_of(svg) % c.ROW == 0


def test_header_is_deterministic():
    assert header.render(CFG, {}, c.LIGHT) == header.render(CFG, {}, c.LIGHT)


def test_header_ignores_fetched_data():
    """The headline is hand-written; nothing in data/ should reach it."""
    assert header.render(CFG, {}, c.LIGHT) == \
        header.render(CFG, {"stats": {"followers": 9000}}, c.LIGHT)
