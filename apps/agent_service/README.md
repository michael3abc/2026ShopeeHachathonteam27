# Return Agent Service

完整重建與可靠性邊界見 [M06 Agent Service](../../docs/reconstruction/M06-service.md)（485048c 固定快照）。

Queue-driven deployment boundary around [`return-agent-runtime`](../../packages/agent_runtime/README.md).
It consumes versioned commands from Redis Streams, invokes the LangGraph library,
and publishes typed lifecycle and terminal events. HTTP is health-only; start and
resume are never exposed as synchronous routes.

## Ownership

- Owns Redis worker lifecycle, runtime composition and health checks.
- Uses independent integrated-profile loops for Agent commands, resolved-event
  Memory enqueue, Memory distillation, Activity publishing, and narration.
- Injects model, Provider adapters, LangGraph checkpointer and command journal.
- Does not own browser APIs, canonical case state, SSE projection or refund execution.
- Must not import `apps/api` or access the API database.

Cross-service DTOs and stream constants are defined by
[`return_agent_contracts.service`](../contracts/src/return_agent_contracts/service.py).
Redis entries contain one `body` field with the complete JSON contract.

## Operational Memory pipeline

所有完成裁決案件在 graph checkpoint 內留下含 learning trace 的 `MemoryDistillationInput`。主
Agent Worker 發布 `RESOLVED` 後即完成 customer command；Memory Enqueue Worker
以獨立 consumer group 消費相同 event，讀取 checkpoint 並發布
`MemoryDistillationJob`。v2 FULL_REFUND 必須先在 Agent DB `memory_completion_joins`
以 resolution／authorization reference 與 resolution hash 配對 correction 與 API
`APPLIED` 事件；任意到達順序與重送只對應一個 logical job，未付款不蒸餾。
v1 與 DECLINE 保留原排程。Memory Worker 再呼叫 structured-output distiller：

- `SKIP`：回顧與學習判定保存在 Agent replay；發布 completed event，不呼叫 store。trace 不完整／超限／不安全的 preflight skip 不呼叫模型。
- `CREATE_CANDIDATE`：以 `memory_id` 冪等呼叫
  `OperationalMemoryStore.submit_candidate`，狀態仍是 `CANDIDATE`。
- 非法 job：寫入 memory DLQ 後 ACK。
- distillation/store 失敗：發布 typed failed event 後 ACK，不影響 customer case。
- Redis event publication 失敗：不 ACK，交由 consumer-group reclaim。

Memory enqueue／distillation loops 對 Redis、checkpoint、replay DB 的暫時性
transport failure 保持運行，使用 capped exponential backoff。可配置
`RETURN_AGENT_MEMORY_RETRY_INITIAL_SECONDS`（預設 0.25）與
`RETURN_AGENT_MEMORY_RETRY_MAX_SECONDS`（預設 30）；stop/cancellation 立即中斷
等待，成功一輪重設 delay。授權、schema、程式錯誤不進 transport retry。
模型錯誤仍為 terminal `FAILED`；candidate submit 的暫時 transport failure
只重送已保存的同一 payload，未知 HTTP/contract 錯誤仍明確 failed。

整合版以 Agent PostgreSQL 的 `memory_job_results` 保存首次模型 output，再提交
candidate；之後保存完整 completed/failed event 再發布 Redis。重啟或 redelivery
沿用既有結果，不重新蒸餾；candidate store 仍拒絕相同 ID 的不同內容。若 submit
成功但 event 尚未保存，重送的是同一份已保存的 candidate。

啟動時先執行 package 內 Agent Alembic `0001_memory_replay → 0002_memory_model_profile → 0003_memory_completion`，再啟動
workers；版本記錄使用 `agent_service_alembic_version`，不修改 API 或 LangGraph
的 migration 表。新增 SQLAlchemy／Alembic 為此持久化與版本管理的直接依賴，
沿用 repository 已使用的套件，不增加外部服務。既有 `agent_command_journal`
與 checkpoints 保留；不可在 pending jobs 存在時刪除 replay records。
Migration 支援 PostgreSQL offline SQL；有 completion join 歷史時，online 與
offline downgrade 都在 DROP 前拒絕。多 replica 啟動仍以 advisory transaction lock
序列化 migration。Command journal 首次 claim 使用 INSERT ON CONFLICT 加 row lock，
避免多 worker 同時首次 claim 的 unique-key race；租約／terminal 判斷保持持久化。

Streams：`return-agent.memory-jobs.v2`、`return-agent.memory-events.v2` 與
`return-agent.memory-jobs.dlq.v2`。正式 Policy 永遠高於 Operational Memory；只有
外部治理流程升成 `APPROVED` 的資料能被案件 graph 查回。
付款完成另由 API transactional outbox 投遞 `return-agent.refund-completions.v2`，
Memory completion group 為 `return-agent.memory-completion.v2`。

## Profiles

The explicit `demo` profile uses deterministic Provider/model fixtures,
`InMemorySaver`, and an in-memory command journal. It is suitable only for local
transport smoke tests; restart loses graph and idempotency state.
The default fixture is the no-evidence `CHANGED_MIND` scenario. Tests may select
`create_demo_runtime(reason_code=ReasonCode.ITEM_DAMAGED)` to exercise evidence
interrupt/resume. Both reuse their fixture model for repeated cases; neither
replaces the real model or HTTP Providers of `integrated-qwen`.

```bash
docker compose up -d redis
RETURN_AGENT_SERVICE_PROFILE=demo \
RETURN_AGENT_REDIS_URL=redis://localhost:6379/0 \
uv run --package return-agent-service return-agent-service
```

要以相同 fixture Providers 嫁接 OpenAI-compatible Qwen，改用 `demo-qwen` 並
明確注入設定。Key 可透過受限檔案掛載，不得提交：

```bash
RETURN_AGENT_SERVICE_PROFILE=demo-qwen \
RETURN_AGENT_MODEL_BASE_URL=https://qwen.yoyoserver.com/v1 \
RETURN_AGENT_MODEL_NAME=qwen3.8-27b-q4-gguf \
RETURN_AGENT_MODEL_API_KEY_FILE=/run/secrets/model_api_key \
uv run --package return-agent-service return-agent-service
```

Docker Compose 可用本機 ignored secret file，key 不進 repository：

```bash
mkdir -p .secrets
# 將 key 寫入 .secrets/model_api_key 並 chmod 600
RETURN_AGENT_SERVICE_PROFILE=demo-qwen \
RETURN_AGENT_MODEL_BASE_URL=https://qwen.yoyoserver.com/v1 \
RETURN_AGENT_MODEL_NAME=qwen3.8-27b-q4-gguf \
RETURN_AGENT_MODEL_API_KEY_HOST_FILE=.secrets/model_api_key \
docker compose up -d agent-service
```

`integrated-qwen` 是完整跨服務 profile：Qwen 使用 OpenAI-compatible endpoint，
LangGraph checkpoint 與 command journal 寫入獨立的 Agent PostgreSQL，七個
Provider 透過 shared typed HTTP adapters 呼叫 API。Agent Service 不 import API
package，也不存取 API DB。

```bash
RETURN_AGENT_SERVICE_PROFILE=integrated-qwen \
RETURN_AGENT_MODEL_BASE_URL=https://qwen.yoyoserver.com/v1 \
RETURN_AGENT_MODEL_NAME=qwen3.8-27b-q4-gguf \
RETURN_AGENT_MODEL_API_KEY_FILE=/run/secrets/model_api_key \
RETURN_AGENT_DATABASE_URL=postgresql://return_agent_graph:return_agent_graph@localhost:5433/return_agent_graph \
RETURN_AGENT_API_BASE_URL=http://localhost:8000 \
RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE=/run/secrets/internal_service_token \
uv run --package return-agent-service return-agent-service
```

在 Compose 中，key 由 `.secrets/` 掛載，API provider endpoints 只接受相同 internal
Bearer token。未知或未完整配置的 production profile 會直接啟動失敗；不會退回
in-process execution、fake Provider 或無持久化模式。

## Compass through the existing host router

For cross-machine access use `https://compass.yoyoserver.com/v1`. The repository's
ignored `.env` selects this endpoint for both LLM and embedding; `.env.example`
documents the same configuration without credentials. The gateway client key is
read from `.secrets/compass_gateway_key` (mode 600), never from Compass upstream
credentials. A different machine needs its own private copy of this client key.
The public endpoint does not accept the `local-router` placeholder.

Load the environment explicitly for host processes:

```bash
uv run --env-file .env --package return-agent-service return-agent-service
```

Other integrated dependencies (API/Redis/Agent DB/internal token) must still be
configured; this is model connectivity configuration, not a full stack launch.
Compose reads `.env` for interpolation and mounts the configured
`*_API_KEY_HOST_FILE` into fixed `/run/secrets/*` paths. Host-side
`*_API_KEY_FILE` paths are not forwarded into containers.

The following loopback example is for local-only access, not the public gateway:

Use `integrated-compass` for the same durable integrated composition with
Responses streaming. Run the Agent on the host; container localhost cannot reach
the host router. Keep the existing router bound to loopback.

```bash
RETURN_AGENT_SERVICE_PROFILE=integrated-compass \
RETURN_AGENT_MODEL_BASE_URL=http://127.0.0.1:8790/v1 \
RETURN_AGENT_MODEL_NAME=compass-5.6-terra \
RETURN_AGENT_MODEL_REASONING_EFFORT=medium \
RETURN_AGENT_MODEL_API_KEY=local-router \
RETURN_AGENT_DATABASE_URL=postgresql://return_agent_graph:return_agent_graph@localhost:5433/return_agent_graph \
RETURN_AGENT_API_BASE_URL=http://localhost:8000 \
RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE=.secrets/internal_service_token \
uv run --package return-agent-service return-agent-service
```

The local router currently injects its own Compass upstream credential; the
client key above is a non-secret SDK placeholder, not an upstream key. Do not
copy Compass credentials into this repository. Deployments with client auth must
supply their actual local credential via the existing key-file setting.

The Compass model sends no temperature or Qwen chat-template kwargs and uses
Responses `reasoning.effort=medium` by default.
It requires a completed Responses terminal event and valid structured output;
refusal, incomplete streams and schema errors fail explicitly without a provider
fallback. The Qwen profile retains its existing parameters. Embedding is unchanged.

Acceptance for this profile is model connectivity: Compass and the existing Qwen
LLM must return a validated structured response, and the unchanged embedding
provider must return a finite 1536-dimensional vector. Live calls are opt-in,
not part of normal pytest. This does not certify complete case resolution or
Memory processing; graph routing, Human Review and Memory scheduling are unchanged.

### Unified Terra-medium model profile

`integrated-compass` 的 Intake、Resolver、Reviewer、Memory query summary、
narration 與 Distiller 全部預設使用 `compass-5.6-terra`／Responses
`reasoning.effort=medium`。Distiller 仍是獨立 model instance，故 timeout、output
budget、transport 與 replay profile 邊界不變。Embedding 不變。

| Environment | Compass default | 邊界 |
| --- | --- | --- |
| `RETURN_AGENT_MODEL_NAME` | `compass-5.6-terra` | Intake、Resolver、Reviewer、query summary、narration |
| `RETURN_AGENT_MODEL_REASONING_EFFORT` | `medium` | 前景與 narration 的 Responses effort |
| `RETURN_AGENT_MEMORY_MODEL_NAME` | `compass-5.6-terra` | 只影響 Distiller |
| `RETURN_AGENT_MEMORY_REASONING_EFFORT` | `medium` | Distiller 的 Responses effort |
| `RETURN_AGENT_MEMORY_MODEL_TIMEOUT_SECONDS` | `180` | 必須有限且大於零 |
| `RETURN_AGENT_MEMORY_MAX_OUTPUT_TOKENS` | `16384` | reasoning 與可見 output 共用上限 |
| `RETURN_AGENT_MEMORY_MODEL_BASE_URL` | 共用一般 model URL | 可明示獨立 gateway；Compose 有 pass-through |
| `RETURN_AGENT_MEMORY_MODEL_API_KEY` / `RETURN_AGENT_MEMORY_MODEL_API_KEY_FILE` | 共用一般 model key | 原生 process 可獨立覆寫；不可輸出 key |

Compose 的 model/memory name/effort 空值讓 Python 按 profile 選定：Compass 為
Terra/medium，Qwen 保留自己的 Chat profile。若從 `.env.example` 改用 Qwen，
必須移除兩個 reasoning effort 與 Compass memory model 設定；Qwen 配了 Compass
memory model 或 reasoning effort 會明確拒絕，不默默忽略。
獨立 memory credential 在 Compose 需用 override 加入 secret mount 及容器內
`RETURN_AGENT_MEMORY_MODEL_API_KEY_FILE`；不得直接套用 host file path。

所有 model retries 固定 0；401／429／timeout／schema error 不切換模型，
不重跑 customer graph。若 output budget 不足，明確 FAILED，需另行調整設定。
這是請求設定與契約保證；gateway selector 是否可用須另外做 live preflight。

Replay 保存首輪 `model_profile`：model、effort、API、endpoint hash、timeout、
retries、output budget，不保存 URL／secret。新 migration 保留舊行 NULL。
Pending job 的 prompt/profile 不符會拒絕，已保存 result/event 原樣重播。
舊 DTO 預設欄位不改變原 input hash；有 profile 時不允許 downgrade 丟棄來源。
部署前先排空或隔離舊 pending，再協調 API/Agent DTO 升級；不自動補造對話。

對話由 checkpoint learning trace 直接取得，不向 API 撈聊天全文、不依賴晚到的
narration。初始／澄清／補件文字去識別化且有 stable turn/request ID；舊 evidence
resume 無文字時保留裁決、蒸餾 `TRACE_INCOMPLETE`。詳見 [Memory spec](../../docs/spec/04-operational-memory.md)。

## Tests

### Activity workers

主 worker 使用 runtime observer 接收即時活動，再由獨立有界 publisher 寫 Redis。
Memory 排程／執行／提交也使用同一 ActivityEmission。Narration worker 只讀 API outbox 的
指定 node summary facts，使用現有配置模型，不讀其他案件／Memory 原文、不加入 graph。
RETURN_AGENT_ACTIVITY_QUEUE_SIZE 預設1024且需大於0；RETURN_AGENT_NARRATION_CONCURRENCY
預設2（1–16）；RETURN_AGENT_NARRATION_TIMEOUT_SECONDS 預設20且需大於0。
timeout 先發布 UNAVAILABLE，同步模型執行緒尚未停止時占住該 slot，避免無上限堆積；
模型 adapter 的 HTTP timeout 應保持有限。傳輸 retry 使用同 event ID，錯誤不記錄敏感 exception。
內存 queue 滿／程序崩潰可能造成 trace 缺失；觀察 error logs、Redis pending、.rejected stream
及未送出的 narration outbox。本版不宣稱 exactly-once model invocation 或完整稽核。
輸出快取與 outbox 防重保證至多一份已保存結果；跨 crash/lease expiry 的模型呼叫可能重做。
目前無自動 retention，部署前需評估 stream／cache／DB 容量，不能清理仍可能 replay 的去重資料。
預設 demo profile 明確不注入 narration model；worker 仍消費工作，保存並回傳
UNAVAILABLE／NARRATION_DISABLED_OFFLINE_DEMO／text=null，再依原流程 cache、publish、ACK。
此路徑不呼叫模型、不產生 ACTIVITY_NARRATION 的 model STARTED／FAILED，也不以模板冒充 LLM。
demo-qwen、integrated-qwen、integrated-compass 沿用配置模型；真實模型錯誤仍是 NARRATION_UNAVAILABLE。
停用結果與其他結果一樣會快取；切換 profile 不會為同一來源摘要重新產生解說。

```bash
uv run --package return-agent-service pytest apps/agent_service/tests
```

Replay migration／並行保存測試預設用 SQLite；設定 `AGENT_TEST_POSTGRES_URL`
可驗證 PostgreSQL 分支，測試會建立並清除唯一命名 schema，不修改既有 tables。
請指向專用測試 database，執行
`pytest apps/agent_service/tests/test_memory_worker.py -k 'agent_migration or concurrent_first'`。

v2 的可信版本來自 API case context。Reviewer 獨立讀取自己的 findings，不接收
Assessment 結論、Operational Memory 或 user-risk facts；Model verdict 保持
APPROVE／REVISE。核准後才計算金額 gate 與 v2 FULL_REFUND risk gate；HIGH／UNKNOWN
進既有 Human Review，revision exhaustion 仍以原異議進人審。UserRisk HTTP Provider
只取 API 的 immutable snapshot，不讀 API DB；API 與 Agent 共用
`config/reviewer-gates.json`／`config/user-risk.json`。

Policy path／必須退回的條件由 typed POLICY_CONFIRMATION resume 恢復；API 保存
同意後經 outbox 發送，Agent 不自行信任瀏覽器 payload。核准 emit 不代表退款已完成，
後續 consent／return inspection／payment 由 API 履約 worker 負責。v1/v2 checkpoint
不得跨版重播或自動降級。

隔離 PG／Redis 的完整指令與 offline SQL 見
[migration/recovery runbook](../../scripts/README.md#policy-v2-migration-與-recovery-驗證)。
真 PostgreSQL 已覆蓋 correction/APPLIED 任意順序、並行 first-result／journal claim；
真 Redis 已覆蓋 reclaim、ACK loss 後重建 worker 不重跑 distiller。這些 deterministic
測試不代替真模型 A–F／risk persona／B→C 學習驗收。

## 同模型圖片輸入

`integrated-compass`／`integrated-qwen` composition 為既有 `OpenAIStructuredOutputModel` 注入內部圖片 Provider。沿用 Resolver 的 model、endpoint、key 與 timeout；沒有另外的 vision model 或文字降級。實際 endpoint 必須支援圖片及 structured output；僅憑型號不能保證 gateway 支援。

ASSESS、PROPOSE_OR_REVISE、REVIEW 呼叫前讀取已提交的 `artifact://upload/…`，以對應 evidence ID 和 pixels 一起送入模型。Reviewer 獨立取得圖片；Memory／narration 不接收圖片。bytes／base64 僅存在模型呼叫期間，不加入 graph state、Redis、checkpoint 或 Activity。模型錯誤經過去敏感資訊處理。下載失敗不會改用純文字裁決；離線 demo 仍只驗證既有合成 fixtures。

## 申請理解展示

理解結果透過既有 Activity NodeSummary 傳輸；不新增模型呼叫或背景工作。API Narration outbox 仍只保存 facts。
