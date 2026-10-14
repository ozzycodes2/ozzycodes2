# ozzycodes2

GitHub profile README, rendered as one terminal window sliced into consecutive
SVGs. `tools/profile/README.md` is the pipeline; `tools/profile/panels/CONTRACT.md`
is the panel API — read it before touching a panel.

## Publishing a profile change

Any change to the profile is finished only when it is live. Do not stop at the
local render, and do not ask whether to push — this is the standing go-ahead.

1. Re-render: `.venv/bin/python tools/profile/render.py`, then `readme.py`.
2. Run the suite. 90% coverage on changed source, as everywhere.
3. Commit to `main` and push. The push *is* the trigger: the workflow fires on
   `push` to `main` under `paths: tools/profile/**`. A `workflow_dispatch`
   without a push re-renders whatever is already on `main`, which is the old
   design — it is the wrong tool for a change you just made.
4. Watch it to green: `gh run watch <id> --exit-status`.
5. `git pull --rebase` afterwards. The job commits `chore: refresh profile` on
   top, so local `main` is one behind the moment it succeeds.

Rebasing onto `origin/main` usually conflicts in generated output — the README
block, `data/manifest.json`, `assets/`. Resolve by re-running the renderer, not
by hand-merging.

Deletions and anything outside `tools/profile/` still need a check first; this
authorization covers rendering changes reaching the profile, not the repo at
large.
