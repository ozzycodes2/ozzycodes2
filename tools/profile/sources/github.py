"""Every network call the profile makes, and the wire formats they come back in.

Three sources, and which credential each gets is load-bearing rather than
incidental. Contribution totals and the daily calendar come from the public
profile page with none at all (`calendar_year`). The private share of those
totals comes from the GraphQL API asked with a token that must lack `read:user`
(`outsider_token`). Everything else — repositories, languages, pull requests —
comes from the same API asked with the most privileged token there is.

No repository, organization or owner *name* is ever requested for anything
beyond the repos profile.toml curates by hand. Organization work reaches the
profile only as counts and as language byte totals.

Functions here return records, never summaries: `contributed_repos` pages
through the API and hands back the nodes it saw without counting them, because
counting is the transform layer's job and a count cannot be re-derived from
itself.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

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


def profile():
    """The account's own totals and the repositories it owns."""
    return graphql(PROFILE_Q, login=USER)["user"]


def contributed_repos():
    """`(nodes, orgs)` for every repository worked in, owned or not.

    Pages to exhaustion: a 100-repo page cap would silently truncate the
    language totals. The nodes come back as the API shaped them — summing them
    is `transform.stats.aggregate_repos`.
    """
    nodes, orgs, after = [], 0, None
    while True:
        result = graphql(CONTRIB_REPOS_Q, login=USER, after=after)["user"]
        orgs = result["organizations"]["totalCount"]
        page = result["repositoriesContributedTo"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return nodes, orgs
        after = page["pageInfo"]["endCursor"]


def restricted_count(outsider, start, end):
    """How much of a window was private, per the one field that reports it."""
    # `from` is a Python keyword, so the GraphQL variable goes in by name.
    coll = graphql(YEAR_Q, _token=outsider, login=USER,
                   **{"from": start, "to": end})["user"]["contributionsCollection"]
    return coll["restrictedContributionsCount"]


def repository(owner, name):
    """Live stars, forks, push time and primary language for one named repo."""
    return graphql(REPO_Q, owner=owner, name=name)["repository"]


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
