# Operational Memory

Distiller prompt 3.0 以完整 learning trace 產生整案回顧、學習判定及至多一則候選。排除系統缺陷與無根據的 Reviewer 異議；採納不等於普遍正確，結案不等於因果效益。Memory 改善下一案尚須對照驗證。

人工無法收斂裁決沿用既有 correction trace 與非同步 Distiller：保留原 Reviewer 意見、人工最終決定及整體 review_note，不將人工改判偽裝成 Reviewer APPROVE。人工結果帶 reviewer_id 作稽核；不因此自動核准 Memory，也不新增歷史案件索引。

Operational Memory 用來保存可泛化的操作經驗，而不是自動改寫正式 Policy。Memory pipeline 與案件決策解耦，失敗不得阻塞案件輸出。

## 觸發來源

- Reviewer 回傳 `REVISE`：立即記錄 `DecisionRevisionEvent`，但不立即發布 memory。
- Human Review 回傳 `EDIT` 或 `REJECT`：記錄 correction 與 final resolution reference。
- Reviewer `APPROVE` 或 Human `APPROVE`：只用於補足案件最終結果，不單獨形成 candidate。

所有取得最終核准／拒絕結果的案件均準備背景蒸餾，包含無修正案件。等待補件、等待人工與技術性終止不算完成裁決。缺失、超限或不安全的 learning trace 明確 SKIP；不得以 correction history 或 Activity 補造完整歷程。

此處的「最終結果」= `emit_resolution_handoff` 產出的 `ResolutionHandoff`（agent/human 端最終結果）。執行系統的執行確認不在 Agent 團隊範圍，蒸餾不等待它。

實作上，主 graph 的 `enqueue_memory_distillation` 只組裝 `MemoryDistillationInput` 並存入 LangGraph checkpoint。Agent Worker 發布 durable `RESOLVED` event 後即可完成主 command；另一個 consumer group 的 Memory Enqueue Worker 讀取 checkpoint payload，發布至 `return-agent.memory-jobs.v2`。Memory Worker 再獨立執行模型蒸餾與 `submit_candidate`。因此 memory 服務故障不會回滾或重跑已完成的客戶 resolution。

Memory Worker 在 Agent DB 的 `memory_job_results` 保存首次蒸餾結果及 prompt
version，成功 commit 後才提交 candidate；再保存含 `submission_ref` 的完整 terminal
event，commit 後才發布 Redis。重送或重啟沿用既有結果與事件，不再次蒸餾、不改寫
同一 `memory_id` 的內容；若提交結果不明而尚未保存 event，只能重送相同 candidate。
同一 `job_id` 的 semantic input 必須相同（enqueue 重送的 `issued_at` 除外）。
此表由 Agent Service 專用 Alembic migration 管理，與 API DB／LangGraph checkpoint
migrations 分離；重播紀錄不可在 Redis job 仍可能重送時清除。

兩個 Memory worker 對 retry-safe 的 Redis／checkpoint／replay DB 暫時性傳輸
失敗採 capped exponential backoff；delay 由 Agent Service settings 配置，成功一輪
即重設。等待可被 stop/cancellation 立即中斷，永久驗證／授權／程式錯誤不重試。
模型失敗仍產生 terminal `FAILED`；candidate submit 只有已保存 output 且確認是
暫時性 transport error 才以相同內容重送。Retry 不重跑 customer graph。

## Whole-case learning v2

Runtime 每個完成節點獨立產生 typed `LearningEvent`，隨 graph update 原子 checkpoint；不從 Activity、narration 或 hidden reasoning 重建。事件 ID 由 thread、sequence、node 穩定決定；interrupt 不產完成事件，補件需求已在前一個 assessment/proposal event 保存。

涵蓋初始 normalized claim、品項／澄清、Case／Policy 版本、Memory 命中及方法、每輪補件需求與實得證據 references／中性摘要、assessment、提案、Verification、Reviewer／revision、人審與最終裁決。無原始媒體、artifact URL 或聊天全文；明顯個資會使 trace 標為不可蒸餾，不默默删去後當成完整。這是有限的格式／明顯個資檢查，不是完整 DLP 保證。

`RETURN_AGENT_LEARNING_TRACE_MAX_EVENTS` 預設 96（上限 256）；`RETURN_AGENT_LEARNING_TRACE_MAX_BYTES` 預設 131072 bytes。超限保留先前事件並標 `LIMIT_EXCEEDED`，Distiller 不處理局部歷程。缺失／不完整、不安全或超限分別回 `TRACE_INCOMPLETE`、`TRACE_UNSAFE_CONTENT`、`TRACE_LIMIT_EXCEEDED`。

單次模型呼叫輸出 `case_review`、`learning` 與至多一則 candidate 或 SKIP。回顧及學習判定保存於 Agent-owned replay；不加入 case 向量索引。候選需 `applicability_limits` 與 `prohibited_inferences`，核准後同樣傳給 Resolver；Reviewer 不讀 Memory。只有 `VERIFIABLE_ERROR`／`OPERATIONAL_METHOD` 可產候選；來源驗證不等於方法具有因果效益。

新候選的 reason／claim／category scope 不得超出來源案；store 將空列表視為 wildcard，因此來源的允許列表非空時，新候選不可用空列表擴大適用範圍。此限制不改寫歷史經驗的治理狀態。

新工作與事件使用 schema v2、`memory-v2:`／`memory-event-v2:` ID namespace、v2 Redis streams／consumer groups。既有首次結果及 terminal event 不覆寫；pending job 的 prompt version 不相符時拒絕執行。V1 jobs、pending graph 與 replay records 不自動轉成 v2；切換前須排空或隔離，由原版本處理舊 pending 工作。

API migration `0014_memory_learning_sources` 保留歷史來源值、治理狀態、事件、摘要及向量，rename source 欄位，補空限制欄位並更新可投影候選的 payload hash。舊版無摘要資料保留原 hash。已有 v2 來源／限制資料時拒絕破壞性 downgrade。需 online migration，只在隔離 DB 驗證後才安排部署；本變更不重啟服務。

測試通過只證明契約、儲存及恢復流程；Memory 效益仍須 A 無 Memory／B scoped 經驗注入／C 真實檢索的分組配對、反例與遷移測試。未完成實測前，不宣稱越用越準。

### Experience lifecycle

```text
Case intake and every completed investigation/review step
→ bounded typed learning trace in checkpoint
→ wait for final adjudication (not refund execution)
→ reject incomplete, oversized or unsafe trace
→ whole-case review and learning judgment
→ at most one operational candidate or SKIP
→ validate scope, policy version and claim registry version
→ retrieval_summary embedding + atomic candidate insert (API)
→ human/governance approval
→ APPROVED memory
→ retrieve only within matching scope
→ RETIRED when stale or invalidated
```

狀態只能依序轉換：

```text
CANDIDATE → APPROVED → RETIRED
```

Agent 不得自行將 `CANDIDATE` 升級為 `APPROVED`。Approval workflow、storage 與 UI 由外部 owner 負責，介面見 [External Interfaces](08-external-interfaces.md)。

## MemoryCandidate

```json
{
  "memory_id": "MEM-001",
  "retrieval_summary": "Damage claim has only close-up images; collect missing evidence together.",
  "trigger_conditions": [
    "damage claim evidence contains only a close-up of the product, outer packaging not in frame",
    "at least two required USER_EVIDENCE claims are missing at the same time"
  ],
  "recommended_behavior": "Request all missing evidence (outer packaging, damaged area, and other missing claims) in a single EvidenceRequest instead of splitting it across rounds.",
  "rationale": "Human review overturned the original FULL_REFUND to DECLINE because evidence did not establish damage on arrival.",
  "source_case_refs": ["CASE-005"],
  "source_event_refs": ["LEARNING-SOURCE-001", "LEARNING-SOURCE-002"],
  "applicability_limits": ["Arrival-damage claims with missing context only."],
  "prohibited_inferences": ["A damage photo alone does not establish arrival timing or refund eligibility."],
  "policy_version": "POLICY-12:v3",
  "claim_registry_version": "claim-registry:1.0",
  "scope": {
    "market": "TW",
    "reason_codes": ["ITEM_DAMAGED"],
    "claim_ids": ["DAMAGE_PRESENT_ON_ARRIVAL"],
    "categories": []
  },
  "confidence": 0.72,
  "status": "CANDIDATE"
}
```

`scope` 欄位語意：

| 欄位 | 空值語意 | 匹配規則 |
| --- | --- | --- |
| `market` | 不得為空 | 必須等於 `CaseContext.market` |
| `reason_codes` | 空 = 不限 | 非空時只能取自本案最後提案的 `reason_code` |
| `claim_ids` | 空 = 不限 | 非空時必須是適用條款 `required_claim_ids` 的子集合 |
| `categories` | 空 = 不限 | 非空時必須是本案 `claimed_line_item_ids` 對應 `category_ref` 集合的子集合 |

`confidence` 是 candidate quality metadata，只用於 cosine 同分時的排序，**不得**用來越過 Policy 或自動 approve。

Runtime 會把上述可用值以 `allowed_scope` 提供給 Distiller；模型必須原樣複製
opaque identifier，不得自行翻譯或縮寫。輸出仍由 deterministic validator 驗證，
超出來源案件的 scope 會失敗且不得提交 candidate。

## ApprovedMemory

`retrieve_memory` 消費的形狀。它是 approval workflow 對 `MemoryCandidate` 核准後的儲存記錄，由外部 memory store 提供（見 [External Interfaces](08-external-interfaces.md)）。

```json
{
  "memory_id": "MEM-001",
  "retrieval_summary": "Damage claim has only close-up images; collect missing evidence together.",
  "status": "APPROVED",
  "recommended_behavior": "Request all missing evidence (outer packaging, damaged area, and other missing claims) in a single EvidenceRequest instead of splitting it across rounds.",
  "trigger_conditions": [
    "damage claim evidence contains only a close-up of the product, outer packaging not in frame",
    "at least two required USER_EVIDENCE claims are missing at the same time"
  ],
  "policy_version": "POLICY-12:v3",
  "claim_registry_version": "claim-registry:1.0",
  "scope": {
    "market": "TW",
    "reason_codes": ["ITEM_DAMAGED"],
    "claim_ids": ["DAMAGE_PRESENT_ON_ARRIVAL"],
    "categories": []
  },
  "confidence": 0.72,
  "approved_at": "2026-09-02T09:00:00Z"
}
```

與 `MemoryCandidate` 的差異：`status` 固定為 `APPROVED`、多了 `approved_at`，且**不含** `rationale`、`source_case_refs` 與 `source_event_refs`。這些是給人審核用的溯源欄位，不應進入 Resolver 的 prompt —— 注入來源案件只會讓模型把舊案件的細節當成本案事實。溯源仍保存於 memory store，供稽核查詢。

## 蒸餾規則

Memory Distiller 必須比較：

- 原始 `ProposedDecisionHandoff`。
- Reviewer `revision_reasons` 與 `reviewer_claim_findings`。
- 修正版 handoff。
- `HumanReviewResult.review_note`，以及 `corrected_decision` 與 `correction_reason_code`（若為 `EDIT`）。
- `HumanReviewResult.generalizable`（若人工有提供）只作為提示；Distiller 仍須依結構化全案 learning trace 自行判斷，不得因 `true` 直接建立 candidate。
- 最終結果、適用 Policy version 與 claim registry version。

比較必須是**結構化比對**：`action`、`refund_scope`、`return_decision` 的前後差異，以及 claim finding 的 status 差異。三種人工結果的 `review_note` 都必須保留作稽核脈絡，但不能取代結構欄位。

只有 correction 可抽象為跨案件適用的行為提示時，才輸出 `MemoryCandidate`。下列情況輸出 `SKIP`：

- 只有單一使用者的偏好或個人資訊。
- 修正源自資料輸入錯誤，沒有可泛化行為。
- 無 final outcome，無法確認 correction 是否被採納。
- Policy 版本或 claim registry 版本未知、已失效，或 correction 與正式 Policy 衝突。
- 內容只是重述現有 Policy 或 claim registry 的 `observable_requirement`，沒有額外操作價值。

## Retrieval 與 precedence

首次：`retrieve_policy → prepare_memory_query → retrieve_memory → assess_case`。補件：`request_evidence → prepare_memory_query → retrieve_memory → assess_case`。

`prepare_memory_query` 先解析尚未處理的附件，再呼叫一次 LLM 產生中性 `query_summary`：退貨主張、申請品項、可信訂單事實與當下證據。不得讀舊 Memory、預判退款資格、臆測證據缺口或輸出個資／原始 artifact URL。程式獨立產生下列 scope 與版本條件，模型無權修改：

```text
status = APPROVED
AND scope.market = CaseContext.market
AND (scope.reason_codes 為空 OR 包含 normalized_intent.reason_code)
AND (scope.claim_ids 為空 OR 與適用條款 required_claim_ids 有交集)
AND (scope.categories 為空 OR 與 claimed line items 的 category_ref 集合有交集)
AND policy_version ∈ { 適用條款的 policy_version }
AND claim_registry_version 的 major version = 當前 registry major version
```

排序與上限：

- 篩選後使用精確 cosine similarity 遞減排序；同分依 `confidence DESC, approved_at DESC, memory_id ASC`。
- 回傳 `MemorySearchHit { memory: ApprovedMemory, similarity: [-1,1] }`。不設未校準門檻、不增加 reranker、不做 confidence-only fallback。Graph 保留 provider 順序。
- 最多注入 `top_k = 3` 筆。超出者丟棄，不做摘要合併。
- 查無結果時 `operational_memory[]` 為空陣列，流程照常進行。

precedence 與邊界：

- Resolver（`assess_case` 與 `propose_decision`）是唯一消費者。
- **Reviewer 預設不讀 Operational Memory。這是刻意設計，不是遺漏。** Memory 只影響取證方式與提案品質，不影響 eligibility；Reviewer 的職責是依正式 Policy 與 evidence 獨立複核，讀取 memory 只會讓它繼承 Resolver 的既有偏誤。
- Memory 必須標明來源 case references，但送入模型前應移除 PII。
- Memory 只能影響 evidence collection、提案方式或注意事項，**不得**新增 eligibility、授權退款、改變 `refund_scope` 的合法性判準或覆寫 `return_policy`。
- 正式且適用版本的 Policy 優先於所有 Operational Memory。衝突時忽略 memory。

## 失效與重新驗證

下列任一情況發生時，相關 memory 必須重新驗證或標為 `RETIRED`：

- 引用的 Policy 條款更新或失效。
- [Claim Registry](07-claim-registry.md) 升 major version，且 memory 的 `scope.claim_ids` 或 `recommended_behavior` 引用了受影響的 claim。
- Registry 的 `observable_requirement` 收緊，使 `recommended_behavior` 與現行要求不一致。

`claim_registry_version` 因此是 candidate 的必填欄位 —— 沒有它就無法判斷一條「請補外箱照片」的經驗是否仍符合現行的 `observable_requirement`。

## Privacy 與 audit

- Candidate 不保存姓名、電話、地址、聊天原文、付款資料或 artifact bytes。
- Shared semantic validator 會拒絕 candidate natural-language 欄位中的明顯 email、電話、付款卡號、具名姓名/地址標記與 raw artifact URL；此檢查是 prompt 之外的最後一道 deterministic boundary。
- Memory failed event 只保存錯誤型別與一般化訊息；模型輸出或 validation error 原文不得寫入共享 event stream，以免錯誤訊息反向洩漏候選內容。
- Source case 使用 opaque reference。
- 蒸餾輸入、prompt version、claim registry version、輸出與 approval/retirement event 必須可追溯。
- 新候選 `source_event_refs` 必須存在於本案 `LearningTrace.events`。未發生 revision 不得偽造 revision；migration 保留歷史來源值但不重新蒸餾舊工作。
- 刪除或保留期限由外部 data governance owner 定義；Agent spec 不自行指定。

人工接手由 Reviewer 修正 budget 用盡觸發，不再依風險門檻。最終 ResolutionHandoff.review_result 保留最後一次審核與未解決異議，連同三次 revision_events 形成 correction trace；不得把 REVISE 本身當作拒絕退款或已成立的 fraud fact。


## 向量儲存與失敗語意

只索引蒸餾後的操作經驗，不做歷史案件搜尋。一筆 Memory 一個向量、不切 chunks。
Policy 與 Memory 共用 Compass `text-embedding-3-large`，1536 維。
部署 factory 與 Compose 預設 Compass endpoint；只使用專用 embedding key/key file，
不借用 OpenAI credential。embedding timeout 預設25秒，可由 RETURN_AGENT_EMBEDDING_TIMEOUT_SECONDS 調整；無 SDK 自動 retry。
Distiller `memory-distiller:3.0` 保留 `retrieval_summary`（適用情境＋可泛化建議行為，1–2000 字元）與 trigger/action/rationale/source，加入整案回顧、學習依據、適用限制與不可推論事項。
API 在 candidate 提交時產生 embedding；摘要與向量成功後才原子寫入。
先檢查既有 memory_id/hash，再做外部 I/O，再 transaction insert/recheck；重送相同 candidate 不新增記錄、不重新 embedding。
DB derived columns：retrieval_summary、summary_version、summary_hash、embedding_model、embedding。
summary_hash 是 UTF-8 canonical JSON string 的 SHA-256；新摘要版本為 memory-summary:1.0。
原始 candidate_payload_hash 繼續用於冪等識別，回填不得改寫它。

檢索每次整批替換 operational_memory 與 typed observation。OK＋hits=[] 是正常空結果；
摘要失敗是 UNAVAILABLE/SUMMARY_UNAVAILABLE，embedding、VDB 或模型不符是 UNAVAILABLE/RETRIEVAL_UNAVAILABLE。
失敗時清空本案 Memory 並繼續 assessment，不回退到舊命中或 confidence 排序。
附件解析／scope 驗證失敗仍 fail-closed。可用性失敗不帶 provider 原始錯誤或敏感模型輸出到 UI。

NodeExecutionObservation.memory_retrieval 經 Agent Service NODE_OBSERVED、Redis、API event projector 產生
memory_retrieval SSE event，包含 status/query_summary/hits/error_code。API 以同一 transaction 保存 lifecycle 與檢索事件，
依既有 event ID/index 去重。Web 依 seq replay，重新進入 prepare 時清除前次顯示，
最新事件取代舊卡片（包括空或 unavailable）；顯示摘要、條件、建議行為、cosine 及獨立的 confidence。
Reviewer 不消費此 observation 或 Memory。

## 遷移與切換 runbook

1. 先在隔離 PostgreSQL 演練。0011_memory_vectors 只新增 nullable derived columns，不刪既有資料、狀態、來源或 governance event。
2. 正式切換另排維護窗口；停止接收新案件／補件及 Memory job，排空 commands、events、outbox 和舊蒸餾 replay job，確認無舊 worker 寫入。備份 API DB、Agent DB/checkpoint/replay 與 Redis pending jobs，記錄可回復的 image/config。
3. 升級 API schema；以目標模型設定執行 `return-agent-backfill-memory --dry-run`，核對清單後執行 `return-agent-backfill-memory`。舊摘要只由 `Situation: trigger_conditions\nAction: recommended_behavior` 機械組合，版本 legacy-composed:1.0，不再讓 LLM 改寫。逐筆 transaction、外部 embedding 失敗即明確退出，已完成記錄保留，修正後重跑續接。空白、PII、過長或無效向量須明確人工處理，不截斷、不跳過冒充成功。
4. 使用既有 `return-agent-ingest-policy --input <每份原始 fixture> --reembed`；不得改 Policy 文字、checksum、版本或歷史 retrieval bundle。舊 fixtures 必須完整涵蓋所有啟用條款。
5. 在隔離／維護窗口核對所有 Memory（含 Candidate/Retired）及 Policy 向量皆為 large、1536 維且摘要/hash 完整；dry-run 全部 unchanged，正式檢索可返回帶分數結果。未完成或模型不同的 scope 不可恢復成正常結果。
6. 協調 API、Agent Service、Web 同時升版（query_summary 必填、回傳 wrapper、SSE 事件與 checkpoint state 已改）。既有暫停 checkpoint 須先完成或受控重開，不能拿舊 version payload 混送。通過 smoke 後才恢復 ingress/retrieval；本功能 commit 不執行部署。
7. 失敗時保持停寫，優先回復已驗證的完整 DB/config/images 備份；不可只 downgrade 欄位卻留新版 jobs、candidate hash 或 checkpoint。

可重現驗收：scripts/run_memory_vdb_rehearsal.py 使用合成案例與經驗、真實 LLM／large embedding／pgvector，
輸出完整 JSONL、耗時與保留性 assertions。舊 Policy 向量為明確標示的 synthetic legacy fixture，不是假稱生產資料。

Integrated demo bootstrap 僅建立尚不存在的 fixture Memory；既有記錄核對原始經驗內容後保留其摘要、冪等 hash 與 Candidate／Approved／Retired 狀態，不重新提交或核准 migrated fixture。


## 2026-09-10 隔離實跑紀錄

合成經驗／evidence fixtures，真實 Compass LLM（compass-5.6-luna Responses）、
text-embedding-3-large/1536 與 pgvector；不是生產案件，也未部署。
完整 output 保存於 .artifacts/memory-vdb-rehearsal/output-v5.jsonl（本地驗收 artifact）。

| 階段 | LLM 摘要 | embedding＋檢索 | Top 3（cosine） |
| --- | --- | --- | --- |
| 首次：只有裂痕近拍 | 3.7436 s | 0.8214 s | ARRIVAL .547873 → BATTERY .533044 → SERIAL .500519 |
| 補件：到貨外箱與裂痕同框 | 2.6996 s | 0.7645 s | ARRIVAL .540904 → BATTERY .522424 → SERIAL .509221 |

ARRIVAL confidence=.70，仍優先於 BATTERY=.95／SERIAL=.99，證實未按 confidence 重排。
兩次摘要與分數不同，命中次序不必因補件而強制改變。較弱相關的電池／序號經驗仍可能進入 Top 3；
cosine 不是適用性保證，Resolver 仍須核對 trigger，不能把經驗當本案事實。這份小型結果不是品質校準，未據此增加門檻或 reranker。
先前較冗長摘要的 output-v4.jsonl 亦保留：補件後曾把 SERIAL 排第一，因此 prompt 收斂為短句、移除 opaque category IDs／精確時間戳以減少干擾，未修改 scope 與排序程式。

migration 0.2554 s；3 筆 legacy 回填／dry-run／續跑 3.6096 s，原欄位保持一致。
Policy reembed 1.6607 s，文字、版本與歷史 bundle 不變；7 筆 Memory 與 Policy 模型皆一致為 large。
回填 failure/resume（包括逐筆摘要／向量驗證失敗識別）、205筆 keyset batches、scope/status/version、atomic submission 與服務事件 replay 另由離線 regression tests 驗證。

驗證命令：`make check`、改動檔案的 `uvx ruff check`、Web `npm test`／`npm run lint`／`npm run build`／`npm run test:browser`，以及 `docker compose -p memory-vdb-validation build api agent-service web`。完整 source-tree Ruff 掃描仍有未改動檔案的既有 lint 問題；本次只修與檢查改動檔案，不宣稱整個 monorepo 的全域 lint 已清零。

最終驗證：Python 332 tests（contracts 58、API 165、runtime 58、Agent Service 50、跨服務 E2E 1）全數通過；Web 5 unit tests、6 browser tests、lint、TypeScript／production build 通過；API／Agent Service／Web Docker images build 通過。未執行現有服務部署或正式資料庫切換。

### Activity tracing

Activity tracing 以 MEMORY scope、原 command 的 run_id、job_id 及每次執行的 attempt_id 關聯背景工作。
排程／STARTED／RETRYING／COMPLETED／SKIPPED／FAILED 與 distill_memory、submit_candidate lifecycle
透過獨立 activity stream 即時傳遞；不等待案件主 stream、不因案件 terminal 而停止 SSE。
範圍止於 Candidate 提交、skip 或 failure，後續人工核准不在本版。重送沿用 Memory 既有 journal／replay，不能為 trace 重做業務提交。
node_summary 解說工作不讀 Candidate 原文或歷史 Memory，只取當次 allowlisted facts。

### API／Compass main 整合驗證

Rebase 至 `fda55d7`（main PR #19）後，保留 Compass Responses completed／解析失敗驗證與 Qwen profile，補齊上游 candidate 測試的 retrieval_summary，並覆蓋 MemoryQuerySummary 的 Responses 成功與無效輸出。
`make check` 共350 tests（contracts 58、API 165、runtime 72、Agent Service 54、跨服務 E2E 1）通過；Web unit／browser tests、lint、TypeScript／production build 與三個 Docker image build 通過。此輪沒有重新呼叫 live LLM、遷移正式 DB 或部署服務；上方實跑 output 仍是先前隔離驗收紀錄。
