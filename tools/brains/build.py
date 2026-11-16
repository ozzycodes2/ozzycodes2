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

# 30 frames of 4cs is 1.2s exactly, which is the loop `brains.js` declares.
# Only 1, 2, 4, 5, 10, 20, 25, 50 and 100 fps come out exact; anything else the
# player rounds, and the GIF drifts against the animation it was captured from.
#
# 25fps because 10 stepped visibly: the comet is a small bright mark and the eye
# tracks its head, which is the worst case for a low rate. The encoder writes
# near-enough a full frame per tick — measured, size tracks frame count almost
# linearly — so the rate was paid for by shortening the loop to a single dash
# repeat rather than by spending frames. 50fps is the next step up and puts the
# right half past 250 KB.
DURATION = 1.2
DELAY_CS = 4
FRAMES = 30

# What a pinned card may cost. Camo is not in the path for a gist file, so
# nothing enforces this but the number itself; Terkel's reference is 117 KB for
# 48 frames at this size, and the thrown field is what put these past it — 64
# marks move every tick and none of them repeats a previous frame, so there is
# almost no compression to find and size tracks the frame count. 243 KB and
# 270 KB measured. The ceiling leaves room for a mark or two and none for
# another lane.
BUDGET = 300_000


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


# Where `channel="chrome"` looks. Playwright resolves the channel through the
# OS, not through its own download cache.
CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def chrome_missing():
    """Whether the browser itself is absent, which the library's presence does
    not answer.

    `capture.chrome_shoot` launches `channel="chrome"` — the Google Chrome
    already on the machine. A clone that ran `playwright install chromium` has
    the pip package and a managed build and still cannot satisfy that channel,
    so gating a test on the package alone turns a skip into a hard failure.
    """
    import shutil

    return not any(pathlib.Path(p).exists() for p in CHROME) and not any(
        shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser")
    )


def render(name, out, *, shoot=None):
    frames = capture.frames(figures.load(name), count=FRAMES, duration=DURATION, shoot=shoot)
    encode.gif(frames, out, delay_cs=DELAY_CS, inks=figures.paints(name))


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
