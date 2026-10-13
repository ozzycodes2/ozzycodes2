"""Contribution calendar as an isometric night skyline.

One building per day of the last year, laid out on the same 7-row week grid
GitHub uses, projected 2:1 isometric. Building height encodes the day's
contribution count; the roof colour encodes its intensity bucket. The walls are
the same navy on every building, so height and roof carry the whole signal and
the mass below reads as one continuous city.

The ground is laid over the full week grid rather than over the days that have
data. The last 365 days do not start on a Monday or end on a Sunday, so the
first and last columns are partial, and tiling only the days present punches
notches out of two corners of the plane.

The projection puts increasing (row + col) further down and forward on screen,
so drawing in that order is a painter's-algorithm depth sort — no z-buffer
needed, and no face is ever drawn over a building in front of it.
"""
import datetime
import math

from .. import console as c

ROWS = 7             # one per weekday, as on GitHub's calendar
BAND = 400           # vertical space the ground plane is always given
MAX_H = 130          # headroom above the plane, and the tallest any tower draws
MIN_STOREYS = 8      # a single contribution still has to be visible

GROUND_FILL = "#161b22"
GROUND_EDGE = "#0d1117"

# One navy for every building. Only the roof carries the bucket: varying the
# walls too made adjacent days of different levels read as separate districts
# rather than as one skyline.
WALL_L = "#1a2440"
WALL_R = "#111831"
ROOFS = ["#0c2d6b", "#14458f", "#1554c0", "#2f81f7", "#1fd5ff"]

# Glass, not a tint of the roof. Windows pick up the colour of what is behind
# the glass, which is the same lit interior on every building regardless of how
# busy its day was. The east wall faces away from the light, so its panes are
# the dimmer of the two.
WIN_ON = "#7df9ff"
WIN_ON_SIDE = "#4cc9f0"
WIN_OFF = "#111827"

WIN_COLS = (0.18, 0.58)   # fraction along each wall, from its outer corner
WIN_W = 0.26              # window width, as a fraction of the wall
WIN_H = 0.128             # window height, as a fraction of the tile width
WIN_PITCH = 0.28          # storey pitch, as a fraction of the tile width

# Three clocks for the failing ballasts and three for the stars. Sharing one
# would make a whole district blink in unison, which reads as a dropped frame
# rather than as a city.
VARIANTS = 3
CITY_CSS = """@keyframes flick{0%,40%,100%{opacity:1}45%,60%{opacity:.12}}
@keyframes twinkle{0%,100%{opacity:1}50%{opacity:.2}}
.fl0{animation:flick 5s linear infinite}
.fl1{animation:flick 7s linear 2s infinite}
.fl2{animation:flick 9s linear 4s infinite}
.tw0{animation:twinkle 3s ease-in-out infinite}
.tw1{animation:twinkle 4.5s ease-in-out 1.2s infinite}
.tw2{animation:twinkle 6s ease-in-out 2.4s infinite}"""


def _jitter(*coords):
    """A stable pseudo-random int from integer coordinates.

    Hashed rather than drawn from a sequence so a window's state does not
    depend on how many windows were emitted before it — otherwise one extra
    contribution reshuffles the whole skyline and the daily job commits a diff
    touching every building.
    """
    n = 0
    for v in coords:
        n = (n * 1103515245 + v * 12345 + 54321) & 0x7FFFFFFF
    return n


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
        # Towers, not lids. A building has to stand several tiles tall to read
        # as a building at all; capped at the headroom the panel reserves, so a
        # short window's much larger tiles cannot grow a tower off the top.
        self.max_h = min(self.tile_w * 4.6, MAX_H)

    def project(self, col, row, x0, y0):
        return x0 + (col - row) * self.tile_w / 2, y0 + (col + row) * self.tile_h / 2

    def diamond(self, x, y):
        hw, hh = self.tile_w / 2, self.tile_h / 2
        return f"M{x:.1f} {y - hh:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z"

    def ground_tile(self, x, y):
        return f'<path d="{self.diamond(x, y)}" fill="{GROUND_FILL}" stroke="{GROUND_EDGE}" stroke-width=".6"/>'

    def height_for(self, count, peak):
        """Square root of the day's share of the peak, off a visible floor.

        Linear would bury an ordinary day next to a 66-commit one; the root
        keeps the middle of the range legible without flattening the top.
        """
        return MIN_STOREYS + (self.max_h - MIN_STOREYS) * math.sqrt(count / peak)

    def building(self, x, y, height, lvl):
        """A cuboid rising from the ground tile centred at (x, y).

        Unstroked. An outline at this tile size reads as a black gap between
        neighbours rather than as an edge, and the shading alone already
        separates the two walls.
        """
        hw, hh = self.tile_w / 2, self.tile_h / 2
        top = y - height
        # Only the west-facing and east-facing walls are ever visible in this view.
        return (f'<path d="M{x - hw:.1f} {top:.1f}L{x:.1f} {top + hh:.1f}L{x:.1f} {y + hh:.1f}L{x - hw:.1f} {y:.1f}Z" fill="{WALL_L}"/>'
                f'<path d="M{x:.1f} {top + hh:.1f}L{x + hw:.1f} {top:.1f}L{x + hw:.1f} {y:.1f}L{x:.1f} {y + hh:.1f}Z" fill="{WALL_R}"/>'
                f'<path d="{self.diamond(x, top)}" fill="{ROOFS[lvl]}"/>')

    def pane(self, ax, ay, bx, by, rise, tall):
        """One window: the wall quad between two points on a base edge, raised.

        The walls are sheared, not axis-aligned — the west wall's base falls at
        the projection's +1/2 gradient and the east wall's rises at -1/2 — so a
        window has to be a parallelogram that inherits that gradient. An upright
        rect would sit at an angle to the wall it is painted on.
        """
        return (f"M{ax:.1f} {ay - rise:.1f}L{bx:.1f} {by - rise:.1f}"
                f"L{bx:.1f} {by - rise - tall:.1f}L{ax:.1f} {ay - rise - tall:.1f}Z")

    def windows(self, x, y, height, col, row):
        """Lit, dark and failing windows gridded onto both visible walls.

        Storeys are stacked up from the base rather than down from the roof, so
        the bottom row of every building on a street lands at the same height
        and the ragged edge falls under the roofline where it is hidden.

        Returns the markup for one building, batched by state: three paths carry
        every steady pane, and only the few that flicker need their own element.
        """
        if height < 16 or self.tile_w < 14:
            return ""
        hw, hh = self.tile_w / 2, self.tile_h / 2
        tall, pitch = self.tile_w * WIN_H, self.tile_w * WIN_PITCH
        storeys = int((height - tall - 3) // pitch)
        if storeys < 1:
            return ""

        # Base edges, outer corner first: the west wall runs down from the west
        # corner to the south corner, the east wall back up to the east corner.
        walls = ((x - hw, y, x, y + hh), (x, y + hh, x + hw, y))
        on, side, off, failing = [], [], [], []
        for storey in range(storeys):
            rise = 4 + storey * pitch
            for j, f in enumerate(WIN_COLS):
                for s, (wax, way, wbx, wby) in enumerate(walls):
                    n = _jitter(col, row, storey, j * 2 + s)
                    ax = wax + (wbx - wax) * f
                    ay = way + (wby - way) * f
                    bx = wax + (wbx - wax) * (f + WIN_W)
                    by = way + (wby - way) * (f + WIN_W)
                    seg = self.pane(ax, ay, bx, by, rise, tall)
                    if n % 100 >= 55:            # dark flat
                        if (n // 100) % 100 < 50:  # or no window cut at all
                            off.append(seg)
                        continue
                    if (n // 10_000) % 100 < 4:
                        failing.append((seg, s, n))
                    else:
                        (on if s == 0 else side).append(seg)

        out = []
        for segs, fill in ((off, WIN_OFF), (on, WIN_ON), (side, WIN_ON_SIDE)):
            if segs:
                out.append(f'<path d="{"".join(segs)}" fill="{fill}"/>')
        for seg, s, n in failing:
            fill = WIN_ON if s == 0 else WIN_ON_SIDE
            out.append(f'<path d="{seg}" fill="{fill}" class="fl{n % VARIANTS}"/>')
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
        cls = f' class="tw{i % VARIANTS}"' if i % 3 == 0 else ""
        stars.append(f'<circle{cls} cx="{sx}" cy="{sy}" r="{r}" fill="{c.WHITE}" opacity="{0.2 + 0.07 * (i % 5):.2f}"/>')

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
    # The reserved headroom, not the tallest tower this window actually drew,
    # so the panel's height does not move when `window_days` changes.
    y0 = 132 + MAX_H

    # Ground first as its own layer — a tile never occludes a building, since
    # the near edge of one meets the far edge of the next exactly. Each
    # building's walls and its windows then go out together: emitted as
    # separate layers, every window would draw after every wall, and the far
    # side of the grid would shine through the blocks standing in front of it.
    tiles = [grid.ground_tile(*grid.project(col, row, x0, y0))
             for col in range(weeks) for row in range(ROWS)]
    blocks = []
    for col, row, _, count in sorted(cells, key=lambda t: t[0] + t[1]):
        if count <= 0:
            continue
        x, y = grid.project(col, row, x0, y0)
        height = grid.height_for(count, peak)
        blocks.append(grid.building(x, y, height, level(count, cuts))
                      + grid.windows(x, y, height, col, row))

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
        f'<tspan class="ac" dx="6" font-weight="700">{busiest[2]:%b %-d}</tspan>'
        f'<tspan class="faint" dx="8">· {busiest[3]}</tspan></text>'
        f'<text x="{rx}" y="{y0 + 38}" text-anchor="end" class="faint" style="font-size:13px">'
        f'{active} active days</text>'
    )

    # Measured from the reserved band, not the actual depth, so the panel is
    # the same height at every window length.
    legend_y = y0 + BAND + 34
    ramp = [GROUND_FILL] + ROOFS
    swatches = "".join(
        f'<rect x="{c.TEXT_X + 58 + i * 15}" y="{legend_y - 8}" width="11" height="11" rx="2" fill="{fill}"/>'
        for i, fill in enumerate(ramp)
    )
    legend = (f'<text x="{c.TEXT_X}" y="{legend_y}" class="faint" style="font-size:12px">quiet</text>'
              f'{swatches}'
              f'<text x="{c.TEXT_X + 58 + len(ramp) * 15 + 6}" y="{legend_y}" class="faint" style="font-size:12px">skyscraper</text>')

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
