"""Tests for the link row, which is cut vertically so each tile gets an href."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import links

CFG = {"links": [
    {"icon": "github", "label": "GitHub", "url": "https://github.com/me"},
    {"icon": "linkedin", "label": "LinkedIn", "url": "https://linkedin.com/in/me"},
    {"icon": "mail", "label": "Email", "url": "mailto:me@example.com"},
]}


def by_file(cfg):
    out = links.render(cfg, {})
    return {s.file: s for s in out}


@pytest.fixture(scope="module")
def out():
    return by_file(CFG)


def tiles(out):
    return [s for f, s in out.items() if f != "links.svg"]


def attr(markup, name):
    return int(re.search(rf'{name}="(\d+)"', markup).group(1))


# --- file set --------------------------------------------------------------

def test_emits_a_heading_strip_plus_one_file_per_link(out):
    assert list(out) == ["links.svg", "links/github.svg",
                         "links/linkedin.svg", "links/mail.svg"]


def test_every_tile_carries_its_own_url(out):
    assert out["links/mail.svg"].href == "mailto:me@example.com"
    assert out["links.svg"].href is None


def test_no_slice_contains_an_anchor(out):
    """GitHub strips <a> from rendered SVG; the README wraps the <img>."""
    for slice_ in out.values():
        assert "<a " not in slice_.markup and "</a>" not in slice_.markup


def test_the_heading_strip_is_full_width_so_it_is_not_inside_a_link(out):
    assert attr(out["links.svg"].markup, "width") == c.W
    assert "links" in c.visible(out["links.svg"].markup)


# --- geometry --------------------------------------------------------------

def test_tile_widths_fill_the_window_exactly():
    for count in range(1, links.MAX_LINKS + 1):
        assert sum(links.tile_widths(count)) == c.W


def test_tile_widths_stay_on_the_grid_so_the_pattern_does_not_step():
    for count in range(1, links.MAX_LINKS + 1):
        assert all(w % c.ROW == 0 for w in links.tile_widths(count))


def test_leftover_cells_go_to_the_middle_so_the_row_is_symmetric():
    assert links.tile_widths(3) == [280, 320, 280]
    assert links.tile_widths(4) == [200, 240, 240, 200]


def test_more_links_than_can_be_laid_out_is_reported_not_drawn():
    with pytest.raises(ValueError, match="will not tile"):
        links.tile_widths(links.MAX_LINKS + 1)


def test_only_the_outer_tiles_draw_a_rail(out):
    first, middle, last = (s.markup for s in tiles(out))
    # A rail is inset by MARGIN; a flush edge starts the background at zero.
    assert f'<rect x="{c.MARGIN}"' in first
    assert '<rect x="0"' in middle
    assert '<rect x="0"' in last
    # The middle slice paints no vertical edge at all.
    assert re.search(r'<path d=""', middle)


def test_a_single_link_keeps_both_rails():
    out = by_file({"links": [CFG["links"][0]]})
    markup = out["links/github.svg"].markup
    assert attr(markup, "width") == c.W
    assert f'M{c.FRAME_R} 0V' in markup


def test_every_tile_is_the_same_height_and_on_the_grid(out):
    heights = {attr(s.markup, "height") for s in tiles(out)}
    assert heights == {links.ROW_H}
    assert links.ROW_H % c.ROW == 0 and links.HEAD_H % c.ROW == 0


def test_tiles_are_identically_sized_and_evenly_spaced(out):
    """Boxes are centred in their own slice, so the row reads as a grid."""
    widths, boxes = links.tile_widths(3), []
    left = 0
    for width, slice_ in zip(widths, tiles(out)):
        x = float(re.search(r'<rect x="([\d.]+)" y="16"', slice_.markup).group(1))
        w = float(re.search(r'y="16" width="([\d.]+)"', slice_.markup).group(1))
        boxes.append((left + x, w))
        left += width
    assert {w for _, w in boxes} == {float(links.TILE_W)}
    starts = [x for x, _ in boxes]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert len(set(gaps)) == 1
    # Symmetric inside the frame: same margin from each rail.
    assert round(starts[0] - c.FRAME_L, 1) == round(c.FRAME_R - (starts[-1] + links.TILE_W), 1)


def test_a_label_too_wide_for_its_tile_is_truncated_not_overflowed():
    out = by_file({"links": [
        {"icon": "github", "label": "x" * 40, "url": "u"},
        {"icon": "mail", "label": "Email", "url": "u"},
        {"icon": "rss", "label": "Feed", "url": "u"},
        {"icon": "globe", "label": "Site", "url": "u"},
        {"icon": "x", "label": "X", "url": "u"},
        {"icon": "bluesky", "label": "Bluesky", "url": "u"},
        {"icon": "mastodon", "label": "Mastodon", "url": "u"},
    ]})
    shown = re.search(r'font-size:12px">([^<]*)</text>', out["links/github.svg"].markup).group(1)
    assert shown.endswith("…")
    tile_w = min(links.TILE_W, min(links.tile_widths(7)) - 36)
    assert len(shown) * links.LABEL_CHAR <= tile_w


# --- icons -----------------------------------------------------------------

def test_the_icon_sheet_covers_every_key_a_profile_can_ask_for():
    keys = {k for k in links.ICONS if not k.startswith("_")}
    assert {"github", "linkedin", "mail", "x", "bluesky",
            "mastodon", "rss", "globe"} <= keys


def test_every_icon_is_one_path_sized_for_a_24_box():
    for key, d in links.ICONS.items():
        if key.startswith("_"):
            continue
        assert isinstance(d, str) and d.startswith("M")
        numbers = [abs(float(n)) for n in re.findall(r"-?\d*\.?\d+", d)]
        assert max(numbers) <= 24, key


def test_an_unknown_icon_falls_back_to_the_globe():
    out = by_file({"links": [{"icon": "nope", "label": "Site", "url": "u"}]})
    assert links.ICONS["globe"] in out["links/nope.svg"].markup


# --- accessibility and degrading -------------------------------------------

def test_desc_names_each_link_and_its_target(out):
    desc = re.search(r"<desc id=\"d\">([^<]*)</desc>", out["links/github.svg"].markup).group(1)
    assert "GitHub" in desc and "https://github.com/me" in desc
    strip = re.search(r"<desc id=\"d\">([^<]*)</desc>", out["links.svg"].markup).group(1)
    assert "GitHub" in strip and "LinkedIn" in strip and "Email" in strip


@pytest.mark.parametrize("cfg", [{}, {"links": []}])
def test_no_links_renders_one_short_panel_instead_of_raising(cfg):
    out = by_file(cfg)
    assert list(out) == ["links.svg"]
    assert "No links are configured." in out["links.svg"].markup
    assert attr(out["links.svg"].markup, "height") % c.ROW == 0


def test_the_panel_never_closes_the_frame(out):
    """Only header and footer draw a horizontal edge; links sits between them."""
    for slice_ in out.values():
        edges = re.search(r'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="1.2"',
                          slice_.markup).group(1)
        assert "H" not in edges
