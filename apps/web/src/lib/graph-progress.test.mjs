import assert from "node:assert/strict";
import test from "node:test";

import { graphProgress, withRefundWait } from "./graph-progress.mjs";

let seq = 0;

/** @param {string} node @param {object} payload */
function activity(node, payload, { attempt = `${node}-1`, operation = `${attempt}-node`, eventId, scope = "CASE" } = {}) {
  seq += 1;
  return {
    seq,
    event_id: eventId ?? `event-${seq}`,
    case_ref: "CASE-1",
    run_id: "RUN-1",
    scope,
    node,
    attempt_id: attempt,
    operation_id: operation,
    occurred_at: "2026-09-11T00:00:00Z",
    payload,
  };
}

const started = (node, attempt) => activity(node, { type: "node", phase: "STARTED", name: node }, { attempt });
const ended = (node, attempt, phase = "COMPLETED") => activity(node, { type: "node", phase, name: node }, { attempt });
const summary = (node, attempt, next_node, eventId) =>
  activity(node, { type: "node_summary", facts: { next_node } }, { attempt, eventId });
/** A node attempt that ran to completion and routed to `next`. */
const completed = (node, attempt, next) => [started(node, attempt), ended(node, attempt), summary(node, attempt, next)];
const narration = (node, attempt, source, fields) =>
  activity(node, { type: "narration", source_event_id: source, ...fields }, { attempt });

test("intent snapshots stay with their attempt and deduplicate late replay", () => {
  const first = activity("parse_request", {type:"node_summary", facts:{}, intent_display:{
    requested_action:"REFUND", completeness:"INCOMPLETE", claimed_line_item_ids:[], missing_fields:["ITEMS"],
  }}, {attempt:"P1"});
  const second = activity("parse_request", {type:"node_summary", facts:{}, intent_display:{
    requested_action:"RETURN_AND_REFUND", completeness:"COMPLETE", claimed_line_item_ids:["LI-1"], missing_fields:[],
  }}, {attempt:"P2"});
  const progress = graphProgress([
    started("parse_request","P1"), first, ...completed("load_case_context","L1","parse_request"),
    started("parse_request","P2"), second, first,
  ]);
  assert.equal(progress.visits.parse_request.length, 2);
  assert.deepEqual(progress.visits.parse_request.map(v => v.intents.map(i => i.value.requested_action)),
    [["REFUND"], ["RETURN_AND_REFUND"]]);
});

test("a node resumed after a pause is one visit, and edges follow next_node", () => {
  const progress = graphProgress([
    ...completed("parse_request", "P1", "request_clarification"),
    started("request_clarification", "C1"),
    ended("request_clarification", "C1", "PAUSED"),
    ...completed("request_clarification", "C2", "parse_request"),
    started("parse_request", "P2"),
  ]);

  assert.deepEqual(progress.visits.request_clarification.map((visit) => visit.attemptIds), [["C1", "C2"]]);
  assert.deepEqual(progress.budgets.clarification, { used: 1, max: 2 });
  assert.deepEqual(progress.edgeTraversals, {
    "parse_request>request_clarification": 1,
    "request_clarification>parse_request": 1,
  });
  assert.equal(progress.lastEdge, "request_clarification>parse_request");
  assert.equal(progress.visits.parse_request.length, 2);
  assert.equal(progress.activeNode, "parse_request");
});

test("a paused node is waiting, not active, so the agent is never shown as working", () => {
  const progress = graphProgress([started("request_evidence", "E1"), ended("request_evidence", "E1", "PAUSED")]);

  assert.equal(progress.states.request_evidence, "waiting");
  assert.equal(progress.activeNode, "request_evidence");
});

test("await_human_review re-entering itself after submitting is one visit without a drawn edge", () => {
  const progress = graphProgress([
    ...completed("await_human_review", "H1", "await_human_review"),
    started("await_human_review", "H2"),
    ended("await_human_review", "H2", "PAUSED"),
  ]);

  assert.equal(progress.visits.await_human_review.length, 1);
  assert.deepEqual(progress.edgeTraversals, {});
  assert.equal(progress.states.await_human_review, "waiting");
});

test("edges come only from next_node on a graph edge, never from arrival order", () => {
  const progress = graphProgress([
    ...completed("parse_request", "P1", "reviewer"),
    started("load_case_context", "L1"),
  ]);

  assert.deepEqual(progress.edgeTraversals, {});
  assert.equal(progress.lastEdge, undefined);
});

test("activity for an unseen attempt still counts its visit when STARTED was lost", () => {
  const progress = graphProgress([
    ...completed("parse_request", "P1", "load_case_context"),
    ended("load_case_context", "L1"),
    summary("load_case_context", "L1", "retrieve_policy"),
  ]);

  assert.equal(progress.visits.load_case_context.length, 1);
  assert.equal(progress.states.load_case_context, "done");
  // Nothing is running any more, but the last node that moved stays followable.
  assert.equal(progress.activeNode, undefined);
  assert.equal(progress.lastNode, "load_case_context");
  assert.equal(progress.edgeTraversals["load_case_context>retrieve_policy"], 1);
});

test("budgets count loop visits and the verification FAIL route", () => {
  const progress = graphProgress([
    ...completed("propose_decision", "D1", "external_verification"),
    ...completed("external_verification", "V1", "propose_decision"),
    ...completed("propose_decision", "D2", "external_verification"),
    ...completed("external_verification", "V2", "reviewer"),
    ...completed("reviewer", "R1", "record_revision_event"),
    ...completed("record_revision_event", "X1", "propose_decision"),
    started("propose_decision", "D3"),
  ]);

  assert.deepEqual(progress.budgets.verification, { used: 1, max: 2 });
  assert.deepEqual(progress.budgets.revision, { used: 1, max: 3 });
  assert.deepEqual(progress.budgets.propose, { used: 3, max: 6 });
});

test("tool and model operations pair by operation id onto their attempt", () => {
  const progress = graphProgress([
    started("retrieve_policy", "T1"),
    activity("retrieve_policy", { type: "tool", phase: "STARTED", name: "policy_provider.retrieve_policy" }, { attempt: "T1", operation: "op-1" }),
    activity("retrieve_policy", { type: "model", phase: "STARTED", name: "ASSESS" }, { attempt: "T1", operation: "op-2" }),
    activity(
      "retrieve_policy",
      { type: "tool", phase: "COMPLETED", name: "policy_provider.retrieve_policy", duration_ms: 810, facts: { count: 3 } },
      { attempt: "T1", operation: "op-1" },
    ),
  ]);

  assert.deepEqual(progress.visits.retrieve_policy[0].operations, [
    { operationId: "op-1", kind: "tool", name: "policy_provider.retrieve_policy", status: "ok", durationMs: 810, facts: { count: 3 } },
    { operationId: "op-2", kind: "model", name: "ASSESS", status: "running" },
  ]);
});

test("narration's own late model call is not counted as the node's operation", () => {
  const progress = graphProgress([
    ...completed("reviewer", "R1", "record_revision_event"),
    activity("reviewer", { type: "model", phase: "STARTED", name: "ACTIVITY_NARRATION" }, { attempt: "R1", operation: "op-n" }),
    activity("reviewer", { type: "model", phase: "FAILED", name: "ACTIVITY_NARRATION" }, { attempt: "R1", operation: "op-n" }),
  ]);

  assert.deepEqual(progress.visits.reviewer[0].operations, []);
  assert.equal(progress.states.reviewer, "done");
});

test("completed narration attaches to its summary's visit and wins over unavailable results", () => {
  const progress = graphProgress([
    started("reviewer", "R1"),
    ended("reviewer", "R1"),
    summary("reviewer", "R1", "record_revision_event", "SUMMARY-1"),
    narration("reviewer", "R1", "SUMMARY-1", { status: "UNAVAILABLE", error_code: "NARRATION_UNAVAILABLE" }),
    narration("reviewer", "R1", "SUMMARY-1", { status: "COMPLETED", text: "複核要求修訂提案。" }),
    narration("reviewer", "R1", "SUMMARY-1", { status: "UNAVAILABLE", error_code: "NARRATION_UNAVAILABLE" }),
  ]);

  assert.deepEqual(progress.visits.reviewer[0].narration, { status: "completed", text: "複核要求修訂提案。" });
  assert.deepEqual(progress.latestNarration, { node: "reviewer", text: "複核要求修訂提案。" });
});

test("offline demo narration is disabled, distinct from a failed narration", () => {
  const progress = graphProgress([
    ...completed("parse_request", "P1", "load_case_context").slice(0, 2),
    summary("parse_request", "P1", "load_case_context", "SUMMARY-P"),
    narration("parse_request", "P1", "SUMMARY-P", { status: "UNAVAILABLE", error_code: "NARRATION_DISABLED_OFFLINE_DEMO" }),
    ...completed("load_case_context", "L1", "retrieve_policy").slice(0, 2),
    summary("load_case_context", "L1", "retrieve_policy", "SUMMARY-L"),
    narration("load_case_context", "L1", "SUMMARY-L", { status: "UNAVAILABLE", error_code: "NARRATION_UNAVAILABLE" }),
  ]);

  assert.deepEqual(progress.visits.parse_request[0].narration, { status: "disabled" });
  assert.deepEqual(progress.visits.load_case_context[0].narration, { status: "unavailable" });
  assert.equal(progress.latestNarration, undefined);
});

test("a failed node is failed, and activity outside the case run is ignored", () => {
  const progress = graphProgress([
    started("reviewer", "R1"),
    ended("reviewer", "R1", "FAILED"),
    activity("parse_request", { type: "node", phase: "STARTED", name: "execute_refund" }, { scope: "REFUND" }),
  ]);

  assert.equal(progress.states.reviewer, "failed");
  assert.equal(progress.activeNode, undefined);
  assert.equal(progress.states.parse_request, "pending");
});

const refund = (payload, fields = {}) =>
  activity("execute_refund", payload, { attempt: "RF1", scope: "REFUND", ...fields });

test("the API's refund run joins the stage after the agent's resolution", () => {
  const progress = graphProgress([
    ...completed("emit_resolution_handoff", "O1", "__end__"),
    refund({ type: "node", phase: "STARTED", name: "execute_refund" }),
    refund({ type: "tool", phase: "STARTED", name: "refund_execution_provider.execute" }, { operation: "op-r" }),
    refund({ type: "tool", phase: "COMPLETED", name: "refund_execution_provider.execute", duration_ms: 90, facts: { outcome: "SUCCEEDED" } }, { operation: "op-r" }),
    refund({ type: "node", phase: "COMPLETED", name: "execute_refund" }),
    refund({ type: "node_summary", facts: { outcome: "SUCCEEDED" } }),
  ]);

  assert.equal(progress.states.execute_refund, "done");
  assert.equal(progress.edgeTraversals["emit_resolution_handoff>execute_refund"], 1);
  assert.equal(progress.visits.execute_refund[0].operations[0].status, "ok");
});

test("a refund the API rejected is shown as failed, and retries stay one visit", () => {
  const progress = graphProgress([
    refund({ type: "node", phase: "STARTED", name: "execute_refund" }, { attempt: "RF1" }),
    refund({ type: "node", phase: "FAILED", name: "execute_refund" }, { attempt: "RF1" }),
    refund({ type: "node", phase: "STARTED", name: "execute_refund" }, { attempt: "RF2" }),
    refund({ type: "node", phase: "COMPLETED", name: "execute_refund" }, { attempt: "RF2" }),
    refund({ type: "node_summary", facts: { outcome: "REJECTED" } }, { attempt: "RF2" }),
  ]);

  assert.equal(progress.states.execute_refund, "failed");
  assert.equal(progress.visits.execute_refund.length, 1);
  assert.equal(progress.edgeTraversals["emit_resolution_handoff>execute_refund"], 1);
});

test("a case left EXECUTING shows the refund step as the waiting, current step", () => {
  const progress = graphProgress(completed("emit_resolution_handoff", "O1", "__end__"));

  const waiting = withRefundWait(progress, "EXECUTING");
  assert.equal(waiting.states.execute_refund, "waiting");
  assert.equal(waiting.activeNode, "execute_refund");
  // Other statuses, or a refund that already started, keep the real projection.
  assert.equal(withRefundWait(progress, "RESOLVED"), progress);
  const started = graphProgress([refund({ type: "node", phase: "STARTED", name: "execute_refund" })]);
  assert.equal(withRefundWait(started, "EXECUTING"), started);
});
