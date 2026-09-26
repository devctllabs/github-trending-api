# Product Documentation

These documents describe the currently implemented behavior of the GitHub Trending Dataset. They
are authoritative for product rules; decision records preserve the reasons behind selected rules.

## Capabilities

- [Dataset behavior](dataset.md)
- [JSON and RSS data contract](data-contract.md)

## Product decisions

- [PDR-0001: Current snapshots and UTC daily rollups](decisions/0001-current-and-utc-daily-rollups.md)
- [PDR-0002: Publish JSON and RSS](decisions/0002-publish-json-and-rss.md)
- [PDR-0003: Partial publication and stale feeds](decisions/0003-partial-publication-and-stale-feeds.md)
- [PDR-0004: Preserve identifiable degraded observations](decisions/0004-preserve-identifiable-degraded-observations.md)
- [PDR-0005: Stable latest-only schema versioning](decisions/0005-stable-latest-only-schema-versioning.md)

Architecture and operational concerns are documented in the [architecture overview](../architecture/overview.md)
and [deployment guide](../architecture/deployment.md).
