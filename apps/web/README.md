# Web App

重建規格與離線素材見 [M07 Web](../../docs/reconstruction/M07-web.md)。

Next.js 16 Demo UI for creating and following synthetic return cases. With
Demo authentication configured, each identity signs in using its own credential
and an opaque HttpOnly session cookie. Backend owns the identity, case owner
and role; the browser cannot choose a trusted role. Without that configuration,
the existing v1 demo retains its fixed `demo_customer` / `demo_reviewer` flow.

## Run locally

```bash
cd apps/web
cp .env.example .env.local
npm ci
npm run dev
```

Next.js proxies `/backend/*` to the Case API at `http://127.0.0.1:8000` by
default, so browser calls and SSE remain same-origin. Override `API_BASE_URL`
when the API is hosted elsewhere.
The production rewrite is fixed at build time: use the isolated launcher's
`web-build` before `web` after changing API ports.

## Contract generation

`npm run contracts` generates TypeScript types under `src/contracts/` from the
versioned JSON Schemas in `apps/contracts`. `npm run build` runs this step
automatically; generated files should not be edited manually.

## Current demo boundary

The UI supports case creation, case detail, clarification/evidence submission,
and live progress through SSE. Human APPROVE/REJECT actions call
`POST /cases/{case_ref}/review` using the generated `ReviewDecision` type and
require a nonempty review note. Backend remains the case-state owner; the UI
never resumes LangGraph directly. The EDIT form supports selecting originally
claimed refund items and a Policy-compatible return requirement; its correction
code is `OTHER` and it does not expose `generalizable`. Exact governance-bearing
payloads require the API. Multiple image attachments are supported by the UI. The human panel is
distinct from the LLM `reviewer` node. Activity tracing uses a separate paginated
API and SSE cursor from case events; late narration/background Memory can arrive
after the case is terminal.

Policy v2 shows deterministic policy evaluation and buyer path confirmation in
graph playback. Buyers can confirm their own path/return requirement; operators
can simulate scoped return arrival and inspection; reviewers alone can read the
risk dossier and submit APPROVE (`採用原建議`), EDIT or REJECT. HIGH/UNKNOWN risk
requires human authorization after Reviewer APPROVE and is displayed separately
from exhausted revision objections. Buyer/operator API JSON and both SSE streams
are projected by Backend to exclude risk facts, review notes and dossiers.

Authorization does not mean payment: the UI distinguishes waiting for return
consent, return arrival, inspection and payment. Required-return cases remain
unpaid until the trusted inspection releases payment; human approval obeys the
same fulfillment conditions.

With the integrated demo profile, enter a unique `ORDER-DEMO-*` order reference.
The context provider binds it to the versioned demo speaker, not a real order.
Initial applications and subsequent clarification/evidence messages accept
JPEG/PNG/WebP through the picker, drag-and-drop or clipboard anywhere in the
composer. Select the related order item (or ORDER/packaging); on multi-item orders
this choice is required. The default limits are 6 images per message, 10 MiB per
image and 25M pixels; the UI reads the configured limits from the API.
The Next.js proxy also reads `RETURN_AGENT_IMAGE_MAX_BYTES` at build time and
adds 64 KiB for multipart overhead. Rebuild Web when changing this limit;
Compose passes the same configured value to the API, Agent Service and Web build.

Each image shows upload progress and a preview. Failed images must be retried or
removed before sending; failed message submission retains the draft. Submitted
messages and images reload from the persisted conversation endpoint; clicking an
image opens its preview. The advanced Demo control still accepts existing refs
such as `artifact://demo/EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE`.

Image upload needs an integrated API order provider and the 0014 migration.
The integrated Agent profile sends actual pixels to the existing Resolver model
for Assessment/Proposal and to Reviewer independently. Configure the existing
model endpoint/key; an image-capable model name alone does not prove the endpoint
accepts images. Offline metadata fixtures remain explicitly synthetic.

The app is also available through `docker compose up --build web`; Compose
builds the same standalone Next.js server and routes Backend requests to the
`api` service.

## Browser verification

`@playwright/test` is a development-only dependency; Chromium does not ship in
the production image. Browser regression tests mock Backend HTTP/SSE, never LLMs:

```bash
npx playwright install chromium
npm run build
npm run test:browser
```

To exercise the real integrated stack and Qwen through Chromium:

```bash
UI_E2E_BASE_URL=http://127.0.0.1:3000 npm run test:e2e:live
```

This is explicitly opt-in and is not run by CI. See
[`scripts/README.md`](../../scripts/README.md) for prerequisites and artifacts.
The existing live E2E launcher targets v1 and does not sign in to the authenticated
v2 stack. Policy v2 browser regressions cover buyer confirmation, risk-authorized
human approval, operator inspection and versioned graph playback alongside v1.

## 申請理解展示

理解節點與讀取訂單節點顯示各次執行的理解結果；商品先顯示識別碼。缺少歷史結果時明示，理解不代表退款核准。對話保留買家原文換行與圖片，載入／失敗／未保存分別提示。
