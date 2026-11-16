# Left Brain / Right Brain Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two animated transparent GIFs, published as pinned gists, heading the profile's pinned section as engineering and creative columns.

**Architecture:** The drawing is authored in `design-preview` as a new preview tab, vendored into this repo as SVG, rasterized frame-by-frame through headless Chrome with explicit animation seek, and encoded to a two-entry transparent GIF with ffmpeg. The console README and `tools/profile/` are untouched; this is a parallel tool directory whose output never enters `assets/`.

**Tech Stack:** Python 3.12, Playwright (new dependency), ffmpeg ≥ 6.0 (9.0.1 present), pytest + pytest-cov. Preview side is vanilla JS, no build step.

**Spec:** `docs/superpowers/specs/2026-10-19-brain-pins-design.md`

## Global Constraints

- Art is **1340×400**, displayed by GitHub at 335×100. Hard-edged; the 4× downscale does the antialiasing.
- Accent is **`#ef6306`**, identical in both themes, and is the **only visible colour**. Background is transparent.
- **No type inside the art.** The gist filename is the label.
- **Nothing animates in.** Frame zero is the complete drawing; motion only ever subtracts.
- Loop is **≥3s**, travel **≤24px**, on the clock `--motion-fast: 160ms` / `--motion-step: 480ms` / `--motion-hold: 720ms`.
- GIF frame delays: **2cs floor**; exact framerates only at 1, 2, 4, 5, 10, 20, 25, 50, 100 fps. Dither `atkinson`. Reserve the transparent palette entry.
- Nothing this plan produces may be written under `assets/` — the workflow's `git add assets` would commit it on every scheduled run.
- `tools/profile/**` and `README.md` are not modified by any task.
- Preview edits land in `~/personal/design-preview`, which is not a git repository. `fabric` must still report **0 unspent tokens**.

## Review Focus

Five conditions the spec implies that no task's happy path exercises. Each has a test in the task that owns the code.

- **No browser installed.** The suite must skip capture tests, not fail — the repo's CI installs only `fonttools` and `brotli`. (Task 3)
- **ffmpeg missing or below 6.0.** `atkinson` dither does not exist before 6.0; encoding must refuse loudly rather than silently fall back and ship a 3× larger GIF. (Task 4)
- **`design-preview` absent.** A clone of this repo alone must run green; the parity check skips. (Task 5)
- **An element that animates in.** Frame zero would render incomplete to reduced-motion viewers, mobile apps, and every static renderer. Must be caught by assertion, not by eye. (Task 2)
- **Palette drift above two entries, or a lost transparent index.** Either one puts an opaque slab on the card in one of the two themes. (Task 4)

---

### Task 1: The left hemisphere, in the preview

**Files:**
- Create: `~/personal/design-preview/site/assets/brains.js`
- Create: `~/personal/design-preview/test/brains.mjs`
- Modify: `~/personal/design-preview/site/index.html` (script tags, after line 32)
- Modify: `~/personal/design-preview/site/assets/app.js` (`TABS` line 9, dispatch map line 432)
- Modify: `~/personal/design-preview/test/dom-stub.mjs` (asset load list)
- Modify: `~/personal/design-preview/test/smoke.mjs` (`TAB_IDS` line 6)
- Modify: `~/personal/design-preview/systems/DESIGN-fabric.md` (Motion section prose)

**Interfaces:**
- Consumes: `panelTheme(s)`, `solid()`, `piso(ox, oy)`, `r2()` from `panels.js`, already global under `vm.runInThisContext`.
- Produces: `brainFigure(s, side)` → `{slug, title, desc, w, h, body, svg}` where `side` is `"left"` or `"right"`; `brainSvg(s, side)` → complete SVG document string; `tabBrains(s)` → HTML for the tab.

**Note on scope:** the tab renders for every system from that system's own tokens, matching `tabPanels`. `smoke.mjs` hardcodes `TAB_IDS` and asserts every system × tab yields ≥400 chars, so gating it to one system would mean shipping a filler panel for the other eight.

- [ ] **Step 1: Write the failing invariants**

`test/brains.mjs`, following `test/panels.mjs` conventions (`import "./dom-stub.mjs"`, a local `assert`, exit non-zero on failure). Assertions, against `brainSvg(s, "left")` for every system in `window.DESIGN_SYSTEMS`:

```js
assert(/viewBox="0 0 1340 400"/.test(svg), "art is 1340x400");
assert(!/<text/.test(svg), "the art sets no type");
assert(!/<rect[^>]*width="(100%|1340)"[^>]*fill=/.test(svg), "no background rect: the card surface shows through");
assert(colours(svg).size === 1 && colours(svg).has(t.accent), "one visible colour, the accent");
assert(!/opacity:\s*0[^.]/.test(svg) && !/opacity="0"/.test(svg), "nothing starts invisible");
assert(/@keyframes/.test(svg), "motion is declarative CSS, not SMIL");
assert(loopSeconds(svg) >= 3, "loop is at least 3s");
assert(maxTravelPx(svg) <= 24, "travel is within 24px");
```

where `colours(svg)` collects every `fill="…"`/`stroke="…"` literal that is not `none`, `loopSeconds` reads the `animation` shorthand's duration, and `maxTravelPx` reads `translate*()` distances out of the `@keyframes` blocks.

- [ ] **Step 2: Run it to verify it fails**

Run: `node test/brains.mjs`
Expected: FAIL — `brainSvg is not defined`.

- [ ] **Step 3: Implement `brainFigure`, `brainSvg` and `tabBrains` in `site/assets/brains.js`**

Left hemisphere geometry: 2:1 dimetric via `piso`, orthogonal in world space, every coordinate and gap divisible by 4, read as Navizet's "printed circuit". Accent strokes only; no fills that would need a second colour. Motion is one `loop`-class decorative token — the spec caps it at 24px travel and gives no further shape, so pick one and keep it subtractive from frame zero.

- [ ] **Step 4: Wire the tab**

`TABS` gains `["brains", "Brains"]` after `["diagrams", "Diagrams"]`; the dispatch map at `app.js:432` gains `brains: tabBrains, // brains.js`; `index.html` gains `<script src="assets/brains.js"></script>` after the `panels.js` tag; `dom-stub.mjs` gains `"assets/brains.js"` at the same position in its load list; `smoke.mjs` gains `"brains"` to `TAB_IDS`.

- [ ] **Step 5: Amend the motion prose**

In `systems/DESIGN-fabric.md`, the Motion section records that figures captured for publication outside the page run under the diagram layer's `loop` mode and its clock. Prose only — no new tokens, or the 0-unspent census breaks.

- [ ] **Step 6: Run the preview suite**

Run, from the preview root: `python3 build.py && node test/brains.mjs && node test/panels.mjs && node test/smoke.mjs && python3 test/unused_tokens.py`
Expected: all pass; `fabric` reports `0 unspent`.

- [ ] **Step 7: Mutation-test the new assertions**

Break the renderer deliberately — emit a background rect, then a second colour — and confirm `test/brains.mjs` fails each time. Revert.

- [ ] **Step 8: Look at it**

Run: `open site/index.html`, Brains tab, both themes.

---

### Task 2: Vendor the SVG, with its invariants

**Files:**
- Create: `tools/brains/__init__.py`
- Create: `tools/brains/figures.py`
- Create: `tools/brains/left-brain.svg` (generated, provenance comment at top)
- Create: `tests/test_brains_figures.py`

**Interfaces:**
- Produces: `figures.NAMES = ("left-brain", "right-brain")`; `figures.load(name: str) -> str`; `figures.W, figures.H = 1340, 400`; `figures.ACCENT = "#ef6306"`; `figures.provenance(name: str) -> dict` with keys `source` and `generated`.

- [ ] **Step 1: Write the failing test**

`tests/test_brains_figures.py`, parametrised over the names present on disk:

```python
def test_the_art_is_the_published_size(name):
    assert f'viewBox="0 0 {figures.W} {figures.H}"' in figures.load(name)

def test_the_art_sets_no_type(name):
    assert "<text" not in figures.load(name)

def test_the_accent_is_the_only_visible_colour(name):
    assert paints(figures.load(name)) == {figures.ACCENT}

def test_nothing_animates_in(name):
    """Frame zero is what a static renderer, a reduced-motion viewer and
    GitHub's mobile apps paint. An element that fades up from nothing is
    simply absent there."""
    svg = figures.load(name)
    assert 'opacity="0"' not in svg
    assert not re.search(r"0%\s*\{[^}]*opacity:\s*0[^.\d]", svg)

def test_it_names_where_it_was_generated_from(name):
    p = figures.provenance(name)
    assert p["source"].endswith("brains.js") and p["generated"]

def test_load_rejects_a_name_it_does_not_carry():
    with pytest.raises(FileNotFoundError):
        figures.load("middle-brain")
```

with a local `paints(svg)` helper collecting non-`none` `fill`/`stroke` literals.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_brains_figures.py -q`
Expected: FAIL — no module `tools.brains.figures`.

- [ ] **Step 3: Generate and vendor `left-brain.svg`**

Dump `brainSvg(mineFinal, "left")` from the preview under node, prepend an XML comment naming the generating file and the date, and write it to `tools/brains/left-brain.svg`. Never hand-edit the result.

- [ ] **Step 4: Implement `figures.py`**

Reads the sibling `.svg` files. `provenance` parses the leading comment.

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_brains_figures.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/brains/ tests/test_brains_figures.py
git commit -m "feat: vendor the left hemisphere drawing"
```

---

### Task 3: Capture frames

**Files:**
- Create: `tools/brains/capture.py`
- Create: `tests/test_brains_capture.py`
- Modify: `tools/profile/README.md` is **not** touched; document the new dependency in `tools/brains/README.md` (create)

**Interfaces:**
- Consumes: `figures.load`, `figures.W`, `figures.H`.
- Produces: `capture.times(count: int, duration: float) -> list[float]`; `capture.frames(svg: str, *, count: int, duration: float, shoot=None) -> list[bytes]` returning one PNG per frame; `capture.chrome_shoot(svg: str, times: list[float], width: int, height: int) -> list[bytes]`, the default and the only browser-dependent symbol.

- [ ] **Step 1: Write the failing test**

`tests/test_brains_capture.py`. The seam is the point: every test here injects a fake `shoot` and no test launches a browser.

```python
def test_times_span_one_loop_without_repeating_the_seam():
    """The last frame must not duplicate frame zero, or the loop stutters."""
    assert capture.times(4, 2.0) == [0.0, 0.5, 1.0, 1.5]

def test_frames_asks_the_shooter_for_one_image_per_time():
    seen = {}
    def shoot(svg, times, width, height):
        seen.update(times=times, width=width, height=height)
        return [b"png"] * len(times)
    out = capture.frames("<svg/>", count=3, duration=3.0, shoot=shoot)
    assert len(out) == 3
    assert seen["times"] == [0.0, 1.0, 2.0]
    assert (seen["width"], seen["height"]) == (figures.W, figures.H)

def test_a_shooter_that_returns_the_wrong_count_is_an_error():
    with pytest.raises(ValueError, match="3 frames"):
        capture.frames("<svg/>", count=3, duration=3.0, shoot=lambda *a: [b"png"])

def test_capture_skips_cleanly_when_no_browser_is_installed():
    """CI installs fonttools and brotli and nothing else."""
    pytest.importorskip("playwright")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_brains_capture.py -q`
Expected: FAIL — no module `tools.brains.capture`.

- [ ] **Step 3: Implement `capture.py`**

`chrome_shoot` inlines the SVG into a blank page — referenced via `<img>` it is frozen and exposes no `contentDocument` — then per time: `svg.pauseAnimations()`, `svg.setCurrentTime(t)`, and `document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000 })`, screenshotting with `omit_background=True`. Do not use `--virtual-time-budget`: it freezes composited transforms at 0 while SMIL advances, and it is not reproducible across runs.

```python
def chrome_shoot(svg, times, width, height):
    from playwright.sync_api import sync_playwright  # import inside: CI has no browser
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_brains_capture.py -q`
Expected: PASS.

- [ ] **Step 5: Prove the seek against a real browser, by hand**

Install once: `.venv/bin/pip install playwright==1.56.0 && .venv/bin/playwright install chromium`. Capture frame 0 and a mid-loop frame of `left-brain.svg` and confirm they differ, and that frame 0 is the complete drawing. Record the pin in `tools/brains/README.md`.

- [ ] **Step 6: Commit**

```bash
git add tools/brains/capture.py tools/brains/README.md tests/test_brains_capture.py
git commit -m "feat: capture animated svg frames by explicit seek"
```

---

### Task 4: Encode the GIF

**Files:**
- Create: `tools/brains/encode.py`
- Create: `tests/test_brains_encode.py`

**Interfaces:**
- Produces: `encode.ffmpeg_version() -> tuple[int, int]`; `encode.gif(frames: list[bytes], out: pathlib.Path, *, delay_cs: int, colours: int = 2, version: tuple[int, int] | None = None) -> None` where `version` defaults to `ffmpeg_version()` and exists so the floor check is testable without a second ffmpeg on the machine; `encode.palette(path: pathlib.Path) -> tuple[list[tuple[int, int, int]], int | None]` returning the global colour table and the transparent index, read from the GIF header rather than through a decoder library.

- [ ] **Step 1: Write the failing test**

`tests/test_brains_encode.py`:

```python
def test_a_delay_below_the_honoured_floor_is_refused():
    """0 and 1 are clamped *up* to 100ms by Chromium and Firefox: asking for
    the fastest gives you the slowest."""
    with pytest.raises(ValueError, match="2cs"):
        encode.gif([b""], tmp, delay_cs=1)

def test_ffmpeg_below_six_is_refused():
    """`atkinson` does not exist before 6.0, and the fallback is 25% larger."""
    with pytest.raises(RuntimeError, match="6.0"):
        encode.gif(..., version=(5, 1))

def test_the_encoded_palette_is_one_visible_colour_and_one_transparent():
    table, transparent = encode.palette(out)
    assert transparent is not None
    assert len([c for i, c in enumerate(table) if i != transparent]) == 1

def test_the_gif_loops_forever():
    assert b"NETSCAPE2.0" in out.read_bytes()

def test_palette_reads_a_two_entry_table_from_a_known_gif():
    """Pinned against a fixture rather than against our own encoder, so a
    change in ffmpeg's output cannot silently satisfy both sides."""
```

The last test's fixture is a 2-colour transparent GIF built once with ffmpeg and committed under `tests/fixtures/`.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_brains_encode.py -q`
Expected: FAIL — no module `tools.brains.encode`.

- [ ] **Step 3: Implement `encode.py`**

Two ffmpeg passes over the PNG frames, piped rather than written to disk. Palette generation must reserve the transparent entry and cap colours hard — re-encoding the reference GIF with `max_colors=32` grew it from 117 KB to 291 KB.

```
palettegen=max_colors={colours}:reserve_transparent=1:stats_mode=diff
paletteuse=dither=atkinson:diff_mode=rectangle:alpha_threshold=128
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_brains_encode.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/brains/encode.py tests/test_brains_encode.py tests/fixtures/
git commit -m "feat: encode frames to a two-entry transparent gif"
```

---

### Task 5: Build entrypoint and the parity check

**Files:**
- Create: `tools/brains/parity.py`
- Create: `tools/brains/build.py`
- Create: `tests/test_brains_parity.py`
- Create: `tests/test_brains_build.py`

**Interfaces:**
- Consumes: `figures.load`, `capture.frames`, `encode.gif`.
- Produces: `parity.PREVIEW: pathlib.Path`, the module-level default location, patchable in tests; `parity.preview_root() -> pathlib.Path | None` returning `None` when `PREVIEW` is absent; `parity.regenerate(name: str, root: pathlib.Path) -> str`; `parity.diff(name: str, *, regenerate=None) -> str | None` where `None` means match and `regenerate` defaults to `parity.regenerate` bound to `preview_root()`; `build.main(argv: list[str] | None = None) -> int`, writing `gists/<Title>.gif`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parity_skips_when_the_preview_is_not_on_this_machine(monkeypatch):
    """A clone of this repo alone must run green."""
    monkeypatch.setattr(parity, "PREVIEW", pathlib.Path("/nope"))
    assert parity.preview_root() is None

def test_parity_reports_a_difference_when_the_vendored_copy_drifted():
    assert "left-brain" in parity.diff("left-brain", regenerate=lambda *a: "<svg/>")

def test_parity_is_silent_when_they_match():
    assert parity.diff("left-brain", regenerate=figures.load) is None

def test_build_writes_the_gist_filename_github_shows_as_the_card_title():
    """The filename is the only label the card carries."""
    build.main(["left-brain"])
    assert (ROOT / "gists" / "Left Brain.gif").exists()

def test_build_writes_nothing_under_assets():
    """`git add assets` in the workflow would commit it on every run."""
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_brains_parity.py tests/test_brains_build.py -q`
Expected: FAIL — no modules.

- [ ] **Step 3: Implement `parity.py` and `build.py`**

`regenerate` runs the preview's `brains.js` under node against a stubbed DOM, the way `test/dom-stub.mjs` does, and returns the SVG for comparison with the provenance comment stripped. `build.main` takes figure names as arguments, defaulting to all of `figures.NAMES` present on disk.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests -q`
Expected: PASS, whole suite.

- [ ] **Step 5: Check coverage on everything new**

Run: `.venv/bin/python -m pytest tests -q --cov=tools.brains --cov-report=term-missing`
Expected: ≥90% on every `tools/brains` module.

- [ ] **Step 6: Commit**

```bash
git add tools/brains/parity.py tools/brains/build.py tests/test_brains_parity.py tests/test_brains_build.py
git commit -m "feat: build the brain gifs and check vendored parity"
```

---

### Task 6: Tracer bullet — one hemisphere, live

Stop here and look before building the second half. This task writes no code.

- [ ] **Step 1: Build the GIF**

Run: `.venv/bin/python -m tools.brains.build left-brain`
Expected: `gists/Left Brain.gif` exists, under 200 KB.

- [ ] **Step 2: Confirm frame zero is the whole drawing**

Extract frame 0 alone and view it. Expected: complete, not partial.

- [ ] **Step 3: Commit the master**

```bash
git add "gists/Left Brain.gif" && git commit -m "feat: add the left hemisphere card"
```

- [ ] **Step 4: Publish and pin**

Create a public gist with the file named `Left Brain.gif`, then pin it by hand — there is no pinning API, and `updateUserListsForItem` governs lists, not profile pins.

- [ ] **Step 5: Look at the real card in both themes**

Expected: the drawing reads at 100px, the card surface shows through on both themes, and the motion is a loop rather than a flicker. **Gate: if it does not read at this size, revisit Task 1's geometry before starting the right hemisphere.**

---

### Task 7: The right hemisphere

Same path as Tasks 1, 2 and 6, for the half that argues with the first.

**Files:**
- Modify: `~/personal/design-preview/site/assets/brains.js`
- Modify: `~/personal/design-preview/test/brains.mjs`
- Create: `tools/brains/right-brain.svg`

- [ ] **Step 1: Extend the preview invariants to `"right"`**

Parametrise `test/brains.mjs` over both sides. Every Global Constraint still holds — the right half breaks the **grid**, not the palette, the size, the type ban or the motion budget. Add one assertion that it is in fact off-grid, so "organic" cannot silently regress to a second orthogonal drawing:

```js
assert(!onFourGrid(svg), "the right half is deliberately off the 4px grid");
```

and the mirror assertion on the left, that it is on it.

- [ ] **Step 2: Run to verify the right-side assertions fail**

Run: `node test/brains.mjs`
Expected: FAIL — `brainFigure(s, "right")` not implemented.

- [ ] **Step 3: Draw the right hemisphere**

Round, organic, floating off the grid, per the spec's accepted decision that the halves disagree. Fabric has no vocabulary for this, so it is invention: curves rather than orthogonal elbows, and no obligation to the 4px grid. It keeps one accent colour, no type, and frame-zero completeness.

- [ ] **Step 4: Run the preview suite**

Run, from the preview root: `node test/brains.mjs && node test/panels.mjs && node test/smoke.mjs && python3 test/unused_tokens.py`
Expected: all pass.

- [ ] **Step 5: Vendor, build, and verify**

Regenerate `tools/brains/right-brain.svg`, then: `.venv/bin/python -m pytest tests -q` and `.venv/bin/python -m tools.brains.build right-brain`.

- [ ] **Step 6: Commit**

```bash
git add tools/brains/right-brain.svg "gists/Right Brain.gif"
git commit -m "feat: add the right hemisphere card"
```

- [ ] **Step 7: Publish, pin, and order the six**

Publish as `Right Brain.gif`, pin it, and order the pins so the two gists take row one and the four repos fall into their intended columns. At one pin per row the repo-to-column mapping is lost by GitHub's reflow and that is accepted.

Then look at the finished pair on both GitHub themes at the real 100px height. Expected: the halves read as one piece and visibly disagree — the left orthogonal and gridded, the right round and floating.

- [ ] **Step 8: Push**

```bash
git push origin main
```

Docs and `tools/brains/**` only — the profile workflow's `paths:` filter is scoped to `tools/profile/**`, so this triggers nothing.
