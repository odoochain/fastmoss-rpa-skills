"""Aggregate FastMoss category-distribution CSVs into a crosstab report.

Reads CSVs produced by fetch_distribution.py (multi-region or per-region)
and prints/writes cross-tabulations:
  - Per-region category ranking (top categories by sale amount)
  - Region x category crosstab (which categories dominate which markets)
  - High-growth categories (sorted by mom_rate)
  - Cross-region repeat categories (in Top 5 of multiple regions)

Usage:
    python analyze.py --distribution <path> [--out-md <path>]
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


def to_number(s):
    """Parse '24%' or '1234.56' into a number for sorting."""
    if s is None:
        return 0
    s = str(s).strip().rstrip("%")
    try:
        return float(s)
    except Exception:
        return 0


def render_plain(stats):
    out = []
    for section, data in stats.items():
        out.append(f"=== {section} ===")
        if isinstance(data, dict) and "rows" in data:
            out.append(f"total: {data['total']}")
            for k, v in data["rows"]:
                out.append(f"  {k}: {v} ({pct(v, data['total']) if isinstance(v, int) else v})")
        elif isinstance(data, list):
            for item in data:
                out.append(f"  {item}")
        out.append("")
    return "\n".join(out)


def render_markdown(stats, out_path, source_files):
    template = REFERENCE_TEMPLATE.read_text(encoding="utf-8")

    today = datetime.now().strftime("%Y-%m-%d")
    regions = stats["regions"]
    sample = f"region 数: {len(regions)} ({', '.join(regions)})"
    source_str = ", ".join(Path(s).name for s in source_files)

    # Top categories per region (top 5)
    top_per_region_md = []
    for region, cats in stats["top_categories_per_region"].items():
        top5 = ", ".join(f"{name} ({amt})" for name, amt, _ in cats[:5])
        top_per_region_md.append(f"| {region} | {top5} |")

    # Top categories by growth (overall)
    growth_md = []
    for name, region, rate in stats["top_growth"][:15]:
        growth_md.append(f"| {name} | {region} | {rate}% |")

    # Region x category crosstab (which region has which categories in top 10)
    rc_md = []
    for region, cats in stats["top_categories_per_region"].items():
        names = ", ".join(name for name, _, _ in cats[:10])
        rc_md.append(f"| {region} | {len(cats)} | {names} |")

    # Cross-region repeat categories (in Top 5 of multiple regions)
    repeat_md = []
    for name, count in stats["cross_region_repeats"]:
        repeat_md.append(f"- `{name}` 出现在 {count} 个市场的 Top 5")
    if not repeat_md:
        repeat_md.append("_(无 — 各市场 Top 5 没有重复品类)_")

    content = template.format(
        scrape_date=today,
        sample=sample,
        source_files=source_str,
        top_per_region_table="\n".join(top_per_region_md) or "_(无数据)_",
        growth_table="\n".join(growth_md) or "_(无数据)_",
        region_crosstab_table="\n".join(rc_md) or "_(无数据)_",
        cross_region_repeats="\n".join(repeat_md),
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--distribution", action="append", default=[],
                   help="categoryDistribution CSV (from fetch_distribution.py). Repeatable.")
    p.add_argument("--out-md", help="If given, write the full Markdown report here")
    args = p.parse_args()

    rows = []
    for path in args.distribution:
        rows.extend(read_csv(path))

    if not rows:
        print("NO ROWS. Pass --distribution <path> (repeatable).")
        return

    # Group by region
    by_region = defaultdict(list)
    for r in rows:
        reg = r.get("region") or "(global)"
        by_region[reg].append(r)

    # Top categories per region (by category_sale_amount)
    top_per_region = {}
    for region, items in by_region.items():
        items_sorted = sorted(items,
                              key=lambda r: to_number(r.get("category_sale_amount", 0)),
                              reverse=True)
        top_per_region[region] = [
            (it.get("category_name", ""),
             it.get("category_sale_amount_show", ""),
             to_number(it.get("category_sale_amount_mom_rate", 0)))
            for it in items_sorted
        ]

    # Top growth overall
    growth = []
    for r in rows:
        rate = to_number(r.get("category_sale_amount_mom_rate", 0))
        if rate > 0:
            growth.append((r.get("category_name", ""), r.get("region") or "(global)", int(rate)))
    growth.sort(key=lambda x: x[2], reverse=True)

    # Cross-region repeat categories (Top 5 in multiple regions)
    cat_region_count = Counter()
    for region, top in top_per_region.items():
        for name, _, _ in top[:5]:
            cat_region_count[name] += 1
    repeats = [(name, c) for name, c in cat_region_count.most_common(20) if c >= 2]

    stats = {
        "regions": list(by_region.keys()),
        "top_categories_per_region": top_per_region,
        "top_growth": growth,
        "cross_region_repeats": repeats,
    }

    if args.out_md:
        out = render_markdown(stats, Path(args.out_md), args.distribution)
        print(f"[done] report -> {out}")
    else:
        print(render_plain(stats))


if __name__ == "__main__":
    main()
