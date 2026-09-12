# 開發進度

此文件追蹤功能里程碑、測試結果與未完成項目。

| 任務 | 狀態 | 證據／未完成 |
| --- | --- | --- |
| T01 骨架與依賴 | 骨架驗證通過 | 四個 packages 可安裝；Python 3.12.0、uv.lock、npm lock；3 項架構／health 測試通過，Next build 通過，Compose config 通過。Docker daemon／映像建置未驗證。 |
| T02 Contracts | 核心契約通過，持續補齊 | 112 份自行生成 schemas、TS、74 項契約測試；Service events、完整 UI／Activity／distillation contracts 與相應驗證仍待補。 |
| T03 API／DB | 未開始 | 待 T02。 |
| T04 能力／退款 | 未開始 | 待 T03。 |
| T05 Graph | 未開始 | 待 T02。 |
| T06 跨服務 | 未開始 | 待 T04、T05。 |
| T07 VDB／Memory | 未開始 | 待 T06。 |
| T08 Activity | 未開始 | 待 T06。 |
| T09 Web | 未開始 | 待 T06–T08。 |
| T10 整合／真模型 | 未開始 | 待 T09；需要允許的模型設定與 credentials。 |

## 驗收追蹤

C01–C36 及 SYS/M01–M08 所有 R 規則目前均尚未驗證。實作時逐項建立測試對應與命令、exit code、耗時證據。

## 執行前置檢查

- Git 使用 main 分支，依通過測試的邏輯里程碑提交。
- 系統：Ubuntu 24.04；Git 2.43.0；Python 3.12.3。
- PATH 未找到 gh、uv、Node/npm、Docker；sudo 無免密碼權限。
- gh 2.100.0、uv 0.12.13、Python 3.12.0、Node 24.21.0、npm 11.19.0 已安裝於使用者目錄。
- Docker 29.8.0 CLI／Compose 5.5.1 已安裝；系統 Docker Engine 29.1.3 已啟動。後續 sudo 驗證成功、安裝系統套件並設定 docker 群組；不儲存密碼。既有 shell 以 `sg docker -c '…'` 使用新群組。
- GitHub 裝置登入完成，帳號 michael3abc；目標名稱查詢回 404，未覆寫任何既有 repo。
- 尚未執行 migration 或呼叫真模型。

## T01 本機測試證據

| 命令 | 結果 |
| --- | --- |
| `uv sync --all-packages` | exit 0；77 個鎖定 packages，四個本機 packages 安裝成功。 |
| `uv run pytest tests/test_architecture.py -q` | exit 0；3 passed，0.51s；Starlette 的第三方 deprecation warning 1 筆。 |
| `npm --prefix apps/web install --no-audit --no-fund` | exit 0；375 packages，約 1 分鐘。 |
| `npm --prefix apps/web run build` | exit 0；Next 16.3.4 編譯、TypeScript 與靜態頁生成成功；編譯 3.0s。 |
| `docker compose config --quiet` | exit 0；僅配置解析，不代表容器已啟動。 |

- `uv sync --frozen --all-packages`：exit 0。
- Node 24.21.0／npm 11.19.0 下 `npm ci --no-audit --no-fund`：exit 0，15s；隨後 `npm run lint`、`npm run typecheck` 均 exit 0、無 lint warning。
- 一次 lint/typecheck 曾與 npm ci 競爭而失敗；安裝完成後依序重跑通過。使用者層級 Node 連結另被切至 22，驗證改用既有 24.21.0 的獨立路徑，未覆寫該連結。

C01–C36、Docker build、DB／Redis／SSE 與 A/B/C 均未驗證。

## T02 核心契約里程碑

- `uv run pytest -q`：exit 0；**77 passed**（74 contracts＋3 architecture），1.66s；第三方 deprecation warning 1 筆。
- `uv run return-agent-export-schemas --check`：exit 0；112 schemas 無 drift。
- `npm --prefix apps/web run contracts -- --check`、`typecheck`、`lint`：全部 exit 0。
- `docker compose up -d --wait api-db agent-db redis`：exit 0；三個本專案容器 healthy。這只驗證服務啟動，尚非 DB migration／跨服務驗收。
- 公開 repo：`https://github.com/michael3abc/2026ShopeeHachathonteam27`；main 已推送。T01 commit `3cedea7` 的 GitHub Actions run `34669340717`：success。

| 規則 | 本次測試證據／剩餘工作 |
| --- | --- |
| M01-R01 | 金額拒絕 float、非有限值；UTC、未知欄位、精確加總、schema／Python shape 測試。 |
| M01-R02 | 十個 claim 完整性、distinguish_from 對稱性。 |
| M01-R03–R04 | C01–C03 的完整 pairs、缺漏／重複、UNSUPPORTED 不等於 CONTRADICTED、逐 item 可退款／拒絕。 |
| M01-R05 | C04 的 artifact/ref/subject/source、補件完整集合、system-only、accepted types union。 |
| M01-R06 | C05 的金額／幣別／scope、Policy authority、draft 禁止 amount；人審金額由最新訂單計算。 |
| M01-R07 | Reviewer APPROVE 必須由自己的 findings 支持；REVISE 必須有 structured objection。 |
| M01-R08 | C06 的早期 proposal 版本、round、event 順序／引用／case、重複 ID。 |
| M01-R09 | 兩種人審入口、四次 REVISE、人審 gate 重新計算及 config hash 變更拒絕。 |
| M01-R10 | 原申請 scope 內人工重判、不可超 scope／最新 order 上限；持久化 handoff/result 綁定待 T04。 |
| M01-R11 | summary 受限內容、Candidate scope／correction provenance／重複 sources；完整 distillation trace 待補。 |
| M04-R04 | C10–C11 門檻 below/equal/above、USD、DECLINE、REVISE 不跑 gate；fingerprint 正規化。 |

C01–C06、C10–C11 的上述**契約子案例**通過；C12–C13 僅已驗證純函式部分。尚未執行退款、不宣稱完整 C01–C36 conformance。
