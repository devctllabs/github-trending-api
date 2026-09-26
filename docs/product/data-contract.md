# JSON and RSS Data Contract

The canonical files are UTF-8, newline-terminated JSON and RSS 2.0 documents. JSON field names use
camelCase, timestamps use RFC 3339 UTC, collections are arrays, and nullable scalar values are
explicitly represented as `null`.

## Paths

```text
data/current/{period}/{language}.json
data/current/{period}/{language}.xml
data/archive/YYYY/MM/DD/{period}/{language}.json
data/archive/YYYY/MM/DD/{period}/{language}.xml
```

`period` is `daily`, `weekly`, or `monthly`. `language` is `all`, `python`, `rust`, `go`,
`javascript`, or `typescript`.

## Snapshot JSON

| Field | Type | Meaning |
| --- | --- | --- |
| `schemaVersion` | integer | Contract version; currently `1`. |
| `kind` | string | Always `snapshot`. |
| `period` | string | Feed period. |
| `language` | string | Feed language filter. |
| `sourceUrl` | string | Canonical GitHub Trending URL. |
| `observedAt` | timestamp | Time the source response was parsed. |
| `status` | string | `complete` or `degraded`. |
| `issues` | array | Structured Snapshot Issues. |
| `items` | array | Ranked repository observations. |

A Snapshot item contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `rank` | integer | Original one-based source position. |
| `fullName` | string | Repository Identity as `owner/name`. |
| `url` | string | Canonical repository URL. |
| `description` | string or null | Normalized source description. |
| `programmingLanguage` | string or null | Source programming language. |
| `stars` | nonnegative integer or null | Total stars; null is accompanied by an issue. |
| `forks` | nonnegative integer or null | Total forks; null is accompanied by an issue. |
| `starsInPeriod` | nonnegative integer or null | Period Metric. Absence is valid; malformed values produce an issue. |

## Daily Rollup JSON

A Daily Rollup uses the common `schemaVersion`, `period`, `language`, and `sourceUrl` fields. Its
remaining top-level fields are:

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | string | Always `daily-rollup`. |
| `date` | date | Owning UTC date. |
| `updatedAt` | timestamp | Time of the latest merged Snapshot. |
| `latestStatus` | string | Status of the latest merged Snapshot. |
| `latestIssues` | array | Issues from the latest merged Snapshot. |
| `items` | array | Unique repositories observed during the UTC date. |

Rollup items replace `rank` with `bestRank`, `latestRank`, `firstSeenAt`, `lastSeenAt`, and
`appearances`. Their repository metadata and metrics are the latest observed values. A later
`null` replaces an earlier numeric metric rather than carrying old data forward.

## Snapshot Issues

Each issue contains `code`, original source `rank`, `field`, and `rawValue`. `rawValue` is the
source text when available and otherwise `null`.

| Code | Meaning |
| --- | --- |
| `invalid_repository_link` | The row has no valid `/owner/repository` identity and is skipped. |
| `missing_field` | A required metric is absent. |
| `invalid_integer` | A metric was present but could not be parsed as an integer. |
| `out_of_range` | A metric was a negative integer. |

One retained item may produce multiple issues. A missing `starsInPeriod` does not produce an issue;
if period text is present but invalid or negative, it does.

## RSS 2.0

RSS documents use standard channel and item elements plus extensions in the
`urn:github-trending:v1` namespace, conventionally prefixed `ght`. Repository URLs are permanent
item GUIDs.

Snapshot channels expose kind, Feed, timestamp, status, and issues. Rollup channels expose kind,
date, Feed, update timestamp, latest status, and latest issues. Repository items expose the same
metrics as JSON plus rank or rollup summary fields. A JSON `null` metric is an empty extension
element. Issue attributes omit `rawValue` when no source text exists.

## Compatibility

Schema version 1 is stable. Additive fields may appear without changing `schemaVersion`; consumers
must ignore unknown JSON fields and unknown RSS extension elements. A breaking change requires a
new schema version. Canonical paths always serve only the latest schema version, so prior versions
are not published in parallel. See
[PDR-0005](decisions/0005-stable-latest-only-schema-versioning.md).
