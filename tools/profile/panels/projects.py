"""Project cards: a heading slice, then one slice per repo, two to a row.

Alone among the panels this one emits several files. GitHub strips <a> out of a
rendered SVG, so a clickable card has to be an <img> the README itself wraps in
an anchor — which means one file per card. Each card is therefore a half-width
slice of the same window row, drawing the side rail on its outer edge only and
running flush to the seam on the inner one, so a pair tiles back into one row.
"""
import textwrap

from .. import console as c

HALF = c.W // 2
GAP = 24                                    # between the cards, straddling the seam
CARD_W = ((c.CONTENT_R - c.TEXT_X) - GAP) // 2
PAD = 18                                    # card edge to its own text

# Blurbs are prose, so they are set in the sans face — which cannot be measured
# by character count the way the mono face can. textwrap still needs a column
# count, so this assumes 0.62em per glyph: more than Inter's average lowercase
# advance and less than its widest, which wraps a line or two short of the
# available width rather than past it.
BLURB_PX = c.CAPTION.size
BLURB_COLS = int((CARD_W - 2 * PAD) // (BLURB_PX * 0.62))
LINE_H = 19

NAME_DY = 32                                # card top to repo-name baseline
TAGS_DY = 54
BLURB_DY = 80
BLURB_TAIL = 16                             # breathing room under the last blurb line
FOOT_H = 42                                 # rule, footer line and bottom padding
VPAD = 24                                   # slice edge to card, before centring


def render(cfg, data, theme):
    entries = cfg.get("projects") or []
    live = {r.get("repo"): r for r in data.get("projects") or [] if isinstance(r, dict)}
    if not entries or not live:
        return [c.Slice("projects.svg", _unavailable(theme, len(entries)))]

    cards = [_measure(entry, live.get(entry.get("repo"), {})) for entry in entries]

    # One height for every card, from the longest blurb: cards sit side by side,
    # so a per-card height would leave a step in the middle of each row.
    tallest = max(len(card["blurb"]) for card in cards)
    card_h = BLURB_DY + (tallest - 1) * LINE_H + BLURB_TAIL + FOOT_H
    slice_h = c.to_grid(card_h + 2 * VPAD)
    top = (slice_h - card_h) // 2

    out = [c.Slice("projects.svg", _heading_slice(theme, len(cards)))]
    for i, (card, entry) in enumerate(zip(cards, entries)):
        # Even index sits left of the seam and owns the left rail; odd sits
        # right. The right card's own origin is the seam, hence the shifted x.
        left = i % 2 == 0
        x = c.TEXT_X if left else c.TEXT_X + CARD_W + GAP - HALF
        out.append(c.Slice(
            f"projects-{i + 1}.svg",
            c.slice_svg(
                theme, slice_h, _card(theme, card, x, top, card_h),
                title=f"{card['name']} — {card['language']}",
                desc=card["desc"], text="·",
                width=HALF, rails="left" if left else "right",
            ),
            f"https://github.com/{entry['repo']}",
        ))
    return out


def _measure(entry, record):
    """Fold a profile.toml entry together with its fetched repo record.

    Star counts are deliberately dropped: every repo here has none, and a row
    of zeroes reads as neglect rather than as data.
    """
    name = entry.get("name") or (entry.get("repo") or "").split("/")[-1]
    tags = [str(t) for t in entry.get("tags") or []]
    # profile.toml wins: GitHub picks a repo's language by byte count, which on
    # a small project is often a vendored stylesheet rather than what the thing
    # is written in, and the card would then contradict its own tags.
    language = entry.get("language") or record.get("language") or "—"
    updated = c.ago(record.get("pushed_at"))
    blurb = textwrap.wrap(entry.get("blurb") or "", BLURB_COLS) or [""]

    desc = f"{name}, {language}"
    if updated:
        desc += f", updated {updated}"
    if tags:
        desc += f". Tagged {', '.join(tags)}"
    return {"name": name, "tags": tags, "language": language,
            "updated": f"updated {updated}" if updated else "",
            "blurb": blurb, "desc": f"{desc}. {entry.get('blurb') or ''}".strip()}


def _card(theme, card, x, y, height):
    tx, inner = x + PAD, CARD_W - 2 * PAD
    bottom = y + height

    box = (f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{height}" rx="{c.R_CARD}" '
           f'fill="{theme.surface}" stroke="{theme.hairline}" stroke-width="{c.EDGE_W}"/>')

    name = f'<text x="{tx}" y="{y + NAME_DY}" class="body ink">{c.e(card["name"])}</text>'

    tags = (f'<text x="{tx}" y="{y + TAGS_DY}" class="caption dim">'
            f'{c.e(" · ".join(t.upper() for t in card["tags"]))}</text>'
            if card["tags"] else "")

    blurb = "\n".join(
        f'<text x="{tx}" y="{y + BLURB_DY + i * LINE_H}" class="caption dim">{c.e(line)}</text>'
        for i, line in enumerate(card["blurb"])
    )

    # The footer hangs off the card's bottom, not off the blurb, so it lands on
    # the same baseline in all four cards however short the blurb wrapped.
    fy = bottom - 18
    foot = (f'<line x1="{tx}" y1="{bottom - 42}" x2="{tx + inner}" y2="{bottom - 42}" '
            f'stroke="{theme.hairline}" stroke-width="{c.EDGE_W}" shape-rendering="crispEdges"/>'
            f'<text x="{tx}" y="{fy}" class="mono ink">{c.e(card["language"])}</text>')
    if card["updated"]:
        foot += (f'<text x="{tx + inner}" y="{fy}" text-anchor="end" class="caption dim">'
                 f'{c.e(card["updated"])}</text>')

    return f'<g class="ln" style="animation-delay:0.20s">{box}\n{name}\n{tags}\n{blurb}\n{foot}</g>'


def _heading_slice(theme, n):
    """`~/projects` on its own full-width row, so the title is not inside a link."""
    body = c.heading(theme, 52, "projects", f"{n} repos")
    return c.slice_svg(
        theme, c.to_grid(72), body,
        title="~/projects", desc=f"Section heading: projects, {n} public repositories.",
    )


def _unavailable(theme, n):
    body = c.heading(theme, 52, "projects", f"{n} repos") + (
        f'<text x="{c.TEXT_X}" y="96" class="body dim">No repository data available.</text>')
    return c.slice_svg(
        theme, c.to_grid(128), body,
        title="~/projects", desc="Projects section: no repository data available.",
    )
