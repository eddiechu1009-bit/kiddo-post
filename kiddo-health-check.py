#!/usr/bin/env python3
"""
kiddo-health-check.py — Kiddo POST 親子網站健檢腳本

每週三 12:10 KiddoPost-Weekly 跑完後接著呼叫,聚焦兩個關鍵指標:

  1. 過期活動清單 — articles.json 裡看似已結束的活動
  2. 未來 2 週活動數量 — 少於 4 個 = 空窗警報

額外資訊(免費附加):
  - 各週別/區域分布
  - 各 topics 文章年齡組覆蓋
  - 檔案大小

用法:
  python parent-intel-site/kiddo-health-check.py
  python parent-intel-site/kiddo-health-check.py --json     # 輸出 JSON 到 stdout
  python parent-intel-site/kiddo-health-check.py --report   # 產出 health-YYYY-WXX.md

退出碼:
  0 - 健康(無異常)
  2 - 有警報(過期 ≥3 OR 未來 2 週 < 4)
  1 - 腳本本身錯誤
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 排程 OEM 終端中文 print 防亂碼
except Exception:
    pass

SITE_DIR = Path(__file__).resolve().parent
ARTICLES_JSON = SITE_DIR / "articles.json"
TOPICS_DIR = SITE_DIR / "topics"
INDEX_HTML = SITE_DIR / "index.html"

# 看到這些字眼就視為「不會過期」
YEAR_LONG_KEYWORDS = ["全年", "長期", "常設", "永久", "持續", "終年"]

# 可解析年齡組(對齊 kiddo-monthly-topic.md 的 6 大類)
AGE_GROUPS = ["0-2", "3-4", "5-6", "6-12", "0-12", "all"]


def extract_dates(s: str, default_year: int) -> list[date]:
    """從中文日期字串抓出所有 M/D 或 YYYY/M/D 日期。"""
    out = []
    # YYYY/M/D
    for m in re.finditer(r"(\d{4})/(\d{1,2})/(\d{1,2})", s):
        try:
            out.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    # M/D (排除已被 YYYY/M/D 抓走的)
    cleaned = re.sub(r"\d{4}/\d{1,2}/\d{1,2}", "", s)
    for m in re.finditer(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", cleaned):
        try:
            out.append(date(default_year, int(m.group(1)), int(m.group(2))))
        except ValueError:
            continue
    return out


def has_year_long(s: str) -> bool:
    return any(kw in s for kw in YEAR_LONG_KEYWORDS)


def get_event_end_date(info_date_str: str, today: date) -> date | None:
    """
    從活動的 info.date 字串推測「結束日期」。
    回傳 None 代表全年型 / 無法解析(視為不過期)。
    """
    if not info_date_str:
        return None
    if has_year_long(info_date_str):
        return None
    dates = extract_dates(info_date_str, today.year)
    if not dates:
        return None
    return max(dates)


def is_expired(info_date_str: str, today: date) -> bool:
    end = get_event_end_date(info_date_str, today)
    if end is None:
        return False
    return end < today


def is_in_future_window(info_date_str: str, today: date, days: int = 14) -> bool:
    """活動在未來 N 天內仍可參加(含當天)。"""
    if not info_date_str:
        return False
    if has_year_long(info_date_str):
        return True
    dates = extract_dates(info_date_str, today.year)
    if not dates:
        return False
    end = today + timedelta(days=days)
    # 任一日期在 [today, today+days] 區間,或活動橫跨此區間
    earliest = min(dates)
    latest = max(dates)
    if latest < today:
        return False
    if earliest > end:
        return False
    return True


def get_iso_week_tag(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def check_topics() -> dict:
    """檢查 topics 資料夾文章覆蓋。"""
    if not TOPICS_DIR.exists():
        return {"exists": False, "count": 0, "files": []}
    files = sorted(TOPICS_DIR.glob("*.html"))
    return {
        "exists": True,
        "count": len(files),
        "files": [f.name for f in files],
        "newest": max((f.stat().st_mtime for f in files), default=0),
    }


def check_files() -> dict:
    """檔案大小檢查。"""
    out = {}
    for fname in ["index.html", "articles.json"]:
        p = SITE_DIR / fname
        out[fname] = p.stat().st_size if p.exists() else 0
    return out


def main():
    today = date.today()
    week_tag = get_iso_week_tag(today)

    if not ARTICLES_JSON.exists():
        print(f"[ERROR] {ARTICLES_JSON} 不存在", file=sys.stderr)
        return 1

    with ARTICLES_JSON.open(encoding="utf-8") as f:
        articles = json.load(f)

    # === 核心檢查 1:過期活動 ===
    expired = []
    for a in articles:
        info_date = a.get("info", {}).get("date", "")
        if is_expired(info_date, today):
            end_d = get_event_end_date(info_date, today)
            expired.append({
                "id": a.get("id"),
                "title": a.get("title"),
                "info_date": info_date,
                "end_date": end_d.isoformat() if end_d else None,
                "days_past": (today - end_d).days if end_d else None,
                "week": a.get("week"),
            })

    # === 核心檢查 2:未來 2 週活動 ===
    future_2w = []
    for a in articles:
        info_date = a.get("info", {}).get("date", "")
        if is_in_future_window(info_date, today, days=14):
            future_2w.append({
                "id": a.get("id"),
                "title": a.get("title"),
                "info_date": info_date,
                "region": a.get("region", a.get("category", "?")),
            })

    # === 附加資訊 ===
    week_dist = Counter(a.get("week", "?") for a in articles)
    region_dist = Counter(a.get("region", a.get("category", "?")) for a in articles)
    age_dist = Counter()
    for a in articles:
        for ag in a.get("age_range", []):
            age_dist[ag] += 1

    topics = check_topics()
    files = check_files()

    # === 健康判斷 ===
    n_expired = len(expired)
    n_future = len(future_2w)
    alerts = []
    if n_expired >= 3:
        alerts.append(f"過期活動 {n_expired} 個 ≥ 3 (建議下架)")
    if n_future < 4:
        alerts.append(f"未來 2 週可去活動只有 {n_future} 個 < 4 (空窗警報)")

    has_alert = bool(alerts)

    result = {
        "date": today.isoformat(),
        "week_tag": week_tag,
        "total_articles": len(articles),
        "expired_count": n_expired,
        "expired": expired,
        "future_2w_count": n_future,
        "future_2w": future_2w,
        "week_distribution": dict(week_dist.most_common()),
        "region_distribution": dict(region_dist.most_common()),
        "age_range_distribution": dict(age_dist.most_common()),
        "topics": topics,
        "file_sizes": files,
        "alerts": alerts,
        "has_alert": has_alert,
    }

    # === 輸出 ===
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 純文字摘要(給 scheduler 抓)
        print(f"=== Kiddo POST 網站健檢 | {today} ({week_tag}) ===")
        print(f"總活動數:     {len(articles)}")
        print(f"過期(該下架): {n_expired}")
        print(f"未來 2 週可去: {n_future}")
        print(f"Topics 文章:  {topics['count']}")
        print()
        if expired:
            print("[過期活動清單]")
            for e in expired:
                d_str = f"({e['days_past']} 天前)" if e['days_past'] is not None else ""
                print(f"  - {e['id']}: {e['title'][:40]} | {e['info_date']} {d_str}")
            print()
        if future_2w:
            print(f"[未來 2 週活動 ({n_future} 個)]")
            for ev in future_2w[:10]:
                print(f"  - [{ev['region']}] {ev['title'][:50]}")
            if n_future > 10:
                print(f"  ... 還有 {n_future - 10} 個")
            print()
        if alerts:
            print("[警報]")
            for a in alerts:
                print(f"  ⚠️ {a}")
        else:
            print("[健康]")

    if "--report" in sys.argv:
        report_path = SITE_DIR / "review-reports" / f"health-{week_tag}.json"
        report_path.parent.mkdir(exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] 健檢報告: {report_path}", file=sys.stderr)

    return 2 if has_alert else 0


if __name__ == "__main__":
    sys.exit(main())
