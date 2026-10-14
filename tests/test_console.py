"""Tests for the shared frame primitives: relative dates, colour, sliced rails."""
import datetime
import re

import pytest

from tools.profile import console as c

NOW = datetime.datetime(2026, 10, 12, 12, 0, tzinfo=datetime.timezone.utc)


def at(**delta):
    return (NOW - datetime.timedelta(**delta)).isoformat().replace("+00:00", "Z")


# --- ago -------------------------------------------------------------------

@pytest.mark.parametrize("when", [None, "", "garbage", "2026-13-45", 7, []])
def test_ago_returns_empty_for_anything_unusable(when):
    assert c.ago(when, NOW) == ""


@pytest.mark.parametrize("delta,expected", [
    ({"seconds": 5}, "today"),
    ({"hours": 23}, "today"),
    ({"hours": 24}, "1d ago"),
    ({"days": 9}, "9d ago"),
    ({"days": 44}, "44d ago"),
    ({"days": 45}, "1mo ago"),       # 45/30.44 rounds to 1, not 2
    ({"days": 300}, "10mo ago"),
    ({"days": 700}, "23mo ago"),
    ({"days": 731}, "2y ago"),       # 24 months promotes to years
    ({"days": 2600}, "7y ago"),
])
def test_ago_abbreviates_to_one_unit(delta, expected):
    """Set in mono in a card corner, so it has to be short before it is precise."""
    assert c.ago(at(**delta), NOW) == expected


def test_ago_floors_rather_than_rounds_the_first_day():
    """A push a few hours old reads "today", never "0d ago"."""
    assert c.ago(at(hours=20), NOW) == "today"


def test_ago_accepts_the_z_suffix_github_actually_sends():
    assert c.ago("2026-10-03T00:00:00Z", NOW) == "9d ago"


def test_ago_treats_a_naive_timestamp_as_utc():
    naive = (NOW - datetime.timedelta(days=40)).replace(tzinfo=None).isoformat()
    assert c.ago(naive, NOW) == "40d ago"


def test_ago_does_not_count_backwards_for_a_future_timestamp():
    assert c.ago(at(days=-5), NOW) == "today"


def test_ago_defaults_to_the_current_clock():
    assert c.ago(datetime.datetime.now(datetime.timezone.utc).isoformat()) == "today"


# --- num -------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0, "0"), (None, "0"), (999, "999"), (1000, "1,000"), (1234567, "1,234,567"),
])
def test_num_separates_thousands(value, expected):
    assert c.num(value) == expected


# --- colour ----------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_mix_at_either_endpoint_returns_that_colour_untouched(theme):
    """A panel shades toward the canvas, so t=0 and t=1 must be the tokens."""
    assert c.mix(theme.ink, theme.canvas, 0) == theme.canvas
    assert c.mix(theme.ink, theme.canvas, 1) == theme.ink


@pytest.mark.parametrize("a,b,expected", [
    ("#000000", "#ffffff", "#808080"),
    ("#ff0000", "#00ff00", "#808000"),
    ("#102030", "#304050", "#203040"),
])
def test_mix_at_the_midpoint_averages_every_channel(a, b, expected):
    assert c.mix(a, b, 0.5) == expected


def test_mix_rounds_a_half_up_the_way_the_browser_does():
    """`#f7f8f8` at 0.5 over `#010102` puts green on exactly 124.5; `round` would
    take it to 124 and the skyline would differ from the preview by one unit."""
    assert c.mix("#f7f8f8", "#010102", 0.5) == "#7c7d7d"


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_mix_returns_a_literal_hex_with_no_opacity(theme):
    """Shading has to be literal: the city's blocks overlap, and a translucent
    face shows the block behind it through its own wall."""
    assert re.fullmatch(r"#[0-9a-f]{6}", c.mix(theme.ink, theme.canvas, 0.37))


# --- the themes ------------------------------------------------------------

# What the preview's panelTheme() derives from DESIGN-mine-final.md. These are
# the numbers that make the two renderers agree, so they are pinned literally
# rather than recomputed — a test that derived them the same way console.py does
# would pass whatever console.py said. Regenerate by running panelTheme() in
# design-preview against mine-final and reading off both themes.
PREVIEW = {
    "dark": dict(canvas="#010102", ink="#f7f8f8", surface="#0f1011",
                 dim="#d0d6e0", faint="#909091", hairline="#23252a",
                 accent="#ef6306"),
    "light": dict(canvas="#f8f8f8", ink="#171717", surface="#ffffff",
                  dim="#4d4d4d", faint="#727272", hairline="#d9d9d9",
                  accent="#ef6306"),
}


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_each_theme_matches_the_preview_role_for_role(theme):
    """The README and the design preview are two renderers of one drawing."""
    assert {k: v for k, v in theme._asdict().items() if k != "name"} \
        == PREVIEW[theme.name]


def test_the_accent_is_one_value_across_both_themes():
    """A brand hue that changes with the reader's system setting is two brands,
    so Mine Final shares the accent where it splits every other role."""
    assert len({t.accent for t in c.THEMES}) == 1


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_three_text_tiers_are_distinct_and_ordered(theme):
    """ink > dim > faint in contrast against the canvas, or the tiers are decor."""
    def lum(hexa):
        parts = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [p / 12.92 if p <= 0.04045 else ((p + 0.055) / 1.055) ** 2.4
               for p in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    def ratio(a, b):
        x, y = sorted((lum(a) + 0.05, lum(b) + 0.05))
        return y / x

    tiers = [ratio(v, theme.canvas) for v in (theme.ink, theme.dim, theme.faint)]
    assert tiers == sorted(tiers, reverse=True), tiers
    assert tiers[-1] >= 4.5, f"faint is only {tiers[-1]:.2f}:1 on the canvas"


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_base_css_declares_only_the_pulse(theme):
    """Type is set per element now; the stylesheet has one job left."""
    css = c.base_css(theme)
    assert ".live{animation:pulse" in css
    assert "font-size" not in css and "fill:" not in css


def test_the_mono_stack_asks_for_sf_mono_before_the_embedded_fallback():
    """SF Mono is not redistributable, so JBM only covers the machines without it."""
    assert c.MONO_STACK.index("SF Mono") < c.MONO_STACK.index("JBM")


# --- tx --------------------------------------------------------------------

def test_tx_emits_only_the_attributes_it_was_given():
    plain = c.tx(10, 20, "hi", fill="#fff", family="Inter", size=13)
    assert plain == '<text x="10" y="20" fill="#fff" font-family="Inter" font-size="13">hi</text>'


def test_tx_adds_weight_tracking_and_anchor_when_asked():
    markup = c.tx(0, 0, "x", fill="#000", family="Inter", size=30,
                  weight=700, ls="-0.5", anchor="end")
    for part in ('font-weight="700"', 'letter-spacing="-0.5"', 'text-anchor="end"'):
        assert part in markup


def test_tx_escapes_the_text_and_the_family():
    markup = c.tx(0, 0, "<b> & 'q'", fill="#000", family="'SF Mono', x", size=13)
    assert "<b>" not in markup and "&amp;" in markup
    assert "&#x27;SF Mono&#x27;" in markup


# --- the frame's own edge --------------------------------------------------

def arcs(d):
    """(radius, dx, dy) for every corner arc in a path."""
    return [(float(r), float(x), float(y)) for r, x, y in
            re.findall(r"a([\d.]+) [\d.]+ 0 0 1 (-?[\d.]+) (-?[\d.]+)", d)]


def test_outline_rounds_the_one_corner_where_two_drawn_edges_meet():
    rails, caps = c._outline(0, 100, 0, 50, 10, top=True, bottom=False,
                             left=True, right=False)
    assert arcs(caps) == [(10, 10, -10)]             # the top-left turn only
    assert rails == "M0 50V10"                       # rail stops short of the corner
    assert caps.endswith("H100")                     # cap runs flush to the far edge


def test_outline_separates_the_rails_from_the_caps():
    """They are two paths so each can be rasterised the way it needs: the rails
    snapped to a device column, the arcs antialiased."""
    rails, caps = c._outline(0, 100, 0, 50, 10, top=True, bottom=True,
                             left=True, right=True)
    assert arcs(rails) == []                         # no curve in a rail
    assert "V" not in caps and "H" in caps           # no straight run in a cap


def test_outline_rounds_nothing_where_only_one_edge_is_drawn():
    rails, caps = c._outline(0, 100, 0, 50, 10, top=True, bottom=False,
                             left=False, right=False)
    assert rails == "" and arcs(caps) == []
    rails, caps = c._outline(0, 100, 0, 50, 10, top=False, bottom=False,
                             left=True, right=True)
    assert caps == "" and arcs(rails) == []


def test_outline_leaves_every_uncapped_end_open():
    """The stroke has to stop at the seam so the next slice continues it."""
    for kw in (dict(top=True, bottom=False, left=True, right=True),
               dict(top=False, bottom=True, left=True, right=True),
               dict(top=False, bottom=False, left=True, right=True)):
        d = "".join(c._outline(0, 100, 0, 50, 10, **kw))
        assert "Z" not in d, d


def test_outline_closes_all_four_corners_when_both_ends_are_capped():
    _, caps = c._outline(0, 100, 0, 50, 10, top=True, bottom=True,
                         left=True, right=True)
    assert arcs(caps) == [(10, 10, -10), (10, 10, 10), (10, -10, 10), (10, -10, -10)]


def test_outline_meets_its_own_caps_where_the_rails_stop():
    """A gap or an overlap here shows as a notch at the corner."""
    rails, caps = c._outline(0, 100, 0, 50, 10, top=True, bottom=True,
                             left=True, right=True)
    assert rails == "M0 40V10M100 10V40"             # both stop one radius short
    assert caps.startswith("M0 10a")                 # and the arc starts there
    assert "M100 40a" in caps


def test_outline_draws_nothing_at_all_for_a_piece_with_no_edges():
    assert c._outline(0, 100, 0, 50, 10, top=False, bottom=False,
                      left=False, right=False) == ("", "")


def test_fill_is_a_closed_shape_rounded_only_where_asked():
    d = c._fill(0, 100, 0, 50, 10, tl=True, tr=False, br=False, bl=False)
    assert d.endswith("Z")
    assert arcs(d) == [(10, 10, -10)]


# --- slice geometry --------------------------------------------------------

def bare(theme=c.LIGHT, height=80, *, title="t", desc="d", **kw):
    return c.slice_svg(theme, height, "", title=title, desc=desc, **kw)


def fill_path(markup):
    """The `d` of the background path — the slice's own shape."""
    return re.search(r'<path d="([^"]*)" fill="#', markup).group(1)


def edge_paths(markup):
    """Every stroked frame path, as `d` -> whether it is told to snap."""
    return {d: bool(snap) for d, snap in re.findall(
        rf'<path d="([^"]*)" fill="none" stroke="[^"]*" '
        rf'stroke-width="{c.RAIL_W}"( shape-rendering="crispEdges")?/>', markup)}


def rails_path(markup):
    """The snapped path: the straight verticals. Empty when none are drawn."""
    return next((d for d, snap in edge_paths(markup).items() if snap), "")


def caps_path(markup):
    """The antialiased path: a horizontal edge and its corner arcs."""
    return next((d for d, snap in edge_paths(markup).items() if not snap), "")


def span(d):
    """The x range a straight-edged path covers. Arcs are not counted."""
    xs = [float(n) for n in re.findall(r"[MH](-?[\d.]+)", d)]
    return min(xs), max(xs)


def test_height_must_sit_on_the_grid():
    with pytest.raises(ValueError, match="multiple"):
        bare(height=90)


def test_unknown_rails_value_is_rejected():
    with pytest.raises(ValueError, match="rails"):
        bare(rails="middle")


def test_the_rails_snap_to_whole_pixels_in_every_slice():
    """Each slice is a separate file rasterised on its own.

    A rail whose stroke edges fall mid-unit can round one way in one slice and
    the other way in the next, which shows up as the frame stepping sideways at
    the seam. Integer coordinates, the rendering hint, and twice the weight of
    an interior stroke, since a 1px rail survives neither the resample nor the
    difference in height between one slice and the next.
    """
    assert c.RAIL_W == 2 and c.RAIL_W > c.EDGE_W
    assert c.MARGIN % 1 == 0
    for markup in (bare(), bare(width=440, rails="left"), bare(top=True)):
        d = rails_path(markup)
        assert d, markup
        coords = [float(n) for n in re.findall(r"[MHV](-?[\d.]+)", d)]
        assert all(n.is_integer() for n in coords), coords


def test_default_slice_is_unchanged_by_the_new_parameters():
    """Existing panels pass neither width nor rails and must be untouched."""
    markup = bare()
    assert f'width="{c.W}" height="80"' in markup
    assert span(fill_path(markup)) == (c.FRAME_L, c.FRAME_R)
    assert rails_path(markup) == f"M{c.FRAME_L} 80V0M{c.FRAME_R} 0V80"


def test_a_middle_slice_draws_two_straight_rails_and_rounds_nothing():
    """Everything between the header and the footer continues the rails only."""
    markup = bare()
    d = rails_path(markup)
    assert arcs(d) == []
    assert "Z" not in d
    assert d.count("M") == 2 and "H" not in d       # two verticals, no cap
    assert caps_path(markup) == ""                  # and no cap path at all


def test_left_half_keeps_its_outer_rail_and_runs_flush_to_the_seam():
    markup = bare(width=440, rails="left")
    assert 'width="440"' in markup
    assert span(fill_path(markup)) == (c.MARGIN, 440)
    assert rails_path(markup) == f"M{c.MARGIN} 80V0"


def test_right_half_mirrors_the_left():
    markup = bare(width=440, rails="right")
    assert span(fill_path(markup)) == (0, 440 - c.MARGIN)
    assert rails_path(markup) == f"M{440 - c.MARGIN} 0V80"


def test_a_middle_piece_of_a_split_row_draws_no_rail_at_all():
    markup = bare(width=440, rails="none")
    assert edge_paths(markup) == {}                 # no stroked frame path emitted
    assert span(fill_path(markup)) == (0, 440)


def test_the_two_halves_tile_into_one_full_width_row():
    left, right = bare(width=440, rails="left"), bare(width=440, rails="right")
    lx0, lx1 = span(fill_path(left))
    rx0, rx1 = span(fill_path(right))
    assert lx0 == c.FRAME_L
    assert lx1 == 440                           # left background ends at the seam
    assert 440 + rx0 == 440                     # right background starts at it
    assert 440 + rx1 == c.FRAME_R


def test_half_width_slices_keep_the_grid_in_step():
    """The right half's origin must land on a grid line or the pattern shifts."""
    assert (c.W // 2) % c.ROW == 0


@pytest.mark.parametrize("edge,left_arc,right_arc", [
    ("top", (c.R_CARD, c.R_CARD, -c.R_CARD), (c.R_CARD, c.R_CARD, c.R_CARD)),
    ("bottom", (c.R_CARD, -c.R_CARD, -c.R_CARD), (c.R_CARD, -c.R_CARD, c.R_CARD)),
])
def test_a_half_slice_rounds_only_the_corner_on_the_rail_it_draws(edge, left_arc,
                                                                 right_arc):
    left = bare(width=440, rails="left", **{edge: True})
    right = bare(width=440, rails="right", **{edge: True})
    assert arcs(caps_path(left)) == [left_arc]
    assert arcs(caps_path(right)) == [right_arc]
    # The other end of the cap runs flush to the seam, where the neighbour's
    # own cap picks it up.
    assert span(caps_path(left))[1] == 440
    assert span(caps_path(right))[0] == 0


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_both_themes_produce_a_complete_frame(theme):
    """A one-slice console: capped at both ends, all four corners rounded."""
    markup = c.slice_svg(theme, 120, "", title="t", desc="d", top=True, bottom=True)
    caps, rails, fill = caps_path(markup), rails_path(markup), fill_path(markup)
    assert len(arcs(caps)) == 4
    assert {r for r, _, _ in arcs(caps)} == {c.R_CARD}
    assert fill.endswith("Z")
    assert f'fill="{theme.canvas}"' in markup
    assert f'stroke="{theme.hairline}"' in markup
    assert f"M{c.FRAME_L} " in rails and f"H{c.FRAME_R - c.R_CARD}" in caps


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_slice_names_only_its_own_themes_colours(theme):
    markup = c.slice_svg(theme, 80,
                         c.title_bar(theme, "zsh") + c.heading(theme, 70, "x"),
                         title="t", desc="d", top=True)
    for other in c.THEMES:
        if other.name != theme.name:
            assert other.canvas not in markup
            assert other.hairline not in markup


def test_a_rounded_corner_is_not_told_to_snap_to_a_device_column():
    """Only a rail is straight enough; a snapped arc steps where it meets one."""
    markup = bare(top=True)
    assert edge_paths(markup) == {rails_path(markup): True, caps_path(markup): False}
    assert arcs(caps_path(markup))


def test_css_and_defs_are_passed_through():
    markup = bare(css=".x{fill:red}", defs='<clipPath id="k"/>')
    assert ".x{fill:red}" in markup
    assert '<defs>\n<clipPath id="k"/>' in markup


# --- accessibility and motion ----------------------------------------------

def test_a_slice_names_itself_for_a_screen_reader():
    markup = bare(title="the name", desc="the real numbers")
    assert 'role="img" aria-labelledby="t d"' in markup
    assert '<title id="t">the name</title>' in markup
    assert '<desc id="d">the real numbers</desc>' in markup


def test_a_slice_escapes_markup_in_its_title_and_desc():
    markup = bare(title='A <b> & "B"', desc='<script> & "quoted"')
    assert "<b>" not in markup and "<script>" not in markup
    assert "&lt;b&gt; &amp; &quot;B&quot;" in markup
    assert "&lt;script&gt;" in markup


def test_reduced_motion_switches_the_one_animation_off():
    markup = bare()
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in markup
    assert ".live{animation:" in markup


# --- font embedding --------------------------------------------------------

def payloads(markup):
    return re.findall(r"src:url\(data:font/woff2;base64,([^)]+)\) format", markup)


def test_a_slice_embeds_the_four_faces_the_css_asks_for():
    """GitHub strips <link> and external url(), so the subset has to inline.

    Both families carry a bold: the panels set 700 on every value and section
    heading, which in a terminal are set in mono as often as in sans.
    """
    markup = bare()
    assert re.findall(r"font-family:'(\w+)';font-weight:(\d+)", markup) == [
        ("Inter", "400"), ("Inter", "600"), ("JBM", "400"), ("JBM", "700")]
    assert len(payloads(markup)) == 4
    assert all(p for p in payloads(markup))


def test_the_subset_grows_with_the_glyphs_it_has_to_carry():
    assert len(c.font_faces("ab")) < len(c.font_faces("abcdefghijklmnopqrstuvwxyz"))


def test_digits_are_embedded_even_when_nothing_prints_one():
    """Every panel counts something, and CSS content can inject one unseen."""
    assert c.font_faces("") == c.font_faces("0123456789")


def test_the_subset_ignores_glyphs_that_only_appear_in_markup():
    """`visible` is what feeds the subsetter, so an attribute pays nothing."""
    plain = bare(height=40)
    with_attrs = c.slice_svg(c.LIGHT, 40, '<text class="qwkzj"></text>',
                             title="t", desc="d")
    assert payloads(with_attrs) == payloads(plain)


def test_the_text_argument_adds_glyphs_the_body_does_not_contain():
    assert payloads(bare(text="xyz")) != payloads(bare())


# --- chrome ----------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_title_bar_draws_three_faint_rings(theme):
    markup = c.title_bar(theme, "ozzycodes2 — zsh")
    mid = c.MARGIN + c.TITLE_H // 2
    rings = re.findall(
        rf'<circle cx="(\d+)" cy="{mid}" r="5" fill="none" stroke="{theme.faint}"',
        markup)
    assert [int(x) for x in rings] == [c.FRAME_L + 24, c.FRAME_L + 42, c.FRAME_L + 60]
    assert f'fill="{theme.surface}"' in markup
    # Chrome is not a datum and not a section, so it gets neither accent job.
    assert theme.accent not in markup


def test_the_title_bar_centres_its_label_in_mono():
    markup = c.title_bar(c.LIGHT, "ozzycodes2 — zsh")
    assert f'<text x="{c.W // 2}" y="{c.MARGIN + c.TITLE_H // 2 + 5}" ' \
           f'fill="{c.LIGHT.faint}" font-family="{c.e(c.MONO_STACK)}" ' \
           'font-size="12" letter-spacing="1" text-anchor="middle">' in markup


def test_the_title_bar_escapes_its_label():
    assert "<b>" not in c.title_bar(c.LIGHT, "<b>")


def test_the_title_bar_sits_on_the_frames_rounded_cap():
    """Not merely rounded to the same radius — on the same arc.

    Floated below the cap it leaves a strip of canvas above itself and the two
    sets of corners read as two misaligned windows.
    """
    band = fill_path(c.title_bar(c.LIGHT, "ozzycodes2 — zsh"))
    assert arcs(band) == [(c.R_CARD, c.R_CARD, c.R_CARD),
                          (c.R_CARD, c.R_CARD, -c.R_CARD)]
    frame = caps_path(c.slice_svg(c.LIGHT, 120, "", title="t", desc="d", top=True))
    assert band.startswith(f"M{c.FRAME_L + c.R_CARD} {c.MARGIN}")
    assert frame.startswith(f"M{c.FRAME_L} {c.MARGIN + c.R_CARD}")
    # Both turn between the same two points: (FRAME_L, MARGIN + R) and
    # (FRAME_L + R, MARGIN), so the band's arc lies under the frame's.
    assert band.endswith(f"V{c.MARGIN + c.R_CARD}"
                         f"a{c.R_CARD} {c.R_CARD} 0 0 1 {c.R_CARD} {-c.R_CARD}Z")


def test_the_title_bar_rules_off_at_a_fixed_depth():
    markup = c.title_bar(c.LIGHT, "ozzycodes2 — zsh")
    rule = c.MARGIN + c.TITLE_H
    assert f'<line x1="{c.FRAME_L}" y1="{rule}" x2="{c.FRAME_R}" y2="{rule}"' in markup
    assert f'V{rule}H{c.FRAME_L}' in fill_path(markup)


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_foot_bar_mirrors_the_title_bar_at_the_frames_other_end(theme):
    """Same depth, same surface, rounded the other way, so the window has two ends."""
    markup = c.foot_bar(theme, 200)
    y0 = 200 - c.MARGIN - c.TITLE_H
    assert f'y1="{y0}" x2="{c.FRAME_R}" y2="{y0}" stroke="{theme.hairline}"' in markup
    assert f'fill="{theme.surface}"' in markup
    band, r = fill_path(markup), c.R_CARD
    assert band.startswith(f"M{c.FRAME_L} {y0}H{c.FRAME_R}")
    assert f"a{r} {r} 0 0 1 {-r} {r}H{c.FRAME_L + r}a{r} {r} 0 0 1 {-r} {-r}" in band


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_heading_rules_the_content_width_and_indexes_its_start(theme):
    """The 2px accent stroke is the console's section index: identical in every
    panel, so it marks where a section begins without ranking the sections."""
    markup = c.heading(theme, 100, "stack")
    assert f'x1="{c.TEXT_X}" y1="114" x2="{c.CONTENT_R}" y2="114" ' \
           f'stroke="{theme.hairline}" stroke-width="{c.EDGE_W}"' in markup
    assert f'x2="{c.TEXT_X + 120}" y2="114" stroke="{theme.accent}" ' \
           'stroke-width="2"' in markup


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_heading_sets_its_path_in_mono_with_the_prefix_dropped_back(theme):
    """`~/` only reads as a path in a monospace, and it is chrome, not the name."""
    markup = c.heading(theme, 100, "stack")
    mono = c.e(c.MONO_STACK)
    assert f'<text x="{c.TEXT_X}" y="100" fill="{theme.faint}" ' \
           f'font-family="{mono}" font-size="20" font-weight="700">~/</text>' in markup
    assert f'<text x="{c.TEXT_X + 24}" y="100" fill="{theme.ink}" ' \
           f'font-family="{mono}" font-size="20" font-weight="700">stack</text>' in markup


def test_a_heading_right_aligns_its_counter_in_mono():
    markup = c.heading(c.LIGHT, 100, "stack", "12 repos")
    assert f'<text x="{c.CONTENT_R}" y="100" fill="{c.LIGHT.faint}" ' \
           f'font-family="{c.e(c.MONO_STACK)}" font-size="12" ' \
           'letter-spacing="1" text-anchor="end">12 repos</text>' in markup


def test_a_heading_without_a_counter_emits_only_the_path():
    assert c.heading(c.LIGHT, 100, "stack").count("<text") == 2


def test_a_heading_escapes_its_name_and_counter():
    markup = c.heading(c.LIGHT, 100, "<b>", '"x" & y')
    assert "<b>" not in markup
    assert "&lt;b&gt;" in markup and "&quot;x&quot; &amp; y" in markup


def test_headings_stay_inside_the_content_width():
    assert c.TEXT_X < c.CONTENT_R < c.FRAME_R


# --- grid, output ----------------------------------------------------------

@pytest.mark.parametrize("value,expected", [(0, 0), (1, 40), (40, 40), (41, 80)])
def test_to_grid_rounds_up_to_the_next_row(value, expected):
    assert c.to_grid(value) == expected


def test_write_puts_each_theme_in_its_own_directory(tmp_path, monkeypatch):
    """readme.py pairs ./assets/light/x.svg with ./assets/dark/x.svg by name."""
    monkeypatch.setattr(c, "OUT", tmp_path)
    for theme in c.THEMES:
        path = c.write(theme, "nested/x.svg", f"<svg>{theme.name}</svg>")
        assert path == tmp_path / theme.name / "nested/x.svg"
        assert path.read_text() == f"<svg>{theme.name}</svg>"


def test_visible_keeps_nested_text_and_drops_attributes():
    assert c.visible('<text class="dim">a<tspan>b</tspan></text>') == "ab"
    assert c.visible("&amp;&lt;") == "&<"
