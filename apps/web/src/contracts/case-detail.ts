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
  | "ITEM_CONFIRMED_UNDELIVERED"
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
export type ArrivedEventId = string | null;
export type AuthorizationRef = string;
export type InspectionEventId = string | null;
export type PaymentStatus = "NOT_STARTED" | "IN_PROGRESS" | "SUCCEEDED" | "REJECTED";
export type Reason = string | null;
export type RefundReleaseCondition = "RETURN_INSPECTION_PASSED" | "AUTHORIZED_NO_RETURN";
export type ReturnRequired = boolean;
export type ReturnRequirementHash = string;
export type PolicyPathId = "COOLING_OFF" | "DAMAGED_ON_ARRIVAL" | "WRONG_ITEM" | "UNDELIVERED_ITEM";
export type State =
  | "AWAITING_RETURN_CONFIRMATION"
  | "AWAITING_RETURN"
  | "AWAITING_RETURN_INSPECTION"
  | "EXECUTING"
  | "RESOLVED"
  | "ESCALATED";
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
export type DeliveredAt = string | null;
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
export type CrossBorder = boolean | null;
export type Cancelled = boolean | null;
export type DeadlineAt = string;
export type RuleSourceRef = string;
export type RuleSourceVersion = string;
export type Timezone = "Asia/Taipei";
export type Deadlines = PathDeadline[];
export type DeliveryStatus = "RECEIVED" | "CONFIRMED_UNDELIVERED" | "IN_TRANSIT" | "UNKNOWN";
export type Exception = "NONE_CONFIRMED" | "ESTABLISHED" | "UNKNOWN" | "DISPUTED";
export type ExceptionSourceRef = string | null;
export type InvestigationRef = string | null;
export type IsBundle = boolean | null;
export type LineItemId1 = string;
export type PendingSplitDelivery = boolean | null;
export type ReceivedAt = string | null;
export type Refunded = boolean | null;
export type ReservationCaseRef = string | null;
export type ReturnableQuantity = number | null;
export type ShipmentRefs = string[];
export type SourceRef = string;
export type TransactionVersion = string | null;
export type WaiverBasisRefs = string[];
export type Items = ItemPolicyFacts[];
export type Platform = "SHOPEE_TW" | "OTHER" | "UNKNOWN";
export type ProductType = "GENERAL_PHYSICAL" | "SPECIAL" | "UNKNOWN";
export type SellerType = "BUSINESS" | "MALL" | "PERSONAL" | "UNKNOWN";
export type SourceRef1 = string;
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
export type RequiredClaimIds = ClaimId[];
export type ReturnPolicy = "REQUIRED" | "NOT_REQUIRED" | "MODEL_JUDGMENT";
export type Text = string;
export type Clauses = PolicyClause[];
export type CommonConstraints = string[];
/**
 * @minItems 1
 */
export type ClauseRefs = [string, ...string[]];
export type EffectiveFrom1 = string;
export type EffectiveTo1 = string | null;
/**
 * @minItems 1
 */
export type EntryReasons = [ReasonCode, ...ReasonCode[]];
export type InterpretationHash = string;
export type PolicyVersion1 = "DEMO-TW-RETURNS:v2.0";
export type RequiredClaimIds1 = ClaimId[];
/**
 * @minItems 1
 */
export type SourceRefs = [string, ...string[]];
export type SystemPredicate =
  | "TRANSACTION_IN_SCOPE"
  | "SINGLE_REFUNDABLE_ITEM"
  | "NO_EXCEPTION_ESTABLISHED"
  | "WITHIN_PATH_WINDOW"
  | "RECEIPT_CONFIRMED"
  | "PURCHASE_SPEC_AVAILABLE"
  | "NONDELIVERY_CONFIRMED"
  | "NO_PENDING_SPLIT_DELIVERY"
  | "PAYMENT_SCOPE_AVAILABLE";
export type SystemPredicates = SystemPredicate[];
export type Paths = PolicyPath[];
export type PolicyBundleVersion = string;
export type RetrievalStatus = "OK" | "AMBIGUOUS" | "NOT_FOUND";
export type RetrievedAt = string;
export type SchemaVersion = "v1" | "v2";
export type PolicyBundleHistory = PolicyBundle[];
/**
 * @minItems 1
 */
export type ProposalHistory = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type AgentPromptVersion = string;
export type AssessmentFindings = ClaimFinding[] | null;
export type Explanation = string;
export type ClaimStatus = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
export type Subject1 = string;
export type SupportingEvidenceRefs = string[];
export type CaseRef3 = string;
export type ClaimRegistryVersion1 = string;
export type ArtifactRef = string;
export type CollectedAt = string;
export type EvidenceId = string;
export type ExtractedSummary = string;
export type EvidenceSource = "USER" | "ORDER_TOOL" | "LOGISTICS_TOOL" | "SYSTEM";
export type Subject2 = string;
export type EvidenceBundle = EvidenceItem[];
export type HandoffId = string;
export type HandoffVersion = "1.0" | "2.0";
export type OrderSnapshotRef1 = string;
export type PolicyBundleVersion1 = string;
export type Accepted = boolean;
export type ConfirmationRef = string;
export type ConfirmedAt = string;
export type CaseRef4 = string;
export type OriginalScopeHash = string;
export type RequestRef = string;
export type ReturnRequired1 = boolean;
export type ReturnRequirementHash1 = string;
export type SelectionVersion = number;
export type CaseRef5 = string;
export type ClaimRegistryVersion2 = "claim-registry:2.0";
export type EvaluatedAt = string;
export type EvaluationHash = string;
export type EvaluationRef = string;
export type EvaluatorVersion = "policy-evaluator:2.0";
export type EvidenceBundleHash = string;
export type FindingsRef = string;
/**
 * @minItems 1
 */
export type ItemEvaluations = [ItemPolicyEvaluation, ...ItemPolicyEvaluation[]];
export type ClaimRefs = ClaimId[];
export type ClauseRefs1 = string[];
export type LineItemId2 = string;
export type SourceRef2 = string | null;
export type Status = "PASS" | "FAIL" | "UNKNOWN";
export type Predicates = PredicateFinding[];
export type ReasonCodes1 = string[];
export type Status1 = "ELIGIBLE" | "INELIGIBLE" | "NEEDS_INFORMATION" | "SPECIALIST_REQUIRED";
export type OrderSnapshotRef2 = string;
export type PolicyBundleVersion2 = string;
export type ConfirmationRef1 = string | null;
export type RequestedAction = "REFUND" | "RETURN_AND_REFUND" | "EXCHANGE" | "UNSPECIFIED";
export type SelectionVersion1 = number;
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
export type RequiredReturnReasonCode =
  "POLICY_RETURN_REQUIRED" | "RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION";
export type Required = true;
export type WaivedReturnReasonCode =
  | "ITEM_NOT_RECEIVED"
  | "ITEM_UNSALVAGEABLE"
  | "HYGIENE_RISK"
  | "RETURN_UNECONOMICAL"
  | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN";
export type Required1 = false;
export type Source = "POLICY";
export type BasisRefs = string[];
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
export type Reason1 = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status2 = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
/**
 * @minItems 1
 */
export type ReviewHistory = [
  ApprovedReviewResult | RevisedReviewResult,
  ...(ApprovedReviewResult | RevisedReviewResult)[]
];
export type ReviewedAt = string;
export type ReviewerClaimFindings = ClaimFinding[];
export type ReviewerPromptVersion = string;
/**
 * @maxItems 0
 */
export type RevisionReasons = [];
export type Verdict = "APPROVE";
export type ReviewedAt1 = string;
export type ReviewerClaimFindings1 = ClaimFinding[];
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
export type ReviewerEvaluations = PolicyEvaluation[];
export type CaseRef6 = string;
export type CreatedAt1 = string;
export type EventId = string;
export type HandoffBeforeRef = string;
export type ReviewResult = ApprovedReviewResult | RevisedReviewResult;
export type RevisionRound1 = number;
export type RevisionEvents = DecisionRevisionEvent[];
export type RoutingReason =
  | "REVISION_BUDGET_EXCEEDED"
  | "HIGH_VALUE_ITEM"
  | "CURRENCY_THRESHOLD_UNCONFIGURED"
  | "HIGH_USER_RISK"
  | "USER_RISK_UNAVAILABLE";
export type ConfigHash1 = string;
export type ConfigVersion1 = string;
export type MatchedRules = string[];
export type Reason2 = ("HIGH_USER_RISK" | "USER_RISK_UNAVAILABLE") | null;
export type UserRiskLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
export type Score = number;
export type SnapshotRef = string | null;
export type Status3 = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type RiskTag = "REPEATED_SAME_REASON_CLAIMS" | "HIGH_REFUND_RATE" | "NEW_ACCOUNT_REPEATED_CLAIMS";
export type Tags = RiskTag[];
export type AccountAgeDays = number;
export type AsOf = string;
export type CaseRef7 = string;
export type CreatedAt2 = string;
export type Orders90D = number;
export type RefundedOrders90D = number;
export type SameReasonClaims90D = number;
export type SnapshotRef1 = string;
export type UserRef = string;
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
export type RoutingReason1 =
  | "REVISION_BUDGET_EXCEEDED"
  | "HIGH_VALUE_ITEM"
  | "CURRENCY_THRESHOLD_UNCONFIGURED"
  | "HIGH_USER_RISK"
  | "USER_RISK_UNAVAILABLE";
export type Action3 = "DECLINE";
export type Amount4 = string;
export type CaseRef8 = string;
export type Currency5 = string;
export type EvidenceRefs4 = EvidenceDisplayRef[];
export type HandoffId2 = string;
export type MemoriesUsed1 = string[];
export type PolicyHits1 = PolicyDisplayRef[];
export type RationaleSummary2 = string;
export type ReviewResult2 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason2 =
  | "REVISION_BUDGET_EXCEEDED"
  | "HIGH_VALUE_ITEM"
  | "CURRENCY_THRESHOLD_UNCONFIGURED"
  | "HIGH_USER_RISK"
  | "USER_RISK_UNAVAILABLE";
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
export type PolicyFindings = ClaimFinding[] | null;
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
export type PolicySchemaVersion = "v1" | "v2";
/**
 * Backend-owned status displayed by the UI, not Agent graph state.
 */
export type CaseStatus =
  | "OBSERVING"
  | "AWAITING_POLICY_CONFIRMATION"
  | "AWAITING_RETURN_CONFIRMATION"
  | "AWAITING_RETURN"
  | "AWAITING_RETURN_INSPECTION"
  | "AWAITING_CLARIFICATION"
  | "AWAITING_EVIDENCE"
  | "AWAITING_HUMAN_REVIEW"
  | "EXECUTING"
  | "RESOLVED"
  | "ESCALATED";
export type UpdatedAt = string;
export type UserRef1 = string;

/**
 * Backend-owned case view for the Demo UI.
 */
export interface CaseDetail {
  case_ref: CaseRef;
  clarification_request?: ClarificationRequest | null;
  created_at: CreatedAt;
  evidence_request?: EvidenceRequestView | null;
  fulfillment?: FulfillmentProjection | null;
  human_review?: HumanReview;
  human_review_result?: HumanReviewResult;
  order_ref: OrderRef1;
  policy_confirmation_request?: PolicyConfirmationRequest | null;
  policy_evaluation?: PolicyEvaluation | null;
  policy_schema_version?: PolicySchemaVersion;
  status: CaseStatus;
  updated_at: UpdatedAt;
  user_ref: UserRef1;
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
export interface FulfillmentProjection {
  arrived_event_id?: ArrivedEventId;
  authorization_ref: AuthorizationRef;
  inspection_event_id?: InspectionEventId;
  payment_status: PaymentStatus;
  reason?: Reason;
  refund_release_condition: RefundReleaseCondition;
  return_required: ReturnRequired;
  return_requirement_hash: ReturnRequirementHash;
  selected_path_id: PolicyPathId;
  state: State;
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
  policy_bundle_history?: PolicyBundleHistory;
  proposal_history: ProposalHistory;
  review_gate?: ReviewGateResult | null;
  review_history: ReviewHistory;
  reviewer_evaluations?: ReviewerEvaluations;
  revision_events?: RevisionEvents;
  routing_reason?: RoutingReason;
  user_risk_gate?: UserRiskGateResult | null;
  user_risk_snapshot?: UserRiskSnapshot | null;
}
export interface OrderSnapshot {
  already_refunded_amount: AlreadyRefundedAmount;
  captured_at: CapturedAt;
  currency: Currency1;
  delivered_at: DeliveredAt;
  line_items: LineItems;
  order_ref: OrderRef;
  order_snapshot_ref: OrderSnapshotRef;
  policy_facts?: OrderPolicyFacts | null;
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
export interface OrderPolicyFacts {
  cross_border?: CrossBorder;
  items: Items;
  platform?: Platform;
  product_type?: ProductType;
  seller_type?: SellerType;
  source_ref: SourceRef1;
}
export interface ItemPolicyFacts {
  cancelled?: Cancelled;
  deadlines?: Deadlines;
  delivery_status?: DeliveryStatus;
  exception?: Exception;
  exception_source_ref?: ExceptionSourceRef;
  investigation_ref?: InvestigationRef;
  is_bundle?: IsBundle;
  line_item_id: LineItemId1;
  pending_split_delivery?: PendingSplitDelivery;
  purchased_spec?: PurchasedSpec;
  received_at?: ReceivedAt;
  refunded?: Refunded;
  reservation_case_ref?: ReservationCaseRef;
  returnable_quantity?: ReturnableQuantity;
  shipment_refs?: ShipmentRefs;
  source_ref: SourceRef;
  transaction_version?: TransactionVersion;
  waiver_basis_refs?: WaiverBasisRefs;
}
export interface PathDeadline {
  deadline_at: DeadlineAt;
  policy_path_id: PolicyPathId;
  rule_source_ref: RuleSourceRef;
  rule_source_version: RuleSourceVersion;
  timezone?: Timezone;
}
export interface PurchasedSpec {
  [k: string]: string;
}
export interface PolicyBundle {
  clauses?: Clauses;
  common_constraints?: CommonConstraints;
  paths?: Paths;
  policy_bundle_version: PolicyBundleVersion;
  retrieval_status: RetrievalStatus;
  retrieved_at: RetrievedAt;
  schema_version?: SchemaVersion;
  selected_path_id?: PolicyPathId | null;
}
export interface PolicyClause {
  allowed_actions: AllowedActions;
  applicable_conditions: ApplicableConditions;
  clause_id: ClauseId;
  effective_from: EffectiveFrom;
  effective_to?: EffectiveTo;
  path_id?: PolicyPathId | null;
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
export interface PolicyPath {
  clause_refs: ClauseRefs;
  effective_from: EffectiveFrom1;
  effective_to?: EffectiveTo1;
  entry_reasons: EntryReasons;
  interpretation_hash: InterpretationHash;
  path_id: PolicyPathId;
  policy_version?: PolicyVersion1;
  required_claim_ids: RequiredClaimIds1;
  return_policy: ReturnPolicy;
  source_refs: SourceRefs;
  system_predicates: SystemPredicates;
}
export interface ProposedDecisionHandoff {
  agent_prompt_version: AgentPromptVersion;
  assessment_findings?: AssessmentFindings;
  case_ref: CaseRef3;
  claim_registry_version: ClaimRegistryVersion1;
  evidence_bundle?: EvidenceBundle;
  handoff_id: HandoffId;
  handoff_version: HandoffVersion;
  order_snapshot_ref: OrderSnapshotRef1;
  policy_bundle_version: PolicyBundleVersion1;
  policy_confirmation?: PolicyConfirmation | null;
  policy_evaluation?: PolicyEvaluation | null;
  policy_refs: PolicyRefs1;
  policy_selection?: PolicySelection | null;
  proposed_decision: ProposedDecision;
  rationale_summary: RationaleSummary;
  revision_round: RevisionRound;
}
export interface ClaimFinding {
  claim_id: ClaimId;
  explanation: Explanation;
  status: ClaimStatus;
  subject: Subject1;
  supporting_evidence_refs?: SupportingEvidenceRefs;
}
export interface EvidenceItem {
  artifact_ref: ArtifactRef;
  collected_at: CollectedAt;
  evidence_id: EvidenceId;
  extracted_summary: ExtractedSummary;
  source: EvidenceSource;
  subject: Subject2;
  type: EvidenceType;
}
export interface PolicyConfirmation {
  accepted: Accepted;
  confirmation_ref: ConfirmationRef;
  confirmed_at: ConfirmedAt;
  request: PolicyConfirmationRequest;
}
export interface PolicyConfirmationRequest {
  case_ref: CaseRef4;
  original_path_id: PolicyPathId;
  original_scope_hash: OriginalScopeHash;
  path_id: PolicyPathId;
  request_ref: RequestRef;
  return_required: ReturnRequired1;
  return_requirement_hash: ReturnRequirementHash1;
  selection_version: SelectionVersion;
}
export interface PolicyEvaluation {
  case_ref: CaseRef5;
  claim_registry_version?: ClaimRegistryVersion2;
  evaluated_at: EvaluatedAt;
  evaluation_hash: EvaluationHash;
  evaluation_ref: EvaluationRef;
  evaluator_version?: EvaluatorVersion;
  evidence_bundle_hash: EvidenceBundleHash;
  findings_ref: FindingsRef;
  item_evaluations: ItemEvaluations;
  order_snapshot_ref: OrderSnapshotRef2;
  policy_bundle_version: PolicyBundleVersion2;
  selection: PolicySelection;
}
export interface ItemPolicyEvaluation {
  claim_refs: ClaimRefs;
  clause_refs: ClauseRefs1;
  line_item_id: LineItemId2;
  path_id: PolicyPathId;
  predicates: Predicates;
  reason_codes: ReasonCodes1;
  status: Status1;
}
export interface PredicateFinding {
  predicate: SystemPredicate;
  source_ref: SourceRef2;
  status: Status;
}
export interface PolicySelection {
  confirmation_ref?: ConfirmationRef1;
  original_requested_action: RequestedAction;
  selected_path_id: PolicyPathId;
  selection_version: SelectionVersion1;
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
  basis_refs?: BasisRefs;
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
  reason: Reason1;
  status: Status2;
  threshold: Threshold;
}
export interface ApprovedReviewResult {
  reviewed_at: ReviewedAt;
  reviewer_claim_findings: ReviewerClaimFindings;
  reviewer_prompt_version: ReviewerPromptVersion;
  revision_reasons?: RevisionReasons;
  verdict: Verdict;
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
  case_ref: CaseRef6;
  created_at: CreatedAt1;
  event_id: EventId;
  handoff_before_ref: HandoffBeforeRef;
  review_result: ReviewResult;
  revision_round: RevisionRound1;
}
export interface UserRiskGateResult {
  config_hash: ConfigHash1;
  config_version: ConfigVersion1;
  matched_rules: MatchedRules;
  reason: Reason2;
  risk_level: UserRiskLevel;
  score: Score;
  snapshot_ref: SnapshotRef;
  status: Status3;
  tags: Tags;
}
export interface UserRiskSnapshot {
  account_age_days: AccountAgeDays;
  as_of: AsOf;
  case_ref: CaseRef7;
  created_at: CreatedAt2;
  orders_90d: Orders90D;
  reason_code: ReasonCode;
  refunded_orders_90d: RefundedOrders90D;
  same_reason_claims_90d: SameReasonClaims90D;
  snapshot_ref: SnapshotRef1;
  user_ref: UserRef;
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
  case_ref: CaseRef8;
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
  policy_evaluation?: PolicyEvaluation | null;
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
  policy_evaluation?: PolicyEvaluation | null;
  review_note: ReviewNote1;
  reviewed_at: ReviewedAt3;
  reviewer_id?: ReviewerId1;
}
export interface CorrectedFullRefundDecision {
  action: Action4;
  policy_findings?: PolicyFindings;
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
  policy_evaluation?: PolicyEvaluation | null;
  review_note: ReviewNote2;
  reviewed_at: ReviewedAt4;
  reviewer_id?: ReviewerId2;
}
