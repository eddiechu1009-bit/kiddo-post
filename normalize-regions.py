#!/usr/bin/env python3
"""
normalize-regions.py — Kiddo POST region 欄位正規化 / 稽核

前端的區域篩選器與地圖 chip 都是**直接把 region 字串去重當選項**
（index.html: `new Set(ALL_ARTICLES.map(a => a.region))`），
所以「台北市 / 臺北市」「東京 / 東京都 / 日本 東京」這種混用
會把同一個地方切成兩三個選項。2026-09 健檢連兩個月抓到，
而且新資料每次都會長出新的混用值 —— 這是產出端問題，光修歷史資料沒用。

口徑（2026-09-15 定案，Eddie）：
  · 台灣一律用「台」不用「臺」，且補全「市 / 縣」→ 台北市 / 台中市 / 台南市 / 台東縣 / 花蓮縣
    （現有 95% 資料與 places.json 全部都是這個寫法，改動最小）
  · 日本全部收成單一 region「日本」，都道府県放到 district 最前面
    → region: "日本", district: "東京都 練馬區"
  · 無法自動判斷的（如「新竹」「嘉義」分不出市/縣）只報不改，留人工確認

用法:
  python parent-intel-site/normalize-regions.py            # 稽核（不改檔），有問題 exit 2
  python parent-intel-site/normalize-regions.py --fix      # 實際改寫 articles.json / places.json
  python parent-intel-site/normalize-regions.py --fix --quiet

退出碼:
  0 - 全部乾淨（或 --fix 已修完且無待人工項目）
  2 - 有需要正規化 / 需人工確認的值
  1 - 腳本錯誤
"""
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 排程 OEM 終端中文 print 防亂碼
except Exception:
    pass

SITE_DIR = Path(__file__).resolve().parent
TARGETS = [SITE_DIR / "articles.json", SITE_DIR / "places.json"]

# ── 台灣：正規值（22 縣市，一律「台」）────────────────────────────
TW_CANON = {
    "台北市", "新北市", "基隆市", "宜蘭縣", "桃園市", "新竹市", "新竹縣",
    "苗栗縣", "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "台南市", "高雄市", "屏東縣", "台東縣", "花蓮縣", "澎湖縣", "金門縣",
    "連江縣",
}
# 舊值 → 正規值（含臺/台、缺市縣後綴）
TW_FIX = {
    "臺北市": "台北市", "臺北": "台北市", "台北": "台北市",
    "臺中市": "台中市", "臺中": "台中市", "台中": "台中市",
    "臺南市": "台南市", "臺南": "台南市", "台南": "台南市",
    "臺東縣": "台東縣", "臺東": "台東縣", "台東": "台東縣",
    "花蓮": "花蓮縣", "宜蘭": "宜蘭縣", "基隆": "基隆市",
    "桃園": "桃園市", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "屏東": "屏東縣",
    "高雄": "高雄市", "新北": "新北市", "澎湖": "澎湖縣",
}
# 分不出市/縣 → 只報不改
TW_AMBIGUOUS = {"新竹", "嘉義"}

# 非縣市但合法的 region 值（全台巡演 / 線上等）
REGION_ALLOW = {"全台巡演", "全台", "線上"}

# ── 日本：region 一律「日本」，都道府県移到 district ──────────────
JP_REGION = "日本"
# 舊 region 值 → 該筆的都道府県
JP_REGION_TO_PREF = {
    "東京都": "東京都", "東京": "東京都", "日本 東京": "東京都",
    "日本東京": "東京都", "大阪": "大阪府", "大阪府": "大阪府",
    "日本 大阪": "大阪府", "千葉": "千葉縣", "千葉縣": "千葉縣",
    "日本 千葉": "千葉縣", "埼玉": "埼玉縣", "埼玉縣": "埼玉縣",
    "日本 埼玉": "埼玉縣", "京都": "京都府", "京都府": "京都府",
    "北海道": "北海道", "沖繩": "沖繩縣", "神奈川": "神奈川縣",
    "橫濱": "神奈川縣", "名古屋": "愛知縣", "福岡": "福岡縣",
    "奈良": "奈良縣", "兵庫": "兵庫縣", "神戶": "兵庫縣",
}
# district 開頭若是這些（含簡寫）→ 已含都道府県，不再前綴
JP_PREFS = [
    "東京都", "大阪府", "京都府", "北海道", "神奈川縣", "千葉縣", "埼玉縣",
    "茨城縣", "櫪木縣", "栃木縣", "群馬縣", "山梨縣", "長野縣", "新潟縣",
    "富山縣", "石川縣", "福井縣", "岐阜縣", "靜岡縣", "愛知縣", "三重縣",
    "滋賀縣", "兵庫縣", "奈良縣", "和歌山縣", "鳥取縣", "島根縣", "岡山縣",
    "廣島縣", "山口縣", "德島縣", "香川縣", "愛媛縣", "高知縣", "福岡縣",
    "佐賀縣", "長崎縣", "熊本縣", "大分縣", "宮崎縣", "鹿兒島縣", "沖繩縣",
    "青森縣", "岩手縣", "宮城縣", "秋田縣", "山形縣", "福島縣",
]
# district 開頭的簡寫 → 補成正式都道府県名
JP_DISTRICT_PREF_FIX = {
    "東京": "東京都", "大阪": "大阪府", "京都": "京都府", "奈良": "奈良縣",
    "千葉": "千葉縣", "埼玉": "埼玉縣", "神奈川": "神奈川縣",
    "兵庫": "兵庫縣", "愛知": "愛知縣", "福岡": "福岡縣", "沖繩": "沖繩縣",
    "山梨": "山梨縣", "靜岡": "靜岡縣", "宮城": "宮城縣", "青森": "青森縣",
    "北海道": "北海道",
}


def normalize_record(rec: dict) -> tuple[bool, str | None]:
    """就地正規化一筆資料的 region / district。

    回傳 (是否有改動, 待人工確認訊息 or None)。
    """
    region = (rec.get("region") or "").strip()
    district = (rec.get("district") or "").strip()
    if not region:
        return False, f"{rec.get('id', '?')}: region 空白"

    # 日本
    if region == JP_REGION or region in JP_REGION_TO_PREF:
        pref = JP_REGION_TO_PREF.get(region)  # region 就是「日本」時為 None
        # district 開頭已含都道府県 → 只補正式名稱
        head = district.split(" ")[0] if district else ""
        if head in JP_PREFS:
            new_district = district
        elif head in JP_DISTRICT_PREF_FIX:
            new_district = (JP_DISTRICT_PREF_FIX[head]
                            + district[len(head):])
        elif pref:
            new_district = f"{pref} {district}".strip()
        else:
            # region=日本 且 district 不是都道府県開頭 → 認不出來，留人工
            return False, (f"{rec.get('id', '?')}: region=日本 但 district"
                           f"「{district}」認不出都道府県")
        changed = (region != JP_REGION) or (new_district != district)
        rec["region"], rec["district"] = JP_REGION, new_district
        return changed, None

    # 台灣
    if region in TW_CANON:
        return False, None
    if region in TW_FIX:
        rec["region"] = TW_FIX[region]
        return True, None
    if region in TW_AMBIGUOUS:
        return False, (f"{rec.get('id', '?')}: region「{region}」分不出市/縣，"
                       f"請人工補（district={district}）")
    if region in REGION_ALLOW:
        return False, None
    return False, f"{rec.get('id', '?')}: region「{region}」不在已知清單"


def main() -> int:
    fix = "--fix" in sys.argv
    quiet = "--quiet" in sys.argv
    total_changed, manual = 0, []

    for path in TARGETS:
        if not path.exists():
            print(f"[WARN] {path.name} 不存在，跳過", file=sys.stderr)
            continue
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            print(f"[ERROR] {path.name} 不是 list", file=sys.stderr)
            return 1

        before = Counter(r.get("region") for r in data)
        changed_ids = []
        for rec in data:
            changed, note = normalize_record(rec)
            if changed:
                changed_ids.append(rec.get("id", "?"))
            if note:
                manual.append(f"{path.name} | {note}")
        total_changed += len(changed_ids)
        after = Counter(r.get("region") for r in data)

        if not quiet:
            print(f"=== {path.name} ===")
            print(f"region 選項數: {len(before)} → {len(after)}"
                  f" | 需正規化筆數: {len(changed_ids)}")
            for r, c in sorted(before.items()):
                if after.get(r, 0) != c:
                    print(f"  {r!r}: {c} → {after.get(r, 0)}")

        if fix and changed_ids:
            out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            # LF + UTF-8 無 BOM（對齊 CLAUDE.md 寫檔規則）
            path.write_bytes(out.encode("utf-8"))
            if not quiet:
                print(f"  [OK] 已寫回 {path.name}")

    if manual:
        print("\n[需人工確認]")
        for m in manual:
            print(f"  ⚠️ {m}")

    if not quiet:
        verb = "已修" if fix else "待修"
        print(f"\n合計 {verb} {total_changed} 筆；需人工 {len(manual)} 筆")

    if manual:
        return 2
    if total_changed and not fix:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
