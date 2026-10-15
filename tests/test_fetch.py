"""Tests for fetch.py's wiring: which source answers which question, and the
three files that come out.

The sources and the arithmetic are pinned in test_github.py and
test_transform_stats.py. What is left here is the join between them — above all
that the private share is asked for with the token that lacks `read:user`, and
is not asked for at all when no such credential exists.
"""
import datetime
import json

import pytest

from tools.profile import fetch
from tools.profile.sources import store

TODAY = datetime.date(2026, 10, 12)

USER = {
    "createdAt": "2025-08-28T00:35:26Z",
    "followers": {"totalCount": 5},
    "pullRequests": {"totalCount": 372},
    "allPullRequests": {"totalCount": 423},
    "issues": {"totalCount": 0},
    "repositories": {"totalCount": 11, "nodes": [
        {"name": "a", "isPrivate": False, "stargazerCount": 1, "forkCount": 0},
    ]},
}

NODE = {"isPrivate": True, "isInOrganization": True,
        "languages": {"edges": [{"size": 400, "node": {"name": "Python"}}]}}

RECORD = {"stargazerCount": 7, "forkCount": 2,
          "pushedAt": "2026-08-27T17:16:50Z",
          "primaryLanguage": {"name": "TypeScript"}}


def fixed_date(day):
    """`datetime.date` whose `today()` is pinned, so a run is reproducible."""
    class Date(datetime.date):
        @classmethod
        def today(cls):
            return day
    return Date


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Every source stubbed, every write landing in tmp_path."""
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.setattr(fetch.datetime, "date", fixed_date(TODAY))
    monkeypatch.setattr(fetch.github, "profile", lambda: USER)
    monkeypatch.setattr(fetch.github, "contributed_repos", lambda: ([NODE], 2))
    monkeypatch.setattr(fetch.github, "repository", lambda o, n: RECORD)
    monkeypatch.setattr(fetch.github, "calendar_year",
                        lambda year: [(f"{year}-10-12", 10)])
    monkeypatch.setattr(fetch.github, "restricted_count", lambda tok, start, end: 4)
    monkeypatch.setattr(fetch.github, "outsider_token", lambda: "scopeless")
    monkeypatch.setattr(fetch.files, "profile_config",
                        lambda: {"projects": [{"repo": "me/thing"}]})
    return tmp_path


def written(tmp_path, name):
    return json.loads((tmp_path / name).read_text())


# --- collect_years ---------------------------------------------------------

def test_collect_years_walks_every_year_since_the_account_was_created(monkeypatch):
    seen = []
    monkeypatch.setattr(fetch.github, "outsider_token", lambda: "scopeless")
    monkeypatch.setattr(fetch.github, "calendar_year",
                        lambda year: seen.append(year) or [])
    monkeypatch.setattr(fetch.github, "restricted_count", lambda *a: 1)
    fetch.collect_years(2024, datetime.date(2026, 1, 1))
    assert seen == [2024, 2025, 2026]


def test_collect_years_asks_the_api_without_the_read_user_token(monkeypatch):
    """`read:user` drives restrictedContributionsCount to zero — see github.py."""
    seen = {}
    monkeypatch.setattr(fetch.github, "outsider_token", lambda: "scopeless")
    monkeypatch.setattr(fetch.github, "calendar_year", lambda y: [("x", 9)])

    def spy(tok, start, end):
        seen.update(token=tok, start=start, end=end)
        return 3

    monkeypatch.setattr(fetch.github, "restricted_count", spy)
    _, restricted = fetch.collect_years(2026, TODAY)
    assert seen["token"] == "scopeless"
    assert seen["start"].startswith("2026-01-01")
    assert seen["end"].startswith("2026-10-12"), "clamped to today"
    assert restricted == {2026: 3}


def test_collect_years_skips_the_api_entirely_without_an_outsider_token(monkeypatch):
    """With only a privileged credential the count is unknowable, so it is zero."""
    monkeypatch.setattr(fetch.github, "outsider_token", lambda: None)
    monkeypatch.setattr(fetch.github, "calendar_year", lambda y: [("x", 9)])

    def forbidden(*_a):
        raise AssertionError("asked the API with the wrong credential")

    monkeypatch.setattr(fetch.github, "restricted_count", forbidden)
    calendars, restricted = fetch.collect_years(2026, TODAY)
    assert restricted == {2026: 0}
    assert calendars == {2026: [("x", 9)]}


# --- main ------------------------------------------------------------------

def test_main_writes_the_three_files_panels_read(wired):
    fetch.main()
    assert sorted(p.name for p in wired.glob("*.json")) == \
        ["calendar.json", "projects.json", "stats.json"]


def test_main_joins_every_source_into_stats(wired):
    fetch.main()
    stats = written(wired, "stats.json")
    assert stats["languages"] == {"Python": 400}, "from contributed_repos"
    assert stats["prs"] == 423, "from profile"
    assert stats["contributions_year"] == 10, "from the calendar page"
    assert stats["private_year"] == 4, "from the outsider token"
    assert stats["repos_contributed"] == 1


def test_main_fetches_one_repository_per_curated_project(wired, monkeypatch):
    seen = []
    monkeypatch.setattr(fetch.github, "repository",
                        lambda o, n: seen.append((o, n)) or RECORD)
    fetch.main()
    assert seen == [("me", "thing")]
    assert written(wired, "projects.json")[0]["repo"] == "me/thing"


def test_main_writes_an_empty_list_for_a_profile_with_no_projects(wired, monkeypatch):
    monkeypatch.setattr(fetch.files, "profile_config", dict)
    fetch.main()
    assert written(wired, "projects.json") == []


def test_main_names_each_file_it_wrote(wired, capsys):
    fetch.main()
    printed = capsys.readouterr().out
    for name in ("stats.json", "calendar.json", "projects.json"):
        assert f"wrote data/{name}" in printed


def test_main_starts_the_calendar_at_the_year_the_account_was_created(
        wired, monkeypatch):
    seen = []
    monkeypatch.setattr(fetch.github, "calendar_year",
                        lambda year: seen.append(year) or [(f"{year}-10-12", 10)])
    fetch.main()
    assert seen == [2025, 2026], "createdAt is 2025"


def test_main_writes_the_calendar_as_date_count_pairs(wired):
    fetch.main()
    assert written(wired, "calendar.json") == [["2026-10-12", 10]]
