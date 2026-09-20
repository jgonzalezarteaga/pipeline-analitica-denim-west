from datetime import datetime
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.cloud import bigquery

PROPERTY_ID = "324817988"
TABLE_ID = "denimwest-data-warehouse.denim_west_analytics.google_ads_campanas"

ga_client = BetaAnalyticsDataClient.from_service_account_json("gcp-credentials.json")

request = RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    dimensions=[Dimension(name="date"), Dimension(name="sessionCampaignName")],
    metrics=[
        Metric(name="advertiserAdCost"),
        Metric(name="advertiserAdClicks"),
        Metric(name="advertiserAdImpressions"),
    ],
    date_ranges=[DateRange(start_date="90daysAgo", end_date="today")],
)

response = ga_client.run_report(request)

filas = []
for row in response.rows:
    fecha_raw = row.dimension_values[0].value  # formato "20260715"
    fecha = datetime.strptime(fecha_raw, "%Y%m%d").strftime("%Y-%m-%d")
    filas.append({
        "fecha": fecha,
        "campania": row.dimension_values[1].value,
        "costo": float(row.metric_values[0].value),
        "clics": int(row.metric_values[1].value),
        "impresiones": int(row.metric_values[2].value),
    })

print(f"Filas traídas de GA4: {len(filas)}")

bq_client = bigquery.Client.from_service_account_json("gcp-credentials.json")
job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
job = bq_client.load_table_from_json(filas, TABLE_ID, job_config=job_config)
job.result()

print(f"Listo: {len(filas)} filas cargadas en {TABLE_ID}")