# Explorer 驗證結果

驗證時間：2026-09-12 07:53:58 UTC。瀏覽器：Chromium 153.0.8010.12；Playwright 1.63.0。

## 基準與交付

- Source：`c70351e4a8f711698def4e5fd9cec28fdae215a9`，branch 記錄為 `main`。
- 描述的 profiles：API `integrated-demo`；Agent `integrated-qwen`。
- 入口：`dist/index.html` 與 `offline/index.html`；內容相同。
- 單一 HTML 約 654 KiB（669,164 bytes），含全部資料、JS、CSS 與離線 source excerpts；無 CDN、Backend 或模型請求。
- 90 entities、16 個實際 Graph nodes、42 條含 START / END 的 source-supported routes、129 source references。
- 七種實際 ModelTask 呼叫，加上獨立 embedding call；有 payload expression、packaged prompt、output type 與 adapter 說明。

## 執行命令與結果

於 `presentation/` 執行：

```bash
npm install --ignore-scripts --no-audit --no-fund
npm run check
npm run test:browser
```

全部通過。`npm run check` 包含 JavaScript syntax check、固定 SHA rebuild、source / routing / schema / references 驗證，以及離線 bundle parity 與關鍵架構 regression checks。

瀏覽器驗證共 11 組，逐一檢查五個 scenarios 的全部 **125 steps**：

| 驗證項目 | 結果 |
| --- | --- |
| GitHub Pages repository subpath | PASS |
| 六種架構視圖、UI mapping、LLM Calls、Code Map | PASS |
| 深連結重新整理、node 鍵盤操作、state inspector | PASS |
| Zoom / Fit、連線篩選、關係細節 | PASS |
| 高階分組展開、browser back | PASS |
| 搜尋無結果、LLM task 搜尋與 payload / prompt | PASS |
| 五個場景全部 125 steps 的標題與 Backend status | PASS |
| Previous / Next / Play / Pause / Restart、場景切換重設 | PASS |
| 390px 手機版、圖形列表模式、reduced motion | PASS |
| 真正 file:// 且 offline context 的圖、搜尋、LLM source 與回放 | PASS |
| Page / console errors = 0；外部 runtime requests = 0 | PASS |

測試期間修正：hash navigation 的測試等待條件、精確 LLM 搜尋結果定位、手機版長路徑與 grid intrinsic width 溢出、深色區域按鈕對比。

已檢視桌面首頁、Graph inspector 與手機首頁截圖；所有測試 server 與 browser 在測試結束時關閉。

原始碼格式整理後，重新通過 `npm run check`，並以桌面斷網瀏覽器補驗 10 個視圖與回放 Next，無 page errors。依後續使用者指示，桌面為主要驗收目標，手機不列為後續優化重點。

## 可檢視的 artifacts

`verification-artifacts/browser-report.json` 保存完整機器可讀結果。

- `01-overview-desktop.png`：作品首頁。
- `02-graph-desktop.png`：真實 Graph 與 state inspector。
- `03-llm-desktop.png`：實際 model task / payload / prompt。
- `04-trace-desktop.png`：案件回放。
- `05-overview-mobile.png`：390px 手機首頁。
- `06-offline.png`：斷網 file:// 閱覽與回放。

## 已知限制

- 五個案例均為 **Illustrative**；不是 Recorded execution。來源中的業務測試定義有引用，但這一輪沒有重跑 Backend / Agent 業務測試或 live LLM E2E。
- 沒有 captured model HTTP response、token usage、完整 state snapshots 或實際 latency。LLM call 指實作中的真實呼叫點與組裝方式。
- 沒有正式平台金流、真實客戶資料、正式 Human Review authentication 或 B→C 學習改善實測。
- 不包含其他 worktree 的未合併功能。未更動應用程式 runtime、API contracts 或 DB schema。
- Graph 路由檢查是基於指定版本的 AST inventory 與 reviewed catalogue，不是任意 Python 控制流的可達性證明。
- 沒有做新工程師的 10 分鐘理解實驗，也沒有跨 Firefox / Safari 或 Windows 瀏覽器矩陣驗證。
- 本次只交付本地 build；**未發布 GitHub Pages**。
