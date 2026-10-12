"""`~/links` — a heading strip plus one narrow slice per configured link.

An SVG can only sit inside one `<a>`, so a single tile strip could not give
each service its own href. Instead the row is cut vertically into one file per
link, which the README lays out edge to edge and wraps individually. The cuts
land on ROW boundaries and only the outermost pieces draw a rail, so the window
frame and its background grid read as continuous across the joins.
"""
import json

from .. import console as c

ICONS = json.loads((c.HERE / "icons.json").read_text())

HEAD_H = 80       # the `~/links` strip above the row
HEAD_Y = 44

ROW_H = 120       # the row of link slices
TILE_W = 190      # bordered box inside a slice; shrinks if the row gets busy
TILE_H = 86
TILE_Y = 16
ICON = 24

LABEL_FS = 12
LABEL_TRACK = 1.5
# JetBrains Mono advances 0.6em per glyph; letter-spacing adds to every one.
LABEL_CHAR = LABEL_FS * 0.6 + LABEL_TRACK

MIN_CELLS = 3            # 120px a tile: an icon plus a readable label
MAX_LINKS = c.W // c.ROW // MIN_CELLS


def tile_widths(count):
    """Slice widths that tile `count` links across the window.

    Every width is a multiple of ROW, so each slice's background grid starts on
    the same phase as its neighbour's and the pattern never steps sideways.
    The leftover cells go to the middle slices, keeping the row symmetric.
    """
    if not 1 <= count <= MAX_LINKS:
        # A hand-edited profile.toml with too many links cannot be laid out at
        # all; say so rather than emit slivers the README then mis-tiles.
        raise ValueError(f"{count} links will not tile across {c.W}px "
                         f"(at most {MAX_LINKS})")
    base, rem = divmod(c.W // c.ROW, count)
    cells = [base] * count
    middle_out = sorted(range(count), key=lambda i: (abs(i - (count - 1) / 2), i))
    for i in middle_out[:rem]:
        cells[i] += 1
    return [n * c.ROW for n in cells]


def _rails(i, count):
    if count == 1:
        return "both"
    return "left" if i == 0 else "right" if i == count - 1 else "none"


def _tile(cx, w, icon, label):
    """One bordered box, centred on `cx` in its own slice's coordinates."""
    x, y = round(cx - w / 2, 1), TILE_Y
    glyph = ICONS.get(icon) or ICONS["globe"]
    # Corner ticks rather than a rounded card: a terminal selection box.
    ticks = "".join(
        f'M{x + dx} {y + dy}V{y + dy + 11 * sv}M{x + dx} {y + dy}H{x + dx + 11 * sh}'
        for dx, sh in ((0, 1), (w, -1))
        for dy, sv in ((0, 1), (TILE_H, -1))
    )
    fit = int((w - 20) // LABEL_CHAR)
    text = label.upper()
    if len(text) > fit:
        text = text[:fit - 1] + "…"
    return f'''<g class="ln" style="animation-delay:0.20s">
<rect x="{x}" y="{y}" width="{w}" height="{TILE_H}" fill="{c.ACCENT}" fill-opacity=".04"/>
<rect x="{x}" y="{y}" width="{w}" height="{TILE_H}" fill="none" stroke="{c.ACCENT}" stroke-opacity=".22"/>
<path d="{ticks}" fill="none" stroke="{c.ACCENT}" stroke-width="1.6" opacity=".7"/>
<g transform="translate({round(cx - ICON / 2, 1)} {y + 18})">
<path d="{glyph}" fill="{c.ACCENT}" filter="url(#soft)" opacity=".65"/>
<path d="{glyph}" fill="{c.WHITE}"/>
</g>
<text x="{cx}" y="{y + 70}" text-anchor="middle" class="dim" letter-spacing="{LABEL_TRACK}" style="font-size:{LABEL_FS}px">{c.e(text)}</text>
</g>'''


def _empty():
    body = (c.heading(HEAD_Y, "links")
            + f'<text x="{c.TEXT_X}" y="{HEAD_Y + 46}" class="dim">no links configured</text>')
    return [c.Slice("links.svg", c.slice_svg(c.to_grid(HEAD_Y + 66), body,
                                             title="Links", desc="No links are configured."))]


def render(cfg, _data):
    links = cfg.get("links") or []
    if not links:
        return _empty()

    labels = ", ".join(link["label"] for link in links)
    out = [c.Slice("links.svg", c.slice_svg(
        HEAD_H, c.heading(HEAD_Y, "links", counter=f"[ {len(links)} ]"),
        title="Links", desc=f"Links: {labels}.",
    ))]

    widths = tile_widths(len(links))
    tile_w = min(TILE_W, min(widths) - 36)
    for i, (width, link) in enumerate(zip(widths, links)):
        icon, label, url = link.get("icon", "globe"), link["label"], link["url"]
        out.append(c.Slice(f"links/{icon}.svg", c.slice_svg(
            ROW_H, _tile(width / 2, tile_w, icon, label),
            title=label, desc=f"{label} — {url}",
            text="…", width=width, rails=_rails(i, len(links)),
        ), url))
    return out
