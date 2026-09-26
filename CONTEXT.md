# GitHub Trending Dataset

This context describes the vocabulary of observed GitHub Trending rankings and their history.

## Language

**Feed**:
A single GitHub Trending ranking for one language filter and one period.
_Avoid_: Endpoint, channel

**Observation**:
One repository's appearance at a particular rank in a feed at a point in time.
_Avoid_: Record, event

**Repository Identity**:
The case-insensitive owner and repository name that relates observations of the same repository.
_Avoid_: URL, GUID

**Period Metric**:
The number of stars GitHub reports for a repository within a feed's period. It is optional because
GitHub may omit it from an otherwise valid observation.
_Avoid_: Total stars, growth rate

**Snapshot**:
The ordered observations obtained from one successful reading of a feed.
_Avoid_: Current archive, batch

**Snapshot Issue**:
A structured description of an unexpectedly missing or malformed field at its original source rank.
_Avoid_: Feed failure, validation error

**Current Dataset**:
The latest successfully published snapshot of each feed.
_Avoid_: Cache, latest archive

**Daily Rollup**:
The unique repositories observed in one feed during a UTC day, together with their latest values and daily rank summary.
_Avoid_: Daily snapshot, cumulative current

**Archive**:
The date-addressed collection of daily rollups.
_Avoid_: Backup, snapshot history

**Degraded Snapshot**:
A snapshot containing every identifiable observation from a recognized ranking while identifying
unexpectedly missing or malformed fields. An absent optional period metric does not cause
degradation; only source positions without repository identity are skipped.
_Avoid_: Partial failure, incomplete feed

**Stale Feed**:
A feed whose latest read failed entirely, leaving its previously published snapshot unchanged.
_Avoid_: Empty feed, degraded snapshot

**Update Run**:
One attempt to read every configured feed and publish each snapshot that was obtained successfully.
_Avoid_: Snapshot, deployment
