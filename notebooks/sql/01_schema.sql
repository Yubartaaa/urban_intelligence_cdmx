-- =============================================================================
-- Mexico City Urban Intelligence Geospatial Data Warehouse
-- Dimensional Model DDL (PostgreSQL 14+ with PostGIS)
-- Target Analytical Grain: AGEB Urbana (EPSG:6372 Metric Projection)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS fact_crime_events CASCADE;
DROP TABLE IF EXISTS fact_economic_units CASCADE;
DROP TABLE IF EXISTS fact_census_demographics CASCADE;
DROP TABLE IF EXISTS dim_geography CASCADE;
DROP TABLE IF EXISTS dim_crime_type CASCADE;
DROP TABLE IF EXISTS dim_economic_activity CASCADE;
DROP TABLE IF EXISTS dim_time CASCADE;

-- 1. DIMENSION TABLES
CREATE TABLE dim_geography (
    cvegeo VARCHAR(13) PRIMARY KEY,
    cve_ent VARCHAR(2) NOT NULL DEFAULT '09',
    cve_mun VARCHAR(3) NOT NULL,
    cve_loc VARCHAR(4) NOT NULL,
    cve_ageb VARCHAR(4) NOT NULL,
    nom_mun VARCHAR(100),
    area_km2 NUMERIC(10, 4) NOT NULL CHECK (area_km2 > 0),
    geom GEOMETRY(MultiPolygon, 6372) NOT NULL
);
CREATE INDEX idx_dim_geography_geom ON dim_geography USING GIST(geom);
CREATE INDEX idx_dim_geography_mun ON dim_geography(cve_mun);

CREATE TABLE dim_crime_type (
    crime_type_id SERIAL PRIMARY KEY,
    categoria_delito VARCHAR(150) NOT NULL,
    delito VARCHAR(255) NOT NULL,
    CONSTRAINT uq_crime_category UNIQUE (categoria_delito, delito)
);
CREATE INDEX idx_dim_crime_cat ON dim_crime_type(categoria_delito);

CREATE TABLE dim_economic_activity (
    activity_id SERIAL PRIMARY KEY,
    codigo_act VARCHAR(10) NOT NULL UNIQUE,
    nombre_act TEXT NOT NULL,
    sector_scian VARCHAR(2) NOT NULL,
    categoria VARCHAR(50) NOT NULL CHECK (categoria IN ('Retail', 'Services', 'Manufacturing', 'Other'))
);
CREATE INDEX idx_dim_econ_sector ON dim_economic_activity(sector_scian);
CREATE INDEX idx_dim_econ_cat ON dim_economic_activity(categoria);

CREATE TABLE dim_time (
    date_id DATE PRIMARY KEY,
    anio INT NOT NULL,
    mes INT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    dia INT NOT NULL CHECK (dia BETWEEN 1 AND 31),
    dia_semana INT NOT NULL,
    trimestre INT NOT NULL CHECK (trimestre BETWEEN 1 AND 4)
);

-- 2. FACT TABLES
CREATE TABLE fact_census_demographics (
    cvegeo VARCHAR(13) PRIMARY KEY REFERENCES dim_geography(cvegeo) ON DELETE CASCADE,
    total_population INT NOT NULL DEFAULT 0 CHECK (total_population >= 0),
    female_population INT DEFAULT 0,
    male_population INT DEFAULT 0,
    working_age_population INT DEFAULT 0 CHECK (working_age_population >= 0),
    economically_active_population INT DEFAULT 0 CHECK (economically_active_population >= 0),
    employed_population INT DEFAULT 0,
    total_dwellings INT DEFAULT 0
);

CREATE TABLE fact_crime_events (
    event_id BIGSERIAL PRIMARY KEY,
    cvegeo VARCHAR(13) NOT NULL REFERENCES dim_geography(cvegeo) ON DELETE CASCADE,
    crime_type_id INT NOT NULL REFERENCES dim_crime_type(crime_type_id),
    date_id DATE REFERENCES dim_time(date_id),
    hora TIME,
    latitud NUMERIC(10, 7) NOT NULL,
    longitud NUMERIC(10, 7) NOT NULL,
    geom GEOMETRY(Point, 6372) NOT NULL
);
CREATE INDEX idx_fact_crime_cvegeo ON fact_crime_events(cvegeo);
CREATE INDEX idx_fact_crime_geom ON fact_crime_events USING GIST(geom);

CREATE TABLE fact_economic_units (
    unit_id BIGSERIAL PRIMARY KEY,
    id_denue VARCHAR(50) NOT NULL,
    cvegeo VARCHAR(13) NOT NULL REFERENCES dim_geography(cvegeo) ON DELETE CASCADE,
    activity_id INT NOT NULL REFERENCES dim_economic_activity(activity_id),
    estrato_ocupacion VARCHAR(50),
    latitud NUMERIC(10, 7) NOT NULL,
    longitud NUMERIC(10, 7) NOT NULL,
    geom GEOMETRY(Point, 6372) NOT NULL
);
CREATE INDEX idx_fact_econ_cvegeo ON fact_economic_units(cvegeo);
CREATE INDEX idx_fact_econ_geom ON fact_economic_units USING GIST(geom);