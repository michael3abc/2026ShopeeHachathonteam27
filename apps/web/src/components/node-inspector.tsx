import { Bot, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { AgentEvent } from "@/contracts/agent-event";
import type { graphProgress } from "@/lib/graph-progress.mjs";
import { latestMemoryRetrieval, nodeLabel } from "@/lib/present-event.mjs";
import { cn } from "@/lib/utils";

type GraphProgress = ReturnType<typeof graphProgress>;
type NodeState = GraphProgress["states"][string];
type NodeVisit = GraphProgress["visits"][string][number];
type OperationRun = NodeVisit["operations"][number];

const memoryNodes = new Set(["prepare_memory_query", "retrieve_memory"]);

const stateLabel: Record<NodeState, string> = {
  pending: "尚未執行",
  active: "執行中",
  waiting: "等待中",
  done: "已完成",
  failed: "執行失敗",
};

const stateBadge: Record<NodeState, string> = {
  pending: "",
  active: "border-orange-200 bg-orange-50 text-orange-700",
  waiting: "border-amber-200 bg-amber-50 text-amber-800",
  done: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700",
};

export function NodeInspector({
  events,
  node,
  onFollowCurrent,
  progress,
}: {
  events: AgentEvent[];
  node: string;
  /** Present while a node is pinned; resumes following the running node. */
  onFollowCurrent?: () => void;
  progress: GraphProgress;
}) {
  const state = progress.states[node] ?? "pending";
  const visits = progress.visits[node] ?? [];
  const gate = node === "reviewer" ? latestReviewGate(events) : undefined;

  return (
    <section
      aria-label="節點檢視"
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-stone-200 bg-white"
      role="tabpanel"
    >
      <header className="flex items-start justify-between gap-4 border-b border-stone-200 px-5 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-bold text-stone-950">{nodeLabel(node)}</h2>
          <code className="mt-0.5 block truncate text-[10px] text-stone-400">{node}</code>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {onFollowCurrent ? (
            <button
              className="rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-orange-300 hover:text-orange-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
              onClick={onFollowCurrent}
              type="button"
            >
              <span className="text-[11px] font-semibold">跟隨目前節點</span>
            </button>
          ) : null}
          {visits.length > 1 ? (
            <Badge className="border-violet-200 bg-violet-50 text-violet-700">進入 {visits.length} 次</Badge>
          ) : null}
          <Badge className={stateBadge[state]}>{stateLabel[state]}</Badge>
        </div>
      </header>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
        {visits.length === 0 && state === "waiting" ? (
          <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50/60 p-5 text-center" role="status">
            <p className="text-sm font-semibold text-amber-800">處理結果已送出，等待退款系統執行</p>
            <p className="mt-1 text-xs leading-5 text-amber-700">
              退款由 API 在 agent 完成後執行。若目前的設定沒有接上退款服務（例如預設的 demo），案件會一直停在這一步。
            </p>
          </div>
        ) : visits.length === 0 ? (
          <div className="rounded-xl border border-dashed border-stone-300 p-5 text-center">
            <p className="text-sm font-semibold text-stone-600">這個節點還沒有執行紀錄</p>
            <p className="mt-1 text-xs text-stone-400">Agent 走到這一步後，工具與模型呼叫會即時顯示在這裡。</p>
          </div>
        ) : (
          visits.map((visit, index) => (
            <section aria-label={`第 ${index + 1} 次執行`} className="space-y-2" key={visit.attemptIds[0] ?? index}>
              {visits.length > 1 ? (
                <h3 className="text-[10px] font-bold tracking-[0.12em] text-stone-400 uppercase">第 {index + 1} 次</h3>
              ) : null}
              {visit.operations.length ? (
                <ol className="divide-y divide-stone-100 rounded-xl border border-stone-200">
                  {visit.operations.map((operation) => (
                    <OperationRow key={operation.operationId} operation={operation} />
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-stone-400">這次沒有呼叫工具或模型。</p>
              )}
              <NarrationNote narration={visit.narration} />
              {["parse_request", "load_case_context"].includes(node) && (
                visit.intents?.length ? visit.intents.map(item => <IntentResult key={item.id} value={item.value} />) :
                <p className="text-xs text-stone-500">{state === "active" ? "理解結果尚未完成" : "未記錄理解結果"}</p>
              )}
            </section>
          ))
        )}
        {memoryNodes.has(node) ? <MemoryResults events={events} /> : null}
        {gate ? (
          <p aria-label="Reviewer gate 結果" className="rounded-xl bg-stone-50 p-3 text-xs leading-5">
            金額 gate：{gate.status} · {gate.currency} {gate.amount} · 門檻 {gate.threshold ?? "未設定"} ·{" "}
            {gate.reason ?? "未命中"} · {gate.config_version}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function IntentResult({value}: {value: import("@/contracts/activity-event").IntentDisplay}) {
  const items = value.claimed_line_item_ids ?? [];
  const fields = value.missing_fields ?? [];
  const reasons: Record<string, string> = {ITEM_DAMAGED:"商品損壞", ITEM_NOT_AS_DESCRIBED:"商品與描述不符", MISSING_ITEM:"缺少商品", WRONG_ITEM:"收到錯誤商品", QUALITY_ISSUE:"品質問題", CHANGED_MIND:"改變心意"};
  const actions: Record<string, string> = {REFUND:"退款", RETURN_AND_REFUND:"退貨退款", EXCHANGE:"換貨", UNSPECIFIED:"尚未明確"};
  const missing: Record<string, string> = {ORDER:"訂單資訊", REASON:"申請原因", ACTION:"希望的處理方式", ITEMS:"申請商品範圍", OTHER:"其他待補充資訊"};
  return <section aria-label="理解結果" className="rounded-xl border border-orange-100 bg-orange-50/40 p-3 text-xs">
    <h4 className="mb-2 font-semibold">理解結果</h4>
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
      <dt>申請原因</dt><dd>{value.reason_code ? reasons[value.reason_code] ?? "尚未辨識" : "尚未辨識"}</dd>
      <dt>希望的處理</dt><dd>{actions[value.requested_action] ?? "尚未明確"}</dd>
      <dt>申請商品</dt><dd className="break-all">{items.length ? items.join("、") : "尚未綁定"}</dd>
      <dt>資訊完整度</dt><dd>{value.completeness === "COMPLETE" ? "已足夠進入下一步" : "需要補充說明"}</dd>
      <dt>待補充資訊</dt><dd>{fields.length ? fields.map(key => missing[key] ?? missing.OTHER).join("、") : "無"}</dd>
    </dl>
    <p className="mt-3 text-stone-500">理解結果不代表退款核准</p>
  </section>;
}

function OperationRow({ operation }: { operation: OperationRun }) {
  const separator = operation.name.indexOf(".");
  const provider = separator > 0 ? operation.name.slice(0, separator) : undefined;
  const method = separator > 0 ? operation.name.slice(separator + 1) : operation.name;
  const facts = [
    operation.facts?.outcome,
    operation.facts?.count != null ? `${operation.facts.count} 筆` : undefined,
  ].filter(Boolean);

  return (
    <li className="flex items-start gap-3 px-3 py-2.5" data-operation-status={operation.status}>
      <span
        className={cn(
          "mt-0.5 grid size-6 shrink-0 place-items-center rounded-md",
          operation.kind === "model" ? "bg-violet-50 text-violet-600" : "bg-stone-100 text-stone-600",
        )}
      >
        {operation.kind === "model" ? <Bot className="size-3.5" /> : <Wrench className="size-3.5" />}
      </span>
      <span className="min-w-0 flex-1">
        <strong className="block truncate font-mono text-xs text-stone-800">
          {operation.kind === "model" ? `LLM · ${method}` : method}
        </strong>
        <span className="block truncate text-[11px] text-stone-400">
          {[provider ?? (operation.kind === "model" ? "模型呼叫" : "工具呼叫"), ...facts].join(" · ")}
        </span>
      </span>
      <span
        className={cn(
          "shrink-0 text-[11px] tabular-nums",
          operation.status === "running" && "tool-blink text-orange-600",
          operation.status === "failed" && "text-red-600",
          operation.status === "ok" && "text-stone-500",
        )}
      >
        {operation.status === "running" ? "執行中…" : operation.status === "failed" ? "失敗" : formatDuration(operation.durationMs)}
      </span>
    </li>
  );
}

function NarrationNote({ narration }: { narration?: NodeVisit["narration"] }) {
  if (!narration) return null;
  if (narration.status === "completed") {
    return (
      <p aria-label="AI 解說" className="rounded-xl border border-violet-100 bg-violet-50/70 px-3 py-2 text-xs leading-5 text-violet-900">
        {narration.text}
      </p>
    );
  }
  return (
    <p className="text-[11px] text-stone-400">
      {narration.status === "disabled" ? "此模式未啟用 AI 解說。" : "AI 解說暫不可用。"}
    </p>
  );
}

function formatDuration(durationMs: number | null | undefined) {
  if (durationMs == null) return "完成";
  return durationMs < 1000 ? `${durationMs} ms` : `${(durationMs / 1000).toFixed(1)} s`;
}

function latestReviewGate(events: AgentEvent[]) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.type === "node_exit" && event.node === "reviewer" && event.payload?.review_gate) {
      return event.payload.review_gate;
    }
  }
  return undefined;
}

function MemoryResults({ events }: { events: AgentEvent[] }) {
  const result = latestMemoryRetrieval(events);
  if (!result) return <p className="text-sm text-stone-500">等待本次 Memory 檢索結果。</p>;
  return (
    <section aria-label="最新 Memory 檢索" className="space-y-3">
      <h3 className="text-sm font-bold">最新操作經驗檢索</h3>
      <p className="text-xs leading-5 text-stone-600">查詢摘要：{result.query_summary ?? "無法產生"}</p>
      {result.status === "UNAVAILABLE" ? (
        <p className="text-sm text-amber-700" role="status">
          Memory 暫不可用（{result.error_code}）；案件繼續，不使用舊結果。
        </p>
      ) : (result.hits ?? []).length === 0 ? (
        <p className="text-sm text-stone-500" role="status">
          沒有符合條件的已核准操作經驗。
        </p>
      ) : (
        <ol className="space-y-3">
          {(result.hits ?? []).map(({ memory, similarity }, index) => (
            <li className="rounded-xl border border-stone-200 p-3 text-xs leading-5" data-memory-id={memory.memory_id} key={memory.memory_id}>
              <strong>
                {index + 1}. {memory.memory_id}
              </strong>
              <div className="flex flex-wrap gap-2 py-2">
                <Badge>cosine {similarity.toFixed(4)}</Badge>
                <Badge>confidence {memory.confidence.toFixed(2)}</Badge>
              </div>
              <p>{memory.retrieval_summary}</p>
              <p className="mt-2">適用條件：{memory.trigger_conditions.join("；")}</p>
              <p>建議行為：{memory.recommended_behavior}</p>
              <p className="mt-2 break-words text-stone-500">
                範圍：{memory.scope.market} · 原因 {memory.scope.reason_codes?.join(", ") || "不限"} · 品類{" "}
                {memory.scope.categories?.join(", ") || "不限"} · claim {memory.scope.claim_ids?.join(", ") || "不限"}
              </p>
              <p className="break-words text-stone-500">
                {memory.policy_version} · {memory.claim_registry_version}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
