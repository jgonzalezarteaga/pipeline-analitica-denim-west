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
    "User-Agent": "Denim West Analytics Pipeline (your-email@example.com)",
}


def fetch_orders():
    orders = []
    page = 1
    since = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    while True:
        url = f"https://api.tiendanube.com/v1/{STORE_ID}/orders"
        params = {"per_page": 50, "page": page, "created_at_min": since}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 404:
            break
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        orders.extend(data)
        print(f"Page {page}: {len(data)} orders")
        page += 1
    return orders


def transform(order):
    # Column names match the live BigQuery table schema
    # (denim_west_analytics.tiendanube_pedidos) — kept in Spanish
    product = order["products"][0] if order["products"] else {}
    return {
        "pedido": order["number"],
        "fecha": order["created_at"],
        "cliente": order["contact_name"],
        "moneda": order["currency"],
        "total": float(order["total"]),
        "metodo_envio": order.get("shipping_option"),
        "estado_pago": order.get("payment_status"),
        "sku": product.get("sku"),
        "cantidad": product.get("quantity"),
        "precio": float(product.get("price", 0)),
    }


orders = fetch_orders()
print(f"Total orders fetched: {len(orders)}")

rows = [transform(o) for o in orders]

client = bigquery.Client.from_service_account_json("gcp-credentials.json")

target_table = "denimwest-data-warehouse.denim_west_analytics.tiendanube_pedidos"

job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    autodetect=True,
    write_disposition="WRITE_TRUNCATE",
)

job = client.load_table_from_json(rows, target_table, job_config=job_config)
job.result()
print(f"Done: {job.output_rows} orders loaded (full table replace, no duplicates)")
