import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const data = JSON.parse(
  await readFile(new URL("./architecture-data.json", import.meta.url), "utf8"),
);
const graphEdges = new Set(
  data.edges.filter((e) => e.kind === "graph").map((e) => `${e.from}>${e.to}`),
);
for (const edge of [
  "parse_request>retrieve_policy",
  "request_clarification>terminate_automation",
  "await_human_review>await_human_review",
  "record_revision_event>terminate_automation",
  "retrieve_memory>terminate_automation",
  "assess_case>evaluate_policy",
  "evaluate_policy>confirm_policy_path",
  "confirm_policy_path>retrieve_policy",
  "emit_resolution_handoff>enqueue_memory_distillation",
  "enqueue_memory_distillation>__end__",
]) {
  assert(
    graphEdges.has(edge),
    `Real routes omitted by the old UI map must be retained: ${edge}`,
  );
}
assert(
  !data.graph.nodes.execute_refund,
  "API refund must not masquerade as a Graph node",
);
assert(
  !data.graph.nodes.distill_memory,
  "Background distillation must stay outside the case Graph",
);
assert(
  !graphEdges.has("parse_request>reviewer"),
  "Common destinations must not become spurious reachable edges",
);
assert.equal(data.llmCalls.length, 8);
assert.equal(
  data.llmCalls.filter((c) => c.scope.startsWith("案件 Graph")).length,
  5,
);
assert(
  data.llmCalls
    .find((c) => c.task === "REVIEW")
    .promptText.includes("Reviewer"),
);
assert(
  data.entities
    .find((e) => e.id === "propose_decision")
    .writes.includes("pending_review_result"),
);
assert.equal(data.baseline.profiles.agent, "integrated-compass");
assert(data.entities.find((e) => e.id === "evaluate_policy"));
assert(data.entities.find((e) => e.id === "confirm_policy_path"));
assert(
  data.schema.tables.some(
    (t) => t.name === "cases" && t.columns.includes("thread_id"),
  ),
);
assert(data.schema.tables.some((t) => t.foreignKeys.length));
for (const s of data.scenarios) {
  assert.equal(s.provenance, "Illustrative");
  assert(s.steps.length > 0);
  for (const step of s.steps) assert.equal(step.duration, null);
}
const html = await readFile(
  new URL("./offline/index.html", import.meta.url),
  "utf8",
);
assert.equal(
  html,
  await readFile(new URL("./dist/index.html", import.meta.url), "utf8"),
);
assert(
  !/<script[^>]+src=|<link[^>]+href=|type=["']module/i.test(html),
  "Offline bundle must be self contained",
);
assert(
  !/fetch\s*\(/.test(
    await readFile(new URL("./src/app.js", import.meta.url), "utf8"),
  ),
  "Explorer may not call runtime services",
);
assert(!html.includes("/* DATA */"));
console.log(
  "Content regression checks passed: graph boundary, routing, LLM call inventory, provenance, DB ownership and offline bundle parity.",
);
