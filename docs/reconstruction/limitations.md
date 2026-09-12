# 現況、未實作與矛盾（不要自行轉成新需求）

## 已確認的產品邊界

- 固定demo_customer/demo_reviewer；public case/review/activity沒有正式使用者／RBAC/tenant authorization。internal token不是public auth。
- 訂單合成fixtures；refundapplication模擬，不接Shopee live API或真金流。
- Evidence只解artifact ref至metadata，沒有upload/blobstore/OCR/vision；圖片供人工核對，不宣稱Agent看过bytes。
- UI每message一artifact；API可多refs。EDIT UI已存在，但correction code固定OTHER、沒有generalizable欄位；B精確學習payload要API。
- API保存user messages，但CaseDetail／caseevent SSE非完整user transcript replay；refresh不能還原全部對話。
- Memory governance僅trusted service，無UI／publicHTTP；不是自動自我核准。
- UI功能等價，不要求重做原像素、CSS或每項圖播放動畫。

## 已知可靠性／安全限制

- Activitypublisher為有界記憶體queue→Redis，無producer-sideDBoutbox；crash/queuefull會缺trace並記failed。API持久化部分才具dedup/outbox保證，非end-to-end完整。
- regex redaction和allowlist不是通用個資辨識器；業務messages/handoff和restrictedreject記錄不等於Activity安全surface。
- POST create沒有Idempotency-Key；重送可新案。messages/review以pending狀態與handoff綁定防重送，不保證重複HTTP返回相同成功payload。
- 部分internalprovider領域例外未統一轉4xx/503，可能500。不能以empty成功掩蓋；改善errorcontract需另版需求。
- defaultdemo/unconfigured非integratedworkflow；health200不是LLM/退款/RAG驗收。production profile拒絕未完成composition。
- 合成case opened/delivered固定；重跑須保留日期相對性與Policy有效範圍，不任意改日期當相同基底。

## 文件／程式與素材矛盾

| 項目 | 現況及處理 |
| --- | --- |
| 舊WebREADME寫EDIT未實作 | baseline已有EDIT；本次僅修README，UI不改 |
| 歷史revision「第3次不過」 | code limit3代表三次修正，round0..3最多4次review；本包依code，非新行為 |
| Agent-only docs範圍 | 保留細部來源；本包補API/DB/UI/部署全快照 |
| 歷史Risk migration名稱 | 不代表現行riskgate；terminate與human不同 |
| Policy「證據不足可否拒絕」文字矛盾 | 不改Policy文字。deterministic UNSUPPORTED不能DECLINE；記錄並獨立處理，不在文件/VDB時改業務 |
| Narration版本 | inline無版本constant，標unversioned-inline@485048c及hash，不偽造版本 |
| assets-manifest pendingverification/artifact不可解析 | template素材標记保留；檔案存在不代表已核對／runtime注入。T10重新核對，不把修改來源當證據 |
| 模型gateway預設 | 原compose站台URL明示換portable placeholder，無私key/主機依賴 |

本次未重新跑真LLM A/B/C，不複製舊run credentials、環境paths或DB記錄。提供的是重建驗收步驟／合成fixtures；重建完成由新系統證據判定。
