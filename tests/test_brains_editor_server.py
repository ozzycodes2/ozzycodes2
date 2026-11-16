"""Tests for the grid editor's save endpoint.

The editor autosaves on every click. A save that fails silently loses a drawing
the browser has already forgotten, so the round trip is checked rather than
assumed.
"""
import http.server
import json
import threading
import urllib.error
import urllib.request

import pytest

from tools.brains.editor import server


@pytest.fixture
def serving(tmp_path, monkeypatch):
    """A live server on an ephemeral port, saving into `tmp_path`."""
    monkeypatch.setattr(server, "STATE", tmp_path / "state.json")
    with server.serve(0) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{srv.server_address[1]}"
        srv.shutdown()


def put(base, path, body):
    req = urllib.request.Request(f"{base}/{path}", data=body, method="PUT")
    return urllib.request.urlopen(req)


def test_a_save_round_trips_to_disk(serving):
    drawing = {"left": {"104,20|152,48": "solid"}, "right": {}}
    assert put(serving, "state.json", json.dumps(drawing).encode()).status == 204
    read = json.loads(urllib.request.urlopen(f"{serving}/state.json").read())
    assert read == drawing


def test_an_unsaved_editor_gets_an_empty_board(serving):
    """The common first run. A 404 here renders the page without a grid."""
    body = json.loads(urllib.request.urlopen(f"{serving}/state.json").read())
    assert body == {"left": {}, "right": {}}


def test_a_put_anywhere_else_is_refused(serving):
    with pytest.raises(urllib.error.HTTPError) as exc:
        put(serving, "index.html", b"{}")
    assert exc.value.code == 405


def test_a_malformed_save_is_refused_and_leaves_the_drawing_alone(serving):
    good = {"left": {"104,20|152,48": "solid"}, "right": {}}
    put(serving, "state.json", json.dumps(good).encode())
    with pytest.raises(urllib.error.HTTPError) as exc:
        put(serving, "state.json", b"{not json")
    assert exc.value.code == 400
    assert json.loads(server.STATE.read_text()) == good


def test_the_page_itself_is_served(serving):
    assert b'<div id="board">' in urllib.request.urlopen(f"{serving}/index.html").read()


def test_main_binds_and_says_where(capsys, monkeypatch):
    """What `main` adds to `serve` is the address it printed and the file it
    claims to be saving to — the two things the operator acts on."""
    monkeypatch.setattr(http.server.ThreadingHTTPServer, "serve_forever", lambda self: None)
    server.main(["--port", "0"])
    out = capsys.readouterr().out
    assert "http://127.0.0.1:" in out and str(server.STATE) in out
    assert ":0/" not in out  # the bound port, not the requested one


def test_the_editor_is_never_cached(serving):
    """A stale page would render a grid whose clicks save to a newer schema."""
    res = urllib.request.urlopen(f"{serving}/state.json")
    assert res.headers["Cache-Control"] == "no-store"
