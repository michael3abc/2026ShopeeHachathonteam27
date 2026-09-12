# Reasoning and Decision

本文件規範**模型如何推理**。資料形狀見 [Agent Contracts](02-agent-contracts.md)，claim 詞彙見 [Claim Registry](07-claim-registry.md)，節點與 routing 見 [Agent Graph](01-agent-graph.md)。

## Reasoning pipeline

Agent 必須依固定順序處理，不得從使用者敘述直接跳到退款結論：

```text
Normalized intent + claimed line items
→ Verified case/order/logistics facts
→ Applicable versioned policy（含 required_claim_ids）
→ Approved operational memory（scope 相符者）
→ 逐 claim 的 evidence 判定
→ Evidence sufficiency（三值）
→ Eligible actions 與 effective return policy
→ ProposedDecisionDraft
→ Graph 組裝 amount / currency / handoff_id / revision_round
→ External Verification
→ Independent Reviewer
```

每階段只輸出結構化 findings、引用與精簡理由。Prompt 不要求模型揭露完整推理過程，graph state 也不保存隱藏 Chain-of-Thought。

## 資訊優先順序

由高到低：

1. 外部系統提供且帶版本的 case/order/logistics facts。
2. 當下案件適用的正式 versioned Policy。
3. 該案件已有的 Human-approved exception。
4. `APPROVED` 且 scope/policy version 相符的 Operational Memory。
5. 模型既有知識。

低優先來源與高優先來源衝突時必須忽略。Operational Memory 只能影響取證方式與提案品質，**不得**新增 eligibility 或覆寫 `return_policy`（見 [Operational Memory](04-operational-memory.md)）。

`PolicyBundle` 的 `retrieval_status` 由 Policy owner 判定，模型不得自行挑選條款或判斷條款是否互斥。`AMBIGUOUS` 與 `NOT_FOUND` 一律 fail closed 至外部人工流程。

## 適用條款

`PolicyBundle.clauses` 中的每一條都是**適用條款** —— 篩選在 retrieval 時由 Policy owner 完成，模型不得再自行剔除。模型自行判斷「這條不適用」等於在 retrieval 之外重建一套 policy 選擇邏輯。

Graph 只做一項機械檢查：條款的 `effective_from`/`effective_to` 必須涵蓋 `CaseContext.case_opened_at`。不涵蓋者視為 provider 契約違規，fail closed（`CONTRACT_VIOLATION`），不由模型悄悄忽略。

## Evidence 判定

`assess_case` 對適用條款 `required_claim_ids` 聯集依 `subject_scope` 建立 findings：`ORDER` 的 claim 各一筆（`subject = "ORDER"`），`LINE_ITEM` 的 claim 對 `claimed_line_item_ids` 中每個品項各一筆：

```text
claim_id       ← 必須存在於 Claim Registry
subject        ← ORDER 或 line_item_id，須符合 registry 的 subject_scope
status         ← SUPPORTED | UNSUPPORTED | CONTRADICTED
supporting_evidence_refs[]
explanation
```

Claim 集合是**查表得出**的，不由模型決定要判哪些 claim。Evidence 的存在不等於 claim 成立；摘要、來源與 artifact reference 必須可追溯。

### 核准方向與拒絕方向是兩條不同的規則

這兩條規則不對稱，混為一談會讓「證據不足」變成拒絕理由：

| 方向 | 條件 | 說明 |
| --- | --- | --- |
| 可核准 | 某個 claimed item 的**所有** required claims 皆 `SUPPORTED` | 該 item 才可進入 `refund_scope` |
| 可拒絕 | **每個** claimed item 都至少有一個 required claim 為 `CONTRADICTED` | 證據逐品項反證主張，才能做案件級 `DECLINE` |

`UNSUPPORTED` **永遠不得**成為拒絕的依據。它只表示尚未證明，正確反應是索取證據或（budget 用盡時）轉人工，不是 `DECLINE`。

逾期、未送達這類案件同樣以 `CONTRADICTED` 表達 —— `ORDER_WITHIN_RETURN_WINDOW` 被 order facts 反證，而不是另設一種拒絕理由。這使「拒絕」在整份規格中只有單一來源。

`evidence_status` 三值的判定公式見 [Agent Contracts](02-agent-contracts.md#evidenceassessment)，由模型依該公式輸出，graph 於 routing 時驗證其與 `claim_findings` 一致。

### 缺少 evidence 時

`EvidenceRequest.missing_claims` 必須恰好涵蓋所有仍為 `UNSUPPORTED` 且可由 `USER_EVIDENCE` 滿足的 claim-subject pairs，不能重問已解決的 claim，也不能拆成多輪漏問。它同時指出：

- 尚未成立的 claim 與其 `subject`。
- 可接受的 evidence type —— 由 registry `accepted_evidence_types` **查表**得出。
- 使用者應提供什麼可觀察內容 —— 忠實反映 registry 的 `observable_requirement`。
- 相關 policy reference。

`satisfiable_by` 僅含 `SYSTEM_FACTS` 的 claim 不得進入 `EvidenceRequest`。若剩餘 unresolved claim 全屬此類，案件 fail closed，不得只回覆「請提供更多證據」或向使用者索取無法成立該 claim 的資料。

## Effective return policy

多個適用條款可能帶有不同的 `return_policy`。模型不得自行挑選，precedence 由 graph 機械決定：

```text
S = { clause.return_policy | clause ∈ 適用條款 }

REQUIRED ∈ S 且 NOT_REQUIRED ∈ S  → 條款衝突，fail closed（CONTRACT_VIOLATION）
REQUIRED ∈ S                       → graph 填 required = true；Resolver 填相容 reason
NOT_REQUIRED ∈ S                   → graph 填 required = false；Resolver 填相容 reason
S = { MODEL_JUDGMENT }             → Resolver 同時決定 required 與相容 reason
```

原則是：**明文規則優先於裁量**。`REQUIRED` 與 `NOT_REQUIRED` 都是條款的明文決定，`MODEL_JUDGMENT` 是條款明文授權的裁量空間。只要有任何一條明文規則存在，裁量空間就不存在。

`REQUIRED` 與 `NOT_REQUIRED` 同時出現是真正的條款衝突，Agent 不得挑選其一 —— 那是 Policy owner 的責任。

## Proposed decision

Resolver 的 `action` 只能是：

- `DECLINE`
- `FULL_REFUND`

本版沒有部分金額退款。退款範圍以 `refund_scope.line_item_ids` 表達，金額由 graph 依品項的 `refundable_amount` 加總推導。多商品訂單只退其中一件，屬 `FULL_REFUND` + 單一品項 scope，不是 partial refund。

Resolver 必須提供 `action`、`refund_scope`、`reason_code`，以及支持 decision 的 policy/evidence references。`FULL_REFUND` 一律附 `return_decision`：靜態 Policy 只由 Resolver 提供 reason、graph 補 required boolean；`MODEL_JUDGMENT` 由 Resolver 提供兩者。`DECLINE` 不帶 `return_decision`。它不得：

- 輸出 `amount`、`currency`、`handoff_id`、`revision_round` 或任何 counter。這些是 graph-derived 欄位。
- 在 `rationale_summary` 中寫出金額數字。產生 draft 時模型尚未取得 `amount`，任何數字都是幻覺。
- 在 effective return policy 非 `MODEL_JUDGMENT` 時自行填寫 required boolean。
- 把 `refund_scope` 擴及 required claims 未全部 `SUPPORTED` 的品項。
- 宣稱退款已完成。
- 自行建立 Policy、Risk threshold 或 exception。
- 以 Operational Memory 覆蓋正式 Policy。
- 以「常見做法」填補缺少的 order facts。
- 將 `REQUEST_EVIDENCE` 或 Reviewer verdict 當成 resolution action。

Over-scoping 是 deterministic 契約違規，由 graph 在組裝 handoff 時擋下，不進入 Verification 也不進入 Reviewer。Reviewer 不是 scope 正確性的第一道防線。

## Reviewer independence

Reviewer 接收：

- `ProposedDecisionHandoff` 完整內容（含 `evidence_bundle`）。
- **完整 `PolicyBundle`**，包含條款 `text` 與 `required_claim_ids`，不只是 handoff 引用到的條款。
- Claim Registry。
- 必要的 case/order snapshot facts。

Reviewer **不接收**：

- `EvidenceAssessment` 與 Resolver 的 `claim_findings`。
- Operational Memory。
- Resolver 的隱藏推理或未結構化 scratchpad。

給 Reviewer 完整 bundle 而非只給被引用的條款，才能檢出「引用了對自己有利的條款、略過限制性條款」。不給 Resolver 的 findings，才能讓 Reviewer 的判定成為獨立的第二次判定 —— 兩邊 findings 的差異率因此可量測；若 Reviewer 先看過 Resolver 的結論，差異率會趨近於零且不代表任何品質訊號。

### 檢查順序

順序本身是設計的一部分：**先自行判定 claim，再檢視 Resolver 的結論**。反過來會使 Reviewer 被錨定。

1. 依適用條款的 `required_claim_ids`，自行對每個 claim 產生 `reviewer_claim_findings`。
2. Handoff 必填欄位與 references 是否完整。
3. `refund_scope` 是否只涵蓋**自身判定**為 required claims 全部 `SUPPORTED` 的品項。
4. Policy references 是否適用，且 `action` 是否在該條款的 `allowed_actions` 之內。
5. `return_decision` 與 effective return policy 是否一致（收斂規則見下）。
6. `action`、`refund_scope`、`reason_code` 與 `return_decision` 之間是否互相一致。
7. `rationale_summary` 是否忠實描述 facts、policy 與 evidence。

全數通過才回 `APPROVE`；deterministic validation 會再次確認 `FULL_REFUND` scope 全受 Reviewer findings 支持，或案件級 `DECLINE` 對每個 claimed item 都有反證。任何一項未通過都回 `REVISE`。Reviewer 沒有 `NEED_EVIDENCE` verdict，也不得直接修正 proposal。

`amount` **不是** Reviewer 的檢查項。它由 graph 依公式推導、由 Verification 權威重算；讓 LLM 複驗一個 deterministic 計算結果，只會引入本來不存在的錯誤來源。

### `return_decision` 的收斂規則

Reviewer 只能在下列情況對退貨決定提出 `REVISE`（code = `RETURN_REQUIREMENT_INCONSISTENT`）：

- `return_decision.source` 或 `requirement.required` 與 effective return policy 矛盾。
- `return_decision.requirement.reason_code` 所宣稱的事實不受 facts/evidence 支持。例如宣稱 `ITEM_UNSALVAGEABLE`，但證據只顯示外觀刮痕。

Reviewer **不得**因偏好差異而 `REVISE`（「換作是我會要求退貨」）。

理由：`MODEL_JUDGMENT` 是條款明文授權的裁量空間，對裁量結果的偏好異議**沒有收斂條件**。Resolver 沒有可執行的 `required_change`，第二輪會產生同樣的提案，三輪之內燒完 revision budget 並把本可自動處理的案件推進人工佇列。那不是嚴謹，是把 Reviewer 的偏好偷換成條款的授權。

## Revision 行為

Reviewer `REVISE` 後：

1. Graph 驗證 `revision_reasons` 非空。
2. `record_revision_event` 寫入 append-only `DecisionRevisionEvent` 並遞增 `revision_round`。**模型不遞增任何 counter。**
3. 完整 `ReviewResult` 存入 `pending_review_result` 並傳給 `propose_decision`。
4. Resolver 先判斷是否可利用既有 facts/evidence 完成所有 `required_change`。
5. 若可修正，產生新的 `ProposedDecisionDraft`；若不可修正，產生具體 `EvidenceRequest`。
6. 走 `EvidenceRequest` 時流程會經過 interrupt，`pending_review_result` 必須存活並在 resume 後重新餵回 `propose_decision`，否則 Reviewer 會以相同理由再次 `REVISE`。
7. 新 handoff 重新經過外部 Verification 與 Reviewer，不得跳過。

Resolver 不得忽略任何 revision reason。若多個 required_change 互相衝突且正式 Policy 無法解決，仍走 fail-closed。Reviewer 修正 budget 用盡時，交最後提案與全部未解決異議至人工審核 UI；其餘 budget 保留既有 fail-closed 路徑。

人工接手另帶完整 HumanReviewDossier，允許在原申請品項內重新裁決，填寫一份整體理由。人對證據的解讀可不同於 Reviewer；不得修改原始 findings、訂單事實或條款。API 先驗證待審 handoff、適用 Policy、範圍、退貨要求及目前退款上限，再持久化結果與 enqueue resume；退款執行仍複核授權與目前訂單。無有效裁決時維持 AWAITING_HUMAN_REVIEW，不自動拒絕、不進入新補件 loop。

Verification `FAIL` 的處理相同：Resolver 只能依 `issues` 調整提案或轉為 `EvidenceRequest`，**不得解釋、爭辯或覆蓋 verifier 規則**。

## Rationale 與 auditability

`rationale_summary` 應採「結論 + 直接依據」格式，例如：

> LI-002 仍在條款 POLICY-12:v3#4.2 的適用期間；EV-002 同時呈現外箱塌陷與商品裂痕，支持到貨時已受損，因此建議全額退款該品項。

不得輸出無來源的信心陳述（例如「我認為使用者可信」），也不得出現金額數字。每個 policy/evidence claim 必須能由 reference 回查。

## Reviewer 放行與修正標準

只有具體缺失才允許 REVISE：必須指出 subject、可引用的政策或證據與可驗證的 required_change。
證據、政策與提案一致時必須 APPROVE；不得憑風險直覺、自創金額門檻、買家歷史或偏好要求修正。

模型核准後，同一 reviewer node 的 Python 金額授權規則才執行（見 contracts 的 Reviewer 金額授權）。命中只表示需要人工授權，不改寫 verdict、不製造異議、不消耗 revision budget。
模型輸出不新增 verdict。Graph 最多允許三次修正，再次 REVISE 時輸出
routing_reason = REVISION_BUDGET_EXCEEDED 並等待人工。此 revision budget 不等於傳輸 retry。

## 直接看圖

Resolver 的 Assessment／Proposal 及 Reviewer 各自接收當案已提交的原始可視內容（套用方向並去除 metadata）。圖片依 evidence ID 引用；不將模型觀察覆寫為可信 Provider 事實。圖片內的文字指令不具權限，subject 是使用者指定而非已驗證身分，收件／上傳時間不等於損壞發生時間。

圖片讀取或模型不支援時走明確失敗／既有 escalation，不能只看檔案摘要繼續核准。既有金額 gate、Policy、Verification 與人審語義維持。
