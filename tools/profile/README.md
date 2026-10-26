# How this README works

The profile page is one terminal window. It is not a live service and not a
third-party widget — it is a directory of static SVG files in this repo, which
a GitHub Action regenerates once a day and commits.

## The pipeline

```
profile.toml ─┐
              ├─> render.py ─> assets/{light,dark}/*.svg ─> readme.py ─> README.md
fetch.py ─────┘                 + manifest.json
   │
   └─> data/*.json
```

| Step | Reads | Writes |
|---|---|---|
| `fetch.py` | the public profile page, GitHub GraphQL API | `data/stats.json`, `calendar.json`, `projects.json` |
| `render.py` | `profile.toml`, the rosters, `data/*.json` | `assets/<theme>/**.svg`, `data/manifest.json` |
| `preview.py` | `data/manifest.json` | `assets/preview.html` — both themes side by side |
| `readme.py` | `data/manifest.json` | the block between the markers in `README.md` |

Each step is independently runnable, and only the step that owns a file ever
writes it. `fetch.py` never draws; `render.py` never calls the network, so it
can be re-run offline against the committed JSON while iterating on a panel.

## The three layers

Those four scripts are wiring. The work sits in three packages, and which one a
change belongs in is decided by whether it touches the outside world, computes
a number, or draws:

| Layer | Holds | May import |
|---|---|---|
| `sources/` | every request and every file: `github.py` (GraphQL and the contributions page), `files.py` (the committed TOML and rosters), `store.py` (`data/*.json`), `assets.py` (SVGs, the preview, `README.md`) | nothing above it |
| `transform/` | derivation with no I/O: `stats.py` (counters, streaks, language bytes), `layout.py` (the manifest and its row grouping), `config.py` (the mapping panels read) | nothing |
| `present/` | markup only: `console.py` (the frame), `panels/`, `slices.py` (the registry), `readme.py` and `preview.py` (the two emitters), `fonts.py` | `transform/` |

`tests/test_layers.py` enforces that table by walking each module's imports, so
the rule fails a run rather than drifting. Three things it buys:

- The arithmetic is tested against literals. `transform/stats.py` takes fetched
  records as arguments, so `streaks` and the private-share cap need no stubbed
  network to pin.
- A panel cannot reach for data. Everything it draws arrives in `cfg` and
  `data`, including the brand marks, which `render.py` reads and
  `transform/config.py` folds in — the stack panel used to open that file
  itself at import time.
- The row grouping has one implementation. `readme.py` and `preview.py` both
  call `transform/layout.py`, so a change to how a split row is packed cannot
  make the preview disagree with what the README will render.

The one file read above the data layer is `present/fonts.py`, which opens the
vendored woff2 faces beside it. They are pinned resources rather than data, and
deferring that read would mean threading a loader through `slice_svg` and every
panel that calls it.

`data/` holds the committed JSON the pipeline generates; the data *layer* is
`sources/`. They are different things with similar names, which is why neither
is called the other.

## Why SVG files instead of a badge service

Rendering locally and committing the result means the profile has no runtime
dependency on anything but GitHub's own CDN: no rate limits, no outage from a
third party, no request from a visitor's browser to a server that logs it. The
numbers are only ever as fresh as the last run, which for a profile page is the
right trade.

GitHub sanitises SVG it renders in markdown. It strips `<script>`, external
`<link>`, and `url()` pointing off-origin, and it does not run SMIL. It *does*
keep inline `<style>`, CSS animations, filters, and `data:` URLs. That is why
every slice embeds its own base64 woff2 subset of the faces it uses: a webfont
reference would simply be dropped and the panels would fall back to whatever the
viewer happens to have.

Inter is embedded for that reason. SF Mono is not, because it is not
redistributable — the mono stack asks for it first, which resolves on macOS, and
falls back to an embedded JetBrains Mono subset everywhere else.

## Why the window is sliced

A single tall SVG could not be partly clickable — one image, one link. Slicing
the frame into consecutive images lets the README wrap individual slices in
their own `<a>`, which is how the project cards work. Each slice
redraws the side rails, and because every height is a multiple of 40px the seams
land on the grid; only the first slice caps the top and draws the title bar,
only the last closes the frame.

## Why there are two of everything

Both themes are the Fabric token set — `dark` and `light`. Panels name
roles, never colours, so one renderer produces both: `render.py` runs every
panel once per theme and `readme.py` pairs the output in a `<picture>` with a
`prefers-color-scheme: dark` source, which GitHub honours. Light is the `<img>`
fallback, so a client that ignores `<picture>` still gets a readable console.

The two differ in palette and nothing else. Type, geometry and radii are the
same in both; a console that changed size with the colour scheme would be two
designs rather than one in two finishes.

The drawing itself is a port of the `Panels` tab in the `design-preview` site.
Its `site/assets/panels.js` is the reference, down to the per-element type sizes
— which is why those are a terminal's own scale rather than the token type
steps. `tests/test_console.py` pins the seven theme roles against what that
site derives from the tokens; each panel's tests pin its geometry.

## Adding or changing a panel

Content that is prose lives in `profile.toml` — headline, project blurbs. Two
rosters are JSON instead, because TOML cannot express either: `stack.json` maps
each category's tools to a pedestal height on a 1–5 ladder, key order being draw
order, top category first; `languages.json` maps a language to bytes and is the
polar ring in the same slice. Editing any of the three and pushing is enough; the
workflow re-renders on any change under `tools/profile/`.

`languages.json` is curated, not fetched. `data/stats.json` still carries what
the API reports and no panel reads it: whole-tree byte counts answer which
checkout is largest rather than which languages the work is in, and one
generated monorepo had been half the total. The number in the file is a
judgement about what the chart should say, so it is reviewed in a diff like the
prose is.

`logos/stack-logos.json` is the brand marks that roster draws, generated by the
preview's `vendor_logos.py` from Simple Icons (CC0 1.0) and Devicon (MIT). It
reaches the panel the way the rosters do — read by `sources/files.py`, folded
into `cfg` by `transform/config.py`. A tool with no entry falls back to mono
type at its cell's centre, so adding one to the roster without vendoring its
mark degrades rather than breaks.

A new panel is a module in `present/panels/` exposing `render(cfg, data, theme)`,
registered in `present/slices.py`'s `PANELS` list. It must read every colour off
the theme it is handed; a hardcoded hex renders the same in both schemes and will
be wrong in one of them. `present/panels/CONTRACT.md` is the API and the rules
about heights, rails, escaping, and accessible descriptions.

## Running it locally

```bash
python -m venv .venv && .venv/bin/pip install fonttools==4.62.1 brotli==1.2.0
GITHUB_TOKEN=$(gh auth token) .venv/bin/python tools/profile/fetch.py
.venv/bin/python tools/profile/render.py
.venv/bin/python tools/profile/preview.py   # assets/preview.html, both themes
.venv/bin/python tools/profile/readme.py
```

`render.py`, `preview.py` and `readme.py` need no token. The README cannot be
previewed as the README — GitHub picks one theme and the other stays hidden — so
`preview.py` writes a page carrying both.

A slice is rendered into an `<img>`, where a CSS animation paints its first
frame and stops. Nothing animates in for that reason — the live dot is the only
moving element and it starts opaque, so a screenshot needs no flags.

## Why the contribution counts come from a web page

Counting private work through the API does not work, and the reason is a
property of the API rather than of any token. GitHub's schema defines
`restrictedContributionsCount` as "a count of contributions made by the user
that **the viewer cannot access**", and the profile setting that exposes
private work says the same thing from the other side: it shows daily counts to
"people **without access** to those private repositories". Authenticating as
yourself makes you a viewer *with* access, so the anonymized disclosure stops
applying and the numbers fall back to whatever your credential can still reach.
Where an organization forbids personal access tokens, that is the public
subset. Measured on this profile for 2026: **259 through the API, 1,303 on the
profile page.**

So the counts and the daily calendar are read from
`github.com/users/<login>/contributions` with no credential attached — the same
fragment the profile page renders its graph from, and the same source
`sallar/github-contributions-chart`, `Platane/snk` and
`grubersjoe/github-contributions-api` use. Nothing is published that the
profile page does not already show to anyone, and there is no secret to rotate,
leak, or lose access with.

The cost is that the fragment is undocumented and unversioned. `calendar_year`
therefore checksums itself: the page's headline total is rendered by a
different code path than the grid, so a parse that drifts fails the run instead
of quietly committing a year of zeroes.

**The private count needs the opposite of a privileged token.** How much of
the year was private is reported by `restrictedContributionsCount`, and the one
scope that governs it is `read:user`: with it, `contributionsCollection`
switches from the anonymized aggregate to per-repository itemization, and the
field correctly drops to zero — nothing is restricted from a viewer who can
reach it. So `fetch.py` asks for that field with `outsider_token()`, which
skips `PROFILE_TOKEN` and takes `GITHUB_TOKEN` instead. Actions' own job token
has no scopes at all and is perfect for it; so is `gh auth token`, whose
scopes do not include `read:user`. With no such credential available the count
is reported as zero and the panel drops the counter rather than guess.

`PROFILE_TOKEN` is optional and never touches the contribution counts. It is
read only for repository and pull request metadata: set it to a classic PAT
with `repo` and `read:user` and the repo tally includes private repositories it
can reach; leave it unset and the job falls back to `GITHUB_TOKEN` and reports
public repositories only. The counts therefore shift with the credential — a
local run through `gh` reaches more repositories than the PAT in CI, and the
difference has been large enough to change which number the panel states.

Private repository, organization and owner *names* are never requested, never
written to `data/`, and never rendered. Organization work reaches the profile
only as counts and language byte totals, and a test pins the absence of those
fields from the query.

## Determinism

The daily job commits only when something actually changed, so the history
stays readable. That requires byte-identical output from identical input, which
two things would otherwise break:

- `fontTools` stamps a build timestamp into the font tables, so the subsetter is
  called with `recalcTimestamp=False`.
- Every value the city derives comes from the calendar itself, never from
  `random` or from the order in which blocks were emitted, so one extra
  contribution does not reshuffle the plan and rewrite every file.

`fonttools` and `brotli` are pinned in the workflow for the same reason: a minor
upgrade can change how a subset is packed and rewrite every file.
