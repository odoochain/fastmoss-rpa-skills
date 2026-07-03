---
name: fastmoss-products
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok Shop PRODUCT rankings — 新品榜 / 销量榜 / 热推榜 / 视频商品榜 — with country/category/shop-type filters, plus single-shop new-listing cadence tracking. Use when the user asks to extract FastMoss product ranking data, compare TikTok Shop markets, filter rankings by country or category, track a shop's new-product rhythm, generate a multi-dimensional product analysis report, or run any data pull from the 商品 section of fastmoss.com. Drives the user's real logged-in browser via kimi-webbridge. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-shops, fastmoss-creators, fastmoss-ads, fastmoss-creatives, fastmoss-livestreams (each covers a different FastMoss section)."
---

# fastmoss-products

End-to-end FastMoss **product ranking** scraper + analyzer. Uses `kimi-webbridge` to drive the user's logged-in browser, extracts product rows into CSVs, and ships an aggregation script + Markdown report template that produces an analysis report. Scope: the 商品 section of fastmoss.com (product rankings + a single shop's product-list cadence). For shop-level analytics, creator analytics, ads, videos, or live streams, use the corresponding sister skill.

**Self-contained**: includes its own environment notes (`references/environment.md`) and analysis recipe (`references/analysis_recipe.md`). Paths in examples use placeholders (`<your-out-dir>/`, `<your-report>.md`) — pass any path you like via `--out`.

## Prerequisites

1. Kimi WebBridge daemon healthy:
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   # expect: {"running": true, "extension_connected": true}
   ```
   If not healthy: invoke `Skill(kimi-webbridge)` and follow `references/operations.md`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS — Windows + bash + no-jq + heredoc-escaping rules all live there. Cost of skipping: silent failures that look like daemon bugs.

## Project flow (typical)

1. **Scrape** → CSVs (paths you choose via `--out`)
2. **Analyze** → Markdown report via the recipe template
3. **Decide** → write insights / actions

The three scraping scripts and the analyzer cover the standard flow. Any FastMoss ranking page that uses the standard table layout (新品榜/销量榜/热推榜/视频商品榜) works.

## Quick start

All `--out` paths below are illustrative — pick whatever directory layout suits your project.

```bash
# Step 1: Top N from any ranking page
python <path-to-skill>/scripts/fastmoss_scraper.py \
    --url https://www.fastmoss.com/zh/e-commerce/newProducts \
    --pages 5 --out <out-dir>/top50.csv

# Step 2a: Multi-country comparison (writes one CSV per country + a combined file)
python <path-to-skill>/scripts/fastmoss_filtered.py \
    --filter-type country --labels 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 --out <out-dir>/by_country.csv

# Step 2b: Multi-category comparison
python <path-to-skill>/scripts/fastmoss_filtered.py \
    --filter-type category --labels 美妆个护,女装与女士内衣,保健 \
    --pages 3 --out <out-dir>/by_category.csv

# Step 2c: Shop listing-cadence pull (need shop numeric ID — see "Discover shop ID" below)
python <path-to-skill>/scripts/shop_scraper.py \
    --shop-id <shop-id> --shop-name <shop-name> \
    --pages 4 --out <out-dir>/shop_<name>.csv

# Step 3: Aggregate the CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --top50 <out-dir>/top50.csv \
    --by-country <out-dir>/by_country.csv \
    --by-category <out-dir>/by_category.csv \
    --shop <out-dir>/shop_<name>.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-products` inside the project, or `~/.claude/skills/fastmoss-products` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fastmoss_scraper.py` | Top-N paginating scraper, any ranking page |
| `scripts/fastmoss_filtered.py` | Country/category/shop-type filter + paginate, multi-label |
| `scripts/shop_scraper.py` | Single shop's product list with `listed_at` for cadence |
| `scripts/analyze.py` | Aggregate CSVs → crosstabs (stdout) or full Markdown report (template-driven) |

## References (read on demand)

| File | When to read |
|---|---|
| `references/environment.md` | Before writing any new shell or `evaluate` JS — Windows/bash/jq/heredoc rules |
| `references/analysis_recipe.md` | The Markdown template `analyze.py` fills. Read to understand the report structure or to extend it |

## Ranking page URLs

| Page | URL |
|---|---|
| 新品榜 | `https://www.fastmoss.com/zh/e-commerce/newProducts` |
| 销量榜 | `https://www.fastmoss.com/zh/e-commerce/hotProducts` |
| 热推榜 | `https://www.fastmoss.com/zh/e-commerce/popularProducts` |
| 视频商品榜 | `https://www.fastmoss.com/zh/e-commerce/videoProducts` |
| Shop detail | `https://www.fastmoss.com/zh/shop-marketing/detail/{shopId}` |

Use `/zh/` (Chinese) locale for richest data. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 5`+).

## Filter label vocabularies

`--filter-type country --labels <中文,comma-separated>`:
`全部`, `美国`, `印度尼西亚`, `英国`, `越南`, `泰国`, `马来西亚`, `菲律宾`, `西班牙`, `墨西哥`, `德国`, `法国`, `意大利`, `巴西`, `日本`, `新加坡`.

`--filter-type category --labels <中文>` (after `展开`):
`美妆个护`, `女装与女士内衣`, `保健`, `时尚配件`, `运动与户外`, `手机与数码`, `居家日用`, `食品饮料`, `汽车与摩托车`, `男装与男士内衣`, `穆斯林时尚`, `电脑办公`, etc.

`--filter-type shop_type --labels <中文>`: `全部`, `跨境店`, `本土店`.

## Discover a shop's numeric ID

Run a one-shot `evaluate` against any ranking page that shows the shop:

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"evaluate","args":{"code":"JSON.stringify(Array.from(document.querySelectorAll(\"a[href*=\\\"/shop-marketing/detail/\\\"]\")).slice(0,5).map(a=>({shop:a.innerText.split(\"\\n\")[0], href:a.href})))"},"session":"fastmoss-products"}'
```

Extract the trailing digits from any `href`. Pass via `--shop-id` to `shop_scraper.py`.

## Critical gotchas (each cost real time on first run)

Full details in `references/environment.md`. Summary:

1. **@e refs from `snapshot` go stale after every navigation** → `"No node with given id found"`. Bundled scripts click by text via `evaluate`, never @e refs.
2. **Bash heredoc + JS regex = `"Invalid regular expression: missing /"`** — heredoc eats a backslash layer. Use `.split('\n')` over `.replace(/\n+/g, ...)`.
3. **Page 1 of ranking tables has an empty filler row at top** — `parse_row` filters it (`product_name` empty → drop).
4. **SPA hydration lag** — wait ≥5s after navigate, ≥3.5s between pages. Too fast → 0 rows.
5. **`jq` may not be installed** — the kimi-webbridge `screenshot.sh` helper depends on it. Decode screenshots manually with `python -c` + `base64`.
6. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.

## CSV output schema

Ranking CSVs share these columns:
```
page, rank, product_name, price, listed_at, country,
shop, shop_total_sales, category, commission,
sales_period, gmv_period, total_sales, total_gmv
```
Shop CSV (different table):
```
page, shop, product_name, price, country, category,
listed_at, commission, sales_28d, gmv_28d
```
All CSVs are `utf-8-sig` (BOM) for Excel.

## Session hygiene

- Default session `"fastmoss-products"` for all calls (isolated tab group from sister skills' sessions like `fastmoss-shops`, `fastmoss-creators`). Override with `--session` if needed.
- At task end: `curl -d '{"action":"close_session","args":{},"session":"fastmoss-products"}' http://127.0.0.1:10086/command`.
- All bundled scripts use `newTab:True` on first navigate so they work whether or not the session pre-exists.
