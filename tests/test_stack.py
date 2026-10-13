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


@pytest.fixture(scope="module")
def markup():
    return stack.render(CFG, {})


def chips(markup):
    """(x, y, width, label) of every chip, in draw order."""
    found = re.findall(
        r'<rect x="([\d.]+)" y="(\d+)" width="([\d.]+)" height="24"[^>]*/>'
        r'<text x="[\d.]+" y="\d+" class="fg" style="font-size:[\d.]+px">([^<]*)</text>',
        markup)
    return [(float(x), int(y), float(w), label) for x, y, w, label in found]


def height_of(markup):
    return int(re.search(r'height="(\d+)"', markup).group(1))


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert height_of(markup) % c.ROW == 0
    edges = re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="{c.EDGE_W}"',
                      markup).group(1)
    assert "H" not in edges


def test_height_grows_with_the_number_of_categories():
    one = stack.render({"stack": {"Cloud": ["AWS"]}}, {})
    assert height_of(markup := stack.render(CFG, {})) > height_of(one)
    assert height_of(markup) % c.ROW == 0


# --- chip geometry ---------------------------------------------------------

def test_chip_width_is_derived_from_the_label_length(markup):
    for _, _, w, label in chips(markup):
        assert w == pytest.approx(len(label) * stack.CHAR_W + 2 * stack.CHIP_PAD, abs=0.1)
    assert stack._chip_w("MCP") < stack._chip_w("Kubernetes")


def test_no_chip_runs_past_the_content_edge(markup):
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
    drawn = chips(stack.render(long, {}))
    lines = sorted({y for _, y, _, _ in drawn})
    assert len(lines) > 1
    assert [b - a for a, b in zip(lines, lines[1:])] == [stack.LINE_PITCH] * (len(lines) - 1)
    for x, _, w, label in drawn:
        assert x + w <= stack.CHIP_R, label
    # Every wrapped line restarts at the first chip column.
    assert {min(x for x, y, _, _ in drawn if y == line) for line in lines} == {stack.CHIP_L}


def test_a_wrapped_category_pushes_the_panel_taller():
    long = {"stack": {"Everything": [f"item-{i:02d}" for i in range(24)]}}
    assert height_of(stack.render(long, {})) > \
        height_of(stack.render({"stack": {"Everything": ["one"]}}, {}))


def test_a_single_item_too_wide_for_any_line_is_truncated():
    """Wrapping cannot rescue one over-long chip, so it is clipped instead."""
    drawn = chips(stack.render({"stack": {"Long": ["AWS", "x" * 200]}}, {}))
    assert len(drawn) == 2
    assert drawn[1][1] > drawn[0][1]        # pushed to a second line
    assert drawn[1][3].endswith("…")
    assert drawn[1][0] + drawn[1][2] <= stack.CHIP_R


# --- rows ------------------------------------------------------------------

def test_categories_keep_their_toml_order(markup):
    labels = re.findall(r'text-anchor="end" class="faint" style="font-size:13px">([^<]*)<',
                        markup)
    assert labels == list(CFG["stack"])


def test_each_category_name_is_right_aligned_in_the_gutter(markup):
    assert markup.count(f'<text x="{stack.GUTTER_R}" y=') == len(CFG["stack"])


def test_every_item_appears_once(markup):
    drawn = [label for _, _, _, label in chips(markup)]
    assert drawn == [item for items in CFG["stack"].values() for item in items]


def test_adjacent_categories_are_tinted_differently(markup):
    rows = re.findall(r'<text x="156"[^>]*>([^<]*)</text>\s*<rect[^>]*stroke="(#[0-9a-f]{6})"',
                      markup)
    colours = [colour for _, colour in rows]
    assert colours == [c.ACCENT, c.ALT, c.ACCENT, c.ALT]


def test_the_counter_reports_the_total_item_count(markup):
    assert f"[ {sum(len(v) for v in CFG['stack'].values())} ]" in c.visible(markup)


# --- accessibility and degrading -------------------------------------------

def test_desc_lists_every_category_and_item(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    for category, items in CFG["stack"].items():
        assert f"{category}: {', '.join(items)}" in desc


@pytest.mark.parametrize("cfg", [{}, {"stack": {}}])
def test_a_missing_stack_renders_one_short_panel_instead_of_raising(cfg):
    markup = stack.render(cfg, {})
    assert height_of(markup) % c.ROW == 0 and height_of(markup) <= 120
    assert "no stack configured" in c.visible(markup)


def test_a_category_with_no_items_still_gets_its_label():
    markup = stack.render({"stack": {"Cloud": [], "Tooling": ["Git"]}}, {})
    assert "Cloud" in c.visible(markup)
    assert len(chips(markup)) == 1
