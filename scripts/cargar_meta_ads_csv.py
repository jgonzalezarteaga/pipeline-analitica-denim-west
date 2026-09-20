"""
Carga manual de datos de Meta Ads a BigQuery.

Uso normal (recomendado):
    python cargar_meta_ads_csv.py

    Busca solo el CSV más reciente en tu carpeta de Descargas y lo carga.
    No hace falta escribir nombres de archivo ni moverlo de carpeta.

Uso con ruta explícita (por si el archivo está en otro lado):
    python cargar_meta_ads_csv.py "C:\\ruta\\al\\archivo.csv"

El CSV debe exportarse desde Meta Ads Manager con:
- Nivel: Campañas
- Desglose: Por día
- Columnas: Importe gastado, Impresiones, Clics en el enlace, Alcance

Este script reemplaza por completo la tabla destino en cada corrida
(WRITE_TRUNCATE), igual que los scripts de Tiendanube y Google Ads/GA4.
Por eso hay que exportar siempre el rango completo que se quiere tener
disponible en BigQuery, no solo los días nuevos.
"""

import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Configuración ---
PROJECT_ID = "denimwest-data-warehouse"
DATASET = "denim_west_analytics"
TABLE = "meta_ads_campanas"
CREDENTIALS_FILE = "gcp-credentials.json"

TABLA_DESTINO = f"{PROJECT_ID}.{DATASET}.{TABLE}"

# Carpeta donde el navegador guarda los exports de Meta Ads Manager por
# defecto, y patrón de nombre a buscar (Meta siempre arranca el archivo
# con "DENIM-WEST-Campa..."). Path.home() resuelve solo a
# C:\Users\<tu usuario> en Windows.
CARPETA_DESCARGAS = Path.home() / "Downloads"
PATRON_ARCHIVO = "DENIM-WEST-Campa*.csv"


def encontrar_csv_mas_reciente(carpeta: Path, patron: str) -> Path:
    """Busca en `carpeta` los archivos que matchean `patron` y devuelve
    el que se modificó más recientemente (el último export)."""

    candidatos = list(carpeta.glob(patron))
    if not candidatos:
        raise FileNotFoundError(
            f"No encontré ningún archivo que matchee '{patron}' en "
            f"{carpeta}.\nExportá el CSV desde Meta Ads Manager, o pasá "
            f"la ruta manualmente: python cargar_meta_ads_csv.py \"ruta\""
        )
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def leer_csv_meta(ruta_csv: str) -> pd.DataFrame:
    """Lee el CSV exportado de Meta Ads Manager y lo deja en el esquema
    que usamos en BigQuery."""

    df = pd.read_csv(ruta_csv, encoding="utf-8-sig")

    columnas_esperadas = {
        "Inicio del informe",
        "Nombre de la campaña",
        "Fecha de creación",
        "Importe gastado (ARS)",
        "Impresiones",
        "Clics en el enlace",
        "Alcance",
    }
    faltantes = columnas_esperadas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El CSV no tiene las columnas esperadas. Faltan: {faltantes}\n"
            f"Columnas encontradas: {list(df.columns)}"
        )

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

    # Nos quedamos solo con las columnas que van a BigQuery
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

    # Clics en el enlace viene vacío cuando fue 0, no como "0"
    df["clics_enlace"] = df["clics_enlace"].fillna(0)

    # Tipos
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


def cargar_a_bigquery(df: pd.DataFrame) -> None:
    """Sube el DataFrame a BigQuery reemplazando la tabla completa."""

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
        df, TABLA_DESTINO, job_config=job_config
    )
    job.result()  # espera a que termine

    print(f"Carga completa: {len(df)} filas en {TABLA_DESTINO}")


def main():
    if len(sys.argv) == 2:
        # Se pasó una ruta explícita
        ruta_csv = Path(sys.argv[1])
        if not ruta_csv.exists():
            print(f"No se encontró el archivo: {ruta_csv}")
            sys.exit(1)
    elif len(sys.argv) == 1:
        # Modo automático: buscar el más reciente en Descargas
        try:
            ruta_csv = encontrar_csv_mas_reciente(
                CARPETA_DESCARGAS, PATRON_ARCHIVO
            )
        except FileNotFoundError as e:
            print(e)
            sys.exit(1)
        print(f"Archivo más reciente encontrado: {ruta_csv.name}")
    else:
        print('Uso: python cargar_meta_ads_csv.py  (o con ruta: "archivo.csv")')
        sys.exit(1)

    print(f"Leyendo {ruta_csv}...")
    df = leer_csv_meta(ruta_csv)
    print(f"{len(df)} filas leídas. Rango de fechas: "
          f"{df['fecha'].min()} a {df['fecha'].max()}")

    print("Cargando a BigQuery...")
    cargar_a_bigquery(df)


if __name__ == "__main__":
    main()