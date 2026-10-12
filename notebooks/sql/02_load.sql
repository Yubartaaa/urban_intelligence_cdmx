-- =============================================================================
-- Verification & Data Integrity Queries Post-Ingestion
-- =============================================================================

SELECT 'dim_geography' AS table_name, count(*) AS count FROM dim_geography
UNION ALL
SELECT 'dim_crime_type', count(*) FROM dim_crime_type
UNION ALL
SELECT 'dim_economic_activity', count(*) FROM dim_economic_activity
UNION ALL
SELECT 'dim_time', count(*) FROM dim_time;

SELECT 'fact_census_demographics' AS table_name, count(*) AS count FROM fact_census_demographics
UNION ALL
SELECT 'fact_crime_events', count(*) FROM fact_crime_events
UNION ALL
SELECT 'fact_economic_units', count(*) FROM fact_economic_units;

-- Integrity check: Facts without Geography
SELECT count(*) AS orphan_demographic_records
FROM fact_census_demographics f
LEFT JOIN dim_geography g ON f.cvegeo = g.cvegeo
WHERE g.cvegeo IS NULL;
