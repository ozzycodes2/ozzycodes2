"""The vendored hemisphere drawings and the facts every stage downstream holds.

The SVGs here are generated, not written. `design-preview` is where the drawing
is authored and looked at; this is the copy that makes a capture reproducible on
a machine that has only this repository. `parity.py` is what keeps the two
honest.
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent

NAMES = ("left-brain", "right-brain")

# GitHub paints a pinned image at 100 CSS px tall, so this is the 4x master the
# browser downscales. The downscale is also the only antialiasing the drawing
# gets: GIF alpha is one bit, and GitHub strips density descriptors from srcset.
W, H = 1340, 400

# Theme-invariant by design, so an accent-on-transparent drawing needs no themed
# pair. 3.25:1 on GitHub light, 5.82:1 on dark — both clear the 3:1 floor for a
# graphical object, and nothing lighter clears it on light. The drawing paints
# this hue at several shades of it, every one of which has to clear the same
# floor; `test_brains_figures.py` is where that is checked.
ACCENT = "#ef6306"

_FIELD = re.compile(r"^(?:\s|<!--)*(source|generated):\s*(\S+)\s*$", re.M)
_PAINT = re.compile(r'(?:fill|stroke)="(#[0-9a-f]{6})"')


def accent_rgb():
    """`ACCENT` as a byte triple."""
    return tuple(int(ACCENT[i : i + 2], 16) for i in (1, 3, 5))


def paints(name):
    """Every colour the drawing names, brightest first.

    Read off the file rather than listed here, because this is what the GIF
    palette is built from: a list kept alongside the drawing would go stale the
    first time a shade changed, and the symptom would be a flattened figure
    rather than an error.
    """
    found = {tuple(int(h[i : i + 2], 16) for i in (1, 3, 5)) for h in _PAINT.findall(load(name))}
    return sorted(found, key=lambda c: (-sum(c), c))


def path(name):
    """The vendored file for `name`, whether or not it exists yet."""
    if name not in NAMES:
        raise FileNotFoundError(f"{name!r} is not a hemisphere: expected one of {NAMES}")
    return HERE / f"{name}.svg"


def load(name):
    return path(name).read_text()


def provenance(name):
    """`source` and `generated` off the leading comment.

    Vendoring means two renderers can disagree about one drawing. This is the
    half of the answer that travels with the file; `parity.diff` is the other.
    """
    head = load(name).split("-->", 1)[0]
    found = dict(_FIELD.findall(head))
    missing = {"source", "generated"} - found.keys()
    if missing:
        raise ValueError(f"{name}.svg states no {', '.join(sorted(missing))}")
    return found
