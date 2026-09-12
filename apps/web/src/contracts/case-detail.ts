/* Generated from apps/contracts. Do not edit manually. */

export type CaseRef = string;
export type ClarificationQuestion = string;
export type ClarificationRound = number;
/**
 * @minItems 1
 */
export type MissingFields = [string, ...string[]];
export type RequestId = string;
export type CreatedAt = string;
/**
 * @minItems 1
 */
export type AcceptedEvidenceTypes = [EvidenceType, ...EvidenceType[]];
export type EvidenceType = "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT";
export type CaseRef1 = string;
/**
 * @minItems 1
 */
export type MissingClaims = [MissingClaim, ...MissingClaim[]];
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
export type Subject = string;
/**
 * @minItems 1
 */
export type PolicyRefs = [string, ...string[]];
export type RequestId1 = string;
export type UserMessage = string;
export type HumanReview = (FullRefundHumanReviewPayload | DeclineHumanReviewPayload) | null;
export type Action = "FULL_REFUND";
export type Amount = string;
export type CaseRef2 = string;
export type Currency = string;
export type ClaimRegistryVersion = string;
/**
 * @minItems 1
 */
export type ClaimedLineItemIds = [string, ...string[]];
export type AlreadyRefundedAmount = string;
export type CapturedAt = string;
export type Currency1 = string;
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
export type Categories = string[];
export type Markets = string[];
export type ReasonCode =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReasonCodes = ReasonCode[];
export type ClauseId = string;
export type EffectiveFrom = string;
export type EffectiveTo = string | null;
export type PolicyVersion = string;
/**
 * @minItems 1
 */
export type RequiredClaimIds = [ClaimId, ...ClaimId[]];
export type ReturnPolicy = "REQUIRED" | "NOT_REQUIRED" | "MODEL_JUDGMENT";
export type Text = string;
export type Clauses = PolicyClause[];
export type PolicyBundleVersion = string;
export type RetrievalStatus = "OK" | "AMBIGUOUS" | "NOT_FOUND";
export type RetrievedAt = string;
/**
 * @minItems 1
 */
export type ProposalHistory = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type AgentPromptVersion = string;
export type CaseRef3 = string;
export type ClaimRegistryVersion1 = string;
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
export type Amount1 = string;
export type Currency2 = string;
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
export type Amount2 = string;
export type Currency3 = string;
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
export type Amount3 = string;
export type ConfigHash = string;
export type ConfigVersion = string;
export type Currency4 = string;
export type Reason = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
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
export type CaseRef4 = string;
export type CreatedAt1 = string;
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
export type PolicyVersion1 = string;
export type Relevance = number | null;
export type Title1 = string | null;
export type PolicyHits = PolicyDisplayRef[];
export type RationaleSummary1 = string;
export type ReturnDecision1 = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type ReviewResult1 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason1 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type Action3 = "DECLINE";
export type Amount4 = string;
export type CaseRef5 = string;
export type Currency5 = string;
export type EvidenceRefs4 = EvidenceDisplayRef[];
export type HandoffId2 = string;
export type MemoriesUsed1 = string[];
export type PolicyHits1 = PolicyDisplayRef[];
export type RationaleSummary2 = string;
export type ReviewResult2 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason2 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type HumanReviewResult =
  (ApprovedHumanReviewResult | EditedHumanReviewResult | RejectedHumanReviewResult) | null;
export type Decision = "APPROVE";
export type FinalResolutionRef = string;
export type Generalizable = boolean | null;
export type ReviewNote = string;
export type ReviewedAt2 = string;
export type ReviewerId = string;
export type CorrectedDecision = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type Action4 = "FULL_REFUND";
export type Requirement2 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source2 = "HUMAN_REVIEW";
export type Action5 = "DECLINE";
export type HumanCorrectionReasonCode =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision1 = "EDIT";
export type FinalResolutionRef1 = string;
export type Generalizable1 = boolean | null;
export type ReviewNote1 = string;
export type ReviewedAt3 = string;
export type ReviewerId1 = string;
export type Decision2 = "REJECT";
export type FinalResolutionRef2 = string;
export type Generalizable2 = boolean | null;
export type ReviewNote2 = string;
export type ReviewedAt4 = string;
export type ReviewerId2 = string;
export type OrderRef1 = string;
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
export type UpdatedAt = string;
export type UserRef = string;

/**
 * Backend-owned case view for the Demo UI.
 */
export interface CaseDetail {
  case_ref: CaseRef;
  clarification_request?: ClarificationRequest | null;
  created_at: CreatedAt;
  evidence_request?: EvidenceRequestView | null;
  human_review?: HumanReview;
  human_review_result?: HumanReviewResult;
  order_ref: OrderRef1;
  status: CaseStatus;
  updated_at: UpdatedAt;
  user_ref: UserRef;
}
export interface ClarificationRequest {
  clarification_question: ClarificationQuestion;
  clarification_round: ClarificationRound;
  missing_fields: MissingFields;
  request_id: RequestId;
}
/**
 * The user-evidence interrupt rendered by the conversation UI.
 */
export interface EvidenceRequestView {
  accepted_evidence_types: AcceptedEvidenceTypes;
  case_ref: CaseRef1;
  missing_claims: MissingClaims;
  policy_refs: PolicyRefs;
  request_id: RequestId1;
  user_message: UserMessage;
}
export interface MissingClaim {
  claim_id: ClaimId;
  subject: Subject;
}
export interface FullRefundHumanReviewPayload {
  action: Action;
  amount: Amount;
  case_ref: CaseRef2;
  currency: Currency;
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
  claim_registry_version: ClaimRegistryVersion;
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
  currency: Currency1;
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
  policy_version: PolicyVersion;
  required_claim_ids: RequiredClaimIds;
  return_policy: ReturnPolicy;
  text: Text;
}
export interface ApplicableConditions {
  categories?: Categories;
  markets?: Markets;
  reason_codes?: ReasonCodes;
}
export interface ProposedDecisionHandoff {
  agent_prompt_version: AgentPromptVersion;
  case_ref: CaseRef3;
  claim_registry_version: ClaimRegistryVersion1;
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
  amount: Amount1;
  currency: Currency2;
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
  amount: Amount2;
  currency: Currency3;
  evidence_refs?: EvidenceRefs1;
  policy_refs: PolicyRefs3;
  reason_code: ReasonCode;
  refund_scope: EmptyRefundScope;
}
export interface EmptyRefundScope {
  line_item_ids?: LineItemIds1;
}
export interface ReviewGateResult {
  amount: Amount3;
  config_hash: ConfigHash;
  config_version: ConfigVersion;
  currency: Currency4;
  reason: Reason;
  status: Status;
  threshold: Threshold;
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
  case_ref: CaseRef4;
  created_at: CreatedAt1;
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
  policy_version: PolicyVersion1;
  relevance?: Relevance;
  title?: Title1;
}
export interface DeclineHumanReviewPayload {
  action: Action3;
  amount: Amount4;
  case_ref: CaseRef5;
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
export interface ApprovedHumanReviewResult {
  decision: Decision;
  final_resolution_ref: FinalResolutionRef;
  generalizable?: Generalizable;
  review_note: ReviewNote;
  reviewed_at: ReviewedAt2;
  reviewer_id?: ReviewerId;
}
export interface EditedHumanReviewResult {
  corrected_decision: CorrectedDecision;
  correction_reason_code: HumanCorrectionReasonCode;
  decision: Decision1;
  final_resolution_ref: FinalResolutionRef1;
  generalizable?: Generalizable1;
  review_note: ReviewNote1;
  reviewed_at: ReviewedAt3;
  reviewer_id?: ReviewerId1;
}
export interface CorrectedFullRefundDecision {
  action: Action4;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface HumanReviewReturnDecision {
  requirement: Requirement2;
  source: Source2;
}
export interface CorrectedDeclineDecision {
  action: Action5;
  refund_scope: EmptyRefundScope;
}
export interface RejectedHumanReviewResult {
  decision: Decision2;
  final_resolution_ref: FinalResolutionRef2;
  generalizable?: Generalizable2;
  review_note: ReviewNote2;
  reviewed_at: ReviewedAt4;
  reviewer_id?: ReviewerId2;
}
