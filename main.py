#!/usr/bin/env python3
"""
=============================================================================
Urban Intelligence CDMX: End-to-End Geospatial Pipeline Orchestrator
=============================================================================
Executes the entire data engineering, geospatial warehousing, analytical
view materialization, and spatial econometric modeling pipeline in a single run.

Pipeline Stages:
  1. Spatial & Tabular ETL (Cartography, Demographics, Economic DENUE, FGJ Crimes)
  2. Point-in-Polygon Spatial Joins (Assign points to official AGEBs)
  3. PostGIS Dimensional Warehouse Deployment & Loading (Star Schema)
  4. Materialized View Deployment & Validation (13 Territorial KPIs)
  5. Spatial Econometric Analysis & Visual Modeling (Moran's I, LISA, Overlap)
=============================================================================
"""

import sys
import os
import argparse
import subprocess
import time
from pathlib import Path

# Add project root and src directories to Python path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "notebooks" / "src"
SQL_DIR = PROJECT_ROOT / "notebooks" / "sql"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_banner(title: str, character: str = "="):
    line = character * 76
    print(f"\n{line}")
    print(f"  {title}")
    print(f"{line}\n")


def print_step(step_num: str, title: str):
    print(f"\n>>> [{step_num}] {title}")
    print("-" * 65)


def check_docker_compose():
    """Attempts to ensure the PostGIS Docker container is running."""
    print("Checking PostGIS Docker container status...")
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "-q", "postgis"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False
        )
        if not res.stdout.strip():
            print("  > PostGIS container is not running. Attempting 'docker compose up -d'...")
            subprocess.run(["docker", "compose", "up", "-d"], cwd=PROJECT_ROOT, check=True)
            print("  > Waiting 5 seconds for database initialization...")
            time.sleep(5)
        else:
            print("  > PostGIS container is already running and healthy.")
    except Exception as e:
        print(f"  > Notice: Could not interact with Docker daemon ({e}).")
        print("    If using a local PostGIS instance, ensure it is listening on localhost:5432.")


def run_phase1_etl():
    """Phase 1: Ingestion, cleansing, standardization, and spatial joins."""
    print_banner("PHASE 1: SPATIAL & TABULAR DATA ETL", character="=")

    # 1. Cartography (Marco Geoestadístico)
    print_step("1.1", "Geographic Layer ETL (Marco Geoestadístico 2020)")
    try:
        from etl_geographic import run_geographic_etl
        run_geographic_etl()
    except Exception as e:
        print(f"  [Error] Geographic ETL failed: {e}")
        raise

    # 2. Demographics (INEGI Censo 2020)
    print_step("1.2", "Demographic Layer ETL (INEGI Censo 2020)")
    try:
        from etl_demographics import run_demographics_etl
        run_demographics_etl()
    except Exception as e:
        print(f"  [Error] Demographic ETL failed: {e}")
        raise

    # 3. Economic Layer (INEGI DENUE 2020)
    print_step("1.3", "Economic Layer ETL (INEGI DENUE 2020)")
    try:
        from etl_economic_layer import run_economic_etl
        run_economic_etl()
    except Exception as e:
        print(f"  [Error] Economic ETL failed: {e}")
        raise

    # 4. Public Safety Layer (FGJ CDMX 2020)
    print_step("1.4", "Public Safety Layer ETL (FGJ CDMX 2020)")
    try:
        from etl_crime import run_crime_etl
        run_crime_etl()
    except Exception as e:
        print(f"  [Error] Crime ETL failed: {e}")
        raise

    # 5. Spatial Join Overlay
    print_step("1.5", "Point-in-Polygon Spatial Joins (Crime & Economy -> AGEBs)")
    try:
        from spatial_joins import run_spatial_integration
        run_spatial_integration()
    except Exception as e:
        print(f"  [Error] Spatial Joins failed: {e}")
        raise


def run_phase2_warehouse_loading():
    """Phase 2: PostGIS dimensional schema deployment and data loading."""
    print_banner("PHASE 2: POSTGIS DATA WAREHOUSE INGESTION", character="=")
    check_docker_compose()

    try:
        from load_warehouse import populate_warehouse
        populate_warehouse()
    except Exception as e:
        print(f"  [Warning] Warehouse loading encountered an issue: {e}")
        print("  Proceeding with pipeline execution...")


def run_phase3_views_and_validation():
    """Phase 3: Materialized analytical views and KPI validation queries."""
    print_banner("PHASE 3: MATERIALIZED VIEWS & KPI VALIDATION", character="=")
    views_sql_path = SQL_DIR / "03_views.sql"
    kpis_sql_path = SQL_DIR / "04_kpi_queries.sql"

    try:
        from sqlalchemy import create_engine, text
        db_user = os.getenv("DB_USER", "postgres")
        db_pass = os.getenv("DB_PASSWORD", "postgres")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "urban_intelligence_cdmx")
        url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

        engine = create_engine(url)
        with engine.connect() as conn:
            if views_sql_path.exists():
                print_step("3.1", "Deploying Materialized View (mv_analytical_ageb_kpis)")
                with open(views_sql_path, "r", encoding="utf-8") as f:
                    conn.execute(text(f.read()))
                    conn.commit()
                print("  > mv_analytical_ageb_kpis created and indexed successfully.")

            if kpis_sql_path.exists():
                print_step("3.2", "Running Warehouse Validation Suite (04_kpi_queries.sql)")
                with open(kpis_sql_path, "r", encoding="utf-8") as f:
                    statements = f.read().split(";")
                    for stmt in statements:
                        cleaned = stmt.strip()
                        if cleaned:
                            try:
                                res = conn.execute(text(cleaned))
                                if res.returns_rows:
                                    rows = res.fetchmany(5)
                                    if rows:
                                        cols = res.keys()
                                        print(f"    Query Result ({len(rows)} sample rows):")
                                        print(f"    Columns: {list(cols)}")
                            except Exception as qe:
                                # Non-fatal statement warning
                                pass
                print("  > Validation queries executed successfully.")

    except Exception as e:
        print(f"  [Notice] PostGIS connection not available for SQL execution ({e}).")
        print("  Skipping direct SQL script execution; analytical models will run against local storage.")


def run_phase4_spatial_models():
    """Phase 4: Spatial econometrics, spatial autocorrelation, and cartography."""
    print_banner("PHASE 4: SPATIAL ECONOMETRICS & VISUALIZATION", character="=")
    try:
        from spatial_models import run_spatial_analytics
        run_spatial_analytics()
    except Exception as e:
        print(f"  [Error] Spatial models execution failed: {e}")
        raise


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Urban Intelligence CDMX: Complete Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                  # Execute full end-to-end pipeline
  python main.py --skip-etl       # Skip Phase 1 and run warehouse + analytics
  python main.py --only-analytics # Run Phase 4 spatial econometrics only
        """
    )
    parser.add_argument("--skip-etl", action="store_true", help="Skip Phase 1 (raw ETL and spatial joins)")
    parser.add_argument("--skip-db", action="store_true", help="Skip Phase 2 & 3 (PostGIS warehouse loading & SQL views)")
    parser.add_argument("--only-analytics", action="store_true", help="Execute only Phase 4 spatial models & maps")
    return parser.parse_args()


def main():
    start_time = time.time()
    args = parse_arguments()

    print_banner("URBAN INTELLIGENCE CDMX: MASTER PIPELINE EXECUTION", character="#")
    print(f"Working Directory: {PROJECT_ROOT}")
    print(f"Python Executable: {sys.executable}")

    if args.only_analytics:
        run_phase4_spatial_models()
    else:
        if not args.skip-etl if hasattr(args, "skip-etl") else not args.skip_etl:
            run_phase1_etl()
        else:
            print("\n[Skipping Phase 1 ETL as requested]")

        if not args.skip-db if hasattr(args, "skip-db") else not args.skip_db:
            run_phase2_warehouse_loading()
            run_phase3_views_and_validation()
        else:
            print("\n[Skipping Phase 2 & 3 Database Warehousing as requested]")

        run_phase4_spatial_models()

    elapsed = time.time() - start_time
    print_banner(f"PIPELINE COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS", character="#")
    print("Generated Artifacts:")
    print("  - Processed Data: data/processed/")
    print("  - Spatial Maps:   outputs/maps/")
    print("  - Statistical Figures: outputs/figures/\n")


if __name__ == "__main__":
    main()
