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


def test_building_faces_are_not_outlined():
    """At this tile size an outline reads as a black gap, not as an edge."""
    grid = city.Grid(26, 800, 400)
    assert "stroke" not in grid.building(100, 100, 30, 3)


def test_only_the_roof_carries_the_bucket():
    """Shading the walls too broke the mass into districts."""
    grid = city.Grid(26, 800, 400)
    for lvl in range(len(city.ROOFS)):
        markup = grid.building(100, 100, 30, lvl)
        assert f'fill="{city.ROOFS[lvl]}"' in markup
        assert f'fill="{city.WALL_L}"' in markup
        assert f'fill="{city.WALL_R}"' in markup


def test_height_rises_with_the_count_off_a_visible_floor():
    grid = city.Grid(26, 800, 400)
    assert grid.height_for(1, 60) >= city.MIN_STOREYS
    assert grid.height_for(60, 60) == pytest.approx(grid.max_h)
    assert grid.height_for(10, 60) < grid.height_for(30, 60)


def test_towers_stand_clear_of_their_own_footprint():
    """Below about twice the tile width a building reads as a lid, not a tower.

    This is what bounds `window_days` from below: the headroom is capped, so
    past roughly 26 weeks the tiles get wide enough to outgrow it.
    """
    for weeks in (26, 40, 53):
        grid = city.Grid(weeks, 800, 400)
        assert grid.max_h >= 2 * grid.tile_w


def test_ground_tile_is_a_closed_diamond():
    grid = city.Grid(26, 800, 400)
    assert grid.ground_tile(100, 100).count("Z") == 1


# --- windows ---------------------------------------------------------------

GLASS = re.compile(r'<path d="([^"]+)" fill="([^"]+)"')
PANE = re.compile(r"M([\d.-]+) ([\d.-]+)L([\d.-]+) ([\d.-]+)"
                  r"L([\d.-]+) ([\d.-]+)L([\d.-]+) ([\d.-]+)Z")


def panes(markup):
    """Every window as eight floats, from the batched paths they ship in.

    Steady panes are concatenated into one path per state, so the segments have
    to be split back out of the `d` attribute.
    """
    out = []
    for d, fill in GLASS.findall(markup):
        if fill not in (city.WIN_ON, city.WIN_ON_SIDE, city.WIN_OFF):
            continue
        out += [tuple(float(v) for v in m) for m in PANE.findall(d)]
    return out


def lit_markup(grid, **kw):
    """One building's windows, with enough storeys for every state to appear."""
    return grid.windows(400, 300, grid.max_h, kw.get("col", 0), kw.get("row", 0))


def test_windows_skip_single_storey_buildings():
    grid = city.Grid(26, 800, 400)
    assert grid.windows(100, 100, 5, 0, 0) == ""


def test_windows_appear_on_tall_buildings():
    assert panes(lit_markup(city.Grid(26, 800, 400)))


def test_windows_skip_tiny_tiles():
    """Past a year the tiles are too small to carry legible glass."""
    assert city.Grid(400, 800, 400).windows(100, 200, 58, 0, 0) == ""


def test_windows_are_glass_not_a_tint_of_the_roof():
    """The lit interior is the same on every building, whatever its bucket."""
    grid = city.Grid(26, 800, 400)
    fills = {fill for _, fill in GLASS.findall(lit_markup(grid))}
    assert fills & {city.WIN_ON, city.WIN_ON_SIDE}
    assert not fills & set(city.ROOFS)


def test_both_walls_are_glazed_and_the_east_one_is_dimmer():
    grid = city.Grid(26, 800, 400)
    fills = {fill for _, fill in GLASS.findall(lit_markup(grid))}
    assert {city.WIN_ON, city.WIN_ON_SIDE} <= fills


def test_window_bases_follow_the_gradient_of_the_wall_they_sit_on():
    """Both walls are sheared ±1/2; an upright rect would cross its own wall."""
    # Coordinates are emitted at one decimal, so the gradient only survives to
    # about that.
    slopes = {round((by - ay) / (bx - ax), 1)
              for ax, ay, bx, by, *_ in panes(lit_markup(city.Grid(26, 800, 400)))}
    assert slopes == {0.5, -0.5}


def test_window_sides_stay_vertical():
    """A sheared base, but the pane itself stands plumb."""
    grid = city.Grid(26, 800, 400)
    tall = grid.tile_w * city.WIN_H
    for ax, ay, bx, by, cx, cy, dx, dy in panes(lit_markup(grid)):
        assert (cx, dx) == (bx, ax)
        # Coordinates ship at one decimal, so the two sides can disagree by a
        # rounding step without the pane being out of true.
        assert by - cy == pytest.approx(tall, abs=0.15)
        assert ay - dy == pytest.approx(tall, abs=0.15)


def rises(grid):
    """(is_west, height above the base edge) for each pane of one building.

    The base edge is read at the pane's own x rather than taken as a single y,
    which is the whole point of the measurement: both walls slope.
    """
    xc, base, hw, hh = 400, 300, grid.tile_w / 2, grid.tile_h / 2
    out = []
    for ax, ay, bx, by, *_ in panes(lit_markup(grid)):
        west = by > ay
        edge = base + (ax - xc + hw) / 2 if west else base + hh - (ax - xc) / 2
        out.append((west, round(edge - ay, 1)))
    return out


def test_window_rows_line_up_across_the_corner():
    """Both walls stack off one ladder of storeys, each from its own base edge.

    Compared against the ladder rather than wall against wall: a storey whose
    panes all came up dark on one side contributes no row to measure there.
    """
    grid = city.Grid(26, 800, 400)
    pitch = grid.tile_w * city.WIN_PITCH
    rs = rises(grid)
    for _, r in rs:
        assert (r - 4) % pitch == pytest.approx(0, abs=0.15) or \
               (r - 4) % pitch == pytest.approx(pitch, abs=0.15)
    for want in (True, False):
        assert len({r for is_west, r in rs if is_west is want}) > 1


def test_no_window_overhangs_its_wall():
    grid = city.Grid(26, 800, 400)
    tall = grid.tile_w * city.WIN_H
    for _, r in rises(grid):
        assert 0 <= r and r + tall <= grid.max_h


def test_windows_are_identical_for_the_same_cell():
    grid = city.Grid(26, 800, 400)
    assert lit_markup(grid, col=3, row=2) == lit_markup(grid, col=3, row=2)


def test_window_state_is_hashed_per_cell_not_drawn_from_a_sequence():
    """So one new day does not relight every building and rewrite the panel."""
    grid = city.Grid(26, 800, 400)
    assert lit_markup(grid, col=3, row=2) != lit_markup(grid, col=4, row=2)


def test_some_windows_are_dark_and_some_are_failing():
    """A fully lit tower at 3am is a texture, not a building."""
    grid = city.Grid(26, 800, 400)
    seen = set()
    for col in range(12):
        markup = grid.windows(400, 300, grid.max_h, col, 0)
        seen |= {fill for _, fill in GLASS.findall(markup)}
        seen |= set(re.findall(r'class="(fl\d)"', markup))
    assert city.WIN_OFF in seen
    assert any(cls.startswith("fl") for cls in seen)


def test_every_animation_variant_is_defined():
    for i in range(city.VARIANTS):
        assert f".fl{i}{{animation:flick" in city.CITY_CSS
        assert f".tw{i}{{animation:twinkle" in city.CITY_CSS


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
    walls = [m.start() for m in re.finditer(re.escape(f'fill="{city.WALL_L}"'), svg)]
    lights = [m.start() for m in re.finditer(re.escape(f'fill="{city.WIN_ON}"'), svg)]
    assert walls and lights
    assert lights[0] < walls[-1], "windows all emitted after the last wall"


def test_render_paves_the_whole_grid_not_just_the_days_with_data():
    """A window rarely starts on a Monday, so the end columns are partial.

    Tiling only the days present notched two corners out of the plane.
    """
    svg = city.render({"city": {"window_days": 30}}, {"calendar": calendar([1] * 30)})
    _, weeks = city.layout(calendar([1] * 30), 30)
    assert svg.count(f'fill="{city.GROUND_FILL}"') == weeks * city.ROWS + 1  # + legend swatch


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
