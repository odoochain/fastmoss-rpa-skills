# AGENTS.md

## What this repo is

Browser-RPA + data analysis on [fastmoss.com](https://www.fastmoss.com) (TikTok Shop analytics). Drives the user's real logged-in Chrome/Edge via BrowserSkill — no headless browsers, no token/auth automation.

## Environment

- **Windows + bash shell.** Use forward-slash paths and `/dev/null` (not `NUL`).
- **Python 3.8+ only.** No Node.js, jq, selenium, playwright, puppeteer, ffmpeg needed.
- **BrowserSkill daemon** must be running: `bsk doctor --json` → `{"ok": true}`. Start with `bsk daemon start` if not.
- User must be logged into fastmoss.com in their browser — skills reuse that session.

## Architecture

7 skills under `.claude/skills/`, each self-contained with `SKILL.md`, `scripts/`, and `references/`:

| Skill | Module | Method |
|---|---|---|
| fastmoss-products | 商品 | DOM scrape |
| fastmoss-creators | 达人 | DOM scrape |
| fastmoss-shops | 店铺 | DOM scrape |
| fastmoss-livestreams | 直播 | DOM scrape |
| fastmoss-creatives | 视频&素材 | DOM scrape |
| fastmoss-ads | 广告引擎 | DOM scrape |
| fastmoss-market | 品类大盘 | **API-first** (page-context fetch) |

Shared wrapper: `scripts/bsk_client.py` — wraps `bsk` CLI, auto-adds `--json`, parses output.

## Key commands

```bash
# Check daemon health
bsk doctor --json

# Example: scrape products top 50
python .claude/skills/fastmoss-products/scripts/fastmoss_scraper.py --pages 5 --out data/top50.csv

# Example: multi-country comparison
python .claude/skills/fastmoss-products/scripts/fastmoss_filtered.py \
    --ranking newProducts --country 美国,印度尼西亚,泰国 --pages 3 --out data/by_country.csv

# Example: generate analysis report
python .claude/skills/fastmoss-products/scripts/analyze.py \
    --top50 data/top50.csv --by-country data/by_country.csv \
    --by-category data/by_category.csv --out-md analysis.md
```

Every script supports `--help`. Read the relevant `SKILL.md` before running any skill — it documents all flags, ranking names, and gotchas.

## Gotchas that WILL bite you

1. **SPA hydration lag** — 0-row output almost always means the page wasn't ready. Bump `--nav-sleep 8 --page-sleep 4` (defaults are 6/3.5).

2. **Never use `@e` refs** in BrowserSkill evaluate calls. They go stale. All bundled scripts use `evaluate` + text/selector matching.

3. **bash heredoc breaks JS regex.** The `\\n` gets consumed. Write JS to a `.js` file and invoke via Python/bsk, or use `.split('\n')` instead of regex.

4. **CSV encoding is `utf-8-sig`** (BOM). All bundled scripts write this way. If you read CSVs in downstream code, use `encoding='utf-8-sig'`.

5. **Country labels differ between skills.** DOM-scraping skills use Chinese (`--country 美国,印度尼西亚`). `fastmoss-market` uses ISO codes (`--region US,ID`). Don't mix them.

6. **Ant Design dual-table quirk.** Sticky headers split `<thead>` and `<tbody>` into separate `<table>` elements. The EXTRACT_JS in scrapers merges them — if you write new scrapers, do the same.

7. **Rate limiting.** If FastMoss returns errors, increase `--page-sleep` to 5-8s or add `sleep 30` between script runs.

8. **Session cleanup.** Each skill uses its own session name. Clean up with `bsk session stop <session-name>` when done.

## CSV schema

DOM-scrape skills auto-read `<thead>` for column names — don't hardcode business columns. Base columns are always: `page, ranking, rank, entity_name, country`.

Multi-country scripts output both per-country CSVs (`<out>_<country>.csv`) and a merged CSV with a `filter_country` column.

## No build/test/lint

There are no build, test, lint, or typecheck commands. Outputs land in `data/` (gitignored). Reports land in `analysis.md` or custom paths.

## Useful references

- Each skill's `SKILL.md` — authoritative for that module's scripts, flags, and quirks.
- `references/environment.md` in each skill — Windows/bash/jq environment details.
- `references/analysis_recipe.md` — report template and aggregation logic.
- `CLAUDE.md` — project overview for Claude Code sessions.
