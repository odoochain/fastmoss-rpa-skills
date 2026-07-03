"""Aggregate FastMoss scraped CSVs into crosstabs for the analysis report.

Reads the CSVs produced by fastmoss_scraper.py / fastmoss_filtered.py /
shop_scraper.py and prints cross-tabulations (Top-N country/category/commission
breakdown, country x category crosstab, repeat shops, shop monthly cadence).

Usage:
    python analyze.py \\
        --top50 <path/to/top50.csv> \\
        [--by-country <path/to/by_country.csv>] \\
        [--by-category <path/to/by_category.csv>] \\
        [--shop <path/to/shop.csv>] [--shop <path/to/shop2.csv> ...] \\
        [--out-md <path/to/report.md>]

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


def top_breakdown(rows, key, top_n=8, label=None):
    cnt = Counter(r[key] for r in rows if r.get(key, "").strip())
    total = sum(cnt.values())
    top = cnt.most_common(top_n)
    return {"label": label or key, "total": total, "rows": top}


def country_category_crosstab(by_country_rows):
    """For each filter (=country), top categories; returns {country: Counter}"""
    out = defaultdict(Counter)
    for r in by_country_rows:
        out[r.get("filter", "")][r.get("category", "")] += 1
    return out


def category_country_crosstab(by_category_rows):
    out = defaultdict(Counter)
    for r in by_category_rows:
        out[r.get("filter", "")][r.get("country", "")] += 1
    return out


def repeat_shops(top50_rows, min_count=2):
    shops = Counter(r["shop"] for r in top50_rows if r.get("shop", "").strip())
    return [(s, c) for s, c in shops.most_common() if c >= min_count]


def shop_cadence(shop_rows):
    months = Counter(r["listed_at"][:7] for r in shop_rows if r.get("listed_at", ""))
    return dict(sorted(months.items(), reverse=True))


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
                out.append(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                out.append(f"  {item}")
        out.append("")
    return "\n".join(out)


def render_markdown(stats, out_path):
    """Render the full report using the template in references/analysis_recipe.md."""
    template = REFERENCE_TEMPLATE.read_text(encoding="utf-8")
    # Build the Top-N country/category/commission tables
    top = stats["top50_breakdown"]
    country_md = "\n".join(f"| {n} | {c} | {pct(c, top['country']['total'])} |"
                            for n, c in top["country"]["rows"])
    category_md = "\n".join(f"| {n} | {c} |" for n, c in top["category"]["rows"])
    commission_md = "\n".join(f"| {n} | {c} | {pct(c, top['commission']['total'])} |"
                               for n, c in top["commission"]["rows"])
    # Country x category crosstab
    cc_md = "\n".join(
        f"| {country} | " + " | ".join(f"{cnt}" for cat, cnt in cats.most_common(3)) +
        f" | (total {sum(cats.values())}) |"
        for country, cats in stats["country_category"].items()
    )
    # Category x country crosstab
    catc_md = "\n".join(
        f"| {cat} | " + " | ".join(f"{cnt}" for ctry, cnt in countries.most_common(3)) +
        f" | (total {sum(countries.values())}) |"
        for cat, countries in stats["category_country"].items()
    )
    # Repeat shops
    rep_md = "\n".join(f"- `{s}` × {c}" for s, c in stats["repeat_shops"]) or "_(none — Top 50 中无重复店铺)_"
    # Shop cadence
    cadence = stats["shop_cadence"]
    cadence_md = "\n".join(f"| {m} | {c} |" for m, c in cadence.items()) or "_(无数据)_"

    today = datetime.now().strftime("%Y-%m-%d")
    n_top = top["country"]["total"]
    n_country = sum(sum(c.values()) for c in stats["country_category"].values())
    n_category = sum(sum(c.values()) for c in stats["category_country"].values())
    n_shop = sum(cadence.values())

    content = template.format(
        scrape_date=today,
        sample=f"{n_top} (Top50) + {n_country} (国家筛选) + {n_category} (品类筛选) + {n_shop} (单店铺)",
        country_table=country_md,
        category_table=category_md,
        commission_table=commission_md,
        country_category_table=cc_md,
        category_country_table=catc_md,
        repeat_shops=rep_md,
        shop_cadence_table=cadence_md,
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--top50", help="Path to top50 CSV (or any unfiltered ranking CSV)")
    p.add_argument("--by-country", help="Path to by_country CSV (combined multi-country)")
    p.add_argument("--by-category", help="Path to by_category CSV (combined multi-category)")
    p.add_argument("--shop", action="append", default=[],
                   help="Path to single-shop CSV. Repeat flag for multiple shops (rows are concatenated).")
    p.add_argument("--out-md", help="If given, write the full Markdown report here using the recipe template")
    args = p.parse_args()

    top50 = read_csv(args.top50)
    by_country = read_csv(args.by_country)
    by_category = read_csv(args.by_category)
    shop = []
    for path in args.shop:
        shop.extend(read_csv(path))

    stats = {
        "top50_breakdown": {
            "country": top_breakdown(top50, "country", label="country"),
            "category": top_breakdown(top50, "category", label="category"),
            "commission": top_breakdown(top50, "commission", label="commission"),
        },
        "country_category": country_category_crosstab(by_country),
        "category_country": category_country_crosstab(by_category),
        "repeat_shops": repeat_shops(top50),
        "shop_cadence": shop_cadence(shop),
    }

    if args.out_md:
        out = render_markdown(stats, Path(args.out_md))
        print(f"[done] report -> {out}")
    else:
        print(render_plain(stats))


if __name__ == "__main__":
    main()
