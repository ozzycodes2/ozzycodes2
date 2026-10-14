"""Bottom slice: closes the frame on a live prompt."""
from .. import console as c

HEIGHT = 120
PROMPT_Y = 48


def render(_cfg, _data, theme):
    # Three fills in one line, so this is the one label that cannot go through
    # c.tx: the glyph, the command and the cursor each take a different tier.
    prompt = (
        f'<text x="{c.TEXT_X}" y="{PROMPT_Y}" font-family="{c.e(c.MONO_STACK)}" font-size="12">'
        f'<tspan fill="{theme.faint}">❯</tspan>'
        f'<tspan fill="{theme.dim}" dx="10">exit</tspan>'
        f'<tspan fill="{theme.ink}" dx="10">▌</tspan>'
        f'</text>'
    )

    return c.slice_svg(
        theme, HEIGHT, f"{prompt}\n{c.foot_bar(theme, HEIGHT)}",
        title="End of profile", desc="Closing prompt: exit.",
        text="❯▌", bottom=True,
    )
