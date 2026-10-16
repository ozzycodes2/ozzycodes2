"""Tests for the work-route timeline.

The type's one claim is that distance along the axis is time, so most of what is
checked here is position: that the scale is constant, that unequal intervals
arrive unequal, and that a role the author never dated is left out rather than
placed at the origin.
"""
import re

import pytest

from tools.profile.present import console as c
from tools.profile.present.panels import route

NOW = 2026 * 12 + 9          # 2026-10, the month the open tenure runs to

ROSTER = [
    {"org": "Northgate Systems", "title": "software engineer",
     "start": "2017-02", "end": "2019-08"},
    {"org": "Veridian Health", "title": "senior backend engineer",
     "start": "2019-09", "end": "2022-06"},
    {"org": "Lattice Freight", "title": "staff engineer, platform",
     "start": "2022-07", "end": "2024-02"},
    {"org": "Machinify", "title": "platform engineer", "start": "2024-03"},
]

CFG = {"route": ROSTER}
MONO = c.e(c.MONO_STACK)


def render(cfg=CFG, theme=c.LIGHT, now=NOW):
    return route.render(cfg, {}, theme, now=now)


def desc_of(svg):
    return re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1)


def height_of(svg):
    return int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))


def runs(svg):
    """(x0, x1, stroke) of every tenure, in draw order."""
    return [(float(a), float(b), s) for a, b, s in re.findall(
        rf'<line x1="([\d.]+)" y1="{route.AXIS_Y}" x2="([\d.]+)" '
        rf'y2="{route.AXIS_Y}" stroke="([^"]*)" stroke-width="{route.SEG_W}"', svg)]


def texts(svg):
    """(x, y, content) of every <text>, in draw order."""
    return [(float(x), int(y), body) for x, y, body in re.findall(
        r'<text x="([\d.]+)" y="(\d+)"[^>]*>(.*?)</text>', svg)]


@pytest.fixture(scope="module")
def out():
    return render()


# --- the scale ---------------------------------------------------------------

@pytest.mark.parametrize("value,months", [
    ("2017-02", 2017 * 12 + 1),
    ("2017", 2017 * 12),
    ("2017-12", 2017 * 12 + 11),
])
def test_a_date_reads_as_a_month_index(value, months):
    assert route.month_of(value) == months


@pytest.mark.parametrize("value", ["2017-13", "2017-00", "", None, "nope", "17-02",
                                   "2017-02-11"])
def test_a_date_the_panel_cannot_read_is_not_guessed_at(value):
    assert route.month_of(value) is None


@pytest.mark.parametrize("months,text", [(31, "2y 7mo"), (7, "7mo"), (12, "1y"),
                                         (0, "0mo"), (24, "2y")])
def test_a_tenure_reads_as_years_and_months(months, text):
    assert route.span_of(months) == text


def test_one_scale_runs_the_whole_axis(out):
    """Pixels per month has to be the same for every tenure, or the axis is
    decorative. The roster's runs are 31, 34, 20 and 31 months, so even spacing
    fails this rather than passing it by luck."""
    plan = route.layout(ROSTER, NOW)
    scales = [(x1 - x0) / r["months"]
              for (x0, x1, _), r in zip(runs(out), plan["rows"])]
    assert len(set(r["months"] for r in plan["rows"])) > 1
    assert max(scales) - min(scales) < 0.02


def test_the_span_fills_the_content_column_end_to_end(out):
    first, last = runs(out)[0], runs(out)[-1]
    assert first[0] == c.TEXT_X
    assert last[1] == c.CONTENT_R


def test_the_roster_is_sorted_by_date_whatever_order_it_arrives_in():
    shuffled = [ROSTER[2], ROSTER[0], ROSTER[3], ROSTER[1]]
    assert render({"route": shuffled}) == render()


def test_a_tenure_ends_at_the_close_of_the_month_it_names():
    """`end` is the last month held. Read as an instant the figure loses a month
    off every run and opens a gap between two roles that ran back to back."""
    plan = route.layout(ROSTER, NOW)
    assert plan["rows"][0]["months"] == 31
    assert plan["rows"][0]["x1"] == plan["rows"][1]["x0"]


def test_a_real_gap_between_two_roles_draws_as_one():
    plan = route.layout([
        {"org": "A", "title": "a", "start": "2017-01", "end": "2017-12"},
        {"org": "B", "title": "b", "start": "2019-01", "end": "2019-12"},
    ], NOW)
    assert plan["rows"][0]["x1"] < plan["rows"][1]["x0"]


def test_the_axis_is_ticked_once_a_year(out):
    """The only scale annotation it carries: the heading counts the span and
    every label carries its own dates."""
    ticks = re.findall(rf'<line x1="([\d.]+)" y1="{route.AXIS_Y - route.TICK}" '
                       rf'x2="[\d.]+" y2="{route.AXIS_Y + route.TICK}"', out)
    assert len(ticks) == 2026 - 2018 + 1          # 2017-02 opens inside 2017
    assert all(c.TEXT_X <= float(x) <= c.CONTENT_R for x in ticks)


def test_a_lone_role_dated_to_one_month_does_not_divide_by_zero():
    plan = route.layout([{"org": "A", "title": "a", "start": "2026-10"}], NOW)
    assert plan["rows"][0]["x0"] == plan["rows"][0]["x1"] == c.TEXT_X


# --- the marked tenure -------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_role_still_held_is_the_one_marked_datum(theme):
    """Rule 6: one mark per panel. The milestone circle the type reference would
    also paint in the accent stays in the ink — a second mark on the same event
    spends the budget twice — so size carries it instead."""
    svg = render(theme=theme)
    accented = [r for r in runs(svg) if r[2] == theme.accent]
    assert len(accented) == 1
    assert accented[0] == runs(svg)[-1]
    assert svg.count(theme.accent) == 2          # the section rule, and this run


def test_a_roster_with_no_open_tenure_marks_nothing_but_the_rule():
    """Every role dated to the past is a set of equals; `~/projects` gets the
    same treatment."""
    closed = [{**r, "end": r.get("end", "2026-01")} for r in ROSTER]
    svg = render({"route": closed})
    assert svg.count(c.LIGHT.accent) == 1
    assert not [r for r in runs(svg) if r[2] == c.LIGHT.accent]


def test_the_accent_never_sets_type(out):
    """It is corrected to 3:1, the threshold for an object. The header's one
    proper noun is the window's only exception and it is not this panel's."""
    assert f'fill="{c.LIGHT.accent}"' not in re.sub(r"<line[^>]*>", "", out)
    assert "<tspan" not in out


# --- the labels --------------------------------------------------------------

def test_a_label_block_is_three_tiers_in_one_reading_order(out):
    """Eyebrow, employer, title from the top, whichever side it falls on, so a
    label means the same thing wherever it sits."""
    block = [t for t in texts(out) if t[1] in
             [route.AXIS_Y + dy for dy in route.ABOVE]][:3]
    assert [b for _, _, b in block] == [
        "2017-02 .. 2019-08", "Northgate Systems", "software engineer"]
    sizes = re.findall(r'font-size="(\d+)"[^>]*>(?:2017-02|Northgate|software)', out)
    assert sizes == [str(route.EYEBROW), str(route.NAME), str(route.SUBLABEL)]


def test_the_labels_alternate_above_and_below_the_axis(out):
    """Two roles a few months apart would otherwise collide."""
    plan = route.layout(ROSTER, NOW)
    assert [r["above"] for r in plan["rows"]] == [True, False, True, False]
    ys = {y for _, y, _ in texts(out) if y > c.HEAD_Y + c.CMD_DY}
    assert ys == {route.AXIS_Y + dy for dy in route.ABOVE + route.BELOW}


def test_each_event_is_bound_to_its_label_by_a_drop(out):
    """The line is what makes a block belong to a circle rather than to the one
    beside it, so it takes the traced tier rather than the hairline."""
    ends = {side: tuple(route.AXIS_Y + dy for dy in side)
            for side in (route.DROP_ABOVE, route.DROP_BELOW)}
    drops = [(x, (int(a), int(b))) for x, a, b in re.findall(
        r'<line x1="([\d.]+)" y1="(\d+)" x2="\1" y2="(\d+)" '
        rf'stroke="{c.LIGHT.faint}"', out) if (int(a), int(b)) in ends.values()]
    rows = route.layout(ROSTER, NOW)["rows"]
    assert [x for x, _ in drops] == [str(route._n(r["x0"])) for r in rows]
    assert [ys for _, ys in drops] == [
        ends[route.DROP_ABOVE if r["above"] else route.DROP_BELOW] for r in rows]


def test_a_late_role_carries_its_label_back_off_the_right_rail():
    """Mono advances 0.6em, so the block's extent is known before it is drawn."""
    svg = render({"route": [
        {"org": "Early", "title": "a", "start": "2017-02", "end": "2026-08"},
        {"org": "Late", "title": "distributed systems engineer", "start": "2026-09"},
    ]})
    widest = len("distributed systems engineer") * route.SUBLABEL * c.MONO_ADVANCE
    assert route._n(c.CONTENT_R - widest) in [x for x, _, _ in texts(svg)]
    assert max(x for x, _, _ in texts(svg)) <= c.CONTENT_R


def test_the_eyebrows_tracking_counts_toward_its_own_width():
    """It is the widest line in a block whose employer and title are both short,
    and 18 characters of tracking is nine pixels the clamp would otherwise miss.
    """
    svg = render({"route": [
        {"org": "A", "title": "b", "start": "2017-02", "end": "2026-08"},
        {"org": "C", "title": "d", "start": "2026-09", "end": "2026-10"},
    ]})
    width = len("2026-09 .. 2026-10") * (route.EYEBROW * c.MONO_ADVANCE + 0.5)
    assert route._n(c.CONTENT_R - width) in [x for x, _, _ in texts(svg)]


def test_every_run_stays_inside_the_content_column(out):
    assert all(c.TEXT_X <= x <= c.CONTENT_R for x, _, _ in texts(out))


# --- the frame ---------------------------------------------------------------

def test_the_slice_is_a_whole_number_of_grid_rows(out):
    assert route.HEIGHT % c.ROW == 0
    assert height_of(out) == route.HEIGHT


def test_the_height_is_a_property_of_the_frame_not_of_the_roster():
    """A role added or dropped must not move every section below this one."""
    one = render({"route": [ROSTER[-1]]})
    assert height_of(one) == route.HEIGHT
    assert len(runs(one)) == 1


def test_the_slice_continues_the_rails(out):
    """Only the header caps the top and only the footer the bottom."""
    assert f'M{c.FRAME_L} {route.HEIGHT}V0M{c.FRAME_R} 0V{route.HEIGHT}' in out
    assert f"a{c.R_CARD} {c.R_CARD}" not in out


def test_nothing_rides_up_into_the_command_transcript(out):
    """The axis block clears the quoted command by the height of a label."""
    above = min(y for _, y, _ in texts(out) if y > c.HEAD_Y + c.CMD_DY)
    assert above - (c.HEAD_Y + c.CMD_DY) >= 20


def test_the_heading_names_the_span_and_the_command_that_produced_it(out):
    """Rule 14: a section drawn from curated files has no source to cite, so it
    takes a command in the window's own voice."""
    assert "2017 — 2026" in out
    assert "traceroute --since=2017" in out


# --- degrading ---------------------------------------------------------------

@pytest.mark.parametrize("cfg", [{}, {"route": None}, {"route": []}])
def test_an_unconfigured_roster_renders_a_short_slice_rather_than_raising(cfg):
    svg = route.render(cfg, {}, c.LIGHT)
    assert "no route configured" in c.visible(svg.split("</style>", 1)[-1])
    assert desc_of(svg) == "No route is configured: 0 roles."
    assert height_of(svg) % c.ROW == 0
    assert not runs(svg)


@pytest.mark.parametrize("entry", [
    {"org": "Undated", "title": "b"},
    {"org": "Undated", "title": "b", "start": "whenever"},
    {"org": "Undated", "title": "b", "start": "2020-01", "end": "2019-01"},
])
def test_a_role_the_panel_cannot_place_is_dropped_rather_than_guessed_at(entry):
    """At the origin it would read as the start of the career, which is the one
    thing the axis claims to say."""
    svg = render({"route": [{"org": "Dated", "title": "a", "start": "2020-01"}, entry]})
    assert "Dated" in svg
    assert "Undated" not in svg


def test_a_roster_that_dates_none_of_its_roles_degrades():
    svg = render({"route": [{"org": "A", "title": "a"}]})
    assert "no route configured" in c.visible(svg.split("</style>", 1)[-1])


def test_route_escapes_markup_in_an_employers_name():
    svg = render({"route": [{"org": 'A <b>& "B"', "title": "a", "start": "2020-01"}]})
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_the_open_tenure_dates_itself_from_the_clock():
    """The only thing in this panel that is not config."""
    later = render(now=NOW + 12)
    assert later != render()
    assert "2024-03 .. now" in later


# --- colour and alt text -------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_route_takes_every_paint_from_the_theme(theme):
    svg = render(theme=theme)
    assert f'fill="{theme.canvas}"' in svg
    assert f'stroke="{theme.hairline}"' in svg
    assert not re.search(r'(fill|stroke)="#(?!'
                         + "|".join(v.lstrip("#") for v in theme[1:]) + r')', svg)


def test_the_two_themes_differ_in_nothing_but_colour():
    light, dark = (render(theme=theme) for theme in c.THEMES)
    for role, value in zip(c.LIGHT._fields, c.LIGHT):
        if role != "name":
            light = light.replace(value, role)
    for role, value in zip(c.DARK._fields, c.DARK):
        if role != "name":
            dark = dark.replace(value, role)
    assert light == dark


def test_desc_names_every_role_the_figure_draws(out):
    """It is the README's alt text, and the only place a screen reader finds the
    tenures the drawing states as length."""
    desc = desc_of(out)
    assert desc.startswith("4 roles from 2017 to 2026,")
    for r in ROSTER:
        assert r["org"] in desc and r["title"] in desc
    assert "2024-03 .. now (2y 7mo)" in desc


def test_route_is_deterministic(out):
    """The daily job commits only when a byte changed, so renders must repeat."""
    assert render() == render()


def test_nothing_animates(out):
    assert "animation" not in out.split("</style>", 1)[-1]
    assert 'class="live"' not in out
