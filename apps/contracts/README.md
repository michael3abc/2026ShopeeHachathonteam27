# Shared Contracts

Single source of truth for cross-component Pydantic DTOs, Provider Protocols, deterministic contract adapters, and generated JSON Schema. Python consumers import `return_agent_contracts`; Web and non-Python consumers use the versioned schemas in this app.

JSON Schema validates one wire payload's scalar constraints, required fields, and discriminated unions. Cross-object rules involving Policy, Order, evidence findings, and handoffs are semantic validation and must be enforced with `return_agent_contracts.validation` by the Python boundary adapter. Money is a Python `Decimal` and a JSON decimal string; UTC wire timestamps must end in `Z` or `+00:00`.

- `schemas/agent/v1/`: Agent invocation/resume/result、Provider transport 與 outbound handoff payloads。
- `schemas/ui/v1/`: Backend/UI projection and resume payloads.

API 與 Agent Service 的 Redis boundary 使用
`return_agent_contracts.service`。Command 與 event 都是 versioned discriminated
union；stream entry 只放一個 `body` JSON 欄位。Transport owner 不得把它改成
未定型 dictionary。

同一 module 也定義非同步 Operational Memory 的 job/completed/failed/DLQ DTO。
Memory 使用 v2 schema／streams／ID namespace（主案件 commands/events 仍為 v1）。`LearningTrace` 是 typed、allowlisted、有界歷程；輸出含回顧、學習判定與至多一則經驗。`source_event_refs` 取代 correction-only 欄位，核准後仍保留適用限制與不可推論事項。JSON Schema 目錄保持既有路徑，Memory DTO 的版本以其 schema_version 與 stream 為準。

`LearningTrace.dialogue_version=learning-dialogue:1` 新增逐事件、去識別化對話及 turn/request 追溯；未驗證主張與 Agent 要求分別標記。`EvidenceResume.turn` 可選但附件必須一致；缺失可裁決、不可假造完整學習輸入。主 commands 仍為 v1，嚴格 DTO consumer 必須與 producer 協調更新。
`MemoryDistillationCompletedEvent` 以 schema-visible union 保證 candidate 必有
`submission_ref`、`SKIP` 必為 `null`；跨物件的 case/trace 一致性則仍由 Pydantic
semantic validator 強制。

API 與 Runtime 之間的 Python boundary 使用
`return_agent_contracts.runtime`。其中 `AgentRunResult` 與 interrupt/resume
payload 都是 discriminated union；`NodeExecutionObservation` 是不含 LangGraph
state/input/output 的 framework-neutral lifecycle DTO。不得以未定型 `dict` 取代。

Do not edit generated schemas by hand. Regenerate them from the repository root with `make contracts`.

獨立活動契約在 return_agent_contracts.activity，framework-neutral observer/span 在
activity_observer。ActivityEmission/NarrationJob 為 Redis DTO；ActivityEvent/ActivityPage
為 API／Web DTO。只允許 typed fields，不輸出 raw arguments、state、prompt、exception
或 hidden reasoning；NodeSummary 的 Memory 文字會標記 omitted。generate-contracts.mjs
同步產生 activity-event.ts／activity-page.ts，不改 UI 行為。規格見
[Activity wire contract](../../docs/spec/02-agent-contracts.md#activity-wire-contract)。

Reviewer output 仍為 APPROVE / REVISE。ResolutionHandoff 改用 REVIEWER_APPROVE 與 review_result；Human Review 傳遞最後的 RevisedReviewResult，並顯示程式產生的 REVISION_BUDGET_EXCEEDED。Risk transport 與 UI risk_route 欄位已移除，所有 producer / consumer 必須一起更新。

圖片上傳與對話查詢 DTO 位於 `attachments.py`，包含 `AttachmentView`、`UploadOptions`、`ConversationPage` 及圖片讀取 Protocol；HTTP 圖片 adapter 位於 `image_adapter.py`。圖片 bytes 不屬於案件、事件或 handoff DTO。

## 申請理解展示

Activity 的可選 `NodeSummary.intent_display` 使用共享 IntentDisplay，只保存允許的結構化理解欄位；舊資料無需 migration。
