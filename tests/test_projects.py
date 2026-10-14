"""Tests for the project cards, which are the only panel emitting many files."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import projects

CFG = {"projects": [
    {"repo": "me/one", "name": "one", "blurb": "Short one.", "tags": ["Go", "CLI"]},
    {"repo": "me/two", "name": "two", "tags": ["Rust"],
     "blurb": " ".join(["word"] * 60)},
    {"repo": "me/three", "name": "three", "blurb": "Third.", "tags": []},
    {"repo": "me/four", "name": "four", "blurb": "Fourth.", "tags": ["C"]},
]}
DATA = {"projects": [
    {"repo": "me/one", "language": "Go", "stars": 0, "pushed_at": "2026-08-01T00:00:00Z"},
    {"repo": "me/two", "language": "Rust", "stars": 0, "pushed_at": "2019-01-01T00:00:00Z"},
    {"repo": "me/three", "language": "Zig", "stars": 0, "pushed_at": None},
]}

# `.ink .dim .accent` for fill, the five type steps, `.ln .cursor .dot` for
# motion. Everything else went with the two retired palettes.
LIVE = {"ink", "dim", "accent", "display", "heading", "body", "caption", "mono",
        "ln", "cursor", "dot"}

INNER = projects.CARD_W - 2 * projects.PAD


def by_file(cfg, data, theme=c.LIGHT):
    """The panel's slices, keyed by filename for readability."""
    return {s.file: s for s in projects.render(cfg, data, theme)}


@pytest.fixture(scope="module")
def out():
    return by_file(CFG, DATA)


def cards(out):
    return [out[f"projects-{i}.svg"].markup for i in range(1, 5)]


def attr(markup, name):
    return re.search(rf'{name}="(-?\d+)"', markup).group(1)


def card_box(markup):
    """(x, y, width, height) of the card itself, in its own slice's coordinates."""
    m = re.search(r'<rect x="(-?\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', markup)
    return tuple(int(v) for v in m.groups())


def rail(markup):
    """The slice's frame path: one vertical, on the card's outer edge."""
    return re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]*" '
                     rf'stroke-width="{c.EDGE_W}"', markup).group(1)


def canvas(markup, theme=c.LIGHT):
    """(left, right) x of the slice background, which meets its neighbour."""
    d = re.search(rf'<path d="([^"]*)" fill="{theme.canvas}"/>', markup).group(1)
    m = re.match(r"M(-?\d+) \d+H(-?\d+)", d)
    return int(m.group(1)), int(m.group(2))


def blurb_lines(markup):
    """The wrapped blurb, in draw order.

    The tag line is set at the same step, so the two are told apart by where
    they sit inside the card rather than by their class.
    """
    _, cy, _, _ = card_box(markup)
    return [body for y, body in re.findall(
        r'<text x="-?\d+" y="(\d+)" class="caption dim">([^<]*)</text>', markup)
        if int(y) >= cy + projects.BLURB_DY]


def classes(markup):
    return {token for value in re.findall(r'class="([^"]*)"', markup)
            for token in value.split()}


# --- file set --------------------------------------------------------------

def test_emits_a_heading_slice_and_one_file_per_entry(out):
    assert list(out) == ["projects.svg", "projects-1.svg", "projects-2.svg",
                         "projects-3.svg", "projects-4.svg"]


def test_the_heading_is_full_width_so_the_title_is_not_inside_a_card_link(out):
    assert f'width="{c.W}"' in out["projects.svg"].markup
    assert "~/" in out["projects.svg"].markup and "4 repos" in out["projects.svg"].markup


def test_no_card_contains_an_anchor(out):
    """GitHub strips <a> from a rendered SVG; the README wraps the <img>."""
    for markup in (s.markup for s in out.values()):
        assert "<a " not in markup and "</a>" not in markup


def test_cards_are_half_width_and_alternate_their_rail(out):
    one, two, three, four = cards(out)
    height = int(attr(one, "height"))
    for markup in (one, two, three, four):
        assert attr(markup, "width") == str(c.W // 2)
    for markup in (one, three):                     # left of the seam, outer rail
        assert rail(markup) == f"M{c.MARGIN} {height}V0"
    for markup in (two, four):                      # right of it, mirrored
        assert rail(markup) == f"M{c.W // 2 - c.MARGIN} 0V{height}"


def test_the_two_halves_of_a_row_meet_at_the_seam(out):
    """Each half runs flush to the seam, so the backgrounds tile with no gap."""
    one, two, _, _ = cards(out)
    seam = c.W // 2
    assert seam % c.ROW == 0
    assert canvas(one) == (c.FRAME_L, seam)
    assert tuple(seam + v for v in canvas(two)) == (seam, c.FRAME_R)


def test_every_card_is_the_same_height(out):
    heights = {attr(m, "height") for m in cards(out)}
    assert len(heights) == 1
    assert int(heights.pop()) % c.ROW == 0


def test_card_height_is_driven_by_the_longest_blurb():
    """Entry two wraps to many lines, so it sets the height of all four."""
    short = by_file({"projects": CFG["projects"][:1]}, DATA)
    tall = by_file(CFG, DATA)
    assert int(attr(tall["projects-1.svg"].markup, "height")) > \
        int(attr(short["projects-1.svg"].markup, "height"))


def test_each_card_carries_the_repo_url_so_the_readme_can_anchor_it(out):
    assert out["projects-1.svg"].href == "https://github.com/me/one"
    assert out["projects.svg"].href is None


# --- card contents ---------------------------------------------------------

def test_a_card_is_a_plain_rounded_rect_with_one_hairline_edge(out):
    """The corner brackets are gone; the card is its own stroke now."""
    for markup in cards(out):
        assert markup.count("<rect") == 1
        assert (f'rx="{c.R_CARD}" fill="{c.LIGHT.surface}" '
                f'stroke="{c.LIGHT.hairline}" stroke-width="{c.EDGE_W}"') in markup


def test_the_repo_name_is_set_at_the_body_step(out):
    one = out["projects-1.svg"].markup
    x, cy, _, _ = card_box(one)
    assert (f'<text x="{x + projects.PAD}" y="{cy + projects.NAME_DY}" '
            f'class="body ink">one</text>') in one


def test_the_live_language_wins_over_the_hand_written_tag(out):
    """profile.toml tags are prose; `language` is what GitHub actually reports."""
    assert ">Zig<" in out["projects-3.svg"].markup
    assert "ZIG" not in out["projects-3.svg"].markup    # the tag list is unaffected


def test_a_repo_absent_from_the_fetched_data_still_renders(out):
    four = out["projects-4.svg"].markup
    assert "four" in four
    assert "—" in four                            # language placeholder
    assert "updated" not in four


def test_relative_update_line_is_rendered(out):
    assert "updated" in out["projects-1.svg"].markup
    assert re.search(r"updated \d+ (month|year)s? ago", out["projects-2.svg"].markup)


def test_the_footer_is_a_mono_language_and_a_caption_stamp(out):
    """The accent square that used to sit before the language is gone."""
    one = out["projects-1.svg"].markup
    assert 'class="mono ink">Go</text>' in one
    assert 'text-anchor="end" class="caption dim">updated 2 months ago</text>' in one
    assert f'fill="{c.LIGHT.accent}"' not in one


def test_star_count_is_never_drawn(out):
    """Every repo here has zero stars, and a column of noughts reads as rot."""
    for markup in cards(out):
        assert "star" not in c.visible(markup).lower()
        assert not re.search(r"★|\b0 \b", c.visible(markup))


def test_tags_are_one_caption_line_joined_with_a_middot(out):
    assert 'class="caption dim">GO · CLI</text>' in out["projects-1.svg"].markup


def test_a_card_without_tags_leaves_no_empty_line_behind(out):
    three = out["projects-3.svg"].markup
    _, cy, _, _ = card_box(three)
    assert f'y="{cy + projects.TAGS_DY}"' not in three


# --- blurb wrapping --------------------------------------------------------

def test_blurb_is_wrapped_to_the_card_width(out):
    lines = blurb_lines(out["projects-2.svg"].markup)
    assert len(lines) > 1
    assert max(len(line) for line in lines) <= projects.BLURB_COLS


def test_wrap_width_fits_inside_the_card():
    """The blurb is proportional sans and cannot be measured by character
    count, so the column figure is deliberately pessimistic: 0.62em a glyph is
    more than Inter's average lowercase advance, which wraps a line short of
    the card rather than past it."""
    assert projects.BLURB_COLS * projects.BLURB_PX * 0.62 <= INNER


def test_no_blurb_line_runs_past_the_cards_inner_width(out):
    """Checked line by line, not just as a column count: wrap() breaks on
    spaces, so a line of short words is the one that comes closest."""
    for markup in cards(out):
        for line in blurb_lines(markup):
            assert len(line) * projects.BLURB_PX * 0.62 <= INNER, line


def test_an_unbreakable_blurb_is_hard_wrapped_rather_than_overhanging():
    lines = blurb_lines(
        by_file({"projects": [{"repo": "me/one", "blurb": "x" * 200}]},
                DATA)["projects-1.svg"].markup)
    assert len(lines) > 1
    for line in lines:
        assert len(line) * projects.BLURB_PX * 0.62 <= INNER, line


def test_the_blurb_stops_above_the_footer_rule(out):
    """The footer hangs off the card's bottom rather than off the blurb, so a
    blurb that grew into it would print over the rule instead of moving it."""
    for markup in cards(out):
        _, cy, _, height = card_box(markup)
        last = cy + projects.BLURB_DY + (len(blurb_lines(markup)) - 1) * projects.LINE_H
        assert last + projects.BLURB_TAIL <= cy + height - projects.FOOT_H


# --- geometry --------------------------------------------------------------

def test_cards_stay_inside_the_content_column(out):
    """Left card starts at TEXT_X; right card ends at the contract's right edge."""
    assert projects.CARD_W * 2 + projects.GAP == c.CONTENT_R - c.TEXT_X
    one, two, _, _ = cards(out)
    lx, _, lw, _ = card_box(one)
    rx, _, rw, _ = card_box(two)
    assert lx == c.TEXT_X
    assert lx + lw <= c.W // 2
    assert c.W // 2 + rx + rw == c.CONTENT_R


def test_the_gap_between_a_pair_straddles_the_seam(out):
    one, two, _, _ = cards(out)
    lx, _, lw, _ = card_box(one)
    rx, _, _, _ = card_box(two)
    assert (c.W // 2 + rx) - (lx + lw) == projects.GAP


def test_every_line_of_text_sits_within_its_own_cards_padding(out):
    for markup in cards(out):
        x, _, width, _ = card_box(markup)
        for tx in (int(v) for v in re.findall(r'<text x="(-?\d+)"', markup)):
            assert x + projects.PAD <= tx <= x + width - projects.PAD


# --- colour ----------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_both_themes_render_a_complete_card(out, theme):
    """Same box, same words in both: readme.py pairs the two files in one
    <picture> and shares a single alt text between them."""
    markup = by_file(CFG, DATA, theme)["projects-1.svg"].markup
    assert card_box(markup) == card_box(out["projects-1.svg"].markup)
    assert blurb_lines(markup) == blurb_lines(out["projects-1.svg"].markup)
    assert f'fill="{theme.surface}" stroke="{theme.hairline}"' in markup
    assert f'fill="{theme.canvas}"' in markup
    assert f".ink{{fill:{theme.ink}}}.dim{{fill:{theme.dim}}}" in markup
    for part in ("one", "GO · CLI", "Short one.", "Go", "updated 2 months ago"):
        assert part in markup


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_cards_name_only_classes_the_new_systems_keep(theme):
    for entry in projects.render(CFG, DATA, theme):
        assert classes(entry.markup) <= LIVE, classes(entry.markup) - LIVE
        for gone in ("glow", "soft", "grid"):
            assert f"url(#{gone})" not in entry.markup


# --- accessibility ---------------------------------------------------------

def test_desc_spells_out_the_values_it_draws(out):
    desc = re.search(r"<desc id=\"d\">([^<]*)</desc>", out["projects-1.svg"].markup).group(1)
    assert "one" in desc and "Go" in desc and "updated" in desc
    assert "Short one." in desc and "CLI" in desc


def test_the_heading_desc_counts_the_repos_it_announces(out):
    desc = re.search(r"<desc id=\"d\">([^<]*)</desc>", out["projects.svg"].markup).group(1)
    assert "4 public repositories" in desc


# --- degrading -------------------------------------------------------------

@pytest.mark.parametrize("cfg,data", [
    ({}, DATA),
    ({"projects": []}, DATA),
    (CFG, {}),
    (CFG, {"projects": []}),
])
def test_missing_inputs_render_one_short_panel_instead_of_raising(cfg, data):
    out = by_file(cfg, data)
    assert list(out) == ["projects.svg"]
    assert "No repository data available." in out["projects.svg"].markup
    assert int(attr(out["projects.svg"].markup, "height")) % c.ROW == 0


def test_an_entry_without_a_name_falls_back_to_the_repo_path():
    out = by_file({"projects": [{"repo": "me/odd-one", "blurb": "x"}]}, DATA)
    assert "odd-one" in out["projects-1.svg"].markup
