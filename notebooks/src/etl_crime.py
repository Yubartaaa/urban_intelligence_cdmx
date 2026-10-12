# ==================================================================
# ETL Module: Public Safety Data (FGJ CDMX Crime Incident Open Data 2020)
# Filters incidents for the year 2020, audits geocoding precision, and builds Point geometries.
# ==================================================================

from pathlib import Path
import pandas as pd
import geopandas as gpd

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def run_crime_etl() -> gpd.GeoDataFrame:
    root = get_project_root()
    raw_path = root / "data" / "raw" / "crime_dataset.csv"
    output_path = root / "data" / "processed" / "crime_incidents.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading Public Safety records from: {raw_path}")
    if not raw_path.exists():
        print(f"Warning: Crime dataset not found at {raw_path}. Skipping execution test.")
        return gpd.GeoDataFrame()

    df_raw = pd.read_csv(raw_path, low_memory=False)
    df_raw.columns = df_raw.columns.str.lower().str.strip()

    # Temporal filter: Year 2020
    if "anio_hecho" in df_raw.columns:
        df_2020 = df_raw[pd.to_numeric(df_raw["anio_hecho"], errors="coerce") == 2020].copy()
    elif "fecha_hecho" in df_raw.columns:
        df_raw["fecha_parsed"] = pd.to_datetime(df_raw["fecha_hecho"], errors="coerce")
        df_2020 = df_raw[df_raw["fecha_parsed"].dt.year == 2020].copy()
    else:
        raise KeyError("Crime dataset missing temporal attributes.")

    df_2020["latitud"] = pd.to_numeric(df_2020["latitud"], errors="coerce")
    df_2020["longitud"] = pd.to_numeric(df_2020["longitud"], errors="coerce")

    valid_coords = (
        df_2020["latitud"].between(19.0, 19.7) &
        df_2020["longitud"].between(-99.4, -98.8)
    )
    df_clean = df_2020[valid_coords].copy()

    df_clean["delito"] = df_clean.get("delito", "NO ESPECIFICADO").astype(str).str.strip().str.upper()
    df_clean["categoria_delito"] = df_clean.get("categoria_delito", "DELITO DE BAJO IMPACTO").astype(str).str.strip().str.upper()
    df_clean["fecha_hecho"] = df_clean.get("fecha_hecho", "2020-01-01").astype(str)
    df_clean["hora_hecho"] = df_clean.get("hora_hecho", "00:00:00").astype(str)

    gdf_crime = gpd.GeoDataFrame(
        df_clean[[
            "delito", "categoria_delito", "fecha_hecho", "hora_hecho", "latitud", "longitud"
        ]],
        geometry=gpd.points_from_xy(df_clean.longitud, df_clean.latitud),
        crs="EPSG:4326"
    )

    gdf_crime.to_parquet(output_path, index=False)
    print(f"  > Exported {len(gdf_crime):,} processed crime points to: {output_path}")
    return gdf_crime

if __name__ == "__main__":
    run_crime_etl()