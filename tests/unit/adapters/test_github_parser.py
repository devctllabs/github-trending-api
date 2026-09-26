from datetime import UTC, datetime

import httpx
import pytest

from github_trending.adapters.github import GitHubTrendingSource, parse_snapshot, source_url
from github_trending.domain import DocumentStatus, Feed, Period
from github_trending.service import SourceError

OBSERVED_AT = datetime(2026, 9, 25, 6, 17, 12, tzinfo=UTC)
FEED = Feed(Period.DAILY, "rust")
SOURCE_URL = "https://github.com/trending/rust"


def test_parse_complete_repository_item() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/astral-sh/uv"> astral-sh / uv </a></h2>
      <p> An  extremely\n fast &amp; reliable package manager. </p>
      <span itemprop="programmingLanguage"> Rust </span>
      <a href="/astral-sh/uv/stargazers">42,137</a>
      <a href="/astral-sh/uv/forks">1,289</a>
      <span>Built by contributors</span>
      <span>742 stars today</span>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.COMPLETE
    assert snapshot.issues == ()
    assert len(snapshot.items) == 1
    item = snapshot.items[0]
    assert item.rank == 1
    assert item.full_name == "astral-sh/uv"
    assert item.url == "https://github.com/astral-sh/uv"
    assert item.description == "An extremely fast & reliable package manager."
    assert item.programming_language == "Rust"
    assert item.stars == 42_137
    assert item.forks == 1_289
    assert item.stars_in_period == 742


def test_malformed_metric_is_reported_without_dropping_the_item() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/owner/broken">owner/broken</a></h2>
      <a href="/owner/broken/stargazers">not-a-number</a>
      <a href="/owner/broken/forks">10</a>
      <span>5 stars today</span>
    </article>
    <article class="Box-row">
      <h2><a href="/owner/valid">owner/valid</a></h2>
      <a href="/owner/valid/stargazers">100</a>
      <a href="/owner/valid/forks">20</a>
      <span>8 stars today</span>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.DEGRADED
    assert [(issue.code, issue.rank, issue.field) for issue in snapshot.issues] == [
        ("invalid_integer", 1, "stars")
    ]
    assert snapshot.issues[0].raw_value == "not-a-number"
    assert [item.rank for item in snapshot.items] == [1, 2]
    broken = snapshot.items[0]
    assert broken.stars is None
    assert broken.forks == 10
    assert broken.stars_in_period == 5


def test_zero_metrics_are_valid() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/owner/zero">owner/zero</a></h2>
      <a href="/owner/zero/stargazers">0</a>
      <a href="/owner/zero/forks">0</a>
      <span>0 stars today</span>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.COMPLETE
    assert snapshot.issues == ()
    item = snapshot.items[0]
    assert (item.stars, item.forks, item.stars_in_period) == (0, 0, 0)


def test_missing_period_metric_is_optional() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/owner/no-period-metric">owner/no-period-metric</a></h2>
      <a href="/owner/no-period-metric/stargazers">100</a>
      <a href="/owner/no-period-metric/forks">10</a>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.COMPLETE
    assert snapshot.issues == ()
    assert snapshot.items[0].stars_in_period is None


def test_all_malformed_metrics_are_reported_on_one_retained_item() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/owner/broken">owner/broken</a></h2>
      <a href="/owner/broken/forks">unknown</a>
      <span>-1 stars today</span>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.DEGRADED
    assert [(issue.code, issue.field, issue.raw_value) for issue in snapshot.issues] == [
        ("missing_field", "stars", None),
        ("invalid_integer", "forks", "unknown"),
        ("out_of_range", "starsInPeriod", "-1"),
    ]
    assert len(snapshot.items) == 1
    item = snapshot.items[0]
    assert (item.stars, item.forks, item.stars_in_period) == (None, None, None)


def test_invalid_repository_identity_is_reported_and_skipped() -> None:
    html = """
    <article class="Box-row">
      <h2><a href="/owner/too/many">broken</a></h2>
    </article>
    <article class="Box-row">
      <h2><a href="/owner/valid">owner/valid</a></h2>
      <a href="/owner/valid/stargazers">10</a>
      <a href="/owner/valid/forks">2</a>
      <span>1 stars today</span>
    </article>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert [
        (issue.code, issue.rank, issue.field, issue.raw_value) for issue in snapshot.issues
    ] == [("invalid_repository_link", 1, "fullName", "/owner/too/many")]
    assert [item.rank for item in snapshot.items] == [2]


def test_explicit_blankslate_is_a_valid_empty_feed() -> None:
    html = """
    <div class="blankslate-container">
      <h2 class="blankslate-heading">
        It looks like we don't have any trending repositories for ABNF.
      </h2>
    </div>
    """

    snapshot = parse_snapshot(html, FEED, SOURCE_URL, OBSERVED_AT)

    assert snapshot.status is DocumentStatus.COMPLETE
    assert snapshot.items == ()


def test_unrecognized_empty_page_is_a_parse_failure() -> None:
    with pytest.raises(SourceError, match="expected repository rows or empty-state marker") as exc:
        parse_snapshot("<html><h1>GitHub</h1></html>", FEED, SOURCE_URL, OBSERVED_AT)

    assert exc.value.category == "parse_failed"


def test_source_builds_urls_paces_feeds_and_retries_server_errors() -> None:
    calls: list[str] = []
    responses = iter([200, 503, 200])
    empty_html = (
        '<h2 class="blankslate-heading">It looks like we don\'t have any trending repositories '
        "for Rust.</h2>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(next(responses), text=empty_html, request=request)

    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GitHubTrendingSource(
            client=client,
            clock=lambda: OBSERVED_AT,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
        )
        daily = source.fetch(Feed(Period.DAILY, "all"))
        weekly = source.fetch(Feed(Period.WEEKLY, "rust"))

    assert daily.source_url == "https://github.com/trending"
    assert weekly.source_url == "https://github.com/trending/rust?since=weekly"
    assert calls == [
        "https://github.com/trending",
        "https://github.com/trending/rust?since=weekly",
        "https://github.com/trending/rust?since=weekly",
    ]
    assert sleeps == [2.0, 1.0]


def test_source_url_omits_daily_query_and_all_path_segment() -> None:
    assert source_url(Feed(Period.DAILY, "python")) == "https://github.com/trending/python"
    assert source_url(Feed(Period.MONTHLY, "all")) == ("https://github.com/trending?since=monthly")


def test_source_honors_numeric_retry_after() -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "4.5"}),
            httpx.Response(
                200,
                text=(
                    '<h2 class="blankslate-heading">It looks like we don\'t have any trending '
                    "repositories for Rust.</h2>"
                ),
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        response = next(responses)
        response.request = request
        return response

    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GitHubTrendingSource(client, lambda: OBSERVED_AT, sleeps.append, lambda: 0.0)
        source.fetch(FEED)

    assert sleeps == [4.5]
