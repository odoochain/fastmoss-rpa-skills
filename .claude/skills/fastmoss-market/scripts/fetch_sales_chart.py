"""Fetch FastMoss daily sales-chart time-series for one region.

Endpoint: /api/analysis/GoodCategory/salesChart?region=<R>&action=<A>[&pcid=<C>]

Returns one row per day with category_sold_count, inc_product_count,
sales_product_count, sales_author_count, sales_video_count, sales_live_count.

Usage:
    python fetch_sales_chart.py --region US \\
        --out <out-dir>/us_sales_chart.csv

    python fetch_sales_chart.py --region US --pcid 14 \\
        --out <out-dir>/us_beauty_sales_chart.csv
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    ensure_market_page, fetch_json, write_csv, ANALYZE_URL,
    DEFAULT_SESSION, REGION_NAMES,
)


def build_url(region, action, pcid):
    params = []
    if region:
        params.append(f"region={region}")
    params.append(f"action={action}")
    if pcid:
        params.append(f"pcid={pcid}")
    return "/api/analysis/GoodCategory/salesChart?" + "&".join(params)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="", help="Region code (e.g. 'US'). Empty = global.")
    p.add_argument("--action", default="1", help="Time-action enum (default: '1' = daily)")
    p.add_argument("--pcid", type=int, default=None, help="Category id (default = all)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--session", default=DEFAULT_SESSION)
    args = p.parse_args()

    region = args.region.strip().upper()
    ensure_market_page(args.session, page_url=ANALYZE_URL)

    url = build_url(region, args.action, args.pcid)
    res = fetch_json(url, args.session)
    if "_error" in res:
        print(f"[error] {res['_error']}")
        sys.exit(1)
    if res.get("status") != 200:
        print(f"[error] HTTP {res.get('status')}: {res}")
        sys.exit(1)
    body = res.get("data", {})
    if body.get("code") != 200:
        print(f"[error] API code {body.get('code')}: {body}")
        sys.exit(1)

    items = body.get("data", {}).get("list", [])
    rows = []
    for item in items:
        row = dict(item)
        row["region"] = region or "global"
        row["region_name"] = REGION_NAMES.get(region, "")
        rows.append(row)
    print(f"[done] {len(rows)} daily rows for region={region or 'global'} (url: {url})")

    base_fields = ["region", "region_name", "dt", "data_value",
                   "category_sold_count", "category_sold_count_show",
                   "inc_product_count", "inc_product_count_show",
                   "sales_product_count", "sales_product_count_show",
                   "sales_author_count", "sales_author_count_show",
                   "sales_video_count", "sales_video_count_show",
                   "sales_live_count", "sales_live_count_show"]
    write_csv(args.out, rows, base_fields)
    print(f"[csv] -> {args.out}")


if __name__ == "__main__":
    main()
