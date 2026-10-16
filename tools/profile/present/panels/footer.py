"""Bottom slice: closes the frame on the command that ends the session."""
from .. import console as c

# The frame closes directly under the sign-off. A band mirroring the title bar's
# depth is the obvious symmetry and it was wrong twice over: the preview sets a
# second line of metadata inside that band and this footer has none to put
# there, so it drew an empty row under `exit`; and the dark theme's surface is
# 1.01:1 from GitHub's own dark page, so those 44px did not read as a closing
# band at all but as a hole the bottom of the window fell through.
HEIGHT = 120
PROMPT_Y = 44     # `$ exit`
CLOSE_Y = 66      # what the shell printed back


def render(cfg, _data, theme):
    handle = (cfg.get("identity") or {}).get("handle", "")
    where = f" to {handle}" if handle else ""
    closed = f"connection{where} closed. //EOF"

    # Two fills in one line, so this is the one label that cannot go through
    # c.tx: the prompt and the command sit in different tiers, as they do in
    # every section heading above.
    prompt = (
        f'<text x="{c.TEXT_X}" y="{PROMPT_Y}" font-family="{c.e(c.MONO_STACK)}" font-size="12">'
        f'<tspan fill="{theme.faint}">$</tspan>'
        f'<tspan fill="{theme.dim}" dx="10">exit</tspan>'
        f'</text>'
    )

    return c.slice_svg(
        theme, HEIGHT,
        prompt + "\n" + c.tx(c.TEXT_X, CLOSE_Y, closed, fill=theme.faint,
                             family=c.MONO_STACK, size=12),
        title="End of profile",
        desc=f"Closing prompt: exit. {closed[0].upper()}{closed[1:]}",
        bottom=True,
    )
