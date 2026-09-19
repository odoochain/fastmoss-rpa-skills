"""Fastmoss ranking scraper via BrowserSkill.

Generic paginating scraper for any FastMoss ranking page that shares the
standard table layout (新品榜/销量榜/热推榜/视频商品榜). One row per product,
advances via the pager, writes a CSV.

Usage:
    python fastmoss_scraper.py --url URL --pages N --out path.csv [--session fastmoss]
    python fastmoss_scraper.py --help
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

DEFAULT_URL = "https://www.fastmoss.com/zh/e-commerce/newProducts"
DEFAULT_SESSION = "fastmoss-products"

EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table', url: location.href});
  const table = tables[tables.length - 1];
  const out = [];
  table.querySelectorAll('tr').forEach(r => {
    const cells = Array.from(r.querySelectorAll('td'));
    if (cells.length < 5) return;
    out.push(cells.map(c => c.innerText.trim()));
  });
  return JSON.stringify({rowCount: out.length, rows: out, title: document.title});
})()
"""

NEXT_PAGE_JS = """
(() => {
  const sel = 'li[title="\\u4e0b\\u4e00\\u9875"], li[class*=next]:not([class*=disabled])';
  const btn = document.querySelector(sel);
  if (!btn) return JSON.stringify({clicked: false});
  btn.click();
  return JSON.stringify({clicked: true});
})()
"""


import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from bsk_client import bsk, configure_utf8_output  # noqa: E402


def call(action, args, session):
    if action == "navigate":
        url = args.get("url")
        new_tab = args.get("newTab", False)
        if new_tab:
            return bsk("tab create", session, url)
        else:
            return bsk("navigate", session, url)
    elif action == "evaluate":
        code = args.get("code", "")
        return bsk("evaluate", session, code)
    elif action == "click":
        selector = args.get("selector", "")
        return bsk("click", session, selector)
    elif action == "fill":
        selector = args.get("selector", "")
        value = args.get("value", "")
        return bsk("fill", session, selector, value=value)
    elif action == "close_session":
        return bsk("session stop", session)
    else:
        raise RuntimeError(f"Unsupported action: {action}")


def evaluate(code, session):
    res = call("evaluate", {"code": code}, session)
    if isinstance(res, dict) and res.get("type") == "string":
        try:
            return json.loads(res["value"])
        except Exception:
            return {"raw": res.get("value")}
    return res


def parse_row(cells):
    """Parse a table row into a structured dict.

    Layout: [rank, product_block, country, shop_block, category,
             commission, sales_period, gmv_period, total_sales, total_gmv, action]
    product_block: name + price + listing date as separate lines.
    shop_block: shop name + 店铺销量 line.
    """
    if len(cells) < 10:
        return None
    product_raw = cells[1].split("\n")
    product_name = product_raw[0] if product_raw else ""
    if not product_name.strip():
        return None
    price = ""
    listed_at = ""
    for line in product_raw[1:]:
        if "售价" in line:
            price = line.split("：")[-1].split(":")[-1].strip()
        elif "上架" in line:
            listed_at = line.split("：")[-1].split(":")[-1].strip()
    shop_raw = cells[3].split("\n")
    shop = shop_raw[0].strip() if shop_raw else ""
    shop_total_sales = ""
    if len(shop_raw) > 1:
        shop_total_sales = shop_raw[1].replace("店铺销量：", "").replace("店铺销量:", "").strip()
    return {
        "rank": cells[0].strip(),
        "product_name": product_name.strip(),
        "price": price,
        "listed_at": listed_at,
        "country": cells[2].strip(),
        "shop": shop,
        "shop_total_sales": shop_total_sales,
        "category": cells[4].strip(),
        "commission": cells[5].strip(),
        "sales_period": cells[6].strip() if len(cells) > 6 else "",
        "gmv_period": cells[7].strip() if len(cells) > 7 else "",
        "total_sales": cells[8].strip() if len(cells) > 8 else "",
        "total_gmv": cells[9].strip() if len(cells) > 9 else "",
    }


def scrape_current(session):
    res = evaluate(EXTRACT_JS, session)
    if "error" in res:
        return [], res
    rows = [parse_row(c) for c in res.get("rows", [])]
    return [r for r in rows if r], res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=DEFAULT_URL, help=f"Ranking page URL (default: {DEFAULT_URL})")
    p.add_argument("--pages", type=int, default=5, help="Number of pages to scrape (default: 5)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--session", default=DEFAULT_SESSION, help=f"Browser session name (default: {DEFAULT_SESSION})")
    p.add_argument("--nav-sleep", type=float, default=5.0, help="Seconds to wait after navigation (default: 5)")
    p.add_argument("--page-sleep", type=float, default=3.5, help="Seconds to wait between pages (default: 3.5)")
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nav = call("navigate", {"url": args.url, "newTab": True, "group_title": "fastmoss-products"}, args.session)
    print(f"[navigate] {nav.get('data', nav)}")
    time.sleep(args.nav_sleep)

    all_rows = []
    for i in range(args.pages):
        rows, meta = scrape_current(args.session)
        title = meta.get("title", "")
        print(f"[page {i+1}] rows={len(rows)} title={title[:50]}")
        for r in rows:
            r["page"] = i + 1
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

    fields = ["page", "rank", "product_name", "price", "listed_at", "country",
              "shop", "shop_total_sales", "category", "commission",
              "sales_period", "gmv_period", "total_sales", "total_gmv"]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(f"[done] {len(all_rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
