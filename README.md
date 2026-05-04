# 🎨 Kiddo POST · 亞麻親子情報站

每週精選大台北、全台、日本親子活動、學習資源；地圖視角 + 多維度篩選，對照年齡提供發展與健康建議。

🔗 **網站：** <https://eddiechu1009-bit.github.io/kiddo-post/>
📦 **Repo：** <https://github.com/eddiechu1009-bit/kiddo-post>

## 📁 檔案結構

```
kiddo-post/ (parent-intel-site)
├── index.html          # 單頁 SPA, 5 個 Tab 整合
│                         (本週精選 / 瀏覽 / 地圖 / 行事曆 / 議題)
├── articles.json       # 活動資料庫
├── review-reports/     # 月度健康檢查報告
├── .nojekyll           # 關閉 GitHub Pages Jekyll
├── .gitignore
└── README.md
```

## 🎨 設計風格

繪本風 — 參考 **麵包小偷** / **野貓軍團** / **好餓的毛毛蟲**。

**色系**
- 底色 奶油白 `#fdf6ec`
- 番茄橘 `#ff7a45` · 薄荷青 `#2ba89a` · 櫻花粉 `#ff9eb5` · 蜂蜜黃 `#ffc93c`

**字型**（UX Pro Max 「Playful Creative」pairing）
- Fredoka 標題（圓潤展示字）
- Noto Sans TC 中文內文
- Nunito 拉丁內文
- Caveat 手寫口吻點綴

**質感** — 粗邊框、虛線分隔、大圓角、微旋轉貼紙、手繪 emoji 裝飾。

## 🧩 Tab 結構

| Tab | 內容 |
|-----|------|
| 📰 **本週精選** | Hero banner + 本週最新 6 則情報 + 側欄撇步 + 訂閱入口 |
| 🎨 **活動瀏覽** | 多 facet 篩選：地區 / 類型 / 場域 / 年齡 / 費用 + 關鍵字 |
| 🗺️ **地圖** | Leaflet + OSM，pin 按分類著色，點擊開 popup |
| 📅 **行事曆** | 5~8 月月曆卡片 |
| 💡 **親子議題** | 6 大分類：發展、教育、心理、健康、家庭、安全（籌備中） |

## 🔍 搜尋

- **Nav 全站搜尋**：跨 articles + calendar + topics 的即時搜尋
- **快捷鍵**：`Ctrl/Cmd + K` 聚焦搜尋框
- **Browse Tab 內搜尋**：配合 facet 疊加篩選

## 🗂️ 資料格式 (articles.json)

```json
{
  "id": "bubble-show-2026",
  "date": "2026-05-04",
  "week": "2026-W18",
  "category": "taipei | outside | japan | development",
  "region": "台北市 | 新北市 | 日本 | ...",
  "district": "信義區",
  "type": "表演 | 展覽 | 共融遊戲場 | 遊樂園 | ...",
  "venue": "室內 | 戶外",
  "age_range": ["0-3", "3-6", "6-12"],
  "cost": "免費 | 付費",
  "facilities": ["哺乳室", "親子廁所", "無障礙", "停車場", "捷運可達"],
  "tags": ["付費", "室內", "劇場"],
  "coord": [25.0406, 121.5598],
  "title": "...",
  "summary": "...",
  "highlight": "推薦理由 / 撇步",
  "info": { "date": "...", "location": "...", "age": "...", "price": "..." },
  "source_name": "...",
  "sources": [{ "name": "...", "url": "..." }]
}
```

## 🚀 本機預覽

```bash
cd parent-intel-site
python -m http.server 8080
# 瀏覽器開 → http://localhost:8080
```

## 📤 部署到 GitHub Pages

這個資料夾要推到 <https://github.com/eddiechu1009-bit/kiddo-post>

```bash
cd parent-intel-site
git init
git add -A
git commit -m "🧸 init Kiddo POST"
git branch -M main
git remote add origin https://github.com/eddiechu1009-bit/kiddo-post.git
git push -u origin main
```

推完後到 Repo Settings → Pages：
- Source: `main` / root → Save
- 等 1~2 分鐘 <https://eddiechu1009-bit.github.io/kiddo-post/> 會上線

## 🔄 每週更新流程

1. 產出新的 `parent-intel/weekly-report-YYYY-Www.html`
2. 從週報抽出活動卡片，更新 `articles.json`（加入新活動、移除已結束的）
3. `git commit -am "update W19" && git push`
4. GitHub Pages 1~2 分鐘內自動發佈

## 📝 週報 ↔ 網站同步原則

| 項目 | 週報 | 網站 |
|------|------|------|
| **時間範圍** | 只收錄未來 2 週（結束日 ≥ 本週三） | 所有未結束的活動 |
| **篇幅** | 精選 + 推薦理由 + Action | 同上 + facet 標籤 + 座標 |
| **更新週期** | 每週三寄信 | 同步更新 articles.json |
| **連結** | 週報 CTA 按鈕 → Kiddo POST | — |
