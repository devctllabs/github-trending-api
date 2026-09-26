from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from github_trending.domain import (
    DocumentStatus,
    Feed,
    Period,
    RepositoryItem,
    RunStatus,
    Snapshot,
    SnapshotIssue,
)
from github_trending.service import GenerationService, SourceError


@dataclass
class StubSource:
    snapshot: Snapshot

    def fetch(self, feed: Feed) -> Snapshot:
        assert feed == self.snapshot.feed
        return self.snapshot


@dataclass
class SpyPublisher:
    published: list[tuple[Snapshot, date]] = field(default_factory=list)

    def publish(self, snapshot: Snapshot, archive_date: date) -> None:
        self.published.append((snapshot, archive_date))


@dataclass
class SpyProgressReporter:
    events: list[str] = field(default_factory=list)

    def fetching(self, position: int, total: int, feed: Feed) -> None:
        self.events.append(f"fetching {position}/{total} {feed.key}")

    def published(self, position: int, total: int, snapshot: Snapshot) -> None:
        self.events.append(f"published {position}/{total} {snapshot.feed.key}")

    def failed(self, position: int, total: int, feed: Feed, error: SourceError) -> None:
        self.events.append(f"failed {position}/{total} {feed.key} {error.category}")


@dataclass
class PartiallyFailingSource:
    snapshots: dict[Feed, Snapshot]
    failing_feed: Feed

    def fetch(self, feed: Feed) -> Snapshot:
        if feed == self.failing_feed:
            raise SourceError(category="fetch_failed", detail="HTTP 503")
        return self.snapshots[feed]


def test_successful_feed_is_published_for_the_run_utc_date() -> None:
    feed = Feed(period=Period.DAILY, language="python")
    observed_at = datetime(2026, 9, 25, 6, 17, tzinfo=UTC)
    snapshot = Snapshot(
        feed=feed,
        source_url="https://github.com/trending/python",
        observed_at=observed_at,
        status=DocumentStatus.COMPLETE,
        issues=(),
        items=(
            RepositoryItem(
                rank=1,
                full_name="astral-sh/uv",
                url="https://github.com/astral-sh/uv",
                description="An extremely fast Python package manager.",
                programming_language="Rust",
                stars=42_137,
                forks=1_289,
                stars_in_period=742,
            ),
        ),
    )
    publisher = SpyPublisher()
    started_at = datetime(2026, 9, 25, 23, 59, tzinfo=UTC)

    report = GenerationService(StubSource(snapshot), publisher, (feed,)).run(started_at)

    assert report.status is RunStatus.COMPLETE
    assert report.published == (feed,)
    assert report.failures == ()
    assert publisher.published == [(snapshot, date(2026, 9, 25))]


def test_failed_feed_stays_stale_while_later_feeds_are_published() -> None:
    failed_feed = Feed(period=Period.DAILY, language="python")
    successful_feed = Feed(period=Period.DAILY, language="rust")
    snapshot = Snapshot(
        feed=successful_feed,
        source_url="https://github.com/trending/rust",
        observed_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        status=DocumentStatus.COMPLETE,
        issues=(),
        items=(),
    )
    publisher = SpyPublisher()
    source = PartiallyFailingSource({successful_feed: snapshot}, failed_feed)

    report = GenerationService(source, publisher, (failed_feed, successful_feed)).run(
        datetime(2026, 9, 25, 6, 17, tzinfo=UTC)
    )

    assert report.status is RunStatus.DEGRADED
    assert report.published == (successful_feed,)
    assert len(report.failures) == 1
    assert report.failures[0].feed == failed_feed
    assert report.failures[0].category == "fetch_failed"
    assert report.failures[0].detail == "HTTP 503"
    assert publisher.published == [(snapshot, date(2026, 9, 25))]


def test_progress_reports_each_feed_in_processing_order() -> None:
    failed_feed = Feed(period=Period.DAILY, language="python")
    successful_feed = Feed(period=Period.DAILY, language="rust")
    snapshot = Snapshot(
        feed=successful_feed,
        source_url="https://github.com/trending/rust",
        observed_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        status=DocumentStatus.COMPLETE,
        issues=(),
        items=(),
    )
    progress = SpyProgressReporter()
    source = PartiallyFailingSource({successful_feed: snapshot}, failed_feed)

    GenerationService(source, SpyPublisher(), (failed_feed, successful_feed)).run(
        datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        progress=progress,
    )

    assert progress.events == [
        "fetching 1/2 daily/python",
        "failed 1/2 daily/python fetch_failed",
        "fetching 2/2 daily/rust",
        "published 2/2 daily/rust",
    ]


def test_item_level_issues_are_reported_after_degraded_snapshot_is_published() -> None:
    feed = Feed(Period.DAILY, "rust")
    issue = SnapshotIssue("invalid_integer", 4, "stars")
    snapshot = Snapshot(
        feed=feed,
        source_url="https://github.com/trending/rust",
        observed_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        status=DocumentStatus.DEGRADED,
        issues=(issue,),
        items=(),
    )

    report = GenerationService(StubSource(snapshot), SpyPublisher(), (feed,)).run(
        datetime(2026, 9, 25, 6, 17, tzinfo=UTC)
    )

    assert report.status is RunStatus.DEGRADED
    assert report.degraded[0].feed == feed
    assert report.degraded[0].issues == (issue,)
