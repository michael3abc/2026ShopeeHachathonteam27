# Return Atlas — Technical Keynote

直接用瀏覽器開啟 **[presentation.html](presentation.html)**。不需 build、server、CDN、套件或 Backend。`presentation/presentation.html` 亦可進入同一份簡報。

依最新指示，Codex 頁先略過；Live Demo 僅保留切換提示，不串接、不模擬系統。八頁總長 **5:25**：Slides 4:00 + Demo 1:25，保留 35 秒 buffer。

| 頁 | 主題 | 秒 |
| --- | --- | ---: |
| 1 | 為什麼需要 Agent | 30 |
| 2 | 完整系統與 state ownership | 45 |
| 3 | Controlled Autonomy | 50 |
| 4 | Learning Without Losing Control | 35 |
| 5 | Reliability Is Part of the Agent | 35 |
| 6 | Live Demo 切換提示 | 85 |
| 7 | Resolution ≠ Execution | 25 |
| 8 | Trustworthy Domain Agent | 20 |

## 操作

- `→` / `Space` / `PageDown`：下一步。架構頁分三階段展開。
- `←` / `PageUp`：上一步；`Home` / `End`：第一頁／最後一頁。
- `O`：總覽並跳頁。`N`：本頁講稿、時間與操作提示。
- `F`：全螢幕。`T`：開始／暫停總計時。`R`：重設計時。
- `Esc`：關閉視窗。瀏覽器列印：輸出全部投影片，包含展開內容。
- `#1` 至 `#8`：可直接連到任一頁；重新整理保留頁數。計時需手動開始，重新整理會歸零。

## 內容依據

已用 `git ls-remote origin refs/heads/main` 確認 **main@8c0c49068d3b46f79232198ef9167b228cf16403**（2026-09-12）。每個技術頁的 SOURCE 提供 pinned source 連結；敘事依本機同一 commit 的 implementation 與 specs 核對。`js/presentation.js` 包含逐頁講稿、範圍限制與來源。

樣式沿用 `presentation/src/style.css` 的 typography、paper / ink / muted / green / blue / violet tokens、16px radius 與 card / diagram language，另以深綠與 lime 建立 keynote 重點。圖為原生 HTML / CSS，沒有遠端字型或素材依賴。

Runtime 圖是主要步驟的閱讀順序，非完整 raw graph；Monetary / User Risk gates 位於 `reviewer` 的 deterministic code。Memory 不會自動核准；v2 FULL_REFUND 的 correction / APPLIED join 與其他 outcome admission 分開。簡報不宣稱正式 Shopee 金流、學習效果量測或本次 live E2E 通過。

## GitHub Pages

可直接發布整個 `slide/`，入口 `presentation.html`（`index.html` 會導向該入口）。相對 CSS / JS 路徑支援 repo subpath。既有 Pages workflow 另將此目錄複製至 Explorer artifact 的 `slide/`；部署後以 `slide/presentation.html` 存取，不覆蓋 Explorer 首頁。另有 artifact 根目錄 `presentation.html` 捷徑。

```bash
node --check slide/js/presentation.js
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node slide/verify-browser.mjs
```

瀏覽器驗證包括真實 `file://`、離線、逐步展開、鍵盤、總覽、筆記、計時、source dialog、所有頁面桌面邊界與 Pages subpath。只驗證簡報，不操作業務 Backend。
