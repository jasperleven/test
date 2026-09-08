"""
One-off check: which deals tagged with a given baer became a sale
("Договор подписан", status_id 69561406) on a SPECIFIC date -- not the
date they were created, but the date of the actual status transition.

Usage:
    export AMO_BASE_URL=https://daangrah000.amocrm.ru
    export AMO_TOKEN=<your token>
    python check_sales_on_date.py --baer BNS --date 2026-09-07
"""

import argparse
import calendar
from datetime import datetime, timezone
import os
import time

import requests

# Вставлено напрямую по прямой просьбе пользователя.
AMO_BASE_URL = "https://daangrah000.amocrm.ru"
AMO_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjBlMTQ2YzI3MDk0NTkyMmQxM2JmMGZkMTgzYjU2ZjI4NzI0N2Y3ZDk2NGI3OWRiY2YwNGQ1ZTJjZTQ5YWJkNThmNWY2ZmI1YjM1MTRkYzQ0In0.eyJhdWQiOiIwNDRlYzY0Mi0xMTAxLTRlYzgtOTBiYy03MThjODU1YTZjYmIiLCJqdGkiOiIwZTE0NmMyNzA5NDU5MjJkMTNiZjBmZDE4M2I1NmYyODcyNDdmN2Q5NjRiNzlkYmNmMDRkNWUyY2U0OWFiZDU4ZjVmNmZiNWIzNTE0ZGM0NCIsImlhdCI6MTc4Mjg5NDE1NCwibmJmIjoxNzgyODk0MTU0LCJleHAiOjE4NDM0MzA0MDAsInN1YiI6IjExNDY3MjU4IiwiZ3JhbnRfdHlwZSI6IiIsImFjY291bnRfaWQiOjMxOTI4Mjk4LCJiYXNlX2RvbWFpbiI6ImFtb2NybS5ydSIsInZlcnNpb24iOjIsInNjb3BlcyI6WyJwdXNoX25vdGlmaWNhdGlvbnMiLCJmaWxlcyIsImNybSIsImZpbGVzX2RlbGV0ZSIsIm5vdGlmaWNhdGlvbnMiXSwiaGFzaF91dWlkIjoiMjM2Mjc0M2UtMDA3NC00ZjJhLWIzMzgtOTc5YjgxZjY1NGFlIiwiYXBpX2RvbWFpbiI6ImFwaS1iLmFtb2NybS5ydSJ9.AC-lkIhD_CIkM9c12WVayoEjolvyTNEpvDkfBY95WyoMjsRaRgn57wkDBl-pOGuNuLkts94DubkkoyAkZjEVZ7AuZyoTuZvyTL5TFYz4cU2tmR0Igy-WdboJcD3AgAdSe1KSb5chmoOX06kqH93cO78H_F_5_u2k4pyWHvLTe2LMwbthXU900UMQFQshLVKTsilaLJviUBfYdscNKd2Un0XedJL8Fiu--lp4BkWWr0oq_71Jy9CETm2U8oUaFW8lkGKezjnLcqXhdma3siZNqICOHFVXLQRAE7k6qvJIfUyCendrepO_rLoMt7ShGQjYB4MDd3lBXSjhK8-Svn1Xsg"

SALE_STATUS_ID = 69561406


def amo_get(base_url, token, path, params=None):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{base_url.rstrip('/')}{path}", headers=headers, params=params or {}, timeout=45)
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.text:
        return {}
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baer", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    base_url = AMO_BASE_URL
    token = AMO_TOKEN

    day = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    from_ts = int(day.timestamp())
    to_ts = from_ts + 86399

    print(f"Fetching lead_status_changed events for {args.date}...")
    page = 1
    limit = 250
    matching_deal_ids = []

    while True:
        params = {
            "filter[type]": "lead_status_changed",
            "filter[created_at][from]": from_ts,
            "filter[created_at][to]": to_ts,
            "limit": limit,
            "page": page,
        }
        data = amo_get(base_url, token, "/api/v4/events", params)
        events = data.get("_embedded", {}).get("events", [])
        if not events:
            break

        for event in events:
            value_after = event.get("value_after") or []
            for v in value_after:
                lead_status = v.get("lead_status") or {}
                if lead_status.get("id") == SALE_STATUS_ID:
                    matching_deal_ids.append(event.get("entity_id"))

        if len(events) < limit:
            break
        page += 1
        time.sleep(0.2)

    print(f"  {len(matching_deal_ids)} transition(s) into sale status on {args.date}")

    if not matching_deal_ids:
        print("No deals to check tags for.")
        return

    print("Checking tags for each deal...")
    matched = []
    for deal_id in matching_deal_ids:
        lead = amo_get(base_url, token, f"/api/v4/leads/{deal_id}", {"with": "tags"})
        tags = [t.get("name", "").strip().lower() for t in (lead.get("_embedded") or {}).get("tags") or []]
        if args.baer.lower() in tags:
            matched.append((deal_id, lead.get("name")))
        time.sleep(0.15)

    print(f"\n{len(matched)} deal(s) tagged '{args.baer}' became a sale on {args.date}:")
    for deal_id, name in matched:
        print(f"  {deal_id}  {name}")


if __name__ == "__main__":
    main()
