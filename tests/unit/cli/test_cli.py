from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from github_trending.cli import CliDeps, main
from github_trending.domain import (
    DocumentStatus,
    Feed,
    FeedDegradation,
    FeedFailure,
    Period,
    RunReport,
    RunStatus,
    Snapshot,
    SnapshotIssue,
)
from github_trending.service import ProgressReporter, SourceError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class StubGenerator:
    report: RunReport
    calls: int = 0
    received_progress: ProgressReporter | None = None

    def run(self, *, progress: ProgressReporter | None = None) -> RunReport:
        self.calls += 1
        self.received_progress = progress
        return self.report


class FailingGenerator:
    def run(self, *, progress: ProgressReporter | None = None) -> RunReport:
        del progress
        raise ValueError("archive schema is invalid")


@dataclass
class ProgressGeneratingStub:
    report: RunReport
    snapshot: Snapshot
    failed_feed: Feed

    def run(self, *, progress: ProgressReporter | None = None) -> RunReport:
        assert progress is not None
        progress.fetching(1, 2, self.snapshot.feed)
        progress.published(1, 2, self.snapshot)
        progress.fetching(2, 2, self.failed_feed)
        progress.failed(2, 2, self.failed_feed, SourceError("fetch_failed", "HTTP 503"))
        return self.report


def report(status: RunStatus) -> RunReport:
    return RunReport(
        started_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        status=status,
        published=(Feed(Period.DAILY, "rust"),),
        failures=(),
    )


def test_complete_run_prints_summary_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    generator = StubGenerator(report(RunStatus.COMPLETE))

    exit_code = main([], CliDeps(generator))

    assert exit_code == 0
    assert generator.calls == 1
    assert generator.received_progress is None
    assert "Status: complete" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-v", "--verbose"])
def test_verbose_flag_supplies_progress_reporter(flag: str) -> None:
    generator = StubGenerator(report(RunStatus.COMPLETE))

    exit_code = main([flag], CliDeps(generator))

    assert exit_code == 0
    assert generator.received_progress is not None


@pytest.mark.parametrize(
    ("status", "issues", "published_line"),
    [
        (
            DocumentStatus.COMPLETE,
            (),
            "[1/2] daily/rust: published repositories=0 status=complete issues=0",
        ),
        (
            DocumentStatus.DEGRADED,
            (SnapshotIssue("missing_field", 4, "starsInPeriod"),),
            "[1/2] daily/rust: published repositories=0 status=degraded issues=1",
        ),
    ],
)
def test_verbose_run_streams_feed_progress(
    status: DocumentStatus,
    issues: tuple[SnapshotIssue, ...],
    published_line: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    successful_feed = Feed(Period.DAILY, "rust")
    failed_feed = Feed(Period.WEEKLY, "python")
    snapshot = Snapshot(
        feed=successful_feed,
        source_url="https://github.com/trending/rust",
        observed_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
        status=status,
        issues=issues,
        items=(),
    )
    generator = ProgressGeneratingStub(report(RunStatus.DEGRADED), snapshot, failed_feed)

    exit_code = main(["--verbose"], CliDeps(generator))

    assert exit_code == 2
    assert capsys.readouterr().out.startswith(
        "[1/2] daily/rust: fetching\n"
        f"{published_line}\n"
        "[2/2] weekly/python: fetching\n"
        "[2/2] weekly/python: failed category=fetch_failed detail=HTTP 503\n"
        "# GitHub Trending update\n"
    )


def test_degraded_run_writes_actions_summary_and_returns_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary_path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    failed = Feed(Period.WEEKLY, "python")
    degraded = Feed(Period.DAILY, "rust")
    generator = StubGenerator(
        RunReport(
            started_at=datetime(2026, 9, 25, 6, 17, tzinfo=UTC),
            status=RunStatus.DEGRADED,
            published=(degraded,),
            failures=(FeedFailure(failed, "fetch_failed", "HTTP 503"),),
            degraded=(
                FeedDegradation(
                    degraded,
                    (SnapshotIssue("invalid_integer", 4, "stars"),),
                ),
            ),
        )
    )

    exit_code = main([], CliDeps(generator))

    assert exit_code == 2
    summary = summary_path.read_text()
    assert "Status: degraded" in summary
    assert "weekly/python" in summary
    assert "fetch_failed" in summary
    assert "daily/rust" in summary
    assert "invalid_integer at rank 4 (stars)" in summary


def test_help_does_not_construct_or_run_dependencies(capsys: pytest.CaptureFixture[str]) -> None:
    generator = StubGenerator(report(RunStatus.COMPLETE))

    with pytest.raises(SystemExit) as exc:
        main(["--help"], CliDeps(generator))

    assert exc.value.code == 0
    assert generator.calls == 0
    assert "-v, --verbose" in capsys.readouterr().out


def test_fatal_generation_error_returns_one(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([], CliDeps(FailingGenerator()))

    assert exit_code == 1
    assert "archive schema is invalid" in capsys.readouterr().err
