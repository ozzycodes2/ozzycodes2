# Panel contract

Each panel is one module exposing `render(cfg, data, theme)`, returning a
complete SVG document. `render.py` lists them in display order and writes each
to `assets/<theme>/<name>.svg`, once per theme; the README stacks them with
consecutive `<picture>` tags so they read as one continuous window.

A panel whose parts must be separately clickable returns a list of `Slice`s
instead — it names its own files and supplies their `href`s. See rule 10.

## API

```python
from .. import console as c

def render(cfg, data, theme):
    ...
    return c.slice_svg(theme, height, body, title=..., desc=...)
```

- `cfg` — parsed `profile.toml` (hand-written content).
- `data` — `{stem: parsed json}` for every file in `data/`: `stats`, `calendar`,
  `projects`. A panel must tolerate a missing key.
- `theme` — a `Theme`. Every colour the panel draws comes from here.

### `console` exports

| Name | Purpose |
|---|---|
| `slice_svg(theme, height, body, *, title, desc, text="", top=False, bottom=False, css="", defs="", width=W, rails="both")` | Wraps body markup in the frame. `height` **must** be a multiple of `ROW` (40). `title`/`desc` are the accessible name and description. `text` lists glyphs the body needs but does not literally contain. `width`/`rails` cut one row into side-by-side files — see rule 10. |
| `ago(when, now=None)` | `"3 days ago"` for an ISO-8601 instant; `""` for a missing or unparseable one. Coarse by design; use it rather than formatting dates in a panel. |
| `mix(a, b, t)` | `t` of colour `a` over `b`, as a literal hex. The way to get a shade between the theme's ink and its canvas. |
| `Slice(file, markup, href=None)` | One output file, and the URL the README should wrap it in. `file` is a path *within* a theme directory. See rule 10. |
| `title_bar(theme)` | Window chrome and title. Header panel only. Takes no y: the band caps the frame, so it shares the frame's top edge and radius. Its content ends at `MARGIN + TITLE_H`. |
| `heading(theme, y, name, counter="")` | `~/section` header over a hairline rule; `counter` is right-aligned mono. Full-width slices only — it positions against `CONTENT_R`, so on a partial slice the counter lands outside the viewBox. Give a split row its own full-width heading slice. |
| `stagger(rows, y0, line_height, delay=0.15, step=0.12)` | Wraps rows (markup containing `{y}`, or `None` for a spacer) in sequential fade-ins. Returns `(markup, next_y)`. |
| `to_grid(value)` | Rounds a height up to the next multiple of 40. |
| `e(s)` | `html.escape`. Use on every interpolated string. |

Geometry: `W` (880), `MARGIN` (16), `ROW` (40), `TEXT_X` (52), `FRAME_L` (16),
`FRAME_R` (864), `CONTENT_R` (828), `TITLE_H` (44), and the shared radius ladder
`R_INLINE` (5), `R_CONTROL` (11), `R_CARD` (18).

Two stroke weights: `EDGE_W` (1) for anything a panel draws, `RAIL_W` (2) for the
frame rails only. The rails are heavier because they are the one stroke that
spans two files: each slice is rasterised at 880px and resampled to the page's
column width, and a 1px rail lands on one device column in a tall slice and
spreads across two in a short one, so the frame steps at that seam. Panels do
not draw rails — `slice_svg` does — so `EDGE_W` is the only one you need.

Theme roles: `canvas` `surface` `sunken` `ink` `dim` `hairline` `accent`
`on_accent`. `LIGHT` and `DARK` are the two instances, `THEMES` is both.

Type steps, as CSS classes and as `Step(size, weight, tracking)` constants:
`display` (40/600), `heading` (24/600), `body` (16/400), `caption` (13/400),
`mono` (14/400). Fill classes: `.ink .dim .accent`. Motion classes: `.ln`
(fade-in), `.cursor` (blink), `.dot` (pulse).

## Rules

1. **Only the header passes `top=True`; only the footer passes `bottom=True`.**
   Everything else passes neither, so the side rails continue across seams.
2. **Height must be a multiple of 40** — `slice_svg` raises otherwise. Derive it
   with `c.to_grid(last_y + padding)`, never hardcode.
3. **Body text starts at `x=TEXT_X`** (52) and the right edge of content is
   `CONTENT_R` (828). Stay inside that. Vertically: first baseline 38–44px
   below the slice top, ~28px of padding below the last element.
4. **Use the five type steps, nothing else.** A panel that needs a size the
   scale does not have is asking the wrong question — the console shares its
   scale with the rest of the system, and a sixth step here puts it off that
   scale. Only the mono face can be measured by character count: it advances
   `MONO_ADVANCE` (0.6em) per glyph, so anything whose width must be known
   before it is drawn goes in `mono`. Truncate with `…` rather than overflow.
5. **Never name a colour.** Every fill and stroke comes off `theme`. A
   hardcoded hex renders identically in both schemes and is therefore wrong in
   one of them. Shade with `mix(theme.ink, theme.canvas, t)`, not with
   `fill-opacity`, wherever the shapes overlap.
6. **The accent is state, not decoration.** It is spent exactly once in the
   whole console, on the live dot in `~/stats`. A panel that wants a second
   colour wants a different design.
7. **Never reference an external font, image, or stylesheet.** GitHub strips
   them. Everything inlines; `slice_svg` handles the font subset.
8. **Escape all interpolated content** with `c.e(...)`.
9. **`desc` must state the real numbers**, not "a chart of contributions" — it
   is the only thing a screen reader gets. `readme.py` copies these into the
   README's `alt` attributes.
10. **Degrade, don't crash.** Empty `data` or a missing key renders a short
    panel saying nothing is available, not a traceback.
11. Respect `prefers-reduced-motion`: use the existing `.ln`/`.cursor`/`.dot`
    classes rather than inline `animation:` shorthand, so the global override in
    `slice_svg` disables them.
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

## Preview

```bash
.venv/bin/python tools/profile/render.py
.venv/bin/python tools/profile/preview.py
open assets/preview.html
```

Both themes, side by side, each column stacked the way the README stacks it.
A screenshot needs `--force-prefers-reduced-motion`: a CSS animation inside an
`<img>` paints its first frame and stops, and `.ln` starts at `opacity:0`, so
without it the panels come out blank.
