"""Tests for the project cards, which are the only panel emitting many files."""
import datetime
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import projects

NOW = datetime.datetime.now(datetime.timezone.utc)


def days_ago(n):
    return (NOW - datetime.timedelta(days=n)).isoformat().replace("+00:00", "Z")


CFG = {"projects": [
    {"repo": "me/one", "name": "one", "blurb": "Short one.", "tags": ["Go", "CLI"]},
    {"repo": "me/two", "name": "two", "tags": ["Rust"],
     "blurb": " ".join(["word"] * 60)},
    {"repo": "me/three", "name": "three", "blurb": "Third.", "tags": []},
    {"repo": "me/four", "name": "four", "blurb": "Fourth.", "tags": ["C"]},
]}
DATA = {"projects": [
    {"repo": "me/one", "language": "Go", "stars": 0, "pushed_at": days_ago(9)},
    {"repo": "me/two", "language": "Rust", "stars": 0, "pushed_at": days_ago(2000)},
    {"repo": "me/three", "language": "Zig", "stars": 0, "pushed_at": None},
]}

MONO = c.e(c.MONO_STACK)
SANS = c.e(c.SANS_STACK)


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


def paint(markup):
    """The markup without its <style> block, for assertions about colour.

    The inlined woff2 payloads are long enough that a bare `in` test against
    the whole file could match a hex string inside the base64.
    """
    return re.sub(r"<style>.*?</style>", "", markup, flags=re.S)


def rects(markup):
    """Every <rect>, in draw order, as attribute dicts. The card is the first."""
    return [dict(re.findall(r'([\w-]+)="([^"]*)"', m))
            for m in re.findall(r"<rect ([^>]*)/>", markup)]


def card_box(markup):
    """(x, y, width, height) of the card itself, in its own slice's coordinates."""
    box = rects(markup)[0]
    return tuple(int(box[k]) for k in ("x", "y", "width", "height"))


def texts(markup):
    """Every <text> as (attributes, content), in draw order."""
    return [(dict(re.findall(r'([\w-]+)="([^"]*)"', head)), body)
            for head, body in re.findall(r"<text ([^>]*)>([^<]*)</text>", markup)]


def typeset(markup, family, size):
    """(x, y, content) for every label set in one face and size."""
    return [(int(a["x"]), int(a["y"]), body) for a, body in texts(markup)
            if a["font-family"] == family and a["font-size"] == str(size)]


def blurb_lines(markup):
    """The wrapped blurb, in draw order. It is the only sans run on a card."""
    return [body for _, _, body in typeset(markup, SANS, 13)]


def chips(markup):
    """(rect attributes, label attributes, label) per tag chip, in draw order."""
    labels = [(a, body) for a, body in texts(markup)
              if a["font-family"] == MONO and a["font-size"] == "11"
              and "text-anchor" not in a]
    return [(box, *label) for box, label in zip(rects(markup)[1:], labels)]


def rail(markup):
    """The slice's frame path: one vertical, on the card's outer edge.

    `RAIL_W`, not `EDGE_W` — the rail is the one stroke that spans two files and
    is drawn at twice the weight so the two agree after resampling.
    """
    return re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]*" '
                     rf'stroke-width="{c.RAIL_W}"', markup).group(1)


def canvas(markup, theme=c.LIGHT):
    """(left, right) x of the slice background, which meets its neighbour."""
    d = re.search(rf'<path d="([^"]*)" fill="{theme.canvas}"/>', markup).group(1)
    m = re.match(r"M(-?\d+) \d+H(-?\d+)", d)
    return int(m.group(1)), int(m.group(2))


def desc(markup):
    return re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)


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


def test_card_height_is_fixed_whatever_the_blurb_does():
    """Height is the reference's 164 regardless of content: the two halves of a
    row are separate files and cannot negotiate a height between them, and the
    blurb is capped rather than allowed to grow the box."""
    short = by_file({"projects": CFG["projects"][:1]}, DATA)
    tall = by_file(CFG, DATA)
    assert attr(tall["projects-1.svg"].markup, "height") == \
        attr(short["projects-1.svg"].markup, "height")
    assert {card_box(m)[3] for m in cards(tall)} == {projects.CARD_H}


def test_each_card_carries_the_repo_url_so_the_readme_can_anchor_it(out):
    assert out["projects-1.svg"].href == "https://github.com/me/one"
    assert out["projects.svg"].href is None


# --- card contents ---------------------------------------------------------

def test_a_card_is_a_plain_rounded_rect_with_one_hairline_edge(out):
    """The card draws its own stroke at EDGE_W; only the frame rail is heavier."""
    for markup in cards(out):
        assert (f'width="{projects.CARD_W}" height="{projects.CARD_H}" '
                f'rx="{c.R_CARD}" fill="{c.LIGHT.surface}" '
                f'stroke="{c.LIGHT.hairline}" stroke-width="{c.EDGE_W}"') in markup


def test_the_repo_name_is_mono_fifteen_bold_in_the_ink(out):
    one = out["projects-1.svg"].markup
    x, y, _, _ = card_box(one)
    assert (f'<text x="{x + projects.PAD}" y="{y + projects.NAME_DY}" '
            f'fill="{c.LIGHT.ink}" font-family="{MONO}" font-size="15" '
            f'font-weight="700">one</text>') in one


def test_the_age_is_end_anchored_at_the_cards_far_padding(out):
    """It shares the name's baseline and is set a tier down, in faint mono 11,
    so the corner reads as one line with the repo name leading it."""
    one = out["projects-1.svg"].markup
    x, y, _, _ = card_box(one)
    assert (f'<text x="{x + projects.CARD_W - projects.PAD}" '
            f'y="{y + projects.NAME_DY}" fill="{c.LIGHT.faint}" '
            f'font-family="{MONO}" font-size="11" text-anchor="end">'
            f'{c.ago(DATA["projects"][0]["pushed_at"])}</text>') in one


def test_the_age_reads_as_an_abbreviated_span(out):
    """`ago()` is console's, not the panel's: days under 45, then months, then
    years, so the label always fits the card corner."""
    assert ">9d ago<" in out["projects-1.svg"].markup
    assert re.search(r">\d+(d|mo|y) ago<", out["projects-2.svg"].markup)


def test_the_blurb_is_sans_thirteen_dim_on_a_nineteen_pixel_step(out):
    one = out["projects-1.svg"].markup
    x, y, _, _ = card_box(one)
    assert typeset(one, SANS, 13) == [
        (x + projects.PAD, y + projects.BLURB_DY, "Short one.")]
    assert f'fill="{c.LIGHT.dim}" font-family="{SANS}" font-size="13"' in one

    two = out["projects-2.svg"].markup
    ys = [ly for _, ly, _ in typeset(two, SANS, 13)]
    assert [b - a for a, b in zip(ys, ys[1:])] == [projects.LINE_H] * (len(ys) - 1)


def test_the_blurb_is_capped_at_three_lines(out):
    """A fourth line would print over the chips, which hang off the card's
    bottom edge rather than following the text."""
    lines = blurb_lines(out["projects-2.svg"].markup)
    assert len(lines) == projects.BLURB_MAX
    assert " ".join(lines) != " ".join(["word"] * 60)


def test_blurb_is_wrapped_to_the_card_width(out):
    lines = blurb_lines(out["projects-2.svg"].markup)
    assert projects.BLURB_COLS == int((projects.CARD_W - 2 * projects.PAD) / 6.6)
    assert max(len(line) for line in lines) <= projects.BLURB_COLS


def test_an_unbreakable_blurb_overhangs_rather_than_being_cut_mid_token():
    """The reference's wrap() breaks on whitespace only. A single word wider
    than the card is left whole: a clipped repo name is worse than a long one."""
    lines = blurb_lines(
        by_file({"projects": [{"repo": "me/one", "blurb": "x" * 200}]},
                DATA)["projects-1.svg"].markup)
    assert lines == ["x" * 200]


def test_a_blurb_is_wrapped_on_spaces_and_not_on_hyphens():
    lines = blurb_lines(by_file(
        {"projects": [{"repo": "me/one", "blurb": "hand-written " + "word " * 20}]},
        DATA)["projects-1.svg"].markup)
    assert lines[0].startswith("hand-written word")


# --- tag chips -------------------------------------------------------------

def test_a_chip_is_a_tinted_rect_sized_to_its_label(out):
    """Width is the label measured at the mono advance plus the two paddings,
    which is the only reason the chips can be laid out without a text metric."""
    one = out["projects-1.svg"].markup
    x, y, _, _ = card_box(one)
    box, label, body = chips(one)[0]
    assert body == "Go"
    assert int(box["width"]) == round(2 * projects.GLYPH) + 2 * projects.CHIP_PAD
    assert (int(box["x"]), int(box["y"])) == (x + projects.PAD, y + projects.CHIP_DY)
    assert (box["height"], box["rx"]) == (str(projects.CHIP_H), str(c.R_CHIP))
    assert (box["fill"], box["opacity"]) == (c.LIGHT.ink, str(projects.CHIP_TINT))
    assert (int(label["x"]), int(label["y"])) == \
        (x + projects.PAD + projects.CHIP_PAD, y + projects.CHIP_BASE)
    assert (label["fill"], label["font-size"]) == (c.LIGHT.dim, "11")


def test_chips_run_along_a_row_with_a_fixed_gap_between_them(out):
    one = out["projects-1.svg"].markup
    first, second = chips(one)
    assert int(second[0]["x"]) - (int(first[0]["x"]) + int(first[0]["width"])) \
        == projects.CHIP_GAP
    assert first[0]["y"] == second[0]["y"]


def test_the_chip_row_stays_inside_the_cards_padding(out):
    for markup in cards(out):
        x, _, width, _ = card_box(markup)
        for box, _, _ in chips(markup):
            assert x + projects.PAD <= int(box["x"])
            assert int(box["x"]) + int(box["width"]) <= x + width - projects.PAD


def test_the_live_language_leads_the_chips(out):
    """profile.toml names tags as prose; `language` is what GitHub reports, and
    a repo with no hand-written tags still gets that one chip."""
    assert [body for _, _, body in chips(out["projects-3.svg"].markup)] == ["Zig"]


def test_the_language_is_not_repeated_as_its_own_chip(out):
    """Entry one is tagged Go and reported as Go; that is one chip, not two."""
    assert [body for _, _, body in chips(out["projects-1.svg"].markup)] == ["Go", "CLI"]


def test_tags_are_drawn_as_written_rather_than_upper_cased(out):
    assert ">Go<" in out["projects-1.svg"].markup
    assert ">GO<" not in out["projects-1.svg"].markup


def test_a_card_without_tags_or_a_language_draws_no_chips():
    markup = by_file({"projects": [{"repo": "me/unfetched", "blurb": "x"}]},
                     DATA)["projects-1.svg"].markup
    assert rects(markup) == rects(markup)[:1]


def test_a_repo_absent_from_the_fetched_data_still_renders(out):
    """Its card loses the age and the language chip and keeps everything else;
    a hand-written entry is not contingent on the fetch having reached it."""
    four = out["projects-4.svg"].markup
    assert "four" in four and "Fourth." in four
    assert [body for _, _, body in chips(four)] == ["C"]
    assert "text-anchor=\"end\"" not in four
    assert "ago" not in c.visible(four)


def test_star_count_is_never_drawn(out):
    """Every repo here has zero stars, and a column of noughts reads as rot."""
    for markup in cards(out):
        assert "star" not in c.visible(markup).lower()
        assert not re.search(r"★|\b0 \b", c.visible(markup))


# --- restraint -------------------------------------------------------------

def test_no_card_is_marked_out_from_the_others(out):
    """The list is curated, not ranked, so there is no highest value to mark;
    the accent reaches this panel only as the heading's section rule."""
    for markup in cards(out):
        assert c.LIGHT.accent not in paint(markup)


def test_nothing_on_a_card_animates(out):
    """A rendered SVG is painted at frame zero, so a staggered fade-in is simply
    an invisible card on GitHub."""
    for markup in cards(out):
        assert "animation-delay" not in markup
        assert 'class="ln"' not in markup and 'class="live"' not in markup


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


def test_the_card_is_centred_in_its_slice(out):
    """A slice height must be a multiple of ROW and 164 is not, so the card sits
    inside the row with the remainder split evenly above and below it — which is
    the one place this panel's rhythm differs from the single-slice reference."""
    assert projects.SLICE_H % c.ROW == 0
    for markup in cards(out):
        _, y, _, height = card_box(markup)
        assert y == projects.TOP
        assert projects.SLICE_H - (y + height) == y


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
    assert f'fill="{theme.ink}" font-family="{MONO}" font-size="15"' in markup
    assert f'fill="{theme.dim}" font-family="{SANS}" font-size="13"' in markup
    assert f'fill="{theme.faint}" font-family="{MONO}" font-size="11"' in markup
    for part in ("one", "Go", "CLI", "Short one.", "9d ago"):
        assert part in markup


# --- accessibility ---------------------------------------------------------

def test_desc_spells_out_the_values_it_draws(out):
    d = desc(out["projects-1.svg"].markup)
    assert "one" in d and "Go" in d and "updated" in d
    assert "Short one." in d and "CLI" in d


def test_desc_carries_the_whole_blurb_even_though_the_card_truncates_it(out):
    """A screen reader has the room three lines of 13px sans do not."""
    assert desc(out["projects-2.svg"].markup).endswith(" ".join(["word"] * 60))


def test_the_heading_desc_counts_the_repos_it_announces(out):
    assert "4 public repositories" in desc(out["projects.svg"].markup)


# --- degrading -------------------------------------------------------------

@pytest.mark.parametrize("cfg,data", [
    ({}, DATA),
    ({"projects": []}, DATA),
    (CFG, {}),
    (CFG, {"projects": []}),
    (CFG, {"projects": ["not a record"]}),
])
def test_missing_inputs_render_one_short_panel_instead_of_raising(cfg, data):
    out = by_file(cfg, data)
    assert list(out) == ["projects.svg"]
    assert "No repository data available." in out["projects.svg"].markup
    assert int(attr(out["projects.svg"].markup, "height")) % c.ROW == 0


def test_an_entry_without_a_name_falls_back_to_the_repo_path():
    out = by_file({"projects": [{"repo": "me/odd-one", "blurb": "x"}]}, DATA)
    assert "odd-one" in out["projects-1.svg"].markup
