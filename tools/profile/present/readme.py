"""The generated block of README.md, written from the render manifest.

A panel decides what it says; only this module decides how the README is
spelled. The manifest's descriptions become `alt` text, which is all a screen
reader gets — the SVGs themselves are images to it.

Everything outside the markers is left exactly as it is, so hand-written notes
above or below the console survive the daily job.
"""
import html

from ..transform import layout

START = "<!-- profile:start -->"
END = "<!-- profile:end -->"


def img(entry):
    """One slice as a themed <picture>, wrapped in an <a> when it names a URL.

    The same slice exists under assets/light/ and assets/dark/, and GitHub
    honours `prefers-color-scheme` on a <source>, so the console follows the
    reader's setting. Light is the <img> fallback: a client that ignores
    <picture> entirely still gets a readable console rather than nothing.

    `align="top"` is what keeps consecutive half-width slices on the same row
    without a gap; GitHub's markdown renderer otherwise baseline-aligns them
    and the frame develops a seam. It sits on the <img>, which is the element
    that is actually laid out.
    """
    alt = html.escape(entry["desc"], quote=True)
    width = entry.get("width", "100%")
    tag = (f'<picture>'
           f'<source media="(prefers-color-scheme: dark)" srcset="./assets/dark/{entry["file"]}">'
           f'<img src="./assets/light/{entry["file"]}" width="{width}" '
           f'align="top" alt="{alt}">'
           f'</picture>')
    href = entry.get("href")
    return f'<a href="{html.escape(href, quote=True)}">{tag}</a>' if href else tag


def block(manifest):
    """The whole console, one `<p>`, left-aligned.

    Not centred, which it was: every slice is `width="100%"` except the two
    halves of a card row, so centring aligns nothing — it only decides where the
    slack goes when those halves do not sum to the column. Engines that lay
    images out in whole pixels round each 50% down, leaving the row a pixel
    narrow; centred, half that pixel lands on the left and the row's rail sits
    inside the rail of every full-width slice above and below it. Left-aligned,
    every slice's left edge is the column's left edge and the slack collects at
    the right, inside the frame's own gutter.
    """
    lines = ["".join(img(entry) for entry in row) for row in layout.rows(manifest)]
    return "\n".join([START, "<p>", *lines, "</p>", END])


def splice(text, generated):
    """`text` with everything between the markers replaced.

    Raises ValueError naming the missing marker, so the caller can exit with a
    message rather than silently appending a second console to the file.
    """
    before, found, rest = text.partition(START)
    if not found:
        raise ValueError(f"README.md is missing the {START} marker")
    _, found, after = rest.partition(END)
    if not found:
        raise ValueError(f"README.md is missing the {END} marker")
    return before + generated + after
