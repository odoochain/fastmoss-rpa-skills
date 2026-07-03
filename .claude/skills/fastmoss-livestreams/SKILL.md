---
name: fastmoss-livestreams
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok livestream rankings — TT直播榜 / 直播爆品榜 / 直播带货达人榜 — with country filter; 直播搜索 entry point noted but not scripted. Use when the user asks to extract FastMoss livestream data, compare live markets by country, find breakout live products via 爆品榜, identify top live-commerce creators, or run any data pull from the 直播 section of fastmoss.com. Drives the user's real logged-in browser via kimi-webbridge. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-creators, fastmoss-shops, fastmoss-ads, fastmoss-creatives."
---

# fastmoss-livestreams

End-to-end FastMoss **livestream ranking** scraper + analyzer. Uses `kimi-webbridge` to drive the user's logged-in browser, extracts rows into CSVs, and ships an aggregation script + Markdown report template that produces an analysis report. Scope: the 直播 section of fastmoss.com (3 rankings + live search). For products, shops, creators, ads, or videos, use the corresponding sister skill.

## Prerequisites

1. Kimi WebBridge daemon healthy:
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   # expect: {"running": true, "extension_connected": true}
   ```
   If not healthy: invoke `Skill(kimi-webbridge)` and follow `references/operations.md`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS.

## Livestream ranking URLs

| Ranking key | 中文 | URL |
|---|---|---|
| `tiktok` | TT直播榜 | `https://www.fastmoss.com/zh/live/tiktok` |
| `hotProduct` | 直播爆品榜 | `https://www.fastmoss.com/zh/live/hotProduct` |
| `liveCommerce` | 直播带货达人榜 | `https://www.fastmoss.com/zh/live/liveCommerce` |
| (search) | 直播搜索 | `https://www.fastmoss.com/zh/live/search` |

Use `/zh/` (Chinese) locale. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 6`+).

## Per-ranking column schemas

Each ranking has a different schema (live room / product / creator centric). The scraper reads `<thead>` dynamically and writes one CSV column per header.

| Ranking | Header columns (after rank/main entity) |
|---|---|
| `tiktok` | 直播间, 主播信息, 开播时间, 直播时长, 总销量, 总销售额, 累计观看人次, 在线人数峰值 |
| `hotProduct` | 商品, 所属店铺, 直播销量, 直播GMV, 直播场次, Top销量直播间 |
| `liveCommerce` | 达人, 粉丝数, 直播销量, 直播GMV, 动销商品数, TopGMV直播间 |

The 直播间/商品/达人 columns are multi-line text; the scraper pre-parses the primary entity name into `entity_name` and keeps the raw cell under its original header.

## Quick start

```bash
# Step 1: Scrape one ranking (Top N pages)
python <path-to-skill>/scripts/live_scraper.py \
    --ranking tiktok --pages 5 --out <out-dir>/tiktok.csv
python <path-to-skill>/scripts/live_scraper.py \
    --ranking hotProduct --pages 5 --out <out-dir>/hot_product.csv
python <path-to-skill>/scripts/live_scraper.py \
    --ranking liveCommerce --pages 5 --out <out-dir>/live_commerce.csv

# Step 2: Multi-country comparison on one ranking
python <path-to-skill>/scripts/live_filtered.py \
    --ranking tiktok --country 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 \
    --out <out-dir>/tiktok_by_country.csv

# Step 3: Aggregate the per-ranking CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --tiktok <out-dir>/tiktok.csv \
    --hot-product <out-dir>/hot_product.csv \
    --live-commerce <out-dir>/live_commerce.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-livestreams` inside the project, or `~/.claude/skills/fastmoss-livestreams` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/live_scraper.py` | Top-N paginating scraper, any of the 3 rankings (schema auto-detected from `<thead>`) |
| `scripts/live_filtered.py` | Multi-country filter + paginate |
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
4. **SPA hydration lag** — live pages may need slightly longer waits than product pages (6s default). Too fast → 0 rows.
5. **Schema differs between rankings** — `live_scraper.py` reads `<thead>` dynamically. Don't assume a fixed schema in downstream code; iterate over `dict.keys()`.
6. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
7. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.

## CSV output schema

Base columns (always present):
```
page, ranking, rank, entity_name, country
```
Plus one column per `<thead>` header (Chinese, kept as-is). All CSVs are `utf-8-sig` (BOM) for Excel.

When using `live_filtered.py`, one extra column is prepended:
```
filter_country
```

## Session hygiene

- Default session `"fastmoss-livestreams"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `curl -d '{"action":"close_session","args":{},"session":"fastmoss-livestreams"}' http://127.0.0.1:10086/command`.
- All bundled scripts use `newTab:True` on first navigate so they work whether or not the session pre-exists.

## 直播搜索 (live search) — not scripted

The search page (`/zh/live/search`) takes free-text input and returns live room cards, not a table. Not covered by the bundled scripts. Write a custom evaluate per the pattern documented in `references/environment.md`.
