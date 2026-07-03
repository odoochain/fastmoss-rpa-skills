"""FastMoss creator ranking scraper with time/country filters applied.

Clicks the filter radio/chip by text label (no @e refs — they go stale
after navigation), then paginates and extracts. Useful for multi-country
comparison on one ranking, or for switching between 日榜/周榜/月榜.

Usage:
    # Multi-country on one ranking (writes one CSV per country + combined)
    python creator_filtered.py --ranking fans \\
        --country 美国,印度尼西亚,泰国,马来西亚 --pages 3 \\
        --out <out-dir>/fans_by_country.csv

    # One country, custom time window
    python creator_filtered.py --ranking commerceTop \\
        --country 美国 --time 周榜 --pages 3 \\
        --out <out-dir>/commerce_us_weekly.csv

Filters supported (all clicked by text via evaluate):
    --time <日榜|周榜|月榜|近28天>   (which option appears depends on ranking)
    --country <中文 labels>          (16 markets, same as fastmoss-products)

See SKILL.md for the full country label vocabulary.
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
from creator_scraper import call, evaluate, scrape_current, sanitize_header, RANKINGS  # noqa: E402

DEFAULT_SESSION = "fastmoss-creators"

CLICK_TIME_JS = """
((label) => {
  const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
  const t = radios.find(r => {
    const parent = r.closest('label') || r.parentElement;
    return parent && parent.innerText.trim() === label;
  });
  if (!t) return JSON.stringify({clicked: false, reason: 'time label not found'});
  t.click();
  return JSON.stringify({clicked: true, value: t.value});
})(%s)
"""

CLICK_COUNTRY_JS = """
((label) => {
  const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
  const t = radios.find(r => {
    const parent = r.closest('label') || r.parentElement;
    return parent && parent.innerText.includes(label);
  });
  if (!t) return JSON.stringify({clicked: false, reason: 'country not found'});
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


def click_filter(js_template, label, session):
    return evaluate(js_template % json.dumps(label, ensure_ascii=False), session)


def scrape_one(ranking_key, country_label, time_label, pages, session, nav_sleep, page_sleep):
    url = RANKINGS[ranking_key]
    call("navigate", {"url": url, "newTab": False}, session)
    time.sleep(nav_sleep)
    if time_label:
        click = click_filter(CLICK_TIME_JS, time_label, session)
        print(f"[{ranking_key}/{country_label}/{time_label}] time click: {click}")
        time.sleep(nav_sleep)
    if country_label:
        click = click_filter(CLICK_COUNTRY_JS, country_label, session)
        print(f"[{ranking_key}/{country_label}/{time_label}] country click: {click}")
        time.sleep(nav_sleep)
    rows_out = []
    headers_seen = None
    for p in range(pages):
        rows, meta = scrape_current(session)
        if not headers_seen and "headers" in meta:
            headers_seen = meta["headers"]
        if p == 0 and rows:
            countries = {r.get("country", "") for r in rows}
            print(f"[{ranking_key}/{country_label} page {p+1}] rows={len(rows)} countries={countries}")
        else:
            print(f"[{ranking_key}/{country_label} page {p+1}] rows={len(rows)}")
        for r in rows:
            r["filter_country"] = country_label or "(default)"
            r["filter_time"] = time_label or "(default)"
            r["ranking"] = ranking_key
            r["page"] = p + 1
            rows_out.append(r)
        if p < pages - 1:
            evaluate(NEXT_PAGE_JS, session)
            time.sleep(page_sleep)
    return rows_out, headers_seen


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ranking", required=True, choices=list(RANKINGS.keys()),
                   help="Creator ranking to scrape (one of: %s)" % ", ".join(RANKINGS))
    p.add_argument("--country", default="",
                   help="Comma-separated country labels (e.g. '美国,印度尼西亚,泰国,马来西亚'). Empty = no country filter.")
    p.add_argument("--time", default="",
                   help="Time-window label (日榜/周榜/月榜/近28天). Empty = no time filter.")
    p.add_argument("--pages", type=int, default=3, help="Pages per filter combination (default: 3)")
    p.add_argument("--out", required=True, help="Combined output CSV path (per-country CSVs also written next to it)")
    p.add_argument("--session", default=DEFAULT_SESSION, help=f"Browser session (default: {DEFAULT_SESSION})")
    p.add_argument("--nav-sleep", type=float, default=6.0)
    p.add_argument("--page-sleep", type=float, default=3.5)
    args = p.parse_args()

    countries = [s.strip() for s in args.country.split(",") if s.strip()] if args.country else [""]
    combined_path = Path(args.out)
    per_run_dir = combined_path.parent
    per_run_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    headers_seen = None
    for country in countries:
        rows, hs = scrape_one(args.ranking, country, args.time, args.pages,
                              args.session, args.nav_sleep, args.page_sleep)
        if hs and not headers_seen:
            headers_seen = hs
        if rows and len(countries) > 1:
            suffix = country or "all"
            out = per_run_dir / f"{combined_path.stem}_{suffix}{combined_path.suffix}"
            write_csv(out, rows)
            print(f"[{country or 'all'}] saved {len(rows)} -> {out}")
        all_rows.extend(rows)

    if all_rows:
        write_csv(combined_path, all_rows)
        print(f"[combined] {len(all_rows)} -> {combined_path}")


def write_csv(path, rows):
    base_fields = ["page", "ranking", "filter_country", "filter_time",
                   "rank", "creator_name", "creator_id", "creator_category", "country"]
    extra_fields = []
    seen = set(base_fields)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                extra_fields.append(k)
                seen.add(k)
    fields = base_fields + extra_fields
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
