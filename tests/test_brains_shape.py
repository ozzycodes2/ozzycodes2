"""Tests for the grid editor's saved state read as figure geometry.

The editor is the authoring surface for the left hemisphere: what is clicked in
the browser is what publishes. This module is the only thing between the two,
so the invariants the drawing has to satisfy — on the grid, inside the canvas,
one extent — are checked here rather than discovered in a capture run.
"""
import json

import pytest

from tools.brains import shape


def state(left=None, right=None):
    return {"left": left or {}, "right": right or {}}


def test_sides_reads_endpoints_and_the_dashed_flag():
    s = state({"104,20|152,48": "solid", "104,20|56,48": "dashed"})
    assert shape.sides(s, "left") == [
        ((56, 48), (104, 20), True),
        ((104, 20), (152, 48), False),
    ]


def test_sides_orders_endpoints_and_itself():
    """A stable order, so a regenerated figure is byte-identical to the last
    one unless the drawing changed. The editor's JSON is keyed by insertion."""
    a = shape.sides(state({"152,48|104,20": "solid", "104,76|152,48": "solid"}), "left")
    b = shape.sides(state({"104,76|152,48": "solid", "104,20|152,48": "solid"}), "left")
    assert a == b


def test_a_half_with_nothing_drawn_has_no_sides():
    assert shape.sides(state(), "right") == []


@pytest.mark.parametrize(
    "point, expected",
    [
        ((104, 20), True),
        ((8, 20), True),
        ((152, 48), True),
        # Right column, wrong row: the lattice takes every other one.
        ((104, 48), False),
        ((152, 20), False),
        # Off the column spacing entirely.
        ((130, 20), False),
        ((104, 34), False),
    ],
)
def test_on_grid_takes_every_other_lattice_point(point, expected):
    assert shape.on_grid(point) is expected


def test_a_side_joins_two_neighbouring_vertices():
    """A side of a triangle, not a chord across several. The editor can only
    emit neighbours; a hand-edited `state.json` can emit anything."""
    assert shape.strays(state({"104,20|152,48": "solid"}), "left") == []
    assert shape.strays(state({"104,20|200,76": "solid"}), "left") == [((104, 20), (200, 76))]
    assert shape.strays(state({"104,20|130,34": "solid"}), "left") == [((104, 20), (130, 34))]


def test_shift_brings_the_drawing_inside_the_canvas():
    """The editor's grid runs past the bottom of the card on purpose — a shape
    is easier to draw than to place. The shift is what places it."""
    sides = shape.sides(state({"104,20|152,48": "solid", "104,384|152,412": "solid"}), "left")
    dv = shape.shift(shape.side_points(sides))
    assert dv == -16
    vs = [p[1] for a, b, _ in shape.shifted(sides, 0, dv) for p in (a, b)]
    assert min(vs) == shape.PAD
    assert max(vs) <= shape.H - shape.PAD


def test_shift_stays_on_the_4px_grid():
    """Every coordinate the editor can emit is a multiple of four, and placing
    the drawing may not be what takes it off."""
    sides = shape.sides(state({"104,48|152,76": "solid"}), "left")
    assert shape.shift(shape.side_points(sides)) % 4 == 0


def test_a_drawing_taller_than_the_card_is_an_error():
    sides = shape.sides(state({"104,0|104,56": "solid", "104,0|152,420": "solid"}), "left")
    with pytest.raises(ValueError, match="taller than the card"):
        shape.shift(shape.side_points(sides))


def test_shift_of_nothing_is_nothing():
    assert shape.shift([]) == 0


@pytest.mark.parametrize(
    "u0, expected, why",
    [
        (56, -48, "one empty column comes off"),
        (8, 0, "already up against the midline"),
        (200, -192, "four empty columns come off"),
        (4, 0, "at the pad, and a column inward would cross the midline"),
    ],
)
def test_the_drawing_is_brought_up_to_the_midline_by_whole_columns(u0, expected, why):
    assert shape.column_shift([(u0, 20), (248, 384)]) == expected, why


def test_column_shift_of_nothing_is_nothing():
    assert shape.column_shift([]) == 0


def test_extent_measures_the_box_the_drawing_occupies():
    sides = shape.sides(state({"104,20|152,48": "solid", "200,76|248,104": "solid"}), "left")
    assert shape.extent(shape.side_points(sides)) == (104, 20, 248, 104)


def test_extent_of_nothing_is_nothing():
    assert shape.extent([]) is None


def test_as_js_emits_a_literal_naming_every_side():
    s = state({"104,20|152,48": "solid", "104,20|56,48": "dashed"})
    js = shape.as_js(s)
    assert "const BRAIN_EDGES = {" in js
    # Generated, and says so where the next reader of brains.js will see it.
    assert "tools.brains.shape" in js
    assert "[[56, 4], [104, 32], 0]" in js
    assert "[[8, 32], [56, 4], 1]" in js
    assert js.rstrip().endswith("};")


def test_as_js_refuses_a_side_that_is_not_on_the_grid():
    """Generating from a bad state would put the error in the published figure,
    where it reads as a drawing decision rather than as a bad file."""
    with pytest.raises(ValueError, match="not a triangle side"):
        shape.as_js(state({"104,20|200,76": "solid"}))


def circled(right):
    return {"left": {}, "right": right}


def test_circles_reads_a_centre_and_its_arcs():
    c = circled({"152,160": "101100"})
    assert shape.circles(c, "right") == [((152, 160), "101100")]


def test_circles_orders_itself():
    """Stable, for the same reason the sides are: a regenerated figure differs
    only where the drawing did. The editor's JSON is keyed by insertion."""
    a = shape.circles(circled({"200,132": shape.FULL, "152,160": shape.FULL}), "right")
    b = shape.circles(circled({"152,160": shape.FULL, "200,132": shape.FULL}), "right")
    assert a == b == [((152, 160), shape.FULL), ((200, 132), shape.FULL)]


def test_a_half_with_no_circles_has_none():
    assert shape.circles(state(), "right") == []


@pytest.mark.parametrize(
    "mask, why",
    [
        ("11111", "five arcs, not six"),
        ("1111111", "seven"),
        ("000000", "a circle with nothing drawn on it"),
        ("11x111", "not a flag"),
    ],
)
def test_a_circle_the_editor_could_not_have_saved_is_a_stray(mask, why):
    assert shape.odd_circles(circled({"152,160": mask}), "right") == [((152, 160), mask)], why


def test_a_circle_hangs_off_a_triangle_tip():
    """Any other centre puts the six arcs across triangles they do not divide,
    and the arc ends land nowhere on the construction."""
    assert shape.odd_circles(circled({"152,160": shape.FULL}), "right") == []
    assert shape.odd_circles(circled({"152,188": shape.FULL}), "right") == [((152, 188), shape.FULL)]


def test_an_arc_begins_and_ends_on_a_grid_vertex():
    """Which is what lets the drawing join up: two circles on neighbouring tips
    cross at exactly the two tips they both border, so arcs from different
    circles share an endpoint instead of near-missing between vertices."""
    ends = [shape.tip((152, 160), k) for k in range(shape.SECTORS)]
    assert ends[0] == (152, 104)  # straight up, one RISE from the centre
    assert all(shape.on_grid(e) for e in ends)


def test_an_arc_wraps_round_the_circle():
    assert shape.tip((152, 160), shape.SECTORS) == shape.tip((152, 160), 0)


@pytest.mark.parametrize(
    "mask, expected, why",
    [
        ("100000", [(0, 1)], "one arc is a run of one"),
        ("111000", [(0, 3)], "three in a row are one run"),
        ("111111", [(0, 6)], "a whole circle is one run and has no ends"),
        ("101000", [(0, 1), (2, 1)], "a gap splits the runs"),
        ("100011", [(4, 3)], "a run wraps past the last sextant"),
    ],
)
def test_runs_are_the_maximal_chains_of_contiguous_arcs(mask, expected, why):
    """A run is one stroke. Emitting a path per arc instead leaves a seam at
    every tip a run passes through, which the node grammar then has to hide."""
    assert shape.runs(mask) == expected, why


def test_arc_runs_collects_every_circle_in_one_order():
    drawn = shape.arc_runs(circled({"200,132": "100100", "152,160": "110000"}), "right")
    assert drawn == [((152, 160), 0, 2), ((200, 132), 0, 1), ((200, 132), 3, 1)]


def test_a_run_reaches_the_tips_it_spans():
    assert shape.run_points((152, 160), 1, 2) == [(200, 132), (200, 188), (152, 216)]


def test_a_whole_circle_reaches_all_six_tips_once():
    pts = shape.run_points((152, 160), 0, shape.SECTORS)
    assert len(pts) == len(set(pts)) == shape.SECTORS


def test_the_tips_bound_the_drawing_vertically():
    """What makes placing the right half a question about tips rather than about
    sweeps. An arc's extremes in `u` fall mid-sweep, but 90° and 270° — the
    lowest and highest points of a circle — are themselves tips, so no arc ever
    reaches above or below the tips of the run it belongs to."""
    pts = shape.run_points((152, 160), 0, shape.SECTORS)
    assert min(p[1] for p in pts) == 160 - shape.R
    assert max(p[1] for p in pts) == 160 + shape.R


def test_as_js_emits_a_literal_naming_every_run():
    js = shape.as_js(circled({"152,160": "110000"}))
    assert "const BRAIN_RUNS = {" in js
    # Placed: the run reaches u 152..200 and v 104..188, so it comes in three
    # columns and up by PAD - 104.
    assert "[8, 60, 0, 2]," in js
    assert "  left: [\n  ]," in js  # the left half is not drawn in arcs


def test_as_js_refuses_a_circle_the_editor_could_not_have_saved():
    with pytest.raises(ValueError, match="not a circle"):
        shape.as_js(circled({"152,188": "111111"}))


def test_as_js_refuses_a_circle_with_every_arc_drawn():
    """A closed shape is an outline, which is the thing neither half has. It is
    also unrenderable: an `A` to the point the path already stands on is a
    zero-length segment, which SVG skips, so the last sixth would vanish."""
    with pytest.raises(ValueError, match="closes"):
        shape.as_js(circled({"152,160": shape.FULL}))


def test_both_halves_are_placed_at_one_corner():
    """One extent against one gutter, which is the only thing that makes the
    pinned pair read as one brain rather than as two drawings at two sizes."""
    s = shape.load()
    corners = []
    for drawn, pts in (
        (shape.sides(s, "left"), shape.side_points),
        (shape.arc_runs(s, "right"), shape.arc_points),
    ):
        u0, v0, _, _ = shape.extent(pts(drawn))
        corners.append((u0 + shape.column_shift(pts(drawn)), v0 + shape.shift(pts(drawn))))
    assert corners == [(8, shape.PAD), (8, shape.PAD)]


def test_the_saved_drawing_is_on_the_grid_and_fits():
    """The real file, as the editor left it. The halves are drawn in different
    things — sides on the left, circles on the right — and checked as such."""
    s = shape.load()
    assert shape.strays(s, "left") == []
    assert shape.odd_circles(s, "right") == []
    for drawn, pts in (
        (shape.sides(s, "left"), shape.side_points),
        (shape.arc_runs(s, "right"), shape.arc_points),
    ):
        if drawn:
            shape.shift(pts(drawn))  # raises if it cannot be placed


def test_load_reads_the_editor_state(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(state({"104,20|152,48": "solid"})))
    assert shape.load(p)["left"] == {"104,20|152,48": "solid"}


def test_load_of_a_missing_file_is_an_empty_board(tmp_path):
    assert shape.load(tmp_path / "nope.json") == {"left": {}, "right": {}}


def test_main_prints_both_literals(capsys):
    assert shape.main([]) == 0
    out = capsys.readouterr().out
    assert "const BRAIN_EDGES" in out and "const BRAIN_RUNS" in out
