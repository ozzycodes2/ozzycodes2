"""Tests for the isometric contribution plan."""
import datetime
import re

import pytest

from tools.profile.present import console as c
from tools.profile.present.panels import city

# The section rule `heading` draws, which no roof may cross.
RULE_Y = 44 + 14


def calendar(counts, start="2026-04-15"):
    """One [date, count] pair per consecutive day from `start`.

    Matches the shape of data/calendar.json: the panel reads the dates only to
    name the peak day, and lays the grid out by index.
    """
    day = datetime.date.fromisoformat(start)
    return [[(day + datetime.timedelta(days=i)).isoformat(), n]
            for i, n in enumerate(counts)]


# A full 26-week window whose counts reach every bucket. 26 weeks is what the
# plane is cut for, so this is the geometry the panel is tuned against.
YEAR = calendar([(i * 7) % 13 for i in range(182)])
YEAR_WEEKS = 26


@pytest.fixture(scope="module", params=c.THEMES, ids=[t.name for t in c.THEMES])
def theme(request):
    return request.param


@pytest.fixture(scope="module")
def panel(theme):
    return city.render({"city": {"window_days": 182}}, {"calendar": YEAR}, theme)


def layers(markup):
    """The ground layer and the block layer, as their two bare `<g>` runs.

    They are the only two groups the panel emits, and they come out in draw
    order: the plane, then the blocks standing on it. Either may be empty.
    """
    return re.findall(r"<g>(.*?)</g>", markup, re.S)


def polys(markup):
    """(points, fill, trailing attributes) for every polygon, in draw order."""
    return re.findall(r'<polygon points="([^"]+)" fill="(#[0-9a-f]{6})"([^/]*)/>', markup)


def points(spec):
    """One polygon's `points` attribute, as (x, y) floats."""
    return [(float(x), float(y)) for x, y in (p.split(",") for p in spec.split())]


def coords(markup):
    """Every point the polygons in a layer touch."""
    return [xy for spec, _, _ in polys(markup) for xy in points(spec)]


def circles(markup):
    """(cx, cy, r, trailing attributes) for every circle, in draw order.

    The legend swatches are the only circles this panel draws, so a search over
    a whole slice finds the key and nothing else.
    """
    return [(float(cx), float(cy), float(r), rest) for cx, cy, r, rest
            in re.findall(r'<circle cx="([\d.-]+)" cy="([\d.-]+)" '
                          r'r="([\d.]+)"([^/]*)/>', markup)]


def toward(theme, fill, base):
    """How far `fill` has travelled from the theme's canvas toward `base`.

    The panel shades by mixing, so a face's bucket is this fraction and nothing
    else — comparing hex strings would only hold for one of the two themes.
    `base` is a parameter because the plan rides two ramps: the ink one every
    block is shaded on, and the accent one the tallest block has to itself.
    """
    channels = [(int(fill[i:i + 2], 16), int(theme.canvas[i:i + 2], 16),
                 int(base[i:i + 2], 16)) for i in (1, 3, 5)]
    return (sum(abs(f - canvas) for f, canvas, _ in channels)
            / sum(abs(b - canvas) for _, canvas, b in channels))


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def texts(svg):
    """(x, content) for every label, so a test can locate one by its words."""
    return [(float(x), body) for x, body
            in re.findall(r'<text x="([\d.]+)"[^>]*>(.*?)</text>', svg)]


# --- buckets ---------------------------------------------------------------

def test_thresholds_ignore_quiet_days():
    """A bare day is ground, not a quartile, so it must not shift the cuts."""
    assert city.thresholds_for([0, 0, 0, 1, 2, 3, 4]) == city.thresholds_for([1, 2, 3, 4])


def test_thresholds_are_quartiles_of_the_active_days():
    assert city.thresholds_for(list(range(1, 101))) == [26, 51, 76]


def test_thresholds_on_an_all_quiet_calendar():
    """With nothing to split, every cut is 1 — the lowest a count can be."""
    assert city.thresholds_for([0, 0, 0]) == [1, 1, 1]


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
    assert city.level(0, [1, 2, 3]) == 0


def test_level_is_clamped_to_the_top_bucket():
    assert city.level(10_000, [1, 2, 3]) == 4


def test_level_is_monotonic():
    cuts = [2, 5, 9]
    levels = [city.level(n, cuts) for n in range(1, 40)]
    assert levels == sorted(levels)


def test_levels_counts_the_ground_plus_every_quartile():
    """The legend draws one swatch per occupied bucket, so the two must not
    drift: three cuts make four occupied buckets above the ground."""
    cuts = city.thresholds_for([1, 2, 3, 4])
    assert city.LEVELS == len(cuts) + 2
    assert city.level(10_000, cuts) == city.LEVELS - 1


# --- heights ---------------------------------------------------------------

def test_height_of_a_bare_day_is_no_block_at_all():
    assert city.height_for(0, 40, 0) == 0


def test_height_floors_at_a_visible_minimum():
    """One contribution against a huge peak still has to read as a building."""
    assert city.height_for(1, 10_000, 1) == city.MIN_H


def test_the_tallest_day_stands_exactly_at_the_headroom():
    assert city.height_for(40, 40, 4) == city.MAX_H


def test_height_scales_by_the_root_not_linearly():
    """Linear would bury an ordinary day beside a 40-commit one."""
    assert city.height_for(25, 100, 2) == city.MAX_H // 2
    assert city.height_for(25, 100, 2) > city.MAX_H * 0.25


def test_height_rises_with_the_count():
    heights = [city.height_for(n, 40, 2) for n in range(1, 41)]
    assert heights == sorted(heights)


def test_height_is_a_whole_number_of_pixels():
    """Every coordinate in this panel is an integer, so the markup carries no
    decimals and two renders of the same data cannot differ in a last digit."""
    for n in range(1, 41):
        assert isinstance(city.height_for(n, 40, 3), int)


# --- shades ----------------------------------------------------------------

def test_shades_are_literal_hex_not_an_opacity(theme):
    """Solid mixes only: the blocks overlap, and a translucent face shows the
    block behind it through its own wall."""
    for lvl in range(1, city.LEVELS):
        for fill in city.shades(theme, lvl):
            assert re.fullmatch(r"#[0-9a-f]{6}", fill), fill


def test_the_three_faces_of_a_block_are_distinct(theme):
    for lvl in range(1, city.LEVELS):
        assert len(set(city.shades(theme, lvl))) == 3


def test_shades_light_the_roof_hardest_and_the_right_wall_least(theme):
    """One light direction for the whole plan: the roof is the face nearest the
    canvas, the right wall the face nearest the ink."""
    for lvl in range(1, city.LEVELS):
        faces = city.shades(theme, lvl)
        left, right, roof = (toward(theme, f, theme.ink) for f in faces)
        assert roof < left < right


def test_shades_deepen_with_the_bucket(theme):
    roofs = [toward(theme, city.shades(theme, lvl)[2], theme.ink)
             for lvl in range(city.LEVELS)]
    assert roofs == sorted(roofs)
    assert len(set(roofs)) == city.LEVELS


def test_the_busiest_bucket_saturates_at_the_ink(theme):
    """The right wall's 1.3 multiplier runs past the end of the ramp; clamping
    it keeps the mix a colour rather than an extrapolation past the ink."""
    assert city.shades(theme, city.LEVELS - 1)[1] == theme.ink


def test_shades_are_mixed_out_of_the_theme_that_asked_for_them():
    for lvl in range(city.LEVELS):
        assert city.shades(c.LIGHT, lvl) != city.shades(c.DARK, lvl)


def test_the_peak_block_is_mixed_off_the_accent_instead_of_the_ink(theme):
    """Its one job is to be the block the eye lands on, so no bucket of the ink
    ramp may land on the same three faces."""
    for lvl in range(1, city.LEVELS):
        assert city.shades(theme, lvl, peak=True) != city.shades(theme, lvl)


def test_the_peak_block_is_lit_from_the_same_side_as_its_neighbours(theme):
    """Same three ratios off a different base: the accent changes which paint
    the tall block wears, not where the light falls on it."""
    for lvl in range(1, city.LEVELS):
        faces = city.shades(theme, lvl, peak=True)
        left, right, roof = (toward(theme, f, theme.accent) for f in faces)
        assert roof < left <= right


def test_the_busiest_peak_bucket_saturates_at_the_accent(theme):
    """The legend's last swatch is the bare accent, so the face the eye reads
    the tall block by has to arrive at exactly that value."""
    assert city.shades(theme, city.LEVELS - 1, peak=True)[1] == theme.accent


# --- projection ------------------------------------------------------------

def test_project_puts_the_first_tile_at_the_plane_origin():
    assert city.project(0, 0, 84) == (city.OX, 84)


def test_project_moves_a_week_right_and_down():
    assert city.project(1, 0, 84) == (city.OX + city.HALF_W, 84 + city.HALF_H)


def test_project_moves_a_weekday_left_and_down():
    assert city.project(0, 1, 84) == (city.OX - city.HALF_W, 84 + city.HALF_H)


def test_project_is_two_to_one():
    """The whole illusion is the 2:1 tile; a different ratio reads as a shear."""
    (x0, y0), (x1, y1) = city.project(0, 0, 0), city.project(4, 0, 0)
    assert (x1 - x0) == 2 * (y1 - y0)


def test_the_full_window_sits_centred_between_the_rails():
    """OX is cut for 26 weeks: the rhombus is 726px wide and the slack left and
    right of it is equal. A longer window would run off the right rail."""
    xs = [city.project(col, row, 84)[0]
          for col in range(YEAR_WEEKS) for row in range(city.ROWS)]
    west, east = min(xs) - city.HALF_W, max(xs) + city.HALF_W
    assert west - c.FRAME_L == c.FRAME_R - east
    assert c.FRAME_L < west and east < c.FRAME_R


def test_diamond_is_a_closed_two_to_one_rhombus():
    corners = points(city.diamond(100, 200))
    assert corners == [(100, 200), (122, 211), (100, 222), (78, 211)]


def test_a_lifted_diamond_is_the_same_shape_moved_up():
    """A roof is the block's own footprint, translated — anything else would
    make the top face the wrong size for the walls under it."""
    low, high = points(city.diamond(100, 200)), points(city.diamond(100, 200, 30))
    assert [(x, y + 30) for x, y in high] == low


def test_block_draws_three_faces(theme):
    assert city.block(theme, 100, 200, 30, 3).count("<polygon") == 3


def test_block_faces_are_not_outlined(theme):
    """At this tile size an outline reads as a gap between neighbours rather
    than as an edge, and the shading already separates the faces."""
    assert "stroke" not in city.block(theme, 100, 200, 30, 3)


def test_block_walls_meet_along_the_near_corner(theme):
    """The two walls share the tile's south vertex; a gap there shows the
    ground through the middle of the block."""
    left, right, _ = polys(city.block(theme, 100, 200, 30, 2))
    assert points(left[0])[1] == points(right[0])[0] == (100, 222)


def test_block_wears_the_shades_of_its_own_bucket(theme):
    for lvl in range(1, city.LEVELS):
        markup = city.block(theme, 100, 200, 30, lvl)
        assert [fill for _, fill, _ in polys(markup)] == list(city.shades(theme, lvl))


def test_block_wears_the_accent_shades_when_it_is_the_peak(theme):
    for lvl in range(1, city.LEVELS):
        markup = city.block(theme, 100, 200, 30, lvl, peak=True)
        assert [fill for _, fill, _ in polys(markup)] == list(
            city.shades(theme, lvl, peak=True))


# --- cells -----------------------------------------------------------------

def test_a_tie_for_the_peak_marks_only_the_first_day_holding_it():
    """Two tall blocks in the accent would contradict the note beside the
    legend, which names a single date."""
    values = [3, 9, 4, 9, 2, 1, 9]
    cells = city.cells_for(values, 1, 9, city.thresholds_for(values))
    assert [is_peak for *_, is_peak in cells] == [i == 1 for i in range(7)]


def test_an_all_quiet_calendar_marks_no_peak_at_all():
    """`render` floors the peak at 1 so the heights stay finite, but no day
    holds that value, so there is no block for the accent to land on."""
    values = [0] * 7
    cells = city.cells_for(values, 1, 1, city.thresholds_for(values))
    assert not any(is_peak for *_, is_peak in cells)


# --- overhang --------------------------------------------------------------

def test_overhang_is_nothing_when_no_block_outgrows_its_own_depth():
    """A block standing far back is already below the plane's top edge by its
    own depth, so it needs no extra room above the plane."""
    assert city.overhang_of([(5, 5, 4, 60, False)]) == 0


def test_overhang_is_measured_from_the_nearest_tall_block():
    """Only a block at the far corner of the grid can push the plane down."""
    assert city.overhang_of([(0, 0, 4, 120, True), (5, 5, 4, 120, False)]) == 120


def test_overhang_of_an_empty_grid():
    assert city.overhang_of([]) == 0


def test_render_keeps_the_tallest_roof_below_the_section_rule():
    """The tallest block stands on the first tile, where the plane gives it no
    depth to hide the height in, so the whole plane has to start lower."""
    svg = city.render({"city": {"window_days": 14}},
                      {"calendar": calendar([99] + [1] * 13)}, c.LIGHT)
    _, blocks = layers(svg)
    assert min(y for _, y in coords(blocks)) == city.OY
    assert city.OY > RULE_Y


# --- render ----------------------------------------------------------------

def test_render_height_is_on_the_grid(panel):
    assert height_of(panel) % c.ROW == 0


def test_render_height_clears_the_legend(panel):
    """The legend is the lowest thing drawn; the slice has to close below it."""
    legend_y = max(cy + r for _, cy, r, _ in circles(panel))
    assert legend_y < height_of(panel) <= legend_y + c.ROW + 24


def test_render_paves_the_whole_grid_not_just_the_days_with_data(panel):
    """Most days are quiet, and tiling only the built-on ones would punch
    holes in the plane."""
    ground, _ = layers(panel)
    assert len(polys(ground)) == YEAR_WEEKS * city.ROWS


def test_render_drops_a_trailing_part_week():
    """A short final column would read as a torn edge on the plane."""
    svg = city.render({"city": {"window_days": 10}},
                      {"calendar": calendar([1] * 10)}, c.LIGHT)
    ground, _ = layers(svg)
    assert len(polys(ground)) == city.ROWS


def test_render_draws_one_block_per_active_day(panel):
    _, blocks = layers(panel)
    active = sum(1 for _, n in YEAR[:YEAR_WEEKS * city.ROWS] if n > 0)
    assert len(polys(blocks)) == 3 * active


def test_render_emits_far_blocks_before_near_ones(panel):
    """Increasing (col + row) runs toward the viewer, so emitting in that order
    is the depth sort — no face is ever drawn over a block in front of it."""
    _, blocks = layers(panel)
    walls = polys(blocks)[::3]
    bases = [points(spec)[1][1] for spec, _, _ in walls]
    assert bases == sorted(bases)


def test_render_paints_every_face_as_a_solid_fill(panel):
    """No face may be an opacity over the block behind it, or the plan stops
    reading as solid where two blocks overlap."""
    for tag in re.findall(r"<polygon[^>]*>", "".join(layers(panel))):
        assert "opacity" not in tag, tag
    assert "fill-opacity" not in panel


def test_render_lays_the_ground_as_a_hairline_plane(panel, theme):
    """The plane is one step above the canvas and edged at half a pixel: any
    heavier and the paving reads louder than the blocks standing on it."""
    ground, _ = layers(panel)
    for _, fill, rest in polys(ground):
        assert fill == theme.surface
        assert f'stroke="{theme.hairline}" stroke-width="0.5"' in rest


def test_render_keeps_the_plane_inside_the_rails(panel):
    xs = [x for x, _ in coords("".join(layers(panel)))]
    assert c.FRAME_L <= min(xs) and max(xs) <= c.FRAME_R


def test_render_draws_nothing_above_the_slice(panel):
    ys = [y for _, y in coords("".join(layers(panel)))]
    assert 0 <= min(ys) and max(ys) <= height_of(panel)


def test_render_keeps_its_text_inside_the_content_column(panel):
    for x, _ in texts(panel):
        assert c.TEXT_X <= x <= c.CONTENT_R


def test_render_counts_the_window_beside_the_heading(panel):
    assert f"{len(YEAR)} days" in panel


def test_render_window_falls_back_to_the_width_the_plane_is_cut_for():
    svg = city.render({}, {"calendar": calendar([1] * 400)}, c.LIGHT)
    assert f"{city.WINDOW_DAYS} days" in svg


def test_render_reports_real_numbers_in_the_description(theme):
    svg = city.render({"city": {"window_days": 7}},
                      {"calendar": calendar([1, 0, 5, 0, 0, 2, 0])}, theme)
    desc = desc_of(svg)
    assert "7 tiles" in desc and "3 built on" in desc
    assert "8 contributions" in desc
    assert "Tallest block is 5 on 2026-04-17" in desc


def test_render_spends_the_accent_in_exactly_three_places(panel, theme):
    """The section rule's 120px overstroke, the last legend swatch and the
    saturated face of the one tall block. Everything else is the ink ramp, so
    the bare hex may not appear anywhere a fourth time."""
    assert panel.count(theme.accent) == 3
    assert f'stroke="{theme.accent}" stroke-width="2"' in panel
    assert sum(f'fill="{theme.accent}"' in rest for *_, rest in circles(panel)) == 1
    _, blocks = layers(panel)
    saturated = city.shades(theme, city.LEVELS - 1, peak=True)[1]
    assert [fill for _, fill, _ in polys(blocks)].count(saturated) == 1


def test_render_paints_one_block_off_the_accent_and_it_is_the_tallest(panel, theme):
    """The whole point of the panel: the eye should land on the busiest day
    without reading the note. Two accented blocks would name two days, none
    would leave the legend's last swatch keying nothing."""
    _, blocks = layers(panel)
    walls = polys(blocks)[::3]   # the left wall of each block, in draw order
    heights = [points(spec)[1][1] - points(spec)[2][1] for spec, _, _ in walls]
    accented = [i for i, (_, fill, _) in enumerate(walls)
                if fill == city.shades(theme, city.LEVELS - 1, peak=True)[0]]
    assert len(accented) == 1
    assert heights[accented[0]] == max(heights) == city.MAX_H


def test_render_is_flat_fills_and_nothing_else(panel):
    """No filter, no gradient and no fade-in: GitHub paints a rendered SVG at
    frame zero, so anything that animates in is simply invisible."""
    for forbidden in ("<filter", "Gradient", "<pattern", 'class="ln"'):
        assert forbidden not in panel


def test_render_is_deterministic(theme):
    """A reshuffle would make the daily job commit noise."""
    data = {"calendar": calendar([2, 0, 7] * 60)}
    assert city.render({}, data, theme) == city.render({}, data, theme)


def test_render_emits_one_well_formed_document(panel):
    assert panel.count("<svg") == panel.count("</svg") == 1


# --- legend ----------------------------------------------------------------

def test_legend_draws_one_circle_per_occupied_bucket(panel):
    """Dots, not little rhombi: drawn as tiles the swatches invited reading as
    four more buildings standing beside the plan."""
    assert len(circles(panel)) == city.LEVELS - 1
    assert not polys(panel.split("</g>")[-1])


def test_legend_swatches_step_at_the_block_ramp(theme):
    """The swatches are the only thing the panel paints at an opacity —
    nothing overlaps them — so the ladder has to be the blocks' own."""
    found = re.findall(r'opacity="([\d.]+)"', city.legend(theme, 400))
    assert found == [f"{0.18 + lvl * 0.16:.2f}" for lvl in range(1, city.LEVELS - 1)]


def test_the_last_legend_swatch_is_the_accent_at_full_strength(theme):
    """It keys the block painted off the accent, so it has to be that paint and
    not a dimmed sample of it — the ink ramp's top step is a different colour."""
    *ramp, top = circles(city.legend(theme, 400))
    assert f'fill="{theme.accent}"' in top[3] and "opacity" not in top[3]
    assert all("opacity" in rest for *_, rest in ramp)


def test_legend_swatches_sit_between_their_two_labels(theme):
    markup = city.legend(theme, 400)
    edges = [x for cx, _, r, _ in circles(markup) for x in (cx - r, cx + r)]
    labelled = dict((body, x) for x, body in texts(markup))
    assert labelled["quieter"] < min(edges)
    assert max(edges) < labelled["busier"]


def test_legend_swatches_are_evenly_pitched(theme):
    centres = [cx for cx, _, _, _ in circles(city.legend(theme, 400))]
    assert centres == [city.LEGEND_X + i * city.LEGEND_PITCH
                       for i in range(city.LEVELS - 1)]


def test_legend_swatches_share_one_baseline_and_one_radius(theme):
    """A ladder of four steps reads as a ladder only if the dots differ in
    nothing but their paint."""
    rows = {(cy, r) for _, cy, r, _ in circles(city.legend(theme, 400))}
    assert len(rows) == 1


def test_render_ends_the_peak_note_at_the_content_edge(panel):
    """It shares a baseline with "busier", so it is set from the right edge
    inward rather than from a guessed width."""
    note = re.search(r'<text x="(\d+)"[^>]*text-anchor="(end)"[^>]*>tallest ', panel)
    assert note and (int(note.group(1)), note.group(2)) == (c.CONTENT_R, "end")


# --- degraded input --------------------------------------------------------

def test_render_without_a_calendar_key_degrades_instead_of_raising(theme):
    svg = city.render({}, {}, theme)
    assert "no contribution data" in svg
    assert height_of(svg) % c.ROW == 0


def test_render_with_an_empty_calendar_degrades(theme):
    svg = city.render({}, {"calendar": []}, theme)
    assert "No contribution data available." == desc_of(svg)


def test_render_with_an_all_quiet_calendar(theme):
    """Nothing is built on, so the plan is bare paving — and the peak note
    falls back to the last day rather than naming a day that never happened."""
    svg = city.render({"city": {"window_days": 14}},
                      {"calendar": calendar([0] * 14)}, theme)
    assert layers(svg)[1] == ""
    assert "tallest 1 on 2026-04-28" in svg
    assert height_of(svg) % c.ROW == 0


def test_a_window_of_part_weeks_keeps_its_newest_days(theme):
    """The part-week is trimmed off the far end, so the peak is always inside
    the plan. Trimming the near end instead would drop the most recent days —
    where the peak usually is — and leave the legend keying nothing."""
    counts = [1] * 179 + [99]
    svg = city.render({"city": {"window_days": 180}},
                      {"calendar": calendar(counts)}, theme)
    assert svg.count(theme.accent) == 3     # rule, legend swatch, peak wall
    assert "tallest 99 on 2026-10-11" in svg
    assert "175 tiles" in desc_of(svg)


def test_render_with_less_than_one_week_of_history(theme):
    """Fewer than seven days is no columns at all, so the panel says so rather
    than captioning an empty plane with a tile count it never drew."""
    svg = city.render({"city": {"window_days": 3}},
                      {"calendar": calendar([1, 2, 3])}, theme)
    assert "3 days of history" in desc_of(svg)
    assert "less than a week of history" in svg
    assert height_of(svg) % c.ROW == 0


# --- themes ----------------------------------------------------------------

def test_both_themes_render_identical_geometry():
    """render.py pairs the two files point for point; only the fills may move."""
    cfg, data = {"city": {"window_days": 182}}, {"calendar": YEAR}
    light, dark = (city.render(cfg, data, t) for t in (c.LIGHT, c.DARK))
    assert height_of(light) == height_of(dark)
    assert desc_of(light) == desc_of(dark)
    for a, b in zip(layers(light), layers(dark)):
        assert [spec for spec, _, _ in polys(a)] == [spec for spec, _, _ in polys(b)]


def test_neither_theme_borrows_the_other_s_ink():
    """Every role but `accent` is per-polarity, and the accent is deliberately
    one value across both — a brand hue that follows the system setting is two
    brands — so the peak block is the one face the two renders may share."""
    cfg, data = {"city": {"window_days": 182}}, {"calendar": YEAR}
    fills = {}
    for scheme in (c.LIGHT, c.DARK):
        _, blocks = layers(city.render(cfg, data, scheme))
        fills[scheme.name] = {fill for _, fill, _ in polys(blocks)}
        assert fills[scheme.name]
    assert fills["light"] & fills["dark"] == {c.LIGHT.accent}
    assert c.LIGHT.accent == c.DARK.accent
