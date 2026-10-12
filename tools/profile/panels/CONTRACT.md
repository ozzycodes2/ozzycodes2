# Panel contract

Each panel is one module exposing `render(cfg, data)`, returning a complete SVG
document. `render.py` lists them in display order and writes each to
`assets/<name>.svg`; the README stacks them with consecutive `<img>` tags so
they read as one continuous terminal window.

A panel whose parts must be separately clickable returns a list of `Slice`s
instead — it names its own files and supplies their `href`s. See rule 10.

## API

```python
from .. import console as c

def render(cfg, data):
    ...
    return c.slice_svg(height, body, title=..., desc=..., text=..., )
```

- `cfg` — parsed `profile.toml` (hand-written content).
- `data` — `{stem: parsed json}` for every file in `data/`: `stats`, `calendar`,
  `projects`. A panel must tolerate a missing key.

### `console` exports

| Name | Purpose |
|---|---|
| `slice_svg(height, body, *, title, desc, text="", top=False, bottom=False, css="", defs="", weights=(400,700), width=W, rails="both")` | Wraps body markup in the frame. `height` **must** be a multiple of `ROW` (40). `title`/`desc` are the accessible name and description. `text` lists glyphs the body needs but does not literally contain. `width`/`rails` cut one row into side-by-side files — see rule 10. |
| `ago(when, now=None)` | `"3 days ago"` for an ISO-8601 instant; `""` for a missing or unparseable one. Coarse by design; use it rather than formatting dates in a panel. |
| `Slice(file, markup, href=None)` | One output file, and the URL the README should wrap it in. See rule 10. |
| `title_bar(y)` | Traffic lights + window title. Header panel only. |
| `heading(y, name, counter="")` | `~/section` header with glowing underline; `counter` is right-aligned small caps. Full-width slices only — it positions against `FRAME_R`, so on a partial slice the counter lands outside the viewBox. Give a split row its own full-width heading slice. |
| `stagger(rows, y0, line_height, delay=0.15, step=0.12)` | Wraps rows (markup containing `{y}`, or `None` for a spacer) in sequential fade-ins. Returns `(markup, next_y)`. |
| `to_grid(value)` | Rounds a height up to the next multiple of 40. |
| `e(s)` | `html.escape`. Use on every interpolated string. |

Constants: `W` (880), `MARGIN` (16), `ROW` (40), `TEXT_X` (52), `FRAME_L`,
`FRAME_R`, and colours `ACCENT` `ALT` `OK` `BG` `FG` `DIM` `FAINT` `WHITE`.

CSS classes already defined: `.ac .alt .ok .fg .dim .faint .wh` (fills),
`.ln` (fade-in), `.cursor` (blink), `.dot` (pulse). Filters: `url(#glow)`,
`url(#soft)`. Pattern: `url(#grid)`.

## Rules

1. **Only the header passes `top=True`; only the footer passes `bottom=True`.**
   Everything else passes neither, so the side rails continue across seams.
2. **Height must be a multiple of 40** — `slice_svg` raises otherwise. Derive it
   with `c.to_grid(last_y + padding)`, never hardcode.
3. **Body text starts at `x=TEXT_X`** (52) and the right edge of content is
   `FRAME_R - 36` (828). Stay inside that. Vertically: first baseline 38–44px
   below the slice top, ~28px of padding below the last element.
4. **Font size 15px for body, 20px/700 for headings, 12–13px for labels.**
   JetBrains Mono is monospace: one character advances 0.6em, so 15px ≈ 9px.
   `letter-spacing` adds to every advance, including the last — add it per
   character when predicting width. Truncate with `…` rather than overflow.
5. **Never reference an external font, image, or stylesheet.** GitHub strips
   them. Everything inlines; `slice_svg` handles the font subset.
6. **Escape all interpolated content** with `c.e(...)`.
7. **`desc` must state the real numbers**, not "a chart of contributions" —
   it is the only thing a screen reader gets. `readme.py` copies these into the
   README's `alt` attributes.
8. **Degrade, don't crash.** Empty `data` or a missing key renders a short
   panel saying nothing is available, not a traceback.
9. Respect `prefers-reduced-motion`: use the existing `.ln`/`.cursor`/`.dot`
   classes rather than inline `animation:` shorthand, so the global override in
   `slice_svg` disables them.
10. **Never emit `<a>`.** GitHub strips anchors from a rendered SVG, so a
    clickable region has to be its own file for the README to wrap. A panel
    needing that returns `Slice`s instead of markup, one per file, and splits
    the row with `width=` plus `rails="left"`/`"right"` (`"none"` for a middle
    piece). The piece carrying a rail keeps the `MARGIN` gutter outside it; the
    other edge runs flush to the slice boundary so the backgrounds meet with no
    seam. Every piece's width must be a multiple of `ROW` or the grid steps
    sideways across the join, and pieces in one row must share a height.

## Preview

```bash
.venv/bin/python tools/profile/render.py
/tmp/preview/shot.sh /tmp/preview/out.png assets/header.svg assets/<yours>.svg
```

The screenshot script forces reduced-motion, so fade-ins appear in their final
state. Rendering a panel mid-animation shows a blank frame — that is expected.
