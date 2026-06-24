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

# 開始日 / 進行中語意:字串只給「開始日」沒給結束日,抓到的日期是起點不是終點,
# 不可拿來判過期(否則「6/19 起」「首演起」會被誤判成當天就結束)。
ONGOING_KEYWORDS = ["起", "首演", "首場", "開園", "開展", "開幕", "登場",
                    "開唱", "開跑", "陸續", "預售", "巡演", "巡迴", "起跑"]

# 範圍符號(連接起訖日期)
RANGE_SEP = r"[~～\-－—到至]"

# 多場次活動:只抓得到首場日期,結束日不可靠 → 視為進行中
MULTI_SESSION_RE = re.compile(r"共\s*\d+\s*[場天梯次]")

# 範圍符號後接模糊詞(如「~ 暑假」「~ 另行通知」):沒有明確結束日 → 視為進行中
VAGUE_END_RE = re.compile(RANGE_SEP + r"\s*(暑假|寒假|待定|另行|連假|月底|底|陸續|預計|不定)")

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


def has_explicit_range(s: str) -> bool:
    """字串是否含「日期 範圍符號 日期」的封閉區間(如 6/21~6/28、4/3 - 9/28)。"""
    pat = r"\d{1,2}/\d{1,2}\s*" + RANGE_SEP + r"\s*\d{1,2}/\d{1,2}"
    return re.search(pat, s) is not None


def get_event_end_date(info_date_str: str, today: date) -> date | None:
    """
    從活動的 info.date 字串推測「結束日期」。
    回傳 None 代表全年型 / 進行中 / 無明確結束日(一律視為不過期)。

    重點:只有「明確封閉日期區間」或「單一明確日期」才當結束日判過期。
    碰到開始日語意(起/首演/共N場/~暑假…)就回 None,避免把進行中活動誤判成過期。
    """
    if not info_date_str:
        return None
    if has_year_long(info_date_str):
        return None
    # 多場次(共N場)/ 模糊結尾(~暑假)→ 結束日不可靠
    if MULTI_SESSION_RE.search(info_date_str) or VAGUE_END_RE.search(info_date_str):
        return None
    # 有開始日語意但「沒有」封閉日期區間 → 只有起點,視為進行中
    has_ongoing = any(kw in info_date_str for kw in ONGOING_KEYWORDS)
    if has_ongoing and not has_explicit_range(info_date_str):
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


def classify_expiry(article: dict, today: date) -> dict | None:
    """判斷一篇活動的過期狀態,回傳 None 表示不算過期。

    優先序:
      1. status == "archived" → 已收起,不報(回 None)。
      2. 有明確 end_date 欄位 → 用它判過期(可自動收)。
      3. 無 end_date → 退回字串推測(已修起/首演/共N場誤判);
         字串能推出結束日且已過 → 標「需人工確認」(語意較弱)。

    回傳 dict 含 mode: "auto"(有 end_date,可自動 archive)
                 / "review"(僅字串推測,建議人工確認)。
    """
    if article.get("status") == "archived":
        return None  # 已收起,不再報

    end_date_str = article.get("end_date")
    info_date = article.get("info", {}).get("date", "")

    # 2. 明確 end_date 欄位
    if end_date_str:
        try:
            end_d = date.fromisoformat(end_date_str)
        except ValueError:
            end_d = None
        if end_d and end_d < today:
            return {
                "id": article.get("id"), "title": article.get("title"),
                "info_date": info_date, "end_date": end_date_str,
                "days_past": (today - end_d).days, "week": article.get("week"),
                "mode": "auto",
            }
        return None  # 有 end_date 但還沒過,或無法解析

    # 3. 無 end_date → 字串推測(較弱,標 review)
    if is_expired(info_date, today):
        end_d = get_event_end_date(info_date, today)
        return {
            "id": article.get("id"), "title": article.get("title"),
            "info_date": info_date,
            "end_date": end_d.isoformat() if end_d else None,
            "days_past": (today - end_d).days if end_d else None,
            "week": article.get("week"), "mode": "review",
        }
    return None


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
    # status==archived 不報;有 end_date 已過 → auto;僅字串推測 → review
    expired = []
    for a in articles:
        e = classify_expiry(a, today)
        if e:
            expired.append(e)
    expired_auto = [e for e in expired if e["mode"] == "auto"]
    expired_review = [e for e in expired if e["mode"] == "review"]

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
    n_auto = len(expired_auto)
    n_review = len(expired_review)
    n_future = len(future_2w)
    alerts = []
    # auto(有 end_date 且已過)可信度高,任何 1 個都該收
    if n_auto >= 1:
        alerts.append(f"過期活動 {n_auto} 個有明確結束日已過 (可下架/標 archived)")
    # review(僅字串推測)較弱,沿用 ≥3 門檻避免噪音
    if n_review >= 3:
        alerts.append(f"另有 {n_review} 個疑似過期需人工確認 (無 end_date,字串推測)")
    if n_future < 4:
        alerts.append(f"未來 2 週可去活動只有 {n_future} 個 < 4 (空窗警報)")

    has_alert = bool(alerts)

    result = {
        "date": today.isoformat(),
        "week_tag": week_tag,
        "total_articles": len(articles),
        "expired_count": n_expired,
        "expired_auto_count": n_auto,
        "expired_review_count": n_review,
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
        print(f"過期-可下架:  {n_auto} (有明確 end_date 已過)")
        print(f"過期-待確認:  {n_review} (僅字串推測)")
        print(f"未來 2 週可去: {n_future}")
        print(f"Topics 文章:  {topics['count']}")
        print()
        if expired_auto:
            print("[過期-可下架 (end_date 已過,建議標 archived)]")
            for e in expired_auto:
                d_str = f"({e['days_past']} 天前)" if e['days_past'] is not None else ""
                print(f"  - {e['id']}: {e['title'][:40]} | 結束 {e['end_date']} {d_str}")
            print()
        if expired_review:
            print("[過期-待人工確認 (無 end_date,字串推測,可能進行中)]")
            for e in expired_review:
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
        # LF 換行、UTF-8 無 BOM(對齊 CLAUDE.md 寫檔規則)
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        report_path.write_bytes(text.encode("utf-8"))
        print(f"\n[OK] 健檢報告: {report_path}", file=sys.stderr)

    return 2 if has_alert else 0


if __name__ == "__main__":
    sys.exit(main())
