"""Tests for the stack chips, whose widths are measured rather than guessed."""
import re

import pytest

from tools.profile import console as c
from tools.profile.panels import stack

CFG = {"stack": {
    "Languages": ["Java", "Rust", "Python", "TypeScript", "Swift", "Shell"],
    "Platform": ["Kubernetes", "Terraform", "Helm", "ArgoCD", "Docker"],
    "Cloud": ["AWS", "EKS", "Grafana", "Prometheus"],
    "Tooling": ["Claude Code", "MCP", "Git", "Just", "Neovim"],
}}

TOTAL = sum(len(v) for v in CFG["stack"].values())

# One chip: the capsule and the label inside it are emitted as one run, which is
# what lets a single pattern read back the geometry and the paint together.
CHIP = (rf'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="{stack.CHIP_H}" ([^/]*)/>'
        r'<text x="(\d+)" y="(\d+)" fill="([^"]+)" font-family="[^"]*" '
        r'font-size="(\d+)">([^<]*)</text>')


@pytest.fixture(scope="module")
def markup():
    return stack.render(CFG, {}, c.LIGHT)


def chips(markup):
    """(x, baseline, width, label) of every chip, in draw order."""
    return [(int(m[0]), int(m[1]) + 16, int(m[2]), m[8])
            for m in re.findall(CHIP, markup)]


def faces(markup):
    """How each chip is painted: the capsule's fill and the label's type."""
    return [(m[3], m[6], m[7]) for m in re.findall(CHIP, markup)]


def labels(markup):
    """(x, y, letter-spacing, size, text) of every category label."""
    return re.findall(
        r'<text x="(\d+)" y="(\d+)" fill="[^"]+" font-family="[^"]*" '
        r'font-size="(\d+)" letter-spacing="([\d.]+)">([a-z ]+)</text>',
        markup)


def height_of(markup):
    return int(re.search(r'height="(\d+)"', markup).group(1))


def body_of(markup):
    """The drawing, without the <style> block the embedded fonts live in."""
    return markup.split("</style>")[1]


# --- frame -----------------------------------------------------------------

def test_height_is_on_the_grid_and_the_frame_stays_open(markup):
    assert height_of(markup) % c.ROW == 0
    edges = re.search(rf'<path d="([^"]*)" fill="none" stroke="[^"]+" stroke-width="{c.RAIL_W}"',
                      markup).group(1)
    assert "H" not in edges


def test_height_grows_with_the_number_of_categories(markup):
    one = stack.render({"stack": {"Cloud": ["AWS"]}}, {}, c.LIGHT)
    assert height_of(markup) > height_of(one)
    assert height_of(one) % c.ROW == 0


def test_a_wrapped_category_pushes_the_panel_taller():
    """A wrap costs a line, so the slice below it has to grow by one too."""
    long = {"stack": {"Everything": [f"item-{i:02d}" for i in range(24)]}}
    assert height_of(stack.render(long, {}, c.LIGHT)) > \
        height_of(stack.render({"stack": {"Everything": ["one"]}}, {}, c.LIGHT))


# --- chip geometry ---------------------------------------------------------

def test_chip_width_is_derived_from_the_label_length(markup):
    """The mono face advances a fixed fraction of its size per glyph, which is
    the only reason a width can be known before the text is drawn."""
    assert stack.CHAR_W == stack.CHIP_FS * c.MONO_ADVANCE
    for _, _, w, label in chips(markup):
        assert w == round(len(label) * stack.CHAR_W) + 2 * stack.CHIP_PAD
    assert stack._chip_w("MCP") < stack._chip_w("Kubernetes")


def test_the_label_sits_one_inset_inside_its_capsule(markup):
    for m in re.findall(CHIP, markup):
        assert int(m[4]) == int(m[0]) + stack.CHIP_PAD


def test_no_chip_runs_past_the_content_edge(markup):
    for x, _, w, label in chips(markup):
        assert x + w <= c.CONTENT_R, label


def test_chips_start_right_of_the_label_column(markup):
    for x, _, _, _ in chips(markup):
        assert x >= c.TEXT_X + stack.LABEL_W


def test_chips_on_one_line_never_overlap(markup):
    by_line = {}
    for x, y, w, _ in chips(markup):
        by_line.setdefault(y, []).append((x, w))
    for row in by_line.values():
        row.sort()
        for (x, w), (nx, _) in zip(row, row[1:]):
            assert x + w + stack.CHIP_GAP <= nx


def test_a_category_wider_than_the_row_wraps_instead_of_overrunning():
    long = {"stack": {"Everything": [f"item-{i:02d}" for i in range(24)]}}
    drawn = chips(stack.render(long, {}, c.LIGHT))
    assert len(drawn) == 24
    lines = sorted({y for _, y, _, _ in drawn})
    assert len(lines) > 1
    assert [b - a for a, b in zip(lines, lines[1:])] == [stack.WRAP_STEP] * (len(lines) - 1)
    for x, _, w, label in drawn:
        assert x + w <= c.CONTENT_R, label
    # Every wrapped line restarts at the first chip column.
    assert {min(x for x, y, _, _ in drawn if y == line) for line in lines} \
        == {c.TEXT_X + stack.LABEL_W}


def test_a_wrap_moves_the_categories_below_it_down():
    """The wrap spends a line out of the same running baseline the next
    category measures from, so the two can never collide."""
    narrow = stack.render({"stack": {"A": ["one"], "B": ["two"]}}, {}, c.LIGHT)
    wide = stack.render(
        {"stack": {"A": [f"item-{i:02d}" for i in range(24)], "B": ["two"]}},
        {}, c.LIGHT)
    wraps = len({y for _, y, _, label in chips(wide) if label != "two"}) - 1
    assert wraps, "the fixture is meant to wrap"
    assert chips(wide)[-1][1] - chips(narrow)[-1][1] == stack.WRAP_STEP * wraps


# --- type and paint --------------------------------------------------------

@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_every_chip_is_drawn_exactly_like_every_other(theme):
    """Categories are told apart by their own label, so no chip is tinted to
    mark the row it belongs to."""
    drawn = faces(stack.render(CFG, {}, theme))
    assert len(drawn) == TOTAL
    assert set(drawn) == {(f'rx="{c.R_CHIP}" fill="{theme.surface}" '
                           f'stroke="{theme.hairline}" stroke-width="{c.EDGE_W}"',
                           theme.dim, str(stack.CHIP_FS))}


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_label_is_a_tier_quieter_than_the_chips_it_names(theme):
    """Two text tiers under the heading: the chips carry the content in `dim`
    at 13, the category naming them is `faint` at 11."""
    drawn = stack.render(CFG, {}, theme)
    assert {(size, ls) for _, _, size, ls, _ in labels(drawn)} \
        == {(str(stack.LABEL_FS), "0.5")}
    assert drawn.count(f'font-size="{stack.LABEL_FS}" letter-spacing="0.5"') \
        == len(CFG["stack"])
    for _, _, size, _, text in labels(drawn):
        assert f'fill="{theme.faint}" font-family="{c.e(c.MONO_STACK)}" ' \
               f'font-size="{size}"' in drawn
    assert theme.faint != theme.dim


@pytest.mark.parametrize("theme", c.THEMES, ids=lambda t: t.name)
def test_the_panel_reaches_for_no_accent_at_all(theme):
    """The one accent in the console belongs to the header's live dot."""
    body = body_of(stack.render(CFG, {}, theme))
    assert theme.accent not in body
    assert "accent" not in body


def test_both_themes_draw_the_same_geometry():
    """render.py pairs the two files element for element, so the only
    difference between them may be which role each paint names."""
    def roles(theme):
        drawn = body_of(stack.render(CFG, {}, theme))
        for role in theme._fields[1:]:
            drawn = drawn.replace(getattr(theme, role), f"${role}")
        return drawn
    assert roles(c.LIGHT) == roles(c.DARK)


# --- rows ------------------------------------------------------------------

def test_categories_keep_their_toml_order_in_the_left_column(markup):
    drawn = labels(markup)
    assert [text for *_, text in drawn] == [k.lower() for k in CFG["stack"]]
    assert {int(x) for x, *_ in drawn} == {c.TEXT_X}


def test_each_label_shares_a_baseline_with_its_first_chip(markup):
    firsts = []
    seen = 0
    for items in CFG["stack"].values():
        firsts.append(chips(markup)[seen][1])
        seen += len(items)
    assert [int(y) for _, y, *_ in labels(markup)] == firsts


def test_every_item_appears_once_in_order(markup):
    assert [label for *_, label in chips(markup)] == \
        [item for items in CFG["stack"].values() for item in items]


def test_the_counter_reports_the_tool_count(markup):
    assert f'text-anchor="end">{TOTAL} tools</text>' in markup


# --- accessibility and degrading -------------------------------------------

def test_desc_names_every_category_and_how_many_it_holds(markup):
    desc = re.search(r'<desc id="d">([^<]*)</desc>', markup).group(1)
    assert desc.startswith(f"{TOTAL} tools across {len(CFG['stack'])} categories:")
    for category, items in CFG["stack"].items():
        assert f"{category} ({len(items)})" in desc


@pytest.mark.parametrize("cfg", [{}, {"stack": {}}, {"stack": None}])
def test_a_missing_stack_renders_one_short_panel_instead_of_raising(cfg):
    markup = stack.render(cfg, {}, c.LIGHT)
    assert height_of(markup) % c.ROW == 0 and height_of(markup) <= 120
    assert "no stack configured" in c.visible(markup)
    assert chips(markup) == []


def test_a_category_with_no_items_still_gets_its_label():
    markup = stack.render({"stack": {"Cloud": [], "Tooling": ["Git"]}}, {}, c.LIGHT)
    assert [text for *_, text in labels(markup)] == ["cloud", "tooling"]
    assert len(chips(markup)) == 1
