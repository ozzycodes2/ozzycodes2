"""Rewrites the generated block of README.md from the render manifest.

Wiring only: `sources.store` supplies the manifest, `present.readme` spells the
block, `sources.assets` reads and rewrites the file. Everything outside the
markers survives untouched.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.profile.present import readme as present
from tools.profile.sources import assets, store


def main():
    if not store.exists(store.MANIFEST):
        sys.exit("error: no manifest; run tools/profile/render.py first")
    manifest = store.read_manifest()

    try:
        text = present.splice(assets.read_readme(), present.block(manifest))
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    assets.write_readme(text)
    print(f"README updated ({len(manifest)} slices)")


if __name__ == "__main__":
    main()
