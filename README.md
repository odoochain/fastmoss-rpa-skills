# fastmoss-rpa

> Browser-RPA + 数据分析工具集，覆盖 [fastmoss.com](https://www.fastmoss.com) (TikTok Shop 数据分析平台) 全部 7 个核心模块。基于 [Kimi WebBridge](https://kimi.com/features/webbridge) 驱动用户真实浏览器（复用登录态），把 FastMoss 的榜单/趋势/市场数据落成 CSV，并自动生成 Markdown 分析报告。

---

## 目录

- [项目特点](#项目特点)
- [架构概览](#架构概览)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [Skills 一览](#skills-一览)
- [每个 Skill 的使用](#每个-skill-的使用)
  - [fastmoss-products · 商品](#fastmoss-products--商品)
  - [fastmoss-creators · 达人](#fastmoss-creators--达人)
  - [fastmoss-shops · 店铺](#fastmoss-shops--店铺)
  - [fastmoss-livestreams · 直播](#fastmoss-livestreams--直播)
  - [fastmoss-creatives · 视频&素材](#fastmoss-creatives--视频素材)
  - [fastmoss-ads · 广告引擎](#fastmoss-ads--广告引擎)
  - [fastmoss-market · 品类大盘](#fastmoss-market--品类大盘)
- [输出文件结构](#输出文件结构)
- [通用约定](#通用约定)
- [常见问题与坑](#常见问题与坑)
- [扩展开发指南](#扩展开发指南)

---

## 项目特点

- **真实浏览器复用登录态** — 通过 Kimi WebBridge 驱动用户已经登录的 Chrome/Edge，无需扫码、无需 token、无需 captcha 破解。
- **7 个 FastMoss 模块全覆盖** — 商品/达人/店铺/直播/视频&素材/广告引擎/品类大盘，每个模块独立 skill，互不干扰。
- **CSV + Markdown 双输出** — 原始数据进 `data/`，聚合报告生成到 `analysis.md` 或自定义路径，Excel 友好（UTF-8 BOM）。
- **Schema 自动适配** — 6 个 DOM-scraping skill 动态读取 `<thead>`，无论 FastMoss 改字段都不需要改代码。
- **API-first 优先** — `fastmoss-market` 是 API skill，直接调用 FastMoss JSON 接口（通过页面上下文 `fetch()`），无分页、无 SPA 等待、无 selector 维护。
- **多市场对比内置** — 所有 ranking skill 都支持 `--country 美国,印度尼西亚,泰国,马来西亚` 一键多市场抓取并自动切分。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     fastmoss-rpa 项目                       │
├─────────────────────────────────────────────────────────────┤
│  .claude/skills/                                            │
│    ├── fastmoss-products/      # 商品模块 (DOM scrape)      │
│    ├── fastmoss-creators/      # 达人模块 (DOM scrape)      │
│    ├── fastmoss-shops/         # 店铺模块 (DOM scrape)      │
│    ├── fastmoss-livestreams/   # 直播模块 (DOM scrape)      │
│    ├── fastmoss-creatives/     # 视频&素材 (DOM scrape)     │
│    ├── fastmoss-ads/           # 广告引擎 (DOM scrape)      │
│    ├── fastmoss-market/        # 品类大盘 (API-first)       │
│    └── skill-creator/          # Claude skill 创建工具      │
├─────────────────────────────────────────────────────────────┤
│  data/                        # CSV 输出目录                 │
│  analysis.md                  # 默认分析报告                 │
│  CLAUDE.md                    # Claude Code 项目指南         │
└─────────────────────────────────────────────────────────────┘
         │
         │ 每个 skill 内部结构一致：
         │   SKILL.md                  # 入口文档
         │   scripts/                  # 可执行 Python 脚本
         │     ├── <section>_scraper.py
         │     ├── <section>_filtered.py
         │     └── analyze.py
         │   references/               # 进阶参考文档
         │     ├── environment.md
         │     └── analysis_recipe.md
         ▼
┌─────────────────────────────────────────────────────────────┐
│         Kimi WebBridge daemon (localhost:10086)              │
│   通过 WebSocket 连接用户的 Chrome/Edge 扩展                  │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
   用户的真实浏览器（已登录 fastmoss.com）
```

**核心思路：** 不破解、不逆向、不模拟登录 — 直接复用用户日常浏览器的登录态，通过 WebBridge 的 `evaluate` / `click` / `network` 等工具驱动页面。

---

## 环境要求

| 依赖 | 版本/要求 | 安装方式 |
|---|---|---|
| Python | 3.8+ (内置 `urllib`, `csv`, `json`, `argparse` 即可) | https://python.org |
| Chrome 或 Edge | 任意现代版本 | 用于 Kimi WebBridge 扩展 |
| Kimi WebBridge | v1.9.10+ (daemon + 浏览器扩展) | 见 [Kimi WebBridge 文档](https://kimi.com/features/webbridge) |
| FastMoss 账号 | 任意等级（订阅决定可见数据深度） | https://www.fastmoss.com 注册 |
| 操作系统 | Windows / macOS / Linux 都可 | bash shell（Windows 用 Git Bash 或 WSL） |

**不需要**：Node.js、jq、selenium、playwright、puppeteer、ffmpeg、任何 headless 浏览器。

---

## 快速开始

### 1. 检查 WebBridge daemon

```bash
~/.kimi-webbridge/bin/kimi-webbridge status
# 期望输出：
# {"running": true, "extension_connected": true, "version": "v1.9.10", ...}
```

如果 `running: false` 或 `extension_connected: false`，先启动 daemon 并打开浏览器：

```bash
~/.kimi-webbridge/bin/kimi-webbridge start
# 然后在浏览器里手动打开任意页面，让扩展激活
```

### 2. 登录 fastmoss.com

在 Chrome/Edge 里打开 https://www.fastmoss.com 并登录你的账号。**只需要登录一次**，所有 skill 会复用这个 session。

### 3. 跑一个 skill

以商品模块的"销量榜 Top 50"为例：

```bash
python .claude/skills/fastmoss-products/scripts/fastmoss_scraper.py \
    --pages 5 \
    --out data/top50.csv
```

浏览器会自动打开 FastMoss 销量榜 → 翻 5 页 → 输出 50 条记录到 `data/top50.csv`。

### 4. 生成分析报告

```bash
python .claude/skills/fastmoss-products/scripts/analyze.py \
    --top50 data/top50.csv \
    --by-country data/by_country.csv \
    --by-category data/by_category.csv \
    --out-md analysis.md
```

报告会输出到 `analysis.md`，包含国家分布、品类分布、店铺分布、跨榜重复商品等分析章节。

---

## Skills 一览

| Skill | FastMoss 模块 | 抓取方式 | 覆盖页面 | 是否支持多市场对比 |
|---|---|---|---|---|
| **fastmoss-products** | 商品 | DOM scrape | 新品榜 / 销量榜 / 热推榜 / 视频商品榜 + 单店铺上新 | ✅ |
| **fastmoss-creators** | 达人 | DOM scrape | 涨粉榜 / 带货榜 / 蓝V榜 / 热门榜 / 黑马榜 | ✅ |
| **fastmoss-shops** | 店铺 | DOM scrape | 店铺销量榜 / 店铺热推榜 | ✅ |
| **fastmoss-livestreams** | 直播 | DOM scrape | TT直播榜 / 直播爆品榜 / 直播带货达人榜 | ✅ |
| **fastmoss-creatives** | 视频素材 | DOM scrape | 热门视频 / 热门音乐 / 热门标签 | ✅ |
| **fastmoss-ads** | 广告引擎 | DOM scrape | 标签洞察 / 关键词趋势 / 热门品类趋势 | ✅ |
| **fastmoss-market** | 品类大盘 | **API-first** | 行业格局 / 市场总览 / 销售趋势 / 价格带 | ✅（多 region） |

> **API-first 意味着什么？** `fastmoss-market` 直接调用 FastMoss 的 JSON 接口（`/api/analysis/...`），通过页面上下文 `fetch()` 复用 cookies。无 DOM 解析、无分页、无 SPA hydration 等待 — 更快、更可靠、字段更干净。其他 6 个 skill 走 DOM scrape 是因为目标页面没有公开 API。

---

## 每个 Skill 的使用

下面每个 skill 的脚本路径用 `<SKILL_DIR>` 代替 `.claude/skills/<skill-name>`。所有脚本都支持 `--help` 查看完整参数。

### fastmoss-products · 商品

**覆盖 4 个榜单 + 单店铺上新跟踪。**

```bash
# Top 50 销量榜
python <SKILL_DIR>/scripts/fastmoss_scraper.py \
    --ranking newProducts --pages 5 \
    --out data/top50.csv

# 多国家对比（每个国家单独 CSV + 合并 CSV）
python <SKILL_DIR>/scripts/fastmoss_filtered.py \
    --ranking newProducts \
    --country 美国,印度尼西亚,泰国,马来西亚 \
    --pages 3 \
    --out data/by_country.csv

# 多品类对比
python <SKILL_DIR>/scripts/fastmoss_filtered.py \
    --ranking newProducts \
    --category 美妆个护,保健,女装与女士内衣 \
    --pages 3 \
    --out data/by_category.csv

# 跟踪单个店铺连续多日上新节奏
python <SKILL_DIR>/scripts/shop_scraper.py \
    --shop-id <FASTMOSS_SHOP_ID> --pages 2 \
    --out data/shop_<name>.csv

# 聚合成报告
python <SKILL_DIR>/scripts/analyze.py \
    --top50 data/top50.csv \
    --by-country data/by_country.csv \
    --by-category data/by_category.csv \
    --shop data/shop_*.csv \
    --out-md analysis.md
```

**国家词汇表（16 个市场，所有 skill 通用）：**
`全部`、`美国`、`印度尼西亚`、`英国`、`越南`、`泰国`、`马来西亚`、`菲律宾`、`西班牙`、`墨西哥`、`德国`、`法国`、`意大利`、`巴西`、`日本`、`新加坡`

---

### fastmoss-creators · 达人

**覆盖 5 个达人榜（涨粉/带货/蓝V/热门/黑马）。**

```bash
# 涨粉达人榜 Top 50
python <SKILL_DIR>/scripts/creator_scraper.py \
    --ranking fans --pages 5 \
    --out data/fans.csv

# 黑马达人榜（潜力达人提前签约）
python <SKILL_DIR>/scripts/creator_scraper.py \
    --ranking potentialTop --pages 3 \
    --out data/horse.csv

# 多国家 + 自定义时间窗
python <SKILL_DIR>/scripts/creator_filtered.py \
    --ranking fans \
    --country 美国,印度尼西亚,泰国 \
    --time 周榜 \
    --pages 3 \
    --out data/fans_by_country.csv

# 跨榜分析报告（找出同时进多榜的达人）
python <SKILL_DIR>/scripts/analyze.py \
    --fans data/fans.csv \
    --commerce data/commerce.csv \
    --blue-v data/blue-v.csv \
    --popular data/popular.csv \
    --horse data/horse.csv \
    --out-md data/creators_report.md
```

**时间窗：** `日榜` / `周榜` / `月榜`（`黑马榜` 用 `近28天` 替代 `日榜`）

---

### fastmoss-shops · 店铺

**销量榜 + 热推榜（找出新增带货达人最多的店铺）。**

```bash
python <SKILL_DIR>/scripts/shop_scraper.py --ranking sales --pages 5 --out data/shop_sales.csv
python <SKILL_DIR>/scripts/shop_scraper.py --ranking hot --pages 5 --out data/shop_hot.csv

python <SKILL_DIR>/scripts/shop_filtered.py \
    --ranking sales \
    --country 美国,印度尼西亚 \
    --pages 3 \
    --out data/shop_sales_by_country.csv

python <SKILL_DIR>/scripts/analyze.py \
    --sales data/shop_sales.csv \
    --hot data/shop_hot.csv \
    --out-md data/shops_report.md
```

---

### fastmoss-livestreams · 直播

```bash
python <SKILL_DIR>/scripts/live_scraper.py --ranking tiktok --pages 5 --out data/live_tiktok.csv
python <SKILL_DIR>/scripts/live_scraper.py --ranking hotProduct --pages 5 --out data/live_hot_product.csv
python <SKILL_DIR>/scripts/live_scraper.py --ranking liveCommerce --pages 5 --out data/live_commerce.csv

python <SKILL_DIR>/scripts/analyze.py \
    --tiktok data/live_tiktok.csv \
    --hot-product data/live_hot_product.csv \
    --live-commerce data/live_commerce.csv \
    --out-md data/live_report.md
```

---

### fastmoss-creatives · 视频&素材

```bash
python <SKILL_DIR>/scripts/creative_scraper.py --ranking video --pages 5 --out data/videos.csv
python <SKILL_DIR>/scripts/creative_scraper.py --ranking song --pages 3 --out data/songs.csv
python <SKILL_DIR>/scripts/creative_scraper.py --ranking hashtag --pages 3 --out data/hashtags.csv

python <SKILL_DIR>/scripts/analyze.py \
    --video data/videos.csv \
    --song data/songs.csv \
    --hashtag data/hashtags.csv \
    --out-md data/creatives_report.md
```

> `AI带货视频榜` 是卡片式布局（无 `<table>`），未脚本化。如需抓取请按 `<SKILL_DIR>/references/environment.md` 的 evaluate 模式自写脚本。

---

### fastmoss-ads · 广告引擎

**3 个趋势榜（标签/关键词/品类）。** 3 个广告搜索页（电商广告/种草广告/广告主洞察）是卡片式过滤页，未脚本化。

```bash
python <SKILL_DIR>/scripts/ads_scraper.py --ranking tag --pages 5 --out data/tags.csv
python <SKILL_DIR>/scripts/ads_scraper.py --ranking keyword --pages 5 --out data/keywords.csv
python <SKILL_DIR>/scripts/ads_scraper.py --ranking category --pages 3 --out data/categories.csv

python <SKILL_DIR>/scripts/analyze.py \
    --tag data/tags.csv \
    --keyword data/keywords.csv \
    --category data/categories.csv \
    --out-md data/ads_report.md
```

---

### fastmoss-market · 品类大盘

**唯一的 API-first skill。** 覆盖 `/market/market-category` 行业格局 + `/market/market-analyze` 市场总览。

```bash
# 先看一下当前分类/国家词汇表
python <SKILL_DIR>/scripts/fetch_filter_info.py

# 行业格局：多市场对比（一个月数据，每个市场一份 CSV + 合并 CSV）
python <SKILL_DIR>/scripts/fetch_distribution.py \
    --region US,ID,TH,MY --time month \
    --out data/category_distribution.csv

# 单市场总览（含 Top Products）
python <SKILL_DIR>/scripts/fetch_base.py \
    --region US \
    --out data/us_market_base.json \
    --top-products-csv data/us_top_products.csv

# 销售趋势时间序列（每日）
python <SKILL_DIR>/scripts/fetch_sales_chart.py \
    --region US \
    --out data/us_sales_chart.csv

# 多市场品类对比报告
python <SKILL_DIR>/scripts/analyze.py \
    --distribution data/category_distribution.csv \
    --out-md data/market_report.md
```

**region 编码（不同于其他 skill 用中文）：**
`US`（美国）、`ID`（印度尼西亚）、`GB`（英国）、`VN`（越南）、`TH`（泰国）、`MY`（马来西亚）、`PH`（菲律宾）、`ES`（西班牙）、`MX`（墨西哥）、`DE`（德国）、`FR`（法国）、`IT`（意大利）、`BR`（巴西）、`JP`（日本）、`SG`（新加坡）

**pcid 品类编码（前 10）：**
`14` 美妆个护、`2` 女装与女士内衣、`25` 保健、`8` 时尚配件、`9` 运动与户外、`16` 手机与数码、`10` 居家日用、`24` 食品饮料、`23` 汽车与摩托车、`3` 男装与男士内衣

完整词汇表运行 `fetch_filter_info.py` 即可获取。

---

## 输出文件结构

```
fastmoss-rpa/
├── data/                                # 所有 CSV 输出
│   ├── top50.csv                        # 销量榜 Top 50
│   ├── by_country.csv                   # 多国家合并 CSV
│   ├── by_country_美国.csv              # 单国家 CSV（自动拆分）
│   ├── by_country_印度尼西亚.csv
│   ├── by_category.csv
│   ├── by_category_美妆个护.csv
│   ├── shop_<name>.csv                  # 单店铺上新
│   ├── fans.csv / commerce.csv / ...    # 达人各榜
│   ├── shop_sales.csv / shop_hot.csv
│   ├── live_*.csv
│   ├── videos.csv / songs.csv / hashtags.csv
│   ├── tags.csv / keywords.csv / categories.csv
│   ├── category_distribution.csv        # 品类大盘
│   ├── us_market_base.json              # API 返回的原始 JSON
│   └── us_sales_chart.csv
├── analysis.md                          # 默认商品分析报告
├── data/creators_report.md              # 各 skill 自定义报告
├── data/shops_report.md
├── data/live_report.md
├── data/creatives_report.md
├── data/ads_report.md
└── data/market_report.md
```

**所有 CSV 都是 `utf-8-sig`（带 BOM）编码**，直接双击在 Excel 打开不会乱码。

---

## 通用约定

### Session 隔离

每个 skill 用自己的 session name（`fastmoss-products` / `fastmoss-creators` / ... / `fastmoss-market`），互不影响。这意味着可以并行跑多个 skill（但注意浏览器性能和 FastMoss 的频率限制）。

任务结束时建议清理 session：

```bash
curl -d '{"action":"close_session","args":{},"session":"fastmoss-products"}' \
  http://127.0.0.1:10086/command
```

### CSV schema（DOM scrape 类 skill）

基础列（一定有）：
```
page, ranking, rank, entity_name (或 creator_name / shop_name), country
```

业务列：动态读取 `<thead>`，每个榜单字段不同。例如商品销量榜有 `销量/销量环比/销售额/销售额环比/动销商品数`，涨粉达人榜有 `粉丝变化量/粉丝数/涨粉率/作品数`。

不要在下游代码里写死列名 — 用 `dict.keys()` 遍历。

### 国家/地区过滤

DOM-scraping skill 用中文 label（`--country 美国,印度尼西亚`）。
`fastmoss-market` 用 ISO 代码（`--region US,ID`）。

### 多市场对比的产物

`<skill>_filtered.py` 类脚本在传多个国家时，会同时输出：
- `<out-prefix>_<country1>.csv` — 每个国家单独一份
- `<out-prefix>.csv` — 合并一份（含 `filter_country` 列用于区分）

### 分页参数

所有 ranking skill 支持：
- `--pages N` — 抓 N 页（每页通常 10 条）
- `--nav-sleep 6` — 初次导航后等几秒（默认 6 秒，给 SPA hydration 时间）
- `--page-sleep 3.5` — 翻页之间等几秒（默认 3.5 秒）

如果 0 行输出，先尝试把 `--nav-sleep` 提到 8-10。

---

## 常见问题与坑

### 1. `extension_connected: false`

浏览器扩展没连上 daemon。常见原因：
- 浏览器没打开 — 打开任意页面激活扩展
- 扩展被禁用 — 在 `chrome://extensions` 启用 Kimi WebBridge 扩展
- daemon 端口被占 — 重启 daemon：`~/.kimi-webbridge/bin/kimi-webbridge restart`

### 2. 抓到 0 行

99% 是 SPA 还没 hydrate。调高 `--nav-sleep`：
```bash
--nav-sleep 8 --page-sleep 4
```

### 3. `No node with given id found`

这是 WebBridge 的 @e 引用过期报错。所有 bundled 脚本都不用 @e，全部走 `evaluate` + 文字匹配。如果你自己写脚本也避免 @e。

### 4. `Invalid regular expression: missing /`

bash heredoc 把 JS 里的 `\\n` 吃掉一层。**别在 bash heredoc 里写正则** — 改用 `.split('\n')` 或把 JS 写到 `.js` 文件用 Python urllib POST。

### 5. CSV 在 Excel 里乱码

用 `utf-8-sig` 读，不是 `utf-8`：
```python
with open('your.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
```

所有 bundled 脚本默认就是 `utf-8-sig` 写。

### 6. `MAG_AUTH_3024` 报错（fastmoss-market）

FastMoss 对非高级订阅返回这个 code，但响应体里**仍然包含数据**。`fastmoss-market` 的 bundled fetcher 已经做了兜底（只要有 `dots` 数组就当成功），所以可以无视。

### 7. 跑得太快被 FastMoss 限流

调高 `--page-sleep` 到 5-8 秒，或在脚本之间插入 `sleep 30`。

### 8. `jq: command not found`

`scripts/screenshot.sh` 依赖 jq。Windows 环境下用 Python 解码：
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -d '{"action":"screenshot","args":{"format":"jpeg","quality":75},"session":"fastmoss-products"}' \
  | python -c "import sys,json,base64; open('out.jpeg','wb').write(base64.b64decode(json.load(sys.stdin)['data']['data']))"
```

---

## 扩展开发指南

### 写一个新 ranking 的 scraper

参考任意一个现有的 `<skill>_scraper.py`。核心模板：

```python
EXTRACT_JS = """
(() => {
  const tables = document.querySelectorAll('table');
  if (!tables.length) return JSON.stringify({error: 'no table'});
  // Ant Design 经常拆成 sticky-header (table[0]) + data (table[1]) 两张表
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
  return JSON.stringify({headers, rows});
})()
"""
```

关键点：
1. **不要用 @e** — 走 `evaluate` + 文字匹配
2. **多表合并** — Ant Design 的 sticky header 会把 `<thead>` 和 `<tbody>` 拆成两张表
3. **`innerText || textContent`** — Ant Design 的某些 cell 在 hydration 完成前 `innerText` 是空的
4. **`title` 属性兜底** — 排序表头 `<th title="排名">` 经常 `innerText` 为空

### 写一个新 API 的 fetcher（参考 fastmoss-market）

```python
from common import ensure_market_page, fetch_json

ensure_market_page(session)  # 第一次必须先 navigate 到目标域名下
res = fetch_json("/api/your/endpoint?param=value", session)
if res.get("status") != 200:
    # 错误处理
    ...
body = res["data"]
if body.get("code") != 200:
    # FastMoss 有时 code 是 MAG_AUTH_xxxx 但 data 仍有内容
    if not body.get("data", {}).get("your_array"):
        # 真的失败了
        ...
# 处理 body["data"]
```

### 调试技巧

```bash
# 抓页面快照（保存到文件，避免 base64 污染终端）
curl -s -X POST http://127.0.0.1:10086/command \
  -d '{"action":"screenshot","args":{"format":"jpeg","quality":75},"session":"<session>"}' \
  | python -c "import sys,json,base64; open('debug.jpeg','wb').write(base64.b64decode(json.load(sys.stdin)['data']['data']))"

# 跑 evaluate 探 DOM
curl -s -X POST http://127.0.0.1:10086/command \
  -d '{"action":"evaluate","args":{"code":"(() => JSON.stringify({title: document.title, url: location.href}))()"}}'

# 抓网络请求（找 API endpoint）
curl -s -X POST http://127.0.0.1:10086/command \
  -d '{"action":"network","args":{"cmd":"start","filter":"/api/"}}'
# ... 操作页面触发请求 ...
curl -s -X POST http://127.0.0.1:10086/command \
  -d '{"action":"network","args":{"cmd":"list","filter":"/api/"}}'
```

---

## 许可与免责

- 本项目仅供个人数据分析用途，请遵守 FastMoss 的服务条款。
- 严禁用于：批量爬取倒卖、对抗 FastMoss 反爬、绕过订阅权限。
- 任何因使用本项目产生的账号封禁、法律责任，由使用者自行承担。

---

## 相关链接

- [FastMoss 官网](https://www.fastmoss.com)
- [Kimi WebBridge 文档](https://kimi.com/features/webbridge)
- [Claude Code 文档](https://claude.ai/code)
- 项目内：`CLAUDE.md`（Claude Code 项目指南）、各 skill 的 `SKILL.md`（入口文档）

## 特别感谢：

https://linux.do 社区佬友 