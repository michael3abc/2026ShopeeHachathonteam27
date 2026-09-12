# Shopee Hackathon 2026 Agent Infrastructure


本 worktree 從 `main@c70351e` 實作 Policy v2 與 User Risk。API 依可信 Demo
scenario 選用並保存政策版本；v1 保留既有語意，v2 新案使用四條獨立政策路徑、
版本化確認、Reviewer 後的 deterministic gates 與退回履約。買家、reviewer、
operator 使用個別憑證登入；核准退款與實際 `APPLIED` 分開保存。
真模型 A–F、risk persona 與 B→C 學習驗收仍須逐項核對，不能由測試數量宣稱完成。

本機啟動使用 scripts/local_import.py，讀取此機既有 .env，不匯入來源密鑰。
PostgreSQL / Redis 使用獨立 Compose project `team27-policy-v2-user-risk`；預設
API DB／Agent DB／Redis 為 `58432 / 58433 / 58379`，API／Agent／Web 為
`8200 / 8290 / 3200`。Project、ports 與 env file 均可參數化；用法見
[launcher 說明](scripts/README.md#policy-v2-隔離-launcher)。不切換原 main 服務。
embedding endpoint 必須明確配置，沒有私人 gateway 預設值。

此整合替換了原重建的 DTO、schema 目錄與 migration lineage，不能原地升級
原重建 DB（0004_resolution_projection）。只能在新資料庫套用新 migrations；
原 DB、checkpoint 與 pending jobs 保留隔離，不交給新 worker 重播。

提交驗證：make check、make check-web、make contracts 後檢查生成檔 drift，
並建置 API、Agent Service、Web Docker images。CI 使用 fake models；
真實 LLM smoke 與 Memory A/B/C 驗收是獨立結果，不由單元測試宣稱通過。

本機命令（服務分別執行；先配置模型、embedding、內部 token 與 Demo 身分檔）：

```bash
uv sync --locked --all-packages
uv run --all-packages python scripts/local_import.py check-config
uv run --all-packages python scripts/local_import.py infra
uv run --all-packages python scripts/local_import.py migrate
uv run --all-packages python scripts/local_import.py api
uv run --all-packages python scripts/local_import.py agent
npm --prefix apps/web ci
uv run --all-packages python scripts/local_import.py web-build
uv run --all-packages python scripts/local_import.py web
```

瀏覽器入口為 `http://127.0.0.1:3200`。`web-build` 以本次設定的 API URL
編譯 Next `/backend/*` rewrite；改 API port 後須重新 build。Demo 登入設定見
[API 認證與履約](apps/api/README.md#policy-v2-user-risk-與-demo-認證)。
以下既有 `smoke`／no-UI／UI scripts 為 v1 驗收入口，沒有新增 Demo 登入流程；
不可直接用於啟用角色認證的 v2 stack，或視為 A–F／risk persona 完整驗收。

- [Adaptive Return Resolution Agent Spec](docs/spec/README.md)
- [全專案離線重建規格包（485048c 固定快照）](docs/reconstruction/README.md)：八模組、契約／prompt／合成資產、實作任務與 A/B/C 驗收；不包含應用程式碼。

## Monorepo

```text
apps/api/                 BFF, Case API, SSE, canonical case state
apps/agent_service/       Redis Agent worker and composition root
apps/web/                 Next.js Demo/UI workspace
apps/contracts/           Shared DTOs, interfaces, adapters, schemas, and tests
packages/agent_runtime/   Pure LangGraph library
tests/                    Cross-app and integration tests
scripts/                  Development and CI helpers
```

Use `uv` from the repository root. Run `make test-contracts` for contract tests and `make contracts` to regenerate shared schemas.

不啟動 UI 的跨服務 E2E：

```bash
uv sync --locked --all-packages
make test-e2e
```

它以 SQLite／fakeredis 取代外部基礎設施，但會走真實 Case API、transactional
outbox、Redis adapters、Agent worker、LangGraph、補件 resume 與事件回投。

Local service smoke：

```bash
docker compose up --build -d
uv run --package return-agent-service python scripts/run_agent_smoke.py
```

Compose 使用獨立 API/Agent PostgreSQL container 與 Redis；預設 Agent profile 是
non-production deterministic demo。API 已使用 transactional outbox 發送 Agent
command；正式 refund executor 尚未組裝，因此全額退款 handoff 會停在
`EXECUTING`，不會宣稱退款已完成。

真實 no-UI 整合使用 `integrated-demo` API 與 `integrated-qwen` Agent Service。
它會呼叫 OpenAI-compatible Qwen/embedding gateways，並走完 PostgreSQL、Redis、
typed Provider HTTP boundary、補件、Verification、Reviewer 與 demo refund
application。所有完成裁決案件在結案後由獨立 Memory workers 做整案回顧，
產生至多一則 `CANDIDATE` 或明確 `SKIP`，不阻塞退款結果。完整 trace、v2 工作分流與 migration 邊界見 [Operational Memory](docs/spec/04-operational-memory.md#whole-case-learning-v2)：

```bash
mkdir -p .secrets
# 將 model key 與 internal service token 分別寫入 .secrets/，並 chmod 600
RETURN_AGENT_API_PROFILE=integrated-demo \
RETURN_AGENT_SERVICE_PROFILE=integrated-qwen \
RETURN_AGENT_MODEL_BASE_URL=https://model.example.invalid/v1 \
RETURN_AGENT_MODEL_NAME=qwen3.8-27b-q4-gguf \
RETURN_AGENT_MODEL_API_KEY_HOST_FILE=.secrets/model_api_key \
RETURN_AGENT_EMBEDDING_BASE_URL=https://embedding.example.invalid/v1 \
RETURN_AGENT_EMBEDDING_MODEL=text-embedding-3-large \
RETURN_AGENT_EMBEDDING_API_KEY_HOST_FILE=.secrets/embedding_api_key \
RETURN_AGENT_INTERNAL_SERVICE_TOKEN_HOST_FILE=.secrets/internal_service_token \
docker compose up --build -d

uv run python scripts/run_no_ui_e2e.py --timeout 300
```

`integrated-demo` 仍使用 fixture order/provider 與 deterministic refund application；
正式 Order/Logistics、artifact extraction、production 身分系統與退款 mutation adapter
必須由各能力 owner 替換。

包含 UI 的真實 E2E（先按上述設定啟動完整 Compose）：

```bash
npm --prefix apps/web ci
cd apps/web && npx playwright install chromium && cd ../..
npm --prefix apps/web run test:e2e:live
```

瀏覽器開啟 `http://localhost:3000`，損壞案件會經補件後完成
`RESOLVED / REVIEWER_APPROVE`；詳見 [UI smoke 說明](scripts/README.md#ui-live-e2e)。

Memory VDB 切換需先排空工作並完成 Policy reembed 與 Memory 回填；參見 [遷移 runbook](docs/spec/04-operational-memory.md#遷移與切換-runbook)。不要直接以新設定啟動含舊向量的正式服務。
