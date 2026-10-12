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
CONTENT_R = c.FRAME_R - 36                  # right edge of body content, per the contract
CARD_W = ((CONTENT_R - c.TEXT_X) - GAP) // 2
PAD = 16                                    # card border to its own text

# Blurbs run at 13px; monospace advances 0.6em, so the wrap width is a
# character count, not a pixel one. textwrap is the only thing deciding how
# tall a card gets, which is why every card is measured before any is drawn.
BLURB_PX = 13
BLURB_COLS = int((CARD_W - 2 * PAD) // (BLURB_PX * 0.6))
LINE_H = 18

NAME_DY = 30                                # card top to repo-name baseline
TAGS_DY = 52
BLURB_DY = 78
BLURB_TAIL = 14                             # breathing room under the last blurb line
FOOT_H = 40                                 # rule, footer line and bottom padding
VPAD = 24                                   # slice edge to card, before centring


def render(cfg, data):
    entries = cfg.get("projects") or []
    live = {r.get("repo"): r for r in data.get("projects") or [] if isinstance(r, dict)}
    if not entries or not live:
        return [c.Slice("projects.svg", _unavailable(len(entries)))]

    cards = [_measure(entry, live.get(entry.get("repo"), {})) for entry in entries]

    # One height for every card, from the longest blurb: cards sit side by side,
    # so a per-card height would leave a step in the middle of each row.
    tallest = max(len(card["blurb"]) for card in cards)
    card_h = BLURB_DY + (tallest - 1) * LINE_H + BLURB_TAIL + FOOT_H
    slice_h = c.to_grid(card_h + 2 * VPAD)
    top = (slice_h - card_h) // 2

    out = [c.Slice("projects.svg", _heading_slice(len(cards)))]
    for i, (card, entry) in enumerate(zip(cards, entries)):
        # Even index sits left of the seam and owns the left rail; odd sits
        # right. The right card's own origin is the seam, hence the shifted x.
        left = i % 2 == 0
        x = c.TEXT_X if left else c.TEXT_X + CARD_W + GAP - HALF
        out.append(c.Slice(
            f"projects-{i + 1}.svg",
            c.slice_svg(
                slice_h, _card(card, x, top, card_h),
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


def _card(card, x, y, height):
    tx, inner = x + PAD, CARD_W - 2 * PAD
    right = x + CARD_W
    bottom = y + height

    # Brackets on opposing corners instead of a closed bevel — the box reads as
    # a terminal selection rather than as a UI card.
    ticks = (f'<path d="M{x} {y + 16}V{y}H{x + 16}"/>'
             f'<path d="M{right - 16} {bottom}H{right}V{bottom - 16}"/>')
    box = (f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{height}" fill="{c.ACCENT}" fill-opacity=".03" '
           f'stroke="{c.ACCENT}" stroke-opacity=".22"/>'
           f'<g fill="none" stroke="{c.ACCENT}" stroke-width="2" opacity=".75">{ticks}</g>'
           f'<g fill="none" stroke="{c.ACCENT}" stroke-width="2" opacity=".5" filter="url(#soft)">{ticks}</g>')

    name = (f'<text x="{tx}" y="{y + NAME_DY}" font-weight="700" fill="{c.ACCENT}" filter="url(#soft)" opacity=".55" style="font-size:16px">{c.e(card["name"])}</text>'
            f'<text x="{tx}" y="{y + NAME_DY}" font-weight="700" class="wh" style="font-size:16px">{c.e(card["name"])}</text>')

    spans = []
    for i, tag in enumerate(card["tags"]):
        if i:
            spans.append('<tspan class="faint" dx="7">·</tspan>')
        spans.append(f'<tspan class="alt" dx="{7 if i else 0}" opacity=".85">{c.e(tag.upper())}</tspan>')
    tags = (f'<text x="{tx}" y="{y + TAGS_DY}" style="font-size:11px" letter-spacing=".8">{"".join(spans)}</text>'
            if spans else "")

    blurb = "\n".join(
        f'<text x="{tx}" y="{y + BLURB_DY + i * LINE_H}" class="dim" style="font-size:{BLURB_PX}px">{c.e(line)}</text>'
        for i, line in enumerate(card["blurb"])
    )

    # The footer hangs off the card's bottom, not off the blurb, so it lands on
    # the same baseline in all four cards however short the blurb wrapped.
    fy = bottom - 18
    foot = (f'<line x1="{tx}" y1="{bottom - 40}" x2="{tx + inner}" y2="{bottom - 40}" stroke="{c.ACCENT}" stroke-opacity=".16"/>'
            f'<rect x="{tx}" y="{fy - 8}" width="7" height="7" fill="{c.ACCENT}" opacity=".8"/>'
            f'<text x="{tx + 15}" y="{fy}" class="ac" style="font-size:12px">{c.e(card["language"])}</text>')
    if card["updated"]:
        foot += (f'<text x="{tx + inner}" y="{fy}" text-anchor="end" class="faint" '
                 f'style="font-size:12px">{c.e(card["updated"])}</text>')

    return f'<g class="ln" style="animation-delay:0.20s">{box}\n{name}\n{tags}\n{blurb}\n{foot}</g>'


def _heading_slice(n):
    """`~/projects` on its own full-width row, so the title is not inside a link."""
    body = c.heading(52, "projects", f"[ {n} REPOS ]")
    return c.slice_svg(
        c.to_grid(72), body,
        title="~/projects", desc=f"Section heading: projects, {n} public repositories.",
    )


def _unavailable(n):
    body = c.heading(52, "projects", f"[ {n} REPOS ]") + (
        f'<text x="{c.TEXT_X}" y="96" class="dim">No repository data available.</text>')
    return c.slice_svg(
        c.to_grid(128), body,
        title="~/projects", desc="Projects section: no repository data available.",
    )
