"""Fastmoss shop detail page scraper.

Extracts the shop's product list (with listing dates) for cadence analysis.
Paginates the shop's product table on `/shop-marketing/detail/{shopId}`.

Usage:
    python shop_scraper.py --shop-id <shop-id> --shop-name <shop-name> \\
        --pages 4 --out <out-dir>/shop_<name>.csv

    # Discover the shop ID first via evaluate (see SKILL.md "Discover shop ID"):
    python shop_scraper.py --help
"""
import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from fastmoss_scraper import call, evaluate  # noqa: E402

SHOP_URL_TEMPLATE = "https://www.fastmoss.com/zh/shop-marketing/detail/{shop_id}"
DEFAULT_SESSION = "fastmoss-products"

EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table'});
  const table = tables[0];
  const out = [];
  table.querySelectorAll('tr').forEach(r => {
    const cells = Array.from(r.querySelectorAll('td'));
    if (cells.length < 5) return;
    out.push(cells.map(c => c.innerText.trim()));
  });
  return JSON.stringify({rowCount: out.length, rows: out});
})()
"""

NEXT_PAGE_JS = """
(() => {
  const btn = document.querySelector('li[title="\\u4e0b\\u4e00\\u9875"], li[class*=next]:not([class*=disabled])');
  if (!btn) return JSON.stringify({clicked: false});
  btn.click();
  return JSON.stringify({clicked: true});
})()
"""


def parse_shop_row(cells):
    """Shop product table: [product_block, category, listed_at, commission, sales_28d, gmv_28d]."""
    if len(cells) < 5:
        return None
    product_raw = cells[0].split("\n")
    product_name = ""
    price = ""
    for line in product_raw:
        line = line.strip()
        if not product_name and line and "售价" not in line:
            # First non-price line is the product name; skip 已下架 prefix
            name = line.replace("已下架", "").strip()
            if name and not any(c in name for c in ["马来西亚", "泰国", "越南", "印尼"]):
                product_name = name
        if "售价" in line:
            price = line.split("：")[-1].split(":")[-1].strip()
    country = product_raw[-1].strip() if product_raw else ""
    listed = cells[2].strip()
    if "GMT" not in listed:
        return None
    return {
        "product_name": product_name,
        "price": price,
        "country": country,
        "category": cells[1].strip(),
        "listed_at": listed,
        "commission": cells[3].strip(),
        "sales_28d": cells[4].strip() if len(cells) > 4 else "",
        "gmv_28d": cells[5].strip() if len(cells) > 5 else "",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shop-id", required=True, help="FastMoss shop numeric ID (from /shop-marketing/detail/{id})")
    p.add_argument("--shop-name", help="Shop name (for display only; output path uses --out)")
    p.add_argument("--pages", type=int, default=4, help="Pages to scrape (default: 4)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--session", default=DEFAULT_SESSION, help=f"Browser session (default: {DEFAULT_SESSION})")
    p.add_argument("--nav-sleep", type=float, default=6.0, help="Seconds after navigation (default: 6)")
    p.add_argument("--page-sleep", type=float, default=3.5)
    args = p.parse_args()

    url = SHOP_URL_TEMPLATE.format(shop_id=args.shop_id)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    call("navigate", {"url": url, "newTab": False}, args.session)
    time.sleep(args.nav_sleep)

    all_rows = []
    for i in range(args.pages):
        res = evaluate(EXTRACT_JS, args.session)
        if "error" in res:
            print(f"[page {i+1}] {res}")
            continue
        parsed = [parse_shop_row(c) for c in res.get("rows", [])]
        parsed = [r for r in parsed if r]
        print(f"[page {i+1}] rows={len(parsed)}")
        for r in parsed:
            r["page"] = i + 1
            if args.shop_name:
                r["shop"] = args.shop_name
            all_rows.append(r)
        if i < args.pages - 1:
            click = evaluate(NEXT_PAGE_JS, args.session)
            if not click.get("clicked"):
                print(f"[page {i+1}] next button not found, stopping")
                break
            time.sleep(args.page_sleep)

    if not all_rows:
        print("NO ROWS SCRAPED")
        sys.exit(1)

    fields = ["page", "shop", "product_name", "price", "country", "category",
              "listed_at", "commission", "sales_28d", "gmv_28d"]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(f"[done] {len(all_rows)} rows -> {out_path}")

    from collections import Counter
    months = Counter(r["listed_at"][:7] for r in all_rows)
    print(f"[cadence] {dict(sorted(months.items(), reverse=True))}")


if __name__ == "__main__":
    main()
