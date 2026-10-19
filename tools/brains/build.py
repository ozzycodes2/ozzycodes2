"""Build the pinned-card GIFs. Run by hand; never from CI.

    .venv/bin/python -m tools.brains.build            # every vendored figure
    .venv/bin/python -m tools.brains.build left-brain # one

Output goes to `gists/`, named the way GitHub shows it: a pinned gist's card
heading is its filename, extension included, so `Left Brain.gif` is the label
and its spaces and capitals are load-bearing. Nothing here writes to `assets/`,
which `update-profile.yml` commits wholesale on every scheduled run.
"""
import pathlib
import sys

from . import capture, encode, figures, parity

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "gists"

# 36 frames of 10cs is 3.6s exactly, which is the loop `brains.js` declares.
# Only 1, 2, 4, 5, 10, 20, 25, 50 and 100 fps come out exact; anything else the
# player rounds, and the GIF drifts against the animation it was captured from.
DURATION = 3.6
DELAY_CS = 10
FRAMES = 36


def title(name):
    """`left-brain` -> `Left Brain`, which is the card heading GitHub paints."""
    return name.replace("-", " ").title()


def playwright_missing():
    """Whether a capture would fail for want of the library.

    Answered by import machinery rather than by importing it, so asking does not
    pull in a browser binding on a machine that has none.
    """
    import importlib.util

    return importlib.util.find_spec("playwright") is None


def render(name, out, *, shoot=None):
    frames = capture.frames(figures.load(name), count=FRAMES, duration=DURATION, shoot=shoot)
    encode.gif(frames, out, delay_cs=DELAY_CS)


def main(argv=None):
    names = list(argv) if argv else [n for n in figures.NAMES if figures.path(n).exists()]
    for name in names:
        try:
            path = figures.path(name)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if not path.exists():
            print(f"error: {name} is not vendored yet; draw it in the preview first", file=sys.stderr)
            return 1

    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        # A warning, not a gate: a machine without the preview could otherwise
        # never build at all.
        drift = parity.diff(name)
        if drift:
            print(f"warning: {name} has drifted from the preview\n{drift}")
        out = OUT / f"{title(name)}.gif"
        render(name, out)
        print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
