"""Contribution calendar as an isometric plan.

One block per day of the last year, laid out on the same 7-row week grid GitHub
uses, projected 2:1 isometric. Block height encodes the day's contribution
count; how far the three faces are shaded toward the ink encodes its intensity
bucket. There is no sky, no night and no lit windows — the palette has one
accent and it is spent on live state, so this panel is built out of the ink
ramp alone.

The ground is laid over the full week grid rather than over the days that have
data. The last 365 days do not start on a Monday or end on a Sunday, so the
first and last columns are partial, and tiling only the days present punches
notches out of two corners of the plane.

The projection puts increasing (row + col) further down and forward on screen,
so drawing in that order is a painter's-algorithm depth sort — no z-buffer
needed, and no face is ever drawn over a block in front of it.
"""
import datetime
import math

from .. import console as c

ROWS = 7             # one per weekday, as on GitHub's calendar
BAND = 400           # vertical space the ground plane is always given
MAX_H = 130          # headroom above the plane, and the tallest any block draws
MIN_STOREYS = 8      # a single contribution still has to be visible

LEVELS = 5           # ground, then four occupied quartiles


def shades(theme, lvl):
    """(roof, west wall, east wall) for a block in intensity bucket `lvl`.

    Solid mixes rather than one fill at three opacities: the blocks overlap, and
    a translucent face shows whatever stands behind it through its own wall,
    which stops the plan reading as solid. The two walls are fixed fractions of
    the roof, so light always arrives from the same direction.
    """
    t = 0.20 + lvl * 0.17
    return tuple(c.mix(theme.ink, theme.canvas, t * f) for f in (1, 0.72, 0.52))


def thresholds_for(counts):
    """Quartile cut points over the active days.

    Quartiles rather than an even split of the range: one 66-commit day would
    otherwise push every ordinary day into the lowest bucket and flatten the
    skyline into a plain.
    """
    active = sorted(n for n in counts if n > 0)
    if not active:
        return [1, 2, 3, 4]
    return [max(1, active[min(int(len(active) * q), len(active) - 1)])
            for q in (0.3, 0.6, 0.82, 0.94)]


def level(count, cuts):
    if count <= 0:
        return 0
    for i, cut in enumerate(cuts):
        if count <= cut:
            return i + 1
    return 4


class Grid:
    """The isometric ground plane, sized to fill `width` without exceeding `band`.

    A 7-row, N-week calendar projects to a diamond spanning (N - 1 + 6)
    half-tiles horizontally, so the tile size falls out of the week count:
    fewer weeks means bigger blocks. Width is the binding constraint at any
    sensible window; `band` only guards a very short one, where tiles sized to
    fill the width would make the strip taller than the panel reserves.

    The panel always reserves `band` vertically whatever the window, so
    changing `window_days` does not change the README's layout.
    """

    def __init__(self, weeks, width, band):
        self.diag = weeks - 1 + (ROWS - 1)
        # Half a tile of slack at each end: `diag` spans the outermost tile
        # *centres*, and each end tile reaches tile_w/2 beyond its centre.
        self.tile_w = min(2 * width / (self.diag + 2), 4 * band / self.diag)
        self.tile_h = self.tile_w / 2
        self.depth = self.diag * self.tile_h / 2
        self.west = self.tile_w / 2 + (ROWS - 1) * self.tile_w / 2
        # Blocks, not lids. One has to stand several tiles tall to read as a
        # block at all; capped at the headroom the panel reserves, so a short
        # window's much larger tiles cannot grow one off the top.
        self.max_h = min(self.tile_w * 4.6, MAX_H)

    def project(self, col, row, x0, y0):
        return x0 + (col - row) * self.tile_w / 2, y0 + (col + row) * self.tile_h / 2

    def diamond(self, x, y):
        hw, hh = self.tile_w / 2, self.tile_h / 2
        return f"M{x:.1f} {y - hh:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z"

    def ground_tile(self, theme, x, y):
        return (f'<path d="{self.diamond(x, y)}" fill="{c.mix(theme.ink, theme.canvas, 0.06)}" '
                f'stroke="{c.mix(theme.ink, theme.canvas, 0.12)}" stroke-width=".6"/>')

    def height_for(self, count, peak):
        """Square root of the day's share of the peak, off a visible floor.

        Linear would bury an ordinary day next to a 66-commit one; the root
        keeps the middle of the range legible without flattening the top.
        """
        return MIN_STOREYS + (self.max_h - MIN_STOREYS) * math.sqrt(count / peak)

    def block(self, theme, x, y, height, lvl):
        """A cuboid rising from the ground tile centred at (x, y).

        Unstroked. An outline at this tile size reads as a gap between
        neighbours rather than as an edge, and the shading alone already
        separates the two walls.
        """
        hw, hh = self.tile_w / 2, self.tile_h / 2
        top = y - height
        roof, west, east = shades(theme, lvl)
        # Only the west-facing and east-facing walls are ever visible in this view.
        return (f'<path d="M{x - hw:.1f} {top:.1f}L{x:.1f} {top + hh:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z" fill="{west}"/>'
                f'<path d="M{x:.1f} {top + hh:.1f}L{x + hw:.1f} {top:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}Z" fill="{east}"/>'
                f'<path d="{self.diamond(x, top)}" fill="{roof}"/>')


def layout(calendar, window_days=None):
    """(col, row, date, count) per day on GitHub's week grid, plus week count.

    `window_days` trims to the most recent N days first. A shorter window means
    fewer weeks, which Grid turns into larger tiles — so the strip fills the
    frame either way, and a profile whose activity is concentrated in recent
    months does not render as mostly empty land.
    """
    days = [(datetime.date.fromisoformat(d), n) for d, n in calendar]
    if not days:
        return [], 0
    if window_days:
        days = days[-window_days:]
    first = days[0][0]
    origin = first - datetime.timedelta(days=first.weekday())
    cells = [((day - origin).days // 7, day.weekday(), day, n) for day, n in days]
    return cells, max(col for col, _, _, _ in cells) + 1


def render(cfg, data, theme):
    window = (cfg.get("city") or {}).get("window_days") or 365
    calendar = data.get("calendar") or []
    cells, weeks = layout(calendar, window)
    if not cells:
        body = (c.heading(theme, 64, "contribution-city")
                + f'<text x="{c.TEXT_X}" y="112" class="body dim">no contribution data yet</text>')
        return c.slice_svg(theme, 200, body, title="Contribution city",
                           desc="No contribution data available.", text="-")

    counts = [n for _, _, _, n in cells]
    total, peak = sum(counts), max(counts)
    active = sum(1 for n in counts if n > 0)
    cuts = thresholds_for(counts)
    busiest = max(cells, key=lambda t: t[3])
    start, end = cells[0][2], cells[-1][2]

    grid = Grid(weeks, c.FRAME_R - c.FRAME_L - 2 * 18, BAND)
    x0 = c.FRAME_L + 18 + grid.west
    # The reserved headroom, not the tallest block this window actually drew,
    # so the panel's height does not move when `window_days` changes.
    y0 = 96 + MAX_H

    # Ground first as its own layer — a tile never occludes a block, since the
    # near edge of one meets the far edge of the next exactly.
    tiles = [grid.ground_tile(theme, *grid.project(col, row, x0, y0))
             for col in range(weeks) for row in range(ROWS)]
    blocks = []
    for col, row, _, count in sorted(cells, key=lambda t: t[0] + t[1]):
        if count <= 0:
            continue
        x, y = grid.project(col, row, x0, y0)
        blocks.append(grid.block(theme, x, y, grid.height_for(count, peak),
                                 level(count, cuts)))

    prompt = (f'<text x="{c.TEXT_X}" y="{{y}}" class="mono dim">'
              f'<tspan>❯</tspan>'
              f'<tspan class="ink" dx="8">render-city --last {window}d</tspan>'
              f'<tspan dx="10">· one block per day</tspan></text>')

    # The strip leaves the upper right empty, so the numbers live there.
    rx = c.CONTENT_R
    figures = (
        f'<text x="{rx}" y="{y0 - 50}" text-anchor="end">'
        f'<tspan class="mono ink">{total:,}</tspan>'
        f'<tspan class="caption dim" dx="6">contributions</tspan>'
        f'<tspan class="caption dim" dx="8">· last {window} days</tspan></text>'
        f'<text x="{rx}" y="{y0 - 28}" text-anchor="end">'
        f'<tspan class="caption dim">busiest day</tspan>'
        f'<tspan class="mono ink" dx="6">{busiest[2]:%b %-d}</tspan>'
        f'<tspan class="caption dim" dx="8">· {busiest[3]}</tspan></text>'
        f'<text x="{rx}" y="{y0 - 6}" text-anchor="end" class="caption dim">'
        f'{active} active days</text>'
    )

    # Measured from the reserved band, not the actual depth, so the panel is
    # the same height at every window length.
    legend_y = y0 + BAND + 34
    swatches = "".join(
        f'<path d="M{c.TEXT_X + 50 + i * 20} {legend_y - 10}l7 3.5l-7 3.5l-7 -3.5Z" '
        f'fill="{c.mix(theme.ink, theme.canvas, 0.06) if i == 0 else shades(theme, i)[0]}"/>'
        for i in range(LEVELS)
    )
    legend = (f'<text x="{c.TEXT_X}" y="{legend_y}" class="caption dim">quiet</text>'
              f'{swatches}'
              f'<text x="{c.TEXT_X + 50 + LEVELS * 20}" y="{legend_y}" class="caption dim">busiest</text>')

    body = "\n".join([
        c.heading(theme, 64, "contribution-city"),
        c.stagger([prompt], 100, 20)[0],
        figures,
        f'<g>{"".join(tiles)}</g>',
        f'<g>{"".join(blocks)}</g>',
        legend,
    ])

    desc = (f"Contribution city: an isometric plan with one block per day of the last year, "
            f"each block's height set by that day's contribution count. {total:,} contributions across "
            f"{active} active days between {start:%-d %B %Y} and {end:%-d %B %Y}; "
            f"busiest day {busiest[2]:%-d %B %Y} with {busiest[3]}.")

    return c.slice_svg(
        theme, c.to_grid(legend_y + 28), body,
        title="Contribution city", desc=desc,
        text="❯·-/0123456789 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
