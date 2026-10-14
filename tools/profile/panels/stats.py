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
COL_R = c.CONTENT_R
COLS = 3
TOP_N = 6

HEAD_Y = 38

# The language name is set in mono so its width is a character count: 13 glyphs
# at the mono step, plus the gap to the bar.
NAME_W = 118
BAR_X = COL_L + NAME_W + 8
BAR_R = 744       # stops short of the right-aligned percentage
BAR_H = 10


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
    """Label above value. The value takes the heading step: the scale has one
    emphatic size below display, and inventing a counter-sized step for this
    panel alone would put the console off the type scale it shares with the
    rest of the system."""
    tail = (f'<tspan class="caption dim" dx="6">{c.e(suffix)}</tspan>'
            if suffix else "")
    return f'''<text x="{x}" y="{label_y}" class="caption dim">{c.e(label)}</text>
<text x="{x}" y="{label_y + 32}" class="heading ink">{c.e(value)}{tail}</text>'''


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


def _lang_rows(theme, langs, y0, pitch):
    """Top-N languages as name / proportional bar / share of the top-N total."""
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:TOP_N]
    total = sum(size for _, size in top) or 1
    biggest = top[0][1] or 1
    fill = c.mix(theme.ink, theme.canvas, 0.55)
    rows, shares = [], []
    for i, (name, size) in enumerate(top):
        y = y0 + i * pitch
        pct = 100 * size / total
        shares.append((name, pct))
        width = max(BAR_H, round((BAR_R - BAR_X) * size / biggest, 1))
        shown = name if len(name) <= 13 else name[:12] + "…"
        rows.append(f'''<g class="ln" style="animation-delay:{0.40 + i * 0.08:.2f}s">
<text x="{COL_L}" y="{y}" class="mono ink">{c.e(shown)}</text>
<rect x="{BAR_X}" y="{y - 9}" width="{BAR_R - BAR_X}" height="{BAR_H}" rx="{BAR_H // 2}" fill="{theme.sunken}"/>
<rect x="{BAR_X}" y="{y - 9}" width="{width}" height="{BAR_H}" rx="{BAR_H // 2}" fill="{fill}"/>
<text x="{COL_R}" y="{y}" text-anchor="end" class="mono dim">{pct:.1f}%</text>
</g>''')
    return "\n".join(rows), shares


def render(_cfg, data, theme):
    s = data.get("stats")
    if not s:
        body = (c.heading(theme, HEAD_Y, "stats")
                + f'<text x="{COL_L}" y="{HEAD_Y + 46}" class="body dim">no stats available</text>')
        return c.slice_svg(theme, c.to_grid(HEAD_Y + 66), body, title="GitHub stats",
                           desc="No GitHub statistics are available.")

    stamp = str(s.get("updated", "?"))
    body = [c.heading(theme, HEAD_Y, "stats", counter=stamp)]
    # The console's one accent, spent here: the only fact on the page that is
    # about right now rather than about the record.
    body.append(f'<circle class="dot" cx="{COL_R - round(len(stamp) * c.MONO.size * c.MONO_ADVANCE) - 14}" '
                f'cy="{HEAD_Y - 5}" r="4" fill="{theme.accent}"/>')

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
                f'<text x="{COL_L}" y="234" class="caption dim">{c.e(meta)}</text></g>')

    body.append(f'<line x1="{COL_L}" y1="258" x2="{COL_R}" y2="258" '
                f'stroke="{theme.hairline}" stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>')
    body.append(f'<text x="{COL_L}" y="288" class="caption dim">TOP LANGUAGES BY BYTES</text>')

    langs = s.get("languages") or {}
    if langs:
        rows, shares = _lang_rows(theme, langs, 320, 28)
        body.append(rows)
        last_y = 320 + (len(shares) - 1) * 28
        chart = ", ".join(f"{name} {pct:.1f}%" for name, pct in shares)
    else:
        body.append(f'<text x="{COL_L}" y="320" class="body dim">no language data</text>')
        last_y, chart = 320, "none recorded"

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
        theme, c.to_grid(last_y + 28), "\n".join(body),
        title="GitHub stats", desc=desc, text="…·%",
    )
