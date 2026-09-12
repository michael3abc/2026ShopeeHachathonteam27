# M08：部署／Demo／驗收

## 責任與非責任

提供可重建的依賴、容器配置、DB 建立／遷移、fixtures 與 Demo 操作契約。不是 deployment 授權；本包不含 live secrets、DB dump、可運行的原應用程式或完整 offline dependency cache。

## 依賴

Python 3.12.0（API/contracts/service 的 requires-python 精確限制）、uv workspace；Web Node 與 package engines 見 [完整 lock 版本](assets/dependencies/node-resolved.json)，Docker Node base 見 [Web Dockerfile](assets/deployment/web.Dockerfile.reference)。PostgreSQL pgvector:pg16、Redis:7.4-alpine。Python 精確 lock 解出的版本見 [python-resolved](assets/dependencies/python-resolved.json)；原 workspace 的 pyproject 都在 dependencies，先重建 package names／entrypoints 再安裝，不把 workspace package 當公開 PyPI 套件。

## 輸入輸出

[Compose 參考](assets/deployment/compose.reference.yml) 保留服務／ports／health／secret mounts；只把原 site-specific embedding URL 換為不可用 placeholder。Dockerfile.reference 是建置契約，須先完成應用程式與相同入口才能 build，不能把本 ZIP 直接 compose up 宣稱已重建。完整宣告式 [env inventory](assets/environment-inventory.json) 不讀本機實際變數。

## 資料與演算法

- **M08-R01**：default compose API=unconfigured、Agent=demo，無真實模型需求、narration disabled。完整 A/B/C 必須 API=integrated-demo、Agent=integrated-qwen 或現有 integrated 真模型 profile；有 API capabilities／refund executor、durable Agent DB／internal service auth。不得只改 model name 就以為 default demo 會接全部能力。
- **M08-R02**：必填實際 model base/name/key、embedding base/model/key、internal service token、兩 DB URL、Redis URL、相同 reviewer gate 文件、demo data directory。使用 `_FILE` 掛到 `/run/secrets/*`；API 與 Agent 共用 internal token但 browser 不持有。model／embedding credentials 由重建者提供；可同一相容 API endpoint，不強依原私人 gateway。
- **M08-R03**：API fresh DB 使用 vector extension＋全部表/索引/constraints；既有 DB 依 migration chain升級，不對有資料 DB 直接跑 fresh DDL。Agent DB 分 journal、checkpoint setup、Memory replay Alembic 三個 lifecycle，不共用 API alembic_version。
- **M08-R04**：startup 先 DB/Redis healthy → migrations → fixture validation/seed → API providers → Agent durable workers → Web。health/live 是進程存活，ready 需依賴/worker readiness；健康不代表已成功退款或所有 Memory jobs 完成。
- **M08-R05**：fixture bootstrap 將 A/B/C 兩個欄位 case_context＋order_snapshot 組成 `{orders:[...]}` 存 `case-context.json.example`；複製 policy/evidence，speaker-only preload 存 `operational-memory.json.example`。以資料目錄掛載 API；in-memory map 以 order_ref 查。API 綁 actual case_ref。不得把 template human handoff_id=null 直接 POST。

## 正常／失敗流程：A/B/C 真模型

使用隔離 DB/Redis namespace/project。模型語句、similarity、耗時可以變；需完整紀錄版本、模型、UTC 起訖、schema 結果、HTTP request/response（去 secret）、case/events/activities、refund record、Memory candidate/approval/query 前後、影片或截图（若做 UI 驗收）。

| 段落 | 操作 | 必須證明 |
| --- | --- | --- |
| 準備 | 注入 12 個已核對 synthetic image metadata、兩類 Policy、speaker-only approved preload | 耳機無預填 Memory；models/dimensions/config hashes 一致 |
| A | [case-a](assets/demo/case-a.json.example) create_case_request POST `/cases`，保存 actual case_ref；等待 evidence，提交 followup_messages | 1200 TWD；Reviewer APPROVE → gate PASS；無人審；RESOLVED，SUCCEEDED/APPLIED |
| B | [case-b](assets/demo/case-b.json.example) 同流程；6200 TWD 人審 | 初次檢索無耳機 memory；APPROVE＋HIGH_VALUE_ITEM，不是 REVISE；人工 EDIT 改退回要求 |
| B EDIT | GET latest case.human_review.handoff_id，替換 [human-review](assets/demo/human-review.json.example) B request 的 null，核對 scope 才 POST review | correction_reason_code=RETURN_REQUIREMENT_INCORRECT、generalizable=true；保存前後 return requirement，若本來已免退須如實標沒有預期修正，不偽稱學到 |
| 學習 | 等 B 實際 job CREATE_CANDIDATE；核對 source_case_refs 僅 B、category headphones；query核准前無命中 | actual candidate ID及sources；SKIP/FAILED使學習段落不通過，不手工建耳機經驗替代 |
| 治理 | trusted governance approve(actual memory_id)，保留 approved_at/event；同 control query 再查 | CANDIDATE→APPROVED 才能見，不能僅改 fixture status |
| C | [case-c](assets/demo/case-c.json.example) create→初次摘要→補件→重摘要；6800 TWD | 前後 hits 包含同 B memory ID及cosine；仍需獨立證據和高額人審；綁 C handoff 的 APPROVE，退款成功 |

A preload 是展示既有經驗，不能算本次學習。C 仍高額，不要求自動退款。圖片是合成素材、runtime 只解析 reviewed metadata，不宣稱真打 vision。UI每則單 ref，因此三附件 followup 可用 API；B 精確 correction/generalizable 與 C review 同樣可 API 操作，UI 同時觀察。

## 驗收條件

- **M08-R06**：重建後先 deterministic C01～C36，再 migration／Docker／HTTP＋Redis＋SSE／Web checks，最後 real LLM A/B/C。每段 stop_if 包含 unexpected routing、沒有 actual candidate、Candidate提前可見、假 learning、退款未 APPLIED；不要為通過而修改 Policy 或原業務 validator。
- **M08-R07**：既有專案測試入口等價實作：`uv sync --all-packages`、各 package pytest、cross-service pytest（LANGGRAPH_STRICT_MSGPACK=true）、npm ci/test/lint/build、migration empty+upgrade、受影響 Docker build、Playwright browser regression。真模型 opt-in，不做 CI 必要依賴。
- **M08-R08**：保留完整 output 與 elapsed，不承諾逐字／數值相同；任何 SKIP、model fail、unexpected human route 都需記錄。真實金流、production auth、governance UI 不在基準。
