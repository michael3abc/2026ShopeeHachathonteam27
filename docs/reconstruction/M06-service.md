# M06：Agent Service／非同步事件

## 責任與非責任

composition、health、Redis workers、journal/checkpoint、Memory enqueue/distill/replay、Activity transport 與 narration。Runtime observer 只收 typed emission，不持 transport。API 自行持久化 activity 與配 seq。

## 依賴

M01/M02、API internal Provider HTTP、Redis Streams、Agent Postgres、API command/narration outbox。stream/group 名稱完整見 [常數](assets/redis-constants.json)；契約與交付規則見 [介面](interfaces.md)。

## 輸入輸出

START／RESUME command，NODE_OBSERVED／INTERRUPTED／RESOLVED／ESCALATED／RUN_FAILED event（實際 discriminator 值以 schemas 為準）。每筆 Redis stream entry 的 field 為 `body`，值是一份版本化 JSON。ID 與 stream entry ID 分離；不要用 Redis ID 當 API case/activity seq。

## 資料與演算法

- **M06-R01**：API command outbox transaction commit 後 dispatcher lease claim、XADD，再 mark published；發送成功但 mark 失敗可能重送。Agent journal claim 三態 CLAIMED/BUSY/TERMINAL；TERMINAL ACK、BUSY 留 pending，不重跑。durable journal 用 900s lease（可配置），同 thread command 加鎖。
- **M06-R02**：worker 讀 consumer group，XAUTOCLAIM 回收久未 ACK；解析錯誤走 DLQ；node observations 與 terminal event 具 command_id/event_index，API 按 index 投影。先完成持久化再 ACK；網路錯誤不能提前承認完成。不是全系統 exactly-once。
- **M06-R03**：graph runtime 與服務 health 獨立。demo/demo-qwen 可使用 memory journal；integrated profiles 需 durable Postgres journal/checkpointer。production 未完成 composition 時不可用 demo fallback 假裝生產可用。
- **M06-R04**：Memory enqueue consumer 讀 resolved event，自 terminal result 取得 distillation_input，穩定 job_id；不可阻塞主 case event consumer。distiller 首次輸出存 Agent DB memory_job_results 後才 submit candidate，terminal event 先存後 publish。job input_hash 排除 issued_at，prompt version 綁定；重送同 job 不再生成不同經驗。

此處 resolved event 指 **Agent RESOLVED**，不是 API 已確認退款 APPLIED；兩個 consumer 獨立，Memory 可能與退款並行。時序圖畫出常見到達順序，不承諾退款成功後才開始 Memory，也不以 Memory 完成作退款成功證據。
- **M06-R05**：Memory worker 表達 scheduled/running/retrying/completed/skipped/failed 與 attempt；submit 是冪等 Provider。transport retry 用有界退避；永久錯誤記 terminal/DLQ。SKIP 是明確結果，不當 completed candidate。Memory 範圍止於 Candidate 提交，不含人工治理。
- **M06-R06**：Activity emission 用 event_id、case_ref、scope、run_id、job_id、node、operation_id、parent_operation_id、attempt_id、occurred_at、typed payload；API 加 seq。node/model/tool lifecycle 是 STARTED/COMPLETED/PAUSED/FAILED、duration_ms 與安全錯誤碼；開始必在實際操作前送出。
- **M06-R07**：NodeSummary 只選 allowlisted ActivityFacts；Memory observation 的 query／經驗文字在 activity 中被省略，完整 Memory 從專用 case projection 讀。禁止 raw prompt/state/args/SQL/exceptions/PII/credentials/URL/CoT。regex redaction 是有限防護，不宣稱任意自然語言 PII 完全移除。
- **M06-R08**：每個完成 node summary 在 API 同 transaction 建唯一 narration outbox。API source_event_id 驗證 node/case/run/scope/job/operation/attempt/parent 全等；相同來源最多接受一份結果。narration 只輸入 node+facts，不讀 raw memory／prompt 或整案。
- **M06-R09**：narration 獨立 model operation_id，parent 指 source operation；payload.name=ACTIVITY_NARRATION。1–2 句繁中，最多 600 字元；next_node 是預定下一步，不是已執行。timeout 預設20s、concurrency2（允許1..16）；失敗回 UNAVAILABLE，不回模板。
- **M06-R10**：offline demo 明確注入無 narration model；消費 job、cache disabled result、publish、ACK；不呼叫 generate、不發 model STARTED/FAILED；error_code=NARRATION_DISABLED_OFFLINE_DEMO、text=null。真模型 timeout/invalid output 與此不同。
- **M06-R11**：Activity API 依 producer ID 去重、case row lock 配 seq，summary+outbox 同交易後 ACK。publisher queue 1024 可配置；滿時記 failed/log trace incomplete，不阻斷業務。進程崩潰前未進 Redis 的記憶體 queue 可能遺失，不能宣稱完整 durable tracing。
- **M06-R12**：activities 分頁 seq 升序，next_cursor=最後 seq（空維持原值）、has_more；SSE Last-Event-ID 優先於 after_seq，15s heartbeat、250ms poll，terminal 不關閉。case SSE terminal 關閉。late narration 依 source_event_id 顯示，不按 arrival time 改寫執行順序。

## 正常／失敗流程

block Provider 時已可收到 tool STARTED，result 只在返回後；interrupt 為 PAUSED。Redis replay 後 API 不重複 event 或 narration jobs。narration result cache 重送不再 generate；timeout 的底層同步模型呼叫未必可被取消，worker 需維持 slot／lease 管控，不用超時造無限 thread。

## 驗收條件

C15～C18、C30～C36：start-before-result、concurrent case隔離、attempt/source correlation、API transaction→ACK、queue故障、pagination/reconnect、terminal後background/narration、offline disabled 與真模型fail、敏感資料不進 observation。
