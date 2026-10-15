"""Tests for the data layer: the committed content, the JSON store, the output.

The reads of the committed files are deliberately against the real ones. They
are the profile's content, and a test that stubs them pins nothing.
"""
import json

import pytest

from tools.profile.sources import assets, files, store
from tools.profile.transform import config


# --- files ------------------------------------------------------------------

def test_profile_config_reads_the_committed_profile():
    """profile.toml is the hand-written half of the console."""
    assert "identity" in files.profile_config()


def test_both_hand_kept_rosters_are_mappings_to_numbers():
    """The stack figure and the languages ring are both config. Neither reads
    `data/`, so render.py draws the same slice before any fetch."""
    assert files.stack_roster()
    languages = files.languages()
    assert languages
    assert all(isinstance(v, int) and v > 0 for v in languages.values())


def test_every_tool_level_is_on_the_five_step_ladder():
    for tools in files.stack_roster().values():
        assert all(1 <= level <= 5 for level in tools.values())


def test_stack_logos_carry_a_hex_and_a_box():
    """`brand` corrects the hex; `face_tiles` scales the mark by its box."""
    for name, logo in files.stack_logos().items():
        assert logo["hex"].startswith("#"), name
        assert logo["box"] > 0, name


def test_every_tool_in_the_roster_either_has_a_mark_or_degrades_to_type():
    """Not a requirement — a record of which tools currently draw as a word."""
    logos = files.stack_logos()
    tools = {t for tools in files.stack_roster().values() for t in tools}
    assert tools - set(logos) == set(), sorted(tools - set(logos))


# --- store ------------------------------------------------------------------

def test_read_all_keys_every_json_file_by_its_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    (tmp_path / "stats.json").write_text('{"repos": 7}')
    (tmp_path / "calendar.json").write_text("[1, 2]")
    assert store.read_all() == {"stats": {"repos": 7}, "calendar": [1, 2]}


def test_read_all_ignores_anything_that_is_not_json(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    (tmp_path / "notes.txt").write_text("not data")
    assert store.read_all() == {}


def test_read_all_of_a_directory_that_does_not_exist(tmp_path, monkeypatch):
    """A render before the first fetch must produce short panels, not a crash."""
    monkeypatch.setattr(store, "DATA", tmp_path / "absent")
    assert store.read_all() == {}


def test_write_creates_the_directory_and_ends_with_a_newline(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path / "data")
    path = store.write("x.json", {"a": 1})
    text = path.read_text()
    assert text.endswith("\n")
    assert json.loads(text) == {"a": 1}


def test_write_then_read_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    store.write("x.json", [1, 2, 3])
    assert store.read("x.json") == [1, 2, 3]


def test_exists_reports_on_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    assert not store.exists(store.MANIFEST)
    store.write_manifest([{"file": "a.svg"}])
    assert store.exists(store.MANIFEST)
    assert store.read_manifest() == [{"file": "a.svg"}]


def test_the_committed_store_carries_what_the_panels_read():
    """stats, calendar and projects are each the input to at least one panel."""
    assert {"stats", "calendar", "projects", "manifest"} <= set(store.read_all())


# --- assets -----------------------------------------------------------------

def test_write_slice_puts_each_theme_in_its_own_directory(tmp_path, monkeypatch):
    """readme.py pairs ./assets/light/x.svg with ./assets/dark/x.svg by name."""
    monkeypatch.setattr(assets, "OUT", tmp_path)
    for name in ("light", "dark"):
        path = assets.write_slice(name, "nested/x.svg", f"<svg>{name}</svg>")
        assert path == tmp_path / name / "nested/x.svg"
        assert path.read_text() == f"<svg>{name}</svg>"


def test_write_preview_creates_the_assets_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "OUT", tmp_path / "assets")
    monkeypatch.setattr(assets, "PREVIEW", tmp_path / "assets" / "preview.html")
    assert assets.write_preview("<html>").read_text() == "<html>"


def test_readme_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "README", tmp_path / "README.md")
    assets.write_readme("hello")
    assert assets.read_readme() == "hello"


def test_the_committed_readme_is_where_assets_says_it_is():
    assert assets.README.exists() and assets.OUT.is_dir()


# --- config -------------------------------------------------------------------

def test_config_folds_the_rosters_in_under_fixed_keys():
    cfg = config.build({"identity": {"name": "x"}}, {"Cloud": {}}, {"Rust": 1},
                       {"Rust": {"hex": "#000", "box": 24}})
    assert cfg["identity"] == {"name": "x"}
    assert (cfg["stack"], cfg["languages"]) == ({"Cloud": {}}, {"Rust": 1})
    assert cfg["logos"]["Rust"]["box"] == 24


def test_config_lets_the_rosters_win_over_a_toml_key_of_the_same_name():
    """profile.toml must not be able to shadow a roster the panels rely on."""
    cfg = config.build({"stack": "wrong"}, {"Cloud": {}}, {}, {})
    assert cfg["stack"] == {"Cloud": {}}
