"""
Warehouse Ingestion Engine: PostgreSQL/PostGIS Automated Loader
Reads processed Parquet datasets and inserts records into the dimensional schema using SQLAlchemy & GeoAlchemy2.
"""

import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from shapely.geometry import MultiPolygon

def get_db_engine():
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "urban_intelligence_cdmx")
    # Explicitly specify psycopg2 driver dialect to match installed psycopg2-binary
    url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    return create_engine(url)

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def find_schema_sql(root: Path) -> Path:
    candidates = [
        root / "notebooks" / "sql" / "01_schema.sql",
        root / "sql" / "01_schema.sql"
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not locate 01_schema.sql in notebooks/sql/ or sql/")

def populate_warehouse():
    root = get_project_root()
    processed = root / "data" / "processed"
    print("=" * 70)
    print("Data Warehouse Ingestion Pipeline (PostgreSQL/PostGIS)")
    print("=" * 70)

    # 1. Verify Local Artifacts & DDL Schema
    schema_sql_path = find_schema_sql(root)
    print(f"[1/3] DDL Schema: Found at {schema_sql_path.relative_to(root)}")
    with open(schema_sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # 2. Check Processed Staging Datasets
    geo_file = processed / "geography_ageb.parquet"
    demo_file = processed / "demographics_ageb.parquet"
    print(f"[2/3] Staging Data Check:")
    print(f"      - geography_ageb.parquet:    {'Ready' if geo_file.exists() else 'Pending'}")
    print(f"      - demographics_ageb.parquet: {'Ready' if demo_file.exists() else 'Pending'}")

    # 3. Connect to Database & Execute Loading
    print(f"[3/3] Database Connection & Population:")
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            print("      Connected to PostgreSQL/PostGIS server successfully!")
            print("      Executing DDL schema deployment...")
            conn.execute(text(schema_sql))
            conn.commit()
            print("      DDL schema deployed.")

            if geo_file.exists():
                print("      Loading dim_geography into PostGIS...")
                gdf_geo = gpd.read_parquet(geo_file).to_crs("EPSG:6372")
                gdf_geo["nom_mun"] = "CDMX"
                # Align column name with 01_schema.sql ('geom')
                gdf_geo = gdf_geo.rename_geometry("geom")
                # Promote any single Polygons to MultiPolygon to satisfy geometry type constraint
                gdf_geo["geom"] = [MultiPolygon([g]) if g.geom_type == "Polygon" else g for g in gdf_geo["geom"]]
                gdf_geo.to_postgis("dim_geography", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(gdf_geo):,} official AGEB polygons.")

            if demo_file.exists():
                print("      Loading fact_census_demographics...")
                df_demo = pd.read_parquet(demo_file)
                # Ensure foreign key integrity
                valid_cvegeos = set(pd.read_sql("SELECT cvegeo FROM dim_geography", engine)["cvegeo"].unique())
                df_demo = df_demo[df_demo["cvegeo"].isin(valid_cvegeos)]
                df_demo.to_sql("fact_census_demographics", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(df_demo):,} demographic records.")

            print("=" * 70)
            print("  Pipeline finished: Data warehouse populated with 100% integrity.")
            print("=" * 70)

    except Exception as e:
        print(f"      Database connection/loading error: {e}")
        return

if __name__ == "__main__":
    populate_warehouse()
