"""
ETL Module: Economic Data (INEGI DENUE 2020 CDMX)
Cleans establishments, groups SCIAN economic sectors, and generates geocoded point representations.
"""

from pathlib import Path
import pandas as pd
import geopandas as gpd

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def run_economic_etl() -> gpd.GeoDataFrame:
    root = get_project_root()
    raw_dir = root / "data" / "raw" / "economic"
    output_path = root / "data" / "processed" / "economic_units.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Starting Economic (DENUE) ETL from: {raw_dir}")

    # Search for primary CSV or Shapefile
    csv_candidates = list(raw_dir.rglob("denue_inegi_09_*.csv")) + list(raw_dir.rglob("*.csv"))
    # Filter out data dictionary files
    valid_csvs = [f for f in csv_candidates if "diccionario" not in f.name.lower() and "metadatos" not in f.name.lower()]

    if not valid_csvs:
        raise FileNotFoundError("Could not find raw DENUE establishment data in data/raw/economic/")

    raw_file = valid_csvs[0]
    print(f"  > Loading raw establishments from: {raw_file}")

    df_raw = pd.read_csv(raw_file, encoding="latin1", low_memory=False)
    df_raw.columns = df_raw.columns.str.lower().str.strip()
    print(f"  > Total establishment records loaded: {len(df_raw):,}")

    # Standardize coordinate fields
    df_raw["latitud"] = pd.to_numeric(df_raw["latitud"], errors="coerce")
    df_raw["longitud"] = pd.to_numeric(df_raw["longitud"], errors="coerce")

    # Spatial bounding box validation for CDMX
    valid_bbox = (
        df_raw["latitud"].between(19.0, 19.7) &
        df_raw["longitud"].between(-99.4, -98.8)
    )
    df_clean = df_raw[valid_bbox].copy()
    print(f"  > Establishments inside CDMX bounding box: {len(df_clean):,}")

    # Standardize SCIAN sector codes
    df_clean["codigo_act"] = df_clean["codigo_act"].astype(str).str.strip().str[:6]
    df_clean["sector_scian"] = df_clean["codigo_act"].str[:2]

    # Category grouping for Analytical KPIs
    def classify_scian(sector_code: str) -> str:
        if sector_code in ["43", "46"]:
            return "Retail"
        elif sector_code in ["54", "55", "56", "61", "62", "71", "72", "81"]:
            return "Services"
        elif sector_code in ["31", "32", "33"]:
            return "Manufacturing"
        else:
            return "Other"

    df_clean["categoria"] = df_clean["sector_scian"].apply(classify_scian)
    df_clean["id_denue"] = df_clean["id"].astype(str) if "id" in df_clean.columns else df_clean.index.astype(str)
    df_clean["nombre_act"] = df_clean.get("nombre_act", "Desconocido")
    df_clean["per_ocu"] = df_clean.get("per_ocu", "0 a 5 personas")

    # Construct GeoDataFrame in WGS84
    gdf_denue = gpd.GeoDataFrame(
        df_clean[[
            "id_denue", "codigo_act", "nombre_act", "sector_scian", 
            "categoria", "per_ocu", "latitud", "longitud"
        ]],
        geometry=gpd.points_from_xy(df_clean.longitud, df_clean.latitud),
        crs="EPSG:4326"
    )

    gdf_denue.to_parquet(output_path, index=False)
    print(f"  > Successfully exported {len(gdf_denue):,} economic units to: {output_path}")
    return gdf_denue

if __name__ == "__main__":
    run_economic_etl()