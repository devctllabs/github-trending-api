from datetime import UTC, date, datetime

from github_trending.domain import (
    DocumentStatus,
    Feed,
    Period,
    RepositoryItem,
    Snapshot,
    SnapshotIssue,
    merge_snapshot,
)


def item(rank: int, full_name: str, stars: int) -> RepositoryItem:
    return RepositoryItem(
        rank=rank,
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        description=f"Latest description for {full_name}",
        programming_language="Rust",
        stars=stars,
        forks=100,
        stars_in_period=50,
    )


def test_merge_keeps_latest_fields_and_daily_rank_extrema() -> None:
    feed = Feed(Period.DAILY, "rust")
    first_at = datetime(2026, 9, 25, 0, 17, tzinfo=UTC)
    latest_at = datetime(2026, 9, 25, 6, 17, tzinfo=UTC)
    archive_date = date(2026, 9, 25)
    first = Snapshot(
        feed=feed,
        source_url="https://github.com/trending/rust",
        observed_at=first_at,
        status=DocumentStatus.COMPLETE,
        issues=(),
        items=(item(8, "Owner/Alpha", 100),),
    )
    existing = merge_snapshot(None, first, archive_date)
    issue = SnapshotIssue(code="invalid_integer", rank=4, field="stars")
    latest = Snapshot(
        feed=feed,
        source_url="https://github.com/trending/rust",
        observed_at=latest_at,
        status=DocumentStatus.DEGRADED,
        issues=(issue,),
        items=(item(3, "owner/alpha", 120), item(2, "owner/beta", 80)),
    )

    result = merge_snapshot(existing, latest, archive_date)

    assert result.updated_at == latest_at
    assert result.latest_status is DocumentStatus.DEGRADED
    assert result.latest_issues == (issue,)
    assert [entry.full_name for entry in result.items] == ["owner/beta", "owner/alpha"]
    beta, alpha = result.items
    assert beta.best_rank == 2
    assert beta.appearances == 1
    assert alpha.stars == 120
    assert alpha.best_rank == 3
    assert alpha.latest_rank == 3
    assert alpha.first_seen_at == first_at
    assert alpha.last_seen_at == latest_at
    assert alpha.appearances == 2
