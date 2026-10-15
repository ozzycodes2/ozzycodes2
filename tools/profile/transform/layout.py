"""The manifest, and how its slices group into rows.

`render.py` writes one row per rendered slice; `readme.py` and `preview.py`
both need the same slices grouped into the lines they must be written on. That
grouping used to exist twice, once in each, which is exactly the kind of rule
that drifts: a change to how a split row is packed had to be made in two files
or the preview stopped showing what the README would render.
"""


def row(file, desc, width, full, href=None):
    """One manifest entry.

    `width` is the slice's own pixel width and `full` the width of a whole row,
    recorded as a percentage rather than pixels so the console scales with the
    page. Widths within a row sum to `full`, so the percentages sum to 100.
    """
    pct = f"{100 * width / full:.4f}".rstrip("0").rstrip(".") + "%"
    return {"file": file, "desc": desc, "width": pct,
            **({"href": href} if href else {})}


def width_of(entry):
    """An entry's share of its row, as a number."""
    return float(entry.get("width", "100%").rstrip("%"))


def rows(manifest):
    """Group slices into the lines they must be written on.

    Slices narrower than the full width tile a single row of the console, and
    their widths sum to exactly 100%. A newline between two of them is a text
    node in the rendered HTML, which takes up space and wraps the row — so a run
    of partial-width slices has to be emitted on one line with nothing between
    the tags. Full-width slices get a line each.
    """
    out, run, filled = [], [], 0.0
    for entry in manifest:
        width = width_of(entry)
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


def same_slices(a, b):
    """Whether two themes produced the same slice list, in the same order.

    The README pairs the two themes file by file, so a panel that emitted
    different slices for each would silently mismatch them.
    """
    return [r["file"] for r in a] == [r["file"] for r in b]
