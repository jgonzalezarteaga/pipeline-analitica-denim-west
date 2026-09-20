import os
import json
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

ACCESS_TOKEN = os.getenv("TIENDANUBE_ACCESS_TOKEN")
STORE_ID = os.getenv("TIENDANUBE_STORE_ID")

headers = {
    "Authentication": f"bearer {ACCESS_TOKEN}",
    "User-Agent": "Pipeline Analitica Denim West (tu-email@ejemplo.com)",
}


def traer_pedidos():
    pedidos = []
    page = 1
    desde = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    while True:
        url = f"https://api.tiendanube.com/v1/{STORE_ID}/orders"
        params = {"per_page": 50, "page": page, "created_at_min": desde}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 404:
            break
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        pedidos.extend(data)
        print(f"Página {page}: {len(data)} pedidos")
        page += 1
    return pedidos


def transformar(order):
    producto = order["products"][0] if order["products"] else {}
    return {
        "pedido": order["number"],
        "fecha": order["created_at"],
        "cliente": order["contact_name"],
        "moneda": order["currency"],
        "total": float(order["total"]),
        "metodo_envio": order.get("shipping_option"),
        "estado_pago": order.get("payment_status"),
        "sku": producto.get("sku"),
        "cantidad": producto.get("quantity"),
        "precio": float(producto.get("price", 0)),
    }


pedidos = traer_pedidos()
print(f"Total de pedidos traídos: {len(pedidos)}")

filas = [transformar(o) for o in pedidos]

client = bigquery.Client.from_service_account_json("gcp-credentials.json")

tabla_final = "denimwest-data-warehouse.denim_west_analytics.tiendanube_pedidos"

job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    autodetect=True,
    write_disposition="WRITE_TRUNCATE",
)

job = client.load_table_from_json(filas, tabla_final, job_config=job_config)
job.result()
print(f"Listo: {job.output_rows} pedidos cargados (tabla reemplazada completa, sin duplicados)")
