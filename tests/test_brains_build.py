"""Tests for the build entrypoint."""
import pathlib
import shutil

import pytest

from tools.brains import build, encode, figures

needs_browser = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or build.playwright_missing() or build.chrome_missing(),
    reason="needs ffmpeg, Playwright and Google Chrome",
)


def test_the_gist_filename_matches_the_description_the_card_shows():
    """The card heading is the gist's *description*, not its filename — the
    filename appears nowhere on the card and only has to keep a raster
    extension for the image to render at all. Keeping the two the same is what
    makes the published file identifiable from the card, so the spaces and the
    capitals are still load-bearing."""
    assert build.title("left-brain") == "Left Brain"
    assert build.title("right-brain") == "Right Brain"


def test_it_builds_every_vendored_hemisphere_by_default(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(build, "OUT", tmp_path)
    monkeypatch.setattr(build, "render", lambda name, out, **kw: (made.append((name, out)), out.touch()))
    assert build.main([]) == 0
    assert made == [
        ("left-brain", tmp_path / "Left Brain.gif"),
        ("right-brain", tmp_path / "Right Brain.gif"),
    ]


def test_it_builds_only_what_it_is_asked_for(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(build, "OUT", tmp_path)
    monkeypatch.setattr(build, "render", lambda name, out, **kw: (made.append(name), out.touch()))
    assert build.main(["left-brain"]) == 0
    assert made == ["left-brain"]


def test_a_hemisphere_that_is_not_vendored_is_an_error(monkeypatch, tmp_path):
    """Asking for a half that has not been drawn should say so, not capture four
    seconds of nothing. Both are vendored now, so this points `figures` at an
    empty directory to reach the case."""
    monkeypatch.setattr(build, "OUT", tmp_path)
    monkeypatch.setattr(figures, "HERE", tmp_path / "empty")
    assert build.main(["right-brain"]) == 1


def test_a_name_that_is_not_a_hemisphere_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "OUT", tmp_path)
    assert build.main(["middle-brain"]) == 1


def test_it_writes_nothing_under_assets(monkeypatch, tmp_path):
    """`update-profile.yml` runs `git add assets`, so anything this left there
    would be committed on every scheduled refresh — and these are published as
    gists, never as repository assets."""
    assert build.OUT == build.ROOT / "gists"
    assert "assets" not in build.OUT.parts


def test_the_frame_schedule_divides_the_loop_exactly(monkeypatch, tmp_path):
    """Only 1, 2, 4, 5, 10, 20, 25, 50 and 100 fps come out exact. Anything
    else is rounded by the player and the loop drifts against itself."""
    assert build.FRAMES * build.DELAY_CS == round(build.DURATION * 100)
    assert 100 % build.DELAY_CS == 0


@pytest.mark.parametrize("name", figures.NAMES)
def test_the_loop_is_the_one_the_drawing_declares(name):
    """The capture duration has to be the figure's own loop, or the GIF cuts
    the animation off mid-cycle and the seam shows once per repeat. Both halves
    run on one clock: side by side, two periods would beat against each other."""
    import re

    svg = figures.load(name)
    declared = max(float(d) for d in re.findall(r"animation:[^;}]*?(\d+(?:\.\d+)?)s", svg))
    assert build.DURATION == declared


@needs_browser
@pytest.mark.parametrize("name", figures.NAMES)
def test_the_built_card_is_the_drawings_own_shades_on_transparency(tmp_path, name):
    """The assertion `test_brains_encode.py` cannot make: that the colours this
    drawing paints are the colours that reach the file, and that GitHub's own
    surface shows through the rest on both themes.

    Every shade matters. The signal's trail decays through them, so a palette
    that lost one would publish the figure with its motion flattened and
    nothing anywhere would report it."""
    out = tmp_path / f"{build.title(name)}.gif"
    build.render(name, out)
    table, transparent = encode.palette(out)
    assert transparent is not None
    visible = {c for i, c in enumerate(table) if i != transparent} - {(0, 0, 0)}
    assert visible == set(figures.paints(name))
    assert figures.accent_rgb() in visible
    assert encode.size(out) == (figures.W, figures.H)
    assert encode.loops(out) == 0


@needs_browser
@pytest.mark.parametrize("name", figures.NAMES)
def test_the_built_card_fits_the_budget(tmp_path, name):
    """Terkel's reference is 117 KB for 48 frames at this size. Camo is not in
    the path for a gist file, so there is no hard cap — but a card that costs
    more than the page around it is a card drawn wrong."""
    out = tmp_path / f"{build.title(name)}.gif"
    build.render(name, out)
    assert out.stat().st_size < 200_000, f"{out.stat().st_size} bytes"


def test_build_reports_parity_drift_without_blocking_on_it(monkeypatch, tmp_path, capsys):
    """A drifted vendored copy is worth saying out loud, but the build still
    produces the file it was asked for — the check is a warning, not a gate, or
    a laptop without the preview could never build at all."""
    monkeypatch.setattr(build, "OUT", tmp_path)
    monkeypatch.setattr(build, "render", lambda name, out, **kw: out.touch())
    monkeypatch.setattr(build.parity, "diff", lambda name: f"{name} drifted")
    assert build.main(["left-brain"]) == 0
    assert "drifted" in capsys.readouterr().out


def test_the_output_directory_is_made_if_it_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "OUT", tmp_path / "gists")
    monkeypatch.setattr(build, "render", lambda name, out, **kw: out.touch())
    assert build.main(["left-brain"]) == 0
    assert (tmp_path / "gists").is_dir()


def test_playwright_missing_answers_without_importing_a_browser():
    assert isinstance(build.playwright_missing(), bool)


def test_render_passes_the_schedule_through(monkeypatch, tmp_path):
    seen = {}

    def fake_frames(svg, *, count, duration, shoot=None):
        seen.update(count=count, duration=duration)
        return [b"png"] * count

    monkeypatch.setattr(build.capture, "frames", fake_frames)
    monkeypatch.setattr(build.encode, "gif", lambda frames, out, **kw: seen.update(kw, n=len(frames)))
    build.render("left-brain", tmp_path / "x.gif")
    assert seen["count"] == build.FRAMES
    assert seen["duration"] == build.DURATION
    assert seen["delay_cs"] == build.DELAY_CS
    assert seen["n"] == build.FRAMES


def test_root_is_the_repository(monkeypatch):
    assert (build.ROOT / "tools" / "brains" / "figures.py").exists()
    assert isinstance(build.ROOT, pathlib.Path)
