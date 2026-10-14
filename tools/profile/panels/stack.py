"""`~/stack` — one row per `[stack]` category, its items as mono chips.

Chip widths are measured, not guessed: the mono face advances 0.6em per glyph,
so a chip is exactly as wide as its label plus the same inset on either side. A
chip that would reach past the content edge starts a new line within its own
category instead, and the categories below it move down with it.

The category name sits in a 110px gutter to the left of the first chip, one
step quieter than the chips and two below the heading — three text tiers over
one surface is the whole of the panel's hierarchy. No chip is tinted: a row is
told apart by its label, not by colour.
"""
import math

from .. import console as c

HEAD_Y = 44
ROW_TOP = 88              # baseline of the first category
LABEL_W = 110             # gutter the category names sit in
CHIP_X = c.TEXT_X + LABEL_W

CHIP_FS = 13
CHAR_W = CHIP_FS * c.MONO_ADVANCE
CHIP_H = 26
CHIP_PAD = 11             # inset from the chip's edge to its text
CHIP_GAP = 8              # between chips on one line
WRAP_STEP = 32            # between wrapped chip lines inside one category
GROUP_STEP = 44           # between categories

LABEL_FS = 11


def _chip_w(label):
    """Text advance rounded to the device pixel, plus an inset on either side."""
    return math.floor(len(label) * CHAR_W + 0.5) + 2 * CHIP_PAD


def _chip(theme, x, y, w, label):
    """A capsule on the lifted surface, edged with the frame's hairline.

    `y` is the text baseline, so the capsule is drawn 16px above it: the chip
    is centred on the lowercase body rather than hung from the cap height.
    """
    return (f'<rect x="{x}" y="{y - 16}" width="{w}" height="{CHIP_H}" '
            f'rx="{c.R_CHIP}" fill="{theme.surface}" stroke="{theme.hairline}" '
            f'stroke-width="{c.EDGE_W}"/>'
            + c.tx(x + CHIP_PAD, y + 2, label, fill=theme.dim,
                   family=c.MONO_STACK, size=CHIP_FS))


def _layout(items, y):
    """Place one category's chips, left to right, wrapping at the content edge.

    Returns `(chips, y)` — the markup arguments for each chip and the baseline
    the last line landed on, which is where the next category measures from.
    """
    placed, x = [], CHIP_X
    for item in items:
        w = _chip_w(item)
        if x + w > c.CONTENT_R:
            x, y = CHIP_X, y + WRAP_STEP
        placed.append((x, y, w, item))
        x += w + CHIP_GAP
    return placed, y


def render(cfg, _data, theme):
    stack = cfg.get("stack") or {}
    if not stack:
        body = "\n".join([
            c.heading(theme, HEAD_Y, "stack"),
            c.tx(c.TEXT_X, ROW_TOP, "no stack configured", fill=theme.dim,
                 family=c.MONO_STACK, size=CHIP_FS),
        ])
        return c.slice_svg(theme, c.to_grid(ROW_TOP + 8), body,
                           title="Tools in rotation",
                           desc="No stack is configured.")

    groups, y = [], ROW_TOP
    for category, items in stack.items():
        top = y
        placed, y = _layout(items, y)
        label = c.tx(c.TEXT_X, top, category.lower(), fill=theme.faint,
                     family=c.MONO_STACK, size=LABEL_FS, ls=0.5)
        groups.append("\n".join(
            [label] + [_chip(theme, *chip) for chip in placed]))
        y += GROUP_STEP

    count = sum(len(items) for items in stack.values())
    body = "\n".join(
        [c.heading(theme, HEAD_Y, "stack", counter=f"{count} tools")] + groups)
    desc = (f"{count} tools across {len(stack)} categories: "
            + ", ".join(f"{name} ({len(items)})"
                        for name, items in stack.items()) + ".")

    return c.slice_svg(theme, c.to_grid(y + 8), body,
                       title="Tools in rotation", desc=desc)
