# M02：Agent Runtime

## 責任與非責任

純 LangGraph library。state、node routing、bounded loops、結構輸出與 handoff assembly；不實際退款、不寫 API case DB、不組 Redis。Provider 是 Python 程式直接呼叫，不宣稱模型自主 tool selection。

## 依賴

M01、StructuredOutputModel、六個 Provider（context、policy、verification、human、memory、evidence）、Clock、StableIdFactory、checkpoint saver、observer。同步 Provider/model 邊界在 Agent Service 工作執行緒跑，不堵塞 HTTP/SSE。

## 輸入輸出

Start 指定 case_ref、thread_id、可信 order_ref、initial_turn；resume 重用相同 thread，只接受當前 interrupt variant。返回完成／暫停／escalation 及 typed observations。state 最少包含：conversation_turns、normalized_intent、claimed_line_item_ids、case_context、order_snapshot、policy_bundle、evidence_bundle/assessment、memory query/hits/status、current_handoff、proposal_history、review_history、pending_review_result、verification_feedback、revision_events、review_gate/routing_reason、三種 pending request／human result、resolution、memory_distillation_input、escalation、五個 counters、_route。全部可 checkpoint 序列化，不保存 model/client/session 物件。

## 資料與演算法

| 實際 node | 呼叫與輸出 | 下一步／失敗 |
| --- | --- | --- |
| parse_request | INTAKE；可信 order 綁定、品項對照 | 完整 → load context 或 policy；不完整 → request_clarification；錯誤 → terminate |
| request_clarification | interrupt CLARIFICATION；USER turn resume | parse_request；拒絕重複 turn ID／錯 variant |
| load_case_context | CaseContextProvider.load_case_context | 未解品項可重新 parse；完成 → retrieve_policy |
| retrieve_policy | PolicyProvider.retrieve_policy | OK → prepare_memory_query；NOT_FOUND／AMBIGUOUS → terminate |
| prepare_memory_query | EvidenceProvider.resolve 所有未處理 initial artifacts；MEMORY_QUERY_SUMMARY | 成功 → retrieve_memory；summary 錯誤清空 Memory → assess；附件錯誤 → terminate |
| retrieve_memory | OperationalMemoryStore.query_approved | 保留 cosine 順序，replace hits → assess_case；不可用亦繼續 |
| assess_case | ASSESS，Resolver prompt＋assessment schema | insufficient → request_evidence；足夠 → propose_decision |
| request_evidence | interrupt EVIDENCE_REQUEST；resolve 補件 refs | 合併 evidence、prepare_memory_query → 重查重評；錯誤 → terminate |
| propose_decision | PROPOSE_OR_REVISE；DRAFT／REQUEST_EVIDENCE／CONFLICT | DRAFT 由 Python 組金額與 handoff → verification；request → 補件；conflict → terminate |
| external_verification | VerificationProvider.verify | PASS → reviewer；FAIL budget 內 → propose；UNAVAILABLE／超限 → terminate |
| reviewer | REVIEW；APPROVE 後 evaluate_review_gate | PASS/NOT_APPLICABLE → emit；HUMAN_REQUIRED → human；REVISE → record 或超限 human |
| record_revision_event | Python 記 review、before handoff、round+1 | propose_decision |
| await_human_review | submit_for_review，持久化 ref；fetch_result | 未完成 HUMAN_REVIEW interrupt／自循環；有結果 → emit；不回 Reviewer |
| emit_resolution_handoff | Python 組最終決定與授權引用 | enqueue_memory_distillation |
| enqueue_memory_distillation | 構造符合資格的 distillation input | END；真正 LLM job 在 service 背景 |
| terminate_automation | ManualEscalationHandoff | END；API terminal ESCALATED，非人審 interrupt |

- **M02-R01**：budgets 為 [固定設定](assets/budgets.json)：clarification=2、evidence=2、verification=2、revision=3、propose=6、graph recursion=100。計數由 graph 管理，不接受模型指定。revision 是允許三次修正：Reviewer round 0、1、2 REVISE 可修正，round 3 仍 REVISE 才轉人審，最多四次複核。verification FAIL 重提不增加 review round。
- **M02-R02**：既有 review feedback 跨補件 interrupt 保留，不能藉重新 assess 遺失異議。成功新提案後才清 pending feedback。帶異議時不得逐字重交未改變的 decision/rationale。
- **M02-R03**：每次 handoff 身分含 logical proposal attempt；不同重提案不可重用 ID。StableIdFactory 為 UUIDv5 NAMESPACE_URL，name=`return-agent:{kind}:{冒號串接parts}`，wire=`KIND-{hex}`；同一 logical retry 得相同 ID。
- **M02-R04**：只將驗證後 proposal 放入 history；dossier 從 latest handoff 加 revision event 的 before refs 選「實際被 Reviewer 看過」的 proposals，排除 verification-only attempts。
- **M02-R05**：checkpointer 使用受限 allowlist 的 typed serialization，不能反序列化任意 class。相同 case thread 跨進程 resume，不應使用 memory-only saver 冒充 durable。interrupt emit PAUSED，恢復可重新執行 node 前段副作用，因此 submit 與 ID 必須冪等。
- **M02-R06**：policy／order／evidence／model shape、claim、verification contract 錯誤 fail closed；memory optional 的兩條不可用路徑例外，清空舊 hits。gate 不消耗 revision budget、不產生虛構 reviewer 異議。

## 正常／失敗流程

正常例：A 附 closeup → initial resolve → query → insufficient → 補三 refs → 重摘要 → approve → verification PASS → reviewer APPROVE → gate PASS → resolution。模型輸出不合法直接 CONTRACT_VIOLATION；沒有隱式「再問模型直到 JSON 看起來對」。Resolver 可以明確回 CONFLICT，轉 CONFLICTING_REVISIONS。

## 驗收條件

C01～C09、C14：所有 16 nodes 有確定性測試；interrupt 後序列化／重新建立 runtime／resume 能繼續；重試與模型 task 的 operation attempts 可分辨。輸入組裝及所有 prompt 必須依 [模型附錄](model-tasks.md)，Reviewer 不得看 Memory。
