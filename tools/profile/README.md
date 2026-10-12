# How this README works

The profile page is one terminal window. It is not a live service and not a
third-party widget — it is a directory of static SVG files in this repo, which
a GitHub Action regenerates once a day and commits.

## The pipeline

```
profile.toml ─┐
              ├─> render.py ─> assets/*.svg ─> readme.py ─> README.md
fetch.py ─────┘                 + manifest.json
   │
   └─> data/*.json
```

| Step | Reads | Writes |
|---|---|---|
| `fetch.py` | GitHub GraphQL API | `data/stats.json`, `calendar.json`, `projects.json` |
| `render.py` | `profile.toml`, `data/*.json` | `assets/**.svg`, `data/manifest.json` |
| `readme.py` | `data/manifest.json` | the block between the markers in `README.md` |

Each step is independently runnable, and only the step that owns a file ever
writes it. `fetch.py` never draws; `render.py` never calls the network, so it
can be re-run offline against the committed JSON while iterating on a panel.

## Why SVG files instead of a badge service

Rendering locally and committing the result means the profile has no runtime
dependency on anything but GitHub's own CDN: no rate limits, no outage from a
third party, no request from a visitor's browser to a server that logs it. The
numbers are only ever as fresh as the last run, which for a profile page is the
right trade.

GitHub sanitises SVG it renders in markdown. It strips `<script>`, external
`<link>`, and `url()` pointing off-origin, and it does not run SMIL. It *does*
keep inline `<style>`, CSS animations, filters, and `data:` URLs. That is why
every slice embeds its own base64 woff2 subset of JetBrains Mono: a webfont
reference would simply be dropped and the panels would fall back to whatever
monospace the viewer has.

## Why the window is sliced

A single tall SVG could not be partly clickable — one image, one link. Slicing
the frame into consecutive images lets the README wrap individual slices in
their own `<a>`, which is how the project cards work. Each slice
redraws the side rails and the background grid, and because every height is a
multiple of 40px the grid lines up across the seams; only the first slice draws
the top edge, only the last closes the frame.

## Adding or changing a panel

Content that is prose lives in `profile.toml` — headline, the stack table,
project blurbs. Editing it and pushing is enough; the workflow re-renders
on any change under `tools/profile/`.

A new panel is a module in `panels/` exposing `render(cfg, data)`, registered in
`render.py`'s `PANELS` list. `panels/CONTRACT.md` is the API and the rules about
heights, rails, escaping, and accessible descriptions.

## Running it locally

```bash
python -m venv .venv && .venv/bin/pip install fonttools==4.62.1 brotli==1.2.0
GITHUB_TOKEN=$(gh auth token) .venv/bin/python tools/profile/fetch.py
.venv/bin/python tools/profile/render.py
.venv/bin/python tools/profile/readme.py
```

`render.py` and `readme.py` need no token. To preview without pushing, open the
SVGs directly — but note the fade-in animations mean a screenshot taken at t=0
shows an empty frame. Force reduced motion to see the final state.

## The token

The workflow requires a repository secret named `PROFILE_TOKEN`: a classic PAT
with `repo` and `read:user`. It is what makes private repositories count toward
contribution totals, streaks, and language byte counts.

The workflow's built-in `GITHUB_TOKEN` also authenticates, but sees public data
only — totals drop to a small fraction with no error. The job checks for the
PAT and fails rather than committing an undercount that looks plausible.

Private repository *names* are never written to `data/` and never rendered —
only aggregate counts.

One API detail worth recording, because it is easy to get wrong and the error
is silent: when the token can see private repositories,
`contributionCalendar.totalContributions` **already includes** them.
`restrictedContributionsCount` is the private subset of that total, not an
addition to it. Summing the two double-counts every private contribution.

## Determinism

The daily job commits only when something actually changed, so the history
stays readable. That requires byte-identical output from identical input, which
two things would otherwise break:

- `fontTools` stamps a build timestamp into the font tables, so the subsetter is
  called with `recalcTimestamp=False`.
- The city's starfield comes from a fixed linear congruential sequence rather
  than `random`, which would reshuffle the sky on every run.

`fonttools` and `brotli` are pinned in the workflow for the same reason: a minor
upgrade can change how a subset is packed and rewrite every file.
