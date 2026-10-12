"""Refreshes data/*.json from the GitHub API.

Writes four files, each the input to one or more panels:

  stats.json     headline counters, language byte totals, streaks
  calendar.json  [[iso date, count], ...] for the last 365 days
  projects.json  live stars/language for the repos profile.toml curates

PROFILE_TOKEN is a classic PAT with `repo` + `read:user`, SSO-authorized for
every organization whose work should count. Without that access the counters
silently drop to public-only; REQUIRE_PRIVATE makes that an error instead.

No repository, organization or owner *name* is ever requested for anything
beyond the repos profile.toml curates by hand. Organization work reaches the
profile only as counts and as language byte totals.
"""
import datetime
import json
import os
import pathlib
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


def graphql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token()}",
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
# bucketed by language — is not available: GitHub reports private work only as
# an undifferentiated `restrictedContributionsCount`, with no per-repository
# breakdown, so a commit-based chart would silently omit 1,130 of this year's
# 1,185 contributions and misreport the mix.
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

YEAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
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


def year_range(year, today):
    start = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
    end = min(datetime.datetime(year, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc),
              datetime.datetime.combine(today, datetime.time.max, datetime.timezone.utc))
    return start.isoformat(), end.isoformat()


def contributions_by_year(created_year, today):
    """Per-year totals and private counts, plus the raw calendar per year.

    When the token can see private repositories, contributionCalendar totals
    already include them; restrictedContributionsCount is the private subset,
    not an addition to it.
    """
    per_year, private, calendars = {}, {}, {}
    for year in range(created_year, today.year + 1):
        start, end = year_range(year, today)
        # `from` is a Python keyword, so the GraphQL variable goes in by name.
        result = graphql(YEAR_Q, login=USER, **{"from": start, "to": end})
        coll = result["user"]["contributionsCollection"]
        per_year[year] = coll["contributionCalendar"]["totalContributions"]
        private[year] = coll["restrictedContributionsCount"]
        calendars[year] = [(d["date"], d["contributionCount"])
                           for week in coll["contributionCalendar"]["weeks"]
                           for d in week["contributionDays"]]
    return per_year, private, calendars


def trailing_year(calendars, today):
    """The last 365 days of contributions, stitched across the year boundary."""
    cutoff = today - datetime.timedelta(days=364)
    days = sorted({d: n for cal in calendars.values() for d, n in cal}.items())
    return [[d, n] for d, n in days if datetime.date.fromisoformat(d) >= cutoff]


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


def check_private_visible(stats):
    """Abort when a token that should see private work reports none of it.

    A classic PAT that lacks `repo`, or that has not been SSO-authorized for an
    organization, is not rejected — it authenticates and returns a smaller
    answer. The counters then drop by an order of magnitude with no error, and
    the scheduled job commits the undercount as if it were correct. Set
    REQUIRE_PRIVATE on a profile that is known to have private contributions
    and the run fails instead.
    """
    if not os.environ.get("REQUIRE_PRIVATE"):
        return
    if stats["private_all"]:
        return
    sys.exit(
        "error: the token reports 0 private contributions, so the counters "
        "would undercount. A classic PAT needs the `repo` scope, and needs "
        "'Configure SSO' authorization for each SAML organization."
    )


def main():
    today = datetime.date.today()
    config = tomllib.loads((HERE / "profile.toml").read_text())

    stats, calendar = build_stats(today)
    check_private_visible(stats)
    write("stats.json", stats)
    write("calendar.json", calendar)
    write("projects.json", build_projects(config))


if __name__ == "__main__":
    main()
