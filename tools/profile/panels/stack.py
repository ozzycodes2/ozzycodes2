"""`~/stack` — one row per `[stack]` category, items as chips in a fixed gutter.

Chip widths are measured, not guessed: JetBrains Mono advances 0.6em per glyph,
so a chip is exactly as wide as its label plus padding. A row that would reach
past the content edge wraps instead of overflowing it.
"""
from .. import console as c

HEAD_Y = 38
GUTTER_R = 156            # right edge of the right-aligned category column
CHIP_L = GUTTER_R + 16    # first chip starts here
CHIP_R = c.FRAME_R - 36

CHIP_FS = 12.5
CHIP_H = 24
CHIP_PAD = 9
CHIP_GAP = 8
CHAR_W = CHIP_FS * 0.6

LINE_PITCH = 30           # between wrapped chip lines
CAT_GAP = 8               # extra space between categories
ROW_TOP = 70


MAX_CHARS = int((CHIP_R - CHIP_L - 2 * CHIP_PAD) // CHAR_W)


def _chip_w(label):
    return round(len(label) * CHAR_W + 2 * CHIP_PAD, 1)


def _fit(label):
    """Clip a label no line could hold. Wrapping cannot save a single long chip."""
    return label if len(label) <= MAX_CHARS else label[:MAX_CHARS - 1] + "…"


def _wrap(items):
    """Lay items out left to right, breaking before any chip that would clip."""
    lines, line, x = [], [], CHIP_L
    for item in map(_fit, items):
        w = _chip_w(item)
        if line and x + w > CHIP_R:
            lines.append(line)
            line, x = [], CHIP_L
        line.append((x, w, item))
        x += w + CHIP_GAP
    if line:
        lines.append(line)
    return lines


def _chip(x, y, w, label, colour):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{CHIP_H}" fill="{colour}" fill-opacity=".07" '
            f'stroke="{colour}" stroke-opacity=".35"/>'
            f'<text x="{round(x + CHIP_PAD, 1)}" y="{y + 16}" class="fg" style="font-size:{CHIP_FS}px">{c.e(label)}</text>')


def render(cfg, _data):
    stack = cfg.get("stack") or {}
    if not stack:
        body = (c.heading(HEAD_Y, "stack")
                + f'<text x="{c.TEXT_X}" y="{HEAD_Y + 46}" class="dim">no stack configured</text>')
        return c.slice_svg(c.to_grid(HEAD_Y + 66), body, title="Stack",
                           desc="No stack is configured.")

    body = [c.heading(HEAD_Y, "stack", counter=f"[ {sum(len(v) for v in stack.values())} ]")]
    rows, top, n = [], ROW_TOP, 0
    for category, items in stack.items():
        # Cyan and magenta alternate so adjacent categories stay distinguishable
        # without a separator rule between them.
        colour = c.ACCENT if n % 2 == 0 else c.ALT
        lines = _wrap(items)
        chips = "".join(
            _chip(x, top + k * LINE_PITCH, w, label, colour)
            for k, line in enumerate(lines) for x, w, label in line
        )
        rows.append(f'''<g class="ln" style="animation-delay:{0.18 + n * 0.1:.2f}s">
<text x="{GUTTER_R}" y="{top + 16}" text-anchor="end" class="faint" style="font-size:13px">{c.e(category)}</text>
{chips}
</g>''')
        top += LINE_PITCH * len(lines) + CAT_GAP
        n += 1
    bottom = top - CAT_GAP - LINE_PITCH + CHIP_H

    # The gutter rule gives the right-aligned category column an edge to sit on.
    body.append(f'<line x1="{GUTTER_R + 8}" y1="{ROW_TOP}" x2="{GUTTER_R + 8}" y2="{bottom}" '
                f'stroke="{c.ACCENT}" stroke-opacity=".18"/>')
    body.extend(rows)

    desc = "Stack — " + "; ".join(
        f"{category}: {', '.join(items)}" for category, items in stack.items()) + "."
    return c.slice_svg(
        c.to_grid(bottom + 28), "\n".join(body),
        title="Stack", desc=desc,
    )
