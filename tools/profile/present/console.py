"""Primitives for the console frame the README is assembled from.

The README is one continuous window sliced into separate SVG files, stacked by
consecutive <img> tags. Each slice is W wide, a multiple of ROW px tall, and
redraws the same side rails. Only the first slice caps the top and draws the
title bar; only the last closes the frame.

Both themes are the Mine Final token set: DARK is its `dark` theme, LIGHT its
`light` one. Panels never name a colour, they ask the theme for a role.
render.py runs each panel once per theme and readme.py pairs the output with
<picture>, so the console follows the reader's system setting.

The eight role values below are not the raw tokens. They are what the preview's
`panelTheme()` derives from them — `dim` and `faint` are pulled toward the ink
until they clear 4.5:1 on the canvas at the 11-13px these labels run at, and
`accent` is held to 3:1, the threshold for an object rather than a word.
tests/test_console.py pins all sixteen against the preview's own output; that
test is the only thing keeping the two renderers in agreement, so a change here
that does not also change the preview is a bug in one of them.

`accent` is the same value in both themes. Mine Final shares all four of its
accent roles across the two polarities, on the grounds that a brand hue which
changes with the reader's system setting is two brands. It clears 3:1 on both
canvases and 4.5:1 on neither, which is the whole reason it never sets type.

Type is not the token scale. A terminal has its own, and these panels set it per
element in presentation attributes: mono at 11/12/13/15/20/30 for everything
structural, sans at 13/15/30 for the two runs of prose. What the tokens supply
is the two families and the two radii.

`slice_svg` inlines a woff2 subset of every face its body needs, because GitHub
strips <link> and external url() from a rendered SVG; `fonts.py` is how.
"""
import datetime
import html
import math
import re
from typing import NamedTuple

from .fonts import face_css


class Theme(NamedTuple):
    """One palette, named for the `prefers-color-scheme` value it answers.

    Three text tiers, not two: `ink` for anything that carries meaning, `dim`
    for supporting prose, `faint` for the labels above a value and the counters
    beside a heading. `surface` is the one step above the canvas — cards, chips,
    the chrome band and the city's ground plane — which is the whole of this
    system's depth. There are no shadows.

    `accent` does two jobs. Structurally it is the short stroke that starts
    every section rule, identical down the window, so the eye finds the
    sections without a second type weight. As data it marks the single highest
    value in a set, at most once per panel. It paints objects only — a dot, a
    bar, a tower — never a word.
    """
    name: str
    canvas: str
    ink: str
    surface: str
    dim: str
    faint: str
    hairline: str
    accent: str


LIGHT = Theme(
    name="light",
    canvas="#f8f8f8", ink="#171717", surface="#ffffff",
    dim="#4d4d4d", faint="#727272", hairline="#d9d9d9", accent="#ef6306",
)

DARK = Theme(
    name="dark",
    canvas="#010102", ink="#f7f8f8", surface="#0f1011",
    dim="#d0d6e0", faint="#909091", hairline="#23252a", accent="#ef6306",
)

THEMES = (LIGHT, DARK)

# `{rounded.lg}` and `{rounded.xs}`: cards and chips are the only two radii a
# panel draws, and the token set is shared by both themes.
R_CARD = 18
R_CHIP = 5

SANS_STACK = "Inter, 'Helvetica Neue', Helvetica, Arial, system-ui, sans-serif"
MONO_STACK = "'SF Mono', ui-monospace, SFMono-Regular, JBM, Menlo, monospace"

# Both monospaces advance 0.6em per glyph, so a panel can predict text width
# from character count. Inter cannot be measured this way — anything whose
# width has to be known before it is drawn must be set in `mono`.
MONO_ADVANCE = 0.6

W = 880          # slice width
MARGIN = 16      # gutter outside the frame, so the corner radius has room
ROW = 40         # grid pitch; every slice height must be a multiple
TEXT_X = 52      # left edge of body text

# The section block. A panel hangs its heading, its command transcript and its
# first body element off these three rather than spelling its own, so every
# section opens at the same rhythm and the seams between them stay even.
HEAD_Y = 36      # heading baseline, measured from the slice top
CMD_DY = 30      # heading baseline to the command under its rule
BODY_DY = 62     # heading baseline to the first body element

FRAME_L = MARGIN
FRAME_R = W - MARGIN
CONTENT_R = FRAME_R - 36

EDGE_W = 1

# The rails are the one stroke that has to agree across slices, and they are
# twice the weight of everything else because of it. Each slice is rasterised at
# its intrinsic 880px and then resampled to whatever width the page gives it;
# `crispEdges` snaps the rail inside the raster, but the resample afterwards
# redistributes it, and by how much depends on the slice's own height. Measured
# at an 877px column: a 1px rail lands on one device column in a 280px slice and
# spreads across two in an 80px one, so the frame visibly steps at that seam.
# A 2px rail still covers one whole device column at any sub-pixel offset, and
# renders identically in every slice. Interior strokes stay at EDGE_W: they live
# wholly inside one file and never cross a seam.
RAIL_W = 2

TITLE_H = 44     # chrome band, measured down from the frame's top edge

e = html.escape


def ago(when, now=None):
    """Abbreviated age for an ISO-8601 instant, or "" if there isn't one.

    Panels set this in mono beside a repo name, where it has to fit a card
    corner: "today", "9d ago", "14mo ago", "3y ago". Returns the empty string
    for None or anything unparseable rather than raising, because the only
    caller is a renderer that must still produce a panel.

    Whole days, floored, so a push a few hours old reads "today" rather than
    "0d ago". Months and years use the mean Gregorian length and round, so the
    label tracks what a calendar would say to within a day.
    """
    if not when:
        return ""
    try:
        at = datetime.datetime.fromisoformat(when.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return ""
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)

    days = int((now - at).total_seconds() // 86400)
    if days < 1:
        return "today"
    if days < 45:
        return f"{days}d ago"
    months = round(days / 30.44)
    if months < 24:
        return f"{months}mo ago"
    return f"{round(days / 365.25)}y ago"


def num(value):
    """Thousands-separated, for counters set in mono."""
    return f"{int(value or 0):,}"


def tx(x, y, text, *, fill, family, size, weight=None, ls=None, anchor=None):
    """One <text> element, typed by presentation attribute rather than class.

    Size and weight vary per element here and the slices share no stylesheet
    between them, so a class per combination would be a class per element.
    """
    attrs = [f'x="{x}"', f'y="{y}"', f'fill="{fill}"',
             f'font-family="{e(family)}"', f'font-size="{size}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if ls:
        attrs.append(f'letter-spacing="{ls}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    return f'<text {" ".join(attrs)}>{e(text)}</text>'


def mix(a, b, t):
    """`t` of colour `a` over colour `b`, as a literal hex.

    Panels shade with this rather than with `fill-opacity`, because the city's
    blocks overlap: a translucent face shows the block behind it through its own
    wall and the plan stops reading as solid. Both arguments must be #rrggbb.

    Rounds half away from zero, not half to even as `round` would. The preview
    this is ported from rounds through `Math.round`, and a channel landing on
    exactly .5 is common enough in a ramp of evenly spaced shades to show up:
    it is what put the dark skyline's second bucket one unit off the browser's.
    """
    x, y = (tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (a, b))
    return "#" + "".join(f"{math.floor(p * t + q * (1 - t) + 0.5):02x}"
                         for p, q in zip(x, y))


def contrast(a, b):
    """WCAG contrast ratio between two #rrggbb colours.

    The themes above are pinned, so nothing in the frame needs this. The stack
    panel does: it paints twenty brand hexes the design system never declared,
    onto faces that are themselves mixes, and each one has to be corrected until
    it can be seen on the one it landed on. The 0.03928 break is the preview's,
    which differs from the published 0.04045 by less than a code point of any
    channel — matching it is cheaper than explaining a one-unit divergence.
    """
    def lum(hexa):
        parts = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [p / 12.92 if p <= 0.03928 else ((p + 0.055) / 1.055) ** 2.4
               for p in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    lo, hi = sorted((lum(a) + 0.05, lum(b) + 0.05))
    return hi / lo


def visible(markup):
    """The characters a piece of SVG markup actually paints.

    Font subsetting works from this, so a glyph that only appears inside an
    attribute or a comment is correctly left out, and one that appears in a
    nested tspan is correctly kept.
    """
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def base_css(_theme):
    """The one animation in the system, and nothing else.

    Every fill, size and weight is a presentation attribute on the element that
    needs it, so there are no utility classes left to declare. What cannot be an
    attribute is the pulse on the live dot — and it is deliberately the only
    thing moving. A rendered SVG is painted by GitHub as a still image at frame
    zero, so anything that animates *in* is simply invisible; the dot survives
    because it starts at full opacity and the pulse only ever dims it.
    """
    return """@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
.live{animation:pulse 2.4s ease-in-out infinite}"""


def _outline(x0, x1, y0, y1, r, *, top, bottom, left, right):
    """The frame's own edge, as `(rails, caps)` — straight verticals, then the
    capped horizontals with their corner arcs.

    Two paths rather than one so each can be rasterised the way it needs. The
    rails must snap to a device column or the frame wanders between slices; an
    arc told to snap grows a visible step where it meets the rail. As one path
    they had to share a `shape-rendering`, which is why the capped slices
    antialiased their rails and the middle ones did not.

    A middle slice rounds nothing and returns two bare rails and no cap. Every
    uncapped end is left open, so the stroke stops there and the next slice
    continues it.
    """
    tl, tr, br, bl = top and left, top and right, bottom and right, bottom and left

    rails = []
    if left:
        rails.append(f"M{x0} {y1 - (r if bl else 0)}V{y0 + (r if tl else 0)}")
    if right:
        rails.append(f"M{x1} {y0 + (r if tr else 0)}V{y1 - (r if br else 0)}")

    caps = []
    if top:
        caps.append(f"M{x0} {y0 + r}a{r} {r} 0 0 1 {r} {-r}H" if tl else f"M{x0} {y0}H")
        caps.append(f"{x1 - (r if tr else 0)}")
        if tr:
            caps.append(f"a{r} {r} 0 0 1 {r} {r}")
    if bottom:
        caps.append(f"M{x1} {y1 - r}a{r} {r} 0 0 1 {-r} {r}H" if br else f"M{x1} {y1}H")
        caps.append(f"{x0 + (r if bl else 0)}")
        if bl:
            caps.append(f"a{r} {r} 0 0 1 {-r} {-r}")
    return "".join(rails), "".join(caps)


def _fill(x0, x1, y0, y1, r, *, tl, tr, br, bl):
    """The same shape, closed, for the body fill."""
    return (f"M{x0 + (r if tl else 0)} {y0}"
            f"H{x1 - (r if tr else 0)}"
            + (f"a{r} {r} 0 0 1 {r} {r}" if tr else "")
            + f"V{y1 - (r if br else 0)}"
            + (f"a{r} {r} 0 0 1 {-r} {r}" if br else "")
            + f"H{x0 + (r if bl else 0)}"
            + (f"a{r} {r} 0 0 1 {-r} {-r}" if bl else "")
            + f"V{y0 + (r if tl else 0)}"
            + (f"a{r} {r} 0 0 1 {r} {-r}" if tl else "")
            + "Z")


def slice_svg(theme, height, body, *, title, desc, text="", top=False,
              bottom=False, css="", defs="", width=W, rails="both"):
    """One stacked slice of the window.

    `text` lists glyphs the body needs but does not literally contain — text
    injected by CSS, or drawn from a variable the subsetter cannot see.

    `width` and `rails` together cut a row of the window into side-by-side
    files, which is the only way to give two halves of one row separate links:
    the left half is `width=W//2, rails="left"`, the right half the mirror.
    The half carrying a rail keeps the MARGIN gutter outside it; the other edge
    runs flush to the slice boundary so the two backgrounds meet with no seam.
    Any half-width must stay a multiple of ROW or the seam lands off-grid.

    A row cut into three or more pieces needs `rails="none"` for the middle
    ones: they sit between two neighbours and draw no vertical edge at all.
    """
    if height % ROW:
        raise ValueError(f"slice height {height} is not a multiple of {ROW}")
    if rails not in ("both", "left", "right", "none"):
        raise ValueError(f"rails must be both, left, right or none, not {rails!r}")

    y0 = MARGIN if top else 0
    y1 = height - MARGIN if bottom else height
    draw_l, draw_r = rails in ("both", "left"), rails in ("both", "right")
    x0 = MARGIN if draw_l else 0
    x1 = width - MARGIN if draw_r else width

    corners = dict(tl=top and draw_l, tr=top and draw_r,
                   br=bottom and draw_r, bl=bottom and draw_l)
    rails_d, caps_d = _outline(x0, x1, y0, y1, R_CARD,
                               top=top, bottom=bottom, left=draw_l, right=draw_r)
    fill = _fill(x0, x1, y0, y1, R_CARD, **corners)

    edge = "\n".join(
        f'<path d="{d}" fill="none" stroke="{theme.hairline}" '
        f'stroke-width="{RAIL_W}"{snap}/>'
        for d, snap in ((rails_d, ' shape-rendering="crispEdges"'), (caps_d, ""))
        if d
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
<style>
{face_css(text + visible(body))}
{base_css(theme)}
{css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
{defs}
</defs>
<path d="{fill}" fill="{theme.canvas}"/>
{body}
{edge}
</svg>
'''


def title_bar(theme, label):
    """Window chrome and title. Only the top slice draws one.

    Takes no y: the band caps the frame, so it has to share the frame's top
    edge and corner radius exactly. Positioned any lower it leaves a strip of
    canvas above itself inside the cap, and its arcs no longer sit on the
    frame's — the window then reads as two misaligned rectangles.

    Three hairline rings rather than traffic lights: the colour vocabulary has
    one accent and it is spent on live state, so the chrome is drawn in the
    same edge colour as the frame it belongs to.
    """
    mid, rule = MARGIN + TITLE_H // 2, MARGIN + TITLE_H
    rings = "".join(
        f'<circle cx="{FRAME_L + 24 + i * 18}" cy="{mid}" r="5" fill="none" '
        f'stroke="{theme.faint}" stroke-width="{EDGE_W}"/>'
        for i in range(3)
    )
    return f'''<path d="{_fill(FRAME_L, FRAME_R, MARGIN, rule, R_CARD, tl=True, tr=True, br=False, bl=False)}" fill="{theme.surface}"/>
{rings}
{tx(W // 2, mid + 5, label, fill=theme.faint, family=MONO_STACK, size=12, ls=1, anchor="middle")}
<line x1="{FRAME_L}" y1="{rule}" x2="{FRAME_R}" y2="{rule}" stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>'''


def foot_bar(theme, height):
    """The closing band, mirroring the title bar. Only the last slice draws one.

    Same depth and same surface as the chrome at the top, so the window reads as
    having two ends rather than one. It carries no text: the title bar already
    names the window, and repeating that at the foot is the generator credit
    this profile deliberately does not print.
    """
    y1 = height - MARGIN
    y0 = y1 - TITLE_H
    return f'''<line x1="{FRAME_L}" y1="{y0}" x2="{FRAME_R}" y2="{y0}" stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>
<path d="{_fill(FRAME_L, FRAME_R, y0, y1, R_CARD, tl=False, tr=False, br=True, bl=True)}" fill="{theme.surface}"/>'''


def heading(theme, y, name, counter="", cmd=""):
    """A `~/section` header over a hairline rule, and the command behind it.

    Set in mono at 20/700 rather than at a display step: the section markers are
    part of the shell's own voice, not the document's, and `~/` only reads as a
    path in a monospace.

    The rule runs the content width in the hairline colour and is overdrawn for
    its first 120px in the accent at 2px. That stroke is identical in every
    section, which is what makes it structure rather than emphasis: it indexes
    the window without ranking the panels against each other.

    `cmd` goes under the rule as a transcript of what produced the section, so
    the numbers below it name their own source. Its prompt is `$` rather than
    the `❯` the footer closes on: that one is the live prompt, this is quoted
    shell. `$` is also in the subset both vendored monospaces carry, which `❯`
    is not — a glyph repeated in five panels should not depend on a fallback.
    """
    rule = (f'<line x1="{TEXT_X}" y1="{y + 14}" x2="{CONTENT_R}" y2="{y + 14}" '
            f'stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>'
            f'<line x1="{TEXT_X}" y1="{y + 14}" x2="{TEXT_X + 120}" y2="{y + 14}" '
            f'stroke="{theme.accent}" stroke-width="2" shape-rendering="crispEdges"/>')
    right = (tx(CONTENT_R, y, counter, fill=theme.faint, family=MONO_STACK,
                size=12, ls=1, anchor="end") if counter else "")
    command = (f'{tx(TEXT_X, y + CMD_DY, "$", fill=theme.faint, family=MONO_STACK, size=12)}\n'
               f'{tx(TEXT_X + 14, y + CMD_DY, cmd, fill=theme.dim, family=MONO_STACK, size=12)}'
               if cmd else "")
    return f'''{tx(TEXT_X, y, "~/", fill=theme.faint, family=MONO_STACK, size=20, weight=700)}
{tx(TEXT_X + 24, y, name, fill=theme.ink, family=MONO_STACK, size=20, weight=700)}
{right}
{rule}
{command}'''


def to_grid(value):
    """Round a height up to the next grid row."""
    return -(-int(value) // ROW) * ROW


class Slice(NamedTuple):
    """One rendered file, and what the README should do with it.

    A panel returns bare markup when it is a single full-width section. It
    returns Slices when it needs more than that: its own filename, or an
    `href`, since an SVG can only sit inside one anchor and a panel with
    several independently clickable parts must therefore be several files.

    `file` is a path within one theme's directory; render.py prefixes the
    theme name, so a panel never spells a theme into a filename.
    """
    file: str
    markup: str
    href: str | None = None


def describe(markup):
    """The slice's accessible description and pixel width, read back out of it.

    The manifest needs both. Reading them from the finished markup rather than
    having panels report them separately removes the chance of the README's alt
    text drifting from the image's own <desc>.
    """
    desc = re.search(r"<desc[^>]*>(.*?)</desc>", markup, re.S)
    width = re.search(r'<svg[^>]*\swidth="([\d.]+)"', markup)
    return (html.unescape(desc.group(1)) if desc else "",
            float(width.group(1)) if width else W)
