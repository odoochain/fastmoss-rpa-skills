---
name: fastmoss-shops
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok shop rankings — 店铺销量榜 / 店铺热推榜 — with country filter, plus single-shop detail (店铺搜索 entry point noted). Use when the user asks to extract FastMoss shop data, compare shop markets by country, identify breakout shops via 热推榜 (new-creator momentum), or run any data pull from the 店铺 section of fastmoss.com. Drives the user's real logged-in browser via kimi-webbridge. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-creators, fastmoss-ads, fastmoss-creatives, fastmoss-livestreams."
---

# fastmoss-shops

End-to-end FastMoss **shop ranking** scraper + analyzer. Uses `kimi-webbridge` to drive the user's logged-in browser, extracts shop rows into CSVs, and ships an aggregation script + Markdown report template that produces an analysis report. Scope: the 店铺 section of fastmoss.com (2 rankings + shop search). For products, creators, ads, videos, or live streams, use the corresponding sister skill.

## Prerequisites

1. Kimi WebBridge daemon healthy:
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   # expect: {"running": true, "extension_connected": true}
   ```
   If not healthy: invoke `Skill(kimi-webbridge)` and follow `references/operations.md`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS — Windows + bash + no-jq + heredoc-escaping rules all live there. Cost of skipping: silent failures that look like daemon bugs.

## Shop ranking URLs

| Ranking key | 中文 | URL |
|---|---|---|
| `sales` | 店铺销量榜 | `https://www.fastmoss.com/zh/shop-marketing/tiktok` |
| `hot` | 店铺热推榜 | `https://www.fastmoss.com/zh/shop-marketing/hotTiktok` |
| (search) | 店铺搜索 | `https://www.fastmoss.com/zh/shop-marketing/search` |

Use `/zh/` (Chinese) locale. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 6`+).

## Per-ranking column schemas

Each ranking has a different metric column set. The scraper reads `<thead>` dynamically and writes one CSV column per header, so the schema is captured automatically.

| Ranking | Header columns (after rank/shop) |
|---|---|
| `sales` | 销量, 销量环比, 销售额, 销量额环比, 动销商品数, 带货达人数 |
| `hot` | 新增带货达人, 销量, 销量环比, 销售额, 销量额环比, 动销商品数 |

The 店铺 column is multi-line text (品牌 + shop name + legal entity + category + rating). The scraper pre-parses into `shop_name`, `shop_legal_name`, `shop_category`, `shop_rating` for easier analysis.

## Quick start

```bash
# Step 1: Scrape one ranking (Top N pages)
python <path-to-skill>/scripts/shop_scraper.py \
    --ranking sales --pages 5 --out <out-dir>/sales.csv
python <path-to-skill>/scripts/shop_scraper.py \
    --ranking hot --pages 5 --out <out-dir>/hot.csv

# Step 2: Multi-country comparison on one ranking
python <path-to-skill>/scripts/shop_filtered.py \
    --ranking sales --country 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 \
    --out <out-dir>/sales_by_country.csv

# Step 3: Aggregate the per-ranking CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --sales <out-dir>/sales.csv \
    --hot <out-dir>/hot.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-shops` inside the project, or `~/.claude/skills/fastmoss-shops` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/shop_scraper.py` | Top-N paginating scraper, any of the 2 rankings (schema auto-detected from `<thead>`) |
| `scripts/shop_filtered.py` | Multi-country filter + paginate |
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
3. **`<thead>` headers may report empty via `innerText`** on first render. The bundled `EXTRACT_JS` reads `innerText || textContent` and falls back to the `title` attribute — works for both shop rankings.
4. **SPA hydration lag** — shop pages may need slightly longer waits than product pages (6s default vs 5s). Too fast → 0 rows.
5. **Schema differs between rankings** — `shop_scraper.py` reads `<thead>` dynamically so the CSV column set varies by ranking. Don't assume a fixed schema in your downstream code; iterate over `dict.keys()`.
6. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
7. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.

## CSV output schema

Base columns (always present):
```
page, ranking, rank, shop_name, shop_legal_name, shop_category, shop_rating, country
```
Plus one column per `<thead>` header (Chinese, kept as-is). The 店铺 column is duplicated raw under its original header for traceability. All CSVs are `utf-8-sig` (BOM) for Excel.

When using `shop_filtered.py`, two extra columns are prepended:
```
filter_country
```

## Session hygiene

- Default session `"fastmoss-shops"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `curl -d '{"action":"close_session","args":{},"session":"fastmoss-shops"}' http://127.0.0.1:10086/command`.
- All bundled scripts use `newTab:True` on first navigate so they work whether or not the session pre-exists.

## 店铺搜索 (shop search) — not scripted

The search page (`/zh/shop-marketing/search`) takes free-text input and returns shop cards, not a table. Not covered by the bundled scripts. To scrape it, write a custom evaluate that:
1. Fills the search box (`input[placeholder*=搜索]` or text-match).
2. Waits for result cards.
3. Extracts card data via DOM queries.

Use `references/environment.md` rules when writing that JS.
