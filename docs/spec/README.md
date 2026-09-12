# Adaptive Return Resolution Agent 規格

本目錄是退貨 Agent 團隊的唯一規格來源，定義 Agent workflow、reasoning、decision、Operational Memory 與 prompts。可執行的 LangGraph library 位於 [`packages/agent_runtime`](../../packages/agent_runtime/README.md)；外部元件只在此描述 Agent 所依賴的最小介面，不規範其內部實作。

需要從空專案重建 API／DB／Agent Service／Web／部署及 A/B/C，請用 [完整重建規格包](../reconstruction/README.md)。該包是 commit `485048c` 的固定版本快照，附離線資產與驗證；本目錄繼續維護 Agent 細部設計，不把歷史快照當最新 runtime 規格。

## 目標

將使用者的退貨請求與外部案件資料整理成可追溯的 `ProposedDecisionHandoff`，交由外部 Verification、獨立 Reviewer 與 Human Review 處理。人審入口包含 revision budget 用盡，以及 Reviewer APPROVE 後 Python 金額 gate 要求人工授權；可修正三次（review round 0～3），不是總共只審三次。Agent 在資訊不足時提出具體問題，並能依 Reviewer 的結構化意見重建提案。

## Agent 團隊負責範圍

- LangGraph 節點、conditional routing、interrupt/resume 與 loop budget。
- 退貨意圖解析、證據充分性判斷與提案 reasoning。
- [Claim Registry](07-claim-registry.md)：待證事實的受控詞彙。
- `proposed_decision` 與 Reviewer 的結構化輸入輸出。
- Reviewer 對 policy、evidence 與 decision 一致性的獨立複核。
- Reviewer/Human correction 的事件紀錄與 Operational Memory 蒸餾。
- Agent prompts、prompt version 與 Agent 層驗收準則。
- 對外部依賴的[介面需求（含 in-process test fakes，見 08）](08-external-interfaces.md)。

## 不負責範圍

- 前後端、canonical case lifecycle/status 與資料持久化。
- Human Review UI、通知、queue 與操作權限。
- Order/Logistics Tools、Mock API 與退款執行。
- Policy 文件處理、embedding、VDB、retrieval/reranking 實作。
- 不實作獨立風控節點；Reviewer 核准後，由同節點 Python 金額 gate 決定是否需要人工授權，詳見 [contracts](02-agent-contracts.md#reviewer-金額授權)。
- Handoff Verification 的規則與執行環境。
- 折扣分攤、稅務計算與運費／手續費的退款規則。
- 跨系統整合、部署與 E2E Demo。

Agent 團隊仍負責定義外部結果如何影響 graph routing。例如 Verification 回傳失敗時，graph 必須把結構化問題送回 `propose_decision`；這不代表 Agent 團隊擁有 Verification 規則。

**Ownership 與 interface 是兩件事。** 退貨期限幾天由 Policy owner 決定，但條款必須以什麼欄位交付給 Agent 由 Agent 團隊決定。[External Interfaces](08-external-interfaces.md) 只涵蓋後者。

## 核心名詞

| 名詞 | 定義 |
| --- | --- |
| `claim` | 唯一的「待證事實」單位。Policy 條款只引用 `claim_id`，不描述證據。 |
| `PolicyBundle` | `retrieve_policy` 回傳的結構化條款集合，含 `required_claim_ids` 與 `retrieval_status`。 |
| `EvidenceAssessment` | `assess_case` 的輸出：逐 claim 的判定與三值 `evidence_status`。 |
| `ProposedDecisionDraft` | Resolver 的 LLM 輸出，尚不含金額與 id。 |
| `ProposedDecisionHandoff` | Graph 在 draft 上補齊 `amount`、`currency`、`handoff_id`、`revision_round` 後的完整提案封包。 |
| `refund_scope` | 提案涵蓋的 `line_item_ids`。退款範圍以品項表達，不以金額表達。 |
| `return_decision` | `FULL_REFUND` 的退貨處理：含決定來源、required boolean 與相容 reason；`DECLINE` 不帶此物件。 |
| `ReviewResult` | Reviewer 輸出的 `APPROVE` 或 `REVISE`，含 Reviewer 自己的 claim findings。 |
| `final_resolution` | 經外部 Verification、Reviewer/Human Review 與執行系統確認的結果。 |
| `Operational Memory` | 從已結案 correction 蒸餾並經核准的操作經驗，不是正式 Policy。 |
| graph working state | Agent 執行期間所需的 snapshot、reference 與 history，不是 backend 的 canonical case status。 |

## 文件索引

1. [Agent Graph](01-agent-graph.md)：節點、routing、interrupt 與 loop budget。
2. [Agent Contracts](02-agent-contracts.md)：資料形狀的語意與範例；所有可執行 DTO 與 schema 集中在 [`apps/contracts`](../../apps/contracts/README.md)。
3. [Reasoning and Decision](03-reasoning-and-decision.md)：判定順序、輸出限制與 revision 行為。
4. [Operational Memory](04-operational-memory.md)：correction event 與 memory lifecycle。
5. [Prompts](05-prompts/README.md)：各 LLM role 的 prompt 與 structured output。
6. [Agent Acceptance Criteria](06-agent-acceptance-criteria.md)：Agent 層 behavioral contract 與 fixture 目錄。
7. [Claim Registry](07-claim-registry.md)：claim 的受控詞彙與版本規則。
8. [External Interfaces](08-external-interfaces.md)：遞交給其他團隊的 Provider 介面需求與 Demo/UI adapter boundary。

## 全域不變條件

### 職責邊界

- Reviewer verdict 只有 `APPROVE` 與 `REVISE`，不得輸出 `NEED_EVIDENCE`。
- 所有 `REVISE` 都經 `record_revision_event` 回到 `propose_decision`，且 `revision_reasons` 至少一筆。
- Reviewer 不直接向使用者取證，也不直接修改 `proposed_decision`。
- Reviewer 不接收 `EvidenceAssessment` 或 Operational Memory，自行重做 claim 判定。
- Agent 只產生提案或 handoff，不得宣稱退款已執行。

### 資料歸屬

- **`amount` 與 `currency` 永不由模型產生。** 金額由 graph 使用 Python `Decimal` 依 `OrderSnapshot.line_items[].refundable_amount` 加總推導，JSON 以 decimal string 交換；Verification 擁有權威重算權。
- 所有 counter（`revision_round`、`evidence_round`、`clarification_round`、`verification_round`、`propose_round`）一律由 graph 遞增，模型不得填寫。
- `handoff_id` 由 graph 產生且不重用。

### 詞彙與 Policy

- [Claim Registry](07-claim-registry.md) 是 claim 的受控詞彙。模型不得發明 claim，Policy 條款不得自行定義新 claim 或改寫 `observable_requirement`。
- 正式且適用版本的 Policy 優先於所有 Operational Memory。Memory 只影響取證方式與提案品質，不得新增 eligibility。
- 條款是否互斥由 Policy owner 以 `retrieval_status` 判定，不由模型判定。

### 判定原則

- 本版的 resolution action 只有 `DECLINE` 與 `FULL_REFUND`。退款範圍以 `refund_scope.line_item_ids` 表達。
- 可核准的條件是 scope 內品項所有 required claim 皆 `SUPPORTED`；案件級拒絕要求每個 claimed item 都至少有一個 required claim 被 `CONTRADICTED`。**`UNSUPPORTED` 永遠不得作為拒絕依據。**
- 大型 evidence artifact 以 opaque reference 傳遞，不放入 graph state 或 handoff payload。
- 不保存或交換模型的隱藏 Chain-of-Thought，只保存結構化 findings、引用與精簡理由。
- 所有 fail-closed 路徑匯集到 `terminate_automation` 並產生 `ManualEscalationHandoff`，graph 無死路。
