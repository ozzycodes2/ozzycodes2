# Backporting a design change from the preview

The panels in this directory are a **port**. The drawing lives in the
`design-preview` repo, at `site/assets/panels.js`, rendered on each system's
`Panels` tab. That file is the reference; `present/console.py` and
`present/panels/*.py` follow it. A change made here and not there leaves two
renderers disagreeing about one drawing, and nothing will tell you which is
right.

Default path: **change the preview first, look at it, then port.** The preview
is vanilla JS with no build step and no deps, so the loop is seconds long. Only
reverse this for something that exists solely in the README — the slice
pairing, the `<picture>` tags, the font subset.

Preview tree: `~/Documents/personal/design-preview` (not a git repo — no commit
step, and no history to recover a mistake from; read before you overwrite).

## 1. Change the preview and prove it

```bash
cd ~/Documents/personal/design-preview
python3 build.py            # systems/*.md -> site/data.js. Stock python3, no deps.
node test/panels.mjs        # geometry, contrast and accent invariants
node test/smoke.mjs         # every tab of every system renders
python3 test/unused_tokens.py
open site/index.html        # file:// works; data.js is a <script>, not a fetch
```

`build.py` reads a hand-rolled YAML/markdown subset and writes
`window.DESIGN_SYSTEMS`. If you touched a `systems/DESIGN-*.md` front matter,
re-run it or the site still shows the old tokens.

`unused_tokens.py` matches declared tokens at the 2-space level. `mine-final`
should report **0 unspent**: a token nothing references is either dead or a
component that forgot to use it.

Add the assertion before you port. Then **mutation-test it** — break the
renderer the obvious way and confirm the new assertion fails. A green run on an
assertion that cannot fail is the failure mode this pair of repos invites.

## 2. Read the reference out of node

`test/dom-stub.mjs` installs the globals and loads `data.js` plus the three
asset scripts in page order. Import it and you have `DESIGN_SYSTEMS`,
`panelSlices`, `panelTheme`, `applyTheme`, `themeNames`, `mixHex`, `contrast`,
`PANEL_CONTENT`.

```js
import "/Users/.../design-preview/test/dom-stub.mjs";
const s = window.DESIGN_SYSTEMS.find((x) => x.slug === "mine-final");
for (const name of themeNames(s)) {
  applyTheme(s, name);                       // NOT prepare(s, name)
  for (const p of panelSlices(s)) writeFileSync(`/tmp/preview-slices/${name}-${p.file}`, p.svg);
}
```

Two traps, both of which cost an hour once:

- `applyTheme(system, name)` sets `system.colors` then calls `prepare`.
  `prepare` takes **only** the system and reads `system.colors`, so
  `prepare(s, name)` silently returns the first theme for both names.
- Do not hand-roll the loader with `(0,eval)` per file — each file gets its own
  `const`/`let` scope and the later files cannot see the earlier ones. The stub
  uses `vm.runInThisContext`, which is why it works. Just import the stub.

## 3. Map the change onto the port

| preview (`site/assets/panels.js`) | here |
|---|---|
| `panelTheme`, `legible` | the pinned `LIGHT`/`DARK` in `present/console.py` |
| `mixHex` | `console.mix` |
| `tx`, `heading`, `titleBar`, `slice`, `band` | `console.tx/heading/title_bar/slice_svg` |
| `ago`, `toGrid`, `num` | `console.ago/to_grid/num` |
| `wrap` | `projects._wrap` — panel-local here, not in `console` |
| `panelHeader` … `panelFooter` | `present/panels/header.py` … `present/panels/footer.py` |

`panelTheme` derives seven roles from the raw tokens, correcting `dim`/`faint`
to 4.5:1 and `accent` to 3:1 against the canvas. Python does **not** re-derive
them — `console.LIGHT`/`DARK` are the derived values, pinned literally, and
`tests/test_console.py::PREVIEW` is the assertion holding them to the preview's
output. A test that recomputed them the way `console.py` does would pass
whatever `console.py` said. When a token moves, read the new values out of
`panelTheme()` under node and paste them into both places.

### Rounding

`console.mix` rounds **half away from zero**, not half to even as Python's
`round` does, because the preview rounds through `Math.round`. A channel landing
on exactly .5 is common in an evenly spaced ramp — it is what put the dark
skyline's second bucket one unit off the browser's. Same reason `stats._counters`
writes `int(x + 0.5)` for the private share.

## 4. Deviations that are deliberate — do not "fix" them

The README is not a browser. These differences from the preview are load
bearing, and more than one has been reintroduced by someone making the two files
match:

1. **`RAIL_W = 2` vs `EDGE_W = 1`.** Each slice is rasterised at its intrinsic
   880px and bitmap-resampled to the page column, so a 1px `crispEdges` rail
   lands on one device column in a tall slice and two in a short one — the frame
   visibly steps at the seam. Rails are 2px; everything a panel draws is 1px.
2. **`shape-rendering="crispEdges"` on rules.** Same resample. The preview has
   no equivalent because a browser is not resampling anything.
3. **The projects panel splits into half-width slices.** GitHub strips `<a>`
   inside a rendered SVG, so the only way a card can be a link is for the card to
   *be* an image inside an `<a>` in the README markdown.
4. **The projects row gap is 36px, not 40.** A card is 164px, the slice height
   has to be a multiple of `ROW`, and 164 + 20 is not — the 18px left over at
   each end puts 36px between the rows. Geometry, not taste.
5. **`align="top"` on every `<img>`.** Without it GitHub's markdown renderer
   baseline-aligns consecutive half-width slices and the frame seams. It goes on
   the `<img>`, which is the element actually laid out, not the `<picture>`.
   `readme.py` owns this; no preview equivalent.
6. **Four embedded font faces.** GitHub strips `<link>` and off-origin `url()`,
   so Inter 400/600 and JBM 400/700 are subset and inlined. SF Mono is asked for
   first and is not redistributable, hence the fallback stack.

## 5. What GitHub's sanitiser allows

Verified, not guessed. It strips `<script>`, external `<link>`, off-origin
`url()`, and `<a>`. It does not run SMIL. It keeps inline `<style>`, CSS
animations, and `data:` URLs.

**Nothing may animate in.** An SVG served as `<img>` paints frame zero and
stops, so an element that fades up from `opacity: 0` is simply invisible on the
profile. The live dot is the only animation and it works the other way round —
it starts opaque and `.live` only dims it. CONTRACT.md rule 11.

## 6. Port, test, publish

Panel rules are in `present/panels/CONTRACT.md`. Read it before touching a
panel; rule 6 (what the accent may touch) and rule 11 (above) are the two that
catch people.

```bash
R=~/Documents/personal/ozzycodes2
$R/.venv/bin/python -m pytest $R/tests -q --cov=tools.profile --cov-report=term-missing
```

90% on changed source, as everywhere. `console.py` and every panel currently sit
at 100%; keep them there rather than arguing about the threshold.

Then follow the publish steps in `CLAUDE.md` — render, `readme.py`, commit, push
to `main`, `gh run watch --exit-status`, `git pull --rebase`. The push is the
trigger; `workflow_dispatch` re-renders whatever is already on `main`, which is
the old design.

Rebasing onto `origin/main` conflicts in generated output — `README.md`,
`data/manifest.json`, `assets/`. Resolve by `git checkout --ours` on those paths
and re-running the renderer, never by hand-merging an SVG.

## 7. Verify the port against the reference

Content diverges on purpose: the preview reads a static snapshot
(`site/assets/panel-data.js`), this repo reads `tools/profile/data/*.json` from
the last fetch. So bar widths, dates and counts **will** differ. Compare the
shape of the markup, not bytes.

One exception. The languages ring is curated in both — `languages.json` here,
`stats.languages` in the snapshot there — so those two must hold the same
numbers, and a ring that differs between the repos is a missed port rather than
a stale fetch.

```bash
grep -o '<rect x="172" y="300"[^/]*/>' assets/dark/stats.svg /tmp/preview-slices/dark-stats.svg
```

A per-slice colour census is the fastest whole-window check — it catches both a
missed port and an accent that leaked somewhere it does not belong:

```bash
for f in assets/dark/*.svg; do printf "%-26s %s\n" "$(basename $f)" "$(grep -o '#ef6306' $f | wc -l)"; done
```

Expected, and worth re-deriving rather than trusting this table if the doctrine
changes: header 1 (the live dot — the header draws no section heading), stats 1
(the rule; six counters are a set of equals), contribution-city 3 (rule + legend
circle + the peak block's saturated wall), stack 3 (rule + the focal slab's dot +
the leading language's ray), projects 1, projects-N 0, footer 0.

Finally, look at it. `preview.py` writes both themes side by side, which is the
only way to see a seam or a contrast failure without pushing:

```bash
$R/.venv/bin/python $R/tools/profile/render.py
$R/.venv/bin/python $R/tools/profile/preview.py && open $R/assets/preview.html
```

## 8. Watch for divergence the tests cannot see

The pinning tests cover theme roles and per-panel geometry. They do not cover
*content* logic, and that is where the two renderers have actually drifted:

- A bug reached the README that the preview's snapshot hid, because the snapshot
  was exactly 26 weeks and `window_days` was not. The skyline trimmed its
  part-week off the near end and silently dropped the five most recent days —
  including the peak, so the legend keyed a block that was never drawn.
- When a panel's behaviour depends on the *shape* of the data, construct the
  awkward shape as a fixture in both suites. A snapshot that happens to be well
  formed proves nothing about a window that is not.
