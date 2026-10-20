"""Tests for the vendored hemisphere drawings.

These files are a second copy of a drawing that also lives in `design-preview`,
which is the drift `tools/profile/BACKPORT.md` exists to prevent. The copy buys
reproducibility — a drawing living only in the preview exists on one laptop —
and the price is paid here and in `test_brains_parity.py`.
"""
import re

import pytest

from tools.brains import figures

ON_DISK = [n for n in figures.NAMES if (figures.HERE / f"{n}.svg").exists()]


def paints(svg):
    """Every colour literal the document names, `none` excluded."""
    return {m for m in re.findall(r'(?:fill|stroke)="([^"]+)"', svg) if m != "none"}


@pytest.fixture(params=ON_DISK)
def name(request):
    return request.param


def test_the_art_is_the_published_size(name):
    assert f'viewBox="0 0 {figures.W} {figures.H}"' in figures.load(name)


def test_the_art_is_at_least_as_wide_as_the_card_box():
    """The card fits the image with `background-size: contain` from the top
    left. `contain` drops the slack on whichever axis fits loosest, and from the
    top left that slack lands at the right and the bottom.

    Only the right matters. The left hemisphere is anchored to the image's right
    edge, so slack there is a gap between it and the gutter and the pair stops
    reading as one brain; slack at the bottom falls on transparent ground and
    costs nothing. So the image must be no narrower for its height than the
    widest box it can be handed — 374 x 100, where the profile column tops out.
    """
    assert figures.W / figures.H >= 374 / 100


def test_the_art_sets_no_type(name):
    """The accent may not set type in either theme, and a transparent
    two-colour image has no ink to set it in. The gist description is the label."""
    assert "<text" not in figures.load(name)


def luminance(hex_colour):
    ch = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# The two grounds one image has to work on. GitHub's pinned card paints the
# drawing straight onto the card surface and strips no alpha, and the cards
# carry no media query, so there is no themed pair to fall back on.
GITHUB_DARK, GITHUB_LIGHT = "#0d1117", "#ffffff"


def test_every_colour_is_a_shade_of_the_accent(name):
    """One hue. A second hue would be a second decision about a drawing whose
    whole vocabulary is the accent, and the GIF palette is built from whatever
    is in here."""
    rgb = {tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in paints(figures.load(name))}
    accent = figures.accent_rgb()
    # A scale of one triple: every channel the same fraction of the accent's,
    # within the rounding a byte costs.
    for c in rgb:
        ks = [1 - v / a for v, a in zip(c, accent) if a >= 16]
        assert max(ks) - min(ks) < 0.02, f"{c} is not the accent scaled"


def test_the_accent_itself_is_painted(name):
    """The lit state. The ramp runs down from the accent because nothing lighter
    clears 3:1 on a white card, so a drawing that never reaches it is a drawing
    with no bright end at all."""
    assert figures.ACCENT in paints(figures.load(name))


def test_every_shade_reads_on_both_github_themes(name):
    """Why the ramp stops where it does. It is one image for both cards, so the
    darkest step is bounded by the dark card and the lightest by the light one;
    the accent sits at the top of that band and the trail decays down from it."""
    for colour in paints(figures.load(name)):
        on_dark, on_light = contrast(colour, GITHUB_DARK), contrast(colour, GITHUB_LIGHT)
        assert min(on_dark, on_light) >= 3, f"{colour}: {on_dark:.2f} dark, {on_light:.2f} light"


def test_no_ground_is_painted(name):
    """GIF alpha is one bit and the card carries no media query, so a painted
    ground would be an opaque slab on whichever GitHub theme it did not match."""
    assert not re.search(rf'<rect[^>]*width="(?:100%|{figures.W})"[^>]*fill=', figures.load(name))


def test_nothing_animates_in(name):
    """Frame zero is what a static renderer, a reduced-motion viewer and
    GitHub's mobile apps paint. An element that fades up from nothing is
    simply absent there."""
    svg = figures.load(name)
    assert 'opacity="0"' not in svg
    assert not re.search(r"(?:^|[,{\s])(?:0%|from)\s*(?:,\s*[\d.]+%\s*)*\{[^}]*opacity:\s*0(?![.\d])", svg)


def keyframe_declarations(svg):
    """Every `(property, value)` declared inside a `@keyframes` block."""
    out = []
    for body in re.findall(r"@keyframes[^{]*\{(.*?\})\s*\}", svg, re.S):
        for step in re.findall(r"\{([^}]*)\}", body):
            out += [
                tuple(s.strip() for s in d.split(":", 1))
                for d in step.split(";")
                if ":" in d
            ]
    return out


# A whitelist, because the failure is open-ended: `opacity: 0` is only the
# best-known way to make an element absent at frame zero, and `scale(0)`,
# `visibility: hidden` and a `stroke-dasharray` draw-on all do it too. These two
# are what the medium renders honestly.
#
# `stroke-dashoffset` is safe only because the marching trace is a second,
# heavier copy laid over a path that is painted unconditionally: the drawing is
# complete at every instant and the dash only ever adds to it. That is why the
# dash is exempt from the travel budget below, and why the test after it has to
# hold — without the unlit copy, a marching dash is a draw-on.
ANIMATABLE = {"stroke-dashoffset", "transform"}
TRANSFORMS = {"translate", "translateX", "translateY"}
# How a value reaches a transform, not a transform applied to the element.
VALUE_FNS = {"calc", "var"}


def test_motion_touches_only_properties_that_cannot_hide_the_drawing(name):
    declared = keyframe_declarations(figures.load(name))
    assert declared, "the figure declares keyframes but no properties"
    assert {p for p, _ in declared} <= ANIMATABLE


def test_any_transform_is_a_translate_inside_the_stated_budget(name):
    svg = figures.load(name)
    transforms = "".join(v for p, v in keyframe_declarations(svg) if p == "transform")
    assert {f for f in re.findall(r"([A-Za-z]+)\(", transforms)} - VALUE_FNS <= TRANSFORMS
    moves = re.findall(r"translate[XY]?\(([^)]*)\)", transforms)
    assert all(abs(float(v)) <= 24 for a in moves for v in re.findall(r"-?\d+(?:\.\d+)?", a))


def test_nothing_stands_behind_the_drawing(name):
    """The reference's grid is construction: both halves are picked off it and
    then it is deleted, and nothing replaces it. A ground layer would also be
    the one thing in the figure that no click in the editor produced."""
    svg = figures.load(name)
    assert '<g class="drift"' not in svg
    assert "pnl-pin-grid" not in svg


def test_a_marching_dash_is_drawn_over_a_copy_that_is_always_painted(name):
    """What makes `stroke-dashoffset` legal. A lit path with no unlit copy
    beneath it reads, at frame zero, as a broken line — which is an element
    animating in by another name."""
    svg = figures.load(name)
    lit = re.findall(r'<path[^>]*class="signal"[^>]*\sd="([^"]*)"', svg)
    base = set(re.findall(r'<path(?![^>]*class="signal")[^>]*\sd="([^"]*)"', svg))
    assert lit
    assert set(lit) <= base


def test_neither_half_closes_a_shape(name):
    """No hemisphere is outlined. The left is a honeycomb and the right a
    cluster of open arcs, and in both the mass is what implies the shape — a
    closed path is an outline drawn around a construction, which is the badge
    the reference was taken without."""
    assert not re.search(r'<path[^>]*\sd="[^"]*[Zz]"', figures.load(name))


def test_a_dashed_edge_carries_no_signal():
    """The left lattice dashes the edges facing the other half: a connection
    reached for rather than made. A signal travelling one would assert the
    connection the dash denies, and would fill the gaps while it passed."""
    svg = figures.load("left-brain")
    dashed = re.findall(r'<path(?![^>]*class="signal")[^>]*stroke-dasharray[^>]*\sd="([^"]*)"', svg)
    dashed += re.findall(r'<path(?![^>]*class="signal")[^>]*\sd="([^"]*)"[^>]*stroke-dasharray', svg)
    lit = set(re.findall(r'<path[^>]*class="signal"[^>]*\sd="([^"]*)"', svg))
    assert dashed, "the lattice draws no dashed edge"
    assert not (set(dashed) & lit)


def test_motion_is_a_loop_of_at_least_three_seconds(name):
    svg = figures.load(name)
    assert "@keyframes" in svg
    assert max(float(d) for d in re.findall(r"animation:[^;}]*?(\d+(?:\.\d+)?)s", svg)) >= 3


def test_it_names_where_it_was_generated_from(name):
    p = figures.provenance(name)
    assert p["source"].endswith("brains.js") and p["generated"]


def test_load_rejects_a_name_it_does_not_carry():
    with pytest.raises(FileNotFoundError):
        figures.load("middle-brain")


def test_provenance_rejects_a_name_it_does_not_carry():
    with pytest.raises(FileNotFoundError):
        figures.provenance("middle-brain")


def test_a_figure_that_states_no_provenance_is_an_error(tmp_path, monkeypatch):
    """The whole point of the comment is that a vendored copy can be checked
    against the preview. A copy that lost it is not checkable, so it fails here
    rather than at the far end of a capture run."""
    (tmp_path / "left-brain.svg").write_text("<svg/>")
    monkeypatch.setattr(figures, "HERE", tmp_path)
    with pytest.raises(ValueError, match="generated, source"):
        figures.provenance("left-brain")


def test_the_left_hemisphere_is_vendored():
    """Guards the parametrised tests above: an empty `ON_DISK` would make every
    one of them vacuous and the suite would still be green."""
    assert "left-brain" in ON_DISK
