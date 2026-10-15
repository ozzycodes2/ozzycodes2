"""Subsets the embedded typefaces down to the glyphs a slice actually paints.

The one place the presentation layer opens a file, and deliberately so: these
are vendored faces, pinned beside the renderer and identical on every run, not
data. Routing them through the data layer would mean threading a loader through
`slice_svg` and every panel that calls it, to decouple a read whose result
cannot vary.

GitHub strips <link> and external url() from a rendered SVG, so a webfont
reference is simply dropped and the panels fall back to whatever the viewer
happens to have. Each slice therefore carries its own base64 woff2 of only the
glyphs it needs. SF Mono is not embedded — it is not redistributable — so the
mono stack asks for it first, which resolves on macOS, and falls back to JBM.
"""
import base64
import io
import pathlib

from fontTools import subset
from fontTools.ttLib import TTFont

FONT_DIR = pathlib.Path(__file__).resolve().parent.parent / "fonts"

# (family name the CSS asks for, file stem, weight). Both families carry a
# regular and a bold: the panels set 700 on every value, repo name and section
# heading, and 600 on the one display-size name. JBM is the fallback under SF
# Mono, which cannot be embedded.
FACES = (
    ("Inter", "inter-latin-400-normal", 400),
    ("Inter", "inter-latin-600-normal", 600),
    ("JBM", "jetbrains-mono-latin-400-normal", 400),
    ("JBM", "jetbrains-mono-latin-700-normal", 700),
)


def subset_face(source, text):
    """One face cut down to `text`, as woff2 bytes.

    `source` is anything TTFont opens — a path, or a file object in tests.
    recalcTimestamp=False keeps the bytes stable across runs, so an unchanged
    panel produces no diff and the daily job pushes nothing.
    """
    font = TTFont(source, recalcTimestamp=False)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = []
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return buf.getvalue()


def face_css(text):
    """@font-face rules carrying only the glyphs `text` needs, inlined as woff2."""
    text += "0123456789"
    rules = []
    for family, stem, weight in FACES:
        payload = base64.b64encode(
            subset_face(FONT_DIR / f"{stem}.woff2", text)).decode()
        rules.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{payload}) format('woff2')}}"
        )
    return "".join(rules)
