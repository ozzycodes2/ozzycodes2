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


def typeset(svg):
    """The content of every `<text>` node."""
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def test_the_only_type_is_the_left_halfs_thrown_digits(name):
    """The gist description is the label, so nothing in the art may read as
    one. The left half throws binary digits, which are marks rather than
    labelling — drawn as `<text>` because a bar and a ring drawn as paths would
    satisfy a no-type rule and still be read as numbers.

    What keeps that from becoming a hole in the rule is the shape of what is
    permitted: ones and zeros, a handful at a time. A caption cannot be spelled
    in them. The right half's vocabulary has no numbers and it sets no type."""
    words = typeset(figures.load(name))
    if name == "right-brain":
        assert words == []
    else:
        assert words
        assert all(re.fullmatch(r"[01]{1,5}", w) for w in words), sorted(set(words))


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
TRANSFORMS = {"translate", "translateX", "translateY", "scale", "rotate"}
# How a value reaches a transform, not a transform applied to the element.
VALUE_FNS = {"calc", "var"}


def keyframe_blocks(svg):
    """`{name: [(stop, declaration), ...]}` for every `@keyframes` in the file."""
    out = {}
    for name, body in re.findall(r"@keyframes\s+([\w-]+)\s*\{(.*?\})\s*\}", svg, re.S):
        out[name] = re.findall(r"([\d.]+%|from|to)\s*\{([^}]*)\}", body)
    return out


def channels(decl):
    """The `translate`, `scale` and `rotate` a stop names, as `(x, y, s, deg)`."""
    move = re.search(r"translate\(([^)]*)\)", decl)
    pair = (move.group(1).split(",") + ["0"]) if move else ["0", "0"]
    scale = re.search(r"scale\(([\d.]+)\)", decl)
    turn = re.search(r"rotate\((-?[\d.]+)deg\)", decl)
    return (
        float(re.sub(r"[a-z%]", "", pair[0]) or 0),
        float(re.sub(r"[a-z%]", "", pair[1]) or 0),
        float(scale.group(1)) if scale else 1.0,
        float(turn.group(1)) if turn else 0.0,
    )


def test_motion_touches_only_properties_that_cannot_hide_the_drawing(name):
    declared = keyframe_declarations(figures.load(name))
    assert declared, "the figure declares keyframes but no properties"
    assert {p for p, _ in declared} <= ANIMATABLE


def test_every_transform_is_one_of_the_three_the_field_is_built_from(name):
    svg = figures.load(name)
    transforms = "".join(v for p, v in keyframe_declarations(svg) if p == "transform")
    assert {f for f in re.findall(r"([A-Za-z]+)\(", transforms)} - VALUE_FNS <= TRANSFORMS


def lane_periods(svg):
    """`{lane keyframe: slot spacing}` for every lane in the thrown field.

    The spacing is read off the slots themselves rather than any constant, so
    it is the figure's own answer to what one period of the lane is.
    """
    lanes = {}
    for chunk in svg.split('<g transform="translate(')[1:]:
        head = chunk[:400]
        lane = re.search(r"animation-name: ([\w-]+-throw-\d+);", head)
        if not lane:
            continue
        x = float(re.match(r"(-?[\d.]+) (-?[\d.]+)\)", chunk).group(1))
        lanes.setdefault(lane.group(1), []).append(x)
    out = {}
    for lane, xs in lanes.items():
        # A lane carries more than one stream, shifted against each other down
        # the card but not along it, so a column can hold two marks.
        xs = sorted(set(xs))
        gaps = {round(b - a, 3) for a, b in zip(xs, xs[1:])}
        assert len(gaps) == 1, f"{lane}: slots are not evenly spaced ({sorted(gaps)})"
        out[lane] = gaps.pop()
    return out


def test_the_only_travel_in_the_figure_is_one_period_of_a_lane(name):
    """What replaced the 24px travel cap, and why one was needed at all: the
    drawing may not walk off the card over a loop, because the GIF repeats and
    a figure that ended somewhere else would jump back.

    A periodic field is the one thing that can travel and still return. The
    slots in a lane repeat every `p`, so translating the lane by exactly `p`
    puts a different mark in every place a mark already was and the frame is
    indistinguishable from the first. Off by any amount and the whole field
    jumps once per loop — which is visible, and is what the arithmetic here
    catches. Every other channel closes outright: the wind returns, the tumble
    returns to its own angle, and the size is a function of position rather
    than of time.

    The sign is the other half of it. Each hemisphere throws away from the
    gutter they share, so the pair opens outward instead of one half firing
    across the other.
    """
    svg = figures.load(name)
    away = -1 if name == "left-brain" else 1
    periods = lane_periods(svg)
    assert periods, "the figure throws no field"
    for lane, stops in keyframe_blocks(svg).items():
        if not any("transform" in d for _, d in stops):
            continue
        first, last = channels(stops[0][1]), channels(stops[-1][1])
        travel = away * periods.get(lane, 0)
        assert abs((last[0] - first[0]) - travel) < 1e-6, f"{lane}: travels {last[0] - first[0]}, not {travel}"
        assert abs(last[1] - first[1]) < 1e-6, f"{lane}: drifts {last[1] - first[1]} down"
        assert abs(last[3] - first[3]) < 1e-3, f"{lane}: turns {last[3] - first[3]}deg"


def test_nothing_is_scaled_away(name):
    """`scale(0)` hides an element as completely as `opacity: 0`, and the first
    frame is what a static renderer and a reduced-motion viewer paint. The
    field's falloff is a function of where a mark is, so it never reaches zero
    and it starts at the size the mark was drawn."""
    for stops in keyframe_blocks(figures.load(name)).values():
        sizes = [channels(d)[2] for _, d in stops if "scale" in d]
        if not sizes:
            continue
        assert min(sizes) > 0.1, f"{min(sizes)} is gone"
        assert sizes[0] == 1.0, f"the first frame is already at {sizes[0]}"


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
    the reference was taken without.

    The contour inside `<clipPath>` is exempt. It is a region rather than a
    drawing — it states where the field is hidden behind the hemisphere — and a
    region has to close to bound anything.
    """
    painted = re.sub(r"<clipPath[\s\S]*?</clipPath>", "", figures.load(name))
    assert not re.search(r'<path[^>]*\sd="[^"]*[Zz]"', painted)


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


def test_the_march_is_paced_rather_than_the_loop(name):
    """What a viewer reads as speed is dash repeats per second, which is the
    repeats the keyframe walks divided by the period it walks them in. Either
    number alone says nothing: the loop is as short as it can be because the
    published GIF spends a frame on every tick of it and the frame rate is
    bought with its length, and a floor on the period would forbid that while
    still permitting any speed at all inside it.
    """
    svg = figures.load(name)
    assert "@keyframes" in svg
    loop = max(float(d) for d in re.findall(r"animation:[^;}]*?(\d+(?:\.\d+)?)s", svg))
    laps = float(re.search(r"stroke-dashoffset:\s*calc\(-([\d.]+)", svg).group(1))
    assert laps.is_integer(), f"{laps} repeats a loop leaves a seam"
    assert laps / loop <= 1, f"{laps / loop:.2f} repeats a second"


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
