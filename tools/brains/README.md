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

Output lands in `gists/`, named `Left Brain.gif` and `Right Brain.gif` — the
gist filename is the only label the pinned card carries, so the spaces and the
capitals are load-bearing.

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
disk. `playwright install chromium` is an alternative, not a requirement.

If `pip` reports `401` against a CodeArtifact host, it is picking up a work
registry from `~/.config/pip`; add `--index-url https://pypi.org/simple`.

ffmpeg must be 6.0 or newer. `atkinson` dither does not exist before it, and
the next-cheapest dither is 25% more bytes on flat vector art.

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

## The drawing lives somewhere else

`left-brain.svg` and `right-brain.svg` are generated. The drawing is authored in
`~/Documents/personal/design-preview` at `site/assets/brains.js`, on the Brains
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
