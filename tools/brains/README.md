# Brain pins

Two animated transparent GIFs published as public gists and pinned above the
profile's four repositories, heading an engineering column and a creative one.
Nothing here touches the console README or `tools/profile/`.

Design: `docs/superpowers/specs/2026-10-19-brain-pins-design.md`.

## Build

```
.venv/bin/python -m tools.brains.build            # both hemispheres
.venv/bin/python -m tools.brains.build left-brain # one
```

Output lands in `gists/`, named `Left Brain.gif` and `Right Brain.gif`.

The label on the pinned card is the gist's **description**, not the filename —
set it to exactly `Left Brain` or `Right Brain` and nothing more, because GitHub
truncates the heading at about 40 characters mid-word. The filename appears
nowhere on the card, but it has to keep a raster extension or the card renders
source instead of an image, and it is what identifies the published file, so the
spaces and the capitals stay as they are.

```
gh api -X PATCH gists/<id> -f description="Left Brain"
```

## Dependencies, and why they are not in CI

```
.venv/bin/pip install playwright==1.56.0
```

The build is run by hand and is absent from `update-profile.yml`, whose
`paths:` filter and `git add` list are both scoped to `tools/profile/**` and
`assets/`. The workflow installs `fonttools` and `brotli` and nothing else, so
`pytest` here must stay green without a browser: `capture.chrome_shoot` imports
Playwright inside the call and every test injects a fake shooter.

`chrome_shoot` launches `channel="chrome"`, the Google Chrome already on the
machine, rather than a Playwright-managed build — a pin whose bundled browser
was never fetched otherwise fails hunting for a headless shell that is not on
disk. So Chrome itself is a requirement and `playwright install chromium` does
not substitute for it: a managed chromium does not satisfy that channel.
`build.chrome_missing` is what the browser-gated tests skip on, because the pip
package being present says nothing about the browser.

If `pip` reports `401` against a CodeArtifact host, it is picking up a work
registry from `~/.config/pip`; add `--index-url https://pypi.org/simple`.

ffmpeg must be 6.0 or newer. `atkinson` dither does not exist before it, and
the next-cheapest dither is 25% more bytes on flat vector art.

## Why the palette is built rather than measured

`palettegen` will not reproduce a known colour. Asked for the smallest palette
ffmpeg permits alongside a reserved transparent slot, it still resolves its one
painted entry to a histogram average, and the browser's antialiased edge pulls
that average off the accent — `#ed6206` against `#ef6306`, measured. Nothing
downstream can correct it, and the drift tracks how much curve the drawing has,
so it appears when the art changes rather than when the encoder does.

So `encode.palette_png` writes the 256 entries `paletteuse` demands: the accent
255 times and one fully transparent entry last, where GIF's reserved sentinel
lands. Padding is the accent and not black, because black is a nearest-match
target for any dark pixel and, in the written table, indistinguishable from the
entries ffmpeg pads with anyway — a check on the output could not tell a painted
black from an unused slot.

## Why a browser

Every static SVG rasterizer renders frame zero. librsvg, resvg, CairoSVG and
Inkscape decline SMIL explicitly, and resvg underpins the Rust SVG stack, so no
Rust-native tool will do it either. Published `svg-to-gif` packages are variously
unmaintained, CSS-blind, or recently cleaned of supply-chain malware.

Chrome works, but only with an explicit seek — `pauseAnimations()`,
`setCurrentTime(t)`, and `document.getAnimations()` paused and set frame by
frame. `--virtual-time-budget` freezes composited CSS transforms at 0 while SMIL
advances, and it is not reproducible: three identical runs put the figure in
three different positions. Explicit seek gives byte-identical frames across
repeats, which was verified before this pipeline was written and is worth
re-checking if the frames ever start to shimmer.

## Both halves are drawn by hand, in a browser

Neither hemisphere is produced by a rule. Each is a composition: what the figure
draws off the construction grid, picked one mark at a time.

```
.venv/bin/python -m tools.brains.editor.server    # http://127.0.0.1:8732/
```

**Left half — sides.** Click a triangle side to draw it, click again to erase
it, double-click to make it dashed.

**Right half — circles.** Click a triangle tip for the circle through the six
tips around it, radius 56. The triangles cut it into six arcs; click an arc to
cut it away, and the last one takes the circle with it. Clicking a tip that
already has a circle gives the whole thing up.

The radius is what makes the right half join up. Two circles on neighbouring
tips cross at exactly the two tips they both border, so arcs from different
circles share an endpoint rather than crossing somewhere between vertices, and
where two runs touch the shorter ends on the longer. A circle inscribed in the
hexagon instead, radius 48, keeps every arc inside its own triangle and nothing
meets anything: arcs that should join land 4px apart.

Every change autosaves to `editor/state.json`, which holds the two halves in the
two shapes they are drawn in — `"u,v|u,v": "solid"` for a side, `"u,v":
"101101"` for a circle and its arcs. Then:

```
.venv/bin/python -m tools.brains.shape            # both literals
```

Paste those over `BRAIN_EDGES` and `BRAIN_RUNS` in the preview's `brains.js`.
They are the drawing placed inside the card: the editor's grid deliberately runs
past the bottom and leaves room at the midline, so a shape can be drawn without
also being positioned, and `shape.py` translates each half to the corner. Down
the card it goes to the pad exactly; in from the midline it goes by whole
columns, because a fraction of a column would buy a few pixels at the cost of
taking every vertex off the construction. It refuses to emit a chord, an
off-grid endpoint or a closed circle rather than publishing one as if it were a
drawing decision.

Nothing stands behind either half — no grid, nothing drifting. The card's own
surface is the ground.

## The thrown field

Each half throws marks out of its own contour, away from the gutter the two
share, shrinking as they go. The left throws mathematics, programming and logic;
the right throws music, drawing and making.

Two things about it are worth knowing before changing anything.

**It travels, and the 24px cap does not apply.** Everything else in the figure
returns to where it started, because the GIF repeats and a drawing that ended
elsewhere would jump. The field is the one exception: the slots in a lane repeat
every `p`, so translating the lane by exactly `p` puts a different mark wherever
a mark already was and the frame is indistinguishable from the first. Off by any
amount and the whole field jumps once per loop. Every other channel still closes
outright — the wind returns, the tumble returns to its own angle, and size is a
function of position rather than of time, which is what lets one keyframe serve
every slot in a lane.

**The left half sets type, against the rule that nothing in the art does.** Its
marks include binary digits, and they are drawn as `<text>`: a bar and a ring
drawn as paths would satisfy the rule's wording and still be read as numbers. Ones
and zeros a handful at a time cannot spell a caption, which is the rule's reason.
The right half's vocabulary has no numbers and it sets no type at all.

The field is what put the files past the old 200 KB budget — see `build.BUDGET`.

## Why the trail decays downward

A signal is a short bright head with a trail behind it, and the trail decays
back to the resting line rather than out to the card. Two constraints fix the
direction.

One bit of alpha: a half-opaque pixel is simply absent, so a trail that
dissolved into the ground would blink out instead of fading. Every step of the
decay is therefore fully opaque, and what changes along it is shade and weight.

One image for both themes: the accent is already the brightest a pinned figure
can be. `#ef6306` is 3.25:1 on a white card against a 3:1 floor, and the next
step lighter is 2.70:1. So the drawing rests below the accent — `#ac4704`, which
is 3.30:1 on the dark card, the other end of the same band — and the signal is
the accent itself. Brightness is a step up from rest, not a step past it.

Those shades are the GIF palette. `figures.paints` reads them off the vendored
SVG and `encode.palette_pixels` shares the 255 opaque slots between them; a
palette short of any one of them snaps the trail flat, and nothing downstream
reports it.

A run is the maximal chain of contiguous arcs around one circle, emitted as one
path so it carries no seam where two of its arcs meet. Nodes are not emitted:
both halves derive them from the graph, so a mark cannot outlive the stroke it
sits on.

Edit the drawing, never the numbers. A hand-edited literal is lost the next
time the editor saves.

## The drawing lives somewhere else

`left-brain.svg` and `right-brain.svg` are generated. The drawing is authored in
`~/personal/design-preview` at `site/assets/brains.js`, on the Brains
tab, and vendored here so a capture is reproducible on a machine that has only
this repository. Each file states its provenance in a leading comment.

Never hand-edit them. Change the preview, look at it, then:

```
.venv/bin/python -m tools.brains.parity                     # report drift
.venv/bin/python -m tools.brains.parity --write right-brain # re-vendor
```

The drift report skips, and says it skipped, when the preview is not on the
machine — a clone of this repository alone has to run green. Writing does not
skip: there would be nothing to copy from, and a silent no-op would leave the
stale drawing in place and call it success. `build.py` reports drift as a
warning and builds anyway, for the same reason.
