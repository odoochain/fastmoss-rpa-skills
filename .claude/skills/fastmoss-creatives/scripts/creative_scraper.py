"""FastMoss creative material ranking scraper via kimi-webbridge.

Generic paginating scraper for any of the 3 table-based creative ranking
pages on fastmoss.com. Reads thead headers dynamically.

Ranking URLs:
    video   https://www.fastmoss.com/zh/media-source/video
    song    https://www.fastmoss.com/zh/media-source/song
    hashtag https://www.fastmoss.com/zh/media-source/hashtag

Usage:
    python creative_scraper.py --ranking video --pages 5 --out <path>/videos.csv
    python creative_scraper.py --ranking song --pages 3 --out <path>/songs.csv
    python creative_scraper.py --ranking hashtag --pages 3 --out <path>/hashtags.csv
    python creative_scraper.py --url <custom-url> --pages 3 --out <path>/custom.csv
    python creative_scraper.py --help
"""
import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

DAEMON = "http://127.0.0.1:10086"
DEFAULT_SESSION = "fastmoss-creatives"

RANKINGS = {
    "video":   "https://www.fastmoss.com/zh/media-source/video",
    "song":    "https://www.fastmoss.com/zh/media-source/song",
    "hashtag": "https://www.fastmoss.com/zh/media-source/hashtag",
}

ENTITY_HEADERS = {
    "video": "视频内容",
    "song": "音乐",
    "hashtag": "标签",
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
        if (cells.length >= 3) rs.push(cells);
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
    if not h:
        return ""
    return h.replace("\n", " ").replace("\r", " ").strip()


def parse_entity_name(cell):
    if not cell:
        return ""
    first_line = cell.split("\n")[0].strip()
    return first_line[:120]


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
    p.add_argument("--url", help="Custom FastMoss creative ranking URL (overrides --ranking)")
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

    nav = call("navigate", {"url": url, "newTab": True, "group_title": "fastmoss-creatives"}, args.session)
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
