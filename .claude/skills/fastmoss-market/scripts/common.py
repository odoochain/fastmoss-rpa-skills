"""Shared helpers for fastmoss-market scripts.

Centralizes the BrowserSkill call plumbing + the page-context fetch()
helper that all bundled scripts use to call FastMoss JSON APIs.
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from bsk_client import bsk, configure_utf8_output  # noqa: E402

DEFAULT_SESSION = "fastmoss-market"
MARKET_URL = "https://www.fastmoss.com/zh/market/market-category"
ANALYZE_URL = "https://www.fastmoss.com/zh/market/market-analyze"


def call(action, args, session):
    if action == "navigate":
        url = args.get("url")
        new_tab = args.get("newTab", False)
        if new_tab:
            return bsk("tab create", session, url)
        else:
            return bsk("navigate", session, url)
    elif action == "evaluate":
        code = args.get("code", "")
        return bsk("evaluate", session, code)
    else:
        raise RuntimeError(f"Unsupported action: {action}")


def evaluate(code, session):
    res = call("evaluate", {"code": code}, session)
    if isinstance(res, dict) and res.get("type") == "string":
        try:
            return json.loads(res["value"])
        except Exception:
            return {"raw": res.get("value")}
    return res


def ensure_market_page(session, page_url=MARKET_URL, sleep_after=4.0):
    """Navigate to the market page (origin + cookies) if not already there.

    Uses newTab on first call so it works whether or not the session exists.
    """
    call("navigate", {"url": page_url, "newTab": True, "group_title": "fastmoss-market"},
         session)
    time.sleep(sleep_after)


# Page-context fetch helper. Calls fetch() from within the market page so the
# browser attaches cookies + the request shares the page's origin. Returns
# parsed JSON. Uses _time + cnonce anti-cache params like the FastMoss SPA.
FETCH_JS_TEMPLATE = """
(async () => {
  const url = %URL%;
  const resp = await fetch(url, {credentials: 'include'});
  const text = await resp.text();
  let data;
  try { data = JSON.parse(text); } catch (e) { data = {raw: text.slice(0, 2000)}; }
  return JSON.stringify({status: resp.status, data});
})()
"""


def fetch_json(url_path, session, base="https://www.fastmoss.com"):
    """Fetch a FastMoss API path via page-context fetch(). Returns parsed dict.

    url_path: path beginning with /api/... (no query string yet) OR a fully
              constructed URL. The function adds _time + cnonce anti-cache params.
    """
    full_url = url_path if url_path.startswith("http") else base + url_path
    sep = "&" if "?" in full_url else "?"
    full_url = f"{full_url}{sep}_time={int(time.time())}&cnonce={int(time.time()*1000) % 100000000}"
    js = FETCH_JS_TEMPLATE.replace("%URL%", json.dumps(full_url))
    res = evaluate(js, session)
    if "error" in res:
        return {"_error": res["error"]}
    return res


def write_csv(path, rows, base_fields):
    """Write rows to CSV with utf-8-sig (BOM). Dynamic columns appended after base."""
    extra_fields = []
    seen = set(base_fields)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                extra_fields.append(k)
                seen.add(k)
    fields = base_fields + extra_fields
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# Region code → 中文 label mapping (16 markets). Used for human-readable CSV columns.
REGION_NAMES = {
    "US": "美国",
    "ID": "印度尼西亚",
    "GB": "英国",
    "VN": "越南",
    "TH": "泰国",
    "MY": "马来西亚",
    "PH": "菲律宾",
    "ES": "西班牙",
    "MX": "墨西哥",
    "DE": "德国",
    "FR": "法国",
    "IT": "意大利",
    "BR": "巴西",
    "JP": "日本",
    "SG": "新加坡",
    "SA": "沙特",
}
