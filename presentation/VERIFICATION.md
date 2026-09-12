# Explorer 驗證結果

## 基準與交付

- Source：`586c3aa0cce63bc6100f63f9335162d32bd968d1`（`main` 記錄）。
- Profile：API `integrated-demo`；Agent `integrated-compass`。Compass 預設 `compass-5.6-terra`、`reasoning_effort=medium`、Responses API；service composition 注入 image evidence adapter。
- 入口：`dist/index.html`（GitHub Pages artifact）與 `offline/index.html`（可直接以 `file://` 開啟）；兩者由相同資料產生。
- 靜態內容：18 個真實 LangGraph nodes、50 條含 START / END 的 source-supported routes、118 entities、170 immutable source references；API route inventory 含 Policy／Return confirmation、trusted return events 與 image attachments。
- LLM Calls 顯示七種 source-backed `ModelTask` 與獨立 embedding call；這是 call contract 與組裝證據，不是已擷取的 live model request/response。

## 已執行內容檢查

```bash
cd presentation
python3 build.py
node --check src/app.js
node verify-content.mjs
```

結果：PASS。生成 `dist/`、`offline/`、`architecture-data.json`、`source-manifest.json` 與 `content-checks.json`。檢查固定 SHA 引用、18/50 Graph inventory、Policy v2、User Risk、return fulfillment、七種 ModelTask、image evidence、11 個 UI statuses、六條 scenario transitions、architecture-sync scope、source references 與兩個 build 的一致性。

## 已執行瀏覽器驗證

```bash
cd presentation
npm ci
npm run check
npm run test:browser
```

結果：PASS。Chromium / Playwright 執行 11 組檢查、六個 illustrative scenarios 共 170 steps；七段 rail、Pages repository subpath、path-style hash deep links、搜尋、breadcrumb、component drill-down、Graph / State Inspector、LLM/image call detail、Previous / Next / Play / Pause / Restart、瀏覽器返回、重新整理與 `file://` 離線模式均通過。零 console error、零外部 runtime request。截圖驗證使用 1440×900 與 1366×768；手機版不在驗收範圍。

## 已知限制

- 六個回放皆為 **Illustrative**；不是 Recorded execution，也沒有重放 live LLM。
- 沒有 captured model HTTP response、token usage、完整 state snapshots、latency 或新工程師 10 分鐘理解實驗。
- `integrated-demo` 的 order / evidence 與 refund application 仍是 fixture / deterministic demo；沒有正式金流或真實客戶資料。
- Graph route catalogue 是指定版本 AST 加上 reviewed conditions，不是任意 Python control flow 的完整可達性證明。
- 未混入其他 worktree 的未提交或未合併功能；未修改應用程式 runtime、API contracts 或 DB schema。
