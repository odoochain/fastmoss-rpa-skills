"""Dump FastMoss market-page vocabularies (categories + countries).

Calls /api/analysis/GoodCategory/filterInfo via page-context fetch and
prints/writes the category (c_code -> c_name, rank) and country
(region_code -> region_name) mappings.

Usage:
    python fetch_filter_info.py [--out <path>.json] [--session fastmoss-market]
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import ensure_market_page, fetch_json, write_json, DEFAULT_SESSION  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", help="Optional JSON output path (default: print to stdout)")
    p.add_argument("--session", default=DEFAULT_SESSION)
    args = p.parse_args()

    ensure_market_page(args.session)
    res = fetch_json("/api/analysis/GoodCategory/filterInfo", args.session)
    if "_error" in res:
        print(f"[error] {res['_error']}")
        sys.exit(1)
    if res.get("status") != 200:
        print(f"[error] HTTP {res.get('status')}: {res}")
        sys.exit(1)
    payload = res.get("data", {}).get("data", res.get("data", {}))
    if not isinstance(payload, dict):
        payload = {"raw": res}

    if args.out:
        write_json(args.out, payload)
        print(f"[done] {len(payload.get('category', []))} categories, "
              f"{len(payload.get('country', []))} countries -> {args.out}")
    else:
        cats = payload.get("category", [])
        countries = payload.get("country", [])
        print(f"=== {len(cats)} categories ===")
        for c in cats:
            print(f"  pcid={c.get('c_code'):>3}  {c.get('c_name'):<20}  rank={c.get('rank')}")
        print(f"\n=== {len(countries)} countries ===")
        for c in countries:
            print(f"  {c.get('region_code'):<3} {c.get('region_name')}")


if __name__ == "__main__":
    main()
