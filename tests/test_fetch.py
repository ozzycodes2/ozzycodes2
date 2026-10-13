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


def test_trailing_year_drops_the_rest_of_the_calendar_year():
    """The profile page returns whole years, so December arrives pre-padded."""
    today = datetime.date(2026, 3, 1)
    cal = {2026: [("2026-03-01", 4), ("2026-03-02", 0), ("2026-12-31", 0)]}
    assert fetch.trailing_year(cal, today) == [["2026-03-01", 4]]


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


# --- the public contribution calendar --------------------------------------

def calendar_page(days, *, headline=None):
    """The profile page's contribution grid, trimmed to the parts that matter.

    Counts live only in the tooltip prose; the <td> itself carries a 0-4
    intensity level. `headline` overrides the total, to drive the checksum.
    """
    total = sum(n for _, n in days) if headline is None else headline
    out = [f'<h2 class="f4">\n      {total:,}\n      contributions\n        in 2026\n</h2>']
    for i, (date, count) in enumerate(days):
        cell = f"contribution-day-component-0-{i}"
        prose = (f"{count} contribution{'' if count == 1 else 's'}" if count
                 else "No contributions")
        out.append(f'<td tabindex="0" data-date="{date}" id="{cell}" data-level="0"></td>'
                   f'<tool-tip for="{cell}" class="sr-only">{prose} on a day.</tool-tip>')
    return "".join(out)


class FakePage(FakeResponse):
    def __init__(self, text):
        self._payload = text.encode()


def test_calendar_year_reads_the_count_out_of_each_tooltip(monkeypatch):
    page = calendar_page([("2026-01-01", 12), ("2026-01-02", 0), ("2026-01-03", 1)])
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    assert fetch.calendar_year(2026) == [
        ("2026-01-01", 12), ("2026-01-02", 0), ("2026-01-03", 1)]


def test_calendar_year_sends_no_credential(monkeypatch):
    """The private-inclusive total is served to a viewer *without* access.

    Attaching the author's own token is what collapses these numbers to the
    public subset, so sending one is a defect and not merely redundant.
    """
    monkeypatch.setenv("PROFILE_TOKEN", "secret")
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower() for k in req.headers}
        return FakePage(calendar_page([("2026-01-01", 1)]))

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    fetch.calendar_year(2026)
    assert "authorization" not in seen["headers"]
    assert "from=2026-01-01&to=2026-12-31" in seen["url"]


def test_calendar_year_aborts_when_the_total_will_not_reconcile(monkeypatch):
    """The headline is rendered separately, so it catches a drifted parse."""
    page = calendar_page([("2026-01-01", 5)], headline=900)
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    with pytest.raises(SystemExit, match="parsed 5 .* page says 900"):
        fetch.calendar_year(2026)


def test_calendar_year_aborts_when_the_grid_is_gone(monkeypatch):
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: FakePage("<html>redesigned</html>"))
    with pytest.raises(SystemExit, match="no contribution days"):
        fetch.calendar_year(2026)


def test_calendar_year_counts_a_day_with_no_tooltip_as_empty(monkeypatch):
    page = ('<td data-date="2026-01-01" id="contribution-day-component-0-0" '
            'data-level="0"></td>')
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    assert fetch.calendar_year(2026) == [("2026-01-01", 0)]


def test_calendar_year_exits_when_the_page_is_unreachable(monkeypatch):
    def boom(*_a, **_k):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="could not reach the profile calendar"):
        fetch.calendar_year(2026)


def test_calendar_year_exits_on_http_error(monkeypatch):
    def boom(*_a, **_k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(fetch.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="returned 404"):
        fetch.calendar_year(2026)


# --- contributions by year -------------------------------------------------

def collection(restricted):
    return {"user": {"contributionsCollection": {
        "restrictedContributionsCount": restricted,
    }}}


def test_year_totals_come_from_the_page_and_the_private_share_from_the_api(monkeypatch):
    """The two sources disagree on the total; the page wins, being what visitors see."""
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    monkeypatch.setattr(fetch, "calendar_year", lambda _y: [("2026-01-01", 1303)])
    monkeypatch.setattr(fetch, "graphql", lambda *a, **k: collection(1168))
    per_year, private, _ = fetch.contributions_by_year(2026, datetime.date(2026, 10, 12))
    assert per_year[2026] == 1303
    assert private[2026] == 1168


def test_private_share_is_asked_without_the_read_user_token(monkeypatch):
    """PROFILE_TOKEN carries read:user, which zeroes the field being read."""
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    monkeypatch.setattr(fetch, "calendar_year", lambda _y: [("2026-01-01", 9)])
    used = []

    def spy(_q, _token=None, **_k):
        used.append(_token)
        return collection(4)

    monkeypatch.setattr(fetch, "graphql", spy)
    fetch.contributions_by_year(2026, datetime.date(2026, 10, 12))
    assert used == ["scopeless"]


def test_private_share_cannot_exceed_the_total(monkeypatch):
    """The two sources count different windows, so the parts can overshoot."""
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    monkeypatch.setattr(fetch, "calendar_year", lambda _y: [("2026-01-01", 10)])
    monkeypatch.setattr(fetch, "graphql", lambda *a, **k: collection(12))
    _, private, _ = fetch.contributions_by_year(2026, datetime.date(2026, 10, 12))
    assert private[2026] == 10


def test_private_share_is_zero_when_only_a_read_user_token_exists(monkeypatch):
    """Better absent than wrong: the panel drops the counter rather than lie."""
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(fetch, "calendar_year", lambda _y: [("2026-01-01", 1303)])

    def forbidden(*_a, **_k):
        raise AssertionError("asked the API with a read:user token")

    monkeypatch.setattr(fetch, "graphql", forbidden)
    per_year, private, _ = fetch.contributions_by_year(2026, datetime.date(2026, 10, 12))
    assert (per_year[2026], private[2026]) == (1303, 0)


def test_contributions_by_year_walks_every_year(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    seen = []
    monkeypatch.setattr(fetch, "calendar_year",
                        lambda year: seen.append(year) or [(f"{year}-01-01", 1)])
    monkeypatch.setattr(fetch, "graphql", lambda *a, **k: collection(1))
    fetch.contributions_by_year(2024, datetime.date(2026, 1, 1))
    assert seen == [2024, 2025, 2026]


def test_outsider_token_refuses_the_read_user_credential(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    assert fetch.outsider_token() == "scopeless"


def test_outsider_token_is_none_when_only_profile_token_is_set(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    assert fetch.outsider_token() is None


def test_graphql_honours_an_explicit_token(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "wrong")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.headers["Authorization"]
        return FakeResponse({"data": {"ok": 1}})

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    fetch.graphql("query{x}", _token="right")
    assert captured["auth"] == "bearer right"


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
        return collection(6)
    return PROFILE


@pytest.fixture
def stubbed(monkeypatch):
    """`build_stats`' two sources: the GraphQL router and the profile page."""
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    monkeypatch.setattr(fetch, "graphql", route)
    monkeypatch.setattr(fetch, "calendar_year",
                        lambda year: [(f"{year}-10-12", 10)] if year == 2026 else [])


def test_build_stats_sums_languages_across_every_repo_worked_in(stubbed):
    stats, _ = fetch.build_stats(datetime.date(2026, 10, 12))
    assert stats["languages"] == {"Python": 400, "Go": 50}
    assert list(stats["languages"]) == ["Python", "Go"], "sorted by size descending"


def test_build_stats_counts_owned_and_contributed_repos_separately(stubbed):
    """`repos` is what the account owns; `repos_contributed` is what it worked in."""
    stats, calendar = fetch.build_stats(datetime.date(2026, 10, 12))
    assert (stats["repos"], stats["repos_public"]) == (11, 1)
    assert stats["repos_contributed"] == 2
    assert stats["repos_contributed_private"] == 1
    assert stats["repos_contributed_org"] == 1
    assert stats["orgs"] == 2
    assert (stats["prs"], stats["prs_merged"]) == (423, 372)
    assert stats["private_year"] == 6
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
