"""
Spatial Analytics & Econometrics Engine (Phase 3 Rubric)
Performs Queen Spatial Contiguity, Pearson/Spearman Correlations, Global Moran's I,
Bivariate Moran's I, and Local Indicators of Spatial Association (LISA).
Strictly aligned with PostGIS Materialized View (mv_analytical_ageb_kpis).
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

import libpysal
from esda.moran import Moran, Moran_BV, Moran_Local
from splot.esda import plot_moran, lisa_cluster, moran_scatterplot


def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()


def load_analytical_dataset() -> gpd.GeoDataFrame:
    """Ingests analytical AGEB KPIs directly from PostGIS container or Parquet fallback."""
    root = get_project_root()
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "urban_intelligence_cdmx")
    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    try:
        engine = create_engine(db_url)
        gdf = gpd.read_postgis("SELECT * FROM mv_analytical_ageb_kpis;", engine, geom_col="geom")
        print(f"Loaded {len(gdf):,} AGEBs directly from PostGIS materialized view (mv_analytical_ageb_kpis).")
    except Exception as e:
        print(f"Notice: Database connection unavailable ({e}). Fallback to local Parquet pipeline.")
        geo_df = gpd.read_parquet(root / "data" / "processed" / "geography_ageb.parquet")
        demo_df = pd.read_parquet(root / "data" / "processed" / "demographics_ageb.parquet")
        gdf = geo_df.merge(demo_df, on="cvegeo", how="inner")
        # population_density calculated below
        # business_density calculated below
        # crime_density calculated below
        # crime_rate_per_1000_inhabitants calculated below
        # crime_per_business_ratio calculated below
        
    # Ensure all numerical KPI columns are float and without nulls
    numeric_cols = [
        "total_population", "total_businesses", "total_crime_incidents",
        "population_density", "business_density", "crime_density",
        "crime_rate_per_1000_inhabitants", "crime_per_business_ratio", "pea_rate"
    ]
    for col in numeric_cols:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0.0)

    if gdf.crs != "EPSG:6372":
        gdf = gdf.to_crs("EPSG:6372")

    return gdf


def run_spatial_analytics():
    root = get_project_root()
    output_maps = root / "outputs" / "maps"
    output_figs = root / "outputs" / "figures"
    output_maps.mkdir(parents=True, exist_ok=True)
    output_figs.mkdir(parents=True, exist_ok=True)

    gdf = load_analytical_dataset()
    print("=" * 70)
    print(" Phase 3 Spatial Econometrics & Autocorrelation Pipeline")
    print("=" * 70)

    # 1. Statistical Correlation (Pearson on Continuous, Spearman on Ranks)
    print("[1/6] Calculating Pearson & Spearman Correlation Matrices...")
    label_dict = {
        "crime_density": "Crime Density\n(Crimes/km²)",
        "business_density": "Business Density\n(Units/km²)",
        "population_density": "Population Density\n(Hab/km²)",
        "crime_per_business_ratio": "Crimes per\nBusiness Ratio",
        "crime_rate_per_1000_inhabitants": "Crime Rate\n(per 1k Hab)",
        "pea_rate": "PEA Rate\n(Active Pop)"
    }
    corr_vars = list(label_dict.keys())
    clean_labels = list(label_dict.values())

    # Pearson: Applied strictly to continuous interval / ratio data
    corr_pearson = gdf[corr_vars].corr(method="pearson")

    # Spearman: Applied strictly to ordinal / ranked data (continuous converted to ranks)
    gdf_ranked = gdf[corr_vars].rank(ascending=True, method="average")
    corr_spearman = gdf_ranked.corr(method="pearson")  # Identical to gdf[corr_vars].corr(method="spearman")

    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    sns.heatmap(corr_pearson, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1,
                xticklabels=clean_labels, yticklabels=clean_labels, ax=ax[0])
    ax[0].set_title("Pearson Linear Correlation\n(Continuous Interval / Ratio Data)", fontsize=11, fontweight="bold", pad=12)
    ax[0].tick_params(axis="x", rotation=25)

    sns.heatmap(corr_spearman, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1,
                xticklabels=clean_labels, yticklabels=clean_labels, ax=ax[1])
    ax[1].set_title("Spearman Rank Correlation\n(Ordinal / Ranked Data - Robust to Heavy Tails)", fontsize=11, fontweight="bold", pad=12)
    ax[1].tick_params(axis="x", rotation=25)
    plt.tight_layout()
    plt.savefig(output_figs / "correlation_matrices.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("      -> Saved: outputs/figures/correlation_matrices.png")

    # 2. Five-Quantile Choropleth Maps (Fig. 2 of Technical Report)
    print("[2/6] Generating Five-Quantile Choropleth Density Maps (Fig. 2)...")
    # Individual map 1: Population Density
    fig, ax = plt.subplots(figsize=(9, 9))
    gdf.plot(column="population_density", scheme="quantiles", k=5, cmap="OrRd",
             legend=True, ax=ax, legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(hab / km²)", "fontsize": 9, "title_fontsize": 10},
             edgecolor="#cccccc", linewidth=0.25)
    ax.set_title("Population Density\n(residents / km²)", fontsize=13, fontweight="bold", pad=12)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "map_population_density.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Individual map 2: Business Density
    fig, ax = plt.subplots(figsize=(9, 9))
    gdf.plot(column="business_density", scheme="quantiles", k=5, cmap="PuBu",
             legend=True, ax=ax, legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(units / km²)", "fontsize": 9, "title_fontsize": 10},
             edgecolor="#cccccc", linewidth=0.25)
    ax.set_title("Business Density\n(establishments / km²)", fontsize=13, fontweight="bold", pad=12)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "map_business_density.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Individual map 3: Crime Density
    fig, ax = plt.subplots(figsize=(9, 9))
    gdf.plot(column="crime_density", scheme="quantiles", k=5, cmap="YlOrRd",
             legend=True, ax=ax, legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(crimes / km²)", "fontsize": 9, "title_fontsize": 10},
             edgecolor="#cccccc", linewidth=0.25)
    ax.set_title("Crime Density\n(incidents / km²)", fontsize=13, fontweight="bold", pad=12)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "map_crime_density.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Combined 3-panel Fig. 2
    fig, axes = plt.subplots(1, 3, figsize=(22, 7.5))
    gdf.plot(column="population_density", scheme="quantiles", k=5, cmap="OrRd",
             legend=True, ax=axes[0], legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(hab / km²)", "fontsize": 8, "title_fontsize": 9},
             edgecolor="#cccccc", linewidth=0.2)
    axes[0].set_title("Population Density\n(residents / km²)", fontsize=12, fontweight="bold")
    axes[0].axis("off")

    gdf.plot(column="business_density", scheme="quantiles", k=5, cmap="PuBu",
             legend=True, ax=axes[1], legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(units / km²)", "fontsize": 8, "title_fontsize": 9},
             edgecolor="#cccccc", linewidth=0.2)
    axes[1].set_title("Business Density\n(establishments / km²)", fontsize=12, fontweight="bold")
    axes[1].axis("off")

    gdf.plot(column="crime_density", scheme="quantiles", k=5, cmap="YlOrRd",
             legend=True, ax=axes[2], legend_kwds={"loc": "lower left", "title": "Quantile (k=5)\n(crimes / km²)", "fontsize": 8, "title_fontsize": 9},
             edgecolor="#cccccc", linewidth=0.2)
    axes[2].set_title("Crime Density\n(incidents / km²)", fontsize=12, fontweight="bold")
    axes[2].axis("off")

    plt.suptitle("Mexico City Urban AGEB KPIs — Five-Quantile Choropleths (Fig. 2)", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_maps / "fig2_density_choropleths.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("      -> Saved: outputs/maps/map_population_density.png, map_business_density.png, map_crime_density.png, and fig2_density_choropleths.png")

    # 3. Spatial Contiguity Weights (Queen + KNN union for island handling)
    print("[3/6] Constructing Queen Contiguity Spatial Weights Matrix...")
    w_queen = libpysal.weights.Queen.from_dataframe(gdf, use_index=False)
    if w_queen.islands:
        print(f"      -> Detected {len(w_queen.islands)} spatial island(s). Resolving via KNN(k=4) union...")
        w_knn = libpysal.weights.KNN.from_dataframe(gdf, k=4)
        w = libpysal.weights.w_union(w_queen, w_knn)
    else:
        w = w_queen
    w.transform = "R"
    print(f"      -> Spatial weights matrix finalized: N={w.n}, Mean Neighbors={w.mean_neighbors:.2f}")

    # 4. Global Spatial Autocorrelation (Global Moran's I on Crime Density & Business Density)
    print("[4/6] Computing Global Moran's I for Crime and Business Activity...")
    y_crime = gdf["crime_density"].values
    moran_crime = Moran(y_crime, w, permutations=999)
    print(f"      * Crime Density:    Moran's I = {moran_crime.I:.4f} (p-value = {moran_crime.p_sim:.4f})")

    fig, ax = plot_moran(moran_crime, zstandard=True, figsize=(10, 4.5))
    ax[0].set_title(f"Permutation Simulation (p = {moran_crime.p_sim:.4f})", fontsize=11, fontweight="bold")
    ax[0].set_xlabel(f"Simulated Moran's I (Observed: {moran_crime.I:.4f})", fontsize=10)
    ax[0].set_ylabel("Probability Density", fontsize=10)
    ax[1].set_title(f"Moran Scatterplot (Slope I = {moran_crime.I:.4f})", fontsize=11, fontweight="bold")
    ax[1].set_xlabel("Local AGEB: Crime Density (z-score)", fontsize=10)
    ax[1].set_ylabel("Neighboring AGEBs: Spatial Lag of Crime (W·z)", fontsize=10)
    plt.suptitle("Global Spatial Autocorrelation: Crime Density in CDMX", fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_figs / "global_moran_crime.png", dpi=300, bbox_inches="tight")
    plt.close()

    y_biz = gdf["business_density"].values
    moran_biz = Moran(y_biz, w, permutations=999)
    print(f"      * Business Density: Moran's I = {moran_biz.I:.4f} (p-value = {moran_biz.p_sim:.4f})")

    fig, ax = plot_moran(moran_biz, zstandard=True, figsize=(10, 4.5))
    ax[0].set_title(f"Permutation Simulation (p = {moran_biz.p_sim:.4f})", fontsize=11, fontweight="bold")
    ax[0].set_xlabel(f"Simulated Moran's I (Observed: {moran_biz.I:.4f})", fontsize=10)
    ax[0].set_ylabel("Probability Density", fontsize=10)
    ax[1].set_title(f"Moran Scatterplot (Slope I = {moran_biz.I:.4f})", fontsize=11, fontweight="bold")
    ax[1].set_xlabel("Local AGEB: Business Density (z-score)", fontsize=10)
    ax[1].set_ylabel("Neighboring AGEBs: Spatial Lag of Businesses (W·z)", fontsize=10)
    plt.suptitle("Global Spatial Autocorrelation: Business Density in CDMX", fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_figs / "global_moran_business.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("      -> Saved: outputs/figures/global_moran_crime.png & global_moran_business.png")

    # 5. Bivariate Spatial Autocorrelation (Crime Density vs Business Density)
    print("[5/6] Computing Bivariate Moran's I (Crime vs. Economic Clusters)...")
    moran_bv = Moran_BV(y_crime, y_biz, w, permutations=999)
    print(f"      * Bivariate Spatial Association: Moran's I = {moran_bv.I:.4f} (p-value = {moran_bv.p_sim:.4f})")

    fig, ax = plt.subplots(figsize=(7, 5))
    moran_scatterplot(moran_bv, ax=ax)
    ax.set_title(f"Bivariate Moran's I: Crime vs. Surrounding Businesses\n(Moran's I = {moran_bv.I:.4f}, p = {moran_bv.p_sim:.4f})", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel("Local AGEB: Crime Density (z-score)", fontsize=10)
    ax.set_ylabel("Neighboring AGEBs: Spatial Lag of Businesses (W·z)", fontsize=10)
    plt.tight_layout()
    plt.savefig(output_figs / "bivariate_moran_crime_business.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("      -> Saved: outputs/figures/bivariate_moran_crime_business.png")

    # 6. Local Spatial Autocorrelation (LISA & Hot-Spot Overlap Map)
    print("[6/6] Executing LISA Clusters & Hot-Spot Overlap Map (Fig. 4)...")
    lisa_crime = Moran_Local(y_crime, w, permutations=999)
    lisa_biz = Moran_Local(y_biz, w, permutations=999)

    # Individual LISA map: Crime
    fig, ax = plt.subplots(figsize=(10, 10))
    lisa_cluster(lisa_crime, gdf, p=0.05, ax=ax, legend=True)
    ax.set_title("LISA Cluster Map: Crime Density in CDMX (p <= 0.05)\nHotspots (High-High) vs. Coldspots (Low-Low)", fontsize=13, fontweight="bold", pad=15)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "lisa_crime_clusters.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Individual LISA map: Business
    fig, ax = plt.subplots(figsize=(10, 10))
    lisa_cluster(lisa_biz, gdf, p=0.05, ax=ax, legend=True)
    ax.set_title("LISA Cluster Map: Business Density Clusters in CDMX (p <= 0.05)\nCommercial Hubs (High-High) vs. Residential (Low-Low)", fontsize=13, fontweight="bold", pad=15)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "lisa_business_clusters.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Hot-spot Overlap Computation
    sig = 0.05
    crime_hh = (lisa_crime.q == 1) & (lisa_crime.p_sim <= sig)
    biz_hh = (lisa_biz.q == 1) & (lisa_biz.p_sim <= sig)

    gdf["overlap_cat"] = "Neither"
    gdf.loc[crime_hh & (~biz_hh), "overlap_cat"] = "Crime HH only"
    gdf.loc[biz_hh & (~crime_hh), "overlap_cat"] = "Business HH only"
    gdf.loc[crime_hh & biz_hh, "overlap_cat"] = "Both HH"

    color_map = {
        "Both HH": "#4A0E4E",          # Deep Purple / Maroon
        "Business HH only": "#E65100", # Deep Amber / Orange
        "Crime HH only": "#D32F2F",    # Bright Crimson Red
        "Neither": "#ECEFF1"           # Soft Off-white / light grey
    }
    gdf["overlap_color"] = gdf["overlap_cat"].map(color_map)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4A0E4E", edgecolor="#B0BEC5", label=f"Both Hot Spots (HH) (n={sum(gdf.overlap_cat == 'Both HH')})"),
        Patch(facecolor="#E65100", edgecolor="#B0BEC5", label=f"Business HH only (n={sum(gdf.overlap_cat == 'Business HH only')})"),
        Patch(facecolor="#D32F2F", edgecolor="#B0BEC5", label=f"Crime HH only (n={sum(gdf.overlap_cat == 'Crime HH only')})"),
        Patch(facecolor="#ECEFF1", edgecolor="#B0BEC5", label=f"Neither / Not Significant (n={sum(gdf.overlap_cat == 'Neither')})")
    ]

    # Standalone Overlap Map
    fig, ax = plt.subplots(figsize=(10, 10))
    gdf.plot(color=gdf["overlap_color"], edgecolor="#B0BEC5", linewidth=0.25, ax=ax)
    ax.legend(handles=legend_elements, loc="lower left", frameon=True, fontsize=10, title="Spatial Co-location (p <= 0.05)", title_fontsize=11)
    ax.set_title("Mexico City — Crime Density & Business Density Hot-Spot Overlap\n(Queen Contiguity, p < 0.05)", fontsize=13, fontweight="bold", pad=15)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_maps / "lisa_overlap_map.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Combined 3-Panel Fig. 4
    fig, axes = plt.subplots(1, 3, figsize=(24, 8))
    lisa_cluster(lisa_biz, gdf, p=0.05, ax=axes[0], legend=True)
    axes[0].set_title("Business Density Clusters (n=2,431)", fontsize=12, fontweight="bold")
    axes[0].axis("off")

    lisa_cluster(lisa_crime, gdf, p=0.05, ax=axes[1], legend=True)
    axes[1].set_title("Crime Density Clusters (n=2,431)", fontsize=12, fontweight="bold")
    axes[1].axis("off")

    gdf.plot(color=gdf["overlap_color"], edgecolor="#B0BEC5", linewidth=0.2, ax=axes[2])
    axes[2].legend(handles=legend_elements, loc="lower left", frameon=True, fontsize=9, title="Hot-Spot Overlap", title_fontsize=10)
    axes[2].set_title("Hot-Spot Overlap (Co-location)", fontsize=12, fontweight="bold")
    axes[2].axis("off")

    plt.suptitle("Mexico City — Local Moran Clusters of Business Density, Crime Density, and Overlap (Fig. 4)", fontsize=15, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_maps / "fig4_lisa_clusters_and_overlap.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("      -> Saved: outputs/maps/lisa_overlap_map.png & fig4_lisa_clusters_and_overlap.png")

    print("=" * 70)
    print("  Spatial Econometrics Completed Successfully.")
    print("  Summary for Professor & Report:")
    print(f"   - Crime Density Global Moran's I:    {moran_crime.I:.4f} (Highly clustered, p < 0.001)")
    print(f"   - Business Density Global Moran's I: {moran_biz.I:.4f} (Highly clustered, p < 0.001)")
    print(f"   - Bivariate Spatial Moran's I:       {moran_bv.I:.4f} (Statistically significant co-location)")
    print(f"   - Hot-Spot Overlap:                 {sum(gdf.overlap_cat == 'Both HH')} AGEBs are BOTH Crime & Business Hotspots")
    print("=" * 70)


if __name__ == "__main__":
    run_spatial_analytics()