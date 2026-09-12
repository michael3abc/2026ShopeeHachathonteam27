/** Desktop-first browser acceptance, Pages subpath and real file:// offline loading. */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";

const here = fileURLToPath(new URL(".", import.meta.url));
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE
    ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href
    : "playwright"
);
const artifacts = join(here, "verification-artifacts");
await mkdir(artifacts, { recursive: true });
const html = await readFile(join(here, "dist/index.html"));
const data = JSON.parse(await readFile(join(here, "architecture-data.json"), "utf8"));
const server = createServer((req, res) => {
  if (
    req.url.split("?")[0] !== "/2026ShopeeHachathonteam27/" &&
    req.url !== "/2026ShopeeHachathonteam27/index.html"
  ) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(html);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/2026ShopeeHachathonteam27/`;
let browser;
const errors = [], requests = [], checks = [];
const record = (name) => {
  checks.push(name);
  console.log(`PASS ${name}`);
};

try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => requests.push(request.url()));
  const rendered = () => page.waitForFunction(
    () => document.querySelector("#main")?.dataset.route === location.hash,
  );
  const navigate = async (url) => {
    await page.goto(url);
    await rendered();
    await page.locator("h1").waitFor();
  };

  await navigate(base + "#overview");
  assert.match(await page.locator("h1").innerText(), /每一次退款/);
  assert.equal(await page.locator(".rail-nav .nav-item").count(), 7);
  assert.match(await page.locator('.rail-nav [aria-current="page"]').innerText(), /系統全貌/);
  await page.screenshot({ path: join(artifacts, "01-overview-1440x900.png"), fullPage: true });
  record("Return Atlas shell, seven-section rail and overview at 1440x900");

  const routes = [
    "#workflow/no_return/0",
    "#architecture/context",
    "#architecture/service",
    "#architecture/high",
    "#architecture/exact/reviewer",
    "#architecture/ownership",
    "#data/sequence?scenario=policy_return",
    "#data/ui",
    "#data/hitl?scenario=human",
    "#data/fulfillment",
    "#components",
    "#component/fulfillment",
    "#infra",
    "#code/llm%3AREVIEW",
  ];
  for (const hash of routes) {
    await navigate(base + hash);
    assert((await page.locator("#main").innerText()).length > 180, hash);
  }
  record("All seven sections and architecture/data drill-down routes render");

  await navigate(base + "#architecture/exact/reviewer");
  await page.reload();
  await rendered();
  assert.match(await page.locator(".inspector").innerText(), /雙授權 gate/);
  assert.equal(await page.locator(".diagram-node").count(), 20);
  assert.equal(await page.locator('[data-entity="evaluate_policy"]').count() > 0, true);
  assert.equal(await page.locator('[data-entity="confirm_policy_path"]').count() > 0, true);
  await page.locator('[data-entity="request_evidence"]').first().focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => location.hash.includes("request_evidence"));
  await rendered();
  assert.match(await page.locator(".inspector").innerText(), /STATE READS/);
  await page.screenshot({ path: join(artifacts, "02-graph-exact-1440x900.png"), fullPage: true });
  record("18 real nodes plus START/END, Policy v2 nodes and keyboard inspector");

  await page.locator('[data-zoom="in"]').click();
  assert.match(await page.locator(".diagram-viewport svg").first().getAttribute("style"), /120/);
  await page.locator('[data-zoom="fit"]').click();
  await page.locator("#edge-filter").selectOption("failure");
  await page.waitForFunction(() => location.hash.includes("filter=failure"));
  await rendered();
  assert((await page.locator(".diagram-edge").count()) > 0);
  await page.locator(".diagram-edge").first().focus();
  await page.keyboard.press("Enter");
  await page.locator('[aria-label="關係細節"]').waitFor();
  record("Graph zoom, fit, failure filter and relationship inspector");

  await navigate(base + "#architecture/high");
  await page.locator('[data-group="review"]').click();
  await page.waitForFunction(() => location.hash.includes("group=review"));
  await rendered();
  assert.equal(await page.locator(".diagram-node").count(), 4);
  await page.goBack();
  await page.waitForFunction(() => location.hash === "#architecture/high");
  record("High-level semantic grouping drill-down and browser back");

  await page.locator("[data-search]").first().click();
  await page.locator("#search-input").fill("no_such_component_very_unlikely");
  assert.match(await page.locator("#search-results").innerText(), /找不到/);
  await page.locator("#search-input").fill("MEMORY_QUERY_SUMMARY");
  await page.locator('[data-search-entity="llm:MEMORY_QUERY_SUMMARY"]').click();
  await page.waitForFunction(() => location.hash.startsWith("#code/"));
  await rendered();
  assert.match(await page.locator("#main").innerText(), /Payload 組裝/);
  assert.match(await page.locator("#main").innerText(), /Image evidence/);
  await page.screenshot({ path: join(artifacts, "03-llm-call-1440x900.png"), fullPage: true });
  record("Search routes to ModelTask call inspector with payload, prompt and image contract");

  for (const scenario of data.scenarios) {
    for (let index = 0; index < scenario.steps.length; index += 1) {
      await navigate(base + `#workflow/${encodeURIComponent(scenario.id)}/${index}`);
      assert.equal(await page.locator(".trace-head h2").innerText(), scenario.steps[index].title);
      assert.equal(await page.locator(".ui-status").innerText(), scenario.steps[index].status);
    }
  }
  record("Every step of all six illustrative scenarios renders correct status and content");

  const policyWait = data.scenarios.find((scenario) => scenario.id === "policy_return")
    .steps.findIndex((step) => step.status === "AWAITING_POLICY_CONFIRMATION");
  await navigate(base + `#workflow/policy_return/${policyWait}`);
  assert.match(await page.locator("#main").innerText(), /AWAITING_POLICY_CONFIRMATION/);
  await page.screenshot({ path: join(artifacts, "04-policy-return-1440x900.png"), fullPage: true });
  await page.locator('[data-play="restart"]').click();
  assert.match(await page.locator(".position").innerText(), /01/);
  await page.locator('[data-play="next"]').click();
  assert.match(await page.locator(".position").innerText(), /02/);
  await page.locator('[data-play="prev"]').click();
  await page.locator('[data-play="toggle"]').click();
  await page.waitForFunction(() => location.hash.endsWith("/1"), {}, { timeout: 5000 });
  await page.locator('[data-play="toggle"]').click();
  const paused = await page.locator(".position").innerText();
  await page.waitForTimeout(2400);
  assert.equal(await page.locator(".position").innerText(), paused);
  await page.locator('a[href^="#workflow/human/0"]').first().click();
  await rendered();
  assert.match(await page.locator(".position").innerText(), /01/);
  record("Previous, Next, Play, Pause, Restart and scenario reset on path routes");

  await page.setViewportSize({ width: 1366, height: 768 });
  await navigate(base + "#overview");
  assert.equal(await page.locator(".rail").evaluate((el) => getComputedStyle(el).position), "fixed");
  await page.screenshot({ path: join(artifacts, "05-overview-1366x768.png"), fullPage: true });
  record("Desktop reference hierarchy remains usable at 1366x768");

  const offline = await browser.newContext({ offline: true, viewport: { width: 1440, height: 900 } });
  const filePage = await offline.newPage();
  filePage.on("pageerror", (error) => errors.push(error.message));
  filePage.on("request", (request) => {
    if (/^https?:/.test(request.url())) errors.push("Offline network request: " + request.url());
  });
  await filePage.goto(pathToFileURL(join(here, "offline/index.html")).href + "#code/llm%3AREVIEW");
  await filePage.locator("h1").waitFor();
  assert.match(await filePage.locator("#main").innerText(), /Payload 組裝/);
  await filePage.goto(pathToFileURL(join(here, "offline/index.html")).href + "#workflow/no_return/0");
  await filePage.locator('[data-play="next"]').click();
  assert.match(await filePage.locator(".position").innerText(), /02/);
  await filePage.screenshot({ path: join(artifacts, "06-offline-1440x900.png"), fullPage: true });
  record("Real file:// offline: Return Atlas UI, LLM inspector and workflow playback");

  assert.deepEqual(errors, []);
  assert(requests.every((url) => url.startsWith(base)), requests.filter((url) => !url.startsWith(base)));
  record("Zero page/console errors and zero external runtime requests");
  const report = {
    testedAt: new Date().toISOString(),
    browser: await browser.version(),
    baseline: data.baseline,
    checks,
    scenarios: data.scenarios.length,
    steps: data.scenarios.reduce((total, scenario) => total + scenario.steps.length, 0),
    viewport: ["1440x900", "1366x768"],
    errors,
    requests: requests.length,
  };
  await writeFile(join(artifacts, "browser-report.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({ checks: checks.length, steps: report.steps, errors }));
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
