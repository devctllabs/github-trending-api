# Dataset Behavior

The product is a static, read-only dataset derived from GitHub Trending. Each Feed is identified by
one period and one language filter.

## Supported feeds

The periods are `daily`, `weekly`, and `monthly`. The language filters are `all`, `python`, `rust`,
`go`, `javascript`, and `typescript`, producing 18 independent feeds per Update Run.

GitHub is the source of ranking membership, order, repository metadata, total stars, forks, and the
optional Period Metric. The source rank is preserved even when another source position is skipped.
An explicit GitHub empty-state marker produces a valid empty Snapshot; an unrecognized empty page
is a Feed failure rather than an empty ranking.

## Current Dataset and Archive

The Current Dataset holds the latest successfully published Snapshot for each Feed. A Degraded
Snapshot is still publishable and therefore replaces the previous current document.

The Archive is organized by UTC date. Each date contains one Daily Rollup for every Feed observed
on that date. An Update Run changes only its current UTC date; normal operation never rewrites past
dates and does not backfill dates before the first run.

A Daily Rollup:

- identifies repositories by case-insensitive `owner/name`;
- keeps each repository once, using its latest casing, metadata, and metrics, including latest
  `null` values;
- stores its best and latest rank for the day;
- stores first-seen and last-seen timestamps;
- increments appearances for every successful observation, including manual recovery runs;
- orders repositories by best rank, first-seen time, and identity.

This separation is intentional; see
[PDR-0001](decisions/0001-current-and-utc-daily-rollups.md).

## Completeness and failures

A Snapshot is complete when every unexpected field problem is absent. Missing descriptions,
programming languages, and Period Metrics are allowed and do not cause degradation. Zero is a
valid value for every metric.

When an identifiable source row has a missing required metric, a malformed number, or a negative
metric, the repository remains in the Snapshot. The affected field is `null`, a Snapshot Issue
records the problem, and the Snapshot is degraded. Only a row without a valid Repository Identity
is skipped. See [PDR-0004](decisions/0004-preserve-identifiable-degraded-observations.md).

A network, HTTP, or whole-page parsing failure makes that Feed stale: its current and archive files
remain unchanged. Other feeds continue and are published. The Update Run is degraded when any Feed
is stale or any published Snapshot is degraded. See
[PDR-0003](decisions/0003-partial-publication-and-stale-feeds.md).

## Publication formats

Every current Snapshot and Daily Rollup is published in JSON and RSS 2.0. Both representations are
generated from the same observation data. JSON is also the persisted representation used to merge
later observations into the current UTC day's Daily Rollup.

The exact paths, fields, nullability, issue codes, and compatibility rules are defined by the
[data contract](data-contract.md). The dual-format decision is recorded in
[PDR-0002](decisions/0002-publish-json-and-rss.md).
