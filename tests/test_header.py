"""Tests for the top slice."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import header

CFG = {"identity": {
    "name": "Osniel Quintana",
    "handle": "ozzycodes2",
    "role": "platform engineer",
    "tagline": ["first line", "second line", "third line"],
}}


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def test_header_is_the_slice_that_closes_the_top():
    """Only this panel draws the top edge; the rest continue the rails."""
    svg = header.render(CFG, {})
    assert f"M{c.FRAME_L} {c.MARGIN}H{c.FRAME_R}" in svg


def test_header_draws_the_window_title_bar():
    assert "ozzycodes2 — zsh" in header.render(CFG, {})


def test_header_height_is_on_the_grid():
    assert height_of(header.render(CFG, {})) % c.ROW == 0


def test_header_grows_with_the_tagline():
    short = dict(identity={**CFG["identity"], "tagline": ["one"]})
    long = dict(identity={**CFG["identity"], "tagline": ["one"] * 6})
    assert height_of(header.render(long, {})) > height_of(header.render(short, {}))


def test_header_renders_every_tagline_line():
    svg = header.render(CFG, {})
    for line in CFG["identity"]["tagline"]:
        assert line in svg


def test_header_description_carries_name_role_and_tagline():
    desc = desc_of(header.render(CFG, {}))
    assert "Osniel Quintana" in desc
    assert "platform engineer" in desc
    assert "third line" in desc


def test_header_escapes_markup_in_the_name():
    cfg = {"identity": {**CFG["identity"], "name": 'A <b>& "B"'}}
    svg = header.render(cfg, {})
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_header_with_an_empty_tagline():
    cfg = {"identity": {**CFG["identity"], "tagline": []}}
    svg = header.render(cfg, {})
    assert height_of(svg) % c.ROW == 0


def test_header_is_deterministic():
    assert header.render(CFG, {}) == header.render(CFG, {})


def test_header_ignores_fetched_data():
    """The headline is hand-written; nothing in data/ should reach it."""
    assert header.render(CFG, {}) == header.render(CFG, {"stats": {"followers": 9000}})


def test_header_blinks_a_cursor_via_the_shared_class():
    """Inline animation shorthand would escape the reduced-motion override."""
    svg = header.render(CFG, {})
    assert 'class="wh cursor"' in svg
    assert "prefers-reduced-motion" in svg
