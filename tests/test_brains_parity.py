"""Tests for the parity check between the vendored SVG and the preview.

Vendoring puts two copies of one drawing in two places, which is the drift
`tools/profile/BACKPORT.md` exists to prevent: a change made in one and not the
other "leaves two renderers disagreeing about one drawing, and nothing will tell
you which is right." Vendoring was chosen anyway, so this is the something that
tells you.
"""
import pathlib

import pytest

from tools.brains import figures, parity


def test_parity_skips_when_the_preview_is_not_on_this_machine(monkeypatch):
    """A clone of this repository alone must run green. `design-preview` is not
    a git repository and lives on one laptop."""
    monkeypatch.setattr(parity, "PREVIEW", pathlib.Path("/nope"))
    assert parity.preview_root() is None


def test_parity_finds_the_preview_when_it_is_there(tmp_path, monkeypatch):
    (tmp_path / "site" / "assets").mkdir(parents=True)
    (tmp_path / "site" / "assets" / "brains.js").touch()
    monkeypatch.setattr(parity, "PREVIEW", tmp_path)
    assert parity.preview_root() == tmp_path


def test_a_directory_without_the_drawing_is_not_the_preview(tmp_path, monkeypatch):
    """Guards against pointing at a directory that merely exists — an empty
    checkout would otherwise be reported as parity-clean."""
    monkeypatch.setattr(parity, "PREVIEW", tmp_path)
    assert parity.preview_root() is None


def test_parity_reports_a_difference_when_the_vendored_copy_drifted():
    report = parity.diff("left-brain", regenerate=lambda _: "<svg/>")
    assert "left-brain" in report
    assert "<svg/>" in report


def test_parity_is_silent_when_they_match():
    assert parity.diff("left-brain", regenerate=figures.load) is None


def test_parity_ignores_the_provenance_comment():
    """The comment carries a generation date, so comparing it would make every
    check fail the day after the file was written."""
    fresh = figures.load("left-brain").split("-->", 1)[1].lstrip()
    assert parity.diff("left-brain", regenerate=lambda _: fresh) is None


def test_parity_skips_rather_than_fails_with_no_preview(monkeypatch):
    monkeypatch.setattr(parity, "PREVIEW", pathlib.Path("/nope"))
    assert parity.diff("left-brain") is None


def test_regenerate_runs_the_preview_renderer(tmp_path):
    """The only test here that shells out to node, and the only one that proves
    the vendored copy still matches what the preview draws today."""
    root = parity.preview_root()
    if root is None:
        pytest.skip("design-preview is not on this machine")
    svg = parity.regenerate("left-brain", root)
    assert f'viewBox="0 0 {figures.W} {figures.H}"' in svg
    assert figures.ACCENT in svg


def test_the_vendored_copy_matches_the_preview():
    """The obligation itself. Skips, never fails, without the preview."""
    report = parity.diff("left-brain")
    assert report is None, report


def test_regenerate_refuses_a_name_the_preview_has_no_side_for(tmp_path):
    with pytest.raises(FileNotFoundError):
        parity.regenerate("middle-brain", tmp_path)
