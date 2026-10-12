"""Tests for the data layer: pure functions, plus the GraphQL plumbing stubbed."""
import datetime
import io
import json
import re
import sys
import urllib.error

import pytest

from tools.profile import fetch


# --- token selection -------------------------------------------------------

def test_token_prefers_profile_token(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "private")
    monkeypatch.setenv("GITHUB_TOKEN", "public")
    assert fetch.token() == "private"


def test_token_falls_back_to_job_token(monkeypatch):
    monkeypatch.delenv("PROFILE_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "public")
    assert fetch.token() == "public"


def test_token_exits_when_unset(monkeypatch):
    for name in ("PROFILE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="PROFILE_TOKEN"):
        fetch.token()


# --- graphql ---------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_graphql_returns_data(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        captured["auth"] = req.headers["Authorization"]
        return FakeResponse({"data": {"ok": 1}})

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    assert fetch.graphql("query{x}", login="me") == {"ok": 1}
    assert captured["body"]["variables"] == {"login": "me"}
    assert captured["auth"] == "bearer t"


def test_graphql_exits_on_graphql_errors(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse({"errors": [{"message": "bad field"}]}))
    with pytest.raises(SystemExit, match="bad field"):
        fetch.graphql("query{x}")


def test_graphql_exits_on_http_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    def boom(*_a, **_k):
        raise urllib.error.HTTPError(
            "u", 401, "Unauthorized", {}, io.BytesIO(b'{"message":"Bad credentials"}'))

    monkeypatch.setattr(fetch.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="401.*Bad credentials"):
        fetch.graphql("query{x}")


# --- year windows ----------------------------------------------------------

def test_year_range_clamps_current_year_to_today():
    start, end = fetch.year_range(2026, datetime.date(2026, 3, 4))
    assert start.startswith("2026-01-01")
    assert end.startswith("2026-03-04")


def test_year_range_covers_whole_past_year():
    start, end = fetch.year_range(2020, datetime.date(2026, 3, 4))
    assert start.startswith("2020-01-01")
    assert end.startswith("2020-12-31")


# --- trailing year ---------------------------------------------------------

def test_trailing_year_keeps_365_days_and_drops_older():
    today = datetime.date(2026, 10, 12)
    cal = {2025: [(f"2025-{m:02d}-01", 1) for m in range(1, 13)],
           2026: [((today - datetime.timedelta(days=d)).isoformat(), 2) for d in range(400)]}
    out = fetch.trailing_year(cal, today)
    dates = [datetime.date.fromisoformat(d) for d, _ in out]
    assert min(dates) >= today - datetime.timedelta(days=364)
    assert dates == sorted(dates)


def test_trailing_year_deduplicates_overlapping_calendars():
    today = datetime.date(2026, 1, 10)
    cal = {2025: [("2026-01-05", 3)], 2026: [("2026-01-05", 3)]}
    assert fetch.trailing_year(cal, today) == [["2026-01-05", 3]]


# --- streaks ---------------------------------------------------------------

def days(pairs):
    """(iso date, count) for a run of consecutive days ending at a fixed date."""
    base = datetime.date(2026, 10, 12)
    return [((base - datetime.timedelta(days=i)).isoformat(), n)
            for i, n in enumerate(pairs)]


def test_streak_counts_run_ending_today():
    cal = days([1, 1, 1, 0, 1])
    assert fetch.streaks(cal, datetime.date(2026, 10, 12)) == (3, 3)


def test_streak_ignores_today_when_it_has_nothing_yet():
    """A run should not read as broken just because the job ran before work did."""
    cal = days([0, 1, 1, 1, 1])
    current, longest = fetch.streaks(cal, datetime.date(2026, 10, 12))
    assert (current, longest) == (4, 4)


def test_streak_longest_can_exceed_current():
    cal = days([1, 0, 1, 1, 1, 1, 1])
    current, longest = fetch.streaks(cal, datetime.date(2026, 10, 12))
    assert current == 1
    assert longest == 5


def test_streak_of_nothing_is_zero():
    assert fetch.streaks(days([0, 0, 0]), datetime.date(2026, 10, 12)) == (0, 0)


def test_streak_on_empty_calendar():
    assert fetch.streaks([], datetime.date(2026, 10, 12)) == (0, 0)


# --- contributions by year -------------------------------------------------

def collection(total, restricted, dates):
    return {"user": {"contributionsCollection": {
        "totalCommitContributions": total,
        "restrictedContributionsCount": restricted,
        "contributionCalendar": {
            "totalContributions": total,
            "weeks": [{"contributionDays": [{"date": d, "contributionCount": n}
                                            for d, n in dates]}],
        },
    }}}


def test_private_contributions_are_not_added_to_the_calendar_total(monkeypatch):
    """The calendar total already includes private work; adding it double-counts."""
    monkeypatch.setattr(fetch, "graphql",
                        lambda *a, **k: collection(1174, 1122, [("2026-01-01", 5)]))
    per_year, private, _ = fetch.contributions_by_year(2026, datetime.date(2026, 10, 12))
    assert per_year[2026] == 1174
    assert private[2026] == 1122


def test_contributions_by_year_walks_every_year(monkeypatch):
    seen = []

    def fake(_q, **kw):
        seen.append(kw["from"][:4])
        return collection(1, 0, [("2024-01-01", 1)])

    monkeypatch.setattr(fetch, "graphql", fake)
    fetch.contributions_by_year(2024, datetime.date(2026, 1, 1))
    assert seen == ["2024", "2025", "2026"]


# --- projects --------------------------------------------------------------

def test_projects_joins_live_repo_fields(monkeypatch):
    monkeypatch.setattr(fetch, "graphql", lambda *a, **k: {"repository": {
        "stargazerCount": 7, "forkCount": 2,
        "pushedAt": "2026-08-27T17:16:50Z",
        "primaryLanguage": {"name": "TypeScript"},
    }})
    out = fetch.build_projects({"projects": [{"repo": "me/thing"}]})
    assert out == [{"repo": "me/thing", "stars": 7, "forks": 2,
                    "pushed_at": "2026-08-27T17:16:50Z", "language": "TypeScript"}]


def test_projects_handles_repo_with_no_language(monkeypatch):
    monkeypatch.setattr(fetch, "graphql", lambda *a, **k: {"repository": {
        "stargazerCount": 0, "forkCount": 0,
        "pushedAt": "2026-01-01T00:00:00Z", "primaryLanguage": None,
    }})
    assert fetch.build_projects({"projects": [{"repo": "me/x"}]})[0]["language"] is None


def test_projects_with_none_configured():
    assert fetch.build_projects({}) == []


# --- stats -----------------------------------------------------------------

PROFILE = {"user": {
    "createdAt": "2016-08-28T00:35:26Z",
    "followers": {"totalCount": 5},
    "pullRequests": {"totalCount": 372},
    "allPullRequests": {"totalCount": 423},
    "issues": {"totalCount": 0},
    "repositories": {"totalCount": 11, "nodes": [
        {"name": "a", "isPrivate": False, "stargazerCount": 1, "forkCount": 0,
         "languages": {"edges": [{"size": 100, "node": {"name": "Python"}}]}},
        {"name": "b", "isPrivate": True, "stargazerCount": 0, "forkCount": 1,
         "languages": {"edges": [{"size": 300, "node": {"name": "Python"}},
                                 {"size": 50, "node": {"name": "Go"}}]}},
    ]},
}}


def contributed_page(nodes, *, orgs=2, next_cursor=None):
    return {"user": {
        "organizations": {"totalCount": orgs},
        "repositoriesContributedTo": {
            "totalCount": len(nodes),
            "pageInfo": {"hasNextPage": bool(next_cursor), "endCursor": next_cursor},
            "nodes": nodes,
        },
    }}


def repo(size_by_language, *, private=True, org=True):
    return {"isPrivate": private, "isInOrganization": org,
            "languages": {"edges": [{"size": n, "node": {"name": k}}
                                    for k, n in size_by_language.items()]}}


CONTRIBUTED = contributed_page([
    repo({"Python": 100}, private=False, org=False),
    repo({"Python": 300, "Go": 50}),
])


def route(q, **k):
    """Dispatch a fake response on which query the caller passed."""
    if "repositoriesContributedTo" in q:
        return CONTRIBUTED
    if "contributionsCollection" in q:
        return collection(10, 4, [("2026-10-12", 10)])
    return PROFILE


def test_build_stats_sums_languages_across_every_repo_worked_in(monkeypatch):
    monkeypatch.setattr(fetch, "graphql", route)
    stats, _ = fetch.build_stats(datetime.date(2026, 10, 12))
    assert stats["languages"] == {"Python": 400, "Go": 50}
    assert list(stats["languages"]) == ["Python", "Go"], "sorted by size descending"


def test_build_stats_counts_owned_and_contributed_repos_separately(monkeypatch):
    """`repos` is what the account owns; `repos_contributed` is what it worked in."""
    monkeypatch.setattr(fetch, "graphql", route)
    stats, calendar = fetch.build_stats(datetime.date(2026, 10, 12))
    assert (stats["repos"], stats["repos_public"]) == (11, 1)
    assert stats["repos_contributed"] == 2
    assert stats["repos_contributed_private"] == 1
    assert stats["repos_contributed_org"] == 1
    assert stats["orgs"] == 2
    assert (stats["prs"], stats["prs_merged"]) == (423, 372)
    assert stats["private_year"] == 4
    assert calendar == [["2026-10-12", 10]]


def test_contributed_repos_follows_every_page(monkeypatch):
    """A 100-repo page cap would silently truncate the language totals."""
    pages = iter([
        contributed_page([repo({"Rust": 10})], next_cursor="cursor"),
        contributed_page([repo({"Rust": 5, "Zig": 1})]),
    ])
    monkeypatch.setattr(fetch, "graphql", lambda q, **k: next(pages))
    languages, counts = fetch.contributed_repos()
    assert languages == {"Rust": 15, "Zig": 1}
    assert counts["repos"] == 2


def test_contributed_repos_never_asks_for_a_repository_or_owner_name():
    """An employer's identity must not be reachable from data/.

    Language names are the one `name` the query may select, so they are cut
    out before looking for the rest.
    """
    query = re.sub(r"languages\(.*?\n\s*\}", "", fetch.CONTRIB_REPOS_Q, flags=re.S)
    for field in ("name", "nameWithOwner", "owner", "url", "description"):
        assert field not in query, field


def test_write_emits_trailing_newline(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "DATA", tmp_path)
    fetch.write("x.json", {"a": 1})
    text = (tmp_path / "x.json").read_text()
    assert text.endswith("\n")
    assert json.loads(text) == {"a": 1}


# --- private-visibility guard ----------------------------------------------

def test_private_guard_is_off_by_default(monkeypatch):
    monkeypatch.delenv("REQUIRE_PRIVATE", raising=False)
    fetch.check_private_visible({"private_all": 0})


def test_private_guard_passes_when_private_work_is_visible(monkeypatch):
    monkeypatch.setenv("REQUIRE_PRIVATE", "1")
    fetch.check_private_visible({"private_all": 1302})


def test_private_guard_aborts_on_an_underprivileged_token(monkeypatch):
    """Authenticating is not the same as being able to see the private work."""
    monkeypatch.setenv("REQUIRE_PRIVATE", "1")
    with pytest.raises(SystemExit, match="SSO"):
        fetch.check_private_visible({"private_all": 0})
