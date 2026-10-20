"""The grid editor's saved drawing, as geometry the figures can be built from.

    python -m tools.brains.shape

Prints the `BRAIN_EDGES` literal for `design-preview/site/assets/brains.js`.
The editor at `tools/brains/editor/` is where both hemispheres are drawn, and
this is the only thing between that file and the published figure. Which is why
the invariants live here: on the grid, a side and not a chord, inside the card.

The two halves are drawn in different things and read by different functions.
The left is triangle sides — `sides`, validated by `strays`. The right is
circles inscribed in the six triangles around a tip, each cut into six arcs —
`circles`, validated by `odd_circles`. Only the left is emitted as a literal so
far; the right half's figure is still the hand-tuned `BRAIN_ARCS`.

The vertical shift is this module's one liberty. The editor's grid runs past
the bottom of the card so that a shape can be drawn without also being placed;
placing it is a translation, and a translation of a lattice is the same
lattice.
"""
import argparse
import json
import math
import pathlib
import sys

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

# A circle is inscribed in the hexagon the six triangles around a tip form:
# radius COL clears its vertical sides exactly and its slanted ones by a third
# of a pixel. The triangles cut it into six arcs, one per wedge.
SECTORS = len(NEIGHBOURS)
R = COL
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


def spoke(centre, k):
    """Where spoke `k` leaves the circle around `centre`. The arc ends here, so
    it begins and ends on the construction rather than somewhere chosen by eye.
    """
    du, dv = NEIGHBOURS[k % SECTORS]
    h = math.hypot(du, dv)
    return (centre[0] + R * du / h, centre[1] + R * dv / h)


def extent(drawn):
    """`(u0, v0, u1, v1)` of what is drawn, or `None`. Both halves have to
    occupy one extent or the pinned pair reads as two drawings at two sizes."""
    if not drawn:
        return None
    pts = [p for a, b, _ in drawn for p in (a, b)]
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    return (min(us), min(vs), max(us), max(vs))


def shift(drawn):
    """The vertical translation that places `drawn` inside the card.

    Raises if no translation does, which means the drawing is taller than 400
    and the shape, not the placement, has to change.
    """
    box = extent(drawn)
    if box is None:
        return 0
    _, v0, _, v1 = box
    if v1 - v0 > H - 2 * PAD:
        raise ValueError(f"the drawing is taller than the card ({v1 - v0} over {H - 2 * PAD})")
    return PAD - v0


def shifted(drawn, dv):
    return [((a[0], a[1] + dv), (b[0], b[1] + dv), d) for a, b, d in drawn]


def as_js(state):
    """The `BRAIN_EDGES` literal, placed and ready to paste into `brains.js`."""
    blocks = []
    for side in SIDES:
        # Only the left half is drawn in sides. The right half's own drawing is
        # circles, which this does not emit, so its edge list is empty — not a
        # placeholder for sides nobody has drawn yet.
        bad = strays(state, side) if side == "left" else []
        if bad:
            raise ValueError(f"{side}: not a triangle side: {bad}")
        drawn = shifted(s := sides(state, side), shift(s)) if side == "left" else []
        rows = "".join(
            f"\n    [[{a[0]}, {a[1]}], [{b[0]}, {b[1]}], {int(d)}]," for a, b, d in drawn
        )
        blocks.append(f"  {side}: [{rows}\n  ],")
    return (
        "/* Every side of the construction grid the figure draws, as\n"
        "   `[[u0, v0], [u1, v1], dashed]` in the local frame. Generated from the\n"
        "   grid editor by `python -m tools.brains.shape`; edit the drawing there,\n"
        "   not the numbers here. Nodes are derived from this graph, not listed. */\n"
        "const BRAIN_EDGES = {\n" + "\n".join(blocks) + "\n};\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=pathlib.Path, default=STATE)
    args = ap.parse_args(argv)
    state = load(args.state)
    print(as_js(state), end="")
    drawn = circles(state, "right")
    if drawn:
        # The literal would otherwise look complete, get pasted, and leave the
        # right half with whatever arcs it already had.
        print(
            f"note: {len(drawn)} circle{'s' * (len(drawn) != 1)} drawn on the right half,"
            " which this does not emit",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
