"""Tests for the README block: the markup, the splice, and readme.py's wiring."""
import json
import re

import pytest

from tools.profile import readme as entrypoint
from tools.profile.present import readme
from tools.profile.sources import assets, store


def entry(file, width="100%", desc="d", href=None):
    out = {"file": file, "width": width, "desc": desc}
    if href:
        out["href"] = href
    return out


# --- img markup ------------------------------------------------------------

def test_img_without_href_is_a_bare_picture():
    out = readme.img(entry("a.svg"))
    assert out.startswith("<picture>") and out.endswith("</picture>")
    assert "<a " not in out


def test_img_with_href_wraps_the_whole_picture_in_an_anchor():
    """An SVG sits inside one anchor, so the link has to contain both themes."""
    out = readme.img(entry("a.svg", href="https://example.com/x"))
    assert out.startswith('<a href="https://example.com/x"><picture>')
    assert out.endswith("</picture></a>")


def test_img_offers_a_dark_source_before_the_light_fallback():
    """GitHub honours prefers-color-scheme on a <source>; <img> covers the rest."""
    out = readme.img(entry("a.svg"))
    assert '<source media="(prefers-color-scheme: dark)" ' \
           'srcset="./assets/dark/a.svg">' in out
    assert out.index("<source") < out.index("<img")
    assert 'src="./assets/light/a.svg"' in out


def test_img_keeps_the_width_and_the_top_alignment_on_the_img():
    """The <img> is the element that is laid out, so the row aligns on it."""
    out = readme.img(entry("a.svg", "50%"))
    assert re.search(r'<img src="[^"]*" width="50%" align="top" alt="[^"]*">', out)
    assert "align" not in out.split("<img")[0]


def test_img_treats_a_slice_with_no_width_as_full_width():
    assert 'width="100%"' in readme.img({"file": "a.svg", "desc": "d"})


def test_img_escapes_quotes_in_the_description():
    out = readme.img(entry("a.svg", desc='He said "hi" & left'))
    assert "&quot;hi&quot;" in out and "&amp;" in out
    # A raw quote inside alt="" would terminate the attribute early.
    assert re.fullmatch(
        r'<picture><source media="[^"]*" srcset="[^"]*">'
        r'<img src="[^"]*" width="[^"]*" align="top" alt="[^"]*"></picture>', out)


def test_img_escapes_quotes_in_an_href():
    out = readme.img(entry("a.svg", href='https://e/"onload='))
    assert '"onload=' not in out and "&quot;onload=" in out


def test_img_points_into_both_themed_asset_directories():
    out = readme.img(entry("links/mail.svg"))
    assert 'srcset="./assets/dark/links/mail.svg"' in out
    assert 'src="./assets/light/links/mail.svg"' in out


# --- the generated block ---------------------------------------------------

def test_block_is_delimited_by_the_markers():
    out = readme.block([entry("a.svg")])
    assert out.startswith(readme.START) and out.endswith(readme.END)


def test_tiled_slices_share_a_line_with_no_whitespace_between():
    """Whitespace between two 50% images is a text node that wraps the row."""
    out = readme.block([entry("a.svg", "50%"), entry("b.svg", "50%")])
    row = [ln for ln in out.splitlines() if "a.svg" in ln][0]
    assert "b.svg" in row, "both halves must be on one line"
    assert "> <" not in row and ">\n<" not in row


def test_the_console_is_flush_with_the_left_of_the_column():
    """Centring aligned nothing — every slice is width="100%" — but it decided
    where the rounding slack went on the one row that is two 50% halves: half a
    pixel on the left, which puts that row's rail inside the rail above it."""
    out = readme.block([entry("a.svg")])
    assert "<p>" in out
    assert "align=\"center\"" not in out


# --- splice ----------------------------------------------------------------

def test_splice_replaces_only_the_marked_block():
    text = f"above\n{readme.START}\nstale\n{readme.END}\nbelow\n"
    out = readme.splice(text, "NEW")
    assert out == "above\nNEW\nbelow\n"


@pytest.mark.parametrize("text", ["no markers at all", readme.START, readme.END])
def test_splice_names_the_marker_it_could_not_find(text):
    with pytest.raises(ValueError, match="marker"):
        readme.splice(text, "NEW")


# --- main ------------------------------------------------------------------

@pytest.fixture
def wired(tmp_path, monkeypatch):
    """A README with markers and a manifest, both under tmp_path."""
    path = tmp_path / "README.md"
    path.write_text(f"above\n{readme.START}\nstale\n{readme.END}\nbelow\n")
    monkeypatch.setattr(assets, "README", path)
    monkeypatch.setattr(store, "DATA", tmp_path)
    return path


def write_manifest(tmp_path, manifest):
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))


def test_main_replaces_only_the_marked_block(wired, tmp_path, capsys):
    write_manifest(tmp_path, [entry("a.svg")])
    entrypoint.main()
    out = wired.read_text()
    assert out.startswith("above\n") and out.endswith("below\n")
    assert "stale" not in out
    assert "a.svg" in out
    assert "1 slices" in capsys.readouterr().out


def test_main_is_idempotent(wired, tmp_path):
    write_manifest(tmp_path, [entry("a.svg"), entry("b.svg", "50%")])
    entrypoint.main()
    once = wired.read_text()
    entrypoint.main()
    assert wired.read_text() == once


def test_main_exits_without_a_manifest(wired, tmp_path):
    with pytest.raises(SystemExit, match="render.py"):
        entrypoint.main()


def test_main_exits_on_a_readme_missing_a_marker(wired, tmp_path):
    wired.write_text("no markers at all")
    write_manifest(tmp_path, [])
    with pytest.raises(SystemExit, match="marker"):
        entrypoint.main()


def test_main_leaves_a_markerless_readme_untouched(wired, tmp_path):
    wired.write_text("no markers at all")
    write_manifest(tmp_path, [entry("a.svg")])
    with pytest.raises(SystemExit):
        entrypoint.main()
    assert wired.read_text() == "no markers at all"
