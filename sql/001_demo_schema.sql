-- DEMONSTRATION SCHEMA ONLY. Adjust the adapter before writing to an existing IRIS table.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS iris_staging;
CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    summary TEXT,
    country_code CHAR(2),
    location_name TEXT,
    geo_status TEXT NOT NULL CHECK (geo_status IN ('resolved','ambiguous','unresolved')),
    location_note TEXT,
    geom geometry(Point,25832),
    raw_record JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_signal_source UNIQUE (source_name,source_id),
    CONSTRAINT ck_country_code CHECK (country_code IS NULL OR country_code IN ('DE','AT','CH')),
    CONSTRAINT ck_geom_resolution CHECK ((geo_status='resolved' AND geom IS NOT NULL) OR (geo_status<>'resolved' AND geom IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_signal_ingest_published ON iris_staging.signal_ingest (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_ingest_geom ON iris_staging.signal_ingest USING gist(geom);
