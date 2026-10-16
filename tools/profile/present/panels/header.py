"""Top slice: window chrome, name, handle, role, tagline, live streak."""
from .. import console as c

CMD_Y = 84        # `$ whoami`, the command the rest of the slice answers
NAME_Y = 126      # the one display-size baseline; everything hangs off it
META_Y = 154      # handle · role, and the streak opposite it
TAGLINE_Y = 188
LINE_H = 22
MAX_LINES = 4     # beyond four the slice stops reading as a headline

# The tagline is a list, not a paragraph. Each line is one claim and reads as
# output of the command above it. `»` rather than a bullet or `❯`: both vendored
# monospaces carry it, so it needs no fallback face.
BULLET = "»"
BULLET_X = c.TEXT_X + 18

STREAK_SIZE = 13


def render(cfg, data, theme):
    ident = cfg["identity"]
    name, handle = ident["name"], ident["handle"]
    role = ident["role"]
    lines = list(ident["tagline"])[:MAX_LINES]
    streak = (data.get("stats") or {}).get("streak_current")

    body = [
        c.title_bar(theme, f"{handle} — zsh"),
        # The window opens on the same transcript voice every section below it
        # keeps: a command, then what it printed.
        c.tx(c.TEXT_X, CMD_Y, "$", fill=theme.faint, family=c.MONO_STACK, size=12),
        c.tx(c.TEXT_X + 14, CMD_Y, "whoami", fill=theme.dim,
             family=c.MONO_STACK, size=12),
        # `{typography.display}` literally — the system's largest step, spent
        # on the one thing in the window entitled to it.
        c.tx(c.TEXT_X, NAME_Y, name, fill=theme.ink, family=c.SANS_STACK,
             size=40, weight=600, ls="-0.8"),
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
            # The header's one marked datum: the only live fact on the page.
            f'<circle class="live" cx="{dot_x}" cy="{META_Y - 5}" r="4" '
            f'fill="{theme.accent}"/>',
            c.tx(c.CONTENT_R, META_Y, label, fill=theme.ink,
                 family=c.MONO_STACK, size=13, anchor="end"),
        ]
        tail = f" Current streak {streak} days."

    last_y = META_Y
    for i, line in enumerate(lines):
        last_y = TAGLINE_Y + i * LINE_H
        body += [
            c.tx(c.TEXT_X, last_y, BULLET, fill=theme.faint,
                 family=c.MONO_STACK, size=13),
            c.tx(BULLET_X, last_y, line, fill=theme.dim,
                 family=c.SANS_STACK, size=15),
        ]

    return c.slice_svg(
        theme, c.to_grid(last_y + 26), "\n".join(body),
        title="Profile header",
        desc=f"{name} (@{handle}), {role}. {len(lines)} tagline lines.{tail}",
        top=True,
    )
