"""Contribution calendar as an isometric plan.

One block per day of the window, laid out on a 7-row week grid and projected
2:1 isometric. Height encodes the day's contribution count; how far the three
faces are mixed toward the ink encodes its quartile. There is no sky, no night
and no lit windows — the palette has one accent and it is spent on live state,
so this panel is built out of the ink ramp alone.

The ground is paved over the whole week grid rather than over the days that
have data: a window rarely starts on a Monday, and tiling only the days present
punches notches out of the corners of the plane.

The projection puts increasing (col + row) further down and nearer the viewer,
so sorting the blocks on that sum and drawing in order is a painter's
algorithm — no face is ever drawn over a block standing in front of it.
"""
import math

from .. import console as c

ROWS = 7              # one per weekday, as on GitHub's calendar
TILE_W, TILE_H = 44, 22   # a 2:1 diamond; both halves stay whole pixels
HALF_W, HALF_H = TILE_W // 2, TILE_H // 2
MAX_H = 120           # the tallest a block ever draws
MIN_H = 6             # a single contribution still has to be visible

# The west corner of the plane. A 7-row, 26-week calendar projects to a
# rhombus (25 + 6) half-tiles wide plus a tile of overhang — 726px — and 231
# centres that between the rails. Shorter windows sit a little left of centre;
# longer ones than 26 weeks run off the right rail, which is what bounds
# `window_days` from above.
OX = 231

# The plane's own top edge, before the overhang a tall near block needs.
OY = 84

LEVELS = 5            # ground, then four occupied quartiles
WINDOW_DAYS = 182     # 26 weeks, the width OX is cut for

LEGEND_X = c.TEXT_X + 110   # first swatch; "quieter" sits at TEXT_X
LEGEND_PITCH = 24


def _round(value):
    """Round half up. Python's built-in rounds half to even, which would put a
    block one pixel off wherever the square root lands exactly on .5."""
    return math.floor(value + 0.5)


def thresholds_for(values):
    """The three quartile cut points over the days that were built on.

    Quartiles of the active days rather than an even split of the range: one
    40-commit day would otherwise drop every ordinary day into the lowest
    bucket and flatten the skyline into a plain. Quiet days are excluded
    before the split, so a mostly bare window still spreads its few active
    days across all four.
    """
    active = sorted(v for v in values if v > 0)

    def q(p):
        i = math.floor(len(active) * p)
        return (active[i] if i < len(active) else 0) or 1

    return [q(0.25), q(0.5), q(0.75)]


def level(value, cuts):
    """Which of the five intensity buckets `value` falls in: 0 is bare ground."""
    if value == 0:
        return 0
    if value <= cuts[0]:
        return 1
    if value <= cuts[1]:
        return 2
    if value <= cuts[2]:
        return 3
    return 4


def height_for(value, peak, lvl):
    """Square root of the day's share of the peak, off a visible floor.

    Linear would bury an ordinary day next to a 40-commit one; the root keeps
    the middle of the range legible without flattening the top. A bucket-0 day
    has no block at all, and anything above it stands at least MIN_H so a
    single contribution is not a lid lying on its own tile.
    """
    if not lvl:
        return 0
    return max(MIN_H, _round(math.sqrt(value / peak) * MAX_H))


def shades(theme, lvl):
    """(left wall, right wall, roof) for a block in bucket `lvl`.

    Solid mixes rather than one fill at three opacities: the blocks overlap,
    and a translucent face shows whatever stands behind it through its own
    wall, which stops the plan reading as solid. The right wall is the darkest
    face and the roof the lightest, so light arrives from the same direction
    across the whole plane. The right wall saturates at the ink for the top
    bucket, which is where the ramp runs out.
    """
    o = 0.18 + lvl * 0.16
    return (c.mix(theme.ink, theme.canvas, o),
            c.mix(theme.ink, theme.canvas, min(1, o * 1.3)),
            c.mix(theme.ink, theme.canvas, o * 0.62))


def cells_for(values, weeks, peak, cuts):
    """(col, row, level, height) for every tile of the `weeks`-wide grid.

    Column-major, the way GitHub reads a calendar: seven consecutive days fill
    a column top to bottom, then the next week starts a new one. A trailing
    part-week is dropped rather than drawn as a short column.
    """
    out = []
    for i in range(weeks * ROWS):
        lvl = level(values[i], cuts)
        out.append((i // ROWS, i % ROWS, lvl, height_for(values[i], peak, lvl)))
    return out


def overhang_of(cells):
    """How far above the plane's top edge the tallest block reaches.

    A roof sits `h` above its own tile and a tile's own depth is only
    (col + row) half-tiles, so the far corner of the plane has to start that
    much further down for the tallest *near* block to still clear the section
    rule. Measured, not reserved: a window with no tall block near the front
    wastes no vertical space on one.
    """
    return max([0, *(h - (col + row) * HALF_H for col, row, _, h in cells)])


def project(col, row, oy):
    """Screen position of the top vertex of the tile at (col, row)."""
    return OX + (col - row) * HALF_W, oy + (col + row) * HALF_H


def diamond(x, y, dy=0):
    """A ground tile's four corners, optionally lifted `dy` — i.e. a roof."""
    return (f"{x},{y - dy} {x + HALF_W},{y + HALF_H - dy} "
            f"{x},{y + TILE_H - dy} {x - HALF_W},{y + HALF_H - dy}")


def block(theme, x, y, h, lvl):
    """The two visible walls and the roof of the block standing on (x, y).

    Unstroked: at this tile size an outline reads as a gap between neighbours
    rather than as an edge, and the shading alone already separates the faces.
    """
    left, right, roof = shades(theme, lvl)
    return (f'<polygon points="{x - HALF_W},{y + HALF_H} {x},{y + TILE_H} '
            f'{x},{y + TILE_H - h} {x - HALF_W},{y + HALF_H - h}" fill="{left}"/>'
            f'<polygon points="{x},{y + TILE_H} {x + HALF_W},{y + HALF_H} '
            f'{x + HALF_W},{y + HALF_H - h} {x},{y + TILE_H - h}" fill="{right}"/>'
            f'<polygon points="{diamond(x, y, h)}" fill="{roof}"/>')


def legend(theme, y):
    """Four diamonds between "quieter" and "busier", one per occupied bucket.

    These are the one place the panel paints at an opacity instead of mixing:
    nothing overlaps a swatch, and the ladder reads as the same four steps the
    blocks use.
    """
    note = dict(fill=theme.faint, family=c.MONO_STACK, size=11)
    swatches = "".join(
        f'<polygon points="{x},{y - 9} {x + 9},{y - 4} {x},{y + 1} {x - 9},{y - 4}" '
        f'fill="{theme.ink}" opacity="{0.18 + lvl * 0.16:.2f}"/>'
        for lvl, x in enumerate(
            (LEGEND_X + i * LEGEND_PITCH for i in range(LEVELS - 1)), start=1)
    )
    return (c.tx(c.TEXT_X, y, "quieter", **note)
            + "\n" + swatches
            + "\n" + c.tx(c.TEXT_X + 212, y, "busier", **note))


def _empty(theme):
    """A short slice for a profile with no calendar at all."""
    body = (c.heading(theme, 44, "skyline", "0 days") + "\n"
            + c.tx(c.TEXT_X, 88, "no contribution data yet",
                   fill=theme.dim, family=c.MONO_STACK, size=13))
    return c.slice_svg(theme, 160, body, title="Contribution skyline",
                       desc="No contribution data available.")


def render(cfg, data, theme):
    window = (cfg.get("city") or {}).get("window_days") or WINDOW_DAYS
    days = (data.get("calendar") or [])[-window:]
    if not days:
        return _empty(theme)

    weeks = len(days) // ROWS
    values = [n for _, n in days]
    peak = max([*values, 1])
    active = [v for v in values if v > 0]
    cuts = thresholds_for(values)
    # A calendar with no activity at all has no peak day; name the last one
    # rather than leaving the note blank.
    peak_day = days[values.index(peak)][0] if peak in values else days[-1][0]

    cells = cells_for(values, weeks, peak, cuts)
    oy = OY + math.ceil(overhang_of(cells))

    ground, blocks = [], []
    for col, row, lvl, h in cells:
        x, y = project(col, row, oy)
        ground.append(f'<polygon points="{diamond(x, y)}" fill="{theme.surface}" '
                      f'stroke="{theme.hairline}" stroke-width="0.5"/>')
        if lvl:
            blocks.append((col + row, block(theme, x, y, h, lvl)))
    blocks.sort(key=lambda b: b[0])

    # 32px below the plane's lowest corner, which is the far end of the rhombus.
    legend_y = oy + (weeks - 1 + ROWS - 1) * HALF_H + TILE_H + 32

    body = "\n".join([
        c.heading(theme, 44, "skyline", f"{len(days)} days"),
        f'<g>{"".join(ground)}</g>',
        f'<g>{"".join(markup for _, markup in blocks)}</g>',
        legend(theme, legend_y),
        c.tx(c.CONTENT_R, legend_y, f"tallest {peak} on {peak_day}",
             fill=theme.faint, family=c.MONO_STACK, size=11, anchor="end"),
    ])

    desc = (f"Isometric plan of {weeks} weeks: {len(days)} tiles, "
            f"{len(active)} built on, {c.num(sum(values))} contributions. "
            f"Tallest block is {peak} on {peak_day}.")

    return c.slice_svg(theme, c.to_grid(legend_y + 24), body,
                       title="Contribution skyline", desc=desc)
