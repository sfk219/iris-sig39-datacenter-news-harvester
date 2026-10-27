# IRIS-SIG-39 — DataCenter-Insider Newsfeed Harvester

**Python | RSS/Atom | PostgreSQL 16 | PostGIS 3.4 | EPSG:25832**

Independent engineering-assignment implementation for DACH colocation news, data-center cooling, and Germany's Energy Efficiency Act compliance signals.

## Objective

Collect public RSS/Atom feed entries from `https://www.datacenter-insider.de/rss.xml`, preserve stable source identity, classify relevant signals, retain demonstrable geographic context, and load normalized records idempotently into `iris_staging.signal_ingest`.

## Processing

`RSS/Atom → HTTPS retry/timeout → XML parsing → canonical URLs → topic/DACH filter → geolocation quality → JSONL → PostgreSQL upsert`

Unknown geography is not silently assigned a point. The demo schema is independent of IRIS production. City coordinates are approximate centroids and not facilities.

## Complete offline deliverable

The complete reviewer ZIP contains the Python harvester, SQL migrations and validations, tests and fixture, Docker Compose configuration, example JSONL, quality report, and detailed technical PDF. It is provided separately with the submission email to ensure offline review.

## Review and verification

Source development package has a `README.md` with local setup and test commands. Syntax validation was performed; full pytest, live RSS availability and Docker-backed database run require the appropriate execution environment and are not claimed to have passed.

## Author

Samra Faisal Khan · Technical evaluation task `IRIS-SIG-39`.
