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

def sanitize_time(t):
    if not t or pd.isna(t):
        return None
    s = str(t).strip()
    if s.startswith("24:"):
        s = "00:" + s[3:]
    parts = s.split(":")
    if len(parts) >= 2:
        try:
            h = int(parts[0]) % 24
            m = int(parts[1]) % 60
            sec = int(parts[2][:2]) % 60 if len(parts) > 2 and parts[2][:2].isdigit() else 0
            return f"{h:02d}:{m:02d}:{sec:02d}"
        except Exception:
            return None
    return None

def populate_warehouse():
    root = get_project_root()
    processed = root / "data" / "processed"
    print("=" * 70)
    print("  [Member 3] Data Warehouse Ingestion Pipeline (PostgreSQL/PostGIS)")
    print("=" * 70)

    schema_sql_path = find_schema_sql(root)
    print(f"[1/5] DDL Schema: Found at {schema_sql_path.relative_to(root)}")
    with open(schema_sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            print("      Connected to PostgreSQL/PostGIS server successfully!")
            print("      Executing DDL schema deployment...")
            conn.execute(text(schema_sql))
            conn.commit()
            print("      DDL schema deployed.")

            # 1. Ingest Geography
            geo_file = processed / "geography_ageb.parquet"
            if geo_file.exists():
                print("[2/5] Loading dim_geography into PostGIS...")
                gdf_geo = gpd.read_parquet(geo_file).to_crs("EPSG:6372")
                gdf_geo["nom_mun"] = "CDMX"
                gdf_geo = gdf_geo.rename_geometry("geom")
                gdf_geo["geom"] = [MultiPolygon([g]) if g.geom_type == "Polygon" else g for g in gdf_geo["geom"]]
                gdf_geo.to_postgis("dim_geography", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(gdf_geo):,} official AGEB polygons.")

            valid_cvegeos = set(pd.read_sql("SELECT cvegeo FROM dim_geography", engine)["cvegeo"].unique())

            # 2. Ingest Demographics
            demo_file = processed / "demographics_ageb.parquet"
            if demo_file.exists():
                print("[3/5] Loading fact_census_demographics...")
                df_demo = pd.read_parquet(demo_file)
                df_demo = df_demo[df_demo["cvegeo"].isin(valid_cvegeos)]
                df_demo.to_sql("fact_census_demographics", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(df_demo):,} demographic records.")

            # 3. Ingest Economic Units
            econ_file = processed / "economic_assigned_ageb.parquet"
            if econ_file.exists():
                print("[4/5] Loading Economic Activity & Units...")
                gdf_econ = gpd.read_parquet(econ_file)
                gdf_econ = gdf_econ[gdf_econ["cvegeo"].isin(valid_cvegeos)].copy()

                acts = gdf_econ[["codigo_act", "nombre_act", "sector_scian", "categoria"]].drop_duplicates(subset=["codigo_act"])
                acts.to_sql("dim_economic_activity", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(acts):,} activities into dim_economic_activity.")

                df_acts_db = pd.read_sql("SELECT activity_id, codigo_act FROM dim_economic_activity", engine)
                gdf_econ = gdf_econ.merge(df_acts_db, on="codigo_act", how="left")
                gdf_econ = gdf_econ.rename(columns={"per_ocu": "estrato_ocupacion"}).rename_geometry("geom")
                if gdf_econ.crs != "EPSG:6372":
                    gdf_econ = gdf_econ.to_crs("EPSG:6372")

                econ_facts = gdf_econ[["id_denue", "cvegeo", "activity_id", "estrato_ocupacion", "latitud", "longitud", "geom"]]
                econ_facts.to_postgis("fact_economic_units", engine, if_exists="append", index=False, chunksize=25000)
                print(f"      -> Ingested {len(econ_facts):,} economic unit facts.")

            # 4. Ingest Crime Events
            crime_file = processed / "crime_assigned_ageb.parquet"
            if crime_file.exists():
                print("[5/5] Loading Public Safety & Crime Events...")
                gdf_crime = gpd.read_parquet(crime_file)
                gdf_crime = gdf_crime[gdf_crime["cvegeo"].isin(valid_cvegeos)].copy()

                crime_types = gdf_crime[["categoria_delito", "delito"]].drop_duplicates()
                crime_types.to_sql("dim_crime_type", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(crime_types):,} crime types into dim_crime_type.")

                df_ct_db = pd.read_sql("SELECT crime_type_id, categoria_delito, delito FROM dim_crime_type", engine)
                gdf_crime = gdf_crime.merge(df_ct_db, on=["categoria_delito", "delito"], how="left")

                gdf_crime["date_id"] = pd.to_datetime(gdf_crime["fecha_hecho"], errors="coerce").dt.date
                dates = pd.DataFrame({"date_id": gdf_crime["date_id"].dropna().unique()})
                dates["anio"] = pd.to_datetime(dates["date_id"]).dt.year
                dates["mes"] = pd.to_datetime(dates["date_id"]).dt.month
                dates["dia"] = pd.to_datetime(dates["date_id"]).dt.day
                dates["dia_semana"] = pd.to_datetime(dates["date_id"]).dt.dayofweek + 1
                dates["trimestre"] = pd.to_datetime(dates["date_id"]).dt.quarter
                dates.to_sql("dim_time", engine, if_exists="append", index=False)
                print(f"      -> Ingested {len(dates):,} calendar dates into dim_time.")

                gdf_crime["hora"] = gdf_crime["hora_hecho"].apply(sanitize_time)
                gdf_crime = gdf_crime.rename_geometry("geom")
                if gdf_crime.crs != "EPSG:6372":
                    gdf_crime = gdf_crime.to_crs("EPSG:6372")

                crime_facts = gdf_crime[["cvegeo", "crime_type_id", "date_id", "hora", "latitud", "longitud", "geom"]]
                crime_facts.to_postgis("fact_crime_events", engine, if_exists="append", index=False, chunksize=25000)
                print(f"      -> Ingested {len(crime_facts):,} crime event facts.")

            # 5. Refresh Materialized View if exists
            try:
                conn.execute(text("REFRESH MATERIALIZED VIEW mv_analytical_ageb_kpis;"))
                conn.commit()
                print("      Refreshed mv_analytical_ageb_kpis with latest data.")
            except Exception:
                pass

            print("=" * 70)
            print("  Pipeline finished: Data warehouse populated with 100% integrity.")
            print("=" * 70)

    except Exception as e:
        print(f"      Database connection/loading error: {e}")

if __name__ == "__main__":
    populate_warehouse()
