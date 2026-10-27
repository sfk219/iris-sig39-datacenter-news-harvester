-- Execute against a populated demonstration database.
SELECT COUNT(*) AS total_records, COUNT(DISTINCT (source_name, source_id)) AS unique_source_records FROM iris_staging.signal_ingest;
SELECT signal_type, COUNT(*) AS records FROM iris_staging.signal_ingest GROUP BY signal_type ORDER BY records DESC;
SELECT country_code, geo_status, COUNT(*) AS records FROM iris_staging.signal_ingest GROUP BY country_code, geo_status ORDER BY country_code,geo_status;
SELECT COUNT(*) AS invalid_srid FROM iris_staging.signal_ingest WHERE geom IS NOT NULL AND ST_SRID(geom)<>25832;
SELECT COUNT(*) AS invalid_missing_geom FROM iris_staging.signal_ingest WHERE (geo_status='resolved' AND geom IS NULL) OR (geo_status<>'resolved' AND geom IS NOT NULL);
SELECT COUNT(*) AS invalid_coordinates FROM iris_staging.signal_ingest WHERE geom IS NOT NULL AND NOT ST_IsValid(geom);
SELECT source_url,title,published_at,geo_status FROM iris_staging.signal_ingest ORDER BY last_seen_at DESC LIMIT 20;
