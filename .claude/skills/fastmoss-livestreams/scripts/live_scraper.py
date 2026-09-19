"""FastMoss livestream ranking scraper via BrowserSkill.

Generic paginating scraper for any of the 3 livestream ranking pages on
fastmoss.com. Reads thead headers dynamically and writes one row per entry
with column names = headers (handles per-ranking schema differences).

Ranking URLs:
    tiktok        https://www.fastmoss.com/zh/live/tiktok
    hotProduct    https://www.fastmoss.com/zh/live/hotProduct
    liveCommerce  https://www.fastmoss.com/zh/live/liveCommerce

Usage:
    python live_scraper.py --ranking tiktok --pages 5 --out <path>/tiktok.csv
    python live_scraper.py --ranking hotProduct --pages 3 --out <path>/hot_product.csv
    python live_scraper.py --url <custom-url> --pages 3 --out <path>/custom.csv
    python live_scraper.py --help
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from bsk_client import bsk, configure_utf8_output  # noqa: E402

DEFAULT_SESSION = "fastmoss-livestreams"

RANKINGS = {
    "tiktok":        "https://www.fastmoss.com/zh/live/tiktok",
    "hotProduct":    "https://www.fastmoss.com/zh/live/hotProduct",
    "liveCommerce":  "https://www.fastmoss.com/zh/live/liveCommerce",
}

# Primary-entity column name per ranking (the multi-line cell to extract a clean name from)
ENTITY_HEADERS = {
    "tiktok": "直播间",
    "hotProduct": "商品",
    "liveCommerce": "达人",
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


def parse_entity_name(cell):
    """Pull the primary name from the multi-line main-entity cell."""
    if not cell:
        return ""
    first_line = cell.split("\n")[0].strip()
    return first_line[:80]


def parse_row(headers, cells, entity_header):
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
    entity_cell = row.get(entity_header, "")
    row["entity_name"] = parse_entity_name(entity_cell)
    return row


def scrape_current(session, entity_header):
    res = evaluate(EXTRACT_JS, session)
    if "error" in res:
        return [], res
    headers = res.get("headers", [])
    rows = []
    for cells in res.get("rows", []):
        parsed = parse_row(headers, cells, entity_header)
        if parsed:
            rows.append(parsed)
    return rows, res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ranking", choices=list(RANKINGS.keys()),
                   help="Ranking key (one of: %s). Mutually exclusive with --url." % ", ".join(RANKINGS))
    p.add_argument("--url", help="Custom FastMoss livestream ranking URL (overrides --ranking)")
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
    entity_header = ENTITY_HEADERS.get(args.ranking, "")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nav = call("navigate", {"url": url, "newTab": True, "group_title": "fastmoss-livestreams"}, args.session)
    print(f"[navigate] {nav.get('data', nav)}")
    time.sleep(args.nav_sleep)

    all_rows = []
    headers_seen = None
    for i in range(args.pages):
        rows, meta = scrape_current(args.session, entity_header)
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

    base_fields = ["page", "ranking", "rank", "entity_name"]
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
