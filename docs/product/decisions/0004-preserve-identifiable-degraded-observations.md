# Preserve identifiable degraded observations

Status: Accepted
Date: 2026-09-26

Every source row with a valid Repository Identity is retained even when required metrics are
missing, malformed, or negative. Affected metrics become `null` and structured Snapshot Issues
preserve source details; only unidentifiable rows are skipped, and an absent optional Period Metric
is not degradation.

## Consequences

Consumers keep complete ranking membership and original ranks but must handle nullable metrics.
Numeric fields never mix strings and integers; malformed source text is available through
`rawValue` instead.
