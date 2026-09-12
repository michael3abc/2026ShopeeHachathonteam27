# 從空專案重建的交接計畫

穩定任務ID，依賴DAG見 [tasks.json](tasks.json)。先 deterministic 測試再接外部模型；各任務輸出自己的程式／測試，不需要原應用原始碼。

| 任務 | 前置／輸入材料 | 交付物 | 測試／完成條件 |
| --- | --- | --- | --- |
| T01 骨架與依賴 | 無；README、00、M08、dependencies | uv workspace四Python packages；Next/npm；獨立entrypoints、Compose；lock | Python3.12.0安裝，npm ci；API不得import runtime |
| T02 Contracts與驗證 | T01；M01、schemas、registry/gate、semantic fixtures、validation inventory | DTO/union、schema parity、Decimal、registry、deterministic validators、TS generation | C01～C06/C10～C13；不能只有schema通過；全部M01規則對應測試 |
| T03 DB與Case API | T02；M03、data、freshDDL、interfaces/OpenAPI | SQLAlchemy/Alembic、canonical status、public routes、command outbox介面 | 空DBmigration；錯status409；case/event/outbox同transaction rollback；C15/16 |
| T04 能力與fixture adapters | T03；M04、demo素材、Provider schemas | context/evidence/verification/human store/refund application、exact bundle lookup、reservation | C10～C13/C19～C21；無真金流；auth偽造fail；多item並發rollback |
| T05 Graph與模型adapter | T02；M02、model-tasks、prompts、state、model schemas | 16node graph、typed state、budgets、assembly、interrupt/checkpoint、fake與真模型adapter | C01～C09/C14；重啟resume，不耗錯counter；Reviewer不讀Memory |
| T06 跨服務主流程 | T04,T05；M06/HTTP/Redis契約 | workers/journal、HTTP Providers、outbox/API projection、durable checkpoint | START→補件→人審→refund；C07～C21；重送不雙付／不二次裁決 |
| T07 VDB與學習 | T06；M05、embedding、fixtures | ingest/reembed、atomiccandidate、governance、backfill、querysummary、Memory replayworker | C22～C29；同scope較相關低confidence勝；actual candidate核准前後可見性 |
| T08 Activity與narration | T06；M06、Activity schemas、sample SSE | observer、boundedpublisher、activityprojection/outbox/SSE、narrationworker | C30～C36；provider阻塞期間start已抵達；offline無modelcall |
| T09 Web | T06,T07,T08；M07、public schemas、examples | 首頁/案件頁、dualSSE、graphplayback/inspector、Memory卡、人審EDIT、error/reload | Playwright mockedHTTP/SSE；C15～C18/C29～C36；human payload綁pendinghandoff |
| T10 整合與A/B/C | T09；M08、acceptance、demoassets | Docker、DB演練、conformance report、真模型完整輸出／耗時 | A自動退款、BEDIT→actualcandidate→approve→C命中並退款；SKIP/錯route明記 |

每T交接附：變更摘要、輸入manifest hash、測試命令/exitcode、通過C清單、未通過與理由。各module全部R規則均需追蹤；不能用前任「測過」替代自己的artifact。

放行：T02前不可改DTO避validator；T04前不接真金流；T06前不宣稱跨服務workflow；T07前不宣稱B→C學習；T09前不宣稱UI等價；T10前不宣稱重建完成。
