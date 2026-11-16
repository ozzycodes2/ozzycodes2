"""The grid editor's saved drawing, as geometry the figures can be built from.

    python -m tools.brains.shape

Prints the `BRAIN_EDGES` and `BRAIN_RUNS` literals for
`design-preview/site/assets/brains.js`. The editor at `tools/brains/editor/` is
where both hemispheres are drawn, and this is the only thing between that file
and the published figure. Which is why the invariants live here: on the grid, a
side and not a chord, inside the card.

The two halves are drawn in different things and read by different functions.
The left is triangle sides — `sides`, validated by `strays`. The right is
circles through the six tips around a tip, each cut into six arcs — `circles`,
validated by `odd_circles`, emitted as the maximal contiguous chains `arc_runs`
collects.

Placement is this module's one liberty. The editor's grid runs past the bottom
of the card and leaves room at the midline, so that a shape can be drawn without
also being positioned; positioning it is a translation, and a translation of a
lattice is the same lattice. Down the card it goes to the pad exactly; in from
the midline it goes by whole columns, which keeps it on the construction.
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).parent
STATE = HERE / "editor" / "state.json"

# The construction grid: vertices at {(48p, 28q) : p ≡ q (mod 2)} from ORIGIN.
# Sides 56 and 55.57, angles 60.5°/59.7°/59.7° — balanced to within half a
# degree, which is as close as a 4px grid gets to isometric, since the exact
# run against a 28 rise is 28√3 = 48.497.
COL, ROW, RISE = 48, 28, 56
ORIGIN = (104, 20)
# The six neighbours a side may join, in order of angle from straight up. A
# circle's arcs are numbered off this order, so it is not arbitrary.
NEIGHBOURS = ((0, -RISE), (COL, -ROW), (COL, ROW), (0, RISE), (-COL, ROW), (-COL, -ROW))
STEPS = tuple(sorted(NEIGHBOURS))

# A circle passes through the six tips around a tip, not inside the hexagon
# they form: radius RISE, so each sixth of it begins and ends on a vertex of the
# grid. Which is what lets the drawing join up — two circles on neighbouring
# tips cross at exactly the two tips they both border, so arcs from different
# circles share an endpoint rather than crossing somewhere between vertices.
# Inscribed instead (radius COL) every arc stays inside its own triangle and
# nothing meets anything: arcs that should join land 4px apart.
SECTORS = len(NEIGHBOURS)
R = RISE
FULL = "1" * SECTORS

H = 400
# Clearance at the card's edges for a 4px stroke and the small node on it.
PAD = 4

SIDES = ("left", "right")


def load(path=STATE):
    """The editor's state, or an empty board if it has never saved."""
    path = pathlib.Path(path)
    if not path.exists():
        return {s: {} for s in SIDES}
    saved = json.loads(path.read_text())
    return {s: saved.get(s) or {} for s in SIDES}


def _point(text):
    u, v = text.split(",")
    return (int(u), int(v))


def sides(state, side):
    """`[(a, b, dashed), …]` for one half, endpoints and list both ordered.

    The order is stable so that regenerating an unchanged drawing produces a
    byte-identical figure; the editor's JSON is keyed by the order of clicking.
    """
    out = []
    for key, kind in state.get(side, {}).items():
        a, b = sorted(_point(t) for t in key.split("|"))
        out.append((a, b, kind == "dashed"))
    return sorted(out)


def on_grid(point):
    """Whether a point is a vertex of the construction grid."""
    u, v = point
    p, r = divmod(u - ORIGIN[0], COL)
    q, r2 = divmod(v - ORIGIN[1], ROW)
    return r == 0 and r2 == 0 and (p - q) % 2 == 0


def strays(state, side):
    """Sides that are not sides: a chord across several triangles, or a segment
    with an endpoint off the grid. The editor cannot emit one; a hand-edited
    `state.json` can."""
    bad = []
    for a, b, _ in sides(state, side):
        if not (on_grid(a) and on_grid(b)) or (b[0] - a[0], b[1] - a[1]) not in STEPS:
            bad.append((a, b))
    return bad


def circles(state, side):
    """`[(centre, mask), …]` for one half, ordered by centre.

    The mask is one flag per arc, in `NEIGHBOURS` order: arc `k` spans the wedge
    from the spoke toward neighbour `k` to the next one round.
    """
    return sorted((_point(k), v) for k, v in state.get(side, {}).items())


def odd_circles(state, side):
    """Circles the editor could not have saved: a centre off the grid, a mask
    that is not six flags, or a circle with every arc cut away — which the
    editor deletes rather than keeping as an invisible centre."""
    bad = []
    for centre, mask in circles(state, side):
        if not on_grid(centre) or set(mask) - {"0", "1"} or len(mask) != SECTORS or "1" not in mask:
            bad.append((centre, mask))
    return bad


def tip(centre, k):
    """The vertex arc `k` runs to. Arcs begin and end on the construction, which
    is where arcs of different circles meet."""
    du, dv = NEIGHBOURS[k % SECTORS]
    return (centre[0] + du, centre[1] + dv)


def runs(mask):
    """The maximal chains of contiguous arcs around one circle, as `(k, n)` —
    `n` sixths from spoke `k`. A whole circle is one chain of six.

    A chain is published as one path, so the tips it passes through carry no
    seam: two arcs of one circle meet tangentially, and a stroke broken there
    would need a mark over the break to look continuous.
    """
    on = [c == "1" for c in mask]
    if all(on):
        return [(0, SECTORS)]
    out = []
    for k in range(SECTORS):
        # Start only where a chain starts: this sixth drawn, the one before not.
        if not on[k] or on[k - 1]:
            continue
        n = 0
        while on[(k + n) % SECTORS]:
            n += 1
        out.append((k, n))
    return out


def arc_runs(state, side):
    """`[(centre, k, n), …]` for one half, ordered, the way `sides` is."""
    return sorted(
        (centre, k, n) for centre, mask in circles(state, side) for k, n in runs(mask)
    )


def run_points(centre, k, n):
    """The tips one run spans, in order. A whole circle names each once."""
    span = range(n) if n == SECTORS else range(n + 1)
    return [tip(centre, k + j) for j in span]


def side_points(drawn):
    return [p for a, b, _ in drawn for p in (a, b)]


def arc_points(drawn):
    return [p for run in drawn for p in run_points(*run)]


def extent(pts):
    """`(u0, v0, u1, v1)` of a drawing, or `None`. Both halves have to occupy
    one extent or the pinned pair reads as two drawings at two sizes."""
    if not pts:
        return None
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    return (min(us), min(vs), max(us), max(vs))


def shift(pts):
    """The vertical translation that places a drawing inside the card.

    Tips are enough to place the right half even though its arcs bulge past
    them: a circle's lowest and highest points are at 90° and 270°, which are
    themselves tips, so no sweep reaches above or below the run it belongs to.
    Sideways it does — the extreme at 0° falls mid-sweep — but nothing here
    translates horizontally.

    Raises if no translation places it, which means the drawing is taller than
    400 and the shape, not the placement, has to change.
    """
    box = extent(pts)
    if box is None:
        return 0
    _, v0, _, v1 = box
    if v1 - v0 > H - 2 * PAD:
        raise ValueError(f"the drawing is taller than the card ({v1 - v0} over {H - 2 * PAD})")
    return PAD - v0


def column_shift(pts):
    """The horizontal translation that brings a drawing up against the midline.

    By whole columns rather than to the pad exactly: the drawing is anchored on
    the gutter, and a fraction of a column would buy a few pixels at the cost of
    taking every vertex off the construction. Whatever is left over is the
    clearance the marks on the inner edge need anyway.
    """
    box = extent(pts)
    if box is None:
        return 0
    return -COL * ((box[0] - PAD) // COL)


def shifted(drawn, du, dv):
    return [((a[0] + du, a[1] + dv), (b[0] + du, b[1] + dv), d) for a, b, d in drawn]


GENERATED = (
    "Generated from the grid editor by `python -m tools.brains.shape`; edit\n"
    "   the drawing there, not the numbers here. Nodes are derived from this\n"
    "   graph, not listed."
)


def _block(side, rows):
    return f"  {side}: [{''.join(rows)}\n  ],"


def edges_js(state):
    """The `BRAIN_EDGES` literal, placed and ready to paste into `brains.js`."""
    blocks = []
    for side in SIDES:
        # Only the left half is drawn in sides, so the right one's list is empty
        # — not a placeholder for sides nobody has drawn yet.
        drawn = []
        if side == "left":
            if bad := strays(state, side):
                raise ValueError(f"{side}: not a triangle side: {bad}")
            pts = side_points(s := sides(state, side))
            drawn = shifted(s, column_shift(pts), shift(pts))
        blocks.append(_block(side, [
            f"\n    [[{a[0]}, {a[1]}], [{b[0]}, {b[1]}], {int(d)}]," for a, b, d in drawn
        ]))
    return (
        "/* Every side of the construction grid the figure draws, as\n"
        "   `[[u0, v0], [u1, v1], dashed]` in the local frame.\n"
        f"   {GENERATED} */\n"
        "const BRAIN_EDGES = {\n" + "\n".join(blocks) + "\n};\n"
    )


def runs_js(state):
    """The `BRAIN_RUNS` literal, placed the same way."""
    blocks = []
    for side in SIDES:
        drawn = []
        if side == "right":
            if bad := odd_circles(state, side):
                raise ValueError(f"{side}: not a circle the editor could save: {bad}")
            d = arc_runs(state, side)
            # A circle with every sixth drawn is a closed shape, which is an
            # outline — the thing neither half has. The editor draws one on the
            # first click at a tip, so this is what an unfinished circle looks
            # like, not a corrupt file.
            if shut := [c for c, _, n in d if n == SECTORS]:
                raise ValueError(f"{side}: closes, cut an arc away: {shut}")
            pts = arc_points(d)
            du, dv = column_shift(pts), shift(pts)
            drawn = [((c[0] + du, c[1] + dv), k, n) for c, k, n in d]
        blocks.append(_block(side, [
            f"\n    [{c[0]}, {c[1]}, {k}, {n}]," for c, k, n in drawn
        ]))
    return (
        "/* Every arc the figure draws, as `[cu, cv, spoke, sixths]` in the local\n"
        "   frame: a run of `sixths` consecutive arcs around the circle on `cu, cv`,\n"
        "   beginning at the tip toward neighbour `spoke`.\n"
        f"   {GENERATED} */\n"
        "const BRAIN_RUNS = {\n" + "\n".join(blocks) + "\n};\n"
    )


def as_js(state):
    return f"{edges_js(state)}\n{runs_js(state)}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=pathlib.Path, default=STATE)
    args = ap.parse_args(argv)
    print(as_js(load(args.state)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
