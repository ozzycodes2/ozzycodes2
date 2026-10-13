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

# Every face is outlined in near-background. Without it, neighbouring days of
# equal height merge into one slab and the skyline reads as terrain rather than
# as one building per day.
MORTAR = "#04070e"

WIN_COLS = (0.17, 0.56)   # fraction along each wall, from its outer corner
WIN_W = 0.27              # window width, as a fraction of the wall
WIN_H = 4.6               # window height in px
WIN_PITCH = 9.5           # storey pitch in px

# Roughly one window in seven is wired to a failing ballast. Brightness is
# carried by fill-opacity so the keyframes own `opacity` outright and the two
# multiply; animating a single channel would make the east wall flare to the
# west wall's brightness every time a pane relit. The six variants differ in
# period and start offset because one shared clock makes a whole district blink
# in unison, which reads as a dropped frame rather than as a city.
FLICKERS = 6
CITY_CSS = """@keyframes flick{0%,92%,100%{opacity:1}93%{opacity:.08}95%{opacity:.66}97%{opacity:.14}}
.fl0{animation:flick 5s linear 0s infinite}
.fl1{animation:flick 6.2s linear -1.4s infinite}
.fl2{animation:flick 4.3s linear -2.6s infinite}
.fl3{animation:flick 7.1s linear -0.5s infinite}
.fl4{animation:flick 5.6s linear -3.3s infinite}
.fl5{animation:flick 3.8s linear -1.9s infinite}"""


def _jitter(*coords):
    """A stable pseudo-random int from integer coordinates.

    Hashed rather than drawn from a sequence so a window's flicker does not
    depend on how many windows were emitted before it — otherwise one extra
    contribution reshuffles the whole skyline and the daily job commits a diff
    touching every building.
    """
    n = 0
    for v in coords:
        n = (n * 1103515245 + v * 12345 + 54321) & 0x7FFFFFFF
    return n

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
        return (f'<path d="{self.diamond(x, top)}" fill="{TOPS[lvl]}" stroke="{MORTAR}" stroke-width=".8"/>'
                f'<path d="M{x - hw:.1f} {top:.1f}L{x:.1f} {top + hh:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z" fill="{SIDES_L[lvl]}" stroke="{MORTAR}" stroke-width=".8"/>'
                f'<path d="M{x:.1f} {top + hh:.1f}L{x + hw:.1f} {top:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}Z" fill="{SIDES_R[lvl]}" stroke="{MORTAR}" stroke-width=".8"/>')

    def pane(self, ax, ay, bx, by, depth):
        """One window: the wall quad between two points on a top edge, dropped `depth`.

        The walls are sheared, not axis-aligned — the west wall's top edge falls
        at the projection's +1/2 gradient and the east wall's rises at -1/2 — so
        a window has to be a parallelogram that inherits that gradient. An
        upright rect would sit at an angle to the wall it is painted on.
        """
        return (f"M{ax:.1f} {ay + depth:.1f}L{bx:.1f} {by + depth:.1f}"
                f"L{bx:.1f} {by + depth + WIN_H:.1f}L{ax:.1f} {ay + depth + WIN_H:.1f}Z")

    def windows(self, x, y, height, lvl, col, row):
        """Lit windows gridded onto both visible walls.

        Storeys are measured down from each wall's own top edge, so a row on the
        west wall meets its opposite number across the corner instead of
        drifting past it.
        """
        if height < 16 or self.tile_w < 16:
            return ""
        hw, hh = self.tile_w / 2, self.tile_h / 2
        glass = TOPS[min(lvl + 1, 4)]
        top = y - height

        # Keep the lowest row clear of the ground and the top row clear of the
        # roof slab, so no pane overhangs an edge of the wall it belongs to.
        depths = []
        d = 5.0
        while d + WIN_H <= height - 4:
            depths.append(d)
            d += WIN_PITCH

        out = []
        for i, d in enumerate(depths):
            for j, f in enumerate(WIN_COLS):
                g = f + WIN_W
                walls = (
                    # West wall, parameterised from its outer corner inward.
                    (x - hw + f * hw, top + f * hh, x - hw + g * hw, top + g * hh),
                    # East wall, from the near corner outward.
                    (x + f * hw, top + hh - f * hh, x + g * hw, top + hh - g * hh),
                )
                for side, (ax, ay, bx, by) in enumerate(walls):
                    n = _jitter(col, row, i, j * 2 + side)
                    cls = f' class="fl{n % FLICKERS}"' if n % 7 == 0 else ""
                    out.append(f'<path d="{self.pane(ax, ay, bx, by, d)}" '
                               f'fill="{glass}" fill-opacity="{0.78 if side == 0 else 0.46}"'
                               f'{cls}/>')
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

    # Ground first as its own layer — a tile never occludes a building, since
    # the near edge of one meets the far edge of the next exactly. Each
    # building's walls and its windows then go out together: emitted as
    # separate layers, every window would draw after every wall, and the far
    # side of the grid would shine through the blocks standing in front of it.
    tiles, blocks = [], []
    for col, row, _, count in sorted(cells, key=lambda t: t[0] + t[1]):
        x, y = grid.project(col, row, x0, y0)
        tiles.append(grid.ground_tile(x, y))
        if count <= 0:
            continue
        height = max(4, round(MAX_STOREYS * (count / peak) ** 0.62))
        lvl = level(count, cuts)
        blocks.append(grid.building(x, y, height, lvl)
                      + grid.windows(x, y, height, lvl, col, row))

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
        f'<g>{"".join(blocks)}</g>',
        legend,
    ])

    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, "
            f"each building's height set by that day's contribution count. {total:,} contributions across "
            f"{active} active days between {start:%-d %B %Y} and {end:%-d %B %Y}; "
            f"busiest day {busiest[2]:%-d %B %Y} with {busiest[3]}.")

    return c.slice_svg(
        c.to_grid(legend_y + 28), body,
        title="Contribution city", desc=desc, css=CITY_CSS,
        text="$·-/0123456789 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
