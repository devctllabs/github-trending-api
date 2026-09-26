from datetime import UTC, date, datetime
from typing import Protocol

from github_trending.domain import (
    DocumentStatus,
    Feed,
    FeedDegradation,
    FeedFailure,
    RunReport,
    RunStatus,
    Snapshot,
)


class SourceError(Exception):
    """A normalized failure to obtain one feed."""

    def __init__(self, category: str, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail


class ProgressReporter(Protocol):
    """Receive caller-facing progress for one generation run."""

    def fetching(self, position: int, total: int, feed: Feed) -> None:
        """Report that fetching one feed has started."""
        ...

    def published(self, position: int, total: int, snapshot: Snapshot) -> None:
        """Report that one feed has been published."""
        ...

    def failed(self, position: int, total: int, feed: Feed, error: SourceError) -> None:
        """Report that one feed could not be fetched."""
        ...


class FeedSource(Protocol):
    """Fetch one configured Trending feed."""

    def fetch(self, feed: Feed) -> Snapshot:
        """Return a parsed snapshot or raise a normalized source error."""
        ...


class DatasetPublisher(Protocol):
    """Publish one snapshot into current and daily archive outputs."""

    def publish(self, snapshot: Snapshot, archive_date: date) -> None:
        """Persist a snapshot for its owning UTC archive date."""
        ...


class GenerationService:
    """Coordinate one complete traversal of the configured feeds."""

    def __init__(
        self,
        source: FeedSource,
        publisher: DatasetPublisher,
        feeds: tuple[Feed, ...],
    ) -> None:
        self._source = source
        self._publisher = publisher
        self._feeds = feeds

    def run(
        self,
        started_at: datetime | None = None,
        *,
        progress: ProgressReporter | None = None,
    ) -> RunReport:
        """Fetch and publish every feed while isolating feed-level failures."""
        run_started_at = started_at or datetime.now(UTC)
        archive_date = run_started_at.astimezone(UTC).date()
        published: list[Feed] = []
        failures: list[FeedFailure] = []
        degraded: list[FeedDegradation] = []
        status = RunStatus.COMPLETE

        total = len(self._feeds)
        for position, feed in enumerate(self._feeds, start=1):
            if progress is not None:
                progress.fetching(position, total, feed)
            try:
                snapshot = self._source.fetch(feed)
            except SourceError as exc:
                status = RunStatus.DEGRADED
                failures.append(FeedFailure(feed, exc.category, exc.detail))
                if progress is not None:
                    progress.failed(position, total, feed, exc)
                continue
            self._publisher.publish(snapshot, archive_date)
            published.append(feed)
            if progress is not None:
                progress.published(position, total, snapshot)
            if snapshot.status is DocumentStatus.DEGRADED:
                status = RunStatus.DEGRADED
                degraded.append(FeedDegradation(feed, snapshot.issues))

        return RunReport(
            started_at=run_started_at,
            status=status,
            published=tuple(published),
            failures=tuple(failures),
            degraded=tuple(degraded),
        )
