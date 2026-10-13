"""Refreshes data/*.json from two GitHub sources.

Writes three files, each the input to one or more panels:

  stats.json     headline counters, language byte totals, streaks
  calendar.json  [[iso date, count], ...] for the last 365 days
  projects.json  live stars/language for the repos profile.toml curates

Three sources, and which credential each gets is load-bearing rather than
incidental. Contribution totals and the daily calendar come from the public
profile page with none at all (`calendar_year`). The private share of those
totals comes from the GraphQL API asked with a token that must lack `read:user`
(`outsider_token`). Everything else — repositories, languages, pull requests —
comes from the same API asked with the most privileged token there is.

No repository, organization or owner *name* is ever requested for anything
beyond the repos profile.toml curates by hand. Organization work reaches the
profile only as counts and as language byte totals.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import tomllib
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
API = "https://api.github.com/graphql"
USER = os.environ.get("PROFILE_USER", "ozzycodes2")


def token():
    for name in ("PROFILE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    sys.exit("error: set PROFILE_TOKEN (or GITHUB_TOKEN) to a token with read:user")


def outsider_token():
    """A credential that must *lack* `read:user`, or None if there is none.

    Not least privilege — a different answer. `read:user` switches
    `contributionsCollection` out of the anonymized aggregate and into
    per-repository itemization, which drives
    `restrictedContributionsCount` to zero: there is nothing the viewer cannot
    access, so nothing is restricted. Without the scope the same field reports
    how much of the year was private, which is the only way GitHub states that
    number at all. PROFILE_TOKEN is skipped on purpose, since it carries
    `read:user` for the repository queries; Actions' `GITHUB_TOKEN` has no
    scopes and is ideal.
    """
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    return None


def graphql(query, _token=None, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {_token or token()}",
                 "Content-Type": "application/json",
                 "User-Agent": f"{USER}-profile-readme"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: GitHub API returned {exc.code}: {exc.read().decode()[:400]}")
    if "errors" in payload:
        sys.exit("error: " + "; ".join(e.get("message", "?") for e in payload["errors"]))
    return payload["data"]


PROFILE_Q = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests(states: MERGED) { totalCount }
    allPullRequests: pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        name
        isPrivate
        stargazerCount
        forkCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Repositories actually worked in, across every affiliation, so organization
# work counts toward the language totals and the repo tally. Deliberately asks
# for no `name` and no `owner`: the query cannot leak an employer's identity
# into data/ or into an error message even if one is later dumped verbatim.
# `includeUserRepositories` folds personal repos into the same list, which is
# what lets byte totals be summed without needing names to deduplicate.
#
# These are whole-tree byte counts, so the chart describes the codebases its
# author works in, not lines they wrote. The honest alternative — commits
# bucketed by language — is not available at all: GitHub itemizes contributions
# per repository only for repositories the credential can read, so a
# commit-based chart would silently omit roughly 1,000 of this year's 1,300
# contributions and misreport the mix.
CONTRIB_REPOS_Q = """
query($login: String!, $after: String) {
  user(login: $login) {
    organizations(first: 1) { totalCount }
    repositoriesContributedTo(
      first: 100, after: $after, includeUserRepositories: true,
      contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        isPrivate
        isInOrganization
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Asked only for the private count, and only ever with `outsider_token()`.
# Documented as "a count of contributions made by the user that the viewer
# cannot access" — so it answers truthfully only for a viewer who cannot.
YEAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      restrictedContributionsCount
    }
  }
}
"""


REPO_Q = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    stargazerCount
    forkCount
    pushedAt
    primaryLanguage { name }
  }
}
"""


# The fragment the profile page loads its contribution graph from. `from`
# selects the calendar year; the response is always Jan 1 to Dec 31 of it.
CALENDAR_URL = ("https://github.com/users/{login}/contributions"
                "?from={year}-01-01&to={year}-12-31")

# One <td> per day, then a sibling <tool-tip> keyed to it by id. The count only
# exists in the tooltip prose — the cell itself carries a 0-4 intensity level.
DAY_RE = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})" '
                    r'id="(contribution-day-component-[\d-]+)"')
TIP_RE = re.compile(r'for="(contribution-day-component-[\d-]+)"[^>]*>'
                    r'([^<]*)</tool-tip>')
COUNT_RE = re.compile(r"(\d+) contribution")
TOTAL_RE = re.compile(r">\s*([\d,]+)\s*contributions?\s*in", re.S)


def calendar_year(year):
    """One calendar year of daily contribution counts, as visitors see them.

    Sent unauthenticated, and that is the point rather than an economy.
    GitHub's "Include private contributions on my profile" setting governs what
    a *viewer without access* sees, and the schema says so outright:
    `restrictedContributionsCount` is "a count of contributions made by the
    user that the viewer cannot access". Querying the API as yourself makes you
    a viewer with access, so the anonymized disclosure does not apply and the
    numbers collapse to whatever your credential can still reach — which, when
    an organization forbids personal access tokens, is the public subset. For
    2026 that is 259 against the profile page's 1,303. Attaching no credential
    is therefore not a workaround but the only accurate reading.

    The fragment is undocumented and unversioned, which is the price. The
    headline total is rendered from a different code path than the grid, so it
    is used as a checksum: markup drift fails here instead of quietly
    publishing a year of zeroes.
    """
    url = CALENDAR_URL.format(login=USER, year=year)
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-readme"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = resp.read().decode()
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: profile calendar for {year} returned {exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(f"error: could not reach the profile calendar for {year}: {exc}")

    tips = dict(TIP_RE.findall(page))
    days = []
    for date, cell in DAY_RE.findall(page):
        found = COUNT_RE.match(tips.get(cell, ""))
        days.append((date, int(found.group(1)) if found else 0))
    if not days:
        sys.exit(f"error: no contribution days found for {year} — {url} changed shape")

    headline = TOTAL_RE.search(page)
    if headline:
        expected = int(headline.group(1).replace(",", ""))
        total = sum(n for _, n in days)
        if total != expected:
            sys.exit(f"error: parsed {total} contributions for {year} but the page "
                     f"says {expected} — {url} changed shape")
    return sorted(days)


def year_range(year, today):
    start = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
    end = min(datetime.datetime(year, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc),
              datetime.datetime.combine(today, datetime.time.max, datetime.timezone.utc))
    return start.isoformat(), end.isoformat()


def contributions_by_year(created_year, today):
    """Per-year totals and the private share of them, from two sources.

    Neither source carries both halves. The profile page states the total but
    not its composition; the API states how much was private but disagrees with
    the page about the total — 1,227 against 1,303 for 2026 over the identical
    window, because asking as the account holder changes which contributions
    are counted at all. The page is taken as authoritative on the grounds that
    it is the number every visitor to the profile sees.

    The private figure therefore comes from a window the API measured and the
    page did not, and is capped at the page's total so the counters can never
    claim more private work than there was work.
    """
    outsider, per_year, private, calendars = outsider_token(), {}, {}, {}
    for year in range(created_year, today.year + 1):
        days = calendar_year(year)
        calendars[year] = days
        per_year[year] = sum(n for _, n in days)
        private[year] = 0
        if not outsider:
            continue
        start, end = year_range(year, today)
        # `from` is a Python keyword, so the GraphQL variable goes in by name.
        coll = graphql(YEAR_Q, _token=outsider, login=USER,
                       **{"from": start, "to": end})["user"]["contributionsCollection"]
        private[year] = min(coll["restrictedContributionsCount"], per_year[year])
    return per_year, private, calendars


def trailing_year(calendars, today):
    """The last 365 days of contributions, stitched across the year boundary.

    Upper-bounded as well as lower: the profile page returns whole calendar
    years, so the current one arrives with every remaining day of December
    attached at zero.
    """
    cutoff = today - datetime.timedelta(days=364)
    days = sorted({d: n for cal in calendars.values() for d, n in cal}.items())
    return [[d, n] for d, n in days
            if cutoff <= datetime.date.fromisoformat(d) <= today]


def streaks(calendar, today):
    """(current, longest) run of consecutive contributing days.

    Today counts only if it already has contributions, so the streak never
    resets to zero just because the job ran before the first commit.
    """
    by_date = {datetime.date.fromisoformat(d): n for d, n in calendar}
    longest = run = 0
    for day in sorted(by_date):
        run = run + 1 if by_date[day] else 0
        longest = max(longest, run)

    current, day = 0, today
    if not by_date.get(today):
        day = today - datetime.timedelta(days=1)
    while by_date.get(day):
        current += 1
        day -= datetime.timedelta(days=1)
    return current, longest


def contributed_repos():
    """Every repository worked in, owned or not, aggregated without any names.

    Returns `(language bytes, counts)`. The counts are plain integers — how
    many repositories, how many private, how many under an organization, how
    many organizations — which is as much as the profile says about work that
    is not the author's to name.
    """
    languages, counts, after = {}, {"repos": 0, "private": 0, "org": 0, "orgs": 0}, None
    while True:
        result = graphql(CONTRIB_REPOS_Q, login=USER, after=after)["user"]
        counts["orgs"] = result["organizations"]["totalCount"]
        page = result["repositoriesContributedTo"]
        for repo in page["nodes"]:
            counts["repos"] += 1
            counts["private"] += bool(repo["isPrivate"])
            counts["org"] += bool(repo["isInOrganization"])
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                languages[name] = languages.get(name, 0) + edge["size"]
        if not page["pageInfo"]["hasNextPage"]:
            return languages, counts
        after = page["pageInfo"]["endCursor"]


def build_stats(today):
    user = graphql(PROFILE_Q, login=USER)["user"]
    repos = user["repositories"]["nodes"]
    languages, contributed = contributed_repos()

    created = datetime.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    per_year, private, calendars = contributions_by_year(created.year, today)
    calendar = trailing_year(calendars, today)
    current, longest = streaks(calendar, today)

    stats = {
        "updated": today.isoformat(),
        "year": today.year,
        "created_at": user["createdAt"],
        "followers": user["followers"]["totalCount"],
        "prs": user["allPullRequests"]["totalCount"],
        "prs_merged": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "repos_public": sum(1 for r in repos if not r["isPrivate"]),
        "repos_contributed": contributed["repos"],
        "repos_contributed_private": contributed["private"],
        "repos_contributed_org": contributed["org"],
        "orgs": contributed["orgs"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "contributions_year": per_year.get(today.year, 0),
        "contributions_all": sum(per_year.values()),
        "contributions_trailing": sum(n for _, n in calendar),
        "private_year": private.get(today.year, 0),
        "private_all": sum(private.values()),
        "streak_current": current,
        "streak_longest": longest,
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
    }
    return stats, calendar



def build_projects(config):
    out = []
    for entry in config.get("projects", []):
        owner, name = entry["repo"].split("/", 1)
        repo = graphql(REPO_Q, owner=owner, name=name)["repository"]
        out.append({
            "repo": entry["repo"],
            "stars": repo["stargazerCount"],
            "forks": repo["forkCount"],
            "pushed_at": repo["pushedAt"],
            "language": (repo["primaryLanguage"] or {}).get("name"),
        })
    return out


def write(name, payload):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote data/{name}")


def main():
    today = datetime.date.today()
    config = tomllib.loads((HERE / "profile.toml").read_text())

    stats, calendar = build_stats(today)
    write("stats.json", stats)
    write("calendar.json", calendar)
    write("projects.json", build_projects(config))


if __name__ == "__main__":
    main()
