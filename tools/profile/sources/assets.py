"""Written output: the SVG slices, the preview page, and README.md itself.

Separate from `store.py` because nothing reads these back as data. The slices
and the preview are build products; README.md is the one file here that is
partly hand-written, so it is read and rewritten rather than replaced — see
`present.readme.splice`.
"""
from . import files

ROOT = files.PROFILE.parent.parent
OUT = ROOT / "assets"
README = ROOT / "README.md"
PREVIEW = OUT / "preview.html"


def write_slice(theme_name, name, markup):
    """Write one slice under its theme. `name` may contain a subdirectory."""
    path = OUT / theme_name / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markup)
    return path


def write_preview(markup):
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.write_text(markup)
    return PREVIEW


def read_readme():
    return README.read_text()


def write_readme(text):
    README.write_text(text)
    return README
