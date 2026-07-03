"""Fastmoss ranking scraper with country/category/shop-type filter applied.

Clicks the filter radio/chip by text label (no @e refs — they go stale
after navigation), then paginates and extracts.

Usage:
    # Single filter
    python fastmoss_filtered.py --filter-type country --labels 美国 \\
        --pages 3 --out <out-dir>/us.csv

    # Multiple filters in one run (writes one CSV per filter + a combined file)
    python fastmoss_filtered.py --filter-type country \\
        --labels 美国,印度尼西亚,泰国,马来西亚 --pages 3 \\
        --out <out-dir>/by_country.csv

Filter types supported:
    country      — clicks input[type=radio] whose label matches (美国/印尼/泰国/...)
    category     — clicks the category chip by text (expands the list first)
    shop_type    — clicks 跨境店/本土店 radio
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
from fastmoss_scraper import call, evaluate, parse_row  # noqa: E402

DAEMON = "http://127.0.0.1:10086"
DEFAULT_URL = "https://www.fastmoss.com/zh/e-commerce/newProducts"
DEFAULT_SESSION = "fastmoss-products"

EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table'});
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

CLICK_COUNTRY_JS = """
((label) => {
  const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
  const t = radios.find(r => {
    const parent = r.closest('label') || r.parentElement;
    return parent && parent.innerText.includes(label);
  });
  if (!t) return JSON.stringify({clicked: false, count: radios.length});
  t.click();
  return JSON.stringify({clicked: true, value: t.value, checked: t.checked});
})(%s)
"""

CLICK_CATEGORY_JS = """
((label) => {
  const expand = Array.from(document.querySelectorAll('span, button, a'))
    .find(el => el.innerText && el.innerText.trim() === '展开');
  if (expand) { try { expand.click(); } catch(e) {} }
  const t = Array.from(document.querySelectorAll('span, a, button, div'))
    .find(el => el.innerText && el.innerText.trim() === label && el.offsetParent !== null);
  if (!t) return JSON.stringify({clicked: false, expanded: !!expand});
  t.click();
  return JSON.stringify({clicked: true, expanded: !!expand});
})(%s)
"""

CLICK_SHOP_TYPE_JS = """
((label) => {
  const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
  const t = radios.find(r => {
    const parent = r.closest('label') || r.parentElement;
    return parent && parent.innerText.includes(label);
  });
  if (!t) return JSON.stringify({clicked: false});
  t.click();
  return JSON.stringify({clicked: true, value: t.value});
})(%s)
"""

NEXT_PAGE_JS = """
(() => {
  const btn = document.querySelector('li[title="\\u4e0b\\u4e00\\u9875"], li[class*=next]:not([class*=disabled])');
  if (!btn) return JSON.stringify({clicked: false});
  btn.click();
  return JSON.stringify({clicked: true});
})()
"""

FILTER_TEMPLATES = {
    "country": CLICK_COUNTRY_JS,
    "category": CLICK_CATEGORY_JS,
    "shop_type": CLICK_SHOP_TYPE_JS,
}


def click_filter(filter_type, label, session):
    template = FILTER_TEMPLATES[filter_type]
    return evaluate(template % json.dumps(label, ensure_ascii=False), session)


def scrape_one(filter_type, label, pages, url, session, nav_sleep, page_sleep):
    call("navigate", {"url": url, "newTab": False}, session)
    time.sleep(nav_sleep)
    click = click_filter(filter_type, label, session)
    print(f"[{label}] click: {click}")
    time.sleep(nav_sleep)
    rows_out = []
    for p in range(pages):
        res = evaluate(EXTRACT_JS, session)
        if "error" in res:
            print(f"[{label} page {p+1}] {res}")
            continue
        parsed = [parse_row(c) for c in res.get("rows", [])]
        parsed = [r for r in parsed if r]
        if p == 0 and parsed:
            sample_key = {"country": "country", "category": "category"}.get(filter_type, "country")
            vals = {r.get(sample_key, "") for r in parsed}
            print(f"[{label} page {p+1}] rows={len(parsed)} {sample_key}s={vals}")
        else:
            print(f"[{label} page {p+1}] rows={len(parsed)}")
        for r in parsed:
            r["filter"] = label
            r["page"] = p + 1
            rows_out.append(r)
        if p < pages - 1:
            evaluate(NEXT_PAGE_JS, session)
            time.sleep(page_sleep)
    return rows_out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--filter-type", required=True, choices=list(FILTER_TEMPLATES.keys()),
                   help="Type of filter to apply")
    p.add_argument("--labels", required=True,
                   help="Comma-separated filter labels (e.g. '美国,印度尼西亚' or '美妆个护,女装与女士内衣')")
    p.add_argument("--pages", type=int, default=3, help="Pages per filter (default: 3)")
    p.add_argument("--out", required=True, help="Combined output CSV path (per-label CSVs also written next to it)")
    p.add_argument("--url", default=DEFAULT_URL, help=f"Ranking page URL (default: {DEFAULT_URL})")
    p.add_argument("--session", default=DEFAULT_SESSION, help=f"Browser session (default: {DEFAULT_SESSION})")
    p.add_argument("--nav-sleep", type=float, default=5.0)
    p.add_argument("--page-sleep", type=float, default=3.5)
    args = p.parse_args()

    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    combined_path = Path(args.out)
    per_label_dir = combined_path.parent
    per_label_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for label in labels:
        out = per_label_dir / f"{combined_path.stem}_{label}{combined_path.suffix}"
        rows = scrape_one(args.filter_type, label, args.pages, args.url, args.session,
                          args.nav_sleep, args.page_sleep)
        if rows:
            fields = ["filter", "page", "rank", "product_name", "price", "listed_at",
                      "country", "shop", "shop_total_sales", "category", "commission",
                      "sales_period", "gmv_period", "total_sales", "total_gmv"]
            with out.open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
            print(f"[{label}] saved {len(rows)} -> {out}")
            all_rows.extend(rows)

    if all_rows:
        fields = ["filter", "page", "rank", "product_name", "price", "listed_at",
                  "country", "shop", "shop_total_sales", "category", "commission",
                  "sales_period", "gmv_period", "total_sales", "total_gmv"]
        with combined_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows)
        print(f"[combined] {len(all_rows)} -> {combined_path}")


if __name__ == "__main__":
    main()
