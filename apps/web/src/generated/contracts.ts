/* Generated from this project's Pydantic contracts. Run npm run contracts. */

export type Contracts =
  | AccumulatedEscalationContext
  | ActivityEmission
  | ActivityEvent
  | ActivityFacts
  | ActivityFinding
  | ActivityInputs
  | ActivityPage
  | ActivityPayload
  | AgentCommand
  | AgentEscalatedEvent
  | AgentEscalatedPayload
  | AgentEvent
  | AgentFullRefundFinalDecision
  | AgentInterruptedEvent
  | AgentInterruptedPayload
  | AgentNodeObservedEvent
  | AgentNodeObservedPayload
  | AgentResolvedEvent
  | AgentResolvedPayload
  | AgentResumeCommand
  | AgentResumePayload
  | AgentResumeRequest
  | AgentRunFailedEvent
  | AgentRunFailedPayload
  | AgentRunResult
  | AgentServiceEvent
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
  | BackgroundStatus
  | CaseContext
  | CaseContextLoadResult
  | CaseDetail
  | ClaimDefinition
  | ClaimFinding
  | ClarificationInterruptPayload
  | ClarificationRequest
  | ClarificationResume
  | CorrectedDecision1
  | CorrectedDeclineDecision
  | CorrectedFullRefundDecision
  | CreateCaseRequest
  | CreateCaseResponse
  | DecisionRevisionEvent
  | DeclineEvidenceAssessment
  | DeclineFinalDecision
  | DeclineHumanReviewPayload
  | DeclineProposedDecision
  | DeclineProposedDecisionDraft
  | DoneEvent
  | DonePayload
  | EditReviewDecision
  | EditedHumanReviewResult
  | EmptyRefundScope
  | ErrorEvent
  | ErrorPayload
  | EvidenceAssessment
  | EvidenceDisplayRef
  | EvidenceInterruptPayload
  | EvidenceItem
  | EvidenceRequest
  | EvidenceRequestView
  | EvidenceResume
  | ExecuteRefundRequest
  | FailedVerificationResult
  | FetchHumanReviewParams
  | FetchHumanReviewRequest
  | FullRefundHumanReviewPayload
  | FullRefundProposedDecision
  | FullRefundProposedDecisionDraft
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanEditedFullRefundFinalDecision
  | HumanRejectResolutionHandoff
  | HumanReviewDossier
  | HumanReviewInterruptPayload
  | HumanReviewPayload
  | HumanReviewPollResume
  | HumanReviewResult1
  | HumanReviewReturnDecision
  | InsufficientEvidenceAssessment
  | IntakeResult
  | InterruptEvent
  | InterruptPayload1
  | InterruptedAgentRunResult
  | Lifecycle
  | LoadCaseContextParams
  | LoadCaseContextRequest
  | ManualEscalationAgentRunResult
  | ManualEscalationHandoff
  | MemoryCandidate
  | MemoryCandidateCompletedPayload
  | MemoryCandidateOutput
  | MemoryDistillationCompletedEvent
  | MemoryDistillationFailedEvent
  | MemoryDistillationFailedPayload
  | MemoryDistillationInput
  | MemoryDistillationJob
  | MemoryDistillationJobPayload
  | MemoryDistillationOutput
  | MemoryQuerySummary
  | MemoryRetrievalEvent
  | MemoryRetrievalObservation
  | MemoryScope
  | MemorySearchHit
  | MemoryServiceEvent
  | MemorySkipCompletedPayload
  | MemorySkipOutput
  | MissingClaim
  | ModelJudgmentReturnDecision
  | Narration
  | NarrationJob
  | NarrationText
  | NodeEnterEvent
  | NodeExecutionObservation
  | NodeExitEvent
  | NodeLifecyclePayload
  | NodeSummary
  | NonEmptyRefundScope
  | OrderLineItem
  | OrderSnapshot
  | PassedVerificationResult
  | PolicyBundle
  | PolicyClause
  | PolicyDisplayRef
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
  | ResolutionAgentRunResult
  | ResolutionHandoff3
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
  | ReviewResult7
  | ReviewerApprovedResolutionHandoff
  | ReviewerGateConfig
  | RevisedReviewResult
  | RevisionConflictReport
  | RevisionReason
  | SendMessageRequest
  | StateChangeEvent
  | StateChangePayload
  | SubmitHumanReviewParams
  | SubmitHumanReviewRequest
  | SubmitMemoryCandidateParams
  | SubmitMemoryCandidateRequest
  | SucceededRefundExecutionRecord
  | TokenEvent
  | TokenPayload
  | ToolCallEvent
  | ToolCallPayload
  | ToolResultEvent
  | ToolResultPayload
  | UiClarificationInterruptPayload
  | UiEvidenceInterruptPayload
  | UiHumanReviewInterruptPayload
  | UiInterruptPayload
  | UnavailableVerificationResult
  | UserTurn
  | VerificationIssue
  | VerificationResult
  | VerifyHandoffParams
  | VerifyHandoffRequest
  | WaivedReturnRequirement;
export type ClarificationRound = number;
export type EvidenceRound = number;
export type ReviewHistoryRefs = string[];
export type RevisionRound = number;
export type Code = string;
export type FieldPath = string;
export type Message = string;
export type VerificationIssues = VerificationIssue[];
export type VerificationRound = number;
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
export type Status = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
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
export type RevisionRound1 = number | null;
export type Verdict = ("APPROVE" | "REVISE") | null;
export type ArgumentCount = number;
export type ReasonCode =
  ("ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND") | null;
/**
 * @maxItems 30
 */
export type RequiredClaimIds = (
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
export type TopK = number | null;
export type Model = string | null;
export type Name = string;
export type Phase = "STARTED" | "COMPLETED" | "PAUSED" | "FAILED";
export type Type = "node" | "model" | "tool";
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
export type Status1 = "APPROVED";
/**
 * @minItems 1
 */
export type TriggerConditions = [string, ...string[]];
export type Similarity = number;
export type QuerySummary = string | null;
export type Status2 = "OK" | "UNAVAILABLE";
export type Amount = string;
export type ConfigHash = string;
export type ConfigVersion = string;
export type Currency = string;
export type Reason = ("HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED") | null;
export type Status3 = "PASS" | "HUMAN_REQUIRED" | "NOT_APPLICABLE";
export type Threshold = string | null;
export type Type1 = "node_summary";
export type ErrorCode2 = string | null;
export type SourceEventId = string;
export type Status4 = "COMPLETED" | "UNAVAILABLE";
export type Text = string | null;
export type Type2 = "narration";
export type ErrorCode3 = string | null;
export type Status5 = "SCHEDULED" | "STARTED" | "RETRYING" | "COMPLETED" | "SKIPPED" | "FAILED";
export type Type3 = "background";
export type RunId = string;
export type SchemaVersion = "1.0";
export type Scope = "CASE" | "REFUND" | "MEMORY";
export type AttemptId1 = string;
export type CaseRef1 = string;
export type EventId1 = string;
export type JobId1 = string | null;
export type Node1 = string;
export type OccurredAt1 = string;
export type OperationId1 = string;
export type ParentOperationId1 = string | null;
export type Payload1 = Lifecycle | NodeSummary | Narration | BackgroundStatus;
export type RunId1 = string;
export type SchemaVersion1 = "1.0";
export type Scope1 = "CASE" | "REFUND" | "MEMORY";
export type Seq = number;
export type Events = ActivityEvent[];
export type HasMore = boolean;
export type NextCursor = number;
export type ActivityPayload = Lifecycle | NodeSummary | Narration | BackgroundStatus;
export type AgentCommand = AgentStartCommand | AgentResumeCommand;
export type CaseRef2 = string;
export type CommandId = string;
export type CommandType = "START";
export type IssuedAt = string;
export type AttachedArtifactRefs = string[];
export type ReceivedAt = string;
export type Role = "USER";
export type Text1 = string;
export type TurnId = string;
export type OrderRef = string;
export type SchemaVersion2 = "v1";
export type ThreadId = string;
export type CaseRef3 = string;
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
export type SchemaVersion3 = "v1";
export type ThreadId1 = string;
export type CaseRef4 = string;
export type CommandId2 = string;
export type EventId2 = string;
export type EventIndex = number;
export type EventType = "ESCALATED";
export type OccurredAt2 = string;
export type CaseRef5 = string;
export type CreatedAt = string;
export type EscalationReason =
  | "CLARIFICATION_BUDGET_EXCEEDED"
  | "EVIDENCE_BUDGET_EXCEEDED"
  | "VERIFICATION_BUDGET_EXCEEDED"
  | "REVISION_BUDGET_EXCEEDED"
  | "PROPOSE_BUDGET_EXCEEDED"
  | "VERIFICATION_UNAVAILABLE"
  | "POLICY_AMBIGUOUS"
  | "POLICY_NOT_FOUND"
  | "CONFLICTING_REVISIONS"
  | "CONTRACT_VIOLATION";
export type LastKnownHandoffRef = string | null;
export type ThreadId2 = string;
export type ResultType = "MANUAL_ESCALATION";
export type Status6 = "COMPLETED";
export type SchemaVersion4 = "v1";
export type ThreadId3 = string;
export type AgentEvent =
  | StateChangeEvent
  | NodeEnterEvent
  | NodeExitEvent
  | TokenEvent
  | ToolCallEvent
  | ToolResultEvent
  | InterruptEvent
  | MemoryRetrievalEvent
  | DoneEvent
  | ErrorEvent;
export type CaseRef6 = string;
export type Node2 =
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
export type FromStatus =
  | (
      | "OBSERVING"
      | "AWAITING_CLARIFICATION"
      | "AWAITING_EVIDENCE"
      | "AWAITING_HUMAN_REVIEW"
      | "EXECUTING"
      | "RESOLVED"
      | "ESCALATED"
    )
  | null;
export type Reason1 = string;
export type ToStatus =
  | "OBSERVING"
  | "AWAITING_CLARIFICATION"
  | "AWAITING_EVIDENCE"
  | "AWAITING_HUMAN_REVIEW"
  | "EXECUTING"
  | "RESOLVED"
  | "ESCALATED";
export type Seq1 = number;
export type Ts = string;
export type Type4 = "state_change";
export type CaseRef7 = string;
export type Node3 =
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
export type Seq2 = number;
export type Ts1 = string;
export type Type5 = "node_enter";
export type CaseRef8 = string;
export type Node4 =
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
export type Seq3 = number;
export type Ts2 = string;
export type Type6 = "node_exit";
export type CaseRef9 = string;
export type Node5 =
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
export type Text2 = string;
export type Seq4 = number;
export type Ts3 = string;
export type Type7 = "token";
export type CaseRef10 = string;
export type Node6 =
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
export type CallId = string;
export type ToolName = string;
export type Seq5 = number;
export type Ts4 = string;
export type Type8 = "tool_call";
export type CaseRef11 = string;
export type Node7 =
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
export type CallId1 = string;
export type DurationMs1 = number;
export type Error = string | null;
export type Ok = boolean;
export type Summary = string;
export type ToolName1 = string;
export type Seq6 = number;
export type Ts5 = string;
export type Type9 = "tool_result";
export type CaseRef12 = string;
export type Node8 =
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
export type Payload2 = UiClarificationInterruptPayload | UiEvidenceInterruptPayload | UiHumanReviewInterruptPayload;
export type CaseRef13 = string;
export type InterruptKind = "CLARIFICATION";
export type ClarificationQuestion = string;
export type ClarificationRound1 = number;
/**
 * @minItems 1
 */
export type MissingFields = [string, ...string[]];
export type RequestId = string;
export type InterruptKind1 = "EVIDENCE_REQUEST";
/**
 * @minItems 1
 */
export type AcceptedEvidenceTypes = [
  "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT",
  ...("IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT")[]
];
export type CaseRef14 = string;
/**
 * @minItems 1
 */
export type MissingClaims = [MissingClaim, ...MissingClaim[]];
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
export type Subject = string;
/**
 * @minItems 1
 */
export type PolicyRefs = [string, ...string[]];
export type RequestId1 = string;
export type UserMessage = string;
export type InterruptKind2 = "HUMAN_REVIEW";
export type Review = FullRefundHumanReviewPayload | DeclineHumanReviewPayload;
export type Action1 = "FULL_REFUND";
export type Amount1 = string;
export type CaseRef15 = string;
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
export type OrderRef1 = string;
export type OrderSnapshotRef = string;
export type RefundableAmountMax = string;
export type SnapshotVersion = number;
/**
 * @minItems 1
 */
export type AllowedActions = ["FULL_REFUND" | "DECLINE", ...("FULL_REFUND" | "DECLINE")[]];
export type Categories1 = string[];
export type Markets = string[];
export type ReasonCodes2 = (
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND"
)[];
export type ClauseId = string;
export type EffectiveFrom = string;
export type EffectiveTo = string | null;
export type PolicyVersion1 = string;
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
export type ReturnPolicy = "REQUIRED" | "NOT_REQUIRED" | "MODEL_JUDGMENT";
export type Text3 = string;
export type Clauses = PolicyClause[];
export type PolicyBundleVersion = string;
export type RetrievalStatus = "OK" | "NOT_FOUND" | "AMBIGUOUS";
export type RetrievedAt = string;
/**
 * @minItems 1
 */
export type ProposalHistory = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type AgentPromptVersion = string;
export type CaseRef16 = string;
export type ClaimRegistryVersion2 = string;
export type ArtifactRef = string;
export type CollectedAt = string;
export type EvidenceId = string;
export type ExtractedSummary = string;
export type Source = "USER" | "ORDER_TOOL" | "LOGISTICS_TOOL" | "SYSTEM";
export type Subject1 = string;
export type Type10 = "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT";
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
export type Action2 = "FULL_REFUND";
export type Amount2 = string;
export type Currency3 = string;
export type EvidenceRefs1 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs2 = [string, ...string[]];
export type ReasonCode1 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @minItems 1
 */
export type LineItemIds = [string, ...string[]];
export type ReturnDecision = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type Requirement = RequiredReturnRequirement | WaivedReturnRequirement;
export type ReasonCode2 = "RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION";
export type Required = true;
export type ReasonCode3 =
  "ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN";
export type Required1 = false;
export type Source1 = "POLICY";
export type Requirement1 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source2 = "MODEL_JUDGMENT";
export type Action3 = "DECLINE";
export type Amount3 = string;
export type Currency4 = string;
export type EvidenceRefs2 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs3 = [string, ...string[]];
export type ReasonCode4 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @maxItems 0
 */
export type LineItemIds1 = [];
export type RationaleSummary = string;
export type RevisionRound2 = number;
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
export type Explanation = string;
export type Status7 = "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED";
export type Subject2 = string;
export type SupportingEvidenceRefs = string[];
export type ReviewerPromptVersion = string;
/**
 * @maxItems 0
 */
export type RevisionReasons = [];
export type Verdict1 = "APPROVE";
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
export type Code1 =
  | "EVIDENCE_INSUFFICIENT"
  | "POLICY_MISMATCH"
  | "DECISION_UNSUPPORTED"
  | "DECISION_INCONSISTENT"
  | "SCOPE_UNSUPPORTED"
  | "RETURN_REQUIREMENT_INCONSISTENT"
  | "HANDOFF_INCOMPLETE"
  | "OTHER";
export type EvidenceRefs3 = string[];
export type Message1 = string;
export type PolicyRefs4 = string[];
export type RequiredChange = string;
export type Subject3 = string;
export type Verdict2 = "REVISE";
export type CaseRef17 = string;
export type CreatedAt1 = string;
export type EventId3 = string;
export type HandoffBeforeRef = string;
export type ReviewResult = ApprovedReviewResult | RevisedReviewResult;
export type RevisionRound3 = number;
export type RevisionEvents = DecisionRevisionEvent[];
export type RoutingReason = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type ArtifactRef1 = string;
export type Caption = string;
export type EvidenceId1 = string;
export type Subject4 = string;
export type Type11 = "IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT";
export type EvidenceRefs4 = EvidenceDisplayRef[];
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
export type Action4 = "DECLINE";
export type Amount4 = string;
export type CaseRef18 = string;
export type Currency5 = string;
export type EvidenceRefs5 = EvidenceDisplayRef[];
export type HandoffId2 = string;
export type MemoriesUsed1 = string[];
export type PolicyHits1 = PolicyDisplayRef[];
export type RationaleSummary2 = string;
export type ReviewResult2 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason2 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type Seq7 = number;
export type Ts6 = string;
export type Type12 = "interrupt";
export type CaseRef19 = string;
export type Node9 =
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
export type Seq8 = number;
export type Ts7 = string;
export type Type13 = "memory_retrieval";
export type CaseRef20 = string;
export type Node10 =
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
export type Status8 = "RESOLVED" | "ESCALATED";
export type TerminalRef = string;
export type Seq9 = number;
export type Ts8 = string;
export type Type14 = "done";
export type CaseRef21 = string;
export type Node11 =
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
export type Code2 = string;
export type Message2 = string;
export type Retryable = boolean;
export type Seq10 = number;
export type Ts9 = string;
export type Type15 = "error";
export type Action5 = "FULL_REFUND";
export type Amount5 = string;
export type Currency6 = string;
export type ReasonCode5 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReturnDecision2 = PolicyReturnDecision | ModelJudgmentReturnDecision;
export type CaseRef22 = string;
export type CommandId3 = string;
export type EventId4 = string;
export type EventIndex1 = number;
export type EventType1 = "INTERRUPTED";
export type OccurredAt3 = string;
export type InterruptPayload = ClarificationInterruptPayload | EvidenceInterruptPayload | HumanReviewInterruptPayload;
export type CaseRef23 = string;
export type Kind3 = "CLARIFICATION";
export type CaseRef24 = string;
export type Kind4 = "EVIDENCE_REQUEST";
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
export type MissingClaims1 = [MissingClaim, ...MissingClaim[]];
/**
 * @minItems 1
 */
export type PolicyRefs5 = [string, ...string[]];
export type RequestId2 = string;
export type UserMessage1 = string;
export type CaseRef25 = string;
export type HandoffId3 = string;
export type Kind5 = "HUMAN_REVIEW";
export type MemoryIds = string[];
export type ReviewRef = string;
export type ReviewResult3 = ApprovedReviewResult | RevisedReviewResult;
export type RoutingReason3 = "REVISION_BUDGET_EXCEEDED" | "HIGH_VALUE_ITEM" | "CURRENCY_THRESHOLD_UNCONFIGURED";
export type ResultType1 = "INTERRUPTED";
export type Status9 = "INTERRUPTED";
export type SchemaVersion5 = "v1";
export type ThreadId4 = string;
export type CaseRef26 = string;
export type CommandId4 = string;
export type EventId5 = string;
export type EventIndex2 = number;
export type EventType2 = "NODE_OBSERVED";
export type OccurredAt4 = string;
export type ErrorMessage = string | null;
export type Node12 =
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
export type Phase1 = "ENTER" | "EXIT" | "ERROR";
export type TaskRef = string;
export type SchemaVersion6 = "v1";
export type ThreadId5 = string;
export type CaseRef27 = string;
export type CommandId5 = string;
export type EventId6 = string;
export type EventIndex3 = number;
export type EventType3 = "RESOLVED";
export type OccurredAt5 = string;
export type ResolutionHandoff =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
export type CaseRef28 = string;
export type EmittedAt = string;
export type ExecutionBlocked = false;
export type FinalDecision = AgentFullRefundFinalDecision | DeclineFinalDecision;
export type Action6 = "DECLINE";
export type Amount6 = string;
export type Currency7 = string;
export type ReasonCode6 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type HandoffId4 = string;
export type OutcomeSource = "REVIEWER_APPROVE";
export type CaseRef29 = string;
export type EmittedAt1 = string;
export type ExecutionBlocked1 = false;
export type FinalDecision1 = AgentFullRefundFinalDecision | DeclineFinalDecision;
export type HandoffId5 = string;
export type OutcomeSource1 = "HUMAN_APPROVE";
export type ReviewResult4 = ApprovedReviewResult | RevisedReviewResult;
export type CaseRef30 = string;
export type EmittedAt2 = string;
export type ExecutionBlocked2 = false;
export type FinalDecision2 = HumanEditedFullRefundFinalDecision | DeclineFinalDecision;
export type Action7 = "FULL_REFUND";
export type Amount7 = string;
export type Currency8 = string;
export type ReasonCode7 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type Requirement2 = RequiredReturnRequirement | WaivedReturnRequirement;
export type Source3 = "HUMAN_REVIEW";
export type HandoffId6 = string;
export type OutcomeSource2 = "HUMAN_EDIT";
export type ReviewResult5 = ApprovedReviewResult | RevisedReviewResult;
export type CaseRef31 = string;
export type EmittedAt3 = string;
export type ExecutionBlocked3 = false;
export type HandoffId7 = string;
export type OutcomeSource3 = "HUMAN_REJECT";
export type ReviewResult6 = ApprovedReviewResult | RevisedReviewResult;
export type ResultType2 = "RESOLUTION";
export type Status10 = "COMPLETED";
export type SchemaVersion7 = "v1";
export type ThreadId6 = string;
export type Payload3 = ClarificationResume | EvidenceResume | HumanReviewPollResume;
export type ThreadId7 = string;
export type CaseRef32 = string;
export type CommandId6 = string;
export type EventId7 = string;
export type EventIndex4 = number;
export type EventType4 = "RUN_FAILED";
export type OccurredAt6 = string;
export type Code3 = string;
export type FailedNode =
  | (
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
      | "terminate_automation"
    )
  | null;
export type Message3 = string;
export type Retryable1 = boolean;
export type SchemaVersion8 = "v1";
export type ThreadId8 = string;
export type AgentRunResult = ResolutionAgentRunResult | InterruptedAgentRunResult | ManualEscalationAgentRunResult;
export type AgentServiceEvent =
  AgentNodeObservedEvent | AgentResolvedEvent | AgentInterruptedEvent | AgentEscalatedEvent | AgentRunFailedEvent;
export type CaseRef33 = string;
export type OrderRef2 = string | null;
export type ThreadId9 = string;
export type ApplicationRef = string;
export type AppliedAt = string;
export type Status11 = "APPLIED";
export type ExecutionRef = string;
export type ResolutionHandoff1 =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
/**
 * @minItems 1
 */
export type ClaimFindings = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion3 = string;
export type EvidenceStatus = "SUFFICIENT_FOR_APPROVAL";
export type Decision = "APPROVE";
export type Generalizable = boolean | null;
export type HandoffId8 = string | null;
export type ReviewNote = string;
export type ReviewerId = string;
export type Decision1 = "APPROVE";
export type FinalResolutionRef = string;
export type Generalizable1 = boolean | null;
export type ReviewNote1 = string;
export type ReviewedAt2 = string;
export type ReviewerId1 = string;
export type CaseOpenedAt = string;
export type CaseRef34 = string;
export type Market1 = string;
export type OrderRef3 = string;
export type SnapshotVersion1 = number;
export type CaseRef35 = string;
export type CreatedAt2 = string;
export type HumanReview = (FullRefundHumanReviewPayload | DeclineHumanReviewPayload) | null;
export type HumanReviewResult =
  (ApprovedHumanReviewResult | RejectedHumanReviewResult | EditedHumanReviewResult) | null;
export type Decision2 = "REJECT";
export type FinalResolutionRef1 = string;
export type Generalizable2 = boolean | null;
export type ReviewNote2 = string;
export type ReviewedAt3 = string;
export type ReviewerId2 = string;
export type CorrectedDecision = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type Action8 = "FULL_REFUND";
export type Action9 = "DECLINE";
export type CorrectionReasonCode =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision3 = "EDIT";
export type FinalResolutionRef2 = string;
export type Generalizable3 = boolean | null;
export type ReviewNote3 = string;
export type ReviewedAt4 = string;
export type ReviewerId3 = string;
export type OrderRef4 = string;
export type Status12 =
  | "OBSERVING"
  | "AWAITING_CLARIFICATION"
  | "AWAITING_EVIDENCE"
  | "AWAITING_HUMAN_REVIEW"
  | "EXECUTING"
  | "RESOLVED"
  | "ESCALATED";
export type UpdatedAt = string;
export type UserRef = string;
export type AcceptedEvidenceTypes2 = ("IMAGE" | "VIDEO" | "TEXT" | "DOCUMENT")[];
export type ClaimId3 =
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
export type CorrectedDecision1 = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type AttachedArtifactRefs1 = string[];
export type InitialMessage = string;
export type OrderRef5 = string;
export type UserRef1 = string;
export type CaseRef36 = string;
/**
 * @minItems 1
 */
export type ClaimFindings1 = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion4 = string;
export type EvidenceStatus1 = "SUFFICIENT_FOR_DECLINE";
export type Action10 = "DECLINE";
export type EvidenceRefs6 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs6 = [string, ...string[]];
export type RationaleSummary3 = string;
export type ReasonCode8 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type CorrectedDecision2 = CorrectedFullRefundDecision | CorrectedDeclineDecision;
export type CorrectionReasonCode1 =
  "CLAIM_NOT_ESTABLISHED" | "POLICY_MISAPPLIED" | "SCOPE_INCORRECT" | "RETURN_REQUIREMENT_INCORRECT" | "OTHER";
export type Decision4 = "EDIT";
export type Generalizable4 = boolean | null;
export type HandoffId9 = string | null;
export type ReviewNote4 = string;
export type ReviewerId4 = string;
export type EvidenceAssessment =
  ApprovalEvidenceAssessment | DeclineEvidenceAssessment | InsufficientEvidenceAssessment;
/**
 * @minItems 1
 */
export type ClaimFindings2 = [ClaimFinding, ...ClaimFinding[]];
export type ClaimRegistryVersion5 = string;
export type EvidenceStatus2 = "INSUFFICIENT";
export type ResolutionHandoff2 =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
/**
 * @minItems 1
 */
export type Issues = [VerificationIssue, ...VerificationIssue[]];
export type Status13 = "FAIL";
export type VerificationVersion = string;
export type ReviewRef1 = string;
export type Method = "HumanReviewProvider.fetch_result";
export type Action11 = "FULL_REFUND";
export type EvidenceRefs7 = string[];
/**
 * @minItems 1
 */
export type PolicyRefs7 = [string, ...string[]];
export type RationaleSummary4 = string;
export type ReasonCode9 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type ReturnDecision3 = PolicyReturnDecisionDraft | ModelJudgmentReturnDecision;
export type ReasonCode10 =
  | ("RESALE_VALUE_RETAINED" | "RETURN_REQUIRED_FOR_INSPECTION")
  | ("ITEM_UNSALVAGEABLE" | "HYGIENE_RISK" | "RETURN_UNECONOMICAL" | "EVIDENCE_SUFFICIENT_WITHOUT_RETURN");
export type Source4 = "POLICY";
export type HumanReviewPayload = FullRefundHumanReviewPayload | DeclineHumanReviewPayload;
export type HumanReviewResult1 = ApprovedHumanReviewResult | RejectedHumanReviewResult | EditedHumanReviewResult;
export type ClaimedLineItemIds1 = string[];
export type ClarificationQuestion1 = string | null;
export type Completeness = "COMPLETE" | "INCOMPLETE";
export type MissingFields1 = string[];
export type OrderRef6 = string | null;
export type ReasonCode11 =
  ("ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND") | null;
export type ReasonSummary = string | null;
export type RequestedAction = "REFUND" | "RETURN_AND_REFUND" | "EXCHANGE" | "UNSPECIFIED";
export type InterruptPayload1 = ClarificationInterruptPayload | EvidenceInterruptPayload | HumanReviewInterruptPayload;
export type CaseRef37 = string;
export type Method1 = "CaseContextProvider.load_case_context";
export type ClaimRegistryVersion6 = string;
export type Confidence1 = number;
export type MemoryId1 = string;
export type PolicyVersion3 = string;
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
export type Status14 = "CANDIDATE";
/**
 * @minItems 1
 */
export type TriggerConditions1 = [string, ...string[]];
export type DistillerPromptVersion = string;
export type ResultType3 = "CREATE_CANDIDATE";
export type SubmissionRef = string;
export type CaseRef38 = string;
export type EventId8 = string;
export type EventType5 = "COMPLETED";
export type JobId2 = string;
export type OccurredAt7 = string;
export type Payload4 = MemoryCandidateCompletedPayload | MemorySkipCompletedPayload;
export type DistillerPromptVersion1 = string;
export type ReasonCode12 =
  | "NO_FINAL_OUTCOME"
  | "CASE_SPECIFIC_ONLY"
  | "DATA_ENTRY_ERROR"
  | "POLICY_VERSION_UNKNOWN"
  | "CLAIM_REGISTRY_VERSION_UNKNOWN"
  | "RESTATES_EXISTING_POLICY"
  | "CONFLICTS_WITH_POLICY"
  | "NO_CONFIRMED_GENERALIZABLE_CORRECTION";
export type ResultType4 = "SKIP";
export type SubmissionRef1 = null;
export type SchemaVersion9 = "v1";
export type SourceCommandId = string;
export type ThreadId10 = string;
export type CaseRef39 = string;
export type EventId9 = string;
export type EventType6 = "FAILED";
export type JobId3 = string;
export type OccurredAt8 = string;
export type Code4 = string;
export type DistillerPromptVersion2 = string;
export type Message4 = string;
export type Retryable2 = boolean;
export type SchemaVersion10 = "v1";
export type SourceCommandId1 = string;
export type ThreadId11 = string;
export type ClaimedCategories = string[];
export type EvidenceAssessment1 =
  ApprovalEvidenceAssessment | DeclineEvidenceAssessment | InsufficientEvidenceAssessment;
export type FinalResolution =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
export type HumanReviewResult2 =
  (ApprovedHumanReviewResult | RejectedHumanReviewResult | EditedHumanReviewResult) | null;
/**
 * @minItems 1
 */
export type ProposalHistory1 = [ProposedDecisionHandoff, ...ProposedDecisionHandoff[]];
export type RevisionEvents1 = DecisionRevisionEvent[];
export type CaseRef40 = string;
export type IssuedAt2 = string;
export type JobId4 = string;
export type SchemaVersion11 = "v1";
export type SourceCommandId2 = string;
export type ThreadId12 = string;
export type MemoryDistillationOutput = MemoryCandidateOutput | MemorySkipOutput;
export type QuerySummary1 = string;
export type MemoryServiceEvent = MemoryDistillationCompletedEvent | MemoryDistillationFailedEvent;
export type JobId5 = string;
export type Text4 = string;
/**
 * @maxItems 0
 */
export type Issues1 = [];
export type Status15 = "PASS";
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
export type QuerySummary2 = string;
export type ReasonCode13 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
/**
 * @minItems 1
 */
export type RequiredClaimIds2 = [
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
export type TopK1 = number;
export type Method2 = "OperationalMemoryStore.query_approved";
export type RefundApplicationResult = AppliedRefundApplicationResult | RejectedRefundApplicationResult;
/**
 * @minItems 1
 */
export type ReasonCodes3 = [string, ...string[]];
export type RejectedAt = string;
export type Status16 = "REJECTED";
export type RefundExecutionRecord = SucceededRefundExecutionRecord | RejectedRefundExecutionRecord;
export type CaseRef41 = string;
export type CreatedAt3 = string;
export type ExecutionRef1 = string;
export type HandoffId10 = string;
export type Status17 = "SUCCEEDED";
export type UpdatedAt1 = string;
export type CaseRef42 = string;
export type CreatedAt4 = string;
export type ExecutionRef2 = string;
export type HandoffId11 = string;
export type Status18 = "REJECTED";
export type UpdatedAt2 = string;
export type Decision5 = "REJECT";
export type Generalizable5 = boolean | null;
export type HandoffId12 = string | null;
export type ReviewNote5 = string;
export type ReviewerId5 = string;
export type ResolutionHandoff3 =
  | ReviewerApprovedResolutionHandoff
  | HumanApproveResolutionHandoff
  | HumanEditResolutionHandoff
  | HumanRejectResolutionHandoff;
export type ArtifactRef2 = string;
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
export type ResultType5 = "CONFLICTING_REVISIONS";
export type Draft = FullRefundProposedDecisionDraft | DeclineProposedDecisionDraft;
export type ResultType6 = "DRAFT";
export type ResultType7 = "REQUEST_EVIDENCE";
export type ResolverOutput = ResolverDraftOutput | ResolverEvidenceRequestOutput | ResolverConflictOutput;
export type ResumePayload = ClarificationResume | EvidenceResume | HumanReviewPollResume;
/**
 * @minItems 1
 */
export type ClaimedLineItemIds2 = [string, ...string[]];
export type ReasonCode14 =
  "ITEM_DAMAGED" | "ITEM_NOT_AS_DESCRIBED" | "MISSING_ITEM" | "WRONG_ITEM" | "QUALITY_ISSUE" | "CHANGED_MIND";
export type Method4 = "PolicyProvider.retrieve_policy";
export type ReviewDecision = ApproveReviewDecision | RejectReviewDecision | EditReviewDecision;
export type ReviewResult7 = ApprovedReviewResult | RevisedReviewResult;
export type Version = string;
export type AttachedArtifactRefs2 = string[];
export type Message5 = string;
export type Review1 = ApprovedReviewResult | RevisedReviewResult;
export type Method5 = "HumanReviewProvider.submit_for_review";
export type Method6 = "OperationalMemoryStore.submit_candidate";
export type UiInterruptPayload =
  UiClarificationInterruptPayload | UiEvidenceInterruptPayload | UiHumanReviewInterruptPayload;
/**
 * @maxItems 0
 */
export type Issues2 = [];
export type Status19 = "UNAVAILABLE";
export type VerificationVersion2 = string;
export type AttachedArtifactRefs3 = string[];
export type ReceivedAt1 = string;
export type Role1 = "USER" | "AGENT";
export type Text5 = string;
export type TurnId1 = string;
export type VerificationResult = PassedVerificationResult | FailedVerificationResult | UnavailableVerificationResult;
export type Method7 = "VerificationProvider.verify";

export interface AccumulatedEscalationContext {
  clarification_round: ClarificationRound;
  evidence_round: EvidenceRound;
  review_history_refs?: ReviewHistoryRefs;
  revision_round: RevisionRound;
  verification_issues?: VerificationIssues;
  verification_round: VerificationRound;
}
export interface VerificationIssue {
  code: Code;
  field_path: FieldPath;
  message: Message;
}
export interface ActivityEmission {
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
export interface ActivityFacts {
  action?: Action;
  count?: Count;
  finding_statuses?: FindingStatuses;
  findings?: Findings;
  next_node?: NextNode;
  outcome?: Outcome;
  reason_codes?: ReasonCodes;
  references?: References;
  revision_round?: RevisionRound1;
  verdict?: Verdict;
}
export interface ActivityFinding {
  claim_id: ClaimId;
  evidence_refs?: EvidenceRefs;
  status: Status;
}
export interface ActivityInputs {
  argument_count: ArgumentCount;
  reason_code?: ReasonCode;
  required_claim_ids?: RequiredClaimIds;
  top_k?: TopK;
}
export interface NodeSummary {
  facts: ActivityFacts;
  memory_retrieval?: MemoryRetrievalObservation | null;
  review_gate?: ReviewGateResult | null;
  type?: Type1;
}
export interface MemoryRetrievalObservation {
  error_code?: ErrorCode1;
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
  reason_codes?: ReasonCodes1;
}
export interface ReviewGateResult {
  amount: Amount;
  config_hash: ConfigHash;
  config_version: ConfigVersion;
  currency: Currency;
  reason: Reason;
  status: Status3;
  threshold: Threshold;
}
export interface Narration {
  error_code?: ErrorCode2;
  source_event_id: SourceEventId;
  status: Status4;
  text?: Text;
  type?: Type2;
}
export interface BackgroundStatus {
  error_code?: ErrorCode3;
  status: Status5;
  type?: Type3;
}
export interface ActivityEvent {
  attempt_id: AttemptId1;
  case_ref: CaseRef1;
  event_id: EventId1;
  job_id?: JobId1;
  node: Node1;
  occurred_at: OccurredAt1;
  operation_id: OperationId1;
  parent_operation_id?: ParentOperationId1;
  payload: Payload1;
  run_id: RunId1;
  schema_version?: SchemaVersion1;
  scope: Scope1;
  seq: Seq;
}
export interface ActivityPage {
  events: Events;
  has_more: HasMore;
  next_cursor: NextCursor;
}
export interface AgentStartCommand {
  case_ref: CaseRef2;
  command_id: CommandId;
  command_type: CommandType;
  issued_at: IssuedAt;
  payload: AgentStartPayload;
  schema_version?: SchemaVersion2;
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
  text: Text1;
  turn_id: TurnId;
}
export interface AgentResumeCommand {
  case_ref: CaseRef3;
  command_id: CommandId1;
  command_type: CommandType1;
  issued_at: IssuedAt1;
  payload: AgentResumePayload;
  schema_version?: SchemaVersion3;
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
export interface AgentEscalatedEvent {
  case_ref: CaseRef4;
  command_id: CommandId2;
  event_id: EventId2;
  event_index: EventIndex;
  event_type: EventType;
  occurred_at: OccurredAt2;
  payload: AgentEscalatedPayload;
  schema_version?: SchemaVersion4;
  thread_id: ThreadId3;
}
export interface AgentEscalatedPayload {
  result: ManualEscalationAgentRunResult;
}
export interface ManualEscalationAgentRunResult {
  manual_escalation: ManualEscalationHandoff;
  result_type: ResultType;
  status: Status6;
}
export interface ManualEscalationHandoff {
  accumulated_context: AccumulatedEscalationContext;
  case_ref: CaseRef5;
  created_at: CreatedAt;
  escalation_reason: EscalationReason;
  last_known_handoff_ref?: LastKnownHandoffRef;
  thread_id: ThreadId2;
}
export interface StateChangeEvent {
  case_ref: CaseRef6;
  node: Node2;
  payload: StateChangePayload;
  seq: Seq1;
  ts: Ts;
  type: Type4;
}
export interface StateChangePayload {
  from_status?: FromStatus;
  reason: Reason1;
  to_status: ToStatus;
}
export interface NodeEnterEvent {
  case_ref: CaseRef7;
  node: Node3;
  payload: NodeLifecyclePayload;
  seq: Seq2;
  ts: Ts1;
  type: Type5;
}
export interface NodeLifecyclePayload {
  detail?: Detail;
  review_gate?: ReviewGateResult | null;
}
export interface NodeExitEvent {
  case_ref: CaseRef8;
  node: Node4;
  payload: NodeLifecyclePayload;
  seq: Seq3;
  ts: Ts2;
  type: Type6;
}
export interface TokenEvent {
  case_ref: CaseRef9;
  node: Node5;
  payload: TokenPayload;
  seq: Seq4;
  ts: Ts3;
  type: Type7;
}
export interface TokenPayload {
  text: Text2;
}
export interface ToolCallEvent {
  case_ref: CaseRef10;
  node: Node6;
  payload: ToolCallPayload;
  seq: Seq5;
  ts: Ts4;
  type: Type8;
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
  case_ref: CaseRef11;
  node: Node7;
  payload: ToolResultPayload;
  seq: Seq6;
  ts: Ts5;
  type: Type9;
}
export interface ToolResultPayload {
  call_id: CallId1;
  duration_ms: DurationMs1;
  error?: Error;
  ok: Ok;
  summary: Summary;
  tool_name: ToolName1;
}
export interface InterruptEvent {
  case_ref: CaseRef12;
  node: Node8;
  payload: Payload2;
  seq: Seq7;
  ts: Ts6;
  type: Type12;
}
export interface UiClarificationInterruptPayload {
  case_ref: CaseRef13;
  interrupt_kind: InterruptKind;
  request: ClarificationRequest;
}
export interface ClarificationRequest {
  clarification_question: ClarificationQuestion;
  clarification_round: ClarificationRound1;
  missing_fields: MissingFields;
  request_id: RequestId;
}
export interface UiEvidenceInterruptPayload {
  interrupt_kind: InterruptKind1;
  request: EvidenceRequestView;
}
export interface EvidenceRequestView {
  accepted_evidence_types: AcceptedEvidenceTypes;
  case_ref: CaseRef14;
  missing_claims: MissingClaims;
  policy_refs: PolicyRefs;
  request_id: RequestId1;
  user_message: UserMessage;
}
export interface MissingClaim {
  claim_id: ClaimId1;
  subject: Subject;
}
export interface UiHumanReviewInterruptPayload {
  interrupt_kind: InterruptKind2;
  review: Review;
}
export interface FullRefundHumanReviewPayload {
  action: Action1;
  amount: Amount1;
  case_ref: CaseRef15;
  currency: Currency1;
  dossier?: HumanReviewDossier | null;
  evidence_refs?: EvidenceRefs4;
  handoff_id: HandoffId1;
  memories_used?: MemoriesUsed;
  policy_hits?: PolicyHits;
  rationale_summary: RationaleSummary1;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision1;
  review_result: ReviewResult1;
  routing_reason?: RoutingReason1;
}
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
  order_ref: OrderRef1;
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
  required_claim_ids: RequiredClaimIds1;
  return_policy: ReturnPolicy;
  text: Text3;
}
export interface ApplicableConditions {
  categories?: Categories1;
  markets?: Markets;
  reason_codes?: ReasonCodes2;
}
export interface ProposedDecisionHandoff {
  agent_prompt_version: AgentPromptVersion;
  case_ref: CaseRef16;
  claim_registry_version: ClaimRegistryVersion2;
  evidence_bundle?: EvidenceBundle;
  handoff_id: HandoffId;
  handoff_version: HandoffVersion;
  order_snapshot_ref: OrderSnapshotRef1;
  policy_bundle_version: PolicyBundleVersion1;
  policy_refs: PolicyRefs1;
  proposed_decision: ProposedDecision;
  rationale_summary: RationaleSummary;
  revision_round: RevisionRound2;
}
export interface EvidenceItem {
  artifact_ref: ArtifactRef;
  collected_at: CollectedAt;
  evidence_id: EvidenceId;
  extracted_summary: ExtractedSummary;
  source: Source;
  subject: Subject1;
  type: Type10;
}
export interface FullRefundProposedDecision {
  action: Action2;
  amount: Amount2;
  currency: Currency3;
  evidence_refs?: EvidenceRefs1;
  policy_refs: PolicyRefs2;
  reason_code: ReasonCode1;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision;
}
export interface NonEmptyRefundScope {
  line_item_ids: LineItemIds;
}
export interface PolicyReturnDecision {
  requirement: Requirement;
  source: Source1;
}
export interface RequiredReturnRequirement {
  reason_code: ReasonCode2;
  required: Required;
}
export interface WaivedReturnRequirement {
  reason_code: ReasonCode3;
  required: Required1;
}
export interface ModelJudgmentReturnDecision {
  requirement: Requirement1;
  source: Source2;
}
export interface DeclineProposedDecision {
  action: Action3;
  amount: Amount3;
  currency: Currency4;
  evidence_refs?: EvidenceRefs2;
  policy_refs: PolicyRefs3;
  reason_code: ReasonCode4;
  refund_scope: EmptyRefundScope;
}
export interface EmptyRefundScope {
  line_item_ids: LineItemIds1;
}
export interface ApprovedReviewResult {
  reviewed_at: ReviewedAt;
  reviewer_claim_findings: ReviewerClaimFindings;
  reviewer_prompt_version: ReviewerPromptVersion;
  revision_reasons?: RevisionReasons;
  verdict: Verdict1;
}
export interface ClaimFinding {
  claim_id: ClaimId2;
  explanation: Explanation;
  status: Status7;
  subject: Subject2;
  supporting_evidence_refs?: SupportingEvidenceRefs;
}
export interface RevisedReviewResult {
  reviewed_at: ReviewedAt1;
  reviewer_claim_findings: ReviewerClaimFindings1;
  reviewer_prompt_version: ReviewerPromptVersion1;
  revision_reasons: RevisionReasons1;
  verdict: Verdict2;
}
export interface RevisionReason {
  code: Code1;
  evidence_refs?: EvidenceRefs3;
  message: Message1;
  policy_refs?: PolicyRefs4;
  required_change: RequiredChange;
  subject: Subject3;
}
export interface DecisionRevisionEvent {
  case_ref: CaseRef17;
  created_at: CreatedAt1;
  event_id: EventId3;
  handoff_before_ref: HandoffBeforeRef;
  review_result: ReviewResult;
  revision_round: RevisionRound3;
}
export interface EvidenceDisplayRef {
  artifact_ref: ArtifactRef1;
  caption: Caption;
  evidence_id: EvidenceId1;
  subject: Subject4;
  type: Type11;
}
export interface PolicyDisplayRef {
  clause_id: ClauseId1;
  excerpt: Excerpt;
  policy_version: PolicyVersion2;
  relevance?: Relevance;
  title?: Title1;
}
export interface DeclineHumanReviewPayload {
  action: Action4;
  amount: Amount4;
  case_ref: CaseRef18;
  currency: Currency5;
  dossier?: HumanReviewDossier | null;
  evidence_refs?: EvidenceRefs5;
  handoff_id: HandoffId2;
  memories_used?: MemoriesUsed1;
  policy_hits?: PolicyHits1;
  rationale_summary: RationaleSummary2;
  refund_scope: EmptyRefundScope;
  review_result: ReviewResult2;
  routing_reason?: RoutingReason2;
}
export interface MemoryRetrievalEvent {
  case_ref: CaseRef19;
  node: Node9;
  payload: MemoryRetrievalObservation;
  seq: Seq8;
  ts: Ts7;
  type: Type13;
}
export interface DoneEvent {
  case_ref: CaseRef20;
  node: Node10;
  payload: DonePayload;
  seq: Seq9;
  ts: Ts8;
  type: Type14;
}
export interface DonePayload {
  status: Status8;
  terminal_ref: TerminalRef;
}
export interface ErrorEvent {
  case_ref: CaseRef21;
  node: Node11;
  payload: ErrorPayload;
  seq: Seq10;
  ts: Ts9;
  type: Type15;
}
export interface ErrorPayload {
  code: Code2;
  message: Message2;
  retryable: Retryable;
}
export interface AgentFullRefundFinalDecision {
  action: Action5;
  amount: Amount5;
  currency: Currency6;
  reason_code: ReasonCode5;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision2;
}
export interface AgentInterruptedEvent {
  case_ref: CaseRef22;
  command_id: CommandId3;
  event_id: EventId4;
  event_index: EventIndex1;
  event_type: EventType1;
  occurred_at: OccurredAt3;
  payload: AgentInterruptedPayload;
  schema_version?: SchemaVersion5;
  thread_id: ThreadId4;
}
export interface AgentInterruptedPayload {
  result: InterruptedAgentRunResult;
}
export interface InterruptedAgentRunResult {
  interrupt_payload: InterruptPayload;
  result_type: ResultType1;
  status: Status9;
}
export interface ClarificationInterruptPayload {
  case_ref: CaseRef23;
  kind: Kind3;
  request: ClarificationRequest;
}
export interface EvidenceInterruptPayload {
  case_ref: CaseRef24;
  kind: Kind4;
  request: EvidenceRequest;
}
export interface EvidenceRequest {
  accepted_evidence_types: AcceptedEvidenceTypes1;
  missing_claims: MissingClaims1;
  policy_refs: PolicyRefs5;
  request_id: RequestId2;
  user_message: UserMessage1;
}
export interface HumanReviewInterruptPayload {
  case_ref: CaseRef25;
  dossier?: HumanReviewDossier | null;
  handoff: ProposedDecisionHandoff;
  handoff_id: HandoffId3;
  kind: Kind5;
  memory_ids?: MemoryIds;
  policy_bundle: PolicyBundle;
  review_ref: ReviewRef;
  review_result: ReviewResult3;
  routing_reason?: RoutingReason3;
}
export interface AgentNodeObservedEvent {
  case_ref: CaseRef26;
  command_id: CommandId4;
  event_id: EventId5;
  event_index: EventIndex2;
  event_type: EventType2;
  occurred_at: OccurredAt4;
  payload: AgentNodeObservedPayload;
  schema_version?: SchemaVersion6;
  thread_id: ThreadId5;
}
export interface AgentNodeObservedPayload {
  observation: NodeExecutionObservation;
}
export interface NodeExecutionObservation {
  error_message?: ErrorMessage;
  memory_retrieval?: MemoryRetrievalObservation | null;
  node: Node12;
  phase: Phase1;
  review_gate?: ReviewGateResult | null;
  task_ref: TaskRef;
}
export interface AgentResolvedEvent {
  case_ref: CaseRef27;
  command_id: CommandId5;
  event_id: EventId6;
  event_index: EventIndex3;
  event_type: EventType3;
  occurred_at: OccurredAt5;
  payload: AgentResolvedPayload;
  schema_version?: SchemaVersion7;
  thread_id: ThreadId6;
}
export interface AgentResolvedPayload {
  result: ResolutionAgentRunResult;
}
export interface ResolutionAgentRunResult {
  resolution_handoff: ResolutionHandoff;
  result_type: ResultType2;
  status: Status10;
}
export interface ReviewerApprovedResolutionHandoff {
  case_ref: CaseRef28;
  emitted_at: EmittedAt;
  execution_blocked: ExecutionBlocked;
  final_decision: FinalDecision;
  handoff_id: HandoffId4;
  outcome_source: OutcomeSource;
  review_gate?: ReviewGateResult | null;
  review_result: ApprovedReviewResult;
}
export interface DeclineFinalDecision {
  action: Action6;
  amount: Amount6;
  currency: Currency7;
  reason_code: ReasonCode6;
  refund_scope: EmptyRefundScope;
}
export interface HumanApproveResolutionHandoff {
  case_ref: CaseRef29;
  emitted_at: EmittedAt1;
  execution_blocked: ExecutionBlocked1;
  final_decision: FinalDecision1;
  handoff_id: HandoffId5;
  outcome_source: OutcomeSource1;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult4;
}
export interface HumanEditResolutionHandoff {
  case_ref: CaseRef30;
  emitted_at: EmittedAt2;
  execution_blocked: ExecutionBlocked2;
  final_decision: FinalDecision2;
  handoff_id: HandoffId6;
  outcome_source: OutcomeSource2;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult5;
}
export interface HumanEditedFullRefundFinalDecision {
  action: Action7;
  amount: Amount7;
  currency: Currency8;
  reason_code: ReasonCode7;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface HumanReviewReturnDecision {
  requirement: Requirement2;
  source: Source3;
}
export interface HumanRejectResolutionHandoff {
  case_ref: CaseRef31;
  emitted_at: EmittedAt3;
  execution_blocked: ExecutionBlocked3;
  final_decision: DeclineFinalDecision;
  handoff_id: HandoffId7;
  outcome_source: OutcomeSource3;
  review_gate?: ReviewGateResult | null;
  review_result: ReviewResult6;
}
export interface AgentResumeRequest {
  payload: Payload3;
  thread_id: ThreadId7;
}
export interface AgentRunFailedEvent {
  case_ref: CaseRef32;
  command_id: CommandId6;
  event_id: EventId7;
  event_index: EventIndex4;
  event_type: EventType4;
  occurred_at: OccurredAt6;
  payload: AgentRunFailedPayload;
  schema_version?: SchemaVersion8;
  thread_id: ThreadId8;
}
export interface AgentRunFailedPayload {
  code: Code3;
  failed_node?: FailedNode;
  message: Message3;
  retryable: Retryable1;
}
export interface AgentStartRequest {
  case_ref: CaseRef33;
  initial_turn: AgentUserTurn;
  order_ref?: OrderRef2;
  thread_id: ThreadId9;
}
export interface AppliedRefundApplicationResult {
  application_ref: ApplicationRef;
  applied_at: AppliedAt;
  status: Status11;
}
export interface ApplyRefundRequest {
  execution_ref: ExecutionRef;
  resolution_handoff: ResolutionHandoff1;
}
export interface ApprovalEvidenceAssessment {
  claim_findings: ClaimFindings;
  claim_registry_version: ClaimRegistryVersion3;
  evidence_status: EvidenceStatus;
}
export interface ApproveReviewDecision {
  decision: Decision;
  generalizable?: Generalizable;
  handoff_id?: HandoffId8;
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
export interface CaseContext {
  case_opened_at: CaseOpenedAt;
  case_ref: CaseRef34;
  market: Market1;
  order_ref: OrderRef3;
  snapshot_version: SnapshotVersion1;
}
export interface CaseContextLoadResult {
  case_context: CaseContext;
  order_snapshot: OrderSnapshot;
}
export interface CaseDetail {
  case_ref: CaseRef35;
  clarification_request?: ClarificationRequest | null;
  created_at: CreatedAt2;
  evidence_request?: EvidenceRequestView | null;
  human_review?: HumanReview;
  human_review_result?: HumanReviewResult;
  order_ref: OrderRef4;
  status: Status12;
  updated_at: UpdatedAt;
  user_ref: UserRef;
}
export interface RejectedHumanReviewResult {
  decision: Decision2;
  final_resolution_ref: FinalResolutionRef1;
  generalizable?: Generalizable2;
  review_note: ReviewNote2;
  reviewed_at: ReviewedAt3;
  reviewer_id?: ReviewerId2;
}
export interface EditedHumanReviewResult {
  corrected_decision: CorrectedDecision;
  correction_reason_code: CorrectionReasonCode;
  decision: Decision3;
  final_resolution_ref: FinalResolutionRef2;
  generalizable?: Generalizable3;
  review_note: ReviewNote3;
  reviewed_at: ReviewedAt4;
  reviewer_id?: ReviewerId3;
}
export interface CorrectedFullRefundDecision {
  action: Action8;
  refund_scope: NonEmptyRefundScope;
  return_decision: HumanReviewReturnDecision;
}
export interface CorrectedDeclineDecision {
  action: Action9;
  refund_scope: EmptyRefundScope;
}
export interface ClaimDefinition {
  accepted_evidence_types?: AcceptedEvidenceTypes2;
  claim_id: ClaimId3;
  description: Description;
  distinguish_from?: DistinguishFrom;
  observable_requirement: ObservableRequirement;
  satisfiable_by: SatisfiableBy;
  subject_scope: SubjectScope;
}
export interface CreateCaseRequest {
  attached_artifact_refs?: AttachedArtifactRefs1;
  initial_message: InitialMessage;
  order_ref: OrderRef5;
  user_ref: UserRef1;
}
export interface CreateCaseResponse {
  case_ref: CaseRef36;
}
export interface DeclineEvidenceAssessment {
  claim_findings: ClaimFindings1;
  claim_registry_version: ClaimRegistryVersion4;
  evidence_status: EvidenceStatus1;
}
export interface DeclineProposedDecisionDraft {
  action: Action10;
  evidence_refs?: EvidenceRefs6;
  policy_refs: PolicyRefs6;
  rationale_summary: RationaleSummary3;
  reason_code: ReasonCode8;
  refund_scope: EmptyRefundScope;
}
export interface EditReviewDecision {
  corrected_decision: CorrectedDecision2;
  correction_reason_code: CorrectionReasonCode1;
  decision: Decision4;
  generalizable?: Generalizable4;
  handoff_id?: HandoffId9;
  review_note: ReviewNote4;
  reviewer_id?: ReviewerId4;
}
export interface InsufficientEvidenceAssessment {
  claim_findings: ClaimFindings2;
  claim_registry_version: ClaimRegistryVersion5;
  evidence_status: EvidenceStatus2;
  missing_evidence_request: EvidenceRequest;
}
export interface ExecuteRefundRequest {
  resolution_handoff: ResolutionHandoff2;
}
export interface FailedVerificationResult {
  issues: Issues;
  status: Status13;
  verification_version: VerificationVersion;
}
export interface FetchHumanReviewParams {
  review_ref: ReviewRef1;
}
export interface FetchHumanReviewRequest {
  method: Method;
  params: FetchHumanReviewParams;
}
export interface FullRefundProposedDecisionDraft {
  action: Action11;
  evidence_refs?: EvidenceRefs7;
  policy_refs: PolicyRefs7;
  rationale_summary: RationaleSummary4;
  reason_code: ReasonCode9;
  refund_scope: NonEmptyRefundScope;
  return_decision: ReturnDecision3;
}
export interface PolicyReturnDecisionDraft {
  reason_code: ReasonCode10;
  source: Source4;
}
export interface IntakeResult {
  claimed_line_item_ids?: ClaimedLineItemIds1;
  clarification_question?: ClarificationQuestion1;
  completeness: Completeness;
  missing_fields?: MissingFields1;
  order_ref?: OrderRef6;
  reason_code?: ReasonCode11;
  reason_summary?: ReasonSummary;
  requested_action: RequestedAction;
}
export interface LoadCaseContextParams {
  case_ref: CaseRef37;
}
export interface LoadCaseContextRequest {
  method: Method1;
  params: LoadCaseContextParams;
}
export interface MemoryCandidate {
  claim_registry_version: ClaimRegistryVersion6;
  confidence: Confidence1;
  memory_id: MemoryId1;
  policy_version: PolicyVersion3;
  rationale: Rationale;
  recommended_behavior: RecommendedBehavior1;
  retrieval_summary: RetrievalSummary1;
  scope: MemoryScope;
  source_case_refs: SourceCaseRefs;
  source_revision_event_refs: SourceRevisionEventRefs;
  status: Status14;
  trigger_conditions: TriggerConditions1;
}
export interface MemoryCandidateCompletedPayload {
  distiller_prompt_version: DistillerPromptVersion;
  result: MemoryCandidateOutput;
  submission_ref: SubmissionRef;
}
export interface MemoryCandidateOutput {
  candidate: MemoryCandidate;
  result_type: ResultType3;
}
export interface MemoryDistillationCompletedEvent {
  case_ref: CaseRef38;
  event_id: EventId8;
  event_type: EventType5;
  job_id: JobId2;
  occurred_at: OccurredAt7;
  payload: Payload4;
  schema_version?: SchemaVersion9;
  source_command_id: SourceCommandId;
  thread_id: ThreadId10;
}
export interface MemorySkipCompletedPayload {
  distiller_prompt_version: DistillerPromptVersion1;
  result: MemorySkipOutput;
  submission_ref?: SubmissionRef1;
}
export interface MemorySkipOutput {
  reason_code: ReasonCode12;
  result_type: ResultType4;
}
export interface MemoryDistillationFailedEvent {
  case_ref: CaseRef39;
  event_id: EventId9;
  event_type: EventType6;
  job_id: JobId3;
  occurred_at: OccurredAt8;
  payload: MemoryDistillationFailedPayload;
  schema_version?: SchemaVersion10;
  source_command_id: SourceCommandId1;
  thread_id: ThreadId11;
}
export interface MemoryDistillationFailedPayload {
  code: Code4;
  distiller_prompt_version: DistillerPromptVersion2;
  message: Message4;
  retryable: Retryable2;
}
export interface MemoryDistillationInput {
  case_context: CaseContext;
  claimed_categories?: ClaimedCategories;
  evidence_assessment: EvidenceAssessment1;
  final_resolution: FinalResolution;
  human_review_result?: HumanReviewResult2;
  policy_bundle: PolicyBundle;
  proposal_history: ProposalHistory1;
  revision_events?: RevisionEvents1;
}
export interface MemoryDistillationJob {
  case_ref: CaseRef40;
  issued_at: IssuedAt2;
  job_id: JobId4;
  payload: MemoryDistillationJobPayload;
  schema_version?: SchemaVersion11;
  source_command_id: SourceCommandId2;
  thread_id: ThreadId12;
}
export interface MemoryDistillationJobPayload {
  input: MemoryDistillationInput;
}
export interface MemoryQuerySummary {
  query_summary: QuerySummary1;
}
export interface NarrationJob {
  job_id: JobId5;
  source: ActivityEmission;
}
export interface NarrationText {
  text: Text4;
}
export interface PassedVerificationResult {
  issues?: Issues1;
  status: Status15;
  verification_version: VerificationVersion1;
}
export interface QueryApprovedMemoryParams {
  categories?: Categories2;
  claim_registry_major: ClaimRegistryMajor;
  market: Market2;
  policy_versions: PolicyVersions;
  query_summary: QuerySummary2;
  reason_code: ReasonCode13;
  required_claim_ids: RequiredClaimIds2;
  top_k?: TopK1;
}
export interface QueryApprovedMemoryRequest {
  method: Method2;
  params: QueryApprovedMemoryParams;
}
export interface RejectedRefundApplicationResult {
  reason_codes: ReasonCodes3;
  rejected_at: RejectedAt;
  status: Status16;
}
export interface SucceededRefundExecutionRecord {
  application_result: AppliedRefundApplicationResult;
  case_ref: CaseRef41;
  created_at: CreatedAt3;
  execution_ref: ExecutionRef1;
  handoff_id: HandoffId10;
  status: Status17;
  updated_at: UpdatedAt1;
}
export interface RejectedRefundExecutionRecord {
  application_result: RejectedRefundApplicationResult;
  case_ref: CaseRef42;
  created_at: CreatedAt4;
  execution_ref: ExecutionRef2;
  handoff_id: HandoffId11;
  status: Status18;
  updated_at: UpdatedAt2;
}
export interface RejectReviewDecision {
  decision: Decision5;
  generalizable?: Generalizable5;
  handoff_id?: HandoffId12;
  review_note: ReviewNote5;
  reviewer_id?: ReviewerId5;
}
export interface ResolveEvidenceParams {
  artifact_ref: ArtifactRef2;
}
export interface ResolveEvidenceRequest {
  method: Method3;
  params: ResolveEvidenceParams;
}
export interface ResolverConflictOutput {
  conflict: RevisionConflictReport;
  result_type: ResultType5;
}
export interface RevisionConflictReport {
  conflicting_reason_codes: ConflictingReasonCodes;
  conflicting_review_refs: ConflictingReviewRefs;
  explanation: Explanation1;
}
export interface ResolverDraftOutput {
  draft: Draft;
  result_type: ResultType6;
}
export interface ResolverEvidenceRequestOutput {
  evidence_request: EvidenceRequest;
  result_type: ResultType7;
}
export interface RetrievePolicyParams {
  case_context: CaseContext;
  claimed_line_item_ids: ClaimedLineItemIds2;
  order_snapshot: OrderSnapshot;
  reason_code: ReasonCode14;
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
export interface SendMessageRequest {
  attached_artifact_refs?: AttachedArtifactRefs2;
  message: Message5;
}
export interface SubmitHumanReviewParams {
  dossier?: HumanReviewDossier | null;
  handoff: ProposedDecisionHandoff;
  review: Review1;
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
  status: Status19;
  verification_version: VerificationVersion2;
}
export interface UserTurn {
  attached_artifact_refs?: AttachedArtifactRefs3;
  received_at: ReceivedAt1;
  role: Role1;
  text: Text5;
  turn_id: TurnId1;
}
export interface VerifyHandoffParams {
  handoff: ProposedDecisionHandoff;
}
export interface VerifyHandoffRequest {
  method: Method7;
  params: VerifyHandoffParams;
}
