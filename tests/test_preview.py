"""Tests for the local page that shows both themes side by side."""
import json
import re

import pytest

from tools.profile import console as c
from tools.profile import preview


def entry(file, width="100%", desc="d", href=None):
    out = {"file": file, "width": width, "desc": desc}
    if href:
        out["href"] = href
    return out


def rows_in(markup):
    """The slice filenames of each `.row`, in order."""
    return [re.findall(r'src="[^"]*/([^"]+)"', row)
            for row in re.findall(r'<div class="row">(.*?)</div>', markup, re.S)]


def sections_in(markup):
    return re.findall(r"<section[^>]*>", markup)


# --- row grouping ----------------------------------------------------------
# preview groups slices exactly the way readme.py does, so a row that reads as
# one window here reads as one window in the README.

def test_two_half_width_slices_share_one_row():
    manifest = [entry("a.svg", "50%"), entry("b.svg", "50%")]
    assert rows_in(preview.column(c.LIGHT, manifest)) == [["a.svg", "b.svg"]]


def test_two_full_width_slices_get_a_row_each():
    manifest = [entry("a.svg"), entry("b.svg")]
    assert rows_in(preview.column(c.LIGHT, manifest)) == [["a.svg"], ["b.svg"]]


def test_thirds_share_one_row():
    manifest = [entry("a.svg", "31.8182%"), entry("b.svg", "36.3636%"),
                entry("c.svg", "31.8182%")]
    assert rows_in(preview.column(c.LIGHT, manifest)) == [["a.svg", "b.svg", "c.svg"]]


def test_a_full_width_slice_closes_an_open_partial_row():
    manifest = [entry("a.svg", "50%"), entry("b.svg")]
    assert rows_in(preview.column(c.LIGHT, manifest)) == [["a.svg"], ["b.svg"]]


def test_a_partial_row_is_still_drawn():
    assert rows_in(preview.column(c.LIGHT, [entry("a.svg", "50%")])) == [["a.svg"]]


def test_eight_halves_become_four_rows_of_two():
    manifest = [entry(f"{i}.svg", "50%") for i in range(8)]
    assert [len(row) for row in rows_in(preview.column(c.LIGHT, manifest))] == [2, 2, 2, 2]


def test_a_slice_without_a_width_is_treated_as_full_width():
    manifest = [{"file": "a.svg", "desc": "d"}, {"file": "b.svg", "desc": "d"}]
    assert rows_in(preview.column(c.LIGHT, manifest)) == [["a.svg"], ["b.svg"]]


def test_an_empty_manifest_draws_no_rows():
    out = preview.column(c.LIGHT, [])
    assert rows_in(out) == []
    assert out.startswith("<section")


# --- one theme's column ----------------------------------------------------

def test_a_column_paints_its_own_themes_canvas_and_ink():
    out = preview.column(c.DARK, [entry("a.svg")])
    assert f"background:{c.DARK.canvas}" in out and f"color:{c.DARK.ink}" in out
    assert c.LIGHT.canvas not in out


def test_a_column_names_the_theme_it_shows():
    assert f">{c.DARK.name}</h2>" in preview.column(c.DARK, [entry("a.svg")])


def test_a_column_rules_its_heading_in_the_themes_hairline():
    assert f"border-color:{c.LIGHT.hairline}" in preview.column(c.LIGHT, [entry("a.svg")])


def test_a_column_references_the_slices_under_its_own_theme_directory():
    out = preview.column(c.DARK, [entry("links/mail.svg")])
    assert 'src="./dark/links/mail.svg"' in out
    assert "light/" not in out


def test_a_column_sizes_each_slice_by_its_manifest_width():
    out = preview.column(c.LIGHT, [entry("a.svg", "50%"), entry("b.svg", "50%")])
    assert out.count("style=\"width:50%\"") == 2


def test_a_column_references_the_svgs_rather_than_inlining_them():
    """A reload has to pick up a re-render without rebuilding the page."""
    out = preview.column(c.LIGHT, [entry("a.svg")])
    assert "<img" in out and "<svg" not in out


def test_the_slices_of_a_row_butt_together_with_nothing_between_them():
    """Whitespace between two halves is a text node that wraps the row."""
    out = preview.column(c.LIGHT, [entry("a.svg", "50%"), entry("b.svg", "50%")])
    row = re.search(r'<div class="row">(.*?)</div>', out, re.S).group(1)
    assert "> <" not in row and ">\n<" not in row


# --- the whole page --------------------------------------------------------

@pytest.fixture(scope="module")
def manifest():
    return [entry("a.svg", "50%"), entry("b.svg", "50%"), entry("c.svg")]


def test_the_page_gives_every_theme_a_column(manifest):
    out = preview.page(manifest)
    assert len(sections_in(out)) == len(c.THEMES)
    assert f"repeat({len(c.THEMES)}, 1fr)" in out


def test_the_page_shows_every_slice_once_per_theme(manifest):
    out = preview.page(manifest)
    for theme in c.THEMES:
        assert [f for f in re.findall(rf'src="\./{theme.name}/([^"]+)"', out)] == \
            [e["file"] for e in manifest]


def test_the_page_keeps_the_columns_in_theme_order(manifest):
    out = preview.page(manifest)
    assert [out.index(f">{t.name}</h2>") for t in c.THEMES] == \
        sorted(out.index(f">{t.name}</h2>") for t in c.THEMES)


def test_the_page_is_a_standalone_document(manifest):
    out = preview.page(manifest)
    assert out.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in out
    assert "<title>" in out


# --- main ------------------------------------------------------------------

@pytest.fixture
def out(tmp_path, monkeypatch):
    """Write the page into tmp_path, and read the manifest from there too."""
    monkeypatch.setattr(preview, "OUT", tmp_path / "assets" / "preview.html")
    monkeypatch.setattr(preview.c, "DATA", tmp_path)
    monkeypatch.setattr(preview.c, "ROOT", tmp_path)
    (tmp_path / "assets").mkdir()
    return tmp_path / "assets" / "preview.html"


def test_main_writes_the_page_beside_the_slices(out, tmp_path, capsys):
    (tmp_path / "manifest.json").write_text(json.dumps([entry("a.svg")]))
    preview.main()
    assert 'src="./light/a.svg"' in out.read_text()
    assert "preview.html" in capsys.readouterr().out


def test_main_overwrites_a_stale_page(out, tmp_path):
    out.write_text("stale")
    (tmp_path / "manifest.json").write_text(json.dumps([entry("a.svg")]))
    preview.main()
    assert "stale" not in out.read_text()


def test_main_exits_without_a_manifest(out):
    with pytest.raises(SystemExit, match="render.py"):
        preview.main()


def test_main_writes_nothing_without_a_manifest(out):
    with pytest.raises(SystemExit):
        preview.main()
    assert not out.exists()
