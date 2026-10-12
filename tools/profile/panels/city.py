"""Contribution calendar as an isometric night skyline.

One building per day of the last year, laid out on the same 7-row week grid
GitHub uses, projected 2:1 isometric. Building height encodes the day's
contribution count; colour encodes its intensity bucket. Days with nothing
stay as bare ground tiles, so a quiet stretch reads as undeveloped land
rather than as missing data.

The projection puts increasing (row + col) further down and forward on screen,
so drawing in that order is a painter's-algorithm depth sort — no z-buffer
needed, and no face is ever drawn over a building in front of it.
"""
import datetime

from .. import console as c

ROWS = 7             # one per weekday, as on GitHub's calendar
MAX_STOREYS = 58     # tallest a building may draw, in px
BAND = 400           # vertical space the ground plane is always given

GROUND_FILL = "#0b1120"
GROUND_EDGE = "#16233b"

# Intensity ramp, dark to hot. The top bucket goes magenta so the busiest days
# read instantly against the otherwise cyan skyline.
TOPS = ["#122036", "#0e5a70", "#1189a8", "#25cbe8", c.ALT]
SIDES_L = ["#0b1526", "#0a3a47", "#0b6276", "#179ab3", "#a81d8e"]
SIDES_R = ["#070e1a", "#06222b", "#063c4a", "#0c5c6b", "#6b1259"]


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
    fewer weeks means bigger buildings. Width is the binding constraint at any
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

    def project(self, col, row, x0, y0):
        return x0 + (col - row) * self.tile_w / 2, y0 + (col + row) * self.tile_h / 2

    def diamond(self, x, y):
        hw, hh = self.tile_w / 2, self.tile_h / 2
        return f"M{x:.1f} {y - hh:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z"

    def ground_tile(self, x, y):
        return f'<path d="{self.diamond(x, y)}" fill="{GROUND_FILL}" stroke="{GROUND_EDGE}" stroke-width=".6"/>'

    def building(self, x, y, height, lvl):
        """A cuboid rising from the ground tile centred at (x, y)."""
        hw, hh = self.tile_w / 2, self.tile_h / 2
        top = y - height
        # Only the west-facing and east-facing walls are ever visible in this view.
        return (f'<path d="{self.diamond(x, top)}" fill="{TOPS[lvl]}"/>'
                f'<path d="M{x - hw:.1f} {top:.1f}L{x:.1f} {top + hh:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z" fill="{SIDES_L[lvl]}"/>'
                f'<path d="M{x:.1f} {top + hh:.1f}L{x + hw:.1f} {top:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}Z" fill="{SIDES_R[lvl]}"/>')

    def windows(self, x, y, height, lvl):
        """Lit windows up the visible walls of anything with more than one storey."""
        if height < 15 or self.tile_w < 12:
            return ""
        glass = TOPS[min(lvl + 1, 4)]
        w = max(2.4, self.tile_w * 0.13)
        pitch = max(7.0, self.tile_w * 0.33)
        inset = self.tile_w * 0.16
        out, row = [], y - height + self.tile_h + 1
        while row < y - w - 2:
            out.append(f'<rect x="{x - self.tile_w / 2 + inset:.1f}" y="{row:.1f}" width="{w:.1f}" height="{w * 0.85:.1f}" fill="{glass}" opacity=".6"/>')
            out.append(f'<rect x="{x + inset:.1f}" y="{row + w * 0.8:.1f}" width="{w:.1f}" height="{w * 0.85:.1f}" fill="{glass}" opacity=".38"/>')
            row += pitch
        return "".join(out)


def sky(x0, y0, width, height, count=46):
    """A deterministic starfield plus a crescent moon.

    The positions come from a fixed linear congruential sequence rather than
    `random`, so an unchanged calendar renders byte-identical SVG and the daily
    job pushes no diff.
    """
    stars, seed = [], 20160828
    for i in range(count):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        sx = x0 + (seed >> 8) % width
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        sy = y0 + (seed >> 8) % height
        r = (0.7, 1.0, 1.4)[i % 3]
        stars.append(f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="{c.WHITE}" opacity="{0.2 + 0.07 * (i % 5):.2f}"/>')

    mx, my = x0 + width - 62, y0 + 34
    moon = (f'<circle cx="{mx}" cy="{my}" r="30" fill="{c.ACCENT}" opacity=".16" filter="url(#glow)"/>'
            f'<path d="M{mx + 4} {my - 19}a19 19 0 1 0 0 38a23 23 0 0 1 0 -38Z" fill="#dff6ff" opacity=".9"/>')
    return "".join(stars) + moon


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


def render(cfg, data):
    window = (cfg.get("city") or {}).get("window_days") or 365
    calendar = data.get("calendar") or []
    cells, weeks = layout(calendar, window)
    if not cells:
        body = (c.heading(64, "contribution-city")
                + f'<text x="{c.TEXT_X}" y="112" class="dim">no contribution data yet</text>')
        return c.slice_svg(200, body, title="Contribution city",
                           desc="No contribution data available.", text="-")

    counts = [n for _, _, _, n in cells]
    total, peak = sum(counts), max(counts)
    active = sum(1 for n in counts if n > 0)
    cuts = thresholds_for(counts)
    busiest = max(cells, key=lambda t: t[3])
    start, end = cells[0][2], cells[-1][2]

    grid = Grid(weeks, c.FRAME_R - c.FRAME_L - 2 * 18, BAND)
    x0 = c.FRAME_L + 18 + grid.west
    y0 = 132 + MAX_STOREYS

    tiles, walls, lit = [], [], []
    for col, row, _, count in sorted(cells, key=lambda t: t[0] + t[1]):
        x, y = grid.project(col, row, x0, y0)
        tiles.append(grid.ground_tile(x, y))
        if count <= 0:
            continue
        height = max(4, round(MAX_STOREYS * (count / peak) ** 0.62))
        lvl = level(count, cuts)
        walls.append(grid.building(x, y, height, lvl))
        lit.append(grid.windows(x, y, height, lvl))

    prompt = (f'<text x="{c.TEXT_X}" y="{{y}}" style="font-size:14px">'
              f'<tspan class="ok">$</tspan>'
              f'<tspan class="fg" dx="8">render-city --last {window}d</tspan>'
              f'<tspan class="faint" dx="10">· one building per day</tspan></text>')

    # The strip leaves the upper right empty, so the numbers live in the sky.
    rx = c.FRAME_R - 36
    sky_stats = (
        f'<text x="{rx}" y="{y0 - 6}" text-anchor="end" style="font-size:13px">'
        f'<tspan class="ac" font-weight="700">{total:,}</tspan>'
        f'<tspan class="dim" dx="6">contributions</tspan>'
        f'<tspan class="faint" dx="8">· last {window} days</tspan></text>'
        f'<text x="{rx}" y="{y0 + 16}" text-anchor="end" style="font-size:13px">'
        f'<tspan class="dim">busiest day</tspan>'
        f'<tspan class="alt" dx="6" font-weight="700">{busiest[2]:%b %-d}</tspan>'
        f'<tspan class="faint" dx="8">· {busiest[3]}</tspan></text>'
        f'<text x="{rx}" y="{y0 + 38}" text-anchor="end" class="faint" style="font-size:13px">'
        f'{active} active days</text>'
    )

    # Measured from the reserved band, not the actual depth, so the panel is
    # the same height at every window length.
    legend_y = y0 + BAND + 34
    swatches = "".join(
        f'<rect x="{c.TEXT_X + 58 + i * 15}" y="{legend_y - 8}" width="11" height="11" rx="2" fill="{TOPS[i]}"/>'
        for i in range(5)
    )
    legend = (f'<text x="{c.TEXT_X}" y="{legend_y}" class="faint" style="font-size:12px">quiet</text>'
              f'{swatches}'
              f'<text x="{c.TEXT_X + 58 + 5 * 15 + 6}" y="{legend_y}" class="faint" style="font-size:12px">skyscraper</text>')

    body = "\n".join([
        c.heading(64, "contribution-city", "// 03"),
        c.stagger([prompt], 100, 20)[0],
        f'<g>{sky(c.FRAME_L + 1, 118, c.FRAME_R - c.FRAME_L - 2, 150)}</g>',
        sky_stats,
        f'<g>{"".join(tiles)}</g>',
        f'<g>{"".join(walls)}</g>',
        f'<g>{"".join(lit)}</g>',
        legend,
    ])

    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, "
            f"each building's height set by that day's contribution count. {total:,} contributions across "
            f"{active} active days between {start:%-d %B %Y} and {end:%-d %B %Y}; "
            f"busiest day {busiest[2]:%-d %B %Y} with {busiest[3]}.")

    return c.slice_svg(
        c.to_grid(legend_y + 28), body,
        title="Contribution city", desc=desc,
        text="$·-/0123456789 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
