"""The generated JSON under data/ — what fetch.py writes and render.py reads.

Four files, none of them hand-edited. `fetch.py` owns the first three and
`render.py` owns the manifest; only the step that owns a file ever writes it.

  stats.json     headline counters, language byte totals, streaks
  calendar.json  [[iso date, count], ...] for the last 365 days
  projects.json  live stars/language for the repos profile.toml curates
  manifest.json  one row per rendered slice, the input to readme.py

The directory is committed, so the daily job's `git add tools/profile/data`
picks up whatever changed. A trailing newline goes on every file for the same
reason: a diff of a one-line change should not also show the last line being
rewritten.
"""
import json

from . import files

DATA = files.PROFILE / "data"
MANIFEST = "manifest.json"


def read_all():
    """`{stem: parsed json}` for every file in data/. Missing files are absent.

    Panels are handed this whole mapping and must tolerate a missing key, so a
    render against an empty data/ produces short panels rather than a traceback.
    """
    return {path.stem: json.loads(path.read_text())
            for path in sorted(DATA.glob("*.json"))}


def read(name):
    return json.loads((DATA / name).read_text())


def exists(name):
    return (DATA / name).exists()


def write(name, payload):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(payload, indent=2) + "\n")
    return DATA / name


def read_manifest():
    return read(MANIFEST)


def write_manifest(rows):
    return write(MANIFEST, rows)
