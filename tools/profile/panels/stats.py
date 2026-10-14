"""`~/stats` — a six-cell counter grid over a language chart.

Stars and forks are deliberately absent: the account has none, and a row of
zeroes says less than nothing. Most of the work here happens in private repos,
so the private share carries the honest signal.

Each cell is a three-tier stack — faint label, ink value, dim note — closed by a
hairline under the column it belongs to, which is what separates the two rows
without a second colour or a box.

The language chart is whole-repository byte totals over every repository worked
in, organization repositories included. It describes the codebases rather than
the author's own output. The six bars are shares of *every* language's bytes,
not of the six charted, so they do not sum to 100%.
"""
import datetime

from .. import console as c

HEAD_Y = 44

COLS = 3
COL_W = (c.CONTENT_R - c.TEXT_X) // COLS   # integral, so the columns stay even
GRID_Y = 92                                # first label baseline
GRID_PITCH = 84                            # label to label, row to row
VALUE_DY = 34
NOTE_DY = 54
RULE_DY = 66
RULE_INSET = 24                            # gap between a rule and the next column

TOP_N = 6
LANG_LABEL_Y = 278
# The name is set in mono so its width is a character count; 120px is the gutter
# the longest name may occupy before it touches the bar.
NAME_W = 120
NAME_SIZE = 13
BAR_X = c.TEXT_X + NAME_W
BAR_W = c.CONTENT_R - BAR_X - 56           # 56 leaves the percentage its column
BAR_H = 12
BAR_Y0 = 300
BAR_PITCH = 26
TRACK_OPACITY = "0.06"
MAX_NAME = int(NAME_W / (NAME_SIZE * c.MONO_ADVANCE))


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
    """(label, value, note) per cell, in reading order across the grid.

    Every cell is kept even when its field is missing: the grid is the panel's
    structure, and a hole in it reads as a rendering fault rather than as an
    absent number. A missing count degrades to zero; a date that cannot be
    parsed degrades to an em dash, because a year is not a quantity and "0"
    would be a claim.
    """
    year = stats.get("year", "")
    counted = int(stats.get("contributions_year") or 0)
    private = int(stats.get("private_year") or 0)
    opened, now = _year(stats.get("created_at")), _year(stats.get("updated"))
    # Rounded half up, as the preview's Math.round is; Python's round() would
    # send a .5 to the nearest even and disagree on one share in two hundred.
    share = f"{int(private / counted * 100 + 0.5)}%" if counted else "0%"
    age = f"{now - opened} years" if opened and now else ""

    return [
        (f"contributions {year}".strip(), c.num(counted),
         f"{c.num(stats.get('contributions_all'))} all time"),
        ("pull requests merged", c.num(stats.get("prs_merged")),
         f"of {c.num(stats.get('prs'))} opened"),
        ("repositories touched", c.num(stats.get("repos_contributed")),
         f"{stats.get('repos_public', 0)} public · {stats.get('orgs', 0)} org"),
        ("private share", share, f"{c.num(private)} commits"),
        ("longest streak", f"{stats.get('streak_longest', 0)}d",
         f"current {stats.get('streak_current', 0)}d"),
        ("account opened", str(opened) if opened else "—", age),
    ]


def _grid(theme, stats):
    """The counter cells, three to a row, each closed by a rule under its column."""
    out = []
    for i, (label, value, note) in enumerate(_counters(stats)):
        x = c.TEXT_X + (i % COLS) * COL_W
        y = GRID_Y + (i // COLS) * GRID_PITCH
        out += [
            c.tx(x, y, label, fill=theme.faint, family=c.MONO_STACK,
                 size=11, ls=0.5),
            c.tx(x, y + VALUE_DY, value, fill=theme.ink, family=c.MONO_STACK,
                 size=30, weight=700, ls="-0.5"),
            c.tx(x, y + NOTE_DY, note, fill=theme.dim, family=c.MONO_STACK,
                 size=12),
            f'<line x1="{x}" y1="{y + RULE_DY}" x2="{x + COL_W - RULE_INSET}" '
            f'y2="{y + RULE_DY}" stroke="{theme.hairline}" '
            f'stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>',
        ]
    return out


def _bars(theme, top, total):
    """Name, track, fill and share for each charted language.

    The leading language is the one fact this chart exists to deliver, so it is
    the bar that wears the accent and the only name set in the ink. Everything
    below it steps back a tenth of an opacity per row, which keeps the order
    legible where the bytes are close without a second hue to rank them by.
    """
    out = []
    for i, (name, size) in enumerate(top):
        share = size / total
        y = BAR_Y0 + i * BAR_PITCH
        width = max(2, int(BAR_W * share + 0.5))
        shown = name if len(name) <= MAX_NAME else name[:MAX_NAME - 1] + "…"
        fill = (f'fill="{theme.accent}"' if i == 0 else
                f'fill="{theme.ink}" opacity="{0.82 - i * 0.1:.2f}"')
        out += [
            c.tx(c.TEXT_X, y + 10, shown,
                 fill=theme.ink if i == 0 else theme.dim,
                 family=c.MONO_STACK, size=NAME_SIZE),
            f'<rect x="{BAR_X}" y="{y}" width="{BAR_W}" height="{BAR_H}" '
            f'rx="{c.R_CHIP}" fill="{theme.ink}" opacity="{TRACK_OPACITY}"/>',
            f'<rect x="{BAR_X}" y="{y}" width="{width}" height="{BAR_H}" '
            f'rx="{c.R_CHIP}" {fill}/>',
            c.tx(c.CONTENT_R, y + 10, f"{share * 100:.1f}%", fill=theme.faint,
                 family=c.MONO_STACK, size=12, anchor="end"),
        ]
    return out


def render(_cfg, data, theme):
    stats = data.get("stats")
    if not stats:
        body = (c.heading(theme, HEAD_Y, "stats") + "\n"
                + c.tx(c.TEXT_X, HEAD_Y + 46, "no stats available",
                       fill=theme.dim, family=c.SANS_STACK, size=15))
        return c.slice_svg(theme, c.to_grid(HEAD_Y + 66), body,
                           title="Counters and language mix",
                           desc="No GitHub statistics are available.")

    langs = {k: v for k, v in (stats.get("languages") or {}).items() if v}
    total = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:TOP_N]

    body = [
        c.heading(theme, HEAD_Y, "stats",
                  counter=f"captured {stats.get('updated', '?')}"),
        *_grid(theme, stats),
        c.tx(c.TEXT_X, LANG_LABEL_Y, "languages by bytes", fill=theme.faint,
             family=c.MONO_STACK, size=11, ls=0.5),
    ]

    if top:
        body += _bars(theme, top, total)
        chart = (f" Top language {top[0][0]} at "
                 f"{top[0][1] / total * 100:.1f}% of {c.num(total)} bytes.")
    else:
        body.append(c.tx(c.TEXT_X, BAR_Y0 + 10, "no language data",
                         fill=theme.dim, family=c.MONO_STACK, size=NAME_SIZE))
        chart = " No language data was recorded."

    desc = (f"{c.num(stats.get('contributions_year'))} contributions in "
            f"{stats.get('year', '')}, {c.num(stats.get('prs_merged'))} of "
            f"{c.num(stats.get('prs'))} pull requests merged, "
            f"{c.num(stats.get('repos_contributed'))} repositories touched."
            + chart)

    return c.slice_svg(
        theme, c.to_grid(BAR_Y0 + (len(top) or 1) * BAR_PITCH + 20),
        "\n".join(body), title="Counters and language mix", desc=desc,
    )
