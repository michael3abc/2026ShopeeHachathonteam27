> 以下保留原重建工作的歷史記錄。2026-09-12 起工作樹改為既有實作整合，
> 不表示下列未完成項目已重新實作；現行範圍與驗證入口見根目錄 README。

# 開發進度

此文件追蹤功能里程碑、測試結果與未完成項目。

PostgreSQL CI 回滾驗證修正：當 `0013` 因既有 Activity 稽核歷程拒絕 downgrade 時，PostgreSQL 會將整筆交易還原至呼叫前 revision（含已升級的 `0014`），SQLite 則可能已完成前段 migration。測試依資料庫交易語意檢查 revision，並確認稽核事件筆數未減少；不放寬 migration 的保護条件。

## 2026-09-12 可追溯對話與 Sol-high

- 在遠端 enhancement commit `d409083` 的隔離 worktree 續作，保留原 worktree 未提交變更；本批沒有推送、部署、重啟現有服務或寫入正式 Memory。
- 已實作 API transcript/command 共用訊息 ID、learning trace 的去識別化對話／request 來源／信任標記，以及跨澄清與補件 interrupt 的順序驗證。補件文字只進學習，不改 Resolver inputs／裁決／Activity。
- Distiller prompt 3.1，Compass 的背景模型獨立 Sol/high；Qwen 相容性、Responses wire model/effort/budget、401/429/503 單次失敗及無 fallback 都有測試。
- `make check`：Contracts 91、API 209、Runtime 110、Service 82、跨服務／重建 23，合計 **515 passed**。
- 獨立 PostgreSQL 的 `AGENT_TEST_POSTGRES_URL=... uv run --all-packages pytest apps/agent_service/tests/test_memory_worker.py -q`：**24 passed**；包括從 0001 升至 0002、舊 hash/結果保留、pending profile 衝突與保護來源的 downgrade。CI 加入同一 PostgreSQL 測試。
- `make contracts`／前端 contracts 生成、改動 Python 檔案 Ruff、`git diff --check` 通過。`make check-web`：22 tests、lint、TypeScript／Next production build 通過。API 與 Agent Service Docker build、Compose config 通過。固定 `docs/reconstruction/` 無變更。
- Live smoke：合成 graph／Provider、真實 `compass-5.6-sol`／Responses high，14 events、3 dialogue turns，單次 49.45 秒產生整案回顧及 `OPERATIONAL_METHOD` candidate。未送 store／embedding／approval，沒有模型 retry。ignored `.artifacts/memory-dialogue-sol-smoke.py` 與 `memory-dialogue-sol-smoke-summary.json` 保留命令及摘錄證據。
- **限制**：這不是完整真模型 E2E，也不是圖片辨識、退款或 Memory 效益驗證。模型仍提出「可減少重複取證」的未驗證推論；不因此自動核准候選。切換前仍須處理舊 pending 工作並協調 API/Agent DTO 更新。

## 2026-09-12 全流程 Memory 蒸餾驗證

以下為獨立 `feat/enhance-memory-distill` worktree 的驗證，不變更下方重建里程碑歷史，也未部署或重啟既有服務。

- 已實作：checkpoint 全案 learning trace、無修正／拒絕案件蒸餾、整案回顧與至多一則受限經驗或 SKIP、v2 工作隔離、一般來源事件與保留治理的 0014 migration。修正 DECLINE 不含 return_decision 時的 trace 投影，拒絕 wildcard scope 擴張。
- `make check`：Contracts 80、API 207、Runtime 99、Service 71、跨服務／重建 23，合計 480 項。涵蓋 interrupt/resume、來源不符、PII、trace 缺失／超限、無新經驗、人審與合法拒絕、pending prompt 衝突、v1 job 拒絕及 replay。
- `make check-web`：22 tests、lint、TypeScript／Next production build 通過；`make contracts` 與前端 contracts 生成成功，固定 `docs/reconstruction/` 無修改。
- 獨立 PostgreSQL 上執行 `MEMORY_TEST_POSTGRES_URL=... uv run --all-packages pytest apps/api/tests/test_memory_learning_migration.py -q`：2 passed；保留舊來源／向量／治理與冪等，驗證合法 rollback 及 v2 資料降版拒絕。相同測試加入 CI。
- API、Agent Service、Web Docker build 及 Compose config 通過。測試容器與進程由各隔離 runner 清理；不刪正式資料。

### 真實模型單案 E2E

在 yoyo-laptop 的獨立 WSL worktree，使用既有明示設定的 `compass-5.6-luna`、`text-embedding-3-large`／1536 維；無模型 retry 或 fake fallback。PostgreSQL、Redis、API、Agent 全部隔離；測試治理先退役 demo 預置經驗，來源案未取用人工撰寫 Memory。

| Run | 結果 | 證據 |
| --- | --- | --- |
| `20260912T055422Z` | PASS；81.15 秒 | `CASE-49391403`，補件後 RESOLVED，15 個 COMPLETE trace events，無 revision；真模型產生整案回顧與 OPERATIONAL_METHOD candidate，embedding 入庫。 |
| `20260912T055924Z` | PASS；76.33 秒 | `CASE-78E3AB4D`，同一路徑；加驗 1200 TWD、僅喇叭品項之模擬退款 SUCCEEDED／APPLIED，Memory 重送已由 worker ACK 且首次結果／terminal event 不變。 |

產出的建議是分開判定「商品實體損壞」與「到貨時已損壞」，針對缺口收集同時呈現包裝及損壞位置的補充證據，重新判讀而非照抄退款結果。候選仍為 CANDIDATE、沒有自動核准。

兩次完整產物與 runner 保留於本機忽略的 `mockcase_generater/behavior_v2/`，不提交憑證或原始執行資料。第二次模型結果另通過最新 wildcard scope 驗證；該加嚴檢查於 E2E 後新增，以 deterministic regression 驗證，未再次呼叫模型。

限制：這是合成訂單／證據 metadata 與 demo 退款 adapter，不是圖片辨識、真金流或瀏覽器操作驗收。只證明全流程蒸餾可運作，**尚未證實 Memory 改善下一案**；8 組 A/B/C 先導未執行，也未擴量。切換新版前仍需處理舊版 pending 工作。

| 任務 | 狀態 | 證據／未完成 |
| --- | --- | --- |
| T01 骨架與依賴 | 骨架驗證通過 | 四個 packages 可安裝；Python 3.12.0、uv.lock、npm lock；3 項架構／health 測試通過，Next build 通過，Compose config 通過。Docker daemon／映像建置未驗證。 |
| T02 Contracts | 契約層驗證通過 | 192 份生成 schemas、TS、93 項契約測試；Domain／Provider／Runtime／Service events／UI／Activity／Memory。持久化與執行端驗證續於 T03–T08。 |
| T03 API／DB | 核心持久化通過 | 0001 migration、case create/get/messages/events、atomic outbox；9 項 PostgreSQL 測試與全套 105 項通過，含主庫已有 migration 的隔離回歸。service event 投影接線續於 T06。 |
| T04 能力／退款 | 核心持久化與模擬退款通過 | API 33 項 PostgreSQL 測試；獨立授權、原子人審／RESUME、品項 reservation、APPLIED ledger、未知結果同 key 恢復；跨服務接線待 T06。 |
| T05 Graph | 核心 deterministic 測試通過 | 16 節點、14 項 graph 測試、6 份 prompts、typed fake 與真模型 adapter；durable PostgreSQL checkpoint／跨服務待 T06。 |
| T06 跨服務 | 核心與本機常駐組合通過 | 6 項真 HTTP／Redis／PostgreSQL 整合測試；durable checkpoint／journal／outbox／事件投影／退款 job；本機 offline A=1200 APPLIED。 |
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

C01–C06、C10–C11 的上述**契約子案例**通過；C12–C13 僅已驗證純函式部分。尚未執行退款、…836 tokens truncated…c7料表與 migration。

### T04 能力持久化

- 新增 0002 migration：可信訂單、Evidence metadata、Policy clauses／retrievals、verification 與 human dossier。
- API PostgreSQL 測試 18 passed，exit 0，3.52s；涵蓋 M04-R01–R03、C19 部分：同 ID／hash 重送、併發驗證、偽造金額／metadata、缺失原 Policy、可信 snapshot 改版、人審未驗證 dossier、內部 token／typed HTTP。
- Policy 暫以精確條件篩選資料表；embedding／pgvector 為 T07 未完成項目。人審提交只是保存 dossier，待投影後才進入 canonical 待審狀態。
- 新增 0003 migration：refund execution／reservation／successful item ledger／durable simulated receipt；有退款資料時禁止直接 downgrade。
- API 測試 33 passed，exit 0，9.03s。新增 C19–C21 核心情境：高額偽造 auto、缺 gate／改版本、偽造 human、改最終金額、同品項跨案並行、同 execution 重送、多品項 reservation 回滾、APPLIED 後斷線恢復、遺失 reservation fail-closed、application 明確 REJECTED。
- 人審 APPROVE／REJECT／EDIT 均測試；EDIT 可在原始申請 scope 內限縮，API 計算金額；過期 handoff、scope 越界、outbox 失敗不留下半筆裁決。以上為 deterministic／模擬付款，尚非跨服務 A/B/C。

### T05 Graph 與模型邊界

- 16 節點 LangGraph，state 保存 JSON primitives；14 項 runtime 測試通過，包含補件／clarification、人審 EDIT、三次修訂與四次複核、Verification 重試、異議跨補件保留、Memory optional failure 與 artifact fail-closed。
- Runtime 單元測試使用 InMemorySaver，重建 runtime／resume 通過；**不列為 durable checkpoint 驗收**。跨進程 PostgreSQL 驗證待 T06。
- 6 份 prompts 對應 7 種任務；Resolver 輸入排除金額，Reviewer 排除 Memory／Assessment。Memory distill 與 narration 背景 worker 尚未接線。
- 模型 adapter 8 項測試通過；整組 runtime＋adapter 22 passed，exit 0，1.72s。支援明確 Qwen Chat／Compass Responses profile、timeout 180／max retries 0、union envelope、schema 與本地型別驗證；錯誤不切 fake，也不輸出遠端敏感 response。
- 已確認使用者本機 profile 為 integrated-compass；模型與 secret file 依 RETURN_AGENT_* 設定讀取，尚未宣稱真模型通過。

### T06 跨服務核心

- API 0004 migration 保存 final_resolution／refund_execution 與 durable resolution jobs。使用者已確認新增兩個公開欄位，同步更新生成 Schema／TS。
- Agent 0001 migration 保存 thread／command journal／event outbox；PostgreSQL saver 使用 JSON state、禁止 pickle，僅允許 LangGraph Interrupt／Send 型別。
- 6 項跨服務測試 passed，exit 0，9.02s：真 HTTP Provider、Redis Streams、獨立 API／Agent PostgreSQL schema；人工 EDIT 後重新建立 worker／saver，退款 APPLIED，Reviewer 不重跑。
- C15–C18 相關情境：journal terminal 前 crash 後恢復、XADD 後斷線以同 command 重送、terminal replay 不重跑模型、事件 ID/hash 衝突、亂序留 pending、投影失敗 rollback、前序新事件不被 pending queue 餓死。
- 目前 Memory HTTP 尚未接線，跨服務案例明確 Memory UNAVAILABLE；不把此案例稱為 B→C 學習通過。常駐 composition／容器與完整 A/B/C 待完成。
- 本機 `python3 scripts/dev.py migrate`／`seed` exit 0；API 與 Agent ready 均 200。離線 smoke 案 `CASE-0feb8f79ecc64dbba74b711e86b1df7e`，1200 TWD、RESOLVED、退款 SUCCEEDED／APPLIED，去敏摘要保留於本機 artifacts。該訂單的退款 reservation 保留，不刪除成功紀錄供重複 Demo。
- `scripts/dev.py` 預設 offline，明確 `--profile live` 才啟用既有 RETURN_AGENT_* 模型設定；解析 dotenv 不執行 shell，secret file 不提交。
- 直接退款執行的授權拒絕現在保存並回傳 typed REJECTED；已有 application attempt 且結果未知時維持 IN_PROGRESS／reservation，不能改稱確定拒絕。
