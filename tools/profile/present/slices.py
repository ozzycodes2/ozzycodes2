"""The panel registry, and one theme's worth of rendered slices.

Produces markup and manifest rows; writes nothing. `render.py` takes what comes
back and hands it to the data layer, which is the only thing that touches disk.
"""
from . import console as c
from .panels import city, footer, header, projects, route, stack, stats
from ..transform import layout

# Display order, and the order of the manifest. `top` and `bottom` are decided
# from position by the panels themselves, so header stays first and footer last.
PANELS = [
    ("header.svg", header),
    ("stats.svg", stats),
    ("contribution-city.svg", city),
    ("stack.svg", stack),
    ("route.svg", route),
    ("projects.svg", projects),
    ("footer.svg", footer),
]


def slices_of(name, result):
    """Normalise whatever a panel returned into a list of Slices.

    A panel that is one full-width section returns bare markup and gets `name`.
    A panel whose parts need separate links returns its own named slices —
    either Slices, or a plain {filename: markup} mapping when none of them
    link anywhere.
    """
    if isinstance(result, str):
        return [c.Slice(name, result)]
    if isinstance(result, dict):
        return [c.Slice(f, m) for f, m in result.items()]
    return [s if isinstance(s, c.Slice) else c.Slice(*s) for s in result]


def render_theme(cfg, data, theme, panels=None):
    """`[(file, markup, manifest row)]` for one theme, in display order."""
    out = []
    for name, panel in panels or PANELS:
        for entry in slices_of(name, panel.render(cfg, data, theme)):
            desc, width = c.describe(entry.markup)
            out.append((entry.file, entry.markup,
                        layout.row(entry.file, desc, width, c.W, entry.href)))
    return out
