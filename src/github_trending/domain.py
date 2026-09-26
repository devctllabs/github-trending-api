from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

SCHEMA_VERSION = 1


class Period(StrEnum):
    """A time window exposed by GitHub Trending."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DocumentStatus(StrEnum):
    """Completeness of a successfully parsed document."""

    COMPLETE = "complete"
    DEGRADED = "degraded"


class RunStatus(StrEnum):
    """Overall result of one generation run."""

    COMPLETE = "complete"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class Feed:
    """One language and period combination."""

    period: Period
    language: str

    @property
    def key(self) -> str:
        """Return the stable human-readable feed key."""
        return f"{self.period.value}/{self.language}"


@dataclass(frozen=True, slots=True)
class SnapshotIssue:
    """A structured problem with one source ranking item."""

    code: str
    rank: int
    field: str
    raw_value: str | None = None


@dataclass(frozen=True, slots=True)
class RepositoryItem:
    """One repository observed in a GitHub Trending ranking."""

    rank: int
    full_name: str
    url: str
    description: str | None
    programming_language: str | None
    stars: int | None
    forks: int | None
    stars_in_period: int | None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A successfully parsed GitHub Trending feed."""

    feed: Feed
    source_url: str
    observed_at: datetime
    status: DocumentStatus
    issues: tuple[SnapshotIssue, ...]
    items: tuple[RepositoryItem, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RollupItem:
    """One repository aggregated across observations in a UTC day."""

    full_name: str
    url: str
    description: str | None
    programming_language: str | None
    stars: int | None
    forks: int | None
    stars_in_period: int | None
    best_rank: int
    latest_rank: int
    first_seen_at: datetime
    last_seen_at: datetime
    appearances: int


@dataclass(frozen=True, slots=True)
class DailyRollup:
    """A unique-repository aggregation for one feed and UTC date."""

    feed: Feed
    date: date
    source_url: str
    updated_at: datetime
    latest_status: DocumentStatus
    latest_issues: tuple[SnapshotIssue, ...]
    items: tuple[RollupItem, ...]


def merge_snapshot(
    existing: DailyRollup | None,
    snapshot: Snapshot,
    archive_date: date,
) -> DailyRollup:
    """Merge a snapshot into its UTC day's compact rollup."""
    existing_items = () if existing is None else existing.items
    items_by_name = {item.full_name.casefold(): item for item in existing_items}
    for observed in snapshot.items:
        key = observed.full_name.casefold()
        previous = items_by_name.get(key)
        items_by_name[key] = _merge_item(previous, observed, snapshot.observed_at)

    items = tuple(
        sorted(
            items_by_name.values(),
            key=lambda item: (item.best_rank, item.first_seen_at, item.full_name.casefold()),
        )
    )
    return DailyRollup(
        feed=snapshot.feed,
        date=archive_date,
        source_url=snapshot.source_url,
        updated_at=snapshot.observed_at,
        latest_status=snapshot.status,
        latest_issues=snapshot.issues,
        items=items,
    )


def _merge_item(
    previous: RollupItem | None,
    observed: RepositoryItem,
    observed_at: datetime,
) -> RollupItem:
    first_seen_at = observed_at if previous is None else previous.first_seen_at
    best_rank = observed.rank if previous is None else min(previous.best_rank, observed.rank)
    appearances = 1 if previous is None else previous.appearances + 1
    return RollupItem(
        full_name=observed.full_name,
        url=observed.url,
        description=observed.description,
        programming_language=observed.programming_language,
        stars=observed.stars,
        forks=observed.forks,
        stars_in_period=observed.stars_in_period,
        best_rank=best_rank,
        latest_rank=observed.rank,
        first_seen_at=first_seen_at,
        last_seen_at=observed_at,
        appearances=appearances,
    )


@dataclass(frozen=True, slots=True)
class FeedFailure:
    """A feed that could not produce a new snapshot."""

    feed: Feed
    category: str
    detail: str


@dataclass(frozen=True, slots=True)
class FeedDegradation:
    """A published feed with one or more malformed source fields."""

    feed: Feed
    issues: tuple[SnapshotIssue, ...]


@dataclass(frozen=True, slots=True)
class RunReport:
    """Result of attempting every configured feed once."""

    started_at: datetime
    status: RunStatus
    published: tuple[Feed, ...]
    failures: tuple[FeedFailure, ...]
    degraded: tuple[FeedDegradation, ...] = ()

    @property
    def archive_date(self) -> date:
        """Return the UTC date that owns all observations in this run."""
        return self.started_at.astimezone(UTC).date()
