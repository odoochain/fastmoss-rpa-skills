"""Fetch FastMoss 行业格局 data via the categoryDistribution API.

Pulls per-category sale amount + growth for one or more regions, optionally
filtered by category and time window. Writes one CSV row per (region × category).

Time modes:
  --time 28d    Last 28 days (default; no date_value param sent)
  --time month  Most recent completed month (date_value=YYYY-MM, computed from today)

Usage:
    # One region, last 28 days
    python fetch_distribution.py --region US \\
        --out <out-dir>/us_categories.csv

    # Multi-region comparison (writes one CSV per region + combined)
    python fetch_distribution.py --region US,ID,TH,MY --time month \\
        --out <out-dir>/categories_by_region.csv

    # One region, one specific category
    python fetch_distribution.py --region US --pcid 14 --time month \\
        --out <out-dir>/us_beauty.csv
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    ensure_market_page, fetch_json, write_json, write_csv,
    DEFAULT_SESSION, REGION_NAMES,
)


def most_recent_completed_month(today=None):
    """Return YYYY-MM string for the most recent completed month."""
    today = today or datetime.now()
    if today.month == 1:
        return f"{today.year - 1}-12"
    return f"{today.year}-{today.month - 1:02d}"


def build_url(region, time_mode, pcid, date_value=None):
    """Build the categoryDistribution URL with the right query params."""
    params = ["is_mock=0"]
    if region:
        params.append(f"region={region}")
    if time_mode == "month":
        dv = date_value or most_recent_completed_month()
        params.append(f"date_value={dv}")
    if pcid:
        params.append(f"pcid={pcid}")
    return "/api/analysis/V2/categoryDistribution?" + "&".join(params)


def fetch_one(region, time_mode, pcid, session):
    url = build_url(region, time_mode, pcid)
    res = fetch_json(url, session)
    if "_error" in res:
        return [], res, url
    if res.get("status") != 200:
        return [], res, url
    body = res.get("data", {})
    # FastMoss may return code=MAG_AUTH_3024 (subscription warning) but still
    # include the data payload. Treat as success if dots are present.
    dots = body.get("data", {}).get("dots", [])
    if not dots:
        return [], body, url
    date_value = ""
    if time_mode == "month":
        date_value = most_recent_completed_month()
    rows = []
    region_name = REGION_NAMES.get(region, "")
    for d in dots:
        row = dict(d)
        row["region_name"] = d.get("region_name") or region_name
        row["time_window"] = time_mode
        row["date_value"] = date_value
        rows.append(row)
    return rows, None, url


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="",
                   help="Comma-separated region codes (e.g. 'US,ID,TH,MY'). Empty = global.")
    p.add_argument("--time", choices=["28d", "month"], default="28d",
                   help="Time window (default: 28d)")
    p.add_argument("--pcid", type=int, default=None,
                   help="Category id (e.g. 14 for 美妆个护). Default = all categories.")
    p.add_argument("--out", required=True,
                   help="Combined output CSV path (per-region CSVs also written if multi-region)")
    p.add_argument("--raw-json", help="If given, also dump raw API responses here (one JSON per region)")
    p.add_argument("--session", default=DEFAULT_SESSION)
    args = p.parse_args()

    regions = [r.strip().upper() for r in args.region.split(",") if r.strip()]
    if not regions:
        regions = [""]  # global

    ensure_market_page(args.session)

    combined_path = Path(args.out)
    per_run_dir = combined_path.parent
    per_run_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    raw_payloads = []
    for region in regions:
        rows, err, url = fetch_one(region, args.time, args.pcid, args.session)
        label = region or "global"
        if err:
            print(f"[{label}] error: {err} url={url}")
            continue
        print(f"[{label}] {len(rows)} categories (url: {url})")
        if args.raw_json:
            raw_payloads.append({"region": label, "url": url, "dots": rows})
        if rows and len(regions) > 1:
            out = per_run_dir / f"{combined_path.stem}_{label}{combined_path.suffix}"
            write_csv(out, rows, base_fields())
            print(f"[{label}] saved -> {out}")
        all_rows.extend(rows)

    if all_rows:
        write_csv(combined_path, all_rows, base_fields())
        print(f"[combined] {len(all_rows)} rows -> {combined_path}")

    if args.raw_json and raw_payloads:
        write_json(args.raw_json, raw_payloads)


def base_fields():
    return [
        "region", "region_name", "time_window", "date_value",
        "category_id", "category_name",
        "category_sale_amount", "category_sale_amount_show",
        "category_sale_amount_mom_rate", "category_sale_amount_mom_rate_show",
        "cur_sale_amount", "last_sale_amount",
    ]


if __name__ == "__main__":
    main()
