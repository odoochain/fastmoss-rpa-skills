"""Aggregate FastMoss shop CSVs into crosstabs for the analysis report.

Reads the CSVs produced by shop_scraper.py / shop_filtered.py and
prints cross-tabulations: category distribution, country distribution,
ranking x category crosstab, top shops (multi-ranking presence).

Usage:
    python analyze.py --sales <path> [--hot <path>] \\
        [--filtered <path>] [--out-md <path>]

When --out-md is given, writes a Markdown report using the template in
references/analysis_recipe.md; otherwise prints plain text to stdout.
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
REFERENCE_TEMPLATE = HERE.parent / "references" / "analysis_recipe.md"


def read_csv(path):
    if not path or not Path(path).exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pct(n, total):
    return f"{n*100//total}%" if total else "-"


def breakdown(rows, key, top_n=10):
    cnt = Counter(r.get(key, "").strip() for r in rows if r.get(key, "").strip())
    total = sum(cnt.values())
    return {"total": total, "rows": cnt.most_common(top_n)}


def cross_tab(rows, row_key, col_key, top_n=3):
    out = defaultdict(Counter)
    for r in rows:
        rk = r.get(row_key, "").strip()
        ck = r.get(col_key, "").strip()
        if rk and ck:
            out[rk][ck] += 1
    return out


def top_shops(all_rows, min_count=2):
    seen = Counter()
    for r in all_rows:
        name = r.get("shop_name", "").strip()
        if name:
            seen[name] += 1
    return [(n, c) for n, c in seen.most_common(20) if c >= min_count][:10]


def render_plain(stats):
    out = []
    for section, data in stats.items():
        out.append(f"=== {section} ===")
        if isinstance(data, dict) and "rows" in data:
            out.append(f"total: {data['total']}")
            for k, v in data["rows"]:
                out.append(f"  {k}: {v} ({pct(v, data['total'])})")
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, Counter):
                    out.append(f"  {k}: {dict(v.most_common(5))}")
                elif isinstance(v, dict):
                    out.append(f"  {k}:")
                    for sk, sv in v.items():
                        out.append(f"    {sk}: {sv}")
                else:
                    out.append(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                out.append(f"  {item}")
        out.append("")
    return "\n".join(out)


def render_markdown(stats, out_path):
    template = REFERENCE_TEMPLATE.read_text(encoding="utf-8")

    cat_rows = stats["category_breakdown"]["rows"]
    cat_md = "\n".join(f"| {n} | {c} | {pct(c, stats['category_breakdown']['total'])} |"
                       for n, c in cat_rows)
    country_rows = stats["country_breakdown"]["rows"]
    country_md = "\n".join(f"| {n} | {c} | {pct(c, stats['country_breakdown']['total'])} |"
                           for n, c in country_rows)
    rc_rows = []
    for ranking, cats in stats["ranking_category"].items():
        top3 = " | ".join(f"{c}({n})" for c, n in cats.most_common(3))
        rc_rows.append(f"| {ranking} | {sum(cats.values())} | {top3} |")
    rc_md = "\n".join(rc_rows)
    repeat_md = "\n".join(f"- `{n}` × {c}" for n, c in stats["repeat_shops"]) or "_(无 — 各榜单均无重复店铺)_"

    today = datetime.now().strftime("%Y-%m-%d")
    sample = " + ".join(f"{k}: {v['total']} 条" for k, v in stats["per_ranking"].items() if v["total"])

    content = template.format(
        scrape_date=today,
        sample=sample,
        category_table=cat_md or "_(无数据)_",
        country_table=country_md or "_(无数据)_",
        ranking_category_table=rc_md or "_(无数据)_",
        repeat_shops=repeat_md,
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sales", help="店铺销量榜 CSV")
    p.add_argument("--hot", help="店铺热推榜 CSV")
    p.add_argument("--filtered", help="Combined multi-filter CSV (ranking field used to split)")
    p.add_argument("--out-md", help="If given, write the full Markdown report here using the recipe template")
    args = p.parse_args()

    per_ranking_files = {
        "sales": args.sales,
        "hot": args.hot,
    }
    per_ranking = {k: read_csv(v) for k, v in per_ranking_files.items() if v}
    if args.filtered:
        combined = read_csv(args.filtered)
        bucket = defaultdict(list)
        for r in combined:
            bucket[r.get("ranking", "unknown")].append(r)
        for k, rows in bucket.items():
            per_ranking.setdefault(k, [])
            per_ranking[k].extend(rows)

    all_rows = []
    for rows in per_ranking.values():
        all_rows.extend(rows)

    # Derive a country field from filter_country if present, else fall back to a top-level country column
    for r in all_rows:
        if not r.get("country"):
            r["country"] = r.get("filter_country", "")

    stats = {
        "per_ranking": {k: {"total": len(v)} for k, v in per_ranking.items()},
        "category_breakdown": breakdown(all_rows, "shop_category"),
        "country_breakdown": breakdown(all_rows, "country"),
        "ranking_category": cross_tab(all_rows, "ranking", "shop_category"),
        "repeat_shops": top_shops(all_rows, min_count=2),
    }

    if args.out_md:
        out = render_markdown(stats, Path(args.out_md))
        print(f"[done] report -> {out}")
    else:
        print(render_plain(stats))


if __name__ == "__main__":
    main()
