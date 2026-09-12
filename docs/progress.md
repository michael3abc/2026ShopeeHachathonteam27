# 重建進度

這是本專案的執行紀錄，不沿用規格包的驗證結論。

| 任務 | 狀態 | 證據／未完成 |
| --- | --- | --- |
| T01 骨架與依賴 | 骨架驗證通過 | 四個 packages 可安裝；Python 3.12.0、uv.lock、npm lock；3 項架構／health 測試通過，Next build 通過，Compose config 通過。Docker daemon／映像建置未驗證。 |
| T02 Contracts | 進行中 | 正在重寫 DTO、語意驗證器與測試。尚未宣稱任何 C 案例完成。 |
| T03 API／DB | 未開始 | 待 T02。 |
| T04 能力／退款 | 未開始 | 待 T03。 |
| T05 Graph | 未開始 | 待 T02。 |
| T06 跨服務 | 未開始 | 待 T04、T05。 |
| T07 VDB／Memory | 未開始 | 待 T06。 |
| T08 Activity | 未開始 | 待 T06。 |
| T09 Web | 未開始 | 待 T06–T08。 |
| T10 整合／真模型 | 未開始 | 待 T09；需要允許的模型設定與 credentials。 |

## 驗收追蹤

C01–C36 及 SYS/M01–M08 所有 R 規則目前均尚未驗證。實作時逐項建立測試對應與命令、exit code、耗時證據。

## 執行前置檢查

- 目錄原本不是 Git repository；只有本機規格、AGENTS.md 與忽略規則。
- 系統：Ubuntu 24.04；Git 2.43.0；Python 3.12.3。
- PATH 未找到 gh、uv、Node/npm、Docker；sudo 無免密碼權限。
- gh 2.100.0、uv 0.12.13、Python 3.12.0、Node 24.21.0、npm 11.19.0 已安裝於使用者目錄。
- Docker 29.8.0 binaries／Compose 5.5.1 已安裝，尚無可用 daemon；sudo 驗證未通過，不儲存密碼。
- GitHub 裝置登入完成，帳號 michael3abc；目標名稱查詢回 404，未覆寫任何既有 repo。
- 尚未執行 migration 或呼叫真模型。

## T01 本機測試證據

| 命令 | 結果 |
| --- | --- |
| `uv sync --all-packages` | exit 0；77 個鎖定 packages，四個本機 packages 安裝成功。 |
| `uv run pytest tests/test_architecture.py -q` | exit 0；3 passed，0.51s；Starlette 的第三方 deprecation warning 1 筆。 |
| `npm --prefix apps/web install --no-audit --no-fund` | exit 0；375 packages，約 1 分鐘。 |
| `npm --prefix apps/web run build` | exit 0；Next 16.3.4 編譯、TypeScript 與靜態頁生成成功；編譯 3.0s。 |
| `docker compose config --quiet` | exit 0；僅配置解析，不代表容器已啟動。 |

- `uv sync --frozen --all-packages`：exit 0。
- Node 24.21.0／npm 11.19.0 下 `npm ci --no-audit --no-fund`：exit 0，15s；隨後 `npm run lint`、`npm run typecheck` 均 exit 0、無 lint warning。
- 一次 lint/typecheck 曾與 npm ci 競爭而失敗；安裝完成後依序重跑通過。使用者層級 Node 連結另被切至 22，驗證改用既有 24.21.0 的獨立路徑，未覆寫該連結。

C01–C36、Docker build、DB／Redis／SSE 與 A/B/C 均未驗證。
