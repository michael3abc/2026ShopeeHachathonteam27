# User Risk Authorization Gate — Implementation Specification

> Target repository: `michael3abc/2026ShopeeHachathonteam27`  
> Baseline: `main` @ `c70351e4a8f711698def4e5fd9cec28fdae215a9`  
> Scope: 在目前 Return Resolution Agent 上加入 deterministic User Risk Authorization Gate。  
> 本文件以 target repository 的現行 module、contract、DB migration、Provider 與 refund execution flow 為實作基準。
> 整合決策（2026-09-12）：本分支只在可信 scenario 選定的 Policy v2 新案啟用此 gate；v1 保留既有語意。API migration `0014_user_risk_authorization` 接 `0013`，Policy v2／Demo session 使用接續的 `0015_policy_v2_fulfillment`。履約等待及 APPLIED 後的 Memory join 見 [Policy v2](spec/09-policy-v2-integration.md)，實測與未完成項目見 [progress](progress.md)。

---

# 1. Goal

目前系統已經把兩種責任分開：

```text
Policy + Evidence
        ↓
Resolver
        ↓
Verification
        ↓
Reviewer
        ↓
Reviewer APPROVE
        ↓
Monetary Review Gate
        ↓
Auto Resolution / Human Review
```

現有 monetary gate 已經回答：

> 即使 Reviewer 認定退款成立，這個金額是否允許自動執行？

本功能新增第二個 authorization signal：

> 即使 Reviewer 認定退款成立，依據此 User 過去的可稽核行為模式，這筆退款是否允許自動執行？

最終：

```text
Eligibility
= Policy + Evidence + Reviewer

Automation Authorization
= Monetary Gate + User Risk Gate
```

User Risk **不是退款 eligibility 判斷**，也不是 fraud classifier。

---

# 2. Current Main Baseline

本節描述 target repository main branch 已存在、且本功能必須沿用的架構。

## 2.1 Existing deterministic monetary gate

現有：

```text
apps/contracts/src/return_agent_contracts/review_gates.py
```

包含：

```python
ReviewerGateConfig
ReviewGateResult
HumanReviewRoutingReason
evaluate_review_gate(...)
load_reviewer_gate_config(...)
```

目前 gate：

```text
DECLINE
→ NOT_APPLICABLE

FULL_REFUND + configured currency + amount <= threshold
→ PASS

FULL_REFUND + amount > threshold
→ HUMAN_REQUIRED / HIGH_VALUE_ITEM

FULL_REFUND + unconfigured currency
→ HUMAN_REQUIRED / CURRENCY_THRESHOLD_UNCONFIGURED
```

這是 User Risk Gate 必須模仿的 deterministic authorization pattern。

---

## 2.2 Reviewer routing point already exists

現有：

```text
packages/agent_runtime/src/return_agent_runtime/graph.py
_reviewer_node(...)
```

Reviewer payload 目前只有：

```text
case_context
order_snapshot
policy_bundle
claim_registry
expected_claim_subject_pairs
proposed_decision_handoff
```

Reviewer **沒有收到 Operational Memory、Resolver EvidenceAssessment 或任何 User Risk data**。

Reviewer `APPROVE` 後：

```text
evaluate_review_gate(...)
    ↓
HUMAN_REQUIRED
    → await_human_review

PASS
    → emit_resolution_handoff
```

因此 User Risk 不新增 planner/node chain；直接擴充這個 Reviewer APPROVE authorization branch。

---

## 2.3 Existing Human Review is full-authority

現有 Human Review contract：

```text
apps/contracts/src/return_agent_contracts/models.py
HumanReviewDossier
HumanReviewResult
```

Human result 仍為：

```text
APPROVE
EDIT
REJECT
```

本功能不新增：

```text
RISK_APPROVE
RISK_REJECT
ALLOW_AUTOMATION
```

Risk-triggered case 直接進入既有 Human Review。

---

## 2.4 Existing Human Review validates routing deterministically

現有：

```text
apps/contracts/src/return_agent_contracts/validation.py
validate_human_review_entry(...)
```

目前區分：

```text
REVISION_BUDGET_EXCEEDED
vs
Reviewer APPROVE + monetary HUMAN_REQUIRED
```

User Risk 必須擴充同一 validator，而不是由 UI 或 API 自行判斷是否可進人工。

---

## 2.5 Existing API Human Review persistence

現有：

```text
apps/api/src/return_agent/capabilities/human_review.py
SqlAlchemyHumanReviewProvider
```

它會：

```text
submit_for_review(...)
→ validate_human_review_entry(...)
→ persist handoff/review/dossier hash

complete_for_case(...)
→ reload persisted dossier
→ revalidate entry
→ validate Human corrected decision
→ persist final Human result
```

新增 User Risk 後，這條 integrity chain 必須保留。

---

## 2.6 Existing refund execution independently revalidates machine authorization

現有：

```text
apps/api/src/return_agent/capabilities/refund.py
SqlAlchemyRefundExecutionProvider
```

對 `REVIEWER_APPROVE` machine refund：

```text
load persisted authorization
→ require Verification PASS
→ require Reviewer APPROVE
→ recompute evaluate_review_gate(...)
→ require resolution.review_gate == recomputed gate
→ require monetary gate PASS
→ execute refund
```

因此 User Risk 的 machine PASS 也必須由 API 獨立重新驗證。

Graph 傳來的 `user_risk_gate` 不能被直接信任。

---

## 2.7 Existing internal Provider boundary

Agent Service 透過 HTTP Providers 呼叫 API：

```text
apps/contracts/src/return_agent_contracts/interfaces.py
apps/contracts/src/return_agent_contracts/transport.py
apps/contracts/src/return_agent_contracts/http_adapters.py
apps/api/src/return_agent/app.py
```

目前 internal routes 使用 Bearer service auth。

User Risk 應加入同一 Provider pattern。

---

## 2.8 Existing service composition

Agent runtime dependencies：

```text
packages/agent_runtime/src/return_agent_runtime/dependencies.py
AgentDependencies
```

Integrated Agent Service composition：

```text
apps/agent_service/src/return_agent_service/composition.py
compose_integrated_service(...)
```

目前在此建立：

```text
HttpCaseContextProvider
HttpPolicyProvider
HttpVerificationProvider
HttpHumanReviewProvider
HttpOperationalMemoryStore
HttpEvidenceProvider
ReviewerGateConfig
```

新增 `HttpUserRiskProvider` 與 `UserRiskConfig` 應在相同 composition root 注入。

---

## 2.9 Existing API integrated provider composition

現有：

```text
apps/api/src/return_agent/capabilities/integration.py
IntegratedProviderBundle
compose_integrated_demo_providers(...)
```

目前統一組裝：

```text
CaseContext
Policy
Evidence
Operational Memory
Human Review
Safety/Verification
Refund Execution
```

Demo User Risk Provider 與 mock seed 應在這裡加入，不建立新 service。

---

## 2.10 Existing case identity already contains user_ref

現有：

```text
apps/api/src/return_agent/db/case.py
CaseRecord
```

已包含：

```text
case_ref
order_ref
user_ref
```

因此：

```text
case_ref → user_ref
```

由 API authoritative DB resolve。

不需要：

- 將 `user_ref` 塞進 Reviewer prompt。
- 讓 Agent model 推斷 user identity。
- 修改 Case API command protocol 只為傳遞 risk identity。

---

## 2.11 Existing shared config deployment pattern

目前：

```text
config/reviewer-gates.json
```

透過：

```text
RETURN_AGENT_REVIEW_GATE_CONFIG=/run/config/reviewer-gates.json
```

唯讀 mount 到：

```text
api
agent-service
```

並有：

```text
tests/test_review_gate_compose.py
```

保證兩端使用同一 config/version/hash。

User Risk Config 必須複製這個 deployment pattern。

---

## 2.12 Current Alembic head

此 baseline 的 migration head：

```text
0013_activity_tracing
```

因此 User Risk migration 預計：

```text
0014_user_risk_authorization
down_revision = "0013_activity_tracing"
```

若實作時 main 已新增 migration，必須重新確認 Alembic single head，不可硬套舊 down_revision。

---

## 2.13 Legacy `risk_evaluations` is NOT the new User Risk system

歷史 migration：

```text
apps/api/alembic/versions/0005_safety_verification_risk.py
```

曾建立：

```text
risk_evaluations
risk_route = AUTO | HUMAN | BLOCK
```

目前 main application code沒有 active 使用此 table。

本功能不得復活這個舊語義，原因：

```text
BLOCK
```

與本功能硬 invariant：

```text
HIGH_RISK → HUMAN_REQUIRED
```

衝突。

新功能使用新的：

```text
user_risk_profiles
user_risk_events
user_risk_snapshots
```

不得共用舊 `risk_evaluations` table。

---

# 3. Non-Goals

v1 明確不做：

- LLM fraud/scam classifier。
- ML fraud probability。
- `SCAMMER` / `FRAUD_USER` tag。
- Risk 直接 `DECLINE`。
- Risk 直接 `BLOCK`。
- User history 注入 Reviewer prompt。
- User history 注入 Resolver / Evidence Assessment prompt。
- Operational Memory 修改 Risk threshold。
- 自動學習 Risk score weights。
- 完整 Shopee production account/order history ingestion。
- 從現有 Case DB 回填所有歷史 user behavior。
- 新增 microservice。
- 新增 Redis lifecycle protocol 只為 claim history。
- recommendation system。
- 重構現有 `ReviewGateResult` 成全新的通用 Gate framework。
- 刪除 legacy `risk_evaluations` table。

---

# 4. Hard Invariants

以下 invariants 必須由 contract validation + tests 保護。

1. `HIGH → HUMAN_REQUIRED`。
2. `UNKNOWN → HUMAN_REQUIRED`。
3. User Risk 永遠不能直接產生 `DECLINE`。
4. User Risk 永遠不能產生 `BLOCK`。
5. `LOW` / `MEDIUM` 才能 machine `PASS`。
6. Reviewer prompt 不得包含 User Risk snapshot、score、tags、account age、refund history。
7. Resolver / Evidence Assessment prompt 不得包含 User Risk data。
8. Risk dimension = `User × ReasonCode`，不是 `User × ClaimId`。
9. Risk score 必須由 versioned deterministic config 計算。
10. Provider unavailable / invalid data 必須 fail closed 到 Human Review。
11. Snapshot history cutoff 固定為 `CaseContext.case_opened_at`。
12. Historical aggregation必須使用 `occurred_at < case_opened_at`。
13. Current case 不得 self-count。
14. 同一 case/reason/as_of retry 必須取得同一 immutable snapshot。
15. `CLAIM_REGISTERED` append 必須 idempotent。
16. `REFUND_SUCCEEDED` 只有實際 refund application 成功後才寫入。
17. `REFUND_SUCCEEDED` append 必須 idempotent。
18. Human Review 維持既有 `APPROVE | EDIT | REJECT` 全權限模型。
19. `routing_reason` 與 Human correction reason 不得混用。
20. Reviewer-approved auto refund 必須由 API 重新驗證 User Risk PASS。
21. API revalidation 必須使用同一 persisted snapshot + same config，不可重新 query 最新 history。
22. Human APPROVE / EDIT 可以覆蓋 machine `HUMAN_REQUIRED`，但必須有有效 persisted Human authorization。
23. Buyer-facing UI 不得暴露 User historical risk facts。
24. Risk score 是 routing policy score，不得表示為 fraud probability。

---

# 5. Final Workflow

```text
parse_request
    ↓
load_case_context
    ↓
retrieve_policy
    ↓
memory / evidence / resolver loop
    ↓
external_verification
    ↓
Reviewer
    │
    ├─ REVISE
    │    → existing revision workflow
    │
    └─ APPROVE
           ↓
      ┌─────────────────────────┐
      │ Automation Authorization│
      │                         │
      │  Monetary Gate          │
      │  User Risk Gate         │
      └─────────────────────────┘
           │
           ├─ both PASS
           │      ↓
           │ emit_resolution_handoff
           │      ↓
           │ refund execution
           │      ↓
           │ actual SUCCEEDED
           │      ↓
           │ REFUND_SUCCEEDED ledger event
           │
           └─ any HUMAN_REQUIRED
                  ↓
             existing Human Review
                  ↓
            APPROVE / EDIT / REJECT
```

Risk data 不會回流 Reviewer。

---

# 6. User Risk Policy v1

新增：

```text
config/user-risk.json
```

建議內容：

```json
{
  "version": "user-risk:1.0",
  "low_max_score": 39,
  "medium_max_score": 59,
  "rules": {
    "repeated_same_reason_claims": {
      "same_reason_claims_90d_gte": 3,
      "points": 40
    },
    "high_refund_rate": {
      "minimum_orders_90d": 5,
      "refund_rate_gte": "0.40",
      "points": 25
    },
    "new_account_repeated_claims": {
      "account_age_days_lte": 30,
      "same_reason_claims_90d_gte": 2,
      "points": 30
    }
  }
}
```

## 6.1 Rules

### REPEATED_SAME_REASON_CLAIMS

```text
same_reason_claims_90d >= 3
→ +40
```

### HIGH_REFUND_RATE

```text
orders_90d >= 5
AND
refunded_orders_90d / orders_90d >= 0.40
→ +25
```

Numerator 只使用實際：

```text
REFUND_SUCCEEDED
```

而不是 refund request count。

### NEW_ACCOUNT_REPEATED_CLAIMS

```text
account_age_days <= 30
AND
same_reason_claims_90d >= 2
→ +30
```

---

## 6.2 Risk Levels

```text
0–39   LOW
40–59  MEDIUM
60+    HIGH
```

Routing：

```text
LOW
→ PASS

MEDIUM
→ PASS

HIGH
→ HUMAN_REQUIRED / HIGH_USER_RISK

UNKNOWN
→ HUMAN_REQUIRED / USER_RISK_UNAVAILABLE
```

---

# 7. Contracts

新增：

```text
apps/contracts/src/return_agent_contracts/user_risk.py
```

不要把 User Risk models 混進 LLM output schemas。

---

## 7.1 RiskTag

```python
class RiskTag(StrEnum):
    REPEATED_SAME_REASON_CLAIMS = "REPEATED_SAME_REASON_CLAIMS"
    HIGH_REFUND_RATE = "HIGH_REFUND_RATE"
    NEW_ACCOUNT_REPEATED_CLAIMS = "NEW_ACCOUNT_REPEATED_CLAIMS"
```

這些是 historical patterns，不是詐騙結論。

---

## 7.2 UserRiskLevel

```python
class UserRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"
```

---

## 7.3 UserRiskConfig

```python
class UserRiskConfig(ContractModel):
    version: OpaqueRef = "user-risk:1.0"
    low_max_score: NonNegativeInt
    medium_max_score: NonNegativeInt
    rules: ...
```

要求：

```text
low_max_score < medium_max_score
points >= 0
thresholds valid
unknown JSON keys rejected
```

提供：

```python
@property
def fingerprint(self) -> str:
    ...
```

hash 必須對 canonical JSON deterministic。

---

## 7.4 UserRiskSnapshot

```python
class UserRiskSnapshot(ContractModel):
    snapshot_ref: OpaqueRef

    case_ref: OpaqueRef
    user_ref: OpaqueRef
    reason_code: ReasonCode

    as_of: UTCDateTime

    account_age_days: NonNegativeInt
    orders_90d: NonNegativeInt
    same_reason_claims_90d: NonNegativeInt
    refunded_orders_90d: NonNegativeInt

    created_at: UTCDateTime
```

Contract：

```text
refunded_orders_90d <= orders_90d
snapshot_ref non-empty
```

`refund_rate_90d` 不 persist：

```text
orders_90d == 0
→ 0

else
→ Decimal(refunded_orders_90d) / Decimal(orders_90d)
```

---

## 7.5 UserRiskGateResult

```python
class UserRiskGateResult(ContractModel):
    config_version: OpaqueRef
    config_hash: str

    status: Literal[
        "PASS",
        "HUMAN_REQUIRED",
        "NOT_APPLICABLE",
    ]

    risk_level: UserRiskLevel
    score: NonNegativeInt

    tags: list[RiskTag]
    matched_rules: list[OpaqueRef]

    reason: Literal[
        "HIGH_USER_RISK",
        "USER_RISK_UNAVAILABLE",
    ] | None

    snapshot_ref: OpaqueRef | None
```

Consistency：

```text
PASS
→ LOW or MEDIUM
→ reason = None
→ snapshot_ref required

HUMAN_REQUIRED + HIGH_USER_RISK
→ HIGH
→ snapshot_ref required

HUMAN_REQUIRED + USER_RISK_UNAVAILABLE
→ UNKNOWN
→ snapshot_ref optional/None

NOT_APPLICABLE
→ reason = None
```

---

## 7.6 Evaluator

Shared deterministic function：

```python
def evaluate_user_risk(
    action: ResolutionAction,
    snapshot: UserRiskSnapshot,
    config: UserRiskConfig,
) -> UserRiskGateResult:
    ...
```

Rules：

```text
DECLINE
→ NOT_APPLICABLE

FULL_REFUND
→ deterministic score
→ risk level
→ PASS / HUMAN_REQUIRED
```

另外：

```python
def unavailable_user_risk_gate(
    config: UserRiskConfig,
) -> UserRiskGateResult:
    ...
```

Provider exception 在 Runtime authorization boundary 轉成：

```text
UNKNOWN
HUMAN_REQUIRED
USER_RISK_UNAVAILABLE
```

不得 fallback PASS。

---

# 8. Existing Contracts to Modify

## 8.1 `review_gates.py`

保持現有 monetary types。

只擴充：

```python
HumanReviewRoutingReason = Literal[
    "REVISION_BUDGET_EXCEEDED",
    "HIGH_VALUE_ITEM",
    "CURRENCY_THRESHOLD_UNCONFIGURED",
    "HIGH_USER_RISK",
    "USER_RISK_UNAVAILABLE",
]
```

不要把 user risk evaluator塞入 `review_gates.py`。

---

## 8.2 `interfaces.py`

新增：

```python
@runtime_checkable
class UserRiskProvider(Protocol):
    def prepare_snapshot(
        self,
        case_ref: OpaqueRef,
        reason_code: ReasonCode,
        as_of: UTCDateTime,
    ) -> UserRiskSnapshot:
        ...
```

Provider 負責：

```text
authoritative DB facts
claim registration
history aggregation
immutable snapshot persistence
```

Provider **不負責**決定 PASS/HUMAN_REQUIRED。

---

## 8.3 `transport.py`

新增 version-compatible typed internal transport DTO：

```text
PrepareUserRiskSnapshotParams
PrepareUserRiskSnapshotRequest
PrepareUserRiskSnapshotResponse
```

遵循目前：

```text
method
params
result
```

Provider transport convention。

---

## 8.4 `http_adapters.py`

新增：

```python
class HttpUserRiskProvider(_HttpProvider, UserRiskProvider):
    ...
```

route：

```text
POST /internal/v1/user-risk/snapshot
```

---

## 8.5 contracts `__init__.py`

export：

```text
HttpUserRiskProvider
UserRiskProvider
UserRiskSnapshot
UserRiskGateResult
UserRiskConfig
```

依目前 package export convention 更新。

---

## 8.6 `HumanReviewDossier`

現有：

```text
apps/contracts/src/return_agent_contracts/models.py
```

新增：

```python
user_risk_snapshot: UserRiskSnapshot | None = None
user_risk_gate: UserRiskGateResult | None = None
```

### Semantics

Revision-budget case：

```text
user_risk_snapshot = None
user_risk_gate = None
```

Risk HIGH：

```text
snapshot required
gate = HIGH / HUMAN_REQUIRED
```

Risk unavailable：

```text
snapshot may be None
gate = UNKNOWN / HUMAN_REQUIRED
```

Monetary HIGH + Risk HIGH：

```text
review_gate = HUMAN_REQUIRED
user_risk_gate = HUMAN_REQUIRED
routing_reason = monetary reason
```

---

## 8.7 Resolution Handoff

現有：

```python
class _ResolutionHandoffBase(ContractModel):
    review_gate: ReviewGateResult | None
    ...
```

平行新增：

```python
user_risk_gate: UserRiskGateResult | None = None
```

不要把完整 `UserRiskSnapshot` 放進一般 resolution handoff。

`UserRiskGateResult.snapshot_ref` 足夠供 API 查 persisted snapshot。

---

# 9. Persistence Design

依 target repo 現行 style，backend capability ORM models 集中在：

```text
apps/api/src/return_agent/db/models.py
```

因此 v1 優先在 `db/models.py` 增加三個 ORM records，而不是再拆新的 SQLAlchemy Base。

Capability/repository logic放：

```text
apps/api/src/return_agent/capabilities/user_risk.py
```

---

## 9.1 Migration

新增：

```text
apps/api/alembic/versions/0014_user_risk_authorization.py
```

baseline：

```python
revision = "0014_user_risk_authorization"
down_revision = "0013_activity_tracing"
```

實作前需執行：

```bash
cd apps/api
uv run --package return-agent-api alembic heads
```

確認仍是 single head。

---

## 9.2 `user_risk_profiles`

Demo baseline facts：

```text
user_ref PK
account_created_at
orders_90d
updated_at
```

`orders_90d` 在 Hackathon v1 是 mock authoritative baseline。

Production 未來可替換成真實 Account/Order Provider，不改 evaluator contract。

---

## 9.3 `user_risk_events`

Append-only ledger：

```text
id
event_ref UNIQUE

user_ref
case_ref
order_ref

event_type
reason_code nullable

occurred_at
created_at
```

Event types：

```text
CLAIM_REGISTERED
REFUND_SUCCEEDED
```

DB constraints：

```text
UNIQUE(case_ref, event_type)
```

以及：

```text
CLAIM_REGISTERED
→ reason_code NOT NULL by application/domain validation

REFUND_SUCCEEDED
→ reason_code optional
```

---

## 9.4 `user_risk_snapshots`

```text
snapshot_ref PK

case_ref
user_ref
reason_code
as_of

account_age_days
orders_90d
same_reason_claims_90d
refunded_orders_90d

created_at
```

retry identity：

```text
UNIQUE(case_ref, reason_code, as_of)
```

Snapshot create 後不得 update facts。

---

## 9.5 Do not reuse `risk_evaluations`

即使 DB 仍存在 legacy：

```text
risk_evaluations
```

新 implementation：

```text
MUST NOT read
MUST NOT write
```

該 table 不屬於 User Risk Authorization v1。

---

# 10. CLAIM_REGISTERED Semantics

採已定案的 **Option B / minimum-demo integration**。

不新增 Redis event。

只有在：

```text
Reviewer APPROVE
+
FULL_REFUND
+
開始 User Risk authorization
```

時，由 `UserRiskProvider.prepare_snapshot(...)` idempotently register current claim。

因此 v1：

```text
same_reason_claims_90d
```

精確表示：

> 過去曾進入 Reviewer-approved FULL_REFUND automation authorization path 的同 ReasonCode registered claims。

不是：

> 所有曾建立、未完成、abandoned、policy-not-found 的 raw return cases。

---

# 11. Snapshot Construction

新增：

```text
apps/api/src/return_agent/capabilities/user_risk.py
SqlAlchemyUserRiskProvider
```

`prepare_snapshot(...)`：

```text
1. load CaseRecord(case_ref)
2. resolve authoritative user_ref / order_ref
3. load current CaseContext
4. require requested as_of == CaseContext.case_opened_at
5. load UserRiskProfile(user_ref)
6. idempotently INSERT current CLAIM_REGISTERED
      occurred_at = as_of
      reason_code = current reason
7. find existing snapshot(case_ref, reason_code, as_of)
8. if exists:
      return existing snapshot
9. aggregate prior history:
      occurred_at >= as_of - 90 days
      occurred_at < as_of
10. compute account_age_days
11. persist immutable snapshot
12. return snapshot
```

---

## 11.1 Self-count prevention

Current claim：

```text
occurred_at = case_opened_at
```

Historical query：

```text
occurred_at < case_opened_at
```

因此 current case 永遠不會增加自己的：

```text
same_reason_claims_90d
```

---

## 11.2 Same-reason aggregation

```text
event_type = CLAIM_REGISTERED
AND reason_code = current ReasonCode
AND within historical window
```

Risk dimension：

```text
User × ReasonCode
```

不是 Claim Registry ClaimId。

---

## 11.3 Refund aggregation

```text
COUNT(DISTINCT order_ref)
WHERE event_type = REFUND_SUCCEEDED
```

避免同一 order 多 line-item mutation 造成：

```text
refund_rate > 100%
```

---

## 11.4 Retry stability

一旦 snapshot 已存在：

```text
prepare_snapshot(...)
```

必須直接 return existing record。

不得因為之後其他 case/refund event 出現而重算舊 snapshot。

---

# 12. Demo Mock Seed

新增：

```text
data/user-risk.json.example
```

由：

```text
apps/api/src/return_agent/capabilities/integration.py
compose_integrated_demo_providers(...)
```

啟動 integrated demo 時 seed。

Seed raw facts，不 seed：

```text
risk_score
risk_level
gate status
```

---

## 12.1 Persona: NORMAL

```text
user_ref = USER-NORMAL

account age = 720 days
orders_90d = 15

prior ITEM_DAMAGED registered claims = 1
prior refunded distinct orders = 1
```

Expected：

```text
score = 0
LOW
PASS
```

---

## 12.2 Persona: WATCH

```text
user_ref = USER-WATCH

account age = 500 days
orders_90d = 12

prior ITEM_DAMAGED registered claims = 3
prior refunded distinct orders = 2
```

Expected：

```text
REPEATED_SAME_REASON_CLAIMS +40

score = 40
MEDIUM
PASS
```

---

## 12.3 Persona: HIGH-RISK

```text
user_ref = USER-HIGH-RISK

account age = 180 days
orders_90d = 8

prior ITEM_DAMAGED registered claims = 3
prior refunded distinct orders = 4
```

Expected：

```text
REPEATED_SAME_REASON_CLAIMS +40
HIGH_REFUND_RATE            +25

score = 65
HIGH
HUMAN_REQUIRED
```

---

## 12.4 Existing fixture integration

目前 demo provider 使用：

```text
data/case-context.json.example
data/evidence.json.example
data/policy.json.example
data/operational-memory.json.example
data/scenarios.json.example
```

User Risk Demo 應：

1. 新增 `data/user-risk.json.example`。
2. 擴充 `data/scenarios.json.example`，加入 controlled persona scenarios。
3. 視需要擴充 `case-context.json.example` 的 multi-order templates。
4. Case API 建案時使用不同 `user_ref`。

不要修改 evidence/policy facts 來製造 risk 差異。

---

# 13. API Provider Integration

## 13.1 IntegratedProviderBundle

修改：

```text
apps/api/src/return_agent/capabilities/integration.py
```

新增：

```python
user_risk_provider: UserRiskProvider
```

在：

```python
compose_integrated_demo_providers(...)
```

建立：

```python
user_risk_provider = SqlAlchemyUserRiskProvider(...)
```

並執行：

```text
_seed_user_risk(...)
```

---

## 13.2 Internal route

修改：

```text
apps/api/src/return_agent/app.py
```

新增：

```text
POST /internal/v1/user-risk/snapshot
```

使用現有：

```text
require_internal_service
```

不得公開成 buyer API。

---

## 13.3 Error mapping

例如：

```text
unknown case
profile missing
as_of mismatch
snapshot integrity failure
```

HTTP adapter 可以收到 4xx/5xx，但 Runtime 不把它轉 machine PASS。

Runtime User Risk authorization boundary一律：

```text
Provider/contract failure
→ UNKNOWN
→ HUMAN_REQUIRED
```

---

# 14. Agent Service Integration

修改：

```text
apps/agent_service/src/return_agent_service/composition.py
```

在 `provider_args` pattern下新增：

```python
user_risk_provider=HttpUserRiskProvider(**provider_args)
```

並載入：

```python
user_risk_config=load_user_risk_config(
    os.environ.get("RETURN_AGENT_USER_RISK_CONFIG")
)
```

---

# 15. Config Deployment

新增：

```text
config/user-risk.json
```

Docker Compose：

```text
api:
  environment:
    RETURN_AGENT_USER_RISK_CONFIG: /run/config/user-risk.json
  volumes:
    - ./config/user-risk.json:/run/config/user-risk.json:ro

agent-service:
  environment:
    RETURN_AGENT_USER_RISK_CONFIG: /run/config/user-risk.json
  volumes:
    - ./config/user-risk.json:/run/config/user-risk.json:ro
```

新增 equivalent compose test：

```text
tests/test_user_risk_config_compose.py
```

要求：

```text
API and Agent Service
→ same host source
→ same config version
→ same config hash
→ same rules
```

不要複製兩份 config。

---

# 16. Runtime Integration

修改：

```text
packages/agent_runtime/src/return_agent_runtime/dependencies.py
```

加入：

```python
user_risk_provider: UserRiskProvider
user_risk_config: UserRiskConfig
```

---

## 16.1 AgentState

修改：

```text
packages/agent_runtime/src/return_agent_runtime/state.py
```

新增：

```python
user_risk_snapshot: UserRiskSnapshot | None
user_risk_gate: UserRiskGateResult | None
```

`initial_state`：

```text
None
None
```

---

## 16.2 Reviewer payload must stay unchanged

不得向 `ModelTask.REVIEW` payload加入：

```text
user_ref
user_risk_snapshot
risk_score
risk_level
risk_tags
account_age
refund history
```

需要新增 regression test 鎖住此 boundary。

---

## 16.3 `_reviewer_node` APPROVE branch

現有 monetary gate 必須保留。

新版 pseudo-code：

```python
if result.verdict is ReviewVerdict.APPROVE:
    decision = handoff.proposed_decision

    amount_gate = evaluate_review_gate(
        decision.action,
        decision.amount,
        decision.currency,
        dependencies.reviewer_gate_config,
    )

    if decision.action is ResolutionAction.FULL_REFUND:
        try:
            risk_snapshot = dependencies.user_risk_provider.prepare_snapshot(
                case_ref=state["case_ref"],
                reason_code=decision.reason_code,
                as_of=state["case_context"].case_opened_at,
            )
            risk_gate = evaluate_user_risk(
                decision.action,
                risk_snapshot,
                dependencies.user_risk_config,
            )
        except Exception:
            risk_snapshot = None
            risk_gate = unavailable_user_risk_gate(
                dependencies.user_risk_config
            )
    else:
        risk_snapshot = None
        risk_gate = not_applicable_user_risk_gate(...)
```

---

## 16.4 Routing priority

v1 保留單一：

```text
review_routing_reason
```

避免 contract 大改。

Priority：

```text
if amount_gate.status == HUMAN_REQUIRED:
    primary reason = amount_gate.reason
    → await_human_review

elif risk_gate.status == HUMAN_REQUIRED:
    primary reason = risk_gate.reason
    → await_human_review

else:
    → emit_resolution_handoff
```

所以：

```text
amount HIGH
risk HIGH
```

結果：

```text
routing_reason = HIGH_VALUE_ITEM
review_gate = HUMAN_REQUIRED
user_risk_gate = HUMAN_REQUIRED
```

完整 causal trace 仍存在 dossier 兩個 gate 中。

---

## 16.5 Reviewer REVISE branch

完全不改。

```text
REVISE
→ record_revision_event
→ propose_decision
```

Revision budget exhausted：

```text
REVISION_BUDGET_EXCEEDED
```

此 path 不要求 User Risk assessment。

---

# 17. Human Review Integration

## 17.1 `build_human_review_dossier`

修改：

```text
packages/agent_runtime/src/return_agent_runtime/assembly.py
```

將 state 中：

```text
user_risk_snapshot
user_risk_gate
```

放入 dossier。

---

## 17.2 `validate_human_review_entry`

修改 signature：

```python
validate_human_review_entry(
    handoff,
    review,
    dossier,
    reviewer_gate_config,
    user_risk_config,
)
```

所有 call sites 一起更新：

```text
packages/agent_runtime/.../graph.py
apps/api/.../capabilities/human_review.py
apps/api/.../capabilities/refund.py
tests
```

---

## 17.3 Valid Human Review entry cases

### A. Revision budget

```text
routing_reason = REVISION_BUDGET_EXCEEDED
review verdict = REVISE
revision limit reached
review_gate = None
user_risk_gate = None
```

---

### B. Monetary authorization

```text
review verdict = APPROVE
recomputed monetary gate = HUMAN_REQUIRED
dossier.review_gate == recomputed
routing_reason == monetary reason
```

`user_risk_gate` 可以 PASS 或 HUMAN_REQUIRED。

---

### C. Risk authorization

```text
review verdict = APPROVE
monetary gate = PASS
user_risk_gate = HUMAN_REQUIRED
routing_reason =
    HIGH_USER_RISK
    or
    USER_RISK_UNAVAILABLE
```

HIGH：

```text
snapshot required
evaluate_user_risk(snapshot, config)
== dossier.user_risk_gate
```

UNKNOWN：

```text
snapshot may be None
gate reason = USER_RISK_UNAVAILABLE
```

---

# 18. API Human Review Provider

修改：

```text
apps/api/src/return_agent/capabilities/human_review.py
```

`SqlAlchemyHumanReviewProvider.__init__` 新增：

```python
user_risk_config: UserRiskConfig | None = None
```

所有：

```python
validate_human_review_entry(...)
```

傳入同一 shared config。

在：

```text
apps/api/src/return_agent/capabilities/integration.py
```

以同一：

```text
RETURN_AGENT_USER_RISK_CONFIG
```

載入後注入 Human Review provider。

不要讓 Human Review 使用不同 thresholds。

---

# 19. Human Review UI / Projection

現有：

```text
apps/contracts/src/return_agent_contracts/adapters.py
to_human_review_payload(...)
```

already carries：

```text
dossier
routing_reason
review_result
```

因此 v1 優先將 User Risk context 放在：

```text
HumanReviewDossier
```

不必另建平行 Human Review payload type。

Internal UI 顯示：

```text
Automation Risk: HIGH
Policy score: 65

Triggered patterns:
- REPEATED_SAME_REASON_CLAIMS
  3 ITEM_DAMAGED registered claims / 90d

- HIGH_REFUND_RATE
  4 refunded orders / 8 orders = 50%

Snapshot as_of: ...
Config: user-risk:1.0
```

UNKNOWN：

```text
Automation Risk: unavailable
Manual review required because user history could not be verified.
```

禁止：

```text
Scammer
Fraudster
Fraud probability
```

---

# 20. Resolution Handoff Assembly

修改：

```text
packages/agent_runtime/src/return_agent_runtime/assembly.py
build_resolution_handoff(...)
```

將：

```text
user_risk_gate
```

寫入 resolution。

### Reviewer-approved auto path

必須只有：

```text
risk PASS
```

才可能形成 `OutcomeSource.REVIEWER_APPROVE` executable refund。

### Human path

Human APPROVE / EDIT：

```text
user_risk_gate
```

可為：

```text
HUMAN_REQUIRED
```

因為 execution authority 已轉由 persisted Human Review。

---

# 21. Refund Execution Revalidation

修改：

```text
apps/api/src/return_agent/capabilities/refund.py
SqlAlchemyRefundExecutionProvider
```

建議 constructor 加入：

```python
user_risk_snapshot_repository
user_risk_config
```

或注入可讀取 persisted snapshot 的 User Risk capability。

---

## 21.1 Reviewer-approved machine refund

在現有：

```text
evaluate_review_gate(...)
```

revalidation 後新增：

```text
1. require resolution.user_risk_gate exists
2. require snapshot_ref exists
3. load persisted snapshot(snapshot_ref)
4. require snapshot.case_ref == resolution.case_ref
5. require snapshot.reason_code == proposed_decision.reason_code
6. require gate.config_version/hash == loaded config
7. expected_risk = evaluate_user_risk(
       FULL_REFUND,
       persisted_snapshot,
       user_risk_config
   )
8. require resolution.user_risk_gate == expected_risk
9. require expected_risk.status == PASS
```

Failure reason codes 建議：

```text
USER_RISK_GATE_MISSING
USER_RISK_GATE_INVALID
USER_RISK_SNAPSHOT_INVALID
HUMAN_AUTHORIZATION_REQUIRED
```

---

## 21.2 Never re-query live history during execution

禁止：

```text
refund execution
→ query current User history again
→ calculate a new snapshot
```

否則：

```text
Reviewer 時 PASS
另一筆 case 中途完成 refund
Execution 時變 HIGH
```

會造成同一 authorization nondeterministic。

Execution 必須：

```text
same snapshot
+
same config
+
same evaluator
```

---

## 21.3 Human APPROVE / EDIT

沿用目前 Human authorization model。

增加 integrity check：

```text
resolution.user_risk_gate
==
persisted HumanReviewDossier.user_risk_gate
```

Human path 不要求 risk gate PASS。

---

# 22. REFUND_SUCCEEDED History Update

Canonical trigger：

```text
RefundExecutionStatus.SUCCEEDED
```

也就是 refund application 已：

```text
APPLIED
```

才可以寫 history。

不得在：

```text
Reviewer APPROVE
Human APPROVE
Resolution handoff
refund IN_PROGRESS
```

時提前記錄。

---

## 22.1 Integration point

target repo目前：

```text
apps/api/src/return_agent/capabilities/refund.py
```

先 durable persist refund execution result；

```text
apps/api/src/return_agent/agent_bridge.py
```

收到 `RefundExecutionStatus.SUCCEEDED` 後完成 Case terminal projection。

v1 要求：

> `REFUND_SUCCEEDED` risk event 必須在已確認 canonical refund execution 為 SUCCEEDED 後 idempotently append。

建議優先放在 API refund completion capability 的 durable success boundary；如果為了維持 transaction ownership 選擇 AgentBridge terminal projection，也必須依 `case_ref + REFUND_SUCCEEDED` unique constraint 保證 replay safety。

不要在 Agent Service 寫 risk history。

---

# 23. Config Wiring in API

現有 API integration composition會：

```python
reviewer_gate_config = load_reviewer_gate_config(
    os.environ.get("RETURN_AGENT_REVIEW_GATE_CONFIG")
)
```

新增：

```python
user_risk_config = load_user_risk_config(
    os.environ.get("RETURN_AGENT_USER_RISK_CONFIG")
)
```

同一 config 注入：

```text
SqlAlchemyHumanReviewProvider
SqlAlchemyRefundExecutionProvider
```

User Risk Provider本身只建立 snapshot，不需要自行做 routing decision。

---

# 24. Generated Schemas and Web Contracts

Contracts 修改後，不可手改 generated JSON Schema。

執行：

```bash
make contracts
```

目前 Makefile 會重新產生：

```text
apps/contracts/schemas/agent/v1
apps/contracts/schemas/ui/v1
apps/contracts/schemas/operations/v1
```

Web build會先執行：

```text
npm --prefix apps/web run contracts
```

因此 HumanReviewDossier / Resolution schema 改動後需：

```bash
make contracts
npm --prefix apps/web run contracts
```

再修改 UI rendering。

---

# 25. Required Tests

## 25.1 Contracts

新增：

```text
apps/contracts/tests/contracts/test_user_risk.py
```

至少：

```text
score 0  → LOW PASS
score 40 → MEDIUM PASS
score 59 → MEDIUM PASS
score 60 → HIGH HUMAN_REQUIRED
score 65 → HIGH HUMAN_REQUIRED
```

另測：

- `orders_90d = 0`。
- minimum-order guard。
- deterministic tag order。
- stable config hash。
- unknown config key rejected。
- invalid Gate combinations rejected。
- DECLINE → NOT_APPLICABLE。
- UNKNOWN → HUMAN_REQUIRED。
- no direct BLOCK concept。

---

## 25.2 API persistence

測：

- duplicate `CLAIM_REGISTERED` → one row。
- duplicate `REFUND_SUCCEEDED` → one row。
- current case event at `as_of` excluded。
- 90-day boundary。
- only same ReasonCode counted。
- refunded order uses DISTINCT order_ref。
- snapshot retry returns exact same persisted facts。
- later events do not mutate existing snapshot。
- profile missing fails provider。
- legacy `risk_evaluations` untouched。

---

## 25.3 Internal Provider

測：

```text
POST /internal/v1/user-risk/snapshot
```

- auth required。
- valid round trip。
- unknown case。
- wrong as_of。
- profile missing。
- retry stable。
- unknown response keys rejected by contract。

---

## 25.4 Runtime

測：

### LOW

```text
Reviewer APPROVE
monetary PASS
risk LOW
→ emit_resolution_handoff
```

### MEDIUM

```text
risk score 40
→ PASS
→ emit_resolution_handoff
```

### HIGH

```text
risk score 65
→ await_human_review
routing_reason = HIGH_USER_RISK
```

### unavailable

```text
provider raises
→ UNKNOWN
→ await_human_review
routing_reason = USER_RISK_UNAVAILABLE
```

### both gates

```text
amount HIGH
risk HIGH
→ monetary routing reason remains primary
→ dossier contains both gates
```

### Reviewer independence

explicitly inspect REVIEW model payload and assert no Risk fields。

### Existing Reviewer REVISE

must remain unchanged。

---

## 25.5 Human Review

測：

```text
HIGH → Human APPROVE
HIGH → Human EDIT
HIGH → Human REJECT
UNKNOWN → Human APPROVE
```

以及：

- invalid dossier risk gate rejected。
- changed config hash rejected where recomputation is expected。
- monetary+user-risk dual gate accepted with monetary primary reason。

---

## 25.6 Refund execution

Machine path：

- LOW PASS executes。
- MEDIUM PASS executes。
- forged `user_risk_gate=PASS` rejected。
- wrong snapshot_ref rejected。
- wrong case/reason snapshot rejected。
- risk HIGH cannot execute as REVIEWER_APPROVE。
- API uses persisted snapshot, not current history。

Human path：

- HIGH + valid Human APPROVE executes。
- HIGH + valid Human EDIT executes。
- Human REJECT no refund。
- UNKNOWN + valid Human authorization can execute if final Human decision is refund。

History：

- execution SUCCEEDED → one `REFUND_SUCCEEDED` event。
- replay → still one event。
- REJECTED execution → no success event。

---

## 25.7 Config compose

新增 target repo equivalent：

```text
tests/test_user_risk_config_compose.py
```

要求 API / Agent Service 使用相同：

```text
version
fingerprint
rules
```

---

# 26. Test Commands

依 target repo 現有 Makefile：

```bash
make test-contracts
make test-api
make test-agent-runtime
make test-agent-service
make test-e2e
```

全量：

```bash
make check
```

Web：

```bash
make check-web
```

Migration：

```bash
make migrate
```

Contract regeneration：

```bash
make contracts
```

---

# 27. Controlled Demo

在：

```text
data/scenarios.json.example
```

增加三個 User Risk scenarios。

三個 case 必須保持：

```text
same market
same ReasonCode = ITEM_DAMAGED
same category
same PolicyBundle
same evidence
same amount < monetary threshold
same Reviewer APPROVE
```

唯一變因：

```text
user_ref → seeded historical behavior
```

---

## 27.1 NORMAL

```text
score = 0
LOW
monetary PASS
risk PASS

→ REVIEWER_APPROVE
→ auto refund
```

---

## 27.2 WATCH

```text
score = 40
MEDIUM
risk PASS

→ auto refund
```

這個 scenario 必須保留，用來證明：

> 單一 suspicious historical pattern 不等於一律人工。

---

## 27.3 HIGH-RISK

```text
score = 65
HIGH
risk HUMAN_REQUIRED

→ existing Human Review
```

Human reviewer可示範：

```text
APPROVE
```

然後：

```text
refund SUCCEEDED
→ REFUND_SUCCEEDED event
```

---

# 28. Audit Trace

對 risk case 必須可還原：

```text
case_ref
  ↓
proposed decision
  ↓
Reviewer APPROVE
  ↓
monetary gate
  ↓
UserRiskGateResult
  ├─ config_version
  ├─ config_hash
  ├─ score
  ├─ tags
  ├─ matched_rules
  └─ snapshot_ref
        ↓
persisted immutable UserRiskSnapshot
        ↓
routing_reason
        ↓
Human Review result (if any)
        ↓
RefundExecutionRecord
        ↓
REFUND_SUCCEEDED event (if successful)
```

不依賴 hidden chain-of-thought。

---

# 29. Privacy / Presentation Boundary

## Internal Human Review

可看：

```text
risk level
policy score
matched historical patterns
relevant aggregate counts
snapshot as_of
config version
```

## Buyer-facing UI / conversation

不可看：

```text
risk score
risk tags
account age
refund rate
past claim count
manual-risk routing details
```

Buyer-facing response應只呈現：

```text
case requires additional/manual review
```

不得指控 user fraud/scam。

---

# 30. Files Expected to Change

## New

```text
config/user-risk.json

apps/contracts/src/return_agent_contracts/user_risk.py

apps/api/src/return_agent/capabilities/user_risk.py
apps/api/alembic/versions/0014_user_risk_authorization.py

data/user-risk.json.example

apps/contracts/tests/contracts/test_user_risk.py
apps/api/tests/test_user_risk.py
packages/agent_runtime/tests/<user-risk related tests>
tests/test_user_risk_config_compose.py
```

Exact test filename可依現有 test organization 調整。

---

## Existing files likely modified

```text
apps/contracts/src/return_agent_contracts/__init__.py
apps/contracts/src/return_agent_contracts/interfaces.py
apps/contracts/src/return_agent_contracts/transport.py
apps/contracts/src/return_agent_contracts/http_adapters.py
apps/contracts/src/return_agent_contracts/review_gates.py
apps/contracts/src/return_agent_contracts/models.py
apps/contracts/src/return_agent_contracts/validation.py
apps/contracts/src/return_agent_contracts/adapters.py
apps/contracts/src/return_agent_contracts/ui.py   # only if rendering needs explicit fields

packages/agent_runtime/src/return_agent_runtime/dependencies.py
packages/agent_runtime/src/return_agent_runtime/state.py
packages/agent_runtime/src/return_agent_runtime/graph.py
packages/agent_runtime/src/return_agent_runtime/assembly.py

apps/agent_service/src/return_agent_service/composition.py
apps/agent_service/src/return_agent_service/main.py   # demo profile/config wiring if needed

apps/api/src/return_agent/db/models.py
apps/api/src/return_agent/capabilities/integration.py
apps/api/src/return_agent/capabilities/human_review.py
apps/api/src/return_agent/capabilities/refund.py
apps/api/src/return_agent/app.py

docker-compose.yml
scripts/local_import.py

data/scenarios.json.example
data/README.md

generated schemas under apps/contracts/schemas/**
generated web contracts after npm contracts generation
```

---

# 31. Implementation Order

建議依 dependency direction：

```text
1. shared User Risk contracts + config/evaluator
2. DB migration + ORM + mock seed
3. SqlAlchemyUserRiskProvider
4. internal transport + HttpUserRiskProvider
5. AgentDependencies + state
6. Reviewer APPROVE routing
7. HumanReviewDossier + validation
8. API Human Review config validation
9. Resolution handoff
10. Refund execution revalidation
11. REFUND_SUCCEEDED history write
12. schema regeneration
13. Human Review UI
14. three-persona E2E
15. full regression
```

不要先改 UI 再補 authorization invariants。

---

# 32. Acceptance Criteria

Feature complete when：

1. `NORMAL`、`WATCH`、`HIGH-RISK` 使用相同 Policy/Evidence/Amount 時得到相同 Reviewer APPROVE。
2. NORMAL → LOW → machine refund。
3. WATCH → MEDIUM → machine refund。
4. HIGH-RISK → HIGH → existing Human Review。
5. Provider unavailable → UNKNOWN → existing Human Review。
6. Risk HIGH 本身永遠不能直接 DECLINE/BLOCK。
7. Human Review仍可 APPROVE / EDIT / REJECT。
8. Current case 不 self-count。
9. Snapshot retry 不因後續 history 改變。
10. API reviewer-approved refund會獨立重算 User Risk Gate。
11. API revalidation 使用 persisted snapshot，不使用最新 history。
12. Refund真正成功後才新增 `REFUND_SUCCEEDED`。
13. Refund replay 不重複新增 event。
14. Reviewer prompt中完全沒有 risk information。
15. Buyer-facing UI不洩漏 historical risk facts。
16. Existing monetary gate semantics不 regression。
17. Existing evidence/revision/human-review/refund tests不 regression。
18. `make check` passing。
19. `make check-web` passing。
20. `docker compose config` 驗證 API / Agent Service 共用同一 User Risk config。

---

# 33. Definition of Done

可以用以下一句話精確描述功能：

> The existing agent continues to determine refund eligibility from Policy and Evidence independently; after Reviewer approval, a versioned deterministic user-history gate decides whether the approved refund may execute automatically or must enter the system's existing Human Review flow.

這個 feature 的核心不是「AI 判斷誰是詐騙者」，而是：

```text
Reliable eligibility judgment
+
Deterministic adaptive automation authority
+
Auditable fail-closed Human Review
```
