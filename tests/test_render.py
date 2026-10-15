"""Tests for the slice normaliser and the per-theme render orchestration."""
import json
import types

import pytest

from tools.profile import console as c
from tools.profile import render


def svg(desc="a description", width=c.W):
    """Minimal markup carrying the two things `describe` reads back out."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="40">'
            f'<desc id="d">{c.e(desc)}</desc></svg>')


def panel(result):
    """A stand-in for a panel module.

    `result` is either what every theme renders, or a callable taking the theme
    so one panel can answer differently per theme.
    """
    def render_(_cfg, _data, theme):
        return result(theme) if callable(result) else result
    return types.SimpleNamespace(render=render_)


def files_under(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


@pytest.fixture
def out(tmp_path, monkeypatch):
    """Point every write at tmp_path, so the real assets/ and data/ are safe."""
    assets = tmp_path / "assets"
    monkeypatch.setattr(render.c, "OUT", assets)
    monkeypatch.setattr(render, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(render, "load_config", lambda: {})
    monkeypatch.setattr(render, "load_data", lambda: {})
    return assets


# --- the panel registry ----------------------------------------------------

def test_the_frame_is_opened_by_the_header_and_closed_by_the_footer():
    """`top` and `bottom` are decided from position, not named by the panel."""
    assert render.PANELS[0][0] == "header.svg"
    assert render.PANELS[-1][0] == "footer.svg"


def test_every_registered_panel_can_render():
    assert all(callable(getattr(p, "render", None)) for _, p in render.PANELS)


# --- slices_of -------------------------------------------------------------

def test_slices_of_wraps_bare_markup_under_the_registered_name():
    assert render.slices_of("x.svg", "<svg/>") == [c.Slice("x.svg", "<svg/>")]


def test_slices_of_names_one_slice_per_entry_of_a_mapping():
    out = render.slices_of("x.svg", {"a.svg": "<svg>a</svg>", "b.svg": "<svg>b</svg>"})
    assert [(s.file, s.markup) for s in out] == [("a.svg", "<svg>a</svg>"),
                                                 ("b.svg", "<svg>b</svg>")]


def test_slices_of_leaves_a_mapping_unlinked():
    """A panel that spells its parts as a dict is saying none of them link."""
    out = render.slices_of("x.svg", {"a.svg": "<svg/>"})
    assert all(s.href is None for s in out)


def test_slices_of_passes_slices_through_untouched():
    given = [c.Slice("a.svg", "<svg/>", "https://example.com/1")]
    assert render.slices_of("x.svg", given) == given


def test_slices_of_turns_a_plain_tuple_into_a_slice():
    out = render.slices_of("x.svg", [("a.svg", "<svg/>")])
    assert out == [c.Slice("a.svg", "<svg/>")]
    assert isinstance(out[0], c.Slice)


def test_slices_of_keeps_the_href_of_a_plain_tuple():
    out = render.slices_of("x.svg", [("a.svg", "<svg/>", "https://example.com/1")])
    assert out[0].href == "https://example.com/1"


def test_slices_of_accepts_a_mix_of_slices_and_tuples():
    out = render.slices_of("x.svg", [c.Slice("a.svg", "<svg/>"), ("b.svg", "<svg/>")])
    assert [s.file for s in out] == ["a.svg", "b.svg"]
    assert all(isinstance(s, c.Slice) for s in out)


def test_slices_of_drains_a_generator():
    """A panel may yield its slices rather than build a list."""
    out = render.slices_of("x.svg", (c.Slice(f"{i}.svg", "<svg/>") for i in range(3)))
    assert [s.file for s in out] == ["0.svg", "1.svg", "2.svg"]


def test_slices_of_a_panel_that_rendered_nothing():
    assert render.slices_of("x.svg", []) == []


# --- render_theme ----------------------------------------------------------

def test_render_theme_writes_under_the_theme_it_was_given(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg()))])
    render.render_theme({}, {}, c.DARK)
    assert files_under(out) == ["dark/p.svg"]


def test_render_theme_writes_the_markup_the_panel_returned(out, monkeypatch):
    markup = svg("the real one")
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(markup))])
    render.render_theme({}, {}, c.LIGHT)
    assert (out / "light/p.svg").read_text() == markup


def test_render_theme_writes_a_slice_that_names_a_subdirectory(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel({"links/mail.svg": svg()}))])
    render.render_theme({}, {}, c.LIGHT)
    assert files_under(out) == ["light/links/mail.svg"]


def test_render_theme_reports_the_panels_own_desc(out, monkeypatch):
    """The alt text is read back out of the file, never supplied beside it."""
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg("what it draws")))])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert [r["desc"] for r in rows] == ["what it draws"]


def test_render_theme_unescapes_the_desc_it_reports(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg('5 "starred" & forked')))])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert rows[0]["desc"] == '5 "starred" & forked'


@pytest.mark.parametrize("width,expected", [
    (c.W, "100%"),
    (c.W // 2, "50%"),
    (280, "31.8182%"),
    (320, "36.3636%"),
])
def test_render_theme_states_the_width_as_a_share_of_the_slice_width(
        out, monkeypatch, width, expected):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg(width=width)))])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert rows[0]["width"] == expected


def test_render_theme_reads_the_width_off_a_real_slice(out, monkeypatch):
    """Guards the manifest against a panel whose geometry the test fakes."""
    half = c.slice_svg(c.LIGHT, 40, "", title="T", desc="half", width=c.W // 2, rails="left")
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(half))])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert rows[0] == {"file": "p.svg", "desc": "half", "width": "50%"}


def test_render_theme_carries_an_href_only_when_the_slice_has_one(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel([
        c.Slice("a.svg", svg(), "https://example.com/1"),
        c.Slice("b.svg", svg()),
    ]))])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert rows[0]["href"] == "https://example.com/1"
    # Absent, not None: readme.py asks with .get() and would anchor on a null.
    assert "href" not in rows[1]


def test_render_theme_keeps_the_rows_in_panel_order(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [
        ("first.svg", panel(svg())),
        ("second.svg", panel({"a.svg": svg(), "b.svg": svg()})),
        ("third.svg", panel(svg())),
    ])
    rows = render.render_theme({}, {}, c.LIGHT)
    assert [r["file"] for r in rows] == ["first.svg", "a.svg", "b.svg", "third.svg"]


def test_render_theme_hands_the_panel_the_config_and_data(out, monkeypatch):
    seen = []

    def render_(cfg, data, theme):
        seen.append((cfg, data, theme))
        return svg()

    monkeypatch.setattr(render, "PANELS",
                        [("p.svg", types.SimpleNamespace(render=render_))])
    render.render_theme({"identity": {}}, {"stats": {"n": 1}}, c.DARK)
    assert seen == [({"identity": {}}, {"stats": {"n": 1}}, c.DARK)]


def test_render_theme_names_each_file_it_wrote(out, monkeypatch, capsys):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg()))])
    render.render_theme({}, {}, c.DARK)
    assert "wrote assets/dark/p.svg" in capsys.readouterr().out


# --- main ------------------------------------------------------------------

def test_main_renders_every_theme_into_its_own_directory(out, monkeypatch):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(svg()))])
    render.main()
    assert files_under(out) == [f"{t.name}/p.svg" for t in sorted(
        c.THEMES, key=lambda t: t.name)]


def test_main_writes_one_manifest_row_per_slice_not_per_theme(out, monkeypatch, tmp_path):
    monkeypatch.setattr(render, "PANELS", [
        ("p.svg", panel({"a.svg": svg(), "b.svg": svg()})),
        ("q.svg", panel(svg())),
    ])
    render.main()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [m["file"] for m in manifest] == ["a.svg", "b.svg", "q.svg"]
    assert len(manifest) == 3


def test_main_keeps_the_first_themes_rows(out, monkeypatch, tmp_path):
    """The two themes are identical in geometry and alt text by construction."""
    monkeypatch.setattr(render, "PANELS", [
        ("p.svg", panel(lambda theme: svg(f"drawn for {theme.name}"))),
    ])
    render.main()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [m["desc"] for m in manifest] == [f"drawn for {c.THEMES[0].name}"]


def test_main_exits_when_a_later_theme_produces_a_different_slice_list(out, monkeypatch):
    """Mismatched lists would pair the wrong two images inside one <picture>."""
    def by_theme(theme):
        return svg() if theme is c.THEMES[0] else {"other.svg": svg()}

    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(by_theme))])
    with pytest.raises(SystemExit, match=c.THEMES[1].name):
        render.main()


def test_main_exits_when_a_later_theme_produces_fewer_slices(out, monkeypatch):
    def by_theme(theme):
        return ({"a.svg": svg(), "b.svg": svg()} if theme is c.THEMES[0]
                else {"a.svg": svg()})

    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(by_theme))])
    with pytest.raises(SystemExit, match="different slice list"):
        render.main()


def test_main_does_not_write_a_manifest_it_could_not_trust(out, monkeypatch, tmp_path):
    def by_theme(theme):
        return svg() if theme is c.THEMES[0] else {"other.svg": svg()}

    monkeypatch.setattr(render, "PANELS", [("p.svg", panel(by_theme))])
    with pytest.raises(SystemExit):
        render.main()
    assert not (tmp_path / "manifest.json").exists()


def test_main_gives_each_theme_its_own_rendering_of_the_same_file(out, monkeypatch):
    """Same filename in both directories, but each drawn for its own palette."""
    monkeypatch.setattr(render, "PANELS", [
        ("p.svg", panel(lambda theme: svg(f"drawn for {theme.name}"))),
    ])
    render.main()
    for theme in c.THEMES:
        assert f"drawn for {theme.name}" in (out / theme.name / "p.svg").read_text()


def test_main_counts_slices_and_themes_separately(out, monkeypatch, capsys):
    monkeypatch.setattr(render, "PANELS", [("p.svg", panel({"a.svg": svg(),
                                                            "b.svg": svg()}))])
    render.main()
    assert f"2 slices × {len(c.THEMES)} themes" in capsys.readouterr().out


# --- loading inputs --------------------------------------------------------

def test_load_data_keys_every_json_file_by_its_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(render.c, "DATA", tmp_path)
    (tmp_path / "stats.json").write_text('{"repos": 7}')
    (tmp_path / "calendar.json").write_text("[1, 2]")
    assert render.load_data() == {"stats": {"repos": 7}, "calendar": [1, 2]}


def test_load_data_ignores_anything_that_is_not_json(tmp_path, monkeypatch):
    monkeypatch.setattr(render.c, "DATA", tmp_path)
    (tmp_path / "notes.txt").write_text("not data")
    assert render.load_data() == {}


def test_load_config_reads_the_committed_profile(monkeypatch):
    """profile.toml is the hand-written half of the console."""
    assert "identity" in render.load_config()


def test_load_config_folds_in_both_hand_kept_rosters():
    """The stack figure and the languages ring are both config. Neither reads
    `data/`, so `render.py` draws the same slice before any fetch."""
    cfg = render.load_config()
    assert cfg["stack"] and cfg["languages"]
    assert all(isinstance(v, int) and v > 0 for v in cfg["languages"].values())
