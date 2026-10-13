# Urban Intelligence CDMX: Geospatial Data Warehouse & Spatial Analytics

This repository hosts the data engineering pipeline, containerized PostGIS dimensional data warehouse, and spatial econometric modeling engine for Mexico City (CDMX, 2020). The platform integrates demographic, commercial, and criminal records at the urban Basic Geostatistical Area (**AGEB**) grain to analyze spatial relationships between economic density and urban crime.

---

## 1. Summary of Data Sources

The project integrates four primary open data sources at the urban AGEB grain (EPSG:6372):

| Layer | Source & Origin | Target Raw File / Path | Format & CRS | Analytical Role |
| :--- | :--- | :--- | :--- | :--- |
| **Geographic** | **INEGI Marco Geoestadístico 2020**<br>[INEGI Portal](https://www.inegi.org.mx/programas/mg/#mapas) | `data/raw/geographic/2020_1_09_A/`<br>`2020_1_09_MUN/`<br>`2020_1_09_ENT/` | Shapefiles (`.shp`, `.dbf`, `.shx`, `.prj`) | Primary territorial grain (2,431 Urban AGEBs), municipal boundaries (*alcaldías*), and state geometry. Reprojected to EPSG:6372. |
| **Demographic** | **INEGI Censo de Población y Vivienda 2020**<br>[INEGI Microdatos](https://www.inegi.org.mx/programas/ccpv/2020/#microdatos) | `data/raw/population_dataset.csv` | CSV | Decennial complete census count: Total Population (`POBTOT`), Economically Active Population (`PEA`), Working-Age bracket (`P_15A64`). |
| **Economic** | **INEGI DENUE 2020 CDMX**<br>[INEGI Descarga Masiva](https://www.inegi.org.mx/app/descarga/) | `data/raw/economic/denue_09_csv/`<br>`data/raw/economic/denue_09_shp/` | CSV / Shapefile | Point-level active business directory (472,617 units). Categorized by SCIAN codes (Retail, Services, Manufacturing, Other). |
| **Public Safety** | **FGJ-CDMX Carpetas de Investigación**<br>[Portal Datos Abiertos CDMX](https://datos.cdmx.gob.mx) | `data/raw/crime_dataset.csv` | CSV | Geocoded incident-level criminal investigation files from 2020 (196,990 events) with legal offense categories and timestamps. |

---

## 2. Pipeline Execution

The complete pipeline can be run from start to finish with a single command via `main.py`.

### Prerequisites

1. **Dataset Download**: You can download the exact datasets for this project in [this Google Drive](https://drive.google.com/drive/folders/1Znf9zC0lYqbvMdEaCc87XDNolmC4SU0S?usp=share_link).
2. **Docker & Docker Compose**: Ensure Docker is installed and running to host the PostgreSQL 15 + PostGIS 3.3 container.
3. **Python Environment**: Python 3.10+ with required spatial and analytical packages installed:

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

3. **Database Container**:
```bash
docker compose up -d
```

---

### Single-Command Pipeline Run

To execute the entire end-to-end pipeline (ETL, Spatial Joins, Warehouse Ingestion, Materialized Views, and Spatial Econometrics):

```bash
python main.py
```

### Pipeline Execution Stages

When executed, `main.py` orchestrates the following five sequential phases:

```text
[PHASE 1] SPATIAL & TABULAR ETL
  ├── 1.1 Ingests & repairs AGEB boundaries (EPSG:6372 metric area)     -> data/processed/geography_ageb.parquet
  ├── 1.2 Filters Censo 2020 records strictly to urban AGEBs (MZA=0000)  -> data/processed/demographics_ageb.parquet
  ├── 1.3 Cleans DENUE establishments & groups 2-digit SCIAN sectors    -> data/processed/economic_units.parquet
  └── 1.4 Filters 2020 FGJ crimes, validates coords, and standardizes  -> data/processed/crime_incidents.parquet

[PHASE 2] POINT-IN-POLYGON SPATIAL JOINS
  ├── Allocates crime coordinates to AGEB polygons (gpd.sjoin)          -> data/processed/crime_assigned_ageb.parquet
  └── Allocates DENUE business coordinates to AGEB polygons             -> data/processed/economic_assigned_ageb.parquet

[PHASE 3] POSTGIS DATA WAREHOUSE INGESTION
  ├── Executes DDL schema (notebooks/sql/01_schema.sql)
  ├── Loads conformed dimensions: dim_geography, dim_time, dim_economic_activity, dim_crime_type
  └── Bulk-inserts fact tables: fact_census_demographics, fact_economic_units, fact_crime_events

[PHASE 4] MATERIALIZED VIEWS & KPI VALIDATION
  ├── Materializes 13 territorial KPIs (notebooks/sql/03_views.sql -> mv_analytical_ageb_kpis)
  │     • Resolves Small Number Problem via Crimes per Business Ratio & Area Densities (crimes/km²)
  └── Executes integrity test suite (notebooks/sql/04_kpi_queries.sql)

[PHASE 5] SPATIAL ECONOMETRICS & VISUALIZATION
  ├── Generates Pearson & Spearman correlation matrices                 -> outputs/figures/correlation_matrices.png
  ├── Creates 5-quantile choropleth maps (Pop, Biz, Crime Density)       -> outputs/maps/fig2_density_choropleths.png
  ├── Builds Queen contiguity spatial weights matrix (W) with KNN repair
  ├── Computes Global Moran's I (Crime: 0.5568, Business: 0.4371)        -> outputs/figures/global_moran_*.png
  ├── Computes Bivariate Moran's I (Crime vs. Neighboring Business: 0.34) -> outputs/figures/bivariate_moran_*.png
  └── Calculates Local Moran (LISA) & 91.6% Hot-Spot Overlap map         -> outputs/maps/fig4_lisa_clusters_and_overlap.png
```

### Selective Execution Flags

`main.py` provides command-line flags to skip or focus on individual segments:

```bash
# Skip raw extraction & spatial joins (if parquets already exist in data/processed/)
python main.py --skip-etl

# Skip database loading and materialized view deployment
python main.py --skip-db

# Run only Phase 5 spatial econometric modeling, Moran's I, and map exports
python main.py --only-analytics
```

---

## 3. Repository Tree

Below is the verified structural tree of the repository:

```text
.
├── .gitignore
├── README.md                      # Developer documentation & pipeline guide
├── requirements.txt               # Python package dependencies
├── docker-compose.yml             # PostGIS 15 container deployment configuration
├── main.py                        # Master pipeline orchestrator (single-command run)
│
├── data/
│   ├── raw/                       # Source input datasets (excluded from Git)
│   │   ├── .gitkeep
│   │   ├── population_dataset.csv # INEGI Censo 2020 tabulations
│   │   ├── crime_dataset.csv      # FGJ CDMX 2020 crime incidents
│   │   ├── economic/              # DENUE 2020 establishment records
│   │   │   ├── denue_09_csv/
│   │   │   └── denue_09_shp/
│   │   └── geographic/            # INEGI Marco Geoestadístico 2020 Shapefiles
│   │       ├── 2020_1_09_A/       # Urban AGEBs (primary analytical unit)
│   │       ├── 2020_1_09_MUN/     # Alcaldías (municipalities)
│   │       └── 2020_1_09_ENT/     # Federal Entity (CDMX outline)
│   │
│   └── processed/                 # Standardized intermediate Parquet artifacts
│       ├── .gitkeep
│       ├── geography_ageb.parquet
│       ├── demographics_ageb.parquet
│       ├── economic_units.parquet
│       ├── crime_incidents.parquet
│       ├── economic_assigned_ageb.parquet
│       └── crime_assigned_ageb.parquet
│
├── notebooks/
│   ├── sql/                       # PostGIS dimensional DDL and analytical queries
│   │   ├── 01_schema.sql          # Star schema DDL with GiST spatial indexing
│   │   ├── 02_load.sql            # Referential integrity and load verification queries
│   │   ├── 03_views.sql           # Materialized view computing 13 territorial KPIs
│   │   └── 04_kpi_queries.sql     # KPI validation & Small Number Problem diagnostics
│   │
│   └── src/                       # Modular pipeline implementation scripts
│       ├── etl_geographic.py      # Cartographic boundary ingestion & topology repair
│       ├── etl_demographics.py    # Censo 2020 AGEB demographic extraction
│       ├── etl_economic_layer.py  # DENUE establishment cleaning & SCIAN grouping
│       ├── etl_crime.py           # FGJ crime temporal filtering & point geocoding
│       ├── spatial_joins.py       # Point-in-polygon overlay engine (gpd.sjoin)
│       ├── load_warehouse.py      # SQLAlchemy/GeoAlchemy2 warehouse ingestion engine
│       ├── spatial_models.py      # Queen weights, Moran's I, LISA, and choropleth generation
│       ├── data_assesment.ipynb   # Exploratory data assessment notebook
│       └── spatial_analytics.ipynb # Interactive spatial analytics notebook
│
├── outputs/
│   ├── .gitkeep
│   ├── figures/                   # Statistical charts and econometric plots
│   │   ├── correlation_matrices.png          # Pearson linear vs. Spearman rank heatmaps
│   │   ├── global_moran_crime.png            # Global Moran scatterplot for Crime Density
│   │   ├── global_moran_business.png         # Global Moran scatterplot for Business Density
│   │   └── bivariate_moran_crime_business.png# Cross-spatial correlation scatterplot
│   │
│   └── maps/                      # Cartographic choropleths and spatial cluster maps
│       ├── fig2_density_choropleths.png       # 3-panel 5-quantile choropleth (Pop, Biz, Crime)
│       ├── fig4_lisa_clusters_and_overlap.png # 3-panel LISA cluster & Hot-Spot Overlap map
│       ├── lisa_business_clusters.png        # Standalone Local Moran Business Hot/Cold spots
│       ├── lisa_crime_clusters.png           # Standalone Local Moran Crime Hot/Cold spots
│       ├── lisa_overlap_map.png              # Standalone 91.6% Hot-Spot Overlap map
│       ├── map_population_density.png        # Population density choropleth map
│       ├── map_business_density.png          # Business density choropleth map
│       └── map_crime_density.png             # Crime density choropleth map
│
└── docs/
    ├── .gitkeep
    └── data_dictionary.md         # Data dictionary, dimensional grains & ER diagram
```

---

## 4. Key Performance Indicators (KPIs) Summary

The materialized view `mv_analytical_ageb_kpis` implements all 13 official project KPIs across all 2,431 urban AGEBs:

1. **Demographic**: Total Population, Population Density ($\text{hab}/\text{km}^2$), PEA Rate, Working-Age Share (15–64).
2. **Economic**: Total Businesses, Business Density ($\text{units}/\text{km}^2$), Businesses per 1k Residents, Retail Density, Service Density, Dominant SCIAN Sector.
3. **Public Safety**: Total Crime Incidents, Crime Rate per 1k Residents, **Crimes per Business Ratio** (resolves the Small Number Problem in non-residential commercial corridors).
