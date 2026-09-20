import os
from datetime import date, timedelta
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

load_dotenv()

CUSTOMER_ID = "6726431917"        # tu cuenta real, sin guiones
LOGIN_CUSTOMER_ID = "4413790396"  # tu cuenta Manager, sin guiones

config = {
    "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
    "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
    "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
    "login_customer_id": LOGIN_CUSTOMER_ID,
    "use_proto_plus": True,
}

client = GoogleAdsClient.load_from_dict(config)
ga_service = client.get_service("GoogleAdsService")

hoy = date.today()
hace_90_dias = hoy - timedelta(days=90)

query = f"""
    SELECT
        campaign.id,
        campaign.name,
        segments.date,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE segments.date BETWEEN '{hace_90_dias}' AND '{hoy}'
"""

response = ga_service.search_stream(customer_id=CUSTOMER_ID, query=query)

filas = []
for batch in response:
    for row in batch.results:
        filas.append({
            "campaign_id": row.campaign.id,
            "campaign_name": row.campaign.name,
            "fecha": row.segments.date,
            "impresiones": row.metrics.impressions,
            "clics": row.metrics.clicks,
            "costo": row.metrics.cost_micros / 1_000_000,
            "conversiones": row.metrics.conversions,
        })

print(f"Filas traídas: {len(filas)}")
if filas:
    print(filas[0])