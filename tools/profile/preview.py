"""Writes a local page showing every rendered slice, both themes side by side.

The README cannot be previewed as the README: GitHub decides which theme to
serve, so one of the two is always hidden. This page shows both at once, each
column stacked the way the README stacks them, so a seam or a contrast failure
in either is visible without pushing anything.

    .venv/bin/python tools/profile/render.py
    .venv/bin/python tools/profile/preview.py && open assets/preview.html

The SVGs are referenced, not inlined, so a reload picks up a re-render. Each
column paints its own theme's canvas behind the slices, which is what the
README's page background does for real.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tools.profile import console as c

OUT = c.OUT / "preview.html"


def column(theme, manifest):
    """One theme's slices, stacked and grouped into the README's own rows."""
    rows, run, filled = [], [], 0.0
    for entry in manifest:
        width = float(entry.get("width", "100%").rstrip("%"))
        if run and filled + width > 100.0001:
            rows.append(run)
            run, filled = [], 0.0
        run.append(entry)
        filled += width
        if filled > 99.9999:
            rows.append(run)
            run, filled = [], 0.0
    if run:
        rows.append(run)

    stack = "".join(
        '<div class="row">' + "".join(
            f'<img src="./{theme.name}/{e["file"]}" style="width:{e.get("width", "100%")}">'
            for e in row
        ) + "</div>"
        for row in rows
    )
    return (f'<section style="background:{theme.canvas};color:{theme.ink}">'
            f'<h2 style="border-color:{theme.hairline}">{theme.name}</h2>'
            f'{stack}</section>')


def page(manifest):
    columns = "".join(column(theme, manifest) for theme in c.THEMES)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>profile console — both themes</title>
<style>
  body {{ margin: 0; display: grid; grid-template-columns: repeat({len(c.THEMES)}, 1fr); font-family: {c.SANS_STACK} }}
  section {{ padding: 24px }}
  h2 {{ margin: 0 0 16px; font: 400 13px/1 {c.MONO_STACK}; text-transform: uppercase;
       letter-spacing: .08em; padding-bottom: 12px; border-bottom: 1px solid }}
  /* The slices butt together to read as one window, so no gap and no spare
     line box between them — the same reason readme.py writes a row on one line. */
  .row {{ display: flex; font-size: 0 }}
  img {{ display: block }}
</style>
{columns}
"""


def main():
    manifest = c.DATA / "manifest.json"
    if not manifest.exists():
        sys.exit("error: no manifest; run tools/profile/render.py first")
    OUT.write_text(page(json.loads(manifest.read_text())))
    print(f"wrote {OUT.relative_to(c.ROOT)}")


if __name__ == "__main__":
    main()
