# Claim Registry

Version: `claim-registry:1.0`

Policy v2 新包另使用 `claim-registry:2.0`（`registry_for_version`）；v1 保留原語意。v2 新增 `ITEM_CONFIRMED_UNDELIVERED`，subject 為 LINE_ITEM、僅能由 SYSTEM_FACTS 支持，引用可信調查 reference，不得出現在 EvidenceRequest。`ITEM_NOT_IN_SHIPMENT` 仍描述包裹缺件，不能代替確認整件未交付。P01 的 required claims 為空，但所有固定 system predicates 仍須通過；P02 分開判定實體損壞與到貨時點。

Claim 是本系統唯一的「待證事實」單位。Policy 條款不描述證據，只引用 claim id；`assess_case` 只判定 claim；`EvidenceRequest` 由 claim 定義查表產生。本檔是 claim 的受控詞彙（controlled vocabulary），不是 Policy。

引入 registry 的目的：

- Claim 命名穩定，`claim_id` 可作為 schema enum 約束，[RD-01](06-agent-acceptance-criteria.md) 因此可測。
- `EvidenceRequest` 的可接受型別與可觀察要求改為**查表**而非模型生成，滿足 [Agent Contracts](02-agent-contracts.md) 對「不可只回覆請提供更多證據」的要求。
- Resolver 與 Reviewer 面對**同一組** claim，兩者差異只可能來自證據判定，使 Reviewer 的獨立複核可比較、可量測。

## ClaimDefinition

```json
{
  "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL",
  "description": "商品在送達時已處於受損狀態，而非送達後才造成。",
  "subject_scope": "LINE_ITEM",
  "satisfiable_by": ["USER_EVIDENCE"],
  "accepted_evidence_types": ["IMAGE", "VIDEO"],
  "observable_requirement": "影像須同時包含外包裝與商品受損部位，使兩者關聯可辨識。",
  "distinguish_from": ["ITEM_PHYSICALLY_DAMAGED"]
}
```

| 欄位 | 說明 |
| --- | --- |
| `claim_id` | 全域唯一 enum 值。所有引用 claim 的欄位都必須是本檔列出的值。 |
| `description` | 該 claim 成立的語意條件。 |
| `subject_scope` | `ORDER` 或 `LINE_ITEM`，決定 claim finding 的 `subject` 合法形式。 |
| `satisfiable_by` | `SYSTEM_FACTS` 與/或 `USER_EVIDENCE`。 |
| `accepted_evidence_types` | `satisfiable_by` 含 `USER_EVIDENCE` 時必填。 |
| `observable_requirement` | 使用者需提供什麼**可觀察內容**。`EvidenceRequest` 直接引用。 |
| `distinguish_from` | 易被混為一談的鄰近 claim，須雙向登記。 |

`subject_scope` 與 `satisfiable_by` 是兩條護欄：

- `subject_scope` 讓 [refund scope 的 subset 不變條件](02-agent-contracts.md#proposeddecisionhandoff)可機械檢查。`ORDER` claim 的 `subject` 必須是字面值 `ORDER`；`LINE_ITEM` claim 的 `subject` 必須是 `OrderSnapshot` 中存在的 `line_item_id`。
- `satisfiable_by` 僅含 `SYSTEM_FACTS` 的 claim **不得**出現在 `EvidenceRequest` 中。否則 Agent 會要求使用者證明退貨期限這類本應由 order facts 決定的事實。

## Registry

### `subject_scope = ORDER`

| `claim_id` | `satisfiable_by` | `accepted_evidence_types` | `observable_requirement` | `distinguish_from` |
| --- | --- | --- | --- | --- |
| `DELIVERY_CONFIRMED` | `SYSTEM_FACTS` | — | 由物流 snapshot 判定，不得向使用者索取。 | — |
| `ORDER_WITHIN_RETURN_WINDOW` | `SYSTEM_FACTS` | — | 由 `delivered_at` 與適用條款判定，不得向使用者索取。 | — |
| `SHIPMENT_SEAL_INTACT` | `USER_EVIDENCE` | `IMAGE`, `VIDEO` | 外箱封條或封膠的完整狀態須可辨識。 | — |

### `subject_scope = LINE_ITEM`

| `claim_id` | `satisfiable_by` | `accepted_evidence_types` | `observable_requirement` | `distinguish_from` |
| --- | --- | --- | --- | --- |
| `ITEM_PHYSICALLY_DAMAGED` | `USER_EVIDENCE` | `IMAGE`, `VIDEO` | 商品本體的損傷部位須清晰可見。 | `DAMAGE_PRESENT_ON_ARRIVAL`, `ITEM_FUNCTIONALLY_IMPAIRED` |
| `DAMAGE_PRESENT_ON_ARRIVAL` | `USER_EVIDENCE` | `IMAGE`, `VIDEO` | 影像須同時包含外包裝與商品受損部位，使兩者關聯可辨識。 | `ITEM_PHYSICALLY_DAMAGED` |
| `ITEM_FUNCTIONALLY_IMPAIRED` | `USER_EVIDENCE` | `IMAGE`, `VIDEO`, `TEXT` | 須呈現商品無法達成其預期功能的操作過程或結果。 | `ITEM_PHYSICALLY_DAMAGED` |
| `ITEM_DIFFERS_FROM_LISTING` | `USER_EVIDENCE` | `IMAGE`, `VIDEO` | 收到商品的可辨識特徵須能與商品頁描述逐項對照。 | `WRONG_ITEM_RECEIVED` |
| `WRONG_ITEM_RECEIVED` | `USER_EVIDENCE` | `IMAGE` | 收到商品的品名或料號須可辨識，且與訂購品項不同。 | `ITEM_DIFFERS_FROM_LISTING`, `ITEM_NOT_IN_SHIPMENT` |
| `ITEM_NOT_IN_SHIPMENT` | `USER_EVIDENCE`, `SYSTEM_FACTS` | `IMAGE`, `VIDEO` | 已拆封包裝的完整內容物須入鏡，顯示該品項不存在。 | `WRONG_ITEM_RECEIVED` |
| `ITEM_UNUSED` | `USER_EVIDENCE` | `IMAGE` | 商品、配件與標籤須呈現未使用狀態。 | — |

`ITEM_PHYSICALLY_DAMAGED` 與 `DAMAGE_PRESENT_ON_ARRIVAL` 的區分是本 registry 的首要目的。前者只陳述**當下狀態**，後者額外要求**時點歸屬**。商品特寫可支持前者但不足以支持後者 —— 兩者不得混為同一 claim，這是 [RD-01](06-agent-acceptance-criteria.md) 的結構性防線。

## 版本與相容性

- `claim_registry_version` 隨每次變更遞增，格式 `claim-registry:<version>`。
- 新增 claim 或放寬 `accepted_evidence_types` 升 minor version。
- 刪除 claim、改變 `claim_id`、改變 `subject_scope` 或收緊 `observable_requirement` 升 major version。
- `claim_registry_version` 必須寫入 graph working state 與 `ProposedDecisionHandoff`，使每次判定可回溯到當時的詞彙定義。
- Registry 升 major version 時，引用受影響 claim 的 Operational Memory 必須重新驗證或標為 `RETIRED`（見 [Operational Memory](04-operational-memory.md)）。

## 不變條件

- 任何欄位中出現的 `claim_id` 都必須存在於本檔，否則 schema validation 失敗。
- Policy 條款只能引用 `claim_id`，不得自行定義新 claim 或改寫 `observable_requirement`。
- 模型不得發明 claim。`assess_case` 的 `claim_findings` 只能來自適用條款的 `required_claim_ids` 聯集。
- `distinguish_from` 必須雙向登記；單向登記視為 registry 損壞。
- `satisfiable_by` 僅含 `SYSTEM_FACTS` 的 claim 不得進入 `EvidenceRequest`。
- Registry 是 Agent 團隊擁有的詞彙表；Policy 條款如何引用它由 Policy owner 決定，見 [External Interfaces](08-external-interfaces.md)。
