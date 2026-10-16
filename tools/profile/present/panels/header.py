"""Top slice: window chrome, name, handle, role, tagline, live streak."""
import re

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

# A `*word*` opening a tagline line is set as a branded chip.
CHIP = re.compile(r"^\*([^*]+)\*\s*")
CHIP_SIZE = 13
CHIP_H = 21
CHIP_PAD = 9      # mono's side bearing inside the chip
CHIP_GAP = 10     # chip to the prose that follows it
CHIP_TINT = "0.18"


def _tagline(theme, y, line):
    """One tagline line, with a `*marked*` leading word set as a branded chip.

    The chip is accent as a *surface* under ink type, which is the only way this
    system may colour a word: the accent is corrected to 3:1, the threshold for
    an object, so a word painted in it outright is the one unreadable thing on
    the page. A tint and no edge — the accent budget counts paints, and an edge
    would spend the panel's second one on the same shape.

    The mark is honoured only at the start of a line. The prose after the chip
    is placed from the chip's width, and only the mono face can be measured
    before it is drawn; Inter mid-line cannot be, so there is nowhere else in a
    line to put one.
    """
    out = [c.tx(c.TEXT_X, y, BULLET, fill=theme.faint, family=c.MONO_STACK,
                size=13)]
    x = BULLET_X
    marked = CHIP.match(line)
    if marked:
        word = marked.group(1)
        width = round(len(word) * CHIP_SIZE * c.MONO_ADVANCE) + CHIP_PAD * 2
        out += [
            f'<rect x="{x}" y="{y - 15}" width="{width}" height="{CHIP_H}" '
            f'rx="{c.R_CHIP}" fill="{theme.accent}" fill-opacity="{CHIP_TINT}"/>',
            c.tx(x + CHIP_PAD, y, word, fill=theme.ink, family=c.MONO_STACK,
                 size=CHIP_SIZE, weight=700),
        ]
        x += width + CHIP_GAP
        line = line[marked.end():]
    out.append(c.tx(x, y, line, fill=theme.dim, family=c.SANS_STACK, size=15))
    return out


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
        body += _tagline(theme, last_y, line)

    return c.slice_svg(
        theme, c.to_grid(last_y + 26), "\n".join(body),
        title="Profile header",
        desc=f"{name} (@{handle}), {role}. {len(lines)} tagline lines.{tail}",
        top=True,
    )
