"""Tests for the isometric contribution skyline."""
import datetime
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import city


def calendar(counts, start="2026-04-06"):
    """One entry per consecutive day from `start` (a Monday)."""
    day = datetime.date.fromisoformat(start)
    return [[(day + datetime.timedelta(days=i)).isoformat(), n]
            for i, n in enumerate(counts)]


# --- buckets ---------------------------------------------------------------

def test_thresholds_ignore_quiet_days():
    assert city.thresholds_for([0, 0, 0, 1, 2, 3, 4]) == city.thresholds_for([1, 2, 3, 4])


def test_thresholds_on_all_quiet_calendar():
    assert city.thresholds_for([0, 0, 0]) == [1, 2, 3, 4]


def test_thresholds_are_non_decreasing():
    cuts = city.thresholds_for(list(range(1, 100)))
    assert cuts == sorted(cuts)


def test_one_huge_day_does_not_flatten_the_rest():
    """A quartile split keeps ordinary days spread across buckets."""
    counts = [1, 2, 3, 4, 5, 6, 7, 8, 500]
    cuts = city.thresholds_for(counts)
    levels = {city.level(n, cuts) for n in counts if n}
    assert len(levels) >= 4, f"expected a spread of buckets, got {levels}"


def test_level_of_zero_is_ground():
    assert city.level(0, [1, 2, 3, 4]) == 0


def test_level_is_clamped_to_top_bucket():
    assert city.level(10_000, [1, 2, 3, 4]) == 4


def test_level_is_monotonic():
    cuts = [2, 5, 9, 20]
    levels = [city.level(n, cuts) for n in range(1, 40)]
    assert levels == sorted(levels)


# --- grid ------------------------------------------------------------------

@pytest.mark.parametrize("weeks", [4, 13, 26, 53, 120])
def test_grid_never_exceeds_the_reserved_band(weeks):
    """The band is what the panel reserves; overshooting it would collide
    with the legend below."""
    assert city.Grid(weeks, 800, 400).depth <= 400 + 0.01


def test_grid_tiles_grow_as_the_window_shrinks():
    assert city.Grid(26, 800, 400).tile_w > city.Grid(53, 800, 400).tile_w


@pytest.mark.parametrize("weeks", [4, 13, 26, 53, 120])
def test_grid_keeps_the_diamond_inside_its_width(weeks):
    """The east and west tiles reach half a tile past their centres."""
    width = 800
    grid = city.Grid(weeks, width, 400)
    east = grid.west + (weeks - 1) * grid.tile_w / 2 + grid.tile_w / 2
    assert east <= width + 0.01
    assert grid.west - grid.tile_w / 2 >= -0.01


def test_grid_projection_places_origin_at_the_west_corner():
    grid = city.Grid(10, 800, 400)
    x, y = grid.project(0, 0, 100, 200)
    assert (x, y) == (100, 200)


def test_grid_projection_moves_right_and_down_with_weeks():
    grid = city.Grid(10, 800, 400)
    x1, y1 = grid.project(0, 0, 0, 0)
    x2, y2 = grid.project(1, 0, 0, 0)
    assert x2 > x1 and y2 > y1


def test_grid_projection_moves_left_and_down_with_weekdays():
    grid = city.Grid(10, 800, 400)
    x1, y1 = grid.project(0, 0, 0, 0)
    x2, y2 = grid.project(0, 1, 0, 0)
    assert x2 < x1 and y2 > y1


def test_building_draws_three_faces():
    grid = city.Grid(26, 800, 400)
    assert grid.building(100, 100, 30, 3).count("<path") == 3


def test_ground_tile_is_a_closed_diamond():
    grid = city.Grid(26, 800, 400)
    assert grid.ground_tile(100, 100).count("Z") == 1


def test_windows_skip_single_storey_buildings():
    grid = city.Grid(26, 800, 400)
    assert grid.windows(100, 100, 5, 4) == ""


def test_windows_appear_on_tall_buildings():
    grid = city.Grid(26, 800, 400)
    assert "<rect" in grid.windows(100, 200, 58, 4)


def test_windows_skip_tiny_tiles():
    """At a 365-day window the tiles are too small to carry legible glass."""
    assert city.Grid(400, 800, 400).windows(100, 200, 58, 4) == ""


# --- layout ----------------------------------------------------------------

def test_layout_puts_monday_on_row_zero():
    cells, _ = city.layout(calendar([1]), None)
    assert cells[0][1] == 0


def test_layout_advances_a_column_each_week():
    cells, weeks = city.layout(calendar([1] * 14), None)
    assert weeks == 2
    assert cells[7][0] == 1


def test_layout_trims_to_the_window():
    cells, _ = city.layout(calendar([1] * 100), window_days=14)
    assert len(cells) == 14


def test_layout_of_empty_calendar():
    assert city.layout([], 180) == ([], 0)


# --- render ----------------------------------------------------------------

def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def test_render_height_is_on_the_grid():
    svg = city.render({}, {"calendar": calendar([3] * 180)})
    assert height_of(svg) % c.ROW == 0


def test_render_height_is_stable_across_windows():
    data = {"calendar": calendar([3] * 365)}
    short = city.render({"city": {"window_days": 180}}, data)
    long = city.render({"city": {"window_days": 365}}, data)
    assert height_of(short) == height_of(long)


def test_render_reports_real_numbers_in_the_description():
    svg = city.render({"city": {"window_days": 7}},
                      {"calendar": calendar([1, 0, 5, 0, 0, 2, 0])})
    desc = re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)
    assert "8 contributions" in desc
    assert "3 active days" in desc
    assert "busiest" in desc


def test_render_without_calendar_degrades_instead_of_raising():
    svg = city.render({}, {})
    assert "no contribution data" in svg
    assert height_of(svg) % c.ROW == 0


def test_render_with_an_all_quiet_calendar():
    svg = city.render({"city": {"window_days": 14}}, {"calendar": calendar([0] * 14)})
    assert height_of(svg) % c.ROW == 0


def test_render_is_deterministic():
    """The starfield must not reshuffle, or the daily job commits noise."""
    data = {"calendar": calendar([2, 0, 7] * 60)}
    assert city.render({}, data) == city.render({}, data)


def test_render_draws_one_ground_tile_per_day():
    days = 30
    svg = city.render({"city": {"window_days": days}}, {"calendar": calendar([1] * days)})
    assert svg.count(f'fill="{city.GROUND_FILL}"') == days


def test_render_escapes_nothing_unbalanced():
    svg = city.render({"city": {"window_days": 30}}, {"calendar": calendar([4] * 30)})
    assert svg.count("<svg") == svg.count("</svg") == 1


def test_render_window_falls_back_to_a_year():
    svg = city.render({}, {"calendar": calendar([1] * 365)})
    assert "--last 365d" in svg
