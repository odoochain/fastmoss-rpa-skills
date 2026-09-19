"""FastMoss shop ranking scraper via BrowserSkill.

Generic paginating scraper for any of the 2 shop ranking pages on
fastmoss.com. Reads thead headers dynamically and writes one row per shop
with column names = headers (handles per-ranking schema differences).

Ranking URLs:
    sales  https://www.fastmoss.com/zh/shop-marketing/tiktok
    hot    https://www.fastmoss.com/zh/shop-marketing/hotTiktok

Usage:
    python shop_scraper.py --ranking sales --pages 5 --out <path>/sales.csv
    python shop_scraper.py --ranking hot --pages 3 --out <path>/hot.csv
    python shop_scraper.py --url <custom-url> --pages 3 --out <path>/custom.csv
    python shop_scraper.py --help
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from bsk_client import bsk, configure_utf8_output  # noqa: E402

DEFAULT_SESSION = "fastmoss-shops"

RANKINGS = {
    "sales": "https://www.fastmoss.com/zh/shop-marketing/tiktok",
    "hot":   "https://www.fastmoss.com/zh/shop-marketing/hotTiktok",
}

EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table', url: location.href});
  const readCell = (el) => {
    let txt = (el.innerText || '').trim();
    if (txt) return txt;
    txt = (el.textContent || '').trim();
    if (txt) return txt;
    return (el.getAttribute('title') || '').trim();
  };
  // Ant Design renders a sticky-header table clone separately — table[0] may
  // hold the headers and table[1] the rows (or vice versa). Merge across all.
  let headers = [];
  let rows = [];
  tables.forEach(t => {
    if (!headers.length) {
      const hs = Array.from(t.querySelectorAll('thead th')).map(readCell).filter(x => x);
      if (hs.length) headers = hs;
    }
    if (!rows.length) {
      const rs = [];
      t.querySelectorAll('tbody tr').forEach(r => {
        const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
        if (cells.length >= 4) rs.push(cells);
      });
      if (rs.length) rows = rs;
    }
  });
  return JSON.stringify({headers, rows, title: document.title});
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


def sanitize_header(h):
    if not h:
        return ""
    return h.replace("\n", " ").replace("\r", " ").strip()


def parse_shop_cell(cell):
    """Pull shop_name + legal_name + category + rating out of the multi-line 店铺 cell."""
    parts = [p.strip() for p in cell.split("\n") if p.strip()]
    shop_name = ""
    legal = ""
    category = ""
    rating = ""
    for p in parts:
        if p == "品牌":
            continue
        if re.fullmatch(r"\d+\.\d+", p):
            rating = p
        elif not shop_name:
            shop_name = p
        elif not legal and (p.isupper() or "PT" in p or "INC" in p or "CO" in p or "LLC" in p or "SDN" in p or "LTD" in p or "TRADING" in p):
            legal = p
        elif not category and len(p) <= 12 and p not in ("男", "女"):
            category = p
    return shop_name, legal, category, rating


def parse_row(headers, cells):
    if not any(c.strip() for c in cells):
        return None
    row = {}
    for i, h in enumerate(headers):
        if i >= len(cells):
            break
        if h in ("操作", ""):
            continue
        row[sanitize_header(h)] = cells[i]
    rank = cells[0].strip() if cells else ""
    row["rank"] = rank
    shop_field = row.get("店铺", "")
    shop_name, legal, category, rating = parse_shop_cell(shop_field)
    row["shop_name"] = shop_name
    row["shop_legal_name"] = legal
    row["shop_category"] = category
    row["shop_rating"] = rating
    return row


def scrape_current(session):
    res = evaluate(EXTRACT_JS, session)
    if "error" in res:
        return [], res
    headers = res.get("headers", [])
    rows = []
    for cells in res.get("rows", []):
        parsed = parse_row(headers, cells)
        if parsed:
            rows.append(parsed)
    return rows, res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ranking", choices=list(RANKINGS.keys()),
                   help="Ranking key (one of: %s). Mutually exclusive with --url." % ", ".join(RANKINGS))
    p.add_argument("--url", help="Custom FastMoss shop ranking URL (overrides --ranking)")
    p.add_argument("--pages", type=int, default=5, help="Number of pages to scrape (default: 5)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--session", default=DEFAULT_SESSION, help=f"Browser session (default: {DEFAULT_SESSION})")
    p.add_argument("--nav-sleep", type=float, default=6.0, help="Seconds after navigation (default: 6)")
    p.add_argument("--page-sleep", type=float, default=3.5, help="Seconds between pages (default: 3.5)")
    args = p.parse_args()

    if not args.ranking and not args.url:
        p.error("either --ranking or --url is required")
    url = args.url or RANKINGS[args.ranking]
    ranking_key = args.ranking or "custom"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nav = call("navigate", {"url": url, "newTab": True, "group_title": "fastmoss-shops"}, args.session)
    print(f"[navigate] {nav.get('data', nav)}")
    time.sleep(args.nav_sleep)

    all_rows = []
    headers_seen = None
    for i in range(args.pages):
        rows, meta = scrape_current(args.session)
        if not headers_seen and "headers" in meta:
            headers_seen = meta["headers"]
            print(f"[page {i+1}] headers: {headers_seen}")
        print(f"[page {i+1}] rows={len(rows)} title={meta.get('title','')[:50]}")
        for r in rows:
            r["page"] = i + 1
            r["ranking"] = ranking_key
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

    base_fields = ["page", "ranking", "rank", "shop_name", "shop_legal_name", "shop_category", "shop_rating"]
    extra_fields = []
    seen = set(base_fields)
    for r in all_rows:
        for k in r.keys():
            if k not in seen:
                extra_fields.append(k)
                seen.add(k)
    fields = base_fields + extra_fields

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(f"[done] {len(all_rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
