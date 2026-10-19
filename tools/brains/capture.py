"""One PNG per animation frame, by explicit seek in a real browser.

No static rasterizer can do this. librsvg, resvg, CairoSVG and Inkscape all
render frame zero and decline SMIL explicitly, and resvg underpins the Rust SVG
stack, so no Rust-native tool will either.

`--virtual-time-budget` is the wrong lever even in Chrome: it freezes composited
CSS transforms at 0 while SMIL advances, and it is not reproducible — three
identical runs put the figure in three different positions. Pausing and setting
the time explicitly gives byte-identical frames across repeats.
"""
from . import figures

_PAGE = """<!doctype html><meta charset="utf-8">
<body style="margin:0;background:transparent">{svg}</body>"""

# The SVG is inlined into the page deliberately. Referenced through an `<img>`
# it is frozen and exposes no `contentDocument`, so there is nothing to seek.
_SEEK = """(t) => {
  const svg = document.querySelector('svg');
  svg.pauseAnimations();
  svg.setCurrentTime(t);
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = t * 1000; });
}"""


def times(count, duration):
    """`count` sample points across one loop, the closing seam excluded.

    Sampling `duration` itself would repeat frame zero, which in a GIF playing
    on a loop is a visible hitch once per cycle.
    """
    if count < 1:
        raise ValueError("a capture needs at least one frame")
    return [round(i * duration / count, 6) for i in range(count)]


def chrome_shoot(svg, times, width, height):
    """The browser-dependent half, and the only one.

    Raises whatever Playwright raises when it or its browser is missing; the
    import is inside the call so that importing this module never needs either.
    """
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as pw:
        # The installed Chrome, not a downloaded build: a mismatched Playwright
        # pin otherwise fails looking for a headless shell that was never
        # fetched.
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(_PAGE.format(svg=svg))
        for t in times:
            page.evaluate(_SEEK, t)
            out.append(page.screenshot(omit_background=True))
        browser.close()
    return out


def frames(svg, *, count, duration, shoot=None):
    """One PNG per frame of `svg`'s loop, at the published master size."""
    at = times(count, duration)
    out = (shoot or chrome_shoot)(svg, at, figures.W, figures.H)
    if len(out) != len(at):
        raise ValueError(f"asked for {len(at)} frames, the shooter returned {len(out)}")
    return list(out)
