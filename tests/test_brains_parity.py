"""Tests for the parity check between the vendored SVG and the preview.

Vendoring puts two copies of one drawing in two places, which is the drift
`tools/profile/BACKPORT.md` exists to prevent: a change made in one and not the
other "leaves two renderers disagreeing about one drawing, and nothing will tell
you which is right." Vendoring was chosen anyway, so this is the something that
tells you.
"""
import datetime
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


@pytest.mark.parametrize("name", figures.NAMES)
def test_the_vendored_copy_matches_the_preview(name):
    """The obligation itself. Skips, never fails, without the preview.

    Parametrised because a drift alarm wired to one of two drawings is an alarm
    that stays green while the other one rots — and `build.py` deliberately
    downgrades drift to a warning, so this is the only gate.
    """
    if not figures.path(name).exists():
        pytest.skip(f"{name} is not vendored")
    report = parity.diff(name)
    assert report is None, report


def test_regenerate_refuses_a_name_the_preview_has_no_side_for(tmp_path):
    with pytest.raises(FileNotFoundError):
        parity.regenerate("middle-brain", tmp_path)


@pytest.fixture
def elsewhere(tmp_path, monkeypatch):
    """Point `figures.path` at a scratch directory so vendoring under test can
    never overwrite the real drawings."""
    monkeypatch.setattr(figures, "HERE", tmp_path)
    return tmp_path


def test_vendor_writes_a_copy_parity_then_accepts(elsewhere):
    """The round trip is the point: whatever `vendor` writes, `diff` must find
    nothing to say about."""
    parity.vendor("left-brain", regenerate=lambda _: "<svg>body</svg>")
    assert (elsewhere / "left-brain.svg").exists()
    assert parity.diff("left-brain", regenerate=lambda _: "<svg>body</svg>") is None


def test_vendor_states_its_provenance(elsewhere):
    """A generated file that does not say where it came from is a file someone
    will edit by hand."""
    parity.vendor("left-brain", regenerate=lambda _: "<svg/>", today=datetime.date(2026, 10, 19))
    found = figures.provenance("left-brain")
    assert found["source"] == "site/assets/brains.js"
    assert found["generated"] == "2026-10-19"


def test_vendor_names_the_command_that_regenerates_it(elsewhere):
    """`build.py` builds GIFs; it has never written an SVG. A header that sends
    the reader to the wrong command is worse than one that sends them nowhere."""
    parity.vendor("right-brain", regenerate=lambda _: "<svg/>")
    head = figures.load("right-brain").split("-->", 1)[0]
    assert "tools.brains.parity --write right-brain" in head


def test_vendor_refuses_a_name_that_is_not_a_hemisphere(elsewhere):
    with pytest.raises(FileNotFoundError):
        parity.vendor("middle-brain", regenerate=lambda _: "<svg/>")


def test_vendor_without_the_preview_is_an_error(elsewhere, monkeypatch):
    """`diff` skips when the preview is absent, because a clone of this
    repository alone must run green. Vendoring cannot skip: there is nothing to
    copy from, and a silent no-op would leave the old drawing in place."""
    monkeypatch.setattr(parity, "PREVIEW", pathlib.Path("/nope"))
    with pytest.raises(FileNotFoundError, match="brains.js"):
        parity.vendor("left-brain")


def test_the_cli_is_silent_and_clean_when_the_copies_match(elsewhere, capsys):
    parity.vendor("left-brain", regenerate=lambda _: "<svg/>")
    assert parity.main([], regenerate=lambda _: "<svg/>") == 0
    assert capsys.readouterr().out == ""


def test_the_cli_reports_drift_and_fails(elsewhere, capsys):
    parity.vendor("left-brain", regenerate=lambda _: "<svg/>")
    assert parity.main([], regenerate=lambda _: "<svg>moved</svg>") == 1
    assert "moved" in capsys.readouterr().out


def test_the_cli_skips_a_hemisphere_that_is_not_vendored_yet(elsewhere):
    assert parity.main([], regenerate=lambda _: "<svg/>") == 0


def test_the_cli_says_so_when_it_could_not_check(elsewhere, monkeypatch, capsys):
    """Printing nothing would read as "checked, clean". It checked nothing."""
    parity.vendor("left-brain", regenerate=lambda _: "<svg/>")
    monkeypatch.setattr(parity, "PREVIEW", pathlib.Path("/nope"))
    assert parity.main([]) == 0
    assert "design-preview" in capsys.readouterr().out


def test_the_cli_writes_when_asked(elsewhere, capsys):
    assert parity.main(["--write", "right-brain"], regenerate=lambda _: "<svg/>") == 0
    assert "<svg/>" in figures.load("right-brain")
    assert "wrote" in capsys.readouterr().out
