import { edgeId, graphEdges, graphNodes, isStageActivity, loopBudgets, REFUND_NODE } from "./case-graph.mjs";

const knownEdges = new Set(graphEdges.map(({ from, to }) => edgeId(from, to)));
// Narration's own model call reuses the source node's attempt but runs after the node
// finished; counting it would show a completed node calling a model again.
const NARRATION_TASK = "ACTIVITY_NARRATION";
const OFFLINE_NARRATION = "NARRATION_DISABLED_OFFLINE_DEMO";

/**
 * @typedef {import("../contracts/activity-event").ActivityEvent} ActivityEvent
 * @typedef {import("../contracts/activity-event").ActivityFacts} ActivityFacts
 * @typedef {"pending" | "active" | "waiting" | "done" | "failed"} NodeState
 * @typedef {{
 *   operationId: string,
 *   kind: "tool" | "model",
 *   name: string,
 *   status: "running" | "ok" | "failed",
 *   durationMs?: number | null,
 *   facts?: ActivityFacts,
 * }} OperationRun
 * @typedef {{ status: "completed", text: string } | { status: "disabled" } | { status: "unavailable" }} VisitNarration
 * @typedef {{ attemptIds: string[], operations: OperationRun[], narration?: VisitNarration, intents?: {id: string, value: import("../contracts/activity-event").IntentDisplay}[] }} NodeVisit
 * @typedef {{ used: number, max: number }} BudgetUsage
 */

/**
 * Reduce the case activity stream into the cyclic graph shown on the stage.
 *
 * Edges come from each completed node's `next_node`, never from arrival order:
 * activity `seq` is receipt order, not causal order. A node resumed after a pause
 * starts a new attempt, and `await_human_review` re-enters itself after submitting
 * for review, so consecutive attempts of the same node are merged into one visit.
 * Activity may be lost before it reaches the API, so any event of an unseen attempt
 * opens (or joins) its visit instead of requiring the STARTED event.
 *
 * @param {ActivityEvent[]} activities
 * @returns {{
 *   activeNode: string | undefined,
 *   lastNode: string | undefined,
 *   states: Record<string, NodeState>,
 *   visits: Record<string, NodeVisit[]>,
 *   edgeTraversals: Record<string, number>,
 *   lastEdge: string | undefined,
 *   latestNarration: { node: string, text: string } | undefined,
 *   budgets: Record<string, BudgetUsage>,
 * }}
 */
export function graphProgress(activities) {
  /** @type {Record<string, NodeState>} */
  const states = Object.fromEntries(graphNodes.map(({ node }) => [node, "pending"]));
  /** @type {Record<string, NodeVisit[]>} */
  const visits = Object.fromEntries(graphNodes.map(({ node }) => [node, []]));
  /** @type {Map<string, NodeVisit>} */
  const visitByAttempt = new Map();
  /** @type {Map<string, NodeVisit>} */
  const visitBySummary = new Map();
  /** @type {Record<string, number>} */
  const edgeTraversals = {};
  /** @type {string | undefined} */
  let activeNode;
  /** @type {string | undefined} */
  let lastStartedNode;
  /** @type {string | undefined} */
  let lastNode;
  /** @type {string | undefined} */
  let lastEdge;
  /** @type {{ node: string, text: string } | undefined} */
  let latestNarration;

  /**
   * @param {string} node
   * @param {string} attemptId
   * @param {string} runId
   */
  function visitFor(node, attemptId, runId) {
    const key = runId + ":" + node + ":" + attemptId;
    const known = visitByAttempt.get(key);
    if (known) return known;
    if (node !== lastStartedNode) {
      visits[node].push({ attemptIds: [], operations: [] });
      lastStartedNode = node;
    }
    const visit = visits[node][visits[node].length - 1];
    visit.attemptIds.push(attemptId);
    visitByAttempt.set(key, visit);
    return visit;
  }

  /** @param {string} id */
  function traverse(id) {
    if (!knownEdges.has(id)) return;
    edgeTraversals[id] = (edgeTraversals[id] ?? 0) + 1;
    lastEdge = id;
  }

  for (const activity of activities) {
    if (!isStageActivity(activity) || !(activity.node in states)) continue;
    const { node, payload } = activity;
    if (payload.type === "background") continue;
    if (payload.type === "model" && payload.name === NARRATION_TASK) continue;

    if (payload.type === "narration") {
      const visit = visitBySummary.get(payload.source_event_id);
      if (!visit) continue;
      if (payload.status === "COMPLETED" && payload.text) {
        visit.narration = { status: "completed", text: payload.text };
        latestNarration = { node, text: payload.text };
      } else if (visit.narration?.status !== "completed") {
        visit.narration = { status: payload.error_code === OFFLINE_NARRATION ? "disabled" : "unavailable" };
      }
      continue;
    }

    const visit = visitFor(node, activity.attempt_id, activity.run_id);
    if (payload.type === "node") {
      lastNode = node;
      if (payload.phase === "STARTED") {
        states[node] = "active";
        activeNode = node;
        // The API starts the refund after the agent's resolution; no summary names this edge.
        if (node === REFUND_NODE && visit.attemptIds.length === 1) {
          traverse(edgeId("emit_resolution_handoff", REFUND_NODE));
        }
      } else {
        // Paused for a person: shown apart from "active" so the UI never claims the agent is working.
        states[node] =
          payload.phase === "COMPLETED" ? "done" : payload.phase === "PAUSED" ? "waiting" : "failed";
        if (activeNode === node && states[node] !== "waiting") activeNode = undefined;
      }
    } else if (payload.type === "tool" || payload.type === "model") {
      if (payload.phase === "STARTED") {
        visit.operations.push({
          operationId: activity.operation_id,
          kind: payload.type,
          name: payload.name,
          status: "running",
        });
      } else {
        const run = visit.operations.find((operation) => operation.operationId === activity.operation_id);
        if (run) {
          run.status = payload.phase === "COMPLETED" ? "ok" : "failed";
          run.durationMs = payload.duration_ms;
          run.facts = payload.facts;
        }
      }
    } else if (payload.type === "node_summary") {
      if (payload.intent_display) {
        visit.intents ??= [];
        const id = activity.run_id + ":" + activity.attempt_id + ":" + activity.operation_id;
        if (!visit.intents.some(item => item.id === id)) visit.intents.push({id, value: payload.intent_display});
      }
      visitBySummary.set(activity.event_id, visit);
      if (payload.facts.next_node) traverse(edgeId(node, payload.facts.next_node));
      // A refund the API rejected still finished its step; show it as the failure it is.
      if (node === REFUND_NODE && payload.facts.outcome === "REJECTED") states[node] = "failed";
    }
  }

  /** @type {Record<string, BudgetUsage>} */
  const budgets = Object.fromEntries(
    loopBudgets.map(({ key, max, node, edge }) => [
      key,
      { used: node ? visits[node].length : (edgeTraversals[edge ?? ""] ?? 0), max },
    ]),
  );

  return { activeNode, lastNode, states, visits, edgeTraversals, lastEdge, latestNarration, budgets };
}

/**
 * Without a refund executor the API never starts the refund, so the case stays
 * EXECUTING with no refund activity at all. Show the refund step as the waiting,
 * current step so the stage explains where the case stopped.
 *
 * @param {ReturnType<typeof graphProgress>} progress
 * @param {string} caseStatus
 * @returns {ReturnType<typeof graphProgress>}
 */
export function withRefundWait(progress, caseStatus) {
  if (caseStatus !== "EXECUTING" || progress.states[REFUND_NODE] !== "pending") return progress;
  return { ...progress, activeNode: REFUND_NODE, states: { ...progress.states, [REFUND_NODE]: "waiting" } };
}
