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
    dv = shape.shift(sides)
    assert dv == -16
    vs = [p[1] for a, b, _ in shape.shifted(sides, dv) for p in (a, b)]
    assert min(vs) == shape.PAD
    assert max(vs) <= shape.H - shape.PAD


def test_shift_stays_on_the_4px_grid():
    """Every coordinate in the left half is a multiple of four, which is the
    one thing the right half is allowed to break and this one is not."""
    sides = shape.sides(state({"104,48|152,76": "solid"}), "left")
    assert shape.shift(sides) % 4 == 0


def test_a_drawing_taller_than_the_card_is_an_error():
    sides = shape.sides(state({"104,0|104,56": "solid", "104,0|152,420": "solid"}), "left")
    with pytest.raises(ValueError, match="taller than the card"):
        shape.shift(sides)


def test_shift_of_nothing_is_nothing():
    assert shape.shift([]) == 0


def test_extent_measures_the_box_the_drawing_occupies():
    sides = shape.sides(state({"104,20|152,48": "solid", "200,76|248,104": "solid"}), "left")
    assert shape.extent(sides) == (104, 20, 248, 104)


def test_extent_of_nothing_is_nothing():
    assert shape.extent([]) is None


def test_as_js_emits_a_literal_naming_every_side():
    s = state({"104,20|152,48": "solid", "104,20|56,48": "dashed"})
    js = shape.as_js(s)
    assert "const BRAIN_EDGES = {" in js
    # Generated, and says so where the next reader of brains.js will see it.
    assert "tools.brains.shape" in js
    assert "[[104, 4], [152, 32], 0]" in js
    assert "[[56, 32], [104, 4], 1]" in js
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


def test_an_arc_spans_one_triangle():
    """Arc `k` runs from the spoke toward neighbour `k` to the next one round,
    so it begins and ends on the construction rather than somewhere by eye."""
    ends = [shape.spoke((152, 160), k) for k in range(shape.SECTORS)]
    assert ends[0] == pytest.approx((152, 112))  # straight up, R from the tip
    assert all(
        abs(complex(*e) - complex(152, 160)) == pytest.approx(shape.R) for e in ends
    )


def test_the_saved_drawing_is_on_the_grid_and_fits():
    """The real file, as the editor left it. The halves are drawn in different
    things — sides on the left, circles on the right — and checked as such."""
    s = shape.load()
    assert shape.strays(s, "left") == []
    assert shape.odd_circles(s, "right") == []
    drawn = shape.sides(s, "left")
    if drawn:
        shape.shift(drawn)  # raises if it cannot be placed


def test_load_reads_the_editor_state(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(state({"104,20|152,48": "solid"})))
    assert shape.load(p)["left"] == {"104,20|152,48": "solid"}


def test_load_of_a_missing_file_is_an_empty_board(tmp_path):
    assert shape.load(tmp_path / "nope.json") == {"left": {}, "right": {}}


def test_main_prints_the_literal(capsys):
    assert shape.main([]) == 0
    assert "const BRAIN_EDGES" in capsys.readouterr().out


def test_main_says_when_a_drawn_circle_is_not_in_the_output(capsys, tmp_path):
    """Otherwise the literal looks complete, gets pasted, and the right half
    quietly keeps the arcs it already had."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps(circled({"152,160": shape.FULL})))
    assert shape.main(["--state", str(p)]) == 0
    assert "2 circles" not in (err := capsys.readouterr().err)
    assert "1 circle" in err and "right" in err
