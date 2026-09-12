# 開發進度

此文件追蹤功能里程碑、測試結果與未完成項目。

| 任務 | 狀態 | 證據／未完成 |
| --- | --- | --- |
| T01 骨架與依賴 | 骨架驗證通過 | 四個 packages 可安裝；Python 3.12.0、uv.lock、npm lock；3 項架構／health 測試通過，Next build 通過，Compose config 通過。Docker daemon／映像建置未驗證。 |
| T02 Contracts | 契約層驗證通過 | 192 份生成 schemas、TS、93 項契約測試；Domain／Provider／Runtime／Service events／UI／Activity／Memory。持久化與執行端驗證續於 T03–T08。 |
| T03 API／DB | 核心持久化通過 | 0001 migration、case create/get/messages/events、atomic outbox；9 項 PostgreSQL 測試與全套 105 項通過，含主庫已有 migration 的隔離回歸。service event 投影接線續於 T06。 |
| T04 能力／退款 | 能力持久化通過，退款實作中 | 可信 context／metadata、exact Policy、冪等 verification、人審 dossier 與內部 token；退款 reservation／application 待驗證。 |
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
| M01-R11 | summary 受限內容、Candidate scope／correction provenance／重複 sources；distillation trace 綁 case／latest proposal／版本且必須有 confirmed correction。 |
| M04-R04 | C10–C11 門檻 below/equal/above、USD、DECLINE、REVISE 不跑 gate；fingerprint 正規化。 |

C01–C06、C10–C11 的上述**契約子案例**通過；C12–C13 僅已驗證純函式部分。尚未執行退款、不宣稱完整 C01–C36 conformance。

## T02 訊息與觀察契約

- 新增 service events、Runtime result／interrupt、公開 case/events、Memory job/result、Activity 與 narration DTO。
- Activity 排除 Memory 文字、raw object 與額外欄位；Narration 僅接受 facts summary，離線結果要求 text=null；event 必須綁定同 case/thread。
- `uv run pytest -q`：96 項測試通過（93 contracts＋3 architecture）；exit 0，2.73s。生成 192 份 schemas；Python schema check、TS drift check、typecheck、lint 均 exit 0。
- 這些是契約與安全條件測試；C30–C36 的 Redis／SSE／背景工作時序仍待整合驗證。

## T03 案件與交易

- `TEST_API_DATABASE_URL=<local test DB> uv run pytest apps/api/tests -q`：exit 0，9 passed，1.83s。每項使用獨立測試 schema。
- 驗證 empty migration／metadata parity、重跑 upgrade、create 與 resume 回滾無孤兒資料、兩個並行補件只有一次接受、409／422／404、公開回應不含 thread_id、case seq 的 user-turn 洞與終態 SSE replay。
- 本機 API DB 已執行 `uv run alembic -c apps/api/alembic.ini upgrade head`，exit 0。
- `.env` 已由使用者提供並授權用於真模型，檔案 mode 0600 且已忽略；僅檢查設定名稱與是否存在，不將秘密值加入輸出。
- 尚未接通 command dispatcher／Agent worker；沒有退款 APPLIED、Memory Candidate 或真模型 A/B/C 證據。
- 主庫 migration 後執行全套：103 passed、2 failed，exit 1，3.65s。失敗原因為測試 schema 透過 search_path 看見 public.alembic_version，誤以為已遷移；已改成明確 version_table_schema，加入每個測試必須持有自身資料表的回歸檢查，等待重跑結果。
- 隔離修正後中途 104 passed、1 failed（metadata 比較誤含 Alembic 版本表）；調整比較使用連線預設 schema 後，API 9 passed／1.72s，全套 105 passed／4.52s，exit 0。每個測試仍檢查自身 schema 的版本表與應用資料表確實存在。
- 已逐筆確認並清除隔離問題產生的 8 筆本機合成測試案件；沒有發布 command，保留資料表與 migration。

### T04 能力持久化

- 新增 0002 migration：可信訂單、Evidence metadata、Policy clauses／retrievals、verification 與 human dossier。
- API PostgreSQL 測試 18 passed，exit 0，3.52s；涵蓋 M04-R01–R03、C19 部分：同 ID／hash 重送、併發驗證、偽造金額／metadata、缺失原 Policy、可信 snapshot 改版、人審未驗證 dossier、內部 token／typed HTTP。
- Policy 暫以精確條件篩選資料表；embedding／pgvector 為 T07 未完成項目。人審提交只是保存 dossier，待投影後才進入 canonical 待審狀態。
