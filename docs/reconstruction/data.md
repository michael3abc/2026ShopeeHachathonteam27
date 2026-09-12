# 資料字典、索引與交易附錄

每欄 SQL 型別／nullable／PK／FK／server/application default與索引在 [dictionary.json](assets/db/dictionary.json)，可閱讀版在 [欄位附錄](reference-fields.md)；所有check/unique/index的精確 PostgreSQL定義在 [API fresh SQL](assets/db/api-fresh.sql)。JSON欄位的合法 shape由schemas定義，下表説明其內容，不以任意JSON代替。

## API 所有權與 JSON payload

| table | 主用途／JSON結構 | 識別及約束語意 |
| --- | --- | --- |
| cases | canonical狀態，非graph state | PK case_ref；thread unique；order/user索引；status check |
| case_events | kind=agent_event存AgentEvent；user_turn存{message,attached_artifact_refs} | FK case cascade；unique(case,seq)，seq>0；只agent_event供SSE |
| agent_command_outbox | immutable AgentCommand | PK command_id，attempt≥0；published、claim owner/until、lease_token |
| processed_agent_events | producer event dedup/hash | PK event_id、FKcase、command_id/event_index |
| agent_event_projection_cursors | 每command已連續投影index及終止event | PK command_id；FKcase；index非負 |
| rejected_agent_events | restricted raw_body,error_code/message | PK source_message_id；不可當Activity payload |
| evidence_items | artifact→EvidenceItem所需中性欄位 | opaque identity/subject/type/time，非blob |
| policy_documents | family/version/source/checksum/active | family+version、source+version唯一定義 |
| policy_clauses | structured scope、claims、actions、return rule、text、vector | FK document、clause_id；string arrays scope；vector1536 |
| policy_retrievals | exact PolicyBundle JSON，request_hash | bundle_version/request_hash身份與重讀校驗；保留歷史 |
| operational_memories | candidate資料、retrieval_summary/vector、sources/scope/status/approval | PKmemory_id、submission_refunique、candidate_payload_hash、confidence range與status check |
| operational_memory_events | 治理from/to狀態及時間 | FKmemory；不可刪來源來通過回填 |
| handoff_verifications | handoff_payload=ProposedDecisionHandoff、result_payload=VerificationResult | handoff_id/hash，外部execution依此授權 |
| human_reviews | handoff_payload、review_payload、dossier_payload、result_payload | handoff/ref/case綁定；hash覆蓋handoff+review+dossier；reviewed_at/result一致 |
| refund_executions | request_payload=ExecuteRefundRequest；application_result_payload=RefundApplicationResult | execution_ref/handoffunique、payload_hash、IN_PROGRESS/SUCCEEDED/REJECTED、attempt timestamps |
| refund_item_reservations | 每order/item進行中或既有付款owner | PK(order_ref,line_item_ref)、execution FK；衝突atomic回滾本次新增全部items |
| refund_execution_items | 成功付款品項ledger | order/item唯一，execution FK、可追溯已退額 |
| case_activities | ActivityEvent完整safe投影JSON | PKevent_id、unique(case_ref,seq)、FKcase；獨立序號 |
| activity_narration_outbox | NarrationJob.source=已完成summary僅facts；result_event_id | PKsource_event_id FKactivity；dispatched索引；同來源不重派／不重複接受結果 |

表格是語意索引；若用語與實際 table name不同，SQL/dictionary提供實際名稱，重建可對照調整命名但不可漏constraint。

## Agent DB

- [agent journal DDL](assets/db/agent-journal-fresh.sql)：agent_command_journal，command_idPK，state RUNNING/COMPLETED/FAILED、claimed_by/until、updated_at。lease過期可重新claim，不等於強制取消舊進程。
- [Memory replay DDL](assets/db/agent-memory-fresh.sql)：memory_job_results，job_idPK、input_hash、prompt_version、result=MemoryDistillationOutput、terminal_event=MemoryServiceEvent；首次結果先存再submit；terminal先存再publish。獨立Memory migration版本表，不混API history。
- [checkpoint migration SQL](assets/db/checkpoint-migrations.json)：按已鎖LangGraph library的ordered_sql建立 checkpoints/checkpoint_blobs/checkpoint_writes及migration bookkeeping。這是第三方storage contract，setup按版本執行；checkpoint metadata/thread/namespace/id與typed state一致，序列化限制採M02。

## Transaction boundaries

| 邊界 | 同一transaction | 外部I/O與恢復 |
| --- | --- | --- |
| case create | case＋initial transcript＋START outbox | commit後publish，失敗重送原command |
| message/review | case lock、input/result存檔、status/state_change、RESUME outbox | commit後喚醒，pending狀態防雙次resume |
| Agent event projection | dedup/hash/index、case/state events、cursor | 成功commit後ACK；refund mutation有獨立ledger，不能靠ACK宣稱已付款 |
| verification/human submit | handoff/review/dossier exact hash與資料 | 同ID異內容conflict；不能覆寫原資料授權 |
| refund reserve | execution lock、全部items savepoint、application_started | commit→apply；結果未知保留owner，same key replay |
| refund finish | application result＋terminalexecution＋成功item ledger | externalapply成功但DB失敗走同key恢復；UI最後才投影 |
| Memory candidate | 第二次查重＋summary/vector/source/metadata一起insert | embed在transaction外，失敗無半筆；並發unique後再判hash |
| Memory governance | rowlock＋status/time＋治理event | 不能從retired悄悄approve；queryembed後再次檢查visibility |
| Policy ingest/reembed | documents＋所有clauses/vectors／active | 全成全敗；改embedding不改歷史bundle |
| activity append | caselock seq＋event＋narrationoutbox／resultlink | commit後RedisACK，重送可重讀 |
| Memory job save | 首次result／terminalevent | publish和DB不是原子，利用唯一job/hash+cache重播 |

## 新建與遷移分開

從空專案重建可把fresh DDL化為自己的初始Alembic migration，不需要重做歷史risk-gate欄位。既有DB升級必看 [baseline migration chain](assets/db/migration-history.json)：0001 evidence→0002case→0003policy→0004memory→0005safety historical risk→0006refund→0007reservations→0008bridge→0009human→0010reviewer handoff→0011memoryvectors→0012dossier→0013activity。

既有migration檔的歷史名稱不是現行node；不能因此恢復risk gate。0007舊成功refund row需合法scope/ledger資料，不能盲改reservation；0011舊Memory允許先nullable但不得正常檢索直到backfill；0012有dossier資料時downgrade必須保護，offline SQL先執行PostgreSQL DO檢查有資料raise exception才允許drop；0013刪除activity屬資料毀損操作須備份。

此包另附每一版對前版的離線SQL（assets/db/migrations），不附原Python migration程式。例如 [0011 Memory vectors](assets/db/migrations/0011_memory_vectors.sql)、[0012 dossier](assets/db/migrations/0012_human_review_dossier.sql)、[0012 protected downgrade](assets/db/migrations/0012-protected-downgrade.sql)。這些SQL有原版前置保護：0007有既存refund資料會刻意中止，不可刪保護來強行升級。重建migration的online preflight必須驗每筆IN_PROGRESS/SUCCEEDED的canonical JSON SHA256、handoff/case對應、execution_blocked=false、FULL_REFUND、非空unique scope與order；所有(order,item)只能一owner，成功ledger集合必須精確等於成功request的scope。確認後才從successful ledger與IN_PROGRESS scope回填reservations；任一未知外部付款結果先人工對帳。

不知道升級起點、既有資料形狀、backup狀態時停止，不把fresh SQL套到有資料DB。恢復演練需記錄起點revision、row counts、constraints、向量模型分布、failure續跑與rollback保護。本次驗證SQL能離線產生，沒有對既有部署執行遷移。
