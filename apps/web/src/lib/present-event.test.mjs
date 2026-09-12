import assert from "node:assert/strict";
import test from "node:test";

import { nodeLabel, parseAgentEvent, presentEvent, statusLabel } from "./present-event.mjs";

test("presents backend state without leaking implementation labels", () => {
  const presentation = presentEvent({
    case_ref: "CASE-1",
    seq: 1,
    ts: "2026-09-08T00:00:00Z",
    node: "reviewer",
    type: "state_change",
    payload: {
      from_status: "OBSERVING",
      to_status: "AWAITING_HUMAN_REVIEW",
      reason: "High value item",
    },
  });

  assert.equal(presentation.title, "等待人工審核");
  assert.equal(presentation.detail, "High value item");
  assert.equal(statusLabel("RESOLVED"), "案件已完成");
});

test("ignores EventSource transport errors without domain event data", () => {
  assert.equal(parseAgentEvent({}), undefined);
  assert.equal(
    parseAgentEvent({
      data: JSON.stringify({
        case_ref: "CASE-1",
        seq: 2,
        ts: "2026-09-08T00:00:00Z",
        node: "reviewer",
        type: "error",
        payload: { code: "FAILED", message: "Unable to continue", retryable: false },
      }),
    })?.type,
    "error",
  );
});

test("names graph nodes, including the automation terminal", () => {
  assert.equal(nodeLabel("terminate_automation"), "異常終止自動處理");
  assert.equal(presentEvent({ type: "node_enter", node: "terminate_automation" }).title, "異常終止自動處理");
});

test("latest memory result replaces scores on empty/unavailable/replayed retrieval", async () => {
  const { latestMemoryRetrieval } = await import("./present-event.mjs");
  const hit = { type: "memory_retrieval", node: "retrieve_memory", payload: {
    status: "OK", query_summary: "first", hits: [
      { memory: { memory_id: "LOW", confidence: 0.1 }, similarity: 0.9 },
      { memory: { memory_id: "HIGH", confidence: 0.9 }, similarity: 0.7 },
    ],
  } };
  assert.deepEqual(latestMemoryRetrieval([hit]), hit.payload);
  const empty = { ...hit, payload: { status: "OK", query_summary: "new", hits: [] } };
  const unavailable = { ...hit, payload: { status: "UNAVAILABLE", error_code: "SUMMARY_UNAVAILABLE", hits: [] } };
  assert.deepEqual(latestMemoryRetrieval([hit, empty]), empty.payload);
  assert.deepEqual(latestMemoryRetrieval([hit, empty, unavailable]), unavailable.payload);
  assert.equal(latestMemoryRetrieval([hit, { type: "node_enter", node: "prepare_memory_query" }]), undefined);
});
