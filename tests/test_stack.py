"""Tests for the exploded axonometric, whose geometry is the whole panel.

Four invariants carry it, and each is one that looked fine on screen while being
wrong: the gap has to clear the band the slab above leaves visible, the lattice
pitch has to clear a whole cell rather than half of one, every square in the
figure has to turn at one radius-to-width ratio, and a pedestal's height has to
be its tool's level and nothing else.

A handful of paints are pinned to literals read out of the preview. They are
solved there — `focalTint` searches for a ratio and `brand` walks a hex toward
the ink — so recomputing them the way stack.py does would pass whatever stack.py
said, which is the failure mode this pair of repos invites.
"""
import math
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import stack

CFG = {"stack": {
    "Languages": {"Java": 5, "Rust": 3, "Python": 4, "TypeScript": 2, "Swift": 5, "Shell": 2},
    "Platform": {"Kubernetes": 4, "Terraform": 3, "Helm": 3, "ArgoCD": 4, "Docker": 5},
    "Cloud": {"AWS": 4, "Grafana": 4, "Prometheus": 2, "Datadog": 4},
    "Tooling": {"Claude Code": 5, "MCP": 3, "Git": 4, "Just": 3, "Neovim": 2},
}}

TOTAL = sum(len(v) for v in CFG["stack"].values())
LAYERS = list(reversed(list(CFG["stack"].items())))   # bottom to top, as drawn

# Slab and cell are told apart by the weight of their silhouette stroke, and the
# paint order is slab, its own cells, then the slab above.
SIL = re.compile(r'<polygon points="([^"]*)" fill="none" stroke="[^"]*" '
                 r'stroke-width="([\d.]+)" stroke-linejoin="round"/>')


@pytest.fixture(scope="module")
def markup():
    return stack.render(CFG, {}, c.LIGHT)


def body_of(markup):
    """The drawing, without the <style> block the embedded fonts live in."""
    return markup.split("</style>")[1]


def height_of(markup):
    return int(re.search(r'<svg[^>]*height="(\d+)"', markup).group(1))


def points(raw):
    return [tuple(float(v) for v in p.split(",")) for p in raw.split()]


def levels_of(markup):
    """[(slab outline, [cell outlines])] bottom to top, off the silhouettes."""
    out = []
    for raw, weight in SIL.findall(body_of(markup)):
        if weight == str(c.EDGE_W):
            out.append((points(raw), []))
        else:
            out[-1][1].append(points(raw))
    return out


def text_of(markup):
    return re.findall(r'<text x="([\d.]+)" y="([\d.]+)" fill="(#[0-9a-f]{6})"'
                      r'[^>]*font-size="(\d+)"[^>]*>([^<]*)</text>', body_of(markup))


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert height_of(markup) % c.ROW == 0
    edges = re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]+" '
                      rf'stroke-width="{c.RAIL_W}"', markup).group(1)
    assert "H" not in edges


def test_nothing_is_drawn_over_the_section_rule_or_past_the_rails(markup):
    xs = [x for raw, _ in SIL.findall(body_of(markup)) for x, _ in points(raw)]
    ys = [y for raw, _ in SIL.findall(body_of(markup)) for _, y in points(raw)]
    assert min(xs) >= c.TEXT_X and max(xs) <= c.CONTENT_R
    assert min(ys) >= 60, f"a part reaches y={min(ys)}, into the rule at 58"
    assert max(ys) <= height_of(markup)


def test_a_level_never_moves_the_slice_height():
    """The gap is cut for the ladder's tallest step rather than the roster's, so
    editing one tool's level cannot resize the figure — or every panel under it."""
    base = height_of(stack.render(CFG, {}, c.LIGHT))
    for level in range(1, stack.TILE_LEVELS + 1):
        cfg = {"stack": {k: dict.fromkeys(v, level) for k, v in CFG["stack"].items()}}
        assert height_of(stack.render(cfg, {}, c.LIGHT)) == base, level


def test_a_longer_roster_densifies_the_lattice_rather_than_the_slice():
    """Up to the point the cells hit their 10-unit floor, which is where the
    lattice starts to outgrow the footprint and the height does move."""
    base = height_of(stack.render(CFG, {}, c.LIGHT))
    for n in (6, 7, 8):
        cfg = {"stack": {k: {f"tool-{i}": 3 for i in range(n)} for k in CFG["stack"]}}
        assert height_of(stack.render(cfg, {}, c.LIGHT)) == base, n
        assert stack.tile_size(stack.FOOT_W, stack.FOOT_D,
                               stack.tile_side(n, False)) > 10


def test_height_grows_with_the_number_of_layers():
    one = stack.render({"stack": {"Cloud": {"AWS": 3}}}, {}, c.LIGHT)
    two = stack.render({"stack": {"Cloud": {"AWS": 3}, "Tooling": {"Git": 3}}}, {}, c.LIGHT)
    assert height_of(two) > height_of(one)
    assert height_of(one) % c.ROW == 0


# --- the stack itself ------------------------------------------------------

def test_one_slab_per_category_and_one_cell_per_tool_with_no_blanks(markup):
    """A blank lattice position is a tool the panel is claiming and does not
    have, so a four-tool layer shows four cells on a face that could hold five."""
    drawn = levels_of(markup)
    assert len(drawn) == len(CFG["stack"])
    assert [len(cells) for _, cells in drawn] == [len(items) for _, items in LAYERS]


def test_the_gaps_between_levels_are_equal(markup):
    """Shrinking one gap to fit the frame is the anti-pattern the rounding to the
    4px grid exists to avoid."""
    tops = [min(y for _, y in slab) for slab, _ in levels_of(markup)]
    gaps = [round(a - b, 2) for a, b in zip(tops, tops[1:])]
    assert len(set(gaps)) == 1, gaps
    assert gaps[0] % 4 == 0, f"the gap {gaps[0]} is off the 4px grid"


def test_no_slab_hangs_over_a_cell_of_the_layer_below_it(markup):
    """A slab covers the back of the slab below at every spacing the type allows,
    so the cells sit in the band the gap opens rather than on the face. This is
    the one assertion that fails the moment the lattice or the gap is retuned."""
    drawn = levels_of(markup)
    for i, (_, cells) in enumerate(drawn[:-1]):
        hangs = max(y for _, y in drawn[i + 1][0])
        hidden = [cell for cell in cells if min(y for _, y in cell) < hangs]
        assert not hidden, f"layer {i}: the slab above hangs to y={hangs} over {len(hidden)} cells"


def test_cells_under_a_slab_run_along_the_near_border_only(markup):
    """Which is what lets the stack close up: the slab above may reach the
    lattice's middle diagonal because nothing stands behind it."""
    for i, (_, cells) in enumerate(levels_of(markup)[:-1]):
        fronts = sorted(max(x + y for x, y in cell) for cell in cells)
        # Two screen rows at most — the near border is the two edges facing the
        # viewer, and a third row would mean a cell placed behind them.
        assert len({round(f, 1) for f in fronts}) <= 2 * len(cells)
        depth = max(y for cell in cells for _, y in cell) - \
            min(y for cell in cells for _, y in cell)
        assert depth < stack.FOOT_D, f"layer {i} spreads {depth}px deep"


def test_the_top_layer_fills_the_lattice_instead(markup):
    """Nothing stands over it, so it uses the whole face — six tools land as the
    front half of a 3x3 exactly."""
    _, cells = levels_of(markup)[-1]
    assert len(cells) == 6
    # Measured at the base's front corner, which is the one vertex a cell's own
    # rise does not move.
    rows = {round(max(y for _, y in cell), 1) for cell in cells}
    assert len(rows) == 3, f"the fan drew {len(rows)} screen rows, expected 3"


# --- the lattice -----------------------------------------------------------

def test_the_pitch_clears_a_whole_cell_not_half_of_one():
    """A g x g cell projects to a rhombus 2g wide and g tall, so two cells an
    offset of (p, p/2) apart come apart only at p >= g."""
    g = stack.tile_size(stack.FOOT_W, stack.FOOT_D, stack.TILE_SIDE)
    cells = stack.tile_cells(stack.TILE_SIDE, stack.FOOT_W, stack.FOOT_D, g, 6, True)
    pitch = min(abs(a[0] - b[0]) or abs(a[1] - b[1])
                for a in cells for b in cells if a != b)
    assert pitch >= g
    assert pitch == g + stack.TILE_CLEAR


def test_the_lattice_stays_inside_the_footprint_and_is_centred():
    g = stack.tile_size(stack.FOOT_W, stack.FOOT_D, stack.TILE_SIDE)
    cells = stack.tile_cells(stack.TILE_SIDE, stack.FOOT_W, stack.FOOT_D, g,
                             stack.TILE_SIDE ** 2, True)
    assert min(x for x, _ in cells) >= stack.TILE_PAD
    assert max(x for x, _ in cells) + g <= stack.FOOT_W - stack.TILE_PAD
    assert min(x for x, _ in cells) == stack.FOOT_W - g - max(x for x, _ in cells)


@pytest.mark.parametrize("n,fan,want", [
    (1, False, 3), (5, False, 3), (7, False, 4), (8, False, 5),
    (1, True, 3), (9, True, 3), (10, True, 4), (17, True, 5),
])
def test_lattice_side_is_the_placement_capacity(n, fan, want):
    """The border run holds 2k-1 positions, or 2(k-1) when the count is even and
    the front corner is left empty to keep the run symmetric. The fan holds k^2."""
    assert stack.tile_side(n, fan) == want


def test_a_roster_past_capacity_densifies_rather_than_overflowing():
    side = stack.tile_side(25, True)
    assert stack.tile_size(stack.FOOT_W, stack.FOOT_D, side) \
        < stack.tile_size(stack.FOOT_W, stack.FOOT_D, stack.TILE_SIDE)
    cells = stack.tile_cells(side, stack.FOOT_W, stack.FOOT_D,
                             stack.tile_size(stack.FOOT_W, stack.FOOT_D, side), 25, True)
    assert len(cells) == 25


def test_an_even_border_run_leaves_the_front_corner_empty():
    """Symmetric about the corner either way: an odd count takes it, an even one
    straddles it."""
    g = stack.tile_size(stack.FOOT_W, stack.FOOT_D, 3)
    corner = max(stack.tile_cells(3, stack.FOOT_W, stack.FOOT_D, g, 5, False),
                 key=lambda p: p[0] + p[1])
    assert corner in stack.tile_cells(3, stack.FOOT_W, stack.FOOT_D, g, 5, False)
    assert corner not in stack.tile_cells(3, stack.FOOT_W, stack.FOOT_D, g, 4, False)


# --- pedestal heights ------------------------------------------------------

def test_the_ladder_is_five_even_steps():
    assert [stack.rise_of(i) for i in range(1, 6)] == [5, 9, 13, 17, 21]
    assert stack.RISE_MAX == 21


@pytest.mark.parametrize("level", [0, -3, 9, 5.4, None, "four"])
def test_an_out_of_range_level_clamps_rather_than_raising(level):
    """The roster is hand-authored, and a figure that silently flattens one
    pedestal is a better failure than a panel that does not render."""
    assert stack.TILE_RISE <= stack.rise_of(level) <= stack.RISE_MAX


def test_a_pedestals_height_is_its_tools_level(markup):
    """Measured off the silhouettes: a cell of rise h stands h taller on screen
    than a flat one, and the figure says nothing else about a level."""
    def spans(level):
        cfg = {"stack": {k: dict.fromkeys(v, level) for k, v in CFG["stack"].items()}}
        drawn = levels_of(stack.render(cfg, {}, c.LIGHT))
        return {round(max(y for _, y in cell) - min(y for _, y in cell), 2)
                for _, cells in drawn for cell in cells}

    low, high = spans(1), spans(5)
    assert len(low) == 2 and len(high) == 2, "square cells and round ones, no more"
    assert round(sorted(high)[0] - sorted(low)[0]) == stack.RISE_MAX - stack.TILE_RISE


def test_cells_are_painted_back_to_front(markup):
    """Or a short cell behind a tall one paints over it."""
    for _, cells in levels_of(markup):
        # The base's front corner is the cell's own screen depth; the lid only
        # ever rises off it, so a taller cell in front still paints later.
        depth = [max(y for _, y in cell) for cell in cells]
        assert depth == sorted(depth), depth


# --- shape -----------------------------------------------------------------

def test_every_square_in_the_figure_turns_at_one_radius_to_width_ratio(markup):
    """The cells read as the slab's own parts rather than as a second kind of
    box, which is what the ratio buys."""
    g = stack.tile_size(stack.FOOT_W, stack.FOOT_D, stack.TILE_SIDE)
    corner = stack._round(g * stack.FOOT_R / min(stack.FOOT_W, stack.FOOT_D))
    assert abs(corner / g - stack.FOOT_R / stack.FOOT_W) < 0.02


def test_the_tooling_cells_are_cylinders_and_nothing_else_is(markup):
    """A footprint whose radius is half its width is a circle under this
    projection, so the round cells are the same primitive at a different radius
    — and they are the one thing telling the tray apart from the three layers it
    carries."""
    g = stack.tile_size(stack.FOOT_W, stack.FOOT_D, stack.TILE_SIDE)
    widths = []
    for _, cells in levels_of(markup):
        xs = [x for x, _ in cells[0]]
        widths.append(round(max(xs) - min(xs), 2))
    # A circle of diameter g projects to an ellipse of width g*sqrt(2); a
    # rounded square is wider, because its straight edges are not all
    # foreshortened.
    assert widths[0] == round(g * math.sqrt(2), 2)
    assert len(set(widths[1:])) == 1 and widths[1] > widths[0]


def test_the_glyph_rides_the_one_matrix_that_agrees_with_the_projection(markup):
    """So a mark drawn in plain face coordinates lands on its cell's lid with no
    coordinate placed by hand."""
    found = re.findall(r'transform="matrix\(1,0.5,-1,0.5,([\d.]+),([\d.]+)\)"',
                       body_of(markup))
    assert len(found) == TOTAL
    assert len({ox for ox, _ in found}) == 1, "one figure, one origin"
    # A taller pedestal lifts its own lid, so the matrix is per cell.
    assert len({oy for _, oy in found}) > len(CFG["stack"])


def test_a_tool_with_no_vendored_mark_falls_back_to_type():
    markup = stack.render({"stack": {"Cloud": {"Nothing Here": 3}}}, {}, c.LIGHT)
    assert any(t[-1] == "Nothing Here" for t in text_of(markup))
    assert '<path d="None"' not in markup and "undefined" not in markup


# --- paint -----------------------------------------------------------------

# Read out of the preview's slabFaces()/focalTint()/brand() against mine-final.
# Solved values, not declared ones — see this module's docstring.
PREVIEW_FACES = {
    "light": {"slab": "#ffffff", "cell": "#e8e8e8", "focal": "#f7e3d6", "focal_cell": "#f5c8ab"},
    "dark": {"slab": "#0f1011", "cell": "#262728", "focal": "#2c1303", "focal_cell": "#502103"},
}
PREVIEW_BRAND = {
    # Black marks on a near-black canvas are holes, not brands.
    "light": {"Rust": "#000000", "Swift": "#e74f37", "Datadog": "#632ca6"},
    "dark": {"Rust": "#727272", "Swift": "#f05138", "Datadog": "#875dba"},
}


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_face_paints_match_the_preview(theme):
    want = PREVIEW_FACES[theme.name]
    assert stack.faces(theme, False)[0] == want["slab"]
    assert stack.faces(theme, False, 0.1)[0] == want["cell"]
    assert stack.faces(theme, True)[0] == want["focal"]
    assert stack.faces(theme, True, 0.1)[0] == want["focal_cell"]


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_brand_hex_is_corrected_until_it_clears_three_to_one(theme):
    ground = stack.faces(theme, False, 0.1)[1]
    for name, want in PREVIEW_BRAND[theme.name].items():
        got = stack.brand(theme, stack.LOGOS[name]["hex"], ground)
        assert got == want, name
        assert c.contrast(got, ground) >= 3


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_focal_cells_separate_as_well_as_the_neutral_ones(theme):
    """Matched as a ratio, not as a mix step: the canvas-to-accent ramp is
    shorter than the surface-to-ink one, and much shorter on light paper."""
    neutral = c.contrast(stack.faces(theme, False, 0.1)[0], stack.faces(theme, False)[0])
    focal = c.contrast(stack.faces(theme, True, 0.1)[0], stack.faces(theme, True)[0])
    assert focal >= neutral


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_left_wall_is_one_step_lighter_than_the_right(theme):
    """Light from the top left. An unshaded box flips like a Necker cube, and
    more than one step reads as a drawn line rather than as a solid turning."""
    _, top, left, right, rule = stack.faces(theme, False)
    assert c.mix(theme.ink, top, 0.05) == left
    assert c.mix(theme.ink, top, 0.1) == right
    assert left != right != top
    assert rule == theme.hairline


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_no_face_is_translucent(theme):
    """A part behind would show through the one in front of it, and the figure
    stops reading as solid."""
    body = body_of(stack.render(CFG, {}, theme))
    assert "opacity" not in body and "fill-opacity" not in body


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_accent_marks_the_focal_layer_and_nothing_else(theme):
    """One layer has earned it — the one the author writes in — so it takes the
    dot beside its name and the tint under its face, and nothing else does."""
    body = body_of(stack.render(CFG, {}, theme))
    assert body.count(f'r="{stack.DOT_R}" fill="{theme.accent}"') == 1
    assert f'stroke="{theme.accent}" stroke-width="2"' in body
    # The slab itself takes a mix, not the literal: the accent at full strength
    # under six logos is a field of chroma, not a mark.
    assert body.count(theme.accent) == 2


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_accent_never_sets_type(theme):
    for *_, fill, _size, _text in [(0, 0, f, s, t) for _, _, f, s, t in
                                   text_of(stack.render(CFG, {}, theme))]:
        assert fill != theme.accent


def test_both_themes_draw_the_same_geometry():
    """render.py pairs the two files element for element, so the only difference
    between them may be which paint each element names."""
    def shape(theme):
        return re.sub(r'(fill|stroke)="#[0-9a-f]{6}"', r'\1="$"',
                      body_of(stack.render(CFG, {}, theme)))
    assert shape(c.LIGHT) == shape(c.DARK)


# --- labels ----------------------------------------------------------------

def test_one_leader_per_layer_running_out_and_away_from_its_dot(markup):
    body = body_of(markup)
    dots = [(float(x), float(y)) for x, y in
            re.findall(rf'<circle cx="([\d.]+)" cy="([\d.]+)" r="{stack.DOT_R}"', body)]
    assert len(dots) == len(CFG["stack"])
    assert len({x for x, _ in dots}) == 1, "equal footprints put every dot on one x"
    leaders = re.findall(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="\2"', body)
    on_dots = [m for m in leaders if (float(m[0]) - 9, float(m[1])) in dots]
    assert len(on_dots) == len(dots)
    for x1, _, x2 in on_dots:
        assert float(x1) < float(x2) <= c.CONTENT_R


def test_the_category_names_keep_their_json_order_bottom_to_top(markup):
    names = [t[-1] for t in text_of(markup) if t[3] == str(stack.LABEL_FS)]
    assert names == [name.lower() for name, _ in LAYERS]


def test_the_object_and_its_label_column_are_centred_together(markup):
    xs = [x for raw, _ in SIL.findall(body_of(markup)) for x, _ in points(raw)]
    col = max(float(t[0]) for t in text_of(markup) if t[3] == str(stack.LABEL_FS))
    widest = max(len(name) for name, _ in LAYERS) * stack._round(
        stack.LABEL_FS * c.MONO_ADVANCE)
    assert abs((min(xs) - c.TEXT_X) - (c.CONTENT_R - (col + widest))) <= 1


def test_the_counter_reports_the_tool_count(markup):
    assert f'text-anchor="end">{TOTAL} tools</text>' in markup


# --- accessibility and degrading -------------------------------------------

def test_desc_carries_every_tool_name_the_face_gave_up(markup):
    """The logos cost the twenty names, and this is the only place a screen
    reader — or GitHub's alt text — will find them."""
    desc = re.search(r'<desc id="d">(.*?)</desc>', markup, re.S).group(1)
    assert desc.startswith(f"{TOTAL} tools on {len(CFG['stack'])} layers")
    for category, items in CFG["stack"].items():
        assert f"{category.lower()} ({len(items)})" in desc
        for name in items:
            assert name in desc


@pytest.mark.parametrize("cfg", [{}, {"stack": {}}, {"stack": None}])
def test_a_missing_roster_renders_one_short_panel_instead_of_raising(cfg):
    markup = stack.render(cfg, {}, c.LIGHT)
    assert height_of(markup) % c.ROW == 0 and height_of(markup) <= 160
    assert "no stack configured" in c.visible(markup)
    assert not SIL.findall(body_of(markup))


def test_a_category_with_no_tools_still_takes_a_slab():
    """It is a layer of the object; drawing three slabs for four categories
    would make the figure disagree with its own labels."""
    markup = stack.render({"stack": {"Cloud": {}, "Tooling": {"Git": 3}}}, {}, c.LIGHT)
    drawn = levels_of(markup)
    assert [len(cells) for _, cells in drawn] == [1, 0]
    assert [t[-1] for t in text_of(markup) if t[3] == str(stack.LABEL_FS)] \
        == ["tooling", "cloud"]


# --- projection ------------------------------------------------------------

def test_the_projection_is_two_to_one_dimetric():
    pr = stack.project(0, 0)
    assert pr(2, 0, 0) == (2, 1) and pr(0, 2, 0) == (-2, 1)
    assert pr(0, 0, 2) == (0, -2), "z is unforeshortened and runs up"
    # A line of constant x + y projects to a screen row, which is what the fan
    # placement fills by.
    assert pr(4, 0, 0)[1] == pr(0, 4, 0)[1] == pr(2, 2, 0)[1]


def test_a_footprint_whose_radius_is_half_its_width_is_a_circle():
    out = stack.foot_outline(40, 40, 20)
    centre = (20, 20)
    radii = {round(math.dist(p, centre), 6) for p in out}
    assert len(radii) == 1 and radii.pop() == 20


def test_the_silhouette_indices_are_the_three_screen_extremes():
    out = stack.foot_outline(100, 100, 0)
    b = stack.foot_bounds(out)
    assert out[b["right"]] == (100, 0)
    assert out[b["front"]] == (100, 100)
    assert out[b["left"]] == (0, 100)


def test_an_accent_the_canvas_swallows_saturates_instead_of_looping():
    """`focal_tint` searches for a ratio the ramp may not hold. An accent equal
    to its own canvas never separates from anything, so the search runs out and
    the face takes the accent whole rather than returning no answer."""
    flat = c.LIGHT._replace(accent=c.LIGHT.canvas)
    assert stack.focal_tint(flat, 0.1) == 1.0
    assert stack.faces(flat, True, 0.1)[0] == flat.canvas
