"""Project cards: a heading slice, then one slice per repo, two to a row.

Alone among the panels this one emits several files. GitHub strips <a> out of a
rendered SVG, so a clickable card has to be an <img> the README itself wraps in
an anchor — which means one file per card. Each card is therefore a half-width
slice of the same window row, drawing the side rail on its outer edge only and
running flush to the seam on the inner one, so a pair tiles back into one row.

The card's own geometry is the reference design's, unchanged: a 378×164 box, its
name at +14/+30, three lines of blurb from +56, chips along the bottom. Only the
vertical rhythm *between* rows differs, because a slice height must be a
multiple of ROW and 164 + 20 is not: the row gap comes out at 36 rather than 20.
"""
import textwrap

from .. import console as c

HALF = c.W // 2
GAP = 20                                    # between the cards, straddling the seam
CARD_W = (c.CONTENT_R - c.TEXT_X - GAP) // 2
CARD_H = 164
PAD = 14                                    # card edge to its own text

# One width estimate for everything measured before it is drawn. At 11px the
# mono face advances exactly this, so the chips are sized to their label; the
# 13px sans blurb is measured with the same figure, which is 0.51em there —
# under Inter's average advance, so a line wraps short of the card, never past.
GLYPH = 11 * c.MONO_ADVANCE

BLURB_COLS = int((CARD_W - 2 * PAD) / GLYPH)
BLURB_MAX = 3                               # a fourth line would run into the chips
LINE_H = 19

NAME_DY = 30                                # card top to repo-name baseline
BLURB_DY = 56
CHIP_DY = CARD_H - 36                       # chips hang off the card's bottom
CHIP_H = 22
CHIP_PAD = 9                                # chip edge to its label
CHIP_GAP = 6
CHIP_BASE = CHIP_DY + 16                    # label baseline inside the chip
CHIP_TINT = 0.06                            # ink over surface, a tint not a fill

# The card is centred in its slice: 164 plus breathing room rounds to 200, so
# the 18px left over at each end puts 36px between the two rows.
SLICE_H = c.to_grid(CARD_H + 24)
TOP = (SLICE_H - CARD_H) // 2

HEAD_Y = 44


def render(cfg, data, theme):
    entries = cfg.get("projects") or []
    live = {r.get("repo"): r for r in data.get("projects") or [] if isinstance(r, dict)}
    if not entries or not live:
        return [c.Slice("projects.svg", _unavailable(theme, len(entries)))]

    out = [c.Slice("projects.svg", _heading_slice(theme, len(entries)))]
    for i, entry in enumerate(entries):
        card = _merge(entry, live.get(entry.get("repo")) or {})
        # Even index sits left of the seam and owns the left rail; odd sits
        # right. The right card's own origin is the seam, hence the shifted x.
        left = i % 2 == 0
        x = c.TEXT_X if left else c.TEXT_X + CARD_W + GAP - HALF
        out.append(c.Slice(
            f"projects-{i + 1}.svg",
            c.slice_svg(
                theme, SLICE_H, _card(theme, card, x, TOP),
                title=card["title"], desc=card["desc"],
                width=HALF, rails="left" if left else "right",
            ),
            f"https://github.com/{entry.get('repo', '')}",
        ))
    return out


def _merge(entry, record):
    """Fold a profile.toml entry together with its fetched repo record.

    Star counts are deliberately dropped: every repo here has none, and a row
    of zeroes reads as neglect rather than as data.
    """
    name = entry.get("name") or (entry.get("repo") or "").split("/")[-1]
    # profile.toml wins over the fetch: GitHub picks a repo's language by byte
    # count, which on a small project is often a vendored stylesheet rather
    # than what the thing is written in, and the card would then contradict its
    # own tags. What the fetch does win is the tag list — the language leads the
    # chips, and a hand-written tag naming it is folded into that one chip.
    language = entry.get("language") or record.get("language") or ""
    tags = [str(t) for t in entry.get("tags") or []]
    if language:
        tags = [language] + [t for t in tags if t.casefold() != language.casefold()]

    blurb = entry.get("blurb") or ""
    age = c.ago(record.get("pushed_at"))

    desc = name
    if age:
        desc += f", updated {age}"
    if tags:
        desc += f". Tagged {', '.join(tags)}"
    return {
        "name": name,
        "tags": tags,
        "age": age,
        # The drawn blurb stops at three lines; `desc` carries all of it, since
        # a screen reader has the room the card does not.
        "blurb": _wrap(blurb)[:BLURB_MAX],
        "title": f"{name} — {language}" if language else name,
        "desc": f"{desc}. {blurb}".strip(),
    }


def _wrap(text):
    """Greedy wrap on whitespace only, matching the reference's own `wrap()`.

    Neither long words nor hyphens are broken: a word wider than the card
    overhangs it rather than being cut mid-token, which is what the reference
    does and is the lesser of the two wrongs for a repo name in a blurb.
    """
    return textwrap.wrap(text, BLURB_COLS,
                         break_long_words=False, break_on_hyphens=False)


def _card(theme, card, x, y):
    parts = [
        f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="{c.R_CARD}" '
        f'fill="{theme.surface}" stroke="{theme.hairline}" stroke-width="{c.EDGE_W}"/>',
        c.tx(x + PAD, y + NAME_DY, card["name"], fill=theme.ink,
             family=c.MONO_STACK, size=15, weight=700),
    ]
    if card["age"]:
        parts.append(c.tx(x + CARD_W - PAD, y + NAME_DY, card["age"], fill=theme.faint,
                          family=c.MONO_STACK, size=11, anchor="end"))

    parts += [
        c.tx(x + PAD, y + BLURB_DY + i * LINE_H, line, fill=theme.dim,
             family=c.SANS_STACK, size=13)
        for i, line in enumerate(card["blurb"])
    ]

    chip_x = x + PAD
    for tag in card["tags"]:
        width = round(len(tag) * GLYPH) + 2 * CHIP_PAD
        parts.append(
            f'<rect x="{chip_x}" y="{y + CHIP_DY}" width="{width}" height="{CHIP_H}" '
            f'rx="{c.R_CHIP}" fill="{theme.ink}" opacity="{CHIP_TINT}"/>')
        parts.append(c.tx(chip_x + CHIP_PAD, y + CHIP_BASE, tag, fill=theme.dim,
                          family=c.MONO_STACK, size=11))
        chip_x += width + CHIP_GAP

    return "\n".join(parts)


def _heading_slice(theme, n):
    """`~/projects` on its own full-width row, so the title is not inside a link."""
    return c.slice_svg(
        theme, c.to_grid(HEAD_Y + 28), c.heading(theme, HEAD_Y, "projects", f"{n} repos"),
        title="~/projects", desc=f"Section heading: projects, {n} public repositories.",
    )


def _unavailable(theme, n):
    body = c.heading(theme, HEAD_Y, "projects", f"{n} repos") + c.tx(
        c.TEXT_X, HEAD_Y + 52, "No repository data available.",
        fill=theme.dim, family=c.SANS_STACK, size=15)
    return c.slice_svg(
        theme, c.to_grid(HEAD_Y + 80), body,
        title="~/projects", desc="Projects section: no repository data available.",
    )
