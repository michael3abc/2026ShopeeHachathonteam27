"use client";

import { useEffect, useRef } from "react";

import { Card } from "@/components/ui/card";
import { edgeId, graphEdges, graphNodes, loopBudgets } from "@/lib/case-graph.mjs";
import type { graphProgress } from "@/lib/graph-progress.mjs";
import { nodeLabel } from "@/lib/present-event.mjs";
import type { PlaybackSpeed } from "@/lib/use-activity-playback";
import { cn } from "@/lib/utils";

type GraphProgress = ReturnType<typeof graphProgress>;
type NodeState = GraphProgress["states"][string];
type EdgeTone = "idle" | "forward" | "loop" | "skip" | "failure";
type StagePlayback = {
  speed: PlaybackSpeed;
  remainingSteps: number;
  onSpeedChange: (speed: PlaybackSpeed) => void;
  onSkipToLatest: () => void;
};

const speedOptions: { speed: PlaybackSpeed; label: string }[] = [
  { speed: "live", label: "即時" },
  { speed: "normal", label: "1×" },
  { speed: "slow", label: "0.5×" },
];

const NODE_WIDTH = 136;
const NODE_HEIGHT = 52;
const CANVAS_WIDTH = 1940;
const CANVAS_HEIGHT = 330;

const nodePosition: Record<string, { x: number; y: number }> = {
  parse_request: { x: 90, y: 92 },
  load_case_context: { x: 250, y: 92 },
  retrieve_policy: { x: 410, y: 92 },
  prepare_memory_query: { x: 570, y: 92 },
  retrieve_memory: { x: 730, y: 92 },
  assess_case: { x: 890, y: 92 },
  propose_decision: { x: 1050, y: 92 },
  external_verification: { x: 1210, y: 92 },
  reviewer: { x: 1370, y: 92 },
  emit_resolution_handoff: { x: 1530, y: 92 },
  execute_refund: { x: 1690, y: 92 },
  enqueue_memory_distillation: { x: 1690, y: 222 },
  request_clarification: { x: 90, y: 222 },
  request_evidence: { x: 890, y: 222 },
  record_revision_event: { x: 1240, y: 222 },
  await_human_review: { x: 1470, y: 222 },
  terminate_automation: { x: 1850, y: 222 },
};

// Loops through a node run below the main row and node-less loops above it, so the
// five loops never cross each other.
const edgePath: Record<string, string> = {
  "parse_request>request_clarification": "M62,118 L62,194",
  "request_clarification>parse_request": "M118,196 L118,120",
  "load_case_context>parse_request": "M250,66 C250,24 90,24 90,64",
  "prepare_memory_query>assess_case": "M570,66 C570,14 890,14 890,64",
  "assess_case>request_evidence": "M862,118 L862,194",
  "propose_decision>request_evidence": "M1020,118 C1020,168 940,160 940,194",
  "request_evidence>prepare_memory_query": "M890,248 C890,304 570,304 570,120",
  "external_verification>propose_decision": "M1210,66 C1210,24 1050,24 1050,64",
  "reviewer>record_revision_event": "M1350,118 C1350,160 1260,160 1260,194",
  "record_revision_event>propose_decision": "M1220,248 C1220,304 1080,304 1080,120",
  "reviewer>await_human_review": "M1400,118 C1400,160 1450,160 1450,194",
  "await_human_review>emit_resolution_handoff": "M1500,196 C1500,160 1530,160 1530,120",
  "emit_resolution_handoff>enqueue_memory_distillation": "M1560,118 C1560,160 1690,160 1690,194",
};

const edgeLabels: { edge: string; x: number; y: number; text?: string; budget?: string }[] = [
  { edge: "load_case_context>parse_request", x: 170, y: 16, text: "品項未綁定" },
  { edge: "prepare_memory_query>assess_case", x: 730, y: 12, text: "摘要不可用時略過" },
  { edge: "request_clarification>parse_request", x: 128, y: 162, budget: "clarification" },
  { edge: "request_evidence>prepare_memory_query", x: 730, y: 300, budget: "evidence" },
  { edge: "external_verification>propose_decision", x: 1130, y: 16, budget: "verification" },
  { edge: "record_revision_event>propose_decision", x: 1150, y: 300, budget: "revision" },
];

const arrowColor: Record<EdgeTone, string> = {
  idle: "#d6d3d1",
  forward: "#f97316",
  loop: "#8b5cf6",
  skip: "#78716c",
  failure: "#ef4444",
};

const edgeStroke: Record<EdgeTone, string> = {
  idle: "stroke-stone-300",
  forward: "stroke-orange-500",
  loop: "stroke-violet-500 [stroke-dasharray:6_5]",
  skip: "stroke-stone-500 [stroke-dasharray:4_5]",
  failure: "stroke-red-500 [stroke-dasharray:4_5]",
};

const stateText: Record<NodeState, string> = {
  pending: "尚未執行",
  active: "執行中",
  waiting: "等待中",
  done: "已完成",
  failed: "執行失敗",
};

function pathFor(from: string, to: string) {
  const override = edgePath[edgeId(from, to)];
  if (override) return override;
  const start = nodePosition[from];
  const end = nodePosition[to];
  if (start.y === end.y) {
    return `M${start.x + NODE_WIDTH / 2},${start.y} L${end.x - NODE_WIDTH / 2 - 2},${end.y}`;
  }
  // Failure routes drop below the lower row into the terminal node.
  return `M${start.x},${start.y + NODE_HEIGHT / 2} C${start.x},316 ${end.x},316 ${end.x},${end.y + NODE_HEIGHT / 2 + 2}`;
}

function nodeStyle(state: NodeState, lane: string) {
  if (state === "active") return "node-breathe border-orange-400 bg-orange-50 text-orange-800";
  if (state === "waiting") return "border-dashed border-amber-400 bg-amber-50 text-amber-800";
  if (state === "failed") return "border-red-300 bg-red-50 text-red-800";
  if (state === "done") {
    return lane === "loop" ? "border-violet-300 bg-white text-stone-800" : "border-emerald-300 bg-white text-stone-800";
  }
  return "border-stone-200 bg-white text-stone-400";
}

export function GraphStage({
  onSelectNode,
  playback,
  progress,
  selectedNode,
  unavailable,
}: {
  onSelectNode: (node: string) => void;
  playback: StagePlayback;
  progress: GraphProgress;
  selectedNode: string;
  unavailable: boolean;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const { activeNode } = progress;

  // Bring the running node into view only when it is off-screen, so a wide viewport stays still.
  useEffect(() => {
    const element = scroller.current;
    const position = activeNode ? nodePosition[activeNode] : undefined;
    if (!element || !position) return;
    const margin = 24;
    const inView =
      position.x - NODE_WIDTH / 2 >= element.scrollLeft + margin &&
      position.x + NODE_WIDTH / 2 <= element.scrollLeft + element.clientWidth - margin;
    if (inView) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    element.scrollTo({
      left: Math.max(0, position.x - element.clientWidth / 2),
      behavior: reduced ? "auto" : "smooth",
    });
  }, [activeNode]);

  const started = graphNodes.some(({ node }) => progress.states[node] !== "pending");
  // The refund wait comes from the case status, so it stays true while activity reconnects.
  const refundWaiting = activeNode === "execute_refund" && progress.states[activeNode] === "waiting";
  const caption = refundWaiting
    ? "處理結果已送出，等待退款系統執行。"
    : unavailable
      ? "活動紀錄暫時無法連線，正在重新連線。"
      : !started
        ? "等待 Agent 開始處理。"
        : activeNode
          ? `${nodeLabel(activeNode)} · ${stateText[progress.states[activeNode]]}`
          : "目前沒有執行中的步驟。";

  return (
    <Card aria-label="Agent 決策圖" className="shrink-0 overflow-hidden" role="region">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-stone-200 px-5 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-stone-950">Agent 決策圖</h2>
          <p aria-live="polite" className="mt-0.5 text-[11px] text-stone-500">
            {playback.remainingSteps > 0 && !unavailable ? `回放中 · ${caption}` : caption}
          </p>
        </div>
        <ul aria-label="迴圈次數上限" className="ml-auto flex flex-wrap gap-1.5">
          {loopBudgets.map(({ key, counter }) => {
            const { used, max } = progress.budgets[key];
            return (
              <li
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-2 py-1 font-mono text-[10px]",
                  used >= max
                    ? "border-red-300 text-red-700"
                    : used > 0
                      ? "border-violet-300 text-violet-700"
                      : "border-stone-200 text-stone-400",
                )}
                data-budget={key}
                key={key}
              >
                <span>{counter}</span>
                <span aria-hidden className="flex gap-0.5">
                  {Array.from({ length: max }, (_, index) => (
                    <i
                      className={cn(
                        "block h-2.5 w-1 rounded-[1px]",
                        index < used ? (used >= max ? "bg-red-500" : "bg-violet-500") : "bg-stone-200",
                      )}
                      key={index}
                    />
                  ))}
                </span>
                <strong className="tabular-nums">
                  {used}/{max}
                </strong>
              </li>
            );
          })}
        </ul>
      </div>
      {progress.latestNarration ? (
        <p aria-label="最新 AI 解說" className="border-b border-violet-100 bg-violet-50/70 px-5 py-2 text-xs text-violet-900">
          <strong className="mr-2 font-semibold">AI 解說 · {nodeLabel(progress.latestNarration.node)}</strong>
          {progress.latestNarration.text}
        </p>
      ) : null}
      <div className="overflow-x-auto" ref={scroller}>
        <div className="relative" style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}>
          <svg
            aria-hidden
            className="absolute inset-0"
            height={CANVAS_HEIGHT}
            viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
            width={CANVAS_WIDTH}
          >
            <defs>
              {(Object.keys(arrowColor) as EdgeTone[]).map((tone) => (
                <marker
                  id={`arrow-${tone}`}
                  key={tone}
                  markerHeight="6"
                  markerWidth="6"
                  orient="auto"
                  refX="7"
                  refY="4"
                  viewBox="0 0 8 8"
                >
                  <path d="M0,0 L8,4 L0,8 z" fill={arrowColor[tone]} />
                </marker>
              ))}
            </defs>
            {graphEdges.map((edge) => {
              const id = edgeId(edge.from, edge.to);
              const traversed = (progress.edgeTraversals[id] ?? 0) > 0;
              if (edge.kind === "failure" && !traversed) return null;
              const tone: EdgeTone = traversed ? edge.kind : edge.kind === "loop" || edge.kind === "skip" ? edge.kind : "idle";
              return (
                <path
                  className={cn(
                    "fill-none transition-[stroke,stroke-width] duration-500",
                    edgeStroke[tone],
                    !traversed && tone !== "idle" && "opacity-40",
                    progress.lastEdge === id && "edge-flow",
                  )}
                  d={pathFor(edge.from, edge.to)}
                  data-edge={id}
                  data-traversed={traversed}
                  key={id}
                  markerEnd={`url(#arrow-${traversed ? tone : "idle"})`}
                  strokeWidth={traversed ? 2.2 : 1.5}
                />
              );
            })}
            {edgeLabels.map(({ edge, x, y, text, budget }) => {
              const traversed = (progress.edgeTraversals[edge] ?? 0) > 0;
              const usage = budget ? progress.budgets[budget] : undefined;
              return (
                <text
                  className={cn("font-mono text-[10px]", traversed ? "fill-violet-600 font-semibold" : "fill-stone-400")}
                  key={edge}
                  textAnchor="middle"
                  x={x}
                  y={y}
                >
                  {usage ? `${usage.used}/${usage.max}` : text}
                </text>
              );
            })}
          </svg>
          {graphNodes.map(({ node, lane }) => {
            const position = nodePosition[node];
            const state = progress.states[node];
            const visits = progress.visits[node];
            const operations = visits.flatMap((visit) => visit.operations).slice(-8);
            const selected = selectedNode === node;
            return (
              <button
                aria-label={`${nodeLabel(node)}，${stateText[state]}${visits.length > 1 ? `，第 ${visits.length} 次` : ""}`}
                aria-pressed={selected}
                className={cn(
                  "absolute flex flex-col justify-center rounded-xl border px-2.5 text-left transition-[background-color,border-color,box-shadow,transform] duration-300 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2",
                  nodeStyle(state, lane),
                  selected && "ring-2 ring-stone-900 ring-offset-2",
                )}
                data-node={node}
                data-state={state}
                key={node}
                onClick={() => onSelectNode(node)}
                style={{
                  left: position.x - NODE_WIDTH / 2,
                  top: position.y - NODE_HEIGHT / 2,
                  width: NODE_WIDTH,
                  height: NODE_HEIGHT,
                }}
                type="button"
              >
                <strong className="block truncate text-xs">{nodeLabel(node)}</strong>
                <code className="mt-0.5 block truncate text-[9px] opacity-60">{node}</code>
                {visits.length > 1 ? (
                  <span
                    className="absolute -top-2 -right-2 grid h-5 min-w-5 place-items-center rounded-full bg-violet-600 px-1 text-[10px] font-bold text-white"
                    data-visits={visits.length}
                  >
                    {visits.length}
                  </span>
                ) : null}
                {operations.length ? (
                  <span aria-hidden className="absolute -bottom-1.5 left-2.5 flex gap-1">
                    {operations.map((operation) => (
                      <i
                        className={cn(
                          "block size-2 ring-2 ring-white",
                          operation.kind === "model" ? "rounded-[2px]" : "rounded-full",
                          operation.status === "running" && "tool-blink bg-orange-500",
                          operation.status === "ok" && "bg-emerald-500",
                          operation.status === "failed" && "bg-red-500",
                        )}
                        data-operation-status={operation.status}
                        key={operation.operationId}
                      />
                    ))}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-stone-100 px-5 py-2 text-[10px] text-stone-500">
        <Legend className="border-stone-200 bg-white" label="尚未執行" />
        <Legend className="border-orange-400 bg-orange-50" label="執行中" />
        <Legend className="border-dashed border-amber-400 bg-amber-50" label="等待中" />
        <Legend className="border-emerald-300 bg-white" label="已完成" />
        <Legend className="border-violet-300 bg-white" label="迴圈節點已完成" />
        <Legend className="border-red-300 bg-red-50" label="執行失敗" />
        <span className="flex items-center gap-1.5">
          <i className="block w-5 border-t-2 border-orange-500" /> 已走過
        </span>
        <span className="flex items-center gap-1.5">
          <i className="block w-5 border-t-2 border-dashed border-violet-500" /> 回頭邊
        </span>
        <span className="flex items-center gap-1.5">
          <i className="block size-2 rounded-full bg-emerald-500" /> 工具呼叫
        </span>
        <span className="flex items-center gap-1.5">
          <i className="block size-2 rounded-[2px] bg-emerald-500" /> 模型呼叫
        </span>
        <div aria-label="播放速度" className="ml-auto flex items-center gap-2" role="group">
          <span>播放速度</span>
          <span className="flex rounded-lg bg-stone-100 p-0.5">
            {speedOptions.map(({ speed, label }) => (
              <button
                aria-pressed={playback.speed === speed}
                className={cn(
                  "rounded-md px-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500",
                  playback.speed === speed ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800",
                )}
                key={speed}
                onClick={() => playback.onSpeedChange(speed)}
                type="button"
              >
                <span className="text-[10px] font-semibold">{label}</span>
              </button>
            ))}
          </span>
          {playback.remainingSteps > 0 ? (
            <button
              className="rounded-md border border-orange-200 bg-orange-50 px-2 py-0.5 text-orange-700 hover:bg-orange-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
              onClick={playback.onSkipToLatest}
              type="button"
            >
              <span className="text-[10px] font-semibold">跳到最新（還有 {playback.remainingSteps} 步）</span>
            </button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <i className={cn("block h-2.5 w-4 rounded-sm border", className)} /> {label}
    </span>
  );
}
