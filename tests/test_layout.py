"""Tests for the manifest and the row grouping both emitters share."""
import json

import pytest

from tools.profile.sources import store
from tools.profile.transform import layout


def entry(file, width="100%", desc="d", href=None):
    out = {"file": file, "width": width, "desc": desc}
    if href:
        out["href"] = href
    return out


# --- row ------------------------------------------------------------------

@pytest.mark.parametrize("width,expected", [
    (880, "100%"),
    (440, "50%"),
    (280, "31.8182%"),
    (320, "36.3636%"),
])
def test_a_row_states_its_width_as_a_share_of_the_full_width(width, expected):
    assert layout.row("p.svg", "d", width, 880)["width"] == expected


def test_a_row_carries_an_href_only_when_given_one():
    # Absent, not None: readme.py asks with .get() and would anchor on a null.
    assert "href" not in layout.row("p.svg", "d", 880, 880)
    assert layout.row("p.svg", "d", 880, 880, "https://e/1")["href"] == "https://e/1"


def test_a_row_keeps_the_desc_verbatim():
    assert layout.row("p.svg", '5 "starred" & forked', 880, 880)["desc"] == \
        '5 "starred" & forked'


# --- width_of ---------------------------------------------------------------

def test_a_slice_without_a_width_counts_as_full_width():
    assert layout.width_of({"file": "a.svg"}) == 100.0


# --- rows -------------------------------------------------------------------

def test_full_width_slices_get_a_row_each():
    manifest = [entry("a.svg"), entry("b.svg")]
    assert layout.rows(manifest) == [[manifest[0]], [manifest[1]]]


def test_half_width_slices_pair_up():
    manifest = [entry(f"{i}.svg", "50%") for i in range(4)]
    assert [len(row) for row in layout.rows(manifest)] == [2, 2]


def test_eight_halves_become_four_rows_of_two():
    manifest = [entry(f"{i}.svg", "50%") for i in range(8)]
    assert [len(row) for row in layout.rows(manifest)] == [2, 2, 2, 2]


def test_thirds_group_into_one_row():
    manifest = [entry("a.svg", "31.8182%"), entry("b.svg", "36.3636%"),
                entry("c.svg", "31.8182%")]
    assert [len(row) for row in layout.rows(manifest)] == [3]


def test_a_partial_row_is_still_emitted():
    manifest = [entry("a.svg", "50%")]
    assert layout.rows(manifest) == [[manifest[0]]]


def test_full_width_closes_an_open_partial_row():
    manifest = [entry("a.svg", "50%"), entry("b.svg")]
    assert [len(row) for row in layout.rows(manifest)] == [1, 1]


def test_rows_of_empty_manifest():
    assert layout.rows([]) == []


def test_committed_manifest_rows_each_total_full_width():
    """A row whose widths do not sum to 100% wraps and breaks the frame."""
    for row in layout.rows(store.read_manifest()):
        total = sum(layout.width_of(e) for e in row)
        assert total == pytest.approx(100, abs=0.01), [e["file"] for e in row]


# --- same_slices ------------------------------------------------------------

def test_same_slices_compares_files_in_order():
    assert layout.same_slices([entry("a.svg")], [entry("a.svg", "50%")]), \
        "only the file list is paired; geometry is identical by construction"
    assert not layout.same_slices([entry("a.svg")], [entry("b.svg")])
    assert not layout.same_slices([entry("a.svg"), entry("b.svg")], [entry("a.svg")])
    assert not layout.same_slices([entry("a.svg"), entry("b.svg")],
                                  [entry("b.svg"), entry("a.svg")])


def test_the_committed_manifest_parses_as_rows():
    """Guards the file itself, not just the grouping rule."""
    assert json.loads(json.dumps(store.read_manifest()))
