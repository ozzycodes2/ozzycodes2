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


def test_building_faces_are_outlined():
    """Unstroked neighbours of equal height merge into one unreadable slab."""
    grid = city.Grid(26, 800, 400)
    assert grid.building(100, 100, 30, 3).count(f'stroke="{city.MORTAR}"') == 3


def test_ground_tile_is_a_closed_diamond():
    grid = city.Grid(26, 800, 400)
    assert grid.ground_tile(100, 100).count("Z") == 1


# --- windows ---------------------------------------------------------------

PANE_RE = re.compile(r'd="M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)Z"')


def panes(markup):
    """Each window as eight floats: the four corners, clockwise from top-left."""
    return [tuple(float(v) for v in m) for m in PANE_RE.findall(markup)]


def test_windows_skip_single_storey_buildings():
    grid = city.Grid(26, 800, 400)
    assert grid.windows(100, 100, 5, 4, 0, 0) == ""


def test_windows_appear_on_tall_buildings():
    grid = city.Grid(26, 800, 400)
    assert panes(grid.windows(100, 200, 58, 4, 0, 0))


def test_windows_skip_tiny_tiles():
    """At a 365-day window the tiles are too small to carry legible glass."""
    assert city.Grid(400, 800, 400).windows(100, 200, 58, 4, 0, 0) == ""


def test_window_tops_follow_the_gradient_of_the_wall_they_sit_on():
    """Both walls are sheared ±1/2; an upright rect would cross its own wall."""
    grid = city.Grid(26, 800, 400)
    # Coordinates are emitted at one decimal, so the gradient only survives to
    # about that.
    slopes = set()
    for ax, ay, bx, by, *_ in panes(grid.windows(400, 300, 58, 4, 0, 0)):
        slopes.add(round((by - ay) / (bx - ax), 1))
    assert slopes == {0.5, -0.5}


def test_window_sides_stay_vertical():
    """A sheared top edge, but the pane itself hangs plumb."""
    grid = city.Grid(26, 800, 400)
    for ax, ay, bx, by, cx, cy, dx, dy in panes(grid.windows(400, 300, 58, 4, 0, 0)):
        assert (cx, dx) == (bx, ax)
        assert round(cy - by, 1) == round(dy - ay, 1) == city.WIN_H


def depths(grid, xc, base, height):
    """(is_west, drop below the roofline) for each pane of one building.

    The roofline is read at the pane's own x rather than taken as a single y,
    which is the whole point of the measurement: both walls slope.
    """
    hw, hh = grid.tile_w / 2, grid.tile_h / 2
    top, out = base - height, []
    for ax, ay, bx, by, *_ in panes(grid.windows(xc, base, height, 4, 0, 0)):
        west = by > ay
        edge = top + (ax - xc + hw) / 2 if west else top + hh - (ax - xc) / 2
        out.append((west, round(ay - edge, 1)))
    return out


def test_window_rows_line_up_across_the_corner():
    """Storeys measured from each wall's own top edge, not from a shared y."""
    ds = depths(city.Grid(26, 800, 400), 400, 300, 58)
    west = {d for is_west, d in ds if is_west}
    assert west
    assert west == {d for is_west, d in ds if not is_west}


def test_no_window_overhangs_its_wall():
    height = 58
    for _, d in depths(city.Grid(26, 800, 400), 400, 300, height):
        assert 0 <= d and d + city.WIN_H <= height


def test_windows_are_identical_for_the_same_cell():
    grid = city.Grid(26, 800, 400)
    a = grid.windows(400, 300, 58, 4, 3, 2)
    assert a == grid.windows(400, 300, 58, 4, 3, 2)


def test_flicker_is_assigned_per_cell_not_per_sequence():
    """A hash of the coordinates, so one new day does not rewire the skyline."""
    grid = city.Grid(26, 800, 400)
    classes = re.findall(r'class="(fl\d)"', grid.windows(400, 300, 58, 4, 3, 2))
    assert classes
    assert classes == re.findall(r'class="(fl\d)"',
                                 grid.windows(999, 42, 58, 4, 3, 2))


def test_every_flicker_variant_is_defined():
    for i in range(city.FLICKERS):
        assert f".fl{i}{{animation:flick" in city.CITY_CSS


def test_jitter_is_order_independent():
    assert city._jitter(1, 2, 3) == city._jitter(1, 2, 3)
    assert city._jitter(1, 2, 3) != city._jitter(3, 2, 1)


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


def test_render_interleaves_windows_with_the_blocks_they_belong_to():
    """Batched into layers, every window drew over every wall.

    Far buildings' lights then showed through the blocks standing in front of
    them, as squares floating in open air.
    """
    svg = city.render({"city": {"window_days": 30}}, {"calendar": calendar([9] * 30)})
    walls = [m.start() for m in re.finditer(re.escape(f'stroke="{city.MORTAR}"'), svg)]
    lights = [m.start() for m in re.finditer(r'fill-opacity="0\.78"', svg)]
    assert walls and lights
    assert lights[0] < walls[-1], "windows all emitted after the last wall"


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


def test_render_ships_the_flicker_keyframes_and_the_motion_opt_out():
    svg = city.render({"city": {"window_days": 30}}, {"calendar": calendar([9] * 30)})
    assert "@keyframes flick" in svg
    assert re.search(r'class="fl\d"', svg)
    assert "prefers-reduced-motion" in svg
