"""Tests for the arithmetic between the API and the panels.

Every function under test is pure, so each one is pinned against literals
rather than against a stubbed network.
"""
import datetime

import pytest

from tools.profile.transform import stats


def days(counts, start="2026-10-01"):
    d0 = datetime.date.fromisoformat(start)
    return [[(d0 + datetime.timedelta(days=i)).isoformat(), n]
            for i, n in enumerate(counts)]


# --- year_range ------------------------------------------------------------

def test_year_range_clamps_current_year_to_today():
    start, end = stats.year_range(2026, datetime.date(2026, 3, 4))
    assert start.startswith("2026-01-01")
    assert end.startswith("2026-03-04")


def test_year_range_covers_whole_past_year():
    start, end = stats.year_range(2020, datetime.date(2026, 3, 4))
    assert start.startswith("2020-01-01")
    assert end.startswith("2020-12-31")


def test_year_range_is_timezone_explicit():
    """A naive window shifts the year boundary by the runner's offset."""
    start, end = stats.year_range(2024, datetime.date(2026, 3, 4))
    assert start.endswith("+00:00") and end.endswith("+00:00")


# --- contributions_by_year -------------------------------------------------

def test_year_totals_come_from_the_page_and_the_private_share_from_the_api():
    """The two sources disagree on the total; the page wins, being what visitors see."""
    per_year, private = stats.contributions_by_year(
        {2026: [("2026-01-01", 1303)]}, {2026: 1168})
    assert per_year == {2026: 1303}
    assert private == {2026: 1168}


def test_private_share_cannot_exceed_the_total():
    """Capped, or the counters claim more private work than there was work."""
    _, private = stats.contributions_by_year(
        {2026: [("2026-01-01", 10)]}, {2026: 12})
    assert private == {2026: 10}


def test_private_share_is_zero_when_the_api_was_never_asked():
    per_year, private = stats.contributions_by_year(
        {2026: [("2026-01-01", 1303)]}, {})
    assert per_year == {2026: 1303}
    assert private == {2026: 0}


def test_contributions_by_year_covers_every_year_it_was_given():
    per_year, private = stats.contributions_by_year(
        {2024: [("2024-01-01", 5)], 2025: [], 2026: [("2026-01-01", 7)]},
        {2024: 1, 2026: 3})
    assert per_year == {2024: 5, 2025: 0, 2026: 7}
    assert private == {2024: 1, 2025: 0, 2026: 3}


# --- trailing_year ---------------------------------------------------------

def test_trailing_year_keeps_365_days_and_drops_older():
    today = datetime.date(2026, 10, 12)
    cal = {2025: [("2025-10-12", 1), ("2025-10-13", 2)],
           2026: [("2026-10-12", 3)]}
    out = stats.trailing_year(cal, today)
    assert out[0] == ["2025-10-13", 2], "the 365-day cutoff is inclusive"
    assert out[-1] == ["2026-10-12", 3]
    assert ["2025-10-12", 1] not in out


def test_trailing_year_deduplicates_overlapping_calendars():
    today = datetime.date(2026, 1, 5)
    cal = {2026: [("2026-01-05", 3)], 2025: [("2026-01-05", 3)]}
    assert stats.trailing_year(cal, today) == [["2026-01-05", 3]]


def test_trailing_year_drops_the_rest_of_the_calendar_year():
    """The page returns whole years, so December arrives padded with zeroes."""
    today = datetime.date(2026, 3, 1)
    cal = {2026: [("2026-03-01", 4), ("2026-12-31", 0)]}
    assert stats.trailing_year(cal, today) == [["2026-03-01", 4]]


def test_trailing_year_of_nothing():
    assert stats.trailing_year({}, datetime.date(2026, 10, 12)) == []


# --- streaks ---------------------------------------------------------------

def test_streak_counts_run_ending_today():
    cal = days([0, 1, 1, 1], start="2026-10-09")
    assert stats.streaks(cal, datetime.date(2026, 10, 12)) == (3, 3)


def test_streak_ignores_today_when_it_has_nothing_yet():
    """The job may run before the first commit of the day."""
    cal = days([1, 1, 1, 0], start="2026-10-09")
    current, longest = stats.streaks(cal, datetime.date(2026, 10, 12))
    assert (current, longest) == (3, 3)


def test_streak_longest_can_exceed_current():
    cal = days([1, 1, 1, 1, 0, 1, 1], start="2026-10-06")
    current, longest = stats.streaks(cal, datetime.date(2026, 10, 12))
    assert (current, longest) == (2, 4)


def test_streak_of_nothing_is_zero():
    assert stats.streaks(days([0, 0, 0]), datetime.date(2026, 10, 12)) == (0, 0)


def test_streak_on_empty_calendar():
    assert stats.streaks([], datetime.date(2026, 10, 12)) == (0, 0)


# --- aggregate_repos -------------------------------------------------------

def repo(size_by_language, *, private=True, org=True):
    return {"isPrivate": private, "isInOrganization": org,
            "languages": {"edges": [{"size": n, "node": {"name": k}}
                                    for k, n in size_by_language.items()]}}


def test_aggregate_sums_language_bytes_across_repositories():
    languages, _ = stats.aggregate_repos(
        [repo({"Rust": 10}), repo({"Rust": 5, "Zig": 1})], orgs=2)
    assert languages == {"Rust": 15, "Zig": 1}


def test_aggregate_counts_private_and_organization_repositories():
    languages, counts = stats.aggregate_repos([
        repo({"Python": 100}, private=False, org=False),
        repo({"Python": 300, "Go": 50}),
    ], orgs=2)
    assert languages == {"Python": 400, "Go": 50}
    assert counts == {"repos": 2, "private": 1, "org": 1, "orgs": 2}


def test_aggregate_of_no_repositories_still_reports_the_org_count():
    assert stats.aggregate_repos([], orgs=3) == ({}, {"repos": 0, "private": 0,
                                                      "org": 0, "orgs": 3})


# --- build_stats -----------------------------------------------------------

USER = {
    "createdAt": "2016-08-28T00:35:26Z",
    "followers": {"totalCount": 5},
    "pullRequests": {"totalCount": 372},
    "allPullRequests": {"totalCount": 423},
    "issues": {"totalCount": 0},
    "repositories": {"totalCount": 11, "nodes": [
        {"name": "a", "isPrivate": False, "stargazerCount": 1, "forkCount": 0},
        {"name": "b", "isPrivate": True, "stargazerCount": 0, "forkCount": 1},
    ]},
}

CONTRIBUTED = {"repos": 2, "private": 1, "org": 1, "orgs": 2}
TODAY = datetime.date(2026, 10, 12)


@pytest.fixture
def built():
    return stats.build_stats(
        USER, {"Python": 400, "Go": 50}, CONTRIBUTED,
        {2026: [("2026-10-12", 10)]}, {2026: 6}, TODAY)


def test_build_stats_sorts_languages_by_size_descending(built):
    out, _ = built
    assert out["languages"] == {"Python": 400, "Go": 50}
    assert list(out["languages"]) == ["Python", "Go"]


def test_build_stats_counts_owned_and_contributed_repos_separately(built):
    """`repos` is what the account owns; `repos_contributed` is what it worked in."""
    out, _ = built
    assert (out["repos"], out["repos_public"]) == (11, 1)
    assert out["repos_contributed"] == 2
    assert out["repos_contributed_private"] == 1
    assert out["repos_contributed_org"] == 1
    assert out["orgs"] == 2


def test_build_stats_carries_the_pull_request_pair(built):
    out, _ = built
    assert (out["prs"], out["prs_merged"]) == (423, 372)


def test_build_stats_sums_stars_and_forks_over_owned_repositories(built):
    out, _ = built
    assert (out["stars"], out["forks"]) == (1, 1)


def test_build_stats_reports_the_private_share_of_the_year(built):
    out, _ = built
    assert out["private_year"] == 6


def test_build_stats_returns_the_trailing_calendar_beside_the_counters(built):
    out, calendar = built
    assert calendar == [["2026-10-12", 10]]
    assert out["contributions_trailing"] == 10
    assert out["streak_current"] == 1


def test_build_stats_stamps_the_day_it_ran(built):
    out, _ = built
    assert out["updated"] == "2026-10-12"
    assert out["year"] == 2026


def test_build_stats_totals_every_year_not_just_this_one():
    out, _ = stats.build_stats(
        USER, {}, CONTRIBUTED,
        {2025: [("2025-06-01", 40)], 2026: [("2026-10-12", 10)]},
        {2025: 4, 2026: 6}, TODAY)
    assert out["contributions_year"] == 10
    assert out["contributions_all"] == 50
    assert out["private_all"] == 10


# --- build_projects --------------------------------------------------------

def record(language="TypeScript"):
    return {"stargazerCount": 7, "forkCount": 2,
            "pushedAt": "2026-08-27T17:16:50Z",
            "primaryLanguage": {"name": language} if language else None}


def test_projects_joins_live_repo_fields_to_the_curated_entry():
    assert stats.build_projects([{"repo": "me/thing"}], [record()]) == [{
        "repo": "me/thing", "stars": 7, "forks": 2,
        "pushed_at": "2026-08-27T17:16:50Z", "language": "TypeScript"}]


def test_projects_handles_a_repo_with_no_language():
    assert stats.build_projects([{"repo": "me/x"}],
                                [record(None)])[0]["language"] is None


def test_projects_with_none_configured():
    assert stats.build_projects([], []) == []


def test_projects_keeps_the_curated_order():
    entries = [{"repo": "me/a"}, {"repo": "me/b"}]
    out = stats.build_projects(entries, [record(), record("Rust")])
    assert [p["repo"] for p in out] == ["me/a", "me/b"]
    assert out[1]["language"] == "Rust"
