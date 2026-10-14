"""Top slice: window chrome, name, handle, role, tagline, live streak."""
from .. import console as c

NAME_Y = 104      # the one display-size baseline; everything hangs off it
META_Y = 130      # handle · role, and the streak opposite it
TAGLINE_Y = 176
LINE_H = 22
MAX_LINES = 4     # beyond four the slice stops reading as a headline

STREAK_SIZE = 13


def render(cfg, data, theme):
    ident = cfg["identity"]
    name, handle = ident["name"], ident["handle"]
    role = ident["role"]
    lines = list(ident["tagline"])[:MAX_LINES]
    streak = (data.get("stats") or {}).get("streak_current")

    body = [
        c.title_bar(theme, f"{handle} — zsh"),
        c.tx(c.TEXT_X, NAME_Y, name, fill=theme.ink, family=c.SANS_STACK,
             size=30, weight=600, ls="-0.5"),
        c.tx(c.TEXT_X, META_Y, f"@{handle} · {role}", fill=theme.dim,
             family=c.MONO_STACK, size=13),
    ]

    if streak is None:
        tail = ""
    else:
        label = f"{streak}-day streak"
        # Mono advances 0.6em, so an end-anchored run of n characters starts
        # 0.6·n·size back from the right edge — which is where the dot goes.
        dot_x = c.CONTENT_R - round(len(label) * STREAK_SIZE * c.MONO_ADVANCE) - 12
        body += [
            # The one live fact on the page, and the only thing wearing the accent.
            f'<circle class="live" cx="{dot_x}" cy="{META_Y - 5}" r="4" '
            f'fill="{theme.accent}"/>',
            c.tx(c.CONTENT_R, META_Y, label, fill=theme.ink,
                 family=c.MONO_STACK, size=13, anchor="end"),
        ]
        tail = f" Current streak {streak} days."

    last_y = META_Y
    for i, line in enumerate(lines):
        last_y = TAGLINE_Y + i * LINE_H
        body.append(c.tx(c.TEXT_X, last_y, line, fill=theme.dim,
                         family=c.SANS_STACK, size=15))

    return c.slice_svg(
        theme, c.to_grid(last_y + 28), "\n".join(body),
        title="Profile header",
        desc=f"{name} (@{handle}), {role}. {len(lines)} tagline lines.{tail}",
        top=True,
    )
