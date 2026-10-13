"""`~/stats` — a counter grid, a one-line profile summary, and a language chart.

Stars and forks are deliberately absent: the account has none, and a row of
zeroes says less than nothing. Most of the work here happens in private repos,
so the private contribution count carries the honest signal.

The language chart is whole-repository byte totals over every repository worked
in, organization repositories included. It describes the codebases rather than
the author's own output; `desc` says so, since the bars cannot.
"""
import datetime

from .. import console as c

COL_L = c.TEXT_X
COL_R = c.FRAME_R - 36
COLS = 3
TOP_N = 6

HEAD_Y = 38
LABEL_FS = 11.5
VALUE_FS = 30

NAME_W = 104      # language-name column, 13 chars at 13px
BAR_X = COL_L + NAME_W + 8
BAR_R = 744       # stops short of the right-aligned percentage
BAR_H = 10

DEFS = (f'<linearGradient id="lang" gradientUnits="userSpaceOnUse" '
        f'x1="{BAR_X}" y1="0" x2="{BAR_R}" y2="0">'
        f'<stop offset="0" stop-color="{c.ACCENT}"/>'
        f'<stop offset="1" stop-color="{c.ALT}"/></linearGradient>')


def _counters(s):
    """(label, value, suffix) per cell, in reading order across the grid.

    The private count yields its cell to the follower count when it is zero,
    which happens whenever the fetching token cannot see private work. A
    counter reading 0 asserts that none exists, which would be a stronger and
    falser claim than leaving it out.
    """
    n = lambda key: f"{s.get(key, 0):,}"
    third = (("PRIVATE THIS YEAR", n("private_year"), "") if s.get("private_year")
             else ("FOLLOWERS", n("followers"), ""))
    return [
        (f"CONTRIBUTIONS {s.get('year', '')}".strip(), n("contributions_year"), ""),
        ("ALL TIME", n("contributions_all"), ""),
        third,
        ("PRS MERGED", n("prs_merged"), ""),
        ("LONGEST STREAK", n("streak_longest"), " days"),
        ("REPOS CONTRIBUTED", n("repos_contributed"), ""),
    ]


def _cell(x, label_y, label, value, suffix):
    tail = (f'<tspan class="dim" dx="6" style="font-size:15px">{c.e(suffix)}</tspan>'
            if suffix else "")
    value_y = label_y + 32
    return f'''<text x="{x}" y="{label_y}" class="faint" letter-spacing="1" style="font-size:{LABEL_FS}px">{c.e(label)}</text>
<text x="{x}" y="{value_y}" font-weight="700" fill="{c.ACCENT}" filter="url(#soft)" opacity=".55" style="font-size:{VALUE_FS}px">{c.e(value)}</text>
<text x="{x}" y="{value_y}" font-weight="700" style="font-size:{VALUE_FS}px"><tspan class="ac">{c.e(value)}</tspan>{tail}</text>'''


# Spelled out rather than taken from strftime("%B"), which is locale-sensitive
# and would translate the month on a runner with LC_TIME set.
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def _member_since(raw):
    try:
        when = datetime.datetime.strptime(str(raw)[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"member since {MONTHS[when.month - 1]} {when.year}"


def _lang_rows(langs, y0, pitch):
    """Top-N languages as name / proportional bar / share of the top-N total."""
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:TOP_N]
    total = sum(size for _, size in top) or 1
    biggest = top[0][1] or 1
    rows, shares = [], []
    for i, (name, size) in enumerate(top):
        y = y0 + i * pitch
        pct = 100 * size / total
        shares.append((name, pct))
        width = max(3, round((BAR_R - BAR_X) * size / biggest, 1))
        shown = name if len(name) <= 13 else name[:12] + "…"
        rows.append(f'''<g class="ln" style="animation-delay:{0.40 + i * 0.08:.2f}s">
<text x="{COL_L}" y="{y}" class="fg" style="font-size:13px">{c.e(shown)}</text>
<rect x="{BAR_X}" y="{y - 9}" width="{BAR_R - BAR_X}" height="{BAR_H}" fill="{c.ACCENT}" fill-opacity=".07"/>
<rect x="{BAR_X}" y="{y - 9}" width="{width}" height="{BAR_H}" fill="url(#lang)" opacity=".5" filter="url(#soft)"/>
<rect x="{BAR_X}" y="{y - 9}" width="{width}" height="{BAR_H}" fill="url(#lang)"/>
<rect x="{round(BAR_X + width - 2, 1)}" y="{y - 9}" width="2" height="{BAR_H}" fill="{c.WHITE}" opacity=".75"/>
<text x="{COL_R}" y="{y}" text-anchor="end" class="dim" style="font-size:12px">{pct:.1f}%</text>
</g>''')
    return "\n".join(rows), shares


def render(_cfg, data):
    s = data.get("stats")
    if not s:
        body = (c.heading(HEAD_Y, "stats")
                + f'<text x="{COL_L}" y="{HEAD_Y + 46}" class="dim">no stats available</text>')
        return c.slice_svg(c.to_grid(HEAD_Y + 66), body, title="GitHub stats",
                           desc="No GitHub statistics are available.")

    body = [c.heading(HEAD_Y, "stats", counter=f"[ UPDATED {s.get('updated', '?')} ]")]

    cells = _counters(s)
    step = (COL_R - COL_L) // COLS        # integral, so the columns stay even
    for i, (label, value, suffix) in enumerate(cells):
        x = COL_L + step * (i % COLS)
        label_y = 86 + (i // COLS) * 72
        body.append(f'<g class="ln" style="animation-delay:{0.15 + i * 0.07:.2f}s">'
                    + _cell(x, label_y, label, value, suffix) + "</g>")

    since = _member_since(s.get("created_at"))
    orgs = s.get("orgs", 0)
    parts = [p for p in (
        since,
        f"{s.get('repos_public', 0):,} of {s.get('repos', 0):,} repos public",
        f"{orgs:,} organization{'' if orgs == 1 else 's'}" if orgs else "",
    ) if p]
    meta = " · ".join(parts)
    body.append(f'<g class="ln" style="animation-delay:0.60s">'
                f'<text x="{COL_L}" y="234" class="faint" style="font-size:13px">{c.e(meta)}</text></g>')

    body.append(f'<line x1="{COL_L}" y1="258" x2="{COL_R}" y2="258" '
                f'stroke="{c.ACCENT}" stroke-opacity=".15"/>')
    body.append(f'<text x="{COL_L}" y="288" class="faint" letter-spacing="1" '
                f'style="font-size:{LABEL_FS}px">TOP LANGUAGES BY BYTES</text>')

    langs = s.get("languages") or {}
    if langs:
        rows, shares = _lang_rows(langs, 318, 26)
        body.append(rows)
        last_y = 318 + (len(shares) - 1) * 26
        chart = ", ".join(f"{name} {pct:.1f}%" for name, pct in shares)
    else:
        body.append(f'<text x="{COL_L}" y="318" class="dim" style="font-size:13px">no language data</text>')
        last_y, chart = 318, "none recorded"

    desc = (
        f"GitHub stats updated {s.get('updated', 'unknown')}: "
        f"{s.get('contributions_year', 0):,} contributions in {s.get('year', '')}, "
        f"{s.get('contributions_all', 0):,} all time, "
        + (f"{s['private_year']:,} of them in private repositories, "
           if s.get("private_year") else "") +
        f"{s.get('prs_merged', 0):,} pull requests merged, "
        f"longest streak {s.get('streak_longest', 0):,} days, "
        f"{s.get('repos_contributed', 0):,} repositories contributed to. {meta}. "
        # States the basis: these are whole-repository byte totals across every
        # repository worked in, not a measure of what this author wrote.
        f"Top languages by total bytes across all "
        f"{s.get('repos_contributed', 0):,} repositories: {chart}."
    )
    return c.slice_svg(
        c.to_grid(last_y + 28), "\n".join(body),
        title="GitHub stats", desc=desc, text="…·%", defs=DEFS,
    )
