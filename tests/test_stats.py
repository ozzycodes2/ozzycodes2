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
    "languages": {"TypeScript": 508003, "Python": 417967, "Java": 204747,
                  "Swift": 163026, "JavaScript": 130812, "C++": 83684,
                  "CSS": 80999, "Shell": 39980},
}


@pytest.fixture(scope="module")
def markup():
    return stats.render({}, {"stats": STATS})


@pytest.fixture(scope="module")
def shown(markup):
    return c.visible(markup)


def desc_of(markup):
    return re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)


def bars(markup):
    """(x, width) of each gradient-filled bar, in draw order."""
    return [(float(x), float(w)) for x, w in re.findall(
        r'<rect x="([\d.]+)" y="[\d.-]+" width="([\d.]+)" height="10" fill="url\(#lang\)"/>',
        markup)]


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert int(re.search(r'height="(\d+)"', markup).group(1)) % c.ROW == 0
    edges = re.search(r'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="1.2"',
                      markup).group(1)
    assert "H" not in edges            # neither top=True nor bottom=True


def test_nothing_is_drawn_outside_the_content_column(markup):
    for x in re.findall(r'<(?:text|rect|line) x1?="([\d.]+)"', markup):
        assert c.MARGIN <= float(x) <= stats.COL_R


# --- counters --------------------------------------------------------------

def test_every_requested_counter_is_drawn_with_thousands_separators(shown):
    for label, value in (("CONTRIBUTIONS 2026", "1,174"), ("ALL TIME", "1,441"),
                         ("PRIVATE THIS YEAR", "1,122"), ("PRS MERGED", "372"),
                         ("LONGEST STREAK", "6"), ("FOLLOWERS", "5")):
        assert label in shown and value in shown


def test_the_streak_is_given_a_unit(shown):
    assert "days" in shown


def test_stars_and_forks_are_never_drawn(shown):
    """Both are zero on this account, and a nought reads as neglect."""
    assert "STARS" not in shown and "FORKS" not in shown


def test_counters_sit_in_three_even_columns(markup):
    xs = [float(x) for x in re.findall(
        rf'<text x="([\d.]+)" y="\d+" class="faint" letter-spacing="1" '
        rf'style="font-size:{stats.LABEL_FS}px">', markup)]
    columns = sorted(set(xs[:6]))
    assert len(columns) == stats.COLS
    steps = [b - a for a, b in zip(columns, columns[1:])]
    assert len(set(steps)) == 1
    assert columns[0] == c.TEXT_X


def test_the_summary_line_states_the_join_date_and_the_repo_split(shown):
    assert "member since August 2016" in shown
    assert "5 of 11 repos public" in shown


@pytest.mark.parametrize("raw", [None, "", "not-a-date", 12345])
def test_an_unusable_join_date_is_dropped_not_fatal(raw):
    markup = stats.render({}, {"stats": {**STATS, "created_at": raw}})
    assert "member since" not in c.visible(markup)
    assert "repos public" in c.visible(markup)


# --- language chart --------------------------------------------------------

def test_only_the_top_six_languages_are_charted(shown):
    assert "C++" in shown                        # sixth by bytes
    assert "CSS" not in shown and "Shell" not in shown


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
        r'text-anchor="end" class="dim" style="font-size:12px">([\d.]+)%', markup)]
    assert len(pcts) == stats.TOP_N
    assert sum(pcts) == pytest.approx(100, abs=0.3)
    assert pcts[0] == pytest.approx(100 * top[0] / sum(top), abs=0.05)


def test_the_bar_gradient_runs_cyan_to_magenta_across_the_chart(markup):
    gradient = re.search(r'<linearGradient id="lang"[^>]*>(.*?)</linearGradient>',
                         markup, re.S).group(0)
    assert 'gradientUnits="userSpaceOnUse"' in gradient
    assert f'x1="{stats.BAR_X}"' in gradient and f'x2="{stats.BAR_R}"' in gradient
    assert c.ACCENT in gradient and c.ALT in gradient


def test_a_long_language_name_is_truncated_to_its_column():
    markup = stats.render({}, {"stats": {**STATS, "languages": {"A" * 40: 10}}})
    name = re.search(r'<text x="52" y="318" class="fg" style="font-size:13px">([^<]*)<',
                     markup).group(1)
    assert name.endswith("…") and len(name) <= 13


def test_languages_are_optional(markup):
    without = stats.render({}, {"stats": {**STATS, "languages": {}}})
    assert "no language data" in c.visible(without)
    assert "none recorded" in desc_of(without)
    assert int(re.search(r'height="(\d+)"', without).group(1)) % c.ROW == 0


# --- accessibility and degrading -------------------------------------------

def test_desc_spells_out_every_number_it_draws(markup):
    desc = desc_of(markup)
    for fragment in ("updated 2026-10-12", "1,174 contributions in 2026",
                     "1,441 all time", "1,122 of them in private",
                     "372 pull requests merged", "longest streak 6 days",
                     "5 followers", "member since August 2016",
                     "5 of 11 repos public", "TypeScript 33.7%", "C++ 5.5%"):
        assert fragment in desc, fragment


@pytest.mark.parametrize("data", [{}, {"stats": None}, {"stats": {}}])
def test_missing_stats_render_one_short_panel_instead_of_raising(data):
    markup = stats.render({}, data)
    height = int(re.search(r'height="(\d+)"', markup).group(1))
    assert height % c.ROW == 0 and height <= 120
    assert "no stats available" in c.visible(markup)
    assert "No GitHub statistics are available." in markup


def test_an_entirely_empty_stats_payload_still_counts_from_zero():
    markup = stats.render({}, {"stats": {"updated": "2026-01-01"}})
    assert "CONTRIBUTIONS" in c.visible(markup)
    assert "0" in c.visible(markup)
