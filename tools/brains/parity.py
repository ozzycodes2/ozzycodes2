"""Keeps the vendored drawings honest against the preview that authors them.

`BACKPORT.md` is explicit that a change made in one place and not the other
"leaves two renderers disagreeing about one drawing, and nothing will tell you
which is right." Vendoring was chosen anyway — a drawing living only in
`design-preview` exists on one laptop — so this is the something that tells you.

It skips, never fails, when the preview is absent: a clone of this repository
alone has to run green.
"""
import difflib
import functools
import json
import pathlib
import subprocess

from . import figures

PREVIEW = pathlib.Path.home() / "Documents" / "personal" / "design-preview"

# `dom-stub.mjs` installs the globals and loads every asset script in page
# order, which is the only way `brains.js` gets `panelTheme` and `piso`.
_DUMP = """
import("file://{stub}").then(() => {{
  const s = window.DESIGN_SYSTEMS.find((x) => x.slug === {slug});
  if (!s) {{ console.error("no such system"); process.exit(1); }}
  process.stdout.write(brainSvg(s, {side}));
}});
"""

# The system the drawings are authored under. Every other system renders the
# Brains tab from its own tokens, but only this one is published.
SYSTEM = "mine-final"


def preview_root():
    """`PREVIEW` if the drawing is actually there, else `None`.

    Checks for the file rather than the directory: an empty or half-made
    checkout would otherwise be reported as parity-clean.
    """
    if (PREVIEW / "site" / "assets" / "brains.js").is_file():
        return PREVIEW
    return None


def _body(svg):
    """The document without its provenance comment.

    The comment carries a generation date, so comparing it would make every
    check fail the day after the file was written.
    """
    return svg.split("-->", 1)[-1].strip() if svg.lstrip().startswith("<!--") else svg.strip()


def regenerate(name, root):
    """Re-render `name` from the preview under node, as a string."""
    side = figures.path(name).stem.removesuffix("-brain")
    script = _DUMP.format(
        stub=(root / "test" / "dom-stub.mjs").resolve(),
        slug=json.dumps(SYSTEM),
        side=json.dumps(side),
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=root, check=True)
    return out.stdout


def _regenerate_at(name, *, root):
    return regenerate(name, root)


def diff(name, *, regenerate=None):
    """A unified diff when the vendored copy and the preview disagree, else
    `None`. `None` is also what an absent preview gives: skip, never fail."""
    if regenerate is None:
        root = preview_root()
        if root is None:
            return None
        regenerate = functools.partial(_regenerate_at, root=root)

    want, have = _body(regenerate(name)), _body(figures.load(name))
    if want == have:
        return None
    return "\n".join(
        difflib.unified_diff(
            want.splitlines(), have.splitlines(),
            fromfile=f"{name} (preview)", tofile=f"{name} (vendored)", lineterm="",
        )
    )
