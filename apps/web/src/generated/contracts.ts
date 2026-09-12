/* Generated from this project's Pydantic contracts. Run npm run contracts. */

export type Contracts =
  | AgentCommand
  | AgentFullRefundFinalDecision
  | AgentResumeCommand
  | AgentResumePayload
  | AgentResumeRequest
  | AgentStartCommand
  | AgentStartPayload
  | AgentStartRequest
  | AgentUserTurn
  | ApplicableConditions
  | AppliedRefundApplicationResult
  | ApplyRefundRequest
  | ApprovalEvidenceAssessment
  | ApproveReviewDecision
  | ApprovedHumanReviewResult
  | ApprovedMemory
  | ApprovedReviewResult
  | CaseContext
  | CaseContextLoadResult
  | ClaimDefinition
  | ClaimFinding
  | ClarificationRequest
  | ClarificationResume
  | CorrectedDecision
  | CorrectedDeclineDecision
  | CorrectedFullRefundDecision
  | DecisionRevisionEvent
  | DeclineEvidenceAssessment
  | DeclineFinalDecision
  | DeclineProposedDecision
  | DeclineProposedDecisionDraft
  | EditReviewDecision
  | EditedHumanReviewResult
  | EmptyRefundScope
  | EvidenceAssessment
  | EvidenceItem
  | EvidenceRequest
  | EvidenceResume
  | ExecuteRefundRequest
  | FailedVerificationResult
  | FetchHumanReviewParams
  | FetchHumanReviewRequest
  | FullRefundProposedDecision
  | FullRefundProposedDecisionDraft
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanEditedFullRefundFinalDecision
  | HumanRejectResolutionHandoff
  | HumanReviewDossier
  | HumanReviewPollResume
  | HumanReviewResult
  | HumanReviewReturnDecision
  | InsufficientEvidenceAssessment
  | IntakeResult
  | LoadCaseContextParams
  | LoadCaseContextRequest
  | MemoryCandidate
  | MemoryQuerySummary
  | MemoryScope
  | MemorySearchHit
  | MissingClaim
  | ModelJudgmentReturnDecision
  | NonEmptyRefundScope
  | OrderLineItem
  | OrderSnapshot
  | PassedVerificationResult
  | PolicyBundle
  | PolicyClause
  | PolicyReturnDecision
  | PolicyReturnDecisionDraft
  | ProposedDecision1
  | ProposedDecisionDraft
  | ProposedDecisionHandoff
  | QueryApprovedMemoryParams
  | QueryApprovedMemoryRequest
  | RefundApplicationResult
  | RefundExecutionRecord
  | RejectReviewDecision
  | RejectedHumanReviewResult
  | RejectedRefundApplicationResult
  | RejectedRefundExecutionRecord
  | RequiredReturnRequirement
  | ResolutionHandoff2
  | ResolveEvidenceParams
  | ResolveEvidenceRequest
  | ResolverConflictOutput
  | ResolverDraftOutput
  | ResolverEvidenceRequestOutput
  | ResolverOutput
  | ResumePayload
  | RetrievePolicyParams
  | RetrievePolicyRequest
  | ReviewDecision
  | ReviewGateResult
  | ReviewResult4
  | ReviewerApprovedResolutionHandoff
  | ReviewerGateConfig
  | RevisedReviewResult
  | RevisionConflictReport
  | RevisionReason
  | SubmitHumanReviewParams
  | SubmitHumanReviewRequest
  | SubmitMemoryCandidateParams
  | SubmitMemoryCandidateRequest
  | SucceededRefundExecutionRecord
  | UnavailableVerificationResult
  | UserTurn
  | VerificationIssue
  | VerificationResult
  | VerifyHandoffParams
  | VerifyHandoffRequest
  | WaivedReturnRequirement;
export type AgentCommand = AgentStartCommand | AgentResumeCommand;
export type CaseRef = string;
export type CommandId = string;
export type CommandType = "START";
export type IssuedAt = string;
export type AttachedArtifactRefs = string[];
export type ReceivedAt = string;
export type Role = "USER";
export type Text = string;
export type TurnId = string;
export type OrderRef = string;
export type SchemaVersion = "v1";
export type ThreadId = string;
export type CaseRef1 = string;
export type CommandId1 = string;
export type CommandType1 = "RESUME";
export type IssuedAt1 = string;
export type Resume = ClarificationResume | EvidenceResume | HumanReviewPollResume;
export type Kind = "CLARIFICATION";
/**
 * @minItems 1
 */
export type ArtifactRefs = [string, ...string[]];
export type Kind1 = "EVIDENCE_REQUEST";
export type Kind2 = "HUMAN_REVIEW";
export type SchemaVersion1 = "v1";
export type ThreadId1 = string;
export type Action = "FULL_REFUND";
export type Amount = string;
export type Currency = string;
export type ReasonCode =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @minItems 1
 */
export type LineItemIds = [string, ...string[]];
export type ReturnDecision = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type Requirement = RequiredReturnRequirement | WaivedReturnRequirement;
export type ReasonCode1 = "RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION";
export type Required = true;
export type ReasonCode2 =
  "ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN";
export type Required1 = false;
export type Source = "POLICY";
export type Requirement1 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source1 = "MODEL_JUDGMENT";
export type Payload = ClarificationResume | EvidenceResume | HumanReviewPollResume;
export type ThreadId2 = string;
export type CaseRef2 = string;
export type OrderRef1 = string | null;
export type ThreadId3 = string;
export type Categories = string[];
export type Markets = string[];
export type ReasonCodes = (
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND"
)[];
export type ApplicationRef = string;
export type AppliedAt = string;
export type Status = "APPLIED";
export type ExecutionRef = string;
export type ResolutionHandoff =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
export type CaseRef3 = string;
export type EmittedAt = string;
export type ExecutionBlocked = false;
export type FinalDecision = AgentFullRefundFinalDecision | DeclineFinalDecision;
export type Action1 = "DECLINE";
export type Amount1 = string;
export type Currency1 = string;
export type ReasonCode3 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @maxItems 0
 */
export type LineItemIds1 = [];
export type HandoffId = string;
export type OutcomeSource = "REVIEWER_APPROVE";
export type Amount2 = string;
export type ConfigHash = string;
export type ConfigVersion = string;
export type Currency2 = string;
export type Reason = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status1 = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
export type ReviewedAt = string;
/**
 * @minItems 1
 */
export type ReviewerClaimFindings = [ClaimFinding, ...ClaimFinding[]];
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
export type Explanation = string;
export type Status2 = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
export type Subject = string;
export type SupportingEvidenceRefs = string[];
export type ReviewerPromptVersion = string;
/**
 * @maxItems 0
 */
export type RevisionReasons = [];
export type Verdict = "APPROVE";
export type CaseRef4 = string;
export type EmittedAt1 = string;
export type ExecutionBlocked1 = false;
export type FinalDecision1 = AgentFullRefundFinalDecision | DeclineFinalDecision;
export type HandoffId1 = string;
export type OutcomeSource1 = "HUMAN_APPROVE";
export type ReviewResult = ApprovedReviewResult | RevisedReviewResult;
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
export type Code =
  | "EVIDENCE_INSUFFICIENT"
  | "POLICY_MISMATCH"
  | "DECISION_UNSUPPORTED"
  | "DECISION_INCONSISTENT"
  | "SCOPE_UNSUPPORTED"
  | "RETURN_REQUIREMENT_INCONSISTENT"
  | "HANDOFF_INCOMPLETE"
  | "OTHER";
export type EvidenceRefs = string[];
export type Message = string;
export type PolicyRefs = string[];
export type RequiredChange = string;
export type Subject1 = string;
export type Verdict1 = "REVISE";
export type CaseRef5 = string;
export type EmittedAt2 = string;
export type ExecutionBlocked2 = false;
export type FinalDecision2 = HumanEditedFullRefundFinalDecision | DeclineFinalDecision;
export type Action2 = "FULL_REFUND";
export type Amount3 = string;
export type Currency3 = string;
export type ReasonCode4 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type Requirement2 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source2 = "HUMAN_REVIEW";
export type HandoffId2 = string;
export type OutcomeSource2 = "HUMAN_EDIT";
export type ReviewResult1 = ApprovedReviewResult | RevisedReviewResult;
export type CaseRef6 = string;
export type EmittedAt3 = string;
export type ExecutionBlocked3 = false;
export type HandoffId3 = string;
export type OutcomeSource3 = "HUMAN_REJECT";
export type ReviewResult2 = ApprovedReviewResult | RevisedReviewResult;
/**
 * @minItems 1
 */
export type ClaimFindings = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion = string;
export type EvidenceStatus = "SUFFICIENT_FOR_APPROVAL";
export type Decision = "APPROVE";
export type Generalizable = boolean | null;
export type HandoffId4 = string | null;
export type ReviewNote = string;
export type ReviewerId = string;
export type Decision1 = "APPROVE";
export type FinalResolutionRef = string;
export type Generalizable1 = boolean | null;
export type ReviewNote1 = string;
export type ReviewedAt2 = string;
export type ReviewerId1 = string;
export type ApprovedAt = string;
export type ClaimRegistryVersion1 = string;
export type Confidence = number;
export type MemoryId = string;
export type PolicyVersion = string;
export type RecommendedBehavior = string;
export type RetrievalSummary = string;
export type Categories1 = string[];
export type ClaimIds = (
  | "DELIVERY_CONFIRMED"
  | "ORDER_WITHIN_RETURN_WINDOW"
  | "SHIPMENT_SEAL_INTACT"
  | "ITEM_PHYSICALLY_DAMAGED"
  | "DAMAGE_PRESENT_ON_ARRIVAL"
  | "ITEM_FUNCTIONALLY_IMPAIRED"
  | "ITEM_DIFFERS_FROM_LISTING"
  | "WRONG_ITEM_RECEIVED"
  | "ITEM_NOT_IN_SHIPMENT"
  | "ITEM_UNUSED"
)[];
export type Market = string;
export type ReasonCodes1 = (
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND"
)[];
export type Status3 = "APPROVED";
/**
 * @minItems 1
 */
export type TriggerConditions = [string, ...string[]];
export type CaseOpenedAt = string;
export type CaseRef7 = string;
export type Market1 = string;
export type OrderRef2 = string;
export type SnapshotVersion = number;
export type AlreadyRefundedAmount = string;
export type CapturedAt = string;
export type Currency4 = string;
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
export type OrderRef3 = string;
export type OrderSnapshotRef = string;
export type RefundableAmountMax = string;
export type SnapshotVersion1 = number;
export type AcceptedEvidenceTypes = ("IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT")[];
export type ClaimId1 =
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
export type Description = string;
export type DistinguishFrom = (
  | "DELIVERY_CONFIRMED"
  | "ORDER_WITHIN_RETURN_WINDOW"
  | "SHIPMENT_SEAL_INTACT"
  | "ITEM_PHYSICALLY_DAMAGED"
  | "DAMAGE_PRESENT_ON_ARRIVAL"
  | "ITEM_FUNCTIONALLY_IMPAIRED"
  | "ITEM_DIFFERS_FROM_LISTING"
  | "WRONG_ITEM_RECEIVED"
  | "ITEM_NOT_IN_SHIPMENT"
  | "ITEM_UNUSED"
)[];
export type ObservableRequirement = string;
export type SatisfiableBy = ("SYSTEM_FACTS" | "USER_EVIDENCE")[];
export type SubjectScope = "ORDER" | "LINE_ITEM";
export type ClarificationQuestion = string;
export type ClarificationRound = number;
/**
 * @minItems 1
 */
export type MissingFields = [string, ...string[]];
export type RequestId = string;
export type CorrectedDecision = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type Action3 = "FULL_REFUND";
export type Action4 = "DECLINE";
export type CaseRef8 = string;
export type CreatedAt = string;
export type EventId = string;
export type HandoffBeforeRef = string;
export type ReviewResult3 = ApprovedReviewResult | RevisedReviewResult;
export type RevisionRound = number;
/**
 * @minItems 1
 */
export type ClaimFindings1 = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion2 = string;
export type EvidenceStatus1 = "SUFFICIENT_FOR_DECLINE";
export type Action5 = "DECLINE";
export type Amount4 = string;
export type Currency5 = string;
export type EvidenceRefs1 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs1 = [string, ...string[]];
export type ReasonCode5 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type Action6 = "DECLINE";
export type EvidenceRefs2 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs2 = [string, ...string[]];
export type RationaleSummary = string;
export type ReasonCode6 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type CorrectedDecision1 = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type CorrectionReasonCode =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision2 = "EDIT";
export type Generalizable2 = boolean | null;
export type HandoffId5 = string | null;
export type ReviewNote2 = string;
export type ReviewerId2 = string;
export type CorrectedDecision2 = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type CorrectionReasonCode1 =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision3 = "EDIT";
export type FinalResolutionRef1 = string;
export type Generalizable3 = boolean | null;
export type ReviewNote3 = string;
export type ReviewedAt3 = string;
export type ReviewerId3 = string;
export type EvidenceAssessment =
  ApprovalEvidenceAssessment | DeclineEvidenceAssessment | InsufficientEvidenceAssessment;
/**
 * @minItems 1
 */
export type ClaimFindings2 = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion3 = string;
export type EvidenceStatus2 = "INSUFFICIENT";
/**
 * @minItems 1
 */
export type AcceptedEvidenceTypes1 = [
  "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT",
  ...("IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT")[]
];
/**
 * @minItems 1
 */
export type MissingClaims = [MissingClaim, ...MissingClaim[]];
export type ClaimId2 =
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
export type Subject2 = string;
/**
 * @minItems 1
 */
export type PolicyRefs3 = [string, ...string[]];
export type RequestId1 = string;
export type UserMessage = string;
export type ArtifactRef = string;
export type CollectedAt = string;
export type EvidenceId = string;
export type ExtractedSummary = string;
export type Source3 = "USER" | "ORDER_TOOL" | "LOGISTICS_TOOL" | "SYSTEM";
export type Subject3 = string;
export type Type = "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT";
export type ResolutionHandoff1 =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
/**
 * @minItems 1
 */
export type Issues = [VerificationIssue, ...VerificationIssue[]];
export type Code1 = string;
export type FieldPath = string;
export type Message1 = string;
export type Status4 = "FAIL";
export type VerificationVersion = string;
export type ReviewRef = string;
export type Method = "HumanReviewProvider.fetch_result";
export type Action7 = "FULL_REFUND";
export type Amount5 = string;
export type Currency6 = string;
export type EvidenceRefs3 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs4 = [string, ...string[]];
export type ReasonCode7 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReturnDecision1 = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type Action8 = "FULL_REFUND";
export type EvidenceRefs4 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs5 = [string, ...string[]];
export type RationaleSummary1 = string;
export type ReasonCode8 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReturnDecision2 = PolicyReturnDecisionDraft | ModelJudgmentReturnDecision;
export type ReasonCode9 =
  | ("RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION")
  | ("ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN");
export type Source4 = "POLICY";
export type ClaimRegistryVersion4 = string;
/**
 * @minItems 1
 */
export type ClaimedLineItemIds = [string, ...string[]];
/**
 * @minItems 1
 */
export type AllowedActions = ["FULL_REFUND" | "DECLINE", ...("FULL_REFUND" | "DECLINE")[]];
export type ClauseId = string;
export type EffectiveFrom = string;
export type EffectiveTo = string | null;
export type PolicyVersion1 = string;
/**
 * @minItems 1
 */
export type RequiredClaimIds = [
  (
    | "DELIVERY_CONFIRMED"
    | "ORDER_WITHIN_RETURN_WINDOW"
    | "SHIPMENT_SEAL_INTACT"
    | "ITEM_PHYSICALLY_DAMAGED"
    | "DAMAGE_PRESENT_ON_ARRIVAL"
    | "ITEM_FUNCTIONALLY_IMPAIRED"
    | "ITEM_DIFFERS_FROM_LISTING"
    | "WRONG_ITEM_RECEIVED"
    | "ITEM_NOT_IN_SHIPMENT"
    | "ITEM_UNUSED"
  ),
  ...(
    | "DELIVERY_CONFIRMED"
    | "ORDER_WITHIN_RETURN_WINDOW"
    | "SHIPMENT_SEAL_INTACT"
    | "ITEM_PHYSICALLY_DAMAGED"
    | "DAMAGE_PRESENT_ON_ARRIVAL"
    | "ITEM_FUNCTIONALLY_IMPAIRED"
    | "ITEM_DIFFERS_FROM_LISTING"
    | "WRONG_ITEM_RECEIVED"
    | "ITEM_NOT_IN_SHIPMENT"
    | "ITEM_UNUSED"
  )[]
];
export type ReturnPolicy = "REQUIRED" | "NOT_REQUIRED" | "MODEL_JUDGMENT";
export type Text1 = string;
export type Clauses = PolicyClause[];
export type PolicyBundleVersion = string;
export type RetrievalStatus = "OK" | "NOT_FOUND" | "AMBIGUOUS";
export type RetrievedAt = string;
/**
 * @minItems 1
 */
export type ProposalHistory = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type AgentPromptVersion = string;
export type CaseRef9 = string;
export type ClaimRegistryVersion5 = string;
export type EvidenceBundle = EvidenceItem[];
export type HandoffId6 = string;
export type HandoffVersion = "1.0";
export type OrderSnapshotRef1 = string;
export type PolicyBundleVersion1 = string;
/**
 * @minItems 1
 */
export type PolicyRefs6 = [string, ...string[]];
export type ProposedDecision = FullRefundProposedDecision | DeclineProposedDecision;
export type RationaleSummary2 = string;
export type RevisionRound1 = number;
/**
 * @minItems 1
 */
export type ReviewHistory = [
  ApprovedReviewResult | RevisedReviewResult,
  ...(ApprovedReviewResult | RevisedReviewResult)[]
];
export type RevisionEvents = DecisionRevisionEvent[];
export type RoutingReason = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type HumanReviewResult = ApprovedHumanReviewResult | RejectedHumanReviewResult | EditedHumanReviewResult;
export type Decision4 = "REJECT";
export type FinalResolutionRef2 = string;
export type Generalizable4 = boolean | null;
export type ReviewNote4 = string;
export type ReviewedAt4 = string;
export type ReviewerId4 = string;
export type ClaimedLineItemIds1 = string[];
export type ClarificationQuestion1 = string | null;
export type Completeness = "COMPLETE" | "INCOMPLETE";
export type MissingFields1 = string[];
export type OrderRef4 = string | null;
export type ReasonCode10 =
  ("ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND") | null;
export type ReasonSummary = string | null;
export type RequestedAction = "REFUND" | "RETURN_AND_REFUND" | "EXCHANGE" | "UNSPECIFIED";
export type CaseRef10 = string;
export type Method1 = "CaseContextProvider.load_case_context";
export type ClaimRegistryVersion6 = string;
export type Confidence1 = number;
export type MemoryId1 = string;
export type PolicyVersion2 = string;
export type Rationale = string;
export type RecommendedBehavior1 = string;
export type RetrievalSummary1 = string;
/**
 * @minItems 1
 */
export type SourceCaseRefs = [string, ...string[]];
/**
 * @minItems 1
 */
export type SourceRevisionEventRefs = [string, ...string[]];
export type Status5 = "CANDIDATE";
/**
 * @minItems 1
 */
export type TriggerConditions1 = [string, ...string[]];
export type QuerySummary = string;
export type Similarity = number;
/**
 * @maxItems 0
 */
export type Issues1 = [];
export type Status6 = "PASS";
export type VerificationVersion1 = string;
export type ProposedDecision1 = FullRefundProposedDecision | DeclineProposedDecision;
export type ProposedDecisionDraft = FullRefundProposedDecisionDraft | DeclineProposedDecisionDraft;
export type Categories2 = string[];
export type ClaimRegistryMajor = number;
export type Market2 = string;
/**
 * @minItems 1
 */
export type PolicyVersions = [string, ...string[]];
export type QuerySummary1 = string;
export type ReasonCode11 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @minItems 1
 */
export type RequiredClaimIds1 = [
  (
    | "DELIVERY_CONFIRMED"
    | "ORDER_WITHIN_RETURN_WINDOW"
    | "SHIPMENT_SEAL_INTACT"
    | "ITEM_PHYSICALLY_DAMAGED"
    | "DAMAGE_PRESENT_ON_ARRIVAL"
    | "ITEM_FUNCTIONALLY_IMPAIRED"
    | "ITEM_DIFFERS_FROM_LISTING"
    | "WRONG_ITEM_RECEIVED"
    | "ITEM_NOT_IN_SHIPMENT"
    | "ITEM_UNUSED"
  ),
  ...(
    | "DELIVERY_CONFIRMED"
    | "ORDER_WITHIN_RETURN_WINDOW"
    | "SHIPMENT_SEAL_INTACT"
    | "ITEM_PHYSICALLY_DAMAGED"
    | "DAMAGE_PRESENT_ON_ARRIVAL"
    | "ITEM_FUNCTIONALLY_IMPAIRED"
    | "ITEM_DIFFERS_FROM_LISTING"
    | "WRONG_ITEM_RECEIVED"
    | "ITEM_NOT_IN_SHIPMENT"
    | "ITEM_UNUSED"
  )[]
];
export type TopK = number;
export type Method2 = "OperationalMemoryStore.query_approved";
export type RefundApplicationResult = AppliedRefundApplicationResult | RejectedRefundApplicationResult;
/**
 * @minItems 1
 */
export type ReasonCodes2 = [string, ...string[]];
export type RejectedAt = string;
export type Status7 = "REJECTED";
export type RefundExecutionRecord = SucceededRefundExecutionRecord | RejectedRefundExecutionRecord;
export type CaseRef11 = string;
export type CreatedAt1 = string;
export type ExecutionRef1 = string;
export type HandoffId7 = string;
export type Status8 = "SUCCEEDED";
export type UpdatedAt = string;
export type CaseRef12 = string;
export type CreatedAt2 = string;
export type ExecutionRef2 = string;
export type HandoffId8 = string;
export type Status9 = "REJECTED";
export type UpdatedAt1 = string;
export type Decision5 = "REJECT";
export type Generalizable5 = boolean | null;
export type HandoffId9 = string | null;
export type ReviewNote5 = string;
export type ReviewerId5 = string;
export type ResolutionHandoff2 =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
export type ArtifactRef1 = string;
export type Method3 = "EvidenceProvider.resolve";
/**
 * @minItems 2
 */
export type ConflictingReasonCodes = [
  (
    | "EVIDENCE_INSUFFICIENT"
    | "POLICY_MISMATCH"
    | "DECISION_UNSUPPORTED"
    | "DECISION_INCONSISTENT"
    | "SCOPE_UNSUPPORTED"
    | "RETURN_REQUIREMENT_INCONSISTENT"
    | "HANDOFF_INCOMPLETE"
    | "OTHER"
  ),
  (
    | "EVIDENCE_INSUFFICIENT"
    | "POLICY_MISMATCH"
    | "DECISION_UNSUPPORTED"
    | "DECISION_INCONSISTENT"
    | "SCOPE_UNSUPPORTED"
    | "RETURN_REQUIREMENT_INCONSISTENT"
    | "HANDOFF_INCOMPLETE"
    | "OTHER"
  ),
  ...(
    | "EVIDENCE_INSUFFICIENT"
    | "POLICY_MISMATCH"
    | "DECISION_UNSUPPORTED"
    | "DECISION_INCONSISTENT"
    | "SCOPE_UNSUPPORTED"
    | "RETURN_REQUIREMENT_INCONSISTENT"
    | "HANDOFF_INCOMPLETE"
    | "OTHER"
  )[]
];
/**
 * @minItems 2
 */
export type ConflictingReviewRefs = [string, string, ...string[]];
export type Explanation1 = string;
export type ResultType = "CONFLICTING_REVISIONS";
export type Draft = FullRefundProposedDecisionDraft | DeclineProposedDecisionDraft;
export type ResultType1 = "DRAFT";
export type ResultType2 = "REQUEST_EVIDENCE";
export type ResolverOutput = ResolverDraftOutput | ResolverEvidenceRequestOutput | ResolverConflictOutput;
export type ResumePayload = ClarificationResume | EvidenceResume | HumanReviewPollResume;
/**
 * @minItems 1
 */
export type ClaimedLineItemIds2 = [string, ...string[]];
export type ReasonCode12 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type Method4 = "PolicyProvider.retrieve_policy";
export type ReviewDecision = ApproveReviewDecision | RejectReviewDecision | EditReviewDecision;
export type ReviewResult4 = ApprovedReviewResult | RevisedReviewResult;
export type Version = string;
export type Review = ApprovedReviewResult | RevisedReviewResult;
export type Method5 = "HumanReviewProvider.submit_for_review";
export type Method6 = "OperationalMemoryStore.submit_candidate";
/**
 * @maxItems 0
 */
export type Issues2 = [];
export type Status10 = "UNAVAILABLE";
export type VerificationVersion2 = string;
export type AttachedArtifactRefs1 = string[];
export type ReceivedAt1 = string;
export type Role1 = "USER" | "AGENT";
export type Text2 = string;
export type TurnId1 = string;
export type VerificationResult = PassedVerificationResult | FailedVerificationResult | UnavailableVerificationResult;
export type Method7 = "VerificationProvider.verify";

export interface AgentStartCommand {
  case_ref: CaseRef;
  command_id: CommandId;
  command_type: CommandType;
  issued_at: IssuedAt;
  payload: AgentStartPayload;
  schema_version?: SchemaVersion;
  thread_id: ThreadId;
}
export interface AgentStartPayload {
  initial_turn: AgentUserTurn;
  order_ref: OrderRef;
}
export interface AgentUserTurn {
  attached_artifact_refs?: AttachedArtifactRefs;
  received_at: ReceivedAt;
  role: Role;
  text: Text;
  turn_id: TurnId;
}
export interface AgentResumeCommand {
  case_ref: CaseRef1;
  command_id: CommandId1;
  command_type: CommandType1;
  issued_at: IssuedAt1;
  payload: AgentResumePayload;
  schema_version?: SchemaVersion1;
  thread_id: ThreadId1;
}
export interface AgentResumePayload {
  resume: Resume;
}
export interface ClarificationResume {
  kind: Kind;
  turn: AgentUserTurn;
}
export interface EvidenceResume {
  artifact_refs: ArtifactRefs;
  kind: Kind1;
}
export interface HumanReviewPollResume {
  kind: Kind2;
}
export interface AgentFullRefundFinalDecision {
  action: Action;
  amount: Amount;
  currency: Currency;
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
  reason_code: ReasonCode1;
  required: Required;
}
export interface WaivedReturnRequirement {
  reason_code: ReasonCode2;
  required: Required1;
}
export interface ModelJudgmentReturnDecision {
  requirement: Requirement1;
  source: Source1;
}
export interface AgentResumeRequest {
  payload: Payload;
  thread_id: ThreadId2;
}
export interface AgentStartRequest {
  case_ref: CaseRef2;
  initial_turn: AgentUserTurn;
  order_ref?: OrderRef1;
  thread_id: ThreadId3;
}
export interface ApplicableConditions {
  categories?: Categories;
  markets?: Markets;
  reason_codes?: ReasonCodes;
}
export interface AppliedRefundApplicationResult {
  application_ref: ApplicationRef;
  applied_at: AppliedAt;
  status: Status;
}
export interface ApplyRefundRequest {
  execution_ref: ExecutionRef;
  resolution_handoff: ResolutionHandoff;
}
export interface ReviewerApprovedResolutionHandoff {
  case_ref: CaseRef3;
  emitted_at: EmittedAt;
  execution_blocked: ExecutionBlocked;
  final_decision: FinalDecision;
  handoff_id: HandoffId;
  outcome_source: OutcomeSource;
  review_gate?: ReviewGateResult | null;
  review_result: ApprovedReviewResult;
}
export interface DeclineFinalDecision {
  action: Action1;
  amount: Amount1;
  currency: Currency1;
  reason_code: ReasonCode3;
  refund_scope: EmptyRefundScope;
}
export interface EmptyRefundScope {
  line_item_ids: LineItemIds1;
}
export interface ReviewGateResult {
  amount: Amount2;
  config_hash: ConfigHash;
  config_version: ConfigVersion;
  currency: Currency2;
  reason: Reason;
  status: Status1;
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
  status: Status2;
  subject: Subject;
  supporting_evidence_refs?: SupportingEvidenceRefs;
}
export interface HumanApproveResolutionHandoff {
  case_ref: CaseRef4;
  emitted_at: EmittedAt1;
  execution_blocked: ExecutionBlocked1;
  final_decision: FinalDecision1;
  handoff_id: HandoffId1;
  outcome_source: OutcomeSource1;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult;
}
export interface RevisedReviewResult {
  reviewed_at: ReviewedAt1;
  reviewer_claim_findings: ReviewerClaimFindings1;
  reviewer_prompt_version: ReviewerPromptVersion1;
  revision_reasons: RevisionReasons1;
  verdict: Verdict1;
}
export interface RevisionReason {
  code: Code;
  evidence_refs?: EvidenceRefs;
  message: Message;
  policy_refs?: PolicyRefs;
  required_change: RequiredChange;
  subject: Subject1;
}
export interface HumanEditResolutionHandoff {
  case_ref: CaseRef5;
  emitted_at: EmittedAt2;
  execution_blocked: ExecutionBlocked2;
  final_decision: FinalDecision2;
  handoff_id: HandoffId2;
  outcome_source: OutcomeSource2;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult1;
}
export interface HumanEditedFullRefundFinalDecision {
  action: Action2;
  amount: Amount3;
  currency: Currency3;
  reason_code: ReasonCode4;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface HumanReviewReturnDecision {
  requirement: Requirement2;
  source: Source2;
}
export interface HumanRejectResolutionHandoff {
  case_ref: CaseRef6;
  emitted_at: EmittedAt3;
  execution_blocked: ExecutionBlocked3;
  final_decision: DeclineFinalDecision;
  handoff_id: HandoffId3;
  outcome_source: OutcomeSource3;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult2;
}
export interface ApprovalEvidenceAssessment {
  claim_findings: ClaimFindings;
  claim_registry_version: ClaimRegistryVersion;
  evidence_status: EvidenceStatus;
}
export interface ApproveReviewDecision {
  decision: Decision;
  generalizable?: Generalizable;
  handoff_id?: HandoffId4;
  review_note: ReviewNote;
  reviewer_id?: ReviewerId;
}
export interface ApprovedHumanReviewResult {
  decision: Decision1;
  final_resolution_ref: FinalResolutionRef;
  generalizable?: Generalizable1;
  review_note: ReviewNote1;
  reviewed_at: ReviewedAt2;
  reviewer_id?: ReviewerId1;
}
export interface ApprovedMemory {
  approved_at: ApprovedAt;
  claim_registry_version: ClaimRegistryVersion1;
  confidence: Confidence;
  memory_id: MemoryId;
  policy_version: PolicyVersion;
  recommended_behavior: RecommendedBehavior;
  retrieval_summary: RetrievalSummary;
  scope: MemoryScope;
  status: Status3;
  trigger_conditions: TriggerConditions;
}
export interface MemoryScope {
  categories?: Categories1;
  claim_ids?: ClaimIds;
  market: Market;
  reason_codes?: ReasonCodes1;
}
export interface CaseContext {
  case_opened_at: CaseOpenedAt;
  case_ref: CaseRef7;
  market: Market1;
  order_ref: OrderRef2;
  snapshot_version: SnapshotVersion;
}
export interface CaseContextLoadResult {
  case_context: CaseContext;
  order_snapshot: OrderSnapshot;
}
export interface OrderSnapshot {
  already_refunded_amount: AlreadyRefundedAmount;
  captured_at: CapturedAt;
  currency: Currency4;
  delivered_at: DeliveredAt;
  line_items: LineItems;
  order_ref: OrderRef3;
  order_snapshot_ref: OrderSnapshotRef;
  refundable_amount_max: RefundableAmountMax;
  snapshot_version: SnapshotVersion1;
}
export interface OrderLineItem {
  category_ref: CategoryRef;
  line_item_id: LineItemId;
  quantity: Quantity;
  refundable_amount: RefundableAmount;
  sku_ref: SkuRef;
  title: Title;
}
export interface ClaimDefinition {
  accepted_evidence_types?: AcceptedEvidenceTypes;
  claim_id: ClaimId1;
  description: Description;
  distinguish_from?: DistinguishFrom;
  observable_requirement: ObservableRequirement;
  satisfiable_by: SatisfiableBy;
  subject_scope: SubjectScope;
}
export interface ClarificationRequest {
  clarification_question: ClarificationQuestion;
  clarification_round: ClarificationRound;
  missing_fields: MissingFields;
  request_id: RequestId;
}
export interface CorrectedFullRefundDecision {
  action: Action3;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface CorrectedDeclineDecision {
  action: Action4;
  refund_scope: EmptyRefundScope;
}
export interface DecisionRevisionEvent {
  case_ref: CaseRef8;
  created_at: CreatedAt;
  event_id: EventId;
  handoff_before_ref: HandoffBeforeRef;
  review_result: ReviewResult3;
  revision_round: RevisionRound;
}
export interface DeclineEvidenceAssessment {
  claim_findings: ClaimFindings1;
  claim_registry_version: ClaimRegistryVersion2;
  evidence_status: EvidenceStatus1;
}
export interface DeclineProposedDecision {
  action: Action5;
  amount: Amount4;
  currency: Currency5;
  evidence_refs?: EvidenceRefs1;
  policy_refs: PolicyRefs1;
  reason_code: ReasonCode5;
  refund_scope: EmptyRefundScope;
}
export interface DeclineProposedDecisionDraft {
  action: Action6;
  evidence_refs?: EvidenceRefs2;
  policy_refs: PolicyRefs2;
  rationale_summary: RationaleSummary;
  reason_code: ReasonCode6;
  refund_scope: EmptyRefundScope;
}
export interface EditReviewDecision {
  corrected_decision: CorrectedDecision1;
  correction_reason_code: CorrectionReasonCode;
  decision: Decision2;
  generalizable?: Generalizable2;
  handoff_id?: HandoffId5;
  review_note: ReviewNote2;
  reviewer_id?: ReviewerId2;
}
export interface EditedHumanReviewResult {
  corrected_decision: CorrectedDecision2;
  correction_reason_code: CorrectionReasonCode1;
  decision: Decision3;
  final_resolution_ref: FinalResolutionRef1;
  generalizable?: Generalizable3;
  review_note: ReviewNote3;
  reviewed_at: ReviewedAt3;
  reviewer_id?: ReviewerId3;
}
export interface InsufficientEvidenceAssessment {
  claim_findings: ClaimFindings2;
  claim_registry_version: ClaimRegistryVersion3;
  evidence_status: EvidenceStatus2;
  missing_evidence_request: EvidenceRequest;
}
export interface EvidenceRequest {
  accepted_evidence_types: AcceptedEvidenceTypes1;
  missing_claims: MissingClaims;
  policy_refs: PolicyRefs3;
  request_id: RequestId1;
  user_message: UserMessage;
}
export interface MissingClaim {
  claim_id: ClaimId2;
  subject: Subject2;
}
export interface EvidenceItem {
  artifact_ref: ArtifactRef;
  collected_at: CollectedAt;
  evidence_id: EvidenceId;
  extracted_summary: ExtractedSummary;
  source: Source3;
  subject: Subject3;
  type: Type;
}
export interface ExecuteRefundRequest {
  resolution_handoff: ResolutionHandoff1;
}
export interface FailedVerificationResult {
  issues: Issues;
  status: Status4;
  verification_version: VerificationVersion;
}
export interface VerificationIssue {
  code: Code1;
  field_path: FieldPath;
  message: Message1;
}
export interface FetchHumanReviewParams {
  review_ref: ReviewRef;
}
export interface FetchHumanReviewRequest {
  method: Method;
  params: FetchHumanReviewParams;
}
export interface FullRefundProposedDecision {
  action: Action7;
  amount: Amount5;
  currency: Currency6;
  evidence_refs?: EvidenceRefs3;
  policy_refs: PolicyRefs4;
  reason_code: ReasonCode7;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision1;
}
export interface FullRefundProposedDecisionDraft {
  action: Action8;
  evidence_refs?: EvidenceRefs4;
  policy_refs: PolicyRefs5;
  rationale_summary: RationaleSummary1;
  reason_code: ReasonCode8;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision2;
}
export interface PolicyReturnDecisionDraft {
  reason_code: ReasonCode9;
  source: Source4;
}
export interface HumanReviewDossier {
  claim_registry_version: ClaimRegistryVersion4;
  claimed_line_item_ids: ClaimedLineItemIds;
  order_snapshot: OrderSnapshot;
  policy_bundle: PolicyBundle;
  proposal_history: ProposalHistory;
  review_gate?: ReviewGateResult | null;
  review_history: ReviewHistory;
  revision_events?: RevisionEvents;
  routing_reason?: RoutingReason;
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
export interface ProposedDecisionHandoff {
  agent_prompt_version: AgentPromptVersion;
  case_ref: CaseRef9;
  claim_registry_version: ClaimRegistryVersion5;
  evidence_bundle?: EvidenceBundle;
  handoff_id: HandoffId6;
  handoff_version: HandoffVersion;
  order_snapshot_ref: OrderSnapshotRef1;
  policy_bundle_version: PolicyBundleVersion1;
  policy_refs: PolicyRefs6;
  proposed_decision: ProposedDecision;
  rationale_summary: RationaleSummary2;
  revision_round: RevisionRound1;
}
export interface RejectedHumanReviewResult {
  decision: Decision4;
  final_resolution_ref: FinalResolutionRef2;
  generalizable?: Generalizable4;
  review_note: ReviewNote4;
  reviewed_at: ReviewedAt4;
  reviewer_id?: ReviewerId4;
}
export interface IntakeResult {
  claimed_line_item_ids?: ClaimedLineItemIds1;
  clarification_question?: ClarificationQuestion1;
  completeness: Completeness;
  missing_fields?: MissingFields1;
  order_ref?: OrderRef4;
  reason_code?: ReasonCode10;
  reason_summary?: ReasonSummary;
  requested_action: RequestedAction;
}
export interface LoadCaseContextParams {
  case_ref: CaseRef10;
}
export interface LoadCaseContextRequest {
  method: Method1;
  params: LoadCaseContextParams;
}
export interface MemoryCandidate {
  claim_registry_version: ClaimRegistryVersion6;
  confidence: Confidence1;
  memory_id: MemoryId1;
  policy_version: PolicyVersion2;
  rationale: Rationale;
  recommended_behavior: RecommendedBehavior1;
  retrieval_summary: RetrievalSummary1;
  scope: MemoryScope;
  source_case_refs: SourceCaseRefs;
  source_revision_event_refs: SourceRevisionEventRefs;
  status: Status5;
  trigger_conditions: TriggerConditions1;
}
export interface MemoryQuerySummary {
  query_summary: QuerySummary;
}
export interface MemorySearchHit {
  memory: ApprovedMemory;
  similarity: Similarity;
}
export interface PassedVerificationResult {
  issues?: Issues1;
  status: Status6;
  verification_version: VerificationVersion1;
}
export interface QueryApprovedMemoryParams {
  categories?: Categories2;
  claim_registry_major: ClaimRegistryMajor;
  market: Market2;
  policy_versions: PolicyVersions;
  query_summary: QuerySummary1;
  reason_code: ReasonCode11;
  required_claim_ids: RequiredClaimIds1;
  top_k?: TopK;
}
export interface QueryApprovedMemoryRequest {
  method: Method2;
  params: QueryApprovedMemoryParams;
}
export interface RejectedRefundApplicationResult {
  reason_codes: ReasonCodes2;
  rejected_at: RejectedAt;
  status: Status7;
}
export interface SucceededRefundExecutionRecord {
  application_result: AppliedRefundApplicationResult;
  case_ref: CaseRef11;
  created_at: CreatedAt1;
  execution_ref: ExecutionRef1;
  handoff_id: HandoffId7;
  status: Status8;
  updated_at: UpdatedAt;
}
export interface RejectedRefundExecutionRecord {
  application_result: RejectedRefundApplicationResult;
  case_ref: CaseRef12;
  created_at: CreatedAt2;
  execution_ref: ExecutionRef2;
  handoff_id: HandoffId8;
  status: Status9;
  updated_at: UpdatedAt1;
}
export interface RejectReviewDecision {
  decision: Decision5;
  generalizable?: Generalizable5;
  handoff_id?: HandoffId9;
  review_note: ReviewNote5;
  reviewer_id?: ReviewerId5;
}
export interface ResolveEvidenceParams {
  artifact_ref: ArtifactRef1;
}
export interface ResolveEvidenceRequest {
  method: Method3;
  params: ResolveEvidenceParams;
}
export interface ResolverConflictOutput {
  conflict: RevisionConflictReport;
  result_type: ResultType;
}
export interface RevisionConflictReport {
  conflicting_reason_codes: ConflictingReasonCodes;
  conflicting_review_refs: ConflictingReviewRefs;
  explanation: Explanation1;
}
export interface ResolverDraftOutput {
  draft: Draft;
  result_type: ResultType1;
}
export interface ResolverEvidenceRequestOutput {
  evidence_request: EvidenceRequest;
  result_type: ResultType2;
}
export interface RetrievePolicyParams {
  case_context: CaseContext;
  claimed_line_item_ids: ClaimedLineItemIds2;
  order_snapshot: OrderSnapshot;
  reason_code: ReasonCode12;
}
export interface RetrievePolicyRequest {
  method: Method4;
  params: RetrievePolicyParams;
}
export interface ReviewerGateConfig {
  thresholds?: Thresholds;
  version?: Version;
}
export interface Thresholds {
  /**
   * This interface was referenced by `Thresholds`'s JSON-Schema definition
   * via the `patternProperty` "^[A-Z]{3}$".
   */
  [k: string]: string;
}
export interface SubmitHumanReviewParams {
  dossier?: HumanReviewDossier | null;
  handoff: ProposedDecisionHandoff;
  review: Review;
}
export interface SubmitHumanReviewRequest {
  method: Method5;
  params: SubmitHumanReviewParams;
}
export interface SubmitMemoryCandidateParams {
  candidate: MemoryCandidate;
}
export interface SubmitMemoryCandidateRequest {
  method: Method6;
  params: SubmitMemoryCandidateParams;
}
export interface UnavailableVerificationResult {
  issues?: Issues2;
  status: Status10;
  verification_version: VerificationVersion2;
}
export interface UserTurn {
  attached_artifact_refs?: AttachedArtifactRefs1;
  received_at: ReceivedAt1;
  role: Role1;
  text: Text2;
  turn_id: TurnId1;
}
export interface VerifyHandoffParams {
  handoff: ProposedDecisionHandoff;
}
export interface VerifyHandoffRequest {
  method: Method7;
  params: VerifyHandoffParams;
}
