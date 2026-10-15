"""Tests for the panel registry and one theme's worth of rendered slices.

`render_theme` draws and reports; it writes nothing, so every test here runs
without a filesystem.
"""
import types

from tools.profile.present import console as c
from tools.profile.present import slices


def svg(desc="a description", width=c.W):
    """Minimal markup carrying the two things `describe` reads back out."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="40">'
            f'<desc id="d">{c.e(desc)}</desc></svg>')


def panel(result):
    """A stand-in for a panel module.

    `result` is either what every theme renders, or a callable taking the theme
    so one panel can answer differently per theme.
    """
    def render_(_cfg, _data, theme):
        return result(theme) if callable(result) else result
    return types.SimpleNamespace(render=render_)


def one(result):
    return [("p.svg", panel(result))]


# --- the panel registry ----------------------------------------------------

def test_the_frame_is_opened_by_the_header_and_closed_by_the_footer():
    """`top` and `bottom` are decided from position, not named by the panel."""
    assert slices.PANELS[0][0] == "header.svg"
    assert slices.PANELS[-1][0] == "footer.svg"


def test_every_registered_panel_can_render():
    assert all(callable(getattr(p, "render", None)) for _, p in slices.PANELS)


# --- slices_of -------------------------------------------------------------

def test_slices_of_wraps_bare_markup_under_the_registered_name():
    assert slices.slices_of("x.svg", "<svg/>") == [c.Slice("x.svg", "<svg/>")]


def test_slices_of_names_one_slice_per_entry_of_a_mapping():
    out = slices.slices_of("x.svg", {"a.svg": "<svg>a</svg>", "b.svg": "<svg>b</svg>"})
    assert [(s.file, s.markup) for s in out] == [("a.svg", "<svg>a</svg>"),
                                                 ("b.svg", "<svg>b</svg>")]


def test_slices_of_leaves_a_mapping_unlinked():
    """A panel that spells its parts as a dict is saying none of them link."""
    out = slices.slices_of("x.svg", {"a.svg": "<svg/>"})
    assert all(s.href is None for s in out)


def test_slices_of_passes_slices_through_untouched():
    given = [c.Slice("a.svg", "<svg/>", "https://example.com/1")]
    assert slices.slices_of("x.svg", given) == given


def test_slices_of_turns_a_plain_tuple_into_a_slice():
    out = slices.slices_of("x.svg", [("a.svg", "<svg/>")])
    assert out == [c.Slice("a.svg", "<svg/>")]
    assert isinstance(out[0], c.Slice)


def test_slices_of_keeps_the_href_of_a_plain_tuple():
    out = slices.slices_of("x.svg", [("a.svg", "<svg/>", "https://example.com/1")])
    assert out[0].href == "https://example.com/1"


def test_slices_of_accepts_a_mix_of_slices_and_tuples():
    out = slices.slices_of("x.svg", [c.Slice("a.svg", "<svg/>"), ("b.svg", "<svg/>")])
    assert [s.file for s in out] == ["a.svg", "b.svg"]
    assert all(isinstance(s, c.Slice) for s in out)


def test_slices_of_drains_a_generator():
    """A panel may yield its slices rather than build a list."""
    out = slices.slices_of("x.svg", (c.Slice(f"{i}.svg", "<svg/>") for i in range(3)))
    assert [s.file for s in out] == ["0.svg", "1.svg", "2.svg"]


def test_slices_of_a_panel_that_rendered_nothing():
    assert slices.slices_of("x.svg", []) == []


# --- render_theme ----------------------------------------------------------

def test_render_theme_returns_the_markup_the_panel_drew():
    markup = svg("the real one")
    assert slices.render_theme({}, {}, c.LIGHT, one(markup))[0][:2] == ("p.svg", markup)


def test_render_theme_names_a_slice_that_asked_for_a_subdirectory():
    out = slices.render_theme({}, {}, c.LIGHT, one({"links/mail.svg": svg()}))
    assert [f for f, _, _ in out] == ["links/mail.svg"]


def test_render_theme_reports_the_panels_own_desc():
    """The alt text is read back out of the markup, never supplied beside it."""
    out = slices.render_theme({}, {}, c.LIGHT, one(svg("what it draws")))
    assert [row["desc"] for _, _, row in out] == ["what it draws"]


def test_render_theme_unescapes_the_desc_it_reports():
    out = slices.render_theme({}, {}, c.LIGHT, one(svg('5 "starred" & forked')))
    assert out[0][2]["desc"] == '5 "starred" & forked'


def test_render_theme_reads_the_width_off_a_real_slice():
    """Guards the manifest against a panel whose geometry the test fakes."""
    half = c.slice_svg(c.LIGHT, 40, "", title="T", desc="half",
                       width=c.W // 2, rails="left")
    out = slices.render_theme({}, {}, c.LIGHT, one(half))
    assert out[0][2] == {"file": "p.svg", "desc": "half", "width": "50%"}


def test_render_theme_carries_an_href_only_when_the_slice_has_one():
    out = slices.render_theme({}, {}, c.LIGHT, one([
        c.Slice("a.svg", svg(), "https://example.com/1"),
        c.Slice("b.svg", svg()),
    ]))
    assert out[0][2]["href"] == "https://example.com/1"
    assert "href" not in out[1][2]


def test_render_theme_keeps_the_rows_in_panel_order():
    out = slices.render_theme({}, {}, c.LIGHT, [
        ("first.svg", panel(svg())),
        ("second.svg", panel({"a.svg": svg(), "b.svg": svg()})),
        ("third.svg", panel(svg())),
    ])
    assert [f for f, _, _ in out] == ["first.svg", "a.svg", "b.svg", "third.svg"]


def test_render_theme_hands_the_panel_the_config_the_theme_and_the_data():
    seen = []

    def render_(cfg, data, theme):
        seen.append((cfg, data, theme))
        return svg()

    slices.render_theme({"identity": {}}, {"stats": {"n": 1}}, c.DARK,
                        [("p.svg", types.SimpleNamespace(render=render_))])
    assert seen == [({"identity": {}}, {"stats": {"n": 1}}, c.DARK)]


def test_render_theme_draws_each_theme_with_its_own_palette():
    out = slices.render_theme({}, {}, c.DARK, one(lambda t: svg(f"for {t.name}")))
    assert out[0][2]["desc"] == "for dark"
