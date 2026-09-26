# Deployment and Automation

The repository uses GitHub Actions both for validation and for publishing the static dataset. The
runtime is Python 3.14 with dependencies locked by `uv.lock`.

## Continuous integration

The `CI` workflow runs on non-data-only pushes to `main` and non-data-only pull requests targeting
`main`, with read-only repository permissions. It uses commit-pinned checkout, Python setup, and uv
setup actions, then runs:

- pytest;
- Ruff lint and format checks;
- strict mypy;
- Complexipy with a per-function ceiling of 15 and output sorted by descending complexity;
- Deptry;
- Import Linter architecture contracts.

All commands use the frozen lockfile.

## Pull request and dependency policy

The `Commit checks` workflow validates pull request titles and head commits against Conventional
Commits and requires each pull request to contain exactly one commit. It reruns when the title is
edited, checks the latest commit on non-data-only pushes to `main`, and skips Dependabot pull
requests. The workflow installs its pinned commitlint packages temporarily and does not add a Node
project to the repository.

Dependabot checks the `uv` and GitHub Actions ecosystems weekly. Minor and patch version updates are
grouped, major updates remain separate, and security updates use a separate group for each
ecosystem. Data-only pushes are excluded from the commit checks because generated commits are
owned by the Update data workflow.

## Dataset updates

The `Update data` workflow runs at `00:17`, `06:17`, `12:17`, and `18:17` UTC and supports manual
dispatch. A single concurrency group prevents overlapping Update Runs; an active run is not
cancelled when another is queued.

The job has only `contents: write` permission and runs:

```shell
uv run --frozen github-trending --verbose
```

Verbose progress appears in the Actions log. The final report is appended to
`GITHUB_STEP_SUMMARY`.

## Exit and commit behavior

| Exit code | Meaning | Workflow behavior |
| --- | --- | --- |
| `0` | Every Feed was complete. | Commit changed data, if any, and succeed. |
| `2` | At least one Snapshot was degraded or one Feed stayed stale. | Commit every successful change, then fail the job for notification. |
| `1` | Fatal configuration, filesystem, or persisted-data error. | Stop before the commit step. |

Generated commits use the `github-actions[bot]` identity and a UTC timestamp. The commit step stages
only `data`; when no generated file changed, it exits without creating a commit. Partial publication
is intentional and documented in
[PDR-0003](../product/decisions/0003-partial-publication-and-stale-feeds.md).

## Repository prerequisites

- The workflow must run from the branch that owns the canonical data paths.
- Repository rules must permit the built-in `GITHUB_TOKEN` to push generated commits.
- Standard GitHub Actions web or email notifications should be enabled when degraded scheduled
  runs require operator attention.

A manual rerun is the recovery mechanism for transient failures. It updates the same UTC Daily
Rollup and counts another successful observation in `appearances`; it does not backfill older dates.

## Local operation

Generate into the default `data` directory or an isolated path:

```shell
uv run --frozen github-trending --verbose
uv run --frozen github-trending --verbose --data-dir /tmp/github-trending-data
```

The static delivery architecture and its operational trade-offs are recorded in
[ADR-0001](../adr/0001-static-dataset-via-github-actions.md).
