"""Tests for the top slice.

Every fill, size and weight in this panel is a presentation attribute on the
element that needs it, so the assertions read attributes rather than classes:
there is no stylesheet left to check against.
"""
import re

import pytest
from fontTools.ttLib import TTFont

from tools.profile.present import console as c
from tools.profile.present import fonts
from tools.profile.present.panels import header

CFG = {"identity": {
    "name": "Osniel Quintana",
    "handle": "ozzycodes2",
    "role": "platform engineer",
    "tagline": ["first line", "second line", "third line", "fourth line"],
}}

DATA = {"stats": {"streak_current": 3}}

SANS = c.e(c.SANS_STACK)
MONO = c.e(c.MONO_STACK)


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def elements(svg, tag):
    """Every `tag` element's attributes, as dicts, in draw order."""
    return [dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
            for attrs in re.findall(rf"<{tag}\s([^>]*?)/?>", svg)]


def texts(svg):
    """(attributes, content) of every <text>, in draw order."""
    return [(dict(re.findall(r'([\w-]+)="([^"]*)"', attrs)), body)
            for attrs, body in re.findall(r"<text\s([^>]*)>(.*?)</text>", svg, re.S)]


def one(svg, needle):
    """The single <text> whose content contains `needle`."""
    found = [attrs for attrs, body in texts(svg) if needle in body]
    assert len(found) == 1, f"{needle!r} drawn {len(found)} times"
    return found[0]


def render(cfg=CFG, data=DATA, theme=c.LIGHT):
    return header.render(cfg, data, theme)


def geometry(svg, theme):
    """The slice with every theme colour replaced by the role that supplied it.

    What is left is the drawing: coordinates, sizes, weights and anchors. Two
    themes that agree on this differ in nothing but colour.
    """
    for role, value in zip(theme._fields, theme):
        if role != "name":
            svg = svg.replace(value, role)
    return svg


# --- frame -----------------------------------------------------------------

def test_header_caps_the_top_of_the_frame():
    """Only this panel passes top=True; the rest continue the rails."""
    svg = render()
    assert f"M{c.FRAME_L + c.R_CARD} {c.MARGIN}H{c.FRAME_R - c.R_CARD}" in svg
    assert f"V{height_of(svg)}H{c.FRAME_L}" in svg


def test_header_height_is_on_the_grid():
    """slice_svg refuses an off-grid height, so the stack cannot step."""
    assert height_of(render()) % c.ROW == 0


def test_header_is_the_reference_280_tall_for_a_four_line_tagline():
    """The shipped tagline is four lines; the reference slice is 280px."""
    assert height_of(render()) == 280


def test_header_draws_the_chrome_once_titled_for_the_handle():
    """title_bar supplies the band, the three rings and the rule together."""
    svg = render()
    attrs = one(svg, "zsh")
    assert attrs["x"] == str(c.W // 2)
    assert attrs["text-anchor"] == "middle"
    assert attrs["font-family"] == MONO
    assert attrs["font-size"] == "12"
    assert attrs["fill"] == c.LIGHT.faint
    assert [e["r"] for e in elements(svg, "circle")[:3]] == ["5"] * 3


# --- type --------------------------------------------------------------------

def test_the_name_is_the_one_display_size_element():
    """30/600 sans with -0.5 tracking: the only element off the label scale."""
    attrs = one(render(), "Osniel Quintana")
    assert attrs["x"] == str(c.TEXT_X)
    assert attrs["y"] == str(header.NAME_Y)
    assert attrs["font-family"] == SANS
    assert attrs["font-size"] == "30"
    assert attrs["font-weight"] == "600"
    assert attrs["letter-spacing"] == "-0.5"
    assert attrs["fill"] == c.LIGHT.ink


def test_the_handle_and_role_share_one_mono_line():
    """One <text>, not three tspans: the whole run is the same tier."""
    attrs, body = next((a, b) for a, b in texts(render()) if "@ozzycodes2" in b)
    assert body == "@ozzycodes2 · platform engineer"
    assert attrs["x"] == str(c.TEXT_X)
    assert attrs["y"] == str(header.META_Y)
    assert attrs["font-family"] == MONO
    assert attrs["font-size"] == "13"
    assert attrs["fill"] == c.LIGHT.dim
    assert "font-weight" not in attrs


def test_the_streak_label_is_end_anchored_mono_in_the_ink():
    """It is a fact, not a caption, so it sits in the ink opposite the handle."""
    attrs = one(render(), "3-day streak")
    assert attrs["x"] == str(c.CONTENT_R)
    assert attrs["y"] == str(header.META_Y)
    assert attrs["text-anchor"] == "end"
    assert attrs["font-family"] == MONO
    assert attrs["font-size"] == "13"
    assert attrs["fill"] == c.LIGHT.ink


def test_the_tagline_steps_22px_in_the_sans_body_size():
    """Four lines at 15px, indented past their markers."""
    drawn = [(a, b) for a, b in texts(render()) if b.endswith(" line")]
    assert [b for _, b in drawn] == CFG["identity"]["tagline"]
    for i, (attrs, _) in enumerate(drawn):
        assert attrs["x"] == str(header.BULLET_X)
        assert attrs["y"] == str(header.TAGLINE_Y + i * header.LINE_H)
        assert attrs["font-family"] == SANS
        assert attrs["font-size"] == "15"
        assert attrs["fill"] == c.LIGHT.dim
        assert "font-weight" not in attrs


def test_each_tagline_line_carries_its_own_marker():
    """The list reads as output of the command above it, one claim per line."""
    marks = [a for a, b in texts(render()) if b == header.BULLET]
    assert len(marks) == len(CFG["identity"]["tagline"])
    for i, attrs in enumerate(marks):
        assert attrs["x"] == str(c.TEXT_X)
        assert attrs["y"] == str(header.TAGLINE_Y + i * header.LINE_H)
        assert attrs["font-family"] == MONO
        assert attrs["fill"] == c.LIGHT.faint


@pytest.mark.parametrize("stem", [s for _, s, _ in fonts.FACES if s.startswith("jet")])
def test_the_marker_is_a_glyph_the_vendored_monospace_carries(stem):
    """A marker on every line must not fall through to a substitute face."""
    assert header.BULLET in c.visible(render())
    cmap = TTFont(fonts.FONT_DIR / f"{stem}.woff2").getBestCmap()
    assert ord(header.BULLET) in cmap


def test_the_slice_opens_on_the_command_it_answers():
    """Same transcript voice the sections below it keep: `$`, then the command."""
    svg = render()
    assert one(svg, "whoami")["x"] == str(c.TEXT_X + 14)
    assert one(svg, "whoami")["y"] == str(header.CMD_Y)
    assert one(svg, "whoami")["font-family"] == MONO
    assert one(svg, "whoami")["font-size"] == "12"
    assert one(svg, "$")["x"] == str(c.TEXT_X)
    assert one(svg, "$")["fill"] == c.LIGHT.faint


def test_every_run_stays_inside_the_content_column():
    """TEXT_X for body copy and markers, CONTENT_R for the one end-anchored run."""
    xs = {int(a["x"]) for a, _ in texts(render())}
    assert xs == {c.TEXT_X, c.TEXT_X + 14, header.BULLET_X, c.W // 2, c.CONTENT_R}


def test_header_caps_the_tagline_at_four_lines():
    """A fifth line would push past the reference slice's own height."""
    cfg = {"identity": {**CFG["identity"], "tagline": [f"line {i}" for i in range(7)]}}
    svg = header.render(cfg, DATA, c.LIGHT)
    assert len([b for _, b in texts(svg) if b.startswith("line ")]) == 4
    assert "line 4" not in svg


# --- the live dot ------------------------------------------------------------

def test_the_live_dot_sits_one_label_width_in_from_the_right():
    """Mono advances 0.6em, so the end-anchored label's own left edge is known."""
    svg = render()
    dot = elements(svg, "circle")[-1]
    width = round(len("3-day streak") * 13 * c.MONO_ADVANCE)
    assert dot["cx"] == str(c.CONTENT_R - width - 12)
    assert dot["cy"] == str(header.META_Y - 5)
    assert dot["r"] == "4"
    assert dot["class"] == "live"


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_accent_marks_the_live_dot_and_nothing_else_here(theme):
    """The streak is this panel's one datum worth pointing at. The header draws
    no section heading, so the dot is the only accent in the slice."""
    svg = header.render(CFG, DATA, theme)
    assert svg.count(theme.accent) == 1
    assert f'class="live" cx="722" cy="141" r="4" fill="{theme.accent}"' in svg


def test_the_dot_pulses_through_the_shared_class():
    """Inline animation shorthand would escape the reduced-motion override."""
    svg = render()
    assert ".live{animation:pulse" in svg
    assert "prefers-reduced-motion" in svg
    assert "animation:" not in re.sub(r"<style>.*?</style>", "", svg, flags=re.S)


def test_header_without_a_streak_drops_the_dot_and_the_label():
    """data/ may be empty on a first run; the headline still has to render."""
    svg = header.render(CFG, {}, c.LIGHT)
    assert svg.count("<circle") == 3          # the chrome rings only
    assert "streak" not in svg
    assert c.LIGHT.accent not in svg
    assert "Osniel Quintana" in svg


# --- what the reference does not draw ----------------------------------------

def test_header_draws_no_live_prompt_and_no_cursor():
    """`$` quotes a command; `❯ … ▌` is the live prompt and closes the window.

    The footer draws that one, once. A second cursor in the header would make
    the window look like two sessions.
    """
    svg = render()
    assert "❯" not in svg
    assert "▌" not in svg


def test_header_has_no_fade_in_stagger():
    """GitHub paints a rendered SVG at frame zero, so a fade-in never arrives."""
    svg = render()
    assert "animation-delay" not in svg
    assert 'class="ln"' not in svg


# --- colour ------------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_header_takes_every_paint_from_the_theme(theme):
    svg = header.render(CFG, DATA, theme)
    assert f'fill="{theme.canvas}"' in svg                 # slice body
    assert f'fill="{theme.surface}"' in svg                # chrome band
    assert f'stroke="{theme.hairline}"' in svg             # rails and rule
    assert f'stroke="{theme.faint}"' in svg                # chrome rings
    assert not re.search(r'(fill|stroke)="#(?!'
                         + "|".join(v.lstrip("#") for v in theme[1:]) + r')',
                         svg)


def test_the_two_themes_differ_in_nothing_but_colour():
    """readme.py pairs them in one <picture> under a single alt text."""
    light, dark = (header.render(CFG, DATA, theme) for theme in c.THEMES)
    assert light != dark
    assert geometry(light, c.LIGHT) == geometry(dark, c.DARK)


# --- accessibility and degrading ----------------------------------------------

def test_the_description_names_the_values_it_draws():
    """It is the README's alt text, so it carries the facts, not the layout."""
    desc = desc_of(render())
    assert desc == ("Osniel Quintana (@ozzycodes2), platform engineer. "
                    "4 tagline lines. Current streak 3 days.")


def test_the_description_drops_the_streak_sentence_when_there_is_no_streak():
    assert desc_of(header.render(CFG, {}, c.LIGHT)).endswith("4 tagline lines.")


def test_header_escapes_markup_in_the_name():
    cfg = {"identity": {**CFG["identity"], "name": 'A <b>& "B"'}}
    svg = header.render(cfg, DATA, c.LIGHT)
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_header_with_an_empty_tagline_still_lands_on_the_grid():
    cfg = {"identity": {**CFG["identity"], "tagline": []}}
    svg = header.render(cfg, DATA, c.LIGHT)
    assert height_of(svg) % c.ROW == 0
    assert "0 tagline lines" in desc_of(svg)


def test_header_is_deterministic():
    """The daily job commits only when a byte changed, so renders must repeat."""
    assert render() == render()
