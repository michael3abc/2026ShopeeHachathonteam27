# Development Scripts

Repository-wide development and CI helpers belong here. Prefer the root `Makefile` for stable entry points.

## 固定版本重建規格包

此整合 repo 不含來源專案的 baseline Git object，不能重新匯出快照。
CI 驗證原封不動的 manifest、schema、合成案例語意與可重現 ZIP，並測試
exporter 對缺少 baseline 或來源 drift 的拒絕。重新匯出仍必須在持有
485048c 且來源完全相符的工作樹執行，不以當前程式重新標記原快照。

來源為 commit `485048cc73dc5c8f64d08034f49e318827418f80`，不讀 live DB／模型／secrets、不改 runtime。從 repo root：

```bash
uv run --all-packages python scripts/export_reconstruction.py
uv run --all-packages python scripts/check_reconstruction_semantics.py --export
node scripts/render_reconstruction.mjs
uv run --all-packages python scripts/package_reconstruction.py
uv run --all-packages python docs/reconstruction/tools/verify_package.py --schemas
uv run --all-packages python scripts/export_reconstruction.py --check
uv run --all-packages python scripts/check_reconstruction_semantics.py
uv run --all-packages pytest tests/test_reconstruction_package.py
```

ZIP 預設 `.artifacts/reconstruction/reconstruction-485048c.zip`（不納入Git），內容僅 docs/reconstruction、附屬資產與獨立驗證工具。匯出檢查拒絕 baseline 程式 drift，README修正除外。圖源可編輯，Mermaid CLI 11.16.0、scale3；首次產圖可能需下載工具／browser，不屬離線驗證必需。若原baseline日後不在workingtree，請於獨立worktree取該commit匯出，不覆寫現行branch。

## Agent Service smoke

### Activity tracing 驗證

離線 CI：`uv run --all-packages pytest tests/test_activity_transport.py apps/api/tests/test_activity_migration.py`。
HTTP/SSE 使用真實 loopback socket；預設 fakeredis，不呼叫真實模型。
設 ACTIVITY_TEST_REDIS_URL 到**全新隔離 Redis DB**，可驗證真實 Redis transport。
此測試有 model_enabled 與 offline_demo 兩個參數案例；使用真實 Redis 時，各自指定不同的全新 DB 並分開執行，避免前一案例留下的 stream／cache 干擾：

```bash
ACTIVITY_TEST_REDIS_URL=redis://127.0.0.1:26389/0 uv run --all-packages pytest tests/test_activity_transport.py -k model_enabled
ACTIVITY_TEST_REDIS_URL=redis://127.0.0.1:26389/1 uv run --all-packages pytest tests/test_activity_transport.py -k offline_demo
```

請先自行啟動該隔離測試 Redis；上述 port 僅為範例，不使用既有服務的 Redis。
ACTIVITY_TEST_POSTGRES_URL 到專用 PostgreSQL，可驗證完整 migration、8 worker 並發去重／seq
及 downgrade 保護。測試只建立／刪除唯一 test schema，不能指向正式 DB。

真實模型 smoke：先載入 RETURN_AGENT_MODEL_BASE_URL／NAME／API_KEY_FILE，然後執行
`uv run --all-packages python scripts/run_activity_narration_smoke.py --redis-url redis://127.0.0.1:26389/3 --output .artifacts/activity-tracing/narration-smoke.json`。
只對 synthetic、無個資的三份摘要呼叫配置模型，不跑退款、不建立真實案件；Redis 必須隔離，
輸出含來源 summary、narration、模型與耗時；COMPLETED 以外結果使 smoke 失敗。

`run_agent_smoke.py` 只使用 shared contracts 與 Redis，不直接 import LangGraph。
先啟動 Compose，再送出一筆 `CASE-DEMO` command：

```bash
docker compose up --build -d
uv run --package return-agent-service python scripts/run_agent_smoke.py
```

Compose 會將 repository 的 `config/reviewer-gates.json` 唯讀掛載到 API 與
Agent Service 的相同 container path。調整金額門檻時，必須同時更新 JSON 的
`version`，並協調兩個服務一起切換；不要在 `.env` 重複設定 business threshold。
`tests/test_review_gate_compose.py` 會從 rendered Compose 驗證兩邊的來源、路徑、
read-only flag、version 與 fingerprint 一致。

它會輸出 node lifecycle，並在 `INTERRUPTED`、`RESOLVED`、`ESCALATED` 或
`RUN_FAILED` 結束。Compose 預設使用 non-production deterministic demo profile。

若要連 Case API、補件 resume 與 Agent event projection 一起驗證，使用根目錄的
無 UI E2E：

```bash
make test-e2e
```

此測試使用 in-process 測試基礎設施驗證 command/event、interrupt/resume 與
handoff，不呼叫 live LLM 或真實外部服務。

若 Compose 已用 `integrated-demo` API 與 `integrated-qwen` Agent Service 啟動，
可從公開 Case API 跑真實 no-UI 服務路徑：

```bash
uv run python scripts/run_no_ui_e2e.py --timeout 300
```

The runner creates a unique `ORDER-DEMO-E2E-*` reference on every invocation
while reusing the versioned demo order contents, Policy, Memory, and Evidence.
This keeps refund execution idempotency meaningful and makes repeated smoke runs
independent.

此腳本使用既有 `Demo Bluetooth Speaker` 與
`artifact://demo/EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE`，不直接 import LangGraph，
也不繞過 API transactional outbox、Redis Streams、Provider HTTP boundaries、
Verification、Reviewer 或 refund execution。預期終態是
`RESOLVED`，resolution outcome_source 為 REVIEWER_APPROVE。

## UI live E2E

`run_ui_e2e.mjs` 以 Chromium 操作真實 Web；它不 mock HTTP/SSE/LLM、也不直接
呼叫 runtime。先用 `integrated-demo` API、`integrated-qwen` Agent Service、已初始化的
PostgreSQL 與 Redis 啟動 Compose，再啟動 `web`。啟動／重建時請沿用既有 model、
embedding URL 與 `.secrets/` host-file 設定，避免回到預設的未組裝 profile。

```bash
npm --prefix apps/web ci
cd apps/web && npx playwright install chromium && cd ../..
# 不重建或重設正在運作的 API／Agent Service 設定
docker compose up -d --build --no-deps web
npm --prefix apps/web run test:e2e:live
```

`UI_E2E_BASE_URL` 預設 `http://127.0.0.1:3000`，`UI_E2E_TIMEOUT_MS` 預設
300000。腳本建立唯一 `ORDER-DEMO-UI-*`、輸入損壞申請、等待 SSE 補件通知、
提交既有 demo artifact、驗證 `RESOLVED / AUTO` 與每個主要 node 的完成事件，
再重新整理確認狀態與 node 可重建。它不把 `EXECUTING` 當成成功。

畫面截圖與結果寫入 ignored `.artifacts/ui-e2e/<order_ref>/`。此 live 測試會新增
demo 案件與退款紀錄，但金流仍為 deterministic demo adapter，不會真正扣款。
UI 的 APPROVE/REJECT 與失敗顯示另由 `npm --prefix apps/web run test:browser`
驗證；該組使用 mock Backend，不宣稱覆蓋真實 HUMAN 路線。


## Memory VDB 隔離驗收

`run_memory_vdb_rehearsal.py` 僅接受全新空白、名稱以 memory_rehearsal 開頭的 PostgreSQL。
以既有 provider env 檔載入 LLM/embedding 設定（不回顯 credentials），合成 legacy 狀態、
演練 Alembic 0010→0011、dry-run／回填／續跑、Policy reembed 歷史保留、同 scope 多筆記憶與首次／補件摘要檢索。
LLM 使用 Responses 串流，temperature=None 明確省略（Compass 不接受 temperature）；不改既有 Qwen profile。

```bash
uv run --all-packages python scripts/run_memory_vdb_rehearsal.py \
  --database-url postgresql+psycopg://USER:PASSWORD@127.0.0.1:15439/memory_rehearsal \
  --provider-env /path/to/provider.env \
  --output .artifacts/memory-vdb-rehearsal/output.jsonl
node scripts/render_agent_graph.mjs
```

輸出檔不可覆寫；失敗重跑使用新的隔離 DB／output，保留失敗證據。回填 CLI 自身可原庫續跑，
不需要重建 DB。render_agent_graph 使用 pinned Mermaid CLI，從 canonical graph Markdown 產生3×高解析PNG，
不增加 production dependency。不要執行對正式 DB 的 deployment/restart。
