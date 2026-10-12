"""
ETL Module: Demographic Data (INEGI Censo de Población y Vivienda 2020)
Extracts and normalizes demographic records strictly at the AGEB urbana level for CDMX (Entity 09).
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

def get_project_root() -> Path:
    current = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return Path.cwd().resolve()

def run_demographics_etl() -> pd.DataFrame:
    root = get_project_root()
    raw_path = root / "data" / "raw" / "population_dataset.csv"
    output_path = root / "data" / "processed" / "demographics_ageb.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Starting Demographic ETL from: {raw_path}")
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw population dataset: {raw_path}")

    # INEGI codes missing and privacy-suppressed values with '*' and 'N/D'
    na_values = ["*", "N/D", "n/d", "", " "]
    df_raw = pd.read_csv(raw_path, low_memory=False, na_values=na_values)
    print(f"  > Raw records loaded: {len(df_raw):,}")

    # Standardize column headers
    df_raw.columns = df_raw.columns.str.upper().str.strip()

    # 1. Filter strictly to urban AGEB total rows (MZA == '0000' or MZA == 0)
    # This excludes municipality-wide totals and individual block rows
    if "MZA" in df_raw.columns:
        mza_str = df_raw["MZA"].astype(str).str.strip().str.zfill(4)
        df_filtered = df_raw[mza_str == "0000"].copy()
    else:
        df_filtered = df_raw.copy()

    # 2. Construct 13-character standard CVEGEO key (Entity 2 + Mun 3 + Loc 4 + AGEB 4)
    if "CVEGEO" not in df_filtered.columns:
        required_key_cols = {"ENTIDAD", "MUN", "LOC", "AGEB"}
        if required_key_cols.issubset(df_filtered.columns):
            df_filtered["CVEGEO"] = (
                df_filtered["ENTIDAD"].astype(str).str.strip().str.zfill(2) +
                df_filtered["MUN"].astype(str).str.strip().str.zfill(3) +
                df_filtered["LOC"].astype(str).str.strip().str.zfill(4) +
                df_filtered["AGEB"].astype(str).str.strip().str.zfill(4)
            )
        else:
            raise KeyError("Cannot assemble CVEGEO: missing geographic component keys.")

    # 3. Ensure Entity 09 (CDMX) filter
    df_filtered = df_filtered[df_filtered["CVEGEO"].str.startswith("09")].copy()

    # 4. Extract and cast required demographic metrics for KPIs
    numeric_columns = {
        "POBTOT": "total_population",
        "POBFEM": "female_population",
        "POBMAS": "male_population",
        "P_15A64": "working_age_population",
        "PEA": "economically_active_population",
        "POCUPADA": "employed_population",
        "VIVTOT": "total_dwellings"
    }

    selected_cols = ["CVEGEO"]
    rename_dict = {"CVEGEO": "cvegeo"}

    for raw_col, clean_name in numeric_columns.items():
        if raw_col in df_filtered.columns:
            df_filtered[raw_col] = pd.to_numeric(df_filtered[raw_col], errors="coerce").fillna(0)
            selected_cols.append(raw_col)
            rename_dict[raw_col] = clean_name
        else:
            df_filtered[clean_name] = 0.0
            selected_cols.append(clean_name)

    df_clean = df_filtered[selected_cols].rename(columns=rename_dict)
    df_clean = df_clean.drop_duplicates(subset=["cvegeo"])

    print(f"  > Cleaned CDMX AGEBs with demographic data: {len(df_clean):,}")
    print(f"  > Mean population per AGEB: {df_clean['total_population'].mean():.1f}")
    
    df_clean.to_parquet(output_path, index=False)
    print(f"  > Exported processed demographics to: {output_path}")
    return df_clean

if __name__ == "__main__":
    run_demographics_etl()