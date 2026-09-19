---
name: fastmoss-ads
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok ads trend rankings — 标签洞察 / 关键词趋势 / 热门品类趋势 — with country filter. The 3 card-style ads pages (电商广告 / 种草广告 / 广告主洞察) and 广告案例搜索 are noted but not scripted. Use when the user asks to extract FastMoss ads trend data, find trending ad keywords/tags/categories, identify breakout ad creative categories, or run any data pull from the 广告引擎 section's ranking pages of fastmoss.com. Drives the user's real logged-in browser via BrowserSkill. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-creators, fastmoss-shops, fastmoss-creatives, fastmoss-livestreams."
---

# fastmoss-ads

End-to-end FastMoss **ads trend ranking** scraper + analyzer. Uses `bsk` (BrowserSkill CLI) to drive the user's logged-in browser, extracts rows into CSVs, and ships an aggregation script + Markdown report template. Scope: 3 table-based trend rankings in the 广告引擎 section of fastmoss.com. The 3 card-based ad search pages (电商广告 / 种草广告 / 广告主洞察) are out of scope — they're filter-search interfaces, not rankings. For products, creators, shops, videos, or live streams, use the corresponding sister skill.

## Prerequisites

1. BrowserSkill daemon healthy:
   ```bash
   bsk doctor --json
   # expect: {"ok": true, "daemon": {"running": true}, "extension": {"installed": true, "connected": true}}
   ```
   If not healthy: start daemon with `bsk daemon start`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS.

## Ads ranking URLs

| Ranking key | 中文 | URL | Schema |
|---|---|---|---|
| `tag` | 标签洞察 | `https://www.fastmoss.com/zh/creativecenter/insightTag` | table |
| `keyword` | 关键词趋势 | `https://www.fastmoss.com/zh/creativecenter/keyword-trends` | table |
| `category` | 热门品类趋势 | `https://www.fastmoss.com/zh/creativecenter/product-category-trends` | table |
| (not scripted) | 电商广告 | `https://www.fastmoss.com/zh/creativecenter/search` | cards |
| (not scripted) | 种草广告 | `https://www.fastmoss.com/zh/creativecenter/seed` | cards |
| (not scripted) | 广告主洞察 | `https://www.fastmoss.com/zh/creativecenter/advertiser` | cards |

Use `/zh/` (Chinese) locale. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 6`+).

## Per-ranking column schemas

| Ranking | Header columns |
|---|---|
| `tag` | 标签, 预览, 曝光量, 关联视频数 |
| `keyword` | 排名, 关键词, 趋势, 热度指数, 曝光量, 点赞量, 分享, 评论 |
| `category` | 排名, 热门品类, 趋势, 热度指数, 曝光量, 点赞量, 分享, 评论 |

The 标签/关键词/热门品类 columns are the primary entity. The scraper pre-parses into `entity_name` and keeps the raw cell under its original header.

## Quick start

```bash
# Step 1: Scrape one ranking (Top N pages)
python <path-to-skill>/scripts/ads_scraper.py \
    --ranking tag --pages 5 --out <out-dir>/tags.csv
python <path-to-skill>/scripts/ads_scraper.py \
    --ranking keyword --pages 5 --out <out-dir>/keywords.csv
python <path-to-skill>/scripts/ads_scraper.py \
    --ranking category --pages 3 --out <out-dir>/categories.csv

# Step 2: Multi-country comparison on one ranking
python <path-to-skill>/scripts/ads_filtered.py \
    --ranking keyword --country 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 \
    --out <out-dir>/keywords_by_country.csv

# Step 3: Aggregate the per-ranking CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --tag <out-dir>/tags.csv \
    --keyword <out-dir>/keywords.csv \
    --category <out-dir>/categories.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-ads` inside the project, or `~/.claude/skills/fastmoss-ads` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/ads_scraper.py` | Top-N paginating scraper, any of the 3 trend rankings (schema auto-detected from `<thead>`) |
| `scripts/ads_filtered.py` | Multi-country filter + paginate |
| `scripts/analyze.py` | Aggregate CSVs → crosstabs (stdout) or full Markdown report (template-driven) |

## References (read on demand)

| File | When to read |
|---|---|
| `references/environment.md` | Before writing any new shell or `evaluate` JS — Windows/bash/jq/heredoc rules (mirrors fastmoss-products' version) |
| `references/analysis_recipe.md` | The Markdown template `analyze.py` fills. Read to understand the report structure or to extend it |

## Filter label vocabularies

### Countries (16 markets)

`--country <中文,comma-separated>`: `全部`, `美国`, `印度尼西亚`, `英国`, `越南`, `泰国`, `马来西亚`, `菲律宾`, `西班牙`, `墨西哥`, `德国`, `法国`, `意大利`, `巴西`, `日本`, `新加坡`.

Same vocabulary as fastmoss-products / fastmoss-creators.

## Critical gotchas (each cost real time on first run)

Full details in `references/environment.md`. Summary:

1. **@e refs from `snapshot` go stale after every navigation** → `"No node with given id found"`. Bundled scripts click by text via `evaluate`, never @e refs.
2. **Bash heredoc + JS regex = `"Invalid regular expression: missing /"`** — heredoc eats a backslash layer. Use `.split('\n')` over `.replace(/\n+/g, ...)`.
3. **`<thead>` headers may report empty via `innerText`** on first render. The bundled `EXTRACT_JS` reads `innerText || textContent` and falls back to the `title` attribute.
4. **SPA hydration lag** — pages may need slightly longer waits than product pages (6s default). Too fast → 0 rows.
5. **Schema differs between rankings** — `ads_scraper.py` reads `<thead>` dynamically. Don't assume a fixed schema in downstream code; iterate over `dict.keys()`.
6. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
7. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.
8. **3 of 6 ads pages have no `<table>`** — 电商广告 / 种草广告 / 广告主洞察 are card-based filter UIs. Not covered by the bundled scraper.

## CSV output schema

Base columns (always present):
```
page, ranking, rank, entity_name, country
```
Plus one column per `<thead>` header (Chinese, kept as-is). All CSVs are `utf-8-sig` (BOM) for Excel.

When using `ads_filtered.py`, one extra column is prepended:
```
filter_country
```

## Session hygiene

- Default session `"fastmoss-ads"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `bsk session stop fastmoss-ads`.
- All bundled scripts use `tab create` on first navigate so they work whether or not the session pre-exists.

## Ads search pages (not scripted) — design note

The 3 unscripted pages (`/search`, `/seed`, `/advertiser`) are powerful **filter-based ad listing** interfaces. They expose 16-country, scenario (爆品跟卖 / 小店广告 / 达人推广 / 返佣带货), category, time-window, ad-language, CTA, landing-page, ROAS, and many other filters. Each result is a card, not a row. To scrape them:
1. Apply filters by clicking the desired labels (text-match via evaluate).
2. Wait for cards to load.
3. Extract card data via DOM queries (`[class*=adItem]` or similar).

Use `references/environment.md` rules when writing that JS. The bundled scripts in this skill do not cover this case.
