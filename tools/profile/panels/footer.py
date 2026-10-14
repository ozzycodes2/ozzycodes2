"""Bottom slice: closes the frame on a live prompt."""
from .. import console as c


def render(_cfg, _data, theme):
    body = (f'<text x="{c.TEXT_X}" y="48" class="mono dim">'
            f'<tspan>❯</tspan><tspan dx="10">exit</tspan>'
            f'<tspan class="ink cursor" dx="10">▌</tspan></text>')

    return c.slice_svg(
        theme, c.to_grid(76), body,
        title="End of profile", desc="Closing prompt: exit.",
        text="❯▌", bottom=True,
    )
