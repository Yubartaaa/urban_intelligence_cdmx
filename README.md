# Data Acquisition Guide: Mexico City Urban Intelligence

This document outlines the step-by-step procedure to acquire, verify, and store the official raw datasets required for the Mexico City Geospatial Urban Intelligence project.

---

## Overview of Required Datasets

| Layer | Source | Specific Target / File | Format | Analytical Role |
| :--- | :--- | :--- | :--- | :--- |
| **Geographic** | INEGI Marco Geoestadístico | Entidad `09 Ciudad de México` (Marco 2020) | Shapefile (`.shp`, `.dbf`, `.shx`, `.prj`) | Primary geographic unit of analysis (Urban AGEB) and municipal boundaries |
| **Demographic** | INEGI Censo de Población y Vivienda 2020 | Principales resultados por AGEB y manzana (RESAGEBURB / SCINCE) | CSV (`population_dataset.csv`) | Population base (`POBTOT`, `PEA`, age cohorts) for normalization |
| **Economic** | INEGI DENUE | Conjunto de datos CDMX (DENUE 2020) | CSV / Shapefile | Point-level economic units, SCIAN sector classification (Retail & Services) |
| **Public Safety** | Portal de Datos Abiertos CDMX | Carpetas de investigación FGJ CDMX (2020 hechos) | CSV (`crime_dataset.csv`) | Incident-level geocoded crimes with temporal and categorical attributes |

---

## 1. Geographic Layer: INEGI Marco Geoestadístico

### Portal & Version
* **Source**: Instituto Nacional de Estadística y Geografía (INEGI)
* **URL**: [https://www.inegi.org.mx/programas/mg/#mapas](https://www.inegi.org.mx/programas/mg/#mapas)
* **Version**: Marco Geoestadístico 2020 (aligned 1:1 with the 2020 Census)
* **Target Territory**: `09 Ciudad de México`

### Download Procedure
1. Navigate to the **Descargas / Mapas** section.
2. In the layer selector, check:
   * **AGEB urbano** (layer `2020_1_09_A` / `09a` — Primary analytical unit)
   * **AGEM** (layer `2020_1_09_MUN` / `09mun` — Alcaldías / contextual boundary)
   * *(Optional)* **AGEE** (layer `2020_1_09_ENT` — Federal entity boundary)
3. Filter by state: **09 Ciudad de México**.
4. Click **Consultar** and download the resulting ZIP archive.
5. Extract the contents inside `data/raw/geographic/`.

### Expected Files
```text
data/raw/geographic/
├── 2020_1_09_A/
│   ├── 2020_1_09_A.shp
│   ├── 2020_1_09_A.dbf
│   ├── 2020_1_09_A.shx
│   └── 2020_1_09_A.prj
├── 2020_1_09_MUN/
│   ├── 2020_1_09_MUN.shp
│   └── ...
└── 2020_1_09_ENT/
    ├── 2020_1_09_ENT.shp
    └── ...
```

---

## 2. Demographic Layer: INEGI Censo de Población y Vivienda 2020

### Portal & Version
* **Source**: INEGI Censo de Población y Vivienda 2020
* **URL**: [https://www.inegi.org.mx/programas/ccpv/2020/#microdatos](https://www.inegi.org.mx/programas/ccpv/2020/#microdatos)
* **Product**: *Principales resultados por AGEB y manzana urbana (RESAGEBURB / SCINCE 2020)*
* **Entity**: `09 Ciudad de México`

### Download Procedure
1. Go to the Censo 2020 microdata/tabulated downloads page.
2. Select **Resultados por AGEB y manzana urbana**.
3. Choose state **09 Ciudad de México**.
4. Download the CSV package (typically distributed as `conjunto_de_datos_iter_09CSV20.csv` or `RESAGEBURB_09CSV20.csv`).
5. Move the extracted file to `data/raw/` and rename it to:
   ```bash
   data/raw/population_dataset.csv
   ```

### Key Columns Required
* `CVEGEO` (or composite `CVE_ENT` + `CVE_MUN` + `CVE_LOC` + `CVE_AGEB`)
* `POBTOT` (Total population)
* `PEA` (Economically active population)
* `P_15A64` (Working-age population bracket)
* Filter out municipal summary rows and block-level records (`MZA != '0000'`) during preprocessing to retain AGEB totals only.

---

## 3. Economic Layer: INEGI DENUE

### Portal & Version
* **Source**: Directorio Estadístico Nacional de Unidades Económicas (DENUE)
* **URL**: [https://www.inegi.org.mx/app/descarga/](https://www.inegi.org.mx/app/descarga/)
* **Edition**: DENUE 2020 (or late 2020 release to align with Census 2020)
* **State**: `09 Ciudad de México`

### Download Procedure
1. Under the **Descarga masiva** tab, choose the state filter: **09 Ciudad de México**.
2. Select either the CSV download (`denue_09_csv.zip`) or the Shapefile download (`denue_09_shp.zip`).
3. Download and extract the archive into `data/raw/economic/`.

### Expected Files
```text
data/raw/economic/
└── denue_09_csv/          # or denue_09_shp/
    └── denue_inegi_09_.csv
```

### Key Columns Required
* `latitud`, `longitud` (Point coordinates in WGS84, `EPSG:4326`)
* `codigo_act` / `codigo_scian` (Economic sector codes: Retail `43-46`, Services `54-81`)
* `nombre_act` / `nom_est` (Commercial activity description and establishment name)

---

## 4. Public Safety Layer: Portal de Datos Abiertos CDMX

### Portal & Dataset
* **Source**: Fiscalía General de Justicia de la Ciudad de México (FGJ CDMX)
* **Portal**: [https://datos.cdmx.gob.mx](https://datos.cdmx.gob.mx)
* **Dataset**: *Carpetas de investigación FGJ de la Ciudad de México* (or *Víctimas en carpetas de investigación FGJ*)

### Download Procedure
1. Navigate to the Portal de Datos Abiertos CDMX.
2. Search for `Carpetas de investigación FGJ`.
3. Download the full historical CSV release.
4. Move the file to `data/raw/` and rename it to:
   ```bash
   data/raw/crime_dataset.csv
   ```

### Temporal Filter & Key Columns
* **Temporal Scope**: Filter by `anio_hecho == 2020` (or derive from `fecha_hecho`).
  * *Note*: Do not filter by `fecha_inicio`, as it corresponds to the administrative complaint filing date, which introduces temporal lag.
* `latitud`, `longitud` (Point coordinates in WGS84, `EPSG:4326`)
* `delito` and `categoria_delito` (Categorization of crime type)
* `fecha_hecho` and `hora_hecho` (Temporal incident timestamps)

---

## 5. Verified Repository Layout

Once all files are acquired, verify your repository root adheres to the following directory structure before running verification or pipeline scripts:

```text
.
├── .gitignore
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   │   ├── geographic/
│   │   │   ├── 2020_1_09_A/
│   │   │   │   ├── 2020_1_09_A.shp
│   │   │   │   ├── 2020_1_09_A.dbf
│   │   │   │   ├── 2020_1_09_A.prj
│   │   │   │   └── 2020_1_09_A.shx
│   │   │   ├── 2020_1_09_MUN/
│   │   │   │   └── ...
│   │   │   └── 2020_1_09_ENT/
│   │   │       └── ...
│   │   ├── economic/
│   │   │   └── denue_09_csv/
│   │   │       └── denue_inegi_09_.csv
│   │   ├── population_dataset.csv
│   │   └── crime_dataset.csv
│   └── processed/
└── notebooks/
    └── 01_phase1_data_assessment.py
```

---
