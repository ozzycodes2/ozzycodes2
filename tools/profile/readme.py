"""Rewrites the generated block of README.md from the render manifest.

render.py writes data/manifest.json describing every slice it produced — the
file, its width, its accessible description, and the URL it should link to.
This script turns that into the <img> stack between the markers:

    <!-- profile:start -->  ... generated ...  <!-- profile:end -->

Everything outside the markers is left exactly as it is, so hand-written notes
above or below the console survive the daily job.

Splitting this out of render.py keeps one rule intact: a panel decides what it
says, and only this file decides how the README is spelled. The descriptions
become `alt` text, which is all a screen reader gets — the SVGs themselves are
images to it.
"""
import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
README = ROOT / "README.md"
MANIFEST = HERE / "data" / "manifest.json"

START = "<!-- profile:start -->"
END = "<!-- profile:end -->"


def img(entry):
    """One slice as a themed <picture>, wrapped in an <a> when the manifest
    names a URL.

    render.py writes the same slice under assets/light/ and assets/dark/, and
    GitHub honours `prefers-color-scheme` on a <source>, so the console follows
    the reader's setting. Light is the <img> fallback: a client that ignores
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


def rows(manifest):
    """Group the slices into the lines they must be written on.

    Slices narrower than the full width tile a single row of the console, and
    their widths sum to exactly 100%. A newline between two of them is a text
    node in the rendered HTML, which takes up space and wraps the row — so a
    run of partial-width slices has to be emitted on one line with nothing
    between the tags. Full-width slices get a line each.
    """
    out, run, filled = [], [], 0.0
    for entry in manifest:
        width = float(entry.get("width", "100%").rstrip("%"))
        # A row is closed once it is full, so eight 50%-wide cards become four
        # rows of two rather than one line the renderer has to wrap for us.
        if run and filled + width > 100.0001:
            out.append(run)
            run, filled = [], 0.0
        run.append(entry)
        filled += width
        if filled > 99.9999:
            out.append(run)
            run, filled = [], 0.0
    if run:
        out.append(run)
    return out


def block(manifest):
    lines = ["".join(img(entry) for entry in row) for row in rows(manifest)]
    return "\n".join([START, '<p align="center">', *lines, "</p>", END])


def main():
    if not MANIFEST.exists():
        sys.exit("error: no manifest; run tools/profile/render.py first")
    manifest = json.loads(MANIFEST.read_text())

    text = README.read_text()
    before, found, rest = text.partition(START)
    if not found:
        sys.exit(f"error: README.md is missing the {START} marker")
    _, found, after = rest.partition(END)
    if not found:
        sys.exit(f"error: README.md is missing the {END} marker")

    README.write_text(before + block(manifest) + after)
    print(f"README updated ({len(manifest)} slices)")


if __name__ == "__main__":
    main()
