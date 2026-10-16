# Panel contract

Each panel is one module exposing `render(cfg, data, theme)`, returning a
complete SVG document. `../slices.py` lists them in display order and the data
layer writes each to `assets/<theme>/<name>.svg`, once per theme; the README
stacks them with consecutive `<picture>` tags so they read as one continuous
window.

A panel is presentation and nothing else: it opens no file and makes no
request. Everything it draws arrives in `cfg` and `data`, which `render.py`
assembles before any panel runs. `tests/test_layers.py` fails the run if a
module here imports the data layer.

A panel whose parts must be separately clickable returns a list of `Slice`s
instead — it names its own files and supplies their `href`s. See rule 10.

## API

```python
from .. import console as c

def render(cfg, data, theme):
    ...
    return c.slice_svg(theme, height, body, title=..., desc=...)
```

- `cfg` — the hand-written content: parsed `profile.toml`, plus `stack`,
  `languages` and `logos` folded in from their own files. A panel reading one of
  those three is reading config, not data, and draws the same figure on a
  machine that has never fetched.
- `data` — `{stem: parsed json}` for every file in `data/`: `stats`, `calendar`,
  `projects`. A panel must tolerate a missing key.
- `theme` — a `Theme`. Every colour the panel draws comes from here.

### `console` exports

| Name | Purpose |
|---|---|
| `slice_svg(theme, height, body, *, title, desc, text="", top=False, bottom=False, css="", defs="", width=W, rails="both")` | Wraps body markup in the frame. `height` **must** be a multiple of `ROW` (40). `title`/`desc` are the accessible name and description. `text` lists glyphs the body needs but does not literally contain. `width`/`rails` cut one row into side-by-side files — see rule 10. |
| `tx(x, y, text, *, fill, family, size, weight=None, ls=None, anchor=None)` | One `<text>` element, escaped, typed by presentation attribute. The way a panel draws a label. `family` is `MONO_STACK` or `SANS_STACK`. |
| `ago(when, now=None)` | `"today"`, `"9d ago"`, `"14mo ago"`, `"3y ago"` for an ISO-8601 instant; `""` for a missing or unparseable one. Fits a card corner; use it rather than formatting dates in a panel. |
| `num(value)` | Thousands-separated integer, for counters set in mono. |
| `mix(a, b, t)` | `t` of colour `a` over `b`, as a literal hex. The way to get a shade between the theme's ink and its canvas. |
| `contrast(a, b)` | WCAG ratio between two `#rrggbb` colours. The frame needs none of this — the theme roles are already corrected. A panel needs it only when it paints something the design system never declared, as `~/stack` does with twenty brand hexes. |
| `Slice(file, markup, href=None)` | One output file, and the URL the README should wrap it in. `file` is a path *within* a theme directory. See rule 10. |
| `title_bar(theme, label)` | Window chrome, with `label` centred in mono 12. Header panel only. Takes no y: the band caps the frame, so it shares the frame's top edge and radius. Its content ends at `MARGIN + TITLE_H`. There is no mirror at the foot: this window has one band, at the top. |
| `heading(theme, y, name, counter="", cmd="")` | `~/section` header over a hairline rule; `counter` is right-aligned mono 12, `cmd` is the command that produced the section, quoted under the rule behind a `$`. Full-width slices only — it positions against `CONTENT_R`, so on a partial slice the counter lands outside the viewBox. Give a split row its own full-width heading slice. |
| `to_grid(value)` | Rounds a height up to the next multiple of 40. |
| `e(s)` | `html.escape`. `tx` applies it; use it directly on anything you interpolate by hand. |

Geometry: `W` (880), `MARGIN` (16), `ROW` (40), `TEXT_X` (52), `FRAME_L` (16),
`FRAME_R` (864), `CONTENT_R` (828), `TITLE_H` (44), and two radii — `R_CHIP` (5)
and `R_CARD` (18).

The section block is three more: `HEAD_Y` (36) is the heading baseline, `CMD_DY`
(30) the command's offset below it, `BODY_DY` (62) the first body element's.
Hang a panel off those rather than spelling its own — they are what keeps the
sections at one rhythm, and the gap between two sections is the previous
panel's tail plus `HEAD_Y`.

Two stroke weights: `EDGE_W` (1) for anything a panel draws, `RAIL_W` (2) for the
frame rails only. The rails are heavier because they are the one stroke that
spans two files: each slice is rasterised at 880px and resampled to the page's
column width, and a 1px rail lands on one device column in a tall slice and
spreads across two in a short one, so the frame steps at that seam. Panels do
not draw rails — `slice_svg` does — so `EDGE_W` is the only one you need.

Theme roles: `canvas` `surface` `ink` `dim` `faint` `hairline` `accent`. Three
text tiers, not two — `ink` carries meaning, `dim` is supporting prose, `faint`
is the label above a value and the counter beside a heading. `surface` is the one
step above the canvas and the whole of this system's depth; there are no shadows.
`accent` is the same hex in both themes — see rule 6 for what it may touch.
`LIGHT` and `DARK` are the two instances, `THEMES` is both.

Type is set per element, as a presentation attribute through `tx`, not as a
class. Two families — `MONO_STACK` and `SANS_STACK` — and the sizes a terminal
needs: mono at 11/12/13/15/20/32 for everything structural, sans at 13/15 for
the two runs of prose. These are not the token type scale, deliberately: the
console speaks in its own voice. One run in the window is off even this scale —
the 72px years grounding `~/route`'s axis, which are a surface sized against the
figure sitting on them rather than type to be told apart from other type, and
which at any declared step read as a small label that has lost its colour
instead. It is the only exception, and a test pins that. The one borrowing from
the tokens is the name, set at
`{typography.display}` exactly — sans 40/600/-0.8 — which is the largest step
the system declares and is spent once. What the tokens otherwise supply is the
families and the two radii.

`.live` and `.caret` are the only classes, and the only animations.

## Rules

1. **Only the header passes `top=True`; only the footer passes `bottom=True`.**
   Everything else passes neither, so the side rails continue across seams.
2. **Height must be a multiple of 40** — `slice_svg` raises otherwise. Derive it
   with `c.to_grid(last_y + padding)`, never hardcode, and let `last_y` be the
   last thing actually drawn. Measuring from where a further row *would* have
   started is how `~/stats` came to carry a dead 40px above the next section.
3. **Body text starts at `x=TEXT_X`** (52) and the right edge of content is
   `CONTENT_R` (828). Stay inside that. Vertically: first baseline 38–44px
   below the slice top, ~28px of padding below the last element.
4. **Set type through `tx`, at a size the console already uses.** The list above
   is short on purpose; a size that is not on it should be one of the ones that
   is. Only the mono face can be measured by character count: it advances
   `MONO_ADVANCE` (0.6em) per glyph, so anything whose width must be known
   before it is drawn goes in mono. Truncate with `…` rather than overflow.
5. **Never name a colour.** Every fill and stroke comes off `theme`. A
   hardcoded hex renders identically in both schemes and is therefore wrong in
   one of them. Shade with `mix(theme.ink, theme.canvas, t)`, not with
   `fill-opacity`, wherever the shapes overlap.
6. **The accent indexes, then marks — nothing else.** `heading` already spends
   it on the 2px stroke that starts every section rule; that is structure and
   it is identical in every panel. The caret on `~/header`'s closing prompt is
   the same kind of spend: it stands for the shell rather than for a quantity,
   so it marks nothing and takes nothing from the budget below. There is one of
   it in the window. Beyond that a panel may mark the single
   highest value in one set — the live streak, the leading language, the
   tallest day, the one layer of the stack the author writes in, the tenure
   still being held — at most once, plus a legend swatch keying it. `~/route`
   is where the restraint costs something: the timeline type would paint both
   the current tenure and the milestone that opens the axis, and the milestone
   stays in the ink because the panel's one mark is already spent. `~/stack` is the one slice carrying two
   figures and so two literals: the leading language's ray, and the dot on the
   focal slab, which keys that slab's tint and is therefore the swatch rather
   than a second datum. A set of equals gets nothing: `~/projects`
   carries only the rule. Where the accent paints a surface rather than a mark
   it goes in as a mix over the canvas, not as the literal: six logos on a field
   of chroma are six logos nobody can read. The accent sets type in exactly one
   place — the employer's name in `~/header`'s tagline, in caps at weight 700 —
   since the accent is corrected to 3:1. It is there by instruction. Nothing
   else joins it: a second accented word and the first stops reading as the
   exception. The three tiers corrected for type are `ink`, `dim` and `faint`.

   Two runs in the window sit below 4.5:1 on the canvas, and they are the only
   two: that accented noun, and the years grounding `~/route`'s axis. The second
   is not type at all but a surface the figure sits on, and it is admissible
   only because it carries nothing alone — the heading's counter prints the same
   two years in `faint` and the `desc` states them. A glyph that is the sole
   carrier of a fact is type, whatever its size, and takes a corrected tier.
7. **Never reference an external font, image, or stylesheet.** GitHub strips
   them. Everything inlines; `slice_svg` handles the font subset.
8. **Escape all interpolated content** with `c.e(...)`.
9. **`desc` must state the real numbers**, not "a chart of contributions" — it
   is the only thing a screen reader gets. `readme.py` copies these into the
   README's `alt` attributes.
10. **Degrade, don't crash.** Empty `data` or a missing key renders a short
    panel saying nothing is available, not a traceback.
11. **Nothing animates in.** GitHub paints a rendered SVG as a still at frame
    zero, so an element that fades up from `opacity:0` is simply invisible. Two
    things move, and both work the other way round: the live dot, which starts
    opaque and is only ever dimmed by `.live`, and the prompt caret, which
    starts opaque and is only ever blanked by `.caret`. The caret switches
    rather than eases — a cursor that fades is a glow. Use those classes rather
    than an inline `animation:`, so the `prefers-reduced-motion` override in
    `slice_svg` reaches them.
12. **Never emit `<a>`.** GitHub strips anchors from a rendered SVG, so a
    clickable region has to be its own file for the README to wrap. A panel
    needing that returns `Slice`s instead of markup, one per file, and splits
    the row with `width=` plus `rails="left"`/`"right"` (`"none"` for a middle
    piece). The piece carrying a rail keeps the `MARGIN` gutter outside it; the
    other edge runs flush to the slice boundary so the backgrounds meet with no
    seam. Every piece's width must be a multiple of `ROW`, and pieces in one row
    must share a height.
13. **Both themes must emit the same slice list.** `render.py` pairs them file
    by file and fails the run if they diverge, since the README would otherwise
    pair the wrong two images.
14. **A section that was fetched names where from.** Pass `heading` the real
    call: `~/skyline` quotes the public contributions page because that is what
    it reads, and quoting `api.github.com` there would name the one route that
    cannot report private totals. A section drawn from curated files has no
    source to cite and takes a command in the window's own voice instead, as
    `~/stack` does. Keep either to glyphs both vendored monospaces carry, which
    `❯` is not. `$` is the window's only prompt: the sections quote commands
    with it and the footer ends the session on it.

## Preview

```bash
.venv/bin/python tools/profile/render.py
.venv/bin/python tools/profile/preview.py
open assets/preview.html
```

Both themes, side by side, each column stacked the way the README stacks it.

The panels are a port of the `Panels` tab in the `design-preview` site, whose
`site/assets/panels.js` is the reference drawing. `tests/test_console.py`
pins the seven theme roles against what that site's `panelTheme()` derives, and
each panel's tests pin its geometry; a change here that is not also made there
puts the two renderers out of agreement.

Change the preview first, then port. `../../BACKPORT.md` is the procedure.
