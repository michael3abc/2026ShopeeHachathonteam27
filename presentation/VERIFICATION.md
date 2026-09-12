# Explorer 驗證結果

## 基準與交付

- Source：`e0787068e832962ce65254fae4c70517ef6133d4`（`main` 記錄）。
- Profile：API `integrated-demo`；Agent `integrated-compass`。Compass 預設 `compass-5.6-terra`、`reasoning_effort=medium`、Responses API；service composition 注入 image evidence adapter。
- 入口：`dist/index.html`（GitHub Pages artifact）與 `offline/index.html`（可直接以 `file://` 開啟）；兩者由相同資料產生。
- 靜態內容：18 個真實 LangGraph nodes、50 條含 START / END 的 source-supported routes、103 entities、142 immutable source references。
- LLM Calls 顯示七種 source-backed `ModelTask` 與獨立 embedding call；這是 call contract 與組裝證據，不是已擷取的 live model request/response。

## 已執行內容檢查

```bash
cd presentation
python3 build.py
node --check src/app.js
node verify-content.mjs
```

結果：PASS。生成 `dist/`、`offline/`、`architecture-data.json`、`source-manifest.json` 與 `content-checks.json`。檢查固定 SHA 引用、node inventory、reviewed route catalogue、state fields、scenario transition、source references 與兩個 build 的一致性。

## 已執行瀏覽器驗證

```bash
cd presentation
npm ci
npm run check
npm run test:browser
```

結果：PASS。Chromium / Playwright 執行 11 組檢查、五個 illustrative scenarios 共 131 steps；Pages repository subpath、hash deep link、搜尋、drill-down、Graph / State Inspector、LLM Call detail、Previous / Next / Play / Pause / Restart、`file://` 離線模式與 console errors 均通過，沒有外部 runtime request。測試腳本仍含基本 390px / reduced-motion smoke；手機版不是本交付的優化或驗收目標。

## 已知限制

- 五個回放皆為 **Illustrative**；不是 Recorded execution，也沒有重放 live LLM。
- 沒有 captured model HTTP response、token usage、完整 state snapshots、latency 或新工程師 10 分鐘理解實驗。
- `integrated-demo` 的 order / evidence 與 refund application 仍是 fixture / deterministic demo；沒有正式金流或真實客戶資料。
- Graph route catalogue 是指定版本 AST 加上 reviewed conditions，不是任意 Python control flow 的完整可達性證明。
- 未混入其他 worktree 的未提交或未合併功能；未修改應用程式 runtime、API contracts 或 DB schema。
