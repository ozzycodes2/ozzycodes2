"""Tests for the counter grid."""
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

TEXT = re.compile(
    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" fill="([^"]+)" font-family="[^"]*"'
    r' font-size="(\d+)"([^>]*)>([^<]*)</text>')


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


# --- frame -----------------------------------------------------------------

def test_the_slice_height_lands_on_the_grid_with_the_frame_left_open(markup):
    """A height off the 40px pitch would shift every slice below it, and only
    the header and footer cap the frame."""
    assert height_of(markup) % c.ROW == 0
    rails = re.search(r'<path d="([^"]*)" fill="none"', markup).group(1)
    assert rails == f"M{c.FRAME_L} {height_of(markup)}V0M{c.FRAME_R} 0V{height_of(markup)}"


def test_the_slice_ends_a_padding_below_the_second_row_of_cells(markup):
    """The grid is now the whole panel, so the last rule sets the height."""
    assert height_of(markup) == c.to_grid(
        stats.GRID_Y + 2 * stats.GRID_PITCH + stats.PAD_BELOW)


def test_nothing_is_drawn_outside_the_content_column(markup):
    for x in re.findall(r'<(?:text|rect|line) x1?="([\d.]+)"', markup):
        assert c.MARGIN <= float(x) <= c.CONTENT_R
    for x2 in re.findall(r'<line [^>]*x2="([\d.]+)"', markup):
        assert float(x2) <= c.CONTENT_R


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


# --- colour and motion -----------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_accent_is_spent_once_and_never_on_a_word(theme):
    """Six counters are a set of equals and none of them is the panel's answer,
    so the accent is left on the stroke that indexes the section. The one value
    worth marking here was the leading language, and it marks a ray in
    `~/stack` now."""
    body = stats.render({}, {"stats": STATS}, theme).split("</style>")[1]
    assert body.count(theme.accent) == 1
    assert (f'<line x1="{c.TEXT_X}" y1="{stats.HEAD_Y + 14}" '
            f'x2="{c.TEXT_X + 120}" y2="{stats.HEAD_Y + 14}" '
            f'stroke="{theme.accent}" stroke-width="2"') in body
    assert theme.accent not in [t[2] for t in texts(body)]


def test_nothing_in_the_panel_fades_in(markup):
    """GitHub paints a rendered SVG at frame zero, so a staggered fade-in is
    just a panel that arrives blank."""
    assert "animation-delay" not in markup
    assert 'class="ln"' not in markup


def test_the_two_themes_differ_in_nothing_but_their_polarised_roles():
    """readme.py pairs them in one <picture> under a single alt text, so any
    difference in geometry would show as a jump when the scheme flips.

    The accent is left standing rather than substituted: it is one value across
    both polarities, so the two skeletons agreeing with the literal hex still
    in them is what proves the brand hue does not follow the system setting.
    """
    light, dark = (stats.render({}, {"stats": STATS}, t) for t in c.THEMES)

    def skeleton(svg, theme):
        out = svg.split("</style>")[1]
        for role in ("canvas", "ink", "surface", "dim", "faint", "hairline"):
            out = out.replace(getattr(theme, role), role.upper())
        return out

    assert skeleton(light, c.LIGHT) == skeleton(dark, c.DARK)
    assert c.LIGHT.accent in skeleton(light, c.LIGHT)
    assert light != dark


# --- accessibility and degrading -------------------------------------------

def test_desc_spells_out_every_number_it_draws(markup):
    desc = desc_of(markup)
    for fragment in ("1,174 contributions in 2026",
                     "372 of 423 pull requests merged",
                     "29 repositories touched",
                     "longest streak 6 days"):
        assert fragment in desc, fragment
    assert "language" not in desc              # `~/stack` carries the mix now


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


def test_the_language_payload_no_longer_reaches_this_panel(markup):
    """It is drawn in `~/stack`. A language left in the markup here would be the
    old chart half-ported, which renders as a stray label over the grid."""
    for mix in ({}, {"Nim": 0}, {"<b>": 10}):
        other = stats.render({}, {"stats": {**STATS, "languages": mix}}, c.LIGHT)
        assert other == markup


def test_the_panel_is_deterministic(markup):
    assert stats.render({}, {"stats": STATS}, c.LIGHT) == markup
