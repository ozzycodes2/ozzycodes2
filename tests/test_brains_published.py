"""Tests for the GIFs under `gists/`, as committed.

Everything else in this suite checks a derivation: a figure re-rendered into
`tmp_path` behind a browser-and-ffmpeg gate, which on a bare clone does not run
at all. These two files are the artifact — what gets pushed to the gists and
what a reader of this repository takes as the record — and they are the only
version-controlled output here rather than something regenerated on demand.
Reading them needs neither Chrome nor ffmpeg, so these run everywhere.
"""
import pytest

from tools.brains import build, encode, figures

PUBLISHED = [(n, build.OUT / f"{build.title(n)}.gif") for n in figures.NAMES]


@pytest.fixture(params=PUBLISHED, ids=[n for n, _ in PUBLISHED])
def published(request):
    name, path = request.param
    if not path.exists():
        pytest.skip(f"{path.name} has not been built")
    return path


def test_the_published_card_is_the_accent_on_transparency(published):
    """The claim the whole design rests on: one painted colour, exactly the
    accent, and GitHub's own surface showing through the rest on both themes."""
    table, transparent = encode.palette(published)
    assert transparent is not None
    assert {c for i, c in enumerate(table) if i != transparent} == {figures.accent_rgb()}


def test_the_published_card_is_the_size_it_was_drawn_at(published):
    assert encode.size(published) == (figures.W, figures.H)


def test_the_published_card_loops_forever(published):
    """A count of 1 plays once and parks on the last frame, which on a pinned
    card is a drawing that moves for three seconds and then stops for good."""
    assert encode.loops(published) == 0


def test_the_published_card_runs_at_the_schedule_the_build_declares(published):
    assert encode.delay(published) == build.DELAY_CS


def test_the_published_card_fits_the_budget(published):
    """Terkel's reference is 117 KB for 48 frames at this size. Camo is not in
    the path for a gist file, so there is no hard cap — but a card that costs
    more than the page around it is a card drawn wrong."""
    assert published.stat().st_size < 200_000, f"{published.stat().st_size} bytes"


def test_both_hemispheres_are_published():
    """Guards the fixture: a skip on both would make every test above vacuous
    and leave the suite green with nothing checked."""
    assert [p.name for _, p in PUBLISHED if p.exists()] == [
        "Left Brain.gif",
        "Right Brain.gif",
    ]
