# ==================================================================
# ETL Module: Geographic Cartography (Marco Geoestadístico INEGI 2020 CDMX)
# Loads official AGEBs, validates topology, reprojects to metric EPSG:6372, and computes surface area.
# ==================================================================

from pathlib import Path
import geopandas as gpd

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def run_geographic_etl() -> gpd.GeoDataFrame:
    root = get_project_root()
    shp_path = root / "data" / "raw" / "geographic" / "2020_1_09_A" / "2020_1_09_A.shp"
    output_path = root / "data" / "processed" / "geography_ageb.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading official Marco Geoestadístico from: {shp_path}")
    if not shp_path.exists():
        print(f"Warning: Shapefile not found at {shp_path}. Skipping execution test.")
        return gpd.GeoDataFrame()

    gdf_raw = gpd.read_file(shp_path)
    print(f"  > Raw polygons loaded: {len(gdf_raw):,} | Source CRS: {gdf_raw.crs}")
    
    # Standardize non-geometry columns to uppercase while preserving the active geometry column
    geom_col = gdf_raw.geometry.name
    gdf_raw.columns = [c.upper() if c != geom_col else "geometry" for c in gdf_raw.columns]
    gdf_raw = gdf_raw.set_geometry("geometry")

    if "CVEGEO" not in gdf_raw.columns:
        gdf_raw["CVEGEO"] = (
            gdf_raw["CVE_ENT"].astype(str).str.zfill(2) +
            gdf_raw["CVE_MUN"].astype(str).str.zfill(3) +
            gdf_raw["CVE_LOC"].astype(str).str.zfill(4) +
            gdf_raw["CVE_AGEB"].astype(str).str.zfill(4)
        )

    # Topology repair
    invalid_mask = ~gdf_raw.is_valid
    if invalid_mask.any():
        print(f"  > Fixing {invalid_mask.sum()} invalid geometries using .buffer(0)")
        gdf_raw["geometry"] = gdf_raw["geometry"].buffer(0)

    # Reproject to Official Mexican Metric Projected System: EPSG:6372 (ITRF2008 / LCC)
    gdf_metric = gdf_raw.to_crs("EPSG:6372")
    gdf_metric["area_km2"] = gdf_metric.geometry.area / 1_000_000.0

    gdf_clean = gdf_metric[[
        "CVEGEO", "CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB", "area_km2", "geometry"
    ]].rename(columns={
        "CVEGEO": "cvegeo",
        "CVE_ENT": "cve_ent",
        "CVE_MUN": "cve_mun",
        "CVE_LOC": "cve_loc",
        "CVE_AGEB": "cve_ageb"
    })

    print(f"  > Total validated AGEB polygons: {len(gdf_clean):,}")
    gdf_clean.to_parquet(output_path, index=False)
    print(f"  > Exported processed geography to: {output_path}")
    return gdf_clean

if __name__ == "__main__":
    run_geographic_etl()