/** Live browser smoke. Uses real services; no mocked HTTP, SSE, or model output. */
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(new URL("../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const baseURL = process.env.UI_E2E_BASE_URL ?? "http://127.0.0.1:3000";
const timeout = Number(process.env.UI_E2E_TIMEOUT_MS ?? "300000");
assert(Number.isFinite(timeout) && timeout > 0, "UI_E2E_TIMEOUT_MS must be positive");
const orderRef = `ORDER-DEMO-UI-${randomUUID().slice(0, 8).toUpperCase()}`;
const artifacts = path.join(repoRoot, ".artifacts", "ui-e2e", orderRef);
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(timeout);
const browserErrors = [];
page.on("pageerror", (error) => browserErrors.push(error.message));
// Observe the application's real EventSource without changing network traffic.
await page.addInitScript(() => {
  window.__agentEvents = [];
  const NativeEventSource = window.EventSource;
  window.EventSource = class extends NativeEventSource {
    constructor(url, options) {
      super(url, options);
      for (const kind of ["node_enter", "node_exit", "interrupt", "state_change", "done", "error"]) {
        this.addEventListener(kind, (event) => {
          if (typeof event.data === "string") window.__agentEvents.push(JSON.parse(event.data));
        });
      }
    }
  };
});
try {
  await page.goto(baseURL);
  await page.getByLabel("訂單編號").fill(orderRef);
  await page.getByLabel("告訴退貨助理商品遇到的問題").fill(
    `${orderRef} 的 Demo Bluetooth Speaker 到貨時外箱與商品都已損壞，我要退貨退款`,
  );
  await page.getByRole("button", { name: "送出", exact: true }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/cases/CASE-"));
  const caseRef = decodeURIComponent(new URL(page.url()).pathname.split("/").at(-1));
  console.log(`created case=${caseRef} order=${orderRef}`);
  await page.waitForFunction(() => window.__agentEvents.some((event) => event.type === "interrupt" || event.type === "done"));
  const firstOutcome = await page.evaluate(() => window.__agentEvents.find((event) => event.type === "interrupt" || event.type === "done"));
  assert.equal(firstOutcome.payload.interrupt_kind, "EVIDENCE_REQUEST", JSON.stringify(firstOutcome));
  await page.getByText("需要補交證據", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(artifacts, "01-evidence-interrupt.png"), fullPage: true });
  await page.getByLabel("證據檔案編號").fill(
    "artifact://demo/EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE",
  );
  await page.getByLabel("補充案件說明").fill("補上同一張照片，清楚拍到壓損外箱與喇叭裂痕");
  const sent = page.waitForResponse((response) =>
    response.url().endsWith(`/cases/${caseRef}/messages`) && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "送出", exact: true }).click();
  assert.equal((await sent).status(), 200, "evidence resume failed");
  console.log(`case=${caseRef} evidence submitted; waiting for real Qwen resolution`);
  await page.locator("header").getByText("案件已完成").waitFor();
  // The terminal stream is finite, so replay it after completion to assert the
  // full persisted sequence. The injected EventSource above still proves the
  // evidence interrupt arrived live before the user resumed the case.
  const eventResponse = await context.request.get(`${baseURL}/backend/cases/${caseRef}/events`);
  assert.equal(eventResponse.status(), 200, "case event replay failed");
  const events = (await eventResponse.text())
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)));
  const done = events.find((event) => event.type === "done");
  assert(done, "terminal event missing from persisted SSE replay");
  assert.equal(done.payload.status, "RESOLVED", JSON.stringify(done));
  assert.equal(events.filter((event) => event.type === "error").length, 0);
  assert(events.some((event) => event.type === "interrupt" && event.payload.interrupt_kind === "EVIDENCE_REQUEST"));
  for (const node of ["parse_request", "load_case_context", "retrieve_policy", "retrieve_memory", "assess_case", "propose_decision", "external_verification", "reviewer"]) {
    assert(events.some((event) => event.type === "node_exit" && event.node === node), `missing node_exit ${node}`);
    await page.locator(`[data-node="${node}"][data-state="done"]`).waitFor();
  }
  const response = await context.request.get(`${baseURL}/backend/cases/${caseRef}`);
  assert.equal(response.status(), 200);
  const detail = await response.json();
  assert.equal(detail.status, "RESOLVED");
  assert.equal("risk_route" in detail, false);
  await page.getByRole("tab", { name: "人工審核" }).click();
  await page.getByText("案件不再等待審核", { exact: true }).waitFor();
  assert.deepEqual(browserErrors, []);
  await page.screenshot({ path: path.join(artifacts, "02-resolved.png"), fullPage: true });
  // Reload must reconstruct node progress and final state from Backend/SSE.
  await page.reload();
  await page.locator('[data-node="reviewer"][data-state="done"]').waitFor();
  await page.getByRole("tab", { name: "人工審核" }).click();
  await page.getByText("案件不再等待審核", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(artifacts, "03-reloaded.png"), fullPage: true });
  const result = { caseRef, orderRef, status: detail.status, terminalRef: done.payload.terminal_ref, eventCount: events.length, browserErrors };
  await writeFile(path.join(artifacts, "result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ ...result, artifacts }, null, 2));
} catch (error) {
  await page.screenshot({ path: path.join(artifacts, "failure.png"), fullPage: true }).catch(() => console.warn("Could not capture failure screenshot"));
  throw error;
} finally {
  await browser.close();
}
