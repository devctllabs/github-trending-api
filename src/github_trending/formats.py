import json
from datetime import UTC, date, datetime
from email.utils import format_datetime
from typing import cast
from xml.etree import ElementTree

from github_trending.domain import (
    SCHEMA_VERSION,
    DailyRollup,
    DocumentStatus,
    Feed,
    Period,
    RepositoryItem,
    RollupItem,
    Snapshot,
    SnapshotIssue,
)

GHT_NAMESPACE = "urn:github-trending:v1"
ElementTree.register_namespace("ght", GHT_NAMESPACE)


def render_snapshot_json(snapshot: Snapshot) -> str:
    """Serialize a current snapshot as stable UTF-8 JSON text."""
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "snapshot",
        "period": snapshot.feed.period.value,
        "language": snapshot.feed.language,
        "sourceUrl": snapshot.source_url,
        "observedAt": _rfc3339(snapshot.observed_at),
        "status": snapshot.status.value,
        "issues": [_issue_document(issue) for issue in snapshot.issues],
        "items": [_snapshot_item_document(item) for item in snapshot.items],
    }
    return _json_text(document)


def render_rollup_json(rollup: DailyRollup) -> str:
    """Serialize a daily rollup as stable UTF-8 JSON text."""
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "daily-rollup",
        "date": rollup.date.isoformat(),
        "period": rollup.feed.period.value,
        "language": rollup.feed.language,
        "sourceUrl": rollup.source_url,
        "updatedAt": _rfc3339(rollup.updated_at),
        "latestStatus": rollup.latest_status.value,
        "latestIssues": [_issue_document(issue) for issue in rollup.latest_issues],
        "items": [_rollup_item_document(item) for item in rollup.items],
    }
    return _json_text(document)


def decode_rollup_json(payload: str) -> DailyRollup:
    """Decode and validate a previously generated daily rollup."""
    raw: object = json.loads(payload)
    document = _mapping(raw)
    if _integer(document, "schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unsupported schemaVersion")
    if _string(document, "kind") != "daily-rollup":
        raise ValueError("expected daily-rollup document")
    feed = Feed(Period(_string(document, "period")), _string(document, "language"))
    return DailyRollup(
        feed=feed,
        date=date.fromisoformat(_string(document, "date")),
        source_url=_string(document, "sourceUrl"),
        updated_at=_datetime(document, "updatedAt"),
        latest_status=DocumentStatus(_string(document, "latestStatus")),
        latest_issues=tuple(
            _decode_issue(_mapping(value)) for value in _list(document, "latestIssues")
        ),
        items=tuple(_decode_rollup_item(_mapping(value)) for value in _list(document, "items")),
    )


def render_snapshot_xml(snapshot: Snapshot) -> str:
    """Serialize a current snapshot as RSS 2.0 with typed extensions."""
    root, channel = _rss_channel(snapshot.feed, snapshot.source_url, snapshot.observed_at)
    _extension(channel, "schemaVersion", str(SCHEMA_VERSION))
    _extension(channel, "kind", "snapshot")
    _extension(channel, "period", snapshot.feed.period.value)
    _extension(channel, "language", snapshot.feed.language)
    _extension(channel, "observedAt", _rfc3339(snapshot.observed_at))
    _extension(channel, "status", snapshot.status.value)
    _append_issues(channel, snapshot.issues)
    for item in snapshot.items:
        element = _rss_item(channel, item, snapshot.observed_at)
        _extension(element, "rank", str(item.rank))
        _append_repository_extensions(element, item)
    return _xml_text(root)


def render_rollup_xml(rollup: DailyRollup) -> str:
    """Serialize a daily rollup as RSS 2.0 with typed extensions."""
    root, channel = _rss_channel(rollup.feed, rollup.source_url, rollup.updated_at)
    _extension(channel, "schemaVersion", str(SCHEMA_VERSION))
    _extension(channel, "kind", "daily-rollup")
    _extension(channel, "date", rollup.date.isoformat())
    _extension(channel, "period", rollup.feed.period.value)
    _extension(channel, "language", rollup.feed.language)
    _extension(channel, "updatedAt", _rfc3339(rollup.updated_at))
    _extension(channel, "latestStatus", rollup.latest_status.value)
    _append_issues(channel, rollup.latest_issues, container_name="latestIssues")
    for item in rollup.items:
        element = _rss_item(channel, item, item.first_seen_at)
        _append_repository_extensions(element, item)
        _extension(element, "bestRank", str(item.best_rank))
        _extension(element, "latestRank", str(item.latest_rank))
        _extension(element, "firstSeenAt", _rfc3339(item.first_seen_at))
        _extension(element, "lastSeenAt", _rfc3339(item.last_seen_at))
        _extension(element, "appearances", str(item.appearances))
    return _xml_text(root)


def _snapshot_item_document(item: RepositoryItem) -> dict[str, object]:
    return {
        "rank": item.rank,
        "fullName": item.full_name,
        "url": item.url,
        "description": item.description,
        "programmingLanguage": item.programming_language,
        "stars": item.stars,
        "forks": item.forks,
        "starsInPeriod": item.stars_in_period,
    }


def _rollup_item_document(item: RollupItem) -> dict[str, object]:
    return {
        "fullName": item.full_name,
        "url": item.url,
        "description": item.description,
        "programmingLanguage": item.programming_language,
        "stars": item.stars,
        "forks": item.forks,
        "starsInPeriod": item.stars_in_period,
        "bestRank": item.best_rank,
        "latestRank": item.latest_rank,
        "firstSeenAt": _rfc3339(item.first_seen_at),
        "lastSeenAt": _rfc3339(item.last_seen_at),
        "appearances": item.appearances,
    }


def _issue_document(issue: SnapshotIssue) -> dict[str, object]:
    return {
        "code": issue.code,
        "rank": issue.rank,
        "field": issue.field,
        "rawValue": issue.raw_value,
    }


def _decode_issue(document: dict[str, object]) -> SnapshotIssue:
    return SnapshotIssue(
        code=_string(document, "code"),
        rank=_integer(document, "rank"),
        field=_string(document, "field"),
        raw_value=_optional_string(document, "rawValue"),
    )


def _decode_rollup_item(document: dict[str, object]) -> RollupItem:
    return RollupItem(
        full_name=_string(document, "fullName"),
        url=_string(document, "url"),
        description=_optional_string(document, "description"),
        programming_language=_optional_string(document, "programmingLanguage"),
        stars=_optional_integer(document, "stars"),
        forks=_optional_integer(document, "forks"),
        stars_in_period=_optional_integer(document, "starsInPeriod"),
        best_rank=_integer(document, "bestRank"),
        latest_rank=_integer(document, "latestRank"),
        first_seen_at=_datetime(document, "firstSeenAt"),
        last_seen_at=_datetime(document, "lastSeenAt"),
        appearances=_integer(document, "appearances"),
    )


def _rss_channel(
    feed: Feed,
    source_url: str,
    updated_at: datetime,
) -> tuple[ElementTree.Element, ElementTree.Element]:
    root = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(root, "channel")
    title = f"GitHub Trending — {feed.period.value} — {feed.language}"
    ElementTree.SubElement(channel, "title").text = title
    ElementTree.SubElement(channel, "link").text = source_url
    ElementTree.SubElement(channel, "description").text = title
    ElementTree.SubElement(channel, "lastBuildDate").text = _rss_datetime(updated_at)
    return root, channel


def _rss_item(
    channel: ElementTree.Element,
    item: RepositoryItem | RollupItem,
    published_at: datetime,
) -> ElementTree.Element:
    element = ElementTree.SubElement(channel, "item")
    ElementTree.SubElement(element, "title").text = item.full_name
    ElementTree.SubElement(element, "link").text = item.url
    ElementTree.SubElement(element, "description").text = item.description or ""
    ElementTree.SubElement(element, "guid", {"isPermaLink": "true"}).text = item.url
    ElementTree.SubElement(element, "pubDate").text = _rss_datetime(published_at)
    return element


def _append_repository_extensions(
    element: ElementTree.Element,
    item: RepositoryItem | RollupItem,
) -> None:
    _extension(element, "programmingLanguage", item.programming_language or "")
    _extension(element, "stars", _optional_integer_text(item.stars))
    _extension(element, "forks", _optional_integer_text(item.forks))
    _extension(element, "starsInPeriod", _optional_integer_text(item.stars_in_period))


def _append_issues(
    parent: ElementTree.Element,
    issues: tuple[SnapshotIssue, ...],
    *,
    container_name: str = "issues",
) -> None:
    container = ElementTree.SubElement(parent, _qualified(container_name))
    for issue in issues:
        attributes = {"code": issue.code, "rank": str(issue.rank), "field": issue.field}
        if issue.raw_value is not None:
            attributes["rawValue"] = issue.raw_value
        ElementTree.SubElement(
            container,
            _qualified("issue"),
            attributes,
        )


def _extension(parent: ElementTree.Element, name: str, value: str) -> None:
    ElementTree.SubElement(parent, _qualified(name)).text = value


def _qualified(name: str) -> str:
    return f"{{{GHT_NAMESPACE}}}{name}"


def _json_text(document: dict[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _xml_text(root: ElementTree.Element) -> str:
    ElementTree.indent(root, space="  ")
    payload = ElementTree.tostring(root, encoding="unicode", xml_declaration=True)
    return f"{payload}\n"


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rss_datetime(value: datetime) -> str:
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _optional_integer_text(value: int | None) -> str:
    return "" if value is None else str(value)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")
    return cast("dict[str, object]", value)


def _list(document: dict[str, object], key: str) -> list[object]:
    value = document.get(key)
    if not isinstance(value, list):
        raise TypeError(f"{key} must be an array")
    return cast("list[object]", value)


def _string(document: dict[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _optional_string(document: dict[str, object], key: str) -> str | None:
    value = document.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _integer(document: dict[str, object], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer")
    return value


def _optional_integer(document: dict[str, object], key: str) -> int | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer or null")
    return value


def _datetime(document: dict[str, object], key: str) -> datetime:
    value = datetime.fromisoformat(_string(document, key).replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{key} must include a timezone")
    return value
