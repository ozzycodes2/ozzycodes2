"""Renders every README slice into assets/, and the manifest readme.py reads.

Wiring only: `sources` supplies the content and the fetched numbers,
`transform.config` assembles what panels read, `present.slices` draws, and
`sources.assets` writes. Makes no network call, so it can be re-run offline
against the committed JSON while iterating on a panel.

Every panel is rendered once per theme, into assets/<theme>/. The manifest is
keyed by slice, not by theme: one entry carries both files, because the README
pairs them in a single <picture> and their geometry and alt text are identical
by construction.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.profile.present import console as c
from tools.profile.present import slices
from tools.profile.sources import assets, files, store
from tools.profile.transform import config, layout


def main():
    cfg = config.build(files.profile_config(), files.stack_roster(),
                       files.languages(), files.stack_logos())
    data = store.read_all()

    manifest = None
    for theme in c.THEMES:
        rows = []
        for file, markup, row in slices.render_theme(cfg, data, theme):
            assets.write_slice(theme.name, file, markup)
            rows.append(row)
            print(f"wrote assets/{theme.name}/{file}")
        if manifest is None:
            manifest = rows
        elif not layout.same_slices(rows, manifest):
            sys.exit(f"error: {theme.name} produced a different slice list")

    store.write_manifest(manifest)
    print(f"wrote data/manifest.json ({len(manifest)} slices × {len(c.THEMES)} themes)")


if __name__ == "__main__":
    main()
