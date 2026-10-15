"""Bottom slice: closes the frame on a live prompt."""
from .. import console as c

# The frame closes directly under the prompt. A band mirroring the title bar's
# depth is the obvious symmetry and it was wrong twice over: the preview sets a
# second line of metadata inside that band and this footer has no second line,
# so it drew an empty row under `exit`; and the dark theme's surface is 1.01:1
# from GitHub's own dark page, so those 44px did not read as a closing band at
# all but as a hole the bottom of the window fell through.
HEIGHT = 80
PROMPT_Y = 40


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
        theme, HEIGHT, prompt,
        title="End of profile", desc="Closing prompt: exit.",
        text="❯▌", bottom=True,
    )
