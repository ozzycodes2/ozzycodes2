"""`~/stats` — a six-cell counter grid.

Stars and forks are deliberately absent: the account has none, and a row of
zeroes says less than nothing. Most of the work here happens in private repos,
so the private share carries the honest signal.

Each cell is a faint label over an ink value, closed by a hairline under the
column it belongs to, which is what separates the two rows without a second
colour or a box. Two tiers, not three: the note that used to sit under each
number was a second quantity in the same voice as the first, and six of them
read as a table nobody asked for.

Languages used to be charted here as a row of bars. They are a polar ring in
`~/stack` now, beside the figure that says which layer the author writes in —
same subject at two scales, and one heading instead of two.
"""
import datetime

from .. import console as c

HEAD_Y = c.HEAD_Y

COLS = 3
COL_W = (c.CONTENT_R - c.TEXT_X) // COLS   # integral, so the columns stay even
GRID_Y = HEAD_Y + c.BODY_DY                # first label baseline
GRID_PITCH = 80                            # label to label, row to row
VALUE_DY = 38
RULE_DY = 58
RULE_INSET = 24                            # gap between a rule and the next column

PAD_BELOW = 24


def _year(raw):
    """The calendar year of an ISO-8601 date, or None if there isn't one.

    Sliced to the date before parsing, so the instant GitHub reports for an
    account's creation is accepted as readily as a bare day.
    """
    try:
        return datetime.date.fromisoformat(str(raw)[:10]).year
    except ValueError:
        return None


def _counters(stats):
    """(label, value) per cell, in reading order across the grid.

    Every cell is kept even when its field is missing: the grid is the panel's
    structure, and a hole in it reads as a rendering fault rather than as an
    absent number. A missing count degrades to zero; a date that cannot be
    parsed degrades to an em dash, because a year is not a quantity and "0"
    would be a claim.
    """
    year = stats.get("year", "")
    counted = int(stats.get("contributions_year") or 0)
    private = int(stats.get("private_year") or 0)
    opened = _year(stats.get("created_at"))
    # Rounded half up, as the preview's Math.round is; Python's round() would
    # send a .5 to the nearest even and disagree on one share in two hundred.
    share = f"{int(private / counted * 100 + 0.5)}%" if counted else "0%"

    return [
        (f"contributions {year}".strip(), c.num(counted)),
        ("pull requests merged", c.num(stats.get("prs_merged"))),
        ("repositories touched", c.num(stats.get("repos_contributed"))),
        ("private share", share),
        ("longest streak", f"{stats.get('streak_longest', 0)}d"),
        ("account opened", str(opened) if opened else "—"),
    ]


def _grid(theme, cells):
    """The counter cells, three to a row, each closed by a rule under its column."""
    out = []
    for i, (label, value) in enumerate(cells):
        x = c.TEXT_X + (i % COLS) * COL_W
        y = GRID_Y + (i // COLS) * GRID_PITCH
        out += [
            c.tx(x, y, label, fill=theme.faint, family=c.MONO_STACK,
                 size=11, ls=0.5),
            c.tx(x, y + VALUE_DY, value, fill=theme.ink, family=c.MONO_STACK,
                 size=32, weight=700, ls="-0.5"),
            f'<line x1="{x}" y1="{y + RULE_DY}" x2="{x + COL_W - RULE_INSET}" '
            f'y2="{y + RULE_DY}" stroke="{theme.hairline}" '
            f'stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>',
        ]
    return out


def render(cfg, data, theme):
    stats = data.get("stats")
    if not stats:
        body = (c.heading(theme, HEAD_Y, "stats") + "\n"
                + c.tx(c.TEXT_X, HEAD_Y + 46, "no stats available",
                       fill=theme.dim, family=c.SANS_STACK, size=15))
        return c.slice_svg(theme, c.to_grid(HEAD_Y + 66), body,
                           title="Counters",
                           desc="No GitHub statistics are available.")

    handle = (cfg.get("identity") or {}).get("handle", "")
    cells = _counters(stats)
    body = "\n".join([
        c.heading(theme, HEAD_Y, "stats",
                  counter=f"captured {stats.get('updated', '?')}",
                  cmd=f"gh api graphql -f login={handle}"),
        *_grid(theme, cells),
    ])
    desc = (f"{c.num(stats.get('contributions_year'))} contributions in "
            f"{stats.get('year', '')}, {c.num(stats.get('prs_merged'))} of "
            f"{c.num(stats.get('prs'))} pull requests merged, "
            f"{c.num(stats.get('repos_contributed'))} repositories touched, "
            f"longest streak {stats.get('streak_longest', 0)} days.")

    # Measured off the last row's closing rule, not off where a row after it
    # would have begun: that phantom row left a dead 40px above the next seam.
    rows = -(-len(cells) // COLS)
    return c.slice_svg(
        theme,
        c.to_grid(GRID_Y + (rows - 1) * GRID_PITCH + RULE_DY + PAD_BELOW),
        body, title="Counters", desc=desc,
    )
