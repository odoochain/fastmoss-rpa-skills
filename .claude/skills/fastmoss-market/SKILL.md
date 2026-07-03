---
name: fastmoss-market
description: "Pull FastMoss (fastmoss.com) TikShop category-market data via the FastMoss public web API. Covers both pages in the 品类大盘 section: market-category (行业格局 scatter data — categoryDistribution API) and market-analyze (市场总览 base metrics + salesChart time-series + priceDistribution). Use when the user asks to extract FastMoss market-overview data, compare category sizes by country, find high-growth categories, build a category time-series, or run any data pull from the 品类大盘 section of fastmoss.com. Unlike the sister table-scraping skills, this skill is API-first — it uses page-context fetch() to call FastMoss JSON endpoints directly, so no DOM scraping, no pagination, no SPA-hydration waits. Drives the user's real logged-in browser via kimi-webbridge. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-creators, fastmoss-shops, fastmoss-ads, fastmoss-creatives, fastmoss-livestreams."
---

# fastmoss-market

End-to-end FastMoss **category market overview** data puller + analyzer. Uses `kimi-webbridge` to drive the user's logged-in browser, then calls FastMoss JSON APIs directly from the page context (so cookies/auth are reused). Scope: the 品类大盘 section of fastmoss.com (2 pages: 行业格局 + 市场总览). For products, creators, shops, ads, videos, or live streams, use the corresponding sister skill.

## Why API-first (not DOM scraping)

Both pages in this section are chart-based dashboards (scatter plots, time-series, etc) — there are **no `<table>` elements** to scrape. All data is loaded via these JSON endpoints:

| Endpoint | Purpose | Page |
|---|---|---|
| `GET /api/analysis/V2/categoryDistribution` | 行业格局 scatter: per-category sale amount + growth, one row per (region × category) | market-category |
| `GET /api/analysis/GoodCategory/base` | Market overview: total sales, product count, top products | market-analyze |
| `GET /api/analysis/GoodCategory/salesChart` | Daily time-series of category sales / products / creators / videos / lives | market-analyze |
| `GET /api/analysis/GoodCategory/priceDistribution` | Price-band distribution | market-analyze |
| `GET /api/analysis/GoodCategory/filterInfo` | Vocabularies: 27 category codes + 16 country codes | both |

The bundled scripts call these via page-context `fetch()` (`evaluate`), which automatically attaches the user's session cookies — no separate auth handling needed.

## Prerequisites

1. Kimi WebBridge daemon healthy:
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   # expect: {"running": true, "extension_connected": true}
   ```
   If not healthy: invoke `Skill(kimi-webbridge)` and follow `references/operations.md`.

2. User is **logged in** to fastmoss.com in their browser.

3. **Read `references/environment.md`** for Windows/bash/evaluate JS rules.

## API parameter vocabularies

### Region codes (16 markets)

`--region`: `US` (美国), `ID` (印度尼西亚), `GB` (英国), `VN` (越南), `TH` (泰国), `MY` (马来西亚), `PH` (菲律宾), `ES` (西班牙), `MX` (墨西哥), `DE` (德国), `FR` (法国), `IT` (意大利), `BR` (巴西), `JP` (日本), `SG` (新加坡), `SA` (沙特). Empty string = global / 全部.

### Category codes (`pcid` — top 27)

Run `python <path-to-skill>/scripts/fetch_filter_info.py` to dump the current full mapping. Top 10 by rank:

| pcid | 中文 | rank |
|---|---|---|
| 14 | 美妆个护 | 1 |
| 2 | 女装与女士内衣 | 6 |
| 25 | 保健 | 9 |
| 8 | 时尚配件 | 11 |
| 9 | 运动与户外 | 16 |
| 16 | 手机与数码 | 26 |
| 10 | 居家日用 | 31 |
| 24 | 食品饮料 | 36 |
| 23 | 汽车与摩托车 | 41 |
| 3 | 男装与男士内衣 | 44 |

### Time windows (`--time`)

For `categoryDistribution`:
- `--time 28d` (default) → last 28 days, no `date_value` param sent
- `--time month` → most recent month, sends `date_value=YYYY-MM`

For `base`/`salesChart`/`priceDistribution`:
- `--action 1` (default) → daily granularity

## Quick start

```bash
# Step 1: Pull the 行业格局 data (one row per category, for one country)
python <path-to-skill>/scripts/fetch_distribution.py \
    --region US --time month \
    --out <out-dir>/us_categories.csv

# Multi-country comparison: one CSV per region + combined
python <path-to-skill>/scripts/fetch_distribution.py \
    --region US,ID,TH,MY --time month \
    --out <out-dir>/categories_by_region.csv

# Step 2: Pull the 市场总览 for one region (totals + top products)
python <path-to-skill>/scripts/fetch_base.py \
    --region US \
    --out <out-dir>/us_market_base.json

# Step 3: Pull the daily sales-chart time-series
python <path-to-skill>/scripts/fetch_sales_chart.py \
    --region US \
    --out <out-dir>/us_sales_chart.csv

# Step 4: Aggregate the distribution CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --distribution <out-dir>/categories_by_region.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-market` inside the project, or `~/.claude/skills/fastmoss-market` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_filter_info.py` | Dump the current category (c_code→c_name) and country (region_code→region_name) vocabularies |
| `scripts/fetch_distribution.py` | Pull 行业格局 data — per-category sale amount + growth, multi-region support |
| `scripts/fetch_base.py` | Pull 市场总览 aggregate metrics + top products for one region |
| `scripts/fetch_sales_chart.py` | Pull daily time-series for one region (sales / products / creators / videos / lives) |
| `scripts/analyze.py` | Aggregate distribution CSVs → crosstabs (stdout) or full Markdown report (template-driven) |

## References (read on demand)

| File | When to read |
|---|---|
| `references/environment.md` | Before writing any new shell or `evaluate` JS — Windows/bash/jq/heredoc rules + the page-context `fetch()` pattern this skill relies on |
| `references/api_notes.md` | The FastMoss API contract — endpoint shapes, parameter values, gotchas. Read before extending the bundled scripts or adding new endpoints |
| `references/analysis_recipe.md` | The Markdown template `analyze.py` fills. Read to understand the report structure or to extend it |

## Critical gotchas (each cost real time on first run)

Full details in `references/environment.md` + `references/api_notes.md`. Summary:

1. **Page must be loaded before `fetch()` works** — bundled scripts navigate to `/zh/market/market-category` first so the page origin + cookies are correct. Don't skip the initial navigate.
2. **`_time` + `cnonce` query params** — anti-cache params. The bundled FETCH_JS template adds them automatically; omit if you hit a cached response.
3. **No pagination needed** — these APIs return all data in one shot. Just call once per (region, time, category) tuple.
4. **`region` empty string ≠ `region=Global`** — for the worldwide aggregate, omit the param entirely (the bundled script handles this when `--region` is empty).
5. **`date_value=YYYY-MM` for month mode** uses the most recent completed month (computed by the script — don't hardcode).
6. **`evaluate` returns strings, not parsed JSON** — the FETCH_JS template does `JSON.stringify` + the Python wrapper parses it back. Always round-trip through JSON.
7. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
8. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.

## CSV output schema — distribution (`fetch_distribution.py`)

Base columns (always present):
```
region, region_name, time_window, date_value, category_id, category_name,
category_sale_amount, category_sale_amount_show,
category_sale_amount_mom_rate, category_sale_amount_mom_rate_show,
cur_sale_amount, last_sale_amount
```
All CSVs are `utf-8-sig` (BOM) for Excel.

## CSV output schema — sales_chart (`fetch_sales_chart.py`)

```
region, dt, category_sold_count, inc_product_count,
sales_product_count, sales_author_count, sales_video_count, sales_live_count,
... (with _show variants)
```

## Session hygiene

- Default session `"fastmoss-market"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `curl -d '{"action":"close_session","args":{},"session":"fastmoss-market"}' http://127.0.0.1:10086/command`.
- The bundled scripts navigate with `newTab:True` on first call so they work whether or not the session pre-exists.
