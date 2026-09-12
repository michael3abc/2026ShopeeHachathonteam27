# M04：案件能力與退款

## 責任與非責任

可信 order snapshot、Evidence metadata、deterministic Verification、金額授權、refund execution／application。Evidence 不做圖片 bytes 理解，沒有 upload／OCR。mock refund 不接真實金流。

## 依賴

M01 validators、M03 DB、M05 persisted Policy bundle；fixture adapters 可替換為 production connectors，但 contract／授權不可弱化。實際方法、參數 schema 在 [Providers](interfaces.md)。

## 輸入輸出

CaseContextLoadResult 含 case_ref/order_ref/market/opened_at/snapshot_version 與 OrderSnapshot 的不可變版本、幣別、delivered_at、line_items、max/already_refunded。EvidenceItem 含 evidence_id/type/source/subject/artifact_ref/extracted_summary/collected_at，不把 model claim 結論存成事實。Verification 返回 PASS／FAIL issues／UNAVAILABLE。公開 RefundExecutionRecord 只有 SUCCEEDED／REJECTED，application result 只有 APPLIED／REJECTED；DB 執行中是 IN_PROGRESS，未知結果以 unavailable exception 保留，不發明公開 PENDING／FAILED variant。

## 資料與演算法

- **M04-R01**：context provider 依 canonical case 綁可信 order_ref。fixture 模式支援依 order_ref 選各 A/B/C snapshot；產生 case-context 時換成實際 case_ref，而不是使用模板 case ID。
- **M04-R02**：artifact_ref 是 opaque lookup，不是下載指令。unknown ref／malformed result → fail closed。完整抽取 metadata 可供模型判斷 claim，不允許 provider 宣告退款資格。
- **M04-R03**：Verification 載入目前 order、exact persisted Policy bundle，驗 handoff hash/ID、case/order、金額scope、幣別、最大可退及 return policy。same handoff+same hash 重送可回既有記錄；相同 ID 改內容衝突。缺原 bundle 不能重新檢索一份當作同版本。
- **M04-R04**：共用 reviewer-gates:1.0：FULL_REFUND 且 TWD>5000 或 SGD>200 → HUMAN_REQUIRED/HIGH_VALUE_ITEM；等於門檻 PASS；未配置幣別 → CURRENCY_THRESHOLD_UNCONFIGURED。DECLINE → NOT_APPLICABLE。REVISE 不跑 evaluator。threshold 由 Decimal，無換匯。config fingerprint：幣別排序、Decimal 固定小數文字去尾零、JSON sort_keys（預設 separators），SHA256；不是另份語意相同但 hash 不同的設定。
- **M04-R05**：執行層重新 evaluate gate；不能只信 REVIEWER_APPROVE 字樣。自動模式要求相同原 proposal、PASS verification、有效 APPROVE review、與當前 config 完全相同的 PASS/NOT_APPLICABLE gate。高額偽造 auto approve、改 config/version/hash 一律拒絕，不 fallback。
- **M04-R06**：human 授權需要 persisted review＋dossier＋結果一致。核對 case、handoff、resolution ref、review、payload hash 與合法入口；EDIT 重新檢查原申請 scope、最新 order、原 Policy、return requirement；不需要再交 Reviewer。
- **M04-R07**：execution_ref／handoff_id／request hash 綁定一筆執行。同 ID 相同內容回終態或 resume IN_PROGRESS，異內容 conflict。先把 validated execution 持久化，再標記 application_started；對每個 `(order_ref,line_item_ref)` 建 reservation，防同案及跨案重複退款。只用 order總上限不足以防同品項重退。
- **M04-R08**：reservation 與 application attempt 的記錄先 commit，再呼叫外部 application（不可跨網路持 DB 鎖）。成功 APPLIED 寫 successful-item ledger；已嘗試但結果未知不能釋放 reservation 讓其他 execution 接管。外部 error 恢復用原 execution_ref/idempotency key，不能改 key「再試一筆」。
- **M04-R09**：若執行前已有 reservation owner 必須匹配，若曾呼叫 application 後遺失 reservation 屬完整性錯誤。持久化 final result 後 publish case projection；application 回 REJECTED 如實記錄，不能包成 SUCCEEDED；exception 表示不可用，不是合約中的 FAILED result。

## 正常／失敗流程

正常：verify PASS → Reviewer approval/gate 或 human authorization → execute load persisted authorization → current state checks → IN_PROGRESS/reserve → apply → persist terminal → case RESOLVED。拒絕退款決策不發出付款；流程仍可 RESOLVED。發生 ambiguous transport failure：保持 IN_PROGRESS＋reservation → get_status／同 request resume；確定拒絕或 auth rejection 可終止自動化，不把未付當已付。

## 驗收條件

C10～C13、C19～C21：threshold below/equal/above、unknown currency、DECLINE/REVISE；初次 APPROVE 可直接人審。偽造 auto review／human result／config hash 被拒；並行同 item 只有一 owner；apply 成功後斷線重送仍只退款一次。
