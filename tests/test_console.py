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
    ({"seconds": 5}, "just now"),
    ({"seconds": 89}, "just now"),
    ({"seconds": 120}, "2 minutes ago"),
    ({"minutes": 59}, "59 minutes ago"),
    ({"minutes": 60}, "1 hour ago"),
    ({"hours": 23}, "23 hours ago"),
    ({"hours": 24}, "1 day ago"),
    ({"days": 30}, "30 days ago"),
    ({"days": 31}, "1 month ago"),
    ({"days": 300}, "9 months ago"),
    ({"days": 364}, "11 months ago"),
    ({"days": 366}, "1 year ago"),
    ({"days": 2600}, "7 years ago"),
])
def test_ago_rounds_to_one_coarse_unit(delta, expected):
    assert c.ago(at(**delta), NOW) == expected


@pytest.mark.parametrize("delta", [
    {"minutes": 2}, {"hours": 1}, {"days": 1}, {"days": 32}, {"days": 370},
    {"days": 2600},
])
def test_ago_agrees_in_number(delta):
    n, unit, _ = c.ago(at(**delta), NOW).split()
    assert unit.endswith("s") == (n != "1"), (n, unit)


def test_ago_treats_a_naive_timestamp_as_utc():
    naive = (NOW - datetime.timedelta(days=40)).replace(tzinfo=None).isoformat()
    assert c.ago(naive, NOW) == "1 month ago"


def test_ago_does_not_count_backwards_for_a_future_timestamp():
    assert c.ago(at(days=-5), NOW) == "just now"


def test_ago_defaults_to_the_current_clock():
    assert c.ago(datetime.datetime.now(datetime.timezone.utc).isoformat()) == "just now"


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


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_mix_returns_a_literal_hex_with_no_opacity(theme):
    """Shading has to be literal: the city's blocks overlap, and a translucent
    face shows the block behind it through its own wall."""
    assert re.fullmatch(r"#[0-9a-f]{6}", c.mix(theme.ink, theme.canvas, 0.37))


# --- base_css --------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_base_css_carries_the_themes_own_three_text_fills(theme):
    css = c.base_css(theme)
    assert f".ink{{fill:{theme.ink}}}" in css
    assert f".dim{{fill:{theme.dim}}}" in css
    assert f".accent{{fill:{theme.accent}}}" in css
    assert f"fill:{theme.ink}}}" in css.splitlines()[0]      # the default text fill


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_base_css_names_no_other_themes_colours(theme):
    """One stylesheet per theme; a leaked token renders wrong in one scheme."""
    css = c.base_css(theme)
    for other in c.THEMES:
        if other.name != theme.name:
            assert other.ink not in css
            assert other.accent not in css


def test_base_css_declares_every_type_step_as_a_class():
    css = c.base_css(c.LIGHT)
    for name, step in (("display", c.DISPLAY), ("heading", c.HEADING),
                       ("body", c.BODY), ("caption", c.CAPTION)):
        assert f".{name}{{font-size:{step.size}px;font-weight:{step.weight}" in css
    assert f".mono{{font-family:{c.MONO_STACK};font-size:{c.MONO.size}px" in css


def test_base_css_tracks_only_the_steps_that_ask_for_it():
    css = c.base_css(c.LIGHT)
    assert f"letter-spacing:{c.DISPLAY.tracking}px" in css
    assert ".body{font-size:16px;font-weight:400}" in css


def test_the_mono_stack_asks_for_sf_mono_before_the_embedded_fallback():
    """SF Mono is not redistributable, so JBM only covers the machines without it."""
    assert c.MONO_STACK.index("SF Mono") < c.MONO_STACK.index("JBM")


# --- the frame's own edge --------------------------------------------------

def arcs(d):
    """(radius, dx, dy) for every corner arc in a path."""
    return [(float(r), float(x), float(y)) for r, x, y in
            re.findall(r"a([\d.]+) [\d.]+ 0 0 1 (-?[\d.]+) (-?[\d.]+)", d)]


def test_outline_rounds_the_one_corner_where_two_drawn_edges_meet():
    d = c._outline(0, 100, 0, 50, 10, top=True, bottom=False, left=True, right=False)
    assert arcs(d) == [(10, 10, -10)]                # the top-left turn only
    assert d.startswith("M0 50V10")                  # rail stops short of the corner
    assert d.endswith("H100")                        # and runs flush to the far edge


def test_outline_rounds_nothing_where_only_one_edge_is_drawn():
    assert arcs(c._outline(0, 100, 0, 50, 10, top=True, bottom=False,
                           left=False, right=False)) == []
    assert arcs(c._outline(0, 100, 0, 50, 10, top=False, bottom=False,
                           left=True, right=True)) == []


def test_outline_leaves_every_uncapped_end_open():
    """The stroke has to stop at the seam so the next slice continues it."""
    for kw in (dict(top=True, bottom=False, left=True, right=True),
               dict(top=False, bottom=True, left=True, right=True),
               dict(top=False, bottom=False, left=True, right=True)):
        d = c._outline(0, 100, 0, 50, 10, **kw)
        assert "Z" not in d, d


def test_outline_closes_all_four_corners_when_both_ends_are_capped():
    d = c._outline(0, 100, 0, 50, 10, top=True, bottom=True, left=True, right=True)
    assert arcs(d) == [(10, 10, -10), (10, 10, 10), (10, -10, 10), (10, -10, -10)]


def test_outline_draws_nothing_at_all_for_a_piece_with_no_edges():
    assert c._outline(0, 100, 0, 50, 10, top=False, bottom=False,
                      left=False, right=False) == ""


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


def edge_path(markup):
    return re.search(
        rf'<path d="([^"]*)" fill="none" stroke="[^"]*" stroke-width="{c.EDGE_W}"',
        markup).group(1)


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
    the seam. A 1px stroke on an integer coordinate, plus the rendering hint.
    """
    assert c.EDGE_W == 1
    assert c.MARGIN % 1 == 0
    for markup in (bare(), bare(width=440, rails="left")):
        assert 'shape-rendering="crispEdges"' in markup
        coords = [float(n) for n in re.findall(r"[MHV](-?[\d.]+)", edge_path(markup))]
        assert all(n.is_integer() for n in coords), coords


def test_default_slice_is_unchanged_by_the_new_parameters():
    """Existing panels pass neither width nor rails and must be untouched."""
    markup = bare()
    assert f'width="{c.W}" height="80"' in markup
    assert span(fill_path(markup)) == (c.FRAME_L, c.FRAME_R)
    assert edge_path(markup) == f"M{c.FRAME_L} 80V0M{c.FRAME_R} 0V80"


def test_a_middle_slice_draws_two_straight_rails_and_rounds_nothing():
    """Everything between the header and the footer continues the rails only."""
    markup = bare()
    d = edge_path(markup)
    assert arcs(d) == []
    assert "Z" not in d
    assert d.count("M") == 2 and "H" not in d       # two verticals, no cap
    assert 'shape-rendering="crispEdges"' in markup


def test_left_half_keeps_its_outer_rail_and_runs_flush_to_the_seam():
    markup = bare(width=440, rails="left")
    assert 'width="440"' in markup
    assert span(fill_path(markup)) == (c.MARGIN, 440)
    assert edge_path(markup) == f"M{c.MARGIN} 80V0"


def test_right_half_mirrors_the_left():
    markup = bare(width=440, rails="right")
    assert span(fill_path(markup)) == (0, 440 - c.MARGIN)
    assert edge_path(markup) == f"M{440 - c.MARGIN} 0V80"


def test_a_middle_piece_of_a_split_row_draws_no_rail_at_all():
    markup = bare(width=440, rails="none")
    assert edge_path(markup) == ""
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
    assert arcs(edge_path(left)) == [left_arc]
    assert arcs(edge_path(right)) == [right_arc]
    # The other end of the cap runs flush to the seam, where the neighbour's
    # own cap picks it up.
    assert span(edge_path(left))[1] == 440
    assert span(edge_path(right))[0] == 0


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_both_themes_produce_a_complete_frame(theme):
    """A one-slice console: capped at both ends, all four corners rounded."""
    markup = c.slice_svg(theme, 120, "", title="t", desc="d", top=True, bottom=True)
    outline, fill = edge_path(markup), fill_path(markup)
    assert len(arcs(outline)) == 4
    assert {r for r, _, _ in arcs(outline)} == {c.R_CARD}
    assert fill.endswith("Z")
    assert f'fill="{theme.canvas}"' in markup
    assert f'stroke="{theme.hairline}"' in markup
    assert f"M{c.FRAME_L} " in outline and f"H{c.FRAME_R - c.R_CARD}" in outline


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_slice_names_only_its_own_themes_colours(theme):
    markup = c.slice_svg(theme, 80, c.title_bar(theme, 40) + c.heading(theme, 70, "x"),
                         title="t", desc="d", top=True)
    for other in c.THEMES:
        if other.name != theme.name:
            assert other.canvas not in markup
            assert other.hairline not in markup


def test_a_rounded_corner_is_not_told_to_snap_to_a_device_column():
    """Only a rail is straight enough; a snapped arc steps where it meets one."""
    assert 'shape-rendering="auto"' in bare(top=True)


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


def test_reduced_motion_switches_every_animation_off():
    """Panels animate through shared classes so this one override reaches them."""
    markup = bare()
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in markup
    for cls in (".ln", ".cursor", ".dot"):
        assert f"{cls}{{animation:" in markup


# --- font embedding --------------------------------------------------------

def payloads(markup):
    return re.findall(r"src:url\(data:font/woff2;base64,([^)]+)\) format", markup)


def test_a_slice_embeds_the_three_faces_the_css_asks_for():
    """GitHub strips <link> and external url(), so the subset has to inline."""
    markup = bare()
    assert re.findall(r"font-family:'(\w+)';font-weight:(\d+)", markup) == [
        ("Inter", "400"), ("Inter", "600"), ("JBM", "400")]
    assert len(payloads(markup)) == 3
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
def test_the_title_bar_draws_three_hairline_rings(theme):
    markup = c.title_bar(theme, 60)
    rings = re.findall(
        rf'<circle cx="(\d+)" cy="60" r="5" fill="none" stroke="{theme.hairline}"',
        markup)
    assert [int(x) for x in rings] == [c.FRAME_L + 28, c.FRAME_L + 48, c.FRAME_L + 68]
    assert f'fill="{theme.surface}"' in markup
    assert theme.accent not in markup           # the accent is state, not chrome


def test_the_title_bar_sits_on_the_frames_rounded_cap():
    markup = c.title_bar(c.LIGHT, c.MARGIN + 24)
    assert arcs(fill_path(markup)) == [(c.R_CARD, c.R_CARD, c.R_CARD),
                                       (c.R_CARD, c.R_CARD, -c.R_CARD)]
    assert f'<line x1="{c.FRAME_L}"' in markup and f'x2="{c.FRAME_R}"' in markup


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_a_heading_rules_the_content_width_and_emphasises_its_start(theme):
    markup = c.heading(theme, 100, "stack")
    assert f'x1="{c.TEXT_X}" y1="116" x2="{c.CONTENT_R}" y2="116" ' \
           f'stroke="{theme.hairline}"' in markup
    assert f'x2="{c.TEXT_X + 120}" y2="116" stroke="{theme.ink}"' in markup


def test_a_heading_right_aligns_its_counter_in_mono():
    markup = c.heading(c.LIGHT, 100, "stack", "12 repos")
    assert f'<text x="{c.CONTENT_R}" y="100" text-anchor="end" ' \
           'class="mono dim">12 repos</text>' in markup
    assert 'class="heading ink"><tspan class="dim">~/</tspan>stack' in markup


def test_a_heading_without_a_counter_emits_no_second_text():
    assert c.heading(c.LIGHT, 100, "stack").count("<text") == 1


def test_a_heading_escapes_its_name_and_counter():
    markup = c.heading(c.LIGHT, 100, "<b>", '"x" & y')
    assert "<b>" not in markup
    assert "&lt;b&gt;" in markup and "&quot;x&quot; &amp; y" in markup


def test_headings_stay_inside_the_content_width():
    assert c.TEXT_X < c.CONTENT_R < c.FRAME_R


# --- stagger, grid, output -------------------------------------------------

def test_stagger_delays_each_row_a_step_further_and_skips_spacers():
    markup, y = c.stagger(['<text y="{y}"/>', None, '<text y="{y}"/>'], 100, 20)
    assert 'animation-delay:0.27s' in markup and 'animation-delay:0.39s' in markup
    assert markup.count('class="ln"') == 2
    assert y == 100 + 20 + 14 + 20
    assert "{y}" not in markup


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
