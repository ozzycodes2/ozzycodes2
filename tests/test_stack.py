"""Tests for the stack chips, whose widths are measured rather than guessed."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import stack

CFG = {"stack": {
    "Languages": ["Java", "Python", "TypeScript", "Swift", "Shell"],
    "Platform": ["Kubernetes", "Terraform", "Helm", "ArgoCD", "Docker"],
    "Cloud": ["AWS", "EKS", "Grafana", "Prometheus"],
    "Tooling": ["Claude Code", "MCP", "Git", "Just", "Neovim"],
}}

TOTAL = sum(len(v) for v in CFG["stack"].values())


@pytest.fixture(scope="module")
def markup():
    return stack.render(CFG, {}, c.LIGHT)


def chips(markup):
    """(x, y, width, label) of every chip, in draw order."""
    found = re.findall(
        rf'<rect x="([\d.]+)" y="(\d+)" width="([\d.]+)" height="{stack.CHIP_H}"[^>]*/>'
        r'<text x="[\d.]+" y="\d+" class="mono ink" style="font-size:[\d.]+px">([^<]*)</text>',
        markup)
    return [(float(x), int(y), float(w), label) for x, y, w, label in found]


def faces(markup):
    """How each chip is painted, as the attributes that follow its geometry."""
    return re.findall(
        rf'<rect x="[\d.]+" y="\d+" width="[\d.]+" height="{stack.CHIP_H}" ([^/]*)/>',
        markup)


def height_of(markup):
    return int(re.search(r'height="(\d+)"', markup).group(1))


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert height_of(markup) % c.ROW == 0
    edges = re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="{c.EDGE_W}"',
                      markup).group(1)
    assert "H" not in edges


def test_height_grows_with_the_number_of_categories():
    one = stack.render({"stack": {"Cloud": ["AWS"]}}, {}, c.LIGHT)
    assert height_of(markup := stack.render(CFG, {}, c.LIGHT)) > height_of(one)
    assert height_of(markup) % c.ROW == 0


# --- chip geometry ---------------------------------------------------------

def test_chip_width_is_derived_from_the_label_length(markup):
    """The mono face advances a fixed fraction of its size per glyph, which is
    the only reason a width can be known before the text is drawn."""
    assert stack.CHAR_W == stack.CHIP_FS * c.MONO_ADVANCE
    for _, _, w, label in chips(markup):
        assert w == pytest.approx(len(label) * stack.CHAR_W + 2 * stack.CHIP_PAD, abs=0.1)
    assert stack._chip_w("MCP") < stack._chip_w("Kubernetes")


def test_no_chip_runs_past_the_content_edge(markup):
    assert stack.CHIP_R == c.CONTENT_R
    for x, _, w, label in chips(markup):
        assert x + w <= stack.CHIP_R, label


def test_no_chip_starts_inside_the_category_gutter(markup):
    for x, _, _, _ in chips(markup):
        assert x >= stack.CHIP_L


def test_chips_in_a_line_never_overlap(markup):
    by_line = {}
    for x, y, w, label in chips(markup):
        by_line.setdefault(y, []).append((x, w))
    for row in by_line.values():
        row.sort()
        for (x, w), (nx, _) in zip(row, row[1:]):
            assert x + w <= nx


def test_a_category_wider_than_the_row_wraps_instead_of_clipping():
    long = {"stack": {"Everything": [f"item-{i:02d}" for i in range(24)]}}
    drawn = chips(stack.render(long, {}, c.LIGHT))
    lines = sorted({y for _, y, _, _ in drawn})
    assert len(lines) > 1
    assert [b - a for a, b in zip(lines, lines[1:])] == [stack.LINE_PITCH] * (len(lines) - 1)
    for x, _, w, label in drawn:
        assert x + w <= stack.CHIP_R, label
    # Every wrapped line restarts at the first chip column.
    assert {min(x for x, y, _, _ in drawn if y == line) for line in lines} == {stack.CHIP_L}


def test_a_wrapped_category_pushes_the_panel_taller():
    long = {"stack": {"Everything": [f"item-{i:02d}" for i in range(24)]}}
    assert height_of(stack.render(long, {}, c.LIGHT)) > \
        height_of(stack.render({"stack": {"Everything": ["one"]}}, {}, c.LIGHT))


def test_a_single_item_too_wide_for_any_line_is_truncated():
    """Wrapping cannot rescue one over-long chip, so it is clipped instead."""
    drawn = chips(stack.render({"stack": {"Long": ["AWS", "x" * 200]}}, {}, c.LIGHT))
    assert len(drawn) == 2
    assert drawn[1][1] > drawn[0][1]        # pushed to a second line
    assert drawn[1][3].endswith("…")
    assert drawn[1][0] + drawn[1][2] <= stack.CHIP_R


# --- chip face -------------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_every_chip_is_drawn_exactly_like_every_other(theme):
    """Categories are told apart by their own label and the gutter rule, so no
    chip is tinted to mark the row it belongs to."""
    drawn = faces(stack.render(CFG, {}, theme))
    assert len(drawn) == TOTAL
    assert set(drawn) == {f'rx="{c.R_CONTROL}" fill="{theme.surface}" '
                          f'stroke="{theme.hairline}" stroke-width="{c.EDGE_W}"'}


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_panel_reaches_for_no_accent_at_all(theme):
    """The one accent in the console belongs to the stats panel's live dot."""
    # base_css declares `.accent` in every panel, so only the body is evidence.
    body = stack.render(CFG, {}, theme).split("</style>")[1]
    assert theme.accent not in body
    assert "accent" not in body


# --- rows ------------------------------------------------------------------

def test_categories_keep_their_toml_order(markup):
    labels = re.findall(r'text-anchor="end" class="caption dim">([^<]*)<', markup)
    assert labels == list(CFG["stack"])


def test_each_category_name_is_right_aligned_in_the_gutter(markup):
    assert markup.count(f'<text x="{stack.GUTTER_R}" y=') == len(CFG["stack"])


def test_every_item_appears_once(markup):
    drawn = [label for _, _, _, label in chips(markup)]
    assert drawn == [item for items in CFG["stack"].values() for item in items]


def test_the_counter_reports_the_total_item_count(markup):
    assert (f'<text x="{c.CONTENT_R}" y="{stack.HEAD_Y}" text-anchor="end" '
            f'class="mono dim">{TOTAL}</text>') in markup
    assert "[" not in c.visible(markup)


# --- accessibility and degrading -------------------------------------------

def test_desc_lists_every_category_and_item(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    for category, items in CFG["stack"].items():
        assert f"{category}: {', '.join(items)}" in desc


@pytest.mark.parametrize("cfg", [{}, {"stack": {}}])
def test_a_missing_stack_renders_one_short_panel_instead_of_raising(cfg):
    markup = stack.render(cfg, {}, c.LIGHT)
    assert height_of(markup) % c.ROW == 0 and height_of(markup) <= 120
    assert "no stack configured" in c.visible(markup)


def test_a_category_with_no_items_still_gets_its_label():
    markup = stack.render({"stack": {"Cloud": [], "Tooling": ["Git"]}}, {}, c.LIGHT)
    assert "Cloud" in c.visible(markup)
    assert len(chips(markup)) == 1
