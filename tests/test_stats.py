"""Tests for the counter grid and the language chart."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import stats

STATS = {
    "updated": "2026-10-12", "year": 2026, "created_at": "2016-08-28T00:35:26Z",
    "followers": 5, "prs": 423, "prs_merged": 372, "repos": 11, "repos_public": 5,
    "stars": 0, "forks": 0, "contributions_year": 1174, "contributions_all": 1441,
    "private_year": 1122, "streak_longest": 6, "streak_current": 2,
    "repos_contributed": 29, "repos_contributed_private": 26,
    "repos_contributed_org": 23, "orgs": 2,
    "languages": {"TypeScript": 508003, "Python": 417967, "Java": 204747,
                  "Swift": 163026, "JavaScript": 130812, "C++": 83684,
                  "CSS": 80999, "Shell": 39980},
}

TOTAL = sum(STATS["languages"].values())
TOP = sorted(STATS["languages"].items(), key=lambda kv: -kv[1])[:stats.TOP_N]

TEXT = re.compile(
    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" fill="([^"]+)" font-family="[^"]*"'
    r' font-size="(\d+)"([^>]*)>([^<]*)</text>')
RECT = re.compile(
    rf'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="{stats.BAR_H}"'
    rf' rx="{c.R_CHIP}" fill="([^"]+)" opacity="([\d.]+)"/>')


@pytest.fixture(scope="module")
def markup():
    return stats.render({}, {"stats": STATS}, c.LIGHT)


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def texts(svg):
    """Every <text> as (x, y, fill, size, weight, ls, anchor, content).

    Type here is set per element in presentation attributes rather than by
    class, so the attributes are the only record of which tier a label is in.
    """
    out = []
    for x, y, fill, size, rest, body in TEXT.findall(svg):
        def attr(name, rest=rest):
            found = re.search(rf'{name}="([^"]+)"', rest)
            return found.group(1) if found else None
        out.append((float(x), float(y), fill, int(size), attr("font-weight"),
                    attr("letter-spacing"), attr("text-anchor"), body))
    return out


def said(svg, content):
    """The one text drawing `content`, as a (x, y, fill, size, ...) tuple."""
    found = [t for t in texts(svg) if t[-1] == content]
    assert len(found) == 1, f"{content!r} drawn {len(found)} times"
    return found[0]


def rects(svg):
    """(x, y, width, fill, opacity) of every bar rect, in draw order."""
    return [(int(x), int(y), int(w), fill, float(o))
            for x, y, w, fill, o in RECT.findall(svg)]


# --- frame -----------------------------------------------------------------

def test_the_slice_height_lands_on_the_grid_with_the_frame_left_open(markup):
    """A height off the 40px pitch would shift every slice below it, and only
    the header and footer cap the frame."""
    assert height_of(markup) % c.ROW == 0
    rails = re.search(r'<path d="([^"]*)" fill="none"', markup).group(1)
    assert rails == f"M{c.FRAME_L} {height_of(markup)}V0M{c.FRAME_R} 0V{height_of(markup)}"


def test_the_slice_ends_one_bar_pitch_below_the_last_language(markup):
    assert height_of(markup) == c.to_grid(
        stats.BAR_Y0 + stats.TOP_N * stats.BAR_PITCH + 20)


def test_nothing_is_drawn_outside_the_content_column(markup):
    for x in re.findall(r'<(?:text|rect|line) x1?="([\d.]+)"', markup):
        assert c.MARGIN <= float(x) <= c.CONTENT_R
    for x, _, width, _, _ in rects(markup):
        assert x + width <= c.CONTENT_R


def test_the_heading_counter_carries_the_capture_stamp(markup):
    """The panel is a record, and the stamp is the only thing on it that says
    how old that record is."""
    x, y, fill, size, _, _, anchor, _ = said(markup, "captured 2026-10-12")
    assert (x, y, anchor) == (c.CONTENT_R, stats.HEAD_Y, "end")
    assert (fill, size) == (c.LIGHT.faint, 12)


# --- the counter grid ------------------------------------------------------

def test_the_six_cells_sit_three_to_a_row_on_even_columns(markup):
    labels = ["contributions 2026", "pull requests merged",
              "repositories touched", "private share", "longest streak",
              "account opened"]
    placed = [said(markup, label)[:2] for label in labels]
    assert placed == [(c.TEXT_X + (i % stats.COLS) * stats.COL_W,
                       stats.GRID_Y + (i // stats.COLS) * stats.GRID_PITCH)
                      for i in range(6)]
    assert stats.COL_W * stats.COLS <= c.CONTENT_R - c.TEXT_X


def test_a_cell_stacks_its_label_value_and_note_at_a_fixed_offset(markup):
    """One rhythm for all six, so the two rows read as a table and not as six
    separate blocks."""
    label_y = said(markup, "longest streak")[1]
    assert said(markup, "6d")[1] == label_y + stats.VALUE_DY
    assert said(markup, "current 2d")[1] == label_y + stats.NOTE_DY


@pytest.mark.parametrize("content, tier", [
    ("private share", (c.LIGHT.faint, 11, None, "0.5")),
    ("1,122 commits", (c.LIGHT.dim, 12, None, None)),
    ("96%", (c.LIGHT.ink, 30, "700", "-0.5")),
])
def test_a_cell_uses_three_type_tiers_and_nothing_else(markup, content, tier):
    """Faint label, ink value, dim note: the hierarchy is carried by tone and
    size rather than by a rule or a box around each cell."""
    _, _, fill, size, weight, ls, _, _ = said(markup, content)
    assert (fill, size, weight, ls) == tier


def test_each_cell_is_closed_by_a_rule_stopping_short_of_the_next_column(markup):
    rules = [(int(x1), int(y1), int(x2)) for x1, y1, x2 in re.findall(
        r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="\d+" '
        rf'stroke="{c.LIGHT.hairline}"', markup)]
    cells = [(c.TEXT_X + (i % stats.COLS) * stats.COL_W,
              stats.GRID_Y + (i // stats.COLS) * stats.GRID_PITCH)
             for i in range(6)]
    assert [(x, y + stats.RULE_DY, x + stats.COL_W - stats.RULE_INSET)
            for x, y in cells] == rules[1:]      # rules[0] is the heading's


def test_counters_over_a_thousand_are_separated(markup):
    for value in ("1,174", "1,441 all time", "1,122 commits"):
        assert said(markup, value)


def test_the_private_share_is_rounded_against_this_years_contributions(markup):
    """The panel's point: most of the work happens in private repositories, and
    one share says so where two raw counts would not. Rounded half up, as the
    preview rounds it — round() would send a .5 to the nearest even instead."""
    share = STATS["private_year"] / STATS["contributions_year"] * 100
    assert said(markup, f"{int(share + 0.5)}%")
    assert said(markup, "1,122 commits")


def test_the_account_age_is_the_span_between_opening_and_the_stamp(markup):
    assert said(markup, "2016")
    assert said(markup, "10 years")


@pytest.mark.parametrize("raw", [None, "", "not-a-date", 12345])
def test_an_unusable_join_date_keeps_the_cell_and_drops_the_year(raw):
    """The grid is the panel's structure; a hole in it would read as a broken
    renderer rather than as a date nobody recorded."""
    markup = stats.render({}, {"stats": {**STATS, "created_at": raw}}, c.LIGHT)
    assert said(markup, "account opened")
    assert said(markup, "—")
    assert "years" not in c.visible(markup)


# --- the language chart ----------------------------------------------------

def test_only_the_top_six_languages_are_charted(markup):
    shown = c.visible(markup)
    assert "C++" in shown                        # sixth by bytes
    assert "CSS" not in shown and "Shell" not in shown
    assert said(markup, "languages by bytes")[3] == 11


def test_language_rows_run_on_a_fixed_pitch_below_the_grid(markup):
    ys = [said(markup, name)[1] for name, _ in TOP]
    assert ys == [stats.BAR_Y0 + 10 + i * stats.BAR_PITCH
                  for i in range(stats.TOP_N)]
    assert ys[0] > said(markup, "languages by bytes")[1]


def test_every_bar_sits_in_a_track_running_the_full_span(markup):
    tracks = [r for r in rects(markup) if r[4] == 0.06]
    assert len(tracks) == stats.TOP_N
    for x, _, width, fill, _ in tracks:
        assert (x, width, fill) == (stats.BAR_X, stats.BAR_W, c.LIGHT.ink)


def test_bar_widths_are_shares_of_every_languages_bytes(markup):
    """The chart measures the codebases worked in, so the denominator is all
    the bytes — not just the six that fit, which would inflate every bar."""
    drawn = [r[2] for r in rects(markup) if r[4] != 0.06]
    assert drawn == [max(2, int(stats.BAR_W * size / TOTAL + 0.5))
                     for _, size in TOP]
    assert sum(drawn) < stats.BAR_W * stats.TOP_N
    assert drawn == sorted(drawn, reverse=True)


def test_percentages_are_the_same_shares_the_bars_draw(markup):
    pcts = [float(p) for p in re.findall(r'text-anchor="end">([\d.]+)%', markup)]
    assert pcts == [round(100 * size / TOTAL, 1) for _, size in TOP]
    assert sum(pcts) < 100                       # CSS and Shell are off-chart
    for _, _, fill, size, _, _, anchor, body in texts(markup):
        if body.endswith("%") and anchor == "end":
            assert (fill, size) == (c.LIGHT.faint, 12)


def test_the_bar_fill_steps_back_a_tenth_of_its_opacity_per_row(markup):
    """Rank is carried by tone, since the bottom bars are too short to compare
    by length and the palette has no second hue to spend on a legend."""
    assert [r[4] for r in rects(markup)] == [
        v for i in range(stats.TOP_N)
        for v in (0.06, round(0.82 - i * 0.1, 2))]


def test_a_language_name_too_wide_for_its_column_is_truncated():
    markup = stats.render({}, {"stats": {**STATS, "languages": {"A" * 40: 10}}},
                          c.LIGHT)
    name = [t[-1] for t in texts(markup) if t[0] == c.TEXT_X
            and t[1] == stats.BAR_Y0 + 10][0]
    assert name.endswith("…") and len(name) <= stats.MAX_NAME


# --- colour and motion -----------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_panel_spends_no_accent(theme):
    """The accent is state, and the only live fact in the console is the
    header's streak dot. Nothing on a record of the past earns it."""
    body = stats.render({}, {"stats": STATS}, theme).split("</style>")[1]
    assert theme.accent not in body


def test_nothing_in_the_panel_fades_in(markup):
    """GitHub paints a rendered SVG at frame zero, so a staggered fade-in is
    just a panel that arrives blank."""
    assert "animation-delay" not in markup
    assert 'class="ln"' not in markup


def test_the_two_themes_differ_in_nothing_but_their_role_colours():
    """readme.py pairs them in one <picture> under a single alt text, so any
    difference in geometry would show as a jump when the scheme flips."""
    light, dark = (stats.render({}, {"stats": STATS}, t) for t in c.THEMES)

    def skeleton(svg, theme):
        out = svg.split("</style>")[1]
        for role in ("canvas", "ink", "surface", "dim", "faint", "hairline",
                     "accent"):
            out = out.replace(getattr(theme, role), role.upper())
        return out

    assert skeleton(light, c.LIGHT) == skeleton(dark, c.DARK)
    assert light != dark


# --- accessibility and degrading -------------------------------------------

def test_desc_spells_out_every_number_it_draws(markup):
    desc = desc_of(markup)
    for fragment in ("1,174 contributions in 2026",
                     "372 of 423 pull requests merged",
                     "29 repositories touched",
                     f"Top language TypeScript at {100 * TOP[0][1] / TOTAL:.1f}%",
                     f"of {c.num(TOTAL)} bytes"):
        assert fragment in desc, fragment


@pytest.mark.parametrize("data", [{}, {"stats": None}, {"stats": {}}])
def test_missing_stats_render_one_short_panel_instead_of_raising(data):
    markup = stats.render({}, data, c.LIGHT)
    assert height_of(markup) % c.ROW == 0 and height_of(markup) <= 120
    assert "no stats available" in c.visible(markup)
    assert "No GitHub statistics are available." in markup


def test_an_entirely_empty_stats_payload_still_counts_from_zero():
    """A payload that parsed but carries nothing is a fetch that half failed;
    the grid still has to come out on the grid."""
    markup = stats.render({}, {"stats": {"updated": "2026-01-01"}}, c.LIGHT)
    assert said(markup, "contributions")         # no year to name
    assert said(markup, "0%")                    # no divide by zero either
    assert height_of(markup) % c.ROW == 0


def test_the_chart_is_optional():
    without = stats.render({}, {"stats": {**STATS, "languages": {}}}, c.LIGHT)
    assert said(without, "no language data")[1] == stats.BAR_Y0 + 10
    assert "No language data was recorded." in desc_of(without)
    assert height_of(without) % c.ROW == 0
    assert height_of(without) < height_of(stats.render({}, {"stats": STATS},
                                                       c.LIGHT))


def test_a_language_with_no_bytes_is_not_charted():
    """GitHub occasionally reports a zero-byte language; it would divide the
    chart by nothing and draw a bar nobody can see."""
    markup = stats.render({}, {"stats": {**STATS, "languages": {"Nim": 0}}},
                          c.LIGHT)
    assert "Nim" not in c.visible(markup)
    assert said(markup, "no language data")


def test_markup_in_a_language_name_is_escaped():
    markup = stats.render({}, {"stats": {**STATS, "languages": {"<b>": 10}}},
                          c.LIGHT)
    assert "<b>" not in markup and "&lt;b&gt;" in markup


def test_the_panel_is_deterministic(markup):
    assert stats.render({}, {"stats": STATS}, c.LIGHT) == markup
