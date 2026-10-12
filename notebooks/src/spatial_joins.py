# ==================================================================
# Spatial Integration Module: Point-in-Polygon Overlay
# Executes gpd.sjoin(predicate='within') to allocate Crimes and Economic Units to official AGEBs.
# ==================================================================

from pathlib import Path
import geopandas as gpd

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def run_spatial_integration():
    root = get_project_root()
    geo_path = root / "data" / "processed" / "geography_ageb.parquet"
    crime_path = root / "data" / "processed" / "crime_incidents.parquet"
    econ_path = root / "data" / "processed" / "economic_units.parquet"

    print("Checking processed files for Spatial Integration...")
    if not (geo_path.exists() and crime_path.exists() and econ_path.exists()):
        print("Notice: Prior processed parquets not yet generated on this machine. Ready for pipeline integration.")
        return

    gdf_ageb = gpd.read_parquet(geo_path).to_crs("EPSG:6372")
    gdf_crime = gpd.read_parquet(crime_path).to_crs("EPSG:6372")
    gdf_econ = gpd.read_parquet(econ_path).to_crs("EPSG:6372")

    # 1. Join Crimes to AGEBs
    crime_joined = gpd.sjoin(
        gdf_crime, gdf_ageb[["cvegeo", "geometry"]], how="inner", predicate="within"
    ).drop(columns=["index_right"])

    # 2. Join Economic Units to AGEBs
    econ_joined = gpd.sjoin(
        gdf_econ, gdf_ageb[["cvegeo", "geometry"]], how="inner", predicate="within"
    ).drop(columns=["index_right"])

    crime_out = root / "data" / "processed" / "crime_assigned_ageb.parquet"
    econ_out = root / "data" / "processed" / "economic_assigned_ageb.parquet"
    crime_joined.to_parquet(crime_out, index=False)
    econ_joined.to_parquet(econ_out, index=False)
    print(f"  > Spatial overlay complete. Outputs saved to {root / 'data' / 'processed'}")

if __name__ == "__main__":
    run_spatial_integration()