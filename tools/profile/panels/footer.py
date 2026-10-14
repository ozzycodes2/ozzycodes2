"""Bottom slice: closes the frame on a live prompt."""
from .. import console as c


def render(_cfg, data, theme):
    updated = (data.get("stats") or {}).get("updated")
    credit = "rendered from profile.toml and the GitHub API by a scheduled job"
    stamp = f"last run {updated}" if updated else "last run unknown"

    body = [
        f'<text x="{c.TEXT_X}" y="48" class="mono dim">'
        f'<tspan>❯</tspan><tspan dx="10">exit</tspan>'
        f'<tspan class="ink cursor" dx="10">▌</tspan></text>',
        f'<text x="{c.W // 2}" y="84" text-anchor="middle" class="caption dim">'
        f'{c.e(credit)} — {c.e(stamp)}</text>',
    ]

    return c.slice_svg(
        theme, c.to_grid(104), "\n".join(body),
        title="End of profile", desc=f"Closing prompt: exit. This README is {credit}; {stamp}.",
        text="❯▌—", bottom=True,
    )
