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


def test_the_art_sets_no_type(name):
    """The accent may not set type in either theme, and a transparent
    two-colour image has no ink to set it in. The gist description is the label."""
    assert "<text" not in figures.load(name)


def test_the_accent_is_the_only_visible_colour(name):
    assert paints(figures.load(name)) == {figures.ACCENT}


def test_no_ground_is_painted(name):
    """GIF alpha is one bit and the card carries no media query, so a painted
    ground would be an opaque slab on whichever GitHub theme it did not match."""
    assert not re.search(r'<rect[^>]*width="(?:100%|1340)"[^>]*fill=', figures.load(name))


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
    """The 24px cap governs travel a keyframe states outright. The field's
    drift is stated as its own period instead, so it contributes no literal
    here — what the cap was protecting is asserted below."""
    svg = figures.load(name)
    transforms = "".join(v for p, v in keyframe_declarations(svg) if p == "transform")
    assert {f for f in re.findall(r"([A-Za-z]+)\(", transforms)} - VALUE_FNS <= TRANSFORMS
    moves = re.findall(r"translate[XY]?\(([^)]*)\)", transforms)
    assert all(abs(float(v)) <= 24 for a in moves for v in re.findall(r"-?\d+(?:\.\d+)?", a))


def drifting_dots(svg):
    """`(drift, [(cx, cy, r), …])` for the field group, or `None`. The drift is
    signed: it is the per-loop travel, and its sign is the direction."""
    g = re.search(r'<g class="drift" style="--drift: (-?[\d.]+)">(.*?)</g>', svg, re.S)
    if not g:
        return None
    dots = re.findall(r'<circle cx="(-?[\d.]+)" cy="(-?[\d.]+)" r="([\d.]+)"', g[2])
    return float(g[1]), [tuple(float(v) for v in d) for d in dots]


def test_the_field_drifts_away_from_the_midline(name):
    """The brain is anchored at the midline — the right edge of the left card,
    the left edge of the right one — so the pair radiates outward from the
    gutter they share. Drifting the same way on both cards instead reads as one
    current sweeping across them."""
    drift, _ = drifting_dots(figures.load(name))
    assert drift < 0 if name == "left-brain" else drift > 0


def test_the_field_drifts_by_exactly_its_own_period(name):
    """The whole licence for travelling further than the budget. Every dot the
    drift carries onto the canvas stands where its neighbour stood, so nothing
    enters, leaves or jumps when the loop restarts. Travel that missed the
    spacing would shunt the field once every three and a half seconds."""
    field = drifting_dots(figures.load(name))
    assert field, "the figure declares no drifting field"
    drift, dots = field
    assert drift
    at = {(round(x, 1), y, r) for x, y, r in dots}
    # `x - drift` is the dot upstream of this one, whichever way upstream is.
    assert all(
        (round(x - drift, 1), y, r) in at
        for x, y, r in dots
        if 0 <= x <= figures.W
    )
    # Tiled past both edges, or the replacement arrives from nowhere.
    assert min(x for x, _, _ in dots) < 0 < figures.W < max(x for x, _, _ in dots)


def test_a_marching_dash_is_drawn_over_a_copy_that_is_always_painted(name):
    """What makes `stroke-dashoffset` legal. A lit path with no unlit copy
    beneath it reads, at frame zero, as a broken line — which is an element
    animating in by another name."""
    svg = figures.load(name)
    lit = re.findall(r'<path[^>]*class="signal"[^>]*\sd="([^"]*)"', svg)
    base = set(re.findall(r'<path(?![^>]*class="signal")[^>]*\sd="([^"]*)"', svg))
    assert lit
    assert set(lit) <= base


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
