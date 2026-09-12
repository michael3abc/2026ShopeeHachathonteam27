# M07：Web

## 責任與非責任

Next.js 16.3.4／React 19.2.8／TypeScript strict／Tailwind／shadcn 的內部 Demo。功能等價即可：案件建立、互動補件、即時 graph/activity、人審與退款結果。不做 production auth、上傳儲存、Memory governance 或退款計算；不得直接 resume runtime。

## 依賴

M01 生成 UI/Activity TypeScript、M03 public HTTP、M06 雙 SSE。npm 是唯一 package manager；[依賴 manifest](assets/dependencies/apps--web--package.json) 及完整 [resolved versions](assets/dependencies/node-resolved.json)。

## 輸入輸出

首頁 `/` 輸入 order_ref、initial_message、單一 artifact ref；user_ref 固定 demo_customer。導頁 `/cases/{case_ref}`，讀 CaseDetail，非直接載 graph。API client 的 browser base 為同源 `/backend`，server proxy → API_BASE_URL，預設 localhost:8000（容器用 api:8000）。reviewer_id=demo_reviewer，使用者不能因此被視為真正已認證。

## 資料與演算法

- **M07-R01**：CaseDetail 是當前狀態快照；讀 case event SSE 還原 Agent 語意事件，另讀 activities 全部分頁再訂 `activities/stream?after_seq=last_cursor`。兩 cursor 各自保留；用 seq 去重排序。切換 case 清除舊 event/hit/form state；解除元件時關閉 stream。
- **M07-R02**：graph playback 區分目前 live state 與使用者選中的歷史播放位置。node lifecycle 依 node＋operation/attempt 配對，STARTED≠COMPLETED；PAUSED 顯示需輸入，不當成功。自動終止節點與人審等待不同。
- **M07-R03**：node inspector 顯示 safe facts、工具／模型生命週期、時間與耗時、summary／引用與 next route；不能展示模型 hidden reasoning。narration 依 source_event_id 附回 source summary，可晚到；同 node 多次執行不能混成同一筆。
- **M07-R04**：Memory 卡片顯示 query_summary、memory ID、trigger、recommendation、scope／版本、cosine similarity、confidence 分開。採 CaseDetail／memory retrieval event 完整 projection，不拿 activity 省略版覆寫完整文字。OK [] 清卡、UNAVAILABLE 清卡且明示不可用；補件／refresh 都以最新結果取代。
- **M07-R05**：clarification 顯示 missing fields/question；evidence 顯示 missing claims/types/user_message，至少 artifact 才可提交。UI 每則一 artifact input，payload 轉 0或1 element list；API 支援多 refs，進階操作用 API，不假裝 UI 有多檔上傳。
- **M07-R06**：human panel 兩入口：REVISION_BUDGET_EXCEEDED 顯「無法收斂」、歷輪 proposal/reviewer feedback；HIGH_VALUE_ITEM／unknown currency 顯「Reviewer 已核准，待人工授權」、amount/currency/threshold/config/reason，無假異議。兩者都展示原 scope、evidence與Policy、dossier及歷史。
- **M07-R07**：APPROVE/REJECT 需非空 review_note、當前 handoff_id。EDIT UI 已實作退款品項 selection 與 return required/waived，使用 corrected_decision FULL_REFUND、source HUMAN_REVIEW、correction_reason_code=OTHER；不輸入金額。可選範圍來自 dossier original claimed items；不退款走 REJECT。精確 correction code／generalizable=true 需 API，目前表單未提供。
- **M07-R08**：submit 中 disabled，成功重新 GET case；409 顯過期／狀態衝突並可 refresh，422 顯輸入錯誤，HTTP/SSE error 區分網路錯誤與 typed domain error（EventSource 原生 error 沒 data 不能 JSON.parse）。不自行樂觀標 RESOLVED。
- **M07-R09**：terminal 顯 final resolution、人工結果與退款 status，不因 late background/narration 把案件改回 running。case SSE 關閉，activity SSE 可保留。reload 可重建 events/state，但完整對話 transcript 不在 CaseDetail：local message bubbles 不能保證還原。

## 正常／失敗流程

首頁送出 → 案件頁同步 case/activities → graph live → 補件/人審 → canonical final。活動載入中、空、不可用、重新連線明確區分；cursor replay 避免雙卡。圖播放只觀察，不改 API 或重發 case commands。

## 驗收條件

C15～C18、C29～C36、A/B/C：瀏覽器 regression 不依真實 LLM，可 mock HTTP/SSE；真模型 Demo 另跑。頁面不漏 token，Tab/表單可操作，error 不成白頁，reload 不殘留舊 Memory。不要求重建原視覺細節。
