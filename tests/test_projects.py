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


def by_file(cfg, data):
    """The panel's slices, keyed by filename for readability."""
    return {s.file: s for s in projects.render(cfg, data)}


@pytest.fixture(scope="module")
def out():
    return by_file(CFG, DATA)


def cards(out):
    return [out[f"projects-{i}.svg"].markup for i in range(1, 5)]


def attr(markup, name):
    return re.search(rf'{name}="(\d+)"', markup).group(1)


# --- file set --------------------------------------------------------------

def test_emits_a_heading_slice_and_one_file_per_entry(out):
    assert list(out) == ["projects.svg", "projects-1.svg", "projects-2.svg",
                         "projects-3.svg", "projects-4.svg"]


def test_the_heading_is_full_width_so_the_title_is_not_inside_a_card_link(out):
    assert f'width="{c.W}"' in out["projects.svg"].markup
    assert "~/" in out["projects.svg"].markup and "4 REPOS" in out["projects.svg"].markup


def test_no_card_contains_an_anchor(out):
    """GitHub strips <a> from a rendered SVG; the README wraps the <img>."""
    for markup in (s.markup for s in out.values()):
        assert "<a " not in markup and "</a>" not in markup


def test_cards_are_half_width_and_alternate_their_rail(out):
    one, two, three, four = cards(out)
    for markup in (one, two, three, four):
        assert attr(markup, "width") == str(c.W // 2)
    assert f'<rect x="{c.MARGIN}"' in one        # left of the seam, left rail
    assert '<rect x="0"' in two                  # right of it, flush inner edge
    assert f'<rect x="{c.MARGIN}"' in three
    assert '<rect x="0"' in four


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


def test_star_count_is_never_drawn(out):
    """Every repo here has zero stars, and a column of noughts reads as rot."""
    for markup in cards(out):
        assert "star" not in c.visible(markup).lower()
        assert not re.search(r"★|\b0 \b", c.visible(markup))


def test_tags_are_rendered_as_labels(out):
    assert "GO" in c.visible(out["projects-1.svg"].markup)
    assert "CLI" in c.visible(out["projects-1.svg"].markup)


def test_blurb_is_wrapped_to_the_card_width(out):
    lines = re.findall(r'style="font-size:13px">([^<]*)</text>', out["projects-2.svg"].markup)
    assert len(lines) > 1
    assert max(len(line) for line in lines) <= projects.BLURB_COLS


def test_wrap_width_fits_inside_the_card(out):
    assert projects.BLURB_COLS * projects.BLURB_PX * 0.6 <= projects.CARD_W - 2 * projects.PAD


def test_cards_stay_inside_the_content_column(out):
    """Left card starts at TEXT_X; right card ends at the contract's right edge."""
    assert projects.CARD_W * 2 + projects.GAP == projects.CONTENT_R - c.TEXT_X
    assert c.TEXT_X + projects.CARD_W + projects.GAP - projects.HALF > 0


def test_desc_spells_out_the_values_it_draws(out):
    desc = re.search(r"<desc id=\"d\">([^<]*)</desc>", out["projects-1.svg"].markup).group(1)
    assert "one" in desc and "Go" in desc and "updated" in desc
    assert "Short one." in desc and "CLI" in desc


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
