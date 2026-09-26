from typing import TYPE_CHECKING

from github_trending.domain import Snapshot, merge_snapshot
from github_trending.formats import (
    decode_rollup_json,
    render_rollup_json,
    render_rollup_xml,
    render_snapshot_json,
    render_snapshot_xml,
)

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path


class FilesystemDatasetPublisher:
    """Publish current snapshots and UTC daily rollups under a data root."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root

    def publish(self, snapshot: Snapshot, archive_date: date) -> None:
        """Write matching JSON and RSS documents for one feed."""
        current_base = (
            self._data_root / "current" / snapshot.feed.period.value / snapshot.feed.language
        )
        archive_base = (
            self._data_root
            / "archive"
            / f"{archive_date:%Y/%m/%d}"
            / snapshot.feed.period.value
            / snapshot.feed.language
        )
        archive_json_path = archive_base.with_suffix(".json")
        existing = None
        if archive_json_path.exists():
            existing = decode_rollup_json(archive_json_path.read_text(encoding="utf-8"))
        rollup = merge_snapshot(existing, snapshot, archive_date)

        documents = {
            current_base.with_suffix(".json"): render_snapshot_json(snapshot),
            current_base.with_suffix(".xml"): render_snapshot_xml(snapshot),
            archive_json_path: render_rollup_json(rollup),
            archive_base.with_suffix(".xml"): render_rollup_xml(rollup),
        }
        for path, payload in documents.items():
            _replace_text(path, payload)


def _replace_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
