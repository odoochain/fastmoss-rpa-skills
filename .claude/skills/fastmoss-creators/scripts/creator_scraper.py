"""FastMoss creator ranking scraper via kimi-webbridge.

Generic paginating scraper for any of the 5 creator ranking pages on
fastmoss.com. Reads thead headers dynamically and writes one row per creator
with column names = headers (handles per-ranking schema differences).

Ranking URLs:
    fans          https://www.fastmoss.com/zh/influencer/tiktok/fans
    commerceTop   https://www.fastmoss.com/zh/influencer/tiktok/commerceTop
    blue-v        https://www.fastmoss.com/zh/influencer/tiktok/blue-v
    popular       https://www.fastmoss.com/zh/influencer/tiktok/popular
    potentialTop  https://www.fastmoss.com/zh/influencer/tiktok/potentialTop

Usage:
    python creator_scraper.py --ranking fans --pages 5 --out <path>/fans.csv
    python creator_scraper.py --ranking potentialTop --pages 3 --out <path>/horse.csv
    python creator_scraper.py --url <custom-url> --pages 3 --out <path>/custom.csv
    python creator_scraper.py --help
"""
import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086"
DEFAULT_SESSION = "fastmoss-creators"

RANKINGS = {
    "fans":          "https://www.fastmoss.com/zh/influencer/tiktok/fans",
    "commerceTop":   "https://www.fastmoss.com/zh/influencer/tiktok/commerceTop",
    "blue-v":        "https://www.fastmoss.com/zh/influencer/tiktok/blue-v",
    "popular":       "https://www.fastmoss.com/zh/influencer/tiktok/popular",
    "potentialTop":  "https://www.fastmoss.com/zh/influencer/tiktok/potentialTop",
}

EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table', url: location.href});
  const table = tables[tables.length - 1];
  const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
  const rows = [];
  table.querySelectorAll('tbody tr').forEach(r => {
    const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
    if (cells.length >= 4) rows.push(cells);
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
    body = json.dumps({"action": action, "args": args, "session": session}).encode()
    req = urllib.request.Request(f"{DAEMON}/command", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def evaluate(code, session):
    res = call("evaluate", {"code": code}, session)
    if not res.get("ok"):
        return {"error": res.get("error", {}).get("message", "unknown")}
    data = res["data"]
    if isinstance(data, dict) and data.get("type") == "string":
        try:
            return json.loads(data["value"])
        except Exception:
            return {"raw": data.get("value")}
    return data


def sanitize_header(h):
    """Make header CSV-friendly (drop newlines, keep Chinese)."""
    if not h:
        return ""
    return h.replace("\n", " ").replace("\r", " ").strip()


def parse_row(headers, cells):
    """Map cells to header-named fields. Skip fully-empty rows."""
    if not any(c.strip() for c in cells):
        return None
    row = {}
    for i, h in enumerate(headers):
        if i >= len(cells):
            break
        # Drop the trailing 操作 column (always empty action buttons)
        if h in ("操作", ""):
            continue
        row[sanitize_header(h)] = cells[i]
    # Extract rank from first column (排名 / 达人信息)
    rank = cells[0].strip() if cells else ""
    row["rank"] = rank
    # Extract creator name + ID from the 达人 / 达人信息 column (multi-line)
    creator_field = row.get("达人") or row.get("达人信息") or ""
    parts = [p.strip() for p in creator_field.split("\n") if p.strip()]
    row["creator_name"] = parts[0] if parts else ""
    row["creator_id"] = ""
    row["creator_category"] = ""
    for p in parts[1:]:
        if p.startswith("ID"):
            row["creator_id"] = p.replace("ID：", "").replace("ID:", "").strip()
        elif not row["creator_category"] and p not in ("男", "女") and "%" not in p and "-" not in p[:3] and not p[0].isdigit():
            row["creator_category"] = p
    row["country"] = row.get("国家/地区", "").strip()
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
    p.add_argument("--url", help="Custom FastMoss creator ranking URL (overrides --ranking)")
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

    nav = call("navigate", {"url": url, "newTab": True, "group_title": "fastmoss-creators"}, args.session)
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

    # Build field list: standard prefix + dynamic headers from data
    base_fields = ["page", "ranking", "rank", "creator_name", "creator_id", "creator_category", "country"]
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
