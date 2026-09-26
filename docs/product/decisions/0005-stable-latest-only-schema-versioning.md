# Stable latest-only schema versioning

Status: Accepted
Date: 2026-09-26

Schema version 1 is a stable public JSON and RSS contract. Compatible additive fields may be added
within v1, breaking changes require a new schema version, and canonical paths publish only the
latest version rather than maintaining parallel historical schemas.

## Consequences

Consumers must inspect `schemaVersion` and ignore unknown additive JSON fields and RSS extensions.
A consumer that cannot adopt a future breaking version must preserve its own v1 data or adapter.
