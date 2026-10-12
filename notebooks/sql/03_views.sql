-- =============================================================================
-- Phase 2 & 3 Analytical Views: Official Rubric KPIs
-- Granularity: Strictly AGEB Urbana (cvegeo)
-- =============================================================================

DROP MATERIALIZED VIEW IF EXISTS mv_analytical_ageb_kpis CASCADE;

CREATE MATERIALIZED VIEW mv_analytical_ageb_kpis AS
WITH agg_crime AS (
    SELECT 
        cvegeo,
        count(*) AS total_crimes,
        count(*) FILTER (WHERE date_id IS NOT NULL) AS crimes_with_timestamp
    FROM fact_crime_events
    GROUP BY cvegeo
),
agg_econ AS (
    SELECT 
        e.cvegeo,
        count(*) AS total_businesses,
        count(*) FILTER (WHERE a.categoria = 'Retail') AS total_retail,
        count(*) FILTER (WHERE a.categoria = 'Services') AS total_services,
        mode() WITHIN GROUP (ORDER BY a.sector_scian) AS dominant_sector
    FROM fact_economic_units e
    JOIN dim_economic_activity a ON e.activity_id = a.activity_id
    GROUP BY e.cvegeo
)
SELECT 
    g.cvegeo,
    g.cve_mun,
    g.nom_mun,
    g.area_km2,
    g.geom,

    -- 1. Demographic KPIs (Section 05 Rubric)
    COALESCE(d.total_population, 0) AS total_population,
    ROUND((COALESCE(d.total_population, 0) / g.area_km2)::NUMERIC, 2) AS population_density,
    ROUND(
        CASE 
            WHEN COALESCE(d.total_population, 0) > 0 
            THEN (d.economically_active_population::NUMERIC / d.total_population::NUMERIC) 
            ELSE 0 
        END, 4
    ) AS pea_rate,
    ROUND(
        CASE 
            WHEN COALESCE(d.total_population, 0) > 0 
            THEN (d.working_age_population::NUMERIC / d.total_population::NUMERIC) 
            ELSE 0 
        END, 4
    ) AS working_age_share,

    -- 2. Economic KPIs (Section 05 Rubric)
    COALESCE(e.total_businesses, 0) AS total_businesses,
    ROUND((COALESCE(e.total_businesses, 0) / g.area_km2)::NUMERIC, 2) AS business_density,
    ROUND(
        CASE 
            WHEN COALESCE(d.total_population, 0) > 0 
            THEN (COALESCE(e.total_businesses, 0)::NUMERIC / d.total_population::NUMERIC) * 1000.0 
            ELSE 0 
        END, 2
    ) AS businesses_per_1000_inhabitants,
    ROUND((COALESCE(e.total_retail, 0) / g.area_km2)::NUMERIC, 2) AS retail_density,
    ROUND((COALESCE(e.total_services, 0) / g.area_km2)::NUMERIC, 2) AS service_density,
    COALESCE(e.dominant_sector, 'None') AS dominant_economic_sector,

    -- 3. Public Safety KPIs (Section 05 Rubric)
    COALESCE(c.total_crimes, 0) AS total_crime_incidents,
    ROUND((COALESCE(c.total_crimes, 0) / g.area_km2)::NUMERIC, 2) AS crime_density,
    ROUND(
        CASE 
            WHEN COALESCE(d.total_population, 0) > 0 
            THEN (COALESCE(c.total_crimes, 0)::NUMERIC / d.total_population::NUMERIC) * 1000.0 
            ELSE 0 
        END, 2
    ) AS crime_rate_per_1000_inhabitants,
    ROUND(
        CASE 
            WHEN COALESCE(e.total_businesses, 0) > 0 
            THEN (COALESCE(c.total_crimes, 0)::NUMERIC / e.total_businesses::NUMERIC) 
            ELSE 0 
        END, 4
    ) AS crime_per_business_ratio

FROM dim_geography g
LEFT JOIN fact_census_demographics d ON g.cvegeo = d.cvegeo
LEFT JOIN agg_econ e ON g.cvegeo = e.cvegeo
LEFT JOIN agg_crime c ON g.cvegeo = c.cvegeo;

CREATE UNIQUE INDEX idx_mv_analytical_cvegeo ON mv_analytical_ageb_kpis(cvegeo);
CREATE INDEX idx_mv_analytical_geom ON mv_analytical_ageb_kpis USING GIST(geom);
