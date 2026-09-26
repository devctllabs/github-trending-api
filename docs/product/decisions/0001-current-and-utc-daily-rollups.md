# Current snapshots and UTC daily rollups

Status: Accepted
Date: 2026-09-26

The Current Dataset is kept separately from date-addressed UTC Daily Rollups. Each Update Run
replaces current files and merges observations into the current UTC date instead of moving the
previous current tree into an archive, giving consumers one stable latest path and one compact path
per Feed and day.

## Consequences

The current UTC date changes during the day, past dates remain unchanged in normal operation, and
manual reruns increase `appearances`. The Archive records daily aggregates rather than every raw
run snapshot.
