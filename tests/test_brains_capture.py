"""Tests for frame capture.

Every test here injects a fake shooter. None launches a browser: the repo's CI
installs `fonttools` and `brotli` and nothing else, and a suite that needs
Chromium to go green would be red on every machine but this one. The seam is
the point, so it is what gets tested.
"""
import sys
import types

import pytest

from tools.brains import capture, figures


class FakePage:
    def __init__(self, log):
        self.log = log

    def set_content(self, html):
        self.log.append(("content", html))

    def evaluate(self, script, arg):
        self.log.append(("seek", script, arg))

    def screenshot(self, **kw):
        self.log.append(("shot", kw))
        return b"png"


class FakeBrowser:
    def __init__(self, log):
        self.log = log

    def new_page(self, **kw):
        self.log.append(("page", kw))
        return FakePage(self.log)

    def close(self):
        self.log.append(("close",))


class FakePlaywright:
    """Enough of the sync API for `chrome_shoot`'s call sequence.

    Standing in for the library rather than for a browser: what is worth
    asserting here is that the figure is inlined, paused, seeked once per frame
    and shot without a background — none of which needs Chromium to check.
    """

    def __init__(self, log):
        self.log = log
        self.chromium = types.SimpleNamespace(launch=self._launch)

    def _launch(self, **kw):
        self.log.append(("launch", kw))
        return FakeBrowser(self.log)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_playwright(monkeypatch):
    log = []
    mod = types.ModuleType("playwright.sync_api")
    mod.sync_playwright = lambda: FakePlaywright(log)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)
    return log


def test_times_span_one_loop_without_repeating_the_seam():
    """The last frame must not duplicate frame zero, or the loop stutters once
    per cycle on a card nobody can pause."""
    assert capture.times(4, 2.0) == [0.0, 0.5, 1.0, 1.5]


def test_a_single_frame_is_frame_zero():
    assert capture.times(1, 3.6) == [0.0]


def test_times_refuses_to_shoot_nothing():
    with pytest.raises(ValueError, match="at least one frame"):
        capture.times(0, 3.6)


def test_frames_asks_the_shooter_for_one_image_per_time():
    seen = {}

    def shoot(svg, times, width, height):
        seen.update(svg=svg, times=times, width=width, height=height)
        return [b"png"] * len(times)

    out = capture.frames("<svg/>", count=3, duration=3.0, shoot=shoot)
    assert len(out) == 3
    assert seen["times"] == [0.0, 1.0, 2.0]
    assert (seen["width"], seen["height"]) == (figures.W, figures.H)
    assert seen["svg"] == "<svg/>"


def test_a_shooter_that_returns_the_wrong_count_is_an_error():
    """A short run means the seek silently failed on some frames, and the
    encoder downstream would happily make a shorter loop out of it."""
    with pytest.raises(ValueError, match="3 frames"):
        capture.frames("<svg/>", count=3, duration=3.0, shoot=lambda *a: [b"png"])


def test_the_default_shooter_is_the_browser_one():
    assert capture.frames.__kwdefaults__["shoot"] is None
    assert capture.chrome_shoot.__module__ == capture.__name__


def test_the_shooter_inlines_the_figure_rather_than_referencing_it(fake_playwright):
    """Through an `<img>` an SVG is frozen and has no `contentDocument`, so
    there is nothing to seek and every frame comes back identical."""
    capture.chrome_shoot("<svg id='x'/>", [0.0], 1340, 400)
    html = next(e[1] for e in fake_playwright if e[0] == "content")
    assert "<svg id='x'/>" in html and "<img" not in html


def test_the_shooter_seeks_once_per_frame_and_pauses_first(fake_playwright):
    out = capture.chrome_shoot("<svg/>", [0.0, 1.8], 1340, 400)
    seeks = [e for e in fake_playwright if e[0] == "seek"]
    assert out == [b"png", b"png"]
    assert [e[2] for e in seeks] == [0.0, 1.8]
    assert "pauseAnimations" in seeks[0][1]
    assert "setCurrentTime" in seeks[0][1] and "getAnimations" in seeks[0][1]


def test_the_shooter_keeps_the_background_out(fake_playwright):
    """The card surface shows through the figure on both GitHub themes. A page
    background baked into the PNG would arrive as an opaque slab."""
    capture.chrome_shoot("<svg/>", [0.0], 1340, 400)
    assert all(e[1] == {"omit_background": True} for e in fake_playwright if e[0] == "shot")


def test_the_shooter_uses_the_installed_chrome_and_the_master_viewport(fake_playwright):
    """A Playwright pin whose bundled build was never fetched otherwise fails
    hunting for a headless shell that is not on disk."""
    capture.chrome_shoot("<svg/>", [0.0], 1340, 400)
    assert ("launch", {"channel": "chrome"}) in fake_playwright
    assert ("page", {"viewport": {"width": 1340, "height": 400}}) in fake_playwright
    assert ("close",) in fake_playwright


def test_capture_skips_cleanly_when_no_browser_is_installed():
    """`chrome_shoot` imports Playwright inside the call, so importing this
    module on a machine without it must still work — which is what every test
    above already proves. This one states the dependency that is allowed to be
    absent."""
    pytest.importorskip("playwright")
