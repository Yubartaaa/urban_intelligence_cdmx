-- =============================================================================
-- Warehouse KPI Validation & Relationship Analysis Suite
-- Validates statistical bounds and explores relationships between crime,
-- population, and economic density across all 2,431 CDMX urban AGEBs.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TEST 1: Data Integrity & Boundary Validation
-- -----------------------------------------------------------------------------
SELECT 
    count(*) FILTER (WHERE area_km2 <= 0 OR total_population < 0) AS invalid_area_pop_count,
    count(*) FILTER (WHERE pea_rate < 0 OR pea_rate > 1.0) AS invalid_pea_rate_count,
    count(*) FILTER (WHERE working_age_share < 0 OR working_age_share > 1.0) AS invalid_working_age_count
FROM mv_analytical_ageb_kpis;


-- -----------------------------------------------------------------------------
-- ANALYSIS 1: Option B (Table-Wide) - Crime Relative to Business Activity
-- Evaluates crime victimization per commercial establishment across all AGEBs.
-- -----------------------------------------------------------------------------
SELECT 
    cvegeo, 
    nom_mun,
    total_population, 
    total_businesses, 
    total_crime_incidents, 
    crime_per_business_ratio,
    crime_density,
    business_density
FROM mv_analytical_ageb_kpis
ORDER BY crime_per_business_ratio DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- ANALYSIS 2: Spatial Density Comparison (Crimes / km2 vs. Businesses / km2)
-- Area-normalized density removes population denominator distortions and
-- reveals the city's primary high-intensity crime and commercial corridors.
-- -----------------------------------------------------------------------------
SELECT 
    cvegeo, 
    nom_mun,
    total_population, 
    total_businesses, 
    total_crime_incidents, 
    crime_density,
    business_density,
    population_density
FROM mv_analytical_ageb_kpis
ORDER BY crime_density DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- ANALYSIS 3: Statistical Relationship Test (Full-Table Correlation Matrix)
-- Directly addresses research question: What is the relationship between
-- crime, population density, and economic density across CDMX?
-- -----------------------------------------------------------------------------
SELECT 
    ROUND(corr(crime_density, business_density)::NUMERIC, 4) AS corr_crime_vs_business_density,
    ROUND(corr(crime_density, population_density)::NUMERIC, 4) AS corr_crime_vs_pop_density,
    ROUND(corr(total_crime_incidents, total_businesses)::NUMERIC, 4) AS corr_crimes_vs_businesses,
    ROUND(corr(total_crime_incidents, total_population)::NUMERIC, 4) AS corr_crimes_vs_population
FROM mv_analytical_ageb_kpis;


-- -----------------------------------------------------------------------------
-- ANALYSIS 4: Population-Thresholded Residential Crime Rate
-- Evaluates residential crime rate for AGEBs with residential baseline (>= 500 hab)
-- to contrast residential risk against commercial/transit hotspots.
-- -----------------------------------------------------------------------------
SELECT 
    cvegeo, 
    nom_mun,
    total_population, 
    total_businesses,
    total_crime_incidents, 
    crime_rate_per_1000_inhabitants,
    crime_density
FROM mv_analytical_ageb_kpis
WHERE total_population >= 500
ORDER BY crime_rate_per_1000_inhabitants DESC
LIMIT 10;

