# Return Agent API

完整重建介面、交易與資料字典見 [M03 API](../../docs/reconstruction/M03-api.md) 與 [M04 能力／退款](../../docs/reconstruction/M04-capabilities.md)（485048c 固定快照）。

Python backend workspace for BFF、Case API、SSE 與 canonical case state。它只
使用共享的 [`apps/contracts`](../contracts/README.md)；不 import 或執行
[`packages/agent_runtime`](../../packages/agent_runtime/README.md)。

工作空間固定在 Python 3.12.0（`.python-version`）。

## 憑證功能

第一個遷移僅建立 `evidence_items`。它不建立或查詢
Allen 所有的訂單、物流或案例表格。憑證列包含中立
的後設資料和人工製品參考；原始人工製品位元組和索賠決定
不被存儲。

From the repository root:

```bash
docker compose up -d api-db
uv sync --all-packages
make migrate
uv run --package return-agent-api return-agent-seed-evidence
```

安全地重放最後一個命令：未更改的 fixture 記錄不會被
第二次插入。設定之後，要運行 HTTP 流程：

```bash
uv run --package return-agent-api uvicorn return_agent.app:app --reload
```

Container/console entrypoint `return-agent-api` 會先執行 `alembic upgrade head` 再
啟動 Uvicorn；直接使用 `uvicorn` 時需自行先執行 migration。

## 政策 RAG

政策 fixture 包含版本化的結構化條款，而不是原始塊。
CLI 預設與 integrated-demo 啟動共用 `data/policy.json.example`；自訂
`RETURN_AGENT_DEMO_DATA_DIR` 時，啟動讀取該目錄內的同名檔案，CLI 則以
`--input <目錄>/policy.json.example` 指定。此 canonical fixture 保留原整合版
`RETURNS-TW:v1` 的內容；舊版不同內容的 data example 若已匯入，須保留歷史資料，
改用新的 demo database 或經 owner 審核的新 policy identity，不能覆寫同版本。
檢索提供者在向量排序之前過濾市場、原因、聲稱的類別和政策
有效時間；嵌入只排序相容的條款。
當適當時，它會返回 `NOT_FOUND` 或 `AMBIGUOUS` 故障關閉束。

為執行時嵌入適配器設定 credential，然後擷取 fixture：

```bash
uv run --package return-agent-api return-agent-ingest-policy
```

Policy／Memory 共用 OpenAI-compatible embedding adapter，使用
`text-embedding-3-large`／1536 維；endpoint 必須明確設定，沒有私人預設入口。
必須設定專用 API key 或 key file，不借用 `OPENAI_API_KEY`：

```bash
RETURN_AGENT_EMBEDDING_BASE_URL=https://embedding.example.invalid/v1 \
RETURN_AGENT_EMBEDDING_MODEL=text-embedding-3-large \
RETURN_AGENT_EMBEDDING_API_KEY_FILE=/run/secrets/embedding_api_key \
uv run --package return-agent-api return-agent-ingest-policy
```

請求指定 `dimensions=1536`；回應維度不符會拒絕寫入，不做 padding 或截斷。
`RETURN_AGENT_EMBEDDING_TIMEOUT_SECONDS` 預設 25 秒（必須有限且大於零），
SDK 自動 retries 固定為 0，不切換 provider 或 fallback。

相同維度不代表模型相容。啟動 seed／一般 ingestion 與每次 retrieval 都檢查
既有 clause 的 `embedding_model`；不一致會明確拒絕。切換模型時先停止 policy
retrieval，設定目標模型後執行 `return-agent-ingest-policy --input
data/policy.json.example --reembed`，涵蓋所有會被查詢的 policy fixtures，再重啟
API。每次 CLI 執行以單一 transaction 更新向量與 model tag，任一 embedding
失敗即 rollback；不改寫 Policy immutable content 或歷史 retrieval bundle。
同名模型若更換權重也必須明確執行 `--reembed`，部署應使用版本化 model 名稱。

相同的政策系列/版本無法用更改的 immutable 內容重新擷取；`active`
則由 fixture 管理，可在內容不變時安全切換。這不會自動停用同 family
的其他版本。每個檢索到的 `PolicyBundle` 會保存以供稍後由束版本驗證，
並行的相同檢索只會保留一筆 canonical record。

## Operational Memory

`0004_operational_memory` 建立 `operational_memories` 與其 append-only
`operational_memory_events` 稽核軌跡。`SqlAlchemyOperationalMemoryStore`
嚴格實作共享的 `OperationalMemoryStore` contract：candidate 以 `memory_id`
冪等寫入，只有 payload 完全相同時才會回傳既有 submission reference。

`query_approved` 只回傳 `APPROVED` 的資料，並對 market、reason、required
claim、claimed-item categories、policy version 與 claim-registry major version（v1）
做硬過濾；結果依 query_summary 的精確 cosine 排序（同分 confidence、核准時間遞減、memory ID 遞增），最多3筆 MemorySearchHit。候選入庫前由 API embedding，與 retrieval_summary 原子提交；失敗不留半筆記錄。
v2 改用 exact Policy／registry／path 篩選；COOLING_OFF 的空 claims 以 path scope
定位。切換政策路徑會清除前次 Memory 命中並重新檢索。

核准與 retirement 是不屬於 Agent contract 的受信任治理操作，透過
`OperationalMemoryGovernanceService` 執行唯一允許的
`CANDIDATE → APPROVED → RETIRED` transition，並記錄 audit event。它需要
由外部 approval workflow 授權；本 backend 沒有將它暴露為 Agent tool、公開
API 或 case-memory search。Lifecycle timestamp 一律由服務端產生，且資料庫
保證 submission、approval、retirement 的時間順序。

`0014_memory_learning_sources` 將 correction-only 來源欄位改為
`source_event_refs`，新增 `applicability_limits`／`prohibited_inferences`；
保留歷史來源、embedding、治理狀態及時間，並重算 candidate hash 以維持冪等。
新學習資料存在時禁止降版成 correction-only 資料；升級只在隔離環境驗證，
正式切換前先處理舊版 pending 工作。整案回顧保存在 Agent-owned replay，
API 向量索引只保存經驗，不索引案件歷史。

## Verification

Verification 使用 handoff_verifications，以 handoff_id 與 canonical payload hash 保證冪等：
相同 handoff 回傳最初保存的結果，使用同一 ID 的不同內容會被拒絕。
Verification 的 `UNAVAILABLE` 是唯一可重新執行的結果，讓暫時性相依服務復原後
能取得最終結果。

API integration owner 必須以 Allen 的 `CaseContextProvider` 注入
`compose_safety_providers` 的結果；這個 module 不會直接讀取 Allen 的
case/order tables。Agent Service 則透過 contracts 的 `HttpVerificationProvider`
呼叫 POST /internal/v1/verification，不能存取 API database。
內部 API 要求 RETURN_AGENT_INTERNAL_SERVICE_TOKEN Bearer token；缺少設定回 503，錯誤憑證回 401。
舊 Risk Gate endpoint 不再使用，`compose_safety_providers` 只組裝 Verification。
Reviewer 保持 APPROVE／REVISE；核准後仍須通過 deterministic 金額 gate，
v2 FULL_REFUND 再取得 User Risk snapshot。三次修正後仍 REVISE 以既有異議進人審；
高額或 HIGH／UNKNOWN risk 也須人工授權，均不把 gate 結果改寫為 Reviewer 異議。

### 升級與歷史資料

本次是跨服務契約變更：API、Agent Service、Web 必須一起發布，先停止舊 worker 並處理完舊案件。
不要把舊 graph checkpoint、pending command/event 或 memory job 用新版程式續跑；demo 使用新的
case/thread 與獨立資料庫／Redis namespace，或先由操作者完成舊佇列的歸檔。不得自動清空舊資料。
執行 Alembic upgrade head：0010 新增 human_reviews.review_payload，將舊 risk_payload 改名
legacy_risk_payload 並允許 null。risk_evaluations 與 cases.risk_route 保留作歷史查核，新程式不映射或讀寫。
已有新版人工紀錄時禁止 downgrade；回復需使用升級前備份，避免遺失 Reviewer 異議。

## Authorized Refund Execution

`0007_refund_item_reservations` 新增 mutation 前的品項保留紀錄。相同
`(order_ref, line_item_ref)` 只能由同一 execution 持有；不同 handoff 衝突會在
呼叫 Allen 前被拒絕。多品項必須全部保留成功，才會提交並開始 mutation。
成功或結果不明時保留 ownership；只有確認的 terminal rejection 才原子釋放。
reservation 沒有 TTL，timeout 必須使用原始 execution_ref 恢復。
升降版前須停止退款執行；既有成功與未完成 execution 會回填 reservation，
重疊的舊紀錄須先核對外部退款結果。此保護不取代 Allen 的原子退款檢查。
已有退款資料的部署必須執行 online `alembic upgrade head`，才能完成 hash、
scope、ledger 與 ownership preflight。PostgreSQL offline SQL 僅允許空的退款表；
有舊資料時會明確中止，避免略過 Python preflight。

退款併發測試預設用 SQLite；可將 `REFUND_TEST_POSTGRES_URL` 指向專用測試
PostgreSQL 再執行 `test_refund_execution.py` 中的 concurrent、different_handoffs
及 on_database 測試。每個案例建立隔離 schema，測試後需清理專用資料庫；
不可指向 production DB。測試 fake 僅依 execution_ref 冪等，不會隱藏跨 handoff
重複退款問題。

`0006_refund_execution` 建立 API 自有的 `refund_executions` 與
`refund_execution_items` ledger。`SqlAlchemyRefundExecutionProvider` 只接受既有
`ExecuteRefundRequest` contract；沒有新的 refund HTTP endpoint，也不由 Agent
Runtime/Service 直接呼叫。`AgentBridge` 會消費 `AgentResolvedEvent`；尚未注入 refund
executor 時會讓 full-refund event 保持 pending，不會意外執行或 ACK。

退款執行讀取同一 handoff 的 persisted proposal 與 Verification PASS。
REVIEWER_APPROVE 的 handoff 來自 authenticated Agent Service event，不接受使用者提交的審核結果；必須帶 ApprovedReviewResult，final decision 必須等於原 proposal。
HUMAN_APPROVE / HUMAN_EDIT 必須帶最後保存的 ReviewResult，且對應資料庫裡已完成的
HumanReviewRecord；不能只憑 Agent 宣稱已有人核准。Human EDIT 必須與保存的人工作業完全一致。
付款前重新核對 current snapshot、proposal 金額與 policy、Reviewer findings；Human edit 的 scope
仍限原 proposal 的子集合，金額與 currency 依 current context 驗證。
此限制比 graph 的 claimed-item 邊界更保守：目前 execution contract 未提供權威
claimed-item 集合，因此其他 claimed 但未列入原始 proposal 的品項也不能新增退款。

同一 `handoff_id` 使用相同內容會回傳 canonical result；不同內容會衝突。發送給
Allen 前先保存穩定的 `execution_ref`，因此 timeout 或「Allen 已提交但 API 尚未
保存回應」可使用同一個 `ApplyRefundRequest` 安全重播。未授權、blocked 或 declined
handoff 只產生本地 `REJECTED` 結果，絕不呼叫 Allen mutation adapter。`get_status`
對未完成 execution 回報 typed unavailable，並且不會自行重試 mutation。

## Agent Service boundary

`POST /cases` 與 clarification/evidence resume 只建立共享的 typed Agent command。
`SqlAlchemyAgentCommandOutbox` 會在同一個 SQLAlchemy transaction 將 command
寫入 `agent_command_outbox`，背景 dispatcher 在 commit 後投遞 Redis。Redis 暫時
不可用時，Case 仍可建立，command 會留在 PostgreSQL 等待重送；API 不直接呼叫
LangGraph 或直接 publish Redis。

API 同時以 consumer group 讀取 `return-agent.events.v1`。每個 event、Case 狀態和
UI event 在同一個 transaction 投影，成功 commit 後才 ACK；
`processed_agent_events` 以 case、command、index 與 canonical payload hash 判斷
真正的重送；相同 `event_id` 若內容不同會進 rejection ledger。尚未明確注入並授權
refund executor 時，full-refund event 不會 ACK，因此不會意外觸發退款副作用。

每個 command 的 `event_index` 由 `agent_event_projection_cursors` 保證連續投影；
先到的後續 event 會留在 Redis pending list，consumer 每四次讀取固定掃描一次 pending
並延續 `XAUTOCLAIM` cursor，避免新流量或單一 pending event 造成 starvation。
wire-invalid 或無法套用的 event 會先完整寫入受限的 `rejected_agent_events` 診斷
ledger，再 ACK；該 command projection 會標記 terminated，後續 event 直接記錄並
ACK。仍在進行中的 Case 同時 fail closed 到 `ESCALATED`，UI 只收到固定的公開錯誤碼
與安全訊息，不會收到 Provider 或資料庫 exception 細節。

`agent_command_outbox` 同時是 durable command journal。Dispatcher 會以
`FOR UPDATE SKIP LOCKED` 取得有期限的 ownership lease，再 publish；多個 API replica
不會在正常運作下同時投遞同一筆 command。若 owner crash，lease 到期後其他 replica
可接手；每次 claim 的唯一 fencing token 會阻止 stale owner 完成新 lease。Agent
Service 仍須以穩定 `command_id` 保持 at-least-once idempotency。

## Integrated demo composition

`RETURN_AGENT_API_PROFILE=integrated-demo` 是明確的非 production profile。它以
既有 versioned fixtures 組裝 Case/Order、Policy RAG、Operational Memory、Evidence、
Verification、Human Review 與 deterministic refund application provider。
每次 no-UI smoke 使用唯一 `ORDER-DEMO-E2E-*`，但商品、金額、Policy、Memory 與
Evidence 內容仍來自同一組 fixture，因此可重複驗證而不繞過退款防重。

Agent Service 只透過要求 Bearer token 的內部 routes 呼叫這些能力：

```text
POST /internal/v1/case-context
POST /internal/v1/policy
POST /internal/v1/memory/query
POST /internal/v1/memory/candidates
POST /internal/v1/evidence/resolve
POST /internal/v1/verification
POST /internal/v1/human-reviews
POST /internal/v1/human-reviews/result
```

`0009_human_reviews` 保存 Human Review submission 與 final result。公開的
`POST /cases/{case_ref}/review` 只在案件為 `AWAITING_HUMAN_REVIEW` 時接受 UI
decision，完成後以 `HumanReviewPollResume` 經 transactional outbox 恢復原 graph。
Agent Service 重啟不會重複 submit review，因為 `review_ref` 已保存在 checkpoint。

此 profile 的 refund application 是 deterministic demo adapter；正式部署必須替換為
Allen 的 `RefundApplicationProvider`，不得把 demo adapter 當成真實金流執行器。

## Policy v2 User Risk 與 Demo 認證

新案的版本由 API 依 `data/policy-v2-cases.json.example` 中的訂單 prefix 與 owner
選用並持久化，未知 `ORDER-PV2-*` 或 owner 不符會拒絕；瀏覽器不可直接指定
可信政策版本或配送 facts。v2 使用 `DEMO-TW-RETURNS:v2.0`／`claim-registry:2.0`，
完整適用政策包來自 `data/policy-v2.json.example`。既有 v1 case／checkpoint 不跨版重播。

設定 `RETURN_AGENT_DEMO_IDENTITIES_FILE` 指向受限 JSON：`identities` 每筆含
`user_ref`、`role`（buyer／reviewer／operator）、個別憑證的 `credential_sha256`；
`allowed_origins` 列出此環境允許的 Web origin。不要提交憑證或設定檔。
`POST /auth/login` 只接受 user_ref／credential，後端決定角色，回傳不透明
`return_agent_session` HttpOnly、SameSite=Strict cookie（HTTPS 時 Secure）。
session hash 保存於 DB；`GET /auth/session` 與 `POST /auth/logout` 查詢／撤銷登入。
狀態變更含登入、登出均檢查 Origin；內部 Provider 繼續使用 service Bearer token。

買家只能操作自己的案件；reviewer 才能讀 risk dossier 與提交裁決，
operator 才能模擬物流。後端對 Case JSON、case-events SSE、activities JSON／SSE
與 narration 做角色投影，買家與 operator 不會取得 risk facts／gate／人審筆記；
node inspector 使用同一投影，不依 UI 隱藏敏感欄位。

| POST route | 授權與作用 |
| --- | --- |
| `/cases/{case_ref}/policy-confirmations` | owner buyer；核對 request／selection version，保存同意與 typed resume outbox，重送不得更改內容。 |
| `/cases/{case_ref}/return-confirmations` | owner buyer；核對 authorization 與 return requirement hash，接受退回才進 AWAITING_RETURN。 |
| `/internal/v2/return-events` | service token 加 `RETURN_AGENT_RETURN_PRODUCERS` allowlist；核對 producer/event identity、authorization／品項、順序與 payload hash。 |
| `/demo/cases/{case_ref}/return-simulation` | operator；ARRIVED／PASS／DISPUTE／OVERDUE 產生 synthetic 事件，仍走同一履約驗證。 |
| `/internal/v1/user-risk/snapshot` | service token；固定 case_opened_at cutoff 的 typed snapshot Provider。 |

User Risk 僅用於 v2 Reviewer APPROVE + FULL_REFUND；Decimal evaluator 使用
`config/user-risk.json`，LOW／MEDIUM 放行，HIGH／UNKNOWN 進人審，金額 gate 原因
優先但 dossier 保留兩個 gate。API snapshots 排除 current case，首次保存後重送
沿用完全相同的 facts。Human dossier 逐欄比對持久化 snapshot 與其 hash；僅有相同
snapshot_ref 不足以授權。自動付款重算同 snapshot、同 config 的 PASS；人審
APPROVE／EDIT／REJECT 比對 persisted dossier／result，revision exhaustion 可沒有 risk。

核准後，須退回案件依序進 `AWAITING_RETURN_CONFIRMATION`（已有有效政策同意時
可直接進下一步）、`AWAITING_RETURN`、`AWAITING_RETURN_INSPECTION`。合法驗收
或合法免退才進付款；人工核准不跳過履約。付款前重驗 scope、最新可退額、reservation、
consent、evaluation 與兩份 gate config；設定缺失／改變時停止付款並交專責，不重跑 Reviewer。
UNKNOWN 付款結果保留 reservation，lease 到期後用原 execution key 恢復。

`APPLIED` 成功 ledger、冪等 `REFUND_SUCCEEDED` risk event 與
`refund_completion_outbox` 在同一 transaction 保存。等待退回、人審核准或結果
未知都不寫成功事件；Agent Memory 以 correction／APPLIED durable join 後才排程。

API migration 單鏈為 `0013_activity_tracing → 0014_memory_learning_sources →
0015_user_risk_authorization → 0016_policy_v2_fulfillment → 0017_image_attachments`。
新 Risk 三表不讀寫 legacy `risk_evaluations`；
v2 evaluation／selection／confirmation／authorization／receipt 與 Demo session 有歷史
時禁止直接降版，offline PostgreSQL SQL 亦包含可執行保護。隔離驗證命令見
[scripts runbook](../../scripts/README.md#policy-v2-migration-與-recovery-驗證)。

以下是未啟用 Demo session 的 v1 開發環境 SSE 範例；v2 launcher 使用8200，
呼叫端須帶已登入的 session cookie。Web 經同源 `/backend/*` proxy 訂閱：

```bash
curl -N http://localhost:8000/cases/CASE-001/events
curl -N -H 'Last-Event-ID: 12' http://localhost:8000/cases/CASE-001/events
```

SSE `id` 是 `case_events.seq`，payload 是 UI v1 `AgentEvent`。Backend 只串流
`agent_event`；與它共用 sequence 的 `user_turn` 不會出現在 SSE，因此序號允許有
間隔。所有 writer 先鎖定 Case row，再分配 per-case sequence。

```bash
uv run --package return-agent-api python -c "import return_agent; import return_agent_contracts"
```

## Compass embedding option

Set this host's authorized endpoint explicitly; there is no default URL. Load the
ignored root `.env` using `uv run --env-file .env` when running on the host.
It sets embedding model `text-embedding-3-large` and reads the separate gateway
client key from `.secrets/compass_gateway_key`. No upstream Compass key is needed
in this project. Compose uses the same URL/model and mounts the client key via
`RETURN_AGENT_EMBEDDING_API_KEY_HOST_FILE`. The local placeholder below does not
authenticate public requests. Adding the public endpoint does not rebuild vectors.

Policy and Memory now default to Compass `text-embedding-3-large` / 1536.
The same adapter can also reach the local Compass router explicitly:

```bash
export RETURN_AGENT_EMBEDDING_BASE_URL=http://127.0.0.1:8790/v1
export RETURN_AGENT_EMBEDDING_MODEL=text-embedding-3-large
export RETURN_AGENT_EMBEDDING_API_KEY=local-router
```

The router owns the upstream Compass credential; the client value is only an SDK
placeholder for the current loopback endpoint. Requests retain the existing
1536-dimensional contract. Run the API on the host to reach this loopback URL.
Use an isolated policy database for testing. Existing Qwen vectors must not be
queried with the new model: the model mismatch guard remains active. Explicit
`--reembed` maintenance is required to switch a populated policy DB; merely
adding this endpoint does not rebuild any vectors. Memory vectors must also be
backfilled before retrieval resumes, following the coordinated cutover below.

Memory 舊資料須執行 `return-agent-backfill-memory --dry-run` 後再回填，保留原始冪等 hash／governance。
切換順序與備份要求見 [canonical Memory runbook](../../docs/spec/04-operational-memory.md#遷移與切換-runbook)。

## Activity API

新增 migration 0013（case_activities、activity_narration_outbox），不更動 case_events。
API lifespan 另啟 activity Redis consumer／outbox dispatcher，DB commit 後才 ACK。
分頁 GET /cases/{case_ref}/activities 與 SSE /cases/{case_ref}/activities/stream
可在案件 terminal 後持續讀取背景事件；原 /events 行為不變。
預設離線 demo 的 narration 會回傳 UNAVAILABLE／NARRATION_DISABLED_OFFLINE_DEMO／text=null；
這是預期停用，不是 node 失敗。此結果同樣持久化、去重並支援分頁／SSE replay。
完整 JSON／SSE、cursor、late event 與內部 demo 存取邊界見
[Activity 交接契約](../../docs/spec/08-external-interfaces.md#獨立-activity-api-v1內部-demo審核人員)。
升級前先備份／遷移，再協調 API 和 Agent Service；不重播舊案件以補造 trace。
有活動紀錄時 downgrade 會拒絕，offline downgrade 也要求先作 online empty-data preflight。

## 圖片上傳與保存

新增 Pillow 供真實圖片解碼、像素限制與 EXIF 清除；標準函式庫無法安全完成這些操作。python-multipart 供 FastAPI 解析檔案表單。圖片處理在 API 執行，不增加獨立解析服務或模型。

初次申請及補件使用 multipart `POST /attachments`，欄位為 `file`、`order_ref`、`subject` 與可選 `case_ref`。`GET /attachments/options?order_ref=…` 回傳可信品項及限制。沿用固定 `demo_customer` 身分；這不是新增的登入系統。

預設 JPEG／PNG／WebP、10 MiB／張、6 張／訊息、25M pixels；不接受動畫。API 限制 multipart 總量、驗證真實格式與解碼，套用 EXIF 方向後移除 metadata；檔案權限 0600。上傳對應 `image_attachments`（0014 migration），檔案存於 `RETURN_AGENT_IMAGE_DIR`，Compose 使用獨立持久化 volume。

建立案件／補件時會在既有 transaction 鎖定並綁定附件，驗證 user、order、case 與數量；失敗不建立 command。`GET /attachments/{attachment_id}/content` 供固定使用者預覽；`GET /internal/cases/{case_ref}/images/{attachment_id}` 另需 service bearer token，且僅可取已提交到該案的圖片。讀取檢查 SHA-256；未送出的附件不能被模型讀取。

`GET /cases/{case_ref}/conversation` 依序回傳持久化使用者訊息、artifact refs 及附件描述。證據列只保存中立檔案資訊，圖片觀察由 Resolver／Reviewer 實際讀圖產生。

限制由 `RETURN_AGENT_IMAGE_MAX_BYTES`、`RETURN_AGENT_IMAGE_MAX_PER_MESSAGE`、`RETURN_AGENT_IMAGE_MAX_PIXELS` 設定；API、Agent 與 Web build 的 MAX_BYTES 必須一致。尚未送出／已從草稿移除的附件仍保留在儲存中，首版不自動刪除，需依環境訂定清理政策。有附件資料時 0014 downgrade 拒絕移除 metadata；先備份 DB 與圖片 volume，不能只備份其中之一。
