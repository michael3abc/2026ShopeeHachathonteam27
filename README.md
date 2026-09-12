# 退貨案件 Agent · Team 27

內部退貨案件 Demo，整合證據審核、人工裁決與經驗學習。使用合成資料與模擬退款，不接真實金流。

T01–T06 核心與本機常駐服務驗證通過，包含 HTTP／Redis／PostgreSQL 的人工裁決、重啟恢復與模擬退款。Memory、Activity、完整 Web 與真模型 A/B/C 尚未完成。實際驗證見 [進度紀錄](docs/progress.md)，技術選擇見 [決策紀錄](docs/decisions.md)。

## 開發環境

- Python **3.12.0**、uv **0.12.13**。
- Node **24.21.0**、npm **11.19.0**；Python 與 Node 依賴分別以 `uv.lock`、`apps/web/package-lock.json` 鎖定。
- Docker Engine 與 Compose v2 相容 CLI；PostgreSQL 16、pgvector、Redis 7.4。
- 若工具裝在使用者目錄，先執行 `export PATH="$HOME/.local/bin:$PATH"`。

```bash
uv python install 3.12.0
uv sync --frozen --all-packages
npm --prefix apps/web ci
```

## 本機啟動

各命令分別在不同終端執行：

```bash
python3 scripts/dev.py api
python3 scripts/dev.py agent
python3 scripts/dev.py web
```

Web：`http://localhost:3000`；API：`http://localhost:8000`；Agent health：`http://localhost:8090`。

API `/health`、Agent `/health/live` 僅表示程序存活；兩者 `/health/ready` 檢查 workers。首頁目前為骨架，完整互動介面待 T09。

本機基礎服務與容器骨架：

```bash
docker compose config --quiet
docker compose up -d api-db agent-db redis
python3 scripts/dev.py migrate
python3 scripts/dev.py seed
```

Compose 的資料庫密碼是明示的本機示範值；連接埠只綁 loopback。容器啟動僅代表基礎服務可用。

啟用目前的持久化案件 API：

```bash
export API_DATABASE_URL=postgresql+psycopg://return_agent:local-demo@127.0.0.1:5432/return_agent
uv run alembic -c apps/api/alembic.ini upgrade head
API_PROFILE=integrated-demo uv run return-agent-api
```

`POST /cases` 建立案件與 START outbox；`GET /cases/{case_ref}` 查詢 canonical 狀態、final_resolution 與 refund_execution；`POST /cases/{case_ref}/messages` 只在等待澄清／證據時接受。`GET /cases/{case_ref}/events` 支援 Last-Event-ID replay，終態 drain 後關閉。`POST /cases/{case_ref}/review` 支援 APPROVE／REJECT／EDIT；退款成功以 application_result.status=APPLIED 判定。

`seed` 建立 DEMO-A／B／C 合成訂單，金額 1200／6200／6800 TWD，各有 CLOSEUP／UNBOXING／OVERVIEW／INSPECTION 四個 opaque artifact refs，例如 DEMO-A-CLOSEUP。已退款品項再次申請會被 reservation 拒絕；seed 不覆寫既有訂單或刪除付款紀錄。

## 驗證

```bash
uv run pytest
uv run return-agent-export-schemas --check
npm --prefix apps/web run contracts -- --check
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

PostgreSQL 整合測試必須明確指定本機測試 DB：

```bash
TEST_API_DATABASE_URL=postgresql+psycopg://return_agent:local-demo@127.0.0.1:5432/return_agent uv run pytest apps/api/tests -q
```

完整跨服務測試另指定 Agent DB 與空白的測試 Redis database：

```bash
TEST_API_DATABASE_URL=postgresql+psycopg://return_agent:local-demo@127.0.0.1:5432/return_agent \
TEST_AGENT_DATABASE_URL=postgresql://return_agent:local-demo@127.0.0.1:5433/return_agent \
TEST_REDIS_URL=redis://127.0.0.1:6379/15 uv run pytest -q
```

每個測試建立自己的 `team27_test_*` schema、跑 migration，結束後僅清理該 schema。未指定測試 DB 時會明確 SKIP；CI 提供獨立 PostgreSQL service，不依賴真模型。

測試使用合成資料，安裝、建置與測試所需檔案均包含在專案中。真模型驗收獨立啟用，不列入 CI 必要條件。

修改共享 DTO 後，依序執行 `uv run return-agent-export-schemas` 與 `npm --prefix apps/web run contracts`，並提交生成的 schemas 與 TypeScript。跨物件授權條件由 Python validators 驗證，不能僅憑 JSON Schema 通過而退款。

## 架構

| 元件 | 職責 |
| --- | --- |
| `apps/contracts` | Pydantic DTO、Provider interfaces、語意驗證器；輸出 JSON Schema 與前端型別。 |
| `packages/agent_runtime` | LangGraph state、節點、路由與 interrupt；不持有 HTTP、Redis 或 DB。 |
| `apps/agent_service` | 模型／Provider 組合、durable workers、checkpoint、Memory 蒸餾及 narration。 |
| `apps/api` | canonical case、DB、授權、人審、退款、outbox 與 SSE。 |
| `apps/web` | 透過同源 `/backend` proxy 存取 API 的案件介面。 |

API 不執行 Runtime；API 與 Agent 以 Redis Streams 交換案件命令／事件。Memory 與 Activity 不具退款授權權限。

## 設定與秘密值

`.env.example` 列出本機設定。`scripts/dev.py` 以字面值解析 `.env`，不執行 shell 展開；自動建立本機 internal token secret file。預設 offline 使用 typed fake model；真模型須明確加 `--profile live`，保留 RETURN_AGENT_* 的 endpoint／名稱／secret file。秘密檔案放忽略的 `secrets/`，勿將真實 token、個資、DB dump 或原始模型 payload 提交到 Git。embedding 與 narration composition 待 T07–T08。
