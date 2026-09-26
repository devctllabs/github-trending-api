import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import httpx

from github_trending.adapters.filesystem import FilesystemDatasetPublisher
from github_trending.adapters.github import GitHubTrendingSource
from github_trending.domain import Feed, Period, RunReport, RunStatus, Snapshot
from github_trending.service import GenerationService, ProgressReporter, SourceError

if TYPE_CHECKING:
    from collections.abc import Sequence

LANGUAGES = ("all", "python", "rust", "go", "javascript", "typescript")
DEFAULT_FEEDS = tuple(Feed(period, language) for language in LANGUAGES for period in Period)


class GenerationRunner(Protocol):
    """Run one complete dataset update."""

    def run(self, *, progress: ProgressReporter | None = None) -> RunReport:
        """Return the update report."""
        ...


@dataclass(frozen=True, slots=True)
class CliDeps:
    """Behavioral dependencies supplied to the command boundary."""

    generator: GenerationRunner


class _ConsoleProgressReporter:
    def fetching(self, position: int, total: int, feed: Feed) -> None:
        print(f"[{position}/{total}] {feed.key}: fetching", flush=True)

    def published(self, position: int, total: int, snapshot: Snapshot) -> None:
        print(
            f"[{position}/{total}] {snapshot.feed.key}: published "
            f"repositories={len(snapshot.items)} status={snapshot.status.value} "
            f"issues={len(snapshot.issues)}",
            flush=True,
        )

    def failed(self, position: int, total: int, feed: Feed, error: SourceError) -> None:
        print(
            f"[{position}/{total}] {feed.key}: failed "
            f"category={error.category} detail={error.detail}",
            flush=True,
        )


def main(argv: Sequence[str] | None = None, deps: CliDeps | None = None) -> int:
    """Generate the dataset and return a stable process exit code."""
    parser = argparse.ArgumentParser(
        prog="github-trending",
        description="Generate current and archived GitHub Trending JSON/RSS datasets.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        metavar="PATH",
        help="Output directory (default: data).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print progress for every feed.",
    )
    args = parser.parse_args(argv)
    progress = _ConsoleProgressReporter() if args.verbose else None

    try:
        report = (
            deps.generator.run(progress=progress)
            if deps is not None
            else _run_default(args.data_dir, progress)
        )
    except (OSError, ValueError) as exc:
        print(f"github-trending: {exc}", file=sys.stderr)
        return 1

    summary = _format_summary(report)
    print(summary, end="")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path is not None:
        with Path(summary_path).open("a", encoding="utf-8") as stream:
            stream.write(summary)
    return 0 if report.status is RunStatus.COMPLETE else 2


def _run_default(data_dir: Path, progress: ProgressReporter | None) -> RunReport:
    repository = os.environ.get("GITHUB_REPOSITORY", "github-trending-api")
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": f"github-trending-api/1 (+https://github.com/{repository})",
    }
    timeout = httpx.Timeout(20.0, connect=5.0)
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        source = GitHubTrendingSource(
            client=client,
            clock=lambda: datetime.now(UTC),
            sleep=time.sleep,
            jitter=random.random,
        )
        publisher = FilesystemDatasetPublisher(data_dir)
        return GenerationService(source, publisher, DEFAULT_FEEDS).run(progress=progress)


def _format_summary(report: RunReport) -> str:
    lines = [
        "# GitHub Trending update",
        "",
        f"- Status: {report.status.value}",
        f"- Started: {report.started_at.astimezone(UTC).isoformat()}",
        f"- Published feeds: {len(report.published)}",
    ]
    if report.failures:
        lines.extend(("", "## Stale feeds", ""))
        for failure in report.failures:
            detail = failure.detail.replace("|", "\\|")
            lines.append(f"- `{failure.feed.key}`: {failure.category} — {detail}")
    if report.degraded:
        lines.extend(("", "## Degraded feeds", ""))
        for degradation in report.degraded:
            lines.extend(
                (f"- `{degradation.feed.key}`: {issue.code} at rank {issue.rank} ({issue.field})")
                for issue in degradation.issues
            )
    lines.append("")
    return "\n".join(lines)
