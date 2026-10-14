"""Primitives for the console frame the README is assembled from.

The README is one continuous window sliced into separate SVG files, stacked by
consecutive <img> tags. Each slice is W wide, a multiple of ROW px tall, and
redraws the same side rails. Only the first slice caps the top and draws the
title bar; only the last closes the frame.

Every colour comes from a Theme. LIGHT is the Mine v2 token set, DARK is Mine's;
panels never name a colour, they ask the theme for a role. render.py runs each
panel once per theme and readme.py pairs the output with <picture>, so the
console follows the reader's system setting.

Type is Mine v2's five steps for both themes — the systems differ in palette and
depth, not in how they name type. Inter is embedded because GitHub strips
<link> and external url() from a rendered SVG. SF Mono cannot be: it is not
redistributable, so the mono stack asks for it first and falls back to an
embedded JetBrains Mono subset everywhere it is absent.
"""
import base64
import datetime
import html
import io
import pathlib
import re
from typing import NamedTuple

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "data"
OUT = ROOT / "assets"
FONT_DIR = HERE / "fonts"


class Theme(NamedTuple):
    """One palette, named for the `prefers-color-scheme` value it answers.

    `accent` is state, not decoration: it paints the live dot and nothing else.
    `surface` sits one step toward the ink from `canvas`, `sunken` one step
    further, which is the whole of this system's depth — there are no shadows.
    """
    name: str
    canvas: str
    surface: str
    sunken: str
    ink: str
    dim: str
    hairline: str
    accent: str
    on_accent: str


# Mine v2: eight achromatic tokens with signal red reserved for state.
LIGHT = Theme(
    name="light",
    canvas="#f8f8f8", surface="#ffffff", sunken="#ededed",
    ink="#171717", dim="#616161", hairline="#d9d9d9",
    accent="#cc3300", on_accent="#ffffff",
)

# Mine: Linear's near-black ladder under Apple's component vocabulary.
DARK = Theme(
    name="dark",
    canvas="#010102", surface="#0f1011", sunken="#141516",
    ink="#f7f8f8", dim="#8a8f98", hairline="#3e3e44",
    accent="#5e6ad2", on_accent="#ffffff",
)

THEMES = (LIGHT, DARK)

# Both token sets declare the same Apple-derived ladder, so these are shared.
R_CARD = 18
R_CONTROL = 11
R_INLINE = 5


class Step(NamedTuple):
    """A type step: px size, weight, and tracking in px."""
    size: float
    weight: int
    tracking: float = 0


DISPLAY = Step(40, 600, -0.8)
HEADING = Step(24, 600, -0.24)
BODY = Step(16, 400)
CAPTION = Step(13, 400)
MONO = Step(14, 400)

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

FRAME_L = MARGIN
FRAME_R = W - MARGIN
CONTENT_R = FRAME_R - 36

# The rails are the one thing that has to agree across slices: each file is
# rasterised on its own, and a rail whose edges fall mid-pixel can be rounded
# one way in one slice and the other way in the next, which reads as the frame
# stepping sideways at every seam. A 1px stroke on an integer coordinate plus
# `crispEdges` makes every slice snap the rail to the same device column.
EDGE_W = 1

e = html.escape


def ago(when, now=None):
    """Coarse "N units ago" for an ISO-8601 instant, or "" if there isn't one.

    Panels print this next to repo and event timestamps, so it rounds hard —
    the reader wants "2 months ago", not a duration. Returns the empty string
    for None or anything unparseable rather than raising, because the only
    caller is a renderer that must still produce a panel.
    """
    if not when:
        return ""
    try:
        at = datetime.datetime.fromisoformat(when)
    except (TypeError, ValueError):
        return ""
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)

    seconds = (now - at).total_seconds()
    if seconds < 90:
        return "just now"
    # (singular unit, seconds per unit, how many fit before promoting). Months
    # and years use the mean Gregorian length, so "11 months" never rounds up
    # into "1 year" while the calendar still says otherwise.
    for unit, size, limit in (("minute", 60, 60), ("hour", 3600, 24),
                              ("day", 86400, 31), ("month", 2629800, 12)):
        if seconds < size * limit:
            n = max(int(seconds // size), 1)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    n = max(int(seconds // 31557600), 1)
    return f"{n} year{'s' if n > 1 else ''} ago"


def mix(a, b, t):
    """`t` of colour `a` over colour `b`, as a literal hex.

    Panels shade with this rather than with `fill-opacity`, because the city's
    blocks overlap: a translucent face shows the block behind it through its own
    wall and the plan stops reading as solid. Both arguments must be #rrggbb.
    """
    x, y = (tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (a, b))
    return "#" + "".join(f"{round(p * t + q * (1 - t)):02x}" for p, q in zip(x, y))


def visible(markup):
    """The characters a piece of SVG markup actually paints.

    Font subsetting works from this, so a glyph that only appears inside an
    attribute or a comment is correctly left out, and one that appears in a
    nested tspan is correctly kept.
    """
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


# (family name the CSS asks for, file stem, weight). Inter carries the four
# sans steps; JBM is the fallback under SF Mono, which cannot be embedded.
FACES = (
    ("Inter", "inter-latin-400-normal", 400),
    ("Inter", "inter-latin-600-normal", 600),
    ("JBM", "jetbrains-mono-latin-400-normal", 400),
)


def font_faces(text):
    """@font-face rules carrying only the glyphs `text` needs, inlined as woff2."""
    text += "0123456789"
    rules = []
    for family, stem, weight in FACES:
        # recalcTimestamp=False keeps the bytes stable across runs, so an
        # unchanged panel produces no diff and the daily job pushes nothing.
        font = TTFont(FONT_DIR / f"{stem}.woff2", recalcTimestamp=False)
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = []
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        payload = base64.b64encode(buf.getvalue()).decode()
        rules.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{payload}) format('woff2')}}"
        )
    return "".join(rules)


def _step_css(name, step, family=None):
    face = f"font-family:{family};" if family else ""
    tracking = f";letter-spacing:{step.tracking}px" if step.tracking else ""
    return f".{name}{{{face}font-size:{step.size}px;font-weight:{step.weight}{tracking}}}"


def base_css(theme):
    """The five type steps as classes, plus the theme's three text fills."""
    steps = "".join(_step_css(*s) for s in (
        ("display", DISPLAY), ("heading", HEADING),
        ("body", BODY), ("caption", CAPTION), ("mono", MONO, MONO_STACK),
    ))
    return f"""text{{font-family:{SANS_STACK};font-size:{BODY.size}px;fill:{theme.ink}}}
{steps}
.ink{{fill:{theme.ink}}}.dim{{fill:{theme.dim}}}.accent{{fill:{theme.accent}}}
@keyframes fadein{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:none}}}}
@keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
.ln{{animation:fadein .35s ease-out both}}
.cursor{{animation:blink 1.05s step-end infinite}}
.dot{{animation:pulse 2.4s ease-in-out infinite}}"""


def _outline(x0, x1, y0, y1, r, *, top, bottom, left, right):
    """The frame's own edge, as one path, rounding only where two edges meet.

    A middle slice rounds nothing and draws two bare rails; a capped slice
    rounds the corners where its horizontal edge meets a rail it also draws.
    The path is left open at every uncapped end, so the stroke stops there and
    the next slice continues it.
    """
    tl, tr, br, bl = top and left, top and right, bottom and right, bottom and left
    parts = []
    if left:
        parts.append(f"M{x0} {y1 - (r if bl else 0)}V{y0 + (r if tl else 0)}")
        if tl:
            parts.append(f"a{r} {r} 0 0 1 {r} {-r}")
    if top:
        parts.append(("H" if tl else f"M{x0} {y0}H") + f"{x1 - (r if tr else 0)}")
        if tr:
            parts.append(f"a{r} {r} 0 0 1 {r} {r}")
    if right:
        parts.append(("V" if tr else f"M{x1} {y0}V") + f"{y1 - (r if br else 0)}")
        if br:
            parts.append(f"a{r} {r} 0 0 1 {-r} {r}")
    if bottom:
        parts.append(("H" if br else f"M{x1} {y1}H") + f"{x0 + (r if bl else 0)}")
        if bl:
            parts.append(f"a{r} {r} 0 0 1 {-r} {-r}")
    return "".join(parts)


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
    outline = _outline(x0, x1, y0, y1, R_CARD,
                       top=top, bottom=bottom, left=draw_l, right=draw_r)
    fill = _fill(x0, x1, y0, y1, R_CARD, **corners)

    # Only a rail is straight enough to snap to a device column; an arc that
    # is told to snap grows a visible step where it meets the rail.
    rendering = "auto" if any(corners.values()) else "crispEdges"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
<style>
{font_faces(text + visible(body))}
{base_css(theme)}
{css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
{defs}
</defs>
<path d="{fill}" fill="{theme.canvas}"/>
{body}
<path d="{outline}" fill="none" stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="{rendering}"/>
</svg>
'''


def title_bar(theme, y):
    """Window chrome and title. Only the top slice draws one.

    Three hairline rings rather than traffic lights: the colour vocabulary has
    one accent and it is spent on live state, so the chrome is drawn in the
    same edge colour as the frame it belongs to.
    """
    rings = "".join(
        f'<circle cx="{FRAME_L + 28 + i * 20}" cy="{y}" r="5" fill="none" '
        f'stroke="{theme.hairline}" stroke-width="{EDGE_W}"/>'
        for i in range(3)
    )
    return f'''<path d="{_fill(FRAME_L, FRAME_R, y - 24, y + 20, R_CARD, tl=True, tr=True, br=False, bl=False)}" fill="{theme.surface}"/>
{rings}
<text x="{W // 2}" y="{y + 4}" text-anchor="middle" class="caption dim">ozzycodes2</text>
<line x1="{FRAME_L}" y1="{y + 20}" x2="{FRAME_R}" y2="{y + 20}" stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>'''


def heading(theme, y, name, counter=""):
    """A `~/section` header over a hairline rule.

    The rule runs the content width in the hairline colour and is overdrawn for
    its first 120px in the ink, which is the whole of the emphasis — there is
    no glow and no second colour to reach for.
    """
    rule = (f'<line x1="{TEXT_X}" y1="{y + 16}" x2="{CONTENT_R}" y2="{y + 16}" '
            f'stroke="{theme.hairline}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>'
            f'<line x1="{TEXT_X}" y1="{y + 16}" x2="{TEXT_X + 120}" y2="{y + 16}" '
            f'stroke="{theme.ink}" stroke-width="{EDGE_W}" shape-rendering="crispEdges"/>')
    right = (f'<text x="{CONTENT_R}" y="{y}" text-anchor="end" class="mono dim">{e(counter)}</text>'
             if counter else "")
    return f'''<text x="{TEXT_X}" y="{y}" class="heading ink"><tspan class="dim">~/</tspan>{e(name)}</text>
{right}
{rule}'''


def stagger(rows, y0, line_height, delay=0.15, step=0.12):
    """Wrap rows in fade-in groups that arrive one after another, like typed output.

    Each row is markup containing `{y}`; None inserts a small spacer instead
    of a row. Returns (markup, y below the last row).
    """
    out, y, n = [], y0, 0
    for row in rows:
        if row is None:
            y += 14
            continue
        n += 1
        out.append(f'<g class="ln" style="animation-delay:{delay + n * step:.2f}s">'
                   + row.replace("{y}", str(y)) + "</g>")
        y += line_height
    return "\n".join(out), y


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


def write(theme, name, markup):
    """Write one slice under its theme. `name` may contain a subdirectory."""
    path = OUT / theme.name / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markup)
    return path


def describe(markup):
    """The slice's accessible description and pixel width, read back out of it.

    render.py needs both for the manifest. Reading them from the finished file
    rather than having panels report them separately removes the chance of the
    README's alt text drifting from the image's own <desc>.
    """
    desc = re.search(r"<desc[^>]*>(.*?)</desc>", markup, re.S)
    width = re.search(r'<svg[^>]*\swidth="([\d.]+)"', markup)
    return (html.unescape(desc.group(1)) if desc else "",
            float(width.group(1)) if width else W)
