"""Reviewed narrative and relationships; all references resolve at the baseline SHA."""
from __future__ import annotations

import ast
from typing import Any, Callable


def create_content(ref: Callable, read: Callable, graph: dict, schema: dict) -> dict[str, Any]:
    api = "apps/api/src/return_agent/"
    agent = "apps/agent_service/src/return_agent_service/"
    runtime = "packages/agent_runtime/src/return_agent_runtime/"
    web = "apps/web/src/"
    contracts = "apps/contracts/src/return_agent_contracts/"
    refs = {
        "api": ref(api + "app.py", "create_case"),
        "messages": ref(api + "app.py", "send_message"),
        "review": ref(api + "app.py", "complete_human_review"),
        "bridge": ref(api + "agent_bridge.py"),
        "outbox": ref(api + "db/agent_bridge.py", "AgentCommandOutboxRecord"),
        "compose": ref(agent + "composition.py", "compose_integrated_service"),
        "worker": ref(agent + "worker.py", "AgentWorker"),
        "journal": ref(agent + "journal.py", "PostgresCommandJournal"),
        "broker": ref(agent + "broker.py", "RedisStreamBroker"),
        "runtime": ref(runtime + "runtime.py", "aresume"),
        "case": ref(api + "db/case.py", "CaseRecord"),
        "policy": ref(api + "capabilities/policy.py", "SqlAlchemyPolicyProvider"),
        "memory": ref(api + "capabilities/operational_memory.py", "SqlAlchemyOperationalMemoryStore"),
        "governance": ref(api + "capabilities/operational_memory.py", "OperationalMemoryGovernanceService"),
        "memory_worker": ref(agent + "memory_worker.py", "MemoryWorker"),
        "enqueue": ref(agent + "memory_enqueue_worker.py", "MemoryEnqueueWorker"),
        "replay": ref(agent + "memory_replay.py", "SqlAlchemyMemoryReplayStore"),
        "refund": ref(api + "capabilities/refund.py"),
        "safety": ref(api + "capabilities/safety.py"),
        "human": ref(api + "capabilities/human_review.py"),
        "evidence": ref(api + "capabilities/evidence.py"),
        "web": ref(web + "components/case-workspace.tsx", "export function CaseWorkspace"),
        "ui": ref(web + "components/case-workspace.tsx", "function ConversationPanel"),
        "review_ui": ref(web + "components/case-workspace.tsx", "function ReviewerPanel"),
        "client": ref(web + "lib/api.ts"),
        "progress": ref(web + "lib/graph-progress.mjs", "export function graphProgress"),
        "activity": ref(web + "lib/use-case-activities.ts", "export function useCaseActivities"),
        "activities": ref(api + "activities.py", "ActivityRepository"),
        "activity_bridge": ref(api + "activity_bridge.py"),
        "status": ref(contracts + "ui.py", "CaseStatus"),
        "commands": ref(contracts + "service.py", "AgentStartCommand"),
        "streams": ref(contracts + "service.py", "AGENT_COMMAND_STREAM"),
        "activity_streams": ref(contracts + "activity.py", "ACTIVITY_STREAM"),
        "gate": ref(contracts + "review_gates.py", "evaluate_review_gate"),
        "compose_file": ref("docker-compose.yml"),
        "next": ref("apps/web/next.config.ts"),
        "readme": ref("README.md"),
        "spec": ref("docs/spec/README.md"),
        "demo": ref("data/demo-case-study/README.md"),
        "test_happy": ref("packages/agent_runtime/tests/test_graph_workflow.py", "test_happy_path_emits_graph_derived_resolution"),
        "test_resume": ref("packages/agent_runtime/tests/test_interrupt_resume.py", "test_evidence_interrupt_resolves_refs_and_resumes_assessment"),
        "test_human": ref("packages/agent_runtime/tests/test_interrupt_resume.py", "test_human_review_submit_once_and_poll_until_result"),
        "test_failure": ref("packages/agent_runtime/tests/test_revision_and_failures.py", "test_policy_status_and_provider_exceptions_fail_closed"),
        "test_memory": ref("packages/agent_runtime/tests/test_revision_and_failures.py", "test_closed_revision_prepares_and_distills_memory_candidate"),
        "test_outbox": ref("apps/api/tests/test_agent_bridge.py", "test_case_and_command_outbox_share_one_transaction"),
        "test_idempotent": ref("apps/api/tests/test_agent_bridge.py", "test_projector_is_idempotent_for_duplicate_events"),
    }
    entities, edges = [], []

    def entity(id, title, type, summary, owns, excludes, inputs, outputs, keys, **extra):
        item = {"id": id, "title": title, "type": type, "summary": summary,
                "owns": owns, "excludes": excludes, "inputs": inputs, "outputs": outputs,
                "why": extra.pop("why", summary), "failure": extra.pop("failure", "依呼叫端契約處理；展開來源查看實際分支。"),
                "refs": [refs.get(k, k) for k in keys], "evidence": "Source verified", **extra}
        entities.append(item)
        return item

    def edge(a, b, kind, label, keys, **extra):
        edges.append({"id": f"{kind}:{a}:{b}", "from": a, "to": b, "kind": kind,
                      "label": label, "refs": [refs.get(k, k) for k in keys], "evidence": "Source verified", **extra})

    entity("buyer", "買家", "actor", "提出退貨退款申請，回應澄清與補件。", "申請內容與補充資料", "政策認定、模型執行與金流", "商品問題", "UserTurn / artifact_refs", ["client", "ui"])
    entity("human", "人工審核者", "actor", "在待審案件提出 APPROVE、EDIT 或 REJECT。", "經驗判斷與人工結果", "任意改寫 Graph state", "Human Review dossier", "ReviewDecision", ["review", "review_ui"], failure="非待審案件或不合法結果由 API 拒絕；基準 UI 為 demo 身分。")
    entity("web", "Frontend", "service", "Next.js 案件介面；呈現狀態、對話、審核與活動進度。", "UI selection、連線與回放狀態", "canonical case status、checkpoint、退款授權", "CaseDetail / SSE / ActivityPage", "REST 使用者操作", ["web", "client", "next"], failure="讀取錯誤顯示錯誤；SSE 重連；activity 不可用不阻擋案件。")
    entity("api", "Case API / BFF", "service", "保存案件狀態，驗證操作，排入 Agent command 並投影回傳事件。", "案件 lifecycle、業務資料與執行授權", "模型內部推理與 Graph counters", "REST / AgentServiceEvent", "CaseDetail / SSE / AgentCommand", ["api", "bridge", "case"], failure="不合法狀態轉換回 409；事件依序與去重投影。")
    entity("agent", "Agent Service", "service", "組裝 Redis worker、LangGraph、HTTP Providers 與持久化。", "執行組裝、command 處理與 Graph persistence", "Backend canonical case status", "AgentStartCommand / AgentResumeCommand", "AgentServiceEvent / activity", ["compose", "worker"], failure="command journal 管理 lease；不可恢复的 runtime error 發 RUN_FAILED，並記錄失敗。")
    entity("worker", "AgentWorker", "worker", "消費 START / RESUME command，呼叫 runtime 並發送事件。", "command claim、event_index 與 ACK 時機", "自行決定退款 eligibility", "Redis stream message", "NODE_OBSERVED / INTERRUPTED / RESOLVED / ESCALATED", ["worker", "journal", "streams"])
    entity("runtime", "LangGraph Runtime", "runtime", "純 Python Agent library；以 typed state 執行提案、審核與暫停。", "AgentState、routing、loop counters", "canonical business status、退款 mutation", "initial turn / validated resume payload", "interrupt / ResolutionHandoff / ManualEscalationHandoff", [graph["source"], "runtime", "spec"], failure="有界 loop 與明確 fail-closed 路徑；Memory optional 路徑例外可繼續。")
    entity("api_db", "API PostgreSQL", "database", "案件與業務能力的 canonical persistence；含 Policy / Memory vectors。", "cases、policy、evidence、human review、refund、outbox、activity", "LangGraph working state", "API transactions", "業務資料與可重播事件", ["case", "policy", "memory", "outbox", "activities"])
    entity("agent_db", "Agent PostgreSQL", "database", "Agent execution 的獨立持久化資料庫。", "checkpoint、agent_command_journal、Memory replay", "API 的 cases / policy tables", "AsyncPostgresSaver / journal / replay store", "可恢復 execution 與 command 處理狀態", ["compose", "journal", "replay"], failure="不可用會影響執行／恢復；不會改用 API DB 作隱藏替代。")
    entity("redis", "Redis Streams", "queue", "透過多個 stream 與 consumer group 連接 API、Agent 與背景工作。", "訊息傳輸與 consumer pending 狀態", "取代 business DB 或 Graph checkpoint", "commands / events / memory jobs / activities", "consumer messages / ACK / reclaim", ["broker", "streams", "activity_streams", "compose_file"], failure="at-least-once delivery，需要各層去重；不能宣稱 exactly-once。")
    entity("providers", "HTTP Providers", "module", "Runtime 透過 typed adapters 呼叫 API 的內部能力端點。", "Provider transport 與 typed boundary", "直接跨服務查詢 API DB", "case / policy / evidence / verification requests", "validated DTOs", ["compose"], failure="有 provider timeout；依能力区分 fail-closed 與 optional Memory unavailable。")
    entity("model", "LLM / Embedding", "external", "提供 structured model output 與檢索向量；endpoint 由設定指定。", "模型生成與 embedding", "canonical state、授權或真正退款", "task prompt / schema / text", "structured output / vector", ["compose", "policy", "compose_file"], failure="輸出須經 contract validation；沒有公開網站端的 API key。")
    entity("policy", "Policy RAG", "capability", "依案件條件找適用版本與條款，保留檢索依據。", "正式 Policy documents、clauses、retrieval records", "由 Memory 新增 eligibility", "case context / order / reason / item scope", "PolicyBundle", ["policy", "spec"], failure="NOT_FOUND / AMBIGUOUS 使 Graph 轉人工接手；不讓模型補造政策。")
    entity("evidence", "Evidence Provider", "capability", "解析 opaque artifact reference，交付結構化 evidence metadata。", "EvidenceItem 與 artifact reference 對照", "把 artifact bytes 塞進 Graph state", "artifact_ref", "EvidenceItem", ["evidence", "readme"])
    entity("verification", "Verification", "capability", "獨立驗證提案的 scope、政策、金額與契約。", "權威驗證規則與 persisted verification", "Reviewer verdict", "ProposedDecisionHandoff", "PASS / FAIL / UNAVAILABLE", ["safety", "spec"])
    entity("refund", "Refund Execution", "capability", "API 驗證授權後執行退款；基準 profile 使用模擬 application。", "refund execution records、idempotency 與執行結果", "LangGraph node 或自行改寫 Reviewer 結論", "ResolutionHandoff 與 persisted authorization", "refund record / case terminal state", ["refund", "bridge", "readme"], failure="未配置 executor 時可能停在 EXECUTING；Graph 完成不等於退款完成。")
    entity("memory", "Operational Memory", "capability", "只檢索符合 scope 且已核准的操作經驗，協助取證與提案。", "candidate / approved memory 與 governance events", "正式 Policy 或自動修改資格規則", "scoped semantic query / candidate", "approved hits / submission result", ["memory", "governance", "spec"], failure="Optional retrieval 失敗記 UNAVAILABLE；新 candidate 不自動視為 approved。")
    entity("memory_worker", "Memory Workers", "worker", "独立消費 Agent terminal event，準備 job、蒸餾、提交或 SKIP。", "非同步蒸餾、結果 replay 與重試", "延後使用者退款結果直到學習結束", "AgentResolvedEvent / MemoryDistillationInput", "MemoryCandidateOutput / MemorySkipOutput", ["enqueue", "memory_worker", "replay"], failure="獨立 retry supervision；candidate 生成與治理核准是不同步驟。")
    entity("governance", "Memory Governance", "capability", "使用治理 service 核准可重用經驗，留下 lifecycle event。", "Memory admission 與狀態轉移", "人工同意退款即自動同意 Memory", "candidate ID / governance action", "approved memory / audit event", ["governance", "demo"])
    entity("activity", "Activity Projection", "module", "獨立接收 node / tool / model activity，保存後供前端回放。", "case_activities、seq、narration outbox", "以接收順序推斷因果或決定 business status", "ActivityEmission / narration result", "ActivityPage / activity SSE", ["activities", "activity_bridge", "activity", "progress"], failure="activity 可能缺漏，UI 明示 unavailable；case events 與 activity feed cursor 分離。")
    entity("outbox", "Command Outbox", "module", "案件寫入與待發 command 共享 API DB transaction。", "agent_command_outbox 與 publish lease", "宣稱 Redis publish 與 SQL 是同一 transaction", "START / RESUME command", "Redis command publication", ["outbox", "api", "test_outbox"], failure="publish 失敗保留 pending；租約與去重處理重送。")
    entity("checkpoint", "Graph Checkpoint", "module", "AsyncPostgresSaver 保存 thread 的 execution state，resume 讀取同一 thread。", "Graph snapshot 與 pending interrupt", "Frontend visible case status", "thread_id / AgentState", "persisted checkpoint / pending task", ["compose", "runtime", schema["source"]])
    entity("__start__", "START", "terminal", "LangGraph 入口。", "起始 edge", "業務案件狀態", "initial state", "parse_request", [graph["source"]])
    entity("__end__", "END", "terminal", "本次 Graph 到達終點；API 或 Memory 工作可能仍在進行。", "Graph terminal boundary", "直接保證退款或 Memory 完成", "Graph 結果", "Agent Service result", [graph["source"], "worker"])

    node_info = {
        "parse_request": ("理解申請", "將買家主張轉成 normalized intent，必要時要求澄清。", "normalized_intent claimed_line_item_ids pending_clarification_request clarification_round", "model"),
        "request_clarification": ("等待澄清", "interrupt 等待 USER turn；resume 驗證 role 與唯一 turn_id。", "conversation_turns", ""),
        "load_case_context": ("載入訂單", "載入可信訂單 snapshot；多品項時回 Intake 綁定範圍。", "case_context order_snapshot claimed_line_item_ids normalized_intent", "providers"),
        "retrieve_policy": ("檢索政策", "取得適用 PolicyBundle；歧義與缺失必須停止自動化。", "policy_bundle", "policy"),
        "prepare_memory_query": ("準備經驗查詢", "解析初始 evidence，生成經驗檢索摘要。", "evidence_bundle operational_memory memory_query_summary memory_retrieval memory_retrieval_status", "model evidence"),
        "retrieve_memory": ("檢索已核准經驗", "以 market、category、policy version 與 claim scope 篩選 Memory。", "operational_memory memory_retrieval memory_retrieval_status memory_query_summary", "memory"),
        "assess_case": ("評估證據", "逐 claim 判定證據充分性，不足時產生具體補件要求。", "evidence_bundle evidence_assessment evidence_round pending_evidence_request", "model"),
        "request_evidence": ("等待補件", "interrupt 後解析 artifact_refs，驗證並合併 evidence。", "evidence_bundle", "evidence"),
        "propose_decision": ("建立或修正提案", "Resolver 提出 draft 或補件；Graph 推導金額、ID 與 counters。", "propose_round evidence_round pending_evidence_request current_handoff proposal_history pending_review_result verification_feedback", "model"),
        "external_verification": ("驗證提案", "驗證成功交 Reviewer；失敗在 budget 內回提案修正。", "verification_feedback verification_round", "verification"),
        "reviewer": ("獨立審核與授權 gate", "Reviewer 僅 APPROVE / REVISE；APPROVE 後 Python gate 決定人工授權。", "review_history review_gate review_routing_reason human_review_ref human_review_result pending_review_result", "model"),
        "record_revision_event": ("記錄修正原因", "保留 structured revision event，再回提案節點。", "revision_events revision_round", ""),
        "await_human_review": ("等待人工審核", "先保存 review_ref 並 self-loop；fetch 無結果才 interrupt，resume 後再 fetch。", "human_review_ref human_review_result", "providers"),
        "emit_resolution_handoff": ("交付決策", "建立 ResolutionHandoff；有 correction 時準備後續 Memory input。", "resolution_handoff", ""),
        "enqueue_memory_distillation": ("準備 Memory input", "只把蒸餾 input 寫入 state；真正 enqueue 由 Agent Service 負責。", "memory_distillation_input", ""),
        "terminate_automation": ("停止自動化並交接", "建立 ManualEscalationHandoff，不宣稱已退款或已完成人工裁決。", "manual_escalation", ""),
    }
    conditions = {
        ("parse_request", "request_clarification"): "completeness INCOMPLETE，且仍有 clarification budget",
        ("parse_request", "load_case_context"): "intent 完整且尚未載入 case_context",
        ("parse_request", "retrieve_policy"): "intent 完整且已有 case_context",
        ("load_case_context", "parse_request"): "多品項 snapshot，需要再次綁定 claimed items",
        ("load_case_context", "retrieve_policy"): "單品項 snapshot，Graph 直接綁定 scope",
        ("retrieve_policy", "prepare_memory_query"): "Policy 適用且不為 NOT_FOUND / AMBIGUOUS",
        ("prepare_memory_query", "retrieve_memory"): "摘要與 evidence 解析成功",
        ("prepare_memory_query", "assess_case"): "optional 摘要不可用，記 UNAVAILABLE 後繼續",
        ("retrieve_memory", "assess_case"): "取得 Memory，或 optional retrieval 不可用後繼續",
        ("request_clarification", "parse_request"): "resume payload 為合法且未重複 USER turn",
        ("assess_case", "request_evidence"): "INSUFFICIENT 且尚有 evidence budget",
        ("assess_case", "propose_decision"): "證據評估非 INSUFFICIENT 且符合契約",
        ("request_evidence", "prepare_memory_query"): "resume refs 解析、驗證與合併成功",
        ("propose_decision", "request_evidence"): "Resolver 要求合法補件且有 budget",
        ("propose_decision", "external_verification"): "合法 draft 已建立新的 handoff",
        ("external_verification", "reviewer"): "Verification PASS",
        ("external_verification", "propose_decision"): "Verification FAIL 且尚有重提 budget",
        ("reviewer", "record_revision_event"): "REVISE 且 revision_round 未達上限",
        ("reviewer", "await_human_review"): "REVISE budget 耗盡，或 APPROVE 後 monetary gate 要求人審",
        ("reviewer", "emit_resolution_handoff"): "APPROVE 且 gate 不要求人審",
        ("record_revision_event", "propose_decision"): "structured correction 已記錄",
        ("await_human_review", "await_human_review"): "首次 submit 保存 review_ref；或合法 poll resume 後再 fetch",
        ("await_human_review", "emit_resolution_handoff"): "取得並驗證人工結果",
        ("emit_resolution_handoff", "enqueue_memory_distillation"): "存在 revision_events 或人工 EDIT / REJECT",
        ("emit_resolution_handoff", "__end__"): "沒有需要蒸餾的 correction",
        ("enqueue_memory_distillation", "__end__"): "input 已準備，或組裝失敗記 None；實際 enqueue 在服務層",
        ("terminate_automation", "__end__"): "ManualEscalationHandoff 已建立",
    }
    for name, node in graph["nodes"].items():
        title, summary, writes, providers = node_info[name]
        # These are reviewed output fields, including the shared fail helper.
        field_writes = writes.split() + ([] if name == "terminate_automation" else ["_route"])
        if "terminate_automation" in node["routes"]:
            field_writes += ["escalation_reason"]
        entity(name, title, "node", summary, "Graph state patch 與 routing", "API canonical business state",
               ", ".join(node["reads"]), ", ".join(field_writes), [node["source"], schema["source"]],
               reads=node["reads"], writes=field_writes, providers=providers.split(),
               interrupt=name in {"request_clarification", "request_evidence", "await_human_review"},
               failure="展開下方所有路由；來源中的 _fail 轉 terminate_automation。" if "terminate_automation" in node["routes"] else "依來源處理；此節點沒有共用 _fail route。")
        for dest, lines in node["routes"].items():
            label = "contract/provider error 或該節點 budget 耗盡；詳細條件見 source" if dest == "terminate_automation" else conditions[(name, dest)]
            edge(name, dest, "graph", label, [node["source"], graph["source"]], lines=lines)
    edge("__start__", "parse_request", "graph", "StateGraph START edge", [graph["source"]])

    for a, b, kind, label, keys in [
        ("buyer", "web", "interaction", "申請與補件", ["client"]),
        ("human", "web", "interaction", "人工裁決", ["review_ui"]),
        ("web", "api", "http", "REST /backend/* → API", ["client", "next"]),
        ("api", "web", "observation", "case events SSE + CaseDetail refresh", ["web"]),
        ("api", "outbox", "db", "case + command 原子提交", ["api", "test_outbox"]),
        ("outbox", "api_db", "db", "agent_command_outbox", ["outbox"]),
        ("outbox", "redis", "command", "return-agent.commands.v1", ["bridge", "streams"]),
        ("redis", "worker", "command", "START / RESUME consumer group", ["worker", "streams"]),
        ("agent", "worker", "composition", "composition / lifecycle", ["compose"]),
        ("worker", "runtime", "call", "astart / aresume", ["worker"]),
        ("worker", "agent_db", "db", "agent_command_journal claim / complete", ["journal"]),
        ("runtime", "checkpoint", "db", "checkpoint / interrupt", ["runtime", "compose"]),
        ("checkpoint", "agent_db", "db", "AsyncPostgresSaver", ["compose"]),
        ("runtime", "providers", "call", "typed provider interfaces", ["compose"]),
        ("providers", "api", "http", "POST /internal/v1/*", ["compose"]),
        ("runtime", "model", "http", "structured generation", ["compose"]),
        ("api", "api_db", "db", "業務讀寫 / transaction", ["case", "api"]),
        ("worker", "redis", "event", "return-agent.events.v1", ["worker", "streams"]),
        ("redis", "api", "event", "事件驗證、投影、commit 後 ACK", ["bridge", "test_idempotent"]),
        ("api", "policy", "call", "PolicyProvider", ["policy"]),
        ("api", "evidence", "call", "resolve artifact_ref", ["evidence"]),
        ("api", "verification", "call", "驗證 handoff", ["safety"]),
        ("api", "refund", "call", "授權後執行 demo application", ["refund", "bridge"]),
        ("policy", "api_db", "db", "policy_documents / clauses / retrievals", ["policy"]),
        ("policy", "model", "http", "embedding provider", ["policy"]),
        ("refund", "api_db", "db", "refund_executions / reservations", ["refund"]),
        ("memory", "api_db", "db", "operational_memories / events", ["memory"]),
        ("api", "memory", "call", "query approved / submit candidate", ["memory", "api"]),
        ("redis", "memory_worker", "event", "AgentResolvedEvent → independent consumer", ["enqueue"]),
        ("memory_worker", "agent_db", "db", "checkpoint input / replay store", ["enqueue", "replay"]),
        ("memory_worker", "redis", "command", "return-agent.memory-jobs.v1 / events", ["enqueue", "memory_worker"]),
        ("memory_worker", "api", "http", "submit candidate via provider", ["compose", "memory_worker"]),
        ("governance", "memory", "call", "明確 approve；非自動同意", ["governance"]),
        ("runtime", "activity", "observation", "traced activity 經 queue / Redis / API", ["compose", "activity_bridge"]),
        ("activity", "api_db", "db", "case_activities / narration outbox", ["activities"]),
        ("activity", "web", "observation", "paged history + separate SSE cursor", ["activity"]),
    ]:
        edge(a, b, kind, label, keys)
    edge("api", "agent", "command", "START / RESUME 經 outbox → Redis → worker（高階聚合）", ["bridge", "worker"], contextOnly=True)
    edge("agent", "api", "event", "AgentServiceEvent 經 Redis → API projection（高階聚合）", ["worker", "bridge"], contextOnly=True)
    edge("agent", "runtime", "composition", "Agent Service 組裝並呼叫 Runtime", ["compose"], contextOnly=True)

    # Expose every actual API route and DTO identifier without hand-invented paths.
    for path in (api + "app.py", api + "activities.py"):
        for fn in ast.walk(ast.parse(read(path))):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in fn.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and deco.func.attr in {"get", "post"} and deco.args and isinstance(deco.args[0], ast.Constant):
                    route = deco.args[0].value
                    eid = f"api:{deco.func.attr}:{route}"
                    entity(eid, f"{deco.func.attr.upper()} {route}", "endpoint", f"API handler：{fn.name}", "API request validation 與 response", "Frontend 直接操作 checkpoint", ", ".join(a.arg for a in fn.args.args), ast.unparse(fn.returns) if fn.returns else "見 source", [ref(path, fn.name)])
                    edge("api", eid, "composition", "API endpoint", [ref(path, fn.name)])

    for table in schema["tables"]:
        entity("table:" + table["name"], table["name"], "table", "API-owned SQLAlchemy table。", ", ".join(table["columns"]), "Graph execution state", "API DB transaction", "persisted record", [table["source"]], foreignKeys=table["foreignKeys"])
        edge("api_db", "table:" + table["name"], "composition", "SQLAlchemy table", [table["source"]])

    llm_calls = []
    adapter_ref = ref(runtime + "model.py", "OpenAIStructuredOutputModel")
    config_ref = ref(agent + "main.py", "_configured_model")
    call_specs = [
        ("parse_request", "INTAKE", "INTAKE_SCHEMA", "IntakeResult", "intake", "案件 Graph"),
        ("prepare_memory_query", "MEMORY_QUERY_SUMMARY", "MEMORY_QUERY_SCHEMA", "MemoryQuerySummary", "memory-query", "案件 Graph / optional"),
        ("assess_case", "ASSESS", "ASSESSMENT_SCHEMA", "EvidenceAssessment", "resolver", "案件 Graph"),
        ("propose_decision", "PROPOSE_OR_REVISE", "RESOLVER_SCHEMA", "ResolverOutput", "resolver", "案件 Graph"),
        ("reviewer", "REVIEW", "REVIEW_SCHEMA", "ReviewResult", "reviewer", "案件 Graph / independent review"),
        ("memory_worker", "MEMORY_DISTILL", "MEMORY_OUTPUT_SCHEMA", "MemoryDistillationOutput", "memory-distiller", "背景 MemoryWorker"),
        ("activity", "ACTIVITY_NARRATION", "NarrationText", "NarrationText", None, "背景 NarrationWorker / observational"),
    ]
    for node_id, task, schema_name, model_type, prompt, scope in call_specs:
        path = runtime + "graph.py" if node_id in graph["nodes"] else runtime + "memory.py" if node_id == "memory_worker" else agent + "activity_workers.py"
        tree = ast.parse(read(path))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and any(k.arg == "task" and isinstance(k.value, ast.Attribute) and k.value.attr == task for k in n.keywords)]
        assert len(calls) == 1, (task, calls)
        call = calls[0]
        payload_expr = next(k.value for k in call.keywords if k.arg == "payload")
        if isinstance(payload_expr, ast.Name):
            containing = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.lineno <= call.lineno <= n.end_lineno)
            assignment = next((n for n in ast.walk(containing) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == payload_expr.id for t in n.targets)), None)
            if assignment:
                payload_expr = assignment.value
        prompt_text = read(runtime + f"prompt_text/{prompt}.txt") if prompt else ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "NARRATION_PROMPT" for t in n.targets)))
        call_ref = graph["nodes"][node_id]["source"] if node_id in graph["nodes"] else ref(path, "MemoryDistiller" if node_id == "memory_worker" else "NarrationWorker")
        prompt_ref = ref(runtime + f"prompt_text/{prompt}.txt") if prompt else ref(path, "NARRATION_PROMPT")
        output_ref = ref(contracts + "models.py", model_type) if node_id != "activity" else ref(path, "NarrationText")
        eid = "llm:" + task
        title = f"{task} / 模型呼叫"
        record = {"id": eid, "title": title, "node": node_id, "task": task, "schema": schema_name + " → " + model_type,
                  "scope": scope, "payloadExpression": ast.unparse(payload_expr), "promptText": prompt_text,
                  "refs": [call_ref, prompt_ref, output_ref, adapter_ref, config_ref],
                  "requestShape": {"SystemMessage": "下方的真實 packaged prompt", "HumanMessage": {"task_mode": task, "input": "由下方 source expression 組装的 payload", "required_output_schema": "TypeAdapter.json_schema()；本 profile 注入 prompt"}},
                  "response": "未載入實跑 raw response；adapter 先 structured parse，再做 TypeAdapter.validate_python，最後由 node 做語意驗證。"}
        llm_calls.append(record)
        entity(eid, title, "llm", f"{scope}：{node_id} 的實際 model.generate 呼叫。", "生成符合 output schema 的結果", "直接持久化 business state 或授權退款", ast.unparse(payload_expr), model_type, record["refs"],
               failure="max_retries=0；錯誤交由 caller 處理。Memory query / narration 為 optional，不等同主決策成功。")
        edge(node_id, eid, "call", "model.generate / " + task, [call_ref])
        edge(eid, "model", "http", "ChatOpenAI.with_structured_output → invoke", [adapter_ref, config_ref])
    embed_ref = ref(api + "capabilities/embeddings.py", "OpenAIEmbeddingProvider")
    entity("embedding", "Embedding Call", "llm", "OpenAIEmbeddingProvider.embed 呼叫 embeddings.create，與對話模型生成分離。", "產生 1536 維向量並驗證 finite / nonzero", "生成案件決策", "model / input=text / dimensions=1536", "response.data[0].embedding", [embed_ref, ref(api + "capabilities/embeddings.py", "validate_embedding")], failure="SDK max_retries=0；模型與向量契約必須一致。")
    llm_calls.append({"id": "embedding", "title": "Embedding / 語意向量", "node": "policy", "task": "embeddings.create", "schema": "list[float] / 1536 dimensions", "scope": "API Policy / Operational Memory retrieval", "refs": [embed_ref], "payloadExpression": "client.embeddings.create(model=self.model_name, input=text, dimensions=self.dimensions)", "promptText": "無 system prompt；輸入文字由檢索／匯入能力組裝。", "requestShape": {"model": "RETURN_AGENT_EMBEDDING_MODEL", "input": "text", "dimensions": 1536}, "response": "真實 response 未載入；驗證 response.data[0].embedding 的維度、finite 與 nonzero。"})
    edge("policy", "embedding", "call", "embedding provider", [embed_ref])
    edge("memory", "embedding", "call", "shared embedding boundary", [refs["memory"], embed_ref])
    edge("embedding", "model", "http", "OpenAI SDK embeddings.create", [embed_ref])
    for contract_name in ["AgentStartCommand", "AgentResumeCommand", "AgentInterruptedEvent", "AgentResolvedEvent", "AgentEscalatedEvent", "AgentRunFailedEvent", "MemoryDistillationJob"]:
        contract_ref = ref(contracts + "service.py", contract_name)
        entity("contract:" + contract_name, contract_name, "event", "Versioned service contract；展開 source 查看 fields 與 validators。", "transport payload shape", "自行執行業務決策", "producer DTO", "validated consumer DTO", [contract_ref])

    groups = [
        {"id": "intake", "title": "理解與範圍", "nodes": ["parse_request", "request_clarification", "load_case_context"]},
        {"id": "context", "title": "政策與經驗", "nodes": ["retrieve_policy", "prepare_memory_query", "retrieve_memory"]},
        {"id": "assess", "title": "證據與提案", "nodes": ["assess_case", "request_evidence", "propose_decision"]},
        {"id": "review", "title": "驗證與審核", "nodes": ["external_verification", "reviewer", "record_revision_event", "await_human_review"]},
        {"id": "handoff", "title": "交付與後續", "nodes": ["emit_resolution_handoff", "enqueue_memory_distillation", "terminate_automation"]},
    ]
    statuses = [n.value.value for n in next(n for n in ast.parse(read(contracts + "ui.py")).body
        if isinstance(n, ast.ClassDef) and n.name == "CaseStatus").body if isinstance(n, ast.Assign)]

    def step(title, detail, frm, to, kind, keys, *, node=None, status="OBSERVING", patch=None, ui="案件處理中", db="無業務寫入", extra=()):
        return {"title": title, "detail": detail, "from": frm, "to": to, "kind": kind,
                "entities": list(dict.fromkeys([frm, to, *extra, *([node] if node else [])])),
                "refs": [refs.get(k, k) for k in keys], "node": node, "status": status,
                "patch": patch or {}, "ui": ui, "db": db, "duration": None}

    def nstep(name, **kw):
        node = next(e for e in entities if e["id"] == name)
        targets = node.get("providers", [])
        dest = targets[0] if targets else "checkpoint"
        return step(node["title"], node["summary"], "runtime", dest, "call", node["refs"], node=name,
                    db="Graph checkpoint 由 Agent PostgreSQL 保存；精確提交時間未記錄。", **kw)

    start = [
        step("買家送出申請", "示意案件：收到的藍牙喇叭外殼有裂痕，希望退貨退款。這不是實際案件紀錄。", "buyer", "web", "interaction", ["client"], ui="送出申請"),
        step("建立案件與待發 command", "POST /cases；CaseRecord 與 AgentStartCommand outbox 共用 transaction，commit 後回 case_ref。", "web", "api", "http", ["api", "test_outbox"], db="API DB：cases + agent_command_outbox 同一 transaction", extra=("api_db", "outbox", "api:post:/cases")),
        step("發布 START", "Outbox dispatcher 將 pending command 發往 return-agent.commands.v1；publish 與標記完成不是跨系統原子交易。", "outbox", "redis", "command", ["bridge", "streams"], db="published_at / lease，依 dispatcher 處理"),
        step("Worker claim 與啟動", "消費 command、claim command_id，使用同一 thread_id 呼叫 astart。", "redis", "worker", "command", ["worker", "journal"], db="Agent DB：agent_command_journal", extra=("agent", "agent_db")),
        nstep("parse_request"), nstep("load_case_context"), nstep("retrieve_policy"),
        nstep("prepare_memory_query"), nstep("retrieve_memory"),
    ]
    decision = [nstep("assess_case"), nstep("propose_decision", patch={"propose_round": 1}), nstep("external_verification"), nstep("reviewer")]
    end = [
        nstep("emit_resolution_handoff"),
        step("Graph END", "這次 Graph 到達終點，API 尚須投影結果與執行退款。", "runtime", "worker", "call", [graph["source"], "worker"], node="__end__"),
        step("發布決策結果", "AgentResolvedEvent 送至事件 stream，由 API consumer 投影。", "worker", "redis", "event", ["worker", "streams"]),
        step("API 接收並驗證", "API 驗證事件與 persisted authorization，執行 demo refund application。", "redis", "api", "event", ["bridge", "refund"], status="EXECUTING", ui="退款執行中", db="API DB：projection / refund records", extra=("api_db", "refund")),
        step("模擬退款完成", "本場景假設 demo application 成功；無真實金流，也不是測量紀錄。", "refund", "api_db", "db", ["refund", "bridge"], status="RESOLVED", ui="結果：模擬案件已結束", db="API DB：refund_executions / cases / case events"),
        step("畫面更新", "case events SSE 觸發 CaseDetail refresh；activity feed 獨立呈現執行進度。", "api", "web", "observation", ["web", "activity"], status="RESOLVED", ui="顯示決策與案件結果", extra=("activity",)),
    ]
    evidence = [
        nstep("assess_case", patch={"evidence_round": 1}),
        nstep("request_evidence", ui="Graph 已 pause，等待 API 投影"),
        step("發送 interrupt 結果", "Worker 發 AgentInterruptedEvent；pending task 位於 Graph checkpoint。", "worker", "redis", "event", ["worker", "runtime"]),
        step("投影待補件狀態", "API 將 interrupt 投影成 AWAITING_EVIDENCE，持久化後供 SSE 讀取。", "redis", "api", "event", ["bridge"], status="AWAITING_EVIDENCE", ui="等待補件", db="API DB：cases / events", extra=("api_db",)),
        step("顯示補件操作", "SSE / CaseDetail 讓 ConversationPanel 開啟補件欄位。", "api", "web", "observation", ["web", "ui"], status="AWAITING_EVIDENCE", ui="請補充 evidence artifact reference"),
        step("買家提交 refs", "POST /cases/{case_ref}/messages；row lock 與 status validation 後保存 turn、轉 OBSERVING、enqueue RESUME。", "web", "api", "http", ["messages"], db="API DB transaction：turn / status / command outbox", extra=("api_db", "outbox", "api:post:/cases/{case_ref}/messages")),
        step("發布 RESUME", "Outbox 發送帶原 thread_id 的 AgentResumeCommand。", "outbox", "redis", "command", ["messages", "bridge"]),
        step("恢復原 execution", "Worker 呼叫 aresume，runtime 驗證 pending interrupt kind，使用 Command(resume=...)。", "worker", "runtime", "call", ["runtime", "worker"], extra=("agent_db", "checkpoint")),
        nstep("request_evidence"), nstep("prepare_memory_query"), nstep("retrieve_memory"),
    ]
    human = [
        nstep("await_human_review", ui="審核資料建立中"),
        nstep("await_human_review", ui="review_ref 已保存；fetch 尚無結果 → interrupt"),
        step("人工 interrupt 傳出", "AgentInterruptedEvent 由 Worker 發送，API 投影為等待人工。", "worker", "redis", "event", ["worker"]),
        step("API 持久化待審狀態", "案件轉 AWAITING_HUMAN_REVIEW；這不等於 Reviewer 輸出第三種 verdict。", "redis", "api", "event", ["bridge", "review"], status="AWAITING_HUMAN_REVIEW", ui="等待人工裁決", db="API DB：cases / human_reviews"),
        step("呈現 ReviewerPanel", "Frontend 取得待審資料與可操作狀態。", "api", "web", "observation", ["review_ui", "web"], status="AWAITING_HUMAN_REVIEW", ui="APPROVE / EDIT / REJECT"),
        step("人工提交 EDIT", "示意：人工修正退回要求；提交至 /review。API 驗證 dossier 與合法 action。", "human", "web", "interaction", ["review_ui"], status="AWAITING_HUMAN_REVIEW", ui="提交人工修正"),
        step("保存人工結果", "API 保存結果、轉 OBSERVING 並 enqueue HumanReviewPollResume；金錢授權與結果依 persisted 記錄驗證。", "web", "api", "http", ["review"], db="API DB：human_reviews + case status + outbox transaction", extra=("api_db", "outbox", "api:post:/cases/{case_ref}/review")),
        step("發布人工 RESUME", "相同 thread_id，payload 是 poll signal，不把未驗證的前端裁決直接當 Graph state。", "outbox", "redis", "command", ["review"]),
        step("恢復待審節點", "aresume 重新進入 interrupt node；再由 self-loop 取得 provider 保存的人工結果。", "worker", "runtime", "call", ["runtime", "worker"], extra=("agent_db",)),
        nstep("await_human_review"), nstep("emit_resolution_handoff"), nstep("enqueue_memory_distillation"),
        *end[1:],
    ]
    background = [
        step("獨立 terminal-event consumer", "MemoryEnqueueWorker 依 thread_id 讀 checkpoint 的 input，case UI 不等待此流程。此排列只是可能的非同步順序。", "redis", "memory_worker", "event", ["enqueue"], status="RESOLVED", db="Agent DB checkpoint read", extra=("agent_db",)),
        step("排入 Memory job", "以 handoff_id 關聯 job，發布 return-agent.memory-jobs.v1。", "memory_worker", "redis", "command", ["enqueue", "streams"], status="RESOLVED"),
        step("蒸餾與提交", "示意選擇 candidate 分支；實際也可能 SKIP。背景 Worker 透過 API provider 提交候選經驗。", "memory_worker", "api", "http", ["memory_worker", "compose"], status="RESOLVED", db="Agent replay / API candidate persistence", extra=("memory", "api_db", "agent_db")),
        step("明確治理核准", "這是獨立 governance service 操作示意，不是本版 UI 自動行為。沒有 B→C 實跑證據。", "governance", "memory", "call", ["governance", "demo"], status="RESOLVED", db="API DB：operational_memory_events / approved status", extra=("api_db",)),
    ]
    scenarios = [
        {"id": "normal", "title": "01 正常處理", "summary": "政策、證據與提案一致，通過審核並完成模擬退款。", "test": refs["test_happy"], "steps": start + decision + end},
        {"id": "evidence", "title": "02 補件後繼續", "summary": "觀察 checkpoint、等待狀態、REST 補件與原 thread resume。", "test": refs["test_resume"], "steps": start + evidence + decision + end},
        {"id": "human", "title": "03 人工授權與修正", "summary": "示意 APPROVE 後 monetary gate 要求人工，人工 EDIT 後回 Graph。", "test": refs["test_human"], "steps": start + decision + human},
        {"id": "failure", "title": "04 政策缺失交接", "summary": "NOT_FOUND 中止自動化，產生可追溯的人工接手結果。", "test": refs["test_failure"], "steps": start[:6] + [
            nstep("retrieve_policy", patch={"escalation_reason": "POLICY_NOT_FOUND"}),
            nstep("terminate_automation"),
            step("Graph END", "ManualEscalationHandoff 已交付；不是人工處理已完成。", "runtime", "worker", "call", [graph["source"]], node="__end__"),
            step("Escalated event", "Worker 發 AgentEscalatedEvent。", "worker", "redis", "event", ["worker"]),
            step("API 投影交接", "API 將案件轉 ESCALATED。", "redis", "api", "event", ["bridge"], status="ESCALATED", db="API DB：cases / events", ui="需要人工接手"),
            step("交接畫面", "Frontend 顯示交接結果，不提供捏造的自動退款。", "api", "web", "observation", ["web"], status="ESCALATED", ui="自動化已停止，等待後續處理")
        ]},
        {"id": "memory", "title": "05 案後經驗治理", "summary": "人工 correction → background job → candidate / SKIP → 獨立核准。", "test": refs["test_memory"], "steps": start + decision + human + background},
    ]
    for scenario in scenarios:
        scenario["provenance"] = "Illustrative"
        scenario["note"] = "依固定版本 source 與測試設計的教學回放；未載入 live execution。數值為示意，未記錄完整 Before / After 或耗時。"
        for index, s in enumerate(scenario["steps"]):
            s["id"] = f"{scenario['id']}:{index}"

    mappings = [
        ("OBSERVING", "CaseWorkspace / ConversationPanel", "處理進度；activity 表示觀察到的 node 狀態", "檢視進度", "GET case + events / activities", "web"),
        ("AWAITING_CLARIFICATION", "ConversationPanel", "澄清問題與輸入欄位", "補充申請", "POST /messages → ClarificationResume → parse_request", "messages"),
        ("AWAITING_EVIDENCE", "ConversationPanel", "待補件問題與 artifact reference 欄位", "提交補件", "POST /messages → EvidenceResume → prepare_memory_query", "messages"),
        ("AWAITING_HUMAN_REVIEW", "ReviewerPanel", "人工審核 dossier 與操作", "APPROVE / EDIT / REJECT", "POST /review → HumanReviewPollResume → fetch_result", "review"),
        ("EXECUTING", "CaseWorkspace / withRefundWait", "Graph 結束後，API 退款仍待執行", "檢視處理狀態", "等待 Backend execution / projection", "progress"),
        ("RESOLVED", "CaseWorkspace", "案件結果；Memory activity 仍可能稍後抵達", "檢視結果與歷史", "CaseDetail / done；activity feed 獨立", "web"),
        ("ESCALATED", "CaseWorkspace", "自動處理終止，顯示人工交接", "檢視交接資訊", "ManualEscalationHandoff → done", "bridge"),
    ]
    discrepancies = [
        {"title": "歷史重建規格不是目前 runtime", "detail": "docs/reconstruction 固定於歷史快照；本網站使用 baseline committed source，現行 docs/spec 作語意交叉檢查。", "refs": [refs["spec"], refs["readme"]]},
        {"title": "UI 案件圖不是 Graph 原圖", "detail": "case-graph.mjs 加入 API execute_refund，且未列出所有失敗與 self-loop；Exact View 由 graph.py 與 reviewed routes 建立。", "refs": [ref(web + "lib/case-graph.mjs"), graph["source"]]},
        {"title": "Graph registration 共用 destinations", "detail": "全域 path map 是註冊上限；本網站逐 node / helper 核對 _route，並檢查 curated 路由集與 AST inventory。這不是任意 Python 程式的可達性證明。", "refs": [graph["source"]]},
        {"title": "Deployment profile 改變可用能力", "detail": "Compose 預設 API unconfigured、Agent demo。本網站專門描述 integrated-demo + integrated-qwen；不把預設 compose healthy 當成相同功能。", "refs": [refs["compose_file"], refs["compose"], refs["readme"]]},
        {"title": "實跑證據尚未載入", "detail": "五個回放均為 Illustrative。來源中存在相關 test definitions，但本網站不沿用其他 repo 或舊分支的測試通過數。", "refs": [refs["test_happy"], refs["test_resume"], refs["test_human"]]},
        {"title": "Agent checkpoint 實體 tables 未由本 repo 定義", "detail": "AsyncPostgresSaver.setup() 交由依賴建立 schema。此網站呈現 checkpoint 邏輯資料，不捏造依賴版本的實體欄位與 foreign keys。", "refs": [refs["compose"], refs["runtime"]]},
        {"title": "次序、恢復與 exactly-once 的界線", "detail": "activity seq 是接收順序；journal / event 去重不代表所有外部 side effects exactly-once。Crash 在 node side effect 與 checkpoint 之間的完整保證仍須逐 provider 驗證。", "refs": [refs["progress"], refs["journal"], refs["runtime"]]},
    ]
    # Include deployment / schema / migration / fixture entrypoints in the audited manifest.
    for path in ["apps/api/README.md", "apps/agent_service/README.md", "apps/web/README.md", "apps/contracts/README.md", "packages/agent_runtime/README.md", "apps/api/alembic/versions/0003_policy_rag.py", "apps/agent_service/src/return_agent_service/settings.py", "data/policy.json.example", "apps/api/tests/test_integrated_demo.py"]:
        ref(path)
    return {"entities": entities, "edges": edges, "groups": groups, "graph": graph, "schema": schema,
            "llmCalls": llm_calls,
            "llmTransport": {"summary": "integrated-qwen：main._configured_model → OpenAIStructuredOutputModel → ChatOpenAI.with_structured_output(method=json_schema) → invoke(SystemMessage, HumanMessage)。temperature=0、timeout=180s、max_retries=0、streaming=True、include_schema_in_prompt=True、enable_thinking=False。模型名稱與 base_url 由配置提供，此次未讀取 live secrets／endpoint。Chat Completions endpoint 路徑由 SDK 決定；通常為 base URL 下的 /chat/completions（SDK 協定推論，非 captured request）。integrated-compass 的 Responses 模式不混入本基準。", "failure": "非 object schema 包成 output envelope；解析後 unwrap，再由 Pydantic TypeAdapter 驗證。Node 額外執行 domain validation。SDK streaming 不等於把 raw model tokens 直接推給 Frontend；UI 依 case events 與 activity 投影。Narration 的 timeout / error 只屬觀察流程，不得把失敗 narration 當成案件失敗。", "refs": [adapter_ref, config_ref, embed_ref, ref(agent + "activity_workers.py", "NarrationWorker")]},
            "scenarios": scenarios, "statuses": statuses, "refs": refs, "discrepancies": discrepancies,
            "uiMappings": [{"status": s, "component": c, "screen": d, "action": a, "next": n, "refs": [refs[r], refs["status"]]} for s, c, d, a, n, r in mappings],
            "designReferences": [{"title": "Collect UI", "url": "https://collectui.com/"}, {"title": "S5-Style", "url": "https://www.s5-style.com/"}],
            "designNote": "已讀取參考首頁；動態 gallery 素材未完整取得。採自訂 editorial typography、留白與圖形布局，沒有複製特定設計。"}
