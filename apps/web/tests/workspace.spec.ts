import { expect, test, type Page } from "@playwright/test";
import type { CaseDetail, OrderLineItem, ProposedDecisionHandoff } from "../src/contracts/case-detail";

const humanCase: CaseDetail = {
  case_ref: "CASE-BROWSER",
  order_ref: "ORDER-DEMO-BROWSER",
  user_ref: "demo_customer",
  status: "AWAITING_HUMAN_REVIEW",
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
  human_review: {
    case_ref: "CASE-BROWSER", handoff_id: "HANDOFF-BROWSER",
    action: "FULL_REFUND", amount: "1200", currency: "TWD",
    refund_scope: { line_item_ids: ["LI-DEMO"] },
    routing_reason: "REVISION_BUDGET_EXCEEDED",
    review_result: {
      verdict: "REVISE", reviewer_prompt_version: "reviewer:2.0", reviewed_at: "2026-09-09T00:00:00Z",
      reviewer_claim_findings: [{ claim_id: "ITEM_PHYSICALLY_DAMAGED", subject: "LI-DEMO",
        status: "SUPPORTED", explanation: "照片顯示外觀損壞。" }],
      revision_reasons: [{ code: "RETURN_REQUIREMENT_INCONSISTENT", subject: "LI-DEMO",
        message: "外觀損壞不能證明無法修復。", required_change: "補充免退貨的依據或修正退貨要求。",
        policy_refs: ["POLICY:v1#damaged"], evidence_refs: ["EV-DEMO"] }],
    },
    rationale_summary: "Required claims are supported.",
    return_decision: {
      source: "MODEL_JUDGMENT",
      requirement: { required: false, reason_code: "ITEM_UNSALVAGEABLE" },
    },
  },
};

const review = humanCase.human_review!;
review.dossier = {
  claim_registry_version: "claim-registry:1.0",
  claimed_line_item_ids: ["LI-DEMO", "LI-OTHER"],
  order_snapshot: { order_snapshot_ref: "ORDER@1", order_ref: humanCase.order_ref, snapshot_version: 1,
    captured_at: humanCase.created_at, delivered_at: humanCase.created_at, currency: "TWD",
    refundable_amount_max: "1500", already_refunded_amount: "0",
    line_items: ["LI-DEMO", "LI-OTHER"].map<OrderLineItem>(id => ({line_item_id: id, sku_ref: id, title: id, category_ref: "electronics", quantity: 1, refundable_amount: id === "LI-DEMO" ? "1200" : "300"})) as [OrderLineItem, ...OrderLineItem[]],
  },
  policy_bundle: {policy_bundle_version: "POLICY:v1", retrieval_status: "OK", retrieved_at: humanCase.created_at, clauses: []},
  proposal_history: [0, 1, 2, 3].map<ProposedDecisionHandoff>(round => ({
    handoff_id: `HANDOFF-${round}`, handoff_version: "1.0", case_ref: humanCase.case_ref,
    order_snapshot_ref: "ORDER@1", policy_bundle_version: "POLICY:v1", claim_registry_version: "claim-registry:1.0",
    proposed_decision: {action: "FULL_REFUND", amount: "1200", currency: "TWD", refund_scope: {line_item_ids: ["LI-DEMO"]}, reason_code: "ITEM_DAMAGED", policy_refs: ["POLICY:v1#damaged"], return_decision: {source: "MODEL_JUDGMENT", requirement: {required: false, reason_code: "ITEM_UNSALVAGEABLE"}}},
    evidence_bundle: [], policy_refs: ["POLICY:v1#damaged"], rationale_summary: `第 ${round + 1} 輪提案`, revision_round: round, agent_prompt_version: "resolver:1.0",
  })) as NonNullable<typeof review.dossier>["proposal_history"],
  review_history: [review.review_result, review.review_result, review.review_result, review.review_result],
};

/** Serve a fixed activity history and an idle activity stream for CASE-BROWSER. */
async function routeActivities(page: Page, activities: object[] = []) {
  await page.route(/\/backend\/cases\/CASE-BROWSER\/activities\?/, (route) =>
    route.fulfill({ json: { events: activities, next_cursor: activities.length, has_more: false } }),
  );
  await page.route(/\/backend\/cases\/CASE-BROWSER\/activities\/stream/, (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": keep-alive\n\n" }),
  );
}

test.beforeEach(async ({ page }) => {
  await routeActivities(page);
});

for (const decision of ["REJECT"] as const) {
  test(`Human ${decision} sends only the shared review contract`, async ({ page }) => {
    let detail = structuredClone(humanCase);
    await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
      route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }),
    );
    await page.route("**/backend/cases/CASE-BROWSER", (route) => route.fulfill({ json: detail }));
    await page.route("**/backend/cases/CASE-BROWSER/review", (route) => {
      expect(route.request().postDataJSON()).toEqual({
        decision, review_note: "已確認照片與政策", reviewer_id: "demo_reviewer", handoff_id: "HANDOFF-BROWSER",
      });
      detail = { ...detail, status: "OBSERVING" };
      return route.fulfill({ json: detail });
    });
    await page.goto("/cases/CASE-BROWSER");
    const button = page.getByRole("button", { name: "決定不退款", exact: true });
    await expect(button).toBeDisabled();
    await page.getByLabel("人工審核理由").fill("已確認照片與政策");
    await button.click();
    await expect(page.getByText("Agent 正在處理下一步")).toBeVisible();
    await expect(button).toHaveCount(0);
  });
}

test("review failure leaves the case awaiting review and displays the error", async ({ page }) => {
  await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }),
  );
  await page.route("**/backend/cases/CASE-BROWSER", (route) => route.fulfill({ json: humanCase }));
  await page.route("**/backend/cases/CASE-BROWSER/review", (route) =>
    route.fulfill({ status: 503, json: { detail: "Review service unavailable" } }),
  );
  await page.goto("/cases/CASE-BROWSER");
  await page.getByLabel("人工審核理由").fill("已確認照片與政策");
  await page.getByRole("button", { name: "決定不退款" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Review service unavailable" })).toHaveText("Review service unavailable");
  await expect(page.getByLabel("人工審核理由")).toHaveValue("已確認照片與政策");
  await expect(page.getByRole("button", { name: "決定不退款" })).toBeEnabled();
});

test("evidence submission preserves the artifact reference and resumes observation", async ({ page }) => {
  let detail: CaseDetail = {
    ...humanCase, status: "AWAITING_EVIDENCE", human_review: null,
    evidence_request: {
      case_ref: humanCase.case_ref, request_id: "REQUEST-BROWSER",
      user_message: "請補上外箱與商品照片", accepted_evidence_types: ["IMAGE"],
      missing_claims: [{ claim_id: "DAMAGE_PRESENT_ON_ARRIVAL", subject: "LI-DEMO" }],
      policy_refs: ["POLICY:v1#damaged"],
    },
  };
  await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }),
  );
  await page.route("**/backend/cases/CASE-BROWSER", (route) => route.fulfill({ json: detail }));
  await page.route("**/backend/cases/CASE-BROWSER/messages", (route) => {
    expect(route.request().postDataJSON()).toEqual({
      message: "外箱與商品照片", attached_artifact_refs: ["artifact://demo/damage"],
    });
    detail = { ...detail, status: "OBSERVING", evidence_request: null };
    return route.fulfill({ json: detail });
  });
  await page.goto("/cases/CASE-BROWSER");
  await page.getByLabel("證據檔案編號").fill("artifact://demo/damage");
  await page.getByLabel("補充案件說明").fill("外箱與商品照片");
  await page.getByRole("button", { name: "送出", exact: true }).click();
  await expect(page.getByText("Agent 正在處理下一步")).toBeVisible();
  await expect(page.getByLabel("補充案件說明")).toBeDisabled();
});


test("amount authorization shows approved review without invented objections after refresh", async ({ page }) => {
  const detail = structuredClone(humanCase);
  const human = detail.human_review!;
  human.routing_reason = "HIGH_VALUE_ITEM";
  human.review_result = {verdict: "APPROVE", reviewer_prompt_version: "reviewer:2.0",
    reviewed_at: detail.updated_at, reviewer_claim_findings: human.review_result.reviewer_claim_findings};
  const dossier = human.dossier!;
  dossier.routing_reason = "HIGH_VALUE_ITEM";
  dossier.review_gate = {config_version: "test:1", config_hash: "0".repeat(64), status: "HUMAN_REQUIRED",
    amount: "1200", currency: "TWD", threshold: "1000", reason: "HIGH_VALUE_ITEM"};
  dossier.proposal_history = [dossier.proposal_history[0]];
  dossier.review_history = [human.review_result];
  dossier.revision_events = [];
  await page.route("**/backend/cases/CASE-BROWSER/events", route => route.fulfill({contentType: "text/event-stream", body: ": heartbeat\n\n"}));
  await page.route("**/backend/cases/CASE-BROWSER", route => route.fulfill({json: detail}));
  await page.goto("/cases/CASE-BROWSER");
  for (let iteration = 0; iteration < 2; iteration++) {
    await expect(page.getByText("Reviewer 已核准 · 等待人工授權")).toBeVisible();
    await expect(page.getByLabel("金額 gate")).toContainText("1000");
    await expect(page.getByText("修正次數已用盡 · Reviewer 尚未核准")).toHaveCount(0);
    await expect(page.getByText("外觀損壞不能證明無法修復。", {exact: true})).toHaveCount(0);
    if (iteration === 0) await page.reload();
  }
});

test("budget exhaustion shows unresolved objections and supports a human edit", async ({ page }) => {
  let detail = structuredClone(humanCase);
  await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }));
  await page.route("**/backend/cases/CASE-BROWSER", (route) => route.fulfill({ json: detail }));
  await page.route("**/backend/cases/CASE-BROWSER/review", (route) => {
    const body = route.request().postDataJSON();
    expect(body.decision).toBe("EDIT");
    expect(body.corrected_decision).toEqual({
      action: "FULL_REFUND", refund_scope: { line_item_ids: ["LI-DEMO"] },
      return_decision: { source: "HUMAN_REVIEW", requirement: {
        required: true, reason_code: "RETURN_REQUIRED_FOR_INSPECTION",
      } },
    });
    expect(body).not.toHaveProperty("amount");
    expect(body.corrected_decision).not.toHaveProperty("amount");
    detail = { ...detail, status: "OBSERVING" };
    return route.fulfill({ json: detail });
  });
  await page.goto("/cases/CASE-BROWSER");
  await expect(page.getByText("修正次數已用盡 · Reviewer 尚未核准")).toBeVisible();
  await expect(page.getByText("外觀損壞不能證明無法修復。", {exact: true})).toBeVisible();
  await expect(page.getByRole("region", {name: "完整審核歷程"}).locator("details")).toHaveCount(4);
  await page.getByRole("button", { name: "決定退款", exact: true }).click();
  const submit = page.getByRole("button", { name: "確認退款裁決", exact: true });
  await expect(submit).toBeDisabled();
  await page.getByLabel("人工審核理由").fill("需退回檢查才能確認故障原因");
  await page.getByLabel("LI-DEMO (LI-DEMO)", { exact: true }).uncheck();
  await expect(submit).toBeDisabled();
  await page.getByLabel("LI-DEMO (LI-DEMO)", { exact: true }).check();
  await submit.click();
  await expect(page.getByText("Agent 正在處理下一步")).toBeVisible();
});


test("memory cards preserve cosine order and replace on refreshed empty or unavailable result", async ({ page }) => {
  const hits = [
    ["MEM-LOW", 0.1, 0.9102], ["MEM-HIGH", 0.99, 0.7245], ["MEM-THIRD", 0.8, 0.4156],
  ].map(([id, confidence, similarity]) => ({ memory: {
    memory_id: id, confidence, status: "APPROVED", retrieval_summary: "包裝受損的取證經驗",
    trigger_conditions: ["包裝與商品需要比對"], recommended_behavior: "一起檢視外箱與商品",
    scope: { market: "TW", reason_codes: ["ITEM_DAMAGED"], claim_ids: [], categories: [] },
    policy_version: "POLICY:v1", claim_registry_version: "claim-registry:1.0", approved_at: "2026-09-09T00:00:00Z",
  }, similarity }));
  const event = (seq: number, payload: object) => ({ seq, case_ref: "CASE-BROWSER", type: "memory_retrieval", node: "retrieve_memory", ts: "2026-09-09T00:00:00Z", payload });
  const first = event(1, { status: "OK", query_summary: "首次查詢摘要", hits });
  let history = [first];
  await page.route("**/backend/cases/CASE-BROWSER", route => route.fulfill({ json: humanCase }));
  await page.route("**/backend/cases/CASE-BROWSER/events", route => route.fulfill({
    contentType: "text/event-stream",
    body: history.map(e => "id: " + e.seq + "\nevent: memory_retrieval\ndata: " + JSON.stringify(e) + "\n\n").join(""),
  }));
  await page.goto("/cases/CASE-BROWSER");
  await page.locator('[data-node="retrieve_memory"]').click();
  const panel = page.getByRole("region", { name: "最新 Memory 檢索" });
  await expect(panel.locator("[data-memory-id]")).toHaveCount(3);
  await expect(panel.locator("[data-memory-id]").first()).toHaveAttribute("data-memory-id", "MEM-LOW");
  await expect(panel.getByText("cosine 0.9102")).toBeVisible();
  await expect(panel.getByText("confidence 0.10")).toBeVisible();
  for (const payload of [{ status: "OK", query_summary: "補件後摘要", hits: [] }, { status: "UNAVAILABLE", error_code: "SUMMARY_UNAVAILABLE", hits: [] }]) {
    history = [first, event(2, payload)];
    await page.reload();
    await page.locator('[data-node="retrieve_memory"]').click();
    await expect(panel.locator("[data-memory-id]")).toHaveCount(0);
    await expect(panel.getByRole("status")).toContainText(payload.status === "OK" ? "沒有符合條件" : "暫不可用");
  }
});

test("human reverses decline across claimed items and reopens read-only audit after refresh", async ({ page }) => {
  let detail: CaseDetail = {...humanCase, human_review: {
    case_ref: review.case_ref, handoff_id: review.handoff_id, action: "DECLINE", amount: "0", currency: "TWD",
    refund_scope: {line_item_ids: []}, review_result: review.review_result,
    rationale_summary: "Agent 最後提案不退款", dossier: review.dossier,
  }};
  await page.route("**/backend/cases/CASE-BROWSER/events", route => route.fulfill({contentType: "text/event-stream", body: ": heartbeat\n\n"}));
  await page.route("**/backend/cases/CASE-BROWSER", route => route.fulfill({json: detail}));
  await page.route("**/backend/cases/CASE-BROWSER/review", route => {
    const body = route.request().postDataJSON();
    expect(body.handoff_id).toBe("HANDOFF-BROWSER");
    expect(body.corrected_decision.refund_scope.line_item_ids).toEqual(["LI-DEMO", "LI-OTHER"]);
    expect(body.corrected_decision).not.toHaveProperty("amount");
    detail = {...detail, status: "RESOLVED", human_review_result: {decision: "EDIT", corrected_decision: body.corrected_decision,
      correction_reason_code: "OTHER", review_note: body.review_note, reviewer_id: "demo_reviewer",
      reviewed_at: humanCase.updated_at, final_resolution_ref: "RESOLUTION-BROWSER"}};
    return route.fulfill({json: detail});
  });
  await page.goto("/cases/CASE-BROWSER");
  await page.getByRole("button", {name: "決定退款", exact: true}).click();
  await page.getByLabel("LI-DEMO (LI-DEMO)", {exact: true}).check();
  await page.getByLabel("LI-OTHER (LI-OTHER)", {exact: true}).check();
  await page.getByLabel("人工審核理由").fill("重新檢視原申請的兩件商品，都符合退款條件");
  await page.screenshot({path: "/tmp/shopee-human-adjudication-panel.png", fullPage: true});
  await page.getByRole("button", {name: "確認退款裁決"}).click();
  await expect(page.getByRole("region", {name: "人工裁決紀錄"})).toContainText("兩件商品");
  await page.reload();
  await expect(page.getByRole("region", {name: "完整審核歷程"}).locator("details")).toHaveCount(4);
  await expect(page.getByRole("region", {name: "人工裁決紀錄"})).toContainText("demo_reviewer");
  await expect(page.getByRole("button", {name: "決定不退款"})).toHaveCount(0);
});

test("graph stage animates loops, a resumed evidence request, a running tool and narration", async ({ page }) => {
  let seq = 0;
  const activity = (node: string, attempt: string, payload: object, extra: object = {}) => {
    seq += 1;
    return {
      schema_version: "1.0", event_id: `EV-${seq}`, case_ref: "CASE-BROWSER", run_id: "COMMAND-1", scope: "CASE",
      node, operation_id: `${attempt}-${seq}`, attempt_id: attempt, occurred_at: "2026-09-09T00:00:00Z", seq, payload, ...extra,
    };
  };
  const step = (node: string, attempt: string, next: string) => [
    activity(node, attempt, { type: "node", phase: "STARTED", name: node }),
    activity(node, attempt, { type: "node", phase: "COMPLETED", name: node }),
    activity(node, attempt, { type: "node_summary", facts: { next_node: next } }, { event_id: `SUMMARY-${attempt}` }),
  ];
  const history = [
    ...step("parse_request", "P1", "load_case_context"),
    ...step("load_case_context", "L1", "retrieve_policy"),
    ...step("retrieve_policy", "T1", "prepare_memory_query"),
    ...step("prepare_memory_query", "M1", "retrieve_memory"),
    ...step("retrieve_memory", "R1", "assess_case"),
    ...step("assess_case", "A1", "request_evidence"),
    activity("assess_case", "A1", { type: "narration", source_event_id: "SUMMARY-A1", status: "COMPLETED",
      text: "評估認為還缺少到貨時的損壞證據。下一步預計請買家補件。" }),
    activity("request_evidence", "E1", { type: "node", phase: "STARTED", name: "request_evidence" }),
    activity("request_evidence", "E1", { type: "node", phase: "PAUSED", name: "request_evidence" }),
    ...step("request_evidence", "E2", "prepare_memory_query"),
    ...step("prepare_memory_query", "M2", "retrieve_memory"),
    ...step("retrieve_memory", "R2", "assess_case"),
    activity("assess_case", "A2", { type: "node", phase: "STARTED", name: "assess_case" }),
    activity("assess_case", "A2", { type: "tool", phase: "STARTED", name: "evidence_provider.resolve" }),
  ];
  await routeActivities(page, history);
  await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }));
  await page.route("**/backend/cases/CASE-BROWSER", (route) =>
    route.fulfill({ json: { ...humanCase, status: "OBSERVING", human_review: null } }));
  await page.goto("/cases/CASE-BROWSER");

  const stage = page.getByRole("region", { name: "Agent 決策圖" });
  // History replays one node step at a time; skipping jumps to the current state.
  const skip = stage.getByRole("button", { name: /跳到最新/ });
  await expect(skip).toBeVisible();
  await expect(stage.locator('[data-node="assess_case"]')).not.toHaveAttribute("data-state", "active");
  await skip.click();
  await expect(skip).toHaveCount(0);
  const assess = stage.locator('[data-node="assess_case"]');
  await expect(assess).toHaveAttribute("data-state", "active");
  await expect(assess.locator("[data-visits]")).toHaveText("2");
  await expect(assess.locator('[data-operation-status="running"]')).toHaveCount(1);
  await expect(stage.locator('[data-node="request_evidence"]')).toHaveAttribute("data-state", "done");
  await expect(stage.locator('[data-edge="request_evidence>prepare_memory_query"]')).toHaveAttribute("data-traversed", "true");
  await expect(stage.locator('[data-budget="evidence"]')).toContainText("1/2");
  await expect(stage.getByLabel("最新 AI 解說")).toContainText("評估認為還缺少到貨時的損壞證據");

  const inspector = page.getByRole("tabpanel", { name: "節點檢視" });
  // The inspector follows the running node without a click.
  await expect(inspector.getByRole("heading", { name: "評估申請證據" })).toBeVisible();
  await expect(inspector.getByText("進入 2 次")).toBeVisible();
  await expect(inspector.getByRole("region", { name: "第 1 次執行" }).getByLabel("AI 解說")).toBeVisible();
  await expect(inspector.getByRole("region", { name: "第 2 次執行" }).locator('[data-operation-status="running"]')).toContainText("執行中");

  // Picking another node pins it until following is resumed.
  await stage.locator('[data-node="request_evidence"]').click();
  await expect(inspector.getByRole("heading", { name: "等待補交資料" })).toBeVisible();
  await inspector.getByRole("button", { name: "跟隨目前節點" }).click();
  await expect(inspector.getByRole("heading", { name: "評估申請證據" })).toBeVisible();
  await expect(inspector.getByRole("button", { name: "跟隨目前節點" })).toHaveCount(0);
});

test("a resolution waiting for the refund system shows where the case stopped", async ({ page }) => {
  let seq = 0;
  const activity = (payload: object) => {
    seq += 1;
    return {
      schema_version: "1.0", event_id: `EV-${seq}`, case_ref: "CASE-BROWSER", run_id: "COMMAND-1", scope: "CASE",
      node: "emit_resolution_handoff", operation_id: `O1-${seq}`, attempt_id: "O1", occurred_at: "2026-09-09T00:00:00Z", seq, payload,
    };
  };
  await routeActivities(page, [
    activity({ type: "node", phase: "STARTED", name: "emit_resolution_handoff" }),
    activity({ type: "node", phase: "COMPLETED", name: "emit_resolution_handoff" }),
    activity({ type: "node_summary", facts: { next_node: "__end__" } }),
  ]);
  await page.route("**/backend/cases/CASE-BROWSER/events", (route) =>
    route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" }));
  await page.route("**/backend/cases/CASE-BROWSER", (route) =>
    route.fulfill({ json: { ...humanCase, status: "EXECUTING", human_review: null } }));
  await page.goto("/cases/CASE-BROWSER");

  const stage = page.getByRole("region", { name: "Agent 決策圖" });
  await expect(stage.locator('[data-node="execute_refund"]')).toHaveAttribute("data-state", "waiting");
  await expect(stage).toContainText("處理結果已送出，等待退款系統執行。");
  const inspector = page.getByRole("tabpanel", { name: "節點檢視" });
  await expect(inspector.getByRole("heading", { name: "執行退款" })).toBeVisible();
  await expect(inspector.getByRole("status")).toContainText("沒有接上退款服務");
});
