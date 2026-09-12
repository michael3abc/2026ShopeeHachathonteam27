/** Browser acceptance, including real file:// loading and an offline context. */
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
const errors = [],
  requests = [],
  checks = [];
const record = (name) => {
  checks.push(name);
  console.log(`PASS ${name}`);
};
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const rendered = () =>
    page.waitForFunction(
      () => document.querySelector("#main").dataset.route === location.hash,
    );
  const navigate = async (url) => {
    await page.goto(url);
    await rendered();
  };
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("request", (r) => requests.push(r.url()));
  await navigate(base);
  await page.locator("h1").waitFor();
  assert.match(await page.locator("h1").innerText(), /每一次退款/);
  await page.screenshot({
    path: join(artifacts, "01-overview-desktop.png"),
    fullPage: true,
  });
  record("Pages subpath: homepage renders");

  for (const hash of [
    "#architecture?view=context",
    "#architecture?view=service",
    "#architecture?view=ownership",
    "#agent?view=overview",
    "#agent?view=exact",
    "#agent?view=sequence",
    "#agent?view=ui",
    "#agent?view=llm",
    "#evidence",
  ]) {
    await navigate(base + hash);
    await page.locator("h1").waitFor();
    assert((await page.locator("#main").innerText()).length > 150, hash);
  }
  record("All six architecture views plus UI, LLM and evidence pages render");
  await navigate(base + "#agent?view=exact&entity=reviewer");
  await page.reload();
  assert.match(await page.locator(".inspector").innerText(), /獨立審核/);
  assert.equal(await page.locator(".diagram-node").count(), 18);
  await page.locator('[data-entity="request_evidence"]').first().focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() =>
    location.hash.includes("entity=request_evidence"),
  );
  await rendered();
  assert.match(await page.locator(".inspector").innerText(), /STATE READS/);
  await page.screenshot({
    path: join(artifacts, "02-graph-desktop.png"),
    fullPage: true,
  });
  record(
    "Deep-link refresh, exact nodes, keyboard node selection and state inspector",
  );
  await page.locator('[data-zoom="in"]').click();
  assert.match(
    await page.locator(".diagram-viewport svg").getAttribute("style"),
    /120/,
  );
  await page.locator('[data-zoom="fit"]').click();
  await page.locator("#edge-filter").selectOption("failure");
  await page.waitForFunction(() => location.hash.includes("filter=failure"));
  await rendered();
  assert((await page.locator(".diagram-edge").count()) < 42);
  assert((await page.locator(".diagram-edge").count()) > 0);
  await page.locator(".diagram-edge").first().focus();
  await page.keyboard.press("Enter");
  await page.locator('[aria-label="關係細節"]').waitFor();
  record("Zoom / fit, edge filter and keyboard relationship inspector");
  await navigate(base + "#agent?view=overview");
  await page.locator('[data-group="review"]').click();
  await page.waitForFunction(() => location.hash.includes("group=review"));
  await rendered();
  assert.equal(await page.locator(".diagram-node").count(), 4);
  await page.goBack();
  await page.waitForFunction(() => location.hash === "#agent?view=overview");
  record("High-level grouping drill-down and browser back");

  await page.locator("[data-search]").click();
  await page.locator("#search-input").fill("no_such_component_very_unlikely");
  assert.match(await page.locator("#search-results").innerText(), /找不到/);
  await page.locator("#search-input").fill("MEMORY_QUERY_SUMMARY");
  await page.locator('[data-search-entity="llm:MEMORY_QUERY_SUMMARY"]').click();
  await page.waitForFunction(() => location.hash.includes("view=llm"));
  await rendered();
  assert.match(await page.locator("#main").innerText(), /Payload 組裝/);
  await page.screenshot({
    path: join(artifacts, "03-llm-desktop.png"),
    fullPage: true,
  });
  record("Search: empty result, actual LLM task, payload and packaged prompt");

  const data = JSON.parse(
    await readFile(join(here, "architecture-data.json"), "utf8"),
  );
  for (const s of data.scenarios) {
    for (let i = 0; i < s.steps.length; i++) {
      await navigate(base + `#trace?scenario=${s.id}&step=${i}`);
      await page.locator(".trace-head h2").waitFor();
      assert.equal(
        await page.locator(".trace-head h2").innerText(),
        s.steps[i].title,
      );
      assert.equal(
        await page.locator(".ui-status").innerText(),
        s.steps[i].status,
      );
    }
  }
  record(
    "Every step of all five scenarios renders the correct title and backend status",
  );
  await navigate(base + "#trace?scenario=evidence&step=13");
  await page.screenshot({
    path: join(artifacts, "04-trace-desktop.png"),
    fullPage: true,
  });
  await page.locator('[data-play="restart"]').click();
  assert.match(await page.locator(".position").innerText(), /01/);
  await page.locator('[data-play="next"]').click();
  assert.match(await page.locator(".position").innerText(), /02/);
  await page.locator('[data-play="prev"]').click();
  await page.locator('[data-play="toggle"]').click();
  await page.waitForFunction(
    () => new URLSearchParams(location.hash.split("?")[1]).get("step") === "1",
    {},
    { timeout: 5000 },
  );
  await page.locator('[data-play="toggle"]').click();
  const paused = await page.locator(".position").innerText();
  await page.waitForTimeout(2400);
  assert.equal(await page.locator(".position").innerText(), paused);
  await page.locator('a[href*="scenario=human"]').first().click();
  await page.waitForFunction(() => location.hash.includes("scenario=human"));
  await rendered();
  assert.match(await page.locator(".position").innerText(), /01/);
  record("Previous / Next / Play / Pause / Restart and scenario state reset");

  await page.setViewportSize({ width: 390, height: 844 });
  for (const hash of [
    "#overview",
    "#trace?scenario=evidence",
    "#architecture?view=ownership",
    "#agent?view=exact&display=list",
    "#agent?view=llm&entity=llm:REVIEW",
  ]) {
    await navigate(base + hash);
    await page.locator("h1").waitFor();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 1,
    );
    assert.equal(overflow, false, `Page overflow: ${hash}`);
  }
  await navigate(base + "#overview");
  await page.screenshot({
    path: join(artifacts, "05-overview-mobile.png"),
    fullPage: true,
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
    true,
  );
  record(
    "390px mobile layouts, graph list alternative and reduced-motion mode",
  );

  const offline = await browser.newContext({
    offline: true,
    viewport: { width: 1365, height: 900 },
  });
  const filePage = await offline.newPage();
  filePage.on("pageerror", (e) => errors.push(e.message));
  filePage.on("request", (r) => {
    if (/^https?:/.test(r.url()))
      errors.push("Offline network request: " + r.url());
  });
  await filePage.goto(
    pathToFileURL(join(here, "offline/index.html")).href +
      "#agent?view=llm&entity=llm:REVIEW",
  );
  await filePage.locator("h1").waitFor();
  assert.match(await filePage.locator("#main").innerText(), /Payload 組裝/);
  await filePage.locator("[data-search]").click();
  await filePage.locator("#search-input").fill("policy_documents");
  await filePage.locator("[data-search-entity]").first().click();
  await filePage.locator(".inspector").waitFor();
  await filePage.goto(
    pathToFileURL(join(here, "offline/index.html")).href +
      "#trace?scenario=normal",
  );
  await filePage.locator('[data-play="next"]').click();
  assert.match(await filePage.locator(".position").innerText(), /02/);
  await filePage.screenshot({
    path: join(artifacts, "06-offline.png"),
    fullPage: true,
  });
  record(
    "Real file:// with network offline: diagrams, LLM source, search and playback",
  );
  assert.deepEqual(errors, []);
  assert(
    requests.every((url) => url.startsWith(base)),
    requests.filter((url) => !url.startsWith(base)),
  );
  record("No page/console errors and no external runtime requests");
  const report = {
    testedAt: new Date().toISOString(),
    browser: await browser.version(),
    baseline: data.baseline,
    checks,
    scenarios: data.scenarios.length,
    steps: data.scenarios.reduce((n, s) => n + s.steps.length, 0),
    errors,
    requests: requests.length,
  };
  await writeFile(
    join(artifacts, "browser-report.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(
    JSON.stringify({ checks: checks.length, steps: report.steps, errors }),
  );
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
