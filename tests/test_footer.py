"""Tests for the closing slice."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import footer


@pytest.fixture(scope="module")
def markup():
    return footer.render({}, {"stats": {"updated": "2026-10-12"}})


def dim(markup):
    return int(re.search(r'height="(\d+)"', markup).group(1))


def test_it_closes_the_frame(markup):
    """Only the footer draws a bottom edge, so the window reads as one object."""
    height = dim(markup)
    assert f"M{c.MARGIN} {height - c.MARGIN}H{c.FRAME_R}" in markup


def test_it_stays_short(markup):
    assert dim(markup) <= 160
    assert dim(markup) % c.ROW == 0


def test_the_prompt_blinks(markup):
    assert "❯" in markup
    assert 'class="wh cursor"' in markup      # the shared class, so reduced-motion wins


def test_it_credits_the_generator_and_dates_the_run(markup):
    text = c.visible(markup)
    assert "self" in text or "scheduled job" in text
    assert "2026-10-12" in text


def test_desc_repeats_what_is_drawn(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    assert "exit" in desc and "2026-10-12" in desc


@pytest.mark.parametrize("data", [{}, {"stats": {}}, {"stats": None}])
def test_a_missing_timestamp_does_not_print_none(data):
    out = footer.render({}, data)
    assert "None" not in c.visible(out)
    assert "unknown" in c.visible(out)
    assert dim(out) % c.ROW == 0
