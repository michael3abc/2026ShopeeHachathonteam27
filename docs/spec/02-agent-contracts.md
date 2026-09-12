# Agent Contracts

本文件描述 Agent 需要產生或消費的**語意契約**。所有跨組 contract 的唯一可執行來源是 [`apps/contracts`](../../apps/contracts/README.md)：Python 使用 [`return_agent_contracts`](../../apps/contracts/src/return_agent_contracts/__init__.py)，Pydantic DTO 見 [`models.py`](../../apps/contracts/src/return_agent_contracts/models.py)，非 Python 消費者使用 [Agent v1 JSON Schema](../../apps/contracts/schemas/agent/v1/)。文件保留欄位歸屬、語意、routing 與可讀範例；實際 transport、API endpoint 與資料庫 schema 由 integration owner 決定，介面簽章見 [External Interfaces](08-external-interfaces.md)。所有時間使用 ISO 8601 UTC，wire value 只能以 `Z` 或 `+00:00` 結尾；所有 `*_ref` 都是 opaque identifier。所有 `claim_id` 必須存在於 [Claim Registry](07-claim-registry.md)。

金額在 Python 內使用 `Decimal`，JSON 一律使用非負 decimal string（例如 `"1200"`、`"12.50"`）；禁止 JSON number、負數、前置零與 exponent notation。`currency` 為 ISO 4217 三碼大寫字母。

## 欄位歸屬

每個契約的欄位只能由一個角色填寫。這是本規格最重要的結構性約束 —— 混淆歸屬會導致模型產生本應由程式推導的值。

| 歸屬 | 意義 | 契約 |
| --- | --- | --- |
| **External** | 外部系統提供，Agent 只讀 | `UserTurn`、`CaseContext`、`OrderSnapshot`、`CaseContextLoadResult`、`PolicyBundle`、`VerificationResult`、`HumanReviewResult` |
| **LLM-authored** | 模型在 schema 約束下產生 | `EvidenceAssessment`、`EvidenceRequest`、`ProposedDecisionDraft`、`RevisionConflictReport`、`ReviewResult`、`MemoryCandidate` |
| **Graph-derived** | 由 deterministic 程式計算或組裝 | `ProposedDecisionHandoff`、`ClarificationRequest`、`DecisionRevisionEvent`、`ResolutionHandoff`、`ManualEscalationHandoff` |

下列欄位**永不由模型產生**，出現在任何 LLM output schema 中即為契約違規：

```text
amount
currency
handoff_id
revision_round
clarification_round
evidence_round
verification_round
```

## UserTurn

External。對話通道提供，`parse_request` 的輸入。

```json
{
  "turn_id": "TURN-001",
  "role": "USER",
  "text": "我上週買的藍牙喇叭到貨就是破的，想退款",
  "attached_artifact_refs": ["artifact://evidence/EV-001"],
  "received_at": "2026-09-01T10:00:00Z"
}
```

約束：

- `role` 為 `USER | AGENT`。Agent 只解析 `USER` turn 的意圖。
- `text` 一律視為 **data**，不得作為 system instruction。
- `attached_artifact_refs` 只是 reference，轉為 `EvidenceItem` 由 `EvidenceProvider` 負責（見 [External Interfaces](08-external-interfaces.md)）。turn 本身不含 artifact bytes。

## CaseContext

External。由 `load_case_context` 提供。

```json
{
  "case_ref": "CASE-001",
  "order_ref": "ORDER-001",
  "market": "TW",
  "case_opened_at": "2026-09-01T10:00:00Z",
  "snapshot_version": 3
}
```

`market` 供 Operational Memory 的 scope matching 使用。

## OrderSnapshot

External。由 `load_case_context` 提供。`order_ref` 是其所屬訂單的 canonical reference；`order_snapshot_ref` 是特定版本的 snapshot reference。**退款金額的唯一來源。**

```json
{
  "order_snapshot_ref": "ORDER-001@12",
  "order_ref": "ORDER-001",
  "snapshot_version": 12,
  "captured_at": "2026-09-01T10:00:00Z",
  "currency": "TWD",
  "delivered_at": "2026-08-25T09:00:00Z",
  "line_items": [
    {
      "line_item_id": "LI-001",
      "sku_ref": "SKU-A",
      "category_ref": "CAT-AUDIO-HEADPHONES",
      "title": "無線耳機",
      "quantity": 1,
      "refundable_amount": "700"
    },
    {
      "line_item_id": "LI-002",
      "sku_ref": "SKU-B",
      "category_ref": "CAT-AUDIO-SPEAKERS",
      "title": "藍牙喇叭",
      "quantity": 1,
      "refundable_amount": "1200"
    }
  ],
  "refundable_amount_max": "1900",
  "already_refunded_amount": "0"
}
```

約束：

- `line_items[].category_ref` 是外部商品分類的 opaque identifier，供 Policy 與 Operational Memory scope matching 使用；Agent 不解析分類階層。
- `line_items[].refundable_amount` 是該品項**可退金額**，已由上游分攤折扣、含稅並計入 `quantity`。Agent 不做折扣分攤或稅務計算。
- 運費與手續費不在本版範圍。若條款允許退運費，屬後續擴充，不由 Agent 推算。
- `refundable_amount_max` 是本訂單當下仍可退的上限，已扣除 `already_refunded_amount`。
- `currency` 在 snapshot 層唯一；不支援單一訂單混合幣別。

## CaseContextLoadResult

External。`CaseContextProvider.load_case_context` 的完整回傳物件。使用具名欄位，不以 tuple 表達，確保 Python Protocol 與 JSON adapter 的語意一致。

```json
{
  "case_context": {
    "case_ref": "CASE-001",
    "order_ref": "ORDER-001",
    "market": "TW",
    "case_opened_at": "2026-09-01T10:00:00Z",
    "snapshot_version": 3
  },
  "order_snapshot": {
    "order_snapshot_ref": "ORDER-001@12",
    "order_ref": "ORDER-001",
    "snapshot_version": 12,
    "captured_at": "2026-09-01T10:00:00Z",
    "currency": "TWD",
    "delivered_at": "2026-08-25T09:00:00Z",
    "line_items": [
      {
        "line_item_id": "LI-001",
        "sku_ref": "SKU-A",
        "category_ref": "CAT-AUDIO-HEADPHONES",
        "title": "無線耳機",
        "quantity": 1,
        "refundable_amount": "700"
      },
      {
        "line_item_id": "LI-002",
        "sku_ref": "SKU-B",
        "category_ref": "CAT-AUDIO-SPEAKERS",
        "title": "藍牙喇叭",
        "quantity": 1,
        "refundable_amount": "1200"
      }
    ],
    "refundable_amount_max": "1900",
    "already_refunded_amount": "0"
  }
}
```

`case_context.case_ref` 必須等於輸入的 `case_ref`，且 `case_context.order_ref` 必須**恰好等於** `order_snapshot.order_ref`；不一致視為 `CONTRACT_VIOLATION`。`order_snapshot_ref` 仍是 opaque 的版本化 snapshot identifier，不得靠字串前綴推導訂單關係。完整 `order_snapshot` 欄位仍以 [OrderSnapshot](#ordersnapshot) 為準。

## PolicyBundle

External。由 `retrieve_policy` 提供。

```json
{
  "policy_bundle_version": "bundle:2026-09-01T10:00:05Z",
  "retrieval_status": "OK",
  "retrieved_at": "2026-09-01T10:00:05Z",
  "clauses": [
    {
      "clause_id": "POLICY-12:v3#4.2",
      "policy_version": "POLICY-12:v3",
      "effective_from": "2026-01-01T00:00:00Z",
      "effective_to": null,
      "applicable_conditions": {
        "markets": ["TW"],
        "reason_codes": ["ITEM_DAMAGED"],
        "categories": []
      },
      "required_claim_ids": [
        "DELIVERY_CONFIRMED",
        "ORDER_WITHIN_RETURN_WINDOW",
        "ITEM_PHYSICALLY_DAMAGED",
        "DAMAGE_PRESENT_ON_ARRIVAL"
      ],
      "allowed_actions": ["FULL_REFUND", "DECLINE"],
      "return_policy": "MODEL_JUDGMENT",
      "text": "商品到貨即受損者，得於到貨後七日內申請退款……"
    }
  ]
}
```

約束：

- `retrieval_status` 為 `OK | AMBIGUOUS | NOT_FOUND`。**由外部判定，不由模型判定** —— 讓模型判斷「條款是否互斥」等於用模型的判斷來決定是否信任模型的判斷。`AMBIGUOUS` 與 `NOT_FOUND` 一律 fail closed。
- `applicable_conditions.categories` 使用 `OrderSnapshot.line_items[].category_ref` 的同一 opaque identifier；空陣列代表不限制分類。
- `required_claim_ids` 必須全部存在於 [Claim Registry](07-claim-registry.md)。
- `return_policy` 為 `REQUIRED | NOT_REQUIRED | MODEL_JUDGMENT`。`REQUIRED`/`NOT_REQUIRED` 由 graph 決定是否退回商品，Resolver 仍須提供相容 reason；`MODEL_JUDGMENT` 才授權 Resolver 同時決定 required boolean 與 reason。
- 條款不得攜帶退款金額規則。本版只有 `DECLINE` 與 `FULL_REFUND`，金額完全由 `OrderSnapshot` 推導。
- `text` 供 Reviewer 稽核引用是否忠實，不供模型抽取新規則。

## EvidenceItem

```json
{
  "evidence_id": "EV-001",
  "type": "IMAGE",
  "source": "USER",
  "subject": "LI-002",
  "artifact_ref": "artifact://evidence/EV-001",
  "extracted_summary": "商品右下角可見裂痕，外箱未入鏡。",
  "collected_at": "2026-09-01T10:30:00Z"
}
```

約束：

- `type` 為 `IMAGE | VIDEO | TEXT | DOCUMENT`；`source` 為 `USER | ORDER_TOOL | LOGISTICS_TOOL | SYSTEM`。
- `artifact_ref` 必填。handoff 不嵌入 image/video bytes。
- `subject` 為 `line_item_id` 或字面值 `ORDER`，標示這份證據**針對哪個對象**。多商品訂單缺少 `subject` 時無法判定 refund scope 是否過度涵蓋。
- `extracted_summary` 是**中性觀察描述**，只陳述可見內容，不得包含 claim 判定或結論。
- **本契約不含 `claims_supported`。** 證據與 claim 的對應完全由 `assess_case` 產生。讓證據提供者預先標註支持哪些 claim，等於在 assess 之前完成判定，會使 Reviewer 的獨立複核被錨定，並違反「evidence 存在不等於 claim 成立」。

## EvidenceAssessment

LLM-authored。`assess_case` 的輸出。

```json
{
  "evidence_status": "SUFFICIENT_FOR_APPROVAL",
  "claim_registry_version": "claim-registry:1.0",
  "claim_findings": [
    {
      "claim_id": "DELIVERY_CONFIRMED",
      "subject": "ORDER",
      "status": "SUPPORTED",
      "supporting_evidence_refs": ["EV-SYS-001"],
      "explanation": "物流 snapshot 顯示已於 2026-08-25 完成配送。"
    },
    {
      "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL",
      "subject": "LI-002",
      "status": "SUPPORTED",
      "supporting_evidence_refs": ["EV-002"],
      "explanation": "EV-002 同時呈現外箱破損與商品裂痕，可建立到貨時已受損。"
    }
  ]
}
```

`status` 為 `SUPPORTED | UNSUPPORTED | CONTRADICTED`。

`evidence_status` 為 `SUFFICIENT_FOR_APPROVAL | SUFFICIENT_FOR_DECLINE | INSUFFICIENT`，依下列順序判定：

```text
若 ≥1 個 claimed item 的所有 required claims 皆 SUPPORTED
    → SUFFICIENT_FOR_APPROVAL
否則若所有 claimed item 都至少有一個 required claim 為 CONTRADICTED
    → SUFFICIENT_FOR_DECLINE
否則
    → INSUFFICIENT
```

三值的必要性：`CONTRADICTED` 代表證據**反證**主張，再向使用者索取證據沒有意義，必須有通往 `DECLINE` 的出口。而 `UNSUPPORTED` 只代表證據不足，**永遠不得**成為拒絕的依據。

約束：

- `claim_findings` 的 `(claim_id, subject)` pair 集合必須**恰好等於**期望 pair 集合：適用條款 `required_claim_ids` 聯集中每個 `subject_scope = ORDER` 的 claim 一筆 `subject = "ORDER"`，每個 `subject_scope = LINE_ITEM` 的 claim 對 `claimed_line_item_ids` 中每個 `line_item_id` 各一筆；不得多也不得少。
- `subject` 必須符合該 claim 在 registry 中的 `subject_scope`。
- `subject` 為 `ORDER` 且 `SUPPORTED` 的 claim，視為對所有 claimed item 皆滿足該 claim。
- `INSUFFICIENT` 時 `missing_evidence_request` 必填；其餘兩值不得帶此欄位。若所有 unresolved claim 都只能由 `SYSTEM_FACTS` 滿足，LLM 無法產生合法 `EvidenceRequest`，graph 以 `CONTRACT_VIOLATION` fail closed，不向使用者索取無關資料。
- `satisfiable_by` 僅含 `SYSTEM_FACTS` 的 claim，其 `supporting_evidence_refs` 應指向 `source` 為 `SYSTEM`/`ORDER_TOOL`/`LOGISTICS_TOOL` 的項目。

## EvidenceRequest

內容由 LLM 在 `assess_case` 或 `propose_decision` 產生；`request_id` 由 graph 補齊。

```json
{
  "request_id": "EREQ-002",
  "missing_claims": [
    { "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL", "subject": "LI-002" }
  ],
  "accepted_evidence_types": ["IMAGE", "VIDEO"],
  "user_message": "請補充一張同時拍到 LI-002 外箱與商品受損部位的照片，使兩者關聯可辨識。",
  "policy_refs": ["POLICY-12:v3#4.2"]
}
```

約束：

- `missing_claims` 必須**恰好等於**目前所有 `status = UNSUPPORTED` 且 registry 允許 `USER_EVIDENCE` 滿足的 `(claim_id, subject)` pairs；不得重問已 `SUPPORTED`/`CONTRADICTED` 的 claim，也不得漏問可向使用者取得的 unresolved claim。
- `request_id` 是 graph-owned 欄位。即使 structured-output transport 為符合共用 DTO 暫時帶入 placeholder，graph 也必須在保存 state 或送出 interrupt 前以 deterministic ID 覆寫，不得信任模型提供的值。
- `accepted_evidence_types` 必須是 `missing_claims` 各 claim 在 registry 中 `accepted_evidence_types` 的聯集 —— **查表得出，不由模型自行決定**。
- `user_message` 必須忠實反映 registry 的 `observable_requirement`，不得只回覆「請提供更多證據」。
- `satisfiable_by` 僅含 `SYSTEM_FACTS` 的 claim 不得出現在 `missing_claims`。

## ClarificationRequest

Graph-derived。由 `request_clarification` 產生的 interrupt payload。

```json
{
  "request_id": "CREQ-001",
  "missing_fields": ["order_ref"],
  "clarification_question": "請提供您要退貨的訂單編號。",
  "clarification_round": 1
}
```

`missing_fields` 與 `clarification_question` 取自 Intake 輸出；`clarification_round` 由 graph 填寫。澄清問題不得索取尚未由 Policy 判定為必要的 evidence。

## ProposedDecisionDraft

LLM-authored。`propose_decision` 的輸出，**不是**完整 handoff。

```json
{
  "action": "FULL_REFUND",
  "refund_scope": { "line_item_ids": ["LI-002"] },
  "reason_code": "ITEM_DAMAGED",
  "return_decision": {
    "source": "MODEL_JUDGMENT",
    "requirement": {
      "required": false,
      "reason_code": "ITEM_UNSALVAGEABLE"
    }
  },
  "policy_refs": ["POLICY-12:v3#4.2"],
  "evidence_refs": ["EV-002"],
  "rationale_summary": "LI-002 仍在條款 POLICY-12:v3#4.2 適用期間；EV-002 支持到貨時已受損，因此建議全額退款該品項。"
}
```

`action` 僅允許 `DECLINE` 與 `FULL_REFUND`。

`REQUEST_EVIDENCE` 是 Resolver 的另一種 output type，`APPROVE`/`REVISE` 是 Reviewer verdict，`MANUAL_ESCALATION` 是 graph route；它們都不是 resolution action。

約束：

- Draft **不含** `amount`、`currency`、`handoff_id`、`revision_round`。這些由 graph 於組裝 handoff 時填入。
- `action = FULL_REFUND` ⇒ `refund_scope.line_item_ids` 非空且必須帶 `return_decision`；`action = DECLINE` ⇒ scope 必須為空，且不得帶 `return_decision`。
- `line_item_ids` 必須全部存在於 `OrderSnapshot.line_items`。
- `refund_scope.line_item_ids` ⊆ `{ 所有 required claims 皆 SUPPORTED 的 claimed items }`。違反即 over-scoping，屬 deterministic 契約違規，不進入 Reviewer。
- `return_policy = MODEL_JUDGMENT` 時，Resolver 輸出 `return_decision.source = MODEL_JUDGMENT`，並在 `requirement` 內同時提供 required boolean 與相容 reason。
- `return_policy = REQUIRED | NOT_REQUIRED` 時，Resolver 輸出 `return_decision.source = POLICY` 與 reason；Draft 不含 required boolean，由 graph 依 Policy 填入後形成完整 handoff。
- `action` 必須在適用條款的 `allowed_actions` 之內。
- `rationale_summary` 只陳述可稽核結論，不含隱藏 Chain-of-Thought，也不得包含無來源的信心陳述。

## RevisionConflictReport

LLM-authored。`propose_decision` 的第三種輸出，用於 Reviewer 的多個 `required_change` 互相衝突且正式 Policy 無法解決時。

```json
{
  "conflicting_reason_codes": ["SCOPE_UNSUPPORTED", "DECISION_UNSUPPORTED"],
  "conflicting_review_refs": ["REV-001", "REV-002"],
  "explanation": "一項 required_change 要求把 LI-001 移出 refund_scope，另一項要求以同一組證據核准 LI-001；兩者無法同時滿足。"
}
```

Resolver **不得**自行挑選其中一個 reason 遵守。挑選等於用模型的偏好取代 Reviewer 的判斷，且下一輪 Reviewer 會以未被處理的那個 reason 再次 `REVISE`，兩輪內燒完 budget。此輸出直接 fail closed 至 `terminate_automation`（`CONFLICTING_REVISIONS`）。

## ProposedDecisionHandoff

Graph-derived。交給 Verification 與 Reviewer 的完整封包。

```json
{
  "handoff_version": "1.0",
  "handoff_id": "HANDOFF-001",
  "case_ref": "CASE-001",
  "order_snapshot_ref": "ORDER-001@12",
  "policy_bundle_version": "bundle:2026-09-01T10:00:05Z",
  "claim_registry_version": "claim-registry:1.0",
  "proposed_decision": {
    "action": "FULL_REFUND",
    "refund_scope": { "line_item_ids": ["LI-002"] },
    "amount": "1200",
    "currency": "TWD",
    "reason_code": "ITEM_DAMAGED",
    "return_decision": {
      "source": "MODEL_JUDGMENT",
      "requirement": {
        "required": false,
        "reason_code": "ITEM_UNSALVAGEABLE"
      }
    },
    "policy_refs": ["POLICY-12:v3#4.2"],
    "evidence_refs": ["EV-002"]
  },
  "evidence_bundle": [
    {
      "evidence_id": "EV-002",
      "type": "IMAGE",
      "source": "USER",
      "subject": "LI-002",
      "artifact_ref": "artifact://evidence/EV-002",
      "extracted_summary": "外箱側面塌陷，商品裂痕與塌陷位置對應。",
      "collected_at": "2026-09-01T10:40:00Z"
    }
  ],
  "policy_refs": ["POLICY-12:v3#4.2"],
  "rationale_summary": "LI-002 仍在條款 POLICY-12:v3#4.2 適用期間；EV-002 支持到貨時已受損，因此建議全額退款該品項。",
  "revision_round": 0,
  "agent_prompt_version": "resolver:1.0"
}
```

金額推導（graph 執行，模型不參與）：

```text
amount   = Σ OrderSnapshot.line_items[id].refundable_amount  for id in refund_scope.line_item_ids
currency = OrderSnapshot.currency
```

約束：

- `amount` 必須等於上式結果，且 `amount <= OrderSnapshot.refundable_amount_max`。
- `action = DECLINE` ⇒ `amount = "0"`、`line_item_ids` 為空且不帶 `return_decision`。
- `FULL_REFUND.return_decision.requirement.required` 與 `reason_code` 必須相容；required 與 waived 使用不同 enum。`source = POLICY` 時 required boolean 必須與適用 Policy 一致，`source = MODEL_JUDGMENT` 僅能用於對應 Policy。
- `proposed_decision.evidence_refs` 必須全部存在於 `evidence_bundle`。
- `proposed_decision.policy_refs` 必須是 handoff-level `policy_refs` 的子集合。
- 若適用條款有 `required_claim_ids` 需 `USER_EVIDENCE` 支持，`evidence_bundle` 不得為空。
- `handoff_id` 由 graph 產生且不重用；每次重新提案產生新的 `handoff_id`。
- `revision_round` 由 graph 遞增，模型不得填寫或修改。
- Reviewer 接收完整 handoff，不得只接收 decision 摘要。
- Verification 擁有金額與期限的**權威重算權**；Agent 的推導僅為提案。

## VerificationResult

External。

```json
{
  "status": "FAIL",
  "issues": [
    {
      "code": "RETURN_WINDOW_EXCEEDED",
      "message": "提案與目前適用的退貨期限衝突。",
      "field_path": "proposed_decision.action"
    }
  ],
  "verification_version": "verification:1.0"
}
```

`status` 為 `PASS | FAIL | UNAVAILABLE`。`FAIL` 必須帶至少一筆 issue；`PASS`/`UNAVAILABLE` 的 `issues` 必須為空。Agent 不解釋或覆蓋 verifier 規則；`FAIL` 回到 `propose_decision`，`UNAVAILABLE` fail closed。issue code 清單由 Verification owner 定義，見 [External Interfaces](08-external-interfaces.md)。

## ReviewResult

Reviewer 的 claim findings、verdict 與 revision reasons 由 LLM 產生；版本與時間 metadata 由 graph 補齊。

### APPROVE

```json
{
  "verdict": "APPROVE",
  "reviewer_claim_findings": [
    {
      "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL",
      "subject": "LI-002",
      "status": "SUPPORTED",
      "supporting_evidence_refs": ["EV-002"],
      "explanation": "EV-002 呈現外箱塌陷與商品裂痕位置對應。"
    }
  ],
  "revision_reasons": [],
  "reviewer_prompt_version": "reviewer:1.0",
  "reviewed_at": "2026-09-01T10:35:00Z"
}
```

### REVISE

```json
{
  "verdict": "REVISE",
  "reviewer_claim_findings": [
    {
      "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL",
      "subject": "LI-002",
      "status": "UNSUPPORTED",
      "supporting_evidence_refs": ["EV-001"],
      "explanation": "EV-001 僅為商品特寫，未呈現外箱狀態，無法建立到貨時點。"
    }
  ],
  "revision_reasons": [
    {
      "code": "EVIDENCE_INSUFFICIENT",
      "message": "目前影像無法支持 LI-002 於到貨時已損壞。",
      "policy_refs": ["POLICY-12:v3#4.2"],
      "evidence_refs": ["EV-001"],
      "subject": "LI-002",
      "required_change": "補充同時呈現外箱與受損部位的影像。"
    }
  ],
  "reviewer_prompt_version": "reviewer:1.0",
  "reviewed_at": "2026-09-01T10:35:00Z"
}
```

`revision_reasons[].code` 允許：

| Code | 用途 |
| --- | --- |
| `EVIDENCE_INSUFFICIENT` | 證據不支持 decision 所需 claim |
| `POLICY_MISMATCH` | 引用條款不適用或不支持該 action |
| `DECISION_UNSUPPORTED` | Decision 不受引用的 policy/evidence 支持 |
| `DECISION_INCONSISTENT` | action、scope、reason、return 之間互相矛盾 |
| `SCOPE_UNSUPPORTED` | `refund_scope` 涵蓋證據未支持的品項 |
| `RETURN_REQUIREMENT_INCONSISTENT` | `return_decision` 與條款矛盾，或其 reason 不受事實支持 |
| `HANDOFF_INCOMPLETE` | 必填欄位或 reference 不完整 |
| `OTHER` | 以上皆不適用；須在 `message` 完整說明 |

不變條件：

- `verdict` 只能是 `APPROVE` 或 `REVISE`。
- `REVISE` 時 `revision_reasons` 至少一筆；`APPROVE` 時必須是空陣列。
- `reviewer_claim_findings` 兩種 verdict 都必填。Reviewer **自行重做** claim 判定，不接收 `EvidenceAssessment`；此欄位使 Resolver 與 Reviewer 的判定差異可量測，也使 `REVISE` 可診斷。
- `reviewer_claim_findings` 的 `(claim_id, subject)` pair 集合約束與 `EvidenceAssessment` 相同。
- `APPROVE + FULL_REFUND` 的 scope 必須全部受 Reviewer 自己的 findings 支持；`APPROVE + DECLINE` 必須達 `SUFFICIENT_FOR_DECLINE`。不一致視為 contract violation，不得輸出 resolution。
- `message` 描述實際問題，`required_change` 描述可驗收的修正結果，兩者不得空白。
- Reviewer 不輸出 `NEED_EVIDENCE`。證據不足以 `REVISE + EVIDENCE_INSUFFICIENT` 表達。
- `reviewer_prompt_version` 與 `reviewed_at` 是 graph-owned metadata；graph 必須在 validation 與寫入 `review_history` 前覆寫模型值。
- Reviewer 不輸出新的 decision、`EvidenceRequest` 或人工分流判斷。
- 條款為 `MODEL_JUDGMENT` 時，Reviewer **不得**僅因偏好差異就對 `return_decision.requirement.required` 提出 `REVISE`。詳見 [Reasoning and Decision](03-reasoning-and-decision.md)。

## DecisionRevisionEvent

Graph-derived。每次 Reviewer `REVISE` 必須先記錄事件，再返回 Resolver。

```json
{
  "event_id": "REV-001",
  "case_ref": "CASE-001",
  "handoff_before_ref": "HANDOFF-001",
  "review_result": {},
  "revision_round": 1,
  "created_at": "2026-09-01T10:35:00Z"
}
```

事件是 append-only。`handoff_before_ref` 引用 `ProposedDecisionHandoff.handoff_id`。後續提案與 final resolution 以 reference 關聯，不回寫或覆蓋原始 Reviewer 意見。

## Reviewer routing

模型的 ReviewResult 仍只有 APPROVE / REVISE；不輸出風險分數、retry limit 或第三種 verdict。
Graph 在 REVISE 且 revision_round >= 3 時產生 routing_reason = REVISION_BUDGET_EXCEEDED，
將最後提案及 RevisedReviewResult 交給 Human Review。模型不得自行計算或覆寫此結果。

## HumanReviewDossier

`claim_registry_version` 必填；每輪 proposal 必須使用 dossier 相同的 case、Policy、order snapshot 與 registry。審核輪次從 0 連續遞增，revision event 必須綁定該輪 REVISE、指向下一輪 round，不能跳號、倒序或混用版本。

Agent 組裝、API 持久化的人工裁決依據。包含 intake 綁定後的 `claimed_line_item_ids`、`order_snapshot`、`policy_bundle`、`proposal_history`、`review_history`、`revision_events`。審核歷程只收錄真正經 Reviewer 審核的提案；verification 重試產生的未審提案不冒充審核輪次。按 revision event 的 handoff reference 對齊，保留最後一次 REVISE。

它不包含 hidden reasoning，也不新增 LLM 呼叫。最後提案／review 必須與提交的 handoff／review 相同，dossier 納入冪等 payload hash。舊紀錄允許 dossier 為 null 以保留稽核資料，但不可据此開放重新裁決。

## Reviewer 金額授權

LLM 維持 `APPROVE | REVISE`。`ReviewGateResult` 與模型 review 分開保存，包含 `config_version`、`config_hash`、`status`、`amount`、`currency`、`threshold`、`reason`。只有 APPROVE 才計算；DECLINE 為 NOT_APPLICABLE，REVISE 不產生 gate。

共享 `ReviewerGateConfig` 預設版本 `reviewer-gates:1.0`，TWD > 5000、SGD > 200 回 HUMAN_REQUIRED / HIGH_VALUE_ITEM；等於門檻 PASS。未設定幣別回 CURRENCY_THRESHOLD_UNCONFIGURED，不換匯。金額使用 Decimal。Compose 將同一份 [`config/reviewer-gates.json`](../../config/reviewer-gates.json) 唯讀掛載至 API 與 Agent Service 的 `/run/config/reviewer-gates.json`，兩邊的 `RETURN_AGENT_REVIEW_GATE_CONFIG` 只負責定位該檔案。JSON 必須明確包含 version、thresholds；無效或遺失會啟動失敗。變更門檻時必須同時更新版本並協調兩服務切換，不能在環境變數重複定義 business threshold。

dossier 的 routing_reason 與 review_gate 納入 hash。金額入口允許首輪 APPROVE、空 revision_events；budget 入口仍須 exhausted REVISE 且無 gate。API 提交與裁決時重新計算驗證，執行退款時再次核對持久化資料；缺失、偽造或設定版本/hash 不一致不得自動執行。金額 gate 是人工授權要求，不是退款資格判斷。

## HumanReviewResult

External。**必須結構化** —— [Operational Memory](04-operational-memory.md) 的蒸餾要求對修正前後做結構比較，自由文字無法比較。

```json
{
  "decision": "EDIT",
  "review_note": "外箱照片仍不足以建立到貨時已受損。",
  "generalizable": true,
  "corrected_decision": {
    "action": "DECLINE",
    "refund_scope": { "line_item_ids": [] }
  },
  "correction_reason_code": "CLAIM_NOT_ESTABLISHED",
  "final_resolution_ref": "RESOLUTION-001",
  "reviewed_at": "2026-09-01T11:00:00Z"
}
```

- `decision` 為 `APPROVE | EDIT | REJECT`。
- 三種 decision 都必須帶非空 `review_note`，完整保留人工稽核說明。
- 一份整體裁決理由即可，不要求逐項處置異議。`reviewer_id` 隨結果保存；目前 demo 身份不是正式身分驗證／權限系統。
- Human 可依現有證據推翻原提案（含 DECLINE → FULL_REFUND），但退款 scope 必須是原申請品項的子集合，而非最後提案 scope 的子集合。不可修改可信訂單事實、Policy、任意 amount/currency。
- 人工證據判斷由人工結果及 note 負責，不改寫 Reviewer 的 REVISE，也不再次送 Reviewer。資料不足不得自動當成不退款；本版不支援人工補件。
- `generalizable` 可為 `true | false | null`，只作為 Memory Distiller 的提示；不得直接建立、核准或發布 memory。
- `EDIT` 時 `corrected_decision` 與 `correction_reason_code` 必填；`APPROVE`/`REJECT` 不得帶 correction 欄位。
- `corrected_decision` 只能調整 `action`、`refund_scope` 與退貨決定；`amount` 依同一公式重算，不得手動指定。若修正後為 `FULL_REFUND`，必須帶 `return_decision.source = HUMAN_REVIEW` 與 boolean 相容的新 reason；若為 `DECLINE` 則不得帶 `return_decision`。
- `correction_reason_code` 為 `CLAIM_NOT_ESTABLISHED | POLICY_MISAPPLIED | SCOPE_INCORRECT | RETURN_REQUIREMENT_INCORRECT | OTHER`。
- Agent 僅消費此結果以建立 correction trace；不負責 UI 或執行。

## ResolutionHandoff

Graph-derived。`emit_resolution_handoff` 的輸出。**不代表退款已執行。**

```json
{
  "case_ref": "CASE-001",
  "handoff_id": "HANDOFF-002",
  "outcome_source": "REVIEWER_APPROVE",
  "final_decision": {
    "action": "FULL_REFUND",
    "refund_scope": {
      "line_item_ids": [
        "LI-002"
      ]
    },
    "amount": "1200",
    "currency": "TWD",
    "return_decision": {
      "source": "MODEL_JUDGMENT",
      "requirement": {
        "required": false,
        "reason_code": "ITEM_UNSALVAGEABLE"
      }
    },
    "reason_code": "ITEM_DAMAGED"
  },
  "execution_blocked": false,
  "emitted_at": "2026-09-01T10:45:00Z",
  "review_result": {
    "verdict": "APPROVE",
    "reviewer_claim_findings": [
      {
        "claim_id": "ITEM_PHYSICALLY_DAMAGED",
        "subject": "LI-002",
        "status": "SUPPORTED",
        "supporting_evidence_refs": [
          "EV-002"
        ],
        "explanation": "照片呈現商品裂痕。"
      }
    ],
    "revision_reasons": [],
    "reviewer_prompt_version": "reviewer:2.1",
    "reviewed_at": "2026-09-01T10:45:00Z"
  }
}
```

`outcome_source` 為 `REVIEWER_APPROVE | HUMAN_APPROVE | HUMAN_EDIT | HUMAN_REJECT`。所有結果均帶 `review_result`：REVIEWER_APPROVE 帶 ApprovedReviewResult，人工結果帶用盡修正 budget 的 RevisedReviewResult。`execution_blocked` 保留為 false 的明確執行契約；舊 RISK_BLOCK 分支已移除。規則：

- `HUMAN_REJECT` → `final_decision.action` 必須是 `DECLINE`；`execution_blocked = false`。
- 其餘 `outcome_source` → `execution_blocked = false`。
- `REVIEWER_APPROVE` 與 `HUMAN_APPROVE` 的 `FULL_REFUND.return_decision.source` 只能是 `POLICY | MODEL_JUDGMENT`；只有 `HUMAN_EDIT` 的 `FULL_REFUND` 使用 `HUMAN_REVIEW`。

Agent 不得宣稱退款已執行；`final_resolution` 由外部執行系統確認。

## MemoryDistillationInput

Graph-derived。只在案件已有 final `ResolutionHandoff` 且存在 Reviewer revision 或 Human `EDIT/REJECT` 時組裝，作為非同步 Memory Worker 的封閉輸入：

```text
case_context
policy_bundle
evidence_assessment
proposal_history[]
revision_events[]
human_review_result?
final_resolution
claimed_categories[]
```

所有 case references 必須一致；`final_resolution.handoff_id` 必須等於最後一筆 proposal，`claimed_categories` 只能由 claimed line items deterministic 推導且不得重複。此 DTO 不包含 UserTurn 原文、使用者 reference 或 artifact bytes。Memory job/event transport 見 [External Interfaces](08-external-interfaces.md#api-與-agent-service-邊界)。

## ManualEscalationHandoff

Graph-derived。`terminate_automation` 的輸出，是所有 fail-closed 路徑的匯集點。

```json
{
  "case_ref": "CASE-001",
  "thread_id": "THREAD-001",
  "escalation_reason": "VERIFICATION_UNAVAILABLE",
  "last_known_handoff_ref": "HANDOFF-001",
  "accumulated_context": {
    "clarification_round": 0,
    "evidence_round": 1,
    "verification_round": 1,
    "revision_round": 0,
    "review_history_refs": [],
    "verification_issues": []
  },
  "created_at": "2026-09-01T10:50:00Z"
}
```

`escalation_reason` 允許：

```text
CLARIFICATION_BUDGET_EXCEEDED
EVIDENCE_BUDGET_EXCEEDED
VERIFICATION_BUDGET_EXCEEDED
REVISION_BUDGET_EXCEEDED
PROPOSE_BUDGET_EXCEEDED
VERIFICATION_UNAVAILABLE
POLICY_AMBIGUOUS
POLICY_NOT_FOUND
CONFLICTING_REVISIONS
CONTRACT_VIOLATION
```

各 reason 對應的觸發條件與 loop budget 見 [Agent Graph](01-agent-graph.md)。

`last_known_handoff_ref` 在尚未產生任何 handoff 時為 `null`。

## Enum 總表

| Enum | 值 |
| --- | --- |
| `action` | `DECLINE`、`FULL_REFUND` |
| `reason_code` | `ITEM_DAMAGED`、`ITEM_NOT_AS_DESCRIBED`、`MISSING_ITEM`、`WRONG_ITEM`、`QUALITY_ISSUE`、`CHANGED_MIND` |
| `requested_action`（Intake，使用者要求） | `REFUND`、`RETURN_AND_REFUND`、`EXCHANGE`、`UNSPECIFIED` |
| `return_decision.source` | `POLICY`、`MODEL_JUDGMENT`、`HUMAN_REVIEW` |
| waived return reason（`required = false`） | `ITEM_UNSALVAGEABLE`、`HYGIENE_RISK`、`RETURN_UNECONOMICAL`、`EVIDENCE_SUFFICIENT_WITHOUT_RETURN` |
| required return reason（`required = true`） | `RESALE_VALUE_RETAINED`、`RETURN_REQUIRED_FOR_INSPECTION` |
| `return_policy` | `REQUIRED`、`NOT_REQUIRED`、`MODEL_JUDGMENT` |
| `evidence_status` | `SUFFICIENT_FOR_APPROVAL`、`SUFFICIENT_FOR_DECLINE`、`INSUFFICIENT` |
| `claim status` | `SUPPORTED`、`UNSUPPORTED`、`CONTRADICTED` |
| `evidence type` | `IMAGE`、`VIDEO`、`TEXT`、`DOCUMENT` |
| `evidence source` | `USER`、`ORDER_TOOL`、`LOGISTICS_TOOL`、`SYSTEM` |
| `subject` | `ORDER` 或 `OrderSnapshot` 中存在的 `line_item_id` |
| `verdict` | `APPROVE`、`REVISE` |
| `retrieval_status` | `OK`、`AMBIGUOUS`、`NOT_FOUND` |
| `verification status` | `PASS`、`FAIL`、`UNAVAILABLE` |
| `human decision` | `APPROVE`、`EDIT`、`REJECT` |
| `outcome_source` | `REVIEWER_APPROVE`、`HUMAN_APPROVE`、`HUMAN_EDIT`、`HUMAN_REJECT` |

`requested_action` 是使用者的要求，與 Resolver 的 `action` 是**不同 enum**，不得互相代入。`return_decision.requirement.reason_code` 的 enum 由 `required` boolean 決定。


## Memory retrieval contracts

MemoryCandidate、ApprovedMemory 必填 retrieval_summary（1–2000 字元）。MemoryCandidate 仍固定 CANDIDATE，ApprovedMemory 仍固定 APPROVED；來源／rationale 留在治理記錄。
MemoryQuerySummary 為 query_summary；OperationalMemoryStore.query_approved 接受此摘要與 deterministic scope/version，top_k=1..3。
MemorySearchHit 包含完整 ApprovedMemory 與本次 cosine similarity（有限值，[-1,1]），不覆寫 confidence。
MemoryRetrievalObservation / MemoryRetrievalPayload 包含 status=OK|UNAVAILABLE、query_summary、hits（最多3且ID不重複）、error_code。
OK 必須有摘要、error_code=null；UNAVAILABLE 必須沒有 hits 且帶 SUMMARY_UNAVAILABLE 或 RETRIEVAL_UNAVAILABLE。
NodeExecutionObservation 只有 prepare_memory_query/retrieve_memory 的 EXIT 可帶 memory_retrieval。
可執行 DTO、generated JSON schemas 與 Web TypeScript 是 wire contract source of truth；語意 uniqueness／privacy 另由 deterministic validator 檢查。

## Activity wire contract

`return_agent_contracts.activity` 是唯一來源：`ActivityEmission` 不含 seq；API 產生
`ActivityEvent` 與 `ActivityPage`。scope 為 CASE／REFUND／MEMORY；payload.type
為 node／model／tool lifecycle、node_summary、narration 或 background discriminated union。
Lifecycle phase 為 STARTED／COMPLETED／PAUSED／FAILED，後三者有 duration_ms；模型含 task name 與 model ID，Provider 是程式呼叫，不是模型自主選工具。
安全輸入只含 argument_count、reason_code、required_claim_ids、top_k；不含原始 query 或 request。
Node summary 包含 enum 結果、finding claim/status/evidence references、提案 action／reason code／Policy 與 evidence references、Reviewer verdict／revision reasons、Verification status、next_node。
未通過業務驗證的 model 輸出不能當 node 的已驗證摘要；model lifecycle 只代表呼叫完成。
自由文字 rationale、finding explanation、原始附件與個資不複製進活動紀錄；以結構化原因及引用替代。
Memory observation 沿用既有型別及命中順序／similarity／confidence，但 query 與經驗文字明確標為 omitted；完整內容仍由原 Memory retrieval 介面提供。Reviewer gate 沿用 ReviewGateResult，不改 verdict。
NarrationJob 只含來源 NodeSummary 的 facts，不含 Memory／gate 全文；1–2句中文、長度上限600、URL／email／credential／電話模式與下游已執行宣稱不合格時為 UNAVAILABLE。
這是有限 allowlist／輸出檢查，不宣稱能對任意模型文字作完整語意或個資辨識；禁止擴充成任意物件／自由文字 passthrough。
Schema 在 agent/v1 與 ui/v1，Web generated types 在 `src/contracts/activity-{event,page}.ts`；API 使用方法見 [外部介面](08-external-interfaces.md#獨立-activity-api-v1內部-demo審核人員)。

## 圖片附件與對話 DTO

共享 `attachments.py` 定義 `AttachmentView`（ID、artifact/evidence refs、subject、MIME、尺寸、位元組數及 SHA-256）、`UploadOptions`（限制與可信品項）、`ConversationTurn`／`ConversationPage`（seq、時間、文字與附件）。UI schemas 及 TypeScript 由同一份 DTO 生成。建立案件／補件仍以 `attached_artifact_refs` 傳遞引用。

`OrderUploadProvider.load_order_snapshot` 在案件建立前提供可信品項；`EvidenceImageProvider.load_image(case_ref, artifact_ref)` 回傳短暫 `ImageContent`，不是可持久化 graph DTO。上傳 metadata 不宣稱圖片中的商品狀態，且 handoff 保持原 metadata，Verification 可逐欄核對。

## 申請理解展示

可選 `NodeSummary.intent_display` 使用共享 `IntentDisplay`，包含 reason_code、requested_action、claimed_line_item_ids、completeness 與允許的 missing_fields 分類。旧紀錄可省略；不包含自由文字、原始 prompt、附件 URL。
