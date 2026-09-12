# Return / Resolve — System Architecture Explorer

Team 27 的互動式系統介紹網站，提供作品介紹、案件回放、六種架構視圖、實際 LLM 呼叫、UI mapping 與 Code Map。主要語言為繁體中文。

主要閱讀與驗收目標為桌面瀏覽器；保留基本響應式布局，不以手機版作為後續優化重點。

## 直接閱讀

- **離線版**：雙擊 [`offline/index.html`](offline/index.html)。不需要 server、網路、帳號或 Backend。
- **GitHub Pages 版**：[`dist/index.html`](dist/index.html)。發布 `dist/` 內容即可。
- 兩個版本內容相同，由同一份資料與原始碼產生。使用 hash routing，支援 repository subpath 與重新整理深連結。
- 原始碼與內容 tracked；build 目錄與瀏覽器截圖 ignored。Clone 後執行一次 build 即可產生兩個入口。

這是靜態 Explorer；不呼叫 LLM、Embedding、API、Redis 或資料庫，也不包含任何 API key。

## 版本與能力基準

`baseline.json` 固定於 `main@e0787068e832962ce65254fae4c70517ef6133d4`，描述 API `integrated-demo` 與 Agent `integrated-compass` 的組裝。此 profile 預設以 `compass-5.6-terra`、`reasoning_effort=medium` 走 Responses API；image evidence 的 HTTP adapter 在 service composition 注入。

內容分析只透過 `git show <SHA>:<path>` 讀取 committed source；不混用未提交文件、其他 worktree 或未合併功能。分支名稱是基準記錄，不會在 build 時追蹤最新分支。

五個案例均為 **Illustrative**，用 source 與 test definitions 設計，沒有載入 live execution。Graph、退款與 Memory 的生命週期分開。完整 `Before / After`、token usage、真實 latency 與學習效果均未記錄。

本網站的 LLM Calls 可展開七種 ModelTask 的實際呼叫點、payload expression、packaged prompt、output type 與 adapter；embedding 單獨呈現。它呈現 source-backed 的真實 LLM call contract，但不送出 live call，也不把 SDK request shape 冒充為 captured request。

## 建置與驗證

建置只有 Python 3.10+ 標準函式庫與 Git 需求；無 production dependencies，不匯入應用程式或連線服務。

```bash
python3 presentation/build.py
node --check presentation/src/app.js
node presentation/verify-content.mjs
```

從 `presentation/` 執行整合命令：

```bash
npm ci
npm run check
npx playwright install chromium
npm run test:browser
```

`playwright` 是唯一開發依賴，版本與既有 Web workspace 對齊；僅用於測試，不進入網站。需 Node.js 20+。

如果測試機已有相容 Playwright，可明確指定 module 的絕對路徑：

```bash
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node presentation/verify-browser.mjs
```

瀏覽器測試使用臨時、僅 loopback 的 HTTP server；結束時關閉 server 與 browser。測試 Pages subpath、深連結、鍵盤、搜尋、回放、真正 `file://` 與斷網模式。輸出至 `verification-artifacts/`；桌面版是本交付的驗收目標。

## 內容與生成檔

| 檔案 | 用途 |
| --- | --- |
| `baseline.json` | 唯一 source snapshot 與 profile 條件 |
| `content.py` | Reviewed narrative、entities、relationships、路由條件與 scenarios |
| `build.py` | 固定版本讀取、AST inventory、引用驗證與兩種 build |
| `src/` | HTML template、CSS 與無外部請求的瀏覽器 JavaScript |
| `architecture-data.json` | 生成的共用內容模型；所有視圖使用同一份資料 |
| `source-manifest.json` | 固定 SHA、路徑、symbol、行號、source checksum 與離線 excerpt |
| `content-checks.json` | 內容一致性檢查結果 |
| `VERIFICATION.md` | 本輪驗證結果與限制 |

JSON 生成檔供檢視與重現；請修改 Python source，再重新 build，不直接手改生成資料。

來源標示與範例來源是兩個獨立維度：`Source verified / Inferred / Unknown` 描述結論的依據；`Recorded execution / Test fixture / Illustrative` 描述案例資料來源。Source verified 不等於實跑通過。

## Graph 的抽取界線

本版 Graph 共用 conditional destinations。`build.py` 從各 node 的 `_route` 寫入抽取候選目的地；Policy v2 的 `evaluate_policy`、`confirm_policy_path` 另自 `policy.py` 解析，再與人工核對的路由條件 catalogue 一致性比對。沒有把全域 destinations 當成所有 nodes 的真實互連。

這是針對該版本的 source 分析，不是任意 Python 程式的動態可達性證明。讀取欄位清單包含 `graph.py` 內 helpers；跨檔案 assembly / validators 的完整行為仍應查看 source。Node writes 為 reviewed output fields；示意 patch 會檢查是否屬於該 node。

網站刻意納入舊 UI 案件圖未列出的 self-loop 與 failure routes；API `execute_refund` 與背景 distillation 不得混入 Graph node 集合。

## 更新到新版本

1. 選定已提交且可取得的 SHA，更新 `baseline.json` 的版本、分析日期與 profile。
2. 檢查 source / spec / config 差異，更新 `content.py` 的 ownership、routes、LLM calls 與 scenarios。
3. 確認每個關係和 patch 的 source。新 API / tables / nodes 不得只為通過 validator 加入假說明。
4. 執行 build 與內容驗證；source symbol 或路由不一致會明確失敗。
5. 執行 browser tests，查看截圖，更新 `VERIFICATION.md` 後提交。

既有 docs/spec 是 Agent 契約；網站不是替代其 ownership 的新 source of truth。

## 發布 GitHub Pages

GitHub Actions workflow 會在 `main` 的 `presentation/**` 更新後發布；仍需 repository Settings → Pages 的 Source 選為 **GitHub Actions**。部署成功後入口為 `https://michael3abc.github.io/2026ShopeeHachathonteam27/`。

以 GitHub Actions 建置後，只上傳 `presentation/dist/` 作為 Pages artifact，使用標準 Pages deployment 工作流程發布。請勿發布整個 repo、`.env`、runtime 資料或 node_modules。

Checkout 必須包含 baseline commit（例如設定 `fetch-depth: 0`），因為 build 從固定歷史 SHA 讀取 source，而不是使用目前工作目錄內容。缺少該 Git object 時 build 會明確失敗。

入口頁位於 artifact 根目錄的 `index.html`；所有內容均內嵌，deep links 使用 `#agent?view=llm&entity=llm%3AREVIEW` 等形式，因此無須 server rewrite。

## 設計

暖白底、深綠灰字、橘色重點、原生 SVG 與分層 detail panel。已讀取 [Collect UI](https://collectui.com/) 與 [S5-Style](https://www.s5-style.com/) 首頁；動態 gallery 素材沒有完整取得，不宣稱複製或逐頁比對其設計。

自製圖形和示意案件畫面皆標示用途，不冒充實際應用程式截圖。Browser screenshots 僅是本 Explorer 的驗證 artifact。
