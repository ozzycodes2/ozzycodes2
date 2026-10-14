"""Tests for the isometric contribution plan."""
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


# A full window whose counts vary enough to reach every bucket.
YEAR = calendar([(i * 7) % 13 for i in range(365)])
YEAR_WEEKS = 53


@pytest.fixture(scope="module", params=c.THEMES, ids=[t.name for t in c.THEMES])
def theme(request):
    return request.param


@pytest.fixture(scope="module")
def panel(theme):
    return city.render({"city": {"window_days": 365}}, {"calendar": YEAR}, theme)


def layers(markup):
    """The ground layer and the block layer, as their two bare `<g>` runs.

    Only those two are emitted without attributes; `stagger` wraps its rows in
    `<g class="ln">`, so the plain groups are unambiguous and come out in draw
    order, ground first.
    """
    return re.findall(r"<g>(<path.*?)</g>", markup, re.S)


def faces(markup):
    """(path data, fill) for every painted face in a layer, in draw order."""
    return re.findall(r'<path d="([^"]+)" fill="(#[0-9a-f]{6})"', markup)


def coords(markup):
    """Every point a layer's paths touch, as (x, y) floats."""
    return [(float(x), float(y))
            for d, _ in faces(markup)
            for x, y in re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", d)]


def toward_ink(theme, fill):
    """How far `fill` has travelled from the theme's canvas toward its ink.

    The panel shades by mixing, so a face's bucket is this fraction and nothing
    else — comparing hex strings would only hold for one of the two themes.
    """
    channels = [(int(fill[i:i + 2], 16), int(theme.canvas[i:i + 2], 16),
                 int(theme.ink[i:i + 2], 16)) for i in (1, 3, 5)]
    return (sum(abs(f - canvas) for f, canvas, _ in channels)
            / sum(abs(ink - canvas) for _, canvas, ink in channels))


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


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


def test_levels_counts_the_ground_plus_every_quartile():
    """The legend draws one swatch per level, so the two must not drift."""
    cuts = city.thresholds_for([1, 2, 3, 4])
    assert city.LEVELS == len(cuts) + 1
    assert city.level(10_000, cuts) == city.LEVELS - 1


# --- shades ----------------------------------------------------------------

def test_shades_are_literal_hex_not_an_opacity(theme):
    """Solid mixes only: the blocks overlap, and a translucent face shows the
    block behind it through its own wall."""
    for lvl in range(city.LEVELS):
        for fill in city.shades(theme, lvl):
            assert re.fullmatch(r"#[0-9a-f]{6}", fill), fill


def test_shades_light_the_roof_hardest_and_the_east_wall_least(theme):
    """One light direction for the whole plan: roof, then west, then east."""
    for lvl in range(city.LEVELS):
        roof, west, east = (toward_ink(theme, f) for f in city.shades(theme, lvl))
        assert roof > west > east


def test_shades_deepen_with_the_bucket(theme):
    roofs = [toward_ink(theme, city.shades(theme, lvl)[0])
             for lvl in range(city.LEVELS)]
    assert roofs == sorted(roofs)
    assert len(set(roofs)) == city.LEVELS


def test_shades_are_mixed_out_of_the_theme_that_asked_for_them():
    for lvl in range(city.LEVELS):
        assert city.shades(c.LIGHT, lvl) != city.shades(c.DARK, lvl)


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


def test_block_draws_three_faces(theme):
    grid = city.Grid(26, 800, 400)
    assert grid.block(theme, 100, 100, 30, 3).count("<path") == 3


def test_block_faces_are_not_outlined(theme):
    """At this tile size an outline reads as a black gap, not as an edge."""
    grid = city.Grid(26, 800, 400)
    assert "stroke" not in grid.block(theme, 100, 100, 30, 3)


def test_block_wears_the_shades_of_its_own_bucket(theme):
    """Walls shade with the roof, so a block reads as one mass at one depth."""
    grid = city.Grid(26, 800, 400)
    for lvl in range(city.LEVELS):
        markup = grid.block(theme, 100, 100, 30, lvl)
        for fill in city.shades(theme, lvl):
            assert f'fill="{fill}"' in markup


def test_block_faces_meet_along_one_vertical_corner(theme):
    """The two walls share the near edge; a gap there shows the ground
    through the middle of the block."""
    grid = city.Grid(26, 800, 400)
    west, east, _ = faces(grid.block(theme, 100, 100, 30, 2))
    assert f"L{100.0:.1f} {70.0 + grid.tile_h / 2:.1f}" in west[0]
    assert f"M{100.0:.1f} {70.0 + grid.tile_h / 2:.1f}" in east[0]


def test_height_rises_with_the_count_off_a_visible_floor():
    grid = city.Grid(26, 800, 400)
    assert grid.height_for(1, 60) >= city.MIN_STOREYS
    assert grid.height_for(60, 60) == pytest.approx(grid.max_h)
    assert grid.height_for(10, 60) < grid.height_for(30, 60)


def test_height_scales_by_the_root_not_linearly():
    """Linear would bury an ordinary day beside a 66-commit one."""
    grid = city.Grid(26, 800, 400)
    floor, span = city.MIN_STOREYS, grid.max_h - city.MIN_STOREYS
    assert grid.height_for(25, 100) == pytest.approx(floor + span * 0.5)
    assert grid.height_for(25, 100) > floor + span * 0.25


def test_towers_stand_clear_of_their_own_footprint():
    """Below about twice the tile width a block reads as a lid, not a block.

    This is what bounds `window_days` from below: the headroom is capped, so
    past roughly 26 weeks the tiles get wide enough to outgrow it.
    """
    for weeks in (26, 40, 53):
        grid = city.Grid(weeks, 800, 400)
        assert grid.max_h >= 2 * grid.tile_w


def test_ground_tile_is_a_closed_diamond(theme):
    grid = city.Grid(26, 800, 400)
    assert grid.ground_tile(theme, 100, 100).count("Z") == 1


def test_ground_tile_is_fainter_than_the_quietest_block(theme):
    """The plane has to sit under the blocks, not read as one more bucket."""
    grid = city.Grid(26, 800, 400)
    fill = re.search(r'fill="(#[0-9a-f]{6})"', grid.ground_tile(theme, 100, 100)).group(1)
    quietest = min(toward_ink(theme, f) for f in city.shades(theme, 0))
    assert toward_ink(theme, fill) < quietest


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

def test_render_height_is_on_the_grid(panel):
    assert height_of(panel) % c.ROW == 0


def test_render_height_is_stable_across_windows(theme):
    data = {"calendar": YEAR}
    short = city.render({"city": {"window_days": 180}}, data, theme)
    long = city.render({"city": {"window_days": 365}}, data, theme)
    assert height_of(short) == height_of(long)


def test_render_reports_real_numbers_in_the_description(theme):
    svg = city.render({"city": {"window_days": 7}},
                      {"calendar": calendar([1, 0, 5, 0, 0, 2, 0])}, theme)
    desc = desc_of(svg)
    assert "8 contributions" in desc
    assert "3 active days" in desc
    assert "busiest" in desc


def test_render_without_calendar_degrades_instead_of_raising(theme):
    svg = city.render({}, {}, theme)
    assert "no contribution data" in svg
    assert height_of(svg) % c.ROW == 0


def test_render_with_an_all_quiet_calendar(theme):
    svg = city.render({"city": {"window_days": 14}},
                      {"calendar": calendar([0] * 14)}, theme)
    assert height_of(svg) % c.ROW == 0


def test_render_is_deterministic(theme):
    """A reshuffle would make the daily job commit noise."""
    data = {"calendar": calendar([2, 0, 7] * 60)}
    assert city.render({}, data, theme) == city.render({}, data, theme)


def test_render_paves_the_whole_grid_not_just_the_days_with_data(theme):
    """A window rarely starts on a Monday, so the end columns are partial.

    Tiling only the days present notched two corners out of the plane.
    """
    svg = city.render({"city": {"window_days": 30}},
                      {"calendar": calendar([1] * 30)}, theme)
    ground, _ = layers(svg)
    _, weeks = city.layout(calendar([1] * 30), 30)
    assert len(faces(ground)) == weeks * city.ROWS


def test_render_escapes_nothing_unbalanced(panel):
    assert panel.count("<svg") == panel.count("</svg") == 1


def test_render_window_falls_back_to_a_year(theme):
    svg = city.render({}, {"calendar": YEAR}, theme)
    assert "--last 365d" in svg


def test_render_draws_one_block_per_active_day_back_to_front(panel):
    """Increasing (row + col) runs away from the viewer, so emitting in that
    order is the depth sort — no face is ever drawn over a block in front."""
    _, blocks = layers(panel)
    drawn = faces(blocks)
    active = sum(1 for _, n in YEAR if n > 0)
    assert len(drawn) == 3 * active
    # The last point of a west wall is its own ground corner, which is where
    # the block stands in the plane.
    bases = [float(re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", d)[-1][1])
             for d, _ in drawn[::3]]
    assert bases == sorted(bases)


def test_render_paints_every_face_as_a_solid_fill(panel):
    """No face may be an opacity over the block behind it, or the plan stops
    reading as solid where two blocks overlap."""
    ground, blocks = layers(panel)
    assert "fill-opacity" not in panel
    for tag in re.findall(r"<path[^>]*>", ground + blocks):
        assert "opacity" not in tag, tag
        assert re.search(r'fill="#[0-9a-f]{6}"', tag), tag


def test_render_keeps_the_plane_inside_the_rails(panel):
    points = coords("".join(layers(panel)))
    xs = [x for x, _ in points]
    assert c.FRAME_L <= min(xs)
    assert max(xs) <= c.FRAME_R


@pytest.mark.parametrize("window", [14, 30, 180, 365, 730])
def test_render_keeps_the_plane_inside_the_rails_at_every_window(window):
    svg = city.render({"city": {"window_days": window}},
                      {"calendar": calendar([(i * 5) % 9 for i in range(730)])},
                      c.LIGHT)
    xs = [x for x, _ in coords("".join(layers(svg)))]
    assert c.FRAME_L <= min(xs) and max(xs) <= c.FRAME_R


def test_render_draws_nothing_outside_the_slice(panel):
    ys = [y for _, y in coords("".join(layers(panel)))]
    assert 0 <= min(ys) and max(ys) <= height_of(panel)


def test_render_keeps_its_text_inside_the_content_column(panel):
    for x in re.findall(r'<text x="([\d.]+)"', panel):
        assert c.TEXT_X <= float(x) <= c.CONTENT_R


def test_render_legend_draws_one_small_diamond_per_level(panel):
    assert len(re.findall(r"l7 3\.5l-7 3\.5l-7 -3\.5Z", panel)) == city.LEVELS


def test_both_themes_render_a_complete_plan_in_their_own_ink():
    cfg, data = {"city": {"window_days": 365}}, {"calendar": YEAR}
    fills = {}
    for scheme in (c.LIGHT, c.DARK):
        ground, blocks = layers(city.render(cfg, data, scheme))
        assert len(faces(ground)) == YEAR_WEEKS * city.ROWS
        fills[scheme.name] = {fill for _, fill in faces(blocks)}
        assert fills[scheme.name]
    assert not fills["light"] & fills["dark"]
