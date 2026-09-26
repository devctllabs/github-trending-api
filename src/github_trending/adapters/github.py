import re
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup, Tag

from github_trending.domain import (
    DocumentStatus,
    Feed,
    Period,
    RepositoryItem,
    Snapshot,
    SnapshotIssue,
)
from github_trending.service import SourceError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

_REPOSITORY_PATH = re.compile(r"^/[^/\s]+/[^/\s]+$")
_PERIOD_STARS = re.compile(r"(?P<count>.+?)\s+stars\s+(?:today|this week|this month)")


class _ItemError(ValueError):
    def __init__(self, code: str, field: str, raw_value: str | None = None) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field
        self.raw_value = raw_value


class GitHubTrendingSource:
    """Fetch GitHub Trending feeds through an injected HTTP client."""

    def __init__(
        self,
        client: httpx.Client,
        clock: Callable[[], datetime],
        sleep: Callable[[float], None],
        jitter: Callable[[], float],
    ) -> None:
        self._client = client
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter
        self._has_fetched = False

    def fetch(self, feed: Feed) -> Snapshot:
        """Fetch and parse one feed with bounded retries and request pacing."""
        if self._has_fetched:
            self._sleep(2.0)
        self._has_fetched = True

        url = source_url(feed)
        response = self._request(url)
        return parse_snapshot(response.text, feed, url, self._clock())

    def _request(self, url: str) -> httpx.Response:
        detail = "request failed"
        for attempt in range(3):
            response: httpx.Response | None = None
            try:
                response = self._client.get(url)
                if response.is_success:
                    return response
                detail = f"HTTP {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    break
            except httpx.RequestError as exc:
                detail = type(exc).__name__

            if attempt < 2:
                self._sleep(self._retry_delay(attempt, response))

        raise SourceError(category="fetch_failed", detail=detail)

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return 2.0**attempt + self._jitter() * 0.25


def source_url(feed: Feed) -> str:
    """Return the canonical GitHub Trending URL for a feed."""
    language_path = "" if feed.language == "all" else f"/{feed.language}"
    url = f"https://github.com/trending{language_path}"
    if feed.period is Period.DAILY:
        return url
    return f"{url}?since={feed.period.value}"


def parse_snapshot(
    html: str,
    feed: Feed,
    source_url: str,
    observed_at: datetime,
) -> Snapshot:
    """Parse one GitHub Trending HTML response into a typed snapshot."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("article.Box-row")
    if not rows:
        heading = soup.select_one(".blankslate-heading")
        if heading is None or "have any trending repositories" not in heading.get_text(" "):
            raise SourceError(
                category="parse_failed",
                detail="expected repository rows or empty-state marker",
            )

    items: list[RepositoryItem] = []
    issues: list[SnapshotIssue] = []
    for rank, row in enumerate(rows, start=1):
        try:
            item, item_issues = _parse_item(row, rank)
        except _ItemError as exc:
            issues.append(SnapshotIssue(exc.code, rank, exc.field, exc.raw_value))
            continue
        items.append(item)
        issues.extend(item_issues)

    status = DocumentStatus.DEGRADED if issues else DocumentStatus.COMPLETE
    return Snapshot(
        feed=feed,
        source_url=source_url,
        observed_at=observed_at,
        status=status,
        issues=tuple(issues),
        items=tuple(items),
    )


def _parse_item(row: Tag, rank: int) -> tuple[RepositoryItem, tuple[SnapshotIssue, ...]]:
    repo_link = row.select_one("h2 a[href]")
    href = None if repo_link is None else repo_link.get("href")
    if not isinstance(href, str) or _REPOSITORY_PATH.fullmatch(href) is None:
        raw_value = href if isinstance(href, str) else None
        raise _ItemError("invalid_repository_link", "fullName", raw_value)

    full_name = href.removeprefix("/")
    issues: list[SnapshotIssue] = []
    item = RepositoryItem(
        rank=rank,
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        description=_optional_text(row, "p"),
        programming_language=_optional_text(row, '[itemprop="programmingLanguage"]'),
        stars=_link_integer(row, f"{href}/stargazers", rank, "stars", issues),
        forks=_link_integer(row, f"{href}/forks", rank, "forks", issues),
        stars_in_period=_period_stars(row, rank, issues),
    )
    return item, tuple(issues)


def _optional_text(row: Tag, selector: str) -> str | None:
    element = row.select_one(selector)
    if element is None:
        return None
    normalized = " ".join(element.get_text(" ", strip=True).split())
    return normalized or None


def _link_integer(
    row: Tag,
    href: str,
    rank: int,
    field: str,
    issues: list[SnapshotIssue],
) -> int | None:
    element = row.select_one(f'a[href="{href}"]')
    if element is None:
        issues.append(SnapshotIssue("missing_field", rank, field))
        return None
    return _parse_integer(element.get_text(strip=True), rank, field, issues)


def _period_stars(row: Tag, rank: int, issues: list[SnapshotIssue]) -> int | None:
    for text in row.stripped_strings:
        match = _PERIOD_STARS.fullmatch(text)
        if match is not None:
            return _parse_integer(match.group("count"), rank, "starsInPeriod", issues)
    return None


def _parse_integer(
    value: str,
    rank: int,
    field: str,
    issues: list[SnapshotIssue],
) -> int | None:
    try:
        parsed = int(value.replace(",", ""))
    except ValueError:
        issues.append(SnapshotIssue("invalid_integer", rank, field, value))
        return None
    if parsed < 0:
        issues.append(SnapshotIssue("out_of_range", rank, field, value))
        return None
    return parsed
