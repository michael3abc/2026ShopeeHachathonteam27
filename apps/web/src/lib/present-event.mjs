const nodeLabels = {
  parse_request: "理解申請內容",
  load_case_context: "讀取訂單資料",
  retrieve_policy: "查詢退款政策",
  prepare_memory_query: "摘要本案查詢",
  retrieve_memory: "檢索操作經驗",
  assess_case: "評估申請證據",
  evaluate_policy: "判定政策途徑",
  confirm_policy_path: "確認政策途徑",
  propose_decision: "產生處理建議",
  external_verification: "驗證處理建議",
  request_clarification: "等待補充說明",
  request_evidence: "等待補交資料",
  reviewer: "覆核處理建議",
  record_revision_event: "記錄建議修正",
  await_human_review: "等待人工審核",
  emit_resolution_handoff: "送出處理結果",
  execute_refund: "執行退款",
  enqueue_memory_distillation: "整理案件經驗",
  distill_memory: "整理案件經驗",
  submit_candidate: "保存案件經驗",
  external_memory_approval: "覆核案件經驗",
  terminate_automation: "異常終止自動處理",
};

/**
 * EventSource also emits a transport-level `error` Event with no data. The
 * domain contract has an `error` event too, so only parse actual messages.
 * @param {{ data?: unknown }} message
 * @returns {import("../contracts/agent-event").AgentEvent | undefined}
 */
export function parseAgentEvent(message) {
  if (typeof message.data !== "string") return undefined;
  return JSON.parse(message.data);
}

/** @param {string} node */
export function nodeLabel(node) {
  return nodeLabels[node] ?? node.replaceAll("_", " ");
}

/**
 * Convert the executable event contract into customer-facing copy.
 * @param {import("../contracts/agent-event").AgentEvent} event
 */
export function presentEvent(event) {
  switch (event.type) {
    case "node_enter":
      return { title: nodeLabel(event.node), detail: "開始處理", tone: "active" };
    case "node_exit":
      return { title: nodeLabel(event.node), detail: "處理完成", tone: "success" };
    case "tool_call":
      return { title: "查詢案件資料", detail: event.payload.tool_name, tone: "muted" };
    case "tool_result":
      return {
        title: event.payload.ok ? "資料查詢完成" : "資料查詢失敗",
        detail: event.payload.summary,
        tone: event.payload.ok ? "success" : "danger",
      };
    case "token":
      return { title: "Agent 更新", detail: event.payload.text, tone: "muted" };
    case "memory_retrieval":
      return {
        title: event.payload.status === "UNAVAILABLE" ? "操作經驗暫不可用" : `檢索操作經驗：${(event.payload.hits ?? []).length} 筆`,
        detail: event.payload.query_summary ?? "案件摘要不可用；案件繼續處理。",
        tone: "muted",
      };
    case "interrupt": {
      const kind = event.payload.interrupt_kind;
      const title =
        kind === "CLARIFICATION"
          ? "需要補充說明"
          : kind === "EVIDENCE_REQUEST"
            ? "需要補交資料"
            : kind === "POLICY_CONFIRMATION" ? "確認政策途徑" : "等待人工審核";
      return { title, detail: "案件需要下一步操作", tone: "warning" };
    }
    case "state_change":
      return {
        title: statusLabel(event.payload.to_status),
        detail: event.payload.reason,
        tone: event.payload.to_status === "ESCALATED" ? "danger" : "active",
      };
    case "done":
      return {
        title: event.payload.status === "RESOLVED" ? "案件已完成" : "案件已轉交處理",
        detail: `結果編號 ${event.payload.terminal_ref}`,
        tone: event.payload.status === "RESOLVED" ? "success" : "danger",
      };
    case "error":
      return { title: "處理發生問題", detail: event.payload.message, tone: "danger" };
  }
}

/** @param {string} status */
export function statusLabel(status) {
  const labels = {
    OBSERVING: "AI 處理中",
    AWAITING_CLARIFICATION: "等待補充說明",
    AWAITING_EVIDENCE: "等待補交資料",
    AWAITING_HUMAN_REVIEW: "等待人工審核",
    AWAITING_POLICY_CONFIRMATION: "等待確認途徑",
    AWAITING_RETURN_CONFIRMATION: "等待同意退回",
    AWAITING_RETURN: "等待商品退回",
    AWAITING_RETURN_INSPECTION: "等待退回驗收",
    EXECUTING: "等待退款執行",
    RESOLVED: "案件已完成",
    ESCALATED: "案件已轉交處理",
  };
  return labels[status] ?? status;
}

/** Latest retrieval replaces the entire previous result, also during replay.
 * @param {import("../contracts/agent-event").AgentEvent[]} events
 * @returns {import("../contracts/agent-event").MemoryRetrievalPayload | undefined}
 */
export function latestMemoryRetrieval(events) {
  let latest;
  for (const event of events) {
    if (event.type === "node_enter" && event.node === "prepare_memory_query") latest = undefined;
    if (event.type === "memory_retrieval") latest = event.payload;
  }
  return latest;
}
