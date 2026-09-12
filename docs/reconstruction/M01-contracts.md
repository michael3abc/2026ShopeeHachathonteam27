# M01：Domain／Contracts

## 責任與非責任

共享執行契約：Domain／Provider／service／UI／Activity DTO、registry、gate、adapters、JSON Schema。不得持有 DB session、API app、graph execution；不把 UI projection 反向當可信授權。

## 依賴

Python 3.12.0、Pydantic v2；金額 Decimal、UTC datetime；非 Python 消費者依 [schema catalog](assets/contract-catalog.json) 與 [完整 schemas](assets/schemas/agent/AgentCommand.schema.json) 生成型別。所有模型欄位／required／enum／discriminator／bounds 在本包 schema，完整欄位展開見 [介面](interfaces.md)。

## 輸入輸出

`CaseContextLoadResult → IntakeResult → PolicyBundle → EvidenceAssessment → ResolverOutput → ProposedDecisionHandoff → VerificationResult → ReviewResult → HumanReviewDossier/ResolutionHandoff`。MemoryCandidate 與 ApprovedMemory 分離；MemorySearchHit 的 similarity 不存為 confidence。`AgentStartRequest/AgentResumeRequest/AgentRunResult` 是 runtime API；`AgentCommand/AgentServiceEvent` 是 transport；UI 使用 CaseDetail/AgentEvent/ActivityEvent。

## 資料與演算法

- **M01-R01**：ContractModel 禁止未知欄位；reference 必須非空。UTC timestamp 只接受 UTC offset（`Z` 或 `+00:00`），非 UTC offset 不當同義輸入。金額 JSON 輸出十進位字串，非負；不要用 JS Number 做授權加總。
- **M01-R02**：[registry](assets/registry.json) 完整列出 10 個 claim：DELIVERY_CONFIRMED、ORDER_WITHIN_RETURN_WINDOW、SHIPMENT_SEAL_INTACT、ITEM_PHYSICALLY_DAMAGED、DAMAGE_PRESENT_ON_ARRIVAL、ITEM_FUNCTIONALLY_IMPAIRED、ITEM_DIFFERS_FROM_LISTING、WRONG_ITEM_RECEIVED、ITEM_NOT_IN_SHIPMENT、ITEM_UNUSED。定義 subject scope、satisfiable_by、accepted evidence types、observable requirement、distinguish_from；不能臨時創 claim。distinguish_from 必須對稱。
- **M01-R03**：從 Policy 全部 required_claim_ids 聯集產生 expected pairs：ORDER claim 一次，LINE_ITEM claim 對每個原申請 item 各一次。findings 必須集合完全相同、不能重複／缺漏／多餘。不按模型輸出的清單推導原申請範圍。
- **M01-R04**：每個 item 的狀態包含共同 ORDER claims。至少一品項全部 SUPPORTED → SUFFICIENT_FOR_APPROVAL；所有申請品項各至少一項 CONTRADICTED → SUFFICIENT_FOR_DECLINE；其餘 INSUFFICIENT。退款 scope 只能取所有 required claims 均 supported 的品項；可退部分申請品項，但每品項為全額，不支援任意金額 partial refund。UNSUPPORTED 不等於 CONTRADICTED。
- **M01-R05**：EvidenceRequest.missing_claims 必須恰為全部尚未解決且允許 USER_EVIDENCE 的 pairs；accepted types 恰為 registry union。SYSTEM_FACTS-only 不向使用者索取。policy/evidence refs 必須指向當前 bundle。artifact resolve 結果須與 requested ref、來源與 subject 一致。
- **M01-R06**：draft 不含 amount/currency；金額由 scope 加總 line refundable_amount 並檢查上限，currency 必須等於 snapshot。Policy allowed_actions 取交集；REQUIRED/NOT_REQUIRED 不能被模型退回建議推翻，MODEL_JUDGMENT 才由模型選 requirement。DECLINE scope 為空、amount 為 0、不得有 return_decision。
- **M01-R07**：Reviewer 只 APPROVE／REVISE。APPROVE 無 revision reasons、refunding scope 必須由自己的 findings 支持；DECLINE 必須符合所有 item 可拒絕。REVISE 必附具體 structured reason、required_change、有效引用。
- **M01-R08**：dossier 的 proposal/review 等長；proposal IDs unique，同 case、order_snapshot_ref、policy_bundle_version、claim_registry_version。輪次必為 0..n；events 數 n，event[i] 指 proposal[i]、review[i]、相同 case、round=i+1，且 review=REVISE。未經 Reviewer 的 verification 重提案不放入 dossier 審核序列。
- **M01-R09**：兩種人審入口：耗盡修正次數＋最後 REVISE＋無 gate；或最後 APPROVE＋程式重算 HUMAN_REQUIRED 且 config version/hash/status/reason/amount/threshold 全等。dossier 最後兩項等於傳入 handoff/review。
- **M01-R10**：人工可重判證據但 scope 不超原申請。Policy bundle 不能改、order 同一訂單／幣別、最新 refundable 上限仍適用。APPROVE 採原建議；REJECT 結果為 DECLINE；EDIT 用 corrected_decision，return source=HUMAN_REVIEW。不是讓人工直接填金額。
- **M01-R11**：Memory 有可泛化 trigger/action、retrieval_summary 與修正來源，scope 必須可由源案件支持；summary 禁止 URL、個資格式、憑證。schema 不取代完整安全與範圍驗證。

模型內建 validators 的完整拒絕條件另有 [生成清單](assets/semantic-validation-inventory.json)，含 enum/union variant 的額外一致性；重建須逐一對應實作，不只跑 JSON Schema。

## 正常／失敗流程

先解析輸入 → schema → context-dependent validators → 執行／投影。Provider shape 錯誤或版本不符在 runtime 多數落 CONTRACT_VIOLATION；API 依邊界回 4xx 或 unavailable，不把未知物件當有效。HTTP request shape 錯誤 422；schema 允許不代表跨物件能通過。

## 驗收條件

C01～C06、C10～C13：合法 cross-object fixture 可通過；改 early proposal 版本、漏 claim、重複 subject、unsupported refund、改 amount、偽造 gate、漏 revision event 全拒絕。Python 與 JSON Schema 對形狀一致；TypeScript 從同一 schema 產生，不手寫另一套 drift 的 DTO。
