"""Renders every README slice into assets/, and the manifest readme.py reads.

Reads hand-written content from profile.toml and fetched numbers from
data/*.json. Makes no network calls, so it can be re-run offline against the
committed JSON while iterating on a panel.
"""
import json
import pathlib
import sys
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tools.profile import console as c
from tools.profile.panels import city, footer, header, projects, stack, stats

# Display order, and the order of the manifest. `top` and `bottom` are decided
# from position here, so header stays first and footer last.
PANELS = [
    ("header.svg", header),
    ("stats.svg", stats),
    ("contribution-city.svg", city),
    ("stack.svg", stack),
    ("projects.svg", projects),
    ("footer.svg", footer),
]

MANIFEST = c.DATA / "manifest.json"


def load_config():
    return tomllib.loads((HERE / "profile.toml").read_text())


def load_data():
    """Fetched numbers, keyed by file stem. Missing files render as empty."""
    out = {}
    for path in sorted(c.DATA.glob("*.json")):
        out[path.stem] = json.loads(path.read_text())
    return out


def slices_of(name, result):
    """Normalise whatever a panel returned into a list of Slices.

    A panel that is one full-width section returns bare markup and gets `name`.
    A panel whose parts need separate links returns its own named slices —
    either Slices, or a plain {filename: markup} mapping when none of them
    link anywhere.
    """
    if isinstance(result, str):
        return [c.Slice(name, result)]
    if isinstance(result, dict):
        return [c.Slice(f, m) for f, m in result.items()]
    return [s if isinstance(s, c.Slice) else c.Slice(*s) for s in result]


def main():
    cfg, data = load_config(), load_data()

    manifest = []
    for name, panel in PANELS:
        for entry in slices_of(name, panel.render(cfg, data)):
            c.write(entry.file, entry.markup)
            desc, width = c.describe(entry.markup)
            manifest.append({
                "file": entry.file,
                "desc": desc,
                # Percentages rather than pixels so the console scales with the
                # page. Widths within a row sum to W, so these sum to 100.
                "width": f"{100 * width / c.W:.4f}".rstrip("0").rstrip(".") + "%",
                **({"href": entry.href} if entry.href else {}),
            })
            print(f"wrote assets/{entry.file}")

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote data/manifest.json ({len(manifest)} slices)")


if __name__ == "__main__":
    main()
