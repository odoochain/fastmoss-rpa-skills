"""Fetch FastMoss 市场总览 (market-analyze base) for one region.

Pulls aggregate metrics + top products for one region (and optionally one
category). Writes both the raw JSON (rich structure) and a flattened
top-products CSV.

Endpoint: /api/analysis/GoodCategory/base?region=<R>&action=<A>[&pcid=<C>]

Usage:
    python fetch_base.py --region US \\
        --out <out-dir>/us_market_base.json

    python fetch_base.py --region US --pcid 14 \\
        --out <out-dir>/us_beauty_base.json
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    ensure_market_page, fetch_json, write_json, ANALYZE_URL,
    DEFAULT_SESSION, REGION_NAMES,
)


def build_url(region, action, pcid):
    params = []
    if region:
        params.append(f"region={region}")
    params.append(f"action={action}")
    if pcid:
        params.append(f"pcid={pcid}")
    return "/api/analysis/GoodCategory/base?" + "&".join(params)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="", help="Region code (e.g. 'US'). Empty = global.")
    p.add_argument("--action", default="1", help="Time-action enum (default: '1' = daily)")
    p.add_argument("--pcid", type=int, default=None, help="Category id (default = all)")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--top-products-csv", help="If given, also write top_products CSV here")
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

    payload = body.get("data", {})
    payload["_region"] = region or "global"
    payload["_region_name"] = REGION_NAMES.get(region, "")
    payload["_url"] = url

    write_json(args.out, payload)
    print(f"[done] base metrics for region={region or 'global'} -> {args.out}")
    summary_keys = [
        "category_name", "category_sold_count_show", "category_sale_amount",
        "category_sale_amount_mom_rate", "category_sale_amount_yoy_rate",
        "product_count", "sales_product_count", "sales_author_count",
        "sales_video_count", "sales_live_count",
    ]
    print("[summary]")
    for k in summary_keys:
        if k in payload:
            print(f"  {k}: {payload[k]}")

    top = payload.get("top_products") or []
    print(f"[top_products] {len(top)} items")
    if args.top_products_csv and top:
        out_csv = Path(args.top_products_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = ["region", "rank", "product_id", "title", "sold_count", "sale_amount",
                  "total_sold_count", "total_sale_amount", "sold_count_inc_rate",
                  "aweme_count", "live_count", "author_count", "launch_time"]
        with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for i, p in enumerate(top, 1):
                row = dict(p)
                row["region"] = region or "global"
                row["rank"] = i
                w.writerow(row)
        print(f"[top_products_csv] -> {out_csv}")


if __name__ == "__main__":
    main()
