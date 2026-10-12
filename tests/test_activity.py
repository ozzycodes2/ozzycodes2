"""Tests for the public event log."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import activity

EVENTS = [
    {"kind": "commit", "repo": "cc-powerline", "title": "chore: release 0.2.10",
     "at": "2026-08-26T17:51:27Z"},
    {"kind": "release", "repo": "cc-powerline", "title": "v0.1.2",
     "at": "2026-08-25T20:13:10Z"},
    {"kind": "commit", "repo": "a-very-long-repository-name",
     "title": "A commit subject far longer than the column can ever hold, going on and on",
     "at": "2019-07-25T23:41:02Z"},
]
DATA = {"activity": EVENTS, "stats": {"private_year": 1122}}


@pytest.fixture(scope="module")
def markup():
    return activity.render({}, DATA)


def rows(markup, cls):
    return re.findall(rf'class="{cls}"[^>]*>([^<]*)</text>', markup)


def desc_of(markup):
    return re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)


# --- rows ------------------------------------------------------------------

def test_one_row_per_event(markup):
    assert len(rows(markup, "wh")) == len(EVENTS)


def test_markers_are_coloured_by_kind(markup):
    assert 'class="ok"' in markup and "▲" in markup       # release, green
    assert markup.count('class="ac"') >= 2                # commits, cyan
    assert "●" in markup


def test_an_unknown_kind_falls_back_to_the_commit_marker():
    out = activity.render({}, {"activity": [{"kind": "wat", "repo": "r",
                                             "title": "t", "at": None}]})
    assert "●" in out and "▲" not in out


def test_a_long_title_is_truncated_with_an_ellipsis(markup):
    long = [t for t in rows(markup, "dim") if t.startswith("A commit subject")]
    assert long and long[0].endswith("…")
    assert len(long[0]) <= (activity.CONTENT_R - activity.REPO_X) // activity.CHAR


def test_a_short_title_is_left_alone(markup):
    assert "v0.1.2" in rows(markup, "dim")


def test_dates_are_relative_and_right_aligned(markup):
    assert 'text-anchor="end"' in markup
    assert "1 month ago" in markup and "7 years ago" in markup


def test_the_title_column_clears_the_longest_repo_name(markup):
    longest = max(len(ev["repo"]) for ev in EVENTS)
    title_x = int(re.search(rf'<text x="(\d+)" y="\d+" class="dim"', markup).group(1))
    assert title_x > activity.REPO_X + longest * activity.CHAR


def test_nothing_is_drawn_past_the_content_edge(markup):
    xs = [int(x) for x in re.findall(r'<text x="(\d+)"', markup)]
    assert max(xs) <= activity.CONTENT_R


# --- the private-work note -------------------------------------------------

def test_the_note_carries_the_private_contribution_count(markup):
    assert "1,122 private contributions" in markup
    assert "not listed here" in markup


def test_the_note_degrades_when_the_count_is_missing():
    out = activity.render({}, {"activity": EVENTS})
    assert "Private contributions are counted" in out
    assert "None" not in c.visible(out)


# --- shape and alt text ----------------------------------------------------

def test_height_sits_on_the_grid(markup):
    assert int(re.search(r'height="(\d+)"', markup).group(1)) % c.ROW == 0


def test_it_is_a_middle_slice(markup):
    """Only header and footer close the frame; this one keeps the rails open."""
    assert f'<rect x="{c.MARGIN}" y="0"' in markup


def test_desc_lists_every_event_it_draws(markup):
    desc = desc_of(markup)
    assert "3 recent public events" in desc
    for ev in EVENTS:
        assert ev["repo"] in desc
    assert "release" in desc and "1,122" in desc


# --- degrading -------------------------------------------------------------

@pytest.mark.parametrize("data", [{}, {"activity": []}, {"activity": None},
                                  {"activity": ["not a dict"]}])
def test_no_events_renders_one_line_not_an_empty_box(data):
    out = activity.render({}, data)
    assert "No public events in the fetched window." in out
    assert int(re.search(r'height="(\d+)"', out).group(1)) <= 160
    assert "no public events" in desc_of(out).lower()


def test_rows_tolerate_missing_fields():
    out = activity.render({}, {"activity": [{}]})
    assert "—" in out
