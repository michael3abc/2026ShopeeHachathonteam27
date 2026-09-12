# 五分鐘 Demo：從人工經驗到下一案 Memory

本資料包是合成案例，不是正式平台退貨政策或真實消費爭議。金流使用
`DeterministicDemoRefundApplicationProvider`，不會真正退款。
JSON example 不會自動載入；下列寫入命令供操作者在隔離環境執行，本次資料製作不執行它們。

## 1. 先確認阻擋條件

PR #22 合併後的可執行入口：[E2E 操作手冊](E2E.md)。準備程式與 Compose override
可建立同時包含 A／B／C snapshot 的 fixture，由 provider 按 `order_ref` 精確選取。
此操作使用 API bootstrap 自動核准合成 speaker preload，啟動前須人工核對並同意。

版本基準：已合併 PR #20，包含 Reviewer 金額授權、Memory 向量檢索與 Compose 共用 JSON 掛載修正。

退款流程可由本資料包實跑；B → C 學習是否完成仍以 Distiller 實際輸出與治理核准為準。

| 前置條件 | 現況與負責接入 |
| --- | --- |
| 多訂單 snapshot | 已實作：`FixtureCaseContextProvider` 支援 keyed `orders`，依 `order_ref` 精確選取；未知訂單 fail closed。 |
| Reviewer 整合安全規則 | 已實作：LLM APPROVE 後由 Python 評估金額；API 於人工審核及退款授權時獨立驗證。Compose 的 API／Agent 使用同一 JSON。 |
| B 的蒸餾來源 | B 使用真實 `EDIT` 修正退回要求，形成 correction trace；Distiller 仍可依內容回傳 SKIP，不保證建立 candidate。 |
| Memory 核准 | Louis：現有 governance 可用，但沒有 approval CLI／HTTP endpoint；下方使用現有 Python service。不得直接 UPDATE status。 |
| 素材 | 12 張圖片已提供於 images/；仍需人工核對摘要、模擬標示及 artifact 展示接入。 |

任一外部條件未完成時，停止相應段落並標示待整合，不能用預填 Memory 或成功紀錄代替。

## 2. 資料地圖與格式

| 檔案 | 用途／實際儲存位置 |
| --- | --- |
| `policy.json.example` | 現有 policy CLI → API DB policy_documents／policy_clauses；與上層 canonical policy 完全相同。 |
| `evidence.json.example` | 現有 evidence CLI → API DB evidence_items，只有 metadata／人工摘要，不存圖片 bytes。 |
| `case-a/b/c.json.example` | case_context／order_snapshot 是 provider fixture，非 DB rows；create_case_request 經 Case API 建案；initial_user_turn 為模板，followup_messages 是 SendMessageRequest。 |
| `memory-preload.json.example` | candidate 是 MemoryCandidate；其他欄位是操作期望。submit 後進 operational_memories，approve 留 operational_memory_events。合成歷史 references 不冒充真實來源案件。 |
| `human-review.json.example` | request 是 ReviewDecision；operation／precondition 是操作 metadata。審核完成結果由 API 生成。 |
| `scenarios.json.example` | 操作順序、bindings、預期觀察；不是 runtime DTO，不能整份 POST。 |
| `assets-manifest.json.example` | 待人工補充素材清單，不是 Evidence DTO。 |
| `text-data.json.example` | 中文案件背景、錄影旁白、claim 查核提示與 B 記憶核准參考，不是 DB seed。 |
| `prompt.md` | 交給 ChatGPT-Image 的 12 張圖片生成說明與跨圖一致性要求。 |

金額是 decimal strings；UTC 時間固定為 2026-09-01 到貨、09-02 開案的歷史模擬。
Case API 的真實 created_at 與 fixture 時間不同；錄影需標示模擬訂單時間。若改成當天情境，要一起更新 case_opened_at、captured_at、delivered_at、訊息及 evidence 時間，保持七日期間與先後一致。
執行時以 API 回傳 case_ref 取代模板值，snapshot 綁定實際 order_ref。不要將 initial_user_turn 再送一次造成重複訊息。

## 3. 環境與啟動

由 repo root 執行。Python 固定 3.12.0，使用 uv；Docker 需 PostgreSQL/pgvector、獨立 Agent PostgreSQL、Redis。參閱 [Compose](../../docker-compose.yml)、[API README](../../apps/api/README.md)、[scripts README](../../scripts/README.md)。

先使用獨立 Compose project 及不衝突的 host ports；下列示範 ports 必須先確認未被佔用。不要使用 `down -v` 或清除共用 DB。

```bash
export COMPOSE_PROJECT_NAME=refund-case-study
export API_POSTGRES_PORT=55432 AGENT_POSTGRES_PORT=55433 REDIS_PORT=56379
export API_PORT=58000 AGENT_SERVICE_PORT=58090
docker compose up -d api-db agent-db redis
export DATABASE_URL=postgresql+psycopg://return_agent_api:return_agent_api@127.0.0.1:55432/return_agent_api
uv sync --frozen
uv run --package return-agent-api alembic -c apps/api/alembic.ini upgrade head
```

確認 DB healthy 及 migration 成功才繼續。設定 `RETURN_AGENT_API_PROFILE=integrated-demo`、
`RETURN_AGENT_SERVICE_PROFILE=integrated-compass`。需要可用的 `RETURN_AGENT_MODEL_BASE_URL`、
`RETURN_AGENT_MODEL_NAME`、`RETURN_AGENT_EMBEDDING_BASE_URL`、`RETURN_AGENT_EMBEDDING_MODEL`。
Embedding endpoint 必須符合目前 1536 維要求，seed 與 API 必須使用同一模型。
Compose secrets 使用 `RETURN_AGENT_MODEL_API_KEY_HOST_FILE`、`RETURN_AGENT_EMBEDDING_API_KEY_HOST_FILE`、
`RETURN_AGENT_INTERNAL_SERVICE_TOKEN_HOST_FILE`；指向已有檔案，不把金鑰寫進本包。
本機 CLI 另外需要 `RETURN_AGENT_EMBEDDING_API_KEY_FILE` 指向本機可讀 secret；Compose 的容器路徑不適用本機 CLI。

以根目錄 [.env.example](../../.env.example) 建立本機 `.env`；設定 URL 為
`https://compass.yoyoserver.com/v1`、LLM 為 `compass-5.6-terra`（medium）、embedding 為
`text-embedding-3-large`。Embedding 已是目前預設；LLM/profile 仍應明確指定並核對。
Public gateway 使用私有 client key 檔 `.secrets/compass_gateway_key`；`local-router` placeholder 無法通過 public gateway 認證。
內部 API service token 仍需另設 `RETURN_AGENT_INTERNAL_SERVICE_TOKEN_HOST_FILE`，不可拿 gateway key 代替。
Compose 讀取 `.env` 插值並掛載 HOST_FILE；本機 uv 需 `--env-file .env` 才載入 FILE 與模型設定。
若 shell 已 export 同名變數，先核對是否覆蓋 `.env`，尤其是先前的 Qwen profile/model。

依 E2E 手冊用 `prepare_runtime.py --case all` 產生固定檔名並使用 override；不要直接把
DEMO_DATA_DIR 指向本包。三案共用同一個 API instance，不需在案件間切換 fixture：

```bash
export RETURN_AGENT_API_PROFILE=integrated-demo
export RETURN_AGENT_SERVICE_PROFILE=integrated-compass
docker compose up -d --build api agent-service
curl --fail http://127.0.0.1:58000/health
curl --fail http://127.0.0.1:58090/health/ready
```

Web 依 apps/web/README.md 接至此 API；不要誤接原本 8000 的共用服務。健康檢查不等於 business fixture 正確，建案前仍需核對 context。
金額授權使用根目錄 [config/reviewer-gates.json](../../config/reviewer-gates.json)，不是 DB seed。
Compose 將同一檔案唯讀掛載到兩個服務的 `/run/config/reviewer-gates.json`，並設定
`RETURN_AGENT_REVIEW_GATE_CONFIG` 指向該路徑。本機啟動則需指定本機可讀路徑。
目前版本為 `reviewer-gates:1.0`：TWD > 5000、SGD > 200 為 `HUMAN_REQUIRED`，等於門檻為 `PASS`；未設定幣別也要求人工授權，DECLINE 為 `NOT_APPLICABLE`。
修改設定須更新版本並協調兩個服務重啟；核對實際 `config_version`／`config_hash`，不要修改歷史結果。Reviewer REVISE 走 revision budget，不計算金額 gate。

## 4. DB 注入順序

### 4.1 Policy 與 Evidence

Policy 可先載入；Evidence 必须在第 5 節圖片與摘要核對完成後才載入。

```bash
uv run --env-file .env --package return-agent-api return-agent-ingest-policy --input data/demo-case-study/policy.json.example
uv run --package return-agent-api return-agent-seed-evidence --input data/demo-case-study/evidence.json.example
```

Policy 需要實際 embedding 呼叫。相同內容重播 unchanged，active 狀態變更可 updated；不可自動停用未列出的版本。
同 family/version immutable conflict 時停止，不改 ID 掩蓋問題；先比對 canonical fixture。
模型不相容時停止，經確認後才能使用現有 CLI 的 `--reembed` 重建向量；不要為錄影任意更換模型。
Evidence 相同 ID 不同內容會 conflict；人工修改已載入資料時使用新的版本化 ID 並同步 references，不覆寫歷史。

### 4.2 僅提交 A 的預載 Memory

以下是人工執行的既有 service 呼叫，不是新增 CLI。沿用上述隔離 DATABASE_URL。

```bash
uv run --env-file .env --package return-agent-api python - <<'PY'
import json
from pathlib import Path
from return_agent_contracts.models import MemoryCandidate
from return_agent.capabilities.embeddings import embedding_provider_from_env
from return_agent.capabilities.operational_memory import SqlAlchemyOperationalMemoryStore
from return_agent.db.session import create_session_factory
payload = json.loads(Path('data/demo-case-study/memory-preload.json.example').read_text())
candidate = MemoryCandidate.model_validate(payload['candidate'])
store = SqlAlchemyOperationalMemoryStore(create_session_factory(), embedding_provider_from_env())
print(store.submit_candidate(candidate))
PY
```

先檢查 candidate、scope、來源標示，再明確核准；approval 使用服務端時間，不能注入 timestamp：

```bash
uv run --package return-agent-api python - <<'PY'
from return_agent.capabilities.operational_memory import OperationalMemoryGovernanceService
from return_agent.db.session import create_session_factory
OperationalMemoryGovernanceService(create_session_factory()).approve('MEM-STUDY-SPEAKER-PRELOAD')
PY
```

已核准時不要重複 approve；先查看 status。A scope 僅音箱，不能使用空 categories 作 wildcard。
B 生成的 Memory 禁止事先 seed；B 的 candidate 先驗證耳機 scope 與實際 source_case_refs，再以同一 governance service 核准其**實際 ID**。人工作業同意退款不代表已同意 Memory admission。

### 4.3 注入後只讀檢查

```bash
docker compose exec -T api-db psql -U return_agent_api -d return_agent_api -c 'SELECT memory_id, status, policy_version, scope_market FROM operational_memories;'
docker compose exec -T api-db psql -U return_agent_api -d return_agent_api -c 'SELECT * FROM operational_memory_events;'
```

透過現有 store 查詢，A 應含預載 ID；在 B 開始前耳機 query 必須為空：

```bash
uv run --env-file .env --package return-agent-api python - <<'PY'
from return_agent.capabilities.operational_memory import SqlAlchemyOperationalMemoryStore
from return_agent.capabilities.embeddings import embedding_provider_from_env
from return_agent.db.session import create_session_factory
store = SqlAlchemyOperationalMemoryStore(create_session_factory(), embedding_provider_from_env())
for category in ['CAT-AUDIO-SPEAKERS', 'CAT-AUDIO-HEADPHONES']:
    hits = store.query_approved(query_summary='商品到貨損壞，目前只有裂痕近照，缺少包裝識別及連續拆箱情境。',
        market='TW', reason_code='ITEM_DAMAGED',
        required_claim_ids=['DELIVERY_CONFIRMED', 'ORDER_WITHIN_RETURN_WINDOW',
                            'ITEM_PHYSICALLY_DAMAGED', 'DAMAGE_PRESENT_ON_ARRIVAL'],
        categories=[category], policy_versions=['RETURNS-TW:v1'], claim_registry_major=1)
    print(category, [(hit.memory.memory_id, hit.similarity) for hit in hits])
PY
```

submission 與 query 都需要實際 embedding；預載 `retrieval_summary` 是經驗摘要，不放入個資、案件識別或金額門檻。
結果在 approved／scope／version 過濾後依 cosine 排序，保持回傳順序，不改為 confidence 排序。
既有 DB 若有無向量的 Memory，先依 API README 執行 `return-agent-backfill-memory --dry-run` 並完成核對後的回填；新隔離 DB 不需此步驟。
此查詢只驗證 provider 可見性，不證明 Agent 實際使用；後續需觀察 SSE `memory_retrieval` 的 `status`、`hits[].memory.memory_id` 與 `similarity`。UNAVAILABLE 不是 NO_MATCH。若 B 已有匹配記憶，停止並使用另一個隔離資料環境，不刪既有記錄。

## 5. 人工圖片／影像準備

12 張圖片已提供，實際路徑與 artifact 對應見 manifest；需要重製時使用 [prompt.md](prompt.md)。
所有圖片須核對 `DEMO / AI-GENERATED` 標示與摘要，再 seed；檔案存在不代表內容已驗收。
商品文字已固定：A 石墨灰音箱、B 霧黑有線耳機、C 奶油白無線耳機。
生成圖片無法證明真實到貨時間；本包 arrival 序列僅重建合成案例情境。

每案必備四份 IMAGE 素材：`closeup.jpg`（裂痕）、`package.jpg`（商品與包裝）、
`identity.jpg`（合成商品識別）、`arrival.jpg`（有順序的連續收貨拆箱截圖拼圖）。
A 為音箱；B/C 為不同耳機與不同素材，不能重複利用照片冒充新案件。
選配 `unboxing.mp4` 不直接送入 runtime；人工選取截圖，清楚標示人工摘要。

1. 依 assets manifest 拍攝或提供素材。擺拍标為 Demo 模擬，遮蔽姓名、地址、電話。
2. 逐筆核對 evidence summary 與圖片；不支持的描述應修正，不能照範本宣稱已觀察到。
3. 到貨時點不能由上傳時間證明。arrival 素材須具有連續情境；照片不足則維持缺證，不強迫通過。
4. 在實際整合 artifact 儲存位置登錄／提供素材；同步 evidence 與訊息的 artifact_ref。`artifact://` 是識別碼，不是可下載 URL。
5. 使用 Evidence resolve 介面驗證 metadata 可以解析；另外確認人類展示頁或素材檢視工具確實能開圖。metadata resolve 成功不代表 image bytes 可讀。
6. 完成後才更新 manifest 狀態與 artifact_resolvable，再 seed Evidence。未提供圖片時保留 PENDING，不得宣稱即時辨識。

## 6. 逐案 Runtime 操作

以下需要第 1 節 gates 完成。使用 jq 擷取 DTO 子區段（需先安裝 jq），不要把 wrapper 整份送 API。

```bash
export DEMO_API_URL=http://127.0.0.1:58000
jq '.create_case_request' data/demo-case-study/case-a.json.example |
  curl --fail-with-body -sS -H 'Content-Type: application/json' --data-binary @- "$DEMO_API_URL/cases"
```

保存 CreateCaseResponse 的 case_ref 至操作者的 `DEMO_CASE_REF`；不得使用模板 CASE-STUDY-*-TEMPLATE。
用 GET `/cases/$DEMO_CASE_REF` 看狀態，GET `/cases/$DEMO_CASE_REF/events` 看 SSE；不要以固定 sleep 或只有 node completed 判定成功。

```bash
curl --fail -sS "$DEMO_API_URL/cases/$DEMO_CASE_REF"
curl --fail -N "$DEMO_API_URL/cases/$DEMO_CASE_REF/events"
```

### A：已核准 Memory → 補件 → Reviewer gate PASS

確認 case context 為 1200.00 音箱且 retrieved memory ID 含 MEM-STUDY-SPEAKER-PRELOAD。
初始 closeup 不支持到貨時點，等待 evidence_request；若模型直接退款，停止並保存 trace。
依 request 核對實際素材後送出：

```bash
jq '.followup_messages[0]' data/demo-case-study/case-a.json.example |
  curl --fail-with-body -sS -H 'Content-Type: application/json' --data-binary @- "$DEMO_API_URL/cases/$DEMO_CASE_REF/messages"
```

觀察 Verification PASS、Reviewer APPROVE、review_gate PASS、refund SUCCEEDED 與 case RESOLVED。EXECUTING 不算完成；若 Reviewer 持續 REVISE，低額案仍可能因 revision budget 進人工審核。
Memory hit 不代表建議已被採用，需比對 evidence_request 是否一次列出剩餘必要資料。

### B：無 Memory → HUMAN → candidate → approval

重跑耳機只讀 query 確認無命中；將上述建案／補件命令改為 case-b，保存新的 case_ref。
核對 6200.00、耳機類別；Reviewer APPROVE 後應為 HUMAN_REQUIRED／HIGH_VALUE_ITEM。等待 AWAITING_HUMAN_REVIEW，人工讀取 persisted dossier 的原始 claimed scope、提案歷程與證據，不盲目送範本。送出前取得 pending handoff：

```bash
export DEMO_HANDOFF_ID=$(curl --fail -sS "$DEMO_API_URL/cases/$DEMO_CASE_REF" |
  jq -er 'select(.status == "AWAITING_HUMAN_REVIEW") | .human_review.handoff_id | select(type == "string" and length > 0)')
test -n "$DEMO_HANDOFF_ID" || exit 1
jq --arg handoff "$DEMO_HANDOFF_ID" '.[] | select(.scenario_id == "STUDY-B") | .request | .handoff_id = $handoff' data/demo-case-study/human-review.json.example |
  curl --fail-with-body -sS -H 'Content-Type: application/json' --data-binary @- "$DEMO_API_URL/cases/$DEMO_CASE_REF/review"
```

B 的人工範例是 `EDIT`：在證據已充分時，將模型原提案的「退回檢驗」改成免退，並以
`RETURN_REQUIREMENT_INCORRECT` 記錄可泛化 correction。送出前仍須核對本次提案確實要求退回；
若實際提案不同，停止並由人工產生符合事實的裁決，不可為了蒸餾照貼範例。
refund 完成不證明蒸餾完成，Distiller 仍可 SKIP；以下 candidate 步驟僅在實際產生後執行。
觀察 agent-service logs、memory service event／journal 與 operational_memories：必須有 CREATE_CANDIDATE，source_case_refs 必須含 B 實際 case_ref。
FAILED、SKIP、無 candidate 均停止學習段落。候選內容需為一次蒐集到貨證據的具體建議，不能是略過政策或免除高額審核。
先跑耳機 query 確認 candidate 不可見；人工核對後以第 4 節 governance 呼叫核准實際 ID，再 query 確認可見，保存 ID 供 C 比對。

### C：使用 B 經驗但保留 HUMAN

只有 B candidate 核准後才建立 case-c。核對 6800.00、新訂單及不同圖片。
SSE memory hit 必須包含保存的 B Memory ID；僅看到 retrieve_memory node 完成不算命中。
觀察建議是否影響補件，依實際 request 提交 case-c followup；Memory 不影響金額 gate，Reviewer 不消費 Memory。
人工確認後將上述 jq 的 STUDY-B 改為 STUDY-C，重新取得 C 的 case_ref／pending handoff_id 才提交。核對 audit、退款 SUCCEEDED 與 RESOLVED。
C 到達人工審核及結案後，重新讀取 Case API，`human_review.memories_used` 均須保留 B 的實際
Memory ID；Activity 命中但 Case API 為空視為失敗。
C 同樣不保證產生 candidate；「所有人工結果必定蒸餾」仍是待整合需求。

## 7. 錄影、查核與重跑

分鏡見 scenarios：00:00–00:25 架構；00:25–01:20 A；01:20–03:15 B 學習及核准；
03:15–04:35 C；04:35–05:00 audit 與 mock 金流聲明。
允許剪掉模型與人工等待，不能倒置 approval／retrieval 時序，不能用預填結果代替執行。
若無實測對照，不宣稱輪次一定下降或量化準確率改善。

只讀核對 API DB 的 handoff_verifications、human_reviews、refund_executions、
operational_memories、operational_memory_events；以實際 case_ref／handoff_id 串聯。
可用 `docker compose logs --no-color agent-service` 查看 worker 異常；記錄實際 memory job ID 與終態。
Reviewer EXIT 的 `node_exit.payload.review_gate` 顯示本次金額判定；人工案件的 dossier 與退款 request 保留 gate。核對 version、hash、amount、currency、threshold、status、reason。歷史 risk_evaluations 不代表本次執行。
查核 case、Reviewer gate、refund 與 memory 各自結果，不把其中一項成功當成全部成功。

重跑要產生新的 order_ref/user_ref，同步 snapshot_ref 與 keyed fixture mapping；case_ref 仍由 API 生成。
若換商品或素材，更新 line_item_id、subject、artifact references。沿用同訂單可能被退款 reservation 擋下，不能刪除 audit 迴避。
重錄「首次無 Memory」使用新隔離環境，保留舊環境成果。

## 8. 驗證狀態與研究依據

- 本包可驗證：JSON、DTO 子區段、keyed case snapshot、Policy/Evidence loader、references、decimal 合計、時間、scope 及 canonical policy 一致性。
- B → C 必須保存實際 candidate、governance approval、C retrieval similarity 與 Case API `memories_used`；Distiller SKIP 時不可宣稱學習完成。
- 已提供：12 份圖片；待人工核對圖片內容、摘要及模擬標示，並完成 artifact 展示接入與 Memory admission；3 段影片為選配。
- live run 證據應記錄在 PR／驗收紀錄，不把一次執行產生的 case ID 或分數硬編碼回 fixture。

案例設計參考 [Shopify 退貨規則](https://help.shopify.com/en/manual/orders/self-serve-returns/return-rules)
對退貨期間的設定，以及 [Shopify 退貨詐欺討論](https://www.shopify.com/blog/return-fraud)
對商品與退回狀態核對的問題背景。這些只提供情境靈感，非本系統政策來源；
七日期間、TWD 5000 門檻與 Memory 治理均以 repo 自訂 Demo 規則為準。
