/* Generated from apps/contracts. Do not edit manually. */

export type AttemptId = string;
export type CaseRef = string;
export type EventId = string;
export type JobId = string | null;
export type Node = string;
export type OccurredAt = string;
export type OperationId = string;
export type ParentOperationId = string | null;
export type Payload = Lifecycle | NodeSummary | Narration | BackgroundStatus;
export type DurationMs = number | null;
export type ErrorCode = string | null;
export type Action = ("FULL_REFUND" | "DECLINE") | null;
export type Count = number | null;
/**
 * @maxItems 30
 */
export type FindingStatuses = string[];
export type ClaimId =
  | "DELIVERY_CONFIRMED"
  | "ORDER_WITHIN_RETURN_WINDOW"
  | "SHIPMENT_SEAL_INTACT"
  | "ITEM_PHYSICALLY_DAMAGED"
  | "DAMAGE_PRESENT_ON_ARRIVAL"
  | "ITEM_FUNCTIONALLY_IMPAIRED"
  | "ITEM_DIFFERS_FROM_LISTING"
  | "WRONG_ITEM_RECEIVED"
  | "ITEM_NOT_IN_SHIPMENT"
  | "ITEM_UNUSED";
/**
 * @maxItems 30
 */
export type EvidenceRefs = string[];
export type ClaimStatus = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
/**
 * @maxItems 30
 */
export type Findings = ActivityFinding[];
export type NextNode = string | null;
export type Outcome = string | null;
/**
 * @maxItems 30
 */
export type ReasonCodes = string[];
/**
 * @maxItems 30
 */
export type References = string[];
export type RevisionRound = number | null;
export type Verdict = ("APPROVE" | "REVISE") | null;
export type ArgumentCount = number;
export type ReasonCode =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @maxItems 30
 */
export type RequiredClaimIds = ClaimId[];
export type TopK = number | null;
export type Model = string | null;
export type Name = string;
export type Phase = "STARTED" | "COMPLETED" | "PAUSED" | "FAILED";
export type Type = "node" | "model" | "tool";
export type MemoryRetrievalObservation = MemoryRetrievalObservation1;
export type ErrorCode1 = ("SUMMARY_UNAVAILABLE" | "RETRIEVAL_UNAVAILABLE") | null;
/**
 * @maxItems 3
 */
export type Hits =
  [] | [MemorySearchHit] | [MemorySearchHit, MemorySearchHit] | [MemorySearchHit, MemorySearchHit, MemorySearchHit];
export type ApprovedAt = string;
export type ClaimRegistryVersion = string;
export type Confidence = number;
export type MemoryId = string;
export type PolicyVersion = string;
export type RecommendedBehavior = string;
export type RetrievalSummary = string;
export type Categories = string[];
export type ClaimIds = ClaimId[];
export type Market = string;
export type ReasonCodes1 = ReasonCode[];
export type Status = "APPROVED";
/**
 * @minItems 1
 */
export type TriggerConditions = [string, ...string[]];
export type Similarity = number;
export type QuerySummary = string | null;
export type Status1 = "OK" | "UNAVAILABLE";
export type Amount = string;
export type ConfigHash = string;
export type ConfigVersion = string;
export type Currency = string;
export type Reason = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status2 = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
export type Type1 = "node_summary";
export type ErrorCode2 = string | null;
export type SourceEventId = string;
export type Status3 = "COMPLETED" | "UNAVAILABLE";
export type Text = string | null;
export type Type2 = "narration";
export type ErrorCode3 = string | null;
export type Status4 = "SCHEDULED" | "STARTED" | "RETRYING" | "COMPLETED" | "SKIPPED" | "FAILED";
export type Type3 = "background";
export type RunId = string;
export type SchemaVersion = "1.0";
export type Scope = "CASE" | "REFUND" | "MEMORY";
export type Seq = number;

export interface ActivityEvent {
  attempt_id: AttemptId;
  case_ref: CaseRef;
  event_id: EventId;
  job_id?: JobId;
  node: Node;
  occurred_at: OccurredAt;
  operation_id: OperationId;
  parent_operation_id?: ParentOperationId;
  payload: Payload;
  run_id: RunId;
  schema_version?: SchemaVersion;
  scope: Scope;
  seq: Seq;
}
export interface Lifecycle {
  duration_ms?: DurationMs;
  error_code?: ErrorCode;
  facts?: ActivityFacts;
  inputs?: ActivityInputs | null;
  model?: Model;
  name: Name;
  phase: Phase;
  type: Type;
}
/**
 * Finite allowlist; raw prose, URLs, messages and documents are excluded.
 */
export interface ActivityFacts {
  action?: Action;
  count?: Count;
  finding_statuses?: FindingStatuses;
  findings?: Findings;
  next_node?: NextNode;
  outcome?: Outcome;
  reason_codes?: ReasonCodes;
  references?: References;
  revision_round?: RevisionRound;
  verdict?: Verdict;
}
export interface ActivityFinding {
  claim_id: ClaimId;
  evidence_refs?: EvidenceRefs;
  status: ClaimStatus;
}
export interface ActivityInputs {
  argument_count: ArgumentCount;
  reason_code?: ReasonCode | null;
  required_claim_ids?: RequiredClaimIds;
  top_k?: TopK;
}
export interface NodeSummary {
  facts: ActivityFacts;
  memory_retrieval?: MemoryRetrievalObservation | null;
  review_gate?: ReviewGateResult | null;
  type?: Type1;
}
export interface MemoryRetrievalObservation1 {
  error_code?: ErrorCode1;
  hits?: Hits;
  query_summary?: QuerySummary;
  status: Status1;
}
export interface MemorySearchHit {
  memory: ApprovedMemory;
  similarity: Similarity;
}
export interface ApprovedMemory {
  approved_at: ApprovedAt;
  claim_registry_version: ClaimRegistryVersion;
  confidence: Confidence;
  memory_id: MemoryId;
  policy_version: PolicyVersion;
  recommended_behavior: RecommendedBehavior;
  retrieval_summary: RetrievalSummary;
  scope: MemoryScope;
  status: Status;
  trigger_conditions: TriggerConditions;
}
export interface MemoryScope {
  categories?: Categories;
  claim_ids?: ClaimIds;
  market: Market;
  reason_codes?: ReasonCodes1;
}
export interface ReviewGateResult {
  amount: Amount;
  config_hash: ConfigHash;
  config_version: ConfigVersion;
  currency: Currency;
  reason: Reason;
  status: Status2;
  threshold: Threshold;
}
export interface Narration {
  error_code?: ErrorCode2;
  source_event_id: SourceEventId;
  status: Status3;
  text?: Text;
  type?: Type2;
}
export interface BackgroundStatus {
  error_code?: ErrorCode3;
  status: Status4;
  type?: Type3;
}
