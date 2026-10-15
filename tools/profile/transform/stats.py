"""Turns fetched records into the three files panels read.

Every function here is pure: records in, numbers out, no request and no file.
That is what lets the arithmetic be tested against literals instead of against
a stubbed network, and what makes `fetch.py` a wiring script rather than a
place where aggregation hides next to a credential.
"""
import datetime


def year_range(year, today):
    """The UTC window covering one calendar year, clamped to today.

    Upper-bounded because the current year is still running: asking the API for
    December of a year that has not happened returns nothing useful and makes
    the window disagree with the calendar page's.
    """
    start = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
    end = min(datetime.datetime(year, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc),
              datetime.datetime.combine(today, datetime.time.max, datetime.timezone.utc))
    return start.isoformat(), end.isoformat()


def contributions_by_year(calendars, restricted):
    """Per-year totals from the page, and the private share capped to them.

    Neither source carries both halves. The profile page states the total but
    not its composition; the API states how much was private but disagrees with
    the page about the total — 1,227 against 1,303 for 2026 over the identical
    window, because asking as the account holder changes which contributions
    are counted at all. The page is taken as authoritative on the grounds that
    it is the number every visitor to the profile sees.

    The private figure therefore comes from a window the API measured and the
    page did not, so it is capped at the page's total: the counters can never
    claim more private work than there was work.
    """
    per_year = {year: sum(n for _, n in days) for year, days in calendars.items()}
    private = {year: min(restricted.get(year, 0), total)
               for year, total in per_year.items()}
    return per_year, private


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


def aggregate_repos(nodes, orgs):
    """Language bytes and plain counts over every repository worked in.

    Returns `(languages, counts)`. The counts are integers — how many
    repositories, how many private, how many under an organization, how many
    organizations — which is as much as the profile says about work that is not
    the author's to name.
    """
    languages = {}
    counts = {"repos": 0, "private": 0, "org": 0, "orgs": orgs}
    for repo in nodes:
        counts["repos"] += 1
        counts["private"] += bool(repo["isPrivate"])
        counts["org"] += bool(repo["isInOrganization"])
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            languages[name] = languages.get(name, 0) + edge["size"]
    return languages, counts


def build_stats(user, languages, contributed, calendars, restricted, today):
    """`(stats, calendar)` — the contents of stats.json and calendar.json."""
    repos = user["repositories"]["nodes"]
    per_year, private = contributions_by_year(calendars, restricted)
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


def build_projects(entries, records):
    """projects.json: each curated entry joined to the repo record fetched for it.

    `entries` is profile.toml's `[[projects]]` and `records` the API response
    for each, in the same order.
    """
    return [{
        "repo": entry["repo"],
        "stars": record["stargazerCount"],
        "forks": record["forkCount"],
        "pushed_at": record["pushedAt"],
        "language": (record["primaryLanguage"] or {}).get("name"),
    } for entry, record in zip(entries, records)]
