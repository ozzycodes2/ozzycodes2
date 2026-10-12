"""Refreshes data/*.json from the GitHub API.

Writes four files, each the input to one or more panels:

  stats.json     headline counters, language byte totals, streaks
  calendar.json  [[iso date, count], ...] for the last 365 days
  activity.json  recent releases and pushes, public repos only
  projects.json  live stars/language for the repos profile.toml curates

PROFILE_TOKEN is a classic PAT with `repo` + `read:user`; with it, private
repositories contribute to counters and language totals. Without it the job
falls back to GITHUB_TOKEN and sees public data only. Private repository
*names* are never written to any of these files.
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

ACTIVITY_Q = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        description
        pushedAt
        primaryLanguage { name }
        releases(last: 3) { nodes { tagName publishedAt url } }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 1) { nodes { committedDate messageHeadline url } }
            }
          }
        }
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


def build_stats(today):
    user = graphql(PROFILE_Q, login=USER)["user"]
    repos = user["repositories"]["nodes"]

    languages = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            languages[edge["node"]["name"]] = languages.get(edge["node"]["name"], 0) + edge["size"]

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


def build_activity(limit=6, per_repo=2, max_age_days=550):
    """Recent public releases and commits, newest first.

    Capped per repository so one busy project cannot fill the panel, and
    cut off by age so a dormant repo's last commit from years ago does not
    get presented as recent activity. Returning fewer than `limit` events
    is expected; the panel sizes itself to what it gets.
    """
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=max_age_days)).isoformat()
    nodes = graphql(ACTIVITY_Q, login=USER)["user"]["repositories"]["nodes"]
    events = []
    for repo in nodes:
        for release in repo["releases"]["nodes"]:
            events.append({"kind": "release", "repo": repo["name"],
                           "title": release["tagName"], "url": release["url"],
                           "at": release["publishedAt"],
                           "language": (repo["primaryLanguage"] or {}).get("name")})
        target = repo["defaultBranchRef"] and repo["defaultBranchRef"]["target"]
        for commit in (target or {}).get("history", {}).get("nodes", []):
            events.append({"kind": "commit", "repo": repo["name"],
                           "title": commit["messageHeadline"], "url": commit["url"],
                           "at": commit["committedDate"],
                           "language": (repo["primaryLanguage"] or {}).get("name")})
    events.sort(key=lambda e: e["at"], reverse=True)

    kept, seen = [], {}
    for event in events:
        if event["at"] < cutoff or seen.get(event["repo"], 0) >= per_repo:
            continue
        seen[event["repo"]] = seen.get(event["repo"], 0) + 1
        kept.append(event)
        if len(kept) == limit:
            break
    return kept


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
    write("activity.json", build_activity())
    write("projects.json", build_projects(config))


if __name__ == "__main__":
    main()
