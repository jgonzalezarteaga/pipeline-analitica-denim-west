import os
from datetime import date, timedelta
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

load_dotenv()

CUSTOMER_ID = "6726431917"        # real account, no dashes
LOGIN_CUSTOMER_ID = "4413790396"  # Manager account, no dashes

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

today = date.today()
ninety_days_ago = today - timedelta(days=90)

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
    WHERE segments.date BETWEEN '{ninety_days_ago}' AND '{today}'
"""

response = ga_service.search_stream(customer_id=CUSTOMER_ID, query=query)

rows = []
for batch in response:
    for row in batch.results:
        rows.append({
            "campaign_id": row.campaign.id,
            "campaign_name": row.campaign.name,
            "date": row.segments.date,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
        })

print(f"Rows fetched: {len(rows)}")
if rows:
    print(rows[0])
