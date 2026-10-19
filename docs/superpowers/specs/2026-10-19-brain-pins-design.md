# Left Brain / Right Brain pins

## Intent

The profile's pinned section currently shows repositories and nothing else. It
should instead read as two labelled columns — engineering on the left, creative
on the right — headed by a pair of animated drawings that state the split
before any repo name is read.

The reference for the mechanism is `github.com/terkelg`. The reference for the
drawing is Sébastien Navizet's *Devarium Brain (construction)*, whose left half
is "line charts, isometric shapes, like a printed circuit" and whose right half
is rounder and organic, deliberately floating off the grid. The grid background
of that shot is not wanted.

The drawing language is Mine Final, as the rest of the profile already is.

## Goals

- Two animated pins acting as column headers, one per hemisphere.
- Four pinned repositories beneath them, falling into the correct column.
- Legible and correct on both GitHub themes, with no second artifact per theme.
- The halves visibly disagree: left obeys Mine Final's grid, right breaks it.

## Non-goals

- Changing `README.md` or anything under `tools/profile/`. The console above the
  pins stays exactly as it is. This work adds an artifact family beside it.
- Choosing which repositories occupy the four repo slots. Pins reorder from the
  profile UI at any time and need no code change.
- Theme-switched variants of the drawings. The chosen palette removes the need.

## Anti-goals

Failure states that a technically working result could still reach:

- A drawing dense enough to need labels. The card is 100 CSS px tall; anything
  that wants a legend has already lost.
- A right half that reads as a mistake rather than a deliberate argument with
  the left.
- A second renderer disagreeing with `design-preview` about one drawing —
  the failure `BACKPORT.md` exists to prevent.

## Constraints

Everything in this section was measured against live GitHub, not assumed.

### The pinned card is the medium, and it is small

A pinned item is an `<li class="… col-12 col-md-6 col-lg-6">` in a flex-wrap
list: two per row on desktop, one per row narrow. Six pins maximum. For a gist
whose file is a raster image, GitHub emits the image as a CSS background on a
bare div:

```html
<div style="height: 100px; background-image: url('…');
            background-size: contain; background-repeat: no-repeat;
            background-position-y: top; overflow: hidden;"></div>
```

Height is pinned at 100px. Displayed width follows from the aspect ratio.
Terkel's 1340×400 therefore paints at 335×100.

There is no `<img>`, so no `alt`, no `width`, no link on the image itself, and
no hover. The only link is the card title, which is **the gist's filename** —
`Left Brain.gif` renders as the card heading, extension included, in GitHub's
own theme-aware colour.

### SVG cannot be used here

A gist `.svg` is served correctly as `content-type: image/svg+xml`, and such a
file does everything we would want: under the exact CSP GitHub serves gist
files with (`default-src 'none'; style-src 'unsafe-inline'; sandbox`), an SVG
used as a CSS background resolves its own internal
`@media (prefers-color-scheme: dark)` and runs CSS keyframes, CSS transforms
and SMIL.

It is still unusable. GitHub's pinned-card image detection is a raster
extension allowlist; `.svg` is not on it, and the card renders
syntax-highlighted source in a `<pre>` instead. Verified by pinning one.

Raster is therefore forced, and with it the loss of any media query. Do not
spend time re-testing this.

### Theme independence comes from transparency, not from theming

Terkel's GIF carries a two-entry global palette with index 0 flagged
transparent. There is no white background; the card surface shows through.
One visible colour, no theming.

Mine Final makes this free. Its accent, `#ef6306`, is deliberately identical in
both themes, on the stated grounds that a brand hue which follows the reader's
OS setting is not one brand. An accent-on-transparent drawing is therefore
theme-invariant by construction.

The consequence is that **the art carries no type**. Mine Final forbids the
accent from setting type at any size in either theme, and a transparent
two-colour image has no ink to set it in. The gist filename is the label. This
is a constraint, not a limitation to work around.

### 1-bit alpha, resolved by supersampling

GIF transparency is one bit: there are no partially transparent edge pixels, so
antialiasing against an unknown card surface is impossible. Draw hard-edged at
4× and let the browser's downscale to 100px do the smoothing. This is the same
mechanism that keeps Terkel's art crisp, and it is the only one available —
GitHub strips density descriptors from `srcset`, so there is no retina variant
to ship.

### Motion budget

Mine Final's system document bans animating transform and opacity outright. The
diagram motion layer is a gated exception to it, and these pins live under that
exception, in its `loop` mode: one decorative token repeats and the meaning does
not change. Its clock is `--motion-fast: 160ms`, `--motion-step: 480ms`,
`--motion-hold: 720ms`, with a loop of at least 3s and travel capped at 24px.
Terkel's loop is 5.54s across 48 frames.

Nothing may animate in. A GIF's first frame is what a static renderer, a
reduced-motion viewer, and GitHub's mobile apps will show, so frame zero must
be the complete drawing. Motion only ever subtracts from it.

### GIF encoding

Measured numbers, to save the builder rediscovering them:

- Frame delays of 0 or 1 centisecond are clamped *up* to 100ms by both Chromium
  and Firefox. 2cs is the honoured floor. Only 1, 2, 4, 5, 10, 20, 25, 50 and
  100 fps come out exact; prefer 20fps (delay 5), or variable delays with one
  long hold frame as Terkel uses.
- Dither cost over 24 frames: none 54,944 B · atkinson 56,037 · floyd_steinberg
  61,981 · bayer 68,510. `atkinson` is the right default for flat vector art and
  needs ffmpeg ≥ 6.0.
- Do not let `palettegen` pick the palette at all. A generous one is expensive —
  re-encoding Terkel's two-colour GIF with `max_colors=32` grew it from 117 KB
  to 291 KB — and the smallest one ffmpeg permits alongside a reserved
  transparent slot still resolves its painted entry to a histogram average,
  which the browser's antialiased edge pulls off the accent: `#ed6206` against
  `#ef6306`, measured. Supply the 256 entries `paletteuse` demands instead, with
  the fully transparent one last.

Camo is not in the path — gist files serve from `gist.githubusercontent.com`
directly — so the 5 MiB camo cap does not apply. Keep files small anyway; 48
frames of 1340×400 cost Terkel 117 KB.

### Rasterizers cannot do this; headless Chrome can

Every static SVG rasterizer renders frame zero. librsvg, resvg, CairoSVG and
Inkscape all decline SMIL explicitly, and because resvg underpins the Rust SVG
stack, no Rust-native tool will do it either. Published `svg-to-gif` packages
are variously unmaintained, CSS-blind, or — in one case — recently cleaned of
supply-chain malware. Do not adopt one.

The working primitive is explicit seek, not virtual time:

```js
await page.evaluate((t) => {
  const svg = document.querySelector('svg');
  svg.pauseAnimations();
  svg.setCurrentTime(t);
  document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000; });
}, t);
await page.screenshot({ path: `frame_${String(i).padStart(4,'0')}.png`, omitBackground: true });
```

The SVG must be **inlined into the page**. Referenced via `<img>` it is frozen
and has no `contentDocument` to seek. `--virtual-time-budget` is the wrong
lever: it freezes composited CSS transforms at 0 while SMIL advances, and it is
not reproducible — three identical runs produced three different positions.
Explicit seek gives byte-identical frames across repeats.

## Decisions already made

Taken by the author:

- Two hemispheres, engineering left and creative right, matching Terkel's split.
- The pins sit beneath an unchanged README console.
- Mine Final is the drawing language.
- The Dribbble shot is the compositional reference, without its grid background.
- **The halves disagree.** The left obeys Mine Final — 2:1 dimetric, orthogonal,
  on the 4px grid, which is the kit `panels.js` already has. The right breaks
  that grid deliberately: round, organic, floating. Mine Final has no vocabulary
  for this, so the right half is invention rather than port, and the two halves
  are meant to look like they are arguing.
- Which repositories go in which column is deferred.
- **The SVG is vendored into this repo** at `tools/brains/`, beside the GIF
  masters, and the capture tool reads that copy. `design-preview` remains the
  place the drawing is authored and looked at, but it is not a git repository
  and a drawing living only there exists on one laptop. The cost is accepted
  knowingly: this is a second copy of a drawing that also lives in the preview,
  which is the drift `BACKPORT.md` exists to prevent, so it buys a parity
  obligation — see below.

Taken by the designer, open to reversal:

- Transparent background with the accent as the only visible colour, rather than
  a themed pair of files.
- No type inside the art; the gist filename does the labelling.
- 1340×400 source art, matching Terkel's 4× ratio.
- **Capture tool is Python with Playwright**, run by hand, absent from CI. The
  repo is Python, the coverage bar is pytest, and the workflow's `paths:` filter
  and `git add` list already exclude a new tool directory. Browser-dependent code
  sits behind a seam so the suite runs green without a browser installed.
- **The preview figure is a new asset file on its own tab**, not a member of
  `PANEL_ORDER`. A figure inside `panelSlices` becomes a slice `render.py` must
  pair against a Python panel that will never exist, and `CONTRACT.md` rule 13
  fails the run on exactly that divergence. The tab renders for every system
  from that system's own tokens, as `tabPanels` already does. Gating it to the
  one system the drawing means something under was the first instinct and does
  not survive contact: `test/smoke.mjs` hardcodes `TAB_IDS` and asserts every
  system × tab yields at least 400 characters, so a gate would mean shipping a
  filler panel for eight systems to satisfy a test.
- **The motion exception is recorded as prose** in the mine-final system
  document, not as tokens. That system reports `0 unspent` and nothing in a GIF
  pipeline would ever reference a motion token, so adding them breaks the census
  to document something a sentence already covers.
- **Narrow reflow is accepted as a partial loss.** At one pin per row the order
  is gist, gist, then four repos: the two drawings stay adjacent, so the halves
  still read as a pair, but no repo sits beneath its hemisphere. The
  column association is a desktop affordance. Nothing about GitHub's reflow is
  changeable, so the drawings are judged as a pair and not on whether a phone
  can infer which repo belongs to which half.

## Left to the builder

- The actual geometry of both hemispheres.
- What moves, within the `loop` budget, and the exact loop length.
- Frame count and delay schedule.
- Whether an accent-to-transparent ramp of a few palette entries pays for itself
  against hard two-colour, measured in bytes and in how the 4× downscale reads.
- Test shapes and assertions, following the conventions already in `tests/`.
- The mechanism of the parity check between the vendored SVG and the preview
  (below). The obligation is fixed; how it is enforced is not.

## The parity obligation

Vendoring creates two copies of one drawing, and `BACKPORT.md` is explicit that
a change made in one place and not the other "leaves two renderers disagreeing
about one drawing, and nothing will tell you which is right." Vendoring is
chosen anyway, so something must tell you.

Two things are required:

- The vendored SVG states its provenance in a comment: which preview file
  generated it, and when.
- A check that regenerates from the preview and diffs against the vendored copy,
  failing on difference. It must skip cleanly — not fail — when `design-preview`
  is absent, so a clone of this repo alone still runs green.

The preview remains where the drawing is authored. Edit there, look at it, then
regenerate the vendored copy. Never hand-edit `tools/brains/*.svg`.

## Build order

A tracer bullet first: one hemisphere, few frames, all the way through to a
pinned card, looked at in both themes before the second is started.

1. Draw in `~/Documents/personal/design-preview` first. `BACKPORT.md` makes this
   the default path for anything that changes how a drawing looks, and the
   preview is vanilla JS with no build step. `mine-final` must report 0 unspent
   tokens. Add the assertion before porting, then break the renderer on purpose
   and confirm the assertion fails.
2. Vendor the generated SVG to `tools/brains/`, with its provenance comment.
3. Capture and encode, in `tools/brains/` — not `tools/profile/`. The GIFs are
   published as gists, never as repo assets, so they have no place in the
   slice/manifest/`<picture>` pipeline, and the workflow's `paths:` filter and
   `git add` list are scoped to `tools/profile/**` and `assets/` regardless.
4. Commit the GIF masters in-repo so the gists are reproducible. Terkel keeps his
   at `gists/*.gif`.
5. Publish to two public gists, filenames `Left Brain.gif` and
   `Right Brain.gif`, since the filename is the visible card title. Gists are
   git repositories and can be pushed to.
6. Pin by hand. There is no pinning API — the GraphQL schema has no mutation for
   it, and `updateUserListsForItem` governs lists, not profile pins. Order the
   six pins so the two gists take row one and the repos fall into the intended
   columns.

## Verification

- `.venv/bin/python -m pytest tests -q` stays green, and new source reaches the
  90% coverage bar the repo holds everywhere.
- Frame zero of each GIF is the complete drawing, checked by viewing frame 0
  alone.
- Both cards read correctly on both GitHub themes at the real 100px height, not
  only in a local replica.
- The existing accent census over `assets/*.svg` is unchanged — these files never
  land in `assets/`, and if they did the workflow's `git add assets` would commit
  them on every scheduled run. The equivalent check here is a hex count on the
  vendored SVG before capture, plus an assertion on the encoded GIF's palette:
  one visible entry, one transparent.
- The parity check passes with `design-preview` present, and skips rather than
  fails without it.
