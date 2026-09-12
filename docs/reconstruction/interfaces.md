# 介面附錄：HTTP／Provider／Redis／SSE

所有 request/response 欄位與巢狀結構在 [OpenAPI](assets/openapi.json)、[schema catalog](assets/contract-catalog.json) 與 [展開欄位字典](reference-fields.md)。可離線解析，不需原 source 或 online swagger。JSON Schema 只驗形狀；跨物件 M01-R03～R11 與以下授權不可省略。

## Public HTTP

public 為內部 Demo 未認證 surface；沒有真正角色／租戶隔離。JSON error 通常 `{detail: string}`，FastAPI 422 為 detail array。schema 未列出的未捕捉 exception 可能是 500；不能推論每項 service-domain error 都已統一映射。

| method/path | request → response | 驗證／錯誤／重送 |
| --- | --- | --- |
| GET /health | 無 → {status:ok} | process-only，不查全部依賴 |
| POST /cases | CreateCaseRequest: order_ref,user_ref,initial_message,attached_artifact_refs → 201 {case_ref} | shape422；每次新 case，不支援 client idempotency key；case+START outbox 同 commit |
| GET /cases/{case_ref} | path ref → CaseDetail: status、events/requests、human_review/result、memory_retrieval、final resolution等（完整欄位見schema） | 404 unknown；只讀可重試，非完整對話 |
| POST /cases/{case_ref}/messages | SendMessageRequest: message,attached_artifact_refs → CaseDetail | 404 unknown；422 missing artifact for evidence；409 非等待／重複提交；clarification帶USER turn，evidence只送refs進resume |
| POST /cases/{case_ref}/review | ReviewDecision union: handoff_id,decision,review_note,reviewer_id,generalizable?；EDIT須 corrected_decision/correction_reason_code → CaseDetail | 409非awaiting／handoff過時／不合法裁決、404 case；非客戶端提供 authoritative result；裁決+RESUME同commit |
| GET /cases/{case_ref}/events | Last-Event-ID? → text/event-stream | 404 case，400無效cursor；case seq，不接受 activity seq；terminal drain後close |
| GET /cases/{case_ref}/activities | after_seq≥0=0、limit1..500=100 → {events,next_cursor,has_more} | 404／422；獨立activity序號、可重讀 |
| GET /cases/{case_ref}/activities/stream | Last-Event-ID?、after_seq≥0=0 → text/event-stream | header優先、400非法header、404case；terminal不關閉、idle heartbeat |

Agent Service 對外僅 health：`GET /health/live` 與 `GET /health/ready`；ready 不代表业务全部完成。重建需保留 worker/broker/journal readiness，不把僅HTTP 200当 E2E 成功。

FastAPI 預設另提供 `/openapi.json`、`/docs`、`/redoc` 等框架文件端點，不是案件業務介面。OpenAPI 不完整描述 SSE frames／terminal-close；以本附錄及 typed AgentEvent／ActivityEvent 為準。

## Internal HTTP／Provider

以下每項 POST，都需 `Authorization: Bearer <internal-service-token>`。未配置 token=503，錯 token=401，Provider 未組合=503；shape422。Provider wire 請求頂層為 `method`（固定 Provider.method 字串）與 `params`，回應為 `result`；不是 Redis 的 schema_version envelope。HTTP adapter 只做 typed serialization/validation、timeout與授權header，不把所有失敗改成空 result。

| path / Provider method | params 與 result | 語意與錯誤 |
| --- | --- | --- |
| /internal/v1/case-context / load_case_context | case_ref → CaseContextLoadResult(context,snapshot) | 只讀重試safe；綁可信case/order；404找不到 |
| /internal/v1/policy / retrieve_policy | case_context,order_snapshot,reason_code,claimed_line_item_ids → PolicyBundle | effective/scope版本 hard-filter；NOT_FOUND/AMBIGUOUS是result，不是成功空OK；保存bundle |
| /internal/v1/verification / verify | handoff → VerificationResult | samehandoff/hash安全重送；409內容衝突；503persistence不可用；claims/金額/Policy限制M04 |
| /internal/v1/evidence/resolve / resolve | artifact_ref → EvidenceItem | metadata lookup，404未知；不抓任意URL、不處理upload |
| /internal/v1/memory/query / query_approved | query_summary,market,reason_code,required_claim_ids,categories,policy_versions,claim_registry_major,top_k≤3 → MemorySearchHit[] | hard-filter+cosine；empty是真空，exception為不可用；不改confidence排序 |
| /internal/v1/memory/candidates / submit_candidate | candidate → opaque submission_ref | id+canonical payload hash冪等；embedding完成再原子寫入；相同ID不同內容拒絕 |
| /internal/v1/human-reviews / submit_for_review | handoff,review,dossier → review_ref | 驗兩合法入口與全部歷史，immutable持久化；相同ID相同內容回原ref，異內容拒絕 |
| /internal/v1/human-reviews/result / fetch_result | review_ref → HumanReviewResult或null | null表示仍待人；404未知ref，不當null；已完成再讀不得更改結果 |

另外兩種 trusted Provider **不是 public 或 graph HTTP tool**：

- RefundExecutionProvider.execute(ExecuteRefundRequest{resolution_handoff}) → RefundExecutionRecord；get_status(execution_ref) → record/null。執行授權與冪等／reservation見 M04；尚未有 terminal結果時可能 unavailable，而非假 SUCCEEDED。
- RefundApplicationProvider.apply(ApplyRefundRequest{execution_ref,resolution_handoff}) → APPLIED{order_ref,amount,currency,refund_ref,applied_at} 或 REJECTED{reason_codes,rejected_at}。外部適配必須按 execution_ref冪等；不允許任意client直呼。

[Provider method 完整參數清單](assets/providers.json) 加上 schemas即可跨語言實作。Memory governance、ingest/reembed/backfill 是 trusted維運操作，不新增未存在的HTTP endpoint。

## Redis 訊息與可靠性

| stream | producer → consumer | body schema／結果 |
| --- | --- | --- |
| return-agent.commands.v1 | API outbox → Agent group return-agent-workers-v1 | AgentCommand: schema_version,command_type,command_id,case_ref,thread_id,issued_at,payload；START(order_ref,initial_turn)，RESUME(resume union) |
| return-agent.events.v1 | Agent → API bridge，Memory enqueue獨立group | AgentServiceEvent: event_type,event_id,command_id,case_ref,thread_id,event_index,occurred_at及variant payload；index每command排序 |
| return-agent.commands.dlq.v1 | Agent → operator | AgentCommandDeadLetter，poison command診斷，不當case成功 |
| return-agent.memory-jobs.v1 | enqueue worker → memory worker group | MemoryDistillationJob: job_id、source command/event、case、issued_at及input；同logical job replay |
| return-agent.memory-events.v1 | memory worker → observer/operator | MemoryServiceEvent completed(output含SKIP/candidate)/failed；背景不覆蓋退款status |
| return-agent.memory-jobs.dlq.v1 | memory worker → operator | MemoryJobDeadLetter，明確失敗 |
| return-agent.activities.v1 | Agent/runtime observer、API refund → activity-api-v1 | ActivityEmission；API配seq成ActivityEvent，persist/outbox成功後ACK |
| return-agent.narrations.v1 | API narration outbox → activity-narrator-v1 | NarrationJob(job_id,source emission)，source僅safe facts |

`return-agent.narrations.v1.rejected` 是無效job診斷（message_id/code），不是 NarrationJob。consumer groups／其餘版本常數以 [redis constants](assets/redis-constants.json) 為準。contract JSON unions覆蓋全部variants，切勿以表內摘要欄位替代完整schema。

投遞語意 at-least-once：API outbox lease token避免錯owner mark；Agent journal＋checkpoint避免重跑；Redis publish和DB提交非同一transaction，可重送。API依 producer ID/hash/index驗證重送，poison要持久化拒絕證據才ACK。Activity queue滿／進程崩潰可能缺trace，業務仍繼續；不是每一觀察事件都有transactional outbox。

## SSE 交接

```text
id: 3
event: activity
data: <ActivityEvent JSON；event_id不等於seq>

: keep-alive

```

合法完整 JSON與實際SSE frames見 [sample](examples/activity.sse)／[typed fixture](examples/semantic-fixtures.json)。`type` 在 payload discriminator，生命週期用 operation_id配對；narration source_event_id找原summary，name區分模型工作；attempt_id標識重新執行。頁面 refresh先GET activities至has_more=false，再用最後cursor連stream，窗口中產生事件會被stream補回。重連 Last-Event-ID=最後已處理 seq，header優先；收到重複seq丟棄，別把case游標傳來。

case `/events` 的 event 名為 body.type、terminal關閉；Activity event 名固定activity、terminal不關閉。NodeSummary.next_node只代表選定路由，narration晚到也不證明下一步已做。offline NARRATION_DISABLED_OFFLINE_DEMO只代表沒啟用解說，不代表node失敗。
