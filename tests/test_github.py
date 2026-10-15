"""Tests for the only module that makes a request.

Which credential each source gets is the thing most worth pinning: the
contribution totals are correct only when asked for anonymously, and the
private share only when asked for with a token that cannot read it.
"""
import io
import json
import re
import urllib.error

import pytest

from tools.profile.sources import github


# --- token selection -------------------------------------------------------

def test_token_prefers_profile_token(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "private")
    monkeypatch.setenv("GITHUB_TOKEN", "public")
    assert github.token() == "private"


def test_token_falls_back_to_job_token(monkeypatch):
    monkeypatch.delenv("PROFILE_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "public")
    assert github.token() == "public"


def test_token_exits_when_unset(monkeypatch):
    for name in ("PROFILE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="PROFILE_TOKEN"):
        github.token()


def test_outsider_token_refuses_the_read_user_credential(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    monkeypatch.setenv("GITHUB_TOKEN", "scopeless")
    assert github.outsider_token() == "scopeless"


def test_outsider_token_is_none_when_only_profile_token_is_set(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "has-read-user")
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    assert github.outsider_token() is None


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
    monkeypatch.setenv("PROFILE_TOKEN", "t")
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["body"] = json.loads(req.data)
        return FakeResponse({"data": {"ok": 1}})

    monkeypatch.setattr(github.urllib.request, "urlopen", fake_urlopen)
    assert github.graphql("query{x}", login="me") == {"ok": 1}
    assert seen["body"]["variables"] == {"login": "me"}


def test_graphql_exits_on_graphql_errors(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "t")
    monkeypatch.setattr(github.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse({"errors": [{"message": "nope"}]}))
    with pytest.raises(SystemExit, match="nope"):
        github.graphql("query{x}")


def test_graphql_exits_on_http_error(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "t")

    def boom(*_a, **_k):
        raise urllib.error.HTTPError("u", 502, "Bad Gateway", {},
                                     io.BytesIO(b"upstream died"))

    monkeypatch.setattr(github.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="502"):
        github.graphql("query{x}")


def test_graphql_honours_an_explicit_token(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN", "wrong")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.headers["Authorization"]
        return FakeResponse({"data": {"ok": 1}})

    monkeypatch.setattr(github.urllib.request, "urlopen", fake_urlopen)
    github.graphql("query{x}", _token="right")
    assert captured["auth"] == "bearer right"


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
    monkeypatch.setattr(github.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    assert github.calendar_year(2026) == [
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

    monkeypatch.setattr(github.urllib.request, "urlopen", fake_urlopen)
    github.calendar_year(2026)
    assert "authorization" not in seen["headers"]
    assert "from=2026-01-01&to=2026-12-31" in seen["url"]


def test_calendar_year_aborts_when_the_total_will_not_reconcile(monkeypatch):
    """The headline is rendered separately, so it catches a drifted parse."""
    page = calendar_page([("2026-01-01", 5)], headline=900)
    monkeypatch.setattr(github.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    with pytest.raises(SystemExit, match="parsed 5 .* page says 900"):
        github.calendar_year(2026)


def test_calendar_year_aborts_when_the_grid_is_gone(monkeypatch):
    monkeypatch.setattr(github.urllib.request, "urlopen",
                        lambda *a, **k: FakePage("<html>redesigned</html>"))
    with pytest.raises(SystemExit, match="no contribution days"):
        github.calendar_year(2026)


def test_calendar_year_counts_a_day_with_no_tooltip_as_empty(monkeypatch):
    page = ('<td data-date="2026-01-01" id="contribution-day-component-0-0" '
            'data-level="0"></td>')
    monkeypatch.setattr(github.urllib.request, "urlopen",
                        lambda *a, **k: FakePage(page))
    assert github.calendar_year(2026) == [("2026-01-01", 0)]


def test_calendar_year_exits_when_the_page_is_unreachable(monkeypatch):
    def boom(*_a, **_k):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(github.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="could not reach the profile calendar"):
        github.calendar_year(2026)


def test_calendar_year_exits_on_http_error(monkeypatch):
    def boom(*_a, **_k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(github.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="returned 404"):
        github.calendar_year(2026)


# --- the API queries -------------------------------------------------------

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


def test_contributed_repos_follows_every_page(monkeypatch):
    """A 100-repo page cap would silently truncate the language totals."""
    pages = iter([
        contributed_page([repo({"Rust": 10})], next_cursor="cursor"),
        contributed_page([repo({"Rust": 5, "Zig": 1})]),
    ])
    monkeypatch.setattr(github, "graphql", lambda q, **k: next(pages))
    nodes, orgs = github.contributed_repos()
    assert len(nodes) == 2
    assert orgs == 2


def test_contributed_repos_passes_the_cursor_of_the_page_it_just_read(monkeypatch):
    seen = []
    pages = iter([contributed_page([repo({"Rust": 1})], next_cursor="c1"),
                  contributed_page([repo({"Zig": 1})])])

    def spy(_q, **kwargs):
        seen.append(kwargs.get("after"))
        return next(pages)

    monkeypatch.setattr(github, "graphql", spy)
    github.contributed_repos()
    assert seen == [None, "c1"]


def test_contributed_repos_counts_nothing_itself(monkeypatch):
    """Summing is the transform layer's job; this returns what the API said."""
    monkeypatch.setattr(github, "graphql",
                        lambda q, **k: contributed_page([repo({"Rust": 10})]))
    nodes, _ = github.contributed_repos()
    assert nodes == [repo({"Rust": 10})]


def test_contributed_repos_never_asks_for_a_repository_or_owner_name():
    """An employer's identity must not be reachable from data/.

    Language names are the one `name` the query may select, so they are cut
    out before looking for the rest.
    """
    query = re.sub(r"languages\(.*?\n\s*\}", "", github.CONTRIB_REPOS_Q, flags=re.S)
    for field in ("name", "nameWithOwner", "owner", "url", "description"):
        assert field not in query, field


def test_profile_returns_the_user_node(monkeypatch):
    monkeypatch.setattr(github, "graphql", lambda q, **k: {"user": {"createdAt": "x"}})
    assert github.profile() == {"createdAt": "x"}


def test_repository_returns_the_repository_node(monkeypatch):
    seen = {}

    def spy(_q, **kwargs):
        seen.update(kwargs)
        return {"repository": {"stargazerCount": 7}}

    monkeypatch.setattr(github, "graphql", spy)
    assert github.repository("me", "thing") == {"stargazerCount": 7}
    assert (seen["owner"], seen["name"]) == ("me", "thing")


def test_restricted_count_asks_with_the_token_it_was_handed(monkeypatch):
    """The field reports truthfully only for a viewer who cannot see the work."""
    seen = {}

    def spy(_q, _token=None, **kwargs):
        seen.update(token=_token, **kwargs)
        return {"user": {"contributionsCollection":
                         {"restrictedContributionsCount": 6}}}

    monkeypatch.setattr(github, "graphql", spy)
    assert github.restricted_count("scopeless", "2026-01-01", "2026-12-31") == 6
    assert seen["token"] == "scopeless"
    assert (seen["from"], seen["to"]) == ("2026-01-01", "2026-12-31")


def test_the_private_count_query_asks_for_nothing_else():
    """A second field here would be asked for with a deliberately weak token."""
    assert github.YEAR_Q.count("Count") == 1
    assert "restrictedContributionsCount" in github.YEAR_Q
