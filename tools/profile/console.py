"""Primitives for the console frame the README is assembled from.

The README is one continuous terminal window sliced into separate SVG files,
stacked by consecutive <img> tags. Each slice is W wide, a multiple of ROW px
tall so the background grid lines up across the seams, and redraws the same
side rails. Only the first slice draws the top edge and title bar; only the
last closes the frame.

GitHub strips <link> and external url() from rendered SVG, so every slice
embeds its own subset of JetBrains Mono as a base64 woff2.
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

# Palette. Swap these three and the whole README re-themes.
ACCENT = "#00d9ff"
ALT = "#ff2bd6"
OK = "#3fb950"

BG = "#03040a"
FG = "#c9d1d9"
DIM = "#8b949e"
FAINT = "#6e7681"
WHITE = "#f0fbff"

W = 880          # slice width
MARGIN = 16      # transparent gutter, leaves room for the glow to bleed
ROW = 40         # grid pitch; every slice height must be a multiple
TEXT_X = 52      # left edge of body text

FRAME_L = MARGIN
FRAME_R = W - MARGIN

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


def visible(markup):
    """The characters a piece of SVG markup actually paints.

    Font subsetting works from this, so a glyph that only appears inside an
    attribute or a comment is correctly left out, and one that appears in a
    nested tspan is correctly kept.
    """
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def font_faces(text, weights=(400, 700)):
    """@font-face rules carrying only the glyphs `text` needs, inlined as woff2."""
    text += "0123456789"
    rules = []
    for weight in weights:
        # recalcTimestamp=False keeps the bytes stable across runs, so an
        # unchanged panel produces no diff and the daily job pushes nothing.
        font = TTFont(FONT_DIR / f"jetbrains-mono-latin-{weight}-normal.woff2", recalcTimestamp=False)
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
            f"@font-face{{font-family:'JBM';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{payload}) format('woff2')}}"
        )
    return "".join(rules)


BASE_CSS = f"""text{{font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:15px}}
.dim{{fill:{DIM}}}.faint{{fill:{FAINT}}}.ac{{fill:{ACCENT}}}.alt{{fill:{ALT}}}.ok{{fill:{OK}}}.fg{{fill:{FG}}}.wh{{fill:{WHITE}}}
@keyframes fadein{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:none}}}}
@keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
.ln{{animation:fadein .35s ease-out both}}
.cursor{{animation:blink 1.05s step-end infinite}}
.dot{{animation:pulse 2s ease-in-out infinite}}"""

BASE_DEFS = f"""<pattern id="grid" width="{ROW}" height="{ROW}" patternUnits="userSpaceOnUse"><path d="M{ROW} 0H0V{ROW}" fill="none" stroke="{ACCENT}" stroke-opacity=".06"/></pattern>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="soft" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>"""


def slice_svg(height, body, *, title, desc, text="", top=False, bottom=False,
              css="", defs="", weights=(400, 700), width=W, rails="both"):
    """One stacked slice of the window.

    `text` lists glyphs the body needs but does not literally contain — text
    injected by CSS, or drawn from a variable the subsetter cannot see.

    `width` and `rails` together cut a row of the window into side-by-side
    files, which is the only way to give two halves of one row separate links:
    the left half is `width=W//2, rails="left"`, the right half the mirror.
    The half carrying a rail keeps the MARGIN gutter outside it; the other edge
    runs flush to the slice boundary so the two backgrounds and their grids
    meet with no seam. Any half-width must stay a multiple of ROW or the grid
    steps sideways across the join.

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

    edges = ""
    if draw_l:
        edges += f"M{x0} {y0}V{y1}"
    if draw_r:
        edges += f"M{x1} {y0}V{y1}"
    if top:
        edges += f"M{x0} {y0}H{x1}"
    if bottom:
        edges += f"M{x0} {y1}H{x1}"

    # The glow overshoots open seams so adjacent slices blend instead of
    # showing a dark band where one ends.
    gy0, gy1 = y0 if top else -ROW, y1 if bottom else height + ROW
    glow = ""
    if draw_l:
        glow += f"M{x0} {gy0}V{gy1}"
    if draw_r:
        glow += f"M{x1} {gy0}V{gy1}"
    if top:
        glow += f"M{x0} {y0}H{x1}"
    if bottom:
        glow += f"M{x0} {y1}H{x1}"
    if draw_l != draw_r and not (top or bottom):
        # #glow derives its filter region from the path's bounding box, and a
        # lone vertical rail has zero width, which drops the blur altogether —
        # the half-width slices would show a hard rail where every other slice
        # blooms. This run sits above the viewBox: it widens the box without
        # painting anything, since the blur dies well short of y=0.
        glow += f"M{x0} {-2 * ROW}H{x1}"

    corners = ""
    if top:
        if draw_l:
            corners += f'<path d="M{x0 - 7} {y0 + 18}V{y0 - 7}H{x0 + 18}"/>'
        if draw_r:
            corners += f'<path d="M{x1 - 18} {y0 - 7}H{x1 + 7}V{y0 + 18}"/>'
    if bottom:
        if draw_l:
            corners += f'<path d="M{x0 - 7} {y1 - 18}V{y1 + 7}H{x0 + 18}"/>'
        if draw_r:
            corners += f'<path d="M{x1 - 18} {y1 + 7}H{x1 + 7}V{y1 - 18}"/>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
<style>
{font_faces(text + visible(body), weights)}
{BASE_CSS}
{css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
{BASE_DEFS}
{defs}
</defs>
<path d="{glow}" fill="none" stroke="{ACCENT}" stroke-width="3" opacity=".55" filter="url(#glow)"/>
<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="{BG}"/>
<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="url(#grid)"/>
{body}
<path d="{edges}" fill="none" stroke="{ACCENT}" stroke-width="1.2"/>
<g fill="none" stroke="{ACCENT}" stroke-width="2">{corners}</g>
</svg>
'''


def title_bar(y):
    """Traffic lights and window title. Only the top slice draws one."""
    lights = "".join(
        f'<circle cx="{FRAME_L + 24 + i * 18}" cy="{y}" r="5" fill="{c}" opacity=".85"/>'
        for i, c in enumerate((ALT, "#f0b429", OK))
    )
    return f'''{lights}
<text x="{W // 2}" y="{y + 5}" text-anchor="middle" class="faint" style="font-size:12px" letter-spacing="1">ozzycodes2 — zsh</text>
<line x1="{FRAME_L}" y1="{y + 20}" x2="{FRAME_R}" y2="{y + 20}" stroke="{ACCENT}" stroke-opacity=".3"/>'''


def heading(y, name, counter=""):
    """A `~/section` section header with an underline that glows at the left."""
    rule = (f'<line x1="{TEXT_X}" y1="{y + 14}" x2="{FRAME_R - 36}" y2="{y + 14}" stroke="{ACCENT}" stroke-opacity=".4"/>'
            f'<line x1="{TEXT_X}" y1="{y + 14}" x2="{TEXT_X + 120}" y2="{y + 14}" stroke="{ACCENT}" stroke-width="2"/>'
            f'<line x1="{TEXT_X}" y1="{y + 14}" x2="{TEXT_X + 120}" y2="{y + 14}" stroke="{ACCENT}" stroke-width="3" filter="url(#soft)"/>')
    right = (f'<text x="{FRAME_R - 36}" y="{y}" text-anchor="end" letter-spacing="2" class="faint" style="font-size:12px">{e(counter)}</text>'
             if counter else "")
    return f'''<text x="{TEXT_X}" y="{y}" font-weight="700" fill="{ACCENT}" filter="url(#soft)" opacity=".8" style="font-size:20px">~/</text>
<text x="{TEXT_X}" y="{y}" font-weight="700" style="font-size:20px"><tspan class="ac">~/</tspan><tspan class="wh">{e(name)}</tspan></text>
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
    """
    file: str
    markup: str
    href: str | None = None


def write(name, markup):
    """Write one slice. `name` may contain a subdirectory (`links/mail.svg`)."""
    path = OUT / name
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
