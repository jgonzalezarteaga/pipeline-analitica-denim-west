"""
Manual load of Meta Ads data into BigQuery.

Normal usage (recommended):
    python load_meta_ads_csv.py

    Looks for the most recent CSV export in your Downloads folder and
    loads it. No need to type file names or move the file around.

Usage with an explicit path (if the file is somewhere else):
    python load_meta_ads_csv.py "C:\\path\\to\\file.csv"

The CSV must be exported from Meta Ads Manager with:
- Level: Campaigns
- Breakdown: By day
- Columns: Amount spent, Impressions, Link clicks, Reach

This script fully replaces the target table on every run
(WRITE_TRUNCATE), same as the Tiendanube and Google Ads/GA4 scripts.
That's why you always need to export the full date range you want
available in BigQuery, not just the new days.
"""

import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Config ---
PROJECT_ID = "denimwest-data-warehouse"
DATASET = "denim_west_analytics"
TABLE = "meta_ads_campanas"
CREDENTIALS_FILE = "gcp-credentials.json"

TARGET_TABLE = f"{PROJECT_ID}.{DATASET}.{TABLE}"

# Folder where the browser saves Meta Ads Manager exports by default,
# and the file name pattern to look for (Meta always starts the file
# with "DENIM-WEST-Campa..."). Path.home() resolves to
# C:\Users\<your user> on Windows on its own.
DOWNLOADS_FOLDER = Path.home() / "Downloads"
FILE_PATTERN = "DENIM-WEST-Campa*.csv"


def find_latest_csv(folder: Path, pattern: str) -> Path:
    """Looks in `folder` for files matching `pattern` and returns the
    most recently modified one (the latest export)."""

    candidates = list(folder.glob(pattern))
    if not candidates:
        raise FileNotFoundError(
            f"No file matching '{pattern}' found in "
            f"{folder}.\nExport the CSV from Meta Ads Manager, or pass "
            f"the path manually: python load_meta_ads_csv.py \"path\""
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_meta_csv(csv_path: str) -> pd.DataFrame:
    """Reads the CSV exported from Meta Ads Manager and shapes it into
    the schema used in BigQuery."""

    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Source column names are Meta Ads Manager's own export headers
    # (in Spanish, matching the account's locale) — kept as-is on purpose
    expected_columns = {
        "Inicio del informe",
        "Nombre de la campaña",
        "Fecha de creación",
        "Importe gastado (ARS)",
        "Impresiones",
        "Clics en el enlace",
        "Alcance",
    }
    missing = expected_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"The CSV doesn't have the expected columns. Missing: {missing}\n"
            f"Columns found: {list(df.columns)}"
        )

    # Target column names match the live BigQuery table schema
    # (denim_west_analytics.meta_ads_campanas) — kept in Spanish
    df = df.rename(
        columns={
            "Inicio del informe": "fecha",
            "Nombre de la campaña": "campania",
            "Fecha de creación": "fecha_creacion_campania",
            "Importe gastado (ARS)": "importe_gastado_ars",
            "Impresiones": "impresiones",
            "Clics en el enlace": "clics_enlace",
            "Alcance": "alcance",
        }
    )

    # Keep only the columns that go to BigQuery
    df = df[
        [
            "fecha",
            "campania",
            "fecha_creacion_campania",
            "importe_gastado_ars",
            "impresiones",
            "clics_enlace",
            "alcance",
        ]
    ]

    # Link clicks comes in blank when it was 0, not as "0"
    df["clics_enlace"] = df["clics_enlace"].fillna(0)

    # Types
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["fecha_creacion_campania"] = pd.to_datetime(
        df["fecha_creacion_campania"]
    ).dt.date
    df["campania"] = df["campania"].astype(str)
    df["importe_gastado_ars"] = df["importe_gastado_ars"].astype(float)
    df["impresiones"] = df["impresiones"].astype(int)
    df["clics_enlace"] = df["clics_enlace"].astype(int)
    df["alcance"] = df["alcance"].astype(int)

    return df


def load_to_bigquery(df: pd.DataFrame) -> None:
    """Uploads the DataFrame to BigQuery, replacing the full table."""

    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE
    )
    client = bigquery.Client(credentials=credentials, project=PROJECT_ID)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("fecha", "DATE"),
            bigquery.SchemaField("campania", "STRING"),
            bigquery.SchemaField("fecha_creacion_campania", "DATE"),
            bigquery.SchemaField("importe_gastado_ars", "FLOAT"),
            bigquery.SchemaField("impresiones", "INTEGER"),
            bigquery.SchemaField("clics_enlace", "INTEGER"),
            bigquery.SchemaField("alcance", "INTEGER"),
        ],
    )

    job = client.load_table_from_dataframe(
        df, TARGET_TABLE, job_config=job_config
    )
    job.result()  # wait for it to finish

    print(f"Load complete: {len(df)} rows in {TARGET_TABLE}")


def main():
    if len(sys.argv) == 2:
        # An explicit path was passed
        csv_path = Path(sys.argv[1])
        if not csv_path.exists():
            print(f"File not found: {csv_path}")
            sys.exit(1)
    elif len(sys.argv) == 1:
        # Automatic mode: find the most recent one in Downloads
        try:
            csv_path = find_latest_csv(
                DOWNLOADS_FOLDER, FILE_PATTERN
            )
        except FileNotFoundError as e:
            print(e)
            sys.exit(1)
        print(f"Most recent file found: {csv_path.name}")
    else:
        print('Usage: python load_meta_ads_csv.py  (or with a path: "file.csv")')
        sys.exit(1)

    print(f"Reading {csv_path}...")
    df = read_meta_csv(csv_path)
    print(f"{len(df)} rows read. Date range: "
          f"{df['fecha'].min()} to {df['fecha'].max()}")

    print("Loading to BigQuery...")
    load_to_bigquery(df)


if __name__ == "__main__":
    main()
