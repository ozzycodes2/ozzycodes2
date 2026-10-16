"""`~/route` as a timeline: one segment per role, positioned by date.

Spacing is the real interval, never an even one — the whole claim of the type is
that distance on the axis is time. A role is a span rather than an instant, so a
tenure is a 3px run over the hairline axis and the gaps between runs are the
gaps between jobs; a circle marks where each one started.

An entry with no employer is a milestone — a circle and a label, no run. It is
what lets the axis open on something that happened rather than on a job, and it
is why a label block is built from the tiers it has rather than from a fixed
three.

The accent falls on the tenure still being held, which is this panel's one datum
worth pointing at. The milestone circle the type reference would paint in the
accent stays in the ink: a second mark on the same role spends the budget twice
on one event, and size already carries it.

Labels alternate above and below so two roles a few months apart do not collide,
and each is clamped to the content column — mono advances 0.6em, so a block's
real extent is known before it is drawn.

The roster is config, not data: the panel draws the same figure on a machine
that has never fetched. Only the month the open tenure runs to comes from the
clock.
"""
import datetime
import math
import re

from .. import console as c

HEAD_Y = c.HEAD_Y
AXIS_Y = 164      # clears the command transcript by the height of a label block
TICK = 4          # half a year mark, drawn through the axis
SEG_W = 3         # a tenure's own weight over the axis
DOT_R = 4
EYEBROW = 11
NAME = 13
SUBLABEL = 11
PAD_BELOW = 28
YEAR = 32         # the span's bounding years, as ground — the largest mono step
WASH = 0.1        # how much ink that ground carries

# Label baselines, as offsets from the axis. Both blocks read eyebrow, employer,
# title from the top, so a label means the same thing wherever it sits; the
# alternation only decides which side it falls on. A block with fewer than three
# tiers keeps the ones nearest the axis, so every label still starts where its
# drop line ends rather than floating a tier away from it.
ABOVE = (-72, -54, -36)
BELOW = (44, 62, 80)
DROP_ABOVE = (-30, -9)   # the 1px line binding a label block to its event
DROP_BELOW = (9, 30)

HEIGHT = c.to_grid(AXIS_Y + BELOW[2] + PAD_BELOW)

MONTH = re.compile(r"^(\d{4})(?:-(\d{1,2}))?$")


def _n(value):
    """A coordinate, at the two decimals the preview's `r2` emits."""
    v = math.floor(value * 100 + 0.5) / 100
    return int(v) if v == int(v) else v


def month_of(value):
    """Months since year 0 for `YYYY` or `YYYY-MM`, or None for anything else."""
    m = MONTH.match(str(value or "").strip())
    if not m:
        return None
    month = int(m.group(2) or 1)
    return int(m.group(1)) * 12 + month - 1 if 1 <= month <= 12 else None


def span_of(months):
    """`2y 7mo`, `7mo`, `1y` — a tenure, for the alt text rather than the drawing."""
    parts = [f"{months // 12}y" if months // 12 else "", f"{months % 12}mo" if months % 12 else ""]
    return " ".join(p for p in parts if p) or "0mo"


def layout(roster, now):
    """The roster as events on one honest scale, or None if it dates none of them.

    `end` is absent on the role still being held, which is the only one the panel
    dates from the clock rather than from the file. Entries the author has not
    dated are dropped rather than placed at the origin: a role at the wrong point
    on a scale that claims to be honest is worse than a role left out.

    A dated `end` is the last month held, so the run reaches the month after it.
    Taken literally the figure would lose a month off every tenure and leave a
    visible gap between two roles that in fact ran back to back.

    An entry with no employer is a milestone rather than a tenure: it is one
    month wide, it draws no run, and it never takes the accent however it is
    dated. An open `end` means "still held", which a thing that happened once
    cannot be.
    """
    rows = []
    for entry in roster or []:
        start = month_of(entry.get("start"))
        if not entry.get("org"):
            end = start
        elif entry.get("end") is None:
            end = now
        else:
            end = month_of(entry["end"])
            end = None if end is None else end + 1
        if start is None or end is None or end < start:
            continue
        rows.append({**entry, "from": start, "to": end})
    if not rows:
        return None
    rows.sort(key=lambda r: r["from"])

    t0 = rows[0]["from"]
    t1 = max(r["to"] for r in rows)
    # A single role dated to one month would divide by zero, and a career is not
    # an instant: the scale falls back to the month so the lone segment is a dot.
    total = max(1, t1 - t0)

    def at(m):
        return c.TEXT_X + (m - t0) / total * (c.CONTENT_R - c.TEXT_X)

    for i, r in enumerate(rows):
        org = r.get("org")
        r.update(x0=at(r["from"]), x1=at(r["to"]),
                 milestone=not org,
                 current=bool(org) and r.get("end") is None,
                 above=i % 2 == 0,
                 dates=f"{r['start']} .. {r.get('end') or 'now'}" if org else str(r["start"]),
                 months=r["to"] - r["from"])

    # Whole years inside the span, which is the only scale annotation the axis
    # carries: the heading counts the span and every label carries its own dates.
    first, last = -(-t0 // 12), t1 // 12
    ticks = [at(y * 12) for y in range(first, last + 1)]
    return {
        "rows": rows,
        "ticks": [x for x in ticks if c.TEXT_X <= x <= c.CONTENT_R],
        "from": t0 // 12,
        "to": t1 // 12,
    }


def _empty(theme):
    """A short slice when no roster is configured. Rule 10: degrade, don't crash."""
    body = "\n".join([
        c.heading(theme, HEAD_Y, "route"),
        c.tx(c.TEXT_X, HEAD_Y + c.BODY_DY, "no route configured", fill=theme.dim,
             family=c.MONO_STACK, size=13),
    ])
    return c.slice_svg(theme, c.to_grid(HEAD_Y + c.BODY_DY + 8), body,
                       title="Work route", desc="No route is configured: 0 roles.")


def render(cfg, _data, theme, now=None):
    """`now` is the month the open tenure runs to; it defaults to this one."""
    if now is None:
        today = datetime.datetime.now(datetime.timezone.utc)
        now = today.year * 12 + today.month - 1

    plan = layout(cfg.get("route"), now)
    if not plan:
        return _empty(theme)

    # The years bounding the span, set large and washed into the canvas as ground
    # for the figure. They are the one run in the window deliberately below the
    # floor for type, and they can be: the heading's counter prints the same two
    # years in faint and the alt text states them, so nothing is carried here
    # alone. Painted first, so the axis and every label sit over them. At the 72px
    # the type reference uses they would need their own step on the scale; 32 is
    # the largest the console already declares and reads as ground at this wash.
    ground = c.mix(theme.ink, theme.canvas, WASH)
    years = "\n".join([
        c.tx(c.TEXT_X, AXIS_Y + BELOW[2], str(plan["from"]), fill=ground,
             family=c.MONO_STACK, size=YEAR, weight=700),
        c.tx(c.CONTENT_R, AXIS_Y + BELOW[2], str(plan["to"]), fill=ground,
             family=c.MONO_STACK, size=YEAR, weight=700, anchor="end"),
    ])

    # Every 1px line in this panel snaps, for the reason deviation 2 in
    # BACKPORT.md gives: the slice is rasterised at 880px and resampled to the
    # page column, and an unsnapped hairline axis blurs across two device
    # columns. The tenure runs are 3px with round caps and stay off it.
    marks = "\n".join(
        f'<line x1="{_n(x)}" y1="{AXIS_Y - TICK}" x2="{_n(x)}" y2="{AXIS_Y + TICK}" '
        f'stroke="{theme.faint}" stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>'
        for x in plan["ticks"]
    )
    runs = "\n".join(
        f'<line x1="{_n(r["x0"])}" y1="{AXIS_Y}" x2="{_n(r["x1"])}" y2="{AXIS_Y}" '
        f'stroke="{theme.accent if r["current"] else theme.dim}" stroke-width="{SEG_W}" '
        f'stroke-linecap="round"/>'
        for r in plan["rows"] if not r["milestone"]
    )

    events = []
    for r in plan["rows"]:
        # The employer's tier carries the milestone's name when there is no
        # employer, so the ink line of a block is always the thing that happened.
        lines = [(s, o) for s, o in [
            (r["dates"], dict(fill=theme.faint, size=EYEBROW, ls=0.5)),
            (r.get("org") or r.get("title"), dict(fill=theme.ink, size=NAME, weight=700)),
            (r.get("title") if r.get("org") else None, dict(fill=theme.dim, size=SUBLABEL)),
        ] if s]
        # Mono advances 0.6em, and a tracked line advances its tracking on top of
        # that — dropping the second term leaves the eyebrow nine pixels wider
        # than the clamp believes it is.
        width = max(len(str(s)) * (o["size"] * 0.6 + o.get("ls", 0)) for s, o in lines)
        x = _n(max(c.TEXT_X, min(r["x0"], c.CONTENT_R - width)))
        side = ABOVE if r["above"] else BELOW
        ys = side[len(side) - len(lines):] if r["above"] else side[:len(lines)]
        d0, d1 = DROP_ABOVE if r["above"] else DROP_BELOW
        events += [
            f'<circle cx="{_n(r["x0"])}" cy="{AXIS_Y}" r="{DOT_R}" fill="{theme.ink}"/>',
            f'<line x1="{_n(r["x0"])}" y1="{AXIS_Y + d0}" x2="{_n(r["x0"])}" '
            f'y2="{AXIS_Y + d1}" stroke="{theme.faint}" stroke-width="{c.EDGE_W}" '
            f'shape-rendering="crispEdges"/>',
            *(c.tx(x, AXIS_Y + ys[i], s, family=c.MONO_STACK, **o)
              for i, (s, o) in enumerate(lines)),
        ]

    roster = "; ".join(
        ", ".join(str(part) for part in [
            r.get("org"), r.get("title"),
            r["dates"] if r["milestone"] else f"{r['dates']} ({span_of(r['months'])})",
        ] if part)
        for r in plan["rows"])
    roles = sum(1 for r in plan["rows"] if not r["milestone"])
    body = "\n".join([
        c.heading(theme, HEAD_Y, "route", counter=f"{plan['from']} — {plan['to']}",
                  cmd=f"traceroute --since={plan['from']}"),
        years,
        f'<line x1="{c.TEXT_X}" y1="{AXIS_Y}" x2="{c.CONTENT_R}" y2="{AXIS_Y}" '
        f'stroke="{theme.faint}" stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>',
        marks, runs, *events,
    ])
    desc = (f"{roles} roles from {plan['from']} to {plan['to']}, "
            f"spaced by date on one axis: {roster}.")

    return c.slice_svg(theme, HEIGHT, body, title="Work route", desc=desc)
