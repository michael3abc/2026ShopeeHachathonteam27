"""Pydantic DTOs for the agent's internal and external contracts."""

from typing import Annotated, Literal, TypeAlias
from .review_gates import ReviewGateResult, HumanReviewRoutingReason

from pydantic import ConfigDict, Field, model_validator

from .base import (
    ContractModel,
    CurrencyCode,
    Money,
    NonEmptyText,
    NonNegativeInt,
    OpaqueRef,
    PositiveInt,
    UnitInterval,
    UTCDateTime,
    ZeroMoney,
)
from .enums import (
    ClaimId,
    ClaimStatus,
    EscalationReason,
    EvidenceSource,
    EvidenceStatus,
    EvidenceType,
    HumanCorrectionReasonCode,
    HumanDecision,
    IntakeCompleteness,
    MemoryDistillationResultType,
    MemorySkipReasonCode,
    MemoryStatus,
    OutcomeSource,
    ReasonCode,
    RefundApplicationStatus,
    RefundExecutionStatus,
    RequestedAction,
    RequiredReturnReasonCode,
    ResolutionAction,
    ResolverResultType,
    RetrievalStatus,
    ReturnDecisionSource,
    ReturnPolicy,
    ReviewVerdict,
    RevisionReasonCode,
    UserRole,
    VerificationStatus,
    WaivedReturnReasonCode,
)

ORDER_SUBJECT = "ORDER"
REVIEW_REVISION_LIMIT = 3
MEMORY_SUMMARY_VERSION = "memory-summary:1.0"


class UserTurn(ContractModel):
    turn_id: OpaqueRef
    role: UserRole
    text: NonEmptyText
    attached_artifact_refs: list[OpaqueRef] = Field(default_factory=list)
    received_at: UTCDateTime


class CaseContext(ContractModel):
    case_ref: OpaqueRef
    order_ref: OpaqueRef
    market: NonEmptyText
    case_opened_at: UTCDateTime
    snapshot_version: PositiveInt


class OrderLineItem(ContractModel):
    line_item_id: OpaqueRef
    sku_ref: OpaqueRef
    category_ref: OpaqueRef
    title: NonEmptyText
    quantity: PositiveInt
    refundable_amount: Money


class OrderSnapshot(ContractModel):
    order_snapshot_ref: OpaqueRef
    order_ref: OpaqueRef
    snapshot_version: PositiveInt
    captured_at: UTCDateTime
    currency: CurrencyCode
    delivered_at: UTCDateTime
    line_items: list[OrderLineItem] = Field(min_length=1)
    refundable_amount_max: Money
    already_refunded_amount: Money

    @model_validator(mode="after")
    def _line_item_ids_are_unique(self) -> "OrderSnapshot":
        ids = [item.line_item_id for item in self.line_items]
        if len(ids) != len(set(ids)):
            raise ValueError("line_item_id values must be unique")
        return self


class CaseContextLoadResult(ContractModel):
    case_context: CaseContext
    order_snapshot: OrderSnapshot


class ApplicableConditions(ContractModel):
    markets: list[NonEmptyText] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    categories: list[OpaqueRef] = Field(default_factory=list)


class PolicyClause(ContractModel):
    clause_id: OpaqueRef
    policy_version: OpaqueRef
    effective_from: UTCDateTime
    effective_to: UTCDateTime | None = None
    applicable_conditions: ApplicableConditions
    required_claim_ids: list[ClaimId] = Field(min_length=1)
    allowed_actions: list[ResolutionAction] = Field(min_length=1)
    return_policy: ReturnPolicy
    text: NonEmptyText

    @model_validator(mode="after")
    def _effective_range_is_ordered(self) -> "PolicyClause":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        if len(self.required_claim_ids) != len(set(self.required_claim_ids)):
            raise ValueError("required_claim_ids must be unique")
        if len(self.allowed_actions) != len(set(self.allowed_actions)):
            raise ValueError("allowed_actions must be unique")
        return self


class PolicyBundle(ContractModel):
    policy_bundle_version: OpaqueRef
    retrieval_status: RetrievalStatus
    retrieved_at: UTCDateTime
    clauses: list[PolicyClause] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ok_bundle_has_clauses(self) -> "PolicyBundle":
        if self.retrieval_status is RetrievalStatus.OK and not self.clauses:
            raise ValueError("OK PolicyBundle must contain at least one clause")
        return self


class EvidenceItem(ContractModel):
    evidence_id: OpaqueRef
    type: EvidenceType
    source: EvidenceSource
    subject: OpaqueRef
    artifact_ref: OpaqueRef
    extracted_summary: NonEmptyText
    collected_at: UTCDateTime


class ClaimFinding(ContractModel):
    claim_id: ClaimId
    subject: OpaqueRef
    status: ClaimStatus
    supporting_evidence_refs: list[OpaqueRef] = Field(default_factory=list)
    explanation: NonEmptyText


class MissingClaim(ContractModel):
    claim_id: ClaimId
    subject: OpaqueRef


class EvidenceRequest(ContractModel):
    request_id: OpaqueRef
    missing_claims: list[MissingClaim] = Field(min_length=1)
    accepted_evidence_types: list[EvidenceType] = Field(min_length=1)
    user_message: NonEmptyText
    policy_refs: list[OpaqueRef] = Field(min_length=1)


class _EvidenceAssessmentBase(ContractModel):
    claim_registry_version: OpaqueRef
    claim_findings: list[ClaimFinding] = Field(min_length=1)


class ApprovalEvidenceAssessment(_EvidenceAssessmentBase):
    evidence_status: Literal[EvidenceStatus.SUFFICIENT_FOR_APPROVAL]


class DeclineEvidenceAssessment(_EvidenceAssessmentBase):
    evidence_status: Literal[EvidenceStatus.SUFFICIENT_FOR_DECLINE]


class InsufficientEvidenceAssessment(_EvidenceAssessmentBase):
    evidence_status: Literal[EvidenceStatus.INSUFFICIENT]
    missing_evidence_request: EvidenceRequest


EvidenceAssessment: TypeAlias = Annotated[
    ApprovalEvidenceAssessment
    | DeclineEvidenceAssessment
    | InsufficientEvidenceAssessment,
    Field(discriminator="evidence_status"),
]


class IntakeResult(ContractModel):
    """Structured output of the parse_request LLM node."""

    completeness: IntakeCompleteness
    order_ref: OpaqueRef | None = None
    reason_code: ReasonCode | None = None
    reason_summary: NonEmptyText | None = None
    requested_action: RequestedAction
    claimed_line_item_ids: list[OpaqueRef] = Field(default_factory=list)
    missing_fields: list[NonEmptyText] = Field(default_factory=list)
    clarification_question: NonEmptyText | None = None

    @model_validator(mode="after")
    def _incomplete_requires_a_question(self) -> "IntakeResult":
        if self.completeness is IntakeCompleteness.INCOMPLETE:
            if not self.missing_fields or self.clarification_question is None:
                raise ValueError(
                    "INCOMPLETE requires missing_fields and clarification_question"
                )
        elif self.missing_fields or self.clarification_question is not None:
            raise ValueError(
                "COMPLETE requires no missing_fields or clarification_question"
            )
        return self


class ClarificationRequest(ContractModel):
    request_id: OpaqueRef
    missing_fields: list[NonEmptyText] = Field(min_length=1)
    clarification_question: NonEmptyText
    clarification_round: PositiveInt


class RefundScope(ContractModel):
    line_item_ids: list[OpaqueRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _line_item_ids_are_unique(self) -> "RefundScope":
        if len(self.line_item_ids) != len(set(self.line_item_ids)):
            raise ValueError("refund_scope.line_item_ids must be unique")
        return self


class NonEmptyRefundScope(RefundScope):
    line_item_ids: list[OpaqueRef] = Field(min_length=1)


class EmptyRefundScope(RefundScope):
    line_item_ids: list[OpaqueRef] = Field(default_factory=list, max_length=0)


class RequiredReturnRequirement(ContractModel):
    required: Literal[True]
    reason_code: RequiredReturnReasonCode


class WaivedReturnRequirement(ContractModel):
    required: Literal[False]
    reason_code: WaivedReturnReasonCode


ReturnRequirement: TypeAlias = Annotated[
    RequiredReturnRequirement | WaivedReturnRequirement,
    Field(discriminator="required"),
]


class PolicyReturnDecisionDraft(ContractModel):
    """Resolver supplies only the reason; graph derives the requirement."""

    source: Literal[ReturnDecisionSource.POLICY]
    reason_code: RequiredReturnReasonCode | WaivedReturnReasonCode


class PolicyReturnDecision(ContractModel):
    source: Literal[ReturnDecisionSource.POLICY]
    requirement: ReturnRequirement


class ModelJudgmentReturnDecision(ContractModel):
    source: Literal[ReturnDecisionSource.MODEL_JUDGMENT]
    requirement: ReturnRequirement


class HumanReviewReturnDecision(ContractModel):
    source: Literal[ReturnDecisionSource.HUMAN_REVIEW]
    requirement: ReturnRequirement


ResolverReturnDecision: TypeAlias = Annotated[
    PolicyReturnDecisionDraft | ModelJudgmentReturnDecision,
    Field(discriminator="source"),
]
AgentReturnDecision: TypeAlias = Annotated[
    PolicyReturnDecision | ModelJudgmentReturnDecision,
    Field(discriminator="source"),
]
ReturnDecision: TypeAlias = Annotated[
    PolicyReturnDecision | ModelJudgmentReturnDecision | HumanReviewReturnDecision,
    Field(discriminator="source"),
]


class FullRefundProposedDecisionDraft(ContractModel):
    action: Literal[ResolutionAction.FULL_REFUND]
    refund_scope: NonEmptyRefundScope
    reason_code: ReasonCode
    return_decision: ResolverReturnDecision
    policy_refs: list[OpaqueRef] = Field(min_length=1)
    evidence_refs: list[OpaqueRef] = Field(default_factory=list)
    rationale_summary: NonEmptyText


class DeclineProposedDecisionDraft(ContractModel):
    action: Literal[ResolutionAction.DECLINE]
    refund_scope: EmptyRefundScope
    reason_code: ReasonCode
    policy_refs: list[OpaqueRef] = Field(min_length=1)
    evidence_refs: list[OpaqueRef] = Field(default_factory=list)
    rationale_summary: NonEmptyText


ProposedDecisionDraft: TypeAlias = Annotated[
    FullRefundProposedDecisionDraft | DeclineProposedDecisionDraft,
    Field(discriminator="action"),
]


class RevisionConflictReport(ContractModel):
    conflicting_reason_codes: list[RevisionReasonCode] = Field(min_length=2)
    conflicting_review_refs: list[OpaqueRef] = Field(min_length=2)
    explanation: NonEmptyText


class FullRefundProposedDecision(ContractModel):
    """Graph-completed refund decision included in a handoff."""

    action: Literal[ResolutionAction.FULL_REFUND]
    refund_scope: NonEmptyRefundScope
    amount: Money
    currency: CurrencyCode
    reason_code: ReasonCode
    return_decision: AgentReturnDecision
    policy_refs: list[OpaqueRef] = Field(min_length=1)
    evidence_refs: list[OpaqueRef] = Field(default_factory=list)


class DeclineProposedDecision(ContractModel):
    action: Literal[ResolutionAction.DECLINE]
    refund_scope: EmptyRefundScope
    amount: ZeroMoney
    currency: CurrencyCode
    reason_code: ReasonCode
    policy_refs: list[OpaqueRef] = Field(min_length=1)
    evidence_refs: list[OpaqueRef] = Field(default_factory=list)


ProposedDecision: TypeAlias = Annotated[
    FullRefundProposedDecision | DeclineProposedDecision,
    Field(discriminator="action"),
]


class ProposedDecisionHandoff(ContractModel):
    handoff_version: Literal["1.0"]
    handoff_id: OpaqueRef
    case_ref: OpaqueRef
    order_snapshot_ref: OpaqueRef
    policy_bundle_version: OpaqueRef
    claim_registry_version: OpaqueRef
    proposed_decision: ProposedDecision
    evidence_bundle: list[EvidenceItem] = Field(default_factory=list)
    policy_refs: list[OpaqueRef] = Field(min_length=1)
    rationale_summary: NonEmptyText
    revision_round: NonNegativeInt
    agent_prompt_version: OpaqueRef

    @model_validator(mode="after")
    def _references_are_consistent(self) -> "ProposedDecisionHandoff":
        evidence_ids = {item.evidence_id for item in self.evidence_bundle}
        if len(evidence_ids) != len(self.evidence_bundle):
            raise ValueError(
                "evidence_bundle must not contain duplicate evidence_id values"
            )
        if not set(self.proposed_decision.evidence_refs).issubset(evidence_ids):
            raise ValueError("decision evidence_refs must exist in evidence_bundle")
        if not set(self.proposed_decision.policy_refs).issubset(self.policy_refs):
            raise ValueError("decision policy_refs must be a handoff-level subset")
        return self


class VerificationIssue(ContractModel):
    code: NonEmptyText
    message: NonEmptyText
    field_path: NonEmptyText


class PassedVerificationResult(ContractModel):
    status: Literal[VerificationStatus.PASS]
    issues: list[VerificationIssue] = Field(default_factory=list, max_length=0)
    verification_version: OpaqueRef


class FailedVerificationResult(ContractModel):
    status: Literal[VerificationStatus.FAIL]
    issues: list[VerificationIssue] = Field(min_length=1)
    verification_version: OpaqueRef


class UnavailableVerificationResult(ContractModel):
    status: Literal[VerificationStatus.UNAVAILABLE]
    issues: list[VerificationIssue] = Field(default_factory=list, max_length=0)
    verification_version: OpaqueRef


VerificationResult: TypeAlias = Annotated[
    PassedVerificationResult | FailedVerificationResult | UnavailableVerificationResult,
    Field(discriminator="status"),
]


class RevisionReason(ContractModel):
    code: RevisionReasonCode
    message: NonEmptyText
    policy_refs: list[OpaqueRef] = Field(default_factory=list)
    evidence_refs: list[OpaqueRef] = Field(default_factory=list)
    subject: OpaqueRef
    required_change: NonEmptyText


class ApprovedReviewResult(ContractModel):
    verdict: Literal[ReviewVerdict.APPROVE]
    reviewer_claim_findings: list[ClaimFinding] = Field(min_length=1)
    revision_reasons: list[RevisionReason] = Field(default_factory=list, max_length=0)
    reviewer_prompt_version: OpaqueRef
    reviewed_at: UTCDateTime


class RevisedReviewResult(ContractModel):
    verdict: Literal[ReviewVerdict.REVISE]
    reviewer_claim_findings: list[ClaimFinding] = Field(min_length=1)
    revision_reasons: list[RevisionReason] = Field(min_length=1)
    reviewer_prompt_version: OpaqueRef
    reviewed_at: UTCDateTime


ReviewResult: TypeAlias = Annotated[
    ApprovedReviewResult | RevisedReviewResult,
    Field(discriminator="verdict"),
]


class DecisionRevisionEvent(ContractModel):
    event_id: OpaqueRef
    case_ref: OpaqueRef
    handoff_before_ref: OpaqueRef
    review_result: ReviewResult
    revision_round: PositiveInt
    created_at: UTCDateTime


class HumanReviewDossier(ContractModel):
    """Immutable, structured decision trace; never model hidden reasoning."""

    claimed_line_item_ids: list[OpaqueRef] = Field(min_length=1)
    claim_registry_version: OpaqueRef
    routing_reason: HumanReviewRoutingReason = "REVISION_BUDGET_EXCEEDED"
    review_gate: ReviewGateResult | None = None
    order_snapshot: OrderSnapshot
    policy_bundle: PolicyBundle
    proposal_history: list[ProposedDecisionHandoff] = Field(min_length=1)
    review_history: list[ReviewResult] = Field(min_length=1)
    revision_events: list[DecisionRevisionEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_trace(self) -> "HumanReviewDossier":
        proposals = self.proposal_history
        if len(proposals) != len(self.review_history):
            raise ValueError("every reviewed proposal requires its review result")
        if len(set(self.claimed_line_item_ids)) != len(self.claimed_line_item_ids):
            raise ValueError("claimed scope must be unique")
        if not set(self.claimed_line_item_ids).issubset(
            item.line_item_id for item in self.order_snapshot.line_items
        ):
            raise ValueError("claimed scope must belong to the order")
        if len({p.handoff_id for p in proposals}) != len(proposals):
            raise ValueError("proposal IDs must be unique")
        if any(p.case_ref != proposals[-1].case_ref for p in proposals):
            raise ValueError("review trace cannot mix cases")
        if len(self.revision_events) != len(proposals) - 1:
            raise ValueError("review trace requires each completed revision event")
        for index, event in enumerate(self.revision_events):
            if (event.handoff_before_ref != proposals[index].handoff_id
                or event.review_result != self.review_history[index]
                or event.case_ref != proposals[-1].case_ref
                or event.revision_round != index + 1
                or event.review_result.verdict is not ReviewVerdict.REVISE):
                raise ValueError("revision event does not match its reviewed proposal")
        for index, proposal in enumerate(proposals):
            if proposal.revision_round != index:
                raise ValueError("dossier revision rounds must start at zero and be contiguous")
            if proposal.policy_bundle_version != self.policy_bundle.policy_bundle_version:
                raise ValueError("dossier policy version mismatch")
            if proposal.order_snapshot_ref != self.order_snapshot.order_snapshot_ref:
                raise ValueError("dossier order snapshot mismatch")
            if proposal.claim_registry_version != self.claim_registry_version:
                raise ValueError("dossier claim registry mismatch")
        return self


class CorrectedFullRefundDecision(ContractModel):
    action: Literal[ResolutionAction.FULL_REFUND]
    refund_scope: NonEmptyRefundScope
    return_decision: HumanReviewReturnDecision


class CorrectedDeclineDecision(ContractModel):
    action: Literal[ResolutionAction.DECLINE]
    refund_scope: EmptyRefundScope


CorrectedDecision: TypeAlias = Annotated[
    CorrectedFullRefundDecision | CorrectedDeclineDecision,
    Field(discriminator="action"),
]


class _HumanReviewResultBase(ContractModel):
    review_note: NonEmptyText
    reviewer_id: OpaqueRef = "demo_reviewer"
    generalizable: bool | None = None
    final_resolution_ref: OpaqueRef
    reviewed_at: UTCDateTime


class ApprovedHumanReviewResult(_HumanReviewResultBase):
    decision: Literal[HumanDecision.APPROVE]


class EditedHumanReviewResult(_HumanReviewResultBase):
    decision: Literal[HumanDecision.EDIT]
    corrected_decision: CorrectedDecision
    correction_reason_code: HumanCorrectionReasonCode


class RejectedHumanReviewResult(_HumanReviewResultBase):
    decision: Literal[HumanDecision.REJECT]


HumanReviewResult: TypeAlias = Annotated[
    ApprovedHumanReviewResult | EditedHumanReviewResult | RejectedHumanReviewResult,
    Field(discriminator="decision"),
]


class FullRefundFinalDecision(ContractModel):
    action: Literal[ResolutionAction.FULL_REFUND]
    refund_scope: NonEmptyRefundScope
    amount: Money
    currency: CurrencyCode
    return_decision: ReturnDecision
    reason_code: ReasonCode


class DeclineFinalDecision(ContractModel):
    action: Literal[ResolutionAction.DECLINE]
    refund_scope: EmptyRefundScope
    amount: ZeroMoney
    currency: CurrencyCode
    reason_code: ReasonCode


FinalDecision: TypeAlias = Annotated[
    FullRefundFinalDecision | DeclineFinalDecision,
    Field(discriminator="action"),
]


class AgentFullRefundFinalDecision(FullRefundFinalDecision):
    """Final refund copied from an Agent-authored approved handoff."""

    return_decision: AgentReturnDecision


class HumanEditedFullRefundFinalDecision(FullRefundFinalDecision):
    """Final refund whose return requirement was authored by Human Review."""

    return_decision: HumanReviewReturnDecision


AgentFinalDecision: TypeAlias = Annotated[
    AgentFullRefundFinalDecision | DeclineFinalDecision,
    Field(discriminator="action"),
]
HumanEditedFinalDecision: TypeAlias = Annotated[
    HumanEditedFullRefundFinalDecision | DeclineFinalDecision,
    Field(discriminator="action"),
]


class _ResolutionHandoffBase(ContractModel):
    review_gate: ReviewGateResult | None = None
    case_ref: OpaqueRef
    handoff_id: OpaqueRef
    emitted_at: UTCDateTime


class ReviewerApprovedResolutionHandoff(_ResolutionHandoffBase):
    outcome_source: Literal[OutcomeSource.REVIEWER_APPROVE]
    final_decision: AgentFinalDecision
    review_result: ApprovedReviewResult
    execution_blocked: Literal[False]


class HumanApproveResolutionHandoff(_ResolutionHandoffBase):
    outcome_source: Literal[OutcomeSource.HUMAN_APPROVE]
    final_decision: AgentFinalDecision
    review_result: ReviewResult
    execution_blocked: Literal[False]


class HumanEditResolutionHandoff(_ResolutionHandoffBase):
    outcome_source: Literal[OutcomeSource.HUMAN_EDIT]
    final_decision: HumanEditedFinalDecision
    review_result: ReviewResult
    execution_blocked: Literal[False]


class HumanRejectResolutionHandoff(_ResolutionHandoffBase):
    outcome_source: Literal[OutcomeSource.HUMAN_REJECT]
    final_decision: DeclineFinalDecision
    review_result: ReviewResult
    execution_blocked: Literal[False]


ResolutionHandoff: TypeAlias = Annotated[
    ReviewerApprovedResolutionHandoff
    | HumanApproveResolutionHandoff
    | HumanEditResolutionHandoff
    | HumanRejectResolutionHandoff,
    Field(discriminator="outcome_source"),
]


class MemoryDistillationInput(ContractModel):
    """Closed-case correction trace consumed by the async memory worker."""

    case_context: CaseContext
    policy_bundle: PolicyBundle
    evidence_assessment: EvidenceAssessment
    proposal_history: list[ProposedDecisionHandoff] = Field(min_length=1)
    revision_events: list[DecisionRevisionEvent] = Field(default_factory=list)
    human_review_result: HumanReviewResult | None = None
    final_resolution: ResolutionHandoff
    claimed_categories: list[OpaqueRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _trace_is_closed_and_consistent(self) -> "MemoryDistillationInput":
        case_ref = self.case_context.case_ref
        if self.final_resolution.case_ref != case_ref:
            raise ValueError("final resolution must match case context")
        if any(proposal.case_ref != case_ref for proposal in self.proposal_history):
            raise ValueError("all proposals must match case context")
        if any(event.case_ref != case_ref for event in self.revision_events):
            raise ValueError("all revision events must match case context")
        proposal_ids = [proposal.handoff_id for proposal in self.proposal_history]
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("proposal history handoff ids must be unique")
        revision_ids = [event.event_id for event in self.revision_events]
        if len(revision_ids) != len(set(revision_ids)):
            raise ValueError("revision event ids must be unique")
        if any(
            event.handoff_before_ref not in proposal_ids
            for event in self.revision_events
        ):
            raise ValueError("every revision event must reference a proposal")
        latest = self.proposal_history[-1]
        if latest.handoff_id != self.final_resolution.handoff_id:
            raise ValueError("final resolution must reference the latest proposal")
        if latest.policy_bundle_version != self.policy_bundle.policy_bundle_version:
            raise ValueError("latest proposal must match the policy bundle")
        if (
            latest.claim_registry_version
            != self.evidence_assessment.claim_registry_version
        ):
            raise ValueError(
                "assessment and latest proposal registry versions must match"
            )
        has_human_correction = isinstance(
            self.human_review_result,
            (EditedHumanReviewResult, RejectedHumanReviewResult),
        )
        if not self.revision_events and not has_human_correction:
            raise ValueError(
                "memory distillation requires a confirmed correction trace"
            )
        expected_human_type = {
            OutcomeSource.HUMAN_APPROVE: ApprovedHumanReviewResult,
            OutcomeSource.HUMAN_EDIT: EditedHumanReviewResult,
            OutcomeSource.HUMAN_REJECT: RejectedHumanReviewResult,
        }.get(self.final_resolution.outcome_source)
        if expected_human_type is None and self.human_review_result is not None:
            raise ValueError("non-human resolution must not carry a human result")
        if expected_human_type is not None and not isinstance(
            self.human_review_result, expected_human_type
        ):
            raise ValueError("human resolution source must match the human result")
        if len(self.claimed_categories) != len(set(self.claimed_categories)):
            raise ValueError("claimed_categories must be unique")
        return self


class AccumulatedEscalationContext(ContractModel):
    clarification_round: NonNegativeInt
    evidence_round: NonNegativeInt
    verification_round: NonNegativeInt
    revision_round: NonNegativeInt
    review_history_refs: list[OpaqueRef] = Field(default_factory=list)
    verification_issues: list[VerificationIssue] = Field(default_factory=list)


class ManualEscalationHandoff(ContractModel):
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    escalation_reason: EscalationReason
    last_known_handoff_ref: OpaqueRef | None = None
    accumulated_context: AccumulatedEscalationContext
    created_at: UTCDateTime


class MemoryScope(ContractModel):
    market: NonEmptyText
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    claim_ids: list[ClaimId] = Field(default_factory=list)
    categories: list[OpaqueRef] = Field(default_factory=list)


class MemoryCandidate(ContractModel):
    memory_id: OpaqueRef
    retrieval_summary: NonEmptyText = Field(max_length=2000)
    trigger_conditions: list[NonEmptyText] = Field(min_length=1)
    recommended_behavior: NonEmptyText
    rationale: NonEmptyText
    source_case_refs: list[OpaqueRef] = Field(min_length=1)
    source_revision_event_refs: list[OpaqueRef] = Field(min_length=1)
    policy_version: OpaqueRef
    claim_registry_version: OpaqueRef
    scope: MemoryScope
    confidence: UnitInterval
    status: Literal[MemoryStatus.CANDIDATE]


class ApprovedMemory(ContractModel):
    memory_id: OpaqueRef
    retrieval_summary: NonEmptyText = Field(max_length=2000)
    status: Literal[MemoryStatus.APPROVED]
    recommended_behavior: NonEmptyText
    trigger_conditions: list[NonEmptyText] = Field(min_length=1)
    policy_version: OpaqueRef
    claim_registry_version: OpaqueRef
    scope: MemoryScope
    confidence: UnitInterval
    approved_at: UTCDateTime


class MemoryQuerySummary(ContractModel):
    query_summary: NonEmptyText = Field(max_length=2000)


class MemorySearchHit(ContractModel):
    memory: ApprovedMemory
    similarity: float = Field(ge=-1, le=1, allow_inf_nan=False)


class MemoryRetrievalObservation(ContractModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"status": {"const": "OK"}},
                        "required": ["status"],
                    },
                    "then": {
                        "required": ["query_summary"],
                        "properties": {
                            "query_summary": {"type": "string", "minLength": 1},
                            "error_code": {"type": "null"},
                        },
                    },
                    "else": {
                        "required": ["error_code"],
                        "properties": {
                            "error_code": {"type": "string"},
                            "hits": {"maxItems": 0},
                        },
                    },
                }
            ]
        }
    )
    status: Literal["OK", "UNAVAILABLE"]
    query_summary: NonEmptyText | None = Field(default=None, max_length=2000)
    hits: list[MemorySearchHit] = Field(default_factory=list, max_length=3)
    error_code: Literal["SUMMARY_UNAVAILABLE", "RETRIEVAL_UNAVAILABLE"] | None = None

    @model_validator(mode="after")
    def _status_matches_result(self) -> "MemoryRetrievalObservation":
        if self.status == "OK" and (
            self.query_summary is None or self.error_code is not None
        ):
            raise ValueError("successful retrieval requires a query and no error")
        if self.status == "UNAVAILABLE" and (self.hits or self.error_code is None):
            raise ValueError("unavailable retrieval requires an error and no hits")
        ids = [hit.memory.memory_id for hit in self.hits]
        if len(ids) != len(set(ids)):
            raise ValueError("memory retrieval cannot repeat a memory ID")
        return self


class ResolverDraftOutput(ContractModel):
    result_type: Literal[ResolverResultType.DRAFT]
    draft: ProposedDecisionDraft


class ResolverEvidenceRequestOutput(ContractModel):
    result_type: Literal[ResolverResultType.REQUEST_EVIDENCE]
    evidence_request: EvidenceRequest


class ResolverConflictOutput(ContractModel):
    result_type: Literal[ResolverResultType.CONFLICTING_REVISIONS]
    conflict: RevisionConflictReport


ResolverOutput: TypeAlias = Annotated[
    ResolverDraftOutput | ResolverEvidenceRequestOutput | ResolverConflictOutput,
    Field(discriminator="result_type"),
]


class MemoryCandidateOutput(ContractModel):
    result_type: Literal[MemoryDistillationResultType.CREATE_CANDIDATE]
    candidate: MemoryCandidate


class MemorySkipOutput(ContractModel):
    result_type: Literal[MemoryDistillationResultType.SKIP]
    reason_code: MemorySkipReasonCode


MemoryDistillationOutput: TypeAlias = Annotated[
    MemoryCandidateOutput | MemorySkipOutput,
    Field(discriminator="result_type"),
]


class ExecuteRefundRequest(ContractModel):
    """Trusted Backend request to execute an authorized final resolution."""

    resolution_handoff: ResolutionHandoff


class AppliedRefundApplicationResult(ContractModel):
    """Allen's canonical order/case system applied the refund exactly once."""

    status: Literal[RefundApplicationStatus.APPLIED]
    application_ref: OpaqueRef
    applied_at: UTCDateTime


class RejectedRefundApplicationResult(ContractModel):
    """Allen's canonical order/case system refused the refund mutation."""

    status: Literal[RefundApplicationStatus.REJECTED]
    reason_codes: list[NonEmptyText] = Field(min_length=1)
    rejected_at: UTCDateTime


RefundApplicationResult: TypeAlias = Annotated[
    AppliedRefundApplicationResult | RejectedRefundApplicationResult,
    Field(discriminator="status"),
]


class ApplyRefundRequest(ContractModel):
    """Louis-to-Allen idempotent canonical refund application request."""

    execution_ref: OpaqueRef
    resolution_handoff: ResolutionHandoff


class SucceededRefundExecutionRecord(ContractModel):
    execution_ref: OpaqueRef
    handoff_id: OpaqueRef
    case_ref: OpaqueRef
    status: Literal[RefundExecutionStatus.SUCCEEDED]
    application_result: AppliedRefundApplicationResult
    created_at: UTCDateTime
    updated_at: UTCDateTime


class RejectedRefundExecutionRecord(ContractModel):
    execution_ref: OpaqueRef
    handoff_id: OpaqueRef
    case_ref: OpaqueRef
    status: Literal[RefundExecutionStatus.REJECTED]
    application_result: RejectedRefundApplicationResult
    created_at: UTCDateTime
    updated_at: UTCDateTime


RefundExecutionRecord: TypeAlias = Annotated[
    SucceededRefundExecutionRecord | RejectedRefundExecutionRecord,
    Field(discriminator="status"),
]
