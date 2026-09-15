import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { createServer } from 'node:http';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, extname, sep } from 'node:path';
const here = fileURLToPath(new URL('.', import.meta.url));
const modulePath = process.env.PLAYWRIGHT_MODULE || resolve(here, '../presentation/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(modulePath).href);
const artifacts = '/tmp/return-atlas-keynote-verification';
await mkdir(artifacts, {recursive:true});
const errors = [];
const layoutErrors = [];
let browser;
const server = createServer(async (req,res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const prefix = '/team27/slide/';
    if (!path.startsWith(prefix)) throw Error('Not found');
    const target = resolve(here, path.slice(prefix.length) || 'index.html');
    if (!target.startsWith(here.endsWith(sep) ? here : here + sep)) throw Error('Invalid path');
    const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css'};
    res.writeHead(200, {'content-type':`${types[extname(target)] || 'text/plain'}; charset=utf-8`});
    res.end(await readFile(target));
  } catch {res.writeHead(404);res.end('Not found');}
});
try {
  browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const externalRequests = [];
  page.on('request', request => {if (/^https?:/.test(request.url())) externalRequests.push(request.url());});
  await context.setOffline(true);
  await page.goto(pathToFileURL(resolve(here, 'presentation.html')).href);
  assert.equal(await page.locator('.slide:visible').count(),1);
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('#slide-2').isVisible(),true);
  assert.equal(await page.locator('#slide-2 .unrevealed').count(),5);
  await page.keyboard.press('Space');
  assert.equal(await page.locator('#slide-2 .unrevealed').count(),2);
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('#slide-2 .unrevealed').count(),0);
  await page.screenshot({path:resolve(artifacts,'02-architecture.png')});
  await page.keyboard.press('ArrowLeft');
  assert.equal(await page.locator('#slide-2 .unrevealed').count(),2);
  await page.keyboard.press('o');
  assert.equal(await page.locator('.overview-card').count(),8);
  await page.locator('.overview-card').nth(6).click();
  assert.equal(await page.locator('#slide-7').isVisible(),true);
  await page.keyboard.press('n');
  assert.match(await page.locator('#notes-content').innerText(),/04:40–05:05/);
  await page.keyboard.press('Escape');
  await page.locator('#slide-7 [data-source]').click();
  assert.match(await page.locator('#source-content').innerText(),/capabilities\/refund.py/);
  await page.keyboard.press('Escape');
  await page.keyboard.press('t');
  await page.waitForFunction(() => document.querySelector('#timer').textContent !== '00:00', null, {timeout:5000});
  assert.notEqual(await page.locator('#timer').innerText(),'00:00');
  await page.keyboard.press('t');
  await page.keyboard.press('r');
  assert.equal(await page.locator('#timer').innerText(),'00:00');
  await page.keyboard.press('End');
  assert.equal(await page.locator('#next').isDisabled(),true);
  await page.keyboard.press('Home');
  assert.equal(await page.locator('#prev').isDisabled(),true);
  for (const size of [{width:1440,height:900},{width:1280,height:720}]) {
    await page.setViewportSize(size);
    for (let i=1;i<=8;i++) {
      await page.goto(pathToFileURL(resolve(here,'presentation.html')).href + `#${i}`);
      if (i===2) { await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); }
      const bounds = await page.evaluate(() => ({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,viewportWidth:innerWidth,viewportHeight:innerHeight}));
      assert.ok(bounds.width <= bounds.viewportWidth,`slide ${i} horizontal overflow ${JSON.stringify(bounds)}`);
      if (bounds.height > bounds.viewportHeight+1) layoutErrors.push(`slide ${i} vertical overflow ${JSON.stringify(bounds)}`);
      if (size.width===1440) await page.screenshot({path:resolve(artifacts,`${String(i).padStart(2,'0')}.png`)});
    }
  }
  await page.setViewportSize({width:390,height:844});
  for(let i=1;i<=8;i++) {
    await page.goto(pathToFileURL(resolve(here,'presentation.html')).href+`#${i}`);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),`mobile slide ${i} horizontal overflow`);
  }
  await page.screenshot({path:resolve(artifacts,'mobile.png'),fullPage:true});
  assert.equal(externalRequests.length,0,'offline deck must not request external resources');
  await page.goto(pathToFileURL(resolve(here,'../presentation/presentation.html')).href+'#4');
  await page.waitForURL('**/slide/presentation.html#4');
  assert.equal(await page.locator('#slide-4').isVisible(),true);
  await context.setOffline(false);
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  await page.goto(`http://127.0.0.1:${server.address().port}/team27/slide/index.html#3`);
  await page.waitForURL('**/presentation.html#3');
  assert.equal(await page.locator('#slide-3').isVisible(),true);
  await page.reload();
  assert.equal(await page.locator('#slide-3').isVisible(),true);
  await page.locator('#fullscreen-button').click();
  await page.waitForFunction(() => Boolean(document.fullscreenElement));
  await page.locator('#fullscreen-button').click();
  await page.waitForFunction(() => !document.fullscreenElement);
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.slide:visible').count(),8);
  assert.equal(errors.length,0, errors.join('\n'));
  assert.equal(layoutErrors.length,0,layoutErrors.join('\n'));
  console.log('PASS: offline file entry, reveal/back, overview, notes, sources, timer, boundaries, 8 desktop slides at 1440/1280, mobile width, entry alias, Pages subpath/deep link/reload, fullscreen, print; no JS errors.');
  console.log(`Screenshots: ${artifacts}`);
} finally {
  await browser?.close();
  if (server.listening) await new Promise(resolve=>server.close(resolve));
}
