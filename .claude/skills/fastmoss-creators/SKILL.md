---
name: fastmoss-creators
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok creator/influencer rankings — 涨粉达人榜 / 带货达人榜 / 蓝V达人榜 / 热门达人榜 / 黑马达人榜 — with time-window (日/周/月榜) and country filters. Use when the user asks to extract FastMoss creator data, compare creator markets by country, find cross-ranking creators, identify breakout creators via 黑马榜, or run any data pull from the 达人 section of fastmoss.com. Includes 达人搜索 entry point. Drives the user's real logged-in browser via kimi-webbridge. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-shops, fastmoss-ads, fastmoss-creatives, fastmoss-livestreams."
---

# fastmoss-creators

End-to-end FastMoss **creator ranking** scraper + analyzer. Uses `kimi-webbridge` to drive the user's logged-in browser, extracts creator rows into CSVs, and ships an aggregation script + Markdown report template that produces an analysis report. Scope: the 达人 section of fastmoss.com (5 rankings + creator search). For products, shops, ads, videos, or live streams, use the corresponding sister skill.

## Prerequisites

1. Kimi WebBridge daemon healthy:
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   # expect: {"running": true, "extension_connected": true}
   ```
   If not healthy: invoke `Skill(kimi-webbridge)` and follow `references/operations.md`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS — Windows + bash + no-jq + heredoc-escaping rules all live there. Cost of skipping: silent failures that look like daemon bugs.

## Creator ranking URLs

| Ranking key | 中文 | URL |
|---|---|---|
| `fans` | 涨粉达人榜 | `https://www.fastmoss.com/zh/influencer/tiktok/fans` |
| `commerceTop` | 带货达人榜 | `https://www.fastmoss.com/zh/influencer/tiktok/commerceTop` |
| `blue-v` | 蓝V达人榜 | `https://www.fastmoss.com/zh/influencer/tiktok/blue-v` |
| `popular` | 热门达人榜 | `https://www.fastmoss.com/zh/influencer/tiktok/popular` |
| `potentialTop` | 黑马达人榜 | `https://www.fastmoss.com/zh/influencer/tiktok/potentialTop` |
| (search) | 达人搜索 | `https://www.fastmoss.com/zh/influencer/search?shop_window=1` |

Use `/zh/` (Chinese) locale. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 6`+).

## Per-ranking column schemas

Each ranking has a different metric column set. The scraper reads `<thead>` dynamically and writes one CSV column per header, so the schema is captured automatically.

| Ranking | Header columns (after rank/creator/country) |
|---|---|
| `fans` | 粉丝变化量, 粉丝数, 涨粉率, 作品数 |
| `commerceTop` | 总粉丝数, 带货商品数, 带货总GMV |
| `blue-v` | 粉丝变化量, 粉丝数, 点赞增量 |
| `popular` | 总粉丝数, 总作品数, 点赞增量 |
| `potentialTop` | 带货品类, 潜力指数, 带货总GMV, 视频发布量, 平均视频播放量, 总销量 |

The 达人 / 达人信息 column is multi-line text (name + `ID：xxx` + category). The scraper pre-parses into `creator_name`, `creator_id`, `creator_category` for easier analysis.

## Quick start

```bash
# Step 1: Scrape one ranking (Top N pages)
python <path-to-skill>/scripts/creator_scraper.py \
    --ranking fans --pages 5 --out <out-dir>/fans.csv
python <path-to-skill>/scripts/creator_scraper.py \
    --ranking commerceTop --pages 5 --out <out-dir>/commerce.csv

# Step 2: Multi-country comparison on one ranking
python <path-to-skill>/scripts/creator_filtered.py \
    --ranking fans --country 美国,印度尼西亚,泰国,马来西亚 \
    --time 周榜 --pages 3 \
    --out <out-dir>/fans_by_country.csv

# Step 3: Aggregate the per-ranking CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --fans <out-dir>/fans.csv \
    --commerce <out-dir>/commerce.csv \
    --blue-v <out-dir>/blue-v.csv \
    --popular <out-dir>/popular.csv \
    --horse <out-dir>/horse.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-creators` inside the project, or `~/.claude/skills/fastmoss-creators` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/creator_scraper.py` | Top-N paginating scraper, any of the 5 rankings (schema auto-detected from `<thead>`) |
| `scripts/creator_filtered.py` | Multi-country or multi-time-window filter + paginate |
| `scripts/analyze.py` | Aggregate CSVs → crosstabs (stdout) or full Markdown report (template-driven) |

## References (read on demand)

| File | When to read |
|---|---|
| `references/environment.md` | Before writing any new shell or `evaluate` JS — Windows/bash/jq/heredoc rules (mirrors fastmoss-products' version) |
| `references/analysis_recipe.md` | The Markdown template `analyze.py` fills. Read to understand the report structure or to extend it |

## Filter label vocabularies

### Time windows (which appear depends on ranking)

| Label | Value | Where it appears |
|---|---|---|
| `日榜` | 1 | fans, commerceTop, blue-v, popular |
| `周榜` | 2 | all rankings |
| `月榜` | 3 | all rankings |
| `近28天` | 1 | potentialTop (instead of 日榜) |

### Countries (16 markets)

`--country <中文,comma-separated>`: `全部`, `美国`, `印度尼西亚`, `英国`, `越南`, `泰国`, `马来西亚`, `菲律宾`, `西班牙`, `墨西哥`, `德国`, `法国`, `意大利`, `巴西`, `日本`, `新加坡`.

Same vocabulary as fastmoss-products.

## Critical gotchas (each cost real time on first run)

Full details in `references/environment.md`. Summary:

1. **@e refs from `snapshot` go stale after every navigation** → `"No node with given id found"`. Bundled scripts click by text via `evaluate`, never @e refs.
2. **Bash heredoc + JS regex = `"Invalid regular expression: missing /"`** — heredoc eats a backslash layer. Use `.split('\n')` over `.replace(/\n+/g, ...)`.
3. **Page 1 of ranking tables has an empty filler row at top** — `parse_row` filters it (`country` empty AND `creator_name` empty → drop).
4. **SPA hydration lag** — creator pages may need slightly longer waits than product pages (6s default vs 5s). Too fast → 0 rows.
5. **Time filter labels vary by ranking** (`日榜` vs `近28天`) — pass the label you see on the page; the bundled click script matches by exact text.
6. **Schema differs between rankings** — `creator_scraper.py` reads `<thead>` dynamically so the CSV column set varies by ranking. Don't assume a fixed schema in your downstream code; iterate over `dict.keys()`.
7. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
8. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.

## CSV output schema

Base columns (always present):
```
page, ranking, rank, creator_name, creator_id, creator_category, country
```
Plus one column per `<thead>` header (Chinese, kept as-is). The 达人/达人信息 column is duplicated raw under its original header for traceability. All CSVs are `utf-8-sig` (BOM) for Excel.

When using `creator_filtered.py`, two extra columns are prepended:
```
filter_country, filter_time
```

## Session hygiene

- Default session `"fastmoss-creators"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `curl -d '{"action":"close_session","args":{},"session":"fastmoss-creators"}' http://127.0.0.1:10086/command`.
- All bundled scripts use `newTab:True` on first navigate so they work whether or not the session pre-exists.

## 达人搜索 (creator search) — not scripted

The search page (`/zh/influencer/search`) takes free-text input and returns creator cards, not a table. Not covered by the bundled scripts. To scrape it, write a custom evaluate that:
1. Fills the search box (`input[placeholder*=搜索]` or text-match).
2. Waits for result cards.
3. Extracts card data via DOM queries.

Use `references/environment.md` rules when writing that JS.
