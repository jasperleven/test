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

    base_url = os.environ["AMO_BASE_URL"]
    token = os.environ["AMO_TOKEN"]

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
