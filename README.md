# IRIS-SIG-39 · DataCenter-Insider Newsfeed Harvester

**Candidate engineering evaluation** · Python 3.12 · RSS/Atom · PostgreSQL 16 · PostGIS 3.4 · EPSG:25832

A source-traceable signal ingestion adapter that monitors the DataCenter-Insider public newsfeed for DACH (Germany/Austria/Switzerland) **colocation announcements**, **cooling innovations** and **energy-efficiency compliance**.

> **Scope note:** The database schema supplied here is an independent demonstration schema. It is not the private production IRIS DDL. Synthetic fixtures are not publisher articles.

## Architecture

```text
https://www.datacenter-insider.de/rss.xml
      |
 HTTPS fetch / timeout / retries / max byte limit
      |
 RSS or Atom parsing (feedparser)
      |
 canonical link + stable SHA-256 source ID
      |
 topic classification + DACH evidence gate
      |
 city evidence / geographic uncertainty classification
      |
 +--> JSONL + JSON quality report (--dry-run)
 |
 +--> PostgreSQL 16 / PostGIS 3.4
        iris_staging.signal_ingest
        unique(source_name, source_id)
        ON CONFLICT DO UPDATE
        ST_Transform(..., EPSG:25832)
```

## Quick start: offline, without database credentials

```bash
python -m venv .venv
# activate virtualenv on your platform
python -m pip install -r requirements.txt
python -m pytest -v
python harvester.py --fixture tests/fixtures_rss.xml --dry-run
```

Inspect `run/output.jsonl` and `run/quality_report.json`. The test feed is **synthetic** and includes cases for a relevant German colocation item, Austrian cooling item, EnEfG compliance, ambiguous multi-city location, an irrelevant item, a duplicate tracking URL, and a malformed URL.

## PostgreSQL demonstration

```bash
cp .env.example .env
docker compose up -d --wait
python harvester.py --fixture tests/fixtures_rss.xml
python harvester.py --fixture tests/fixtures_rss.xml
docker compose exec db psql -U iris -d iris_demo -c "SELECT COUNT(*) FROM iris_staging.signal_ingest;"
```

On a **fresh** database the synthetic fixture is expected to produce four unique records after either the first or second run. First and second runs use the same unique source keys. Docker creates the schema at first initialization of the named volume. Use demo credentials only locally.

## Live feed

```bash
python harvester.py --dry-run
```

The publisher may change feed structure, block access, or return no entries. This implementation performs recurring snapshots rather than promising historical backfill or unsupported pagination.

## Configuration

Copy `.env.example` to a local, ignored `.env`. Settings: `FEED_URL`, `DATABASE_URL`, `HTTP_TIMEOUT`, `HTTP_RETRIES`, `USER_AGENT`, `MAX_FEED_BYTES`, and optional `FIXTURE_FILE`. Do not commit real credentials.

## Mapping and quality rules

| Source or derived value | Target | Policy |
| --- | --- | --- |
| Canonical permalink | `source_url` | HTTP(S), publisher domain, strip marketing tracking parameters |
| SHA-256 of canonical permalink | `source_id` | Stable unique key with source name |
| Upstream title / description | `title`, `summary` | Normalize whitespace and HTML entities |
| RSS/Atom published or updated date | `published_at` | Convert to UTC; invalid/missing becomes NULL |
| Relevant keyword matches | `signal_type` | Deterministic colocation, cooling, energy_compliance |
| Explicit place/country evidence | `country_code` | DE / AT / CH; unknown geography excluded |
| City evidence | `location_name`, `geo_status` | `resolved`, `ambiguous`, or `unresolved` |
| City longitude/latitude | `geom` | Only resolved city centroid; transform WGS84 to EPSG:25832 |
| GUID and raw source date | `raw_record` | Traceability / diagnostics |
| Ingestion audit | `first_seen_at`, `last_seen_at` | Retain insertion date; update last-seen on upsert |

**Important geospatial caveat:** approximate city-centroid points are not facility coordinates, and an article discussing a city is not proof of a facility at that location. The bundled city list is deliberately restricted. Country-only or ambiguous locations have NULL geometry. UTM 32N is assigned by the task; zone 33N would sometimes be more appropriate in eastern Austria.

## Tests and validation

`pytest -v` checks representative fixture processing, stable identity after dropping tracking query strings, DACH evidence, safe null geometry, malformed feed handling, and UTC date parsing. GitHub Actions runs tests and a synthetic smoke test automatically.

For SQL validation after the Docker demo:

```sql
SELECT COUNT(*) AS rows, COUNT(DISTINCT (source_name, source_id)) AS unique_keys
FROM iris_staging.signal_ingest;

SELECT geo_status, COUNT(*) FROM iris_staging.signal_ingest GROUP BY geo_status;

SELECT COUNT(*) FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL AND ST_SRID(geom) <> 25832;
```

## Operational safeguards and limitations

- HTTP timeout, retry for retryable status codes, maximum feed size, explicit failure logs.
- Invalid URLs and unsupported publisher hosts are rejected.
- In-feed duplicates are suppressed; database records are upserted, not duplicated.
- Missing publication dates remain NULL; missing titles are rejected.
- Feed snapshots may omit older news, and there is no assumed pagination API.
- Rule-based relevance has false-positive and false-negative risk.
- City detection and precision are conservative but not equivalent to a trusted geocoder.
- No claim is made that live feed ingestion or a production database integration has been exercised.

## Offline handoff

A reviewer ZIP containing the **complete code, more extensive tests, documentation, technical PDF, sample outputs and validation SQL** is supplied as an attachment to the submission email. The ZIP is the self-contained fallback if GitHub is unavailable.

**Author:** Samra Faisal Khan · Assignment IRIS-SIG-39
