"""Tests for the README rewriter and the render orchestrator's manifest."""
import json
import re

import pytest

from tools.profile import console as c
from tools.profile import readme, render


def entry(file, width="100%", desc="d", href=None):
    out = {"file": file, "width": width, "desc": desc}
    if href:
        out["href"] = href
    return out


# --- row grouping ----------------------------------------------------------

def test_full_width_slices_get_a_row_each():
    manifest = [entry("a.svg"), entry("b.svg")]
    assert readme.rows(manifest) == [[manifest[0]], [manifest[1]]]


def test_half_width_slices_pair_up():
    manifest = [entry(f"{i}.svg", "50%") for i in range(4)]
    assert [len(row) for row in readme.rows(manifest)] == [2, 2]


def test_thirds_group_into_one_row():
    manifest = [entry("a.svg", "31.8182%"), entry("b.svg", "36.3636%"),
                entry("c.svg", "31.8182%")]
    assert [len(row) for row in readme.rows(manifest)] == [3]


def test_a_partial_row_is_still_emitted():
    manifest = [entry("a.svg", "50%")]
    assert readme.rows(manifest) == [[manifest[0]]]


def test_full_width_closes_an_open_partial_row():
    manifest = [entry("a.svg", "50%"), entry("b.svg")]
    assert [len(row) for row in readme.rows(manifest)] == [1, 1]


def test_rows_of_empty_manifest():
    assert readme.rows([]) == []


# --- img markup ------------------------------------------------------------

def test_img_without_href_is_a_bare_tag():
    out = readme.img(entry("a.svg"))
    assert out.startswith("<img") and "<a " not in out


def test_img_with_href_is_wrapped_in_an_anchor():
    out = readme.img(entry("a.svg", href="https://example.com/x"))
    assert out.startswith('<a href="https://example.com/x">')
    assert out.endswith("</a>")


def test_img_escapes_quotes_in_the_description():
    out = readme.img(entry("a.svg", desc='He said "hi" & left'))
    assert "&quot;hi&quot;" in out and "&amp;" in out
    # A raw quote inside alt="" would terminate the attribute early.
    assert re.fullmatch(r'<img src="[^"]*" width="[^"]*" align="top" alt="[^"]*">', out)


def test_img_points_into_the_assets_directory():
    assert 'src="./assets/links/mail.svg"' in readme.img(entry("links/mail.svg"))


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


# --- main ------------------------------------------------------------------

def readme_with_markers(tmp_path, body=""):
    path = tmp_path / "README.md"
    path.write_text(f"above\n{readme.START}{body}{readme.END}\nbelow\n")
    return path


def test_main_replaces_only_the_marked_block(tmp_path, monkeypatch, capsys):
    path = readme_with_markers(tmp_path, "\nstale\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([entry("a.svg")]))
    monkeypatch.setattr(readme, "README", path)
    monkeypatch.setattr(readme, "MANIFEST", manifest)

    readme.main()
    out = path.read_text()
    assert out.startswith("above\n") and out.endswith("below\n")
    assert "stale" not in out
    assert "a.svg" in out
    assert "1 slices" in capsys.readouterr().out


def test_main_is_idempotent(tmp_path, monkeypatch):
    path = readme_with_markers(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([entry("a.svg"), entry("b.svg", "50%")]))
    monkeypatch.setattr(readme, "README", path)
    monkeypatch.setattr(readme, "MANIFEST", manifest)

    readme.main()
    once = path.read_text()
    readme.main()
    assert path.read_text() == once


def test_main_exits_without_a_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(readme, "MANIFEST", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="render.py"):
        readme.main()


@pytest.mark.parametrize("body", ["no markers at all", readme.START, readme.END])
def test_main_exits_on_a_readme_missing_a_marker(tmp_path, monkeypatch, body):
    path = tmp_path / "README.md"
    path.write_text(body)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("[]")
    monkeypatch.setattr(readme, "README", path)
    monkeypatch.setattr(readme, "MANIFEST", manifest)
    with pytest.raises(SystemExit, match="marker"):
        readme.main()


# --- render orchestration --------------------------------------------------

def test_slices_of_wraps_bare_markup_under_the_registered_name():
    assert render.slices_of("x.svg", "<svg/>") == [c.Slice("x.svg", "<svg/>")]


def test_slices_of_accepts_a_filename_mapping():
    out = render.slices_of("x.svg", {"a.svg": "<svg/>", "b.svg": "<svg/>"})
    assert [s.file for s in out] == ["a.svg", "b.svg"]
    assert all(s.href is None for s in out)


def test_slices_of_preserves_hrefs():
    given = [c.Slice("a.svg", "<svg/>", "https://e/1")]
    assert render.slices_of("x.svg", given) == given


def test_slices_of_accepts_plain_tuples():
    out = render.slices_of("x.svg", [("a.svg", "<svg/>", "https://e/1")])
    assert out[0].href == "https://e/1"


def test_render_main_writes_every_slice_and_the_manifest(tmp_path, monkeypatch):
    class Panel:
        @staticmethod
        def render(_cfg, _data):
            return [c.Slice("one.svg", c.slice_svg(
                40, "", title="One", desc="first half", width=c.W // 2, rails="left"),
                "https://example.com/1"),
                c.Slice("two.svg", c.slice_svg(
                    40, "", title="Two", desc="second half", width=c.W // 2, rails="right"))]

    monkeypatch.setattr(render.c, "OUT", tmp_path / "assets")
    monkeypatch.setattr(render, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(render, "PANELS", [("p.svg", Panel)])
    monkeypatch.setattr(render, "load_config", lambda: {})
    monkeypatch.setattr(render, "load_data", lambda: {})

    render.main()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [m["file"] for m in manifest] == ["one.svg", "two.svg"]
    assert [m["width"] for m in manifest] == ["50%", "50%"]
    assert manifest[0]["href"] == "https://example.com/1"
    assert "href" not in manifest[1]
    assert manifest[0]["desc"] == "first half"
    assert (tmp_path / "assets/one.svg").exists()


def test_committed_manifest_rows_each_total_full_width():
    """A row whose widths do not sum to 100% wraps and breaks the frame."""
    manifest = json.loads((c.DATA / "manifest.json").read_text())
    for row in readme.rows(manifest):
        total = sum(float(e["width"].rstrip("%")) for e in row)
        assert total == pytest.approx(100, abs=0.01), [e["file"] for e in row]


# --- describe --------------------------------------------------------------

def test_describe_reads_back_desc_and_width():
    svg = c.slice_svg(40, "", title="T", desc="the real numbers", width=440, rails="left")
    assert c.describe(svg) == ("the real numbers", 440.0)


def test_describe_unescapes_entities():
    svg = c.slice_svg(40, "", title="T", desc='a "quoted" & escaped desc')
    assert c.describe(svg)[0] == 'a "quoted" & escaped desc'


def test_describe_defaults_width_when_absent():
    assert c.describe("<svg></svg>") == ("", c.W)
