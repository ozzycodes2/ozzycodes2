"""Public event log: one row per release or commit, newest first."""
from .. import console as c

CONTENT_R = c.FRAME_R - 36
MARK_X = c.TEXT_X                   # kind marker
REPO_X = c.TEXT_X + 26
CHAR = 9                            # 15px JetBrains Mono advance, per the contract
LINE_H = 28

# ▲ for a tagged release, ● for a loose commit; green reads as "shipped". The
# triangle gets a point more because it sits on the baseline rather than
# centred, so at a matched size it looks lighter than the dot beside it.
MARKERS = {"release": ("▲", "ok", 13), "commit": ("●", "ac", 12)}
FALLBACK = ("●", "ac", 12)


def render(cfg, data):
    events = [ev for ev in data.get("activity") or [] if isinstance(ev, dict)]
    stats = data.get("stats") or {}

    y = 52
    body = [c.heading(y, "activity", "[ PUBLIC ]")]
    y += 44

    if not events:
        body.append(f'<text x="{c.TEXT_X}" y="{y}" class="dim">'
                    f'No public events in the fetched window.</text>')
        return c.slice_svg(
            c.to_grid(y + 32), "\n".join(body),
            title="~/activity", desc="Activity section: no public events in the fetched window.",
        )

    # The repo column is as wide as the longest name, so titles align into a
    # second column instead of ragging off the end of each repo.
    title_x = REPO_X + (max(len(str(ev.get("repo") or "")) for ev in events) + 2) * CHAR
    dates = [c.ago(ev.get("at")) for ev in events]
    title_w = CONTENT_R - max(len(d) for d in dates) * CHAR - 16 - title_x

    rows, spoken = [], []
    for ev, date in zip(events, dates):
        glyph, cls, size = MARKERS.get(ev.get("kind"), FALLBACK)
        repo = str(ev.get("repo") or "—")
        title = _fit(str(ev.get("title") or ""), title_w // CHAR)
        rows.append(
            f'<text x="{MARK_X}" y="{{y}}" class="{cls}" style="font-size:{size}px">{glyph}</text>'
            f'<text x="{REPO_X}" y="{{y}}" class="wh">{c.e(repo)}</text>'
            f'<text x="{title_x}" y="{{y}}" class="dim">{c.e(title)}</text>'
            f'<text x="{CONTENT_R}" y="{{y}}" text-anchor="end" class="faint" style="font-size:13px">{c.e(date)}</text>'
        )
        spoken.append(f"{ev.get('kind', 'event')} in {repo}, {title}, {date}")

    markup, y = c.stagger(rows, y, LINE_H)
    body.append(markup)

    # Public events are a sliver of the real total; say so rather than let the
    # short list imply the year was quiet.
    private = stats.get("private_year")
    note = ("Private contributions are counted in the stats above but not listed here."
            if private is None else
            f"{private:,} private contributions this year are counted in the stats above, not listed here.")
    body.append(f'<text x="{c.TEXT_X}" y="{y + 10}" class="faint" style="font-size:12px">{c.e(note)}</text>')

    desc = f"{len(events)} recent public events: " + "; ".join(spoken) + f". {note}"
    return c.slice_svg(
        c.to_grid(y + 42), "\n".join(body),
        title="~/activity", desc=desc, text="▲●…",
    )


def _fit(s, cols):
    """Clip to `cols` characters, spending the last one on an ellipsis."""
    return s if len(s) <= cols else s[:max(cols - 1, 1)].rstrip() + "…"
