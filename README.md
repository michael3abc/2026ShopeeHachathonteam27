# 退貨案件 Agent · Team 27

內部退貨案件 Demo，整合證據審核、人工裁決與經驗學習。使用合成資料與模擬退款，不接真實金流。

T01 骨架已驗證，T02 契約正在實作，案件互動尚未完成；進度與實際驗證見 [進度紀錄](docs/progress.md)，資產使用與差異見 [決策紀錄](docs/decisions.md)。

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

## 啟動骨架

各命令分別在不同終端執行：

```bash
uv run return-agent-api
uv run return-agent-service
npm --prefix apps/web run dev
```

Web：`http://localhost:3000`；API：`http://localhost:8000`；Agent health：`http://localhost:8090`。

API `/health`、Agent `/health/live` 僅表示程序存活；兩者 `/health/ready` 在組合尚未完成時回 503。首頁目前顯示建置狀態，不提供假的案件成功流程。

本機基礎服務與容器骨架：

```bash
docker compose config --quiet
docker compose up -d api-db agent-db redis
docker compose --profile app up --build
```

Compose 的資料庫密碼是明示的本機示範值；連接埠只綁 loopback。尚未實作 migration、fixture seed 或 A/B/C driver，容器啟動僅代表基礎服務可用。

## 驗證

```bash
uv run pytest
uv run return-agent-export-schemas --check
npm --prefix apps/web run contracts -- --check
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

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

複製 `.env.example` 作為本機設定參考；目前骨架僅讀取 host/port，完整 composition 尚未接線。模型、embedding 與 internal token 使用後續 `_FILE` 設定，檔案放忽略的 `secrets/`。勿將真實 token、個資、DB dump 或原始模型 payload 提交到 Git。
