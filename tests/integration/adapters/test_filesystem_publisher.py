import json
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from github_trending.adapters.filesystem import FilesystemDatasetPublisher
from github_trending.domain import (
    DocumentStatus,
    Feed,
    Period,
    RepositoryItem,
    Snapshot,
    SnapshotIssue,
)
from github_trending.formats import decode_rollup_json

if TYPE_CHECKING:
    from pathlib import Path


def snapshot(
    observed_at: datetime,
    *,
    rank: int,
    stars: int | None,
    status: DocumentStatus = DocumentStatus.COMPLETE,
    stars_in_period: int | None = 742,
) -> Snapshot:
    issues = (
        (SnapshotIssue("invalid_integer", 4, "stars", "unavailable"),)
        if status is DocumentStatus.DEGRADED
        else ()
    )
    return Snapshot(
        feed=Feed(Period.DAILY, "rust"),
        source_url="https://github.com/trending/rust",
        observed_at=observed_at,
        status=status,
        issues=issues,
        items=(
            RepositoryItem(
                rank=rank,
                full_name="astral-sh/uv",
                url="https://github.com/astral-sh/uv",
                description="An extremely fast package manager.",
                programming_language="Rust",
                stars=stars,
                forks=1_289,
                stars_in_period=stars_in_period,
            ),
        ),
    )


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def test_publish_writes_current_and_mergeable_daily_json_and_rss(tmp_path: Path) -> None:
    archive_date = date(2026, 9, 25)
    first_at = datetime(2026, 9, 25, 0, 17, 12, tzinfo=UTC)
    second_at = datetime(2026, 9, 25, 6, 17, 13, tzinfo=UTC)
    data_root = tmp_path / "data"

    FilesystemDatasetPublisher(data_root).publish(
        snapshot(first_at, rank=8, stars=100), archive_date
    )
    FilesystemDatasetPublisher(data_root).publish(
        snapshot(second_at, rank=3, stars=None, status=DocumentStatus.DEGRADED),
        archive_date,
    )

    current_json = data_root / "current/daily/rust.json"
    current_xml = data_root / "current/daily/rust.xml"
    archive_json = data_root / "archive/2026/09/25/daily/rust.json"
    archive_xml = data_root / "archive/2026/09/25/daily/rust.xml"
    assert all(path.is_file() for path in (current_json, current_xml, archive_json, archive_xml))

    assert read_json(current_json) == {
        "schemaVersion": 1,
        "kind": "snapshot",
        "period": "daily",
        "language": "rust",
        "sourceUrl": "https://github.com/trending/rust",
        "observedAt": "2026-09-25T06:17:13Z",
        "status": "degraded",
        "issues": [
            {
                "code": "invalid_integer",
                "rank": 4,
                "field": "stars",
                "rawValue": "unavailable",
            }
        ],
        "items": [
            {
                "rank": 3,
                "fullName": "astral-sh/uv",
                "url": "https://github.com/astral-sh/uv",
                "description": "An extremely fast package manager.",
                "programmingLanguage": "Rust",
                "stars": None,
                "forks": 1_289,
                "starsInPeriod": 742,
            }
        ],
    }
    assert read_json(archive_json) == {
        "schemaVersion": 1,
        "kind": "daily-rollup",
        "date": "2026-09-25",
        "period": "daily",
        "language": "rust",
        "sourceUrl": "https://github.com/trending/rust",
        "updatedAt": "2026-09-25T06:17:13Z",
        "latestStatus": "degraded",
        "latestIssues": [
            {
                "code": "invalid_integer",
                "rank": 4,
                "field": "stars",
                "rawValue": "unavailable",
            }
        ],
        "items": [
            {
                "fullName": "astral-sh/uv",
                "url": "https://github.com/astral-sh/uv",
                "description": "An extremely fast package manager.",
                "programmingLanguage": "Rust",
                "stars": None,
                "forks": 1_289,
                "starsInPeriod": 742,
                "bestRank": 3,
                "latestRank": 3,
                "firstSeenAt": "2026-09-25T00:17:12Z",
                "lastSeenAt": "2026-09-25T06:17:13Z",
                "appearances": 2,
            }
        ],
    }
    for xml_path in (current_xml, archive_xml):
        root = ElementTree.parse(xml_path).getroot()  # noqa: S314 - parses trusted generated XML
        assert root.tag == "rss"
        assert root.attrib == {"version": "2.0"}
        title = root.find("channel/item/title")
        schema_version = root.find("channel/{urn:github-trending:v1}schemaVersion")
        assert title is not None
        assert title.text == "astral-sh/uv"
        assert schema_version is not None
        assert schema_version.text == "1"
        stars = root.find("channel/item/{urn:github-trending:v1}stars")
        issue = root.find("channel/{urn:github-trending:v1}issues/{urn:github-trending:v1}issue")
        if issue is None:
            issue = root.find(
                "channel/{urn:github-trending:v1}latestIssues/{urn:github-trending:v1}issue"
            )
        assert stars is not None
        assert stars.text is None
        assert issue is not None
        assert issue.attrib["rawValue"] == "unavailable"

    decoded = decode_rollup_json(archive_json.read_text())
    assert decoded.items[0].stars is None
    assert decoded.latest_issues[0].raw_value == "unavailable"

    legacy_document = read_json(archive_json)
    assert isinstance(legacy_document, dict)
    legacy_issues = legacy_document["latestIssues"]
    assert isinstance(legacy_issues, list)
    assert isinstance(legacy_issues[0], dict)
    legacy_issues[0].pop("rawValue")
    legacy = decode_rollup_json(json.dumps(legacy_document))
    assert legacy.latest_issues[0].raw_value is None

    assert current_json.read_bytes().endswith(b"\n")
    assert archive_json.read_bytes().endswith(b"\n")


def test_missing_metric_has_json_null_and_no_xml_raw_value(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    missing = replace(
        snapshot(
            datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
            rank=1,
            stars=None,
            status=DocumentStatus.DEGRADED,
        ),
        issues=(SnapshotIssue("missing_field", 1, "stars"),),
    )

    FilesystemDatasetPublisher(data_root).publish(missing, date(2026, 9, 25))

    document = read_json(data_root / "current/daily/rust.json")
    assert isinstance(document, dict)
    issues = document["issues"]
    assert isinstance(issues, list)
    assert isinstance(issues[0], dict)
    assert issues[0]["rawValue"] is None
    root = ElementTree.parse(  # noqa: S314 - parses trusted generated XML
        data_root / "current/daily/rust.xml"
    ).getroot()
    issue = root.find("channel/{urn:github-trending:v1}issues/{urn:github-trending:v1}issue")
    assert issue is not None
    assert "rawValue" not in issue.attrib


def test_optional_period_metric_is_published_as_null_without_issue(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    complete = snapshot(
        datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        rank=1,
        stars=100,
        stars_in_period=None,
    )

    FilesystemDatasetPublisher(data_root).publish(complete, date(2026, 9, 25))

    document = read_json(data_root / "current/daily/rust.json")
    assert isinstance(document, dict)
    assert document["status"] == "complete"
    assert document["issues"] == []
    items = document["items"]
    assert isinstance(items, list)
    assert isinstance(items[0], dict)
    assert items[0]["starsInPeriod"] is None
    root = ElementTree.parse(  # noqa: S314 - parses trusted generated XML
        data_root / "current/daily/rust.xml"
    ).getroot()
    period_stars = root.find("channel/item/{urn:github-trending:v1}starsInPeriod")
    assert period_stars is not None
    assert period_stars.text is None


def test_new_utc_date_does_not_rewrite_previous_rollup(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    first_date = date(2026, 9, 25)
    publisher = FilesystemDatasetPublisher(data_root)
    publisher.publish(
        snapshot(datetime(2026, 9, 25, 18, 17, tzinfo=UTC), rank=5, stars=100),
        first_date,
    )
    first_path = data_root / "archive/2026/09/25/daily/rust.json"
    original = first_path.read_bytes()

    publisher.publish(
        snapshot(datetime(2026, 9, 26, 0, 17, tzinfo=UTC), rank=2, stars=120),
        date(2026, 9, 26),
    )

    assert first_path.read_bytes() == original
    second = read_json(data_root / "archive/2026/09/26/daily/rust.json")
    assert isinstance(second, dict)
    assert second["date"] == "2026-09-26"
    items = second["items"]
    assert isinstance(items, list)
    assert isinstance(items[0], dict)
    assert items[0]["appearances"] == 1
