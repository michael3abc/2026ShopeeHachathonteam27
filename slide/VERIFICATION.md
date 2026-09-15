# Presentation verification

2026-09-12，內容基準 `main@8c0c49068d3b46f79232198ef9167b228cf16403`。

- `node --check slide/js/presentation.js`：PASS。
- `node --check slide/verify-browser.mjs`：PASS。
- `node slide/verify-browser.mjs`：PASS，Chromium / Playwright 1.63.0。
- 真正 `file://` ＋ offline：HTML、CSS、JS 正常，無 HTTP(S) resource requests。
- 八頁於 1440×900、1280×720 無水平／垂直 overflow；390×844 無水平 overflow。
- 架構 progressive reveal 與反向操作、總覽跳頁、Home / End、講者筆記、來源視窗、計時 start / pause / reset：PASS。
- 全螢幕 enter / exit、所有投影片 print visibility：PASS。
- `presentation/presentation.html` 捷徑、Pages subpath、hash deep link 與 reload：PASS。
- 八頁共 325 秒；HTML ID 唯一、local assets 與 pinned source 路徑存在。
- `python3 slide/build-pages.py`：PASS，產出 Explorer artifact 下 `slide/` 與 `presentation.html` 捷徑。
- `git diff --check`：PASS。

截圖保留在 `/tmp/return-atlas-keynote-verification/`。本機 sandbox 禁止 Chromium 啟動，使用已獲准的 sandbox 外執行完成上述瀏覽器驗證。

未執行 Live Demo 或業務 E2E；未部署 GitHub Pages。Codex 頁依使用者指示略過。來源連結需要網路，但靜態簡報無外部依賴。未驗證 Safari / Firefox。
