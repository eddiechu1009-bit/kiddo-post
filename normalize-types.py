#!/usr/bin/env python3
"""
normalize-types.py — Kiddo POST 活動 type / venue 欄位正規化 / 稽核

前端「類型」篩選器是直接把 type 字串去重當選項（index.html:
`new Set(ALL_ARTICLES.map(a => a.type))`），2026-11 健檢時 type 有 73 種
自由寫法、大半只出現 1 次 → 篩選器形同失效，也無法統計類型分布。
venue 篩選是字串相等比對，「室內＋戶外」「室內 / 戶外」這類寫法
在「室內」「戶外」兩個選項下都不會出現。

口徑（2026-11-05，Eddie 指示「分類先做」）：
  type 收成 7 類（不含室內/戶外 —— 那是 venue 欄位的事，避免重複）：
    展覽 · 表演 · 節慶市集 · 樂園動物園 · 戶外踏青 · 戲水 · 親子體驗
  原本的細類（如「光影展」「花火大會」）不丟：自動補進 tags，關鍵字搜尋照樣找得到。
  venue 收成 3 值：室內 · 戶外 · 室內＋戶外（「半室內」併入 室內＋戶外）。
  認不出來的值只報不改，請把它加進下面的 TYPE_MAP 再跑。

用法:
  python parent-intel-site/normalize-types.py          # 稽核（不改檔），有問題 exit 2
  python parent-intel-site/normalize-types.py --fix    # 實際改寫 articles.json
  python parent-intel-site/normalize-types.py --fix --quiet

退出碼: 0 乾淨 / 2 有待正規化或認不出來的值 / 1 腳本錯誤
"""
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SITE_DIR = Path(__file__).resolve().parent
TARGET = SITE_DIR / "articles.json"

TYPE_CANON = ["展覽", "表演", "節慶市集", "樂園動物園", "戶外踏青", "戲水", "親子體驗"]

_GROUPS = {
    "展覽": [
        "展覽", "特展", "主題展", "光影展", "光影藝術展", "光影藝術", "燈光藝術",
        "體驗型展覽", "美術館", "博物館", "兒童館", "親子展區", "VR 沉浸體驗",
    ],
    "表演": [
        "表演", "音樂會", "音樂節", "劇場", "展演", "藝術節", "藝術節/表演",
        "影片放映", "影城限定企畫",
    ],
    "節慶市集": [
        "嘉年華", "祭典", "節慶", "節慶活動/小展", "萬聖節活動", "萬聖節",
        "燈節", "花火大會", "花火", "煙火", "文化活動", "文化節", "美食祭",
        "市集", "市集/物產展", "耶誕市集", "街區活動", "快閃店",
        "主題活動", "主題月活動",
    ],
    "樂園動物園": [
        "主題樂園", "遊樂園", "動物園", "動物園活動", "水族館", "主題列車", "套票",
    ],
    "戶外踏青": [
        "花季活動", "花海", "賞花", "步道", "觀星", "戶外休憩", "戶外體驗/遊船",
        "共融遊戲場", "遊戲場",
    ],
    "戲水": ["水樂園", "戲水區", "戲水", "親水活動"],
    "親子體驗": [
        "體驗", "手作工作坊", "食農體驗", "科學節", "科學活動", "科學教育",
        "防災教育活動", "實境解謎", "闖關遊戲", "集章", "集章活動",
    ],
}
TYPE_MAP = {raw: canon for canon, raws in _GROUPS.items() for raw in raws}

VENUE_CANON = {"室內", "戶外", "室內＋戶外"}
VENUE_MAP = {
    "室內+戶外": "室內＋戶外", "室內 / 戶外": "室內＋戶外", "室內/戶外": "室內＋戶外",
    "戶外＋室內": "室內＋戶外", "半室內": "室內＋戶外",
}


def normalize_record(rec: dict) -> tuple[bool, list[str]]:
    changed, notes = False, []
    t = (rec.get("type") or "").strip()
    if t and t not in TYPE_CANON:
        canon = TYPE_MAP.get(t)
        if canon:
            tags = rec.get("tags") or []
            if t not in tags:
                tags.append(t)
            rec["tags"] = tags
            rec["type"] = canon
            changed = True
        else:
            notes.append(f"{rec.get('id', '?')}: type 認不出來 {t!r}")
    v = (rec.get("venue") or "").strip()
    if v and v not in VENUE_CANON:
        canon = VENUE_MAP.get(v)
        if canon:
            rec["venue"] = canon
            changed = True
        else:
            notes.append(f"{rec.get('id', '?')}: venue 認不出來 {v!r}")
    return changed, notes


def main() -> int:
    fix = "--fix" in sys.argv
    quiet = "--quiet" in sys.argv
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("[ERROR] articles.json 不是 list", file=sys.stderr)
        return 1

    before_t = Counter(r.get("type") for r in data)
    before_v = Counter(r.get("venue") for r in data)
    changed_ids, manual = [], []
    for rec in data:
        changed, notes = normalize_record(rec)
        if changed:
            changed_ids.append(rec.get("id", "?"))
        manual.extend(notes)
    after_t = Counter(r.get("type") for r in data)
    after_v = Counter(r.get("venue") for r in data)

    if not quiet:
        print(f"type 選項數: {len(before_t)} → {len(after_t)} | venue 選項數: "
              f"{len(before_v)} → {len(after_v)} | 需正規化筆數: {len(changed_ids)}")
        for k, c in after_t.most_common():
            print(f"  type {k}: {c}")
        for k, c in after_v.most_common():
            print(f"  venue {k}: {c}")

    if fix and changed_ids:
        out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        TARGET.write_bytes(out.encode("utf-8"))  # LF + UTF-8 無 BOM
        if not quiet:
            print("  [OK] 已寫回 articles.json")

    if manual:
        print("\n[需人工確認 —— 把新值加進 TYPE_MAP / VENUE_MAP 再跑]")
        for m in manual:
            print(f"  ⚠️ {m}")
    if not quiet:
        print(f"\n合計 {'已修' if fix else '待修'} {len(changed_ids)} 筆；需人工 {len(manual)} 筆")

    if manual or (changed_ids and not fix):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
