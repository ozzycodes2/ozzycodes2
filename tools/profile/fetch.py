"""Refreshes data/*.json from GitHub.

Wiring only: `sources.github` makes the requests, `transform.stats` turns the
records into numbers, `sources.store` writes them. Three files come out, each
the input to one or more panels:

  stats.json     headline counters, language byte totals, streaks
  calendar.json  [[iso date, count], ...] for the last 365 days
  projects.json  live stars/language for the repos profile.toml curates

Which credential each source gets is load-bearing rather than incidental — see
sources/github.py.
"""
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.profile.sources import files, github, store
from tools.profile.transform import stats as transform


def collect_years(created_year, today):
    """Each year's calendar from the page, and its private share from the API.

    Two sources, neither carrying both halves, walked year by year. The private
    figure is asked with `outsider_token()`, which must *lack* `read:user`; with
    no such credential available it is reported as zero and the panel drops the
    counter rather than guess.
    """
    outsider = github.outsider_token()
    calendars, restricted = {}, {}
    for year in range(created_year, today.year + 1):
        calendars[year] = github.calendar_year(year)
        if not outsider:
            restricted[year] = 0
            continue
        start, end = transform.year_range(year, today)
        restricted[year] = github.restricted_count(outsider, start, end)
    return calendars, restricted


def main():
    today = datetime.date.today()
    config = files.profile_config()

    user = github.profile()
    nodes, orgs = github.contributed_repos()
    languages, contributed = transform.aggregate_repos(nodes, orgs)
    calendars, restricted = collect_years(
        datetime.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00")).year,
        today)

    stats, calendar = transform.build_stats(
        user, languages, contributed, calendars, restricted, today)

    entries = config.get("projects", [])
    records = [github.repository(*entry["repo"].split("/", 1)) for entry in entries]

    for name, payload in (("stats.json", stats),
                          ("calendar.json", calendar),
                          ("projects.json", transform.build_projects(entries, records))):
        store.write(name, payload)
        print(f"wrote data/{name}")


if __name__ == "__main__":
    main()
