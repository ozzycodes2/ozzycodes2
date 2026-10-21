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
    return name, path


def test_the_published_card_is_the_drawings_own_shades_on_transparency(published):
    """The claim the whole design rests on: one hue, at the shades the drawing
    names and no others, with GitHub's own surface showing through the rest on
    both themes. A file short of any shade has published the figure with its
    motion flattened, which nothing else here would catch."""
    name, path = published
    table, transparent = encode.palette(path)
    assert transparent is not None
    visible = {c for i, c in enumerate(table) if i != transparent} - {(0, 0, 0)}
    assert visible == set(figures.paints(name))
    assert figures.accent_rgb() in visible


def test_the_published_card_is_the_size_it_was_drawn_at(published):
    assert encode.size(published[1]) == (figures.W, figures.H)


def test_the_published_card_loops_forever(published):
    """A count of 1 plays once and parks on the last frame, which on a pinned
    card is a drawing that moves for three seconds and then stops for good."""
    assert encode.loops(published[1]) == 0


def test_the_published_card_runs_at_the_schedule_the_build_declares(published):
    assert encode.delay(published[1]) == build.DELAY_CS


def test_the_published_card_fits_the_budget(published):
    """A card that costs more than the page around it is a card drawn wrong.
    `build.BUDGET` carries the number and the reasoning."""
    size = published[1].stat().st_size
    assert size < build.BUDGET, f"{size} bytes"


def test_both_hemispheres_are_published():
    """Guards the fixture: a skip on both would make every test above vacuous
    and leave the suite green with nothing checked."""
    assert [p.name for _, p in PUBLISHED if p.exists()] == [
        "Left Brain.gif",
        "Right Brain.gif",
    ]
