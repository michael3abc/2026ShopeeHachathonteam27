/**
 * Topology of the case graph as observed on the activity stream, following
 * docs/spec/01-agent-graph.md, plus the API's refund execution for the case.
 * Layout belongs to the stage component.
 *
 * `distill_memory` is intentionally absent: it runs in the memory worker after
 * the case run, reported under scope MEMORY, so it never lights up on this graph.
 */

/** @typedef {import("../contracts/agent-event").GraphNodeName} GraphNodeName */
/** @typedef {GraphNodeName | "execute_refund"} StageNodeName */
/** @typedef {"main" | "loop" | "human" | "memory" | "refund" | "terminal"} NodeLane */
/** @typedef {"forward" | "loop" | "skip" | "failure"} EdgeKind */

/** @type {readonly { node: StageNodeName, lane: NodeLane }[]} */
export const graphNodes = [
  { node: "parse_request", lane: "main" },
  { node: "load_case_context", lane: "main" },
  { node: "retrieve_policy", lane: "main" },
  { node: "prepare_memory_query", lane: "main" },
  { node: "retrieve_memory", lane: "main" },
  { node: "assess_case", lane: "main" },
  { node: "propose_decision", lane: "main" },
  { node: "external_verification", lane: "main" },
  { node: "reviewer", lane: "main" },
  { node: "emit_resolution_handoff", lane: "main" },
  { node: "execute_refund", lane: "refund" },
  { node: "request_clarification", lane: "loop" },
  { node: "request_evidence", lane: "loop" },
  { node: "record_revision_event", lane: "loop" },
  { node: "await_human_review", lane: "human" },
  { node: "enqueue_memory_distillation", lane: "memory" },
  { node: "terminate_automation", lane: "terminal" },
];

/** @type {readonly { from: StageNodeName, to: StageNodeName, kind: EdgeKind }[]} */
export const graphEdges = [
  { from: "parse_request", to: "load_case_context", kind: "forward" },
  { from: "load_case_context", to: "retrieve_policy", kind: "forward" },
  { from: "retrieve_policy", to: "prepare_memory_query", kind: "forward" },
  { from: "prepare_memory_query", to: "retrieve_memory", kind: "forward" },
  { from: "retrieve_memory", to: "assess_case", kind: "forward" },
  { from: "assess_case", to: "propose_decision", kind: "forward" },
  { from: "propose_decision", to: "external_verification", kind: "forward" },
  { from: "external_verification", to: "reviewer", kind: "forward" },
  { from: "reviewer", to: "emit_resolution_handoff", kind: "forward" },
  { from: "reviewer", to: "await_human_review", kind: "forward" },
  { from: "await_human_review", to: "emit_resolution_handoff", kind: "forward" },
  { from: "emit_resolution_handoff", to: "enqueue_memory_distillation", kind: "forward" },
  // The API executes the refund after the agent emits its resolution.
  { from: "emit_resolution_handoff", to: "execute_refund", kind: "forward" },
  // Memory summary unavailable: assessment continues without retrieval.
  { from: "prepare_memory_query", to: "assess_case", kind: "skip" },
  { from: "parse_request", to: "request_clarification", kind: "loop" },
  { from: "request_clarification", to: "parse_request", kind: "loop" },
  // Line items could not be bound until the order snapshot was loaded.
  { from: "load_case_context", to: "parse_request", kind: "loop" },
  { from: "assess_case", to: "request_evidence", kind: "loop" },
  { from: "propose_decision", to: "request_evidence", kind: "loop" },
  { from: "request_evidence", to: "prepare_memory_query", kind: "loop" },
  { from: "external_verification", to: "propose_decision", kind: "loop" },
  { from: "reviewer", to: "record_revision_event", kind: "loop" },
  { from: "record_revision_event", to: "propose_decision", kind: "loop" },
  ...(
    /** @type {const} */ ([
      "parse_request",
      "load_case_context",
      "retrieve_policy",
      "prepare_memory_query",
      "assess_case",
      "request_evidence",
      "propose_decision",
      "external_verification",
      "reviewer",
    ])
  ).map((from) => ({ from, to: /** @type {const} */ ("terminate_automation"), kind: /** @type {const} */ ("failure") })),
];

/**
 * Graph-owned loop counters. Each is derived from what the event stream shows:
 * entering a node, or traversing one routing edge.
 * @type {readonly { key: string, counter: string, max: number, node?: GraphNodeName, edge?: string }[]}
 */
export const loopBudgets = [
  { key: "clarification", counter: "clarification_round", max: 2, node: "request_clarification" },
  { key: "evidence", counter: "evidence_round", max: 2, node: "request_evidence" },
  { key: "verification", counter: "verification_round", max: 2, edge: "external_verification>propose_decision" },
  { key: "revision", counter: "revision_round", max: 3, node: "record_revision_event" },
  { key: "propose", counter: "propose_round", max: 6, node: "propose_decision" },
];

/**
 * @param {string} from
 * @param {string} to
 */
export function edgeId(from, to) {
  return `${from}>${to}`;
}

export const REFUND_NODE = "execute_refund";

/**
 * The stage draws the case run plus the API's refund execution for it; memory work
 * and other background scopes stay off the graph.
 * @param {import("../contracts/activity-event").ActivityEvent} activity
 */
export function isStageActivity(activity) {
  return activity.scope === "CASE" || (activity.scope === "REFUND" && activity.node === REFUND_NODE);
}
