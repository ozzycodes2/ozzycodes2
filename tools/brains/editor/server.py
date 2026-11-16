"""Serve the grid editor and accept its saves.

    python -m tools.brains.editor.server

Static hosting plus one extra verb: the page PUTs `state.json` back on every
change, so what is clicked in the browser is on disk for `shape.py` to read.
`http.server` is enough because this never leaves the loopback interface and
holds nothing but grid coordinates.
"""
import argparse
import functools
import http.server
import json
import pathlib

HERE = pathlib.Path(__file__).parent
STATE = HERE / "state.json"
PORT = 8732


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        if pathlib.PurePosixPath(self.path).name != STATE.name:
            self.send_error(405)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            state = json.loads(body)
        except json.JSONDecodeError as exc:
            self.send_error(400, str(exc))
            return
        STATE.write_text(json.dumps(state, indent=1) + "\n")
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # The drawing is read from where the PUT wrote it, not from the static
        # directory — otherwise the editor can load a different file than it
        # saves. An unsaved editor is the common first run, not an error.
        if pathlib.PurePosixPath(self.path).name == STATE.name:
            body = STATE.read_bytes() if STATE.exists() else b'{"left":{},"right":{}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.command != "GET":
            super().log_message(fmt, *args)


def serve(port=PORT):
    """A bound, not-yet-serving server. Port 0 binds an ephemeral one, which is
    how the tests get a server without fighting a running editor for 8732."""
    handler = functools.partial(Handler, directory=str(HERE))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=PORT)
    with serve(ap.parse_args(argv).port) as srv:
        print(f"http://127.0.0.1:{srv.server_address[1]}/  ->  {STATE}")
        srv.serve_forever()


if __name__ == "__main__":
    main()
