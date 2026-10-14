"""Tests for the counter grid and language chart."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import stats

STATS = {
    "updated": "2026-10-12", "year": 2026, "created_at": "2016-08-28T00:35:26Z",
    "followers": 5, "prs": 423, "prs_merged": 372, "repos": 11, "repos_public": 5,
    "stars": 0, "forks": 0, "contributions_year": 1174, "contributions_all": 1441,
    "private_year": 1122, "streak_longest": 6,
    "repos_contributed": 29, "repos_contributed_private": 26,
    "repos_contributed_org": 23, "orgs": 2,
    "languages": {"TypeScript": 508003, "Python": 417967, "Java": 204747,
                  "Swift": 163026, "JavaScript": 130812, "C++": 83684,
                  "CSS": 80999, "Shell": 39980},
}

ROW_Y0 = 320          # first language baseline
ROW_PITCH = 28


@pytest.fixture(scope="module")
def markup():
    return stats.render({}, {"stats": STATS}, c.LIGHT)


@pytest.fixture(scope="module")
def shown(markup):
    return c.visible(markup)


def desc_of(markup):
    return re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)


def layers(markup):
    """(x, width, fill) of every bar rect — trough and fill alike, in draw order.

    Both layers are the same capsule geometry, so the regex pins the rounding
    and the two are told apart by their tone.
    """
    return [(float(x), float(w), fill) for x, w, fill in re.findall(
        rf'<rect x="([\d.]+)" y="[\d.-]+" width="([\d.]+)" height="{stats.BAR_H}" '
        rf'rx="{stats.BAR_H // 2}" fill="(#[0-9a-f]{{6}})"/>', markup)]


def bars(markup, theme=c.LIGHT):
    """(x, width) of each solid bar, in draw order."""
    return [(x, w) for x, w, fill in layers(markup) if fill != theme.sunken]


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert int(re.search(r'height="(\d+)"', markup).group(1)) % c.ROW == 0
    edges = re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="{c.RAIL_W}"',
                      markup).group(1)
    assert "H" not in edges            # neither top=True nor bottom=True


def test_nothing_is_drawn_outside_the_content_column(markup):
    for x in re.findall(r'<(?:text|rect|line) x1?="([\d.]+)"', markup):
        assert c.MARGIN <= float(x) <= stats.COL_R


# --- counters --------------------------------------------------------------

def test_every_requested_counter_is_drawn_with_thousands_separators(shown):
    for label, value in (("CONTRIBUTIONS 2026", "1,174"), ("ALL TIME", "1,441"),
                         ("PRIVATE THIS YEAR", "1,122"), ("PRS MERGED", "372"),
                         ("LONGEST STREAK", "6"), ("REPOS CONTRIBUTED", "29")):
        assert label in shown and value in shown


def test_the_streak_is_given_a_unit(shown):
    assert "days" in shown


def test_stars_and_forks_are_never_drawn(shown):
    """Both are zero on this account, and a nought reads as neglect."""
    assert "STARS" not in shown and "FORKS" not in shown


def test_counters_sit_in_three_even_columns(markup):
    xs = [float(x) for x in re.findall(
        r'<text x="([\d.]+)" y="\d+" class="caption dim">', markup)]
    columns = sorted(set(xs[:6]))
    assert len(columns) == stats.COLS
    steps = [b - a for a, b in zip(columns, columns[1:])]
    assert len(set(steps)) == 1
    assert columns[0] == c.TEXT_X


def test_a_counter_value_takes_the_shared_heading_step(markup):
    """Inventing a counter-sized step for this panel alone would put the
    console off the type scale it shares with the rest of the system."""
    for value in ("1,174", "1,441", "1,122", "372", "29"):
        assert f'class="heading ink">{value}' in markup
    assert 'style="font-size' not in markup       # no bespoke counter step


def test_a_counter_label_and_its_suffix_take_the_caption_step(markup):
    assert '<text x="52" y="86" class="caption dim">CONTRIBUTIONS 2026</text>' in markup
    assert '<tspan class="caption dim" dx="6"> days</tspan>' in markup


def test_the_summary_line_states_the_join_date_and_the_repo_split(shown):
    assert "member since August 2016" in shown
    assert "5 of 11 repos public" in shown


@pytest.mark.parametrize("raw", [None, "", "not-a-date", 12345])
def test_an_unusable_join_date_is_dropped_not_fatal(raw):
    markup = stats.render({}, {"stats": {**STATS, "created_at": raw}}, c.LIGHT)
    assert "member since" not in c.visible(markup)
    assert "repos public" in c.visible(markup)


# --- the console's one accent ----------------------------------------------

def test_the_heading_counter_is_the_bare_update_stamp(markup):
    assert (f'<text x="{stats.COL_R}" y="{stats.HEAD_Y}" text-anchor="end" '
            f'class="mono dim">2026-10-12</text>') in markup
    assert "[" not in c.visible(markup)


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_live_dot_is_the_only_accent_in_the_panel(theme):
    """The accent is state, not decoration: one pulsing dot for the one fact on
    the page that is about right now, and nothing else reaches for it."""
    # base_css declares `.accent` in every panel, so only the body is evidence.
    body = stats.render({}, {"stats": STATS}, theme).split("</style>")[1]
    assert body.count(theme.accent) == 1
    assert "accent" not in body                  # nothing takes the class either
    dot = re.search(r'<circle class="dot" cx="([\d.]+)" cy="[\d.-]+" r="4" '
                    rf'fill="{re.escape(theme.accent)}"/>', body)
    assert dot, "the live dot is missing"
    stamp_w = len(STATS["updated"]) * c.MONO.size * c.MONO_ADVANCE
    assert c.MARGIN < float(dot.group(1)) + 4 <= stats.COL_R - stamp_w


# --- language chart --------------------------------------------------------

def test_only_the_top_six_languages_are_charted(shown):
    assert "C++" in shown                        # sixth by bytes
    assert "CSS" not in shown and "Shell" not in shown


def test_language_rows_start_below_the_divider_on_a_fixed_pitch(markup):
    ys = [int(y) for y in re.findall(
        rf'<text x="{stats.COL_L}" y="(\d+)" class="mono ink">', markup)]
    assert len(ys) == stats.TOP_N
    assert ys[0] == ROW_Y0
    assert [b - a for a, b in zip(ys, ys[1:])] == [ROW_PITCH] * (stats.TOP_N - 1)


def test_the_name_column_is_wide_enough_for_the_mono_face(markup):
    """Names are set in mono, so the column is a character count: thirteen
    glyphs at the mono step, plus the gap to the bar."""
    assert stats.NAME_W >= 13 * c.MONO.size * c.MONO_ADVANCE
    assert stats.BAR_X == stats.COL_L + stats.NAME_W + 8


def test_bars_are_proportional_to_the_largest(markup):
    drawn = bars(markup)
    assert len(drawn) == stats.TOP_N
    span = stats.BAR_R - stats.BAR_X
    assert drawn[0][1] == span                   # TypeScript is the longest
    expected = STATS["languages"]["Python"] / STATS["languages"]["TypeScript"]
    assert drawn[1][1] == pytest.approx(span * expected, abs=0.1)
    assert drawn == sorted(drawn, key=lambda b: -b[1])


def test_no_bar_runs_past_the_percentage_column(markup):
    for x, w in bars(markup):
        assert x == stats.BAR_X
        assert x + w <= stats.BAR_R


def test_percentages_are_shares_of_the_charted_total(markup):
    top = sorted(STATS["languages"].values(), reverse=True)[:stats.TOP_N]
    pcts = [float(p) for p in re.findall(
        r'text-anchor="end" class="mono dim">([\d.]+)%', markup)]
    assert len(pcts) == stats.TOP_N
    assert sum(pcts) == pytest.approx(100, abs=0.3)
    assert pcts[0] == pytest.approx(100 * top[0] / sum(top), abs=0.05)


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_every_bar_sits_in_a_capsule_trough_of_the_full_span(theme):
    troughs = [(x, w) for x, w, fill in layers(stats.render({}, {"stats": STATS}, theme))
               if fill == theme.sunken]
    assert len(troughs) == stats.TOP_N
    for x, w in troughs:
        assert (x, w) == (stats.BAR_X, stats.BAR_R - stats.BAR_X)


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_every_bar_is_one_solid_tone_mixed_from_the_themes_ink(theme):
    """No gradient and no second colour: the bar is the ink pulled back toward
    the canvas, which is the only shading this palette has."""
    markup = stats.render({}, {"stats": STATS}, theme)
    assert "linearGradient" not in markup and "fill-opacity" not in markup
    tones = {fill for _, _, fill in layers(markup)}
    assert len(tones) == 2                       # the trough and the fill
    fill, = tones - {theme.sunken}
    assert fill in {c.mix(theme.ink, theme.canvas, t / 100) for t in range(1, 101)}


def test_a_long_language_name_is_truncated_to_its_column():
    markup = stats.render({}, {"stats": {**STATS, "languages": {"A" * 40: 10}}}, c.LIGHT)
    name = re.search(rf'<text x="{stats.COL_L}" y="{ROW_Y0}" class="mono ink">([^<]*)<',
                     markup).group(1)
    assert name.endswith("…") and len(name) <= 13


def test_languages_are_optional(markup):
    without = stats.render({}, {"stats": {**STATS, "languages": {}}}, c.LIGHT)
    assert "no language data" in c.visible(without)
    assert "none recorded" in desc_of(without)
    assert int(re.search(r'height="(\d+)"', without).group(1)) % c.ROW == 0


# --- accessibility and degrading -------------------------------------------

def test_desc_spells_out_every_number_it_draws(markup):
    desc = desc_of(markup)
    for fragment in ("updated 2026-10-12", "1,174 contributions in 2026",
                     "1,441 all time", "1,122 of them in private",
                     "372 pull requests merged", "longest streak 6 days",
                     "29 repositories contributed to",
                     "member since August 2016", "5 of 11 repos public",
                     "2 organizations", "TypeScript 33.7%", "C++ 5.5%"):
        assert fragment in desc, fragment


@pytest.mark.parametrize("data", [{}, {"stats": None}, {"stats": {}}])
def test_missing_stats_render_one_short_panel_instead_of_raising(data):
    markup = stats.render({}, data, c.LIGHT)
    height = int(re.search(r'height="(\d+)"', markup).group(1))
    assert height % c.ROW == 0 and height <= 120
    assert "no stats available" in c.visible(markup)
    assert "No GitHub statistics are available." in markup


def test_an_entirely_empty_stats_payload_still_counts_from_zero():
    markup = stats.render({}, {"stats": {"updated": "2026-01-01"}}, c.LIGHT)
    assert "CONTRIBUTIONS" in c.visible(markup)
    assert "0" in c.visible(markup)


# --- degrading to public-only data -----------------------------------------

def test_private_counter_yields_to_followers_when_there_is_no_private_work():
    """A counter reading 0 would assert no private work exists, not that the
    token could not see it."""
    public_only = dict(STATS, private_year=0, followers=5)
    shown = c.visible(stats.render({}, {"stats": public_only}, c.LIGHT))
    assert "PRIVATE THIS YEAR" not in shown
    assert "FOLLOWERS" in shown


def test_desc_omits_the_private_clause_when_the_count_is_zero():
    desc = desc_of(stats.render({}, {"stats": dict(STATS, private_year=0)}, c.LIGHT))
    assert "private repositories" not in desc
    assert "1,441 all time, 372 pull requests merged" in desc


def test_private_counter_returns_when_private_work_is_visible():
    shown = c.visible(stats.render({}, {"stats": STATS}, c.LIGHT))
    assert "PRIVATE THIS YEAR" in shown and "FOLLOWERS" not in shown
