# 模型任務、prompts 與輸入組裝

每次 model generate 是程式明確 task，不是讓模型自行選工具。共 **7 個 task、6 份 system prompt**，ASSESS 與 PROPOSE_OR_REVISE 共用 Resolver。

| task | system prompt／版本 | structured output | input 組裝（非全部 state） |
| --- | --- | --- | --- |
| INTAKE | [intake](assets/prompts/intake.txt) intake:1.1 | [IntakeResult](assets/schemas/model/IntakeResult.schema.json) | prompt_version、trusted_order_ref、conversation_turns、existing_intent、order_line_items（未 load 時 null；有資料只提供識別／title/category/quantity） |
| MEMORY_QUERY_SUMMARY | [memory-query](assets/prompts/memory-query.txt) memory-query:1.0 | [MemoryQuerySummary](assets/schemas/model/MemoryQuerySummary.schema.json) | prompt_version、reason_summary作reason、reason_code、market、case_opened_at、delivered_at、claimed_items[{title,category}]、evidence[{subject,type,source,summary}]；先 resolve 未處理附件 |
| ASSESS | [resolver](assets/prompts/resolver.txt) resolver:1.1 | [EvidenceAssessment](assets/schemas/model/EvidenceAssessment.schema.json) | 下述 Resolver input；evidence_assessment 首次 null，補件可帶前輪 assessment，review_feedback跨interrupt保留 |
| PROPOSE_OR_REVISE | 同 Resolver | [ResolverOutput](assets/schemas/model/ResolverOutput.schema.json) | 同 Resolver input，但已具 assessment及可能 verification/review feedback；模型無 amount/currency output |
| REVIEW | [reviewer](assets/prompts/reviewer.txt) reviewer:2.1 | [ReviewResult](assets/schemas/model/ReviewResult.schema.json) | prompt_version、reviewed_at_utc、case_context、完整 order_snapshot、policy_bundle、registry/version、expected_claim_subject_pairs、proposed_decision_handoff（含 evidence bundle及簡短 rationale）；不加 assessment/Memory |
| MEMORY_DISTILL | [distiller](assets/prompts/memory-distiller.txt) memory-distiller:2.0 | [MemoryDistillationOutput](assets/schemas/agent/MemoryDistillationOutput.schema.json) | distillation_input；allowed_scope:{market,reason_codes,claim_ids,categories} 由可信來源推導 |
| ACTIVITY_NARRATION | [inline narration](assets/prompts/narration.txt)，原程式沒有版本常數，資產以baseline/hash定位 | [NarrationText](assets/schemas/model/NarrationText.schema.json) | 僅 node＋source NodeSummary.facts；不帶 summary.memory_retrieval、gate細節、raw prompt或整案 |

Resolver input 全欄位：prompt_version、normalized_intent、claimed_line_item_ids、case_context、order_facts、policy_bundle、claim_registry_version、claim_registry、expected_claim_subject_pairs、evidence_bundle、evidence_assessment、operational_memory、verification_feedback、review_feedback。order_facts 保留 order ref／snapshot version／capture／delivered、line ID/SKU/category/title/quantity，剔除 amount/currency/max/already refunded。registry 只選本 bundle required claims，pair 清單由 M01-R03 生成，不由模型推導。

## Adapter 線路

SystemMessage=上述逐字 prompt；HumanMessage 的 JSON 為 `{task_mode: TASK, input: assembled_payload}`，`ensure_ascii=false`、compact separators。include_schema_in_prompt=true 時另加 required_output_schema，支援僅把 schema 当 grammar 的相容服務。使用 `with_structured_output(method=json_schema)`；輸出根若非 object，包成 `{output: UNION}`，required output、additionalProperties=false，將 `$defs` 提至 envelope 根；解包後仍本地 TypeAdapter.validate_python。

OpenAI-compatible Chat 或 Responses API adapter：模型名、endpoint、key、timeout、temperature、extra_body 由 profile組合。預設 timeout 180s/max_retries0/temperature0；特定模型 profile可覆寫，以 environment inventory與profile附錄為準。Responses 回傳 parsed 或 raw function-call JSON 時要明確解析、沒有有效 structured output就錯誤，不直接當任意字串。

現有真模型profile：demo-qwen／integrated-qwen 使用 temperature=0、include_schema_in_prompt=true、Chat API、streaming=true、extra_body.chat_template_kwargs.enable_thinking=false；integrated-compass 使用 Responses API、temperature不傳、include_schema_in_prompt=false、streaming=true、無extra_body。兩者 timeout180/max_retries0；配置model名稱不綁特定私人endpoint。demo-qwen仍是fixture Providers／memory journal，不能當integrated驗收。

Python 會覆寫 graph-owned registry/prompt timestamps/ID、金額、refs，然後做 M01 semantic validators；不能以 Pydantic model_copy 跳過最終安全驗證。Memory candidate ID/source/status/version 和 allowed scope由程式控制。Narration output 還會限制不應虛構「已進入／轉交／送交／啟動」下一節點；只能述已發生 facts，失敗 UNAVAILABLE。

## 安全／可重建界線

原 prompt 與 schemas 已自包含，不需要 import 原 code。模型 arbitrary text不是可信規則，使用者/evidence/Memory 指令不得覆蓋系統規則。合成 fixture與 opaque refs可能進業務 prompt；Activity 另走 allowlist，不能用全 prompt copy 做 tracing。LLM 不參與 gate／refund authority；narration 不參與任何業務分支。
