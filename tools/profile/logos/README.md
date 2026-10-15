# Vendored brand marks

`stack-logos.json` is the glyph table the `~/stack` panel draws. One entry per
tool named in `../stack.json`:

| Key | Meaning |
|---|---|
| `d` | the `<path>` data, a single path |
| `box` | the square viewBox side the path is drawn in — 24 for Simple Icons, 128 for Devicon |
| `hex` | the brand's own colour, before the panel corrects it |
| `src` | upstream set and slug |

**Generated — do not hand-edit.** It is written by `vendor_logos.py` in the
`design-preview` repo, which fetches both sets at a pinned version and emits the
JS form for the preview and this JSON for the port. Re-run that script to add a
tool; editing here puts the two renderers out of agreement.

A tool with no entry is not an error: the panel sets its name in mono at the
cell's centre instead. So a roster can name something before its mark is
vendored.

The panel never paints `hex` as given. It is corrected to 3:1 against the face
it lands on, which is the threshold for a graphical object — several marks are
pure black or near-white upstream and would vanish into one theme or the other.

## Provenance

18 of the 20 marks are [Simple Icons](https://github.com/simple-icons/simple-icons)
16.35.0, CC0 1.0 — `SIMPLE-ICONS-CC0.md`.

`Java` and `AWS` are [Devicon](https://github.com/devicons/devicon) 2.16.0, MIT
— `DEVICON-MIT.txt`. Simple Icons removed both at their owners' request, so
there is no CC0 source for them.

Neither licence covers trademark. The marks identify the tools they name and
imply no endorsement by Oracle, Amazon, or any other owner.
