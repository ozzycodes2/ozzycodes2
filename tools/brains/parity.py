"""Keeps the vendored drawings honest against the preview that authors them.

`BACKPORT.md` is explicit that a change made in one place and not the other
"leaves two renderers disagreeing about one drawing, and nothing will tell you
which is right." Vendoring was chosen anyway — a drawing living only in
`design-preview` exists on one laptop — so this is the something that tells you.

It skips, never fails, when the preview is absent: a clone of this repository
alone has to run green. Vendoring does not skip — see `vendor`.

    python -m tools.brains.parity                    # report drift, exit 1 if any
    python -m tools.brains.parity --write left-brain # re-vendor from the preview
"""
import datetime
import difflib
import functools
import json
import pathlib
import subprocess
import sys

from . import figures

PREVIEW = pathlib.Path.home() / "personal" / "design-preview"

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
SYSTEM = "fabric"

SOURCE = "site/assets/brains.js"

_PROVENANCE = """<!-- source: {source}
     generated: {date}
     Vendored from design-preview, system {system}. Never hand-edit:
     change the preview, look at it, then run
     `python -m tools.brains.parity --write {name}`. -->
"""


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


def _renderer(regenerate):
    """The callable that re-renders a drawing, or `None` when the preview is
    not on this machine."""
    if regenerate is not None:
        return regenerate
    root = preview_root()
    return None if root is None else functools.partial(_regenerate_at, root=root)


def vendor(name, *, regenerate=None, today=None):
    """Write `name`'s vendored copy from the preview, provenance and all.

    Unlike `diff`, this raises when the preview is absent: there is nothing to
    copy from, and a silent no-op would leave the stale drawing in place and
    report success.
    """
    dest = figures.path(name)
    render = _renderer(regenerate)
    if render is None:
        raise FileNotFoundError(f"{PREVIEW / 'site' / 'assets' / 'brains.js'} is not on this machine")
    head = _PROVENANCE.format(
        source=SOURCE, system=SYSTEM, name=name, date=(today or datetime.date.today()).isoformat()
    )
    dest.write_text(f"{head}{render(name).strip()}\n")
    return dest


def diff(name, *, regenerate=None):
    """A unified diff when the vendored copy and the preview disagree, else
    `None`. `None` is also what an absent preview gives: skip, never fail."""
    regenerate = _renderer(regenerate)
    if regenerate is None:
        return None

    want, have = _body(regenerate(name)), _body(figures.load(name))
    if want == have:
        return None
    return "\n".join(
        difflib.unified_diff(
            want.splitlines(), have.splitlines(),
            fromfile=f"{name} (preview)", tofile=f"{name} (vendored)", lineterm="",
        )
    )


def main(argv=None, *, regenerate=None):
    args = list(argv) if argv else []
    names = [a for a in args if not a.startswith("-")] or list(figures.NAMES)

    if "--write" in args:
        for name in names:
            print(f"wrote {vendor(name, regenerate=regenerate)}")
        return 0

    if _renderer(regenerate) is None:
        # Printing nothing here would read as "checked, clean". It checked
        # nothing: the drawing is authored in a directory that is not present.
        print(f"skipped: design-preview is not at {PREVIEW}")
        return 0

    drifted = 0
    for name in names:
        if not figures.path(name).exists():
            continue
        report = diff(name, regenerate=regenerate)
        if report:
            print(report)
            drifted = 1
    return drifted


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
