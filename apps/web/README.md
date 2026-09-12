# Web App

重建規格與離線素材見 [M07 Web](../../docs/reconstruction/M07-web.md)。

Next.js 16 demo UI for creating and following return cases. The app uses a
fixed `demo_customer` and `demo_reviewer`; it does not implement authentication
or mutate real orders.

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
