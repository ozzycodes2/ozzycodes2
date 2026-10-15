"""Tests for render.py's wiring: every theme written, one manifest, no mismatch."""
import json
import types

import pytest

from tools.profile import render
from tools.profile.present import console as c
from tools.profile.sources import assets, store


def svg(desc="a description", width=c.W):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="40">'
            f'<desc id="d">{c.e(desc)}</desc></svg>')


def panel(result):
    def render_(_cfg, _data, theme):
        return result(theme) if callable(result) else result
    return types.SimpleNamespace(render=render_)


def files_under(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


@pytest.fixture
def out(tmp_path, monkeypatch):
    """Point every write at tmp_path, so the real assets/ and data/ are safe."""
    monkeypatch.setattr(assets, "OUT", tmp_path / "assets")
    monkeypatch.setattr(store, "DATA", tmp_path / "data")
    monkeypatch.setattr(render.config, "build", lambda *a: {})
    monkeypatch.setattr(render.store, "read_all", lambda: {})
    return tmp_path / "assets"


def manifest_in(tmp_path):
    return json.loads((tmp_path / "data" / "manifest.json").read_text())


def use(monkeypatch, panels):
    monkeypatch.setattr(render.slices, "PANELS", panels)


def test_main_renders_every_theme_into_its_own_directory(out, monkeypatch):
    use(monkeypatch, [("p.svg", panel(svg()))])
    render.main()
    assert files_under(out) == sorted(f"{t.name}/p.svg" for t in c.THEMES)


def test_main_writes_the_markup_the_panel_returned(out, monkeypatch):
    markup = svg("the real one")
    use(monkeypatch, [("p.svg", panel(markup))])
    render.main()
    assert (out / "light/p.svg").read_text() == markup


def test_main_writes_a_slice_that_names_a_subdirectory(out, monkeypatch):
    use(monkeypatch, [("p.svg", panel({"links/mail.svg": svg()}))])
    render.main()
    assert files_under(out) == sorted(f"{t.name}/links/mail.svg" for t in c.THEMES)


def test_main_writes_one_manifest_row_per_slice_not_per_theme(
        out, monkeypatch, tmp_path):
    use(monkeypatch, [("p.svg", panel({"a.svg": svg(), "b.svg": svg()})),
                      ("q.svg", panel(svg()))])
    render.main()
    assert [m["file"] for m in manifest_in(tmp_path)] == ["a.svg", "b.svg", "q.svg"]


def test_main_keeps_the_first_themes_rows(out, monkeypatch, tmp_path):
    """The two themes are identical in geometry and alt text by construction."""
    use(monkeypatch, [("p.svg", panel(lambda t: svg(f"drawn for {t.name}")))])
    render.main()
    assert [m["desc"] for m in manifest_in(tmp_path)] == \
        [f"drawn for {c.THEMES[0].name}"]


def test_main_gives_each_theme_its_own_rendering_of_the_same_file(out, monkeypatch):
    """Same filename in both directories, but each drawn for its own palette."""
    use(monkeypatch, [("p.svg", panel(lambda t: svg(f"drawn for {t.name}")))])
    render.main()
    for theme in c.THEMES:
        assert f"drawn for {theme.name}" in (out / theme.name / "p.svg").read_text()


def test_main_exits_when_a_later_theme_produces_a_different_slice_list(
        out, monkeypatch):
    """Mismatched lists would pair the wrong two images inside one <picture>."""
    use(monkeypatch, [("p.svg", panel(
        lambda t: svg() if t is c.THEMES[0] else {"other.svg": svg()}))])
    with pytest.raises(SystemExit, match=c.THEMES[1].name):
        render.main()


def test_main_exits_when_a_later_theme_produces_fewer_slices(out, monkeypatch):
    use(monkeypatch, [("p.svg", panel(
        lambda t: {"a.svg": svg(), "b.svg": svg()} if t is c.THEMES[0]
        else {"a.svg": svg()}))])
    with pytest.raises(SystemExit, match="different slice list"):
        render.main()


def test_main_does_not_write_a_manifest_it_could_not_trust(
        out, monkeypatch, tmp_path):
    use(monkeypatch, [("p.svg", panel(
        lambda t: svg() if t is c.THEMES[0] else {"other.svg": svg()}))])
    with pytest.raises(SystemExit):
        render.main()
    assert not (tmp_path / "data" / "manifest.json").exists()


def test_main_names_each_file_it_wrote(out, monkeypatch, capsys):
    use(monkeypatch, [("p.svg", panel(svg()))])
    render.main()
    printed = capsys.readouterr().out
    assert "wrote assets/dark/p.svg" in printed
    assert "wrote assets/light/p.svg" in printed


def test_main_counts_slices_and_themes_separately(out, monkeypatch, capsys):
    use(monkeypatch, [("p.svg", panel({"a.svg": svg(), "b.svg": svg()}))])
    render.main()
    assert f"2 slices × {len(c.THEMES)} themes" in capsys.readouterr().out


def test_main_hands_the_panels_the_assembled_config(monkeypatch, tmp_path):
    """render.py reads four files; the panels see one mapping, and no path."""
    monkeypatch.setattr(assets, "OUT", tmp_path / "assets")
    monkeypatch.setattr(store, "DATA", tmp_path / "data")
    seen = {}

    def render_(cfg, data, theme):
        seen.update(cfg=cfg, data=data)
        return svg()

    use(monkeypatch, [("p.svg", types.SimpleNamespace(render=render_))])
    render.main()
    assert set(seen["cfg"]) >= {"identity", "stack", "languages", "logos"}
    assert seen["data"] == {}, "an empty data/ renders from config alone"
