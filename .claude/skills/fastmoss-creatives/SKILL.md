---
name: fastmoss-creatives
description: "Scrape and analyze FastMoss (fastmoss.com) TikTok creative/video rankings — 热门视频 / 热门音乐 / 热门标签 — with country filter; AI带货视频榜 is card-based and noted but not scripted. Use when the user asks to extract FastMoss video/music/hashtag trend data, find trending creative materials, identify breakout tracks or hashtags, or run any data pull from the 视频&素材 section of fastmoss.com. Drives the user's real logged-in browser via BrowserSkill. Self-contained — includes Windows/bash environment notes and the analysis report recipe. Sister skills: fastmoss-products, fastmoss-creators, fastmoss-shops, fastmoss-ads, fastmoss-livestreams."
---

# fastmoss-creatives

End-to-end FastMoss **creative material ranking** scraper + analyzer. Uses `bsk` (BrowserSkill CLI) to drive the user's logged-in browser, extracts rows into CSVs, and ships an aggregation script + Markdown report template that produces an analysis report. Scope: the 视频&素材 section of fastmoss.com (3 table-based rankings; AI带货视频榜 is card-based and noted below). For products, shops, creators, ads, or live streams, use the corresponding sister skill.

## Prerequisites

1. BrowserSkill daemon healthy:
   ```bash
   bsk doctor --json
   # expect: {"ok": true, "daemon": {"running": true}, "extension": {"installed": true, "connected": true}}
   ```
   If not healthy: start daemon with `bsk daemon start`.

2. User is **logged in** to fastmoss.com in their browser (this skill reuses their session — no auth).

3. **Read `references/environment.md`** before writing new shell or `evaluate` JS.

## Creative ranking URLs

| Ranking key | 中文 | URL | Schema |
|---|---|---|---|
| `video` | 热门视频 | `https://www.fastmoss.com/zh/media-source/video` | table |
| `song` | 热门音乐 | `https://www.fastmoss.com/zh/media-source/song` | table |
| `hashtag` | 热门标签 | `https://www.fastmoss.com/zh/media-source/hashtag` | table |
| `top-ai-videos` | AI带货视频榜 | `https://www.fastmoss.com/zh/media-source/top-ai-videos` | cards (not scripted) |

Use `/zh/` (Chinese) locale. Site is a NUXT/Vue SPA — always wait for hydration (`--nav-sleep 6`+).

## Per-ranking column schemas

| Ranking | Header columns |
|---|---|
| `video` | 视频内容, 达人信息, 达人粉丝数, 发布时间, 播放量, 点赞数, 互动率 |
| `song` | 音乐, 达人, 播放量 |
| `hashtag` | 标签, 预览, 曝光量, 关联视频数 |

The 视频内容/音乐/标签 columns are multi-line text; the scraper pre-parses the primary entity name into `entity_name` and keeps the raw cell under its original header.

## Quick start

```bash
# Step 1: Scrape one ranking (Top N pages)
python <path-to-skill>/scripts/creative_scraper.py \
    --ranking video --pages 5 --out <out-dir>/videos.csv
python <path-to-skill>/scripts/creative_scraper.py \
    --ranking song --pages 3 --out <out-dir>/songs.csv
python <path-to-skill>/scripts/creative_scraper.py \
    --ranking hashtag --pages 3 --out <out-dir>/hashtags.csv

# Step 2: Multi-country comparison on one ranking
python <path-to-skill>/scripts/creative_filtered.py \
    --ranking video --country 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 \
    --out <out-dir>/videos_by_country.csv

# Step 3: Aggregate the per-ranking CSVs into a Markdown report
python <path-to-skill>/scripts/analyze.py \
    --video <out-dir>/videos.csv \
    --song <out-dir>/songs.csv \
    --hashtag <out-dir>/hashtags.csv \
    --out-md <report>.md
```

`<path-to-skill>` is wherever this skill is installed (typically `.claude/skills/fastmoss-creatives` inside the project, or `~/.claude/skills/fastmoss-creatives` for a user-level install). Run any script with `--help` for the full arg list.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/creative_scraper.py` | Top-N paginating scraper, any of the 3 table rankings (schema auto-detected from `<thead>`) |
| `scripts/creative_filtered.py` | Multi-country filter + paginate |
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
5. **Schema differs between rankings** — `creative_scraper.py` reads `<thead>` dynamically. Don't assume a fixed schema in downstream code; iterate over `dict.keys()`.
6. **`jq` may not be installed** — decode screenshots manually with `python -c` + `base64`.
7. **Python defaults to a locale-specific encoding on Windows** — always `open(..., encoding='utf-8-sig')` when reading the produced CSVs.
8. **AI带货视频榜 has no `<table>`** — it's a card grid. Not covered by the bundled scraper. Write a custom evaluate per `references/environment.md` if needed.

## CSV output schema

Base columns (always present):
```
page, ranking, rank, entity_name, country
```
Plus one column per `<thead>` header (Chinese, kept as-is). All CSVs are `utf-8-sig` (BOM) for Excel.

When using `creative_filtered.py`, one extra column is prepended:
```
filter_country
```

## Session hygiene

- Default session `"fastmoss-creatives"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- At task end: `bsk session stop fastmoss-creatives`.
- All bundled scripts use `tab create` on first navigate so they work whether or not the session pre-exists.
