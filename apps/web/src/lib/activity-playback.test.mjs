import assert from "node:assert/strict";
import test from "node:test";

import { beatWeight, nextStepEnd, pendingSteps } from "./activity-playback.mjs";

const node = (name, phase, scope = "CASE") => ({ scope, node: name, payload: { type: "node", phase, name } });
const call = (name, type, phase, callName = "provider.call") => ({
  scope: "CASE",
  node: name,
  payload: { type, phase, name: callName },
});
const summary = (name) => ({ scope: "CASE", node: name, payload: { type: "node_summary", facts: {} } });

const stream = [
  node("parse_request", "STARTED"), // 0
  node("parse_request", "COMPLETED"), // 1
  summary("parse_request"), // 2
  node("load_case_context", "STARTED"), // 3
  call("load_case_context", "tool", "STARTED"), // 4
  node("distill_memory", "STARTED", "MEMORY"), // 5
  call("load_case_context", "tool", "COMPLETED"), // 6
  node("load_case_context", "COMPLETED"), // 7
  node("retrieve_policy", "STARTED"), // 8
  call("load_case_context", "model", "STARTED", "ACTIVITY_NARRATION"), // 9
];

test("beats end after a node starts and after each of its calls starts or finishes", () => {
  assert.equal(nextStepEnd(stream, 0), 1);
  assert.equal(nextStepEnd(stream, 1), 4);
  assert.equal(nextStepEnd(stream, 4), 5);
  // Activity outside the case run neither ends a beat nor is skipped over.
  assert.equal(nextStepEnd(stream, 5), 7);
  assert.equal(nextStepEnd(stream, 7), 9);
  // Narration's own model call is not a beat.
  assert.equal(nextStepEnd(stream, 9), stream.length);
});

test("a call beat holds half as long as a node beat", () => {
  assert.equal(beatWeight(stream[0]), 1);
  assert.equal(beatWeight(stream[4]), 0.5);
  assert.equal(beatWeight(stream[6]), 0.5);
  assert.equal(beatWeight(stream[9]), 1);
  assert.equal(beatWeight(undefined), 1);
});

test("pending steps count the node starts not yet shown, not the calls inside them", () => {
  assert.equal(pendingSteps(stream, 0), 3);
  assert.equal(pendingSteps(stream, 1), 2);
  assert.equal(pendingSteps(stream, 4), 1);
  assert.equal(pendingSteps(stream, stream.length), 0);
});

test("the API's refund step plays back like a case node", () => {
  const refund = [node("emit_resolution_handoff", "COMPLETED"), node("execute_refund", "STARTED", "REFUND")];
  assert.equal(nextStepEnd(refund, 0), 2);
  assert.equal(pendingSteps(refund, 0), 1);
});
