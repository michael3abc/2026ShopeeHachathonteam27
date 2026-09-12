/* Generated from apps/contracts. Do not edit manually. */

export type AgentEvent =
  | NodeEnterEvent
  | NodeExitEvent
  | ToolCallEvent
  | ToolResultEvent
  | TokenEvent
  | MemoryRetrievalEvent
  | InterruptEvent
  | StateChangeEvent
  | DoneEvent
  | ErrorEvent;
export type CaseRef = string;
export type GraphNodeName =
  | "parse_request"
  | "request_clarification"
  | "load_case_context"
  | "retrieve_policy"
  | "prepare_memory_query"
  | "retrieve_memory"
  | "assess_case"
  | "request_evidence"
  | "propose_decision"
  | "external_verification"
  | "reviewer"
  | "record_revision_event"
  | "await_human_review"
  | "emit_resolution_handoff"
  | "enqueue_memory_distillation"
  | "distill_memory"
  | "submit_candidate"
  | "external_memory_approval"
  | "terminate_automation";
export type Detail = string | null;
export type Amount = string;
export type ConfigHash = string;
export type ConfigVersion = string;
export type Currency = string;
export type Reason = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
export type Seq = number;
export type Ts = string;
export type Type = "node_enter";
export type CaseRef1 = string;
export type Seq1 = number;
export type Ts1 = string;
export type Type1 = "node_exit";
export type CaseRef2 = string;
export type CallId = string;
export type ToolName = string;
export type Seq2 = number;
export type Ts2 = string;
export type Type2 = "tool_call";
export type CaseRef3 = string;
export type CallId1 = string;
export type DurationMs = number;
export type Error = string | null;
export type Ok = boolean;
export type Summary = string;
export type ToolName1 = string;
export type Seq3 = number;
export type Ts3 = string;
export type Type3 = "tool_result";
export type CaseRef4 = string;
export type Text = string;
export type Seq4 = number;
export type Ts4 = string;
export type Type4 = "token";
export type CaseRef5 = string;
/**
 * The latest query result, including empty or unavailable retrieval.
 */
export type MemoryRetrievalPayload = MemoryRetrievalPayload1;
export type ErrorCode = ("SUMMARY_UNAVAILABLE" | "RETRIEVAL_UNAVAILABLE") | null;
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
export type ClaimIds = ClaimId[];
export type Market = string;
export type ReasonCode =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReasonCodes = ReasonCode[];
export type Status1 = "APPROVED";
/**
 * @minItems 1
 */
export type TriggerConditions = [string, ...string[]];
export type Similarity = number;
export type QuerySummary = string | null;
export type Status2 = "OK" | "UNAVAILABLE";
export type Seq5 = number;
export type Ts5 = string;
export type Type5 = "memory_retrieval";
export type CaseRef6 = string;
export type Payload = ClarificationInterruptPayload | EvidenceInterruptPayload | HumanReviewInterruptPayload;
export type CaseRef7 = string;
export type InterruptKind = "CLARIFICATION";
export type ClarificationQuestion = string;
export type ClarificationRound = number;
/**
 * @minItems 1
 */
export type MissingFields = [string, ...string[]];
export type RequestId = string;
export type InterruptKind1 = "EVIDENCE_REQUEST";
/**
 * @minItems 1
 */
export type AcceptedEvidenceTypes = [EvidenceType, ...EvidenceType[]];
export type EvidenceType = "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT";
export type CaseRef8 = string;
/**
 * @minItems 1
 */
export type MissingClaims = [MissingClaim, ...MissingClaim[]];
export type Subject = string;
/**
 * @minItems 1
 */
export type PolicyRefs = [string, ...string[]];
export type RequestId1 = string;
export type UserMessage = string;
export type InterruptKind2 = "HUMAN_REVIEW";
export type Review = FullRefundHumanReviewPayload | DeclineHumanReviewPayload;
export type Action = "FULL_REFUND";
export type Amount1 = string;
export type CaseRef9 = string;
export type Currency1 = string;
export type ClaimRegistryVersion1 = string;
/**
 * @minItems 1
 */
export type ClaimedLineItemIds = [string, ...string[]];
export type AlreadyRefundedAmount = string;
export type CapturedAt = string;
export type Currency2 = string;
export type DeliveredAt = string;
/**
 * @minItems 1
 */
export type LineItems = [OrderLineItem, ...OrderLineItem[]];
export type CategoryRef = string;
export type LineItemId = string;
export type Quantity = number;
export type RefundableAmount = string;
export type SkuRef = string;
export type Title = string;
export type OrderRef = string;
export type OrderSnapshotRef = string;
export type RefundableAmountMax = string;
export type SnapshotVersion = number;
/**
 * @minItems 1
 */
export type AllowedActions = [ResolutionAction, ...ResolutionAction[]];
export type ResolutionAction = "DECLINE" | "FULL_REFUND";
export type Categories1 = string[];
export type Markets = string[];
export type ReasonCodes1 = ReasonCode[];
export type ClauseId = string;
export type EffectiveFrom = string;
export type EffectiveTo = string | null;
export type PolicyVersion1 = string;
/**
 * @minItems 1
 */
export type RequiredClaimIds = [ClaimId, ...ClaimId[]];
export type ReturnPolicy = "REQUIRED" | "NOT_REQUIRED" | "MODEL_JUDGMENT";
export type Text1 = string;
export type Clauses = PolicyClause[];
export type PolicyBundleVersion = string;
export type RetrievalStatus = "OK" | "AMBIGUOUS" | "NOT_FOUND";
export type RetrievedAt = string;
/**
 * @minItems 1
 */
export type ProposalHistory = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type AgentPromptVersion = string;
export type CaseRef10 = string;
export type ClaimRegistryVersion2 = string;
export type ArtifactRef = string;
export type CollectedAt = string;
export type EvidenceId = string;
export type ExtractedSummary = string;
export type EvidenceSource = "USER" | "ORDER_TOOL" | "LOGISTICS_TOOL" | "SYSTEM";
export type Subject1 = string;
export type EvidenceBundle = EvidenceItem[];
export type HandoffId = string;
export type HandoffVersion = "1.0";
export type OrderSnapshotRef1 = string;
export type PolicyBundleVersion1 = string;
/**
 * @minItems 1
 */
export type PolicyRefs1 = [string, ...string[]];
export type ProposedDecision = FullRefundProposedDecision | DeclineProposedDecision;
export type Action1 = "FULL_REFUND";
export type Amount2 = string;
export type Currency3 = string;
export type EvidenceRefs = string[];
/**
 * @minItems 1
 */
export type PolicyRefs2 = [string, ...string[]];
/**
 * @minItems 1
 */
export type LineItemIds = [string, ...string[]];
export type ReturnDecision = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type Requirement = RequiredReturnRequirement | WaivedReturnRequirement;
export type RequiredReturnReasonCode = "RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION";
export type Required = true;
export type WaivedReturnReasonCode =
  "ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN";
export type Required1 = false;
export type Source = "POLICY";
export type Requirement1 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source1 = "MODEL_JUDGMENT";
export type Action2 = "DECLINE";
export type Amount3 = string;
export type Currency4 = string;
export type EvidenceRefs1 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs3 = [string, ...string[]];
/**
 * @maxItems 0
 */
export type LineItemIds1 = [];
export type RationaleSummary = string;
export type RevisionRound = number;
/**
 * @minItems 1
 */
export type ReviewHistory = [
  ApprovedReviewResult | RevisedReviewResult,
  ...(ApprovedReviewResult | RevisedReviewResult)[]
];
export type ReviewedAt = string;
/**
 * @minItems 1
 */
export type ReviewerClaimFindings = [ClaimFinding, ...ClaimFinding[]];
export type Explanation = string;
export type ClaimStatus = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
export type Subject2 = string;
export type SupportingEvidenceRefs = string[];
export type ReviewerPromptVersion = string;
/**
 * @maxItems 0
 */
export type RevisionReasons = [];
export type Verdict = "APPROVE";
export type ReviewedAt1 = string;
/**
 * @minItems 1
 */
export type ReviewerClaimFindings1 = [ClaimFinding, ...ClaimFinding[]];
export type ReviewerPromptVersion1 = string;
/**
 * @minItems 1
 */
export type RevisionReasons1 = [RevisionReason, ...RevisionReason[]];
export type RevisionReasonCode =
  | "EVIDENCE_INSUFFICIENT"
  | "POLICY_MISMATCH"
  | "DECISION_UNSUPPORTED"
  | "DECISION_INCONSISTENT"
  | "SCOPE_UNSUPPORTED"
  | "RETURN_REQUIREMENT_INCONSISTENT"
  | "HANDOFF_INCOMPLETE"
  | "OTHER";
export type EvidenceRefs2 = string[];
export type Message = string;
export type PolicyRefs4 = string[];
export type RequiredChange = string;
export type Subject3 = string;
export type Verdict1 = "REVISE";
export type CaseRef11 = string;
export type CreatedAt = string;
export type EventId = string;
export type HandoffBeforeRef = string;
export type ReviewResult = ApprovedReviewResult | RevisedReviewResult;
export type RevisionRound1 = number;
export type RevisionEvents = DecisionRevisionEvent[];
export type RoutingReason = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type ArtifactRef1 = string;
export type Caption = string;
export type EvidenceId1 = string;
export type Subject4 = string;
export type EvidenceRefs3 = EvidenceDisplayRef[];
export type HandoffId1 = string;
export type MemoriesUsed = string[];
export type ClauseId1 = string;
export type Excerpt = string;
export type PolicyVersion2 = string;
export type Relevance = number | null;
export type Title1 = string | null;
export type PolicyHits = PolicyDisplayRef[];
export type RationaleSummary1 = string;
export type ReturnDecision1 = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type ReviewResult1 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason1 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type Action3 = "DECLINE";
export type Amount4 = string;
export type CaseRef12 = string;
export type Currency5 = string;
export type EvidenceRefs4 = EvidenceDisplayRef[];
export type HandoffId2 = string;
export type MemoriesUsed1 = string[];
export type PolicyHits1 = PolicyDisplayRef[];
export type RationaleSummary2 = string;
export type ReviewResult2 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason2 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type Seq6 = number;
export type Ts6 = string;
export type Type6 = "interrupt";
export type CaseRef13 = string;
/**
 * Backend-owned status displayed by the UI, not Agent graph state.
 */
export type CaseStatus =
  | "OBSERVING"
  | "AWAITING_CLARIFICATION"
  | "AWAITING_EVIDENCE"
  | "AWAITING_HUMAN_REVIEW"
  | "EXECUTING"
  | "RESOLVED"
  | "ESCALATED";
export type Reason1 = string;
export type Seq7 = number;
export type Ts7 = string;
export type Type7 = "state_change";
export type CaseRef14 = string;
export type Status3 = "RESOLVED" | "ESCALATED";
export type TerminalRef = string;
export type Seq8 = number;
export type Ts8 = string;
export type Type8 = "done";
export type CaseRef15 = string;
export type Code = string;
export type Message1 = string;
export type Retryable = boolean;
export type Seq9 = number;
export type Ts9 = string;
export type Type9 = "error";

export interface NodeEnterEvent {
  case_ref: CaseRef;
  node: GraphNodeName;
  payload?: NodeLifecyclePayload;
  seq: Seq;
  ts: Ts;
  type: Type;
}
export interface NodeLifecyclePayload {
  detail?: Detail;
  review_gate?: ReviewGateResult | null;
}
export interface ReviewGateResult {
  amount: Amount;
  config_hash: ConfigHash;
  config_version: ConfigVersion;
  currency: Currency;
  reason: Reason;
  status: Status;
  threshold: Threshold;
}
export interface NodeExitEvent {
  case_ref: CaseRef1;
  node: GraphNodeName;
  payload?: NodeLifecyclePayload;
  seq: Seq1;
  ts: Ts1;
  type: Type1;
}
export interface ToolCallEvent {
  case_ref: CaseRef2;
  node: GraphNodeName;
  payload: ToolCallPayload;
  seq: Seq2;
  ts: Ts2;
  type: Type2;
}
export interface ToolCallPayload {
  arguments?: Arguments;
  call_id: CallId;
  tool_name: ToolName;
}
export interface Arguments {
  [k: string]: string;
}
export interface ToolResultEvent {
  case_ref: CaseRef3;
  node: GraphNodeName;
  payload: ToolResultPayload;
  seq: Seq3;
  ts: Ts3;
  type: Type3;
}
export interface ToolResultPayload {
  call_id: CallId1;
  duration_ms: DurationMs;
  error?: Error;
  ok: Ok;
  summary: Summary;
  tool_name: ToolName1;
}
export interface TokenEvent {
  case_ref: CaseRef4;
  node: GraphNodeName;
  payload: TokenPayload;
  seq: Seq4;
  ts: Ts4;
  type: Type4;
}
export interface TokenPayload {
  text: Text;
}
export interface MemoryRetrievalEvent {
  case_ref: CaseRef5;
  node: GraphNodeName;
  payload: MemoryRetrievalPayload;
  seq: Seq5;
  ts: Ts5;
  type: Type5;
}
export interface MemoryRetrievalPayload1 {
  error_code?: ErrorCode;
  hits?: Hits;
  query_summary?: QuerySummary;
  status: Status2;
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
  status: Status1;
  trigger_conditions: TriggerConditions;
}
export interface MemoryScope {
  categories?: Categories;
  claim_ids?: ClaimIds;
  market: Market;
  reason_codes?: ReasonCodes;
}
export interface InterruptEvent {
  case_ref: CaseRef6;
  node: GraphNodeName;
  payload: Payload;
  seq: Seq6;
  ts: Ts6;
  type: Type6;
}
export interface ClarificationInterruptPayload {
  case_ref: CaseRef7;
  interrupt_kind: InterruptKind;
  request: ClarificationRequest;
}
export interface ClarificationRequest {
  clarification_question: ClarificationQuestion;
  clarification_round: ClarificationRound;
  missing_fields: MissingFields;
  request_id: RequestId;
}
export interface EvidenceInterruptPayload {
  interrupt_kind: InterruptKind1;
  request: EvidenceRequestView;
}
/**
 * The user-evidence interrupt rendered by the conversation UI.
 */
export interface EvidenceRequestView {
  accepted_evidence_types: AcceptedEvidenceTypes;
  case_ref: CaseRef8;
  missing_claims: MissingClaims;
  policy_refs: PolicyRefs;
  request_id: RequestId1;
  user_message: UserMessage;
}
export interface MissingClaim {
  claim_id: ClaimId;
  subject: Subject;
}
export interface HumanReviewInterruptPayload {
  interrupt_kind: InterruptKind2;
  review: Review;
}
export interface FullRefundHumanReviewPayload {
  action: Action;
  amount: Amount1;
  case_ref: CaseRef9;
  currency: Currency1;
  dossier?: HumanReviewDossier | null;
  evidence_refs?: EvidenceRefs3;
  handoff_id: HandoffId1;
  memories_used?: MemoriesUsed;
  policy_hits?: PolicyHits;
  rationale_summary: RationaleSummary1;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision1;
  review_result: ReviewResult1;
  routing_reason?: RoutingReason1;
}
/**
 * Immutable, structured decision trace; never model hidden reasoning.
 */
export interface HumanReviewDossier {
  claim_registry_version: ClaimRegistryVersion1;
  claimed_line_item_ids: ClaimedLineItemIds;
  order_snapshot: OrderSnapshot;
  policy_bundle: PolicyBundle;
  proposal_history: ProposalHistory;
  review_gate?: ReviewGateResult | null;
  review_history: ReviewHistory;
  revision_events?: RevisionEvents;
  routing_reason?: RoutingReason;
}
export interface OrderSnapshot {
  already_refunded_amount: AlreadyRefundedAmount;
  captured_at: CapturedAt;
  currency: Currency2;
  delivered_at: DeliveredAt;
  line_items: LineItems;
  order_ref: OrderRef;
  order_snapshot_ref: OrderSnapshotRef;
  refundable_amount_max: RefundableAmountMax;
  snapshot_version: SnapshotVersion;
}
export interface OrderLineItem {
  category_ref: CategoryRef;
  line_item_id: LineItemId;
  quantity: Quantity;
  refundable_amount: RefundableAmount;
  sku_ref: SkuRef;
  title: Title;
}
export interface PolicyBundle {
  clauses?: Clauses;
  policy_bundle_version: PolicyBundleVersion;
  retrieval_status: RetrievalStatus;
  retrieved_at: RetrievedAt;
}
export interface PolicyClause {
  allowed_actions: AllowedActions;
  applicable_conditions: ApplicableConditions;
  clause_id: ClauseId;
  effective_from: EffectiveFrom;
  effective_to?: EffectiveTo;
  policy_version: PolicyVersion1;
  required_claim_ids: RequiredClaimIds;
  return_policy: ReturnPolicy;
  text: Text1;
}
export interface ApplicableConditions {
  categories?: Categories1;
  markets?: Markets;
  reason_codes?: ReasonCodes1;
}
export interface ProposedDecisionHandoff {
  agent_prompt_version: AgentPromptVersion;
  case_ref: CaseRef10;
  claim_registry_version: ClaimRegistryVersion2;
  evidence_bundle?: EvidenceBundle;
  handoff_id: HandoffId;
  handoff_version: HandoffVersion;
  order_snapshot_ref: OrderSnapshotRef1;
  policy_bundle_version: PolicyBundleVersion1;
  policy_refs: PolicyRefs1;
  proposed_decision: ProposedDecision;
  rationale_summary: RationaleSummary;
  revision_round: RevisionRound;
}
export interface EvidenceItem {
  artifact_ref: ArtifactRef;
  collected_at: CollectedAt;
  evidence_id: EvidenceId;
  extracted_summary: ExtractedSummary;
  source: EvidenceSource;
  subject: Subject1;
  type: EvidenceType;
}
/**
 * Graph-completed refund decision included in a handoff.
 */
export interface FullRefundProposedDecision {
  action: Action1;
  amount: Amount2;
  currency: Currency3;
  evidence_refs?: EvidenceRefs;
  policy_refs: PolicyRefs2;
  reason_code: ReasonCode;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision;
}
export interface NonEmptyRefundScope {
  line_item_ids: LineItemIds;
}
export interface PolicyReturnDecision {
  requirement: Requirement;
  source: Source;
}
export interface RequiredReturnRequirement {
  reason_code: RequiredReturnReasonCode;
  required: Required;
}
export interface WaivedReturnRequirement {
  reason_code: WaivedReturnReasonCode;
  required: Required1;
}
export interface ModelJudgmentReturnDecision {
  requirement: Requirement1;
  source: Source1;
}
export interface DeclineProposedDecision {
  action: Action2;
  amount: Amount3;
  currency: Currency4;
  evidence_refs?: EvidenceRefs1;
  policy_refs: PolicyRefs3;
  reason_code: ReasonCode;
  refund_scope: EmptyRefundScope;
}
export interface EmptyRefundScope {
  line_item_ids?: LineItemIds1;
}
export interface ApprovedReviewResult {
  reviewed_at: ReviewedAt;
  reviewer_claim_findings: ReviewerClaimFindings;
  reviewer_prompt_version: ReviewerPromptVersion;
  revision_reasons?: RevisionReasons;
  verdict: Verdict;
}
export interface ClaimFinding {
  claim_id: ClaimId;
  explanation: Explanation;
  status: ClaimStatus;
  subject: Subject2;
  supporting_evidence_refs?: SupportingEvidenceRefs;
}
export interface RevisedReviewResult {
  reviewed_at: ReviewedAt1;
  reviewer_claim_findings: ReviewerClaimFindings1;
  reviewer_prompt_version: ReviewerPromptVersion1;
  revision_reasons: RevisionReasons1;
  verdict: Verdict1;
}
export interface RevisionReason {
  code: RevisionReasonCode;
  evidence_refs?: EvidenceRefs2;
  message: Message;
  policy_refs?: PolicyRefs4;
  required_change: RequiredChange;
  subject: Subject3;
}
export interface DecisionRevisionEvent {
  case_ref: CaseRef11;
  created_at: CreatedAt;
  event_id: EventId;
  handoff_before_ref: HandoffBeforeRef;
  review_result: ReviewResult;
  revision_round: RevisionRound1;
}
/**
 * Reference-only evidence view; signed URLs stay in the Backend/UI layer.
 */
export interface EvidenceDisplayRef {
  artifact_ref: ArtifactRef1;
  caption: Caption;
  evidence_id: EvidenceId1;
  subject: Subject4;
  type: EvidenceType;
}
export interface PolicyDisplayRef {
  clause_id: ClauseId1;
  excerpt: Excerpt;
  policy_version: PolicyVersion2;
  relevance?: Relevance;
  title?: Title1;
}
export interface DeclineHumanReviewPayload {
  action: Action3;
  amount: Amount4;
  case_ref: CaseRef12;
  currency: Currency5;
  dossier?: HumanReviewDossier | null;
  evidence_refs?: EvidenceRefs4;
  handoff_id: HandoffId2;
  memories_used?: MemoriesUsed1;
  policy_hits?: PolicyHits1;
  rationale_summary: RationaleSummary2;
  refund_scope: EmptyRefundScope;
  review_result: ReviewResult2;
  routing_reason?: RoutingReason2;
}
export interface StateChangeEvent {
  case_ref: CaseRef13;
  node: GraphNodeName;
  payload: StateChangePayload;
  seq: Seq7;
  ts: Ts7;
  type: Type7;
}
export interface StateChangePayload {
  from_status?: CaseStatus | null;
  reason: Reason1;
  to_status: CaseStatus;
}
export interface DoneEvent {
  case_ref: CaseRef14;
  node: GraphNodeName;
  payload: DonePayload;
  seq: Seq8;
  ts: Ts8;
  type: Type8;
}
export interface DonePayload {
  status: Status3;
  terminal_ref: TerminalRef;
}
export interface ErrorEvent {
  case_ref: CaseRef15;
  node: GraphNodeName;
  payload: ErrorPayload;
  seq: Seq9;
  ts: Ts9;
  type: Type9;
}
export interface ErrorPayload {
  code: Code;
  message: Message1;
  retryable: Retryable;
}
