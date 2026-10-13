"""Tests for the shared frame primitives: relative dates and sliced rails."""
import datetime
import re

import pytest

from tools.profile import console as c

NOW = datetime.datetime(2026, 10, 12, 12, 0, tzinfo=datetime.timezone.utc)


def at(**delta):
    return (NOW - datetime.timedelta(**delta)).isoformat().replace("+00:00", "Z")


# --- ago -------------------------------------------------------------------

@pytest.mark.parametrize("when", [None, "", "garbage", "2026-13-45", 7, []])
def test_ago_returns_empty_for_anything_unusable(when):
    assert c.ago(when, NOW) == ""


@pytest.mark.parametrize("delta,expected", [
    ({"seconds": 5}, "just now"),
    ({"seconds": 89}, "just now"),
    ({"seconds": 120}, "2 minutes ago"),
    ({"minutes": 59}, "59 minutes ago"),
    ({"minutes": 60}, "1 hour ago"),
    ({"hours": 23}, "23 hours ago"),
    ({"hours": 24}, "1 day ago"),
    ({"days": 30}, "30 days ago"),
    ({"days": 31}, "1 month ago"),
    ({"days": 300}, "9 months ago"),
    ({"days": 364}, "11 months ago"),
    ({"days": 366}, "1 year ago"),
    ({"days": 2600}, "7 years ago"),
])
def test_ago_rounds_to_one_coarse_unit(delta, expected):
    assert c.ago(at(**delta), NOW) == expected


@pytest.mark.parametrize("delta", [
    {"minutes": 2}, {"hours": 1}, {"days": 1}, {"days": 32}, {"days": 370},
    {"days": 2600},
])
def test_ago_agrees_in_number(delta):
    n, unit, _ = c.ago(at(**delta), NOW).split()
    assert unit.endswith("s") == (n != "1"), (n, unit)


def test_ago_treats_a_naive_timestamp_as_utc():
    naive = (NOW - datetime.timedelta(days=40)).replace(tzinfo=None).isoformat()
    assert c.ago(naive, NOW) == "1 month ago"


def test_ago_does_not_count_backwards_for_a_future_timestamp():
    assert c.ago(at(days=-5), NOW) == "just now"


def test_ago_defaults_to_the_current_clock():
    assert c.ago(datetime.datetime.now(datetime.timezone.utc).isoformat()) == "just now"


# --- slice geometry --------------------------------------------------------

def bare(height=80, **kw):
    return c.slice_svg(height, "", title="t", desc="d", **kw)


def rect(markup):
    """The x/width of the slice's background rect."""
    m = re.search(r'<rect x="(-?\d+)" y="-?\d+" width="(\d+)"', markup)
    return int(m.group(1)), int(m.group(2))


def glow_path(markup):
    return re.search(r'<path d="([^"]*)"[^>]*filter="url\(#glow\)"', markup).group(1)


def edge_path(markup):
    return re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]*" stroke-width="{c.EDGE_W}"',
                     markup).group(1)


def test_height_must_sit_on_the_grid():
    with pytest.raises(ValueError, match="multiple"):
        bare(90)


def test_unknown_rails_value_is_rejected():
    with pytest.raises(ValueError, match="rails"):
        bare(rails="middle")


def test_the_rails_snap_to_whole_pixels_in_every_slice():
    """Each slice is a separate file rasterised on its own.

    A rail whose stroke edges fall mid-unit can round one way in one slice and
    the other way in the next, which shows up as the frame stepping sideways at
    the seam. Even width on an integer centre line, plus the rendering hint.
    """
    assert c.EDGE_W % 2 == 0
    assert c.MARGIN % 1 == 0
    for markup in (bare(), bare(width=440, rails="left")):
        assert 'shape-rendering="crispEdges"' in markup


def test_default_slice_is_unchanged_by_the_new_parameters():
    """Existing panels pass neither width nor rails and must be untouched."""
    markup = bare()
    assert f'width="{c.W}" height="80"' in markup
    assert rect(markup) == (c.FRAME_L, c.FRAME_R - c.FRAME_L)
    assert f"M{c.FRAME_L} 0V80" in markup and f"M{c.FRAME_R} 0V80" in markup


def test_left_half_keeps_its_outer_rail_and_runs_flush_to_the_seam():
    markup = bare(width=440, rails="left")
    assert 'width="440"' in markup
    assert rect(markup) == (c.MARGIN, 440 - c.MARGIN)
    assert edge_path(markup) == f"M{c.MARGIN} 0V80"


def test_right_half_mirrors_the_left():
    markup = bare(width=440, rails="right")
    assert rect(markup) == (0, 440 - c.MARGIN)
    assert edge_path(markup) == f"M{440 - c.MARGIN} 0V80"


def test_the_two_halves_tile_into_one_full_width_row():
    left, right = bare(width=440, rails="left"), bare(width=440, rails="right")
    lx, lw = rect(left)
    rx, rw = rect(right)
    assert lx == c.FRAME_L
    assert lx + lw == 440                       # left background ends at the seam
    assert 440 + rx == 440                      # right background starts at it
    assert 440 + rx + rw == c.FRAME_R


def test_single_rail_slice_still_gets_a_glow_region():
    """A lone vertical has a zero-width bbox, which silently kills #glow."""
    glow = glow_path(bare(width=440, rails="left"))
    assert f"H{440}" in glow, glow
    xs = [int(n) for n in re.findall(r"[MH](-?\d+)", glow)]
    assert max(xs) > min(xs)


def test_half_width_slices_keep_the_grid_in_step():
    """The right half's origin must land on a grid line or the pattern shifts."""
    assert (c.W // 2) % c.ROW == 0


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_a_half_slice_brackets_only_its_own_corner(edge):
    left = bare(width=440, rails="left", **{edge: True})
    right = bare(width=440, rails="right", **{edge: True})
    assert f"M{c.MARGIN - 7} " in left
    assert f"H{440 - c.MARGIN + 7}" not in left      # not the neighbour's corner
    assert f"H{440 - c.MARGIN + 7}" in right
    assert f"M{c.MARGIN - 7} " not in right


def test_a_middle_slice_draws_no_corner_brackets():
    assert "><path" not in bare(width=440, rails="left").split("<g fill=")[-1]
