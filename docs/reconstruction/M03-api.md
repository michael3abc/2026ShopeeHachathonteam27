# M03：Case API／持久化

## 責任與非責任

FastAPI BFF、canonical case lifecycle、public DTO projection、Provider internal endpoints、DB 交易與退款執行協調。API 不載入或執行 LangGraph；graph checkpoint 不存在 case DB。

## 依賴

M01、M04/M05、SQLAlchemy／psycopg、Redis bridge。資料表完整型別與約束在 [資料附錄](data.md)／[fresh SQL](assets/db/api-fresh.sql)。

## 輸入輸出

公開端點為 create/get/messages/review/events/activities；沒有「列出全部案件」、完整 transcript replay 或 Memory governance HTTP UI。內部以 `{params: ...}` 請求／`{result: ...}` 回應（包含 schema_version 等欄位時以相應 schema 為準），詳 [介面附錄](interfaces.md) 與完整 OpenAPI。public demo identities 不是身份驗證。

## 資料與演算法

- **M03-R01**：初始 OBSERVING；可到 AWAITING_CLARIFICATION、AWAITING_EVIDENCE、AWAITING_HUMAN_REVIEW、EXECUTING、ESCALATED。三種 awaiting 可回 OBSERVING 或 ESCALATED；human 另可 EXECUTING。EXECUTING → RESOLVED／ESCALATED；terminal 無 outgoing。完整 machine-readable adjacency 在 [case-transitions](assets/case-transitions.json)。
- **M03-R02**：create 產生新 case/thread 與 initial user turn，START outbox 與 case 同 transaction commit。沒有 public Idempotency-Key；重送 create 會開新案，不能聲稱 exactly once。
- **M03-R03**：messages 鎖 case；只有 clarification/evidence awaiting 可接受。evidence resume 至少一 artifact；存 turn、轉 OBSERVING、state_change、RESUME outbox 同 transaction。concurrent 第二次提交應 409，不重用已消耗的 interrupt。
- **M03-R04**：human review 鎖 case，必須 awaiting 且 handoff_id 是 pending 案件。裁決紀錄、status、case event、RESUME 同 transaction；graph 只 fetch 已存結果，不能信任前端回傳整個 HumanReviewResult。
- **M03-R05**：case_events 每案 seq≥1 unique。所有 writer 先鎖 cases row，再 max(seq)+1。user_turn 和 agent_event 共用 case 序號，但 `/events` 只回 agent_event，所以 SSE 序號可以有洞；不要把洞當 transport loss。
- **M03-R06**：service event 以 event_id＋payload_hash dedup，command event_index 應連續；超前事件保留等待，不錯序改 case。poison event 保存 restricted rejection record 後 ACK；不能把完整 exception/raw body 推給 UI。
- **M03-R07**：HumanReviewDossier 不可變地綁完整 trace 與原申請範圍；API 重算 routing/gate/hash、驗證所有 proposal 版本及 revision chain。人工 EDIT 不得突破 order/Policy/金額限制，但不把最後 Reviewer 的支持範圍當唯一授權 scope。
- **M03-R08**：GET CaseDetail 重建 pending request、人審 dossier/result、latest memory retrieval、final result，不暴露 backend thread、raw checkpoints。終態事件與退款結果需一致；不能在 API 接到 ResolutionHandoff 時立刻標退款成功。

## 正常／失敗流程

內部 service Bearer 缺配置 503、錯 credential 401；context/evidence/review ref 不存在 404；輸入 422；非法狀態／同 ID 不同 payload 409（不同 provider 未統一映射例外的現況見 limitations）。退款 unavailable 保留可恢復狀態，不重送一筆全新付款。新案若用 unconfigured API profile，沒有 assembled executor，不保證自動從 EXECUTING 收斂。

## 驗收條件

C07～C13、C15～C18：跨 HTTP、Redis 重送不重複改狀態；同 handoff 改 dossier／過時裁決拒絕。兩個 awaiting 人審入口都可 resume，terminate_automation 不可；refresh 取得持久化 dossier 與結案。
