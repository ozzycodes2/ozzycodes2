"""Writes assets/preview.html — every slice, both themes side by side.

Wiring only. The README cannot be previewed as the README: GitHub picks one
theme and the other stays hidden, so this page carries both.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.profile.present import preview as present
from tools.profile.sources import assets, store


def main():
    if not store.exists(store.MANIFEST):
        sys.exit("error: no manifest; run tools/profile/render.py first")
    path = assets.write_preview(present.page(store.read_manifest()))
    print(f"wrote {path.relative_to(assets.ROOT)}")


if __name__ == "__main__":
    main()
